# Cross-Team Communication Skill

OpenClaw 跨团队/跨实例通信技能。通过 Tailscale + SSH + Gateway API + sessions_send 实现不同 OpenClaw 实例之间的 Agent 协作。

## 触发词
跨团队通信、跨实例协作、远程 agent、连通其他团队、sessions_send 远程、Tailscale 通信、跨 Gateway

## 适用场景
- 连接另一个 OpenClaw 实例的 Agent 团队
- 跨团队派发任务 / 获取信息
- 通过飞书/Telegram 等渠道发送跨团队消息
- 远程管理其他实例的配置和 Agent

## 通信方式（优先级排序）

### 1. sessions_send（推荐 ✅）
最简单的方式，直接跨 Gateway 发消息给目标 Agent。

```
sessions_send(
  sessionKey="agent:<agentId>:<channel>:group:<chatId>",
  message="你的消息",
  gatewayUrl="ws://<target-host>:<port>",
  gatewayToken="<token>"
)
```

**示例**：
```
sessions_send(
  sessionKey="agent:main:feishu:group:YOUR_FEISHU_CHAT_ID",
  message="你好！我是小a，来自Daniel团队。",
  gatewayUrl="ws://100.118.109.75:18789",
  gatewayToken="YOUR_GATEWAY_TOKEN"
)
```

**优点**：原生支持，Agent 可直接回复
**限制**：需要目标 Gateway 开放 Tailscale 或公网访问；loopback 绑定的需通过 SSH 中转

### 2. SSH + 本地 API（可靠 ✅）
当 Gateway 只绑定 loopback 时，先 SSH 到目标机器，再调用本地 API。

```bash
ssh user@<tailscale-ip>
curl -s -X POST "http://127.0.0.1:<port>/v1/sessions/send" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"sessionKey":"agent:main:...","message":"..."}'
```

### 3. 直接调用目标渠道 API（兜底）
当 sessions_send 和 SSH 都不方便时，直接用目标团队的渠道凭据发消息。

**飞书示例**：
```python
import requests, json

# 1. 获取 tenant_access_token
token_resp = requests.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    json={"app_id": "<app_id>", "app_secret": "<app_secret>"}
)
token = token_resp.json()["tenant_access_token"]

# 2. 发送消息
requests.post(
    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "receive_id": "<chat_id>",
        "msg_type": "text",
        "content": json.dumps({"text": "消息内容"})
    }
)
```

## 首次连通 SOP

### Step 1: 网络连通
确保两台机器在同一 Tailscale 网络（或有 SSH 访问）：
```bash
tailscale status  # 查看在线设备
ssh user@<ip>     # 测试连通
```

### Step 2: 收集目标信息
SSH 登录后收集：
```bash
openclaw --version
openclaw gateway status
cat ~/.openclaw/openclaw.json | grep -E "port|token|feishu|telegram|appId"
find ~/.openclaw/workspace* -name "SOUL.md" -o -name "IDENTITY.md"
ls ~/.openclaw/agents/
```

### Step 3: 测试通信
```
sessions_send(sessionKey="agent:main:...", message="连通测试")
```

### Step 4: 记录到 MEMORY.md
```markdown
### 目标团队名 (机器名)
| 项目 | 值 |
|------|------|
| 主机 | <hostname> (<tailscale-ip>) |
| Gateway | 端口 / Token |
| Agents | 列表 |
| 渠道 | 飞书群ID / Telegram群ID |
| 通信方式 | sessions_send / SSH / API |
```

## 注意事项

1. **Gateway bind**: 很多实例默认 `bind: loopback`，只能本地访问。要远程直连需改为 `bind: tailscale` 或 `0.0.0.0`
2. **Token 安全**: Gateway token 等同于完全控制权，仅存 `pass` 或 MEMORY.md，不要明文传输
3. **凭据存储**: 对方的飞书/Telegram 凭据用 `pass insert` 存储
4. **API 路径**: OpenClaw Gateway REST API 路径可能因版本不同而变化，优先用 sessions_send 工具
5. **消息格式**: 跨团队发消息时，说明来源（"我是小a，来自Daniel团队"），避免对方 Agent 困惑
