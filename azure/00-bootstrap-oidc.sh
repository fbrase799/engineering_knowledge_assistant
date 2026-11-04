#!/usr/bin/env bash
# One-time bootstrap: creates an Azure AD app registration that GitHub
# Actions can federate into (OIDC), grants it Contributor on the
# resource group, and writes the three identifiers that the workflow
# needs into GitHub repository secrets.
#
# Run once from your workstation. Requires:
#   - az login (you confirmed this is done)
#   - gh auth login (already done earlier in this project)
#   - permission to create AAD app registrations in your tenant
#     (normally true on a personal / pay-as-you-go subscription)

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=config.env
source "$HERE/config.env"

echo ">>> Using subscription:"
az account show --query '{name:name, id:id, tenantId:tenantId}' -o table
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

echo ">>> Ensuring resource group '$AZ_RESOURCE_GROUP' exists in '$AZ_LOCATION' (needed for role assignment scope)"
az group create --name "$AZ_RESOURCE_GROUP" --location "$AZ_LOCATION" --output none

echo ">>> Creating AAD app '$AAD_APP_NAME' (idempotent)"
APP_ID=$(az ad app list --display-name "$AAD_APP_NAME" --query '[0].appId' -o tsv)
if [ -z "${APP_ID:-}" ]; then
  APP_ID=$(az ad app create --display-name "$AAD_APP_NAME" --query appId -o tsv)
  echo "    created app with appId=$APP_ID"
else
  echo "    already exists, appId=$APP_ID"
fi

echo ">>> Ensuring service principal for app exists"
SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' -o tsv)
if [ -z "${SP_ID:-}" ]; then
  SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
  echo "    created SP objectId=$SP_ID"
else
  echo "    already exists, SP objectId=$SP_ID"
fi

echo ">>> Granting Contributor on resource group '$AZ_RESOURCE_GROUP'"
SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$AZ_RESOURCE_GROUP"
az role assignment create \
  --assignee-object-id "$SP_ID" \
  --assignee-principal-type ServicePrincipal \
  --role Contributor \
  --scope "$SCOPE" \
  --only-show-errors \
  --output none 2>/dev/null || echo "    (role assignment already present, ignoring)"

echo ">>> Adding federated credential for GitHub Actions (ref=$GH_DEPLOY_REF)"
FED_NAME="gh-${GH_REPO//\//-}-$(echo "$GH_DEPLOY_REF" | tr '/' '-')"
az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters "$(cat <<JSON
{
  "name": "$FED_NAME",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:$GH_REPO:ref:$GH_DEPLOY_REF",
  "description": "GitHub Actions deploy from $GH_REPO@$GH_DEPLOY_REF",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
)" --only-show-errors --output none 2>/dev/null \
  || echo "    (federated credential already exists, ignoring)"

echo ">>> Writing GitHub repository secrets via gh CLI"
if command -v gh >/dev/null 2>&1; then
  gh secret set AZURE_CLIENT_ID       --repo "$GH_REPO" --body "$APP_ID"
  gh secret set AZURE_TENANT_ID       --repo "$GH_REPO" --body "$TENANT_ID"
  gh secret set AZURE_SUBSCRIPTION_ID --repo "$GH_REPO" --body "$SUBSCRIPTION_ID"
  echo "    set AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID"
else
  echo ""
  echo "    gh CLI not found. Set these manually in GitHub:"
  echo "      AZURE_CLIENT_ID       = $APP_ID"
  echo "      AZURE_TENANT_ID       = $TENANT_ID"
  echo "      AZURE_SUBSCRIPTION_ID = $SUBSCRIPTION_ID"
fi

cat <<EOF

>>> Bootstrap complete.

    Tenant:         $TENANT_ID
    Subscription:   $SUBSCRIPTION_ID
    Resource group: $AZ_RESOURCE_GROUP
    App (clientId): $APP_ID
    Federated sub:  repo:$GH_REPO:ref:$GH_DEPLOY_REF

Next step: ./azure/01-setup.sh
EOF
