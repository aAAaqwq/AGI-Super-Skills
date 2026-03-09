#!/bin/bash
# run-framework.sh - Momentum-Aware Context Hand-off
# Updated to support enriched JSON and sequential inference.

set -euo pipefail

# 1. Environment Setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/lib/cache.sh"
source "$SCRIPT_DIR/lib/cost-tracker.sh"
source "$SCRIPT_DIR/lib/api-client.sh"
source "$SCRIPT_DIR/lib/trace.sh"

# 2. Argument Parsing & Defaults
TICKER="${1:-}"
FW_ID="${2:-}"
PROMPT_FILE="${3:-}"
OUTPUT_DIR="${4:-$SKILL_DIR/assets/outputs}"
# No output token limit: use high default (8192) so API does not truncate; cost is low per costs.log
LIMIT_ARG="${5:-8192}"

# Usage guard: this script does NOT take --live (that flag is for analyze-pipeline.sh only)
if [[ -z "$PROMPT_FILE" || "$PROMPT_FILE" == -* ]]; then
    echo "Usage: run-framework.sh <TICKER> <FW_ID> <PROMPT_FILE> [OUTPUT_DIR] [LIMIT]" >&2
    echo "  Example (01-phase only): run-framework.sh KVYO 01-phase \"$SKILL_DIR/references/prompts/01-phase.txt\" \"$SKILL_DIR/assets/outputs\"" >&2
    echo "  Note: Do not pass --live. Use analyze-pipeline.sh <TICKER> --live for the full pipeline." >&2
    exit 1
fi
[ ! -f "$PROMPT_FILE" ] && { echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2; exit 1; }

# Inherit context from analyze-pipeline.sh
PREVIOUS_CONTEXT="${SUMMARY_CONTEXT:-None}"

# Single high cap so output is not truncated; per-framework limits removed (costs are low)
FW_MAX_TOKENS="${LIMIT_ARG:-8192}"

# 3. Data Segmenting (Surgical Injection)
TICKER_UPPER=$(echo "$TICKER" | tr '[:lower:]' '[:upper:]')
DATA_FILE="$SKILL_DIR/.cache/data/${TICKER_UPPER}_data.json"

# Log start immediately so trace shows which step ran (and which step failed before first API log)
init_trace
log_trace "INFO" "$FW_ID" "Starting..."

# Require data file so we never pass empty context (avoids "N/A / Insufficient data" when wrong ticker is used)
if [ ! -f "$DATA_FILE" ]; then
    log_trace "ERROR" "$FW_ID" "Data file not found: $DATA_FILE"
    echo "ERROR: No data for $TICKER_UPPER. Expected: $DATA_FILE" >&2
    echo "  If analyzing Klaviyo, use ticker KVYO (not KYVO). Run fetch_data.sh first." >&2
    exit 1
fi

get_relevant_context() {
    case "$FW_ID" in
        "07-business")
            # Inject profile and financial metrics for business evaluation
            jq -c '{profile: .company_profile, metrics: .financial_metrics, valuation: .valuation}' "$DATA_FILE" ;;
        "03-ai-moat") 
            # Inject ROE, valuation, and Earnings Surprises for Moat inference
            jq -c '{momentum: .momentum, valuation: .valuation, description: .company_profile.description}' "$DATA_FILE" ;;
        "08-risk") 
            # Inject valuation and momentum for Risk analysis
            jq -c '{valuation: .valuation, momentum: .momentum, profile: .company_profile}' "$DATA_FILE" ;;
        "01-phase")
            # Enriched context for lifecycle phase: profile + financial_metrics + valuation + momentum from *_data.json
            jq -c '{profile: .company_profile, metrics: .financial_metrics, valuation: .valuation, momentum: .momentum}' "$DATA_FILE" ;;
        "02-metrics") 
            # Core financial metrics
            jq -c '{metrics: .financial_metrics, valuation: .valuation}' "$DATA_FILE" ;;
        *) 
            # Default to description and basic profile
            jq -c '{profile: .company_profile, valuation: .valuation}' "$DATA_FILE" ;;
        esac
}

# Refuse to run with empty or stub data (e.g. all N/A) so we don't get "Insufficient data" output
check_context_not_empty() {
    local ctx="$1"
    if [ -z "$ctx" ] || [ "$ctx" = "{}" ]; then
        log_trace "ERROR" "$FW_ID" "Context is empty after loading $DATA_FILE"
        exit 1
    fi
    # For phase and metrics steps, require real financial data (revenue not N/A)
    if [[ "$FW_ID" == "01-phase" || "$FW_ID" == "02-metrics" ]]; then
        if echo "$ctx" | jq -e '(.metrics.revenue // "N/A") == "N/A"' >/dev/null 2>&1; then
            log_trace "ERROR" "$FW_ID" "No financial metrics in data file (revenue N/A). Fetch data for $TICKER_UPPER first."
            echo "ERROR: $DATA_FILE has no financial data (revenue N/A). Run fetch_data.sh for $TICKER_UPPER." >&2
            echo "  Check ticker: Klaviyo is KVYO, not KYVO." >&2
            exit 1
        fi
    fi
}

# 4. Initialization & Cache Check
mkdir -p "$OUTPUT_DIR"
CONTEXT=$(get_relevant_context) || {
    log_trace "ERROR" "$FW_ID" "get_relevant_context failed (jq or data file)"
    echo "ERROR: Failed to load context from $DATA_FILE for $FW_ID." >&2
    exit 1
}
check_context_not_empty "$CONTEXT"
PROMPT_CONTENT=$(cat "$PROMPT_FILE")

# When running 02-metrics alone, inject phase from 01-phase output so the correct metric set is used
if [[ "$FW_ID" == "02-metrics" && ( -z "$PREVIOUS_CONTEXT" || "$PREVIOUS_CONTEXT" == "None" ) ]]; then
    PHASE_FILE="$OUTPUT_DIR/${TICKER_UPPER}_01-phase.md"
    if [[ -f "$PHASE_FILE" ]]; then
        PREVIOUS_CONTEXT="Phase from 01-phase (use this to select which of the 5 metric sets and thresholds to apply): $(head -n 10 "$PHASE_FILE" | tr '\n' ' ' | sed 's/  */ /g')"
    else
        log_trace "ERROR" "02-metrics" "01-phase output not found; 02-metrics requires phase from 01-phase"
        echo "ERROR: 02-metrics needs the phase from 01-phase. Run 01-phase first, then 02-metrics." >&2
        echo "  Example: run-single-step.sh $TICKER_UPPER 01-phase && run-single-step.sh $TICKER_UPPER 02-metrics" >&2
        echo "  Expected file: $PHASE_FILE" >&2
        exit 1
    fi
fi

# The Context Bridge: Combine the raw data + previous framework results
FULL_PROMPT="Company: $TICKER_UPPER
Analysis Context from Previous Steps: $PREVIOUS_CONTEXT

Raw Data:
$CONTEXT

Task Instructions:
$PROMPT_CONTENT"

# Include output token limit in cache key so increasing the limit yields a fresh (non-truncated) response
CACHE_KEY=$(cache_key "$TICKER_UPPER" "$FW_ID" "$FULL_PROMPT")"_max${FW_MAX_TOKENS}"

# Helper: append one line to rolling context (used on both cache hit and fresh response)
append_to_rolling_context() {
    local outfile="$1"
    ROLLING_FILE="$OUTPUT_DIR/${TICKER_UPPER}_rolling_context.txt"
    get_golden_nugget() {
        local f="$1"
        case "$FW_ID" in
            01-phase)  grep -A1 "^PHASE:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            02-metrics) grep -A1 "^SUMMARY:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            03-ai-moat) grep -A1 "^VERDICT:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            04-strategic-moat) grep -A1 "^RATING:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            05-sentiment) grep -A1 "^VALUATION:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            06-growth) grep -A1 "^STRATEGY:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            07-business) grep -A1 "^REVENUE MIX:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            08-risk) grep -A1 "^OVERALL RISK LEVEL:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
            *) grep -A1 "^VERDICT:\|^RATING:\|^SUMMARY:" "$f" 2>/dev/null | tail -n 1 | sed 's/^[[:space:]]*//' | head -c 120 ;;
        esac
    }
    GOLDEN_NUGGET=$(get_golden_nugget "$outfile")
    [ -z "$GOLDEN_NUGGET" ] && GOLDEN_NUGGET=$(grep -v -E '^[A-Z][A-Z_]*:$' "$outfile" 2>/dev/null | head -n 1 | sed 's/^[[:space:]]*//' | head -c 120)
    [ -z "$GOLDEN_NUGGET" ] && GOLDEN_NUGGET="(no summary extracted)"
    echo "$FW_ID: $GOLDEN_NUGGET" >> "$ROLLING_FILE"
}

# 5. Output validation (detect truncation by required end-marker per framework)
validate_framework_output() {
    local content="$1"
    local marker=""
    case "$FW_ID" in
        01-phase)  marker="Avoid:" ;;
        02-metrics) marker="SUMMARY:" ;;
        03-ai-moat) marker="CRITICAL FAILURE POINT:" ;;
        04-strategic-moat) marker="THREAT:" ;;
        05-sentiment) marker="RATIONALE:" ;;
        06-growth)   marker="ANALYSIS:" ;;
        07-business) marker="SCALABILITY:" ;;
        08-risk)    marker="ASSESSMENT DETAILS:" ;;
        *) return 0 ;;
    esac
    [ -z "$marker" ] && return 0
    if echo "$content" | grep -qF "$marker"; then
        return 0
    fi
    log_trace "WARN" "$FW_ID" "Output missing required end-marker: $marker (possible truncation)"
    return 1
}

# 6. Cache & Budget Enforcement
CACHED_RESPONSE=$(cache_get "$CACHE_KEY" || echo "")
if [ -n "$CACHED_RESPONSE" ]; then
    if validate_framework_output "$CACHED_RESPONSE"; then
        echo "$CACHED_RESPONSE" > "$OUTPUT_DIR/${TICKER_UPPER}_${FW_ID}.md"
        log_trace "INFO" "$FW_ID" "Cache HIT"
        append_to_rolling_context "$OUTPUT_DIR/${TICKER_UPPER}_${FW_ID}.md"
        echo "$CACHED_RESPONSE"
        exit 0
    fi
    log_trace "WARN" "$FW_ID" "Cached response truncated; bypassing cache and calling API"
fi

if ! check_budget "$FW_ID"; then
    log_trace "ERROR" "$FW_ID" "Budget check failed"
    exit 1
fi

# 7. API Execution (no output token cap; FW_MAX_TOKENS=8192 so API does not truncate)
API_RESPONSE=$(call_llm_api "$FULL_PROMPT" "$FW_MAX_TOKENS")
CONTENT=$(extract_content "$API_RESPONSE")
read INPUT_TOKENS OUTPUT_TOKENS <<< "$(extract_usage "$API_RESPONSE" "$FULL_PROMPT")"

if ! validate_framework_output "$CONTENT"; then
    read -r finish_reason out_tokens max_tokens <<< "$(extract_finish_info "$API_RESPONSE" "$FW_MAX_TOKENS" 2>/dev/null || echo "? ? ?")"
    log_trace "TRUNC" "$FW_ID" "finishReason=$finish_reason outTokens=$out_tokens limit=$max_tokens"
    echo "⚠️  $FW_ID output incomplete (finishReason=$finish_reason, ${out_tokens} tokens). Re-run step; response not cached." >&2
    echo "$CONTENT" > "$OUTPUT_DIR/${TICKER_UPPER}_${FW_ID}.md"
    exit 1
fi

# 8. Final Save & Metadata
echo "$CONTENT" > "$OUTPUT_DIR/${TICKER_UPPER}_${FW_ID}.md"
log_cost "$TICKER_UPPER" "$FW_ID" "$INPUT_TOKENS" "$OUTPUT_TOKENS"
log_trace "INFO" "$FW_ID" "Complete | ${INPUT_TOKENS}i/${OUTPUT_TOKENS}o"

# 9. Golden Nugget Extraction
append_to_rolling_context "$OUTPUT_DIR/${TICKER_UPPER}_${FW_ID}.md"

# Cache only if output passed validation (do not cache truncated responses)
METADATA=$(jq -n --arg i "$INPUT_TOKENS" --arg o "$OUTPUT_TOKENS" '{input: $i, output: $o}')
cache_set "$CACHE_KEY" "$CONTENT" "$METADATA"
echo "✅ $FW_ID complete"