# ⏱️ Entry Timing Analysis — RSI/MA20/Odds Trend Scoring

Technical analysis script for determining optimal entry timing on Polymarket prediction markets. Combines Binance price indicators with Polymarket odds trend analysis.

## Usage
```bash
bash entry_timing.sh <symbol> [polymarket_token_id]
```

**Symbols**: btc, eth, sol, gold

## Output Format
```
ENTRY_NOW|BTC|$71,500|RSI:45|MA20:ABOVE(+0.3%)|4hMom:+0.19%|Vol:0.9x|Range:35%|Odds:FLAT(+0.1%)|Score:3|reasons...
```

## Signal Levels

| Signal | Score | Meaning |
|--------|-------|---------|
| ENTRY_NOW | ≥3 | Multiple bullish signals, good entry point |
| ENTRY_WAIT | 1-2 | Mixed signals, wait for better timing |
| ENTRY_SKIP | ≤0 | Bearish signals dominate, do not enter |

## Scoring Factors

### Binance Technical Indicators (1h candles, 30 bars)

| Factor | Bullish | Bearish |
|--------|---------|---------|
| RSI-14 | <30 oversold (+2), <40 low (+1) | >70 overbought (-2), >60 high (-1) |
| MA20 position | Pullback to MA20 (+2), Above near (+1) | Below MA20 (-1) |
| 24h range | Low position <25% (+1) | High position >80% (-1) |
| Volume | Noted but not scored | Noted but not scored |

### Polymarket Odds Trend (optional, requires token_id)

| Factor | Bullish | Bearish |
|--------|---------|---------|
| Odds dip | Price pulled back >3% from recent high (+2) | — |
| Odds chase | — | Price surged >5% from low + still rising (-2) |

## Data Sources
- **Binance API**: `/api/v3/klines?symbol={PAIR}&interval=1h&limit=30`
- **Polymarket CLOB**: `/prices-history?market={token_id}&interval=1h&fidelity=60`

## Integration
Designed to be called by the crypto-hunt skill as the 4th gate in the 5-gate entry system:
1. Sweet zone (75-85¢) ✓
2. Trend direction ✓
3. Buffer >3% ✓
4. **Entry timing (this script)** ✓
5. All pass → execute trade

## Changelog
- v1.0 (2026-03-15): Initial release — RSI + MA20 + odds trend scoring
