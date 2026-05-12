#!/usr/bin/env python3
"""
CLOB Trade Executor v8.0
复用 skills/polymarket-api/scripts/trade.py 的真实API连接。
支持: info/buy/sell/balance/price

用法:
  python3 trade.py info BTC --type ABOVE --threshold 76000 --date 2026-04-30
  python3 trade.py buy BTC --type ABOVE --threshold 76000 --side NO 10 --date 2026-04-30
  python3 trade.py balance
"""
import json, sys, os, re, argparse
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent

# 复用 polymarket-api 的真实 trade 模块
POLY_TRADE = SKILL_DIR.parent / "polymarket-api" / "scripts" / "trade.py"

COIN_NAMES = {
    'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana',
    'xrp': 'xrp', 'bnb': 'bnb', 'doge': 'dogecoin', 'hype': 'hype',
}
MONTHS = ['january','february','march','april','may','june',
          'july','august','september','october','november','december']

def coin_to_slug(coin: str, mtype: str, date_str: str = "") -> str:
    """生成Gamma slug"""
    from datetime import datetime
    dt = datetime.fromisoformat(date_str) if date_str else datetime.now()
    month = MONTHS[dt.month - 1]
    day = dt.day
    coin_name = COIN_NAMES.get(coin.lower(), coin.lower())
    
    if mtype.upper() in ('ABOVE', 'BELOW'):
        return f"{coin_name}-{mtype.lower()}-on-{month}-{day}"
    else:
        return f"{coin.lower()}-up-or-down-on-{month}-{day}-{dt.year}"

def run_poly_trade(args: list):
    """调用真实 polymarket-api trade.py"""
    import subprocess
    env = os.environ.copy()
    # 清除 proxy 避免 httpx SOCKS crash
    for k in ['ALL_PROXY', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
        env.pop(k, None)
    env["PYTHONPATH"] = str(POLY_TRADE.parent)
    
    result = subprocess.run(
        [sys.executable, str(POLY_TRADE)] + args,
        capture_output=True, text=True, timeout=30,
        cwd=str(POLY_TRADE.parent),
        env=env,
    )
    print(result.stdout, end="")
    if result.stderr and "urllib3" not in result.stderr and "warning" not in result.stderr.lower():
        # 只打印真正的错误
        for line in result.stderr.split("\n"):
            if line.strip() and "urllib3" not in line and "DEBUG" not in line:
                print(f"  stderr: {line}", file=sys.stderr)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(description='Crypto-Hunt Trade Executor v8.0 (real API)')
    subparsers = parser.add_subparsers(dest='command')
    
    def add_market_args(p):
        p.add_argument('coin', help='BTC/ETH/SOL/XRP/BNB/DOGE/HYPE')
        p.add_argument('--type', dest='market_type', default='ABOVE', 
                      choices=['ABOVE', 'BELOW', 'UPDOWN'])
        p.add_argument('--threshold', default='', help='Price threshold')
        p.add_argument('--date', default='', help='YYYY-MM-DD')
        p.add_argument('--side', default='YES', choices=['YES', 'NO'])
    
    # info
    p_info = subparsers.add_parser('info')
    add_market_args(p_info)
    
    # price
    p_price = subparsers.add_parser('price')
    add_market_args(p_price)
    
    # buy
    p_buy = subparsers.add_parser('buy')
    add_market_args(p_buy)
    p_buy.add_argument('amount', type=float, help='USD amount')
    p_buy.add_argument('--price', type=float, default=None)
    
    # sell
    p_sell = subparsers.add_parser('sell')
    add_market_args(p_sell)
    p_sell.add_argument('amount', type=float, help='USD amount')
    p_sell.add_argument('--price', type=float, default=None)
    
    # balance
    subparsers.add_parser('balance')
    
    # execute (从 decisions.json 自动执行)
    p_exec = subparsers.add_parser('execute')
    p_exec.add_argument('--max-amount', type=float, default=20)
    p_exec.add_argument('--dry-run', action='store_true')
    p_exec.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    p_exec.add_argument('--market-id', help='Direct CLOB token market ID')
    
    args = parser.parse_args()
    
    if args.command == 'balance':
        return run_poly_trade(['balance'])
    
    if args.command == 'execute':
        return cmd_execute(args)
    
    if args.command in ('info', 'price', 'buy', 'sell'):
        slug = coin_to_slug(args.coin, args.market_type, args.date)
        threshold = args.threshold.replace(',', '') if args.threshold else None
        
        if args.command == 'info':
            poly_args = ['info', slug]
            if threshold:
                poly_args += ['--threshold', threshold]
        elif args.command == 'price':
            poly_args = ['price', slug, args.side]
            if threshold:
                poly_args += ['--threshold', threshold]
        elif args.command == 'buy':
            price_str = f"{args.price:.2f}" if args.price else None
            poly_args = ['buy', slug, args.side, str(args.amount)]
            if price_str:
                poly_args.append(price_str)
            if threshold:
                poly_args += ['--threshold', threshold]
        elif args.command == 'sell':
            price_str = f"{args.price:.2f}" if args.price else None
            poly_args = ['sell', slug, args.side, str(args.amount)]
            if price_str:
                poly_args.append(price_str)
            if threshold:
                poly_args += ['--threshold', threshold]
        
        return run_poly_trade(poly_args)
    
    parser.print_help()
    return 1

def cmd_execute(args):
    """从 decisions.json 自动执行交易 (v6 format)"""
    decisions_path = SKILL_DIR / "data" / "decisions.json"
    if not decisions_path.exists():
        print("❌ No decisions.json. Run decision_engine.py first.")
        return 1
    
    with open(decisions_path) as f:
        decisions = json.load(f)
    
    # v6 format: decision == "TRADE", has direction/position/coin/market_type/threshold
    tradeable = [d for d in decisions if d.get("decision") == "TRADE"]
    if not tradeable:
        print("No tradeable decisions.")
        return 0
    
    # 按confidence排序
    tradeable.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    
    for t in tradeable:
        amount = min(t.get("position", 2.0), args.max_amount)
        amount = max(0.5, amount)
        direction = t.get("direction", "YES")
        coin = t.get("coin", "BTC")
        mtype = t.get("market_type", t.get("type", "ABOVE"))
        threshold = t.get("threshold", "")
        market_slug = t.get("market", "")
        layer = t.get("layer", "?")
        
        print(f"🎯 {coin} {mtype}@{threshold:,.0f} → {direction} ${amount:.1f} [{layer}]")
        print(f"  conf={t.get('confidence',0):.2f} RR={t.get('risk_reward',0):.2f} | {t.get('reason','')[:60]}")
        
        if args.dry_run:
            print(f"  [DRY RUN] Would execute")
            continue
        
        # 确认
        if not args.yes:
            try:
                confirm = input(f"  Execute? [y/N] ").strip().lower()
                if confirm != 'y':
                    print("  Skipped.")
                    continue
            except (EOFError, KeyboardInterrupt):
                print("  Cancelled.")
                return 0
        
        slug = market_slug or coin_to_slug(coin, mtype, "")
        thresh_str = str(int(float(threshold))) if threshold else None
        
        try:
            poly_args = ['buy', slug, direction, f"{amount:.1f}"]
            if thresh_str:
                poly_args += ['--threshold', thresh_str]
            print(f"  Executing: {' '.join(poly_args)}")
            rc = run_poly_trade(poly_args)
            if rc != 0:
                print(f"  ❌ Failed (rc={rc})")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
