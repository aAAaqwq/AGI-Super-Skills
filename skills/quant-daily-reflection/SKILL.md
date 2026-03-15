# 📝 Daily P&L Reflection

Nightly full P&L review with trade-by-trade analysis, strategy evaluation, and lesson extraction.

## Execution Flow

### Step 1: Account Overview
- Open Polymarket portfolio via browser
- Record: Portfolio value, Cash, utilization %
- Fetch BTC/ETH/SOL prices from Binance
- Calculate daily P&L (compare morning vs now)
- Calculate cumulative ROI from initial capital

### Step 2: Trade-by-Trade Review
For each trade executed today:
- Market | Direction | Entry Price | Current/Settlement Price | Amount | P&L $ | P&L %
- Was the edge real? What was the information source? Did it hold up in hindsight?
- Was trend analysis correct? Entry judgment vs actual movement
- If loss: Root cause? Was it avoidable?

### Step 3: Strategy Layer Statistics
Group by strategy layer:
- S1 Sweet Zone: trade count / win rate / total P&L / avg return
- S2 Trend: trade count / win rate / total P&L
- S-Elon: tweet market performance
- S3 Arbitrage: opportunities found?
- **Which strategy performed best/worst? Why?**

### Step 4: Risk Audit
- Any rule violations? (bought >85¢? concentration >40%? sports/geopolitical? counter-trend?)
- Were stop-losses executed? Any missed stops?
- Position concentration trend

### Step 5: Market Environment Review
- Overall market sentiment (fear/greed/neutral)
- Major events impacting markets
- Which categories performed well/poorly

### Step 6: Tomorrow's Adjustments
- Specific parameter changes (price ranges, position sizes, category weights)
- Key markets/events to watch
- Execution improvements needed

### Step 7: Output
1. Write full reflection to daily memory file
2. Push summary report to channel
3. If important lesson found, update strategy rules or long-term memory

## Changelog
- v1.0 (2026-03-15): Initial release
