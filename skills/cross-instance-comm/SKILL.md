# 跨 OpenClaw 实例通信 (Tailscale Gateway)

通过 Tailscale 网络向其他 OpenClaw 实例发送消息，实现跨机器 Agent 通信。

## 触发条件

- "给小m发消息"、"发到Mac Mini"、"跨实例通信"
- "在小m上执行"、"远程部署"、"同步到小m"

## 已知实例

| 实例 | 域名 | 端口 | Token |
|------|------|------|-------|
| 小m (Mac Mini M2) | daniellimac-mini.tail0db0a3.ts.net | 18789 | $(pass show api/xiaom-gateway-token) |
| 本机 (Linux) | 127.0.0.1 | 18789 | (本地) |

## 发送消息到远程实例

```bash
# 给小m的主agent发消息
curl -s -X POST "http://daniellimac-mini.tail0db0a3.ts.net:18789/api/message" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "你的消息内容"}'
```

## 通过 OpenClaw sessions_send（推荐）

如果当前 OpenClaw 配置了远程 Gateway，可直接用 sessions_send：

```python
# 在代码中通过 Gateway API
import httpx

def send_to_instance(host, port, token, message, session_key=None):
    url = f"http://{host}:{port}/api/message"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"message": message}
    if session_key:
        data["sessionKey"] = session_key
    resp = httpx.post(url, headers=headers, json=data, timeout=30)
    return resp.json()

# 发到小m
send_to_instance(
    "daniellimac-mini.tail0db0a3.ts.net", 18789,
    "$(pass show api/xiaom-gateway-token)",
    "帮XX公司做GEO，行业是云计算"
)
```

## 脚本快捷方式

```bash
# scripts/send-to-m2.sh
#!/bin/bash
MSG="${1:?用法: send-to-m2.sh '消息内容'}"
curl -s -X POST "http://daniellimac-mini.tail0db0a3.ts.net:18789/api/message" \
  -H "Authorization: Bearer $(pass show api/xiaom-gateway-token)" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MSG\"}"
```

## 注意事项

- 需要 Tailscale 网络连通（两台机器都在同一 Tailnet）
- Token 不要泄露到公开仓库
- 超时建议设 30s（跨网络延迟）
- 远程实例的 Gateway 必须在运行状态
