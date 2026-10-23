#!/usr/bin/env bash
set -uo pipefail

# a file edited on Windows would otherwise turn the branch into 'main\r' and skip the target
TARGETS="${TARGETS//$'\r'/}"
WAIT="${WAIT:-false}"
WAIT_MINUTES="${WAIT_MINUTES:-300}"
POLL_INTERVAL="${POLL_INTERVAL:-60}"
FAILURES=()
RUNS=()
declare -A RESULTS=()

fail() { # fail <message>, reports an error and collects it for the output 'failures'
  echo "::error::$1"
  FAILURES+=("$1")
}

# an organization secret that is not shared with the repository arrives as an empty string
if [ -z "${GH_TOKEN:-}" ]; then
  fail "the token is empty, check that DISPATCH_TOKEN is shared with ${GITHUB_REPOSITORY:-the repository} and passed on by the caller"
  TARGETS=''
fi

dispatch() { # dispatch <repository> <workflow> <branch>
  local out id url
  if ! out="$(gh api --method POST "repos/$1/actions/workflows/$2/dispatches" \
    -f "ref=$3" -F return_run_details=true 2>&1 < /dev/null)"; then
    fail "dispatch of $2 in $1@$3 failed: ${out##*$'\n'}"
    return
  fi
  id="$(jq -r '.workflow_run_id // empty' <<< "$out" 2> /dev/null)"
  url="$(jq -r '.html_url // empty' <<< "$out" 2> /dev/null)"
  echo "dispatched $2 in $1@$3${url:+ ${url}}"
  if [ -n "$id" ]; then
    RUNS+=("$1 $2 $3 ${id} ${url}")
  elif [ "$WAIT" = true ]; then
    echo "::warning::no run id returned for $2 in $1@$3, not waiting for it"
  fi
}

while read -r repository workflow branch; do
  [ -z "$repository" ] && continue
  [[ "$repository" == \#* ]] && continue
  branch="${branch:-$DEFAULT_BRANCH}"
  if ! ERR="$(gh api "repos/${repository}" --silent 2>&1 < /dev/null)"; then
    fail "cannot access ${repository}: ${ERR##*$'\n'}"
    continue
  fi

  # git does not allow '*', '?' and '[' in branch names, so they mark a pattern
  if [[ "$branch" == *[*?[]* ]]; then
    if ! NAMES="$(gh api --paginate "repos/${repository}/branches?per_page=100" --jq '.[].name' 2>&1 < /dev/null)"; then
      fail "cannot list the branches of ${repository}: ${NAMES##*$'\n'}"
      continue
    fi
    MATCHED=0
    while read -r name; do
      # shellcheck disable=SC2053 # the unquoted right-hand side is the pattern
      [[ "$name" == $branch ]] || continue
      if ERR="$(gh api "repos/${repository}/contents/.github/workflows/${workflow}?ref=${name}" --silent 2>&1 < /dev/null)"; then
        MATCHED=1
        dispatch "$repository" "$workflow" "$name"
      elif [[ "$ERR" == *"HTTP 404"* ]]; then
        echo "${repository}@${name} has no ${workflow}, skipped"
      else
        fail "cannot check ${workflow} in ${repository}@${name}: ${ERR##*$'\n'}"
      fi
    done <<< "$NAMES"
    if [ "$MATCHED" = 0 ]; then
      echo "::notice::no branch of ${repository} matching ${branch} has ${workflow}"
    fi
    continue
  fi

  if ! ERR="$(gh api "repos/${repository}/branches/${branch}" --silent 2>&1 < /dev/null)"; then
    if [[ "$ERR" == *"HTTP 404"* ]]; then
      echo "::notice::${repository} has no branch ${branch}, skipped"
    else
      fail "cannot check ${repository}@${branch}: ${ERR##*$'\n'}"
    fi
    continue
  fi
  dispatch "$repository" "$workflow" "$branch"
done <<< "$TARGETS"

if [ "$WAIT" = true ] && [ "${#RUNS[@]}" -gt 0 ]; then
  echo "waiting for ${#RUNS[@]} runs, at most ${WAIT_MINUTES} minutes"
  # ends before the job limit of GitHub, which would cancel the job without a failure to report
  DEADLINE=$(($(date +%s) + WAIT_MINUTES * 60))
  while [ "${#RESULTS[@]}" -lt "${#RUNS[@]}" ]; do
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
      for i in "${!RUNS[@]}"; do
        [ -n "${RESULTS[$i]:-}" ] && continue
        read -r repository workflow branch id url <<< "${RUNS[$i]}"
        RESULTS[$i]=unfinished
        fail "${workflow} in ${repository}@${branch} did not finish within ${WAIT_MINUTES} minutes, ${url}"
      done
      break
    fi
    sleep "$POLL_INTERVAL"
    for i in "${!RUNS[@]}"; do
      [ -n "${RESULTS[$i]:-}" ] && continue
      read -r repository workflow branch id url <<< "${RUNS[$i]}"
      if ! STATE="$(gh api "repos/${repository}/actions/runs/${id}" --jq '.status + " " + (.conclusion // "")' 2>&1 < /dev/null)"; then
        echo "cannot check ${url} yet: ${STATE##*$'\n'}"
        continue
      fi
      read -r status conclusion <<< "$STATE"
      [ "$status" = completed ] || continue
      RESULTS[$i]="${conclusion:-unknown}"
      case "${RESULTS[$i]}" in
        success)
          echo "${workflow} in ${repository}@${branch} succeeded"
          ;;
        cancelled | skipped)
          echo "::warning::${workflow} in ${repository}@${branch} was ${RESULTS[$i]}, ${url}"
          ;;
        *)
          fail "${workflow} in ${repository}@${branch} ended with ${RESULTS[$i]}, ${url}"
          ;;
      esac
    done
  done
fi

if [ -n "${GITHUB_STEP_SUMMARY:-}" ] && [ "${#RUNS[@]}" -gt 0 ]; then
  {
    echo "| Repository | Workflow | Branch | Run |"
    echo "|------------|----------|--------|-----|"
    for i in "${!RUNS[@]}"; do
      read -r repository workflow branch id url <<< "${RUNS[$i]}"
      echo "| ${repository} | ${workflow} | ${branch} | [${RESULTS[$i]:-started}](${url}) |"
    done
  } >> "$GITHUB_STEP_SUMMARY"
fi

if [ "${#FAILURES[@]}" -gt 0 ]; then
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    {
      echo 'failures<<__FAILURES_EOF__'
      printf '%s\n' "${FAILURES[@]}"
      echo '__FAILURES_EOF__'
    } >> "$GITHUB_OUTPUT"
  fi
  exit 1
fi
