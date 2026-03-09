#!/usr/bin/env bash
# Verify inference-optimizer installation and script enablement.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_MAIN="${WORKSPACE_MAIN:-$HOME/clawd}"
WORKSPACE_WHATSAPP="${WORKSPACE_WHATSAPP:-$HOME/.openclaw/workspace-whatsapp}"

PASS=0
FAIL=0

check() {
  if eval "$1"; then
    echo "[OK] $2"
    ((PASS++)) || true
    return 0
  else
    echo "[FAIL] $2"
    ((FAIL++)) || true
    return 1
  fi
}

echo "=== inference-optimizer verify ==="
echo ""

check "[[ -f $SKILL_DIR/optimization-agent.md ]]" "optimization-agent.md exists"
check "[[ -f $SKILL_DIR/scripts/openclaw-audit.sh ]]" "openclaw-audit.sh exists"
check "[[ -x $SKILL_DIR/scripts/openclaw-audit.sh ]]" "openclaw-audit.sh executable"
check "[[ -f $SKILL_DIR/scripts/purge-stale-sessions.sh ]]" "purge-stale-sessions.sh exists"
check "[[ -x $SKILL_DIR/scripts/purge-stale-sessions.sh ]]" "purge-stale-sessions.sh executable"
check "[[ -f $SKILL_DIR/SKILL.md ]]" "SKILL.md exists"

if [[ -f "$WORKSPACE_MAIN/AGENTS.md" ]] && grep -q "/optimize" "$WORKSPACE_MAIN/AGENTS.md" 2>/dev/null; then
  echo "[OK] AGENTS.md has /optimize (main workspace)"
  ((PASS++)) || true
else
  echo "[WARN] AGENTS.md missing /optimize — run setup.sh or add manually"
  ((FAIL++)) || true
fi

if [[ -d "$WORKSPACE_MAIN" ]]; then
  if bash "$SKILL_DIR/scripts/openclaw-audit.sh" 2>/dev/null | grep -q "Workspace file sizes"; then
    echo "[OK] openclaw-audit.sh runs (paths resolvable)"
    ((PASS++)) || true
  else
    echo "[WARN] openclaw-audit.sh may have path issues (run on VPS?)"
    ((FAIL++)) || true
  fi
else
  echo "[SKIP] Workspace not found, skipping audit dry-run"
fi

echo ""
echo "---"
echo "Pass: $PASS  Fail: $FAIL"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
