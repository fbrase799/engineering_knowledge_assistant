# Azure deployment scripts

Deploys the Engineering Knowledge Assistant to **Azure Container Apps (ACA)** —
two containers (frontend + backend), same pattern as `vehicle_configurator`.

Secrets come from the **repo-root `.env`** (gitignored). They are never committed;
`01-setup.sh` loads them locally and writes them into Container App secrets.

## What gets created

| Azure resource | Name (default) | Purpose |
|---|---|---|
| Resource group | `rg-engineering-knowledge` | Container for everything else |
| Log Analytics workspace | `eka-logs` | Required by ACA for container logs |
| Container Apps environment | `eka-env` | Network + DNS boundary for the two apps |
| Container app | `backend` | FastAPI + FAISS, **internal** HTTP on :8000 |
| Container app | `frontend` | nginx SPA, **external** HTTPS on :80 |

Both apps use `minReplicas=1` so the demo URL stays warm.

## Prerequisites

- `az login` to the subscription you want to use
- `gh auth login` (for `00-bootstrap-oidc.sh`)
- Filled-in repo-root `.env` with at least:
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `TAVILY_API_KEY`
- Images published to GHCR (workflow **Publish Docker images**) and set to
  **Public** under GitHub → Packages (ACA pulls without registry credentials)

Local Docker continues to prefer `OPENAI_API_KEY` via `LLM_PROVIDER=auto`.  
Azure is forced to `LLM_PROVIDER=azure`.

## One-time setup

1. Publish images (GitHub → Actions → **Publish Docker images** → Run workflow),
   or push to `main` after the workflow file is merged.
2. In GitHub → Packages, open each image → **Package settings** → change
   visibility to **Public** (first publish creates the packages).
3. Then:

```bash
./azure/00-bootstrap-oidc.sh   # AAD app + GitHub OIDC secrets (optional for CI)
./azure/01-setup.sh            # RG, ACA env, 2 apps; loads secrets from .env
```

## Day-to-day

```bash
./azure/02-update-images.sh    # roll apps to IMAGE_TAG
./azure/03-teardown.sh         # delete RG (stop billing); keep OIDC
./azure/04-delete.sh           # full nuke including OIDC + GitHub secrets
```

## How `.env` becomes Azure secrets

`01-setup.sh` does roughly:

1. `source ../.env`
2. `az containerapp secret set ... azure-openai-api-key=... tavily-api-key=...`
3. Maps them into env vars with `secretref:...`

Non-secret settings (`AZURE_OPENAI_DEPLOYMENT`, rate limits, etc.) go in plain env vars.
`CORS_ORIGINS` is set to the public frontend FQDN after the frontend app exists.

## Overriding defaults

All tunables live in [`config.env`](./config.env):

```bash
AZ_LOCATION=germanywestcentral ./azure/01-setup.sh
```

## Cost

Similar to the vehicle configurator demo: roughly **€15–25 / month** while running
in West Europe with `minReplicas=1`. Tear down with `03-teardown.sh` when idle.

Helm / AKS are not used.
