"""
Polymarket CLOB Trading Wrapper
Wraps py-clob-client for simplified trading operations.
Private key loaded from `pass` — never hardcoded.
"""

import os
import subprocess
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL


def _get_private_key() -> str:
    result = subprocess.run(
        ["pass", "show", "api/polymarket-wallet"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _make_client() -> ClobClient:
    pk = _get_private_key()
    client = ClobClient(host="https://clob.polymarket.com", key=pk, chain_id=137)
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


_client = None

def client() -> ClobClient:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def get_markets(limit: int = 100, cursor: str = "") -> dict:
    """Fetch paginated market list from CLOB."""
    params = {"limit": limit}
    if cursor:
        params["next_cursor"] = cursor
    return client().get_markets(**params) if cursor else client().get_markets()


def get_market(token_id: str) -> dict:
    """Get order book for a specific token."""
    return client().get_order_book(token_id)


def get_market_info(condition_id: str) -> dict:
    """Get market info by condition_id from Gamma API."""
    import requests
    r = requests.get(
        f"https://gamma-api.polymarket.com/markets?condition_id={condition_id}",
        timeout=15
    )
    r.raise_for_status()
    data = r.json()
    return data[0] if data else {}


def get_balance() -> dict:
    """Get USDC balance info (via API key endpoints)."""
    # py-clob-client doesn't expose a direct balance call;
    # balance is typically checked on-chain or via positions value
    return {"note": "Check on-chain balance or use get_positions() for position value"}


def get_positions() -> list:
    """Get current open orders as proxy for positions."""
    return client().get_orders()


def get_trades() -> list:
    """Get trade history."""
    return client().get_trades()


def place_order(token_id: str, side: str, size: float, price: float) -> dict:
    """
    Build, sign, and submit an order.
    side: "BUY" or "SELL"
    size: number of shares
    price: price per share (0.01 - 0.99)
    """
    order_side = BUY if side.upper() == "BUY" else SELL
    signed = client().create_order(OrderArgs(
        token_id=token_id,
        price=price,
        size=size,
        side=order_side,
    ))
    return client().post_order(signed)


def cancel_order(order_id: str) -> dict:
    """Cancel an open order by ID."""
    return client().cancel(order_id)


def cancel_all() -> dict:
    """Cancel all open orders."""
    return client().cancel_all()


# --- Gamma API helpers (no auth needed) ---

def search_markets(query: str = "", limit: int = 10, active: bool = True) -> list:
    """Search markets via Gamma API."""
    import requests
    params = {
        "active": str(active).lower(),
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
        "limit": limit,
    }
    if query:
        params["tag"] = query
    r = requests.get("https://gamma-api.polymarket.com/markets", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    print("=== Polymarket CLOB Trader ===")
    print("Testing connection...")
    c = client()
    print("✅ Connected, API creds derived")

    mkts = get_markets()
    count = len(mkts.get("data", [])) if isinstance(mkts, dict) else 0
    print(f"✅ Markets: {count} loaded")

    orders = get_positions()
    print(f"✅ Open orders: {len(orders)}")

    trades = get_trades()
    print(f"✅ Trades: {len(trades)}")

    top = search_markets(limit=3)
    for m in top[:3]:
        q = m.get("question", "?")[:60]
        v = m.get("volume24hr", "?")
        print(f"  📊 {q} | 24h vol: {v}")

    print("\nAll systems go. Ready to trade.")
