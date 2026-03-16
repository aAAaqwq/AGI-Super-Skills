#!/usr/bin/env bash
# embed-status.sh — Show QMD embedding health + backend info
set -euo pipefail

echo "📊 QMD Embedding Status"
echo "========================"
echo ""

# Backend info
BACKEND="${QMD_EMBED_BACKEND:-auto}"
echo "Backend: ${BACKEND}"
case "$BACKEND" in
    google)  echo "  Model: ${QMD_GOOGLE_EMBED_MODEL:-gemini-embedding-001} (3072-dim)" ;;
    ollama)  echo "  URL: ${QMD_OLLAMA_EMBED_URL:-not set}"
             echo "  Model: ${QMD_OLLAMA_EMBED_MODEL:-qwen3-embedding:8b} (4096-dim)" ;;
    local)   echo "  Model: ${QMD_EMBED_MODEL:-embeddinggemma-300M} (768-dim)" ;;
    *)       echo "  Auto-detect (google > ollama > local)" ;;
esac
echo ""

# QMD status
echo "Index Status:"
qmd status 2>/dev/null | grep -E "Total|Vector|Pending|Updated|Collection" || echo "  ⚠️  qmd status failed"
echo ""

# Backend connectivity
echo "Connectivity:"
GOOGLE_KEY="${QMD_GOOGLE_EMBED_KEY:-$(pass show api/google-ai-studio 2>/dev/null || echo "")}"
if [ -n "$GOOGLE_KEY" ]; then
    GTEST=$(curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" \
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key=${GOOGLE_KEY}" \
        -H 'Content-Type: application/json' \
        -d '{"content":{"parts":[{"text":"ping"}]}}' 2>/dev/null || echo "000")
    [ "$GTEST" = "200" ] && echo "  ✅ Google API: reachable" || echo "  ❌ Google API: HTTP $GTEST"
else
    echo "  ⚠️  Google API: no key"
fi

OLLAMA_URL="${QMD_OLLAMA_EMBED_URL:-}"
if [ -n "$OLLAMA_URL" ]; then
    OTEST=$(curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" "${OLLAMA_URL}/api/tags" 2>/dev/null || echo "000")
    [ "$OTEST" = "200" ] && echo "  ✅ Ollama: reachable" || echo "  ❌ Ollama ($OLLAMA_URL): HTTP $OTEST"
else
    echo "  ⚠️  Ollama: not configured"
fi
