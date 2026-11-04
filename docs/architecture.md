# Architecture

## Components

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript (Vite SPA), SSE timeline |
| API | FastAPI (REST + SSE), in-process rate limiting |
| Orchestration | LangGraph `StateGraph` |
| RAG | LangChain + FAISS, FastEmbed MiniLM (CPU) |
| Web | Tavily basic search (≤1 call, ≤3 results) |
| Generation | Azure OpenAI `gpt-5-mini` (≤1 call) |
| Observability | LangSmith (optional) + sanitized UI events |
| Local deploy | Docker Compose under `docker/` (Docker-first; `uv` runs in-container) |
| Cloud deploy | Azure Container Apps (frontend + backend) |

## Request path (Hybrid)

1. `route_mode` selects Hybrid / Local / Web
2. `retrieve_local` queries the shared FAISS index
3. `search_web` runs one Tavily query (**question only** — no document excerpts)
4. `assemble_context` labels and bounds evidence
5. `evidence_gate` short-circuits to an evidence-gap response when empty
6. `generate_answer` performs one Azure OpenAI synthesis call
7. `validate_sources` drops unknown citation IDs

## Data boundaries

- Full corpus never leaves the service; only selected chunks go to Azure OpenAI.
- Retrieved chunks never go to Tavily.
- Frontend never receives API keys or secrets.
- LangSmith may receive prompts/chunks when tracing is enabled — document that boundary for operators.

See also [rag-data-flow.md](rag-data-flow.md) and the generated [langgraph.md](langgraph.md).
