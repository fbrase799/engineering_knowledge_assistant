"""API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.src.retrieval.models import AskResponse, RetrievalMode


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID


class HealthResponse(BaseModel):
    status: str
    version: str
    faiss_ready: bool
    azure_configured: bool
    tavily_configured: bool
    langsmith_tracing: bool


class ExampleQuestion(BaseModel):
    label: str
    question: str
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID


class ExamplesResponse(BaseModel):
    examples: list[ExampleQuestion]


# Re-export for OpenAPI
__all__ = [
    "AskRequest",
    "AskResponse",
    "HealthResponse",
    "ExampleQuestion",
    "ExamplesResponse",
]
