# Polymarket Wallet Discovery Methods

> Methods for finding high-quality wallets to track and copy

## Method 1: Dune Profitability Dashboard (Best for PnL/ROI)

**URL**: https://dune.com/0xtakeprofits/polymarket-profitability-dashboard

**What it shows:**
- Wallet PnL Leaderboard (Top 500 all-time)
- Columns: wallet, net_pnl_usd, roi_pct, total_spent, total_received, trade_count, markets_traded, status
- Searchable by wallet address

**How to use:**
1. Open the dashboard
2. Scroll to "Wallet Leaderboard — Top Earners" table
3. Use search box to filter by address
4. Sort by ROI or PnL

**Pros**: Free, no login, reliable historical data
**Cons**: All-time data only (not recent), no win rate per wallet, 500 wallet limit

## Method 2: Dune Wallet Analyzooooor (Best for Win Rate)

**URL**: https://dune.com/kosard/polymarket-wallet-tracker

**What it shows:**
- Trading History for a specific wallet
- Trading Win-Rate Analysis (win rate, PnL, avg win/loss, profit factor)
- Buy Price Distribution
- Activity by Day of Week

**How to use:**
1. Open the dashboard
2. Enter wallet address in the parameter box
3. Click "Run" (⚠️ requires free Dune login)
4. Wait for results to load

**Pros**: Win rate, detailed per-wallet analysis
**Cons**: Requires login, one wallet at a time, can be slow

## Method 3: Polymarket Data API (Best for Real-Time)

**Endpoints (public, no auth):**
```
GET https://data-api.polymarket.com/positions?user={ADDRESS}&limit=50
GET https://data-api.polymarket.com/closed-positions?user={ADDRESS}&limit=50
GET https://data-api.polymarket.com/trades?user={ADDRESS}&limit=100
```

**How to use:**
```bash
# Quick check a wallet's recent activity
curl -s "https://data-api.polymarket.com/trades?user=0xADDRESS&limit=10" | python3 -m json.tool

# Check open positions
curl -s "https://data-api.polymarket.com/positions?user=0xADDRESS&limit=50" | python3 -m json.tool
```

**Key fields:**
- `cashPnl` — Unrealized PnL (open)
- `realizedPnl` — Realized PnL (closed)
- `avgPrice` — Entry price
- `curPrice` — Current price
- `outcome` — Selected side

**Pros**: Real-time, no login, programmatic
**Cons**: Limited to 50 positions per call, need to paginate for full history

## Method 4: Polymarket Leaderboard (Quick Browse)

**URL**: https://polymarket.com/leaderboard

**What it shows:**
- Top traders by various timeframes (D/W/M/ALL)
- PnL rankings
- Can click into profiles to see positions

**How to use:**
1. Open leaderboard
2. Filter by timeframe
3. Click trader profile
4. View open/closed positions
5. Copy wallet address from URL for deeper analysis

**Pros**: Easy, visual, shows recent activity
**Cons**: No win rate, limited to ranked wallets

## Method 5: Polymarket Profile Page

**URL**: https://polymarket.com/profile/{ADDRESS}?tab=positions

**What it shows:**
- Current open positions
- PnL (D/W/M/ALL)
- Trade history (if public profile)
- Market participation

**Pros**: Visual, shows what they're doing NOW
**Cons**: No win rate, no ROI, limited analytics

## Workflow: Finding Copy-Worthy Wallets

```
1. Start with Dune Leaderboard → identify high ROI wallets
2. Filter out bots: skip wallets with >500K trades or >10K markets
3. Check Polymarket profile → verify still active (recent trades)
4. Run analyze_wallet.py → get win rate, risk score
5. Run copy_score.py → compare multiple candidates
6. Monitor top 3-5 wallets → track their new positions
```

## Filtering Criteria for Copy Trading

| Signal | Good | Warning | Bad |
|--------|------|---------|-----|
| Win Rate | ≥65% | 50-65% | <50% |
| ROI | >200% | 50-200% | <50% |
| Risk Score (avg loss/avg win) | <0.6 | 0.6-1.0 | >1.0 |
| Markets Traded | 50-500 | <50 or >5000 | — |
| Trade Count | 1K-100K | >500K (likely bot) | <100 |
| Recent Activity | Trades in last 7 days | Last 30 days | >30 days inactive |

## Red Flags 🚩

- **Zero trades, huge PnL** → Protocol/internal address
- **Millions of trades** → Market-making bot (not directional, not copyable)
- **Sudden spike then inactive** → Lucky streak, not sustainable
- **Only bets on one category** → Not diversified, might be domain expert but risky
- **All positions same size** → Likely automated, no conviction scaling
