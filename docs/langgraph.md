# LangGraph Workflow

This diagram is **generated from the compiled LangGraph graph**.
Do not edit the Mermaid block by hand — run `uv run python scripts/export_graph.py`.

## Retrieval and synthesis flow

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	route_mode(route_mode)
	retrieve_local(retrieve_local)
	search_web(search_web)
	assemble_context(assemble_context)
	evidence_gate(evidence_gate)
	generate_answer(generate_answer)
	validate_sources(validate_sources)
	report_evidence_gap(report_evidence_gap)
	__end__([<p>__end__</p>]):::last
	__start__ --> route_mode;
	assemble_context --> evidence_gate;
	evidence_gate -.-> generate_answer;
	evidence_gate -.-> report_evidence_gap;
	generate_answer --> validate_sources;
	retrieve_local -.-> assemble_context;
	retrieve_local -.-> search_web;
	route_mode -.-> retrieve_local;
	route_mode -.-> search_web;
	search_web --> assemble_context;
	report_evidence_gap --> __end__;
	validate_sources --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc

```
