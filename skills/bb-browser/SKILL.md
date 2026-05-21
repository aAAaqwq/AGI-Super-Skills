---
name: bb-browser
description: "AI agent browser automation via CDP. Use when you need to access websites that require login, scrape data from platforms (Twitter/X, Reddit, GitHub, Xueqiu, Bilibili, etc.), bypass IP blocks, or fetch structured data from any site the user is logged into. Triggers: bb-browser, browser fetch, login required, scrape, site data, twitter search, xueqiu, weibo, zhihu, bilibili, github data, cookie fetch, CDP, site adapter."
---

# bb-browser Skill

## Overview

bb-browser connects to your running Chrome via CDP (Chrome DevTools Protocol) and executes `fetch()` / JS in your logged-in tabs. No scraping, no API keys — your browser *is* the API.

**v0.11.6** | 143 community adapters | 36 platforms

## Prerequisites

1. Chrome must be running with remote debugging enabled:
   ```bash
   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   
   # Linux
   google-chrome --remote-debugging-port=9222
   
   # Or restart if already running:
   pkill chrome && sleep 1 && google-chrome --remote-debugging-port=9222 &
   ```
2. Verify: `bb-browser status` should show connected browsers.

## OpenClaw Integration

bb-browser supports `--openclaw` flag to use OpenClaw's built-in browser (no Chrome needed):
```bash
bb-browser site reddit/hot --openclaw
bb-browser site xueqiu/hot-stock 5 --openclaw --json
```

**重要**: bb-browser daemon连接的是OpenClaw的隔离Chrome（`/tmp/agent-browser-chrome-...`），
与OpenClaw browser tool的Chrome（`~/.openclaw/browser/openclaw/user-data`）是不同进程。

**Twitter/X特别说明**: Twitter的ct0 cookie是HTTP-only，bb-browser的JavaScript无法读取。
但OpenClaw browser tool（CDP协议）可以。Twitter数据抓取应使用专用脚本：
`scripts/twitter-scraper.py`（Playwright连接OpenClaw browser CDP）。

**架构**: bb-browser daemon → 端口9222 → 找到的第一个Chrome（含OpenClaw的）
**Playwright**: 直接连接 `http://127.0.0.1:18800` → OpenClaw browser

## Command Reference

### Data Fetching (Preferred — use `site` commands first)

```bash
# List all adapters
bb-browser site list

# Adapter info (params, returns, examples)
bb-browser site info <adapter>

# Run adapter
bb-browser site <platform>/<command> [args] [--json] [--jq '<filter>']
```

### Key Adapters for Quant Work

| Adapter | Command | Use Case |
|---------|---------|----------|
| Xueqiu hot stocks | `site xueqiu/hot-stock 5` | A-share sentiment |
| Xueqiu stock quote | `site xueqiu/stock <code>` | Real-time quotes |
| Eastmoney stock | `site eastmoney/stock <code>` | A-share data |
| Eastmoney news | `site eastmoney/news` | CN finance news |
| Yahoo Finance | `site yahoo-finance/quote <ticker>` | US/Crypto quotes |
| Twitter search | `site twitter/search "BTC"` | Crypto sentiment |
| Twitter user tweets | `site twitter/tweets <user>` | Whale watching |
| Reddit | `site reddit/subreddit <name> <limit>` | Community sentiment |
| Hacker News top | `site hackernews/top` | Tech trends |
| GitHub repo | `site github/repo <owner>/<name>` | Repo intel |
| Google search | `site google/search "query"` | Web search |
| Baidu search | `site baidu/search "query"` | CN web search |
| Zhihu hot | `site zhihu/hot` | CN knowledge trending |
| Weibo hot | `site weibo/hot` | CN social trending |
| 36kr newsflash | `site 36kr/newsflash` | CN tech news |

### Browser Control (for sites without adapters)

```bash
bb-browser open <url>              # Open URL
bb-browser snapshot -i             # Accessibility tree snapshot
bb-browser click @<ref>            # Click element
bb-browser fill @<ref> "text"      # Fill input
bb-browser eval "document.title"   # Execute JS
bb-browser fetch <url> --json      # Authenticated HTTP fetch
bb-browser screenshot [path]       # Take screenshot
```

### Utility

```bash
bb-browser tab list                # List open tabs
bb-browser status                  # Browser connection status
bb-browser network requests        # View network requests
bb-browser console                 # View console output
bb-browser site update             # Update community adapters
bb-browser site recommend          # Suggest adapters based on history
```

## Output Formats

All `site` commands support:
- `--json` — structured JSON output
- `--jq '<filter>'` — jq filtering (e.g., `--jq '.items[] | {name, price}'`)

Example:
```bash
bb-browser site xueqiu/hot-stock 5 --jq '.items[] | {name, changePercent}'
# {"name":"云天化","changePercent":"2.08%"}
# {"name":"东芯股份","changePercent":"-7.60%"}
```

## Adapter Tiers

| Tier | Method | Speed | Examples |
|------|--------|-------|---------|
| 1 | Cookie fetch | ~1s | Reddit, GitHub, V2EX |
| 2 | Bearer + CSRF token | ~3s | Twitter, Zhihu |
| 3 | Webpack/Pinia injection | ~10s | Twitter search, Xiaohongshu |

## Use from OpenClaw Agent

### Quick data fetch (exec)
```bash
# In agent exec calls:
bb-browser site twitter/search "BTC price" --json 2>&1
bb-browser site xueqiu/stock SH000001 --json 2>&1
```

### For login-gated sites
If `web_fetch` returns 403/blocked, try bb-browser:
```bash
bb-browser fetch "https://api.binance.me/api/v3/ticker/price?symbol=BTCUSDT" --json 2>&1
```

## Limitations

- **Not for bulk scraping** — designed for single/few queries, not millions of records
- **Rate limits apply** — you're operating as your real account; excessive use = ban risk
- **Chrome must stay open** — daemon connects to running Chrome instance
- **No headless** — the whole point is using your real browser session

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `No browsers connected` | Start Chrome with `--remote-debugging-port=9222` |
| `Tab not found` | Check `bb-browser tab list`, site may need to open first |
| Login required | Manually log into the site in Chrome first |
| `--openclaw` fails | Ensure OpenClaw browser is available (`browser doctor`) |
| Adapter missing | `bb-browser site update` to pull latest |

## Writing Custom Adapters

```bash
bb-browser guide                    # Read the adapter writing guide
bb-browser site info <name>         # Check existing adapter
```

Each adapter is a single JS file. Submit to `bb-sites` repo for community use.

---

*Created: 2026-05-18 | bb-browser v0.11.6 | 143 adapters*
