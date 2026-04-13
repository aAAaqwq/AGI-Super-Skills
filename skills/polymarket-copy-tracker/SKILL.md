---
name: polymarket-copy-tracker
description: Analyze top Polymarket traders for copy trading. Use when asked to find best traders to copy, analyze trader performance/history, evaluate wallet PnL, discover high-ROI wallets, or research trader win rates on Polymarket. Supports Dune analytics, Polymarket Data API, and automated scoring.
---

# Polymarket Copy Tracker

Analyze top Polymarket traders for copy trading signals.

## Data Sources

1. **Data API** (`data-api.polymarket.com`) - Wallet history (public, no auth)
2. **Polymarket.com/leaderboard** - Top traders page (extract wallet addresses)

## Quick Start

### Step 1: Get wallet addresses
```bash
python3 scripts/find_top_traders.py --limit 20
```

### Step 2: Analyze a wallet
```bash
python3 scripts/analyze_wallet.py 0xWALLET_ADDRESS
python3 scripts/analyze_wallet.py 0xWALLET_ADDRESS --json  # raw JSON output
```

### Step 3: Score multiple wallets
```bash
python3 scripts/copy_score.py wallet1 wallet2 wallet3 ...
```

## API Endpoints

### Data API (Public)

```bash
# Open positions
GET https://data-api.polymarket.com/positions?user=WALLET&limit=50

# Closed/resolved positions
GET https://data-api.polymarket.com/closed-positions?user=WALLET&limit=50

# Trade history
GET https://data-api.polymarket.com/trades?user=WALLET&limit=100
```

**Key fields in positions:**
- `title` - Market name
- `size` - Number of shares
- `avgPrice` - Average entry price
- `currentValue` - Current market value
- `cashPnl` - Unrealized P&L (open positions)
- `realizedPnl` - Realized P&L (resolved positions)
- `outcome` - Selected outcome (Yes/No/Team name)
- `redeemable` - True if resolved and can be redeemed

## Scoring Criteria

| Metric | Weight | Good | Bad |
|--------|--------|------|-----|
| Win Rate | 40% | ≥65% | <45% |
| Total PnL | 30% | ≥$1000 | <$0 |
| Risk Score | 20% | <0.8 | ≥1.0 |
| Sample Size | 10% | ≥20 trades | <5 trades |

**Risk Score** = Avg Loss / Avg Win (lower = better, <1.0 means wins > losses)

**Final Score**: 0-100 → COPYABLE (≥70), CAUTION (45-69), NOT RECOMMENDED (<45)

## Example Output

```
=== Analyzing Wallet: 0xf19572...8057 ===

CLOSED POSITIONS (Win Rate & PnL)
==================================================
Total Closed:    49
Win Rate:        67.3%  (33W / 16L)
Total PnL:       +$2,223,761
Avg Win:         $110,028
Avg Loss:        $87,948
Risk Score:      0.80  ✅ GOOD

OPEN POSITIONS: 8 | Value: $17,739 | Unrealized: -$445,325

COPY ASSESSMENT
==================================================
Score: 92/100  ✅ COPYABLE
  ✅ High win rate (67%)
  ✅ Excellent PnL ($2,223,761)
  ✅ Low risk (score 0.80)
  ✅ Good sample (49 trades)
```

## Scripts

| Script | Purpose |
|--------|---------|
| `find_top_traders.py` | Extract wallet addresses from polymarket.com/leaderboard |
| `analyze_wallet.py` | Deep-dive a single wallet (positions, trades, score) |
| `copy_score.py` | Score and rank multiple wallets in parallel |

## Curated Wallet Database

See [references/top-wallets.md](references/top-wallets.md) for a curated list of high-quality wallets organized by tier:
- **Tier 2 wallets** are best for copy trading (high ROI + human-scale activity)
- Includes filtering notes (skip protocol addresses, bots, etc.)

## Discovery Methods

See [references/discovery-methods.md](references/discovery-methods.md) for 5 methods to find wallets:
1. **Dune Profitability Dashboard** — PnL/ROI rankings (free, no login)
2. **Dune Wallet Analyzooooor** — Per-wallet win rate (free, needs login)
3. **Polymarket Data API** — Real-time positions (public API)
4. **Polymarket Leaderboard** — Quick browse top traders
5. **Polymarket Profile Page** — Visual current positions

## Quick Workflow

```bash
# 1. Score a known wallet
python3 scripts/analyze_wallet.py 0x2785e7022dc20757108204b13c08cea8613b70ae

# 2. Compare multiple candidates
python3 scripts/copy_score.py 0x2785e702... 0xed107a85... 0x6a72f618...

# 3. Find new top traders
python3 scripts/find_top_traders.py --limit 20
```

## Notes

- Data API is public (read-only, no auth required)
- Rate limit: ~100 req/min
- Not all wallets have public history (new or privacy)
- `closed-positions` has resolved trades, `positions` has open trades
- PnL is calculated from face value (shares × $1) minus cost (shares × avgPrice)
- Dune data is all-time historical; API shows recent activity
- Wallets with 0 trades but huge PnL are protocol addresses — skip them
- Wallets with >500K trades are likely market-making bots — not suitable for copy trading
