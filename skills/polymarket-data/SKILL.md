---
name: polymarket
description: |
  Polymarket prediction markets — live odds, prices, order books, events, series, market search, leaderboards, portfolio analytics, trading, and on-chain operations. Core commands require no auth or CLI install. Advanced commands require the polymarket CLI binary.

  Use when: user asks about sports betting odds, prediction markets, win probabilities, market sentiment, or "who is favored to win" questions.
  Don't use when: user asks about actual match results, scores, or statistics — use the sport-specific skill: football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). Don't use for historical match data. Don't use for news — use sports-news instead. Don't confuse with Kalshi — Polymarket focuses on crypto-native prediction markets with deeper sports coverage; Kalshi is a US-regulated exchange with different market structure.
license: MIT
metadata:
  author: machina-sports
  version: "0.2.0"
---

# Polymarket — Sports Prediction Markets

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills polymarket get_sports_markets --limit=20
sports-skills polymarket search_markets --query="NBA Finals"
```

Python SDK (alternative):
```python
from sports_skills import polymarket

markets = polymarket.get_sports_markets(limit=20)
prices = polymarket.get_market_prices(token_id="abc123")
```

## Prerequisites

**Core commands** (11 commands) work out of the box — no dependencies, no API keys.

**CLI commands** (30+ commands) require the Polymarket CLI binary:
```bash
pip install sports-skills[polymarket]
```

Or via Homebrew:
```bash
brew tap Polymarket/polymarket-cli https://github.com/Polymarket/polymarket-cli
brew install polymarket
```

**Trading commands** additionally require a configured wallet. Three options:

```bash
# Option 1 — environment variable
export POLYMARKET_PRIVATE_KEY=0x...
```

```python
# Option 2 — Python SDK (per-session)
from sports_skills import polymarket
polymarket.configure(private_key="0x...")
```

```bash
# Option 3 — CLI config file (persists across sessions)
polymarket wallet import <private-key>
polymarket approve set
```

If a CLI command returns "polymarket CLI not installed", install with `pip install sports-skills[polymarket]`.

## Important Notes

- **Prices are probabilities.** A price of 0.65 means 65% implied probability. No conversion needed.
- **`token_id` vs `market_id`:** Price and orderbook endpoints require the CLOB `token_id`, not the Gamma `market_id`. Always call `get_market_details` first to get `clobTokenIds`.
- **`search_markets` matches event titles**, not sport categories. Use specific league names ("Premier League", "Champions League"), not generic terms ("soccer", "football").
- **`cli_search_markets`** is a more powerful full-text search via the CLI binary. Use it when `search_markets` returns no results.
- Before complex fetches, run the parameter validator: `bash scripts/validate_params.sh <command> [args]`

*For detailed reference data, see the files in the `references/` directory.*

## Workflows

### Workflow: Live Odds Check
1. `search_markets --query="<league/event name>"`
2. `get_market_details --market_id=<id>` to get CLOB token IDs.
3. `get_market_prices --token_id=<id>`
4. Present probabilities.

### Workflow: Event Overview
1. `get_sports_events --active=true`
2. Pick event, then `get_event_details --event_id=<id>`.
3. For each market, get prices.

### Workflow: Price Trend Analysis
1. Find market via `search_markets`.
2. `get_market_details` for token_id.
3. `get_price_history --token_id=<id> --interval=1w`
4. Present price movement.

### Workflow: Portfolio Analysis (requires CLI)
1. `get_positions --address=<wallet>` — open positions
2. `get_portfolio_value --address=<wallet>` — total value
3. `get_trade_history --address=<wallet> --limit=20` — recent trades
4. `get_activity --address=<wallet>` — full activity feed

### Workflow: Market Analytics (requires CLI)
1. `get_holders --condition_id=<id>` — who holds positions
2. `get_open_interest --condition_id=<id>` — total interest
3. `get_volume --event_id=<id>` — volume data

### Workflow: Leaderboard (requires CLI)
1. `get_leaderboard --period=week --order_by=pnl --limit=20`
2. `get_profile --address=<top_trader_address>` — inspect top traders

### Workflow: Trading (requires CLI + wallet)
1. `get_balance --asset_type=collateral` — check USDC balance
2. `cli_search_markets --query="NBA"` — find markets
3. `get_market_details --market_id=<id>` — get token_id
4. `create_order --token_id=<id> --side=buy --price=0.55 --size=10`
5. `get_orders` — verify order placed
6. `cancel_order --order_id=<id>` — cancel if needed

## Commands Reference

### Core Commands (no CLI needed)

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_sports_markets` | | limit, offset, sports_market_types, game_id, active, closed, order, ascending | Browse sports markets |
| `get_sports_events` | | limit, offset, active, closed, order, ascending, series_id | Browse sports events |
| `get_series` | | limit, offset | List series (leagues) |
| `get_market_details` | | market_id, slug | Single market details |
| `get_event_details` | | event_id, slug | Single event details |
| `get_market_prices` | | token_id, token_ids | Current CLOB prices |
| `get_order_book` | token_id | | Full order book |
| `get_sports_market_types` | | | Valid market types |
| `search_markets` | | query, sports_market_types, tag_id, limit | Search by keyword |
| `get_price_history` | token_id | interval, fidelity | Historical prices |
| `get_last_trade_price` | token_id | | Most recent trade |

### CLI Commands: Data & Analytics

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_leaderboard` | | period, order_by, limit | Trader leaderboard |
| `get_positions` | address | | Open positions |
| `get_closed_positions` | address | | Closed positions |
| `get_portfolio_value` | address | | Portfolio value |
| `get_trade_history` | address | limit | Trade history |
| `get_activity` | address | | Activity feed |
| `get_holders` | condition_id | | Market position holders |
| `get_open_interest` | condition_id | | Open interest |
| `get_volume` | event_id | | Volume data |
| `get_traded` | address | | Markets traded |

### CLI Commands: Search, Tags & Discovery

| Command | Required | Optional | Description |
|---|---|---|---|
| `cli_search_markets` | query | limit | Full-text search (CLI) |
| `get_tags` | | limit | List all tags |
| `get_tag` | tag | | Tag details |
| `get_related_tags` | tag | | Related tags |

### CLI Commands: Comments & Profiles

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_comments` | entity_type, entity_id | | Comments on entity |
| `get_comment` | comment_id | | Single comment |
| `get_user_comments` | address | | Comments by user |
| `get_profile` | address | | Public profile |

### CLI Commands: Sports Metadata

| Command | Required | Optional | Description |
|---|---|---|---|
| `cli_sports_list` | | | List sports |
| `cli_sports_teams` | league | limit | Teams by league |

### CLI Commands: CLOB Extras

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_tick_size` | token_id | | Minimum tick size |
| `get_fee_rate` | token_id | | Fee rate |

### CLI Commands: Trading (requires wallet)

| Command | Required | Optional | Description |
|---|---|---|---|
| `create_order` | token_id, side, price, size | order_type | Place limit order |
| `market_order` | token_id, side, amount | | Place market order |
| `cancel_order` | order_id | | Cancel order |
| `cancel_all_orders` | | | Cancel all orders |
| `get_balance` | | asset_type, token_id | Wallet balance |
| `get_orders` | | market | Open orders |
| `get_user_trades` | | | Your trades |

### CLI Commands: On-Chain (requires wallet)

| Command | Required | Optional | Description |
|---|---|---|---|
| `ctf_split` | condition_id, amount | | Split USDC to YES/NO |
| `ctf_merge` | condition_id, amount | | Merge YES/NO to USDC |
| `ctf_redeem` | condition_id | | Redeem winning tokens |
| `approve_check` | | address | Check approvals |
| `approve_set` | | | Approve contracts |

## Examples

User: "Who's favored to win the NBA Finals?"
1. Call `search_markets(query="NBA Finals", sports_market_types="moneyline")`
2. Get `token_id` from the market details
3. Call `get_market_prices(token_id="...")` for current odds
4. Present teams with implied probabilities (price = probability)

User: "Who will win the Premier League?"
1. Call `search_markets(query="English Premier League")` -- use full league name
2. Sort results by Yes outcome price descending
3. Present teams with implied probabilities (price = probability)

User: "Show me Champions League odds"
1. Call `search_markets(query="Champions League")`
2. Present top contenders with prices, volume, and liquidity

User: "Show me the Polymarket leaderboard"
1. Call `get_leaderboard(period="week", order_by="pnl", limit=20)`
2. Present traders with rank, username, PnL, and volume

User: "What positions does this wallet hold?"
1. Call `get_positions(address="0x...")`
2. Present positions with outcome, size, avg price, current value, PnL

User: "Buy 10 shares of YES on this market"
1. Call `get_market_details(market_id="...")` to get `token_id`
2. Call `create_order(token_id="...", side="buy", price="0.55", size="10")`
3. Call `get_orders()` to confirm

## Error Handling & Fallbacks

- If search returns 0 results, try full league names ("English Premier League" not "EPL", "Champions League" not "CL"). search_markets matches event titles.
- If `get_market_prices` fails, you likely used `market_id` instead of `token_id`. Always call `get_market_details` first to get CLOB `token_id`.
- If prices seem stale, check `get_last_trade_price` for the most recent trade. Low-liquidity markets may have wide spreads.
- If a CLI command returns "polymarket CLI not installed", the command requires the Rust binary. The original 11 commands work without the CLI.
- If a trading command fails with an auth error, ensure a wallet is configured: `polymarket wallet create && polymarket approve set`.
- **Never fabricate odds or probabilities.** If no market exists, state so.
