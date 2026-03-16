#!/bin/bash
# team-memory-sync - 团队记忆同步工具
# Usage: ./sync.sh <command> [args]

set -e

AGENTS_DIR="$HOME/.openclaw/agents"
CLAWD_DIR="$HOME/clawd"
AGENTS="ops code quant content data finance research market pm law product sales"
TELEGRAM_GROUP="-1003890797239"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# sync-user: 同步 USER-TEMPLATE.md 到所有 agent
sync_user() {
    log_info "同步 USER-TEMPLATE.md 到所有 agent..."
    local count=0
    for agent in $AGENTS; do
        local target_dir="$AGENTS_DIR/$agent/agent"
        mkdir -p "$target_dir"
        cp "$AGENTS_DIR/USER-TEMPLATE.md" "$target_dir/USER.md"
        log_info "✓ $agent"
        ((count++))
    done
    log_info "完成！共同步 $count 个 agent"
}

# sync-charter: 检查 AGENTS.md 是否引用 CHARTER.md
sync_charter() {
    log_info "检查 AGENTS.md 宪章引用..."
    local missing=0
    for agent in $AGENTS; do
        local agents_md="$AGENTS_DIR/$agent/agent/AGENTS.md"
        if [[ -f "$agents_md" ]]; then
            if grep -q "CHARTER.md" "$agents_md"; then
                log_info "✓ $agent 已引用宪章"
            else
                log_warn "⚠ $agent 未引用宪章"
                ((missing++))
            fi
        else
            log_warn "⚠ $agent 没有 AGENTS.md"
            ((missing++))
        fi
    done
    if [[ $missing -eq 0 ]]; then
        log_info "所有 agent 都已正确引用宪章"
    else
        log_warn "$missing 个 agent 需要更新"
    fi
}

# audit: 发送认知审计请求到所有 agent
audit() {
    log_info "发送认知审计请求到所有 agent..."
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local message="【认知审计】$timestamp

请立即汇报以下内容（不超过 200 字）：
1. Daniel 的核心特质（3 个关键词）
2. 你的职责边界
3. 最近一次产出的价值

格式：
🎯 Daniel 认知：...
📋 我的职责：...
💡 最近产出：...

完成后在此群汇报。"

    # 使用 OpenClaw sessions_send API
    for agent in $AGENTS; do
        local session_key="agent:$agent:telegram:group:$TELEGRAM_GROUP"
        if command -v openclaw &> /dev/null; then
            openclaw sessions send "$session_key" "$message" 2>/dev/null && \
                log_info "✓ 已发送给 $agent" || \
                log_warn "⚠ 发送给 $agent 失败"
        else
            log_warn "openclaw CLI 不可用，跳过发送"
            echo "Session: $session_key"
            echo "Message: $message"
            echo "---"
        fi
    done
    log_info "审计请求已发送，等待 agent 汇报..."
}

# freshness: 检查记忆文件新鲜度
freshness() {
    log_info "检查 agent 记忆文件新鲜度..."
    echo ""
    printf "%-12s %-20s %-15s\n" "Agent" "文件" "最后修改"
    printf "%-12s %-20s %-15s\n" "------" "--------------------" "---------------"
    
    for agent in $AGENTS; do
        local agent_dir="$AGENTS_DIR/$agent/agent"
        
        # 检查 MEMORY.md
        if [[ -f "$agent_dir/MEMORY.md" ]]; then
            local mod_time=$(stat -c %y "$agent_dir/MEMORY.md" 2>/dev/null | cut -d'.' -f1)
            local days_ago=$(( ($(date +%s) - $(stat -c %Y "$agent_dir/MEMORY.md")) / 86400 ))
            local freshness="${days_ago}天前"
            printf "%-12s %-20s %-15s\n" "$agent" "MEMORY.md" "$freshness"
        else
            printf "%-12s %-20s %-15s\n" "$agent" "MEMORY.md" "❌ 不存在"
        fi
        
        # 检查 USER.md
        if [[ -f "$agent_dir/USER.md" ]]; then
            local mod_time=$(stat -c %y "$agent_dir/USER.md" 2>/dev/null | cut -d'.' -f1)
            local days_ago=$(( ($(date +%s) - $(stat -c %Y "$agent_dir/USER.md")) / 86400 ))
            local freshness="${days_ago}天前"
            printf "%-12s %-20s %-15s\n" "" "USER.md" "$freshness"
        fi
    done
}

# broadcast: 向所有 agent 广播消息
broadcast() {
    local message="$1"
    if [[ -z "$message" ]]; then
        log_error "请提供广播消息内容"
        exit 1
    fi
    
    log_info "广播消息到所有 agent..."
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local full_message="📢 【团队广播】$timestamp

$message

— 小a (CEO)"
    
    for agent in $AGENTS; do
        local session_key="agent:$agent:telegram:group:$TELEGRAM_GROUP"
        if command -v openclaw &> /dev/null; then
            openclaw sessions send "$session_key" "$full_message" 2>/dev/null && \
                log_info "✓ 已发送给 $agent" || \
                log_warn "⚠ 发送给 $agent 失败"
        else
            log_warn "openclaw CLI 不可用"
            echo "Would send to $session_key:"
            echo "$full_message"
            echo "---"
        fi
    done
    log_info "广播完成"
}

# 帮助信息
show_help() {
    cat << EOF
team-memory-sync - 团队记忆同步工具

Usage: $0 <command> [args]

Commands:
  sync-user       同步 USER-TEMPLATE.md 到所有 agent
  sync-charter    检查 AGENTS.md 宪章引用
  audit           发送认知审计请求
  freshness       检查记忆文件新鲜度
  broadcast <msg> 广播消息到所有 agent

Examples:
  $0 sync-user
  $0 audit
  $0 broadcast "明天 10:00 全员会议"

EOF
}

# 主入口
case "${1:-}" in
    sync-user)
        sync_user
        ;;
    sync-charter)
        sync_charter
        ;;
    audit)
        audit
        ;;
    freshness)
        freshness
        ;;
    broadcast)
        broadcast "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: ${1:-}"
        show_help
        exit 1
        ;;
esac
