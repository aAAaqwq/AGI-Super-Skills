# Valid Commands & Common Mistakes

## Core Commands (no CLI needed)

These work out of the box with no external dependencies:
- `get_sports_markets`
- `get_sports_events`
- `get_series`
- `get_market_details`
- `get_event_details`
- `get_market_prices`
- `get_order_book`
- `get_sports_market_types`
- `search_markets`
- `get_price_history`
- `get_last_trade_price`

## CLI Commands: Data & Analytics (requires polymarket binary)

- `get_leaderboard` — trader leaderboard (period, order_by, limit)
- `get_positions` — open positions by wallet address
- `get_closed_positions` — closed positions by wallet address
- `get_portfolio_value` — portfolio value by wallet address
- `get_trade_history` — trade history by wallet address
- `get_activity` — activity feed by wallet address
- `get_holders` — market position holders by condition_id
- `get_open_interest` — open interest by condition_id
- `get_volume` — volume by event_id
- `get_traded` — markets traded by wallet address

## CLI Commands: Search & Tags (requires polymarket binary)

- `cli_search_markets` — full-text search (more powerful than search_markets)
- `get_tags` — list all tags
- `get_tag` — tag details
- `get_related_tags` — related tags

## CLI Commands: Comments & Profiles (requires polymarket binary)

- `get_comments` — comments on an entity (entity_type + entity_id)
- `get_comment` — single comment by ID
- `get_user_comments` — comments by user address
- `get_profile` — public user profile by address

## CLI Commands: Sports Metadata (requires polymarket binary)

- `cli_sports_list` — list all sports
- `cli_sports_teams` — teams by league

## CLI Commands: CLOB Extras (requires polymarket binary)

- `get_tick_size` — minimum tick size by token_id
- `get_fee_rate` — fee rate by token_id

## CLI Commands: Trading (requires polymarket binary + wallet)

- `create_order` — place a limit order (token_id, side, price, size)
- `market_order` — place a market order (token_id, side, amount)
- `cancel_order` — cancel an order by ID
- `cancel_all_orders` — cancel all open orders
- `get_balance` — check wallet balance
- `get_orders` — view open orders
- `get_user_trades` — view your trades

## CLI Commands: On-Chain (requires polymarket binary + wallet)

- `ctf_split` — split USDC into YES/NO tokens (condition_id, amount)
- `ctf_merge` — merge YES/NO tokens back to USDC (condition_id, amount)
- `ctf_redeem` — redeem winning tokens (condition_id)
- `approve_check` — check contract approvals
- `approve_set` — approve all contracts for trading

## Commands that DO NOT exist (commonly hallucinated)

- ~~`get_market_odds`~~ / ~~`get_odds`~~ -- market prices ARE the implied probability. Use `get_market_prices(token_id="...")` where price = probability.
- ~~`get_implied_probability`~~ -- the price IS the implied probability. No conversion needed.
- ~~`get_current_odds`~~ -- use `get_last_trade_price(token_id="...")` for the most recent price.
- ~~`get_markets`~~ -- the correct command is `get_sports_markets` (for browsing) or `search_markets` (for searching by keyword).

## Other common mistakes

- Using `market_id` where `token_id` is needed -- price and orderbook endpoints require the CLOB `token_id`, not the Gamma `market_id`. Always call `get_market_details` first to get `clobTokenIds`.
- Searching generic terms like "soccer" or "football" -- `search_markets` matches event titles. Use specific league names: "Premier League", "Champions League", "La Liga", etc.
- Forgetting to get the `token_id` before calling price/orderbook endpoints -- always fetch market details first.

If you're unsure whether a command exists, check this list. Do not try commands that aren't listed above.
