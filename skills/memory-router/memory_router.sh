#!/bin/bash
# memory_router.sh — Quick QMD context retrieval for agents
# Usage: ./memory_router.sh "question" [collection] [num_results]
set -euo pipefail

QUERY="${1:?Usage: memory_router.sh '<question>' [collection] [num_results]}"
COLLECTION="${2:-}"
NUM="${3:-5}"

echo "=== Memory Router ==="
echo "Query: $QUERY"
echo ""

if [ -n "$COLLECTION" ]; then
  echo "--- Collection: $COLLECTION ---"
  qmd query -c "$COLLECTION" "$QUERY" -n "$NUM" --line-numbers 2>&1
else
  echo "--- Hybrid Search (all collections) ---"
  qmd query "$QUERY" -n "$NUM" --line-numbers 2>&1
fi

echo ""
echo "--- Daily Memory (recent) ---"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d 2>/dev/null || echo "")
for f in ~/clawd/memory/${TODAY}.md ~/clawd/memory/${YESTERDAY}.md; do
  if [ -f "$f" ]; then
    echo "  File: $f"
    grep -in "$(echo "$QUERY" | cut -d' ' -f1-3)" "$f" 2>/dev/null | head -5 || true
  fi
done

echo ""
echo "=== End Router ==="
