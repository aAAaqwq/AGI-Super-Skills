# Plugins 配置

> 更新时间: 2026-02-04

## 📡 Plugin 列表 (2个)

| Plugin | 状态 | 说明 |
|--------|------|------|
| `telegram` | ✅ 启用 | Telegram Bot 集成 |
| `whatsapp` | ✅ 启用 | WhatsApp 集成 |

---

## 🔧 配置示例

### openclaw.json 中的 plugins 配置

```json
{
  "plugins": {
    "entries": {
      "whatsapp": {
        "enabled": true
      },
      "telegram": {
        "enabled": true
      }
    }
  }
}
```

---

## 📝 Plugin 详情

### telegram

**功能**:
- 接收/发送 Telegram 消息
- 支持私聊和群组
- 支持 inline buttons
- 支持 reactions
- 支持流式输出

**配置**:
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "dmPolicy": "allowlist",
      "botToken": "xxx:xxx",
      "allowFrom": ["user_id"],
      "groupPolicy": "allowlist",
      "streamMode": "partial"
    }
  }
}
```

**获取 Bot Token**: 通过 @BotFather 创建 Bot

### whatsapp

**功能**:
- 接收/发送 WhatsApp 消息
- 支持私聊和群组
- 支持媒体文件
- 支持 self-chat 模式

**配置**:
```json
{
  "channels": {
    "whatsapp": {
      "dmPolicy": "allowlist",
      "selfChatMode": true,
      "allowFrom": ["+xxx"],
      "groupPolicy": "allowlist",
      "mediaMaxMb": 50,
      "debounceMs": 0
    }
  }
}
```

**连接方式**: 使用 `whatsapp_login` 工具扫码连接

---

## 🔗 Channel Bindings

将消息通道绑定到特定 Agent:

```json
{
  "bindings": [
    {
      "agentId": "telegram-agent",
      "match": { "channel": "telegram" }
    },
    {
      "agentId": "whatsapp-agent",
      "match": { "channel": "whatsapp" }
    }
  ]
}
```
