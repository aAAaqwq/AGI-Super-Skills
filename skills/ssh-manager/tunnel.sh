#!/bin/bash
# SSH 端口转发隧道
# 使用：./tunnel.sh <主机名> <远程端口> [本地端口] [用户名]
# 示例：./tunnel.sh daniellimac-mini 11434 11434 danielli

set -e

HOST=$1
REMOTE_PORT=$2
LOCAL_PORT=${3:-$REMOTE_PORT}
USER=${4:-danielli}

if [ -z "$HOST" ] || [ -z "$REMOTE_PORT" ]; then
    echo "❌ 用法: $0 <主机名> <远程端口> [本地端口] [用户名]"
    echo ""
    echo "示例："
    echo "  $0 daniellimac-mini 11434           # 本地 11434 -> 远程 11434"
    echo "  $0 daniellimac-mini 11434 8080      # 本地 8080 -> 远程 11434"
    exit 1
fi

# 获取动态 IP
IP=$(tailscale status | grep "$HOST" | awk '{print $1}' | head -1)

if [ -z "$IP" ]; then
    echo "❌ 主机 '$HOST' 未找到或不在线"
    echo ""
    echo "在线主机："
    tailscale status | grep -v offline | awk '{printf "  %s (%s)\n", $2, $1}'
    exit 1
fi

# 检查本地端口是否被占用
if lsof -i :$LOCAL_PORT > /dev/null 2>&1; then
    echo "⚠️ 本地端口 $LOCAL_PORT 已被占用"
    lsof -i :$LOCAL_PORT | head -3
    echo ""
    read -p "是否继续？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🔗 建立隧道: localhost:$LOCAL_PORT -> $HOST($IP):$REMOTE_PORT"
echo "   用户: $USER"
echo ""
echo "按 Ctrl+C 关闭隧道"
echo ""

# 建立隧道
ssh -N -L $LOCAL_PORT:localhost:$REMOTE_PORT -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $USER@$IP
