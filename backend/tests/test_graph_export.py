"""T-16: generated Mermaid matches compiled graph."""

from __future__ import annotations

from backend.src.graph.workflow import build_assistant_graph, get_graph_mermaid


def test_mermaid_contains_expected_nodes():
    graph = build_assistant_graph()
    mermaid = get_graph_mermaid(graph)
    for node in [
        "route_mode",
        "retrieve_local",
        "search_web",
        "assemble_context",
        "evidence_gate",
        "generate_answer",
        "validate_sources",
        "report_evidence_gap",
    ]:
        assert node in mermaid
