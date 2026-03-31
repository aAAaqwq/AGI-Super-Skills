---
name: auth-manager
description: "网页登录态管理。使用 OpenClaw 内置 browser (profile=openclaw) 统一管理各平台登录状态，定期检查可用性。"
license: MIT
metadata:
  version: 4.0.0
  domains: [auth, browser, session-management]
  type: automation
author: Daniel Li
---

# Auth Manager v4.0 — 平台登录态管理

> **统一使用 OpenClaw 内置 browser (profile=openclaw)**，所有平台共享同一个 Chrome profile。
> ⚠️ **禁止使用 fbu / fast-browser-use**，已废弃。

## 架构 — 单一 Profile 模型

```
~/.openclaw/browser/openclaw/user-data/   ← 唯一的 Chrome profile（内置 browser）
~/.openclaw/auth-platforms.json           ← 平台配置
~/.openclaw/auth-session-state.json       ← 检查结果状态
```

**为什么统一？**
- 所有 agent（quant/ops/main 等）共享同一 browser profile
- 一次登录，全部可用。不存在"这个 agent 没登录"的问题
- OAuth 链式登录（如Provider-A 依赖 GitHub）自动继承

## 核心职责

### 职责 1: 检查登录态（定期 cron）

**优先级：curl/CLI > 内置 browser**

#### 方法 A: curl/CLI 检查（快速、不占资源）

```bash
# GitHub — 最可靠
gh auth status 2>&1

# AIXN — curl API
TOKEN=$(python3 -c "import json; print(json.load(open('/home/aa/.openclaw/chrome-profiles/provider-session.json')).get('token',''))" 2>/dev/null)
curl -s --max-time 10 'https://ai.9w7.cn/api/user/info' -H "Authorization: Bearer $TOKEN"

# Provider-A — curl
COOKIE=$(python3 -c "import json; print(json.load(open('/home/aa/.openclaw/chrome-profiles/your-provider-session.json')).get('cookie',''))" 2>/dev/null)
curl -s --max-time 10 'https://your-provider.example.com/api/user/info' -H "Cookie: $COOKIE"
```

#### 方法 B: 内置 browser 检查（需要渲染的站点）

```
# 导航到目标页面
browser(action='navigate', targetUrl='<check_url>', profile='openclaw')

# 等待加载后截取快照
browser(action='snapshot', compact=true, maxChars=2000, profile='openclaw')
```

适用平台：Polymarket、LinuxDo、X、抖音、小红书

**判定逻辑：**
- 快照包含 `logged_in_indicators` 关键词 → ✅ `active`
- 快照包含 `login_page_indicators` 关键词 → ❌ `expired`
- 超时/网络错误 → ⚠️ `error`（不是 expired！区分清楚）

### 职责 2: 新平台授权

当需要为新平台登录时：

```
# 1. 用内置 browser 打开登录页
browser(action='navigate', targetUrl='https://platform.com/login', profile='openclaw')

# 2. 截图给用户确认页面
browser(action='screenshot', profile='openclaw')

# 3. 如果需要用户操作（扫码等），等待用户确认后再 snapshot 验证
browser(action='snapshot', compact=true, profile='openclaw')
```

登录成功后，cookie/localStorage/IndexedDB 自动保存在 `~/.openclaw/browser/openclaw/user-data/`。

### 职责 3: 其他 agent 使用登录态

**所有 agent 调用内置 browser 时自动继承登录态：**

```
# quant agent 访问 polymarket — 自动已登录
browser(action='navigate', targetUrl='https://polymarket.com', profile='openclaw')

# ops agent 检查 github — 自动已登录
browser(action='navigate', targetUrl='https://github.com', profile='openclaw')
```

无需任何额外配置。profile=openclaw 是共享的。

## 平台配置

`~/.openclaw/auth-platforms.json`:

```json
{
  "platforms": {
    "platform_id": {
      "name": "显示名称",
      "check_url": "https://example.com/dashboard",
      "login_url": "https://example.com/login",
      "check_method": "browser|curl|cli",
      "logged_in_indicators": ["关键词1", "关键词2"],
      "login_page_indicators": ["登录", "Sign in"],
      "enabled": true
    }
  }
}
```

## 已知平台特性（9个）

| 平台 | 检查方式 | 登录方式 | 账号 | 备注 |
|------|----------|----------|------|------|
| GitHub | `gh auth status` (CLI) | 账密/OAuth | aAAaqwq | 最可靠 |
| AIXN | curl API | 账密 | 2067089451@qq.com | session.json token |
| Provider-A | curl API | GitHub OAuth | github_210817 | 依赖 GitHub 登录态 |
| Polymarket | 内置 browser | 钱包/OAuth | Portfolio $41.62 | 检查"portfolio"关键词 |
| LinuxDo | 内置 browser | 账密/OAuth | aaqwqaa68 | Cloudflare 站点 |
| X (Twitter) | 内置 browser | 账密 | @Daniel_Li666 | 可能有验证码 |
| 小红书 | 内置 browser | App扫码/手机号 | 69464fc5... | check: xiaohongshu.com/user/profile/me |
| Reddit | 内置 browser | 账密/OAuth | Jealous-Carrot-9574 | reCAPTCHA 需人工通过 |
| 抖音创作者 | 内置 browser | App扫码 | aa (61747337251) | check: creator.douyin.com/creator-micro/home |

## 状态文件格式

`~/.openclaw/auth-session-state.json`:
```json
{
  "checkedAt": "2026-03-07T09:00:00+08:00",
  "platforms": {
    "github": { "status": "active", "account": "aAAaqwq", "method": "cli" },
    "polymarket": { "status": "active", "detail": "Portfolio $41.56", "method": "browser" }
  }
}
```

status 值: `active` | `expired` | `error`

## Cron 任务

- **Auth 检查 cron**: `1f2eb5a5` — 每天 09:00/21:00 执行
- 过期则推送告警到 DailyNews 群
- 全部正常则静默

## 铁律 ⚠️

1. **禁止使用 fbu / fast-browser-use** — 已废弃
2. **统一使用 `profile='openclaw'`** — 所有 browser 操作
3. **旧 profile 目录 `~/.openclaw/chrome-profiles/<platform>/` 已废弃**，仅保留 session.json 供 curl 读取 token/cookie
4. **超时 ≠ 过期** — 网络问题标记为 error，不标记为 expired
5. **每个检查最多 15 秒** — 避免阻塞

## 迁移说明（v3 → v4）

- 旧版：每个平台独立 fbu Chrome profile (`~/.openclaw/chrome-profiles/<platform>/`)
- 新版：所有平台共享内置 browser profile (`~/.openclaw/browser/openclaw/user-data/`)
- 内置 browser 已有全部平台的 IndexedDB/cookie 数据，无需手动迁移
- 旧 `chrome-profiles/` 目录已于 2026-03-07 彻底删除（释放 ~1.7GB）
- 旧 `<platform>-session.json` 文件也已删除（token 已过期）
