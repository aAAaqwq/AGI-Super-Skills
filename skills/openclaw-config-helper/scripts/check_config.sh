#!/bin/bash
# OpenClaw 配置检查脚本
# 用法: ./check_config.sh <config_path>
# 示例: ./check_config.sh channels.telegram.groupAllowFrom

set -e

CONFIG_PATH="${1:-}"

if [ -z "$CONFIG_PATH" ]; then
    echo "用法: $0 <config_path>"
    echo "示例: $0 channels.telegram.groupAllowFrom"
    exit 1
fi

echo "=== 检查配置路径: $CONFIG_PATH ==="
echo ""

# 1. 获取 schema
echo "1. 获取 schema..."
echo "   运行: gateway action=config.schema"
echo ""

# 2. 获取当前值
echo "2. 获取当前配置值..."
CURRENT=$(jq -r ".$CONFIG_PATH" ~/.openclaw/openclaw.json 2>/dev/null || echo "路径不存在")
echo "   当前值: $CURRENT"
echo ""

# 3. 提醒查阅文档
echo "3. ⚠️  修改前请先查阅官方文档:"
echo "   - https://docs.openclaw.ai/gateway/configuration-reference"
echo "   - https://docs.openclaw.ai/channels/telegram"
echo "   - https://docs.openclaw.ai/channels/whatsapp"
echo ""

# 4. 常见错误提醒
echo "4. 常见配置错误提醒:"
echo "   - groupAllowFrom 应填用户 ID，不是群 ID"
echo "   - allowFrom 应填用户 ID"
echo "   - groups 的 key 是群 ID"
echo "   - bindings 需要包含 default → main"
echo ""

echo "✅ 检查完成，请确认配置正确后再修改！"
