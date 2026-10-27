#!/usr/bin/env bash
set -euo pipefail

# Uploads SIGNED_BUNDLE to Central, which publishes it after the validation, and sets the output deployment-id

CENTRAL_URL="${CENTRAL_URL:-https://central.sonatype.com}"
HEADERS="$(mktemp)"
trap 'rm -f "$HEADERS"' EXIT
TOKEN="$(printf '%s:%s' "$CENTRAL_USERNAME" "$CENTRAL_PASSWORD" | base64 -w0)"
echo "::add-mask::${TOKEN}"
# read from a file, the token does not show up in the arguments of curl
printf 'Authorization: Bearer %s\n' "$TOKEN" > "$HEADERS"

NAME="$(jq -rn --arg name "$DEPLOYMENT_NAME" '$name | @uri')"
# no limit for the transfer, a large bundle takes its time
ID="$(curl -sS --fail-with-body --connect-timeout 30 -H @"$HEADERS" \
  -F "bundle=@${SIGNED_BUNDLE};type=application/octet-stream" \
  "${CENTRAL_URL}/api/v1/publisher/upload?publishingType=AUTOMATIC&name=${NAME}")"
ID="$(tr -d '"[:space:]' <<< "$ID")"
if [ -z "$ID" ]; then
  echo "::error::Central returned no deployment id"
  exit 1
fi
echo "deployment-id=${ID}" >> "$GITHUB_OUTPUT"
mkdir -p "${RUNNER_TEMP}/central-deployment"
printf '%s' "$ID" > "${RUNNER_TEMP}/central-deployment/deployment-id"
echo "uploaded as deployment ${ID}"
