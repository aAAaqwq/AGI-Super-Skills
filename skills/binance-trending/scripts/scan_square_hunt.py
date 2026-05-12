#!/usr/bin/env python3
"""
Binance Square 热度猎杀整合脚本 v2.0
整合多数据源 → 统一交易信号

用法:
  python3 scan_square_hunt.py           # 完整模式（需先保存browser snapshot）
  python3 scan_square_hunt.py --fast   # 快速模式（无需browser，纯API）
  python3 scan_square_hunt.py --all    # 全部模式（包含browser快照解析）
"""
import os, sys, json, re, argparse, urllib.request
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# 清除代理
for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

EXCLUDED_COINS = {
    "BTC","ETH","SOL","BNB","XRP","ADA","DOGE","XLM",
    "USDT","BUSD","USDC","DAI","DOT","AVAX","LINK",
    "MATIC","SHIB","LTC","FTT","UNI","XMR","XAUT",
}

BULLISH_KW = ["surge","rally","breakout","bullish","all-time high","soar",
               "gain","rise","adoption","buy","upgrade","etf","institutional",
               "launch","positive","record","climb","high","profit","inflow"]
BEARISH_KW = ["crash","plunge","bearish","sell","hack","scam","ban","regulation",
              "risk","crackdown","collapse","fear","drop","warn","investigation",
              "security","breach","exploit","tumble","slide","slump","death",
              "loss","theft","seize","liquidat","exploit","exploit"]

RSS_FEEDS = [
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
]

# ============ 数据源1: Fear & Greed ============
def fetch_fear_greed():
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=1", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            item = data.get("data", [{}])[0]
            return {"value": int(item.get("value", 0)), "label": item.get("value_classification", "?")}
    except Exception as e:
        return {"value": None, "label": "UNKNOWN", "error": str(e)}

# ============ 数据源2: Binance Ticker ============
def fetch_binance_ticker(coin="BTCUSDT"):
    try:
        url = f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={coin}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
            return {
                "lastPrice": float(d.get("lastPrice", 0)),
                "changePct": float(d.get("priceChangePercent", 0)),
                "highPrice": float(d.get("highPrice", 0)),
                "lowPrice": float(d.get("lowPrice", 0)),
                "quoteVolume": float(d.get("quoteVolume", 0)),
            }
    except:
        return {}

# ============ 数据源3: 新闻情绪 ============
def fetch_news_sentiment():
    import xml.etree.ElementTree as ET
    all_news = []

    def get_text(el):
        if el is None: return ""
        txt = el.text if isinstance(el.text, str) else ""
        if not txt.strip():
            txt = "".join(el.itertext())
        return re.sub(r"\s+", " ", txt).strip()

    for name, url in RSS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                root = ET.fromstring(r.read())
                for item in root.iter("item"):
                    title = get_text(item.find("title"))
                    if not title or len(title) < 5:
                        title = get_text(item.find("description"))
                    if title and len(title) > 5:
                        all_news.append(title)
        except Exception as e:
            print(f"  ⚠️ {name} RSS failed: {e}", flush=True)

    b = be = ne = 0
    for title in all_news:
        t = title.lower()
        bv = sum(1 for kw in BULLISH_KW if kw in t)
        bev = sum(1 for kw in BEARISH_KW if kw in t)
        if bev > bv: be += 1
        elif bv > bev: b += 1
        else: ne += 1
    total = b + be + ne
    signal = "NEUTRAL"
    if b > be * 1.5: signal = "BULLISH"
    elif be > b * 1.5: signal = "BEARISH"
    return {
        "signal": signal, "bullish": b, "bearish": be, "neutral": ne,
        "total": total,
        "bullish_pct": round(b/total*100, 1) if total else 0,
        "bearish_pct": round(be/total*100, 1) if total else 0,
    }

# ============ 数据源4: Browser快照解析 ============
def parse_browser_snapshot(text: str) -> dict:
    result = {"hot_search_coins": [], "post_sentiment": {"bullish": 0, "bearish": 0, "neutral": 0}, "large_pnl_posts": []}

    # 热搜币
    for coin, is_hot, price_str, change_str in re.findall(
        r'link\s+"([A-Z]{2,15})\s+[A-Z]+\s*(热度上升)?\s*([\d.,]+)?\s*([+-]?\d+\.\d+)?%"', text):
        if coin in EXCLUDED_COINS: continue
        try:
            price = float(price_str.replace(",","")) if price_str and price_str not in ("--","") else None
            change = float(change_str) if change_str and change_str not in ("--","") else None
        except: price = change = None
        result["hot_search_coins"].append({"coin": coin, "price": price, "change_pct": change, "is_hot": bool(is_hot)})

    # 帖子情绪
    b = be = ne = 0
    for pt in re.findall(r'^\s*- text:\s*(.+?)\s*$', text, re.MULTILINE):
        bv = sum(1 for kw in BULLISH_KW if kw in pt)
        bev = sum(1 for kw in BEARISH_KW if kw in pt)
        if bev > bv: be += 1
        elif bv > bev: b += 1
        else: ne += 1
        pnl_m = re.search(r'未实现盈亏\s*([+-])?([\d,]+\.?\d*)', pt)
        if pnl_m:
            try:
                val = float(pnl_m.group(2).replace(",",""))
                val = -val if pnl_m.group(1) == "-" else val
                if abs(val) > 1000:
                    result["large_pnl_posts"].append({"pnl": val, "text": pt[:60]})
            except: pass
    result["post_sentiment"] = {"bullish": b, "bearish": be, "neutral": ne}
    return result

# ============ 主分析引擎 ============
def analyze(fg, btc, eth, news, square):
    fg_val = fg.get("value")
    btc_chg = btc.get("changePct", 0)
    eth_chg = eth.get("changePct", 0)

    if fg_val is not None:
        if fg_val >= 70: mood = "极度贪婪"
        elif fg_val >= 55: mood = "贪婪"
        elif fg_val >= 45: mood = "中性"
        elif fg_val >= 25: mood = "恐惧"
        else: mood = "极度恐惧"
    else: mood = "UNKNOWN"

    signals = []
    # 信号1: BTC下跌+新闻偏空 → 检查做空
    if btc_chg < -1.5 and news["signal"] == "BEARISH":
        signals.append({"type": "BEARISH", "edge": "MEDIUM", "reason": f"BTC {btc_chg:+.1f}%+新闻偏空", "action": "检查BTC below YES"})
    # 信号2: BTC急跌+极度恐惧 → 抄底观察
    if btc_chg < -4 and fg_val and fg_val < 30:
        signals.append({"type": "BUY_BOTTOM", "edge": "HIGH", "reason": f"BTC急跌{btc_chg:+.1f}%+极度恐惧", "action": "观察BTC above YES机会"})
    # 信号3: BTC强势+极度贪婪 → 警惕
    if btc_chg > 2 and fg_val and fg_val > 75:
        signals.append({"type": "CAUTION", "edge": "MEDIUM", "reason": f"BTC强势{btc_chg:+.1f}%+极度贪婪", "action": "减少多头仓位"})
    # 信号4: ETH急跌+恐惧 → 检查ETH below
    if eth_chg < -4:
        signals.append({"type": "ETH_DROP", "edge": "MEDIUM", "reason": f"ETH急跌{eth_chg:+.1f}%", "action": "检查ETH below YES"})

    hot = []
    if square:
        for c in square.get("hot_search_coins", []):
            if c.get("is_hot") and c.get("change_pct"):
                hot.append(f"{c['coin']}{c['change_pct']:+.0f}%🔥" if c["change_pct"] > 0 else f"{c['coin']}{c['change_pct']:+.0f}%📉")

    whales = []
    if square:
        for p in square.get("large_pnl_posts", [])[:3]:
            whales.append(f"${p['pnl']:+,.0f} {'做空' if p['pnl'] > 0 else '做多亏损'}")

    return {
        "scan_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "fear_greed": fg,
        "market_mood": mood,
        "btc": {"price": btc.get("lastPrice"), "change_pct": btc_chg},
        "eth": {"price": eth.get("lastPrice"), "change_pct": eth_chg},
        "news": news,
        "signals": signals,
        "hot_opportunities": hot[:5],
        "whale_actions": whales,
    }

# ============ 主程序 ============
def main():
    args = argparse.ArgumentParser(description="热度猎杀整合").parse_args()
    print("🔍 数据采集中...", flush=True)

    with ThreadPoolExecutor(max_workers=5) as ex:
        fg_f = ex.submit(fetch_fear_greed)
        news_f = ex.submit(fetch_news_sentiment)
        btc_f = ex.submit(fetch_binance_ticker, "BTCUSDT")
        eth_f = ex.submit(fetch_binance_ticker, "ETHUSDT")

    fg = fg_f.result()
    news = news_f.result()
    btc = btc_f.result()
    eth = eth_f.result()

    square = None
    snap_path = "/tmp/binance_square_snapshot.txt"
    if os.path.exists(snap_path) and os.path.getsize(snap_path) > 500:
        try:
            with open(snap_path, encoding="utf-8") as f:
                text = f.read()
            square = parse_browser_snapshot(text)
            print(f"✅ Browser快照: {len(square['hot_search_coins'])}个热搜币", flush=True)
        except Exception as e:
            print(f"⚠️ Snapshot解析失败: {e}", flush=True)

    result = analyze(fg, btc, eth, news, square)
    fg_v = result["fear_greed"].get("value")
    emoji = "😱" if fg_v and fg_v < 45 else "😈" if fg_v and fg_v > 55 else "😐"

    print(f"\n{'='*60}", flush=True)
    print(f"📊 热度猎杀整合 | {result['scan_time']}", flush=True)
    print(f"{emoji} 恐惧贪婪: {fg_v} ({result['fear_greed'].get('label','?')}) | {result['market_mood']}", flush=True)
    print(f"₿ BTC: ${result['btc']['price']:,.0f} {result['btc']['change_pct']:+.2f}%", flush=True)
    print(f"Ξ ETH: ${result['eth']['price']:,.0f} {result['eth']['change_pct']:+.2f}%", flush=True)
    print(f"📰 新闻: {result['news']['signal']} ({result['news']['bullish']}多/{result['news']['bearish']}空)", flush=True)

    if result["hot_opportunities"]:
        print(f"\n🔥 热搜机会: {' | '.join(result['hot_opportunities'])}", flush=True)
    if result["whale_actions"]:
        print(f"\n🐋 大户动态: {' | '.join(result['whale_actions'])}", flush=True)
    if result["signals"]:
        print(f"\n📋 信号:", flush=True)
        for s in result["signals"]:
            flag = "🟢" if "BUY" in s["type"] else "🔴" if "BEARISH" in s["type"] else "⚠️"
            print(f"  {flag} [{s['edge']}] {s['reason']}", flush=True)
            print(f"     → {s['action']}", flush=True)
    else:
        print(f"\n📋 信号: 无特殊信号，等待机会", flush=True)
    print(f"{'='*60}", flush=True)

    with open("/tmp/hunt_signals.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON: /tmp/hunt_signals.json", flush=True)


if __name__ == "__main__":
    main()
