# Azure Container Apps deployment

Two containers only (frontend + backend). Prefer this over Kubernetes for the portfolio demonstrator so infrastructure cost stays near application cost.

Use the scripts under [`azure/`](../azure/README.md) — same pattern as `vehicle_configurator`.

## Prerequisites

- Azure CLI (`az login`)
- Repo-root `.env` with Azure OpenAI + Tavily (gitignored; never commit)
- Container images pushed to GHCR (see `azure/config.env`)

## Quick path

```bash
./azure/00-bootstrap-oidc.sh   # once (OIDC for GitHub Actions)
./azure/01-setup.sh            # creates stack; loads secrets from .env
```

`01-setup.sh` reads `.env` locally and writes values into **Container App secrets**, then maps them with `secretref:` env vars. The `.env` file itself is never uploaded.

## Day-to-day

```bash
./azure/02-update-images.sh    # redeploy image tags
./azure/03-teardown.sh         # stop billing (delete resource group)
./azure/04-delete.sh           # full reset including OIDC
```

## Smoke test

After setup, open the printed `https://…azurecontainerapps.io` URL:

- UI loads
- Local-mode ask returns a grounded answer
- Hybrid needs a valid `TAVILY_API_KEY`

## Cost controls

1. Azure budget + alert on the resource group
2. `minReplicas=1` while demos are active; tear down when idle
3. Prefer local Docker Compose (`OPENAI_API_KEY`) for day-to-day development

Helm / AKS are intentionally not used for v1.
