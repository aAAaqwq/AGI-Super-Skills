---
name: quant-entry-timing
description: Technical entry timing analysis for Polymarket prediction markets. Scores entry quality using Binance RSI-14, MA20 position, 24h range, and optional Polymarket odds trend. Outputs ENTRY_NOW/ENTRY_WAIT/ENTRY_SKIP with numerical score. Use as a gate before executing trades to avoid buying at poor entry points (overbought, chasing highs).
---

# Entry Timing — RSI/MA20/Odds Trend Scoring

Determine if now is a good time to enter a position.

## Usage
```bash
bash scripts/entry_timing.sh <symbol> [polymarket_token_id]
```
Symbols: `btc`, `eth`, `sol`, `gold`

## Output
```
ENTRY_NOW|BTC|$71,500|RSI:45|MA20:ABOVE(+0.3%)|4hMom:+0.19%|Vol:0.9x|Range:35%|Odds:FLAT(+0.1%)|Score:3|reasons
```

## Signals

| Signal | Score | Action |
|--------|-------|--------|
| ENTRY_NOW | ≥3 | Good entry, proceed |
| ENTRY_WAIT | 1-2 | Mixed signals, hold |
| ENTRY_SKIP | ≤0 | Bad entry, skip |

## Scoring

| Factor | Bullish | Bearish |
|--------|---------|---------|
| RSI <30 / <40 | +2 / +1 | — |
| RSI >70 / >60 | — | -2 / -1 |
| Pullback to MA20 | +2 | — |
| Above MA20 (near) | +1 | — |
| Below MA20 | — | -1 |
| 24h low position (<25%) | +1 | — |
| 24h high position (>80%) | — | -1 |
| Odds dip (>3% from high) | +2 | — |
| Odds chase (>5% surge) | — | -2 |

## Data Sources
- Binance: 1h klines (30 bars) for RSI/MA/volume
- Polymarket CLOB: `/prices-history` for odds trend (optional)
