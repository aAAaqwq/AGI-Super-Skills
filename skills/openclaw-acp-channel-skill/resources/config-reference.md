# 配置参考与故障排查（单身份 / 多身份）

## 配置总览

所有配置位于 `~/.openclaw/openclaw.json` 的 `channels.acp`。修改后重启 gateway 生效。

支持两种模式：

- **单身份**：使用 `channels.acp.agentName` 等顶层字段
- **多身份**：使用 `channels.acp.identities.{accountId}`

默认绑定策略：

- `agentAidBindingMode: "strict"`（推荐）

---

## 顶层字段（`channels.acp`）

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `enabled` | boolean | 是 | `false` | 启用 ACP 通道 |
| `agentAidBindingMode` | string | 否 | `"strict"` | `strict`（1:1 强约束）或 `flex`（兼容模式） |
| `agentName` | string | 单身份必需 | — | Agent 名称（`^[a-z0-9-]+$`） |
| `domain` | string | 否 | `"agentcp.io"` | ACP 域名 |
| `seedPassword` | string | 否 | — | 种子密码 |
| `ownerAid` | string | 否 | — | 主人 AID，拥有完整权限 |
| `allowFrom` | string[] | 否 | `[]` | 允许来源 AID，`["*"]` 表示全允许 |
| `agentMdPath` | string | 否 | — | `agent.md` 路径（支持 `~`） |
| `workspaceDir` | string | 否 | — | workspace 自动生成 `agent.md` 的目录 |
| `identities` | object | 多身份必需 | — | 多身份 map，key 为 `accountId` |
| `session` | object | 否 | 见下文 | 会话控制配置 |

当 `enabled=true` 时，必须配置 `agentName` 或 `identities`。

---

## 多身份条目（`channels.acp.identities.{accountId}`）

每个 `accountId` 条目字段与单身份字段一致：

- `agentName`（必需）
- `domain`
- `seedPassword`
- `ownerAid`
- `allowFrom`
- `agentMdPath`
- `workspaceDir`
- `profile`
- `mentionAliases`

---

## 绑定规则（`bindings`）

### strict 模式（默认）

要求：

1. `bindings[].match.channel` 为 `acp` 的条目必须有 `accountId`
2. 1 Agent ↔ 1 Account（双向 1:1）
3. `accountId` 必须存在于 `channels.acp.identities`
4. 推荐并建议保持 `agentId === accountId`

推荐绑定示例：

```json
{
  "bindings": [
    { "agentId": "work", "match": { "channel": "acp", "accountId": "work" } },
    { "agentId": "personal", "match": { "channel": "acp", "accountId": "personal" } }
  ]
}
```

### flex 模式

允许历史复杂映射，但仍建议逐步收敛到 1:1。

---

## 单身份示例

```json
{
  "channels": {
    "acp": {
      "enabled": true,
      "agentAidBindingMode": "strict",
      "agentName": "my-bot",
      "domain": "agentcp.io",
      "seedPassword": "your-seed-password",
      "ownerAid": "owner.agentcp.io",
      "allowFrom": ["*"],
      "agentMdPath": "~/.acp-storage/AIDs/my-bot.agentcp.io/public/agent.md"
    }
  },
  "plugins": {
    "entries": { "acp": { "enabled": true } }
  },
  "bindings": [
    { "agentId": "default", "match": { "channel": "acp", "accountId": "default" } }
  ]
}
```

## 多身份示例

```json
{
  "channels": {
    "acp": {
      "enabled": true,
      "agentAidBindingMode": "strict",
      "identities": {
        "work": {
          "agentName": "work-bot",
          "domain": "agentcp.io",
          "ownerAid": "boss.agentcp.io",
          "allowFrom": ["*"],
          "agentMdPath": "~/.acp-storage/AIDs/work-bot.agentcp.io/public/agent.md"
        },
        "personal": {
          "agentName": "home-bot",
          "domain": "agentcp.io",
          "ownerAid": "me.agentcp.io",
          "allowFrom": ["friend.agentcp.io"],
          "agentMdPath": "~/.acp-storage/AIDs/home-bot.agentcp.io/public/agent.md"
        }
      }
    }
  },
  "plugins": {
    "entries": { "acp": { "enabled": true } }
  },
  "bindings": [
    { "agentId": "work", "match": { "channel": "acp", "accountId": "work" } },
    { "agentId": "personal", "match": { "channel": "acp", "accountId": "personal" } }
  ]
}
```

---

## 常用命令（多身份可指定）

- `/acp-status [accountId]`：查看状态
- `/acp-sync [accountId]`：同步 `agent.md`

---

## 故障排查

| 症状 | 常见原因 | 处理建议 |
|------|----------|----------|
| strict 模式启动失败 | `bindings` 与 `identities` 不一致 | 修正为 1:1，确保 `accountId` 存在且不重复绑定 |
| 多身份下消息路由错位 | 只改了 `identities`，没改 `bindings` | 同步更新 `bindings(channel=acp, accountId=...)` |
| 多身份下配置错身份 | 未指定 `accountId` 就直接改配置 | 先确认目标 `accountId` 再写入 |
| `PREFLIGHT_FAIL: account config missing` | 预检目标身份不存在 | 检查 `identities.{accountId}` 是否存在 |
| `PREFLIGHT_FAIL` + `is used by another user` | AID 被占用 | 更换 `agentName` |
| `PREFLIGHT_FAIL` + `signIn` | AID 已存在但密码不匹配 | 使用正确 `seedPassword` 或更换 `agentName` |
| `PREFLIGHT_FAIL` + `TIMEOUT` | 网络不可达 | 检查网络/代理 |
| `/acp` skill 不可用 | 插件未启用或 skill 未加载 | 检查 `plugins.entries.acp.enabled` 与 `skill/acp/SKILL.md` |
