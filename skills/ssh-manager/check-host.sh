#!/bin/bash
# SSH 主机诊断脚本
# 使用：./check-host.sh <主机名>
# 示例：./check-host.sh daniellimac-mini

set -e

HOST=${1:-daniellimac-mini}

echo "═══════════════════════════════════════════════════════════════"
echo "  SSH 主机诊断: $HOST"
echo "═══════════════════════════════════════════════════════════════"

echo ""
echo "📡 Tailscale 状态"
echo "─────────────────────────────────────────"
tailscale status | grep -E "$HOST|100\." | head -5

echo ""
echo "🌐 IP 地址"
echo "─────────────────────────────────────────"
STATUS_LINE=$(tailscale status | grep "$HOST" | head -1)
IP=$(echo "$STATUS_LINE" | awk '{print $1}')
HOSTNAME=$(echo "$STATUS_LINE" | awk '{print $2}')
STATUS=$(echo "$STATUS_LINE" | awk '{print $NF}')

if [ -z "$IP" ]; then
    echo "❌ 主机 '$HOST' 未找到"
    exit 1
fi

echo "  主机名: $HOSTNAME"
echo "  IP: $IP"
echo "  状态: $STATUS"

echo ""
echo "🏓 Ping 测试"
echo "─────────────────────────────────────────"
if ping -c 2 -W 3 $IP > /dev/null 2>&1; then
    echo "  ✅ Ping 成功"
    ping -c 2 $IP 2>&1 | tail -1
else
    echo "  ❌ Ping 失败"
fi

echo ""
echo "🔐 SSH 测试 (端口 22)"
echo "─────────────────────────────────────────"
SSH_RESULT=$(timeout 5 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 -o BatchMode=yes danielli@$IP "echo 'success'" 2>&1)
if [[ "$SSH_RESULT" == "success" ]]; then
    echo "  ✅ SSH 连接成功"
else
    echo "  ❌ SSH 连接失败: $SSH_RESULT"
fi

echo ""
echo "📊 端口扫描 (常用端口)"
echo "─────────────────────────────────────────"
for PORT in 22 80 443 11434 18789 8080; do
    if timeout 2 bash -c "echo > /dev/tcp/$IP/$PORT" 2>/dev/null; then
        echo "  ✅ 端口 $PORT 开放"
    else
        echo "  ⬜ 端口 $PORT 关闭/超时"
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  诊断完成"
echo "═══════════════════════════════════════════════════════════════"
