#!/usr/bin/env bash
# Full tear-down: undoes BOTH 00-bootstrap-oidc.sh and 01-setup.sh.
#
# Unlike 03-teardown.sh (which only deletes the resource group to stop
# billing while keeping the OIDC plumbing reusable), this script:
#   1. Deletes the resource group (and waits until it is fully gone).
#   2. Deletes the AAD app registration created by 00-bootstrap-oidc.sh
#      (this also removes its service principal and federated credential).
#   3. Deletes the three GitHub repo secrets written by the bootstrap.
#
# After running this you would have to re-run 00-bootstrap-oidc.sh
# before 01-setup.sh works again.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=config.env
source "$HERE/config.env"

POLL_SECONDS="${POLL_SECONDS:-15}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-2400}"  # 40 min

# --------------------------------------------------------------------
# 1. Resource group
# --------------------------------------------------------------------

rg_exists=true
if ! az group show --name "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  rg_exists=false
fi

if [ "$rg_exists" = true ]; then
  state="$(az group show --name "$AZ_RESOURCE_GROUP" --query properties.provisioningState -o tsv 2>/dev/null || echo Unknown)"

  if [ "$state" != "Deleting" ]; then
    echo "About to perform a FULL tear-down:"
    echo "  - delete resource group '$AZ_RESOURCE_GROUP' and everything inside it"
    echo "  - delete AAD app '$AAD_APP_NAME' (and its service principal + federated credential)"
    echo "  - delete GitHub secrets AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_SUBSCRIPTION_ID on '$GH_REPO'"
    read -r -p "Type the resource group name to confirm: " confirm
    if [ "$confirm" != "$AZ_RESOURCE_GROUP" ]; then
      echo "Confirmation did not match. Aborting."
      exit 1
    fi
    az group delete --name "$AZ_RESOURCE_GROUP" --yes --no-wait
    echo ">>> Resource group deletion started."
  else
    echo ">>> Resource group deletion already in progress; waiting for it to finish."
  fi

  echo "    Polling every ${POLL_SECONDS}s (timeout ${TIMEOUT_SECONDS}s). This usually takes 10-30 min"
  echo "    because the Container Apps managed environment deletes asynchronously."

  start="$(date +%s)"
  while :; do
    if ! az group show --name "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
      echo ">>> Resource group '$AZ_RESOURCE_GROUP' is gone."
      break
    fi
    elapsed=$(( $(date +%s) - start ))
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
      echo "!!! Timed out after ${elapsed}s. The RG is still being deleted by Azure."
      echo "    Re-run this script to keep waiting; the OIDC + secrets cleanup below will run on the next attempt."
      exit 1
    fi
    printf '    [%4ds] still deleting...\n' "$elapsed"
    sleep "$POLL_SECONDS"
  done
else
  echo ">>> Resource group '$AZ_RESOURCE_GROUP' does not exist. Skipping RG delete."
fi

# --------------------------------------------------------------------
# 2. AAD app (cascades to SP + federated credential)
# --------------------------------------------------------------------

echo ">>> Deleting AAD app '$AAD_APP_NAME' (if present)"
APP_ID="$(az ad app list --display-name "$AAD_APP_NAME" --query '[0].appId' -o tsv 2>/dev/null || echo '')"
if [ -n "$APP_ID" ]; then
  az ad app delete --id "$APP_ID" --only-show-errors
  echo "    deleted appId=$APP_ID (SP and federated credentials removed with it)"
else
  echo "    no app named '$AAD_APP_NAME' found, skipping."
fi

# --------------------------------------------------------------------
# 3. GitHub repo secrets
# --------------------------------------------------------------------

echo ">>> Deleting GitHub repo secrets on '$GH_REPO'"
if command -v gh >/dev/null 2>&1; then
  for s in AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID; do
    if gh secret delete "$s" --repo "$GH_REPO" >/dev/null 2>&1; then
      echo "    deleted $s"
    else
      echo "    $s not present (or already deleted), skipping."
    fi
  done
else
  echo "    gh CLI not found. Delete these manually in GitHub repo settings:"
  echo "      AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID"
fi

echo ""
echo ">>> Full tear-down complete. To redeploy from scratch, run 00-bootstrap-oidc.sh, then 01-setup.sh."
