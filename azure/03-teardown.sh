#!/usr/bin/env bash
# Deletes the entire resource group and everything in it. Billing stops
# almost immediately. The AAD app registration and federated credential
# from 00-bootstrap-oidc.sh are NOT deleted — they survive tear-downs
# so the next 01-setup.sh can reuse them.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=config.env
source "$HERE/config.env"

if ! az group show --name "$AZ_RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Resource group '$AZ_RESOURCE_GROUP' does not exist. Nothing to do."
  exit 0
fi

echo "About to DELETE resource group '$AZ_RESOURCE_GROUP' and all resources inside it."
echo "(This does not affect the AAD app or your GitHub secrets.)"
read -r -p "Type the resource group name to confirm: " confirm
if [ "$confirm" != "$AZ_RESOURCE_GROUP" ]; then
  echo "Confirmation did not match. Aborting."
  exit 1
fi

az group delete --name "$AZ_RESOURCE_GROUP" --yes --no-wait
echo ">>> Deletion started (running in the background; takes ~2-5 min)."
echo "    Check status: az group show --name $AZ_RESOURCE_GROUP --query properties.provisioningState -o tsv"
