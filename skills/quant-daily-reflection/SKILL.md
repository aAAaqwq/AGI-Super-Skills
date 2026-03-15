---
name: quant-daily-reflection
description: Nightly P&L review with trade-by-trade analysis, strategy evaluation, risk audit, and lesson extraction. Use for daily trading performance review and continuous strategy improvement.
---

# Daily P&L Reflection

Full nightly review of trading performance.

## Flow

### 1. Account Overview
Open portfolio via browser. Record total value, cash, utilization. Fetch prices. Calculate daily P&L and cumulative ROI.

### 2. Trade-by-Trade Review
For each trade today:
- Market, direction, entry, current/settlement price, amount, P&L
- Was the edge real? Information source? Did it hold?
- Trend analysis correct? Entry vs actual movement?
- If loss: root cause, avoidable?

### 3. Strategy Statistics
Group by layer (S1 sweet zone, S2 trend, S-Elon, S3 arbitrage). For each: count, win rate, total P&L, avg return. Identify best/worst.

### 4. Risk Audit
- Rule violations? (>85¢, concentration >40%, sports/geo, counter-trend)
- Stop-losses executed? Missed stops?
- Position concentration trend

### 5. Market Environment
Overall sentiment, major events, category performance.

### 6. Tomorrow's Adjustments
Parameter changes, markets to watch, execution improvements.

### 7. Output
Write reflection to daily memory. Push summary. Update strategy rules if important lesson found.
