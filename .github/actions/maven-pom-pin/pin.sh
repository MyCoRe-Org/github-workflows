#!/usr/bin/env bash
set -euo pipefail

POM="${POM:-pom.xml}"

for value in "${PROPERTY:-}" "${VALUE:-}" "${SCM_URL:-}"; do
  case "$value" in
    *'|'* | *'&'* | *\\* | *'<'* | *'>'*)
      echo "::error::unsupported character in '${value}'"
      exit 1
      ;;
  esac
done

if [ -n "${PROPERTY:-}" ] && [ -n "${VALUE:-}" ]; then
  PROPERTY_RE="${PROPERTY//./\\.}"
  PREVIOUS="$(sed -n -E "s|.*<${PROPERTY_RE}>([^<]*)</${PROPERTY_RE}>.*|\1|p" "$POM" | head -1)"
  if [ -z "$PREVIOUS" ]; then
    echo "::error::no ${PROPERTY} property found in ${POM}"
    exit 1
  fi
  sed -i -E "0,/<${PROPERTY_RE}>/ s|<${PROPERTY_RE}>[^<]*</${PROPERTY_RE}>|<${PROPERTY}>${VALUE}</${PROPERTY}>|" "$POM"
  grep -qF "<${PROPERTY}>${VALUE}</${PROPERTY}>" "$POM"
  echo "${PROPERTY} ${PREVIOUS} -> ${VALUE}"
  echo "previous-property=$PREVIOUS" >> "$GITHUB_OUTPUT"
fi

if [ -n "${SCM_URL:-}" ]; then
  PREVIOUS_URL="$(sed -n -E '/<scm>/,/<\/scm>/ s|.*<url>([^<]*)</url>.*|\1|p' "$POM" | head -1)"
  if [ -n "$PREVIOUS_URL" ]; then
    sed -i -E "/<scm>/,/<\/scm>/ s|<url>[^<]*</url>|<url>${SCM_URL}</url>|" "$POM"
    grep -qF "<url>${SCM_URL}</url>" "$POM"
    echo "scm.url ${PREVIOUS_URL} -> ${SCM_URL}"
    echo "previous-scm-url=$PREVIOUS_URL" >> "$GITHUB_OUTPUT"
  else
    echo "no scm url found in ${POM}, skipped"
  fi
fi
