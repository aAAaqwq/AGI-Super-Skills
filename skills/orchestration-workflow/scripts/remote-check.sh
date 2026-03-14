#!/usr/bin/env bash
# ============================================================================
# remote-check.sh — Pre-flight check for remote worker dispatch
# ============================================================================
# Usage: ./remote-check.sh user@host
#
# Verifies: SSH connectivity, tmux, codex/claude, git, npm, disk space
# ============================================================================

set -euo pipefail

HOST="${1:?Usage: remote-check.sh user@host}"
echo "🔍 Remote pre-flight check: $HOST"
echo ""

ALL_OK=1
check() {
  local label="$1" cmd="$2"
  if ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" "$cmd" &>/dev/null; then
    echo "  ✅ $label"
  else
    echo "  ❌ $label"
    ALL_OK=0
  fi
}

# 1. SSH connectivity
echo "=== Connectivity ==="
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" "echo ok" &>/dev/null; then
  echo "  ✅ SSH connection (passwordless)"
else
  echo "  ❌ SSH connection failed (check key, known_hosts, BatchMode)"
  echo ""
  echo "Fix:"
  echo "  ssh-copy-id $HOST"
  echo "  ssh -o StrictHostKeyChecking=accept-new $HOST"
  exit 1
fi

# 2. Required tools
echo ""
echo "=== Required Tools ==="
check "git" "command -v git"
check "tmux" "command -v tmux"
check "npm" "command -v npm"
check "node" "command -v node"

# 3. Coding agents
echo ""
echo "=== Coding Agents ==="
AGENTS=0
for agent in codex claude; do
  if ssh "$HOST" "command -v $agent" &>/dev/null; then
    VER=$(ssh "$HOST" "$agent --version 2>&1 | head -1" || echo "unknown")
    echo "  ✅ $agent ($VER)"
    AGENTS=$((AGENTS + 1))
  else
    echo "  ⚠️  $agent not found"
  fi
done
[ "$AGENTS" -eq 0 ] && echo "  ❌ No coding agents! Install codex or claude." && ALL_OK=0

# 4. Disk space
echo ""
echo "=== Disk Space ==="
AVAIL=$(ssh "$HOST" "df -h /tmp | tail -1 | awk '{print \$4}'" 2>/dev/null || echo "unknown")
echo "  /tmp available: $AVAIL"

# 5. orchestration-workflow installed?
echo ""
echo "=== Orchestration Workflow ==="
if ssh "$HOST" "[ -f ~/.openclaw/skills/orchestration-workflow/scripts/orchestrate.sh ]" 2>/dev/null; then
  echo "  ✅ Installed"
else
  echo "  ⚠️  Not installed. Run on remote:"
  echo "     git clone https://github.com/Arslan-Z/orchestration-workflow.git /tmp/orch-install && bash /tmp/orch-install/install.sh"
fi

echo ""
if [ "$ALL_OK" -eq 1 ]; then
  echo "🎉 All checks passed. Ready for remote dispatch:"
  echo "   WORKER_HOST=$HOST orchestrate.sh /repo task prompt.md codex --yolo"
else
  echo "⚠️  Some checks failed. Fix above issues before remote dispatch."
fi
