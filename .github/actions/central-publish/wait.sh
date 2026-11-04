#!/usr/bin/env bash
set -euo pipefail

# Waits until Central validated DEPLOYMENT_ID, at most WAIT_MINUTES, and sets the output state to its last state

CENTRAL_URL="${CENTRAL_URL:-https://central.sonatype.com}"
POLL_INTERVAL="${POLL_INTERVAL:-10}"
STATE=''
HEADERS="$(mktemp)"
ERRORS="$(mktemp)"
mkdir -p "${RUNNER_TEMP}/central-deployment"
trap 'rm -f "$HEADERS" "$ERRORS"; echo "state=${STATE}" >> "$GITHUB_OUTPUT"; printf "%s" "$STATE" > "${RUNNER_TEMP}/central-deployment/state"' EXIT
TOKEN="$(printf '%s:%s' "$CENTRAL_USERNAME" "$CENTRAL_PASSWORD" | base64 -w0)"
echo "::add-mask::${TOKEN}"
printf 'Authorization: Bearer %s\n' "$TOKEN" > "$HEADERS"

short() { # short <text>: the text on one line, at most 200 characters
  printf '%s' "$1" | tr -s '\r\n\t ' ' ' | cut -c1-200
}

DEADLINE=$(($(date +%s) + ${WAIT_MINUTES:-30} * 60))
while :; do
  # a hanging request would otherwise outlast the deadline
  if RESPONSE="$(curl -sS --fail-with-body --connect-timeout 10 --max-time 60 -X POST -H @"$HEADERS" \
    "${CENTRAL_URL}/api/v1/publisher/status?id=${DEPLOYMENT_ID}" 2> "$ERRORS")"; then
    # an answer that is no JSON, e.g. the maintenance page of a proxy or of a wrong CENTRAL_URL, reports no state, the
    # loop asks again. STATE keeps the last state Central reported, as after a failed request
    if ! REPORTED="$(jq -r '.deploymentState // empty' <<< "$RESPONSE" 2> /dev/null)"; then
      echo "the answer about deployment ${DEPLOYMENT_ID} is no JSON of Central: $(short "$RESPONSE")"
    # only a plain state, an object or a line break would end up in the outputs
    elif [ -n "$REPORTED" ] && [[ ! "$REPORTED" =~ ^[A-Z_]+$ ]]; then
      echo "the answer about deployment ${DEPLOYMENT_ID} names no plain state: $(short "$RESPONSE")"
    else
      STATE="${REPORTED:-$STATE}"
      case "$REPORTED" in
        VALIDATED | PUBLISHING | PUBLISHED)
          echo "deployment ${DEPLOYMENT_ID} is ${REPORTED}, Central publishes it"
          exit 0
          ;;
        FAILED)
          echo "::error::Central refused deployment ${DEPLOYMENT_ID}: $(jq -c '.errors // {}' <<< "$RESPONSE")"
          exit 1
          ;;
        *)
          echo "deployment ${DEPLOYMENT_ID} is ${REPORTED:-in an unknown state}"
          ;;
      esac
    fi
  else
    # the message of curl names the HTTP status, the body of Central the reason, if it sends one
    BODY="$(short "$RESPONSE")"
    echo "cannot read the state of deployment ${DEPLOYMENT_ID} yet: $(tail -n 1 "$ERRORS")${BODY:+, ${BODY}}"
  fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "::error::deployment ${DEPLOYMENT_ID} was not validated within ${WAIT_MINUTES:-30} minutes. It may still be published, see ${CENTRAL_URL}/publishing/deployments"
    exit 1
  fi
  sleep "$POLL_INTERVAL"
done
