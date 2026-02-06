# OpenClaw 配置快速参考

## 常用命令

```bash
# 查看状态
openclaw status
openclaw models status
openclaw gateway status

# 模型操作
openclaw models set <provider/model>          # 设置默认模型
openclaw models list                          # 列出所有模型
openclaw models aliases set <alias> <model>   # 设置别名
openclaw models fallbacks add <model>         # 添加降级模型

# 配置操作
openclaw config get <path>                    # 获取配置值
openclaw config set <path> <value>            # 设置配置值
openclaw doctor                               # 检查配置
openclaw doctor --fix                         # 自动修复

# Gateway 操作
openclaw gateway restart                      # 重启
openclaw gateway stop                         # 停止
openclaw gateway start                        # 启动
openclaw logs                                 # 查看日志
```

## 配置文件位置

| 文件 | 路径 |
|------|------|
| 主配置 | `~/.openclaw/openclaw.json` |
| 模型配置 | `~/.openclaw/agents/main/agent/models.json` |
| 认证配置 | `~/.openclaw/agents/main/agent/auth-profiles.json` |

## 当前配置的模型

| 别名 | 完整名称 | 供应商 |
|------|---------|--------|
| opus45 | anapi/opus-4.5 | anapi |
| zai47 | zai/glm-4.7 | zai |
| or52 | openrouter-vip/gpt-5.2 | openrouter-vip |
| codex52 | openrouter-vip/gpt-5.2-codex | openrouter-vip |
| opus | anthropic/claude-opus-4-5 | anthropic |
| sonnet | anthropic/claude-sonnet-4-5 | anthropic |
| gemini | google/gemini-3-pro-preview | google |

## 通道配置

### Telegram
```json5
"telegram": {
  "enabled": true,
  "botToken": "xxx:xxx",
  "dmPolicy": "allowlist",
  "allowFrom": ["user_id"],
  "streamMode": "partial"
}
```

### WhatsApp
```json5
"whatsapp": {
  "dmPolicy": "allowlist",
  "selfChatMode": true,
  "allowFrom": ["+phone"],
  "mediaMaxMb": 50
}
```

## 修改配置检查清单

1. ✅ 备份配置
2. ✅ 修改配置
3. ✅ 运行 `openclaw doctor`
4. ✅ 运行 `openclaw gateway restart`
5. ✅ 验证功能
6. ✅ 告知用户

## 故障排查

```bash
# 配置问题
openclaw doctor

# 连接问题
openclaw gateway probe

# 模型问题
openclaw models status

# 查看日志
openclaw logs | tail -50
```
