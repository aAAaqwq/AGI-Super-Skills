---
name: quant-elon-tweets
description: Monitor Elon Musk tweet count prediction markets on Polymarket. Searches for nearest-settling market via slug pattern, fetches real-time tweet count, projects final count, and trades when edge >10% with <12h remaining. Use for automated Elon tweet market monitoring during 21:00-03:00 window.
---

# Elon Tweet Market Scanner

Find nearest-settling Elon tweet market, get tweet count, project outcome, trade on edge.

## Core Logic
Closer to settlement → more certain tweet count → larger edge.

## Flow

### 1. Find Active Market
```bash
bash scripts/elon_slug_search.sh
```
If `NO_ACTIVE_MARKET`, exit without report.

### 3. Check Remaining Time
Elon markets typically settle around 3AM ET next day, not midnight.

- **<6h remaining** → high confidence window, analyze + trade
- **6-12h remaining** → observation only, log data, no trade
- **>12h remaining** → too early, skip

### 4. Get Tweet Count
Fetch Polymarket event page to read "TWEET COUNT" display:
- Primary: `web_fetch` the event URL
- Fallback: browser navigate + snapshot

### 5. Project Final Count
```
rate = tweet_count / hours_elapsed
projected = tweet_count + rate × hours_remaining
```

Confidence: <6h remaining = high (±10%), 6-12h = medium (±20%), >12h = low.

### 6. Find Edge & Trade
- Map projected range to market outcomes
- **<6h remaining** required to trade
- Edge >10% (projected probability vs market price)
- Position ≤4% of assets, max $5/trade
- Hold to settlement, no stop-loss
- **≥6h remaining** → log data only, no trade

### 7. Report
Push: market slug, tweet count, rate, projection, odds comparison, action.

## Slug Pattern
`elon-musk-of-tweets-{month}-{start}-{month}-{end}`
- Windows: 2-day, 7-day
- Not findable via Gamma search — direct slug lookup only
