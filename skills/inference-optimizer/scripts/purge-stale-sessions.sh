#!/usr/bin/env bash
# Purge stale OpenClaw sessions (>24h) and stub memory files (<200 chars).
# Part of inference-optimizer skill. Run on VPS.

set -euo pipefail

SESSIONS="${OPENCLAW_SESSIONS:-$HOME/.openclaw/agents/main/sessions}"
[[ -d "$SESSIONS" ]] || SESSIONS="$HOME/.clawdbot/agents.main/sessions"
MEMORY_DIR="$HOME/.openclaw/workspace-whatsapp/memory"
[[ -d "$MEMORY_DIR" ]] || MEMORY_DIR="$HOME/clawd/memory"

if [[ ! -d "$SESSIONS" ]]; then
  echo "Sessions dir not found (run on VPS): $SESSIONS"
  exit 0
fi

echo "=== Purge stale sessions ==="
BEFORE=$(find "$SESSIONS" -name "*.jsonl" 2>/dev/null | wc -l)
find "$SESSIONS" -type f -name "*.jsonl" -mtime +1 -delete 2>/dev/null || true
AFTER=$(find "$SESSIONS" -name "*.jsonl" 2>/dev/null | wc -l)
echo "  Sessions: $BEFORE -> $AFTER (removed $((BEFORE - AFTER)))"

echo ""
echo "=== Purge stub memory files (<200 chars) ==="
PURGED=0
if [[ -d "$MEMORY_DIR" ]]; then
  shopt -s nullglob 2>/dev/null || true
  for f in "$MEMORY_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    if [[ $(wc -c < "$f") -lt 200 ]]; then
      rm -f "$f"
      echo "  removed $(basename "$f")"
      ((PURGED++)) || true
    fi
  done
  [[ $PURGED -eq 0 ]] && echo "  none found" || echo "  purged $PURGED files"
else
  echo "  memory dir not found: $MEMORY_DIR"
fi

echo ""
echo "=== Verify ==="
echo "  Sessions: $(find "$SESSIONS" -name "*.jsonl" 2>/dev/null | wc -l)"
echo "  Memory files: $(find "$MEMORY_DIR" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l)"
