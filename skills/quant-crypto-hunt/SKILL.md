# 🔍 Polymarket Crypto Hunt — Full Category Daily Scanner

Automated prediction market scanner that finds sweet-zone opportunities across crypto, commodities, and daily up/down markets on Polymarket.

## Strategy Rules (violating any = no trade)

1. **Sweet Zone 75-85¢** — The side you're buying must be 75-85¢. Never buy >85¢ or <75¢.
2. **Only buy the SWEET-marked side** — Script outputs SWEET_YES → only buy YES, SWEET_NO → only buy NO, SWEET_UP → only buy Up, SWEET_DN → only buy Down. Never reverse-buy the non-SWEET side!
3. **Skip on trend ban** — If SWEET_YES but trend is BAN_YES_UP, skip the market entirely. Don't reverse-buy NO.
4. **Buffer >3%** — Buffer = |threshold - current_price| / current_price. Applies to both YES and NO.
5. **Trend gate** — 4h candles: ≥3/4 down = ban YES/Up | ≥2 down + 24h drop >1% = ban YES/Up
6. **Max $20 per trade** — If liquidity < $500, limit to $3-5
7. **Entry timing** — entry_timing.sh must output ENTRY_NOW to proceed. ENTRY_WAIT/ENTRY_SKIP = no trade.

## Execution Flow

### Step 1: Trend Analysis
```bash
bash scripts/trend_analysis.sh
```
Output: `BTC|71500|24h:+0.67%|4h:4↑0↓|STRONG_UP|OK_YES_UP|Support:...|Resist:...|Candles:...`

### Step 2: Market Scan
```bash
bash scripts/scan_markets.sh
```
Output: `ABOVE|BTC above $74k...|YES:9%|NO:91%|Vol:$XX|Liq:$XX|End:...|SWEET_NO|slug`

### Step 3: Entry Timing Analysis
For each SWEET-marked market, run entry timing for the corresponding asset:
```bash
bash scripts/entry_timing.sh btc [token_id]
bash scripts/entry_timing.sh eth [token_id]
bash scripts/entry_timing.sh sol [token_id]
bash scripts/entry_timing.sh gold [token_id]
```
Output: `ENTRY_NOW|BTC|$71,500|RSI:45|MA20:ABOVE(+0.3%)|4hMom:+0.19%|Vol:0.9x|Range:35%|Odds:FLAT(+0.1%)|Score:3|reasons...`

### Step 4: Decision Matrix

For each SWEET-marked market (ignore OUT):

| Marker | Buy Direction | Trend Requirement | Entry Timing |
|--------|---------------|-------------------|--------------|
| SWEET_YES | Buy YES only | OK_YES_UP or CAUTION | ENTRY_NOW |
| SWEET_NO | Buy NO only | BAN_YES_UP | ENTRY_NOW |
| SWEET_UP | Buy Up only | OK_YES_UP or CAUTION | ENTRY_NOW |
| SWEET_DN | Buy Down only | BAN_YES_UP | ENTRY_NOW |

Check order:
1. SWEET marker → determine buy direction
2. Trend check → allowed for that direction?
3. Buffer check → >3%?
4. Entry timing → ENTRY_NOW?
5. **All pass → execute trade** | **Any fail → skip**

### Step 5: Execute Trade (if any)
Navigate to Polymarket event page via browser and execute the trade.

### Step 6: Report
Generate and push a structured report with prices, trends, entry signals, sweet zone scan results, and actions taken.

## Scripts

| Script | Function | Input | Output |
|--------|----------|-------|--------|
| `trend_analysis.sh` | 4h K-line trend + 24h change | none/btc/eth/etc | OK_YES_UP / BAN_YES_UP / CAUTION |
| `scan_markets.sh` | Polymarket Above + Up/Down scan | none | SWEET_YES/NO/UP/DN or OUT |
| `entry_timing.sh` | RSI/MA20/odds trend entry judgment | symbol [token_id] | ENTRY_NOW / WAIT / SKIP + Score |

## Entry Timing Signals

| Signal | Score | Meaning |
|--------|-------|---------|
| ENTRY_NOW | ≥3 | Multiple bullish signals, good entry |
| ENTRY_WAIT | 1-2 | Mixed signals, wait for better timing |
| ENTRY_SKIP | ≤0 | Multiple bearish signals, do not enter |

Scoring factors:
- **RSI-14**: <30 oversold (+2) / <40 low (+1) / >70 overbought (-2) / >60 high (-1)
- **MA20 position**: Pullback to MA20 (+2) / Above near (+1) / Below (-1)
- **24h range position**: Low <25% (+1) / High >80% (-1)
- **Odds trend**: Odds dip/pullback (+2) / Odds chasing (-2)

## Market Types Scanned

- **Above markets**: BTC/ETH/SOL threshold markets (e.g., "Bitcoin above $74k")
- **Up/Down daily**: GC(Gold)/BTC/ETH/SOL daily settlement (e.g., "GC up or down on March 15")
- Slugs: `{coin}-above-on-{month}-{day}`, `{ticker}-up-or-down-on-{month}-{day}-{year}`

## Changelog
- v1.0 (2026-03-15): Initial release — 5-gate entry system (sweet zone + trend + buffer + entry timing + direction)
