#!/usr/bin/env bash
set -euo pipefail

# TO may only change pom.xml files compared to FROM, and in them only values: every changed line is
# <element>value</element> with an element of ALLOWED and keeps its element, no line is only added or only removed,
# and an added value is the one ALLOWED gives for its element, '*' allowing every value

fail() {
  echo "::error::${NAME} is refused, $1"
  exit 1
}

declare -A ALLOWED_VALUES=()
while IFS= read -r spec; do
  spec="$(sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' <<< "$spec")"
  element="${spec%%=*}"
  value="${spec#*=}"
  if [ "$element" != "$spec" ] && [ -n "$element" ] && [ -n "$value" ]; then
    ALLOWED_VALUES["$element"]="$value"
  fi
done <<< "${ALLOWED:-}"

RE='^<([A-Za-z0-9._-]+)>([^<]*)</([A-Za-z0-9._-]+)>$'
while IFS=$'\t' read -r status path; do
  if [ "$status" != M ] || [[ "$path" != pom.xml && "$path" != */pom.xml ]]; then
    fail "it changes ${path} (${status}), only pom.xml files may change"
  fi
  REMOVED=()
  ADDED=()
  while IFS= read -r line; do
    content="$(sed -E 's/^.[[:space:]]*//; s/[[:space:]]*$//' <<< "$line")"
    if [[ ! "$content" =~ $RE ]] || [ "${BASH_REMATCH[1]}" != "${BASH_REMATCH[3]}" ] \
      || [ -z "${ALLOWED_VALUES[${BASH_REMATCH[1]}]+set}" ]; then
      fail "${path} changes the line '${content}'"
    fi
    element="${BASH_REMATCH[1]}"
    if [ "${line:0:1}" = - ]; then
      REMOVED+=("$element")
    elif [ "${ALLOWED_VALUES[$element]}" = '*' ] || [ "${BASH_REMATCH[2]}" = "${ALLOWED_VALUES[$element]}" ]; then
      ADDED+=("$element")
    else
      fail "${path} sets '${content}'"
    fi
  done < <(diff --old-line-format='-%L' --new-line-format='+%L' --unchanged-line-format='' \
    <(git show "${FROM}:${path}") <(git show "${TO}:${path}") || true)
  # values change in place, a line that is only added or only removed is refused
  [ "${REMOVED[*]}" = "${ADDED[*]}" ] || fail "${path} adds or removes lines"
done < <(git diff --no-renames --name-status "$FROM" "$TO")

echo "${NAME} only changes the values of $(printf '%s ' "${!ALLOWED_VALUES[@]}")in pom.xml files"
