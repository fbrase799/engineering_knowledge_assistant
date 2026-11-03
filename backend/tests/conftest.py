"""Shared fixtures with mocked Tavily / Azure clients."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import create_app
from backend.src.config import Settings
from backend.src.graph.workflow import AssistantGraph
from backend.src.integrations.azure_openai import RecordingLLMClient
from backend.src.integrations.tavily_client import RecordingTavilyClient
from backend.src.retrieval.models import (
    ComparisonSections,
    LocalSource,
    WebSource,
)
from backend.src.retrieval.retriever import SharedRetriever


class FakeRetriever(SharedRetriever):
    def __init__(self, sources: list[LocalSource] | None = None):
        self._sources = sources or []
        self.queries: list[str] = []

    def search(self, question: str, **kwargs) -> list[LocalSource]:  # type: ignore[override]
        self.queries.append(question)
        return list(self._sources)


@pytest.fixture
def local_sources() -> list[LocalSource]:
    return [
        LocalSource(
            source_id="REF-ARCH-001#chunk-1",
            doc_id="REF-ARCH-001",
            title="Sensor Monitoring Reference Architecture",
            section="Timeout strategy",
            version="1.2",
            content=(
                "The gateway supervisor uses a two-tier timeout: Healthy within 30 seconds, "
                "Degraded at 30-90 seconds, Offline after 90 seconds."
            ),
            score=0.91,
        ),
        LocalSource(
            source_id="SPEC-HB-010#chunk-1",
            doc_id="SPEC-HB-010",
            title="Watchdog and Heartbeat Specification",
            section="Timing parameters",
            version="1.1",
            content="Heartbeat interval is 10 seconds. Offline threshold is 90 seconds.",
            score=0.88,
        ),
    ]


@pytest.fixture
def web_sources() -> list[WebSource]:
    return [
        WebSource(
            source_id="web-1",
            title="Linux Watchdog Driver Documentation",
            url="https://example.com/linux-watchdog",
            snippet=(
                "Software watchdogs often recommend a hardware fallback reset and careful "
                "timeout margins to avoid false triggers."
            ),
            retrieved_at=datetime.now(UTC),
        ),
        WebSource(
            source_id="web-2",
            title="Embedded Heartbeat Patterns",
            url="https://example.com/heartbeat-patterns",
            snippet=(
                "Prefer dedicated heartbeat channels over inferring "
                "liveness from telemetry alone."
            ),
            retrieved_at=datetime.now(UTC),
        ),
    ]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        faiss_index_dir=tmp_path / "faiss",
        sample_docs_dir=tmp_path / "docs",
        azure_openai_api_key="test-key",
        azure_openai_endpoint="https://example.openai.azure.com/",
        tavily_api_key="tvly-test",
        langsmith_tracing=False,
        rate_limit_per_minute=1000,
    )


@pytest.fixture
def make_graph(local_sources, web_sources, settings):
    def _make(
        *,
        local: list[LocalSource] | None = None,
        web: list[WebSource] | None = None,
        tavily_fail: bool = False,
        llm_fail: bool = False,
        citation_ids: list[str] | None = None,
    ) -> tuple[AssistantGraph, FakeRetriever, RecordingTavilyClient, RecordingLLMClient]:
        retriever = FakeRetriever(local if local is not None else local_sources)
        tavily = RecordingTavilyClient(
            web if web is not None else web_sources,
            fail=tavily_fail,
        )
        llm = RecordingLLMClient(
            sections=ComparisonSections(
                documented_approach="Documents specify 30s/90s timeouts.",
                web_findings="Public guidance emphasizes hardware fallback.",
                comparison="Both value explicit heartbeats; web stresses hardware reset.",
                engineering_implications=(
                    "Consider documenting hardware watchdog policy. (proposal)"
                ),
            ),
            answer_markdown=(
                "## Documented approach\n30s/90s timeouts.\n\n"
                "## Web findings\nHardware fallback recommended.\n\n"
                "## Comparison\nAgree on dedicated heartbeats.\n\n"
                "## Engineering implications\n(proposal) Review hardware reset policy."
            ),
            citation_ids=citation_ids,
            fail=llm_fail,
        )
        graph = AssistantGraph(
            settings=settings,
            retriever=retriever,  # type: ignore[arg-type]
            tavily=tavily,
            llm=llm,
        )
        return graph, retriever, tavily, llm

    return _make


@pytest.fixture
def client(make_graph, settings):
    graph, *_ = make_graph()
    app = create_app(settings=settings, graph=graph)
    with TestClient(app) as test_client:
        yield test_client, graph
