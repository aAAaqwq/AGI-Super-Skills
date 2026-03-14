#!/usr/bin/env bash
# orchestrate-start.sh — Non-blocking: setup worktree + launch worker + return immediately
#
# Usage: orchestrate-start.sh <repo> <task-id> <prompt-file> [agent] [--yolo] [--skills="core frontend"]
#
# Creates:
#   /tmp/orch-tasks/<task-id>.state — JSON state file for patrol to read
#
# After this returns, set up a cron to run orchestrate-patrol.sh every 60-90s.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
# Find persistent-ssh-tmux skill (check multiple possible locations)
SSH_TMUX=""
for p in \
  "${SCRIPTS_DIR}/../../../persistent-ssh-tmux/scripts/ssh_tmux_session.sh" \
  "$HOME/.openclaw/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh" \
  "$HOME/.agents/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh"; do
  [ -f "$p" ] && SSH_TMUX="$p" && break
done
TASK_DIR="/tmp/orch-tasks"
mkdir -p "$TASK_DIR"

# ============================================================================
# Args
# ============================================================================
REPO="${1:?Usage: orchestrate-start.sh <repo> <task-id> <prompt-file> [agent] [--yolo] [--skills=...]}"
TASK_ID="${2:?Missing task-id}"
PROMPT_FILE="${3:?Missing prompt-file}"
AGENT="${4:-codex}"
shift 3; [ $# -gt 0 ] && shift || true

YOLO=0; DEPLOY=0; CLEANUP=1; SKILLS=""
for arg in "$@"; do
  case "$arg" in
    --yolo) YOLO=1 ;;
    --deploy) DEPLOY=1 ;;
    --no-cleanup) CLEANUP=0 ;;
    --skills=*) SKILLS="${arg#--skills=}" ;;
  esac
done

HOST="${WORKER_HOST:-localhost}"
BRANCH="feat/${TASK_ID}"
WORKTREE="/tmp/orch-${TASK_ID}"
STATE_FILE="${TASK_DIR}/${TASK_ID}.state"
SESSION_NAME="orch-${TASK_ID}"

log() { echo "{\"phase\":\"$1\",\"status\":\"$2\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"${3:+,$3}}"; }

# ============================================================================
# Helpers: local tmux vs remote ssh_tmux
# ============================================================================
tmux_ensure() {
  if [ "$HOST" = "localhost" ]; then
    tmux has-session -t "$1" 2>/dev/null || tmux new-session -d -s "$1"
  else
    bash "$SSH_TMUX" "$HOST" "$1" ensure --quiet
  fi
}
tmux_send() {
  if [ "$HOST" = "localhost" ]; then
    tmux send-keys -t "$1" "$2" C-m
  else
    bash "$SSH_TMUX" "$HOST" "$1" send "$2" --quiet
  fi
}
tmux_capture() {
  if [ "$HOST" = "localhost" ]; then
    tmux capture-pane -t "$1" -p -S -"${2:-30}"
  else
    bash "$SSH_TMUX" "$HOST" "$1" capture "${2:-30}" --quiet
  fi
}
tmux_kill() {
  if [ "$HOST" = "localhost" ]; then
    tmux kill-session -t "$1" 2>/dev/null || true
  else
    bash "$SSH_TMUX" "$HOST" "$1" kill --quiet 2>/dev/null || true
  fi
}

# ============================================================================
# Phase 0: Cleanup stale sessions
# ============================================================================
log "preflight" "cleanup"
tmux_kill "$SESSION_NAME"
if [ "$HOST" = "localhost" ]; then
  pkill -f "codex.*orch-${TASK_ID}|claude.*orch-${TASK_ID}" 2>/dev/null || true
fi

# ============================================================================
# Phase 1: Setup worktree
# ============================================================================
log "setup" "starting" "\"repo\":\"$REPO\",\"branch\":\"$BRANCH\",\"worktree\":\"$WORKTREE\""

if [ "$HOST" = "localhost" ]; then
  cd "$REPO"
  git worktree remove "$WORKTREE" --force 2>/dev/null || true
  git branch -D "$BRANCH" 2>/dev/null || true
  git worktree add "$WORKTREE" -b "$BRANCH" 2>/dev/null
  
  # Fast node_modules setup: copy from main repo if available
  # Gate on package.json (skip for non-Node.js projects)
  if [ "${SKIP_INSTALL:-}" != "1" ] && [ -f "$REPO/package.json" ] && [ -d "$REPO/node_modules" ]; then
    log "setup" "node_modules_copy"
    # Use rsync -a to preserve symlinks (cp -R follows symlinks on macOS!)
    if command -v rsync &>/dev/null; then
      rsync -a --quiet "$REPO/node_modules/" "$WORKTREE/node_modules/" 2>/dev/null || true
    else
      cp -RP "$REPO/node_modules" "$WORKTREE/node_modules" 2>/dev/null || true
    fi
  fi
  
  BASELINE=$(cd "$WORKTREE" && git rev-parse --short HEAD)
  log "setup" "ready" "\"baseline\":\"$BASELINE\""
  
  # Inject worker skills
  if [ -n "$SKILLS" ] && [ -x "$SCRIPTS_DIR/inject-worker-skills.sh" ]; then
    bash "$SCRIPTS_DIR/inject-worker-skills.sh" "$WORKTREE" $SKILLS 2>/dev/null || true
    log "setup" "skills_injected" "\"tags\":\"$SKILLS\""
  fi
  
  # Copy prompt file
  cp "$PROMPT_FILE" "$WORKTREE/.task-prompt.md"
  
  # Exclude scaffold files from git (belt + suspenders: info/exclude AND .gitignore)
  GIT_DIR=$(cd "$WORKTREE" && git rev-parse --git-dir 2>/dev/null)
  SCAFFOLD_FILES=".task-prompt.md .task-result.json .orch-setup-done CLAUDE.md .gitignore"
  if [ -n "$GIT_DIR" ]; then
    mkdir -p "$GIT_DIR/info"
    for f in $SCAFFOLD_FILES; do
      grep -q "$f" "$GIT_DIR/info/exclude" 2>/dev/null || echo "$f" >> "$GIT_DIR/info/exclude"
    done
  fi
  # Also write .gitignore in worktree (codex may explicitly git add files, bypassing info/exclude)
  cat > "$WORKTREE/.gitignore" << 'GIEOF'
# Orchestration scaffold — do NOT commit these
.task-prompt.md
.task-result.json
.orch-setup-done
GIEOF
else
  # Remote setup via SSH (npm install deferred to tmux, like local)
  ssh "$HOST" "cd '$REPO' && git worktree remove '$WORKTREE' --force 2>/dev/null; git branch -D '$BRANCH' 2>/dev/null; git worktree add '$WORKTREE' -b '$BRANCH' 2>/dev/null && [ -d '$REPO/node_modules' ] && rsync -a --quiet '$REPO/node_modules/' '$WORKTREE/node_modules/' 2>/dev/null" || true
  BASELINE=$(ssh "$HOST" "cd '$WORKTREE' && git rev-parse --short HEAD" 2>/dev/null)
  
  # Inject worker skills on remote
  if [ -n "$SKILLS" ] && [ -x "$SCRIPTS_DIR/inject-worker-skills.sh" ]; then
    # Generate CLAUDE.md locally, then scp to remote
    TEMP_INJECT="/tmp/orch-inject-${TASK_ID}"
    mkdir -p "$TEMP_INJECT"
    bash "$SCRIPTS_DIR/inject-worker-skills.sh" "$TEMP_INJECT" $SKILLS 2>/dev/null || true
    [ -f "$TEMP_INJECT/CLAUDE.md" ] && scp "$TEMP_INJECT/CLAUDE.md" "${HOST}:${WORKTREE}/CLAUDE.md" 2>/dev/null
    rm -rf "$TEMP_INJECT"
    log "setup" "skills_injected" "\"tags\":\"$SKILLS\",\"remote\":\"$HOST\""
  fi
  
  scp "$PROMPT_FILE" "${HOST}:${WORKTREE}/.task-prompt.md" 2>/dev/null
  
  # Setup git exclude on remote
  ssh "$HOST" "cd '$WORKTREE' && GIT_DIR=\$(git rev-parse --git-dir) && mkdir -p \"\$GIT_DIR/info\" && for f in .task-prompt.md .task-result.json .orch-setup-done CLAUDE.md; do grep -q \"\$f\" \"\$GIT_DIR/info/exclude\" 2>/dev/null || echo \"\$f\" >> \"\$GIT_DIR/info/exclude\"; done" 2>/dev/null || true
  
  log "setup" "ready" "\"baseline\":\"$BASELINE\",\"remote\":\"$HOST\""
fi

# ============================================================================
# Phase 2: Launch worker via persistent-ssh-tmux
# ============================================================================
log "worker" "launching" "\"agent\":\"$AGENT\",\"session\":\"$SESSION_NAME\""

# Ensure tmux session
tmux_ensure "$SESSION_NAME"

# Build codex/claude command
YOLO_FLAG=""
[ "$YOLO" = "1" ] && YOLO_FLAG="--full-auto"

AGENT_CMD=""
case "$AGENT" in
  codex)
    INSTALL_CMD="[ -f package.json ] && npm install --silent 2>/dev/null; touch .orch-setup-done;"
    [ "${SKIP_INSTALL:-}" = "1" ] && INSTALL_CMD="touch .orch-setup-done;"
    AGENT_CMD="cd '$WORKTREE' && ${INSTALL_CMD} codex exec $YOLO_FLAG 'Read .task-prompt.md and follow ALL instructions. When done, write .task-result.json and commit all changes.'"
    ;;
  claude)
    INSTALL_CMD="[ -f package.json ] && npm install --silent 2>/dev/null; touch .orch-setup-done;"
    [ "${SKIP_INSTALL:-}" = "1" ] && INSTALL_CMD="touch .orch-setup-done;"
    AGENT_CMD="cd '$WORKTREE' && ${INSTALL_CMD} claude --dangerously-skip-permissions -p 'Read .task-prompt.md and follow ALL instructions. When done, write .task-result.json and commit all changes.'"
    ;;
  *)
    AGENT_CMD="cd '$WORKTREE' && touch .orch-setup-done; $AGENT $YOLO_FLAG"
    ;;
esac

# Send command to tmux session
MARKER="__ORCH_${TASK_ID}_$(date +%s)__"
tmux_send "$SESSION_NAME" "echo $MARKER"
tmux_send "$SESSION_NAME" "$AGENT_CMD"
log "worker" "started" "\"marker\":\"$MARKER\""

# ============================================================================
# Write state file — patrol reads this
# ============================================================================
cat > "$STATE_FILE" << EOF
{
  "task_id": "${TASK_ID}",
  "repo": "${REPO}",
  "worktree": "${WORKTREE}",
  "branch": "${BRANCH}",
  "baseline": "${BASELINE}",
  "host": "${HOST}",
  "agent": "${AGENT}",
  "session": "${SESSION_NAME}",
  "marker": "${MARKER}",
  "deploy": ${DEPLOY},
  "cleanup": ${CLEANUP},
  "yolo": ${YOLO},
  "skills": "${SKILLS}",
  "ai_review": ${AI_REVIEW:-0},
  "max_retries": ${MAX_RETRIES:-3},
  "retry_count": 0,
  "verify_browser": "${VERIFY_BROWSER:-}",
  "verify_manifest": "${VERIFY_MANIFEST:-}",
  "verify_shots_dir": "${VERIFY_SHOTS_DIR:-}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "prev_file_hash": "",
  "idle_count": 0,
  "patrol_count": 0,
  "status": "running"
}
EOF

log "start" "complete" "\"state_file\":\"$STATE_FILE\""
echo ""
echo "✅ Worker launched in tmux session: $SESSION_NAME"
echo "📋 State file: $STATE_FILE"
echo "🔍 To patrol: bash $SCRIPTS_DIR/orchestrate-patrol.sh $TASK_ID"
echo "📺 To watch:  tmux attach -t $SESSION_NAME"
