#!/usr/bin/env python3
"""
cli/kline_fetch.py — 查询合约 K 线数据

用法:
  python cli/kline_fetch.py --symbol NEARUSDT --interval 15m --limit 100
  python cli/kline_fetch.py --scan                          # 扫 20 主流合约简报
  python cli/kline_fetch.py --symbol BTCUSDT --json         # JSON 输出

TODO:
  - [ ] 对接 Binance fapi/v1/klines
  - [ ] 多币种并发请求（ThreadPool）
  - [ ] 缓存已有数据（避免重复请求）
  - [ ] 数据导出 CSV
"""
import argparse
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="BB套利 - K线数据查询")
    parser.add_argument("--symbol", default="NEARUSDT")
    parser.add_argument("--interval", default="15m",
                       choices=["1m","5m","15m","30m","1h","4h","1d"])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--export-csv")
    args = parser.parse_args()

    # ── 临时占位：实际实现接 Binance API ──
    def fetch_klines(symbol, interval, limit):
        import requests
        url = "https://fapi.binance.com/fapi/v1/klines"
        resp = requests.get(url, params={
            "symbol": symbol, "interval": interval, "limit": limit
        }, timeout=15)
        resp.raise_for_status()
        return [{
            "time": k[0], "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])
        } for k in resp.json()]

    if args.scan:
        # TODO: 从 config.yaml 读 SCAN_SYMBOLS
        symbols = ["NEARUSDT","AVAXUSDT","INJUSDT","DOGEUSDT","SUIUSDT"]
        print(f"📡 扫描 {len(symbols)} 个合约 (15m, {args.limit}根)...\n")
        for sym in symbols:
            try:
                bars = fetch_klines(sym, "15m", args.limit)
                close = bars[-1]["close"]
                print(f"  {sym:12s}  ${close:<12.6f}  {len(bars)} 根 K 线")
            except Exception as e:
                print(f"  {sym:12s}  ❌ {e}")
    else:
        bars = fetch_klines(args.symbol, args.interval, args.limit)
        if args.json:
            print(json.dumps(bars[-20:], indent=2))
        elif args.export_csv:
            with open(args.export_csv, "w") as f:
                f.write("time,open,high,low,close,volume\n")
                for b in bars:
                    ts = datetime.utcfromtimestamp(b["time"]/1000).isoformat()
                    f.write(f"{ts},{b['open']},{b['high']},{b['low']},{b['close']},{b['volume']}\n")
            print(f"✅ 导出 {len(bars)} 根 K 线 → {args.export_csv}")
        else:
            print(f"{'时间':20s} {'开':>10s} {'高':>10s} {'低':>10s} {'收':>10s}")
            for b in bars[-20:]:
                ts = datetime.utcfromtimestamp(b["time"]/1000).strftime("%m-%d %H:%M")
                print(f"{ts:20s} {b['open']:10.6f} {b['high']:10.6f} {b['low']:10.6f} {b['close']:10.6f}")
            print(f"\n  {len(bars)}/{args.limit} 根 {args.interval} K 线 | {args.symbol}")


if __name__ == "__main__":
    main()
