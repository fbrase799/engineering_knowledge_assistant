#!/usr/bin/env bash
# Fast redeploy: rolls each app forward to IMAGE_TAG (default: latest).
# Also reasserts BACKEND_UPSTREAM so the frontend proxy keeps working.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=config.env
source "$HERE/config.env"

ENV_DOMAIN=$(az containerapp env show \
  --name "$AZ_ENVIRONMENT" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
BACKEND_INTERNAL_FQDN="${APP_BACKEND}.internal.${ENV_DOMAIN}"

if [ -n "${GITHUB_SHA:-}" ]; then
  REV_SUFFIX="sha-${GITHUB_SHA:0:7}"
else
  REV_SUFFIX="r$(date +%Y%m%d-%H%M%S)"
fi
echo ">>> Revision suffix: $REV_SUFFIX"

for pair in \
  "$APP_BACKEND  $IMAGE_BACKEND"  \
  "$APP_FRONTEND $IMAGE_FRONTEND" ; do
  # shellcheck disable=SC2086
  set -- $pair
  APP="$1"; IMG="$2"
  echo ">>> $APP -> $IMG"
  if [ "$APP" = "$APP_FRONTEND" ]; then
    az containerapp update \
      --name "$APP" \
      --resource-group "$AZ_RESOURCE_GROUP" \
      --image "$IMG" \
      --revision-suffix "$REV_SUFFIX" \
      --set-env-vars "BACKEND_UPSTREAM=${BACKEND_INTERNAL_FQDN}" \
      --output none
  else
    az containerapp update \
      --name "$APP" \
      --resource-group "$AZ_RESOURCE_GROUP" \
      --image "$IMG" \
      --revision-suffix "$REV_SUFFIX" \
      --output none
  fi
done

FQDN=$(az containerapp show \
  --name "$APP_FRONTEND" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo ">>> Deploy complete: https://$FQDN"
