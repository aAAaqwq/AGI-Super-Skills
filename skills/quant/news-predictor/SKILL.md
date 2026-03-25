---
name: news-predictor
description: Monitor crypto/macroeconomic news for signals that predict impending price crashes or pumps. Scan CoinDesk RSS, macro calendar events (Fed meetings, CPI/PPI, NFP), and geopolitical developments. Generate risk signals (DANGER/CAUTION/OPPORTUNITY) and adjust Polymarket positions accordingly. Use when: (1) checking for breaking news impact on crypto positions, (2) pre-event risk assessment before Fed/data releases, (3) detecting market regime changes from news flow, (4) cron job needs to evaluate news before trading decisions.
---

# News Predictor — 新闻预测引擎

Monitor news/macro events to predict crypto price moves and adjust positions.

## Core Workflow

```
News Sources → Signal Detection → Risk Assessment → Position Action
```

### Step 1: Scan News (run `scripts/news_monitor_v2.sh`)

Scans 5 sources in one call, returns structured JSON:
```bash
bash scripts/news_monitor_v2.sh
```

Output: `{scan_time, items_found, data[{ts,source,title,categories,sentiment,impact}]}`
Sources: CryptoCompare API, Yahoo Finance (prices), CoinTelegraph RSS, Bloomberg RSS, Whale Alert (placeholder)
Only includes news from last 6 hours. See `references/data-sources.md` for full details.

### Step 2: Check Macro Calendar (run `scripts/macro_calendar.sh`)

```bash
bash scripts/macro_calendar.sh
```

Returns upcoming high-impact events in next 48h with risk levels.

### Step 3: Signal Classification

Classify each signal per `references/signal-rules.md`:

| Signal | Meaning | Action |
|--------|---------|--------|
| 🔴 DANGER | High-probability crash incoming | Reduce crypto exposure 50%+, no new buys |
| 🟡 CAUTION | Elevated risk, direction uncertain | No new buys, tighten stops, reduce position sizes |
| 🟢 OPPORTUNITY | High-probability pump or mispricing | Consider adding positions, wider stops |
| ⚪ NEUTRAL | Normal news flow, no actionable signal | Continue normal strategy |

### Step 4: Position Adjustment Rules

When signal detected, apply these rules to all open positions:

**🔴 DANGER actions:**
1. All crypto YES positions with profit: sell immediately
2. All crypto YES positions at loss: sell if loss >10%
3. Block ALL new crypto YES buys for 6h minimum
4. If crypto NO positions exist: hold (they benefit from crash)

**🟡 CAUTION actions:**
1. No new crypto YES buys
2. Reduce position sizes by 50% (use half normal size)
3. Tighten stops by 30% (e.g., 15% SL → 10.5% SL)

**🟢 OPPORTUNITY actions:**
1. Allow normal buying (remove CAUTION bans)
2. Can increase position size by 25%
3. Consider entries in sweet spot with wider buffer

### Step 5: Log & Notify

- Write signals to `data/news-signals.jsonl` (append)
- If DANGER: push alert to Daniel via Telegram immediately
- Update `HEARTBEAT.md` with current risk level

## Data Sources

See `references/data-sources.md` for full source list and fallback options.

## Integration with Trading Cron

**Critical**: News prediction MUST run BEFORE any trading decision.

Cron execution order:
1. `news-predictor` → determines current risk level
2. `crypto-hunt` → respects risk level (skip if DANGER/CAUTION)
3. `position-monitor` → applies position adjustment rules

### Risk Level Persistence

Store current risk level in `data/news-risk-level.json`:
```json
{"level": "CAUTION", "signal": "Fed meeting in 4h", "expires": "2026-03-18T14:00:00+08:00", "updated": "2026-03-18T10:00:00+08:00"}
```

Trading cron reads this file before any buy decision. If level is DANGER/CAUTION, respect the rules above.

## Key Event Calendar (Hardcoded High-Impact Events)

These events ALWAYS trigger CAUTION minimum 4h before:

| Event | Typical Impact | Action |
|-------|---------------|--------|
| FOMC Rate Decision | ±3-5% BTC | CAUTION 24h before, no trade during |
| CPI/PPI Release | ±1-3% BTC | CAUTION 2h before |
| NFP Jobs Report | ±1-3% BTC | CAUTION 2h before |
| Fed Chair Speech | ±1-2% BTC | CAUTION during speech |
| Geopolitical Escalation (Iran/etc) | ±2-5% BTC | DANGER immediately |
| SEC Regulatory Action | ±2-5% BTC | CAUTION/DANGER |
| Major Exchange Incident | ±1-3% BTC | CAUTION |

## News-to-Market Mapping

| News Category | Primary Assets Affected | Typical Direction |
|--------------|------------------------|-------------------|
| Fed hawkish/dovish | BTC, ETH, SOL | Hawkish=down, Dovish=up |
| CPI/PPI > expected | BTC, ETH, SOL | Down (higher rates longer) |
| Iran war escalation | BTC, ETH, SOL, GOLD | Crypto=down, Gold=up |
| Iran de-escalation | BTC, ETH, SOL, GOLD | Crypto=up, Gold=down |
| ETF inflow/outflow | BTC, ETH | Inflow=up, Outflow=down |
| Hack/exploit | Affected token | Down sharply |
| Regulation positive | BTC, ETH | Up |
| Regulation negative | BTC, altcoins | Down |

## Collaboration with 小data

For deep news analysis:
- `sessions_send(sessionKey="agent:data:main", message="...")`
- Ask 小data to investigate specific news events
- 小data can provide: on-chain data, social sentiment, deeper analysis
- Use for: confirming signals, getting additional data points

## Example: 3/18 Crash (What This Skill Would Have Done)

```
12:00 — macro_calendar.sh: "FOMC Rate Decision TODAY 18:00 BJ" → CAUTION
12:00 — news_monitor.sh: "PPI data worse than expected" → CAUTION
14:00 — Risk level upgraded to CAUTION
14:00 — Crypto hunt: ALL new buys BLOCKED (CAUTION rule)
14:00 — Position check: tighten stops by 30% on existing positions
18:00 — news_monitor.sh: "Powell hawkish remarks" → DANGER
18:00 — Sell all profitable crypto positions immediately
18:00 — Block ALL crypto buys for 6h
Result: Avoid $40+ in losses
```
