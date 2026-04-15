---
name: browser-profile-guide
description: OpenClaw Browser 配置文件系统完全指南 — 哪个 profile 何时用、如何选
trigger: browser profile / 浏览器配置 / openclaw browser / browser profile guide
---

# OpenClaw Browser Profile 完整指南

## 三种 Profile 用途速查

| Profile | 驱动 | 登录态 | 何时用 | 是否需要手动开浏览器 |
|---------|------|--------|--------|-------------------|
| `openclaw`（默认） | Playwright + Chrome CDP | ❌ 全新干净浏览器 | 自动化、批量操作、不需要登录 | ❌ 自动启动 |
| `user` | Playwright + Chrome CDP | ✅ 复用你已有的 Chrome 登录态 | 需要 GitHub/邮箱等已登录网站 | ✅ 需先手动开 Chrome |
| `sandbox` | Docker 内 Playwright | ❌ 隔离容器内全新浏览器 | 安全敏感操作 | ❌ 自动启动 |

## 你的当前配置（~/.openclaw/openclaw.json）

```json
"browser": {
  "headless": false,
  "noSandbox": true,
  "profiles": {
    "user": {
      "attachOnly": true,    // 只连接已开的浏览器，不自动启动
      "cdpPort": 9222,       // Chrome 远程调试端口
      "driver": "openclaw",
      "color": "#00AA00"
    }
  }
}
```

**注意**：`openclaw` profile 没有显式定义，但是**默认 profile**，OpenClaw 会自动创建。

## 默认 Profile：`openclaw`（最常用）

```javascript
browser(action="open", profile="openclaw", url="https://github.com")
browser(action="snapshot", profile="openclaw")
browser(action="act", profile="openclaw", ref="e1", kind="click")
```

- OpenClaw 自动管理浏览器生命周期
- 每次启动是干净的浏览器环境
- CDP 端口：18800（`openclaw profile`）

## `user` Profile — 复用已有登录态

**前置条件**：你必须先手动打开 Chrome 并启用远程调试

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome"

# Linux
google-chrome --remote-debugging-port=9222
```

**你的配置里 `user` profile 已设为 `attachOnly: true`**，意味着：
- 如果 Chrome 没开 → 不会自动启动 → 会报错
- Chrome 开着且端口 9222 在监听 → 自动连接

```javascript
// 需要登录 GitHub？用 user profile
browser(action="open", profile="user", url="https://github.com")
browser(action="snapshot", profile="user")
```

## 统一规则（你们团队所有人遵守）

```
任务需要登录网站（GitHub/邮箱/社交媒体）
  → profile="user" + 先手动开 Chrome --remote-debugging-port=9222

普通自动化、批量操作、无需登录
  → profile="openclaw"（默认，可省略 profile 参数）
```

## CDP 直连模式（更快）

当前配置已有 `chromeCdp` 模式（`browser.chromeCdp: true`），这让 OpenClaw 直接用 Chrome DevTools Protocol，绕过 Playwright 的额外开销。

## 常用操作示例

```javascript
// 1. 普通自动化（用默认 openclaw profile）
browser(action="open", url="https://example.com")
browser(action="snapshot")

// 2. 需要登录的网站
browser(action="open", profile="user", url="https://github.com/settings/applications")
browser(action="snapshot")

// 3. 截图
browser(action="screenshot", fullPage=true)

// 4. 复杂交互（先用 snapshot 获取 refs）
browser(action="snapshot")
// → 拿到 @e1, @e2 等 refs
browser(action="act", ref="e1", kind="click")
browser(action="act", ref="e3", kind="type", text="hello world")

// 5. PDF 导出
browser(action="pdf")
```

## 故障排除

| 问题 | 解决 |
|------|------|
| `profile="user"` 报错 "browser not running" | 先手动开 Chrome：`google-chrome --remote-debugging-port=9222` |
| `profile="openclaw"` 报错 "CDP not reachable" | 重启 Gateway：`openclaw gateway restart` |
| 浏览器开着但连不上 | 检查端口：`lsof -i :9222`，确认是 Chrome 在监听 |
| 截图是空白页 | 加 `loadState="networkidle"` 等待网络空闲 |
