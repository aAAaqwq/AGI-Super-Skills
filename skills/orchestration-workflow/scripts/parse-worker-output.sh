#!/usr/bin/env bash
# ============================================================================
# parse-worker-output.sh — Extract structured status from Codex/Claude TUI
# ============================================================================
# Reads raw tmux/zellij capture and extracts actionable signals.
# Designed for Orchestrator to auto-judge Worker progress.
#
# Usage:
#   ./parse-worker-output.sh <session_name>
#   # or pipe raw output:
#   tmux capture-pane -t worker -p | ./parse-worker-output.sh -
#
# Output: Single JSON object with structured status
# ============================================================================

set -euo pipefail

SESSION="${1:?Usage: parse-worker-output.sh <session_name|->}"

# Get raw output
if [ "$SESSION" = "-" ]; then
  RAW=$(cat)
else
  if command -v tmux &>/dev/null && tmux has-session -t "$SESSION" 2>/dev/null; then
    RAW=$(tmux capture-pane -t "$SESSION" -p -S -100 2>/dev/null)
  elif command -v zellij &>/dev/null; then
    TMPF="/tmp/zellij-parse-$$.txt"
    zellij -s "$SESSION" action dump-screen "$TMPF" 2>/dev/null
    RAW=$(cat "$TMPF" 2>/dev/null)
    rm -f "$TMPF"
  else
    echo '{"error":"No active session found"}'
    exit 1
  fi
fi

# ---- Parse Codex signals ----
PHASE="unknown"
FILES_ADDED=0
FILES_MODIFIED=0
ERRORS=0
WAITING_INPUT=false
WORKING=false
DONE=false
LAST_ACTION=""

# Detect phase
if echo "$RAW" | grep -q "Got it"; then
  PHASE="started"
fi
if echo "$RAW" | grep -q "Working"; then
  PHASE="working"
  WORKING=true
fi
# "Done" must be a standalone Codex status line, not "Worked for" (which is a separator)
if echo "$RAW" | grep -qE "^• Done"; then
  PHASE="done"
  DONE=true
fi
if echo "$RAW" | grep -q "Would you like to run"; then
  PHASE="waiting_permission"
  WAITING_INPUT=true
fi
if echo "$RAW" | grep -q "Press enter to confirm"; then
  WAITING_INPUT=true
fi
if echo "$RAW" | grep -qE "error:|Error:|ENOENT|EPERM|failed"; then
  ERRORS=$((ERRORS + 1))
fi

# Count file operations
FILES_ADDED=$(echo "$RAW" | grep -c "Added\|Created" 2>/dev/null || true)
FILES_ADDED=${FILES_ADDED:-0}; FILES_ADDED=$(( FILES_ADDED + 0 ))
FILES_MODIFIED=$(echo "$RAW" | grep -c "Modified\|Changed\|Updated" 2>/dev/null || true)
FILES_MODIFIED=${FILES_MODIFIED:-0}; FILES_MODIFIED=$(( FILES_MODIFIED + 0 ))

# Extract last meaningful action
LAST_ACTION=$(echo "$RAW" | grep -E "^• |^› " | tail -1 | sed 's/^[•›] //' | head -c 120)

# Extract time worked
TIME_WORKED=$(echo "$RAW" | grep -oE "Worked for [0-9]+s|Working \([0-9]+s" | tail -1 | grep -oE "[0-9]+" || echo "0")

# Extract context usage
CONTEXT_LEFT=$(echo "$RAW" | grep -oE "[0-9]+% context left" | tail -1 | grep -oE "[0-9]+" || echo "100")

# ---- Determine action recommendation ----
# Priority: waiting_input > done > errors > wait
RECOMMENDATION="wait"
if [ "$ERRORS" -gt 0 ] && [ "$DONE" = false ]; then
  RECOMMENDATION="investigate"
fi
if [ "$DONE" = true ]; then
  RECOMMENDATION="check_commit"
fi
if [ "$WAITING_INPUT" = true ]; then
  RECOMMENDATION="send_approval"  # Highest priority — blocks everything
fi

# ---- Output structured JSON ----
# Use jq-style construction to avoid shell/python quoting issues
LAST_ACTION_ESCAPED=$(echo "$LAST_ACTION" | LC_ALL=C head -c 120 | LC_ALL=C sed 's/[^a-zA-Z0-9 _\-\.\/\(\),:;@#]//g' | sed 's/"/\\"/g' | tr -d '\n')

cat <<ENDJSON
{"phase":"$PHASE","working":$( [ "$WORKING" = true ] && echo "true" || echo "false" ),"done":$( [ "$DONE" = true ] && echo "true" || echo "false" ),"waiting_input":$( [ "$WAITING_INPUT" = true ] && echo "true" || echo "false" ),"errors":$ERRORS,"files_added":$FILES_ADDED,"files_modified":$FILES_MODIFIED,"time_worked_seconds":$TIME_WORKED,"context_remaining_pct":$CONTEXT_LEFT,"last_action":"$LAST_ACTION_ESCAPED","recommendation":"$RECOMMENDATION"}
ENDJSON
