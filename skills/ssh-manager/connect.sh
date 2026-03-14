#!/bin/bash
# SSH 智能连接脚本
# 使用：./connect.sh <主机名> <用户名> [命令]
# 示例：./connect.sh daniellimac-mini danielli "ollama list"

set -e

HOST=$1
USER=${2:-danielli}
CMD=$3

if [ -z "$HOST" ]; then
    echo "❌ 用法: $0 <主机名> [用户名] [命令]"
    echo ""
    echo "已知主机："
    tailscale status | grep -E "mac-mini|ubuntu" | awk '{printf "  %s (%s)\n", $2, $1}'
    exit 1
fi

# 获取动态 IP
STATUS_LINE=$(tailscale status | grep "$HOST" | head -1)
IP=$(echo "$STATUS_LINE" | awk '{print $1}')

if [ -z "$IP" ]; then
    echo "❌ 主机 '$HOST' 未找到"
    echo ""
    echo "可用主机："
    tailscale status | grep -E "online|active" | awk '{printf "  %s (%s) - %s\n", $2, $1, $NF}'
    exit 1
fi

# 检查是否在线
STATUS=$(echo "$STATUS_LINE" | awk '{print $NF}')
if [[ "$STATUS" == "offline"* ]]; then
    echo "⚠️ 主机 $HOST 当前离线 ($STATUS)"
    echo ""
    echo "在线主机："
    tailscale status | grep -v offline | awk '{printf "  %s (%s)\n", $2, $1}'
    exit 1
fi

echo "🔗 连接 $HOST ($IP) 用户: $USER"

if [ -z "$CMD" ]; then
    # 交互式 SSH
    exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 $USER@$IP
else
    # 执行命令
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 $USER@$IP "$CMD"
fi
