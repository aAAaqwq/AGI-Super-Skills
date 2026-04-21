---
name: model-provider-manager
description: Unified LLM provider and model configuration, health monitoring, and key management
---

# Skill: Model & Provider Manager

## 触发条件
- "模型管理"、"供应商管理"、"provider 健康检查"
- "检查模型"、"模型可用性"、"哪个模型能用"
- "embedding 模型"、"推理模型"、"视觉模型"
- "API key 检查"、"key 过期"、"余额查询"
- "添加模型"、"删除模型"、"更新模型配置"
- "同步模型配置"、"sync agent models"

## 职责
统一维护所有 LLM 供应商和模型的配置、健康状态、密钥管理。
CEO 指定的**专职模型管理 skill**，所有模型相关查询和操作都通过此 skill。

## ⚙️ 配置更新铁律（env-first 三步同步）

**任何模型/密钥/供应商变更，必须按以下顺序执行：**

```
Step 1: 更新 pass 密钥仓库（唯一真相源）
   pass insert api/<provider-name>    # 新建
   pass show api/<provider-name>      # 验证

Step 2: 同步到 ~/.openclaw/.env（运行时环境变量）
   添加/更新: echo 'NEW_API_KEY=<value>' >> ~/.openclaw/.env
   或执行: ~/clawd/scripts/rebuild-env.sh  # 如果存在
   
Step 3: 同步到 ~/.openclaw/openclaw.json（OpenClaw 配置）
   确保模型引用 ${ENV_VAR_NAME} 而非硬编码
   gateway restart 或 config.patch 生效

Step 4: 验证同步完整性
   python3 ~/clawd/skills/model-provider-manager/scripts/health-check.py
   python3 ~/clawd/skills/model-provider-manager/scripts/key-audit.py
```

### Agent & Cron 模型同步
当全局模型配置变更时（新增/删除/切换 provider），需检查并同步：
- **Agent 模型**: `openclaw.json → agents.list[].model.primary/fallbacks`
- **Cron 任务模型**: `cron list` → 检查每个 cron 的 `payload.model`
- **Cron fallback**: `cron list` → 检查 `payload.fallbacks`

### 同步检查脚本
```bash
python3 ~/clawd/skills/model-provider-manager/scripts/sync-check.py
```

## 配置文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| **pass 仓库** | `pass api/<name>` | **密钥唯一真相源** |
| 运行时环境 | `~/.openclaw/.env` | 环境变量（chmod 600） |
| 主配置 | `~/.openclaw/openclaw.json` → `models.providers` | 供应商定义 |
| Agent 模型 | `~/.openclaw/openclaw.json` → `agents.list[].model` | 各 agent 主模型+fallback |
| 全局默认 | `~/.openclaw/openclaw.json` → `agents.defaults.model` | 默认模型 |
| Embedding | `~/.openclaw/openclaw.json` → `agents.defaults.memorySearch` | Embedding 配置 |

## 当前供应商清单

| Provider | baseUrl | API类型 | 模型数 | Key来源 | 状态 |
|----------|---------|---------|--------|---------|------|
| shibacc | http://8.148.217.100:6543 | anthropic-messages | 3 | 🔴硬编码 | ⚠️ key未存pass |
| xingsuancode | https://cn.xingsuancode.com | anthropic-messages | 1 | env | ❌ 9账号全挂 |
| zai | https://open.bigmodel.cn/api/coding/paas/v4 | openai-completions | 5 | 🔴硬编码 | ⚠️ key未存pass |
| minimax | https://api.minimaxi.com/anthropic | anthropic-messages | 1 | env | ✅ |
| xingjiabiapi | https://xingjiabiapi.com/v1 | openai-completions | 4 | env | ✅ |
| xai | https://api.x.ai/v1 | openai-completions | 10 | env | ✅ |
| wow | https://linuxdoapi-api-wow.223387.xyz/v1 | openai-completions | 3 | env | ⚠️ 503偶发 |
| xinyuan | https://api-i.xykjy.com | auto | 4 | env | ✅ |
| aixn | https://ai.xn--vuq861bvij35ps8cv0uohm.com/v1 | openai-completions | 1 | env | ✅ |
| moonshot | https://api.moonshot.cn/v1 | openai-completions | 1 | env | ✅ |
| ollama | http://100.65.110.126:11434 | ollama | 12 | env | ✅ |
| github-copilot | https://api.githubcopilot.com | openai-completions | 17 | env | ✅ |

## Embedding 模型清单

| 位置 | 模型 | 维度 | 大小 | 状态 |
|------|------|------|------|------|
| Mac Studio Ollama | qwen3-embedding:0.6b | 1024 | 639MB | ✅ 推荐 |
| Mac Studio Ollama | qwen3-embedding:8b | 4096 | 4.7GB | ✅ |
| Mac Studio Ollama | nomic-embed-text:latest | 768 | 274MB | ✅ |
| 小m Ollama | qwen3-embedding:0.6b | 1024 | 639MB | ⚠️ 离线不稳定 |
| OpenClaw 内置 | embeddinggemma-300M | 384 | 300MB | ✅ fallback |

## Agent 模型分配方案（待 Daniel 确认）

| Agent | 当前 | 建议主模型 | 建议Fallback |
|-------|------|-----------|-------------|
| main (CEO) | opus-4-6 | shibacc/opus-4-6 ✅ | xsc/opus, zai/glm-5 |
| quant | opus-4-6 | shibacc/opus-4-6 ✅ | xsc/opus, zai/glm-5 |
| code | opus-4-6 | xingsuancode/sonnet-4-6 | shibacc/opus, aixn/gpt-5.2 |
| pm | opus-4-6 | xingsuancode/sonnet-4-6 | shibacc/opus, zai/glm-5 |
| content | opus-4-6 | xingsuancode/sonnet-4-6 | shibacc/opus, minimax/M2.5 |
| research | opus-4-6 | xingsuancode/sonnet-4-6 | shibacc/opus, aixn/gpt-5.2 |
| law | opus-4-6 | xingsuancode/sonnet-4-6 | shibacc/opus, minimax/M2.5 |
| data | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |
| ops | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |
| finance | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |
| market | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |
| product | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |
| sales | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |
| batch | opus-4-6 | zai/glm-5-turbo | xingsuancode/sonnet, minimax/M2.5 |

## 执行命令

| 命令 | 用途 |
|------|------|
| `health-check.py` | 全量 provider 健康检查 |
| `health-check.py --type embedding` | 只检查 embedding 模型 |
| `key-audit.py` | 密钥审计（硬编码/缺pass/env缺失） |
| `sync-check.py` | 检查 env→json→agent→cron 同步完整性 |

## 安全铁律
1. **pass 是唯一真相源** — 所有 key 必须先存 pass
2. **openclaw.json 用 `${ENV_VAR}`** — 永不硬编码 key
3. **换 key**: `pass insert` → 更新 `.env` → `gateway restart`
4. **provider 变更必须经 CEO 确认**

## 更新记录
- 2026-03-29: 初版，覆盖 12 provider 84+ 模型，env-first 三步同步
