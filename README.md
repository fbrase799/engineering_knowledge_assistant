# Engineering Knowledge Assistant

Hybrid engineering Q&A that **compares a curated document corpus with current public web results**.

- **Local RAG:** shared read-only FAISS index (FastEmbed MiniLM, CPU)
- **Web:** at most one Tavily basic search (≤3 results)
- **Synthesis:** at most one Azure OpenAI generation call
- **Orchestration:** LangGraph `StateGraph` with conditional routing
- **UI:** React + TypeScript (Vite) with SSE execution timeline
- **Deploy:** Docker Compose locally, Helm on Azure AKS

Treat [PRD.md](PRD.md) as the product source of truth.

**Docker-first:** run the app and tests with Compose. `uv` and Node tooling execute inside containers — not on the host.

Backend image builds cache dependency install and the FastEmbed model download in separate layers, so routine code changes should rebuild in seconds rather than re-downloading packages/models. First build (or a `pyproject.toml` / lockfile change) is still slow.

## Run locally

```bash
cp .env.example .env
# For local demo with OpenAI platform credits:
#   OPENAI_API_KEY=sk-...
#   TAVILY_API_KEY=...
# Azure OpenAI (AZURE_OPENAI_*) is optional and typical for AKS later.

docker compose -f docker/compose.yaml up --build
```

- UI: http://localhost:5173
- API: [http://localho***st:8000/health](http://localhost:8000/health)***

## ***Tests***

***All checks use containerized*** `uv` ***/*** `npm` ***(no host Python/Node required):***

```bash
docker compose -f docker/compose.yaml --profile test build backend-test frontend-test
docker compose -f docker/compose.yaml --profile test run --rm backend-test
docker compose -f docker/compose.yaml --profile test run --rm frontend-test
```

Regenerate the committed LangGraph diagram (mounts `docs/` so the host file updates):

```bash
docker compose -f docker/compose.yaml --profile test run --rm \
  -v "$PWD/docs:/app/docs" backend-test \
  uv run python scripts/export_graph.py
```

## Example Hybrid question

> How does the sensor timeout handling described in our reference architecture compare with current watchdog recommendations for embedded systems?

Expect: documented approach, web findings, comparison, engineering implications (as proposals), and separated citations.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/product-overview.md](docs/product-overview.md) | Product summary |
| [docs/architecture.md](docs/architecture.md) | System architecture |
| [docs/langgraph.md](docs/langgraph.md) | Generated LangGraph Mermaid |
| [docs/rag-data-flow.md](docs/rag-data-flow.md) | Ingestion and disclosure boundaries |
| [docs/deployment-aks.md](docs/deployment-aks.md) | AKS / Helm / cost controls |
| [docs/evaluation.md](docs/evaluation.md) | Evaluation cases and findings |
| [docs/decisions/](docs/decisions/) | Architecture decision records |

## Hard budgets (per question)

| Operation | Max |
|---|---:|
| Tavily basic search | 1 (0 in Local) |
| Azure OpenAI generation | 1 |
| Local chunks | 4 (default) |
| Tavily results | 3 |

## License

Sample documents are CC0 (see `sample_documents/LICENSE.md`). Application code is provided for portfolio / educational use.
