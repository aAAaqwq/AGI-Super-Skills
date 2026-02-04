# Agents 配置

> 更新时间: 2026-02-04

## 📦 Agent 列表 (11个)

| Agent ID | 模型 | 用途 |
|----------|------|------|
| `main` | anapi/claude-opus-4-5 | 主 Agent |
| `telegram-agent` | anapi/claude-opus-4-5 | Telegram 消息处理 |
| `whatsapp-agent` | anapi/claude-opus-4-5 | WhatsApp 消息处理 |
| `feishu-agent` | zai/glm-4.7 | 飞书消息处理 |
| `multimodal-agent` | xingjiabiapi/gemini-3-pro | 多模态处理（图像理解+视频生成） |
| `news` | anthropic/claude-sonnet-4-5 | 新闻处理 |
| `code` | openrouter-vip/gpt-5.2-codex | 代码开发 |
| `research` | anapi/claude-opus-4-5 | 深度研究 |
| `quick` | google/gemini-flash-latest | 快速任务 |
| `batch` | openrouter-vip/gpt-5.1-codex-mini | 批量处理 |
| `healthcare-monitor` | zai/glm-4.7 | 医疗行业监控 |

---

## 🔧 配置示例

### openclaw.json 中的 agents 配置

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anapi/claude-opus-4-5-20250514",
        "fallbacks": [
          "zai/glm-4.7",
          "openrouter-vip/gpt-5.2-codex",
          "github-copilot/claude-sonnet-4-5",
          "xingjiabiapi/gemini-3-pro-preview"
        ]
      },
      "workspace": "/home/aa/clawd",
      "compaction": {
        "mode": "safeguard"
      },
      "maxConcurrent": 8,
      "subagents": {
        "maxConcurrent": 16
      }
    },
    "list": [
      {
        "id": "main"
      },
      {
        "id": "telegram-agent",
        "name": "telegram-agent",
        "workspace": "/home/aa/clawd",
        "agentDir": "/home/aa/.openclaw/agents/telegram-agent/agent",
        "model": "anapi/claude-opus-4-5-20250514"
      },
      {
        "id": "multimodal-agent",
        "name": "multimodal-agent",
        "workspace": "/home/aa/clawd",
        "agentDir": "/home/aa/.openclaw/agents/multimodal-agent/agent",
        "model": "xingjiabiapi/gemini-3-pro-preview"
      }
    ]
  }
}
```

---

## 📁 Agent 目录结构

```
~/.openclaw/agents/
├── main/
│   └── agent/
│       └── auth-profiles.json
├── telegram-agent/
│   └── agent/
│       ├── system.md
│       └── AGENT.md
├── multimodal-agent/
│   └── agent/
│       ├── system.md
│       └── AGENT.md
└── ...
```

---

## 🎯 Agent 详情

### multimodal-agent

**用途**: 多模态处理（图像理解 + 视频生成）

**模型**: `xingjiabiapi/gemini-3-pro-preview` (Gemini 3 Pro)

**能力**:
- 🖼️ 图像理解和分析
- 📊 图表解读
- 📄 OCR 文字提取
- 🎬 视频生成 (Veo/Sora/Kling)

**调用方式**:
```python
sessions_spawn(agentId="multimodal-agent", task="分析这张图片...")
```

### telegram-agent / whatsapp-agent

**用途**: 消息通道处理

**绑定配置**:
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

### healthcare-monitor

**用途**: 医疗行业企业融资监控

**模型**: `zai/glm-4.7` (低成本)

**功能**:
- 监控医疗健康企业工商变更
- 识别融资信号
- 自动推送告警
