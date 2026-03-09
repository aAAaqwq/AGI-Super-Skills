#!/bin/bash
# Content Factory Agent - Installation Script
# Usage: bash install.sh

set -e

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📰 Installing Content Factory Agent..."

# Create data directories
mkdir -p "$SKILL_DIR/data"/{hotpool,topics,drafts,reviewed,published,config,assets,templates}

# Install Python deps
if [ -f "$SKILL_DIR/requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip3 install -r "$SKILL_DIR/requirements.txt" 2>/dev/null || \
    python3 -m pip install -r "$SKILL_DIR/requirements.txt" 2>/dev/null || \
    echo "⚠️ pip install failed, some features may not work"
fi

# Copy default config if not exists
if [ ! -f "$SKILL_DIR/data/config/sources.json" ]; then
    cp "$SKILL_DIR/scripts/aggregator/config.json" "$SKILL_DIR/data/config/sources.json" 2>/dev/null || true
fi

echo "✅ Content Factory installed at: $SKILL_DIR"
echo ""
echo "Quick start:"
echo "  1. Run: bash $SKILL_DIR/scripts/run_daily.sh"
echo "  2. Or step by step:"
echo "     python3 $SKILL_DIR/scripts/aggregator/fetch_all.py"
echo "     python3 $SKILL_DIR/scripts/topic_scorer.py"
echo "     python3 $SKILL_DIR/scripts/content_generator.py --top 3"
