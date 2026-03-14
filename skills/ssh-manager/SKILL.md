---
name: ssh-manager
description: "专业 SSH 连接管理工具。处理 Tailscale SSH、主机密钥、代理绕过、远程命令执行等操作。"
license: MIT
metadata:
  version: 1.0.0
  domains: [ssh, remote-access, infrastructure]
  type: tool
---

# SSH 连接管理器

## 当使用此技能

- 需要通过 SSH 连接远程主机（小m、Peter's Mac Mini 等）
- Tailscale SSH 连接问题排查
- 执行远程命令
- 配置 SSH 隧道或端口转发
- 处理主机密钥验证问题
- 绕过代理访问内网设备

## 已知主机列表

| 主机名 | Tailscale IP | 用户名 | 用途 |
|--------|-------------|--------|------|
| 小m (Mac Mini M2) | 动态 | danielli | Daniel 的 Mac Mini |
| Peter's Mac Mini | 100.118.109.75 | peterqiu | Peter 团队 |
| daniel-ubuntu | 100.112.88.20 | aa | 本机（Ubuntu） |

> ⚠️ 注意：Tailscale IP 可能会变化，应该动态获取

## 核心功能

### 1. 获取动态 Tailscale IP

```bash
# 获取指定主机的当前 Tailscale IP
tailscale status | grep "主机名" | awk '{print $1}'
```

### 2. 标准化 SSH 连接

```bash
# 推荐：使用 Tailscale MagicDNS 名称
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 用户@主机名.tail0db0a3.ts.net

# 或使用动态 IP
IP=$(tailscale status | grep "主机名" | awk '{print $1}')
ssh -o StrictHostKeyChecking=no 用户@$IP
```

### 3. 绕过代理（重要！）

本地 Clash 代理会拦截 100.x.x.x 流量导致 502 错误：

```bash
# SSH 不需要（走 Tailscale），但 HTTP/API 调用需要绕过
curl --noproxy "*" "http://TAILSCALE_IP:端口/api/endpoint"

# Python
requests.get(url, proxies={"http": None, "https": None})
```

### 4. 主机状态检查

```bash
# 检查主机是否在线
tailscale ping 主机名 --timeout=5s

# 查看详细状态
tailscale status | grep 主机名
```

## 辅助脚本

### `connect.sh` - 智能 SSH 连接

```bash
#!/bin/bash
# 使用：./connect.sh <主机名> [命令]
# 示例：./connect.sh daniellimac-mini "ollama list"

HOST=$1
CMD=$2

# 获取动态 IP
IP=$(tailscale status | grep "$HOST" | awk '{print $1}')

if [ -z "$IP" ]; then
    echo "❌ 主机 $HOST 未找到或不在线"
    tailscale status | grep -E "offline|online" | head -5
    exit 1
fi

# 检查是否在线
STATUS=$(tailscale status | grep "$HOST" | awk '{print $NF}')
if [[ "$STATUS" == "offline"* ]]; then
    echo "⚠️ 主机 $HOST 当前离线 ($STATUS)"
    exit 1
fi

echo "🔗 连接 $HOST ($IP)..."

if [ -z "$CMD" ]; then
    # 交互式 SSH
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null danielli@$IP
else
    # 执行命令
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null danielli@$IP "$CMD"
fi
```

### `tunnel.sh` - 端口转发

```bash
#!/bin/bash
# 使用：./tunnel.sh <主机名> <远程端口> [本地端口]
# 示例：./tunnel.sh daniellimac-mini 11434 11434

HOST=$1
REMOTE_PORT=$2
LOCAL_PORT=${3:-$REMOTE_PORT}

IP=$(tailscale status | grep "$HOST" | awk '{print $1}')

if [ -z "$IP" ]; then
    echo "❌ 主机 $HOST 未找到"
    exit 1
fi

echo "🔗 建立隧道: localhost:$LOCAL_PORT -> $HOST:$REMOTE_PORT"
ssh -N -L $LOCAL_PORT:localhost:$REMOTE_PORT danielli@$IP
```

### `check-host.sh` - 主机诊断

```bash
#!/bin/bash
# 使用：./check-host.sh <主机名>

HOST=$1

echo "=== Tailscale 状态 ==="
tailscale status | grep -E "$HOST|online" | head -5

echo ""
echo "=== IP 地址 ==="
IP=$(tailscale status | grep "$HOST" | awk '{print $1}')
echo "IP: $IP"

echo ""
echo "=== 连通性测试 ==="
if ping -c 2 -W 3 $IP > /dev/null 2>&1; then
    echo "✅ Ping 成功"
else
    echo "❌ Ping 失败"
fi

echo ""
echo "=== SSH 测试 ==="
timeout 5 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 danielli@$IP "echo 'SSH 连接成功'" 2>&1
```

## 常见问题

### Q: SSH 连接超时
1. 检查 Tailscale 状态：`tailscale status`
2. 确认主机在线：`tailscale ping 主机名`
3. 检查防火墙是否允许 SSH（端口 22）

### Q: 主机密钥验证失败
使用 `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`

### Q: HTTP 请求返回 502
本地 Clash 代理干扰，添加 `--noproxy "*"` 或设置 `no_proxy=100.0.0.0/8`

### Q: Tailscale IP 变化
始终用 `tailscale status` 获取当前 IP，不要硬编码

## 触发词

- "SSH 连接"
- "连接远程主机"
- "Tailscale SSH"
- "SSH 隧道"
- "端口转发"
- "远程执行命令"
- "SSH 问题"

## 相关文件

- `~/clawd/MEMORY.md` - 主机配置信息
- `~/.ssh/known_hosts` - 已知主机密钥
- `~/.ssh/config` - SSH 配置文件

---

*Created: 2026-03-06*
