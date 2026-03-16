#!/usr/bin/env bash
# embed-switch.sh — Switch QMD embedding backend
# Usage: ./embed-switch.sh google|ollama|local
#
# ⚠️  Switching backends changes embedding dimensions!
#     After switching, run: qmd embed -f  (force re-embed all)
set -euo pipefail

BACKEND="${1:-}"
if [ -z "$BACKEND" ]; then
    echo "Usage: $0 google|ollama|local"
    echo ""
    echo "Current: QMD_EMBED_BACKEND=${QMD_EMBED_BACKEND:-auto}"
    echo ""
    echo "Backends:"
    echo "  google  — Google AI Studio gemini-embedding-001 (3072-dim, free tier)"
    echo "  ollama  — Mac Studio Ollama qwen3-embedding:8b (4096-dim, free/local)"
    echo "  local   — node-llama-cpp embeddinggemma-300M (768-dim, CPU)"
    exit 1
fi

if [[ "$BACKEND" != "google" && "$BACKEND" != "ollama" && "$BACKEND" != "local" ]]; then
    echo "❌ Invalid backend: $BACKEND (must be google|ollama|local)"
    exit 1
fi

# Update .bashrc
sed -i "s/^export QMD_EMBED_BACKEND=.*/export QMD_EMBED_BACKEND=${BACKEND}/" ~/.bashrc
sed -i "s/^export QMD_EMBED_BACKEND=.*/export QMD_EMBED_BACKEND=${BACKEND}/" ~/.profile 2>/dev/null

# Export for current session
export QMD_EMBED_BACKEND="$BACKEND"

echo "✅ Switched to: ${BACKEND}"
echo ""
echo "⚠️  Embedding dimensions changed! You MUST re-embed:"
echo "   qmd embed -f"
echo ""
echo "   This re-generates ALL vector embeddings (~9600 files)."
echo "   Estimated time: ~5-15 min depending on backend speed."
