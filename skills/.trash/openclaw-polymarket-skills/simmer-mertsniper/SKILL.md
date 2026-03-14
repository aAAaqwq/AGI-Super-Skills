---
name: simmer-mertsniper
displayName: Mert Sniper
description: Near-expiry conviction trading on Polymarket. Snipe markets about to resolve when the odds are heavily skewed. Filter by topic, cap your bets, and only trade strong splits close to deadline.
metadata: {"clawdbot":{"emoji":"🎯","requires":{"env":["SIMMER_API_KEY"]},"cron":null,"autostart":false}}
authors:
  - Simmer (@simmer_markets)
attribution: "Strategy inspired by @0xMert_ — https://x.com/mert/status/2020216613279060433"
version: "1.0.0"
---

# Mert Sniper

Near-expiry conviction trading on Polymarket. Snipe markets about to resolve when the odds are heavily skewed.

> Strategy by [@0xMert_](https://x.com/mert/status/2020216613279060433) — filter by topic, cap your bets, wait until near expiry, and only trade strong splits.

## When to Use This Skill

> **Polymarket only.** All trades execute on Polymarket with real USDC. Use `--live` for real trades, dry-run is the default.

Use this skill when the user wants to:
- Trade markets that are about to resolve (last-minute conviction bets)
- Filter by topic (e.g. only SOL/crypto markets)
- Cap bet size (e.g. never more than $10)
- Only trade when odds are strongly skewed (e.g. 60/40 or better)
- Run an automated expiry-sniping strategy

## When NOT to Use This Skill

- Markets are far from expiry (> 10 minutes) — odds can flip
- Price split is narrow (< 55/45) — not enough conviction
- User wants to research markets (this executes trades, use research tools first)
- Running in observation mode only (use --dry-run flag instead of disabling safeguards)
- Market has ambiguous resolution criteria (high Oracle risk)
- User hasn't set max bet limits (safeguards required)

## Setup Flow

1. **Ask for Simmer API key**
   - Get it from simmer.markets/dashboard -> SDK tab
   - Store in environment as `SIMMER_API_KEY`

2. **Ask about settings** (or confirm defaults)
   - Market filter: Which markets to scan (default: all)
   - Max bet: Maximum per trade (default $10)
   - Expiry window: How close to resolution (default 2 minutes)
   - Min split: Minimum odds skew (default 60/40)

3. **Save settings to config.json or environment variables**

## Configuration

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Market filter | `SIMMER_MERT_FILTER` | (all) | Tag or keyword filter (e.g. `solana`, `crypto`) |
| Max bet | `SIMMER_MERT_MAX_BET` | 10.00 | Maximum USD per trade |
| Expiry window | `SIMMER_MERT_EXPIRY_MINS` | 2 | Only trade markets resolving within N minutes |
| Min split | `SIMMER_MERT_MIN_SPLIT` | 0.60 | Only trade when YES or NO >= this (e.g. 0.60 = 60/40) |
| Max trades/run | `SIMMER_MERT_MAX_TRADES` | 5 | Maximum trades per scan cycle |
| Smart sizing % | `SIMMER_MERT_SIZING_PCT` | 0.05 | % of balance per trade |

## Quick Commands

```bash
# Check account balance and positions
python scripts/status.py

# Detailed position list
python scripts/status.py --positions
```

**API Reference:**
- Base URL: `https://api.simmer.markets`
- Auth: `Authorization: Bearer $SIMMER_API_KEY`
- Portfolio: `GET /api/sdk/portfolio`
- Positions: `GET /api/sdk/positions`

## Running the Skill

```bash
# Dry run (default -- shows opportunities, no trades)
python mert_sniper.py

# Execute real trades
python mert_sniper.py --live

# Filter to specific markets
python mert_sniper.py --filter solana

# Custom expiry window (5 minutes)
python mert_sniper.py --expiry 5

# With smart position sizing (uses portfolio balance)
python mert_sniper.py --live --smart-sizing

# Check positions only
python mert_sniper.py --positions

# View config
python mert_sniper.py --config

# Disable safeguards (not recommended)
python mert_sniper.py --no-safeguards
```

## How It Works

Each cycle the script:
1. Fetches active markets from Simmer API (optionally filtered by tag/keyword)
2. Filters to markets resolving within the expiry window (default 2 minutes)
3. Checks the price split -- only trades when one side >= min_split (default 60%)
4. Determines direction: backs the favored side (higher probability)
5. **Safeguards**: Checks context for flip-flop warnings, slippage, market status
6. **Execution**: Places trade on the favored side, capped at max bet
7. Reports summary of scanned, filtered, and traded markets

## Example Output

```
🎯 Mert Sniper - Near-Expiry Conviction Trading
==================================================

  [DRY RUN] No trades will be executed. Use --live to enable trading.

  Configuration:
  Filter:        solana
  Max bet:       $10.00
  Expiry window: 2 minutes
  Min split:     60/40
  Max trades:    5
  Smart sizing:  Disabled
  Safeguards:    Enabled

  Fetching markets (filter: solana)...
  Found 12 active markets

  Markets expiring within 2 minutes: 2

  SOL highest price on Feb 10?
     Resolves in: 1m 34s
     Split: YES 72% / NO 28%
     Side: YES (72% >= 60%)
     [DRY RUN] Would buy $10.00 on YES

  Summary:
  Markets scanned: 12
  Near expiry:     2
  Strong split:    1
  Trades executed: 0

  [DRY RUN MODE - no real trades executed]
```

## Troubleshooting

**"No markets found"**
- Check your filter -- try without a filter first
- Markets may not be available (check simmer.markets)

**"No markets expiring within window"**
- Increase expiry window: `--expiry 10` (10 minutes)
- Or run more frequently (cron every minute)

**"Split too narrow"**
- Lower the min split: `--set min_split=0.55`
- This trades more often but with less conviction

**"Resolves in: 17h" on 15-min markets**
- Polymarket's `endDate` is the event-level end-of-day, not the individual market close time
- For 15-min crypto markets (e.g. "BTC Up or Down - Feb 8, 11PM ET"), the actual close time is in the question text but not in the API
- This is a Polymarket data limitation — widen the expiry window (`--expiry 1080`) as a workaround, or use the split filter to find conviction opportunities regardless of timing

**"API key invalid"**
- Get new key from simmer.markets/dashboard -> SDK tab
