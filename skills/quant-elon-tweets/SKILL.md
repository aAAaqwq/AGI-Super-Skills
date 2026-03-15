# 🐦 Elon Tweet Market — Prediction Market Scanner

Monitors Elon Musk tweet count prediction markets on Polymarket. Searches for the nearest-settling market, fetches real-time tweet count, projects final count, and trades when edge is found.

## Core Logic
Settlement is approaching → tweet count becomes more certain → edge gets larger.

## Execution Flow

### Step 1: Find Nearest Settling Elon Market
Search Polymarket Gamma API for active Elon tweet markets using slug pattern:
- `elon-musk-of-tweets-{month}-{start}-{month}-{end}`
- Window sizes: 2-day and 7-day
- Look back 10 days (7-day markets may have started earlier)
- Select the market with the earliest `endDate` that's still in the future

### Step 2: Get Market Odds
Fetch all outcome prices for the target market from Gamma API.

### Step 3: Get Real-Time Tweet Count
Fetch the Polymarket event page to read the embedded "TWEET COUNT" display.
- Primary: web_fetch the event URL
- Fallback: browser navigation + snapshot

### Step 4: Project Final Count
```
current_rate = tweet_count / hours_elapsed
projected_total = tweet_count + current_rate × hours_remaining
```

Confidence levels:
- Remaining <6h: High (±10%)
- Remaining 6-12h: Medium (±20%)
- Remaining >12h: Low — be cautious

### Step 5: Find Edge & Trade
1. Map projected range to market outcomes
2. Compare projected probability vs market odds
3. **Only trade when**:
   - <12h remaining
   - Edge >10% (projected probability vs market price)
4. Position ≤4% of available assets, max $5 per trade
5. Hold to settlement (no stop-loss)

### Step 6: Report
Push structured report with tweet count, projection, odds comparison, and action taken.

## Slug Discovery
- Elon tweet markets are **not findable via Gamma search/events API**
- Must use direct slug lookup: `GET /events?slug=elon-musk-of-tweets-{period}`
- Period format examples: `march-5-march-7` (2-day), `march-3-march-10` (7-day)

## Historical Data
Elon's posting rate is highly unpredictable:
- Jan 2026: ~80 posts/day → Feb: ~44/day → Mar: ~21/day (declining trend)
- Short windows (2-day) see high variance
- Wait until data is sufficient before committing

## Changelog
- v1.0 (2026-03-15): Initial release
