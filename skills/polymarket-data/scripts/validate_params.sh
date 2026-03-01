#!/bin/bash
# Validates polymarket parameters
COMMAND="${1:-}"

# CLI-required commands
CLI_COMMANDS="get_leaderboard get_positions get_closed_positions get_portfolio_value get_trade_history get_activity get_holders get_open_interest get_volume get_traded cli_search_markets get_tags get_tag get_related_tags get_comments get_comment get_user_comments get_profile cli_sports_list cli_sports_teams get_tick_size get_fee_rate create_order market_order cancel_order cancel_all_orders get_balance get_orders get_user_trades ctf_split ctf_merge ctf_redeem approve_check approve_set"

if echo "$CLI_COMMANDS" | grep -qw "$COMMAND"; then
  if ! command -v polymarket &>/dev/null; then
    echo "ERROR: $COMMAND requires the polymarket CLI. Install with: brew tap Polymarket/polymarket-cli https://github.com/Polymarket/polymarket-cli && brew install polymarket"
    exit 1
  fi
fi

# Trading commands need wallet
TRADING_COMMANDS="create_order market_order cancel_order cancel_all_orders approve_set ctf_split ctf_merge ctf_redeem"
if echo "$TRADING_COMMANDS" | grep -qw "$COMMAND"; then
  echo "WARNING: $COMMAND requires an authenticated wallet. Ensure POLYMARKET_PRIVATE_KEY is set or wallet is configured."
fi

# token_id vs market_id warning
if [[ "$COMMAND" == "get_market_prices" || "$COMMAND" == "get_order_book" || "$COMMAND" == "get_price_history" || "$COMMAND" == "get_last_trade_price" ]]; then
  if [[ "$*" != *"--token_id="* ]]; then
    echo "ERROR: $COMMAND requires --token_id (CLOB token ID), not market_id. Get it from get_market_details."
    exit 1
  fi
fi

# Search tips
if [[ "$COMMAND" == "search_markets" ]]; then
  echo "TIP: search_markets matches event titles. Use league names (e.g., 'Premier League', 'NBA Finals'), not generic terms like 'soccer'."
fi
echo "OK"
