"""Shared retrieval and answer data models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievalMode(StrEnum):
    HYBRID = "hybrid"
    LOCAL = "local"
    WEB = "web"


class EvidenceStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    NOT_REQUESTED = "not_requested"


class LocalSource(BaseModel):
    source_id: str
    doc_id: str
    title: str
    section: str
    version: str
    content: str
    score: float
    provenance: str = "sample_documents"


class WebSource(BaseModel):
    source_id: str
    title: str
    url: str
    snippet: str
    retrieved_at: datetime
    published_at: str | None = None


class Citation(BaseModel):
    source_id: str
    source_type: Literal["document", "web"]
    label: str
    reference: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageMetrics(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    cost_status: Literal["estimated", "unavailable"] = "unavailable"
    tavily_calls: int = 0
    llm_calls: int = 0
    local_chunk_count: int = 0
    web_result_count: int = 0


class ExecutionEvent(BaseModel):
    event_id: str
    node: str
    status: Literal["started", "succeeded", "skipped", "failed"]
    branch: str | None = None
    message: str
    duration_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class ComparisonSections(BaseModel):
    documented_approach: str | None = None
    web_findings: str | None = None
    comparison: str | None = None
    engineering_implications: str | None = None
    evidence_gap_message: str | None = None


class AskResponse(BaseModel):
    request_id: str
    question: str
    retrieval_mode: RetrievalMode
    comparison_status: Literal[
        "full",
        "partial_local_only",
        "partial_web_only",
        "evidence_gap",
        "local_only",
        "web_only",
    ]
    answer_markdown: str
    sections: ComparisonSections
    citations: list[Citation]
    local_sources: list[LocalSource]
    web_sources: list[WebSource]
    local_evidence_status: EvidenceStatus
    web_evidence_status: EvidenceStatus
    overall_evidence_status: EvidenceStatus
    execution_events: list[ExecutionEvent]
    usage_metrics: UsageMetrics
    langsmith_run_id: str | None = None
    duration_ms: float
    error: str | None = None
