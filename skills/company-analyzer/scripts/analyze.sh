#!/bin/bash
#
# analyze.sh - Unified Company Analysis (LLM-powered via OpenClaw config)
# Usage: ./analyze.sh <TICKER> [--live]
#

set -euo pipefail

TICKER="${1:-}"
LIVE="${2:-}"

if [ -z "$TICKER" ]; then
    echo "Usage: ./analyze.sh <TICKER> [--live]"
    exit 1
fi

TICKER_UPPER=$(echo "$TICKER" | tr '[:lower:]' '[:upper:]')
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUTS_DIR="$SKILL_DIR/assets/outputs"
PROMPTS_DIR="$SKILL_DIR/references/prompts"

# Load shared libraries
source "$SCRIPT_DIR/lib/api-client.sh"
source "$SCRIPT_DIR/lib/cost-tracker.sh"

if [ "$LIVE" != "--live" ]; then
    echo "DRY RUN MODE: ./analyze.sh $TICKER_UPPER --live to execute"
    exit 0
fi

echo "======================================"
echo "  LIVE ANALYSIS: $TICKER_UPPER"
echo "======================================"

mkdir -p "$OUTPUTS_DIR"

# 1. Fetch Data
if [ ! -f "$SKILL_DIR/.cache/data/${TICKER_UPPER}_data.json" ]; then
    echo "📊 Fetching data..."
    "$SCRIPT_DIR/fetch_data.sh" "$TICKER_UPPER" > /dev/null 2>&1
fi

# 2. Run 8 Frameworks
echo "📋 Phase 1: Analyzing 8 Frameworks..."
ROLLING_CONTEXT_FILE="$OUTPUTS_DIR/${TICKER_UPPER}_rolling_context.txt"
# Clear from previous run
rm -f "$ROLLING_CONTEXT_FILE" 

export SUMMARY_CONTEXT="None"

for fw_id in 01-phase 02-metrics 03-ai-moat 04-strategic-moat 05-sentiment 06-growth 07-business 08-risk; do
    echo -n "  🔄 $fw_id... "
    "$SCRIPT_DIR/run-framework.sh" "$TICKER_UPPER" "$fw_id" "$PROMPTS_DIR/$fw_id.txt" "$OUTPUTS_DIR" > /dev/null
    
    # Update SUMMARY_CONTEXT for next framework (Tail -n 3 to keep it small)
    if [ -f "$ROLLING_CONTEXT_FILE" ]; then
        SUMMARY_CONTEXT=$(tail -n 3 "$ROLLING_CONTEXT_FILE")
        export SUMMARY_CONTEXT
    fi
    echo "✅"
done

# 3. Strategic Synthesis
echo ""
echo "🧠 Phase 2: Strategic Synthesis..."

# Aggregate all framework outputs
ALL_OUTPUTS=""
for fw_id in 01-phase 02-metrics 03-ai-moat 04-strategic-moat 05-sentiment 06-growth 07-business 08-risk; do
    FW_FILE="$OUTPUTS_DIR/${TICKER_UPPER}_${fw_id}.md"
    if [ -f "$FW_FILE" ]; then
        ALL_OUTPUTS="${ALL_OUTPUTS}### $fw_id ###\n$(cat "$FW_FILE")\n\n"
    fi
done

SYNTHESIS_PROMPT=$(cat "$PROMPTS_DIR/09-synthesis.txt" 2>/dev/null)
FULL_SYNTHESIS_PROMPT="$SYNTHESIS_PROMPT

=== 8 FRAMEWORK ANALYSES ===
$ALL_OUTPUTS"

# Call API for synthesis
RESPONSE=$(call_llm_api "$FULL_SYNTHESIS_PROMPT" 2000)
CONTENT=$(extract_content "$RESPONSE")
read INPUT_TOKENS OUTPUT_TOKENS <<< "$(extract_usage "$RESPONSE" "$FULL_SYNTHESIS_PROMPT")"

# Save results
echo "$CONTENT" > "$OUTPUTS_DIR/${TICKER_UPPER}_synthesis.md"
echo "$CONTENT" > "$OUTPUTS_DIR/${TICKER_UPPER}_FINAL_REPORT.md"

# Log synthesis cost
log_cost "$TICKER_UPPER" "09-synthesis" "$INPUT_TOKENS" "$OUTPUT_TOKENS"

echo ""
echo "======================================"
echo "  SYNTHESIS & VERDICT"
echo "======================================"
echo ""
echo "$CONTENT"
echo ""
echo "======================================"
echo "✅ ANALYSIS COMPLETE"
echo "======================================"
echo "Report: $OUTPUTS_DIR/${TICKER_UPPER}_FINAL_REPORT.md"
