# 🔐 Browser & Auth 统一规则

> 所有 agent 必须遵守。这是全局规则，不是建议。

## 唯一 Chrome Profile

```
路径: ~/.openclaw/browser/openclaw/user-data/
调用: browser(profile='openclaw')
```

**所有浏览器操作统一使用 `profile='openclaw'`**。一个 profile，所有 agent 共享。

## ❌ 禁止

- `fast-browser-use` / `fbu` — 已废弃（除非 Daniel 明确要求用于特殊场景省 token）
- `~/.openclaw/chrome-profiles/<platform>/` — 旧 profile 目录，不再使用
- 启动独立 Chrome 进程（`google-chrome --user-data-dir=...`）

## ✅ 必须

- 浏览器操作 → `browser(action=..., profile='openclaw')`
- 登录态检查 → 优先 curl/CLI，备选内置 browser
- 新平台登录 → `browser(action='navigate', targetUrl='...login', profile='openclaw')`

## 平台检查速查

| 平台 | 方式 | 命令 |
|------|------|------|
| GitHub | CLI | `gh auth status` |
| AIXN | curl | `curl -H "Authorization: Bearer $TOKEN" https://ai.9w7.cn/api/user/info` |
| 性价比API | curl | `curl -H "Cookie: $COOKIE" https://xingjiabiapi.com/api/user/info` |
| Polymarket | browser | `browser(navigate → polymarket.com/portfolio, profile=openclaw)` |
| LinuxDo | browser | `browser(navigate → linux.do, profile=openclaw)` |
| X | browser | `browser(navigate → x.com/home, profile=openclaw)` |
| 抖音 | browser | `browser(navigate → creator.douyin.com, profile=openclaw)` |
| 小红书 | browser | `browser(navigate → creator.xiaohongshu.com, profile=openclaw)` |

## 文件位置

| 文件 | 用途 |
|------|------|
| `~/.openclaw/browser/openclaw/user-data/` | 唯一 Chrome profile |
| `~/.openclaw/auth-platforms.json` | 平台配置（URL、关键词） |
| `~/.openclaw/auth-session-state.json` | 最近检查结果 |
| `~/clawd/skills/auth-manager/SKILL.md` | 完整 skill 文档 |
| `~/clawd/skills/auth-manager/BROWSER_RULES.md` | 本文件 |
