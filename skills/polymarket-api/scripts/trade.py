#!/usr/bin/env python3
# Proxy fix: only remove SOCKS proxy (httpx crash), keep HTTP proxy
import os as _os
for _k in ['ALL_PROXY', 'all_proxy']:
    _os.environ.pop(_k, None)
# Keep HTTP_PROXY / HTTPS_PROXY for Cloudflare bypass

"""
Polymarket 精准交易脚本 v2.0 (CLOB V2 + pUSD)
2026-04-28: CLOB V2上线, 移除feeRateBps/nonce/taker, 新增timestamp/metadata

用法:
  python3 trade.py buy  <slug> <side> <usd_amount> [price] [--threshold N]
  python3 trade.py sell <slug> <side> <usd_amount> [price] [--threshold N]
  python3 trade.py price <slug> [side] [--threshold N]
  python3 trade.py info  <slug> [--threshold N]
  python3 trade.py balance
  python3 trade.py cancel <order_id>
  python3 trade.py orders
"""

import os, sys, json, re, requests, time, logging

log = logging.getLogger("trade")
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

# === Retry wrapper ===
def retry_get(url, *, max_retries=3, backoff=2, timeout=10, **kwargs):
    kwargs.setdefault('timeout', timeout)
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, **kwargs)
            return r
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                ConnectionResetError, OSError) as e:
            if attempt < max_retries:
                wait = backoff * attempt
                log.warning(f"retry_get attempt {attempt}/{max_retries} failed: {type(e).__name__}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait = backoff * attempt
                time.sleep(wait)
            else:
                raise

# === Config ===
DOTENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env.poly')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(DOTENV_PATH)

PK = os.environ['POLY_PRIVATE_KEY']
PROXY = os.environ['POLY_PROXY_WALLET']

GAMMA_API = "https://gamma-api.polymarket.com"

def get_client():
    """V2 CLOB client"""
    from py_clob_client_v2.client import ClobClient
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=PK,
        chain_id=137,
        signature_type=1,
        funder=PROXY,
    )
    creds = client.create_or_derive_api_key()
    client.set_api_creds(creds)
    return client

def resolve_market(slug, threshold=None):
    slugs_to_try = [slug]
    if slug.startswith("ethereum-"):
        slugs_to_try.append(slug.replace("ethereum-", "eth-"))
    if slug.startswith("bitcoin-"):
        slugs_to_try.append(slug.replace("bitcoin-", "btc-"))

    for s in slugs_to_try:
        r = retry_get(f"{GAMMA_API}/events/slug/{s}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            markets = data.get('markets', [])
            if not markets:
                continue
            if threshold and len(markets) > 1:
                def normalize_number(s):
                    s = s.replace(',', '')
                    if '.' in s:
                        s = s.rstrip('0').rstrip('.')
                    return s
                for m in markets:
                    q = m.get('question', '')
                    nums = re.findall(r'[\$,]?([\d,]+\.?[\d]*)', q)
                    for n in nums:
                        if normalize_number(n) == normalize_number(str(threshold)):
                            return m
            return markets[0]

    r = retry_get(f"{GAMMA_API}/events", params={"slug": slug, "active": "true"}, timeout=8)
    if r.status_code == 200 and r.json():
        markets = r.json()[0].get('markets', [])
        if markets:
            return markets[0]

    r = retry_get(f"{GAMMA_API}/markets", params={"slug": slug}, timeout=8)
    if r.status_code == 200 and r.json():
        return r.json()[0]

    raise ValueError(f"Market not found: {slug}")

def get_tokens(market):
    tids = market.get('clobTokenIds', [])
    if isinstance(tids, str):
        tids = json.loads(tids) if tids else []
    yes_tid = tids[0] if len(tids) > 0 else None
    no_tid = tids[1] if len(tids) > 1 else None
    return yes_tid, no_tid

def get_updown_tokens(slug):
    r = retry_get(f"{GAMMA_API}/events/slug/{slug}", timeout=8)
    if r.status_code == 200:
        data = r.json()
        markets = data.get('markets', [])
        if markets:
            tids = markets[0].get('clobTokenIds', [])
            if isinstance(tids, str):
                tids = json.loads(tids) if tids else []
            return tids[0] if tids else None, tids[1] if len(tids) > 1 else None
    return None, None

def resolve_token_id(market, side, slug=None):
    side = side.upper()
    if side in ("UP", "DOWN") and slug:
        up_tid, down_tid = get_updown_tokens(slug)
        if side == "UP" and up_tid:
            return up_tid, "UP"
        elif side == "DOWN" and down_tid:
            return down_tid, "DOWN"
    yes_tid, no_tid = get_tokens(market)
    if side == "YES" and yes_tid:
        return yes_tid, "YES"
    elif side == "NO" and no_tid:
        return no_tid, "NO"
    elif side == "UP":
        return yes_tid, "YES"
    elif side == "DOWN":
        return no_tid, "NO"
    raise ValueError(f"Cannot resolve token for side={side}")

def cmd_balance():
    client = get_client()
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    bal = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    cash = float(bal['balance']) / 1e6
    print(f"💰 Cash: ${cash:.2f}")

def cmd_orders():
    client = get_client()
    orders = client.get_orders()
    if not orders:
        print("📭 无挂单")
        return
    print(f"📋 挂单: {len(orders)}")
    for o in orders:
        if isinstance(o, dict):
            print(f"  {o.get('id','')[:20]}... | {o.get('side','')} | ${o.get('price','')} | {o.get('size_matched','')}/{o.get('original_size','')}")

def cmd_cancel(order_id):
    client = get_client()
    try:
        result = client.cancel(order_id)
        print(f"✅ 撤单成功: {order_id[:20]}...")
    except Exception as e:
        print(f"❌ 撤单失败: {e}")

def cmd_info(slug, threshold=None):
    market = resolve_market(slug, threshold)
    q = market.get('question', '?')[:80]
    end = market.get('endDate', '?')
    yes_tid, no_tid = get_tokens(market)
    vol = market.get('volume', 0)
    liq = market.get('liquidity', 0)
    condition_id = market.get('conditionId', '?')

    client = get_client()
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    bal = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    usdc = float(bal['balance']) / 1e6

    positions = []
    for tid, label in [(yes_tid, "YES"), (no_tid, "NO")]:
        if not tid:
            continue
        try:
            ba = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=tid))
            shares = float(ba['balance']) / 1e6
            if shares >= 0.01:
                mid_r = retry_get("https://clob.polymarket.com/midpoint", params={"token_id": tid}, timeout=5)
                mid = float(mid_r.json().get('mid', 0)) if mid_r.status_code == 200 else 0
                value = shares * mid
                positions.append(f"  {label}: {shares:.2f} shares × ${mid:.2f} = ${value:.2f}")
        except:
            pass

    print(f"📋 {q}")
    print(f"  End: {end}")
    print(f"  Vol: ${float(vol):,.0f} | Liq: ${float(liq):,.0f}")
    print(f"  Condition: {condition_id[:30]}...")
    print(f"  YES token: {yes_tid[:30]}..." if yes_tid else "  YES token: N/A")
    print(f"  NO  token: {no_tid[:30]}..." if no_tid else "  NO  token: N/A")
    print(f"  Cash: ${usdc:.2f}")
    if positions:
        print("  Positions:")
        for p in positions:
            print(p)

def cmd_price(slug, side="YES", threshold=None):
    market = resolve_market(slug, threshold)
    tid, resolved_side = resolve_token_id(market, side, slug)

    client = get_client()
    try:
        mid_r = client.get_midpoint(tid)
        mid = float(mid_r.get('mid', 0))
    except:
        mid = 0
    try:
        bid_r = client.get_price(tid, "buy")
        ask_r = client.get_price(tid, "sell")
        bid = float(bid_r.get('price', 0))
        ask = float(ask_r.get('price', 0))
    except:
        bid = ask = 0

    print(f"📊 {market.get('question','?')[:60]} [{resolved_side}]")
    print(f"  BID: {bid:.3f} | ASK: {ask:.3f} | MID: {mid:.3f}")
    print(f"  Spread: {(ask-bid)*100:.1f}¢")

def cmd_buy(slug, side, usd_amount, price=None, threshold=None):
    """V2: 无feeRateBps, 无nonce"""
    client = get_client()
    from py_clob_client_v2.clob_types import OrderArgs, OrderType, BalanceAllowanceParams, AssetType

    bal = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    cash = float(bal['balance']) / 1e6
    if usd_amount > cash:
        print(f"❌ 余额不足: 需要${usd_amount:.2f}, 可用${cash:.2f}")
        return

    market = resolve_market(slug, threshold)
    tid, resolved_side = resolve_token_id(market, side, slug)

    if price is None:
        try:
            mid_r = client.get_midpoint(tid)
            price = float(mid_r.get('mid', 0))
        except:
            print("❌ 无法获取MID价格，请手动指定price")
            return
        price = min(price + 0.01, 0.99)

    size = int(usd_amount / price)
    if size < 5:
        print(f"❌ 最小下单5 shares, 当前仅能买{size} shares")
        return

    actual_cost = size * price

    print(f"🎯 {market.get('question','?')[:60]}")
    print(f"  Side: {resolved_side} | Token: {tid[:30]}...")
    print(f"  Price: ${price:.2f} | Size: {size} shares | Cost: ${actual_cost:.2f}")

    if not sys.stdout.isatty():
        print("  (auto-confirmed, non-interactive mode)")
    else:
        confirm = input(f"  确认下单? [y/N] ").strip().lower()
        if confirm != 'y':
            print("  已取消")
            return

    try:
        order_args = OrderArgs(
            token_id=tid,
            price=price,
            size=size,
            side="BUY",
        )
        signed = client.create_order(order_args)
        result = client.post_order(signed, OrderType.FOK)

        if result.get('success'):
            status = result.get('status', '')
            order_id = result.get('orderID', '')
            if status == 'matched':
                taking = result.get('takingAmount', '0')
                making = result.get('makingAmount', '0')
                print(f"  ✅ FILLED: making={making} taking={taking}")
                if result.get('transactionsHashes'):
                    print(f"  Tx: {result['transactionsHashes'][0][:30]}...")
            elif status == 'live':
                print(f"  📤 LIVE: {size} shares @ ${price}")
                print(f"  Order ID: {order_id}")
            else:
                print(f"  📤 Posted: {status}")
        else:
            print(f"  ❌ Error: {result.get('errorMsg', result)}")
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {e}")

def cmd_sell(slug, side, usd_amount, price=None, threshold=None):
    """V2 sell"""
    client = get_client()
    from py_clob_client_v2.clob_types import OrderArgs, OrderType, BalanceAllowanceParams, AssetType

    market = resolve_market(slug, threshold)
    tid, resolved_side = resolve_token_id(market, side, slug)

    try:
        ba = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=tid))
        shares = float(ba['balance']) / 1e6
    except Exception as e:
        print(f"❌ 查持仓失败: {e}")
        return

    if shares < 1:
        print(f"❌ 无持仓 (shares: {shares:.4f})")
        return

    if price is None:
        try:
            bid_r = client.get_price(tid, "buy")
            price = float(bid_r.get('price', 0))
        except:
            print("❌ 无法获取BID价格")
            return
        price = max(price - 0.01, 0.01)

    mid_r = retry_get("https://clob.polymarket.com/midpoint", params={"token_id": tid}, timeout=5)
    mid = float(mid_r.json().get('mid', price)) if mid_r.status_code == 200 else price
    size = min(int(usd_amount / mid), int(shares))

    if size < 1:
        print(f"❌ 卖出量不足: 需要≥1 share, 当前{size}")
        return

    print(f"💰 {market.get('question','?')[:60]}")
    print(f"  Side: SELL {resolved_side} | Holding: {shares:.2f} shares")
    print(f"  Price: ${price:.2f} | Size: {size} shares | Revenue: ~${size*price:.2f}")

    try:
        order_args = OrderArgs(
            token_id=tid,
            price=price,
            size=size,
            side="SELL",
        )
        signed = client.create_order(order_args)
        result = client.post_order(signed, OrderType.FOK)

        if result.get('success'):
            status = result.get('status', '')
            if status == 'matched':
                print(f"  ✅ SOLD: {size} shares @ ${price}")
            elif status == 'live':
                print(f"  📤 SELL LIVE: {size} shares @ ${price}")
            else:
                print(f"  📤 Posted: {status}")
        else:
            print(f"  ❌ Error: {result.get('errorMsg', result)}")
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {e}")

def parse_args(args):
    threshold = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == '--threshold':
            if i + 1 < len(args):
                threshold = float(args[i+1].replace(',', ''))
                i += 2
                continue
        positional.append(args[i])
        i += 1
    return positional, threshold

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()
    rest = sys.argv[2:]
    positional, threshold = parse_args(rest)

    if cmd == 'info' and len(positional) >= 1:
        cmd_info(positional[0], threshold)
    elif cmd == 'balance':
        cmd_balance()
    elif cmd == 'orders':
        cmd_orders()
    elif cmd == 'cancel' and len(positional) >= 1:
        cmd_cancel(positional[0])
    elif cmd == 'price' and len(positional) >= 1:
        side = positional[1] if len(positional) > 1 else "YES"
        cmd_price(positional[0], side, threshold)
    elif cmd == 'buy' and len(positional) >= 3:
        slug = positional[0]
        side = positional[1]
        usd = float(positional[2])
        price = float(positional[3]) if len(positional) > 3 else None
        cmd_buy(slug, side, usd, price, threshold)
    elif cmd == 'sell' and len(positional) >= 2:
        slug = positional[0]
        side = positional[1] if len(positional) > 1 else "YES"
        usd = float(positional[2]) if len(positional) > 2 else 999
        price = float(positional[3]) if len(positional) > 3 else None
        cmd_sell(slug, side, usd, price, threshold)
    else:
        print(f"Unknown command or missing args: {cmd}")
        print(__doc__)
        sys.exit(1)

if __name__ == '__main__':
    main()
