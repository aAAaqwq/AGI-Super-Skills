#!/usr/bin/env bash
# ============================================================================
# deploy-verify.sh — Deploy to Vercel + Smoke Test + Browser Verification
# ============================================================================
# One command: deploy → HTTP check → browser snapshot + screenshot (optional).
#
# Usage:
#   ./deploy-verify.sh <repo_path> [pages...]
#
# Examples:
#   ./deploy-verify.sh /tmp/flyme-new / /search /explore /map
#   VERIFY_BROWSER=1 ./deploy-verify.sh /tmp/flyme-new / /search
#   VERIFY_MANIFEST=/tmp/tasks/verify-manifest.json VERIFY_BROWSER=1 ./deploy-verify.sh /tmp/flyme-new
#
# Env vars:
#   VERCEL_FORCE=1      — add --force flag (bust cache)
#   VERCEL_FLAGS=""     — extra vercel flags
#   DEPLOY_URL=""       — skip deploy, just verify this URL
#   VERIFY_BROWSER=1    — enable actionbook browser verification
#   VERIFY_MANIFEST=""  — path to JSON manifest for per-page expectations + interactions
#   VERIFY_EXPECT=""    — (legacy) global comma-separated text to expect in DOM
#   VERIFY_SHOTS_DIR    — screenshot output dir (default: /tmp/deploy-shots)
#
# Manifest format (JSON):
#   {
#     "pages": {
#       "/search": {
#         "expect": ["Search Flights"],     # text that must exist
#         "reject": ["Error", "500"],        # text that must NOT exist
#         "interact": [                      # optional: steps before final check
#           {"action": "click", "match": "Singapore → Tokyo"},
#           {"action": "wait", "ms": 2000},
#           {"action": "expect", "text": ["Book Now"]}
#         ]
#       }
#     }
#   }
#
# Output: JSON summary for Orchestrator consumption
# ============================================================================

set -euo pipefail

REPO="${1:?Usage: deploy-verify.sh <repo_path> [pages...]}"
shift

VERIFY_BROWSER="${VERIFY_BROWSER:-0}"
VERIFY_SHOTS_DIR="${VERIFY_SHOTS_DIR:-/tmp/deploy-shots}"
VERIFY_EXPECT="${VERIFY_EXPECT:-}"
VERIFY_MANIFEST="${VERIFY_MANIFEST:-}"

# If manifest provided and no pages on CLI, extract pages from manifest
if [ -n "$VERIFY_MANIFEST" ] && [ "$#" -eq 0 ] && [ -f "$VERIFY_MANIFEST" ]; then
  mapfile -t PAGES < <(jq -r '.pages | keys[]' "$VERIFY_MANIFEST" 2>/dev/null)
  [ ${#PAGES[@]} -eq 0 ] && PAGES=("/")
else
  PAGES=("${@:-/}")
fi

# ---- Deploy ----
if [ -z "${DEPLOY_URL:-}" ]; then
  echo '{"phase":"deploy","status":"starting"}'
  cd "$REPO"

  FORCE_FLAG=""
  [ "${VERCEL_FORCE:-0}" = "1" ] && FORCE_FLAG="--force"

  DEPLOY_OUTPUT=$(npx vercel --yes --prod $FORCE_FLAG ${VERCEL_FLAGS:-} 2>&1)
  DEPLOY_URL=$(echo "$DEPLOY_OUTPUT" | grep -o 'https://[^ ]*\.vercel\.app' | tail -1)

  if [ -z "$DEPLOY_URL" ]; then
    echo '{"phase":"deploy","status":"failed","output":"'"$(echo "$DEPLOY_OUTPUT" | tail -3 | tr '\n' ' ')"'"}'
    exit 1
  fi

  ALIAS_URL=$(echo "$DEPLOY_OUTPUT" | grep "Aliased:" | grep -o 'https://[^ ]*' || echo "$DEPLOY_URL")
  echo '{"phase":"deploy","status":"success","url":"'"$ALIAS_URL"'"}'
else
  ALIAS_URL="$DEPLOY_URL"
  echo '{"phase":"deploy","status":"skipped","url":"'"$ALIAS_URL"'"}'
fi

# ---- HTTP Verify ----
echo '{"phase":"verify","status":"starting","pages":'"$(printf '%s\n' "${PAGES[@]}" | jq -R . | jq -s .)"'}'

PASS=0
FAIL=0
RESULTS="["

for PAGE in "${PAGES[@]}"; do
  URL="${ALIAS_URL}${PAGE}"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$URL" 2>/dev/null || echo "000")

  if [ "$HTTP_CODE" = "200" ]; then
    STATUS="pass"
    PASS=$((PASS + 1))
  else
    STATUS="fail"
    FAIL=$((FAIL + 1))
  fi

  RESULTS="${RESULTS}{\"page\":\"${PAGE}\",\"http\":${HTTP_CODE},\"status\":\"${STATUS}\"},"
done

RESULTS="${RESULTS%,}]"

TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
  VERDICT="all_pass"
else
  VERDICT="has_failures"
fi

echo '{"phase":"summary","verdict":"'"$VERDICT"'","pass":'"$PASS"',"fail":'"$FAIL"',"total":'"$TOTAL"',"results":'"$RESULTS"'}'

# ---- Browser Verification (optional) ----
if [ "$VERIFY_BROWSER" = "1" ] && command -v actionbook &>/dev/null; then
  echo '{"phase":"browser_verify","status":"starting"}'
  mkdir -p "$VERIFY_SHOTS_DIR"

  BROWSER_PASS=0
  BROWSER_FAIL=0

  # Open first page
  FIRST_URL="${ALIAS_URL}${PAGES[0]}"
  actionbook browser open "$FIRST_URL" --headless 2>/dev/null

  # ---- Helper: check expect/reject arrays against snapshot ----
  check_text_arrays() {
    local snapshot="$1"
    local page="$2"
    local missing=""
    local rejected=""

    # Per-page expect from manifest
    if [ -n "$VERIFY_MANIFEST" ] && [ -f "$VERIFY_MANIFEST" ]; then
      local expects
      expects=$(jq -r --arg p "$page" '.pages[$p].expect // [] | .[]' "$VERIFY_MANIFEST" 2>/dev/null || true)
      while IFS= read -r e; do
        [ -z "$e" ] && continue
        if ! echo "$snapshot" | grep -qi "$e"; then
          missing="${missing}${e},"
        fi
      done <<< "$expects"

      local rejects
      rejects=$(jq -r --arg p "$page" '.pages[$p].reject // [] | .[]' "$VERIFY_MANIFEST" 2>/dev/null || true)
      while IFS= read -r r; do
        [ -z "$r" ] && continue
        if echo "$snapshot" | grep -qi "$r"; then
          rejected="${rejected}${r},"
        fi
      done <<< "$rejects"
    fi

    # Legacy global VERIFY_EXPECT
    if [ -z "$VERIFY_MANIFEST" ] && [ -n "$VERIFY_EXPECT" ]; then
      IFS=',' read -ra EXPS <<< "$VERIFY_EXPECT"
      for ex in "${EXPS[@]}"; do
        if ! echo "$snapshot" | grep -qi "$ex"; then
          missing="${missing}${ex},"
        fi
      done
    fi

    # Return result
    if [ -n "$missing" ] || [ -n "$rejected" ]; then
      echo "fail|${missing%,}|${rejected%,}"
    else
      echo "pass||"
    fi
  }

  # ---- Helper: run interact steps from manifest ----
  run_interactions() {
    local page="$1"
    [ -z "$VERIFY_MANIFEST" ] && return 0
    [ ! -f "$VERIFY_MANIFEST" ] && return 0

    local steps
    steps=$(jq -c --arg p "$page" '.pages[$p].interact // [] | .[]' "$VERIFY_MANIFEST" 2>/dev/null || true)
    [ -z "$steps" ] && return 0

    local interact_fail=0
    while IFS= read -r step; do
      [ -z "$step" ] && continue
      local action
      action=$(echo "$step" | jq -r '.action')

      case "$action" in
        click)
          local match
          match=$(echo "$step" | jq -r '.match // empty')
          if [ -n "$match" ]; then
            # Find ref by matching text in snapshot
            local ref
            ref=$(actionbook browser snapshot 2>/dev/null | grep -i "$match" | head -1 | grep -o '^e[0-9]*' || true)
            if [ -n "$ref" ]; then
              actionbook browser click --ref-id "$ref" 2>/dev/null || true
            else
              echo "{\"interact\":\"warn\",\"action\":\"click\",\"match\":\"${match}\",\"reason\":\"ref_not_found\"}"
            fi
          fi
          ;;
        wait)
          local ms
          ms=$(echo "$step" | jq -r '.ms // 1000')
          sleep "$(echo "scale=1; $ms / 1000" | bc)"
          ;;
        expect)
          local snapshot_now
          snapshot_now=$(actionbook browser snapshot 2>/dev/null || echo "")
          local texts
          texts=$(echo "$step" | jq -r '.text // [] | .[]')
          while IFS= read -r t; do
            [ -z "$t" ] && continue
            if ! echo "$snapshot_now" | grep -qi "$t"; then
              echo "{\"interact\":\"fail\",\"action\":\"expect\",\"missing\":\"${t}\"}"
              interact_fail=1
            fi
          done <<< "$texts"
          ;;
      esac
    done <<< "$steps"
    return $interact_fail
  }

  # ---- Verify each page ----
  for PAGE in "${PAGES[@]}"; do
    URL="${ALIAS_URL}${PAGE}"
    PAGE_SLUG=$(echo "$PAGE" | sed 's|^/||; s|/|-|g')
    [ -z "$PAGE_SLUG" ] && PAGE_SLUG="home"

    actionbook browser goto "$URL" 2>/dev/null
    sleep 2

    # Screenshot (before interaction)
    SHOT_PATH="${VERIFY_SHOTS_DIR}/${PAGE_SLUG}.png"
    actionbook browser screenshot "$SHOT_PATH" 2>/dev/null

    # DOM snapshot
    SNAPSHOT=$(actionbook browser snapshot 2>/dev/null || echo "")

    if [ -z "$SNAPSHOT" ] || [ ${#SNAPSHOT} -lt 50 ]; then
      echo "{\"page\":\"${PAGE}\",\"browser\":\"fail\",\"reason\":\"empty_snapshot\"}"
      BROWSER_FAIL=$((BROWSER_FAIL + 1))
      continue
    fi

    # Check initial expect/reject
    RESULT=$(check_text_arrays "$SNAPSHOT" "$PAGE")
    IFS='|' read -r STATUS MISS REJ <<< "$RESULT"

    if [ "$STATUS" = "fail" ]; then
      echo "{\"page\":\"${PAGE}\",\"browser\":\"fail\",\"missing\":\"${MISS}\",\"rejected\":\"${REJ}\",\"screenshot\":\"${SHOT_PATH}\"}"
      BROWSER_FAIL=$((BROWSER_FAIL + 1))
      continue
    fi

    # Run interactions if defined
    INTERACT_OK=0
    if run_interactions "$PAGE"; then
      INTERACT_OK=1
    fi

    # Post-interaction screenshot
    if [ -n "$VERIFY_MANIFEST" ] && jq -e --arg p "$PAGE" '.pages[$p].interact | length > 0' "$VERIFY_MANIFEST" &>/dev/null; then
      SHOT_AFTER="${VERIFY_SHOTS_DIR}/${PAGE_SLUG}-after.png"
      actionbook browser screenshot "$SHOT_AFTER" 2>/dev/null
      echo "{\"page\":\"${PAGE}\",\"browser\":\"pass\",\"screenshot\":\"${SHOT_PATH}\",\"after\":\"${SHOT_AFTER}\"}"
    else
      echo "{\"page\":\"${PAGE}\",\"browser\":\"pass\",\"screenshot\":\"${SHOT_PATH}\",\"elements\":$(echo "$SNAPSHOT" | wc -l | tr -d ' ')}"
    fi
    BROWSER_PASS=$((BROWSER_PASS + 1))
  done

  # Console error check (after visiting all pages)
  CONSOLE_ERRORS=""
  CONSOLE_LOG=$(actionbook browser console --level error 2>/dev/null || echo "")
  if [ -n "$CONSOLE_LOG" ]; then
    # Filter out known benign errors (Cesium skybox textures, favicon)
    CRITICAL_ERRORS=$(echo "$CONSOLE_LOG" | grep -viE 'favicon|SkyBox|moonSmall|ion-credit|IAU2006|No console messages captured' | head -5 || true)
    if [ -n "$CRITICAL_ERRORS" ]; then
      CONSOLE_ERRORS=$(echo "$CRITICAL_ERRORS" | tr '\n' ' ' | cut -c1-200)
      echo "{\"phase\":\"console_check\",\"status\":\"warnings\",\"errors\":\"${CONSOLE_ERRORS}\"}"
    else
      echo '{"phase":"console_check","status":"clean"}'
    fi
  else
    echo '{"phase":"console_check","status":"clean"}'
  fi

  # Close browser
  actionbook browser close 2>/dev/null || true

  if [ "$BROWSER_FAIL" -eq 0 ]; then
    echo '{"phase":"browser_verify","status":"all_pass","pass":'"$BROWSER_PASS"',"screenshots":"'"$VERIFY_SHOTS_DIR"'"}'
  else
    echo '{"phase":"browser_verify","status":"has_failures","pass":'"$BROWSER_PASS"',"fail":'"$BROWSER_FAIL"'}'
  fi
fi
