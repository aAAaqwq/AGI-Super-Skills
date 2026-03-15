# 📊 Position Monitor — Stop-Loss & Take-Profit Execution

Automated hourly position monitoring with ladder stop-loss, take-profit rules, and settlement claiming for Polymarket.

## Rules (highest priority, unconditional execution)

| Condition | Action |
|-----------|--------|
| Loss >40% | **Full exit** — sell everything |
| Loss >25% | **Cut 40%** — reduce position by 40% |
| Loss >15% + 4h downtrend (2 consecutive red candles) + buffer <3% | **Cut 50%** — trend-aware stop |
| Gain >50% | **Full sell** — take all profit |
| Gain >30% + settlement >24h away | **Sell 50%** — ladder take-profit |
| Price ≥99¢ + settlement >4h away | **Full sell** — time is cost |

## Execution Flow

### Step 1: Get Current Prices
Fetch real-time prices from Binance (BTC, ETH, SOL) and 4h candle trend data.

### Step 2: Get Portfolio
Open Polymarket portfolio page via browser, extract:
- Portfolio total value
- Cash balance
- Each position: market name, direction, avg cost, current price, P&L %

### Step 3: Claim Settlements
If any "Claim" buttons visible in the portfolio, click to claim settled positions.

### Step 4: Evaluate Each Position
Calculate P&L % for each position, check against stop-loss / take-profit rules.

### Step 5: Execute Sells
For positions triggering rules, execute sell orders through browser.

### Step 6: Report
Push monitoring report with portfolio snapshot, price data, trend info, and any actions taken.

## Failure Handling
- Browser shows login/auth dialog → Alert: "Polymarket session expired, manual refresh needed"
- Browser completely fails → Fallback to Gamma API for price data (cannot execute trades)

## Changelog
- v1.0 (2026-03-15): Initial release — ladder stop-loss + take-profit + claim automation
