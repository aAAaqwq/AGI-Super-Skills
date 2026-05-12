#!/usr/bin/env python3
"""
Binance 热度抓取 v1.0
抓取 Binance 官方页面热门数据 → 热点币排行
"""
import os
import sys
import json
import re
import urllib.request
import urllib.error
from urllib.parse import urlencode

# 清除代理
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(k, None)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.binance.com/",
}

BASE = "https://data-api.binance.vision/api/v3"


def fetch_json(url, params=None):
    if params:
        url += "?" + urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def get_all_tickers():
    """获取所有 USDT 交易对的 24h 数据"""
    return fetch_json(f"{BASE}/ticker/24hr")


def filter_usdt_pairs(tickers):
    """只保留 USDT 交易对，排除小币"""
    result = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        # 过滤小币：成交量 > $1M
        try:
            vol = float(t.get("quoteVolume", 0))
            if vol < 1_000_000:
                continue
            result.append(t)
        except:
            continue
    return result


def get_top_movers(tickers, n=20):
    """按涨幅排序，返回 Top 涨/跌"""
    try:
        sorted_tickers = sorted(tickers, key=lambda x: float(x.get("priceChangePercent", 0) or 0), reverse=True)
        gainers = sorted_tickers[:n]
        losers = sorted_tickers[-n:][::-1]
        return gainers, losers
    except Exception as e:
        return [], []


def get_top_volume(tickers, n=20):
    """按成交额排序"""
    try:
        return sorted(tickers, key=lambda x: float(x.get("quoteVolume", 0) or 0), reverse=True)[:n]
    except:
        return []


def extract_coin(ticker):
    """从 symbol 提取币种名"""
    sym = ticker.get("symbol", "")
    return sym.replace("USDT", "").replace("BUSD", "").replace("USD", "")


def format_ticker(t, rank=None):
    sym = t.get("symbol", "")
    try:
        price = float(t.get("lastPrice", 0))
        change = float(t.get("priceChangePercent", 0))
        vol = float(t.get("quoteVolume", 0))
        vol_str = f"${vol/1e6:.1f}M" if vol < 1e9 else f"${vol/1e9:.2f}B"
        high = float(t.get("highPrice", 0))
        low = float(t.get("lowPrice", 0))
        coin = extract_coin(t)
        rank_str = f"#{rank} " if rank else ""
        return {
            "rank": rank,
            "symbol": sym,
            "coin": coin,
            "price": round(price, 6 if price < 1 else 2),
            "change_pct": round(change, 2),
            "quote_volume_usd": round(vol, 0),
            "vol_str": vol_str,
            "high_24h": round(high, 6 if high < 1 else 2),
            "low_24h": round(low, 6 if low < 1 else 2),
            "is_gain": change > 0,
        }
    except:
        return {}


def main():
    print("🔍 抓取 Binance 热度数据...", flush=True)

    tickers = get_all_tickers()
    if isinstance(tickers, dict) and "error" in tickers:
        print(f"❌ API 失败: {tickers['error']}")
        return

    pairs = filter_usdt_pairs(tickers)
    print(f"📊 筛选后 USDT 交易对: {len(pairs)} 个", flush=True)

    gainers, losers = get_top_movers(pairs, n=20)
    top_vol = get_top_volume(pairs, n=20)

    # 按交易额计算体积倍数
    btc_ticker = next((t for t in pairs if t.get("symbol") == "BTCUSDT"), None)
    btc_vol = float(btc_ticker.get("quoteVolume", 1)) if btc_ticker else 1

    result = {
        "scan_time": "",
        "total_pairs": len(pairs),
        "gainers": [],
        "losers": [],
        "top_volume": [],
        "hot_coins": [],  # 热点币（涨幅>3% 且成交额>BTC的10%）
    }

    for i, t in enumerate(gainers):
        formatted = format_ticker(t, rank=i + 1)
        result["gainers"].append(formatted)

    for i, t in enumerate(losers):
        formatted = format_ticker(t, rank=i + 1)
        result["losers"].append(formatted)

    for i, t in enumerate(top_vol):
        formatted = format_ticker(t, rank=i + 1)
        result["top_volume"].append(formatted)

    # 热点币过滤：涨幅>3% 或 成交量>BTC的20%
    vol_threshold = btc_vol * 0.20
    for t in pairs:
        try:
            change = float(t.get("priceChangePercent", 0) or 0)
            vol = float(t.get("quoteVolume", 0) or 0)
            if change > 3.0 or (change > 1.0 and vol > vol_threshold):
                formatted = format_ticker(t)
                if formatted["coin"] not in [c["coin"] for c in result["hot_coins"]]:
                    result["hot_coins"].append(formatted)
        except:
            continue

    # 按涨幅排序热点币
    result["hot_coins"].sort(key=lambda x: x["change_pct"], reverse=True)

    # 打印摘要
    print(f"\n{'='*50}", flush=True)
    print(f"🔥 热点币 (涨幅>3%): {len([c for c in result['hot_coins'] if c['change_pct'] > 3])} 个", flush=True)
    for c in result["hot_coins"][:10]:
        flag = "📈" if c["is_gain"] else "📉"
        print(f"  {flag} {c['coin']:8s} {c['change_pct']:+.2f}% | {c['vol_str']:>10s} | ${c['price']}", flush=True)

    print(f"\n📈 涨幅榜 Top10:", flush=True)
    for c in result["gainers"][:10]:
        print(f"  #{c['rank']:2d} {c['coin']:8s} {c['change_pct']:+.2f}% | {c['vol_str']:>10s}", flush=True)

    print(f"\n📉 跌幅榜 Top10:", flush=True)
    for c in result["losers"][:10]:
        print(f"  #{c['rank']:2d} {c['coin']:8s} {c['change_pct']:+.2f}% | {c['vol_str']:>10s}", flush=True)

    print(f"\n💧 成交额 Top10:", flush=True)
    for c in result["top_volume"][:10]:
        print(f"  #{c['rank']:2d} {c['coin']:8s} {c['vol_str']:>10s} | {c['change_pct']:+.2f}%", flush=True)
    print(f"{'='*50}", flush=True)

    # 输出 JSON 供后续处理
    output_file = "/tmp/binance_hot.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✅ JSON 已保存: {output_file}", flush=True)

    # 输出可读摘要供 skill 读取
    hot_summary = f"热点币 {len(result['hot_coins'])} 个 | 涨幅榜 #{result['gainers'][0]['coin'] if result['gainers'] else 'N/A'} +{result['gainers'][0]['change_pct'] if result['gainers'] else 0}% | 成交额 #1 {result['top_volume'][0]['coin'] if result['top_volume'] else 'N/A'}"
    print(f"\n📋 Summary: {hot_summary}", flush=True)


if __name__ == "__main__":
    main()
