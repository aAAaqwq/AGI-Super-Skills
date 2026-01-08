#!/bin/bash
# Feishu MCP Setup Script
# 用法: ./feishu-mcp-setup.sh <app_id> <app_secret>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_SCRIPT="$SCRIPT_DIR/feishu-mcp-setup.js"

# 检查 Node.js 是否可用
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 需要安装 Node.js"
    echo "请访问 https://nodejs.org/ 安装 Node.js"
    exit 1
fi

# 检查是否提供了凭证
if [ $# -lt 2 ]; then
    echo "🔧 飞书 MCP 配置工具"
    echo "========================"
    echo ""
    echo "用法: $0 <app_id> <app_secret>"
    echo ""
    echo "参数:"
    echo "  app_id      飞书应用的 App ID"
    echo "  app_secret  飞书应用的 App Secret"
    echo ""
    echo "示例:"
    echo "  $0 cli_a1b2c3d4e5f6 app_secret_xxx"
    echo ""
    echo "💡 提示: 您也可以直接运行 Node.js 脚本进行交互式配置:"
    echo "   node $NODE_SCRIPT"
    exit 1
fi

APP_ID="$1"
APP_SECRET="$2"

echo "🔧 配置飞书 MCP..."
echo "App ID: $APP_ID"
echo ""

# 运行 Node.js 配置脚本
node "$NODE_SCRIPT" "$APP_ID" "$APP_SECRET"
