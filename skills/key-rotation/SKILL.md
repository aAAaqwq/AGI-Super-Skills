---
name: key-rotation
description: API key rotation manager — rotate provider keys across all agent workspaces
---

# Key Rotation Skill

**触发词**: "换key", "更换key", "替换key", "rotate key", "key rotation", "更新密钥", "换API key", "给XX换key"

## 概述
统一管理 OpenClaw 所有 API key 的轮换流程。所有 key 通过 `pass` 金库存储，通过 `~/.openclaw/.env` 分发到 OpenClaw Gateway 和所有 Agent。

## 架构

```
pass (金库)
  ↓ pass show api/xxx
~/.openclaw/.env (运行时环境变量文件)
  ↓ EnvironmentFile= (systemd)
openclaw-gateway 进程环境变量
  ↓ ${VAR_NAME} 引用
openclaw.json + agents/*/agent/models.json
```

## Key 换新流程

### 用户说 "给 XX 换 key" 时，执行以下步骤：

**Step 1: 确认新 key**
```bash
# 用户提供新 key 后，存入 pass
pass insert api/<provider-name>
# 输入新 key
```

**Step 2: 更新 .env**
```bash
# 运行 env 重建脚本
bash ~/.openclaw/skills/key-rotation/scripts/rebuild-env.sh
```

**Step 3: 重启 Gateway**
```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway
```

**Step 4: 验证**
```bash
bash ~/.openclaw/skills/key-rotation/scripts/verify-keys.sh
```

## 供应商 → 变量名 → pass 路径 对照表

| 供应商 | 环境变量 | pass 路径 | 用途 |
|--------|----------|-----------|------|
| ZAI | `ZAI_API_KEY` | `api/zai` | GLM-5 系列 |
| Xingsuancode | `XINGSUANCODE_KEY` | `api/xingsuancode` | Claude Opus/Sonnet |
| XSC Backup | `XSC_BACKUP_API_KEY` | `api/xingsuancode` | 同上备份 |
| Xingjiabiapi | `XINGJIABIAPI_KEY` | `api/xingjiabiapi` | 多模型中转 |
| AIXN | `AIXN_API_KEY` | `api/aixn` | Claude 中转 |
| xAI | `XAI_API_KEY` | `api/xai` | Grok 系列 |
| Moonshot | `MOONSHOT_API_KEY` | `api/kimi` | Kimi K2.5 |
| Minimax | `MINIMAX_API_KEY` | `api/minimax` | MiniMax M2/M2.5 |
| WoW | `WOW_API_KEY` | `api/wow` | 多模型中转 |
| Xinyuan | `XINYUAN_API_KEY` | `api/xinyuan` | 多模型中转 |
| OpenRouter | `OPENROUTER_API_KEY` | `api/openrouter-vip` | 多模型中转 |
| GitHub Copilot | `GITHUB_COPILOT_KEY` | `api/github-copilot` | GPT/Gemini/Claude |
| GitHub Copilot (Agents) | `GITHUB_COPILOT_AGENTS_KEY` | `api/github-copilot-agents` | Agent用 |
| Ollama | `OLLAMA_API_KEY` | - | 固定值 `ollama` |
| Google AI Studio | `GOOGLE_AI_STUDIO_KEY` | `api/google-ai-studio` | Gemini/Veo/Imagen |
| Brave Search | `BRAVE_API_KEY` | `api/brave` | 网络搜索 |
| DeepSeek | `DEEPSEEK_API_KEY` | `api/deepseek` | DeepSeek 系列 |
| Exa | `EXA_API_KEY` | `api/exa` | 语义搜索 |
| Perplexity | `PERPLEXITY_API_KEY` | `api/perplexity` | AI 搜索 |
| Tavily | `TAVILY_API_KEY` | `api/tavily` | 网络搜索 |
| Firecrawl | `FIREFRAWL_API_KEY` | `api/firecrawl` | 网页爬取 |
| KlingAI | `KLINGAI_API_KEY` | `api/klingai` | 视频生成 |
| Notion | `NOTION_API_KEY` | `api/notion` | Notion API |

## 安全原则

1. **永不明文打印 key** — 所有输出用 `***REDACTED***` 遮罩
2. **pass 是唯一真相源** — `.env` 从 pass 生成，不手动编辑
3. **换 key 后必须验证** — 至少调一次 API 确认可用
4. **.env 权限 600** — 仅 owner 可读写
