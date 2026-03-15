---
name: quant-weekly-review
description: Weekly performance review with aggregate statistics, strategy layer breakdown, risk audit, and next-week adjustments. Use for Monday morning trading performance analysis and strategy tuning.
---

# Weekly Performance Review

Aggregate weekly stats and adjust strategy.

## Flow

### 1. Get Current Portfolio
Fetch portfolio data from Polymarket.

### 2. Read Past 7 Days
Load daily memory files, extract all trades.

### 3. Weekly Statistics
Total trades, win rate, total P&L, avg P&L/trade, largest win, largest loss.

### 4. Strategy Breakdown
For each layer (S1 sweet zone, S2 trend, S-Elon, S3 arbitrage, S7 short-term):
trades, win rate, total P&L, avg return.

### 5. Risk Review
Rule violations, stop-loss execution rate, concentration trends, max drawdown.

### 6. Next Week Adjustments
Strategies to scale up/down, category changes, new monitors, parameter tuning.

### 7. Report
Push weekly report. Write to daily memory.
