#!/bin/bash
#
# analyze-pipeline.sh - Momentum-Aware Analysis Pipeline
# Uses OpenClaw-configured LLM and enriched JSON datasets.
#

set -euo pipefail

# 1. Path Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUTS_DIR="$SKILL_DIR/assets/outputs"
PROMPTS_DIR="$SKILL_DIR/references/prompts"

# Source libraries (cache.sh sets CACHE_DIR to $SKILL_DIR/.cache/llm-responses)
source "$SCRIPT_DIR/lib/cache.sh"
source "$SCRIPT_DIR/lib/cost-tracker.sh"
source "$SCRIPT_DIR/lib/api-client.sh"
source "$SCRIPT_DIR/lib/trace.sh"

# 2. Parse arguments
TICKER="${1:-}"
LIVE="${2:-}"

[ -z "$TICKER" ] && { echo "Usage: $0 <TICKER> [--live]"; exit 1; }
TICKER_UPPER=$(echo "$TICKER" | tr '[:lower:]' '[:upper:]')

# 3. Refined Sequence: Metrics & Business run BEFORE Moat
FW_SEQUENCE=("01-phase" "02-metrics" "07-business" "03-ai-moat" "04-strategic-moat" "06-growth" "05-sentiment" "08-risk")

# 4. Initialize
init_trace
init_cost_tracker
mkdir -p "$OUTPUTS_DIR" "$CACHE_DIR"

if [ "$LIVE" != "--live" ]; then
    echo "🔍 DRY RUN: $TICKER_UPPER Pipeline (8 steps)"
    echo "   Sequence: ${FW_SEQUENCE[*]}"
    exit 0
fi

# ============================================
# Phase 1: Sequential Execution
# ============================================
echo "🚀 Starting Momentum Pipeline for $TICKER_UPPER..."
echo "---------------------------------------------------------"

START_TIME=$(date +%s)
export SUMMARY_CONTEXT="" # Export so run-framework.sh can read it

# Reset rolling context for this ticker so each run has a fresh hand-off (no duplicate/leftover lines)
ROLLING_FILE="$OUTPUTS_DIR/${TICKER_UPPER}_rolling_context.txt"
rm -f "$ROLLING_FILE"

FAILED_STEPS=()
for fw_id in "${FW_SEQUENCE[@]}"; do
    PROMPT_FILE="$PROMPTS_DIR/$fw_id.txt"
    
    echo "⏳ Step: $fw_id..."
    
    if ! "$SCRIPT_DIR/run-framework.sh" "$TICKER_UPPER" "$fw_id" "$PROMPT_FILE" "$OUTPUTS_DIR"; then
        echo "❌ $fw_id failed (see error above). Continuing with remaining steps..."
        FAILED_STEPS+=("$fw_id")
        # Keep SUMMARY_CONTEXT from last successful step for subsequent steps
        sleep 10
    else
        # Update Context Hand-off
        FW_OUT="$OUTPUTS_DIR/${TICKER_UPPER}_${fw_id}.md"
        SUMMARY_LINE=$(head -n 5 "$FW_OUT" | tr '\n' ' ' | sed 's/[#*]//g')
        SUMMARY_CONTEXT="- Previous Step ($fw_id): $SUMMARY_LINE"
        echo "  ✅ Done. Cooling down TPM window (45s to avoid 1M TPM spike)..."
        sleep 45
    fi
done

# ============================================
# Phase 2: Local Report Concatenation
# ============================================
echo "🧪 Compiling Final Research Dossier..."
SYNTH_FILE="$OUTPUTS_DIR/${TICKER_UPPER}_FINAL_REPORT.md"

{
    echo "# Strategic Research Dossier: $TICKER_UPPER"
    echo "Analysis Date: $(date)"
    echo "Model: $(jq -r '.agents.defaults.model.primary // "LLM"' "${CONFIG_FILE:-$HOME/.openclaw/openclaw.json}" 2>/dev/null | awk -F'/' '{print $NF}' || echo "LLM")"
    echo "---"
    for fw_id in "${FW_SEQUENCE[@]}"; do
        FW_FILE="$OUTPUTS_DIR/${TICKER_UPPER}_${fw_id}.md"
        if [ -f "$FW_FILE" ]; then
            HEADER=$(echo "$fw_id" | cut -d'-' -f2- | tr '[:lower:]' '[:upper:]')
            echo "## $HEADER"
            cat "$FW_FILE"
            echo -e "\n---\n"
        fi
    done
} > "$SYNTH_FILE"

echo "✅ Dossier saved to $SYNTH_FILE"

if [ ${#FAILED_STEPS[@]} -gt 0 ]; then
    echo ""
    echo "⚠️ Pipeline had ${#FAILED_STEPS[@]} failed step(s): ${FAILED_STEPS[*]}"
    echo "   Partial report includes successful steps only. Common cause: API 503 (Service Unavailable). Re-run later."
    exit 1
fi