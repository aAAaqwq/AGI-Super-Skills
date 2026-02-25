---
name: auth-manager
description: "网页登录态管理。使用 fast-browser-use (fbu) 管理各平台登录状态，定期检查可用性，新平台授权时自动保存 profile。"
license: MIT
metadata:
  version: 3.1.0
  domains: [auth, fbu, session-management]
  type: automation
---

# Auth Manager v3.1 — 平台登录态管理

> 基于 fast-browser-use (fbu)，使用 `--user-data-dir` 保存完整 Chrome profile（cookies + localStorage + IndexedDB）。

## 环境配置（必须）

fbu 二进制在 `~/.cargo/bin/`，**每次执行前必须设置**：

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CHROME_PATH=/usr/bin/google-chrome
export DISPLAY=:1   # 桌面显示，headless false 时必须
```

## 核心职责

### 职责 1: 检查已保存 profile 可用性

定期对 `auth-platforms.json` 中所有 `enabled: true` 平台执行 snapshot 检查：

```bash
# 必须用 timeout 包裹，防止 Chrome 残留
timeout --kill-after=5 60 fast-browser-use snapshot \
  --url "<check_url>" \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform> || true
pkill -f "chrome.*--remote-debugging" 2>/dev/null || true
```

**判定逻辑：**
- DOM 包含 `logged_in_indicators` 关键词 → ✅ `active`
- DOM 包含 `login_page_indicators` 关键词 → ❌ `expired`
- 都不匹配 → ⚠️ `uncertain`
- 命令失败 → 🔴 `error`

**Cloudflare 站点**（如 linux.do）headless 模式会被拦截，需加 `--headless false`：
```bash
timeout --kill-after=5 90 fast-browser-use snapshot \
  --url "https://linux.do" \
  --user-data-dir ~/.openclaw/chrome-profiles/linuxdo \
  --headless false || true
pkill -f "chrome.*--remote-debugging" 2>/dev/null || true
```

结果写入 `~/.openclaw/auth-session-state.json`，过期/异常时推送告警。

### 职责 2: 新平台授权 — 自动保存 profile

当用户使用 fbu 授权新平台时，执行以下完整流程：

#### 步骤 1: 创建 profile 目录
```bash
mkdir -p ~/.openclaw/chrome-profiles/<platform>
```

#### 步骤 2: 打开桌面浏览器让用户登录
```bash
fast-browser-use login \
  --url "https://platform.com/login" \
  --headless false \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform> \
  --save-session ~/.openclaw/chrome-profiles/<platform>-session.json
```

> **关键参数说明：**
> - `--headless false` — 必须，在桌面打开可视 Chrome 窗口
> - `--save-session` — 必填参数（fbu login 要求），即使主要靠 user-data-dir 保存状态
> - `--user-data-dir` — 保存完整 Chrome profile
> - 浏览器打开后终端显示 "Press Enter after you have logged in..."
> - 用户登录完成后，agent 向进程写入换行符（Enter）触发保存

#### 步骤 3: 用户确认登录后发送 Enter
```python
# 使用 process write 向 fbu 进程发送 Enter
process.write(sessionId, "\n")
```

#### 步骤 4: 验证登录态
```bash
fast-browser-use snapshot \
  --url "<check_url>" \
  --user-data-dir ~/.openclaw/chrome-profiles/<platform>
```
检查 DOM 输出是否包含登录态关键词（用户名、余额、dashboard 等）。

#### 步骤 5: 更新配置文件
将新平台添加到 `auth-platforms.json`，包括 check_url、login_url、indicators 等。

#### 步骤 6: 更新状态文件
写入 `auth-session-state.json`。

## 文件结构

```
~/.openclaw/chrome-profiles/<platform>/   # fbu Chrome profile（完整状态）
~/.openclaw/auth-platforms.json           # 平台配置
~/.openclaw/auth-session-state.json       # 检查结果状态
```

## 平台配置格式

`~/.openclaw/auth-platforms.json`:
```json
{
  "platforms": {
    "platform_id": {
      "name": "显示名称",
      "profile_dir": "~/.openclaw/chrome-profiles/platform_id",
      "check_url": "https://example.com/dashboard",
      "login_url": "https://example.com/login",
      "logged_in_indicators": ["关键词1", "关键词2"],
      "login_page_indicators": ["登录", "Sign in"],
      "enabled": true,
      "credentials": {
        "username": "user@example.com",
        "password": "xxx"
      },
      "login_method": "github_oauth"
    }
  }
}
```

### 可选字段说明

- **credentials**：有账密的平台可存储凭据，profile 过期时 agent 可用 fbu navigate 自动填写表单重新登录
- **login_method**：登录方式说明（如 `github_oauth`、`qrcode`、`password`），帮助 agent 判断是否能自动登录

## 批量检查

遍历所有 enabled 平台，用 grep 匹配关键词快速判定：

```bash
# 批量检查示例（用 grep 匹配关键词）
for platform in polymarket aixn xingjiabiapi github douyin xiaohongshu linuxdo; do
  echo "=== $platform ==="
  fast-browser-use snapshot \
    --url "$(jq -r ".platforms.$platform.check_url" ~/.openclaw/auth-platforms.json)" \
    --user-data-dir ~/.openclaw/chrome-profiles/$platform 2>&1 \
    | grep -E "关键词" | head -5
done
```

## 已知平台特性

| 平台 | 登录方式 | Headless | 备注 |
|------|----------|----------|------|
| Polymarket | 钱包/OAuth | ✅ | 检查"资产组合"关键词 |
| AIXN (XAPI) | 账密 | ✅ | 有 credentials，可自动登录 |
| 性价比API | GitHub OAuth | ✅ | 需先有 GitHub 登录态 |
| GitHub | 账密 | ✅ | 检查 Settings 页面 |
| 抖音创作者 | 扫码 | ✅ | 必须用户手动扫码 |
| 小红书创作者 | 扫码 | ✅ | 必须用户手动扫码 |
| Linux Do | 账密/OAuth | ❌ 需 headless false | Cloudflare 拦截 headless |
| X (Twitter) | 账密 | ✅ | 可能有验证码 |

## 状态文件格式

`~/.openclaw/auth-session-state.json`:
```json
{
  "platforms": {
    "polymarket": {
      "status": "active",
      "message": "登录正常 ✅ (发现: 资产组合 $6.02)",
      "checkedAt": 1740000000
    }
  },
  "lastCheck": 1740000000
}
```

status 值: `active` | `expired` | `uncertain` | `error`

## Cron 任务

已配置定期自动检查（cron id: `1f2eb5a5-5c2e-4556-b006-e29325f41609`），过期则推送告警。

## 注意事项

1. **fbu login 必填参数**：`--url`、`--headless`、`--user-data-dir`、`--save-session` 四个缺一不可
2. **Profile 锁**：`--user-data-dir` 会锁定 profile，同一 profile 不能被多个 Chrome 实例同时使用
3. **Cloudflare 站点**：headless 被拦截时用 `--headless false`，但 snapshot 的 `--headless` 参数需要显式传 `false`
4. **OAuth 登录**（GitHub OAuth 等）：新 profile 里没有第三方登录态，需要用户在弹出页面登录第三方账号
5. **扫码登录**（抖音、小红书）：必须用户手动操作，agent 无法自动完成
6. **snapshot 验证**：新平台授权后务必 snapshot 验证一次，确认 profile 已正确保存
7. **超时设置**：fbu login 可能需要较长时间（用户操作），exec timeout 建议 ≥ 300s
