#!/bin/bash
# run-single-step.sh - Run one framework step (e.g. 01-phase only). No --live flag.
# Use this when you want a single prompt (e.g. 01-phase) without the full pipeline or synthesis.
#
# Usage: run-single-step.sh <TICKER> <FW_ID>
# Example: run-single-step.sh KVYO 01-phase

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
PROMPTS_DIR="$SKILL_DIR/references/prompts"
OUTPUTS_DIR="$SKILL_DIR/assets/outputs"

TICKER="${1:-}"
FW_ID="${2:-}"

if [[ -z "$TICKER" || -z "$FW_ID" ]]; then
    echo "Usage: run-single-step.sh <TICKER> <FW_ID>" >&2
    echo "Example: run-single-step.sh KVYO 01-phase" >&2
    exit 1
fi

PROMPT_FILE="$PROMPTS_DIR/${FW_ID}.txt"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
fi

exec "$SCRIPT_DIR/run-framework.sh" "$(echo "$TICKER" | tr '[:lower:]' '[:upper:]')" "$FW_ID" "$PROMPT_FILE" "$OUTPUTS_DIR"
