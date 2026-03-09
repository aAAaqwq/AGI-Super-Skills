#!/bin/bash
# Content Factory - Portable daily pipeline
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$SKILL_DIR/scripts"
DATA="$SKILL_DIR/data"
LOG="$DATA/daily.log"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }
log "=== Content Factory Daily Pipeline ==="

log "Step 1: Fetching hot topics..."
cd "$SCRIPTS/aggregator" && timeout 120 python3 fetch_all.py >> "$LOG" 2>&1 || log "⚠️ Fetch error"

log "Step 2: Scoring topics..."
cd "$SCRIPTS" && python3 topic_scorer.py >> "$LOG" 2>&1 || log "⚠️ Scorer error"

log "Step 3: Presenting topics..."
python3 topic_presenter.py >> "$LOG" 2>&1 || log "⚠️ Presenter error"

log "Step 4: Generating content (Top 3)..."
python3 content_generator.py --top 3 >> "$LOG" 2>&1 || log "⚠️ Generator error"

log "Step 5: Reviewing drafts..."
python3 draft_reviewer.py --all >> "$LOG" 2>&1 || log "⚠️ Reviewer error"

log "=== Pipeline Complete ==="
