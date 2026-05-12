#!/usr/bin/env python3
"""
Trend Data Fetcher v1.0
从 Binance 获取 1h K线原始数据，不做分析。
输出: data/trend_raw.json — 每币种最近48根1h K线 (OHLCV)

用法: python3 trend_data.py [--coins BTC,ETH,SOL,...]
"""
import json, sys, os, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 不走代理
session = requests.Session()
session.trust_env = False

DEFAULT_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"]
BINANCE_API = "https://api.binance.com/api/v3/klines"

def fetch_klines(symbol: str, interval: str = "1h", limit: int = 48) -> list:
    """获取K线原始数据"""
    try:
        r = session.get(BINANCE_API, params={
            "symbol": symbol, "interval": interval, "limit": limit
        }, timeout=15)
        if r.status_code == 200:
            return [{
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
            } for k in r.json()]
    except Exception as e:
        print(f"  ⚠ {symbol}: {e}", file=sys.stderr)
    return []

def main():
    coins_str = os.environ.get("COINS", "")
    if "--coins" in sys.argv:
        idx = sys.argv.index("--coins")
        coins_str = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
    
    pairs = coins_str.split(",") if coins_str else DEFAULT_COINS
    
    now = datetime.now(timezone.utc)
    cst = now + timedelta(hours=8)
    print(f"Trend Data Fetcher v1.0 — {cst.strftime('%Y-%m-%d %H:%M')} CST")
    
    result = {}
    for pair in pairs:
        coin = pair.replace("USDT", "")
        klines = fetch_klines(pair)
        if klines:
            result[coin] = {
                "symbol": pair,
                "interval": "1h",
                "count": len(klines),
                "klines": klines,
                "last_close": klines[-1]["close"],
                "last_time": klines[-1]["close_time"],
                "fetched_at": now.isoformat(),
            }
            print(f"  {coin}: {len(klines)} candles, last=${klines[-1]['close']:,.4f}")
        else:
            print(f"  {coin}: no data")
    
    out_path = DATA_DIR / "trend_raw.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Saved → {out_path}")
    
    # 兼容旧 trend_results.json (简单趋势标签)
    trend_compat = {}
    for coin, d in result.items():
        closes = [k["close"] for k in d["klines"]]
        if len(closes) < 24:
            continue
        last_24 = closes[-24:]
        pct = (last_24[-1] - last_24[0]) / last_24[0] * 100
        up_c = sum(1 for i in range(1, len(last_24)) if last_24[i] > last_24[i-1])
        if pct > 1.0 and up_c >= 16:
            trend = "STRONG_UP"
        elif pct > 0.3:
            trend = "UP"
        elif pct < -1.0 and (24 - up_c) >= 16:
            trend = "STRONG_DOWN"
        elif pct < -0.3:
            trend = "DOWN"
        else:
            trend = "NEUTRAL"
        trend_compat[coin] = {
            "trend": trend,
            "momentum": round(pct, 2),
            "price": closes[-1],
            "yes_size": {"STRONG_UP":100,"UP":100,"NEUTRAL":75,"DOWN":50,"STRONG_DOWN":25}.get(trend, 75),
            "no_size": {"STRONG_UP":25,"UP":50,"NEUTRAL":75,"DOWN":100,"STRONG_DOWN":100}.get(trend, 75),
        }
    
    compat_path = DATA_DIR / "trend_results.json"
    with open(compat_path, "w") as f:
        json.dump(trend_compat, f, indent=2)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
