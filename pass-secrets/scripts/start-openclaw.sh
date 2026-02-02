#!/bin/bash
# 从 Pass 加载密钥并启动 OpenClaw Gateway
# 用法: ./start-openclaw.sh

set -e

echo "🔐 从 Pass 加载密钥..."

# 加载 API 密钥
export ZAI_API_KEY=$(pass api/zai 2>/dev/null)
export OPENROUTER_VIP_API_KEY=$(pass api/openrouter-vip 2>/dev/null)

# 验证
if [ -z "$ZAI_API_KEY" ]; then
    echo "⚠️ 警告: ZAI_API_KEY 未加载"
fi

if [ -z "$OPENROUTER_VIP_API_KEY" ]; then
    echo "⚠️ 警告: OPENROUTER_VIP_API_KEY 未加载"
fi

echo "✅ 密钥已加载"
echo ""
echo "🦞 启动 OpenClaw Gateway..."

exec openclaw gateway "$@"
