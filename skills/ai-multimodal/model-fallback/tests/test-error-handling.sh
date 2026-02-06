#!/bin/bash
# 模拟各种模型错误并测试自动切换

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_SWITCH_HANDLER="$HOME/clawd/skills/model-fallback/scripts/auto-switch-handler.sh"
LOG_DIR="$HOME/.openclaw/logs"
mkdir -p "$LOG_DIR"

echo "========================================="
echo "  模型错误处理测试"
echo "========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 测试用例
test_cases=(
  "timeout:超时错误"
  "rate_limit:速率限制"
  "quota_exceeded:配额耗尽"
  "authentication:认证失败"
  "service_unavailable:服务不可用"
  "network_error:网络错误"
)

for test_case in "${test_cases[@]}"; do
  IFS=':' read -r error_type description <<< "$test_case"

  echo -e "${YELLOW}测试: $description ($error_type)${NC}"

  # 模拟不同重试次数
  for retry_count in 1 2 3; do
    echo "  重试次数: $retry_count"

    # 调用自动切换处理脚本
    if $AUTO_SWITCH_HANDLER \
      --error-type "$error_type" \
      --error-code "500" \
      --error-message "模拟错误: $description" \
      --current-model "test-model" \
      --retry-count "$retry_count" 2>&1 | tee -a "$LOG_DIR/test-error.log"; then
      echo -e "    ${GREEN}✓${NC} 处理成功"
    else
      echo -e "    ${RED}✗${NC} 处理失败"
    fi

    sleep 1
  done

  echo ""
done

echo "========================================="
echo "  测试完成"
echo "========================================="
echo ""
echo "查看日志:"
echo "  cat $LOG_DIR/test-error.log"
echo "  cat $LOG_DIR/auto-switch.log"
echo ""
