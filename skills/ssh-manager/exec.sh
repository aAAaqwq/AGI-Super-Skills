#!/bin/bash
# 快速远程命令执行
# 使用：./exec.sh <主机名> <命令>
# 示例：./exec.sh daniellimac-mini "ollama list"
#       ./exec.sh daniellimac-mini "curl localhost:11434/api/tags"

set -e

HOST=${1:-daniellimac-mini}
CMD=$2
USER=${3:-danielli}

if [ -z "$CMD" ]; then
    echo "❌ 用法: $0 <主机名> <命令> [用户名]"
    echo ""
    echo "示例："
    echo "  $0 daniellimac-mini 'ollama list'"
    echo "  $0 daniellimac-mini 'curl localhost:11434/api/tags'"
    echo "  $0 daniellimac-mini 'ps aux | grep ollama'"
    exit 1
fi

# 获取动态 IP（带超时）
IP=$(timeout 5 tailscale status | grep -m1 "$HOST" | awk '{print $1}')

if [ -z "$IP" ]; then
    echo "❌ 主机 '$HOST' 未找到或不在线"
    exit 1
fi

# 执行命令（静默警告）
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o LogLevel=ERROR $USER@$IP "$CMD" 2>/dev/null
