---
name: openclaw-quick-deploy
description: "通过 SSH 远程快速复刻部署 OpenClaw 系统到 Mac 电脑。Use when: (1) 用户要求在新 Mac 上部署 OpenClaw, (2) 远程搭建/复刻 OpenClaw 运行环境, (3) 从 openclaw-team 仓库克隆 Agent 军团配置, (4) 配置 DeepSeek 或其他模型为默认模型, (5) 任何涉及 SSH 加 OpenClaw 部署的任务."
---

# OpenClaw Quick Deploy

通过 SSH 在远程 Mac 上快速部署完整的 OpenClaw 系统，包括 Agent 军团配置和模型配置。

## Prerequisites

部署前需确保：

- **控制端**：已通过 `ssh-copy-id` 将公钥添加到目标机器
- **目标 Mac**：`系统设置 → 通用 → 共享 → 远程登录` 已开启
- **目标 Mac**：已安装 Node.js（推荐 v24+）和 npm、git
- **秘钥**：持有 DeepSeek API Key（或其他模型）

## Workflow

部署分 5 步，由 `scripts/deploy.sh` 自动完成：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 连通性检查 | 验证 SSH 可达 |
| 2 | 安装 OpenClaw | npm 全局安装最新版 openclaw |
| 3 | 克隆 workspace | `git clone openclaw-team` → `~/.openclaw/workspace` |
| 4 | 部署 Agent 配置 | 从仓库复制 AGENTS.md / SOUL.md 等配置 |
| 5 | 配置模型 | 设默认模型和 API Key |

## Usage

### 快速执行

```bash
bash scripts/deploy.sh <user@host> <api-key>
```

**示例**：

```bash
# 使用默认 DeepSeek 模型
bash scripts/deploy.sh daniel@mac-m4-daniel sk-2312xxxx

# 指定其他模型
bash scripts/deploy.sh peter@192.168.1.100 sk-xxxx --model openai/gpt-4o --provider openai --base-url https://api.openai.com/v1

# 预览模式（不执行）
bash scripts/deploy.sh daniel@mac-m4-daniel sk-xxxx --dry-run
```

### 参数

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `<user@host>` | ✅ | — | SSH 目标，如 `daniel@mac-m4-daniel` 或 `user@192.168.1.100` |
| `<api-key>` | ✅ | — | API Key |
| `--model` | 否 | `deepseek/deepseek-v4-pro` | 模型 ID |
| `--provider` | 否 | `deepseek` | Provider 名称 |
| `--base-url` | 否 | `https://api.deepseek.com/v1` | API 地址 |
| `--workspace-repo` | 否 | openclaw-team 仓库 | Git 仓库 URL |
| `--dry-run` | 否 | false | 仅打印命令 |

### 手动分步执行

如果自动脚本不适用，可按以下步骤手动操作：

#### Step 1: 连接目标 Mac

```bash
ssh user@target-host
```

验证：`echo SSH_OK && uname -a`

#### Step 2: 安装 OpenClaw

```bash
npm install -g openclaw@latest
openclaw --version
```

如果没有 Node.js：

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.nvm/nvm.sh && nvm install v24
```

#### Step 3: 克隆 workspace

```bash
mkdir -p ~/.openclaw/workspace

# 备份已有内容
if [ -f ~/.openclaw/workspace/AGENTS.md ]; then
  cp -r ~/.openclaw/workspace ~/.openclaw/workspace.bak.$(date +%Y%m%d)
fi

rm -rf ~/.openclaw/workspace
git clone https://github.com/shenjj2025-oss/openclaw-team.git ~/.openclaw/workspace
```

#### Step 4: 部署 Agent 配置

根据仓库结构调整：

```bash
# 情况 A: 仓库根目录就是 workspace → 无需操作
# 情况 B: 仓库有 workspace/ 子目录
cp -r ~/.openclaw/workspace/workspace/* ~/.openclaw/workspace/
# 情况 C: 仓库有 agents/ 目录
cp -r ~/.openclaw/workspace/agents/* ~/.openclaw/workspace/
```

#### Step 5: 配置默认模型

```bash
openclaw config set agents.defaults.modelPrimary 'deepseek/deepseek-v4-pro'
openclaw config set models.providers.deepseek.baseUrl 'https://api.deepseek.com/v1'
openclaw config set models.providers.deepseek.apiKey 'sk-xxxx'
openclaw config set agents.defaults.defaultAgent 'main'
```

首次启动：

```bash
openclaw gateway restart
openclaw onboard   # 可选：配置 Telegram 等 channel
```

## Post-Deployment Checklist

- [ ] `openclaw status` 显示网关正常运行
- [ ] workspace 下 AGENTS.md / SOUL.md 存在且内容正确
- [ ] 模型配置生效（可发送测试消息）
- [ ] Agent 军团各子 Agent 配置就绪

## Troubleshooting

### SSH 连接失败

```bash
# 检查连通性
ssh -v user@host

# 确认目标机器 Remote Login 已开
# macOS: 系统设置 → 通用 → 共享 → 远程登录

# 确认公钥已复制
ssh-copy-id user@host
```

### openclaw 命令找不到

```bash
# 查找 openclaw
npm list -g --depth=0 | grep openclaw

# nvm 环境下需要
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
```

### git clone 失败

```bash
# 国内网络可尝试代理
git clone https://github.com/shenjj2025-oss/openclaw-team.git ~/.openclaw/workspace
# 或下载 zip 手动解压
```

### 模型不生效

```bash
openclaw config get agents.defaults.modelPrimary
openclaw gateway restart
```
