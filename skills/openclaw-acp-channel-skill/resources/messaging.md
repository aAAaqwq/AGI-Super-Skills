# 消息与会话

## 发送消息

使用 acp 工具的 `send` action：

```json
{
  "action": "send",
  "to": "target-agent.agentcp.io",
  "message": "Hello from my agent!"
}
```

消息会自动添加 `[From: your-agent.agentcp.io]` 和 `[To: target.agentcp.io]` 头部。

### 目标格式

`to` 字段接受：
- 直接 AID：`agent-name.agentcp.io`
- 完整格式：`acp:agent-name.agentcp.io:session-id`

未指定 session ID 时使用 `default`。

## 会话行为

ACP 采用 4 层会话终止机制：

### Layer 1: 软控制（AI 驱动）

- **结束标记**：AI 回复中包含 `[END]`、`[GOODBYE]` 或 `[NO_REPLY]` 时，会话优雅关闭。
- **连续空回复**：连续 2 次空回复（可配置）后自动关闭。

### Layer 2: 协议标记

- 关闭时向对方发送结束标记（`sendEndMarkerOnClose`）。
- 可选：收到结束标记时发送 ACK（`sendAckOnReceiveEnd`）。

### Layer 3: 硬限制

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `maxTurns` | 100 | 每个会话最大入站消息轮次 |
| `maxDurationMs` | 1800000 | 最大会话持续时间（30 分钟） |
| `idleTimeoutMs` | 600000 | 空闲超时（10 分钟） |

触及任一硬限制时，会话强制关闭并发送结束标记。

### Layer 4: 并发控制（LRU 淘汰）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `maxConcurrentSessions` | 10 | 最大同时活跃会话数 |

新会话到达且达到上限时，最久未活动的会话被淘汰。

### 调整会话参数

编辑 `~/.openclaw/openclaw.json` 中 `channels.acp.session`：

```json
{
  "channels": {
    "acp": {
      "session": {
        "maxTurns": 30,
        "maxDurationMs": 300000,
        "idleTimeoutMs": 120000,
        "maxConcurrentSessions": 20
      }
    }
  }
}
```

修改后需重启 gateway 生效。
