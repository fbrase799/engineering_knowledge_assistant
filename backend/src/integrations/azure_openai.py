"""Azure OpenAI generation client with a hard one-call budget."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from backend.src.config import Settings
from backend.src.retrieval.models import (
    Citation,
    ComparisonSections,
    LocalSource,
    RetrievalMode,
    UsageMetrics,
    WebSource,
)

ANSWER_SCHEMA_HINT = """
Return ONLY valid JSON with this shape:
{
  "documented_approach": string|null,
  "web_findings": string|null,
  "comparison": string|null,
  "engineering_implications": string|null,
  "answer_markdown": string,
  "citation_ids": string[]
}
Rules:
- Distinguish documented facts from interpretation.
- Mark recommendations as proposals/tradeoffs, never as verified compliance.
- Use only provided source_id values in citation_ids.
- Do not invent document sections, URLs, standards, or dates.
"""


class LLMClientProtocol(Protocol):
    def generate(
        self,
        *,
        question: str,
        mode: RetrievalMode,
        local_sources: list[LocalSource],
        web_sources: list[WebSource],
    ) -> tuple[ComparisonSections, str, list[str], UsageMetrics]:
        ...


class AzureOpenAIClient:
    def __init__(self, settings: Settings, client: Any | None = None):
        self._settings = settings
        self._client = client
        self.call_count = 0
        self.last_prompt: str | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._settings.azure_configured:
            raise RuntimeError("Azure OpenAI is not configured")
        from langchain_openai import AzureChatOpenAI

        self._client = AzureChatOpenAI(
            azure_endpoint=self._settings.azure_openai_endpoint,
            api_key=self._settings.azure_openai_api_key,
            api_version=self._settings.azure_openai_api_version,
            azure_deployment=self._settings.azure_openai_deployment,
            temperature=self._settings.azure_openai_temperature,
            max_tokens=self._settings.azure_openai_max_tokens,
        )
        return self._client

    def generate(
        self,
        *,
        question: str,
        mode: RetrievalMode,
        local_sources: list[LocalSource],
        web_sources: list[WebSource],
    ) -> tuple[ComparisonSections, str, list[str], UsageMetrics]:
        prompt = build_generation_prompt(question, mode, local_sources, web_sources)
        self.last_prompt = prompt
        client = self._ensure_client()
        self.call_count += 1
        response = client.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        usage = extract_usage(response, self._settings)
        usage.llm_calls = 1  # this request only; graph aggregates per invocation
        parsed = parse_llm_json(content if isinstance(content, str) else str(content))
        sections = ComparisonSections(
            documented_approach=parsed.get("documented_approach"),
            web_findings=parsed.get("web_findings"),
            comparison=parsed.get("comparison"),
            engineering_implications=parsed.get("engineering_implications"),
        )
        answer = parsed.get("answer_markdown") or content
        citation_ids = [str(x) for x in parsed.get("citation_ids", [])]
        return sections, answer, citation_ids, usage


class RecordingLLMClient(AzureOpenAIClient):
    def __init__(
        self,
        *,
        sections: ComparisonSections | None = None,
        answer_markdown: str = "Test answer",
        citation_ids: list[str] | None = None,
        usage: UsageMetrics | None = None,
        fail: bool = False,
    ):
        self.sections = sections or ComparisonSections(
            documented_approach="Local evidence summary.",
            web_findings="Web evidence summary.",
            comparison="They partially agree.",
            engineering_implications="Consider reviewing thresholds. (proposal)",
        )
        self.answer_markdown = answer_markdown
        self.citation_ids = citation_ids or []
        self.usage = usage or UsageMetrics(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.0001,
            cost_status="estimated",
            llm_calls=1,
        )
        self.fail = fail
        self.call_count = 0
        self.last_prompt: str | None = None
        self.prompts: list[str] = []

    def generate(
        self,
        *,
        question: str,
        mode: RetrievalMode,
        local_sources: list[LocalSource],
        web_sources: list[WebSource],
    ) -> tuple[ComparisonSections, str, list[str], UsageMetrics]:
        prompt = build_generation_prompt(question, mode, local_sources, web_sources)
        self.last_prompt = prompt
        self.prompts.append(prompt)
        self.call_count += 1
        if self.fail:
            raise RuntimeError("simulated Azure OpenAI failure")
        ids = self.citation_ids or (
            [s.source_id for s in local_sources] + [s.source_id for s in web_sources]
        )
        usage = self.usage.model_copy(deep=True)
        usage.llm_calls = 1
        return self.sections, self.answer_markdown, ids, usage


def build_generation_prompt(
    question: str,
    mode: RetrievalMode,
    local_sources: list[LocalSource],
    web_sources: list[WebSource],
) -> str:
    local_block = "\n\n".join(
        (
            f"[{src.source_id}] doc_id={src.doc_id} title={src.title} "
            f"section={src.section} version={src.version}\n{src.content}"
        )
        for src in local_sources
    ) or "(none)"
    web_block = "\n\n".join(
        (
            f"[{src.source_id}] title={src.title} url={src.url} "
            f"retrieved_at={src.retrieved_at.isoformat()}\n{src.snippet}"
        )
        for src in web_sources
    ) or "(none)"

    mode_instructions = {
        RetrievalMode.HYBRID: (
            "Compare and synthesize local documentation with web findings. "
            "Populate documented_approach, web_findings, comparison, and "
            "engineering_implications. If one side is missing, say so."
        ),
        RetrievalMode.LOCAL: (
            "Explain using local documentation only. Leave web_findings and "
            "comparison null unless briefly noting web was not requested."
        ),
        RetrievalMode.WEB: (
            "Summarize current public sources only. Leave documented_approach "
            "and comparison null unless briefly noting local corpus was not queried."
        ),
    }

    return (
        f"You are an engineering decision-support assistant.\n"
        f"Retrieval mode: {mode.value}\n"
        f"{mode_instructions[mode]}\n\n"
        f"Question:\n{question}\n\n"
        f"LOCAL DOCUMENT EXCERPTS:\n{local_block}\n\n"
        f"WEB RESULTS:\n{web_block}\n\n"
        f"{ANSWER_SCHEMA_HINT}"
    )


def parse_llm_json(content: str) -> dict[str, Any]:
    content = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fence:
        content = fence.group(1)
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {
        "documented_approach": None,
        "web_findings": None,
        "comparison": None,
        "engineering_implications": None,
        "answer_markdown": content,
        "citation_ids": [],
    }


def extract_usage(response: Any, settings: Settings) -> UsageMetrics:
    meta = getattr(response, "usage_metadata", None) or {}
    input_tokens = meta.get("input_tokens")
    output_tokens = meta.get("output_tokens")
    total_tokens = meta.get("total_tokens")
    if input_tokens is None and hasattr(response, "response_metadata"):
        token_usage = response.response_metadata.get("token_usage") or {}
        input_tokens = token_usage.get("prompt_tokens")
        output_tokens = token_usage.get("completion_tokens")
        total_tokens = token_usage.get("total_tokens")

    estimated = None
    status: str = "unavailable"
    if input_tokens is not None and output_tokens is not None:
        estimated = (
            (input_tokens / 1000.0) * settings.estimated_input_cost_per_1k
            + (output_tokens / 1000.0) * settings.estimated_output_cost_per_1k
        )
        status = "estimated"
    return UsageMetrics(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated,
        cost_status=status,  # type: ignore[arg-type]
    )


def build_citations(
    local_sources: list[LocalSource],
    web_sources: list[WebSource],
    citation_ids: list[str],
) -> list[Citation]:
    local_map = {s.source_id: s for s in local_sources}
    web_map = {s.source_id: s for s in web_sources}
    citations: list[Citation] = []
    seen: set[str] = set()
    for cid in citation_ids:
        if cid in seen:
            continue
        if cid in local_map:
            src = local_map[cid]
            citations.append(
                Citation(
                    source_id=cid,
                    source_type="document",
                    label=f"{src.title} — {src.section}",
                    reference=f"{src.doc_id} / {src.section} (v{src.version})",
                    metadata={"doc_id": src.doc_id, "score": src.score},
                )
            )
            seen.add(cid)
        elif cid in web_map:
            src = web_map[cid]
            citations.append(
                Citation(
                    source_id=cid,
                    source_type="web",
                    label=src.title,
                    reference=src.url,
                    metadata={
                        "retrieved_at": src.retrieved_at.isoformat(),
                        "published_at": src.published_at,
                    },
                )
            )
            seen.add(cid)
    # Always include retrieved sources even if model omitted some IDs.
    for src in local_sources:
        if src.source_id not in seen:
            citations.append(
                Citation(
                    source_id=src.source_id,
                    source_type="document",
                    label=f"{src.title} — {src.section}",
                    reference=f"{src.doc_id} / {src.section} (v{src.version})",
                    metadata={"doc_id": src.doc_id, "score": src.score},
                )
            )
    for src in web_sources:
        if src.source_id not in seen:
            citations.append(
                Citation(
                    source_id=src.source_id,
                    source_type="web",
                    label=src.title,
                    reference=src.url,
                    metadata={
                        "retrieved_at": src.retrieved_at.isoformat(),
                        "published_at": src.published_at,
                    },
                )
            )
    return citations


def validate_citation_ids(
    citation_ids: list[str],
    local_sources: list[LocalSource],
    web_sources: list[WebSource],
) -> list[str]:
    allowed = {s.source_id for s in local_sources} | {s.source_id for s in web_sources}
    return [cid for cid in citation_ids if cid in allowed]
