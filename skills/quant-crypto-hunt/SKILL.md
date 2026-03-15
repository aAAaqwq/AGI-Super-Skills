---
name: quant-crypto-hunt
description: Automated Polymarket prediction market scanner. Scans crypto above-threshold markets and commodity up/down daily markets to find sweet-zone (75-85¢) opportunities. Integrates 5-gate entry system: sweet zone + trend direction + buffer + entry timing (RSI/MA20) + direction validation. Use for automated periodic market scanning and trade execution on Polymarket.
---

# Crypto Hunt — Full Category Daily Scanner

Scan all daily markets, find sweet-zone opportunities, validate entry timing, execute trades.

## Iron Rules (violate any = no trade)

1. **Sweet zone 75-85¢** — buy side must be 75-85¢
2. **SWEET-marked side only** — SWEET_YES→buy YES, SWEET_NO→buy NO, SWEET_UP→buy Up, SWEET_DN→buy Down. Never reverse.
3. **Trend ban = skip** — SWEET_YES + BAN_YES_UP → skip market, not buy NO
4. **Buffer >3%** — |threshold − price| / price > 3%
5. **Trend gate** — 4h: ≥3/4 down = ban YES/Up; ≥2 down + 24h >1% drop = ban YES/Up
6. **Max $20/trade** — liquidity <$500 → limit $3-5
7. **Entry timing** — `entry_timing.sh` must output ENTRY_NOW

## Flow

### 1. Trend Analysis
```bash
bash scripts/trend_analysis.sh
```

### 2. Market Scan
```bash
bash scripts/scan_markets.sh
```

### 3. Entry Timing
```bash
bash scripts/entry_timing.sh btc
bash scripts/entry_timing.sh eth
bash scripts/entry_timing.sh sol
bash scripts/entry_timing.sh gold
```

Run all three scripts. Do not substitute with manual curl.

### 4. Decision Matrix

| Marker | Direction | Trend Required | Entry Required |
|--------|-----------|----------------|----------------|
| SWEET_YES | YES | OK_YES_UP or CAUTION | ENTRY_NOW |
| SWEET_NO | NO | BAN_YES_UP | ENTRY_NOW |
| SWEET_UP | Up | OK_YES_UP or CAUTION | ENTRY_NOW |
| SWEET_DN | Down | BAN_YES_UP | ENTRY_NOW |

Gate order: SWEET → trend → buffer >3% → entry timing → all pass = trade.

### 5. Execute (if any)
Navigate to `https://polymarket.com/event/{slug}` via browser. Wait 5s, snapshot, buy.

### 6. Report
Push structured report: prices, trends, entry signals, sweet zone results, actions.

## Scripts

| Script | Output |
|--------|--------|
| `scripts/trend_analysis.sh` | `BTC\|71500\|24h:+0.67%\|4h:4↑0↓\|OK_YES_UP` |
| `scripts/scan_markets.sh` | `ABOVE\|BTC above $74k\|YES:9%\|SWEET_NO\|slug` |
| `scripts/entry_timing.sh <sym>` | `ENTRY_NOW\|BTC\|$71.5k\|RSI:45\|Score:3` |

## Market Types

- **Above**: `{coin}-above-on-{month}-{day}` (BTC/ETH/SOL)
- **Up/Down**: `{ticker}-up-or-down-on-{month}-{day}-{year}` (GC/BTC/ETH/SOL)
