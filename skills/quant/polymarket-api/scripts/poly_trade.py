#!/usr/bin/env python3
"""Polymarket API Trading — Buy/Sell/Check via CLOB API (gasless).

Usage:
  python3 poly_trade.py buy  <token_id> <side> <price> <size>
  python3 poly_trade.py sell <token_id> <price> <size>
  python3 poly_trade.py price <token_id>
  python3 poly_trade.py balance
  python3 poly_trade.py orders
  python3 poly_trade.py cancel <order_id>

Examples:
  python3 poly_trade.py buy 88494541...8897 YES 0.95 10    # Buy 10 YES shares at 95¢
  python3 poly_trade.py sell 88494541...8897 0.97 10       # Sell 10 shares at 97¢
  python3 poly_trade.py price 88494541...8897              # Get bid/ask/mid
  python3 poly_trade.py balance                             # Check USDC balance
"""

import os, sys, json

# Load credentials
DOTENV_PATH = '/home/aa/.openclaw/workspace-quant/.env.poly'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(DOTENV_PATH)

PK = os.environ['POLY_PRIVATE_KEY']
PROXY = os.environ['POLY_PROXY_WALLET']

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams

def get_client():
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=PK,
        chain_id=137,
        signature_type=1,  # POLY_PROXY
        funder=PROXY,
    )
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    return client

def cmd_price(client, token_id):
    mid = client.get_midpoint(token_id)
    bid = client.get_price(token_id, "buy")
    ask = client.get_price(token_id, "sell")
    print(f"BID: {bid['price']} | ASK: {ask['price']} | MID: {mid['mid']}")

def cmd_balance(client):
    ba = client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
    bal = float(ba['balance']) / 1e6
    print(f"USDC Balance: ${bal:.2f}")

def cmd_orders(client):
    orders = client.get_orders()
    if not orders:
        print("No open orders")
        return
    print(f"Open orders: {len(orders)}")
    for o in orders:
        if isinstance(o, dict):
            print(f"  {o.get('id','')[:20]}... | {o.get('side','')} | {o.get('price','')} | matched: {o.get('size_matched','')}/{o.get('original_size','')}")

def cmd_buy(client, token_id, side, price, size):
    """Buy YES or NO shares. side='YES' means buy the YES token, 'NO' means buy the NO token."""
    # Resolve token_id for YES/NO
    if side.upper() == 'NO':
        # Get NO token from Gamma API
        import requests
        resp = requests.get(f"https://gamma-api.polymarket.com/markets", params={"clob_token_id": token_id})
        if resp.status_code == 200 and resp.json():
            market = resp.json()[0]
            tokens = json.loads(market.get('clobTokenIds', '[]'))
            if len(tokens) >= 2:
                token_id = tokens[1]  # NO is index 1
                print(f"Using NO token: {token_id[:20]}...")
            else:
                print("ERROR: Could not find NO token ID")
                sys.exit(1)
    
    order_args = OrderArgs(
        token_id=token_id,
        price=float(price),
        size=float(size),
        side="BUY",
        fee_rate_bps=1000,
    )
    signed = client.create_order(order_args)
    result = client.post_order(signed)
    
    if result.get('success'):
        status = result.get('status', 'unknown')
        if status == 'matched':
            print(f"✅ FILLED: {size} shares @ ${price} = ${float(size)*float(price):.2f}")
        elif status == 'live':
            print(f"📤 LIVE: {size} shares @ ${price} — waiting for match")
            print(f"   Order ID: {result.get('orderID','')}")
        else:
            print(f"Result: {result}")
    else:
        print(f"❌ Error: {result.get('errorMsg', result)}")

def cmd_sell(client, token_id, price, size):
    order_args = OrderArgs(
        token_id=token_id,
        price=float(price),
        size=float(size),
        side="SELL",
        fee_rate_bps=1000,
    )
    signed = client.create_order(order_args)
    result = client.post_order(signed)
    
    if result.get('success'):
        status = result.get('status', 'unknown')
        if status == 'matched':
            print(f"✅ SOLD: {size} shares @ ${price} = ${float(size)*float(price):.2f}")
        elif status == 'live':
            print(f"📤 SELL LIVE: {size} shares @ ${price} — waiting for match")
        else:
            print(f"Result: {result}")
    else:
        print(f"❌ Error: {result.get('errorMsg', result)}")

def cmd_cancel(client, order_id):
    result = client.cancel(order_id)
    print(f"Cancel: {result}")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    client = get_client()
    
    if cmd == 'price' and len(sys.argv) >= 3:
        cmd_price(client, sys.argv[2])
    elif cmd == 'balance':
        cmd_balance(client)
    elif cmd == 'orders':
        cmd_orders(client)
    elif cmd == 'buy' and len(sys.argv) >= 6:
        cmd_buy(client, sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == 'sell' and len(sys.argv) >= 5:
        cmd_sell(client, sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'cancel' and len(sys.argv) >= 3:
        cmd_cancel(client, sys.argv[2])
    else:
        print(f"Unknown command or missing args: {cmd}")
        print(__doc__)
        sys.exit(1)

if __name__ == '__main__':
    main()
