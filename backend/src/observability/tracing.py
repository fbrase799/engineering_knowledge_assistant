"""LangSmith tracing setup and sanitized execution event helpers."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.src.config import Settings
from backend.src.retrieval.models import ExecutionEvent


def configure_langsmith(settings: Settings) -> None:
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


def new_event(
    node: str,
    status: str,
    message: str,
    *,
    branch: str | None = None,
    duration_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> ExecutionEvent:
    safe_details = sanitize_details(details or {})
    return ExecutionEvent(
        event_id=str(uuid.uuid4()),
        node=node,
        status=status,  # type: ignore[arg-type]
        branch=branch,
        message=message,
        duration_ms=duration_ms,
        details=safe_details,
        timestamp=datetime.now(UTC),
    )


_FORBIDDEN_DETAIL_KEYS = {
    "api_key",
    "authorization",
    "token",
    "password",
    "secret",
    "azure_openai_api_key",
    "tavily_api_key",
    "langsmith_api_key",
}


def sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in details.items():
        lower = key.lower()
        if any(part in lower for part in _FORBIDDEN_DETAIL_KEYS):
            continue
        if isinstance(value, str) and len(value) > 500:
            cleaned[key] = value[:500] + "…"
        else:
            cleaned[key] = value
    return cleaned


class NodeTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)
