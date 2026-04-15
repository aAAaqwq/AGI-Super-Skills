# 📡 CT Monitor — Crypto Intelligence Analyst

> Monitor 5000+ crypto KOL tweets, real-time news, RSS feeds & CoinGecko prices. Extract Alpha signals, identify narratives, generate AI briefings.

[中文文档 ↓](#中文说明)

---

## What is this?

CT Monitor is an OpenClaw Skill that connects to a continuously running backend service which:

- **Monitors** 5000+ crypto KOL tweets (synced every 30 min ~ 24h, tiered by influence)
- **Aggregates** AI-scored news + curated RSS feeds with automatic deduplication
- **Tracks** CoinGecko real-time prices + trending token analysis + KOL mention correlation
- **Extracts** Alpha signals weighted by KOL influence, identifying high-frequency token mentions
- **Generates** AI briefings powered by Grok 4.1 Fast, integrating multi-source data

Once installed, ask OpenClaw in natural language — it automatically calls the right APIs and synthesizes the results.

---

## What can it do?

| Scenario | Example prompt |
| :--- | :--- |
| 📰 **Morning Brief** | "Give me today's crypto market briefing" |
| 🔍 **Alpha Signals** | "Any notable signals in the last hour?" |
| 👤 **KOL Research** | "What has Vitalik been focused on lately?" |
| 🏗️ **Project Due Diligence** | "Quick research on Hyperliquid" |
| 🚨 **Security Alert** | "Any recent hack or rug news?" |
| 💰 **Price Query** | "What's BTC price? How much did it move in 24h?" |
| 📈 **Trend Analysis** | "What tokens are trending? What are KOLs discussing?" |
| 📅 **DCA Decision** | "Analyze this week's market, give me DCA suggestions" |

---

## Quick Start

### Step 1: Get an API Key

Visit [api.ctmon.xyz/docs](https://api.ctmon.xyz/api/docs) to register and get your API Key.

### Step 2: Install the Skill in OpenClaw

```
/skill install openclaw-twitter-monitor
```

Or search "CT Monitor" on [ClawHub](https://clawhub.ai/skills/openclaw-twitter-monitor).

### Step 3: Configure API Key

OpenClaw will prompt you to enter `CT_MONITOR_API_KEY`. Paste the key from Step 1.

**Verify installation:**
```
Check CT Monitor system status
```

OpenClaw should return sync status and last update time.

---

## Power Combos

CT Monitor's real value is in **combining multiple data sources**. Here are 6 scenarios that show how chaining APIs produces insights far beyond single queries.

### 🌅 Combo 1: Morning Intelligence Brief (Daily)

**You say:**
> Give me today's crypto market briefing — market sentiment, hot narratives, and tokens to watch

**OpenClaw will:**
1. Call `/brief/generate?hours=24` → AI comprehensive briefing
2. Call `/price/trending?hours=24` → trending tokens + KOL mention analysis
3. Call `/signals/recent?hours=6` → last 6h high-frequency signals
4. Synthesize all three into a structured morning report

**You get:** Overall market sentiment + Top 3 narratives today + Tokens to watch (with reasons) + Risk alerts

💡 **Set up auto-delivery:** Schedule OpenClaw to send this to Telegram every morning at 8am

---

### 🎯 Combo 2: Alpha Signal Deep Dive (When opportunity appears)

**You say:**
> Any Alpha signals in the last hour? Deep dive the strongest one

**OpenClaw will:**
1. Call `/signals/recent?hours=1` → discover high-frequency token (e.g. $PENGU)
2. Call `/price/token?symbol=PENGU` → current price and % change
3. Call `/tweets/feed` filtered for $PENGU → what KOLs are actually saying
4. Call `/info/feed?coin=PENGU` → related news and RSS
5. Call `/users/top` → assess influence weight of mentioning KOLs
6. Synthesize → signal strength rating + actionable recommendation

**You get:** Signal strength (Strong/Medium/Weak) + KOL quality assessment + Price context + News corroboration + Trade suggestion (with risk warning)

---

### 👤 Combo 3: KOL Deep Profile (Research a specific KOL)

**You say:**
> Deep dive @cobie — what's he focused on lately, what's his investment thesis?

**OpenClaw will:**
1. Call `/twitter/realtime?username=cobie` → latest real-time tweets
2. Call `/tweets/recent?username=cobie` → historical tweets (longer timespan)
3. Call `/tweets/feed` filtered for "cobie" → how other KOLs reference and quote him
4. Synthesize three dimensions into a KOL profile

**You get:** Recent sector/project focus + Core views (Bullish/Bearish stance) + Investment logic analysis + Influence assessment + Key insights worth noting

---

### 🏗️ Combo 4: Project Due Diligence (Quick comprehensive research)

**You say:**
> Quick research on Hyperliquid — community heat, KOL sentiment, price performance

**OpenClaw will:**
1. Call `/tweets/feed` filtered for Hyperliquid/HYPE → KOL opinion panorama
2. Call `/info/feed?coin=HYPE` → related news and RSS
3. Call `/price/token?symbol=HYPE` → price data
4. Call `/signals/recent?hours=24` → last 24h signals
5. Synthesize into a due diligence report

**You get:** Community heat assessment + KOL sentiment distribution (Bullish/Bearish ratio) + Price performance analysis + Recent catalysts + Key risk factors

---

### 🚨 Combo 5: Security Alert Response (When risk appears)

**You say:**
> I heard a protocol got hacked — confirm it and assess the impact

**OpenClaw will:**
1. Call `/tweets/feed` filtered for hack/exploit/rug → confirm the event
2. Call `/info/feed` → check news coverage
3. Call `/price/token` → check affected token price
4. Call `/signals/recent?hours=0.25` → last 15min panic signals
5. Synthesize → urgency rating + recommended actions

**You get:** Event confirmation (real or FUD) + Impact scope assessment + Affected assets analysis + Urgency rating (High/Medium/Low) + Recommended actions

💡 **Set up real-time monitoring:** Schedule OpenClaw to check every 15 minutes and push alerts immediately

---

### 📅 Combo 6: DCA Decision Support (Weekly review)

**You say:**
> Weekly market review — give me DCA strategy for next week

**OpenClaw will:**
1. Call `/brief/generate?hours=24` → latest market briefing
2. Call `/price/trending?hours=24` → last 24H trending tokens
3. Call `/price/summary` → major coin price overview
4. Call `/signals/recent?hours=6` → recent signal summary
5. Synthesize into an investment decision report

**You get:** Market trend judgment (Bull/Bear/Sideways) + Sectors to watch + Major coin allocation suggestions + Risk warnings + DCA strategy recommendations

---

### 🌊 Combo 7: Narrative Trend Tracker (What story is the market telling?)

**You say:**
> What narratives are hot right now? Which sectors are gaining momentum?

**OpenClaw will:**
1. Scan `/tweets/feed` filtered by sector keywords (AI, RWA, DePIN, BTCFi, etc.) → compare narrative heat across sectors
2. Call `/signals/recent?hours=24` → check if narratives have signal-level resonance
3. Call `/price/trending?hours=24` → verify if narratives are already reflected in prices
4. Synthesize into a narrative heat map

**You get:** Narrative heat ranking + Price validation (early vs. already priced in) + Overheating warnings + Emerging narrative alerts

💡 **Best use case:** Spot the next hot narrative before it goes mainstream

---

### 🪂 Combo 8: Airdrop & Event Hunter (Never miss an opportunity)

**You say:**
> Any upcoming airdrops, TGEs, or unlock events worth paying attention to?

**OpenClaw will:**
1. Scan `/tweets/feed` filtered for airdrop/snapshot/TGE/unlock/claim keywords → surface event mentions
2. Scan `/info/feed` for related news coverage
3. Call `/signals/recent?hours=24` → check if KOLs are concentrating attention on specific events
4. Synthesize into an event calendar with value assessment

**You get:** Upcoming event list + Participation value assessment (effort vs. reward) + Risk flags (potential scams) + Action checklist

💡 **Best use case:** Run this daily — airdrop windows close fast

---

### 🐋 Combo 9: Smart Money Tracker (Follow the whales)

**You say:**
> What are the most influential KOLs quietly positioning in lately?

**OpenClaw will:**
1. Call `/users/top?limit=20` → get the highest-influence KOL list
2. Call `/twitter/realtime?username=XXX` for top 5 KOLs → their latest real-time tweets
3. Call `/tweets/recent?username=XXX` for top 5 KOLs → historical tweet patterns
4. Synthesize → identify common focus areas and quiet accumulation signals

**You get:** Top KOL recent focus summary + Overlapping positions (tokens multiple whales are watching) + Conviction signals (repeated mentions over time) + Divergence alerts (when whales disagree)

💡 **Best use case:** The best alpha often comes before the crowd notices

---

### 🔄 Combo 10: Sector Rotation Detector (Where is the money flowing?)

**You say:**
> Which sectors are gaining momentum and which are cooling down? Where should I rotate?

**OpenClaw will:**
1. Call `/price/trending?hours=24` vs `/price/trending?hours=168` → short-term vs. 7-day heat comparison
2. Call `/signals/recent?hours=6` vs `/signals/recent?hours=24` → signal acceleration or deceleration
3. Scan `/info/feed` filtered by sector keywords → media attention shift
4. Synthesize into a sector rotation matrix

**You get:** Sector heat change matrix (heating up / cooling down / stable) + Rotation direction judgment + Early-stage vs. late-stage sector identification + Reallocation suggestions

💡 **Best use case:** Crypto moves in sector cycles — catching the rotation early is where the biggest gains are

---

## Scheduled Automation Examples

Use `openclaw cron add` to schedule any combo as a recurring automated job. OpenClaw runs a full AI agent session on schedule and delivers results directly to your Telegram (or other channels).

**Combo 1 — Daily morning brief (8am):**
```bash
openclaw cron add \
  --name "CT Morning Brief" \
  --cron "0 8 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run CT Monitor Combo 1: call /brief/generate?hours=24, /price/trending?hours=24, /signals/recent?hours=6. Synthesize into a structured morning report: market sentiment, top 3 narratives, tokens to watch, risk alerts." \
  --announce \
  --channel telegram
```

**Combo 2 — Alpha signal alert (every 15 min, fires only when signal found):**
```bash
openclaw cron add \
  --name "CT Signal Alert" \
  --cron "*/15 * * * *" \
  --session isolated \
  --message "Call CT Monitor /signals/recent?hours=0.25&min_score=60. If any signal has kol_count >= 3, run the full Combo 2 deep dive on that token and send an alert. If no qualifying signals, stay silent." \
  --announce \
  --channel telegram
```

**Combo 5 — Security watch (every 15 min, fires only on confirmed events):**
```bash
openclaw cron add \
  --name "CT Security Watch" \
  --cron "*/15 * * * *" \
  --session isolated \
  --message "Check CT Monitor for hack/exploit/rug mentions in /tweets/feed and /info/feed. If 3+ KOLs mention the same security event, run Combo 5 analysis and send an URGENT alert. If nothing found, stay silent." \
  --announce \
  --channel telegram
```

**Combo 10 — Weekly sector rotation (Sunday 9pm):**
```bash
openclaw cron add \
  --name "CT Sector Rotation" \
  --cron "0 21 * * 0" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run CT Monitor Combo 10: compare trending data 24h vs 7d, signal acceleration 6h vs 24h, media attention by sector. Generate weekly sector rotation matrix with reallocation suggestions." \
  --announce \
  --channel telegram
```

**Manage your jobs:**
```bash
openclaw cron list
openclaw cron runs --id <job-id>
openclaw cron remove <job-id>
```

> 💡 **How it works**: OpenClaw runs a full AI agent session at the scheduled time — it calls the APIs, synthesizes the data, and delivers the result directly to your Telegram. You don't need to be online.

---

## Pricing

CT Monitor charges per API call, deducted from your account balance:

| Endpoint | Cost | Notes |
| :--- | :--- | :--- |
| `/brief/generate` hours=1 | 6¢ | 1H flash briefing (Grok 4.1 Fast) |
| `/brief/generate` hours=8 | 4¢ | 8H briefing |
| `/brief/generate` hours=12/24 | 2¢ | 12/24H briefing |
| `/signals/recent` hours<2 | 3¢ | Real-time data (6551 source) |
| `/signals/recent` hours≥2 | 1¢ | Historical database |
| `/twitter/realtime` | 2¢ | Real-time tweets (6551 source) |
| `/price/token` | 1¢ | Token price query — 3-level fallback (CoinGecko→Binance→DexScreener); response includes `source`, `chain`, `dex`, `pair_address` fields |
| `/price/trending` | 1¢ | Trending token analysis |
| `/price/summary` | 1¢ | Market overview |
| `/info/feed` | 1¢ | Unified news + RSS feed |
| `/tweets/feed` `/tweets/recent` `/tweets/search` | Free | Historical database queries |

**Typical scenario costs:**
- Morning intelligence brief: ~4¢/run
- Alpha signal deep dive: ~6¢/run
- Daily scheduled delivery: ~$1.2/month

---

## FAQ

**Q: How fresh is the data?**
A: KOL tweets are synced by influence tier: Ultra High (53 accounts) every 30 min, High (196) every 1h, Normal (1100) every 4h, Low (500) every 24h. Real-time tweets via `/twitter/realtime` have ~1-2 min latency.

**Q: Which KOLs are monitored?**
A: Currently 5000+ crypto KOLs across 27 sectors including Layer1/Layer2/DeFi/AI/Meme. You can also add custom monitoring via `POST /subscriptions/?username=XXX`.

**Q: What if the API returns empty data?**
A: If `[]` is returned, there's usually no data in that time window. Try expanding the time range (increase `hours` parameter) or retry later.

**Q: What languages are supported?**
A: The API returns raw data (primarily English tweets). AI analysis and synthesis output supports both English and Chinese.

---

## Links

- API Docs: [api.ctmon.xyz/docs](https://api.ctmon.xyz/api/docs)
- GitHub: [github.com/tizerluo/ct-monitor-skill](https://github.com/tizerluo/ct-monitor-skill)
- ClawHub: [clawhub.ai/skills/openclaw-twitter-monitor](https://clawhub.ai/skills/openclaw-twitter-monitor)

---

---

## 中文说明

CT Monitor 是一个专为加密市场设计的 OpenClaw Skill，整合 5000+ KOL 推文、实时新闻、RSS、CoinGecko 价格数据，提取 Alpha 信号、识别新兴叙事、生成 AI 简报。

### 快速上手

1. 访问 [api.ctmon.xyz/docs](https://api.ctmon.xyz/api/docs) 注册并获取 API Key
2. 在 OpenClaw 中执行 `/skill install openclaw-twitter-monitor`
3. 配置 `CT_MONITOR_API_KEY` 环境变量

### 6 大组合拳场景

| 场景 | 示例问题 |
| :--- | :--- |
| 🌅 早间情报简报 | "给我一份今天的加密市场早报" |
| 🎯 Alpha 信号深挖 | "最近 1 小时有什么 Alpha 信号？" |
| 👤 KOL 深度画像 | "帮我深度分析一下 @cobie" |
| 🏗️ 项目尽调 | "帮我快速调查一下 Hyperliquid" |
| 🚨 安全预警响应 | "有没有最新的 Hack 或 Rug 消息？" |
| 📅 定投决策辅助 | "帮我做本周市场复盘，给出定投建议" |

详细使用说明请参考上方英文文档。
