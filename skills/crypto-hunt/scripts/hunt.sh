#!/bin/bash
# hunt.sh — Master hunt pipeline: scan → trend → decide → execute
# Usage: hunt.sh [--dry-run] [--skip-trade]
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$SKILL_DIR/scripts"
DATA="$SKILL_DIR/data"

DRY_RUN=false
SKIP_TRADE=false
for arg in "$@"; do
    case "$arg" in
        --dry-run)     DRY_RUN=true ;;
        --skip-trade)  SKIP_TRADE=true ;;
    esac
done

mkdir -p "$DATA"
log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Step 1: Scan markets
log "Step 1/4: Scanning markets..."
if ! python3 "$SCRIPTS/scan_markets.py"; then
    log "⚠️  Scanner found no actionable markets. Exiting."
    exit 0
fi

# Step 2: Fetch trend data
log "Step 2/4: Fetching trend data..."
python3 "$SCRIPTS/trend_data.py" || {
    log "⚠️  Trend data fetch failed, continuing with stale data."
}

# Step 3: Analyze trends
log "Step 3/4: Analyzing trends..."
python3 "$SCRIPTS/trend_analysis.py" || {
    log "⚠️  Trend analysis failed, continuing with stale data."
}

# Step 4: Run decision engine
log "Step 4/4: Running decision engine..."
python3 "$SCRIPTS/decision_engine.py" || {
    log "❌ Decision engine failed."
    exit 1
}

# Step 5: Execute trades (unless skipped)
if $SKIP_TRADE; then
    log "Trade execution skipped (--skip-trade)."
    exit 0
fi

if $DRY_RUN; then
    log "Dry run — would execute trades."
    python3 "$SCRIPTS/trade.py" execute --dry-run
else
    log "Executing trades..."
    python3 "$SCRIPTS/trade.py" execute
fi
