#!/usr/bin/env bash
# orchestrate.sh — One-command orchestration: worktree → worker → gate → merge → deploy → cleanup
#
# Usage: orchestrate.sh <repo> <task-id> <prompt-file> [agent] [--yolo] [--deploy] [--no-cleanup]
#
# Environment:
#   WORKER_HOST=user@host         — Run Worker on remote machine via SSH
#   VERIFY_MODE=browser|api|test|none — Verification strategy (default: auto-detect)
#     browser: Vercel deploy + actionbook browser verification (web projects)
#     api:     Run test suite + curl health check (API/backend projects)
#     test:    Run test suite only, no deploy (libraries, CLI tools)
#     none:    Skip verification entirely
#   VERIFY_BROWSER=1              — Enable actionbook browser verification in deploy
#   VERIFY_MANIFEST=path.json     — Per-page verification manifest
#   VERIFY_SHOTS_DIR=/tmp/shots   — Screenshot output dir
#   API_HEALTH_URL=http://...     — Health check URL for api mode
#   MAX_FILES=5                   — Max changed files before gate rejects
#   IDLE_THRESHOLD=8              — Polls with no file changes → "worker idle" (default 8 = ~2min)
#   MAX_POLLS=120                 — Safety backstop only (default 120 = ~30min), NOT a timeout
#
# Patrol mode (v4.0): Event-driven, no hard timeout.
#   Worker commits → immediate Gate. Worker idle → auto-commit. Worker stuck → intervene.
#   Agent died → salvage. MAX_POLLS is a safety backstop, not an expected exit path.
#
# Local mode:  git worktree → tmux → patrol → gate → merge → deploy → cleanup
# Remote mode: scp prompt → ssh git branch → ssh tmux codex → ssh poll → ssh merge → cleanup
#
# Examples:
#   orchestrate.sh /tmp/flyme-new fix-nav /tmp/tasks/fix-nav.md codex --yolo --deploy
#   WORKER_HOST=root@100.125.204.29 orchestrate.sh /tmp/project task-1 /tmp/tasks/task.md codex --yolo
#   VERIFY_BROWSER=1 VERIFY_MANIFEST=/tmp/verify.json orchestrate.sh /tmp/flyme-new modal /tmp/tasks/modal.md codex --yolo --deploy

set -euo pipefail

# Exit codes (standardized)
EXIT_OK=0
EXIT_SETUP=10
EXIT_WORKER=20
EXIT_GATE=30
EXIT_MERGE=40
EXIT_DEPLOY=50
EXIT_PREFLIGHT=60

# Resolve symlinks so SCRIPTS_DIR always points to real script directory
SCRIPTS_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
WORKER_HOST="${WORKER_HOST:-}"
MAX_CONCURRENT="${MAX_CONCURRENT:-2}"

# --- Utility: retry with backoff ---
retry_with_backoff() {
  local max_retries="${1:-3}" cmd="${*:2}"
  local attempt=0 delay=2
  while [ $attempt -lt $max_retries ]; do
    if eval "$cmd"; then return 0; fi
    attempt=$((attempt + 1))
    [ $attempt -lt $max_retries ] && { sleep $delay; delay=$((delay * 2)); }
  done
  return 1
}

# --- Preflight check ---
preflight() {
  local fail=0
  # Required binaries
  for bin in git tmux; do
    if ! command -v "$bin" >/dev/null 2>&1; then
      echo "PREFLIGHT FAIL: '$bin' not found in PATH" >&2; fail=1
    fi
  done
  # Agent binary
  local agent_bin="${1:-codex}"
  if ! command -v "$agent_bin" >/dev/null 2>&1; then
    echo "PREFLIGHT WARN: agent '$agent_bin' not in PATH (may be invoked differently)" >&2
  fi
  # Helper scripts exist
  for script in worker-session.sh parse-worker-output.sh; do
    if [ ! -f "$SCRIPTS_DIR/$script" ]; then
      echo "PREFLIGHT FAIL: $SCRIPTS_DIR/$script not found" >&2; fail=1
    fi
  done
  # Concurrent task limit
  local running
  running=$(ls /tmp/orch-*.lock 2>/dev/null | wc -l | tr -d ' ')
  if [ "$running" -ge "$MAX_CONCURRENT" ]; then
    echo "PREFLIGHT FAIL: $running tasks already running (max $MAX_CONCURRENT). Wait or set MAX_CONCURRENT." >&2; fail=1
  fi
  return $fail
}

# --- Args ---
REPO="${1:?Usage: orchestrate.sh <repo> <task-id> <prompt-file> [agent] [--yolo] [--deploy] [--no-cleanup]}"
TASK_ID="${2:?Missing task-id}"
PROMPT_FILE="${3:?Missing prompt-file (path to .md file with task instructions)}"
AGENT="${4:-codex}"
shift 3; shift || true

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
  exit $EXIT_SETUP
fi

YOLO=0; DEPLOY=0; CLEANUP=1; POLL_INTERVAL=15; MAX_POLLS=40
WORKER_SKILLS=""  # Space-separated skill tags: core frontend tdd debug verify all
for arg in "$@"; do
  case "$arg" in
    --yolo) YOLO=1 ;;
    --deploy) DEPLOY=1 ;;
    --no-cleanup) CLEANUP=0 ;;
    --skills=*) WORKER_SKILLS="${arg#--skills=}" ;;
    codex|claude|gemini) AGENT="$arg" ;;
  esac
done
# Default: always inject core skills
[ -z "$WORKER_SKILLS" ] && WORKER_SKILLS="core"

BRANCH="feat/${TASK_ID}"
WORKTREE="/tmp/orch-${TASK_ID}"
LOCKFILE="/tmp/orch-${TASK_ID}.lock"

is_remote() { [ -n "$WORKER_HOST" ]; }
log() {
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%s)
  echo "{\"phase\":\"$1\",\"status\":\"$2\",\"ts\":\"$ts\"${3:+,$3}}"
}
rcmd() { ssh "$WORKER_HOST" "$@"; }

# --- Preflight (Phase -1) ---
if ! preflight "$AGENT"; then
  log "preflight" "fail"
  exit $EXIT_PREFLIGHT
fi
log "preflight" "pass"

# Acquire lock
echo "$$" > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

# ============================================================================
# Phase 0: Cleanup stale sessions (Fix #24)
# ============================================================================
if ! is_remote; then
  # Kill stale tmux session with same name
  if tmux has-session -t "$TASK_ID" 2>/dev/null; then
    tmux kill-session -t "$TASK_ID" 2>/dev/null || true
    log "cleanup" "killed_stale_tmux" "\"session\":\"$TASK_ID\""
  fi
  # Kill stale agent processes in old worktree
  STALE_PIDS=$(pgrep -f "codex.*orch-${TASK_ID}|claude.*orch-${TASK_ID}" 2>/dev/null || true)
  if [ -n "$STALE_PIDS" ]; then
    echo "$STALE_PIDS" | xargs kill 2>/dev/null || true
    sleep 2
    log "cleanup" "killed_stale_agent" "\"pids\":\"$STALE_PIDS\""
  fi
fi

# ============================================================================
# Phase 1: Setup
# ============================================================================
if is_remote; then
  log "setup" "starting" "\"repo\":\"$REPO\",\"branch\":\"$BRANCH\",\"host\":\"$WORKER_HOST\",\"worktree\":\"$WORKTREE\""

  rcmd "
    if [ -d '$REPO/.git' ]; then
      cd '$REPO'
      # Auto-init empty repos
      git rev-parse HEAD >/dev/null 2>&1 || { git add -A 2>/dev/null || true; git commit --allow-empty -m 'chore: initial commit (auto-created by orchestrator)' 2>/dev/null; }
      git worktree remove '$WORKTREE' --force 2>/dev/null || true
      git branch -D '$BRANCH' 2>/dev/null || true
      git worktree add '$WORKTREE' -b '$BRANCH'
    else
      mkdir -p '$WORKTREE'
      cd '$WORKTREE' && git init && git checkout -b '$BRANCH'
    fi
    cd '$WORKTREE'
    GIT_DIR=$(git rev-parse --git-dir 2>/dev/null || echo '')
    if [ -n "$GIT_DIR" ]; then
      mkdir -p "$GIT_DIR/info"
      touch "$GIT_DIR/info/exclude"
      grep -q '.task-prompt.md' "$GIT_DIR/info/exclude" 2>/dev/null || echo '.task-prompt.md' >> "$GIT_DIR/info/exclude"
      grep -q '.task-result.json' "$GIT_DIR/info/exclude" 2>/dev/null || echo '.task-result.json' >> "$GIT_DIR/info/exclude"
      grep -q 'CLAUDE.md' "$GIT_DIR/info/exclude" 2>/dev/null || echo 'CLAUDE.md' >> "$GIT_DIR/info/exclude"
    fi
  "

  scp "$PROMPT_FILE" "${WORKER_HOST}:${WORKTREE}/.task-prompt.md"
  log "setup" "prompt_uploaded"

  if rcmd "[ -f '$WORKTREE/package.json' ]" 2>/dev/null; then
    log "setup" "npm_install"
    rcmd "cd '$WORKTREE' && npm install --silent 2>/dev/null" || true
  fi

  BASELINE=$(rcmd "cd '$WORKTREE' && git log -1 --format=%H 2>/dev/null || echo 'none'")

else
  log "setup" "starting" "\"repo\":\"$REPO\",\"branch\":\"$BRANCH\",\"worktree\":\"$WORKTREE\""

  cd "$REPO"

  # Auto-init empty repos (no HEAD → worktree add fails)
  if ! git rev-parse HEAD >/dev/null 2>&1; then
    log "setup" "auto_init" "\"reason\":\"empty repo, creating initial commit\""
    git add -A 2>/dev/null || true
    git commit --allow-empty -m "chore: initial commit (auto-created by orchestrator)" >/dev/null 2>&1
  fi

  git worktree remove "$WORKTREE" --force 2>/dev/null || true
  git branch -D "$BRANCH" 2>/dev/null || true
  git worktree add "$WORKTREE" -b "$BRANCH"

  if [ -f "$WORKTREE/package.json" ]; then
    log "setup" "npm_install"
    retry_with_backoff 3 "cd '$WORKTREE' && npm install --silent 2>/dev/null" || {
      log "setup" "npm_install_failed"
      exit $EXIT_SETUP
    }
  fi

  cd "$WORKTREE"
  GIT_DIR=$(git rev-parse --git-dir 2>/dev/null || echo "")
  if [ -n "$GIT_DIR" ]; then
    mkdir -p "$GIT_DIR/info"
    touch "$GIT_DIR/info/exclude"
    grep -q ".task-prompt.md" "$GIT_DIR/info/exclude" 2>/dev/null || echo ".task-prompt.md" >> "$GIT_DIR/info/exclude"
    grep -q ".task-result.json" "$GIT_DIR/info/exclude" 2>/dev/null || echo ".task-result.json" >> "$GIT_DIR/info/exclude"
    grep -q "CLAUDE.md" "$GIT_DIR/info/exclude" 2>/dev/null || echo "CLAUDE.md" >> "$GIT_DIR/info/exclude"
  fi

  cp "$PROMPT_FILE" "$WORKTREE/.task-prompt.md"

  BASELINE=$(git log -1 --format=%H)
fi

log "setup" "ready" "\"baseline\":\"${BASELINE:0:7}\""

# ---- Inject Worker Skills (CLAUDE.md) ----
if [ -x "$SCRIPTS_DIR/inject-worker-skills.sh" ] && [ -n "$WORKER_SKILLS" ]; then
  # shellcheck disable=SC2086
  if is_remote; then
    # For remote: inject locally then scp
    TMPCLAUD=$(mktemp)
    "$SCRIPTS_DIR/inject-worker-skills.sh" "$(dirname "$TMPCLAUD")" $WORKER_SKILLS >/dev/null 2>&1
    scp "$(dirname "$TMPCLAUD")/CLAUDE.md" "${WORKER_HOST}:${WORKTREE}/CLAUDE.md" 2>/dev/null
    rcmd "cd '$WORKTREE' && GIT_DIR=\$(git rev-parse --git-dir 2>/dev/null || echo '') && [ -n \"$GIT_DIR\" ] && mkdir -p \"$GIT_DIR/info\" && touch \"$GIT_DIR/info/exclude\"" 2>/dev/null
    rcmd "cd '$WORKTREE' && GIT_DIR=\$(git rev-parse --git-dir 2>/dev/null || echo '') && [ -n \"$GIT_DIR\" ] && (grep -q 'CLAUDE.md' \"$GIT_DIR/info/exclude\" 2>/dev/null || echo 'CLAUDE.md' >> \"$GIT_DIR/info/exclude\")" 2>/dev/null
    rm -f "$TMPCLAUD"
  else
    INJECT_OUT=$("$SCRIPTS_DIR/inject-worker-skills.sh" "$WORKTREE" $WORKER_SKILLS 2>/dev/null || echo '{"injected":0}')
    # Sanitize: extract just the JSON portion, collapse whitespace
    INJECT_CLEAN=$(echo "$INJECT_OUT" | head -1 | tr -d '\n' | sed 's/[^{]*\({[^}]*}\).*/\1/' | sed 's/"/\\"/g')
    log "setup" "skills_injected" "\"detail\":\"$INJECT_CLEAN\""
  fi
fi

# ============================================================================
# Phase 2: Start Worker
# ============================================================================
export WORKER_YOLO="$YOLO"
export WORKER_HOST
"$SCRIPTS_DIR/worker-session.sh" start "$TASK_ID" "$WORKTREE" "$AGENT"
log "worker" "started" "\"agent\":\"$AGENT\",\"yolo\":$YOLO"

# ============================================================================
# Phase 3: Poll for completion
# ============================================================================
log "poll" "starting" "\"interval\":$POLL_INTERVAL,\"max_polls\":$MAX_POLLS"

check_result_json() {
  if is_remote; then
    rcmd "cat '$WORKTREE/.task-result.json' 2>/dev/null" || echo ""
  else
    cat "$WORKTREE/.task-result.json" 2>/dev/null || echo ""
  fi
}

check_commit() {
  if is_remote; then
    rcmd "cd '$WORKTREE' && git log -1 --format=%H 2>/dev/null || echo 'none'"
  else
    (cd "$WORKTREE" && git log -1 --format=%H 2>/dev/null || echo "none")
  fi
}

check_commit_oneline() {
  if is_remote; then
    rcmd "cd '$WORKTREE' && git log -1 --oneline 2>/dev/null"
  else
    (cd "$WORKTREE" && git log -1 --oneline 2>/dev/null)
  fi
}

# ============================================================================
# Phase 3: Event-Driven Patrol (v4.0)
# ============================================================================
# Instead of a hard timeout, patrol the Worker continuously:
#   1. Worker committed       → immediate proceed to Gate
#   2. Worker wrote result.json → immediate proceed
#   3. Worker idle (no new file changes for IDLE_THRESHOLD polls) → auto-commit
#   4. Worker stuck (asking questions) → auto-approve
#   5. Agent process died     → salvage what's there
#   6. Hard safety limit at MAX_POLLS (default 120 = 30 min) as backstop only
#
# Key env vars:
#   IDLE_THRESHOLD=8          — Polls with zero file change delta → "idle" (default 8 = 2 min)
#   MAX_POLLS=120             — Absolute safety backstop (default 120 = 30 min at 15s interval)
IDLE_THRESHOLD=${IDLE_THRESHOLD:-8}
MAX_POLLS=${MAX_POLLS:-120}

POLL=0
RESULT=""
PREV_FILE_HASH=""
IDLE_COUNT=0
log "patrol" "starting" "\"interval\":$POLL_INTERVAL,\"idle_threshold\":$IDLE_THRESHOLD,\"max_polls\":$MAX_POLLS"

while [ $POLL -lt $MAX_POLLS ]; do
  POLL=$((POLL + 1))
  sleep "$POLL_INTERVAL"

  # ---- Event 1: Worker wrote .task-result.json → immediate proceed ----
  RJSON=$(check_result_json)
  if [ -n "$RJSON" ]; then
    RESULT="$RJSON"
    log "patrol" "completed_structured" "\"polls\":$POLL,\"result\":$RESULT"
    break
  fi

  # ---- Event 2: Worker committed to git → immediate proceed ----
  CURRENT=$(check_commit)
  if [ "$CURRENT" != "$BASELINE" ]; then
    sleep 10
    RJSON=$(check_result_json)
    if [ -n "$RJSON" ]; then
      RESULT="$RJSON"
      log "patrol" "completed_structured" "\"polls\":$POLL,\"result\":$RESULT"
    else
      SHORT=$(check_commit_oneline)
      RESULT="{\"status\":\"success\",\"commit\":\"${SHORT}\",\"build_pass\":null,\"notes\":\"no .task-result.json\"}"
      log "patrol" "completed_git" "\"polls\":$POLL,\"commit\":\"$SHORT\""
    fi
    break
  fi

  # ---- Event 3: Worker stuck / asking questions → auto-approve ----
  if ! is_remote && [ -x "$SCRIPTS_DIR/parse-worker-output.sh" ]; then
    PARSER_OUT=$("$SCRIPTS_DIR/parse-worker-output.sh" "$TASK_ID" 2>/dev/null || echo "{}")
    REC=$(echo "$PARSER_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('recommendation','wait'))" 2>/dev/null || echo "wait")
    if [ "$REC" = "send_approval" ]; then
      log "patrol" "auto_approve" "\"poll\":$POLL"
      tmux send-keys -t "$TASK_ID" "p" 2>/dev/null || true
      IDLE_COUNT=0  # Reset idle after intervention
    fi
  fi

  # ---- Event 4: Agent process died → salvage ----
  if ! is_remote; then
    AGENT_ALIVE=$(pgrep -f "codex.*orch-${TASK_ID}|claude.*orch-${TASK_ID}" 2>/dev/null | head -1 || echo "")
    TMUX_ALIVE=$(tmux has-session -t "$TASK_ID" 2>/dev/null && echo "1" || echo "0")
    if [ -z "$AGENT_ALIVE" ] && [ "$TMUX_ALIVE" = "0" ]; then
      log "patrol" "agent_died" "\"poll\":$POLL"
      # Check if there's anything to salvage
      DIRTY=$(cd "$WORKTREE" 2>/dev/null && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
      if [ "$DIRTY" -gt 0 ]; then
        log "patrol" "salvage_dead_agent" "\"dirty_files\":$DIRTY"
        (cd "$WORKTREE" && git add -A && git reset HEAD -- .task-prompt.md .task-result.json CLAUDE.md 2>/dev/null; git commit -m "feat: ${TASK_ID} (salvaged — agent exited)") 2>/dev/null || true
        SALVAGE_BUILD="null"
        if (cd "$WORKTREE" && npm run build 2>/dev/null); then SALVAGE_BUILD="true"; else SALVAGE_BUILD="false"; fi
        SALVAGE_SHORT=$(cd "$WORKTREE" && git log -1 --oneline 2>/dev/null)
        RESULT="{\"status\":\"success\",\"commit\":\"${SALVAGE_SHORT}\",\"build_pass\":${SALVAGE_BUILD},\"notes\":\"salvaged — agent process exited\"}"
        echo "$RESULT" > "$WORKTREE/.task-result.json"
        log "patrol" "salvaged" "\"commit\":\"$SALVAGE_SHORT\",\"build\":\"$SALVAGE_BUILD\""
      else
        log "patrol" "agent_died_no_changes" "\"poll\":$POLL"
        RESULT="{\"status\":\"failed\",\"commit\":null,\"build_pass\":null,\"notes\":\"agent died with no changes\"}"
      fi
      break
    fi
  fi

  # ---- Idle detection: track file change delta ----
  if ! is_remote; then
    CUR_FILE_HASH=$(cd "$WORKTREE" 2>/dev/null && { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort | md5 2>/dev/null || echo "empty")
    if [ "$CUR_FILE_HASH" = "$PREV_FILE_HASH" ]; then
      IDLE_COUNT=$((IDLE_COUNT + 1))
    else
      IDLE_COUNT=0
      PREV_FILE_HASH="$CUR_FILE_HASH"
    fi

    # ---- Event 5: Worker idle (no file changes for IDLE_THRESHOLD polls) → auto-commit ----
    if [ $IDLE_COUNT -ge $IDLE_THRESHOLD ]; then
      DIRTY_FILES=$(cd "$WORKTREE" 2>/dev/null && git diff --name-only HEAD 2>/dev/null | wc -l | tr -d ' ')
      UNTRACKED=$(cd "$WORKTREE" 2>/dev/null && git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')
      TOTAL_CHANGES=$((DIRTY_FILES + UNTRACKED))

      # Skip if only package*.json changed (npm install still running)
      SUBSTANTIVE=0
      if [ "$TOTAL_CHANGES" -gt 0 ]; then
        REAL_FILES=$( (cd "$WORKTREE" 2>/dev/null && { git diff --name-only HEAD; git ls-files --others --exclude-standard; } 2>/dev/null) | grep -vcE '^(package\.json|package-lock\.json|node_modules|\.task-prompt\.md|\.task-result\.json|CLAUDE\.md)' || echo "0")
        [ "$REAL_FILES" -gt 0 ] && SUBSTANTIVE=1
        if [ "$SUBSTANTIVE" -eq 0 ]; then
          log "patrol" "skip_idle_commit" "\"poll\":$POLL,\"reason\":\"only_package_json\",\"idle\":$IDLE_COUNT"
          IDLE_COUNT=0  # Reset — still installing
          log "patrol" "waiting" "\"poll\":$POLL"
          continue
        fi
      fi

      if [ "$TOTAL_CHANGES" -gt 0 ] && [ "$SUBSTANTIVE" -eq 1 ]; then
        log "patrol" "idle_commit" "\"poll\":$POLL,\"idle_polls\":$IDLE_COUNT,\"changes\":$TOTAL_CHANGES"
        # Kill agent
        AGENT_PID=$(pgrep -f "codex.*orch-${TASK_ID}|claude.*orch-${TASK_ID}" 2>/dev/null | head -1 || echo "")
        [ -n "$AGENT_PID" ] && kill "$AGENT_PID" 2>/dev/null || true
        sleep 2
        # Auto-commit (exclude scaffold files)
        (cd "$WORKTREE" && git add -A && git reset HEAD -- .task-prompt.md .task-result.json CLAUDE.md 2>/dev/null; git commit -m "feat: ${TASK_ID} (auto-commit — worker idle)") 2>/dev/null || true
        # Build check
        AUTO_BUILD="null"
        if (cd "$WORKTREE" && npm run build 2>/dev/null); then
          AUTO_BUILD="true"
        else
          AUTO_BUILD="false"
        fi
        AUTO_SHORT=$(cd "$WORKTREE" && git log -1 --oneline 2>/dev/null)
        echo "{\"status\":\"success\",\"commit\":\"${AUTO_SHORT}\",\"build_pass\":${AUTO_BUILD},\"notes\":\"auto-committed — worker idle for ${IDLE_COUNT} polls\"}" > "$WORKTREE/.task-result.json"
        RESULT=$(cat "$WORKTREE/.task-result.json")
        log "patrol" "idle_committed" "\"polls\":$POLL,\"build\":\"$AUTO_BUILD\""
        break
      fi

      # No changes + idle — worker might be stuck doing nothing
      if [ "$TOTAL_CHANGES" -eq 0 ]; then
        log "patrol" "idle_no_changes" "\"poll\":$POLL,\"idle\":$IDLE_COUNT"
        # Don't break — keep waiting, agent might still be reading/thinking
        IDLE_COUNT=0  # Reset to avoid immediate re-trigger
      fi
    fi
  fi

  # Log every 5th poll to reduce noise
  if [ $((POLL % 5)) -eq 0 ] || [ $POLL -le 3 ]; then
    log "patrol" "waiting" "\"poll\":$POLL,\"idle\":$IDLE_COUNT"
  fi
done

# ---- Safety backstop: MAX_POLLS reached ----
if [ $POLL -ge $MAX_POLLS ] && [ -z "$RESULT" ]; then
  log "patrol" "backstop" "\"polls\":$POLL"

  if ! is_remote; then
    DIRTY=$(cd "$WORKTREE" 2>/dev/null && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DIRTY" -gt 0 ]; then
      log "patrol" "backstop_salvage" "\"dirty_files\":$DIRTY"
      AGENT_PID=$(pgrep -f "codex.*orch-${TASK_ID}|claude.*orch-${TASK_ID}" 2>/dev/null | head -1 || echo "")
      [ -n "$AGENT_PID" ] && kill "$AGENT_PID" 2>/dev/null || true
      sleep 2
      (cd "$WORKTREE" && git add -A && git reset HEAD -- .task-prompt.md .task-result.json CLAUDE.md 2>/dev/null; git commit -m "feat: ${TASK_ID} (backstop commit)") 2>/dev/null || true
      SALVAGE_BUILD="null"
      if (cd "$WORKTREE" && npm run build 2>/dev/null); then SALVAGE_BUILD="true"; else SALVAGE_BUILD="false"; fi
      SALVAGE_SHORT=$(cd "$WORKTREE" && git log -1 --oneline 2>/dev/null)
      RESULT="{\"status\":\"success\",\"commit\":\"${SALVAGE_SHORT}\",\"build_pass\":${SALVAGE_BUILD},\"notes\":\"backstop at poll ${POLL}\"}"
      echo "$RESULT" > "$WORKTREE/.task-result.json"
      log "patrol" "backstop_committed" "\"commit\":\"$SALVAGE_SHORT\",\"build\":\"$SALVAGE_BUILD\""
    else
      "$SCRIPTS_DIR/worker-session.sh" stop "$TASK_ID" 2>/dev/null
      if [ "$CLEANUP" = "1" ]; then
        if is_remote; then
          rcmd "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null" || true
        else
          cd "$REPO"
          git worktree remove "$WORKTREE" --force 2>/dev/null || true
          git branch -D "$BRANCH" 2>/dev/null || true
        fi
        log "cleanup" "done"
      fi
      exit $EXIT_WORKER
    fi
  else
    "$SCRIPTS_DIR/worker-session.sh" stop "$TASK_ID" 2>/dev/null
    if [ "$CLEANUP" = "1" ]; then
      rcmd "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null" || true
      log "cleanup" "done"
    fi
    exit $EXIT_WORKER
  fi
fi

# ============================================================================
# Phase 4: Gate check
# ============================================================================
# Sanitise RESULT: collapse literal newlines inside strings so python3 json.loads succeeds
RESULT_CLEAN=$(printf '%s' "$RESULT" | tr '\n' ' ' | sed 's/  */ /g')
STATUS=$(echo "$RESULT_CLEAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
BUILD=$(echo "$RESULT_CLEAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('build_pass', 'null'))" 2>/dev/null || echo "null")
COMMIT=$(echo "$RESULT_CLEAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commit','null'))" 2>/dev/null || echo "null")

# Gate: status=success AND commit exists AND build verified
GATE_PASS=1
GATE_REASON=""

if [ "$STATUS" != "success" ] && [ "$STATUS" != "completed" ] && [ "$STATUS" != "done" ]; then
  GATE_PASS=0; GATE_REASON="status_not_success"
elif [ "$COMMIT" = "null" ] || [ "$COMMIT" = "None" ] || [ -z "$COMMIT" ]; then
  GATE_PASS=0; GATE_REASON="no_commit"
elif [ "$BUILD" = "False" ] || [ "$BUILD" = "false" ]; then
  GATE_PASS=0; GATE_REASON="build_failed"
elif [ "$BUILD" = "null" ] || [ "$BUILD" = "None" ]; then
  # Unknown build status — try running build ourselves
  HAS_BUILD=0
  if is_remote; then
    rcmd "[ -f '$WORKTREE/package.json' ]" 2>/dev/null && HAS_BUILD=1
  else
    [ -f "$REPO/package.json" ] && HAS_BUILD=1
  fi
  if [ "$HAS_BUILD" = "1" ]; then
    log "gate" "build_check" "\"reason\":\"build_pass_unknown_running_build\""
    BUILD_OK=0
    if is_remote; then
      rcmd "cd '$WORKTREE' && npm run build" >/dev/null 2>&1 && BUILD_OK=1
    else
      (cd "$WORKTREE" 2>/dev/null || cd "$REPO") && npm run build >/dev/null 2>&1 && BUILD_OK=1
    fi
    if [ "$BUILD_OK" = "0" ]; then
      GATE_PASS=0; GATE_REASON="build_failed_on_gate_check"
    fi
  fi
fi

# Gate: needs_split check
NEEDS_SPLIT=$(echo "$RESULT_CLEAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('needs_split', False))" 2>/dev/null || echo "False")
if [ "$NEEDS_SPLIT" = "True" ] || [ "$NEEDS_SPLIT" = "true" ]; then
  GATE_PASS=0; GATE_REASON="needs_split_flagged_by_worker"
fi

# Gate: file count check (max 5 new+modified, configurable via MAX_FILES)
if [ "$GATE_PASS" = "1" ] && [ -n "$COMMIT" ] && [ "$COMMIT" != "null" ]; then
  MAX_FILES="${MAX_FILES:-5}"
  if is_remote; then
    FILE_COUNT=$(rcmd "cd '$WORKTREE' && git diff --name-only '$BASELINE' 2>/dev/null | grep -vE '^(\.task-prompt\.md|\.task-result\.json|CLAUDE\.md|package\.json|package-lock\.json)$' | wc -l" 2>/dev/null || echo "0")
  else
    FILE_COUNT=$( (cd "$WORKTREE" 2>/dev/null && git diff --name-only "$BASELINE" 2>/dev/null | grep -vE '^(\.task-prompt\.md|\.task-result\.json|CLAUDE\.md|package\.json|package-lock\.json)$' | wc -l) || echo "0" )
  fi
  FILE_COUNT=$(echo "$FILE_COUNT" | tr -d ' ')
  if [ "$FILE_COUNT" -gt "$MAX_FILES" ] 2>/dev/null; then
    GATE_PASS=0; GATE_REASON="too_many_files_changed (${FILE_COUNT}>${MAX_FILES})"
  fi
fi

# Gate: env var detection (warning only, not blocking)
if [ "$GATE_PASS" = "1" ] && [ -n "$COMMIT" ] && [ "$COMMIT" != "null" ]; then
  NEW_ENVS=""
  if is_remote; then
    NEW_ENVS=$(rcmd "cd '$WORKTREE' && git diff '$BASELINE' -- . ':(exclude).task-prompt.md' ':(exclude).task-result.json' ':(exclude)CLAUDE.md' 2>/dev/null | grep -oE 'process\.env\.[A-Z_]+' | sort -u" 2>/dev/null || echo "")
  else
    NEW_ENVS=$( (cd "$WORKTREE" 2>/dev/null && git diff "$BASELINE" -- . ':(exclude).task-prompt.md' ':(exclude).task-result.json' ':(exclude)CLAUDE.md' 2>/dev/null | grep -oE 'process\.env\.[A-Z_]+' | sort -u) || echo "" )
  fi
  if [ -n "$NEW_ENVS" ]; then
    log "gate" "env_var_warning" "\"new_env_refs\":\"$(echo $NEW_ENVS | tr '\n' ',')\""
  fi
fi

if [ "$GATE_PASS" = "1" ]; then
  log "gate" "pass" "\"status\":\"$STATUS\",\"build\":\"$BUILD\",\"commit\":\"$COMMIT\""
else
  log "gate" "fail" "\"reason\":\"$GATE_REASON\",\"status\":\"$STATUS\",\"build\":\"$BUILD\",\"commit\":\"$COMMIT\""
  "$SCRIPTS_DIR/worker-session.sh" stop "$TASK_ID" 2>/dev/null
  # Cleanup on gate failure too
  if [ "$CLEANUP" = "1" ]; then
    if is_remote; then
      rcmd "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null" || true
    else
      cd "$REPO"
      git worktree remove "$WORKTREE" --force 2>/dev/null || true
      git branch -D "$BRANCH" 2>/dev/null || true
    fi
    log "cleanup" "done"
  fi
  exit $EXIT_GATE
fi

# ============================================================================
# Phase 5: Merge (clean oneline output)
# ============================================================================
if is_remote; then
  rcmd "cd '$REPO' && git merge '$BRANCH' --no-edit" >/dev/null 2>&1
  MERGE_COMMIT=$(rcmd "cd '$REPO' && git log -1 --oneline")
else
  cd "$REPO"
  git merge "$BRANCH" --no-edit >/dev/null 2>&1
  MERGE_COMMIT=$(git log -1 --oneline)
fi

# Show merge diff stat (compact)
if is_remote; then
  DIFF_STAT=$(rcmd "cd '$REPO' && git diff --stat HEAD~1 2>/dev/null | tail -1" || echo "")
else
  DIFF_STAT=$(git diff --stat HEAD~1 2>/dev/null | tail -1 || echo "")
fi
log "merge" "success" "\"commit\":\"$MERGE_COMMIT\",\"diff\":\"$DIFF_STAT\""

# ============================================================================
# Phase 6: Verify & Deploy (optional, project-type-aware)
# ============================================================================
# VERIFY_MODE: browser (default for web), api, test, none
# Auto-detect if not set: has vercel.json/.vercel → browser; has src/main → api; else test
VERIFY_MODE="${VERIFY_MODE:-}"
if [ -z "$VERIFY_MODE" ] && [ "$DEPLOY" = "1" ]; then
  if [ -d "$REPO/.vercel" ] || [ -f "$REPO/vercel.json" ]; then
    VERIFY_MODE="browser"
  elif [ -f "$REPO/Dockerfile" ] || [ -f "$REPO/docker-compose.yml" ]; then
    VERIFY_MODE="api"
  else
    VERIFY_MODE="test"
  fi
fi

if [ "$DEPLOY" = "1" ] && ! is_remote; then
  case "${VERIFY_MODE:-none}" in
    browser)
      # Web projects: Vercel deploy + browser verification
      if [ -x "$SCRIPTS_DIR/deploy-verify.sh" ]; then
        log "deploy" "starting"
        DEPLOY_ARGS=("$REPO")
        if [ -z "${VERIFY_MANIFEST:-}" ] || [ ! -f "${VERIFY_MANIFEST:-}" ]; then
          DEPLOY_ARGS+=("/" "/search" "/explore" "/map")
        fi

        DEPLOY_OUT=$(
          VERIFY_BROWSER="${VERIFY_BROWSER:-0}" \
          VERIFY_MANIFEST="${VERIFY_MANIFEST:-}" \
          VERIFY_SHOTS_DIR="${VERIFY_SHOTS_DIR:-/tmp/deploy-shots}" \
          "$SCRIPTS_DIR/deploy-verify.sh" "${DEPLOY_ARGS[@]}" 2>&1
        )

        VERDICT=$(echo "$DEPLOY_OUT" | grep '"verdict"' | python3 -c "import sys,json; print(json.load(sys.stdin)['verdict'])" 2>/dev/null || echo "unknown")
        BROWSER_VERDICT=$(echo "$DEPLOY_OUT" | grep '"browser_verify"' | tail -1 | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','none'))" 2>/dev/null || echo "none")

        if [ "$BROWSER_VERDICT" != "none" ]; then
          log "deploy" "$VERDICT" "\"browser\":\"$BROWSER_VERDICT\""
        else
          log "deploy" "$VERDICT"
        fi
      fi
      ;;
    api)
      # API/backend: run tests + optional health check
      log "verify" "starting" "\"mode\":\"api\""
      TEST_OK=0
      (cd "$REPO" && npm test 2>/dev/null) && TEST_OK=1 || true
      HEALTH_OK=0
      if [ -n "${API_HEALTH_URL:-}" ]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$API_HEALTH_URL" 2>/dev/null || echo "000")
        [ "$HTTP_CODE" = "200" ] && HEALTH_OK=1
        log "verify" "health_check" "\"url\":\"$API_HEALTH_URL\",\"http\":$HTTP_CODE"
      fi
      if [ "$TEST_OK" = "1" ]; then
        log "verify" "pass" "\"mode\":\"api\",\"tests\":\"pass\",\"health\":$HEALTH_OK"
      else
        log "verify" "fail" "\"mode\":\"api\",\"tests\":\"fail\""
      fi
      ;;
    test)
      # Library/CLI: run test suite only
      log "verify" "starting" "\"mode\":\"test\""
      if (cd "$REPO" && npm test 2>/dev/null); then
        log "verify" "pass" "\"mode\":\"test\""
      else
        log "verify" "fail" "\"mode\":\"test\""
      fi
      ;;
    none|*)
      log "deploy" "skipped"
      ;;
  esac
else
  log "deploy" "skipped"
fi

# ============================================================================
# Phase 7: Cleanup
# ============================================================================
"$SCRIPTS_DIR/worker-session.sh" stop "$TASK_ID" 2>/dev/null || true
if [ "$CLEANUP" = "1" ]; then
  if is_remote; then
    rcmd "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null" || true
  else
    cd "$REPO"
    git worktree remove "$WORKTREE" --force 2>/dev/null || true
    git branch -D "$BRANCH" 2>/dev/null || true
  fi
  log "cleanup" "done"
else
  log "cleanup" "skipped"
fi

# Success schema: three-layer
CODE_SUCCESS="true"  # We have a commit
GATE_SUCCESS="true"  # Gate passed
FUNC_SUCCESS="false" # Default false unless deploy verified
if [ "${VERIFY_MODE:-none}" != "none" ] && [ "$DEPLOY" = "1" ]; then
  FUNC_SUCCESS="true"  # Deploy verification ran
fi
log "complete" "success" "\"task\":\"$TASK_ID\",\"total_polls\":$POLL,\"code_success\":$CODE_SUCCESS,\"gate_success\":$GATE_SUCCESS,\"functional_success\":$FUNC_SUCCESS"
