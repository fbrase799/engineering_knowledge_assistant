"""LangGraph routing, budgets, and evidence-gap tests (T-01..T-15 subset)."""

from __future__ import annotations

from backend.src.retrieval.models import EvidenceStatus, RetrievalMode


def test_hybrid_is_default_in_api_schema():
    from backend.src.api.schemas import AskRequest

    req = AskRequest(question="What are the timeout thresholds?")
    assert req.retrieval_mode == RetrievalMode.HYBRID


def test_local_mode_never_calls_tavily(make_graph):
    graph, retriever, tavily, llm = make_graph()
    result = graph.invoke(
        {
            "request_id": "r1",
            "question": "What timeout thresholds are specified?",
            "retrieval_mode": RetrievalMode.LOCAL,
        }
    )
    assert tavily.call_count == 0
    assert tavily.payloads == []
    assert len(retriever.queries) == 1
    assert result["web_evidence_status"] == EvidenceStatus.NOT_REQUESTED
    assert llm.call_count == 1


def test_web_mode_never_queries_faiss(make_graph):
    graph, retriever, tavily, llm = make_graph()
    result = graph.invoke(
        {
            "request_id": "r2",
            "question": "What do sources say about watchdogs?",
            "retrieval_mode": RetrievalMode.WEB,
        }
    )
    assert retriever.queries == []
    assert tavily.call_count == 1
    assert result["local_evidence_status"] == EvidenceStatus.NOT_REQUESTED
    assert llm.call_count == 1


def test_hybrid_invokes_both_with_one_tavily_call(make_graph):
    graph, retriever, tavily, llm = make_graph()
    result = graph.invoke(
        {
            "request_id": "r3",
            "question": "How do our timeouts compare with public guidance?",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert len(retriever.queries) == 1
    assert tavily.call_count == 1
    assert llm.call_count == 1
    assert result["comparison_status"] == "full"
    assert result["sections"]["comparison"]


def test_tavily_payload_excludes_document_excerpts(make_graph, local_sources):
    graph, _, tavily, _ = make_graph()
    question = "Compare heartbeat monitor with public watchdog guidance"
    graph.invoke(
        {
            "request_id": "r4",
            "question": question,
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert len(tavily.payloads) == 1
    payload = tavily.payloads[0]
    assert payload["query"] == question
    blob = str(payload)
    for src in local_sources:
        assert src.content not in blob
        assert src.source_id not in blob


def test_llm_call_at_most_one(make_graph):
    graph, _, _, llm = make_graph()
    graph.invoke(
        {
            "request_id": "r5",
            "question": "Compare designs",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert llm.call_count == 1


def test_evidence_gap_skips_llm(make_graph):
    graph, _, tavily, llm = make_graph(local=[], web=[])
    result = graph.invoke(
        {
            "request_id": "r6",
            "question": "How does this comply with a missing requirement?",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert result["comparison_status"] == "evidence_gap"
    assert llm.call_count == 0
    assert "Insufficient evidence" in result["answer"]
    assert tavily.call_count == 1


def test_partial_local_only_when_web_fails(make_graph):
    graph, _, tavily, llm = make_graph(tavily_fail=True)
    result = graph.invoke(
        {
            "request_id": "r7",
            "question": "Compare our design with public guidance",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert result["comparison_status"] == "partial_local_only"
    assert "incomplete" in result["answer"].lower()
    assert llm.call_count == 1
    assert tavily.call_count == 1


def test_partial_web_only_when_local_empty(make_graph):
    graph, _, _, llm = make_graph(local=[])
    result = graph.invoke(
        {
            "request_id": "r8",
            "question": "Compare our design with public guidance",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert result["comparison_status"] == "partial_web_only"
    assert "incomplete" in result["answer"].lower()
    assert llm.call_count == 1


def test_citation_validation_drops_unknown_ids(make_graph):
    graph, _, _, _ = make_graph(citation_ids=["REF-ARCH-001#chunk-1", "invented-id", "web-1"])
    result = graph.invoke(
        {
            "request_id": "r9",
            "question": "Compare designs",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    citation_ids = {c["source_id"] for c in result["citations"]}
    assert "invented-id" not in citation_ids
    assert "REF-ARCH-001#chunk-1" in citation_ids
    assert "web-1" in citation_ids


def test_prompt_contains_only_selected_chunks(make_graph, local_sources):
    graph, _, _, llm = make_graph()
    graph.invoke(
        {
            "request_id": "r10",
            "question": "Compare designs",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    prompt = llm.last_prompt or ""
    for src in local_sources:
        assert src.content in prompt
    assert "full corpus should not appear" not in prompt
    # Budget marker: selected excerpts are labeled
    assert "[REF-ARCH-001#chunk-1]" in prompt


def test_shared_retriever_instance_isolation(make_graph):
    graph_a, retriever, _, _ = make_graph()
    graph_b, _, _, _ = make_graph()
    # Same fake source object identity is fine; graph state must not leak.
    result_a = graph_a.invoke(
        {
            "request_id": "a",
            "question": "Question A about timeouts",
            "retrieval_mode": RetrievalMode.LOCAL,
        }
    )
    result_b = graph_b.invoke(
        {
            "request_id": "b",
            "question": "Question B about heartbeats",
            "retrieval_mode": RetrievalMode.WEB,
        }
    )
    assert result_a["request_id"] == "a"
    assert result_b["request_id"] == "b"
    assert result_a["question"] != result_b["question"]


def test_trace_events_match_hybrid_path(make_graph):
    graph, _, _, _ = make_graph()
    result = graph.invoke(
        {
            "request_id": "r11",
            "question": "Compare designs",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    nodes = [e.node for e in result["execution_events"]]
    assert nodes == [
        "route_mode",
        "retrieve_local",
        "search_web",
        "assemble_context",
        "evidence_gate",
        "generate_answer",
        "validate_sources",
    ]
    serialized = str([e.model_dump() for e in result["execution_events"]])
    assert "api_key" not in serialized.lower()
    assert "tvly-" not in serialized


def test_generation_failure_terminates(make_graph):
    graph, _, _, llm = make_graph(llm_fail=True)
    result = graph.invoke(
        {
            "request_id": "r12",
            "question": "Compare designs",
            "retrieval_mode": RetrievalMode.HYBRID,
        }
    )
    assert llm.call_count == 1
    assert result.get("error")
    assert any(e.status == "failed" for e in result["execution_events"])
