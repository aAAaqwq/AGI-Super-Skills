#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///
"""
Polymarket prediction market data + trading.

Read-only commands use the Gamma API (no auth needed).
Trading commands wrap the official Polymarket CLI (Rust binary).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

import requests

BASE_URL = "https://gamma-api.polymarket.com"

# ---------------------------------------------------------------------------
# CLI binary detection
# ---------------------------------------------------------------------------

def find_polymarket_cli() -> str | None:
    """Find the polymarket CLI binary."""
    # Check common locations
    for p in [
        shutil.which("polymarket"),
        os.path.expanduser("~/.local/bin/polymarket"),
        "/usr/local/bin/polymarket",
    ]:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def require_cli() -> str:
    """Return CLI path or exit with install instructions."""
    cli = find_polymarket_cli()
    if not cli:
        print("❌ Polymarket CLI not installed. Trading commands require it.", file=sys.stderr)
        print("   Install: curl -sSL https://raw.githubusercontent.com/Polymarket/polymarket-cli/main/install.sh | sh", file=sys.stderr)
        sys.exit(1)
    return cli


def run_cli(args: list[str], json_output: bool = True) -> dict | str:
    """Run a polymarket CLI command and return output."""
    cli = require_cli()
    cmd = [cli]
    if json_output:
        cmd += ["-o", "json"]
    cmd += args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        print(f"❌ CLI error: {err}", file=sys.stderr)
        sys.exit(1)
    if json_output:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.stdout.strip()
    return result.stdout.strip()

# ---------------------------------------------------------------------------
# Gamma API helpers (read-only, no auth)
# ---------------------------------------------------------------------------

def fetch(endpoint: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_price(price) -> str:
    if price is None:
        return "N/A"
    try:
        return f"{float(price) * 100:.1f}%"
    except Exception:
        return str(price)


def format_volume(volume) -> str:
    if volume is None:
        return "N/A"
    try:
        v = float(volume)
        if v >= 1_000_000:
            return f"${v/1_000_000:.1f}M"
        elif v >= 1_000:
            return f"${v/1_000:.1f}K"
        else:
            return f"${v:.0f}"
    except Exception:
        return str(volume)


def format_market(market: dict) -> str:
    lines = []
    question = market.get('question') or market.get('title', 'Unknown')
    lines.append(f"📊 **{question}**")

    outcomes = market.get('outcomes', [])
    if outcomes and len(outcomes) >= 2:
        prices = market.get('outcomePrices', [])
        if prices and len(prices) >= 2:
            lines.append(f"   Yes: {format_price(prices[0])} | No: {format_price(prices[1])}")
    elif market.get('bestBid') or market.get('bestAsk'):
        lines.append(f"   Bid: {format_price(market.get('bestBid'))} | Ask: {format_price(market.get('bestAsk'))}")

    volume = market.get('volume') or market.get('volumeNum')
    if volume:
        lines.append(f"   Volume: {format_volume(volume)}")

    end_date = market.get('endDate') or market.get('end_date_iso')
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            lines.append(f"   Ends: {dt.strftime('%b %d, %Y')}")
        except Exception:
            pass

    slug = market.get('slug') or market.get('market_slug')
    if slug:
        lines.append(f"   🔗 polymarket.com/event/{slug}")

    return '\n'.join(lines)


def format_event(event: dict) -> str:
    lines = []
    title = event.get('title', 'Unknown Event')
    lines.append(f"🎯 **{title}**")

    volume = event.get('volume')
    if volume:
        lines.append(f"   Total Volume: {format_volume(volume)}")

    markets = event.get('markets', [])
    if markets:
        lines.append(f"   Markets: {len(markets)}")
        for m in markets[:5]:
            q = m.get('question', m.get('groupItemTitle', ''))
            prices = m.get('outcomePrices')
            if prices:
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except Exception:
                        pass
                if isinstance(prices, list) and len(prices) >= 1:
                    lines.append(f"   • {q}: {format_price(prices[0])}")
                else:
                    lines.append(f"   • {q}")
            else:
                lines.append(f"   • {q}")
        if len(markets) > 5:
            lines.append(f"   ... and {len(markets) - 5} more")

    slug = event.get('slug')
    if slug:
        lines.append(f"   🔗 polymarket.com/event/{slug}")

    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# Read-only commands (Gamma API)
# ---------------------------------------------------------------------------

def cmd_trending(args):
    """Get trending/active markets."""
    params = {
        'order': 'volume24hr',
        'ascending': 'false',
        'closed': 'false',
        'limit': args.limit
    }
    data = fetch('/events', params)
    print(f"🔥 **Trending on Polymarket**\n")
    for event in data:
        print(format_event(event))
        print()


def cmd_search(args):
    """Search markets."""
    params = {'closed': 'false', 'limit': args.limit}
    try:
        resp = requests.get(f"{BASE_URL}/search", params={'query': args.query, 'limit': args.limit}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            events = data if isinstance(data, list) else data.get('events', data.get('markets', []))
            print(f"🔍 **Search: '{args.query}'**\n")
            if not events:
                print("No markets found.")
                return
            for item in events[:args.limit]:
                if 'markets' in item:
                    print(format_event(item))
                else:
                    print(format_market(item))
                print()
            return
    except Exception:
        pass

    # Fallback
    data = fetch('/events', {'closed': 'false', 'limit': 100})
    query_lower = args.query.lower()
    matches = []
    for event in data:
        title = event.get('title', '').lower()
        desc = event.get('description', '').lower()
        if query_lower in title or query_lower in desc:
            matches.append(event)
            continue
        for m in event.get('markets', []):
            if query_lower in m.get('question', '').lower():
                matches.append(event)
                break

    print(f"🔍 **Search: '{args.query}'**\n")
    if not matches:
        print("No markets found.")
        return
    for event in matches[:args.limit]:
        print(format_event(event))
        print()


def cmd_event(args):
    """Get specific event by slug."""
    try:
        data = fetch(f'/events/slug/{args.slug}')
        if isinstance(data, list) and data:
            data = data[0]
        print(format_event(data))
        markets = data.get('markets', [])
        if markets:
            print(f"\n📊 **All Markets:**\n")
            for m in markets:
                print(format_market(m))
                print()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"❌ Event not found: {args.slug}")
        else:
            raise


def cmd_category(args):
    """Get markets by category."""
    categories = {
        'politics': 'politics', 'crypto': 'crypto', 'sports': 'sports',
        'tech': 'tech', 'entertainment': 'entertainment',
        'science': 'science', 'business': 'business'
    }
    tag = categories.get(args.category.lower(), args.category)
    params = {
        'closed': 'false', 'limit': args.limit,
        'order': 'volume24hr', 'ascending': 'false'
    }
    data = fetch('/events', params)
    tag_lower = tag.lower()
    matches = []
    for event in data:
        title = event.get('title', '').lower()
        tags = [t.get('label', '').lower() for t in event.get('tags', [])]
        if tag_lower in title or tag_lower in ' '.join(tags):
            matches.append(event)

    print(f"📁 **Category: {args.category.title()}**\n")
    if not matches:
        print(f"(No exact matches for '{tag}', showing trending)\n")
        matches = data[:args.limit]
    for event in matches[:args.limit]:
        print(format_event(event))
        print()

# ---------------------------------------------------------------------------
# Order book / price commands (CLI, no wallet needed)
# ---------------------------------------------------------------------------

def cmd_book(args):
    """Show order book for a token."""
    data = run_cli(["clob", "book", args.token])
    if isinstance(data, dict):
        print(f"📖 **Order Book** ({args.token[:16]}...)\n")
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if asks:
            print("  Asks:")
            for a in asks[:10]:
                print(f"    {a.get('price', '?')} — {a.get('size', '?')} shares")
        if bids:
            print("  Bids:")
            for b in bids[:10]:
                print(f"    {b.get('price', '?')} — {b.get('size', '?')} shares")
    else:
        print(data)


def cmd_price_history(args):
    """Show price history for a token."""
    cli_args = ["clob", "price-history", args.token, "--interval", args.interval]
    if args.fidelity:
        cli_args += ["--fidelity", str(args.fidelity)]
    data = run_cli(cli_args)
    if isinstance(data, list):
        print(f"📈 **Price History** ({args.token[:16]}..., interval={args.interval})\n")
        for point in data[-20:]:  # Last 20 points
            t = point.get("t", "")
            p = point.get("p", "")
            print(f"  {t}  {format_price(p)}")
    else:
        print(data)

# ---------------------------------------------------------------------------
# Wallet commands (CLI, no trading)
# ---------------------------------------------------------------------------

def cmd_wallet_setup(args):
    """Interactive wallet setup."""
    cli = require_cli()
    print("🔧 **Wallet Setup**")
    print("Running interactive setup. This will guide you through wallet creation.\n")
    os.execvp(cli, [cli, "setup"])


def cmd_wallet_show(args):
    """Show wallet info."""
    data = run_cli(["wallet", "show"], json_output=False)
    print(f"👛 **Wallet Info**\n")
    print(data)


def cmd_wallet_balance(args):
    """Show balances."""
    print(f"💰 **Balances**\n")
    # Collateral (USDC)
    data = run_cli(["clob", "balance", "--asset-type", "collateral"], json_output=False)
    print(f"  USDC: {data}")
    if args.token:
        data2 = run_cli(["clob", "balance", "--asset-type", "conditional", "--token", args.token], json_output=False)
        print(f"  Token ({args.token[:16]}...): {data2}")

# ---------------------------------------------------------------------------
# Trading commands (CLI, wallet required, confirmation required)
# ---------------------------------------------------------------------------

def cmd_trade(args):
    """Place a trade (buy or sell)."""
    side = args.side
    token = args.token
    
    if args.market_order:
        # Market order
        amount = args.amount
        if not amount:
            print("❌ --amount required for market orders", file=sys.stderr)
            sys.exit(1)
        
        print(f"🔔 **{'Buy' if side == 'buy' else 'Sell'} Market Order**")
        print(f"   Token: {token}")
        print(f"   Side:  {side.upper()}")
        print(f"   Amount: ${amount}")
        print(f"\n⚠️  This will execute immediately at current market price.")
        
        if not args.confirm:
            print(f"\n❗ Add --confirm to execute this trade.")
            print(f"   This involves REAL MONEY on Polygon.")
            return
        
        data = run_cli(["clob", "market-order", "--token", token, "--side", side, "--amount", str(amount)], json_output=False)
        print(f"\n✅ Order submitted:\n{data}")
    else:
        # Limit order
        price = args.price
        size = args.size
        if not price or not size:
            print("❌ --price and --size required for limit orders (or use --market-order with --amount)", file=sys.stderr)
            sys.exit(1)
        
        cost = float(price) * float(size)
        print(f"🔔 **{'Buy' if side == 'buy' else 'Sell'} Limit Order**")
        print(f"   Token: {token}")
        print(f"   Side:  {side.upper()}")
        print(f"   Price: {price}")
        print(f"   Size:  {size} shares")
        print(f"   Cost:  ~${cost:.2f}")
        
        if not args.confirm:
            print(f"\n❗ Add --confirm to execute this trade.")
            print(f"   This involves REAL MONEY on Polygon.")
            return
        
        cli_args = ["clob", "create-order", "--token", token, "--side", side, "--price", str(price), "--size", str(size)]
        if args.post_only:
            cli_args.append("--post-only")
        data = run_cli(cli_args, json_output=False)
        print(f"\n✅ Order submitted:\n{data}")


def cmd_orders(args):
    """List or cancel orders."""
    if args.cancel:
        if args.cancel == "all":
            print("🗑️ **Cancel All Orders**")
            if not args.confirm:
                print("\n❗ Add --confirm to cancel all open orders.")
                return
            data = run_cli(["clob", "cancel-all"], json_output=False)
        else:
            print(f"🗑️ **Cancel Order:** {args.cancel}")
            if not args.confirm:
                print("\n❗ Add --confirm to cancel this order.")
                return
            data = run_cli(["clob", "cancel", args.cancel], json_output=False)
        print(f"\n✅ {data}")
    else:
        print(f"📋 **Open Orders**\n")
        data = run_cli(["clob", "orders"], json_output=False)
        print(data or "No open orders.")


def cmd_positions(args):
    """View positions."""
    if args.address:
        addr = args.address
    else:
        # Try to get address from wallet show
        try:
            data = run_cli(["wallet", "show"], json_output=False)
            # Parse address from output
            for line in data.split('\n'):
                if '0x' in line:
                    addr = line.strip().split()[-1]
                    if addr.startswith('0x'):
                        break
            else:
                print("❌ Could not determine wallet address. Use --address.", file=sys.stderr)
                sys.exit(1)
        except Exception:
            print("❌ Could not determine wallet address. Use --address.", file=sys.stderr)
            sys.exit(1)
    
    print(f"📊 **Positions** ({addr[:10]}...)\n")
    data = run_cli(["data", "positions", addr], json_output=False)
    print(data or "No open positions.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Polymarket prediction markets")
    parser.add_argument("--limit", "-l", type=int, default=5, help="Number of results")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    parser.add_argument("--confirm", action="store_true", help="Confirm trade execution (required for all trades)")

    sub = parser.add_subparsers(dest="command", required=True)

    # Read-only (Gamma API)
    sub.add_parser("trending", help="Trending markets")
    
    sp = sub.add_parser("search", help="Search markets")
    sp.add_argument("query", help="Search query")

    sp = sub.add_parser("event", help="Get event by slug")
    sp.add_argument("slug", help="Event slug")

    sp = sub.add_parser("category", help="Markets by category")
    sp.add_argument("category", help="Category name")

    # Order book / prices (CLI, no wallet)
    sp = sub.add_parser("book", help="Order book for a token ID")
    sp.add_argument("token", help="Token ID")

    sp = sub.add_parser("price-history", help="Price history for a token ID")
    sp.add_argument("token", help="Token ID")
    sp.add_argument("--interval", default="1d", help="Interval: 1m, 1h, 6h, 1d, 1w, max")
    sp.add_argument("--fidelity", type=int, help="Number of data points")

    # Wallet
    sub.add_parser("wallet-setup", help="Interactive wallet setup")
    sub.add_parser("wallet-show", help="Show wallet info")
    sp = sub.add_parser("wallet-balance", help="Show balances")
    sp.add_argument("--token", help="Token ID for conditional balance")

    # Trading
    sp = sub.add_parser("trade", help="Place a trade")
    sp.add_argument("side", choices=["buy", "sell"], help="Buy or sell")
    sp.add_argument("--token", required=True, help="Token ID")
    sp.add_argument("--price", type=float, help="Limit price (0-1)")
    sp.add_argument("--size", type=float, help="Number of shares")
    sp.add_argument("--amount", type=float, help="Dollar amount (market orders)")
    sp.add_argument("--market-order", action="store_true", help="Place market order instead of limit")
    sp.add_argument("--post-only", action="store_true", help="Post-only limit order")

    # Orders
    sp = sub.add_parser("orders", help="List or cancel orders")
    sp.add_argument("--cancel", help="Order ID to cancel, or 'all'")

    # Positions
    sp = sub.add_parser("positions", help="View positions")
    sp.add_argument("--address", help="Wallet address (auto-detected if omitted)")

    args = parser.parse_args()

    commands = {
        "trending": cmd_trending,
        "search": cmd_search,
        "event": cmd_event,
        "category": cmd_category,
        "book": cmd_book,
        "price-history": cmd_price_history,
        "wallet-setup": cmd_wallet_setup,
        "wallet-show": cmd_wallet_show,
        "wallet-balance": cmd_wallet_balance,
        "trade": cmd_trade,
        "orders": cmd_orders,
        "positions": cmd_positions,
    }

    try:
        commands[args.command](args)
    except requests.RequestException as e:
        print(f"❌ API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
