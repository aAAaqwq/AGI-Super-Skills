#!/bin/bash
# 自动处理模型请求失败并切换的脚本
# 由 OpenClaw 在检测到模型错误时调用

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.openclaw/logs"
LOG_FILE="$LOG_DIR/auto-switch.log"
STATE_FILE="$LOG_DIR/switch-state.json"
FALLBACK_SCRIPT="$HOME/.openclaw/scripts/model-fallback.sh"

mkdir -p "$LOG_DIR"

# 日志函数
log() {
  local level=$1
  shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

# 解析命令行参数
ERROR_TYPE=""
ERROR_CODE=""
ERROR_MESSAGE=""
CURRENT_MODEL=""
RETRY_COUNT=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --error-type)
      ERROR_TYPE="$2"
      shift 2
      ;;
    --error-code)
      ERROR_CODE="$2"
      shift 2
      ;;
    --error-message)
      ERROR_MESSAGE="$2"
      shift 2
      ;;
    --current-model)
      CURRENT_MODEL="$2"
      shift 2
      ;;
    --retry-count)
      RETRY_COUNT="$2"
      shift 2
      ;;
    *)
      log ERROR "未知参数: $1"
      exit 1
      ;;
  esac
done

log INFO "=== 自动模型切换处理 ==="
log INFO "错误类型: $ERROR_TYPE"
log INFO "错误代码: $ERROR_CODE"
log INFO "错误消息: $ERROR_MESSAGE"
log INFO "当前模型: $CURRENT_MODEL"
log INFO "重试次数: $RETRY_COUNT"

# 读取当前状态
if [[ -f "$STATE_FILE" ]]; then
  CONSECUTIVE_FAILURES=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('consecutive_failures', 0))" 2>/dev/null || echo "0")
  LAST_SWITCH=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('last_switch', 0))" 2>/dev/null || echo "0")
else
  CONSECUTIVE_FAILURES=0
  LAST_SWITCH=0
fi

log INFO "连续失败次数: $CONSECUTIVE_FAILURES"

# 决策逻辑
SHOULD_SWITCH=false
SWITCH_REASON=""

case "$ERROR_TYPE" in
  "timeout")
    # 超时错误：重试2次后切换
    if [[ $RETRY_COUNT -ge 2 ]]; then
      SHOULD_SWITCH=true
      SWITCH_REASON="超时重试次数超限"
    fi
    ;;

  "rate_limit"|"429")
    # 速率限制：立即切换
    SHOULD_SWITCH=true
    SWITCH_REASON="API 速率限制"
    ;;

  "quota_exceeded"|"insufficient_quota")
    # 配额耗尽：立即切换并标记
    SHOULD_SWITCH=true
    SWITCH_REASON="配额耗尽"
    ;;

  "authentication"|"401"|"403")
    # 认证错误：立即切换并禁用
    SHOULD_SWITCH=true
    SWITCH_REASON="认证失败"
    ;;

  "service_unavailable"|"503"|"502")
    # 服务不可用：重试3次后切换
    if [[ $RETRY_COUNT -ge 3 ]]; then
      SHOULD_SWITCH=true
      SWITCH_REASON="服务不可用"
    fi
    ;;

  "network_error"|"connection_error")
    # 网络错误：检查连续失败次数
    if [[ $CONSECUTIVE_FAILURES -ge 3 ]]; then
      SHOULD_SWITCH=true
      SWITCH_REASON="网络连续失败"
    fi
    ;;

  *)
    # 其他错误：记录但不切换
    log WARN "未知错误类型，不触发切换"
    exit 0
    ;;
esac

# 冷却期检查（避免频繁切换）
NOW=$(date +%s)
TIME_SINCE_LAST_SWITCH=$((NOW - LAST_SWITCH))
COOLDOWN_PERIOD=300  # 5分钟

if [[ $TIME_SINCE_LAST_SWITCH -lt $COOLDOWN_PERIOD ]] && [[ $SHOULD_SWITCH == true ]]; then
  log WARN "切换冷却期中，距上次切换仅 ${TIME_SINCE_LAST_SWITCH} 秒（需要 ${COOLDOWN_PERIOD} 秒）"

  # 严重错误（认证、配额）不受冷却期限制
  if [[ "$ERROR_TYPE" != "authentication" ]] && [[ "$ERROR_TYPE" != "quota_exceeded" ]]; then
    SHOULD_SWITCH=false
    SWITCH_REASON="冷却期保护"
  fi
fi

# 执行切换
if [[ "$SHOULD_SWITCH" == true ]]; then
  log WARN "触发模型切换: $SWITCH_REASON"

  # 获取当前模型（如果未提供）
  if [[ -z "$CURRENT_MODEL" ]]; then
    CURRENT_MODEL=$(openclaw status 2>/dev/null | grep -oP 'Model\s+\K\S+' | head -1 || echo "unknown")
  fi

  log INFO "切换前模型: $CURRENT_MODEL"

  # 执行切换脚本
  if [[ -x "$FALLBACK_SCRIPT" ]]; then
    log INFO "运行降级切换脚本..."
    if $FALLBACK_SCRIPT >> "$LOG_FILE" 2>&1; then
      log INFO "✓ 切换成功"

      # 获取新模型
      NEW_MODEL=$(openclaw status 2>/dev/null | grep -oP 'Model\s+\K\S+' | head -1 || echo "unknown")
      log INFO "切换后模型: $NEW_MODEL"

      # 更新状态
      cat > "$STATE_FILE" << EOF
{
  "last_switch": $(date +%s),
  "last_switch_from": "$CURRENT_MODEL",
  "last_switch_to": "$NEW_MODEL",
  "switch_reason": "$SWITCH_REASON",
  "consecutive_failures": 0
}
EOF

      # 发送通知（如果配置了）
      if command -v notify-send &> /dev/null; then
        notify-send "OpenClaw 模型切换" "已从 $CURRENT_MODEL 切换到 $NEW_MODEL" 2>/dev/null || true
      fi

      exit 0
    else
      log ERROR "✗ 切换失败"
      # 增加失败计数
      cat > "$STATE_FILE" << EOF
{
  "last_switch": $LAST_SWITCH,
  "consecutive_failures": $((CONSECUTIVE_FAILURES + 1))
}
EOF
      exit 1
    fi
  else
    log ERROR "切换脚本不存在或不可执行: $FALLBACK_SCRIPT"
    exit 1
  fi
else
  log INFO "无需切换: $SWITCH_REASON"

  # 更新失败计数
  cat > "$STATE_FILE" << EOF
{
  "last_switch": $LAST_SWITCH,
  "consecutive_failures": $((CONSECUTIVE_FAILURES + 1))
}
EOF

  exit 0
fi
