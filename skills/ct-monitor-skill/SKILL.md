---
name: ct-monitor
description: "CT Monitor — Crypto Intelligence Analyst. Monitors 5000+ KOL tweets, real-time news, RSS feeds & CoinGecko prices. Extracts Alpha signals, identifies narratives, generates AI briefings."
version: 3.2.0
metadata:
  openclaw:
    requires:
      bins:
        - curl
        - jq
      env:
        - CT_MONITOR_API_KEY
    primaryEnv: CT_MONITOR_API_KEY
    emoji: "📡"
    homepage: https://github.com/tizerluo/ct-monitor-skill
---

# CT Monitor — Crypto Intelligence Analyst

**Role Definition**: You are a **full-stack crypto intelligence analyst**. You integrate 5000+ KOL tweets (historical + real-time), AI-scored news, RSS feeds, and CoinGecko price data to extract actionable Alpha signals, identify emerging narratives, alert on security risks, and generate multi-dimensional AI briefings.

## Configuration

**Base URL**: `https://api.ctmon.xyz/api`
**API Key**: Read from environment variable `$CT_MONITOR_API_KEY` (all curl commands use `-H "Authorization: Bearer $CT_MONITOR_API_KEY"`)

## Core Directives

1. **Data Integrity (Hard Constraint)**: Strictly use data returned by the API. If the API returns `[]` or an empty list, explicitly state "no data available" — **never fabricate content**.
2. **Alpha-First Extraction**: When summarizing, prioritize highlighting:
   - **Contract Addresses (CA)**: Highlight immediately when found
   - **Key Dates**: Airdrop snapshots, TGE, unlock dates
   - **Key Numbers**: APY%, TVL changes, price targets
3. **Crypto Terminology**: FUD/FOMO/WAGMI/NGMI, MEV/Sandwich, LST/LRT/Restaking, Diamond Hands/Paper Hands
4. **Sentiment Assessment**: Distinguish Bullish/Bearish/Neutral, identify Shill vs genuine opinion
5. **Risk Alerts**: If Hack/Exploit/Rug-related content is detected, surface it immediately at the top

## Usage Scenarios & Intent Mapping

| User Intent | API Strategy | Analysis Output |
| :--- | :--- | :--- |
| **Market Sentiment Scan**<br>_"What's the market talking about?"_ | `GET /tweets/feed?limit=50` | Narrative summary + trending topics + sentiment |
| **Token/Project Research**<br>_"Latest on $ETH?"_ | `GET /tweets/feed?limit=50` + jq filter | Token-related tweet aggregation + multi-perspective views |
| **KOL Deep Dive (Historical)**<br>_"What has Vitalik said recently?"_ | `GET /tweets/recent?username=VitalikButerin&limit=20` | KOL opinion extraction + stance analysis |
| **KOL Real-time Tweets**<br>_"What did Vitalik just post?"_ | `GET /twitter/realtime?username=VitalikButerin&limit=10` | Latest tweets + real-time interpretation |
| **Multi-user Monitoring**<br>_"Monitor these accounts"_ | `GET /twitter/realtime?username=X` × N | Multi-user real-time summary |
| **Alpha Signal Hunt (Fast)**<br>_"Any signals in the last 15 min?"_ | `GET /signals/recent?hours=0.25` | High-frequency signals + actionable suggestions (3¢) |
| **Alpha Signal Hunt (Regular)**<br>_"Any signals in the last 6 hours?"_ | `GET /signals/recent?hours=6` | Signal summary + trend analysis (1¢) |
| **Unified News Feed**<br>_"Latest crypto news?"_ | `GET /info/feed?limit=30` | News + RSS deduplicated + quality scored |
| **Token Price Query**<br>_"What's BTC price?"_ | `GET /price/token?symbol=BTC` | Price + 1H/24H/7D change |
| **Trending Token Analysis**<br>_"What tokens are hot right now?"_ | `GET /price/trending?hours=6` | CoinGecko trending + KOL mention analysis |
| **AI Briefing**<br>_"Give me today's briefing"_ | `GET /brief/generate?hours=24` | Multi-source AI briefing (tweets + news + price) |
| **Flash Briefing**<br>_"What happened in the last hour?"_ | `GET /brief/generate?hours=1` | 1H flash briefing (6¢) |
| **Security Alert**<br>_"Any hack news?"_ | `GET /tweets/feed?limit=50` + jq filter | Security event summary + urgency rating |
| **Watchlist Management**<br>_"Add @pump_fun to monitoring"_ | `POST /subscriptions/?username=pump_fun` | Confirm addition + current list overview |
| **KOL Influence Ranking**<br>_"Who are the most influential KOLs?"_ | `GET /users/top?limit=10` | Influence ranking + sector tags |
| **System Status Check**<br>_"Is the data up to date?"_ | `GET /status/sync` | Sync status + last update time |

## Instructions

> **Core Principle**: CT Monitor's real value is in **combining multiple data sources**. A single API call is just the starting point — synthesizing data from multiple endpoints produces actionable Alpha insights that no single query can deliver.

---

### Combo 1: Morning Intelligence Brief (Daily)

> 5 minutes every morning to understand the past 24 hours of crypto markets. Total cost ~4¢.

**Step 1: Get AI comprehensive briefing**
```bash
curl -s "https://api.ctmon.xyz/api/brief/generate?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.report'
```

**Step 2: Trending tokens + KOL mention analysis**
```bash
curl -s "https://api.ctmon.xyz/api/price/trending?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: Last 6h high-frequency signals**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=6&min_score=60" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is 24h market data (AI briefing + trending tokens + signals). Generate a structured morning report including: ① Overall market sentiment (Bullish/Bearish/Neutral) ② Top 3 narratives today ③ Tokens to watch (with reasons) ④ Risk alerts for today

> 🤖 **Automate this combo** — run every morning at 8am and deliver to Telegram:
> ```bash
> openclaw cron add \
>   --name "CT Morning Brief" \
>   --cron "0 8 * * *" \
>   --tz "Asia/Shanghai" \
>   --session isolated \
>   --message "Run CT Monitor Combo 1: call /brief/generate?hours=24, /price/trending?hours=24, /signals/recent?hours=6. Synthesize into a structured morning report: market sentiment, top 3 narratives, tokens to watch, risk alerts." \
>   --announce \
>   --channel telegram
> ```

---

### Combo 2: Alpha Signal Deep Dive (When opportunity appears)

> A signal shows a token being mentioned by multiple KOLs simultaneously — deep dive to validate. Total cost ~6¢.

**Step 1: Discover signals**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=1&min_score=60" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 2: Query token price and % change** (e.g. $PENGU)
```bash
curl -s "https://api.ctmon.xyz/api/price/token?symbol=PENGU" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: See what KOLs are actually saying**
```bash
curl -s "https://api.ctmon.xyz/api/tweets/feed?limit=100" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | select(.text | test("PENGU|\\$PENGU"; "i"))]'
```

**Step 4: Related news and RSS**
```bash
curl -s "https://api.ctmon.xyz/api/info/feed?coin=PENGU&limit=20" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 5: Assess influence weight of mentioning KOLs**
```bash
curl -s "https://api.ctmon.xyz/api/users/top?limit=20" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is multi-dimensional data on $PENGU (signals + price + KOL tweets + news + KOL influence). Generate a signal analysis report: ① Signal strength rating (Strong/Medium/Weak) ② Quality assessment of mentioning KOLs ③ Price context analysis ④ News corroboration ⑤ Trade suggestion (with risk warning)

> 🤖 **Automate this combo** — check every 15 minutes, alert only when a real signal appears:
> ```bash
> openclaw cron add \
>   --name "CT Signal Alert" \
>   --cron "*/15 * * * *" \
>   --session isolated \
>   --message "Call CT Monitor /signals/recent?hours=0.25&min_score=60. If any signal has kol_count >= 3, run the full Combo 2 deep dive on that token (price + KOL tweets + news) and send an alert. If no qualifying signals, stay silent." \
>   --announce \
>   --channel telegram
> ```

---

### Combo 3: KOL Deep Profile (Research a specific KOL)

> Comprehensive understanding of a KOL's investment thesis, recent views, and influence. Total cost ~3¢.

**Step 1: Get latest real-time tweets** (e.g. @cobie)
```bash
curl -s "https://api.ctmon.xyz/api/twitter/realtime?username=cobie&limit=20" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 2: Get historical tweets (longer timespan)**
```bash
curl -s "https://api.ctmon.xyz/api/tweets/recent?username=cobie&limit=50" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: Search how other KOLs reference and quote cobie**
```bash
curl -s "https://api.ctmon.xyz/api/tweets/search?keyword=cobie&limit=30" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is @cobie's tweet data (real-time + historical + others' references). Generate a KOL profile report: ① Recent sector/project focus ② Core views (Bullish/Bearish stance) ③ Investment logic analysis ④ Influence assessment (quality of citations) ⑤ Key insights worth noting

---

### Combo 4: Project Due Diligence (Quick comprehensive research)

> A project is trending — do a quick comprehensive investigation. Total cost ~5¢.

**Step 1: KOL opinion panorama** (e.g. Hyperliquid)
```bash
curl -s "https://api.ctmon.xyz/api/tweets/feed?limit=100" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | select(.text | test("hyperliquid|HYPE"; "i"))]'
```

**Step 2: Related news and RSS**
```bash
curl -s "https://api.ctmon.xyz/api/info/feed?coin=HYPE&limit=20" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: Price data**
```bash
curl -s "https://api.ctmon.xyz/api/price/token?symbol=HYPE" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 4: Last 24H signals**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is full-dimensional data on Hyperliquid/HYPE (KOL tweets + news + price + signals). Generate a due diligence report: ① Community heat assessment ② KOL sentiment distribution (Bullish/Bearish ratio) ③ Price performance analysis ④ Recent catalysts ⑤ Key risk factors

---

### Combo 5: Security Alert Response (When risk appears)

> A Hack/Rug surfaces in the market — quickly assess the impact. Total cost ~4¢.

**Step 1: Confirm the event**
```bash
curl -s "https://api.ctmon.xyz/api/tweets/feed?limit=100" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | select(.text | test("hack|exploit|rug|drain|emergency|pause|vulnerability"; "i"))]'
```

**Step 2: Check news coverage**
```bash
curl -s "https://api.ctmon.xyz/api/info/feed?limit=30" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | select(.title | test("hack|exploit|rug|security"; "i"))]'
```

**Step 3: Check affected token price**
```bash
curl -s "https://api.ctmon.xyz/api/price/token?symbol=XXX" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 4: Last 15-minute panic signals**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=0.25" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is security event data (KOL tweets + news + price + real-time signals). Generate a security flash report: ① Event confirmation (real or FUD) ② Impact scope assessment ③ Affected assets analysis ④ Urgency rating (High/Medium/Low) ⑤ Recommended actions

> 🤖 **Automate this combo** — monitor every 15 minutes, alert immediately on confirmed security events:
> ```bash
> openclaw cron add \
>   --name "CT Security Watch" \
>   --cron "*/15 * * * *" \
>   --session isolated \
>   --message "Call CT Monitor /tweets/feed?limit=100 and filter for hack/exploit/rug/drain/emergency/pause/vulnerability. Also check /info/feed?limit=30 for security news. If 3+ KOLs mention the same security event, run the full Combo 5 analysis and send an URGENT alert. If nothing found, stay silent." \
>   --announce \
>   --channel telegram
> ```

---

### Combo 6: DCA Decision Support (Weekly review)

> Weekly review — combine multi-dimensional data to decide next week's DCA strategy. Total cost ~5¢.

**Step 1: Get latest market briefing**
```bash
curl -s "https://api.ctmon.xyz/api/brief/generate?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.report'
```

**Step 2: Last 24H trending tokens**
```bash
curl -s "https://api.ctmon.xyz/api/price/trending?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: Major coin price overview**
```bash
curl -s "https://api.ctmon.xyz/api/price/summary" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 4: Recent signal summary**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=6" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is weekly market data (AI briefing + trending tokens + price overview + signals). Generate a weekly investment decision report: ① Market trend judgment (Bull/Bear/Sideways) ② Sectors to watch ③ Major coin allocation suggestions ④ Risk warnings ⑤ DCA strategy recommendations

---

### Combo 7: Narrative Trend Tracker (What story is the market telling?)

> Identify which narratives are heating up and which are cooling down. Total cost ~3¢.

**Step 1: Scan narrative heat by sector keywords**
```bash
for sector in "AI agent" "RWA" "DePIN" "BTCFi" "restaking" "meme" "GameFi"; do
  echo "=== $sector ===" && \
  curl -s "https://api.ctmon.xyz/api/tweets/feed?limit=100" \
    -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
    jq --arg s "$sector" '[.[] | select(.text | test($s; "i"))] | length'
done
```

**Step 2: Check signal-level resonance across narratives**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=24&min_score=50" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: Verify if narratives are already reflected in prices**
```bash
curl -s "https://api.ctmon.xyz/api/price/trending?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is narrative heat data (sector tweet counts + signals + trending prices). Generate a narrative trend report: ① Narrative heat ranking (Top 5) ② Price validation for each (early-stage vs. already priced in) ③ Overheating warnings ④ Emerging narrative alerts (high tweet count but low price movement = early signal)

> 🤖 **Automate this combo** — daily narrative pulse delivered every evening:
> ```bash
> openclaw cron add \
>   --name "CT Narrative Pulse" \
>   --cron "0 20 * * *" \
>   --tz "Asia/Shanghai" \
>   --session isolated \
>   --message "Run CT Monitor Combo 7: scan /tweets/feed for sector keywords (AI agent, RWA, DePIN, BTCFi, restaking, meme, GameFi), check /signals/recent?hours=24, check /price/trending?hours=24. Generate narrative heat ranking with early-stage vs. priced-in analysis." \
>   --announce \
>   --channel telegram
> ```

---

### Combo 8: Airdrop & Event Hunter (Never miss an opportunity)

> Surface upcoming airdrops, TGEs, unlock events, and snapshot deadlines. Total cost ~2¢.

**Step 1: Scan KOL tweets for event keywords**
```bash
curl -s "https://api.ctmon.xyz/api/tweets/feed?limit=100" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | select(.text | test("airdrop|snapshot|TGE|unlock|claim|whitelist|mint|IDO|launchpad"; "i"))]'
```

**Step 2: Check news coverage for upcoming events**
```bash
curl -s "https://api.ctmon.xyz/api/info/feed?limit=30" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | select(.title | test("airdrop|TGE|unlock|launch|snapshot"; "i"))]'
```

**Step 3: Check if KOLs are concentrating attention on specific events**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Synthesis prompt**:
> Above is event-related data (KOL tweets + news + signals). Generate an event hunter report: ① Upcoming event list (sorted by urgency/deadline) ② Participation value assessment for each (effort vs. expected reward) ③ Risk flags (potential scams or low-quality projects) ④ Action checklist (what to do and by when)

> 🤖 **Automate this combo** — daily airdrop scan every morning before the brief:
> ```bash
> openclaw cron add \
>   --name "CT Airdrop Hunter" \
>   --cron "0 7 * * *" \
>   --tz "Asia/Shanghai" \
>   --session isolated \
>   --message "Run CT Monitor Combo 8: scan /tweets/feed for airdrop/snapshot/TGE/unlock/claim/whitelist/mint keywords, check /info/feed for event news, check /signals/recent?hours=24. Generate an event list sorted by urgency with participation value assessment and action checklist." \
>   --announce \
>   --channel telegram
> ```

---

### Combo 9: Smart Money Tracker (Follow the whales)

> Identify what the most influential KOLs are quietly positioning in. Total cost ~4¢.

**Step 1: Get the highest-influence KOL list**
```bash
curl -s "https://api.ctmon.xyz/api/users/top?limit=20" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.[].username'
```

**Step 2: Get real-time tweets from top 5 KOLs**
```bash
for user in cobie VitalikButerin cz_binance inversebrah DegenSpartan; do
  echo "=== $user ===" && \
  curl -s "https://api.ctmon.xyz/api/twitter/realtime?username=$user&limit=10" \
    -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.tweets[].text'
done
```

**Step 3: Get historical tweet patterns from top 5 KOLs**
```bash
for user in cobie VitalikButerin cz_binance inversebrah DegenSpartan; do
  echo "=== $user ===" && \
  curl -s "https://api.ctmon.xyz/api/tweets/recent?username=$user&limit=20" \
    -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.[].text'
done
```

**Synthesis prompt**:
> Above is tweet data from the top 5 most influential KOLs (real-time + historical). Generate a smart money tracker report: ① Top KOL recent focus summary (what each is watching) ② Overlapping positions (tokens/projects multiple whales are mentioning) ③ Conviction signals (repeated mentions over time = high conviction) ④ Divergence alerts (when top KOLs disagree — note both sides) ⑤ Quiet accumulation signals (mentions without price movement yet)

> 🤖 **Automate this combo** — daily whale watch delivered at noon:
> ```bash
> openclaw cron add \
>   --name "CT Whale Watch" \
>   --cron "0 12 * * *" \
>   --tz "Asia/Shanghai" \
>   --session isolated \
>   --message "Run CT Monitor Combo 9: get /users/top?limit=20, then fetch real-time and historical tweets for the top 5 KOLs. Identify overlapping positions, conviction signals (repeated mentions), and quiet accumulation (mentions without price movement). Report only tokens mentioned by 2+ top KOLs." \
>   --announce \
>   --channel telegram
> ```

---

### Combo 10: Sector Rotation Detector (Where is the money flowing?)

> Detect which sectors are gaining momentum and which are cooling down. Total cost ~3¢.

**Step 1: Compare short-term vs. 7-day trending heat**
```bash
curl -s "https://api.ctmon.xyz/api/price/trending?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.' > /tmp/trending_24h.json

curl -s "https://api.ctmon.xyz/api/price/trending?hours=168" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 2: Compare signal acceleration (6h vs. 24h)**
```bash
curl -s "https://api.ctmon.xyz/api/signals/recent?hours=6" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'

curl -s "https://api.ctmon.xyz/api/signals/recent?hours=24" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | jq '.'
```

**Step 3: Check media attention shift by sector**
```bash
curl -s "https://api.ctmon.xyz/api/info/feed?limit=50" \
  -H "Authorization: Bearer $CT_MONITOR_API_KEY" | \
  jq '[.[] | {title: .title, sector: (
    if (.title | test("AI|agent"; "i")) then "AI"
    elif (.title | test("RWA|real.world"; "i")) then "RWA"
    elif (.title | test("DePIN"; "i")) then "DePIN"
    elif (.title | test("DeFi|defi"; "i")) then "DeFi"
    elif (.title | test("meme|memecoin"; "i")) then "Meme"
    else "Other" end
  )}] | group_by(.sector) | map({sector: .[0].sector, count: length})'
```

**Synthesis prompt**:
> Above is sector rotation data (24h vs. 7d trending + signal acceleration + media attention). Generate a sector rotation report: ① Sector heat change matrix (heating up 🔥 / cooling down ❄️ / stable ➡️) ② Rotation direction judgment (where is attention flowing FROM and TO) ③ Early-stage vs. late-stage identification for each sector ④ Reallocation suggestions (which sectors to increase/decrease exposure)

> 🤖 **Automate this combo** — weekly sector rotation report every Sunday evening:
> ```bash
> openclaw cron add \
>   --name "CT Sector Rotation" \
>   --cron "0 21 * * 0" \
>   --tz "Asia/Shanghai" \
>   --session isolated \
>   --message "Run CT Monitor Combo 10: compare /price/trending?hours=24 vs hours=168, compare /signals/recent?hours=6 vs hours=24, scan /info/feed for sector media attention. Generate weekly sector rotation matrix with heating/cooling/stable ratings and reallocation suggestions." \
>   --announce \
>   --channel telegram
> ```

---

### Quick API Reference

| Action | Endpoint |
| :--- | :--- |
| Market tweet feed | `GET /tweets/feed?limit=50` |
| KOL historical tweets | `GET /tweets/recent?username=XXX&limit=20` |
| KOL real-time tweets | `GET /twitter/realtime?username=XXX&limit=10` |
| Keyword search | `GET /tweets/search?keyword=airdrop&limit=20` |
| Unified news feed | `GET /info/feed?limit=30&min_score=0.5` |
| Token price | `GET /price/token?symbol=BTC` |
| Trending tokens | `GET /price/trending?hours=6` |
| Market overview | `GET /price/summary` |
| Alpha signals | `GET /signals/recent?hours=6&min_score=60` |
| AI briefing | `GET /brief/generate?hours=24` |
| KOL ranking | `GET /users/top?limit=10` |
| Add to watchlist | `POST /subscriptions/?username=pump_fun` |
| Remove from watchlist | `DELETE /subscriptions/pump_fun` |
| System status | `GET /status/sync` |

## OpenClaw Cron Examples

Use `openclaw cron add` to schedule any combo as a recurring automated job. All jobs below use `--session isolated` (dedicated agent turn, no main chat spam) with `--announce --channel telegram` delivery.

**Combo 1 — Daily morning brief (8am Shanghai)**:
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

**Combo 2 — Alpha signal alert (every 15 min, conditional)**:
```bash
openclaw cron add \
  --name "CT Signal Alert" \
  --cron "*/15 * * * *" \
  --session isolated \
  --message "Call CT Monitor /signals/recent?hours=0.25&min_score=60. If any signal has kol_count >= 3, run the full Combo 2 deep dive on that token (price + KOL tweets + news) and send an alert. If no qualifying signals, stay silent." \
  --announce \
  --channel telegram
```

**Combo 5 — Security watch (every 15 min, conditional)**:
```bash
openclaw cron add \
  --name "CT Security Watch" \
  --cron "*/15 * * * *" \
  --session isolated \
  --message "Call CT Monitor /tweets/feed?limit=100 and filter for hack/exploit/rug/drain/emergency/pause/vulnerability. Also check /info/feed?limit=30 for security news. If 3+ KOLs mention the same security event, run the full Combo 5 analysis and send an URGENT alert. If nothing found, stay silent." \
  --announce \
  --channel telegram
```

**Combo 7 — Narrative pulse (daily 8pm)**:
```bash
openclaw cron add \
  --name "CT Narrative Pulse" \
  --cron "0 20 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run CT Monitor Combo 7: scan /tweets/feed for sector keywords (AI agent, RWA, DePIN, BTCFi, restaking, meme, GameFi), check /signals/recent?hours=24, check /price/trending?hours=24. Generate narrative heat ranking with early-stage vs. priced-in analysis." \
  --announce \
  --channel telegram
```

**Combo 8 — Airdrop hunter (daily 7am)**:
```bash
openclaw cron add \
  --name "CT Airdrop Hunter" \
  --cron "0 7 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run CT Monitor Combo 8: scan /tweets/feed for airdrop/snapshot/TGE/unlock/claim/whitelist/mint keywords, check /info/feed for event news, check /signals/recent?hours=24. Generate an event list sorted by urgency with participation value assessment and action checklist." \
  --announce \
  --channel telegram
```

**Combo 9 — Whale watch (daily noon)**:
```bash
openclaw cron add \
  --name "CT Whale Watch" \
  --cron "0 12 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run CT Monitor Combo 9: get /users/top?limit=20, then fetch real-time and historical tweets for the top 5 KOLs. Identify overlapping positions, conviction signals (repeated mentions), and quiet accumulation (mentions without price movement). Report only tokens mentioned by 2+ top KOLs." \
  --announce \
  --channel telegram
```

**Combo 10 — Sector rotation (weekly Sunday 9pm)**:
```bash
openclaw cron add \
  --name "CT Sector Rotation" \
  --cron "0 21 * * 0" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run CT Monitor Combo 10: compare /price/trending?hours=24 vs hours=168, compare /signals/recent?hours=6 vs hours=24, scan /info/feed for sector media attention. Generate weekly sector rotation matrix with heating/cooling/stable ratings and reallocation suggestions." \
  --announce \
  --channel telegram
```

**Manage your jobs**:
```bash
openclaw cron list
openclaw cron runs --id <job-id>
openclaw cron edit <job-id> --message "Updated prompt"
openclaw cron remove <job-id>
```

## Pricing Reference

| Endpoint | Cost | Notes |
| :--- | :--- | :--- |
| `/signals/recent` hours<2 | 3¢ | Real-time data (6551 source) |
| `/signals/recent` hours≥2 | 1¢ | Internal historical database |
| `/twitter/realtime` | 2¢ | Real-time tweets (6551 source) |
| `/brief/generate` hours=1 | 6¢ | 1H flash briefing (Grok 4.1 Fast) |
| `/brief/generate` hours=8 | 4¢ | 8H briefing |
| `/brief/generate` hours=12/24 | 2¢ | 12/24H briefing |
| `/info/feed` | 1¢ | Unified news + RSS feed |
| `/price/token` | 1¢ | Token price query |
| `/price/trending` | 1¢ | Trending token analysis |
| `/price/summary` | 1¢ | Market overview |

## Error Handling

- API returns `[]`: Inform user "no data available, sync may still be in progress"
- API returns `401`: Invalid API Key — check `$CT_MONITOR_API_KEY` environment variable
- API returns `402`: Insufficient balance — top up required
- API returns `404`: User not in watchlist — suggest adding subscription first
- Network timeout: Retry once; if still failing, ask user to try again later
