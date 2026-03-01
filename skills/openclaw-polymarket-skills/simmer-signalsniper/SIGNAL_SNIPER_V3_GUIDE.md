# Signal Sniper v3.0 - Automated Signal Trading with Risk Controls

**Implementation Date:** 17 February 2026  
**Status:** ✅ Implemented (Pending Dependency Fix)

---

## Overview

Signal Sniper v3.0 transforms the RSS-based signal detector into an **automated trading system** with comprehensive risk controls. It monitors multiple news feeds, detects trading signals, matches them to Polymarket markets, and executes trades automatically within defined risk parameters.

---

## What's New in v3.0

### 1. Multi-Feed RSS Monitoring

**Feeds Configured:**
- Internal OpenClaw alerts (`localhost:3939`)
- Google News (Polymarket + prediction markets)
- CoinDesk (crypto news)
- Cointelegraph (crypto news)
- BBC World News
- Reuters Markets

### 2. Categorized Keywords

```json
{
  "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "etf", "sec", "approval"],
  "political": ["trump", "biden", "executive order", "legislation", "congress", "senate"],
  "markets": ["polymarket", "prediction", "resolve", "announcement", "acquisition"],
  "general": ["musk", "fed", "rate", "fda", "clinical trial"]
}
```

### 3. Automatic Market Matching

- Searches Simmer API for markets matching article keywords
- Scores relevance based on keyword overlap and market metadata
- Filters by minimum keyword match threshold (default: 2)

### 4. Simmer Context Integration

Before executing any trade, v3.0 calls the Simmer context endpoint to check:
- Market resolved status
- Hours to expiry
- Current position holdings
- Flip-flop warnings
- Spread/slippage estimates
- Simmer AI signal divergence

---

## Risk Control Framework

### Position Controls

| Control | Default Value | Description |
|---------|--------------|-------------|
| `max_trades_per_day` | 5 | Hard limit on daily trade count |
| `max_volume_per_day_usd` | $100 | Max daily notional exposure |
| `position_size_usd` | $10 | Base position size per trade |
| `min_position_size` | $5 | Minimum trade size (Polymarket constraint) |

### Confidence Controls

| Control | Default Value | Description |
|---------|--------------|-------------|
| `min_confidence` | 0.75 | Minimum confidence to trade (0.0-1.0) |
| `confidence_scaling` | Enabled | Reduces size by 50% if confidence < 0.8 |

### Market Quality Controls

| Control | Default Value | Description |
|---------|--------------|-------------|
| `max_slippage_percent` | 5% | Skip if estimated slippage > threshold |
| `max_spread_percent` | 10% | Skip if bid-ask spread too wide |
| `market_expiry_min_hours` | 24 | Don't trade markets expiring within 24h |

### Behavioral Controls

| Control | Default Value | Description |
|---------|--------------|-------------|
| `flip_flop_cooldown_hours` | 24 | Cooldown after direction changes |
| `require_simmer_context` | True | Must pass Simmer safeguard checks |

---

## Trade Execution Flow

```
1. Fetch RSS feeds
   ↓
2. Parse articles → Extract title, description, link
   ↓
3. Match keywords → Category detection
   ↓
4. Find best market → Relevance scoring
   ↓
5. Get Simmer context → Risk validation
   ↓
6. Calculate confidence → Keyword + relevance + context
   ↓
7. Check risk controls → Daily limits, expiry, spread, flip-flop
   ↓
8. Determine direction → Bullish/bearish keyword analysis
   ↓
9. Calculate position size → Confidence-adjusted
   ↓
10. Execute trade → Via unified_trade_executor
    ↓
11. Log result → signals.json + signal_trades.json
```

---

## Confidence Calculation

Final confidence = Base (0.5) + Keyword Score + Source Credibility + Market Relevance + Context Adjustment

### Components:

**Keyword Score** (max 0.3)
- +0.1 per matched keyword
- Capped at 3 keywords

**Source Credibility** (max 0.1)
- +0.1 for Reuters, CoinDesk, major outlets
- +0.05 for other recognized sources

**Market Relevance** (max 0.2)
- Based on keyword overlap between article and market
- Time-to-expiry bonus for near-term markets

**Context Adjustment** (-0.15 to 0.0)
- -0.15 for flip-flop caution
- 0.0 if no warnings
- Trade blocked if severe warnings

**Example:**
```
Article: "SEC approves Bitcoin ETF"
Keywords: ["sec", "approves", "bitcoin", "etf"]
Category: crypto

Confidence calculation:
- Base: 0.5
- Keywords (4 matches): +0.3 (capped)
- Source (CoinDesk): +0.1
- Market relevance: +0.15
- Context (no warnings): 0.0
= 1.05 → capped at 1.0
```

---

## Direction Detection

Signal Sniper analyzes article text for bullish/bearish sentiment:

### Bullish Keywords
```
approval, pass, win, agreement, success, launch, 
bullish, up, approved, cleared, positive, gains
```

### Bearish Keywords
```
reject, fail, loss, ban, crash, delay, bearish, 
down, denied, blocked, negative, loses, hack, exploit
```

**Decision:** Trade YES if bullish_score >= bearish_score, otherwise trade NO.

---

## File Structure

```
/home/han/clawd/skills/simmer-signalsniper/
├── config.json                      # Configuration (updated)
├── signal_sniper_v3.py             # Main script (NEW)
├── signal_sniper_v2.py             # Previous version (backup)
├── signal_sniper_wrapper.sh        # Updated wrapper
├── test_config.py                  # Config validator
├── state/
│   ├── signals.json               # Signal detections
│   └── signal_trades.json         # Trade execution log
└── SKILL.md                       # Original documentation
```

---

## Usage

### Dry Run (Default)
```bash
cd /home/han/clawd
./signal_sniper_wrapper.sh
# or
python3 skills/simmer-signalsniper/signal_sniper_v3.py --run --dry-run
```

### Live Trading
```bash
# Method 1: Environment variable
export SIGNAL_SNIPER_MODE=live
./signal_sniper_wrapper.sh

# Method 2: Direct flag
python3 skills/simmer-signalsniper/signal_sniper_v3.py --run --live
```

---

## Configuration Tuning

### Adjust for Higher Frequency
```json
{
  "risk_controls": {
    "max_trades_per_day": 10,
    "max_volume_per_day_usd": 200,
    "min_confidence": 0.65
  }
}
```

### Adjust for Higher Quality (Lower Frequency)
```json
{
  "risk_controls": {
    "max_trades_per_day": 3,
    "max_volume_per_day_usd": 50,
    "min_confidence": 0.85,
    "max_slippage_percent": 3.0
  }
}
```

### Add Custom Feeds
```json
{
  "feeds": [
    "http://localhost:3939/api/openclaw/alerts/rss",
    "https://your-custom-feed.com/rss",
    "https://news.google.com/rss/search?q=YOUR_TOPIC"
  ]
}
```

---

## Monitoring

### Check Recent Signals
```bash
cat /home/han/clawd/skills/simmer-signalsniper/state/signals.json | jq '.[-10:]'
```

### Check Trade History
```bash
cat /home/han/clawd/skills/simmer-signalsniper/state/signal_trades.json | jq '.[-5:]'
```

### Health Check
```bash
python3 /home/han/clawd/utils/trading_health_monitor.py --report
```

---

## Known Limitations

1. **Websocket Dependency**: The `polymarket_trading.lib` requires `websockets` module which may not be installed. To fix:
   ```bash
   source /home/han/clawd/venv/bin/activate
   pip install websockets
   ```

2. **Market Search API**: Simmer's market search endpoint may have rate limits or return incomplete results.

3. **Context Endpoint**: Requires valid Simmer API key with proper permissions.

---

## Risk Warning

⚠️ **Automated RSS-based trading carries significant risk:**

- News may be priced in before detection
- False signals from headline-only scanning
- Market impact of automated execution
- Keyword matching errors

**Recommended Safeguards:**
1. Start with dry-run mode for 1 week
2. Review all signals before enabling live trading
3. Use conservative position sizes initially
4. Monitor daily and adjust keywords/feeds as needed

---

## Next Steps

1. **Install missing dependency**: `pip install websockets`
2. **Test dry-run**: Verify signals are being detected correctly
3. **Review logs**: Check 1 week of dry-run signals
4. **Enable live mode**: Set `SIGNAL_SNIPER_MODE=live`
5. **Monitor daily**: Use health monitor for first 2 weeks

---

*Implementation: 2026-02-17*  
*Version: 3.0*  
*Status: Ready for testing*
