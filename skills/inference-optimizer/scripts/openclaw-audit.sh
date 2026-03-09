#!/usr/bin/env bash
# openclaw-audit.sh — baseline token audit before optimization
# Part of inference-optimizer skill. Run on VPS before optimization.

WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/clawd}"
SESSIONS="${OPENCLAW_SESSIONS:-$HOME/.openclaw/agents/main/sessions}"
[[ -d "$SESSIONS" ]] || SESSIONS="$HOME/.clawdbot/agents.main/sessions"
CONFIG="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"

echo "=== Workspace file sizes (chars → ~tokens) ==="
for f in SOUL.md AGENTS.md TOOLS.md MEMORY.md USER.md HEARTBEAT.md; do
  fp="$WORKSPACE/$f"
  if [ -f "$fp" ]; then
    chars=$(wc -c < "$fp")
    tokens=$((chars / 4))
    echo "  $f: ${chars} chars ≈ ${tokens} tokens"
  else
    echo "  $f: NOT FOUND"
  fi
done

echo ""
echo "=== Daily memory files ==="
find "$WORKSPACE/memory" -name "*.md" 2>/dev/null | while read f; do
  chars=$(wc -c < "$f")
  tokens=$((chars / 4))
  echo "  $(basename $f): ${chars} chars ≈ ${tokens} tokens"
done

echo ""
echo "=== Session files (stale overhead) ==="
SESSION_COUNT=$(find "$SESSIONS" -name "*.jsonl" 2>/dev/null | wc -l)
SESSION_SIZE=$(du -sh "$SESSIONS" 2>/dev/null | cut -f1)
OLD_COUNT=$(find "$SESSIONS" -name "*.jsonl" -mtime +1 2>/dev/null | wc -l)
echo "  Total sessions: $SESSION_COUNT ($SESSION_SIZE)"
echo "  Sessions > 24h old: $OLD_COUNT (safe to purge)"

echo ""
echo "=== Config file ==="
CONFIG_CHARS=$(wc -c < "$CONFIG" 2>/dev/null || echo 0)
echo "  openclaw.json: ${CONFIG_CHARS} chars"

echo ""
echo "=== Estimated total system prompt tokens per request ==="
TOTAL_TOKENS=0
for f in SOUL.md AGENTS.md TOOLS.md MEMORY.md USER.md HEARTBEAT.md; do
  fp="$WORKSPACE/$f"
  [ -f "$fp" ] && TOTAL_TOKENS=$((TOTAL_TOKENS + $(wc -c < "$fp") / 4))
done
echo "  Workspace files: ~${TOTAL_TOKENS} tokens"
echo "  OpenClaw base system prompt: ~8000-15000 tokens (fixed overhead)"
echo "  Tools/skills schema: ~500-2000 tokens (varies by enabled skills)"
echo "  -------"
echo "  Estimated cold request total: ~$((TOTAL_TOKENS + 10000)) tokens"
