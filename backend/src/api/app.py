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
from backend.src.graph.workflow import AssistantGraph, build_assistant_graph, get_graph_mermaid
from backend.src.observability.tracing import configure_langsmith
from backend.src.retrieval.corpus_catalog import build_corpus_catalog
from backend.src.retrieval.models import (
    AskResponse,
    ComparisonSections,
    RetrievalMode,
    UsageMetrics,
)
from backend.src.retrieval.retriever import get_shared_retriever, reset_shared_retriever

EXAMPLE_QUESTIONS = [
    # Hybrid — compare / combine curated knowledge with public web findings
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
        label="Compare alerting",
        question=(
            "How does our Offline paging and flapping suppression policy compare with "
            "common practices in current public SRE / observability guidance?"
        ),
        retrieval_mode=RetrievalMode.HYBRID,
    ),
    ExampleQuestion(
        label="Recovery vs public guidance",
        question=(
            "Our runbook returns Offline devices through a Degraded anti-flap window. "
            "What do current public sources recommend for recovery after watchdog or "
            "heartbeat failures?"
        ),
        retrieval_mode=RetrievalMode.HYBRID,
    ),
    ExampleQuestion(
        label="Evidence gap",
        question=(
            "How does our architecture comply with ISO 26262 ASIL-D for braking systems?"
        ),
        retrieval_mode=RetrievalMode.HYBRID,
    ),
    # Local — curated engineering knowledge only
    ExampleQuestion(
        label="Timeout thresholds",
        question=(
            "What timeout thresholds and fallback states are specified in the sample architecture?"
        ),
        retrieval_mode=RetrievalMode.LOCAL,
    ),
    ExampleQuestion(
        label="Heartbeat decision",
        question=(
            "Why did we choose a dedicated heartbeat monitor instead of measurement-only "
            "liveness, and what was rejected?"
        ),
        retrieval_mode=RetrievalMode.LOCAL,
    ),
    ExampleQuestion(
        label="Alert escalation",
        question=(
            "What severity, channels, and escalation timings apply when a device goes Offline?"
        ),
        retrieval_mode=RetrievalMode.LOCAL,
    ),
    ExampleQuestion(
        label="Offline recovery steps",
        question=(
            "According to the gateway runbook, what steps restore a device after Offline, "
            "and how does the anti-flap rule work?"
        ),
        retrieval_mode=RetrievalMode.LOCAL,
    ),
    ExampleQuestion(
        label="Test acceptance",
        question=(
            "Which fault-injection and regression scenarios does the test strategy require "
            "for heartbeat gaps?"
        ),
        retrieval_mode=RetrievalMode.LOCAL,
    ),
    # Web — public sources only
    ExampleQuestion(
        label="Embedded Linux watchdogs",
        question=(
            "What do current official sources say about watchdog strategies on embedded Linux?"
        ),
        retrieval_mode=RetrievalMode.WEB,
    ),
    ExampleQuestion(
        label="Hardware vs software watchdog",
        question=(
            "What do recent public technical docs recommend when choosing between hardware "
            "and software watchdogs on edge devices?"
        ),
        retrieval_mode=RetrievalMode.WEB,
    ),
    ExampleQuestion(
        label="Heartbeat best practices",
        question=(
            "What current public guidance exists for heartbeat intervals and missed-heartbeat "
            "detection in distributed edge systems?"
        ),
        retrieval_mode=RetrievalMode.WEB,
    ),
    ExampleQuestion(
        label="Flapping and alert noise",
        question=(
            "What do current SRE or monitoring sources recommend for suppressing flapping "
            "alerts without hiding real outages?"
        ),
        retrieval_mode=RetrievalMode.WEB,
    ),
    ExampleQuestion(
        label="systemd watchdog",
        question=(
            "What do current official systemd or Linux documentation sources say about "
            "service watchdog and KeepAlive features?"
        ),
        retrieval_mode=RetrievalMode.WEB,
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
            llm_configured=settings.llm_configured,
            llm_provider=settings.resolved_llm_provider,
            openai_configured=settings.openai_configured,
            azure_configured=settings.azure_configured,
            tavily_configured=settings.tavily_configured,
            langsmith_tracing=settings.langsmith_tracing and bool(settings.langsmith_api_key),
        )

    @app.get("/api/examples", response_model=ExamplesResponse)
    def examples() -> ExamplesResponse:
        return ExamplesResponse(examples=EXAMPLE_QUESTIONS)

    @app.get("/api/corpus")
    def corpus() -> dict[str, Any]:
        return build_corpus_catalog(settings.sample_docs_dir, settings.faiss_index_dir)

    @app.get("/api/graph")
    def graph_diagram() -> dict[str, str]:
        assistant: AssistantGraph = state["graph"]
        return {
            "format": "mermaid",
            "mermaid": get_graph_mermaid(assistant),
        }

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

