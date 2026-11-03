"""FastAPI application: REST + SSE for the engineering knowledge assistant."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from backend.src.api.rate_limit import RateLimiter
from backend.src.api.schemas import (
    AskRequest,
    ExampleQuestion,
    ExamplesResponse,
    HealthResponse,
)
from backend.src.config import Settings, get_settings
from backend.src.graph.workflow import AssistantGraph, build_assistant_graph
from backend.src.observability.tracing import configure_langsmith
from backend.src.retrieval.models import (
    AskResponse,
    ComparisonSections,
    RetrievalMode,
    UsageMetrics,
)
from backend.src.retrieval.retriever import get_shared_retriever, reset_shared_retriever
from backend.src.retrieval.store import load_corpus_metadata

EXAMPLE_QUESTIONS = [
    ExampleQuestion(
        label="Compare timeouts",
        question=(
            "How does the sensor timeout handling described in our reference architecture "
            "compare with current watchdog recommendations for embedded systems?"
        ),
        retrieval_mode=RetrievalMode.HYBRID,
    ),
    ExampleQuestion(
        label="Combine failure detection",
        question=(
            "Our design uses a heartbeat monitor. What additional failure-detection "
            "considerations are suggested by recent public technical guidance?"
        ),
        retrieval_mode=RetrievalMode.HYBRID,
    ),
    ExampleQuestion(
        label="Understand local thresholds",
        question=(
            "What timeout thresholds and fallback states are specified in the sample architecture?"
        ),
        retrieval_mode=RetrievalMode.LOCAL,
    ),
    ExampleQuestion(
        label="Research public watchdogs",
        question=(
            "What do current official sources say about watchdog strategies on embedded Linux?"
        ),
        retrieval_mode=RetrievalMode.WEB,
    ),
    ExampleQuestion(
        label="Evidence gap",
        question=(
            "How does our architecture comply with ISO 26262 ASIL-D for braking systems?"
        ),
        retrieval_mode=RetrievalMode.HYBRID,
    ),
]


def create_app(
    *,
    settings: Settings | None = None,
    graph: AssistantGraph | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_langsmith(settings)
    rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    state: dict[str, Any] = {"graph": graph, "settings": settings}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["graph"] is None:
            # Load FAISS at startup when available; tests may inject a graph.
            try:
                get_shared_retriever()
            except FileNotFoundError:
                pass
            state["graph"] = build_assistant_graph(settings=settings)
        yield
        reset_shared_retriever()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def _enforce_rate_limit(request: Request) -> None:
        if not rate_limiter.allow(_client_key(request)):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    def _run_graph(payload: AskRequest, request_id: str) -> AskResponse:
        assistant: AssistantGraph = state["graph"]
        started = time.perf_counter()
        result = assistant.invoke(
            {
                "request_id": request_id,
                "question": payload.question,
                "retrieval_mode": payload.retrieval_mode,
            }
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        sections = ComparisonSections(**(result.get("sections") or {}))
        usage = result.get("usage_metrics") or UsageMetrics()
        if isinstance(usage, dict):
            usage = UsageMetrics(**usage)
        return AskResponse(
            request_id=request_id,
            question=payload.question,
            retrieval_mode=payload.retrieval_mode,
            comparison_status=result.get("comparison_status", "evidence_gap"),
            answer_markdown=result.get("answer") or "",
            sections=sections,
            citations=result.get("citations") or [],
            local_sources=result.get("local_sources") or [],
            web_sources=result.get("web_sources") or [],
            local_evidence_status=result.get("local_evidence_status"),
            web_evidence_status=result.get("web_evidence_status"),
            overall_evidence_status=result.get("overall_evidence_status"),
            execution_events=result.get("execution_events") or [],
            usage_metrics=usage,
            langsmith_run_id=result.get("langsmith_run_id"),
            duration_ms=duration_ms,
            error=result.get("error"),
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        faiss_ready = (settings.faiss_index_dir / "index.faiss").exists()
        return HealthResponse(
            status="ok",
            version=settings.app_version,
            faiss_ready=faiss_ready,
            azure_configured=settings.azure_configured,
            tavily_configured=settings.tavily_configured,
            langsmith_tracing=settings.langsmith_tracing and bool(settings.langsmith_api_key),
        )

    @app.get("/api/examples", response_model=ExamplesResponse)
    def examples() -> ExamplesResponse:
        return ExamplesResponse(examples=EXAMPLE_QUESTIONS)

    @app.get("/api/corpus")
    def corpus() -> dict[str, Any]:
        return load_corpus_metadata(settings.faiss_index_dir)

    @app.post("/api/ask", response_model=AskResponse)
    def ask(payload: AskRequest, request: Request) -> AskResponse:
        _enforce_rate_limit(request)
        if not payload.question.strip():
            raise HTTPException(status_code=400, detail="Question must not be empty")
        request_id = str(uuid.uuid4())
        return _run_graph(payload, request_id)

    @app.post("/api/ask/stream")
    async def ask_stream(payload: AskRequest, request: Request) -> EventSourceResponse:
        _enforce_rate_limit(request)
        request_id = str(uuid.uuid4())

        async def event_generator() -> AsyncIterator[dict[str, str]]:
            started = {
                "request_id": request_id,
                "retrieval_mode": payload.retrieval_mode.value,
            }
            yield {"event": "started", "data": json.dumps(started)}
            try:
                response = await asyncio.to_thread(_run_graph, payload, request_id)
                for event in response.execution_events:
                    yield {
                        "event": "node",
                        "data": event.model_dump_json(),
                    }
                    await asyncio.sleep(0)
                yield {
                    "event": "result",
                    "data": response.model_dump_json(),
                }
            except Exception as exc:  # noqa: BLE001
                yield {
                    "event": "error",
                    "data": json.dumps({"request_id": request_id, "error": str(exc)}),
                }

        return EventSourceResponse(event_generator())

    return app


app = create_app()
