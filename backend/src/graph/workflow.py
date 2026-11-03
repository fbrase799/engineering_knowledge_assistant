"""Bounded LangGraph workflow for hybrid / local / web retrieval."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from backend.src.config import Settings, get_settings
from backend.src.graph.state import GraphState
from backend.src.integrations.azure_openai import (
    AzureOpenAIClient,
    LLMClientProtocol,
    build_citations,
    validate_citation_ids,
)
from backend.src.integrations.tavily_client import TavilyClient, TavilyClientProtocol
from backend.src.observability.tracing import NodeTimer, new_event
from backend.src.retrieval.models import (
    ComparisonSections,
    EvidenceStatus,
    RetrievalMode,
    UsageMetrics,
)
from backend.src.retrieval.retriever import SharedRetriever, get_shared_retriever


class AssistantGraph:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        retriever: SharedRetriever | None = None,
        tavily: TavilyClientProtocol | None = None,
        llm: LLMClientProtocol | None = None,
    ):
        self.settings = settings or get_settings()
        self.retriever = retriever
        self.tavily = tavily or TavilyClient(self.settings)
        self.llm = llm or AzureOpenAIClient(self.settings)
        self._compiled = self._build()

    def _get_retriever(self) -> SharedRetriever:
        if self.retriever is None:
            self.retriever = get_shared_retriever()
        return self.retriever

    def _build(self):
        graph = StateGraph(GraphState)
        graph.add_node("route_mode", self.route_mode)
        graph.add_node("retrieve_local", self.retrieve_local)
        graph.add_node("search_web", self.search_web)
        graph.add_node("assemble_context", self.assemble_context)
        graph.add_node("evidence_gate", self.evidence_gate)
        graph.add_node("generate_answer", self.generate_answer)
        graph.add_node("validate_sources", self.validate_sources)
        graph.add_node("report_evidence_gap", self.report_evidence_gap)

        graph.add_edge(START, "route_mode")
        graph.add_conditional_edges(
            "route_mode",
            self.after_route,
            {
                "retrieve_local": "retrieve_local",
                "search_web": "search_web",
            },
        )
        graph.add_conditional_edges(
            "retrieve_local",
            self.after_local,
            {
                "search_web": "search_web",
                "assemble_context": "assemble_context",
            },
        )
        graph.add_edge("search_web", "assemble_context")
        graph.add_edge("assemble_context", "evidence_gate")
        graph.add_conditional_edges(
            "evidence_gate",
            self.after_evidence,
            {
                "generate_answer": "generate_answer",
                "report_evidence_gap": "report_evidence_gap",
            },
        )
        graph.add_edge("generate_answer", "validate_sources")
        graph.add_edge("validate_sources", END)
        graph.add_edge("report_evidence_gap", END)
        return graph.compile()

    @property
    def compiled(self):
        return self._compiled

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        initial: GraphState = {
            "request_id": state["request_id"],
            "question": state["question"],
            "retrieval_mode": state["retrieval_mode"],
            "local_sources": [],
            "web_sources": [],
            "selected_context": "",
            "local_evidence_status": EvidenceStatus.NOT_REQUESTED,
            "web_evidence_status": EvidenceStatus.NOT_REQUESTED,
            "overall_evidence_status": EvidenceStatus.UNAVAILABLE,
            "answer": "",
            "sections": {},
            "citations": [],
            "citation_ids": [],
            "comparison_status": "evidence_gap",
            "execution_events": [],
            "usage_metrics": UsageMetrics(),
            "error": None,
            "langsmith_run_id": None,
        }
        return self._compiled.invoke(initial)

    # --- nodes ---

    def route_mode(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        mode = state["retrieval_mode"]
        return {
            "execution_events": [
                new_event(
                    "route_mode",
                    "succeeded",
                    f"Selected retrieval mode: {mode.value}",
                    branch=mode.value,
                    duration_ms=timer.ms(),
                    details={"retrieval_mode": mode.value},
                )
            ]
        }

    def retrieve_local(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        try:
            sources = self._get_retriever().search(state["question"])
            status = (
                EvidenceStatus.AVAILABLE if sources else EvidenceStatus.UNAVAILABLE
            )
            event_status = "succeeded"
            message = f"Retrieved {len(sources)} local chunk(s)"
            error = None
        except Exception as exc:  # noqa: BLE001
            sources = []
            status = EvidenceStatus.UNAVAILABLE
            event_status = "failed"
            message = f"Local retrieval failed: {exc}"
            error = str(exc)
        metrics = state.get("usage_metrics") or UsageMetrics()
        metrics = metrics.model_copy(update={"local_chunk_count": len(sources)})
        return {
            "local_sources": sources,
            "local_evidence_status": status,
            "usage_metrics": metrics,
            "error": error or state.get("error"),
            "execution_events": [
                new_event(
                    "retrieve_local",
                    event_status,
                    message,
                    branch="local",
                    duration_ms=timer.ms(),
                    details={"local_chunk_count": len(sources)},
                )
            ],
        }

    def search_web(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        metrics = state.get("usage_metrics") or UsageMetrics()
        try:
            # Query is the user question only — never local document excerpts.
            sources = self.tavily.search(state["question"])
            status = (
                EvidenceStatus.AVAILABLE if sources else EvidenceStatus.UNAVAILABLE
            )
            event_status = "succeeded"
            message = f"Retrieved {len(sources)} web result(s)"
            error = None
        except Exception as exc:  # noqa: BLE001
            sources = []
            status = EvidenceStatus.UNAVAILABLE
            event_status = "failed"
            message = f"Web search failed: {exc}"
            error = str(exc)
        # One Tavily call for this request (hard budget); do not use client lifetime counters.
        metrics = metrics.model_copy(
            update={
                "web_result_count": len(sources),
                "tavily_calls": 1,
            }
        )
        return {
            "web_sources": sources,
            "web_evidence_status": status,
            "usage_metrics": metrics,
            "error": error or state.get("error"),
            "execution_events": [
                new_event(
                    "search_web",
                    event_status,
                    message,
                    branch="web",
                    duration_ms=timer.ms(),
                    details={
                        "web_result_count": len(sources),
                        "tavily_calls": 1,
                    },
                )
            ],
        }

    def assemble_context(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        mode = state["retrieval_mode"]
        local_sources = state.get("local_sources") or []
        web_sources = state.get("web_sources") or []

        local_status = state.get("local_evidence_status", EvidenceStatus.NOT_REQUESTED)
        web_status = state.get("web_evidence_status", EvidenceStatus.NOT_REQUESTED)

        if mode == RetrievalMode.LOCAL:
            web_status = EvidenceStatus.NOT_REQUESTED
            web_sources = []
        elif mode == RetrievalMode.WEB:
            local_status = EvidenceStatus.NOT_REQUESTED
            local_sources = []

        parts: list[str] = []
        for src in local_sources:
            parts.append(f"[DOC {src.source_id}] {src.content}")
        for src in web_sources:
            parts.append(f"[WEB {src.source_id}] {src.snippet}")
        selected = "\n\n".join(parts)[: self.settings.max_context_chars]

        has_local = local_status == EvidenceStatus.AVAILABLE and bool(local_sources)
        has_web = web_status == EvidenceStatus.AVAILABLE and bool(web_sources)

        if has_local and has_web:
            overall = EvidenceStatus.AVAILABLE
            comparison_status = (
                "full" if mode == RetrievalMode.HYBRID else f"{mode.value}_only"
            )
        elif has_local:
            overall = (
                EvidenceStatus.PARTIAL
                if mode == RetrievalMode.HYBRID
                else EvidenceStatus.AVAILABLE
            )
            comparison_status = (
                "partial_local_only" if mode == RetrievalMode.HYBRID else "local_only"
            )
        elif has_web:
            overall = (
                EvidenceStatus.PARTIAL
                if mode == RetrievalMode.HYBRID
                else EvidenceStatus.AVAILABLE
            )
            comparison_status = (
                "partial_web_only" if mode == RetrievalMode.HYBRID else "web_only"
            )
        else:
            overall = EvidenceStatus.UNAVAILABLE
            comparison_status = "evidence_gap"

        return {
            "local_sources": local_sources,
            "web_sources": web_sources,
            "local_evidence_status": local_status,
            "web_evidence_status": web_status,
            "overall_evidence_status": overall,
            "selected_context": selected,
            "comparison_status": comparison_status,
            "execution_events": [
                new_event(
                    "assemble_context",
                    "succeeded",
                    "Assembled labeled, bounded evidence",
                    duration_ms=timer.ms(),
                    details={
                        "local_chunk_count": len(local_sources),
                        "web_result_count": len(web_sources),
                        "context_chars": len(selected),
                        "comparison_status": comparison_status,
                    },
                )
            ],
        }

    def evidence_gate(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        overall = state.get("overall_evidence_status", EvidenceStatus.UNAVAILABLE)
        usable = overall in {EvidenceStatus.AVAILABLE, EvidenceStatus.PARTIAL}
        return {
            "execution_events": [
                new_event(
                    "evidence_gate",
                    "succeeded",
                    "Evidence available" if usable else "No usable evidence",
                    branch="generate" if usable else "gap",
                    duration_ms=timer.ms(),
                    details={"overall_evidence_status": overall.value},
                )
            ]
        }

    def generate_answer(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        local_sources = state.get("local_sources") or []
        web_sources = state.get("web_sources") or []
        try:
            sections, answer, citation_ids, usage = self.llm.generate(
                question=state["question"],
                mode=state["retrieval_mode"],
                local_sources=local_sources,
                web_sources=web_sources,
            )
            prior = state.get("usage_metrics") or UsageMetrics()
            usage = usage.model_copy(
                update={
                    "tavily_calls": prior.tavily_calls,
                    "local_chunk_count": prior.local_chunk_count,
                    "web_result_count": prior.web_result_count,
                }
            )
            # Annotate partial hybrid comparisons.
            if state.get("comparison_status") == "partial_local_only":
                gap = (
                    "Web evidence was unavailable; comparison is incomplete and "
                    "based only on curated documents."
                )
                sections = sections.model_copy(update={"evidence_gap_message": gap})
                answer = f"**Limited comparison:** {gap}\n\n{answer}"
            elif state.get("comparison_status") == "partial_web_only":
                gap = (
                    "Local document evidence was unavailable; comparison is incomplete "
                    "and based only on web findings."
                )
                sections = sections.model_copy(update={"evidence_gap_message": gap})
                answer = f"**Limited comparison:** {gap}\n\n{answer}"

            return {
                "sections": sections.model_dump(),
                "answer": answer,
                "citation_ids": citation_ids,
                "usage_metrics": usage,
                "execution_events": [
                    new_event(
                        "generate_answer",
                        "succeeded",
                        "Generated answer with one Azure OpenAI call",
                        duration_ms=timer.ms(),
                        details={"llm_calls": usage.llm_calls},
                    )
                ],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "error": str(exc),
                "answer": f"Generation failed: {exc}",
                "sections": ComparisonSections(
                    evidence_gap_message=f"Generation failed: {exc}"
                ).model_dump(),
                "execution_events": [
                    new_event(
                        "generate_answer",
                        "failed",
                        f"Generation failed: {exc}",
                        duration_ms=timer.ms(),
                    )
                ],
            }

    def validate_sources(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        local_sources = state.get("local_sources") or []
        web_sources = state.get("web_sources") or []
        raw_ids = state.get("citation_ids") or []
        valid_ids = validate_citation_ids(raw_ids, local_sources, web_sources)
        citations = build_citations(local_sources, web_sources, valid_ids)
        dropped = sorted(set(raw_ids) - set(valid_ids))
        return {
            "citation_ids": valid_ids,
            "citations": [c.model_dump() for c in citations],
            "execution_events": [
                new_event(
                    "validate_sources",
                    "succeeded",
                    f"Validated citations; dropped {len(dropped)} unknown id(s)",
                    duration_ms=timer.ms(),
                    details={
                        "valid_citation_count": len(valid_ids),
                        "dropped_citation_ids": dropped,
                    },
                )
            ],
        }

    def report_evidence_gap(self, state: GraphState) -> dict[str, Any]:
        timer = NodeTimer()
        message = (
            "Insufficient evidence: neither the curated document corpus nor the "
            "web search returned usable results for this question. No answer was "
            "generated to avoid unsupported claims."
        )
        sections = ComparisonSections(evidence_gap_message=message)
        return {
            "answer": message,
            "sections": sections.model_dump(),
            "citations": [],
            "comparison_status": "evidence_gap",
            "execution_events": [
                new_event(
                    "report_evidence_gap",
                    "succeeded",
                    "Returned evidence-gap response without LLM call",
                    branch="gap",
                    duration_ms=timer.ms(),
                )
            ],
        }

    # --- routing ---

    def after_route(self, state: GraphState) -> Literal["retrieve_local", "search_web"]:
        mode = state["retrieval_mode"]
        if mode == RetrievalMode.WEB:
            return "search_web"
        return "retrieve_local"

    def after_local(self, state: GraphState) -> Literal["search_web", "assemble_context"]:
        if state["retrieval_mode"] == RetrievalMode.HYBRID:
            return "search_web"
        return "assemble_context"

    def after_evidence(
        self, state: GraphState
    ) -> Literal["generate_answer", "report_evidence_gap"]:
        overall = state.get("overall_evidence_status", EvidenceStatus.UNAVAILABLE)
        if overall in {EvidenceStatus.AVAILABLE, EvidenceStatus.PARTIAL}:
            return "generate_answer"
        return "report_evidence_gap"


def build_assistant_graph(**kwargs: Any) -> AssistantGraph:
    return AssistantGraph(**kwargs)


def get_graph_mermaid(graph: AssistantGraph | None = None) -> str:
    assistant = graph or build_assistant_graph()
    return assistant.compiled.get_graph().draw_mermaid()
