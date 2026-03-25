#!/usr/bin/env python3
"""
API-based Polymarket position monitor + exit rules executor.
Replaces browser-based position monitoring.
All credentials from env/.env.polymarket — never hardcoded.
"""

import sys, os, json, math
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/home/aa/.local/lib/python3.12/site-packages')

from dotenv import load_dotenv
load_dotenv('${QUANT_WORKSPACE}/.env.polymarket')

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams
import requests

# ── Config ──────────────────────────────────────────────
WORKSPACE = Path(os.environ.get('QUANT_WORKSPACE', '${QUANT_WORKSPACE}'))
PEAKS_FILE = WORKSPACE / 'data' / 'profit-peaks.json'
SNAPSHOT_FILE = WORKSPACE / 'data' / 'portfolio-snapshot.json'
RISK_FILE = WORKSPACE / 'data' / 'news-risk-level.txt'

PK = os.environ['POLY_PRIVATE_KEY']
PROXY = os.environ['POLY_PROXY_WALLET']
EOA = os.environ['POLY_EOA_ADDRESS']

# ── Init CLOB Client ────────────────────────────────────
def init_clob():
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=PK,
        chain_id=137,
        signature_type=1,  # POLY_PROXY
        funder=PROXY,
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    return client

# ── Data Sources ────────────────────────────────────────
def get_binance_price(symbol='BTCUSDT'):
    try:
        r = requests.get(f'https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}', timeout=8)
        return float(r.json()['price'])
    except:
        return None

def get_binance_klines(symbol='BTCUSDT', interval='4h', limit=3):
    try:
        r = requests.get(
            f'https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}',
            timeout=8
        )
        data = r.json()
        if not isinstance(data, list):
            return []
        return data
    except:
        return []

def get_risk_level():
    if RISK_FILE.exists():
        return RISK_FILE.read_text().strip()
    return 'NEUTRAL'

def get_positions_from_trades(client):
    """Reconstruct positions from CLOB trade history (more reliable than data-api).
    Returns list of active positions with net size > 0 and current price > 0.
    """
    trades = client.get_trades()
    if isinstance(trades, dict):
        trades = trades.get('data', [])
    
    # Aggregate by token_id
    buckets = {}
    for t in trades:
        token = t.get('asset_id', t.get('token_id'))
        if not token:
            continue
        side = t.get('side', '')
        size = float(t.get('size', 0))
        price = float(t.get('price', 0))
        
        if token not in buckets:
            buckets[token] = {
                'buy_size': 0, 'buy_cost': 0, 'sell_size': 0, 'sell_revenue': 0,
                'title': t.get('title', t.get('market', '?')),
            }
        
        if side == 'BUY':
            buckets[token]['buy_size'] += size
            buckets[token]['buy_cost'] += size * price
        elif side == 'SELL':
            buckets[token]['sell_size'] += size
            buckets[token]['sell_revenue'] += size * price
    
    # Build active positions (net > 0 and has live price)
    active = []
    for token, b in buckets.items():
        net = b['buy_size'] - b['sell_size']
        if net < 0.001:
            continue
        try:
            cur = float(client.get_price(token))
        except:
            cur = 0
        
        if cur > 0:
            avg = b['buy_cost'] / b['buy_size'] if b['buy_size'] > 0 else 0
            pnl = ((cur - avg) / avg * 100) if avg > 0 else 0
            active.append({
                'title': b['title'],
                'outcome': '',  # not available from trades
                'size': net,
                'avgPrice': avg,
                'curPrice': cur,
                'token_id': token,
                'pnl_pct': pnl,
                'redeemable': False,
                'endDate': '',
            })
    
    return active

def get_redeemable_from_trades(client):
    """Find settled positions with remaining balance (price=0, net>0)."""
    trades = client.get_trades()
    if isinstance(trades, dict):
        trades = trades.get('data', [])
    
    buckets = {}
    for t in trades:
        token = t.get('asset_id', t.get('token_id'))
        if not token:
            continue
        side = t.get('side', '')
        size = float(t.get('size', 0))
        price = float(t.get('price', 0))
        
        if token not in buckets:
            buckets[token] = {
                'buy_size': 0, 'sell_size': 0,
                'title': t.get('title', t.get('market', '?')),
            }
        if side == 'BUY':
            buckets[token]['buy_size'] += size
        elif side == 'SELL':
            buckets[token]['sell_size'] += size
    
    redeemable = []
    for token, b in buckets.items():
        net = b['buy_size'] - b['sell_size']
        if net < 0.001:
            continue
        try:
            cur = float(client.get_price(token))
        except:
            cur = 0
        if cur == 0:
            redeemable.append({
                'title': b['title'],
                'size': net,
                'redeemableValue': net,  # settle at $1
            })
    return redeemable

def get_balance_allowance(client):
    try:
        params = BalanceAllowanceParams(asset_type="COLLATERAL", signature_type=1)
        return client.get_balance_allowance(params)
    except Exception as e:
        print(f"  [WARN] balance check: {e}")
        return None

def get_market_info(token_id, client):
    """Get current price and order book for a token."""
    info = {}
    try:
        price = client.get_price(token_id)
        info['price'] = float(price) if price else None
    except:
        info['price'] = None
    try:
        book = client.get_order_book(token_id)
        if book:
            info['best_bid'] = float(book.get('bids', [{}])[0].get('price', 0)) if book.get('bids') else None
            info['best_ask'] = float(book.get('asks', [{}])[0].get('price', 0)) if book.get('asks') else None
    except:
        pass
    return info

def search_gamma_market(question, token_id):
    """Find market metadata from Gamma API."""
    try:
        r = requests.get(
            'https://gamma-api.polymarket.com/markets',
            params={'active': 'true', 'closed': 'false', 'limit': 50},
            timeout=10
        )
        for m in r.json():
            tokens = m.get('clobTokenIds', '')
            if token_id in tokens:
                return m
    except:
        pass
    return None

def get_redeemable_positions(eoa_addr):
    """Get settled positions that can be claimed."""
    redeemable = []
    for addr in [eoa_addr, PROXY]:
        try:
            r = requests.get(
                f'https://data-api.polymarket.com/positions?user={addr}',
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    for p in data:
                        if p.get('redeemable', False) and p.get('size', 0) > 0:
                            redeemable.append(p)
        except:
            pass
    return redeemable

# ── Exit Rules v5.0 ────────────────────────────────────
def check_exit_rules(pnl_pct, now_cents, settlement_hours, peak_pct, risk_level):
    """Check SL/TP rules, return (action, rule, reason)."""
    
    # SL rules (check first)
    if pnl_pct <= -40:
        return ('SELL_ALL', 'SL1', f'亏{pnl_pct:.0f}%>-40%')
    if pnl_pct <= -25:
        return ('REDUCE_40', 'SL2', f'亏{pnl_pct:.0f}%>-25%')
    if pnl_pct <= -15:
        # SL3 needs trend data — signal to check separately
        return ('CHECK_TREND', 'SL3', f'亏{pnl_pct:.0f}%>-15%, 需查趋势')

    # TP rules
    if now_cents >= 99 and settlement_hours > 4:
        return ('SELL_ALL', 'TP1', f'{now_cents}¢>=99¢ 结算>{settlement_hours}h')
    if pnl_pct >= 50:
        return ('SELL_ALL', 'TP2', f'盈利{pnl_pct:.0f}%>=50%')
    if pnl_pct >= 30 and now_cents >= 95:
        return ('SELL_ALL', 'TP3', f'盈利{pnl_pct:.0f}% 95¢+')
    if pnl_pct >= 25:
        return ('SELL_HALF', 'TP4', f'盈利{pnl_pct:.0f}%>=25%')
    if pnl_pct >= 15:
        return ('SELL_60', 'TP4b', f'盈利{pnl_pct:.0f}%>=15%')
    
    # TP5/TP6: peak drawdown (only when peak >= 10%)
    if peak_pct is not None and peak_pct >= 10:
        drawdown_pp = peak_pct - pnl_pct
        drawdown_rel = drawdown_pp / peak_pct if peak_pct > 0 else 0
        if drawdown_rel >= 0.5:
            return ('SELL_ALL', 'TP6', f'峰值+{peak_pct:.0f}%→现+{pnl_pct:.0f}% 回撤{drawdown_pp:.0f}pp 腰斩')
        if drawdown_pp >= 10:
            return ('SELL_HALF', 'TP5', f'峰值+{peak_pct:.0f}%→现+{pnl_pct:.0f}% 回撤{drawdown_pp:.0f}pp')

    return ('HOLD', None, None)

# ── Peak Tracking ──────────────────────────────────────
def load_peaks():
    if PEAKS_FILE.exists():
        return json.loads(PEAKS_FILE.read_text())
    return {"positions": {}, "updated_at": None}

def save_peaks(peaks):
    peaks['updated_at'] = datetime.now(timezone.utc).isoformat()
    PEAKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEAKS_FILE.write_text(json.dumps(peaks, indent=2, ensure_ascii=False))

def update_peak(peaks, key, market, side, avg_c, pnl_pct):
    if key not in peaks['positions']:
        peaks['positions'][key] = {}
    pos = peaks['positions'][key]
    old_peak = pos.get('peak_pnl_pct', 0)
    if pnl_pct > old_peak:
        pos['peak_pnl_pct'] = pnl_pct
        pos['peak_ts'] = datetime.now(timezone.utc).isoformat()
        pos['market'] = market
        pos['side'] = side
        pos['avg_c'] = avg_c
    pos['current_pnl_pct'] = pnl_pct
    pos['current_ts'] = datetime.now(timezone.utc).isoformat()
    return old_peak

def clean_peaks(peaks, active_keys):
    """Remove peaks for positions that are no longer active."""
    to_remove = [k for k in peaks['positions'] if k not in active_keys]
    for k in to_remove:
        del peaks['positions'][k]
    return len(to_remove)

# ── Main Monitor ────────────────────────────────────────
def monitor(dry_run=True):
    now = datetime.now(timezone.utc)
    cst_now = now.strftime('%H:%M')
    
    print(f"📊 仓位监控 @ {cst_now} (CST) | {'DRY RUN' if dry_run else 'LIVE'}")
    print("━" * 40)
    
    # Risk level
    risk = get_risk_level()
    risk_emoji = {'DANGER': '🔴', 'CAUTION': '🟡', 'NEUTRAL': '⚪'}.get(risk, '⚪')
    print(f"{risk_emoji} 风险等级: {risk}")
    
    # Prices
    btc = get_binance_price('BTCUSDT')
    eth = get_binance_price('ETHUSDT')
    if btc is not None and eth is not None:
        print(f"📈 BTC: ${btc:,.0f} | ETH: ${eth:,.0f}")
    elif btc is not None:
        print(f"📈 BTC: ${btc:,.0f} | ETH: 获取失败")
    elif eth is not None:
        print(f"📈 BTC: 获取失败 | ETH: ${eth:,.0f}")
    else:
        print("📈 价格获取失败")
    
    # BTC 4h trend
    klines = get_binance_klines()
    down_count = 0
    for k in klines:
        if not isinstance(k, list) or len(k) < 5:
            continue
        o, c = float(k[1]), float(k[4])
        chg = (c - o) / o * 100
        if chg < 0:
            down_count += 1
        print(f"  {'↓' if chg < 0 else '↑'} O:{o:,.0f} C:{c:,.0f} {chg:+.2f}%")
    print(f"  下跌: {down_count}/3")
    
    # Balance
    client = init_clob()
    ba = get_balance_allowance(client)
    cash = 0
    if ba:
        raw_bal = ba.get('balance', '0')
        cash = float(raw_bal) / 1e6  # USDC 6 decimals
        print(f"💰 CLOB余额: ${cash:.2f}")
    
    # Positions (from CLOB trades — more reliable than data-api)
    print("\n📦 扫描持仓...")
    positions = get_positions_from_trades(client)
    
    if not positions:
        print("  无活跃持仓")
        redeemable = get_redeemable_from_trades(client)
        if redeemable:
            total_redeem = sum(float(p.get('redeemableValue', 0)) for p in redeemable)
            print(f"  ⚠️ {len(redeemable)}个可Claim仓位 (~${total_redeem:.2f})")
        save_snapshot(now, cash, [], redeemable)
        print(f"\n⚡ 操作: 无 (空仓)")
        return
    
    # Load peaks
    peaks = load_peaks()
    active_keys = set()
    
    report_lines = []
    actions_taken = []
    
    for pos in positions:
        title = pos.get('title', pos.get('market', '?'))
        outcome = pos.get('outcome', 'YES')
        size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        cur_price = float(pos.get('curPrice', 0))
        token_id = pos.get('token_id', '')
        pnl_pct = pos.get('pnl_pct', 0)
        
        # Position key
        key = f"{title[:30]}_{outcome}"
        active_keys.add(key)
        
        # Update peak
        old_peak = update_peak(peaks, key, title, outcome, avg_price, pnl_pct)
        peak_pct = peaks['positions'][key].get('peak_pnl_pct', 0)
        
        # Settlement info
        end_date = pos.get('endDate', '')
        settlement_hours = 999
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                diff = (end_dt - now).total_seconds() / 3600
                settlement_hours = max(0, diff)
            except:
                pass
        
        # Check exit rules
        action, rule, reason = check_exit_rules(pnl_pct, cur_price * 100, settlement_hours, peak_pct, risk)
        
        # CAUTION override: sell all profitable crypto positions
        if risk == 'CAUTION' and pnl_pct > 0:
            action = 'SELL_ALL'
            rule = 'CAUTION'
            reason = f'CAUTION+盈利{pnl_pct:.0f}%→落袋'
        
        # DANGER override
        if risk == 'DANGER':
            if pnl_pct <= -15:
                action = 'SELL_ALL'
                rule = 'DANGER_SL'
                reason = f'DANGER+亏{pnl_pct:.0f}%→止损'
            elif pnl_pct > 15:
                action = 'SELL_ALL'
                rule = 'DANGER_TP'
                reason = f'DANGER+盈利{pnl_pct:.0f}%→落袋'
        
        # Build report line
        pnl_emoji = '🟢' if pnl_pct > 0 else '🔴' if pnl_pct < 0 else '⚪'
        peak_str = f'峰值:+{peak_pct:.0f}%' if peak_pct > 0 else ''
        settle_str = f' 结算:{settlement_hours:.0f}h' if settlement_hours < 999 else ''
        line = f"  {pnl_emoji} {title[:35]} | {outcome} {avg_price:.2f}→{cur_price:.2f} ({pnl_pct:+.1f}%) | {size:.1f}sh{settle_str}"
        if peak_str:
            line += f' | {peak_str}'
        
        if action != 'HOLD':
            line += f' | ⚡{rule}:{reason}'
            actions_taken.append((key, action, rule, reason, title, outcome, size, token_id))
        
        report_lines.append(line)
    
    # Clean stale peaks
    cleaned = clean_peaks(peaks, active_keys)
    if cleaned:
        print(f"  清理{cleaned}个过期峰值")
    
    save_peaks(peaks)
    
    # Print report
    for line in report_lines:
        print(line)
    
    # Execute actions
    if actions_taken and not dry_run:
        print("\n🚀 执行操作...")
        for key, action, rule, reason, title, outcome, size, token_id in actions_taken:
            if not token_id:
                print(f"  ⚠️ {key}: 无token_id, 跳过")
                continue
            
            sell_size = size
            if action in ('SELL_HALF', 'SELL_60', 'REDUCE_40'):
                sell_size = size * (0.5 if 'HALF' in action else 0.6 if '60' in action else 0.6)
                sell_size = math.floor(sell_size * 100) / 100  # round down to 2 decimals
            
            try:
                price = client.get_price(token_id)
                if not price:
                    print(f"  ⚠️ {key}: 无法获取价格, 跳过")
                    continue
                
                order = client.create_order(OrderArgs(
                    token_id=token_id,
                    price=float(price),
                    size=sell_size,
                    side="SELL",
                    fee_rate_bps=1000,
                ))
                result = client.post_order(order)
                print(f"  ✅ {key}: {action} {sell_size:.1f}sh → {result.get('status', '?')}")
            except Exception as e:
                print(f"  ❌ {key}: {e}")
    
    # Redeemable (from CLOB trades)
    redeemable = get_redeemable_from_trades(client)
    if redeemable:
        total_redeem = sum(float(p.get('redeemableValue', 0)) for p in redeemable)
        print(f"\n  ⚠️ {len(redeemable)}个可Claim仓位 (~${total_redeem:.2f})")
        print(f"  (Claim需browser操作)")
    
    # Save snapshot
    pos_data = []
    for pos in positions:
        if not pos.get('redeemable', False):
            pos_data.append({
                'market': pos.get('title', '')[:50],
                'side': pos.get('outcome', ''),
                'avg_c': float(pos.get('avgPrice', 0)),
                'now_c': float(pos.get('curPrice', 0)),
                'pnl_pct': round((float(pos.get('curPrice',0)) - float(pos.get('avgPrice',0))) / max(float(pos.get('avgPrice',0)), 0.001) * 100, 1),
                'shares': float(pos.get('size', 0)),
            })
    save_snapshot(now, cash, pos_data, redeemable)
    
    # Summary
    print(f"\n⚡ 操作: {', '.join(f'{a[2]}({a[0][:20]})' for a in actions_taken) if actions_taken else '无'}")
    print(f"📊 规则: exit-rules v5.0 | API模式")

def save_snapshot(now, cash, positions, redeemable):
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    total_pos = sum(p['now_c'] * p['shares'] for p in positions)
    snapshot = {
        'ts': now.isoformat(),
        'portfolio_usd': round(cash + total_pos, 2),
        'cash_usd': round(cash, 2),
        'positions': positions,
        'redeemable_count': len(redeemable) if redeemable else 0,
    }
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    dry = '--live' not in sys.argv
    monitor(dry_run=dry)
