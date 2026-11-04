#!/usr/bin/env bash
# Creates / updates the ACA stack: resource group, Log Analytics,
# Container Apps environment, backend (internal) + frontend (external).
#
# Secrets are read from the repo-root .env (gitignored) — never committed.
# Idempotent: re-running updates existing resources.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=config.env
source "$HERE/config.env"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy .env.example and fill Azure OpenAI + Tavily values."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

: "${AZURE_OPENAI_API_KEY:?Set AZURE_OPENAI_API_KEY in .env}"
: "${AZURE_OPENAI_ENDPOINT:?Set AZURE_OPENAI_ENDPOINT in .env}"
: "${TAVILY_API_KEY:?Set TAVILY_API_KEY in .env}"

AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-10-21}"
AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-gpt-4o-mini}"
RATE_LIMIT_PER_MINUTE="${RATE_LIMIT_PER_MINUTE:-20}"
REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-60}"
LANGSMITH_TRACING="${LANGSMITH_TRACING:-false}"
LANGSMITH_PROJECT="${LANGSMITH_PROJECT:-engineering-knowledge-assistant}"
LANGSMITH_API_KEY="${LANGSMITH_API_KEY:-}"

echo ">>> Ensuring az CLI has the containerapp extension"
az extension add --name containerapp --upgrade --only-show-errors --output none

echo ">>> Registering providers (one-time, idempotent)"
for p in Microsoft.OperationalInsights Microsoft.App Microsoft.ContainerRegistry; do
  az provider register --namespace "$p" --only-show-errors --output none || true
done

echo ">>> Resource group: $AZ_RESOURCE_GROUP ($AZ_LOCATION)"
az group create --name "$AZ_RESOURCE_GROUP" --location "$AZ_LOCATION" --output none

echo ">>> Log Analytics workspace: $AZ_LOG_ANALYTICS"
az monitor log-analytics workspace create \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --workspace-name "$AZ_LOG_ANALYTICS" \
  --location "$AZ_LOCATION" \
  --output none 2>/dev/null || echo "    (already exists)"

LAW_ID=$(az monitor log-analytics workspace show \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --workspace-name "$AZ_LOG_ANALYTICS" \
  --query customerId -o tsv)
LAW_KEY=$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --workspace-name "$AZ_LOG_ANALYTICS" \
  --query primarySharedKey -o tsv)

echo ">>> Container Apps environment: $AZ_ENVIRONMENT"
az containerapp env create \
  --name "$AZ_ENVIRONMENT" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --location "$AZ_LOCATION" \
  --logs-workspace-id "$LAW_ID" \
  --logs-workspace-key "$LAW_KEY" \
  --output none 2>/dev/null || echo "    (already exists)"

ENV_DOMAIN=$(az containerapp env show \
  --name "$AZ_ENVIRONMENT" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
BACKEND_INTERNAL_FQDN="${APP_BACKEND}.internal.${ENV_DOMAIN}"

# ---------------------------------------------------------------------
# backend (internal HTTP ingress on :8000)
# ---------------------------------------------------------------------
# --allow-insecure: internal ACA traffic stays inside the env; HTTP on
# :80 is fine. Without this, ACA 301-redirects HTTP→HTTPS and breaks
# the frontend nginx reverse proxy.
echo ">>> App: $APP_BACKEND"
BACKEND_PLAIN_ENV=(
  "LLM_PROVIDER=azure"
  "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}"
  "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}"
  "RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE}"
  "REQUEST_TIMEOUT_SECONDS=${REQUEST_TIMEOUT_SECONDS}"
  "LANGSMITH_TRACING=${LANGSMITH_TRACING}"
  "LANGSMITH_PROJECT=${LANGSMITH_PROJECT}"
  "CORS_ORIGINS=[\"http://localhost:5173\"]"
)

if ! az containerapp show -g "$AZ_RESOURCE_GROUP" -n "$APP_BACKEND" >/dev/null 2>&1; then
  az containerapp create \
    --name "$APP_BACKEND" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --environment "$AZ_ENVIRONMENT" \
    --image "$IMAGE_BACKEND" \
    --transport http \
    --ingress internal \
    --allow-insecure \
    --target-port 8000 \
    --cpu 0.5 --memory 1.0Gi \
    --min-replicas 1 --max-replicas 1 \
    --secrets \
      azure-openai-api-key="$AZURE_OPENAI_API_KEY" \
      azure-openai-endpoint="$AZURE_OPENAI_ENDPOINT" \
      tavily-api-key="$TAVILY_API_KEY" \
      langsmith-api-key="${LANGSMITH_API_KEY:-unused}" \
    --env-vars \
      "${BACKEND_PLAIN_ENV[@]}" \
      "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key" \
      "AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint" \
      "TAVILY_API_KEY=secretref:tavily-api-key" \
      "LANGSMITH_API_KEY=secretref:langsmith-api-key" \
    --output none
else
  az containerapp secret set \
    --name "$APP_BACKEND" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --secrets \
      azure-openai-api-key="$AZURE_OPENAI_API_KEY" \
      azure-openai-endpoint="$AZURE_OPENAI_ENDPOINT" \
      tavily-api-key="$TAVILY_API_KEY" \
      langsmith-api-key="${LANGSMITH_API_KEY:-unused}" \
    --output none
  az containerapp update \
    --name "$APP_BACKEND" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --image "$IMAGE_BACKEND" \
    --min-replicas 1 \
    --max-replicas 1 \
    --set-env-vars \
      "${BACKEND_PLAIN_ENV[@]}" \
      "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key" \
      "AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint" \
      "TAVILY_API_KEY=secretref:tavily-api-key" \
      "LANGSMITH_API_KEY=secretref:langsmith-api-key" \
    --output none
  az containerapp ingress update \
    --name "$APP_BACKEND" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --type internal \
    --allow-insecure \
    --output none
fi

# ---------------------------------------------------------------------
# frontend (EXTERNAL HTTP ingress on :80)
# ---------------------------------------------------------------------
FRONTEND_ENV_VARS=(
  "BACKEND_UPSTREAM=${BACKEND_INTERNAL_FQDN}"
)

echo ">>> App: $APP_FRONTEND (BACKEND_UPSTREAM=${BACKEND_INTERNAL_FQDN})"
if ! az containerapp show -g "$AZ_RESOURCE_GROUP" -n "$APP_FRONTEND" >/dev/null 2>&1; then
  az containerapp create \
    --name "$APP_FRONTEND" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --environment "$AZ_ENVIRONMENT" \
    --image "$IMAGE_FRONTEND" \
    --transport http \
    --ingress external \
    --target-port 80 \
    --cpu 0.25 --memory 0.5Gi \
    --min-replicas 1 --max-replicas 1 \
    --env-vars "${FRONTEND_ENV_VARS[@]}" \
    --output none
else
  az containerapp update \
    --name "$APP_FRONTEND" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --image "$IMAGE_FRONTEND" \
    --min-replicas 1 \
    --max-replicas 1 \
    --set-env-vars "${FRONTEND_ENV_VARS[@]}" \
    --output none
fi

FQDN=$(az containerapp show \
  --name "$APP_FRONTEND" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv)

echo ">>> Setting backend CORS_ORIGINS for https://$FQDN"
az containerapp update \
  --name "$APP_BACKEND" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --set-env-vars "CORS_ORIGINS=[\"https://${FQDN}\"]" \
  --output none

cat <<EOF

>>> Setup complete.

    Public URL:  https://$FQDN

Secrets were loaded from .env into the backend Container App.
Local Docker can keep using OPENAI_API_KEY; Azure uses LLM_PROVIDER=azure.

To tear everything down: ./azure/03-teardown.sh
EOF
