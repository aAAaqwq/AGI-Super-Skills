#!/usr/bin/env bash
# ============================================================================
# watchdog.sh v2 — Background ACP/Mode 7 Worker Monitor
# ============================================================================
# Polls a git worktree for Worker completion. Fire-and-forget.
# v2: + git diff on failure + salvage + Discord notify hook
#
# Usage:
#   ./watchdog.sh <worktree_path> [poll_interval_seconds] [max_idle_minutes]
#
# Env vars:
#   WATCHDOG_NOTIFY=discord    — send completion/failure to Discord via openclaw
#   WATCHDOG_CHANNEL=<id>      — Discord channel id for notifications
#   WATCHDOG_SALVAGE=stash     — on failure: stash | reset | none (default: none)
#   WATCHDOG_TASK_ID=<id>      — task id for notifications
#
# Output: JSON lines for Orchestrator consumption
# ============================================================================

set -euo pipefail

WORKTREE="${1:?Usage: watchdog.sh <worktree_path> [poll_seconds] [max_idle_min]}"
POLL_INTERVAL="${2:-30}"
MAX_IDLE_MIN="${3:-10}"
NOTIFY="${WATCHDOG_NOTIFY:-none}"
CHANNEL="${WATCHDOG_CHANNEL:-}"
SALVAGE="${WATCHDOG_SALVAGE:-none}"
TASK_ID="${WATCHDOG_TASK_ID:-unknown}"

# Validate worktree
if [ ! -d "$WORKTREE/.git" ] && [ ! -f "$WORKTREE/.git" ]; then
  echo '{"status":"error","message":"Not a git worktree: '"$WORKTREE"'"}'
  exit 1
fi

BASELINE_COMMIT=$(cd "$WORKTREE" && git log -1 --format=%H 2>/dev/null || echo "none")
LAST_CHANGE=$(date +%s)
POLL_COUNT=0

# ---- Helper: get diff summary ----
get_diff_summary() {
  local wt="$1"
  local stat modified_files changed_lines
  stat=$(cd "$wt" && git diff --stat 2>/dev/null || echo "")
  modified_files=$(cd "$wt" && git status --short 2>/dev/null | wc -l | tr -d ' ')
  changed_lines=$(cd "$wt" && git diff --numstat 2>/dev/null | awk '{s+=$1+$2}END{print s+0}')
  echo "{\"modified_files\":$modified_files,\"changed_lines\":$changed_lines,\"stat\":$(echo "$stat" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '""')}"
}

# ---- Helper: salvage uncommitted work ----
do_salvage() {
  local wt="$1" mode="$2"
  case "$mode" in
    stash)
      local stash_msg="watchdog-salvage-${TASK_ID}-$(date +%s)"
      cd "$wt" && git stash push -u -m "$stash_msg" 2>/dev/null
      echo "$stash_msg"
      ;;
    reset)
      cd "$wt" && git checkout -- . 2>/dev/null && git clean -fd 2>/dev/null
      echo "reset"
      ;;
    *)
      echo "none"
      ;;
  esac
}

# ---- Helper: notify ----
notify() {
  local msg="$1"
  if [ "$NOTIFY" = "discord" ] && [ -n "$CHANNEL" ]; then
    # Use openclaw CLI if available, otherwise just log
    if command -v openclaw &>/dev/null; then
      openclaw message send --channel "$CHANNEL" --message "$msg" 2>/dev/null || true
    fi
  fi
}

echo '{"status":"started","task":"'"$TASK_ID"'","worktree":"'"$WORKTREE"'","baseline":"'"${BASELINE_COMMIT:0:7}"'","poll_interval":'"$POLL_INTERVAL"'}'

while true; do
  sleep "$POLL_INTERVAL"
  POLL_COUNT=$((POLL_COUNT + 1))

  # Check for .task-result.json (structured completion signal)
  if [ -f "$WORKTREE/.task-result.json" ]; then
    RESULT=$(cat "$WORKTREE/.task-result.json" 2>/dev/null)
    CURRENT_COMMIT=$(cd "$WORKTREE" && git log -1 --format=%H 2>/dev/null || echo "none")
    SHORT=$(cd "$WORKTREE" && git log -1 --oneline 2>/dev/null)
    echo "{\"status\":\"completed_structured\",\"task\":\"$TASK_ID\",\"commit\":\"$SHORT\",\"polls\":$POLL_COUNT,\"result\":$RESULT}"
    notify "✅ Worker [$TASK_ID] 完成 (structured): $SHORT"
    exit 0
  fi

  # Check for new commit (fallback if no .task-result.json)
  CURRENT_COMMIT=$(cd "$WORKTREE" && git log -1 --format=%H 2>/dev/null || echo "none")
  if [ "$CURRENT_COMMIT" != "$BASELINE_COMMIT" ]; then
    SHORT=$(cd "$WORKTREE" && git log -1 --oneline 2>/dev/null)
    DIFF=$(get_diff_summary "$WORKTREE")
    echo '{"status":"completed","task":"'"$TASK_ID"'","commit":"'"$SHORT"'","polls":'"$POLL_COUNT"',"diff":'"$DIFF"'}'
    notify "✅ Worker [$TASK_ID] 完成: $SHORT"
    exit 0
  fi

  # Check if acpx/codex/claude is still running
  WORKER_COUNT=$(ps aux 2>/dev/null | grep -cE "[a]cpx|[c]odex|[c]laude.*dangerously" || true)
  WORKER_COUNT=${WORKER_COUNT:-0}; WORKER_COUNT=$(( WORKER_COUNT + 0 ))
  if [ "$WORKER_COUNT" -eq 0 ]; then
    MODIFIED=$(cd "$WORKTREE" && git status --short | wc -l | tr -d ' ')
    if [ "$MODIFIED" -gt 0 ]; then
      DIFF=$(get_diff_summary "$WORKTREE")
      SALVAGE_RESULT=$(do_salvage "$WORKTREE" "$SALVAGE")
      echo '{"status":"exited_uncommitted","task":"'"$TASK_ID"'","modified_files":'"$MODIFIED"',"polls":'"$POLL_COUNT"',"diff":'"$DIFF"',"salvage":"'"$SALVAGE_RESULT"'"}'
      notify "⚠️ Worker [$TASK_ID] 异常退出: $MODIFIED 个文件未提交 | salvage=$SALVAGE_RESULT"
    else
      echo '{"status":"exited_no_changes","task":"'"$TASK_ID"'","polls":'"$POLL_COUNT"'}'
      notify "❌ Worker [$TASK_ID] 退出无产出"
    fi
    exit 1
  fi

  # Check for idle (no file changes)
  MODIFIED=$(cd "$WORKTREE" && git status --short | wc -l | tr -d ' ')
  NOW=$(date +%s)
  if [ "$MODIFIED" -gt 0 ]; then
    LAST_CHANGE=$NOW
  fi

  IDLE_SECONDS=$((NOW - LAST_CHANGE))
  IDLE_LIMIT=$((MAX_IDLE_MIN * 60))

  if [ "$IDLE_SECONDS" -gt "$IDLE_LIMIT" ]; then
    DIFF=$(get_diff_summary "$WORKTREE")
    SALVAGE_RESULT=$(do_salvage "$WORKTREE" "$SALVAGE")
    echo '{"status":"idle_timeout","task":"'"$TASK_ID"'","idle_seconds":'"$IDLE_SECONDS"',"polls":'"$POLL_COUNT"',"diff":'"$DIFF"',"salvage":"'"$SALVAGE_RESULT"'"}'
    notify "⏰ Worker [$TASK_ID] 闲置超时 (${IDLE_SECONDS}s) | $MODIFIED 文件 | salvage=$SALVAGE_RESULT"
    exit 2
  fi

  # Progress report
  echo '{"status":"polling","task":"'"$TASK_ID"'","poll":'"$POLL_COUNT"',"workers":'"$WORKER_COUNT"',"modified":'"$MODIFIED"'}'
done
