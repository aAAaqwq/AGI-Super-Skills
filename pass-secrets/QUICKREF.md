# Pass 密钥管理快速参考

## 当前存储的密钥

| 路径 | 用途 |
|------|------|
| `api/openrouter-vip` | OpenRouter VIP API Key |
| `api/zai` | 智谱 AI (GLM) API Key |
| `api/anapi` | Anapi Claude API Key |
| `tokens/telegram-bot` | Telegram Bot Token |
| `tokens/github-copilot` | GitHub Copilot Token |

## 常用命令

```bash
# 查看所有密钥
pass

# 获取密钥
pass api/zai

# 复制到剪贴板
pass -c api/zai

# 添加新密钥
pass insert api/new-service

# 编辑密钥
pass edit api/zai

# 删除密钥
pass rm api/old

# 搜索
pass find openai

# Git 同步
pass git pull
pass git push
```

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/setup-pass-git.sh` | 设置 GitHub 同步 |
| `scripts/start-openclaw.sh` | 从 Pass 加载密钥启动 OpenClaw |
| `scripts/list-secrets.sh` | 列出所有密钥（脱敏） |

## 与 OpenClaw 集成

```bash
# 方式1: 使用启动脚本
~/clawd/skills/pass-secrets/scripts/start-openclaw.sh

# 方式2: 手动导出
export ZAI_API_KEY=$(pass api/zai)
export OPENROUTER_VIP_API_KEY=$(pass api/openrouter-vip)
openclaw gateway

# 方式3: 添加到 .bashrc
alias oc='ZAI_API_KEY=$(pass api/zai) OPENROUTER_VIP_API_KEY=$(pass api/openrouter-vip) openclaw gateway'
```

## GPG 密钥信息

- **Key ID**: `5F845B8E1B6C5C52`
- **User**: DL <2067089451@qq.com>
- **有效期**: 至 2028-04-14

## 备份 GPG 密钥

```bash
# 导出私钥（安全保存！）
gpg --export-secret-keys --armor 2067089451@qq.com > ~/gpg-private-key.asc

# 导出公钥
gpg --export --armor 2067089451@qq.com > ~/gpg-public-key.asc
```

## 新设备恢复

```bash
# 1. 导入 GPG 私钥
gpg --import gpg-private-key.asc

# 2. 信任密钥
gpg --edit-key 5F845B8E1B6C5C52
# 输入: trust -> 5 -> quit

# 3. 克隆仓库
git clone git@github.com:用户名/password-store.git ~/.password-store
```
