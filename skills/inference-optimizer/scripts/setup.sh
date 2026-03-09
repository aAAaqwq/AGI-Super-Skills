#!/usr/bin/env bash
# Setup inference-optimizer: copy commands into workspace, make scripts executable.
# Run after install. Targets ~/clawd and ~/.openclaw/workspace-whatsapp.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_MAIN="${WORKSPACE_MAIN:-$HOME/clawd}"
WORKSPACE_WHATSAPP="${WORKSPACE_WHATSAPP:-$HOME/.openclaw/workspace-whatsapp}"

chmod +x "$SKILL_DIR/scripts/openclaw-audit.sh"
chmod +x "$SKILL_DIR/scripts/purge-stale-sessions.sh"
echo "[OK] Scripts executable"

AUDIT_PATH="$SKILL_DIR/scripts/openclaw-audit.sh"
PURGE_PATH="$SKILL_DIR/scripts/purge-stale-sessions.sh"

SNIPPET_AGENTS="

## Chat commands (exact match, run immediately)

| Command | Action |
| \`/optimize\` or \`/audit\` | Exec \`bash $AUDIT_PATH\`, return raw output. Do NOT ask what to optimize. Do NOT list options. |"

SNIPPET_TOOLS="

## inference-optimizer

| App | Use | Example |
| \`/optimize\` | Run audit script | exec \`bash $AUDIT_PATH\`, return raw output. Do NOT ask what to optimize. |
| purge sessions | After /optimize if user approves | exec \`bash $PURGE_PATH\`, return raw output. |"

for ws in "$WORKSPACE_MAIN" "$WORKSPACE_WHATSAPP"; do
  [[ -d "$ws" ]] || continue
  if [[ -f "$ws/AGENTS.md" ]]; then
    if ! grep -q "/optimize" "$ws/AGENTS.md" 2>/dev/null; then
      echo "$SNIPPET_AGENTS" >> "$ws/AGENTS.md"
      echo "[OK] Added /optimize to $ws/AGENTS.md"
    else
      echo "[SKIP] $ws/AGENTS.md already has /optimize"
    fi
  else
    echo "[WARN] $ws/AGENTS.md not found"
  fi
  if [[ -f "$ws/TOOLS.md" ]]; then
    if ! grep -q "inference-optimizer" "$ws/TOOLS.md" 2>/dev/null; then
      echo "$SNIPPET_TOOLS" >> "$ws/TOOLS.md"
      echo "[OK] Added /optimize to $ws/TOOLS.md"
    else
      echo "[SKIP] $ws/TOOLS.md already has inference-optimizer"
    fi
  else
    echo "[WARN] $ws/TOOLS.md not found"
  fi
done

echo ""
echo "Done. Purge allowlist: ensure find *, find **, rm *, rm ** in exec-approvals.json."
echo "Verify: bash $SKILL_DIR/scripts/verify.sh"
