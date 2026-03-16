#!/usr/bin/env bash
# embed-test.sh — Test current QMD embedding backend with sample texts
# Usage: ./embed-test.sh [backend] [text]
#   backend: google|ollama|local (default: current QMD_EMBED_BACKEND)
#   text: test text (default: "测试中文embedding效果")
set -euo pipefail

BACKEND="${1:-${QMD_EMBED_BACKEND:-auto}}"
TEXT="${2:-测试中文embedding效果}"
GOOGLE_KEY="${QMD_GOOGLE_EMBED_KEY:-$(pass show api/google-ai-studio 2>/dev/null || echo "")}"
OLLAMA_URL="${QMD_OLLAMA_EMBED_URL:-http://100.65.110.126:11434}"
OLLAMA_MODEL="${QMD_OLLAMA_EMBED_MODEL:-qwen3-embedding:8b}"
GOOGLE_MODEL="${QMD_GOOGLE_EMBED_MODEL:-gemini-embedding-001}"

test_google() {
    if [ -z "$GOOGLE_KEY" ]; then echo "❌ Google: no API key"; return 1; fi
    local START=$(date +%s%N)
    local RESP=$(curl -s --connect-timeout 5 \
        "https://generativelanguage.googleapis.com/v1beta/models/${GOOGLE_MODEL}:embedContent?key=${GOOGLE_KEY}" \
        -H 'Content-Type: application/json' \
        -d "{\"content\": {\"parts\":[{\"text\": \"${TEXT}\"}]}}")
    local END=$(date +%s%N)
    local MS=$(( (END - START) / 1000000 ))
    local DIM=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('embedding',{}).get('values',[])))" 2>/dev/null || echo "0")
    if [ "$DIM" -gt 0 ]; then
        echo "✅ Google (${GOOGLE_MODEL}): ${DIM}-dim, ${MS}ms"
    else
        echo "❌ Google: failed — $(echo "$RESP" | head -c 200)"
    fi
}

test_ollama() {
    local START=$(date +%s%N)
    local RESP=$(curl -s --connect-timeout 5 \
        "${OLLAMA_URL}/api/embed" \
        -H 'Content-Type: application/json' \
        -d "{\"model\": \"${OLLAMA_MODEL}\", \"input\": \"${TEXT}\"}" 2>/dev/null)
    local END=$(date +%s%N)
    local MS=$(( (END - START) / 1000000 ))
    local DIM=$(echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); e=d.get('embeddings',[[]])[0]; print(len(e))" 2>/dev/null || echo "0")
    if [ "$DIM" -gt 0 ]; then
        echo "✅ Ollama (${OLLAMA_MODEL}): ${DIM}-dim, ${MS}ms"
    else
        echo "❌ Ollama (${OLLAMA_URL}): offline or failed"
    fi
}

test_local() {
    local MODEL="${QMD_EMBED_MODEL:-hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf}"
    echo "ℹ️  Local (node-llama-cpp): model=${MODEL}"
    echo "   Run 'qmd embed --dry-run' to verify"
}

echo "🔍 QMD Embedding Backend Test"
echo "   Text: \"${TEXT}\""
echo "   Current backend: ${BACKEND}"
echo ""

case "$BACKEND" in
    google)  test_google ;;
    ollama)  test_ollama ;;
    local)   test_local ;;
    auto|all|*)
        test_google
        test_ollama
        test_local
        ;;
esac
