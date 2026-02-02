# AGI Skills 通用技能库

> 🌟 **一套技能，多平台通用** - 无论你使用 Claude Code、Codex、OpenClaw 还是其他 AI IDE，都可以快速同步和使用这些技能。

## 概述

这是一个 **AGI 通用技能库**，包含 60+ 个精心设计的技能（Skills），涵盖开发、自动化、文档处理、AI 集成等多个领域。

### 核心特性

- 🔄 **跨平台兼容** - 支持 Claude Code、Codex CLI、OpenClaw、Pi Coding Agent 等
- 📦 **一键同步** - 使用 `env-setup` skill 快速同步到任何新环境
- 🔐 **安全管理** - 使用 `pass-secrets` skill 统一管理所有 API 密钥
- 🛠️ **模块化设计** - 每个 skill 独立，按需使用

## 快速开始

### 方式 1: 克隆到本地

```bash
# Claude Code
git clone https://github.com/aAAaqwq/cc-skills.git ~/.claude/skills

# OpenClaw
git clone https://github.com/aAAaqwq/cc-skills.git ~/clawd/skills

# Codex CLI
git clone https://github.com/aAAaqwq/cc-skills.git ~/.codex/skills
```

### 方式 2: 使用 env-setup 一键同步

```bash
# 运行同步脚本
python skills/env-setup/scripts/sync_env.py --target all
```

## 技能分类

### 🔧 开发工具

| Skill | 描述 |
|-------|------|
| `backend-development` | 后端开发（Python/Node.js/Go） |
| `frontend-development` | 前端开发（React/Vue/Tailwind） |
| `electron-app-dev` | Electron 桌面应用开发 |
| `docker-deployment` | Docker 容器部署 |
| `webapp-testing` | Web 应用测试 |

### 🤖 AI 集成

| Skill | 描述 |
|-------|------|
| `mcp-builder` | MCP 服务器开发 |
| `mcp-installer` | MCP 工具安装 |
| `mcp-manager` | MCP 服务管理 |
| `model-fallback` | 模型自动降级切换 |
| `api-provider-setup` | API 供应商配置 |

### 📄 文档处理

| Skill | 描述 |
|-------|------|
| `docx` | Word 文档处理 |
| `xlsx` | Excel 表格处理 |
| `pptx` | PowerPoint 演示文稿 |
| `pdf` | PDF 文档处理 |
| `docx-perfect` | Word 文档美化 |

### 🔄 自动化

| Skill | 描述 |
|-------|------|
| `n8n-workflow-automation` | n8n 工作流自动化 |
| `github-automation` | GitHub 自动化 |
| `chrome-automation` | Chrome 浏览器自动化 |
| `feishu-automation` | 飞书自动化 |
| `notion-automation` | Notion 自动化 |

### 🔐 安全与配置

| Skill | 描述 |
|-------|------|
| `pass-secrets` | Pass 密钥管理 |
| `openclaw-config` | OpenClaw 配置规范 |
| `env-setup` | 环境一键同步 |
| `permission-manager` | 权限管理 |

### 📱 通道集成

| Skill | 描述 |
|-------|------|
| `feishu-channel` | 飞书通道集成 |
| `wechat-channel` | 微信通道集成 |
| `news-daily` | 每日新闻推送 |

### 🎨 设计与创意

| Skill | 描述 |
|-------|------|
| `frontend-design` | 前端设计 |
| `canvas-design` | Canvas 设计 |
| `algorithmic-art` | 算法艺术 |
| `uml-diagram-design` | UML 图表设计 |
| `theme-factory` | 主题工厂 |

## 平台支持

### Claude Code

```bash
# 安装位置
~/.claude/skills/

# 配置文件
~/.claude.json
~/.claude/CLAUDE.md
```

### OpenClaw

```bash
# 安装位置
~/clawd/skills/
~/.openclaw/agents/main/agent/

# 配置文件
~/.openclaw/openclaw.json
```

### Codex CLI

```bash
# 安装位置
~/.codex/skills/

# 配置文件
~/.codex/config.json
```

### Pi Coding Agent

```bash
# 安装位置
~/.pi/skills/

# 配置文件
~/.pi/config.json
```

## 环境同步

使用 `env-setup` skill 可以一键同步：

- ✅ Skills 技能库
- ✅ 全局提示词（CLAUDE.md / AGENTS.md）
- ✅ MCP 服务器配置
- ✅ Output Styles 风格
- ✅ API 密钥（通过 Pass）

详见 [env-setup/SKILL.md](./env-setup/SKILL.md)

## 密钥管理

使用 `pass-secrets` skill 统一管理所有 API 密钥：

```bash
# 查看所有密钥
pass ls

# 获取密钥
pass api/openai

# 添加密钥
pass insert api/new-service
```

详见 [pass-secrets/SKILL.md](./pass-secrets/SKILL.md)

## 贡献指南

### 添加新 Skill

1. 创建目录：`skills/your-skill-name/`
2. 创建 `SKILL.md`（必需）
3. 添加 `scripts/`（可选）
4. 更新本 README

### Skill 结构

```
your-skill-name/
├── SKILL.md          # 主文档（必需）
├── QUICKREF.md       # 快速参考（可选）
├── README.md         # 说明文档（可选）
├── scripts/          # 脚本目录（可选）
│   └── *.sh / *.py
└── config/           # 配置模板（可选）
```

## 更新日志

### 2026-02-02

- 🆕 新增 `model-fallback` - 模型自动降级切换
- 🆕 新增 `openclaw-config` - OpenClaw 配置规范
- 🆕 新增 `pass-secrets` - Pass 密钥管理
- 🔄 更新 `env-setup` - 支持多平台同步
- 📝 更新 README - AGI 通用技能库定位

### 2026-02-01

- 🆕 新增 `feishu-channel` - 飞书通道集成
- 🆕 新增 `wechat-channel` - 微信通道集成
- 🆕 新增 `api-provider-setup` - API 供应商配置

## 许可证

MIT License

---

**🤖 由小a维护** - 朝着真正的 AGI 不断进化
