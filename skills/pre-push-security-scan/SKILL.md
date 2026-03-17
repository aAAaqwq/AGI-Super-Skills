---
name: pre-push-security-scan
description: "【铁律】Git push 前必须执行的安全扫描。防止 API keys、tokens、passwords、私钥等敏感信息被推送到远程仓库。适用于所有 git push、gh pr create、代码同步等场景。"
metadata:
  openclaw:
    emoji: "🔒"
    triggers:
      - "git push"
      - "push to github"
      - "push to remote"
      - "sync to github"
      - "gh pr create"
      - "推送代码"
      - "同步仓库"
      - "push 代码"
---

# 🔒 Pre-Push Security Scan（铁律）

> **2026-03-04 教训**：AGI-Super-Skills 仓库推送时未扫描，导致飞书 App Secret、Gateway Token、Telegram Bot Token、SSH 密码等 12 个真实密钥泄露到公开 Git 历史。事后用 git-filter-repo 清理 + 全部轮换，代价极大。
>
> **此后，任何 git push 操作前，必须执行本 Skill 的扫描流程。无例外。**

## 触发条件

以下操作 **必须** 先执行安全扫描：
- `git push`（任何分支）
- `git push --force`
- `gh pr create`
- 任何代码同步到远程仓库的操作
- cron 自动同步任务

## 扫描流程（三层检查）

### Layer 1: 扫描当前暂存区 / 待推送的 diff

```bash
# 获取待推送的 commits（与远程对比）
git log --oneline @{u}..HEAD 2>/dev/null || git log --oneline -5

# 扫描 diff 中的敏感模式
git diff @{u}..HEAD 2>/dev/null | grep -inE \
  '(api[_-]?key|secret|token|password|passwd|credential|private[_-]?key|auth)' \
  | grep -v 'REDACTED\|YOUR_.*_HERE\|placeholder\|example\|TODO\|xxx' \
  | head -30
```

### Layer 2: 扫描当前工作目录全部文件

```bash
# 高危模式匹配（排除 .git 目录和已知安全占位符）
grep -rnI --include='*.json' --include='*.md' --include='*.yaml' --include='*.yml' \
  --include='*.sh' --include='*.py' --include='*.js' --include='*.ts' --include='*.env' \
  --include='*.toml' --include='*.conf' --include='*.cfg' \
  -E '(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|xoxb-|xoxp-|AIza[a-zA-Z0-9_-]{35}|AKIA[A-Z0-9]{16})' \
  . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=venv \
  | grep -v 'REDACTED\|YOUR_.*_HERE\|placeholder\|example\|sk-xxx' \
  | head -30

# pass 路径中的密钥值（从 pass store 提取已知密钥进行比对）
# 仅在有 pass 的环境下执行
if command -v pass &>/dev/null; then
  for key_path in api/your-provider api/your-provider api/firecrawl api/deepseek api/your-provider; do
    key_val=$(pass show "$key_path" 2>/dev/null | head -1)
    if [ -n "$key_val" ] && [ ${#key_val} -gt 8 ]; then
      found=$(grep -rnl "$key_val" . --exclude-dir=.git 2>/dev/null)
      if [ -n "$found" ]; then
        echo "🚨 LEAKED: $key_path found in: $found"
      fi
    fi
  done
fi
```

### Layer 3: 扫描 Git 历史中新增的敏感内容

```bash
# 扫描最近 N 个 commits 的完整 patch
git log -p -10 2>/dev/null | grep -inE \
  '^\+.*(api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]' \
  | grep -v 'REDACTED\|YOUR_.*_HERE\|placeholder\|example' \
  | head -20
```

## 判定标准

| 结果 | 动作 |
|------|------|
| Layer 1-3 全部 0 匹配 | ✅ 安全，可以 push |
| 任何一层有匹配 | ❌ **停止 push**，逐条检查 |
| 匹配项为占位符/示例 | ✅ 确认后可以 push |
| 匹配项为真实密钥 | 🚨 **立即移除**，替换为 `pass show` 或占位符 |

## 发现泄露后的修复流程

```bash
# 1. 安装 git-filter-repo
pip install --user --break-system-packages git-filter-repo

# 2. 创建替换文件（每行格式: 真实密钥==>REDACTED_描述）
cat > /tmp/replacements.txt << 'EOF'
actual_secret_value==>REDACTED_SERVICE_NAME
EOF

# 3. 在仓库 clone 中执行替换
git filter-repo --replace-text /tmp/replacements.txt --force

# 4. Force push
git remote add origin <repo-url>
git push --force --all

# 5. 轮换所有已泄露的密钥（最重要！清理历史只防未来，已泄露的必须换）
```

## 已知敏感模式清单（持续更新）

```
# API Keys
sk-[a-zA-Z0-9]{20,}          # OpenAI/兼容格式
ghp_[a-zA-Z0-9]{36}          # GitHub PAT
ghu_[a-zA-Z0-9]{36}          # GitHub User Token
xoxb-                         # Slack Bot Token
xoxp-                         # Slack User Token
AIza[a-zA-Z0-9_-]{35}        # Google API Key
AKIA[A-Z0-9]{16}             # AWS Access Key

# 飞书
cli_[a-f0-9]{16}             # 飞书 App ID（单独不危险，但不应硬编码）
[a-zA-Z0-9]{32}              # 飞书 App Secret（需结合上下文判断）

# Telegram
[0-9]{8,10}:AA[a-zA-Z0-9_-]{33,35}  # Telegram Bot Token

# Gateway
[a-f0-9]{48}                  # OpenClaw Gateway Token（需结合上下文判断）

# 通用
password\s*[:=]\s*\S+
private_key\s*[:=]
-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----
```

## 自动化集成

### Git Hook（推荐）

在仓库 `.git/hooks/pre-push` 中添加自动扫描：

```bash
#!/bin/bash
# Pre-push hook: security scan
echo "🔒 Running pre-push security scan..."

ISSUES=$(git diff @{u}..HEAD 2>/dev/null | grep -icE \
  '(api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*["\x27]?[a-zA-Z0-9_-]{16,}' \
  2>/dev/null || echo 0)

if [ "$ISSUES" -gt 0 ]; then
  echo "🚨 Found $ISSUES potential secret(s) in push. Aborting."
  echo "Run security scan skill for details."
  exit 1
fi

echo "✅ No secrets detected. Proceeding with push."
```

### Cron 同步任务

所有自动同步 cron 任务（如 AGI-Super-Skills 同步）**必须**在 push 前集成 Layer 1 + Layer 2 扫描。

## 历史教训

| 日期 | 事件 | 影响 | 修复成本 |
|------|------|------|----------|
| 2026-02-05 | 公开仓库硬编码 API key | 密钥泄露 | 轮换密钥 |
| 2026-03-04 | AGI-Super-Skills 推送 12 个真实密钥 | 飞书/TG/Gateway/SSH 全部泄露 | git-filter-repo + 全部轮换 |

**两次教训，不允许有第三次。**
