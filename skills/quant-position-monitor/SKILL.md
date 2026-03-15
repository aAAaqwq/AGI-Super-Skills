---
name: quant-position-monitor
description: Automated hourly Polymarket position monitoring with ladder stop-loss, take-profit, and settlement claiming. Checks each position against loss/gain thresholds and executes sells via browser. Use for periodic portfolio risk management and automated exit execution.
---

# Position Monitor — Stop-Loss & Take-Profit

Check all positions hourly. Execute exits when thresholds trigger.

## Exit Rules (unconditional, highest priority)

| Condition | Action |
|-----------|--------|
| Loss >40% | Full exit |
| Loss >25% | Cut 40% of position |
| Loss >15% + 4h downtrend + buffer <3% | Cut 50% (trend-aware) |
| Gain >50% | Full sell |
| Gain >30% + settlement >24h | Sell 50% |
| Price ≥99¢ + settlement >4h | Full sell |

## Flow

### 1. Get Prices
```bash
bash scripts/price_check.sh all
```

### 2. Get Portfolio
Open `https://polymarket.com/portfolio` via browser. Wait 5s, snapshot. Extract:
- Portfolio total, cash balance
- Each position: market, direction, avg cost, current price, P&L %

### 3. Claim Settlements
Click any visible "Claim" buttons. Confirm if dialog appears.

### 4. Evaluate & Execute
For each position: calculate P&L %, check against exit rules, sell if triggered.

### 5. Report
Push: portfolio snapshot, prices, actions taken.

## Failure Handling
- Auth dialog → alert "session expired, manual refresh needed"
- Browser fails → Gamma API fallback (read-only, no sells)
