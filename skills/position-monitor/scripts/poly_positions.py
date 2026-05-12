#!/usr/bin/env python3
"""
Polymarket活跃持仓查询 — 精准版 v3
数据源: data-api.polymarket.com/positions (proxy wallet)
单次请求返回所有字段（title/slug/endDate/curPrice/outcome），无需Gamma。
秒级响应，精准匹配活跃持仓。

Usage:
    python3 poly_positions.py              # 标准报告
    python3 poly_positions.py --json       # JSON输出
    python3 poly_positions.py --check-tpsl # 含止盈止损检查
"""
# Proxy fix: remove ALL_PROXY (socks://) to avoid httpx crash (2026-04-15)
import os as _os
for _k in ['ALL_PROXY', 'all_proxy']:
    _os.environ.pop(_k, None)

import os, sys, json, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent  # scripts/xxx.py → skills/xxx/
ENV_FILE = WORKSPACE / '.env.poly'
PEAKS_FILE = WORKSPACE / 'data' / 'profit-peaks.json'
DATA_API = 'https://data-api.polymarket.com'
TZ_SH = timezone(timedelta(hours=8))

from dotenv import load_dotenv
load_dotenv(ENV_FILE)
PROXY_WALLET = os.environ.get('POLY_PROXY_WALLET', '')
PK = os.environ.get('POLY_PRIVATE_KEY', '')

# ── TP/SL Rules v7.0 ──────────────────────────────────
TP_RULES = [
    {'name': 'TP1', 'min_pct': 99, 'action': 'SELL_ALL', 'cond': 'price>=0.99 AND settle>4h'},
    {'name': 'TP2', 'min_pct': 30, 'action': 'SELL_ALL'},
    {'name': 'TP3', 'min_pct': 25, 'action': 'SELL_80'},
    {'name': 'TP4', 'min_pct': 15, 'action': 'SELL_60'},
]
SL_RULES = [
    {'name': 'SL1', 'max_pct': -15, 'action': 'SELL_ALL'},
    {'name': 'SL2', 'max_pct': -10, 'action': 'SELL_40'},
    {'name': 'SL3', 'max_pct': -5,  'action': 'SELL_20'},
]

# ── Core ───────────────────────────────────────────────
def fetch_positions(historical=False):
    """Fetch positions from data-api. Returns list of dicts with all fields."""
    params = {'user': PROXY_WALLET}
    if historical:
        params['includeHistorical'] = 'true'
    r = requests.get(f'{DATA_API}/positions', params=params,
                     headers={'Accept': 'application/json'}, timeout=10)
    if r.status_code != 200:
        print(f"API Error: {r.status_code} - {r.text}", file=sys.stderr)
        return []
    return r.json()

def get_cash():
    """Get USDC cash balance from CLOB (USDC has 6 decimals)."""
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    try:
        c = ClobClient('https://clob.polymarket.com', key=PK, chain_id=137,
                       signature_type=1, funder=PROXY_WALLET)
        c.set_api_creds(c.create_or_derive_api_creds())
        bal = c.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return float(bal.get('balance', 0)) / 1e6
    except:
        return 0.0

def get_peaks():
    """Load profit peaks for drawdown checks."""
    if PEAKS_FILE.exists():
        try:
            return json.loads(PEAKS_FILE.read_text())
        except:
            pass
    return {}

def check_tpsl(positions):
    """Check TP/SL rules. Returns list of alert strings."""
    alerts = []
    peaks = get_peaks()
    now = datetime.now(TZ_SH)

    for p in positions:
        title = p.get('title', '?')[:45]
        pnl = p.get('percentPnl', 0)
        cur = p.get('curPrice', 0)
        end = p.get('endDate', '')
        cid = p.get('conditionId', '')

        # Time to settle
        hours_to_settle = None
        if end:
            try:
                settle_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                hours_to_settle = (settle_dt - now).total_seconds() / 3600
            except:
                pass

        # TP rules
        if cur >= 0.99 and hours_to_settle is not None and hours_to_settle > 4:
            alerts.append(f'🟢 TP1 {title} {cur:.2f}¢ 结算{hours_to_settle:.0f}h后 → 全卖')
        if pnl >= 30:
            alerts.append(f'🟢 TP2 {title} +{pnl:.1f}% → 全卖')
        elif pnl >= 25:
            alerts.append(f'🟢 TP3 {title} +{pnl:.1f}% → 卖80%')
        elif pnl >= 15:
            alerts.append(f'🟢 TP4 {title} +{pnl:.1f}% → 卖60%')

        # Peak drawdown
        peak_pnl = peaks.get(cid, {}).get('peak_pnl', 0)
        if peak_pnl > 10:
            drawdown = peak_pnl - pnl
            if drawdown >= 10:
                alerts.append(f'🟡 TP5 {title} 峰+{peak_pnl:.1f}%→+{pnl:.1f}% 回撤{drawdown:.1f}pp → 卖半')
            if pnl < peak_pnl / 2:
                alerts.append(f'🟡 TP6 {title} 利润腰斩 → 全卖')

        # SL rules (v7.0: 5%减20%, 10%减40%, 15%全止)
        if pnl <= -15:
            alerts.append(f'🔴 SL1 {title} {pnl:.1f}% → 全止')
        elif pnl <= -10:
            alerts.append(f'🟠 SL2 {title} {pnl:.1f}% → 减仓40%')
        elif pnl <= -5:
            alerts.append(f'🟡 SL3 {title} {pnl:.1f}% → 减仓20%')

    return alerts

def format_report(active, redeemable, alerts, cash=0.0):
    """Format Telegram-friendly report."""
    now = datetime.now(TZ_SH)
    total_hold = sum(p.get('currentValue', 0) for p in active)
    total_pnl = sum(p.get('cashPnl', 0) for p in active)

    lines = [
        f'📊 Quant 仓位报告 [{now.strftime("%m-%d %H:%M")}]',
        '━' * 28,
        f'💰 总资产: ${cash + total_hold:.2f} | 现金: ${cash:.2f} | 持仓: ${total_hold:.2f} | P&L: ${total_pnl:+.2f}',
        '',
    ]

    if active:
        lines.append(f'活跃仓位 ({len(active)}):')
        for p in active:
            title = p.get('title', '?')[:50]
            outcome = p.get('outcome', '?')
            size = p.get('size', 0)
            avg = p.get('avgPrice', 0)
            cur = p.get('curPrice', 0)
            pnl = p.get('percentPnl', 0)
            val = p.get('currentValue', 0)
            end = p.get('endDate', '')[:10]
            redeem = ' 🔄Claim' if p.get('redeemable') else ''

            lines.append(f'\n• {title}{redeem}')
            lines.append(f'  {outcome} {size:.1f}sh | 入{avg:.2f}¢→现{cur:.2f}¢ ({pnl:+.1f}%) | ${val:.2f} | 结算{end}')
    else:
        lines.append('📭 无活跃持仓')

    if redeemable:
        redeem_val = sum(p.get('currentValue', 0) for p in redeemable)
        lines.append(f'\n🔄 可Claim: {len(redeemable)}笔 ~${redeem_val:.2f}')

    if alerts:
        lines.append(f'\n⚠️ 止盈止损:')
        for a in alerts:
            lines.append(f'  {a}')

    return '\n'.join(lines)

# ── Main ───────────────────────────────────────────────
def main():
    args = set(sys.argv[1:])
    do_json = '--json' in args
    do_tpsl = '--check-tpsl' in args

    # Active positions
    active = fetch_positions(historical=False)
    active_cids = {p.get('conditionId', '') for p in active}

    # Redeemable = historical positions not in active
    all_historical = fetch_positions(historical=True)
    redeemable = [p for p in all_historical if p.get('conditionId', '') not in active_cids]

    # Cash
    cash = get_cash()

    # TP/SL
    alerts = check_tpsl(active) if do_tpsl else []

    if do_json:
        output = {
            'timestamp': datetime.now(TZ_SH).isoformat(),
            'cash': cash,
            'total_holdings': sum(p.get('currentValue', 0) for p in active),
            'total_pnl': sum(p.get('cashPnl', 0) for p in active),
            'positions': active,
            'redeemable': redeemable,
            'tpsl_alerts': alerts,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(format_report(active, redeemable, alerts, cash))

if __name__ == '__main__':
    main()
