"""LangGraph state schema."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from backend.src.retrieval.models import (
    EvidenceStatus,
    ExecutionEvent,
    LocalSource,
    RetrievalMode,
    UsageMetrics,
    WebSource,
)


def _merge_events(
    existing: list[ExecutionEvent],
    new: list[ExecutionEvent],
) -> list[ExecutionEvent]:
    return existing + new


class GraphState(TypedDict, total=False):
    request_id: str
    question: str
    retrieval_mode: RetrievalMode
    local_sources: list[LocalSource]
    web_sources: list[WebSource]
    selected_context: str
    local_evidence_status: EvidenceStatus
    web_evidence_status: EvidenceStatus
    overall_evidence_status: EvidenceStatus
    answer: str
    sections: dict[str, Any]
    citations: list[dict[str, Any]]
    citation_ids: list[str]
    comparison_status: str
    execution_events: Annotated[list[ExecutionEvent], _merge_events]
    usage_metrics: UsageMetrics
    error: str | None
    langsmith_run_id: str | None
