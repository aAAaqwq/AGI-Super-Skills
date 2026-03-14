#!/usr/bin/env bash
# ============================================================================
# worker-session.sh — Unified Terminal Session Manager (local + remote)
# ============================================================================
# Local: uses tmux directly (or zellij as fallback)
# Remote: uses persistent-ssh-tmux skill (ssh_tmux_session.sh)
#
# Usage:
#   ./worker-session.sh start  <name> <cwd> <agent> [prompt]
#   ./worker-session.sh send   <name> <message>
#   ./worker-session.sh read   <name> [lines]
#   ./worker-session.sh status <name>
#   ./worker-session.sh stop   <name>
#   ./worker-session.sh list
#
# Environment:
#   WORKER_HOST=user@host    — Run on remote machine via SSH+tmux
#   WORKER_YOLO=1            — Use --dangerously-bypass for codex
#   WORKER_MUX=tmux|zellij   — Override multiplexer (local only)
#
# Examples:
#   ./worker-session.sh start task-1 /tmp/project codex
#   WORKER_HOST=root@100.125.204.29 ./worker-session.sh start task-1 /tmp/project codex
# ============================================================================

set -euo pipefail

WORKER_HOST="${WORKER_HOST:-}"

# ---- Resolve ssh_tmux_session.sh path ----
resolve_ssh_script() {
  local candidates=(
    "$(cd "$(dirname "$0")" && pwd)/../../../persistent-ssh-tmux/scripts/ssh_tmux_session.sh"
    "$HOME/.openclaw/skills/persistent-ssh-tmux/scripts/ssh_tmux_session.sh"
  )
  for c in "${candidates[@]}"; do
    if [ -x "$c" ]; then
      echo "$c"
      return
    fi
  done
  echo ""
}

SSH_TMUX_SCRIPT="$(resolve_ssh_script)"

# ---- Check if remote mode ----
is_remote() {
  [ -n "$WORKER_HOST" ]
}

# ---- Auto-detect local multiplexer ----
detect_mux() {
  if command -v tmux &>/dev/null; then
    echo "tmux"
  elif command -v zellij &>/dev/null; then
    echo "zellij"
  else
    echo '{"error":"No terminal multiplexer found. Install tmux or zellij."}' >&2
    exit 1
  fi
}

MUX="${WORKER_MUX:-$(detect_mux)}"

# ---- LOCAL: tmux implementations ----
tmux_start() {
  local name="$1" cwd="$2" cmd="$3"
  tmux new-session -d -s "$name" -x 200 -y 50 -c "$cwd"
  tmux send-keys -t "$name" "$cmd" Enter
}

tmux_send() {
  local name="$1" msg="$2"
  tmux send-keys -t "$name" "$msg" Enter
}

tmux_read() {
  local name="$1" lines="${2:-50}"
  tmux capture-pane -t "$name" -p -S "-$lines" 2>/dev/null | grep -v "^$"
}

tmux_status() {
  local name="$1"
  if tmux has-session -t "$name" 2>/dev/null; then
    echo "running"
  else
    echo "stopped"
  fi
}

tmux_stop() {
  local name="$1"
  tmux send-keys -t "$name" "/exit" Enter 2>/dev/null
  sleep 2
  tmux kill-session -t "$name" 2>/dev/null || true
}

tmux_list() {
  tmux list-sessions -F '{"name":"#{session_name}","created":"#{session_created}","windows":#{session_windows}}' 2>/dev/null || echo "[]"
}

# ---- LOCAL: zellij implementations ----
zellij_start() {
  local name="$1" cwd="$2" cmd="$3"
  zellij -s "$name" options --default-cwd "$cwd" &
  sleep 2
  zellij -s "$name" action write-chars "$cmd"
  zellij -s "$name" action write 10
}

zellij_send() {
  local name="$1" msg="$2"
  zellij -s "$name" action write-chars "$msg"
  zellij -s "$name" action write 10
}

zellij_read() {
  local name="$1" lines="${2:-50}"
  local tmpfile="/tmp/zellij-dump-${name}.txt"
  zellij -s "$name" action dump-screen "$tmpfile" 2>/dev/null
  tail -n "$lines" "$tmpfile" 2>/dev/null | grep -v "^$"
  rm -f "$tmpfile"
}

zellij_status() {
  local name="$1"
  if zellij list-sessions 2>/dev/null | grep -q "$name"; then
    echo "running"
  else
    echo "stopped"
  fi
}

zellij_stop() {
  local name="$1"
  zellij -s "$name" action write-chars "/exit"
  zellij -s "$name" action write 10
  sleep 2
  zellij delete-session "$name" 2>/dev/null || true
}

zellij_list() {
  zellij list-sessions 2>/dev/null || echo "[]"
}

# ---- REMOTE: persistent-ssh-tmux implementations ----
remote_start() {
  local name="$1" cwd="$2" cmd="$3"
  if [ -z "$SSH_TMUX_SCRIPT" ]; then
    echo '{"error":"persistent-ssh-tmux skill not found. Install it or set path."}' >&2
    exit 1
  fi
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" ensure --quiet
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" send "cd $cwd && $cmd" --quiet
}

remote_send() {
  local name="$1" msg="$2"
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" send "$msg" --quiet
}

remote_read() {
  local name="$1" lines="${2:-200}"
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" capture "$lines"
}

remote_status() {
  local name="$1"
  if "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" list 2>/dev/null | grep -q "$name"; then
    echo "running"
  else
    echo "stopped"
  fi
}

remote_stop() {
  local name="$1"
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" send "/exit" --quiet 2>/dev/null || true
  sleep 2
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "$name" kill 2>/dev/null || true
}

remote_list() {
  "$SSH_TMUX_SCRIPT" "$WORKER_HOST" "" list 2>/dev/null || echo "[]"
}

# ---- Dispatch: local or remote ----
dispatch() {
  local action="$1"; shift
  if is_remote; then
    remote_"$action" "$@"
  else
    ${MUX}_"$action" "$@"
  fi
}

# ---- Agent command builder ----
build_agent_cmd() {
  local agent="$1" prompt="${2:-}" cwd="$3"
  local yolo="${WORKER_YOLO:-0}"
  local prompt_file="${cwd}/.task-prompt.md"

  # Write .task-prompt.md only if prompt argument is given
  if [ -n "$prompt" ]; then
    cat > "$prompt_file" << PROMPT_EOF
# Task Prompt

$prompt

---

## Output Protocol (MUST follow)

When you are completely done (after commit), create a file called \`.task-result.json\` with this exact structure:

\`\`\`json
{
  "status": "success or failed",
  "files_created": ["list of new files"],
  "files_modified": ["list of modified files"],
  "commit": "short hash or null if no commit",
  "build_pass": true or false,
  "notes": "brief summary of what was done",
  "errors": ["list of any errors encountered, empty if none"]
}
\`\`\`

This file is how the Orchestrator knows you are finished. Do NOT skip it.

**Important**: Do NOT commit \`.task-prompt.md\` or \`.task-result.json\`. They are orchestration files, not project code. If you use \`git add -A\`, exclude them: \`git add -A && git reset HEAD .task-prompt.md .task-result.json\`
PROMPT_EOF
  fi

  if [ ! -f "$prompt_file" ] && ! is_remote; then
    echo "echo 'ERROR: .task-prompt.md not found in $cwd'"
    return
  fi

  local read_instruction="Read .task-prompt.md for your full instructions, then execute them."
  case "$agent" in
    codex)
      if [ "$yolo" = "1" ]; then
        echo "codex --dangerously-bypass-approvals-and-sandbox '$read_instruction'"
      else
        echo "codex --full-auto '$read_instruction'"
      fi
      ;;
    claude)
      echo "claude --dangerously-skip-permissions '$read_instruction'"
      ;;
    *)
      echo "$agent '$read_instruction'"
      ;;
  esac
}

# ---- Main dispatch ----
ACTION="${1:?Usage: worker-session.sh <start|send|read|status|stop|list> ...}"
shift

case "$ACTION" in
  start)
    NAME="${1:?name required}"
    CWD="${2:?cwd required}"
    AGENT="${3:?agent required (codex|claude)}"
    PROMPT="${4:-}"
    CMD="cd $CWD && $(build_agent_cmd "$AGENT" "$PROMPT" "$CWD")"

    dispatch start "$NAME" "$CWD" "$CMD"

    local_or_remote="local"
    is_remote && local_or_remote="remote:$WORKER_HOST"
    echo "{\"action\":\"start\",\"name\":\"$NAME\",\"mode\":\"$local_or_remote\",\"agent\":\"$AGENT\",\"cwd\":\"$CWD\"}"
    ;;

  send)
    NAME="${1:?name required}"
    MSG="${2:?message required}"
    dispatch send "$NAME" "$MSG"
    echo "{\"action\":\"send\",\"name\":\"$NAME\",\"message\":\"$(echo "$MSG" | head -c 100)\"}"
    ;;

  read)
    NAME="${1:?name required}"
    LINES="${2:-50}"
    OUTPUT=$(dispatch read "$NAME" "$LINES")
    ESCAPED=$(echo "$OUTPUT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"(parse error)\"")
    echo "{\"action\":\"read\",\"name\":\"$NAME\",\"lines\":$LINES,\"output\":$ESCAPED}"
    ;;

  status)
    NAME="${1:?name required}"
    STATE=$(dispatch status "$NAME")
    local_or_remote="local"
    is_remote && local_or_remote="remote:$WORKER_HOST"
    echo "{\"action\":\"status\",\"name\":\"$NAME\",\"state\":\"$STATE\",\"mode\":\"$local_or_remote\"}"
    ;;

  stop)
    NAME="${1:?name required}"
    dispatch stop "$NAME"
    echo "{\"action\":\"stop\",\"name\":\"$NAME\"}"
    ;;

  list)
    echo "{\"action\":\"list\",\"sessions\":["
    dispatch list
    echo "]}"
    ;;

  *)
    echo "{\"error\":\"Unknown action: $ACTION\"}" >&2
    exit 1
    ;;
esac
