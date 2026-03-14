---
name: skill-config-checker
description: "扫描本地所有 skills，检测需要配置的 API keys、tokens、secrets 等，生成配置需求清单和操作指南。"
license: MIT
metadata:
  version: 1.0.0
  domains: [configuration, skill-management, automation]
  type: tool
---

# Skill 配置检索器

## 当使用此技能

- "检查 skills 配置"
- "哪些 skill 需要配置"
- "skill 配置清单"
- "API key 需求检查"
- "配置需求扫描"

## 功能

1. **扫描所有本地 skills** - 检查 `~/.openclaw/skills` 和 `~/clawd/skills` 目录
2. **检测配置需求** - 识别需要 API keys、tokens、secrets、OAuth 等的 skills
3. **分类整理** - 按配置类型分类（API key、OAuth、环境变量等）
4. **生成报告** - 输出清晰的配置清单和操作步骤

## 使用方法

### 快速扫描
```bash
python3 ~/clawd/skills/skill-config-checker/scripts/check_configs.py
```

### 详细报告
```bash
python3 ~/clawd/skills/skill-config-checker/scripts/check_configs.py --verbose
```

### 只检查特定 agent
```bash
python3 ~/clawd/skills/skill-config-checker/scripts/check_configs.py --agent code
```

## 输出格式

报告包含以下部分：

### ✅ 已配置的 Skills
列出已经有 API key 或 token 的 skills

### ⚠️ 需要配置的 Skills
列出缺少配置的 skills，包括：
- Skill 名称
- 需要的配置项
- 如何获取配置
- 配置步骤

### 🔐 需要 OAuth 授权的 Skills
列出需要 OAuth 授权的 skills，包括：
- Skill 名称
- 授权方式
- 授权链接

### 🆓 无需配置的 Skills
列出不需要任何配置即可使用的 skills

## 配置类型

| 类型 | 示例 | 存储位置 |
|------|------|---------|
| **API Key** | `OPENAI_API_KEY` | 环境变量 / `pass` |
| **OAuth Token** | Google OAuth | Rube MCP / credentials.json |
| **App Credentials** | `app_id` + `app_secret` | `pass show api/<service>` |
| **Environment Variables** | `GEMINI_API_KEY` | `~/.bashrc` / `.env` |

## 常见配置模式

### 1. Rube MCP (推荐)
适用于：Twitter, Gmail, Google Calendar 等
- 无需 API key
- 只需一次性 OAuth 授权
- 授权链接由我提供

### 2. Pass Store (推荐)
适用于：所有 API keys
- `pass show api/<service>` 获取
- 安全存储
- 自动轮换

### 3. 环境变量
适用于：模型 API keys
- `export GEMINI_API_KEY="xxx"`
- 添加到 `~/.bashrc` 持久化

## 触发词

- "检查 skill 配置"
- "哪些 skill 需要配置"
- "skill 配置清单"
- "API key 需求"
- "配置需求扫描"
- "检查 skills 配置需求"

## 示例输出

```
📋 Skills 配置需求总览

✅ 已配置的 Skills (12)
  - tavily (data, research)
  - firecrawl (data)
  - feishu-automation (多个)

⚠️ 需要配置的 Skills (5)
  1. deep-research (research)
     - 需要: GEMINI_API_KEY
     - 获取: https://aistudio.google.com/
     - 配置: export GEMINI_API_KEY="your-key"

🔐 需要 OAuth 授权的 Skills (2)
  - twitter-automation (market)
    - 授权: Rube MCP → Twitter OAuth
    - 链接: [待生成]

🆓 无需配置的 Skills (8)
  - multi-search-engine (research)
  - github-automation (code)
```

## 脚本位置

```
~/clawd/skills/skill-config-checker/
├── SKILL.md              # 本文件
└── scripts/
    └── check_configs.py  # 扫描脚本
```

## 更新日志

- 2026-03-06: v1.0.0 初始版本
