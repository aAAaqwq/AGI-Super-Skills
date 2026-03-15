# 📊 Daily Portfolio Snapshot

Morning portfolio review — full position snapshot with Binance prices, settlement claiming, and daily report.

## Execution Flow

### Step 1: Fetch Market Prices
Get real-time prices from Binance API for BTC, ETH, SOL.

### Step 2: Load Context
Read strategy file and recent memory/logs for context.

### Step 3: Get Polymarket Portfolio
Open portfolio page via browser, extract:
- Portfolio total value and cash balance
- Each position: market, direction, avg cost, current price, P&L %
- Claim any settled positions

### Step 4: Handle Failures
- Login expired → push alert for manual refresh
- Browser fails → fallback to Gamma API for prices

### Step 5: Push Daily Report
Format: portfolio value, cash, prices, each position with P&L, and action recommendations.

### Step 6: Update Daily Memory
Append portfolio snapshot to daily memory file.

## Changelog
- v1.0 (2026-03-15): Initial release
