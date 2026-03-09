#!/bin/bash
#
# retrieve.sh - View cached analyses (FREE)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUTS_DIR="$SKILL_DIR/assets/outputs"

TICKER="${1:-}"
FRAMEWORK="${2:-}"

[ -z "$TICKER" ] && { echo "Usage: ./retrieve.sh <TICKER> [FRAMEWORK]"; exit 1; }

TICKER_UPPER=$(echo "$TICKER" | tr '[:lower:]' '[:upper:]')

# Map numbers to IDs
declare -A NUM_MAP=(
    ["1"]="01-phase"
    ["2"]="02-metrics"
    ["3"]="03-ai-moat"
    ["4"]="04-strategic-moat"
    ["5"]="05-sentiment"
    ["6"]="06-growth"
    ["7"]="07-business"
    ["8"]="08-risk"
    ["full"]="all"
)

if [ -z "$FRAMEWORK" ]; then
    # List all available
    echo "Cached analyses for $TICKER_UPPER:"
    ls -1 "$OUTPUTS_DIR"/${TICKER_UPPER}_*.md 2>/dev/null || echo "  (none)"
    exit 0
fi

if [ "$FRAMEWORK" = "full" ] || [ "$FRAMEWORK" = "all" ]; then
    # Show all
    for f in "$OUTPUTS_DIR"/${TICKER_UPPER}_*.md; do
        [ -f "$f" ] || continue
        echo ""
        echo "=== $(basename "$f") ==="
        cat "$f"
        echo ""
    done
    exit 0
fi

# Single framework
FW_ID="${NUM_MAP[$FRAMEWORK]:-$FRAMEWORK}"
FILE=$(ls "$OUTPUTS_DIR"/${TICKER_UPPER}_${FW_ID}.md 2>/dev/null | head -1)

if [ -f "$FILE" ]; then
    echo "=== $(basename "$FILE") ==="
    echo ""
    cat "$FILE"
else
    echo "Not found: $TICKER_UPPER framework $FRAMEWORK"
    echo "Run: ./scripts/run-single-step.sh $TICKER_UPPER $FW_ID"
    exit 1
fi
