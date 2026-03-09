#!/bin/bash
# Content Factory — Daily Pipeline (portable)
# Uses paths relative to skill directory

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$SKILL_DIR/scripts"
DATA="$SKILL_DIR/data"
LOG="$DATA/daily.log"

# Create data dirs
mkdir -p "$DATA"/{hotpool,topics,drafts,reviewed,published}

# Clear proxy to avoid SSL issues
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }
log "=== 内容工厂每日流程开始 ==="

# Step 1: 热点采集
log "Step 1: 热点采集..."
cd "$SCRIPTS/aggregator"
timeout 120 python3 fetch_all.py >> "$LOG" 2>&1 || log "⚠️ 热点采集超时或部分失败"
log "热点采集完成"

# Step 2: 选题评分
log "Step 2: 选题评分..."
sleep 5
cd "$SCRIPTS"
python3 topic_scorer.py >> "$LOG" 2>&1 || log "⚠️ 选题评分失败"
log "选题评分完成"

# Step 3: 推送选题给用户
log "Step 3: 推送选题..."
sleep 5
python3 topic_presenter.py >> "$LOG" 2>&1 || log "⚠️ 推送失败"
log "选题推送完成"

# Step 4: 内容生成 (Top 3)
log "Step 4: 内容生成 (Top 3)..."
sleep 5
python3 content_generator.py --top 3 >> "$LOG" 2>&1 || log "⚠️ 内容生成失败"
log "草稿生成完成"

# Step 5: 草稿审核
log "Step 5: 草稿审核..."
sleep 5
python3 draft_reviewer.py --all >> "$LOG" 2>&1 || log "⚠️ 草稿审核失败"
log "草稿审核推送完成"

log "=== 内容工厂每日流程结束 ==="
