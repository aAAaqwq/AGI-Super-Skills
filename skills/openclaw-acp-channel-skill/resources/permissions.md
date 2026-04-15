# 权限控制

## Owner vs 外部 Agent

- **Owner**（`ownerAid`）：来自此 AID 的消息拥有完整 `CommandAuthorized` 权限——可执行命令、修改文件、访问所有 agent 能力。
- **外部 Agent**：仅对话权限。消息标记为 `restrictions=no_file_ops,no_config_changes,no_commands,conversation_only`。

## allowFrom 配置

控制哪些 AID 可以发送消息：

- `["*"]` — 接受所有人（默认）
- `["friend.agentcp.io", "colleague.agentcp.io"]` — 仅接受列表中的 AID
- 非允许 AID 的消息被静默拒绝并记录日志。

## 修改权限

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "channels": {
    "acp": {
      "ownerAid": "your-name.agentcp.io",
      "allowFrom": ["trusted-agent.agentcp.io", "another.agentcp.io"]
    }
  }
}
```

修改后需重启 gateway 生效。
