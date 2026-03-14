#!/usr/bin/env bash
# orchestrate-patrol.sh — Non-blocking: check worker status once, trigger gate if done
#
# Usage: orchestrate-patrol.sh <task-id>
#
# Called by cron/heartbeat every 60-90s. Reads state from /tmp/orch-tasks/<task-id>.state.
# Returns immediately after one check.
#
# Exit codes:
#   0 = still running (or completed successfully)
#   1 = error
#   10 = task completed + gate passed
#   20 = task completed + gate failed
#   30 = task failed (no changes)
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
SSH_TMUX=""
for p in \
  "${SCRIPTS_DIR}/../../../persistent-ssh-tmux/scripts/ssh_tmux_session.sh" \
  "$HOME/.openclaw/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh" \
  "$HOME/.agents/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh"; do
  [ -f "$p" ] && SSH_TMUX="$p" && break
done
TASK_DIR="/tmp/orch-tasks"

# Helpers: local tmux vs remote ssh_tmux
tmux_capture() {
  if [ "$HOST" = "localhost" ]; then
    tmux capture-pane -t "$1" -p -S -"${2:-30}" 2>/dev/null
  else
    bash "$SSH_TMUX" "$HOST" "$1" capture "${2:-30}" --quiet 2>/dev/null
  fi
}
tmux_send() {
  if [ "$HOST" = "localhost" ]; then
    tmux send-keys -t "$1" "$2" C-m 2>/dev/null
  else
    bash "$SSH_TMUX" "$HOST" "$1" send "$2" --quiet 2>/dev/null
  fi
}
tmux_kill() {
  if [ "$HOST" = "localhost" ]; then
    tmux kill-session -t "$1" 2>/dev/null || true
  else
    bash "$SSH_TMUX" "$HOST" "$1" kill --quiet 2>/dev/null || true
  fi
}
# Cross-platform hash (macOS md5 / Linux md5sum / fallback cksum)
# Handles empty input gracefully (returns "empty")
file_hash() {
  local input
  input=$(cat)
  if [ -z "$input" ]; then echo "empty"; return; fi
  if command -v md5sum &>/dev/null; then echo "$input" | md5sum | cut -d' ' -f1
  elif command -v md5 &>/dev/null; then echo "$input" | md5 -q
  else echo "$input" | cksum | cut -d' ' -f1
  fi
}

MAX_POLLS=${MAX_POLLS:-120}  # Safety backstop (~2h at 60s intervals)

TASK_ID="${1:?Usage: orchestrate-patrol.sh <task-id>}"
STATE_FILE="${TASK_DIR}/${TASK_ID}.state"
LOCK_FILE="${TASK_DIR}/${TASK_ID}.lock"

if [ ! -f "$STATE_FILE" ]; then
  echo "❌ No state file: $STATE_FILE"
  exit 1
fi

# Prevent concurrent patrols (simple flock or mkdir-based lock)
if command -v flock &>/dev/null; then
  exec 200>"$LOCK_FILE"
  flock -n 200 || { echo "⏳ Another patrol is running"; exit 0; }
else
  if ! mkdir "${LOCK_FILE}.d" 2>/dev/null; then
    echo "⏳ Another patrol is running"; exit 0
  fi
  trap "rmdir '${LOCK_FILE}.d' 2>/dev/null" EXIT
fi

# Read state — single python3 call (not 14 separate invocations)
eval "$(python3 -c "
import json
s = json.load(open('$STATE_FILE'))
for k in ['repo','worktree','branch','baseline','host','session']:
    print(f\"{k.upper()}={s[k]!r}\")
print(f\"DEPLOY={s['deploy']}\")
print(f\"CLEANUP={s['cleanup']}\")
print(f\"STATUS={s['status']!r}\")
print(f\"PREV_HASH={s.get('prev_file_hash','')!r}\")
print(f\"IDLE_COUNT={s.get('idle_count',0)}\")
print(f\"PATROL_COUNT={s.get('patrol_count',0)}\")
")"

IDLE_THRESHOLD=${IDLE_THRESHOLD:-3}  # 3 patrols × 60-90s = ~3-4.5min idle
MAX_FILES=${MAX_FILES:-5}

log() { echo "{\"phase\":\"patrol\",\"status\":\"$1\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"task\":\"$TASK_ID\"${2:+,$2}}"; }

# Skip if already completed
if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
  log "skip" "\"reason\":\"already_$STATUS\""
  exit 0
fi

PATROL_COUNT=$((PATROL_COUNT + 1))

# ============================================================================
# Helper: run command locally or remotely
# ============================================================================
rcmd() {
  if [ "$HOST" = "localhost" ]; then
    eval "$1"
  else
    ssh "$HOST" "$1"
  fi
}

# ============================================================================
# Check 1: Worker wrote .task-result.json → immediate Gate
# ============================================================================
RJSON=$(rcmd "cat '$WORKTREE/.task-result.json' 2>/dev/null" || echo "")
if [ -n "$RJSON" ] && echo "$RJSON" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
  # Give worker 5s to finish committing (it may write result.json before git commit)
  sleep 5
  log "completed_structured" "\"patrol\":$PATROL_COUNT,\"result\":$(echo "$RJSON" | tr '\n' ' ')"
  echo "$RJSON" | tr '\n' ' ' > "/tmp/orch-result-${TASK_ID}.json"
  python3 -c "
import json
s = json.load(open('$STATE_FILE'))
s['status'] = 'completed'
s['result'] = json.loads(open('/tmp/orch-result-' + s['task_id'] + '.json').read())
s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
  # Trigger gate
  bash "$SCRIPTS_DIR/orchestrate-gate.sh" "$TASK_ID"
  exit $?
fi

# ============================================================================
# Check 2: Worker committed to git → immediate Gate
# ============================================================================
CURRENT=$(rcmd "cd '$WORKTREE' && git rev-parse --short HEAD 2>/dev/null" || echo "$BASELINE")
if [ "$CURRENT" != "$BASELINE" ]; then
  SHORT=$(rcmd "cd '$WORKTREE' && git log -1 --oneline 2>/dev/null" || echo "$CURRENT")
  log "completed_git" "\"patrol\":$PATROL_COUNT,\"commit\":\"$SHORT\""
  RESULT="{\"status\":\"success\",\"commit\":\"${SHORT}\",\"build_pass\":null,\"notes\":\"detected commit at patrol $PATROL_COUNT\"}"
  echo "$RESULT" > "/tmp/orch-result-${TASK_ID}.json"
  python3 -c "
import json
s = json.load(open('$STATE_FILE'))
s['status'] = 'completed'
s['result'] = json.loads(open('/tmp/orch-result-' + s['task_id'] + '.json').read())
s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
  bash "$SCRIPTS_DIR/orchestrate-gate.sh" "$TASK_ID"
  exit $?
fi

# ============================================================================
# Check 3: Agent process alive?
# ============================================================================
if [ "$HOST" = "localhost" ]; then
  AGENT_ALIVE=$(pgrep -f "codex.*orch-|claude.*orch-${TASK_ID}" 2>/dev/null | head -1 || echo "")
  TMUX_ALIVE=$(tmux has-session -t "$SESSION" 2>/dev/null && echo "1" || echo "0")
else
  AGENT_ALIVE=$(rcmd "pgrep -f 'codex.*orch-|claude.*orch-${TASK_ID}' 2>/dev/null | head -1" || echo "")
  TMUX_ALIVE=$(bash "$SSH_TMUX" "$HOST" "$SESSION" list 2>/dev/null | grep -q "$SESSION" && echo "1" || echo "0")
fi

if [ -z "$AGENT_ALIVE" ] && [ "$TMUX_ALIVE" = "0" ]; then
  # Agent died — try to salvage
  DIRTY=$(rcmd "cd '$WORKTREE' && git status --porcelain 2>/dev/null | wc -l | tr -d ' '" || echo "0")
  if [ "$DIRTY" -gt 0 ]; then
    log "agent_died_salvage" "\"patrol\":$PATROL_COUNT,\"dirty\":$DIRTY"
    rcmd "cd '$WORKTREE' && git add -A && git reset HEAD -- .task-prompt.md .task-result.json .orch-setup-done CLAUDE.md 2>/dev/null; git commit -m 'feat: ${TASK_ID} (salvaged — agent exited)'" 2>/dev/null || true
    SHORT=$(rcmd "cd '$WORKTREE' && git log -1 --oneline 2>/dev/null" || echo "unknown")
    RESULT="{\"status\":\"success\",\"commit\":\"${SHORT}\",\"build_pass\":null,\"notes\":\"salvaged — agent died\"}"
    echo "$RESULT" > "/tmp/orch-result-${TASK_ID}.json"
    python3 -c "
import json
s = json.load(open('$STATE_FILE'))
s['status'] = 'completed'
s['result'] = json.loads(open('/tmp/orch-result-' + s['task_id'] + '.json').read())
s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
    bash "$SCRIPTS_DIR/orchestrate-gate.sh" "$TASK_ID"
    exit $?
  else
    log "agent_died_empty" "\"patrol\":$PATROL_COUNT"
    python3 -c "
import json; s = json.load(open('$STATE_FILE')); s['status'] = 'failed'; s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
    exit 30
  fi
fi

# ============================================================================
# Check 4: Idle detection (file hash delta)
# ============================================================================
# Skip idle detection during setup phase (npm install etc.)
SETUP_DONE=0
if [ "$HOST" = "localhost" ]; then
  [ -f "$WORKTREE/.orch-setup-done" ] && SETUP_DONE=1
  CUR_HASH=$(cd "$WORKTREE" 2>/dev/null && { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort | file_hash || echo "empty")
else
  SETUP_DONE=$(rcmd "[ -f '$WORKTREE/.orch-setup-done' ] && echo 1 || echo 0" 2>/dev/null || echo "0")
  CUR_HASH=$(rcmd "cd '$WORKTREE' && { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort | md5sum 2>/dev/null | cut -d' ' -f1 || echo empty" || echo "empty")
fi

if [ "$SETUP_DONE" = "0" ] && [ "$PATROL_COUNT" -lt 5 ]; then
  # Still in setup (npm install), don't count as idle
  # Max 5 patrols grace period (~5-7.5 min), then treat as normal
  IDLE_COUNT=0
  log "patrol" "setup_pending" "\"patrol\":$PATROL_COUNT"
elif [ "$SETUP_DONE" = "0" ] && [ "$PATROL_COUNT" -ge 5 ]; then
  # Setup too long — either stuck or non-Node project, start idle tracking
  log "patrol" "setup_timeout" "\"patrol\":$PATROL_COUNT"
  IDLE_COUNT=$((IDLE_COUNT + 1))
elif [ "$CUR_HASH" = "$PREV_HASH" ]; then
  IDLE_COUNT=$((IDLE_COUNT + 1))
else
  IDLE_COUNT=0
fi

# ============================================================================
# Check 5: Worker waiting for input? Capture tmux + detect
# ============================================================================
# Capture last 30 lines from tmux session
TMUX_OUTPUT=$(tmux_capture "$SESSION" 30 || echo "")
NEEDS_INPUT=0
INPUT_TYPE="none"
INPUT_CONTEXT=""

if [ -n "$TMUX_OUTPUT" ]; then
  # Detect common "waiting for input" patterns
  LAST_LINES=$(echo "$TMUX_OUTPUT" | tail -10)
  
  # Pattern 1: Codex/Claude permission prompt (y/n/p)
  if echo "$LAST_LINES" | grep -qiE '(approve|allow|permit|y/n|yes/no|\[y\]|\[n\])'; then
    NEEDS_INPUT=1; INPUT_TYPE="permission"
    INPUT_CONTEXT="$LAST_LINES"
  fi
  
  # Pattern 2: Selection prompt — only match interactive-looking prompts, not code output
  # Must have a question mark or ":" at end of line to indicate waiting for input
  if echo "$LAST_LINES" | tail -3 | grep -qiE '(choose.*[?:]|select.*[?:]|which.*[?:]|pick.*[?:]|enter.*number)'; then
    NEEDS_INPUT=1; INPUT_TYPE="selection"
    INPUT_CONTEXT="$LAST_LINES"
  fi
  
  # Pattern 3: Error / stuck (needs diagnosis) — only match end-of-output errors, not mid-build noise
  if echo "$LAST_LINES" | tail -3 | grep -qiE '(^error:|ERR!|FATAL|ENOENT|SIGTERM|command not found|permission denied)'; then
    NEEDS_INPUT=1; INPUT_TYPE="error"
    INPUT_CONTEXT="$LAST_LINES"
  fi
  
  # Pattern 4: Simple approval prompt (Codex "p" to proceed)
  if echo "$LAST_LINES" | grep -qiE '(proceed|continue|press.*to)'; then
    NEEDS_INPUT=1; INPUT_TYPE="proceed"
    INPUT_CONTEXT="$LAST_LINES"
  fi
fi

if [ "$NEEDS_INPUT" = "1" ]; then
  # Simple cases: auto-handle
  if [ "$INPUT_TYPE" = "permission" ] || [ "$INPUT_TYPE" = "proceed" ]; then
    log "auto_respond" "\"patrol\":$PATROL_COUNT,\"type\":\"$INPUT_TYPE\""
    # Try common approval keys
    tmux_send "$SESSION" "y" || true
    IDLE_COUNT=0
  else
    # Complex cases: write to state file for LLM (Minerva) to handle
    log "needs_input" "\"patrol\":$PATROL_COUNT,\"type\":\"$INPUT_TYPE\""
    # Write input context to temp file to avoid quote escaping issues
    echo "$INPUT_CONTEXT" | head -10 > "/tmp/orch-input-${TASK_ID}.txt"
    echo "$TMUX_OUTPUT" | tail -20 > "/tmp/orch-snapshot-${TASK_ID}.txt"
    python3 << PYEOF
import json
s = json.load(open('$STATE_FILE'))
s['needs_input'] = True
s['input_type'] = '$INPUT_TYPE'
s['input_context'] = open('/tmp/orch-input-${TASK_ID}.txt').read().strip()
s['tmux_snapshot'] = open('/tmp/orch-snapshot-${TASK_ID}.txt').read().strip()
json.dump(s, open('$STATE_FILE','w'), indent=2)
PYEOF
    # Don't increment idle — worker is blocked, not idle
    IDLE_COUNT=0
  fi
fi

# Idle threshold reached → check if substantive changes exist
if [ "$IDLE_COUNT" -ge "$IDLE_THRESHOLD" ]; then
  REAL_FILES=$(rcmd "cd '$WORKTREE' && { git diff --name-only HEAD; git ls-files --others --exclude-standard; } 2>/dev/null | grep -vcE '^(package\.json|package-lock\.json|node_modules|\.task-prompt\.md|\.task-result\.json|CLAUDE\.md)$'" || echo "0")

  if [ "$REAL_FILES" -gt 0 ]; then
    log "idle_commit" "\"patrol\":$PATROL_COUNT,\"idle\":$IDLE_COUNT,\"real_files\":$REAL_FILES"
    # Kill agent
    if [ "$HOST" = "localhost" ]; then
      AGENT_PID=$(pgrep -f "codex.*orch-|claude.*orch-${TASK_ID}" 2>/dev/null | head -1 || echo "")
      [ -n "$AGENT_PID" ] && kill "$AGENT_PID" 2>/dev/null || true
    else
      rcmd "pkill -f 'codex.*orch-|claude.*orch-${TASK_ID}'" 2>/dev/null || true
    fi
    sleep 2
    rcmd "cd '$WORKTREE' && git add -A && git reset HEAD -- .task-prompt.md .task-result.json .orch-setup-done CLAUDE.md 2>/dev/null; git commit -m 'feat: ${TASK_ID} (auto-commit — worker idle)'" 2>/dev/null || true
    SHORT=$(rcmd "cd '$WORKTREE' && git log -1 --oneline 2>/dev/null" || echo "unknown")
    RESULT="{\"status\":\"success\",\"commit\":\"${SHORT}\",\"build_pass\":null,\"notes\":\"idle-committed at patrol $PATROL_COUNT\"}"
    echo "$RESULT" > "/tmp/orch-result-${TASK_ID}.json"
    python3 -c "
import json
s = json.load(open('$STATE_FILE'))
s['status'] = 'completed'
s['result'] = json.loads(open('/tmp/orch-result-' + s['task_id'] + '.json').read())
s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
    bash "$SCRIPTS_DIR/orchestrate-gate.sh" "$TASK_ID"
    exit $?
  else
    log "idle_no_real_files" "\"patrol\":$PATROL_COUNT,\"idle\":$IDLE_COUNT"
    IDLE_COUNT=0  # Reset — might still be installing
  fi
fi

# ============================================================================
# Safety backstop: MAX_POLLS
# ============================================================================
if [ "$PATROL_COUNT" -ge "$MAX_POLLS" ]; then
  DIRTY=$(rcmd "cd '$WORKTREE' && git status --porcelain 2>/dev/null | wc -l | tr -d ' '" || echo "0")
  if [ "$DIRTY" -gt 0 ]; then
    log "backstop_commit" "\"patrol\":$PATROL_COUNT,\"dirty\":$DIRTY"
    rcmd "cd '$WORKTREE' && git add -A && git reset HEAD -- .task-prompt.md .task-result.json .orch-setup-done CLAUDE.md 2>/dev/null; git commit -m 'feat: ${TASK_ID} (backstop at patrol $PATROL_COUNT)'" 2>/dev/null || true
    RESULT="{\"status\":\"success\",\"commit\":\"backstop\",\"build_pass\":null,\"notes\":\"backstop at patrol $PATROL_COUNT\"}"
    echo "$RESULT" > "/tmp/orch-result-${TASK_ID}.json"
    python3 -c "
import json; s = json.load(open('$STATE_FILE')); s['status'] = 'completed'; s['patrol_count'] = $PATROL_COUNT
s['result'] = json.loads(open('/tmp/orch-result-${TASK_ID}.json').read())
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
    bash "$SCRIPTS_DIR/orchestrate-gate.sh" "$TASK_ID"
    exit $?
  else
    log "backstop_empty" "\"patrol\":$PATROL_COUNT"
    python3 -c "
import json; s = json.load(open('$STATE_FILE')); s['status'] = 'failed'; s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"
    exit 30
  fi
fi

# ============================================================================
# Update state and return
# ============================================================================
python3 -c "
import json
s = json.load(open('$STATE_FILE'))
s['prev_file_hash'] = '$CUR_HASH'
s['idle_count'] = $IDLE_COUNT
s['patrol_count'] = $PATROL_COUNT
json.dump(s, open('$STATE_FILE','w'), indent=2)
"

log "waiting" "\"patrol\":$PATROL_COUNT,\"idle\":$IDLE_COUNT,\"files_hash\":\"${CUR_HASH:0:8}\""
exit 0
