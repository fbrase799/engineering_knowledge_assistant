# Evaluation

Dataset: [`evaluations/cases.json`](../evaluations/cases.json)

## Dimensions

| Dimension | What we check |
|---|---|
| Retrieval relevance | Expected `doc_id`s appear for local/hybrid cases |
| Web relevance | Web mode/hybrid issues a Tavily call with the question only |
| Comparison quality | Hybrid answers expose comparison / partial-gap messaging |
| Grounding | Citation IDs ⊆ retrieved source IDs |
| Resilience | Empty evidence → evidence_gap without LLM call |
| Predictability | ≤1 Tavily, ≤1 LLM per question |

## How to run

Automated CI and local checks run inside Docker (`uv` in the `backend-test` image):

```bash
docker compose -f docker/compose.yaml --profile test build backend-test
docker compose -f docker/compose.yaml --profile test run --rm backend-test
```

Optional live smoke (requires `.env` credentials; not run in CI):

```bash
docker compose -f docker/compose.yaml --profile test run --rm \
  --env-file .env backend-test \
  uv run python evaluations/run_eval.py --live
```

## Findings (mocked suite)

Recorded against the v0.1 implementation:

- Hybrid default, Local-without-Tavily, Web-without-FAISS: **pass**
- One-call budgets and Tavily payload isolation: **pass**
- Evidence gap without LLM: **pass**
- Partial hybrid messaging when one side missing: **pass**
- Citation ID validation drops unknowns: **pass**
- Generated Mermaid contains all graph nodes: **pass**

Live comparison quality depends on Azure OpenAI + Tavily responses and should be reviewed manually for portfolio demos.
