#!/bin/bash
# 模型请求包装器 - 捕获错误并自动处理
# 用法: model-error-wrapper.sh --command "your-openclaw-command" --max-retries 3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_SWITCH_HANDLER="$SCRIPT_DIR/auto-switch-handler.sh"
LOG_DIR="$HOME/.openclaw/logs"
mkdir -p "$LOG_DIR"

# 默认参数
COMMAND=""
MAX_RETRIES=3
RETRY_DELAY=2
TIMEOUT=60
LOG_FILE="$LOG_DIR/wrapper.log"

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --max-retries)
      MAX_RETRIES="$2"
      shift 2
      ;;
    --retry-delay)
      RETRY_DELAY="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --log-file)
      LOG_FILE="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      exit 1
      ;;
  esac
done

# 日志函数
log() {
  local level=$1
  shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

# 执行命令并捕获错误
execute_with_retry() {
  local attempt=1
  local current_model=$(openclaw status 2>/dev/null | grep -oP 'Model\s+\K\S+' | head -1 || echo "unknown")

  while [[ $attempt -le $MAX_RETRIES ]]; do
    log INFO "执行命令 (尝试 $attempt/$MAX_RETRIES)..."
    log DEBUG "当前模型: $current_model"

    # 使用 timeout 命令执行
    if timeout $TIMEOUT bash -c "$COMMAND" 2>&1 | tee -a "$LOG_FILE"; then
      log INFO "✓ 命令执行成功"
      return 0
    else
      local exit_code=$?

      # 分析错误类型
      local error_type=""
      local error_code=""

      case $exit_code in
        124)  # timeout 退出码
          error_type="timeout"
          error_code="408"
          log WARN "请求超时 (超过 ${TIMEOUT}秒)"
          ;;
        28)   # curl 超时
          error_type="timeout"
          error_code="408"
          log WARN "网络超时"
          ;;
        7 | 35 | 52)  # curl 网络错误
          error_type="network_error"
          error_code="503"
          log WARN "网络连接失败"
          ;;
        *)
          # 检查错误输出
          error_output=$(tail -20 "$LOG_FILE")
          if echo "$error_output" | grep -qi "rate limit\|429\|too many requests"; then
            error_type="rate_limit"
            error_code="429"
            log WARN "API 速率限制"
          elif echo "$error_output" | grep -qi "quota\|insufficient\|credit"; then
            error_type="quota_exceeded"
            error_code="402"
            log WARN "配额耗尽"
          elif echo "$error_output" | grep -qi "auth\|401\|403\|unauthorized"; then
            error_type="authentication"
            error_code="401"
            log WARN "认证失败"
          elif echo "$error_output" | grep -qi "502\|503\|504\|service unavailable"; then
            error_type="service_unavailable"
            error_code="503"
            log WARN "服务不可用"
          else
            error_type="unknown"
            error_code="$exit_code"
            log WARN "未知错误 (退出码: $exit_code)"
          fi
          ;;
      esac

      # 调用自动切换处理脚本
      if [[ -x "$AUTO_SWITCH_HANDLER" ]]; then
        log INFO "调用自动切换处理..."
        $AUTO_SWITCH_HANDLER \
          --error-type "$error_type" \
          --error-code "$error_code" \
          --error-message "$(tail -1 "$LOG_FILE")" \
          --current-model "$current_model" \
          --retry-count "$attempt" || true
      fi

      # 如果是最后一次尝试，返回失败
      if [[ $attempt -eq $MAX_RETRIES ]]; then
        log ERROR "达到最大重试次数 ($MAX_RETRIES)，放弃"
        return 1
      fi

      # 等待后重试
      local wait_time=$((RETRY_DELAY * attempt))
      log INFO "等待 ${wait_time} 秒后重试..."
      sleep $wait_time

      # 更新当前模型（可能已经切换）
      current_model=$(openclaw status 2>/dev/null | grep -oP 'Model\s+\K\S+' | head -1 || echo "unknown")
      ((attempt++))
    fi
  done

  return 1
}

# 主函数
main() {
  if [[ -z "$COMMAND" ]]; then
    log ERROR "未指定命令，使用 --command 参数"
    exit 1
  fi

  log INFO "=== 模型请求包装器 ==="
  log INFO "命令: $COMMAND"
  log INFO "最大重试: $MAX_RETRIES"
  log INFO "超时设置: ${TIMEOUT}秒"

  execute_with_retry
  exit $?
}

# 如果直接运行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
