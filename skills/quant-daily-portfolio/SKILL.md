---
name: quant-daily-portfolio
description: Morning Polymarket portfolio snapshot with Binance prices, settlement claiming, and daily report. Use for daily portfolio review and position tracking.
---

# Daily Portfolio Snapshot

Morning full-position review.

## Flow

1. Fetch BTC/ETH/SOL prices from Binance
2. Read strategy file and recent memory for context
3. Open `https://polymarket.com/portfolio` via browser, extract portfolio value, cash, positions with P&L
4. Claim any settled positions (click Claim buttons)
5. Handle failures: auth expired → alert; browser fails → Gamma API fallback
6. Push daily report: portfolio, cash, prices, each position with P&L, recommendations
7. Append to daily memory file
