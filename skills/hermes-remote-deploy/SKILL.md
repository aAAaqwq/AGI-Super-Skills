---
name: hermes-remote-deploy
description: "通过 SSH 远程部署 Hermes Agent（Nous Research 自进化 AI Agent）到 Linux/macOS 服务器。Use when: (1) 用户要求在远程服务器上部署 Hermes Agent, (2) 远程搭建 Hermes 运行环境, (3) 配置 Hermes 模型提供商和 API Key, (4) 从 OpenClaw 迁移到 Hermes, (5) 任何涉及 SSH 加 Hermes 部署的任务。"
---

# Hermes Remote Deploy

通过 SSH 在远程 Linux/macOS 服务器上快速部署 Hermes Agent —— Nous Research 出品的自进化 AI Agent，内置学习循环、多平台网关、技能系统。

> **Hermes 是什么**：不是绑在 IDE 里的编程副驾驶，也不是单个 API 的聊天壳。它是一个运行在你服务器上的自主 Agent，记住所学，越用越强。支持 Docker / SSH / Modal / Daytona / Vercel Sandbox 等多种终端后端，通过 Telegram / Discord / Slack / WhatsApp / Signal 等多平台接入。

## Prerequisites

部署前需确保：

- **控制端**：已通过 `ssh-copy-id` 将公钥添加到目标机器
- **目标机器**：Linux (Ubuntu/Debian/CentOS) 或 macOS，SSH 服务已开启
- **目标机器**：已安装 curl、git（基本工具）
- **秘钥**：持有至少一个模型提供商的 API Key（如 DeepSeek / OpenAI / Anthropic / OpenRouter 等）
- **网络**：目标机器可访问 GitHub（`github.com`）和 PyPI（`pypi.org`）

> **注意**：安装脚本会自动安装 Python 3.11、Node.js 22、uv、ripgrep、ffmpeg 等全部依赖，无需手动预装。

## Workflow

部署分 5 步，由 `scripts/deploy.sh` 自动完成：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 连通性检查 | 验证 SSH 可达，检测目标系统类型 |
| 2 | 安装 Hermes | curl 一键安装脚本，自动处理所有依赖 |
| 3 | 配置模型 | `hermes config set` 配置 Provider 和 API Key |
| 4 | 配置身份 | 可选：部署 SOUL.md 和 AGENTS.md |
| 5 | 验证 | `hermes doctor` 诊断 + `hermes --version` |

## Usage

### 快速执行

```bash
bash scripts/deploy.sh <user@host> <provider> <api-key>
```

**示例**：

```bash
# DeepSeek 作为默认模型
bash scripts/deploy.sh daniel@my-vps-01 deepseek sk-2312xxxx

# OpenAI
bash scripts/deploy.sh daniel@my-vps-01 openai sk-proj-xxxx --model openai/gpt-4o

# Anthropic
bash scripts/deploy.sh daniel@192.168.1.100 anthropic sk-ant-xxxx

# OpenRouter (支持 200+ 模型)
bash scripts/deploy.sh daniel@my-vps-01 openrouter sk-or-v1-xxxx --model openrouter/anthropic/claude-sonnet-4

# 预览模式（不执行）
bash scripts/deploy.sh daniel@my-vps-01 deepseek sk-xxxx --dry-run

# 跳过 Gateway 配置（纯 CLI 模式）
bash scripts/deploy.sh daniel@my-vps-01 deepseek sk-xxxx --skip-gateway
```

### 参数

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `<user@host>` | ✅ | — | SSH 目标，如 `root@my-vps` 或 `user@192.168.1.100` |
| `<provider>` | ✅ | — | Provider 名称：`deepseek` / `openai` / `anthropic` / `openrouter` / `nous` |
| `<api-key>` | ✅ | — | 对应 Provider 的 API Key |
| `--model` | 否 | Provider 默认模型 | 模型 ID（如 `deepseek/deepseek-v4-pro`） |
| `--skip-gateway` | 否 | false | 跳过 Gateway 配置，仅部署 CLI |
| `--soul-path` | 否 | — | 本地 SOUL.md 路径，部署到远程 |
| `--branch` | 否 | `main` | Hermes 安装分支 |
| `--dry-run` | 否 | false | 仅打印命令，不实际执行 |

### Provider 默认模型

| Provider | 默认模型 | API Key 环境变量 |
|----------|----------|-----------------|
| `deepseek` | `deepseek/deepseek-v4-pro` | `DEEPSEEK_API_KEY` |
| `openai` | `openai/gpt-4o` | `OPENAI_API_KEY` |
| `anthropic` | `anthropic/claude-sonnet-4` | `ANTHROPIC_API_KEY` |
| `openrouter` | `openrouter/anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| `nous` | `nous/hermes-3-70b` | `NOUS_API_KEY` |

### 手动分步执行

如果自动脚本不适用，可按以下步骤手动操作：

#### Step 1: 连接目标机器

```bash
ssh user@target-host
```

验证：`echo SSH_OK && uname -a`

#### Step 2: 安装 Hermes

```bash
# 一键安装（国内可先设置代理）
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# 或指定分支
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --branch main
```

安装完成后重载 Shell：

```bash
source ~/.bashrc  # 或 source ~/.zshrc
hermes --version
```

> **国内网络提示**：如果 GitHub 访问慢，可先设置代理 `export https_proxy=http://proxy:port`，或在有代理的机器上下载后 scp 传输。

#### Step 3: 配置模型 Provider

```bash
# 设置模型（API key 自动存入 ~/.hermes/.env）
hermes config set model deepseek/deepseek-v4-pro
hermes config set DEEPSEEK_API_KEY sk-xxxx

# 查看当前配置
hermes config
```

支持的所有 Provider 和配置方式见[官方文档](https://hermes-agent.nousresearch.com/docs/integrations/providers)。

#### Step 4: 运行交互式设置（可选但推荐）

```bash
hermes setup
```

交互式向导会引导你完成：
- 模型提供商选择
- 工具启用/禁用
- Gateway 平台连接（Telegram / Discord / Slack 等）
- 记忆系统偏好

#### Step 5: 配置身份和上下文文件（可选）

```bash
# 部署 SOUL.md（Agent 人格）
cat > ~/.hermes/SOUL.md << 'EOF'
# Your Agent Identity
...
EOF

# 部署 MEMORY.md（跨会话记忆）
mkdir -p ~/.hermes/memories
cat > ~/.hermes/memories/MEMORY.md << 'EOF'
# Memory
...
EOF
```

#### Step 6: 启动和验证

```bash
# 诊断检查
hermes doctor

# 启动 CLI 聊天
hermes

# 启动 Gateway（多平台接入）
hermes gateway setup   # 首次配置
hermes gateway start   # 启动
```

## From OpenClaw Migration

如果目标机器已有 OpenClaw，Hermes 支持一键迁移：

```bash
# 交互式迁移（自动检测 ~/.openclaw）
hermes claw migrate

# 预览模式
hermes claw migrate --dry-run

# 仅迁移用户数据（不含密钥）
hermes claw migrate --preset user-data
```

迁移内容包括：SOUL.md、MEMORY.md、USER.md、Skills、API Keys。

## Post-Deployment Checklist

- [ ] `hermes --version` 输出版本号
- [ ] `hermes doctor` 无严重报错
- [ ] `hermes config` 显示正确的模型配置
- [ ] 可正常启动 CLI 对话：`hermes`
- [ ] （可选）Gateway 平台连接正常
- [ ] （可选）SOUL.md / MEMORY.md 内容正确

## Troubleshooting

### SSH 连接失败

```bash
# 检查连通性
ssh -v user@host

# 确认目标机器 SSH 服务已开
# Linux: systemctl status sshd
# macOS: 系统设置 → 通用 → 共享 → 远程登录

# 确认公钥已复制
ssh-copy-id user@host
```

### 安装脚本下载失败

```bash
# 国内网络可尝试
export https_proxy=http://your-proxy:port
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# 或手动克隆
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
uv sync --extra all
```

### hermes 命令找不到

```bash
# 重载 shell 配置
source ~/.bashrc  # 或 source ~/.zshrc

# 检查 PATH
echo $PATH | grep hermes

# 手动添加（安装脚本通常自动处理）
export PATH="$HOME/.hermes/hermes-agent/.venv/bin:$PATH"
```

### 模型 API 调用失败

```bash
# 检查 API Key 配置
hermes config | grep -i key

# 测试连接
hermes doctor

# 手动设置 API Key
hermes config set DEEPSEEK_API_KEY sk-xxxx
# 或直接编辑 .env
vim ~/.hermes/.env
```

### 国内环境特殊处理

```bash
# 设置 uv 镜像
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 设置 npm 镜像
export NPM_CONFIG_REGISTRY=https://registry.npmmirror.com

# 或在安装脚本前设置
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | \
  env UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple bash
```

## Directory Structure (Post-Deploy)

```
~/.hermes/
├── config.yaml        # 主配置文件
├── .env               # API Keys 和密钥
├── auth.json          # OAuth 凭证
├── SOUL.md            # Agent 人格定义
├── memories/          # 跨会话记忆
│   ├── MEMORY.md
│   └── USER.md
├── skills/            # Agent 自创技能
├── cron/              # 定时任务
├── sessions/          # Gateway 会话
└── logs/              # 日志
```

## 与 OpenClaw 部署的对比

| 维度 | Hermes | OpenClaw |
|------|--------|----------|
| 语言栈 | Python 3.11 + Node.js 22 | Node.js |
| 包管理 | uv (Python) + npm (Node) | npm |
| 安装方式 | curl pipe bash | npm install -g |
| 配置方式 | `hermes config set` | `openclaw config set` |
| 配置目录 | `~/.hermes/` | `~/.openclaw/` |
| Gateway | 内置（Telegram/Discord/Slack/WhatsApp/Signal） | 内置 |
| 终端后端 | 7 种（local/docker/ssh/modal/daytona/vercel/singularity） | local |
| 学习循环 | ✅ 内置技能系统 + 记忆系统 | Skills 系统 |
| 迁移支持 | ✅ `hermes claw migrate` | — |
