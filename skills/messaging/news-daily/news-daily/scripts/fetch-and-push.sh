#!/bin/bash
# News Daily - Fetch and Push Script
# This script fetches news and pushes it via OpenClaw message tool

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANNEL="${1:-telegram}"

echo "📰 Fetching daily news..."

# Fetch news (this will generate the summary)
cd "$SCRIPT_DIR"
./news-fetcher.sh

# Read the generated summary
SUMMARY_FILE="$SCRIPT_DIR/../output/daily-summary.txt"
if [ -f "$SUMMARY_FILE" ]; then
    echo "📤 Pushing to $CHANNEL..."
    
    # Output the summary so OpenClaw can pick it up
    cat "$SUMMARY_FILE"
    
    echo ""
    echo "✅ News fetched successfully!"
    echo "📊 Message size: $(wc -c < "$SUMMARY_FILE") bytes"
else
    echo "❌ Error: Summary file not found at $SUMMARY_FILE"
    exit 1
fi
