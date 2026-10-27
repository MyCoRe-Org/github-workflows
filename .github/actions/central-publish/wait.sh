#!/usr/bin/env bash
set -euo pipefail

# Waits until Central validated DEPLOYMENT_ID, at most WAIT_MINUTES, and sets the output state to its last state

CENTRAL_URL="${CENTRAL_URL:-https://central.sonatype.com}"
POLL_INTERVAL="${POLL_INTERVAL:-10}"
STATE=''
HEADERS="$(mktemp)"
mkdir -p "${RUNNER_TEMP}/central-deployment"
trap 'rm -f "$HEADERS"; echo "state=${STATE}" >> "$GITHUB_OUTPUT"; printf "%s" "$STATE" > "${RUNNER_TEMP}/central-deployment/state"' EXIT
TOKEN="$(printf '%s:%s' "$CENTRAL_USERNAME" "$CENTRAL_PASSWORD" | base64 -w0)"
echo "::add-mask::${TOKEN}"
printf 'Authorization: Bearer %s\n' "$TOKEN" > "$HEADERS"

DEADLINE=$(($(date +%s) + ${WAIT_MINUTES:-30} * 60))
while :; do
  # a hanging request would otherwise outlast the deadline
  if RESPONSE="$(curl -sS --fail-with-body --connect-timeout 10 --max-time 60 -X POST -H @"$HEADERS" \
    "${CENTRAL_URL}/api/v1/publisher/status?id=${DEPLOYMENT_ID}" 2>&1)"; then
    STATE="$(jq -r '.deploymentState // empty' <<< "$RESPONSE")"
    case "$STATE" in
      VALIDATED | PUBLISHING | PUBLISHED)
        echo "deployment ${DEPLOYMENT_ID} is ${STATE}, Central publishes it"
        exit 0
        ;;
      FAILED)
        echo "::error::Central refused deployment ${DEPLOYMENT_ID}: $(jq -c '.errors // {}' <<< "$RESPONSE")"
        exit 1
        ;;
      *)
        echo "deployment ${DEPLOYMENT_ID} is ${STATE:-in an unknown state}"
        ;;
    esac
  else
    echo "cannot read the state of deployment ${DEPLOYMENT_ID} yet: ${RESPONSE##*$'\n'}"
  fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "::error::deployment ${DEPLOYMENT_ID} was not validated within ${WAIT_MINUTES:-30} minutes. It may still be published, see ${CENTRAL_URL}/publishing/deployments"
    exit 1
  fi
  sleep "$POLL_INTERVAL"
done
