"""Tavily search integration with hard call budgets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from backend.src.config import Settings
from backend.src.retrieval.models import WebSource


class TavilyClientProtocol(Protocol):
    def search(self, query: str, *, max_results: int, search_depth: str) -> list[WebSource]:
        ...


class TavilyClient:
    """Thin wrapper that never accepts document excerpts as search context."""

    def __init__(self, settings: Settings, client: Any | None = None):
        self._settings = settings
        self._client = client
        self.call_count = 0

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._settings.tavily_api_key:
            raise RuntimeError("Tavily API key is not configured")
        from tavily import TavilyClient as OfficialTavilyClient

        self._client = OfficialTavilyClient(api_key=self._settings.tavily_api_key)
        return self._client

    def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        search_depth: str | None = None,
    ) -> list[WebSource]:
        """Run at most the caller-enforced single search; payload is query-only."""
        limit = min(
            max_results if max_results is not None else self._settings.tavily_max_results,
            3,
        )
        depth = search_depth or self._settings.tavily_search_depth
        client = self._ensure_client()
        self.call_count += 1
        # Explicit payload: never include retrieved document excerpts.
        payload = {
            "query": query,
            "max_results": limit,
            "search_depth": depth,
            "include_answer": False,
            "include_raw_content": False,
        }
        response = client.search(**payload)
        retrieved_at = datetime.now(UTC)
        results: list[WebSource] = []
        for index, item in enumerate(response.get("results", [])[:limit]):
            results.append(
                WebSource(
                    source_id=f"web-{index + 1}",
                    title=item.get("title") or "Untitled",
                    url=item.get("url") or "",
                    snippet=item.get("content") or item.get("snippet") or "",
                    retrieved_at=retrieved_at,
                    published_at=item.get("published_date"),
                )
            )
        return results


class RecordingTavilyClient(TavilyClient):
    """Test double that records payloads and returns canned results."""

    def __init__(self, results: list[WebSource] | None = None, *, fail: bool = False):
        self.results = results or []
        self.fail = fail
        self.payloads: list[dict[str, Any]] = []
        self.call_count = 0

    def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        search_depth: str | None = None,
    ) -> list[WebSource]:
        limit = min(max_results if max_results is not None else 3, 3)
        payload = {
            "query": query,
            "max_results": limit,
            "search_depth": search_depth or "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        self.payloads.append(payload)
        self.call_count += 1
        if self.fail:
            raise RuntimeError("simulated Tavily failure")
        return self.results[:limit]
