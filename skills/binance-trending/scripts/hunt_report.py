#!/usr/bin/env python3
"""
热度猎杀 v4.0 — 简化版
从 Square 主页面直接解析热门帖子（主帖内容 + 互动数据）
不再进入帖子内部爬评论（评论动态加载，复杂度高）
"""
import os, sys, json, re, argparse, urllib.request
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
EXCLUDED = {"BTC","ETH","SOL","BNB","XRP","ADA","DOGE","XLM","USDT","BUSD",
            "USDC","DAI","DOT","AVAX","LINK","MATIC","SHIB","LTC","FTT","UNI"}
RSS_FEEDS = [
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
]

# ============ API ============
def fetch_fear_greed():
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=1", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
            item = d.get("data", [{}])[0]
            return {"value": int(item.get("value", 0)), "label": item.get("value_classification", "?")}
    except:
        return {"value": None, "label": "UNKNOWN"}

def fetch_binance_ticker(coin="BTCUSDT"):
    try:
        url = f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={coin}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
            return {
                "price": float(d.get("lastPrice", 0)),
                "change": float(d.get("priceChangePercent", 0)),
                "high": float(d.get("highPrice", 0)),
                "low": float(d.get("lowPrice", 0)),
                "volume": float(d.get("quoteVolume", 0)),
            }
    except:
        return {}

def fetch_news_sentiment():
    import xml.etree.ElementTree as ET
    all_news = []
    def get_text(el):
        if el is None: return ""
        txt = el.text if isinstance(el.text, str) else ""
        if not txt.strip(): txt = "".join(el.itertext())
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
        except: pass
    b = be = ne = 0
    for title in all_news:
        t = title.lower()
        bv = sum(1 for kw in ["surge","rally","breakout","bullish","buy","etf","institutional","gain"] if kw in t)
        bev = sum(1 for kw in ["crash","plunge","bearish","sell","hack","ban","regulation","drop","risk"] if kw in t)
        if bev > bv: be += 1
        elif bv > bev: b += 1
        else: ne += 1
    signal = "NEUTRAL"
    if b > be * 1.5: signal = "BULLISH"
    elif be > b * 1.5: signal = "BEARISH"
    return {"signal": signal, "bullish": b, "bearish": be, "neutral": ne,
            "headlines": all_news[:5]}

# ============ 解析 Square 主页快照 ============
def parse_square_snapshot(text):
    """
    解析 browser snapshot 文本，提取热门帖子列表
    每个帖子包含: 作者、情绪、内容、币种、盈亏、互动数据
    """
    posts = []
    # 按行解析
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- text:"):
            m = re.search(r'^-\s*text:\s*(.+)$', line)
            if m: lines.append(m.group(1))
        elif line.startswith("- heading:"):
            m = re.search(r'^-\s*heading:\s*(.+?)\s*\[', line)
            if m: lines.append("TITLE:" + m.group(1))
        elif line.startswith("- link:"):
            # 提取链接文本
            m = re.search(r'link:\s*\"([^\"]+)\"', line)
            if m: lines.append("LINK:" + m.group(1))
        elif line.startswith("- img:"):
            pass  # skip images
        else:
            lines.append(line)

    # 找帖子段落：时间 + 情绪 模式开始
    i = 0
    while i < len(lines):
        # 检查是否是帖子开头（时间+情绪标签）
        time_m = re.match(r'^(\d+)\s*(分钟|小时|天)$', lines[i])
        if time_m:
            post = {
                "time": time_m.group(1) + time_m.group(2),
                "sentiment": None,
                "text": "",
                "coins": [],
                "pnl": None,
                "views": 0,
                "comments": 0,
                "forwards": 0,
            }
            # 情感检测：下一行如果是看涨/看跌
            if i + 1 < len(lines) and lines[i+1].strip() in ("看涨", "看跌"):
                post["sentiment"] = lines[i+1].strip()
            # 收集帖子内容（直到下一个时间或空行过多）
            j = i + 1
            content_lines = []
            while j < len(lines):
                l = lines[j]
                # 遇到下一个帖子，停止
                if re.match(r'^\d+\s*(分钟|小时|天)', l):
                    break
                # 忽略互动数字（单独的数字行）
                if re.match(r'^\d+$', l):
                    j += 1
                    continue
                # 忽略常见非内容行
                if l in ("看涨", "看跌", "已投票！请明天再来。",
                         "什么是加密货币恐惧和贪婪指数？", "自动翻译"):
                    j += 1
                    continue
                # 提取币种
                for coin in re.findall(r'\$([A-Z]{2,10})', l):
                    if coin not in EXCLUDED:
                        post["coins"].append(coin)
                # 提取盈亏
                pnl_m = re.search(r'[+-]\d[\d,]+\.\d+', l)
                if pnl_m and not post["pnl"]:
                    try:
                        val = float(pnl_m.group().replace(",",""))
                        post["pnl"] = val
                    except: pass
                # 提取互动数字（按顺序: views, comments, forwards）
                # 出现在内容行之后的一系列数字
                if content_lines and len(content_lines) > 0:
                    nums = re.findall(r'\d+', l)
                    if len(nums) == 1 and int(nums[0]) > 10 and int(nums[0]) < 1000000:
                        if post["views"] == 0:
                            post["views"] = int(nums[0])
                        elif post["comments"] == 0:
                            post["comments"] = int(nums[0])
                        elif post["forwards"] == 0:
                            post["forwards"] = int(nums[0])
                # 内容行累积
                if l and not re.match(r'^[\d,.]+$', l) and len(l) > 3:
                    content_lines.append(l)
                j += 1
            post["text"] = " ".join(content_lines[:5])[:150]
            if post["text"] or post["coins"] or post["pnl"] is not None:
                posts.append(post)
            i = j
        else:
            i += 1

    return posts

# ============ 主报告 ============
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="纯API，无browser")
    args = parser.parse_args()
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

    print(f"\n{'='*60}", flush=True)
    print(f"📊 热度猎杀 v4.0 | {now}", flush=True)
    print(f"{'='*60}", flush=True)

    # API 数据
    with ThreadPoolExecutor(max_workers=6) as ex:
        fg_f = ex.submit(fetch_fear_greed)
        news_f = ex.submit(fetch_news_sentiment)
        btc_f = ex.submit(fetch_binance_ticker, "BTCUSDT")
        eth_f = ex.submit(fetch_binance_ticker, "ETHUSDT")
    fg = fg_f.result(); news = news_f.result()
    btc = btc_f.result(); eth = eth_f.result()

    fg_v = fg.get("value")
    btc_chg = btc.get("change", 0)
    eth_chg = eth.get("change", 0)
    bdir = "↑" if btc_chg > 0.5 else "↓" if btc_chg < -0.5 else "→"
    edir = "↑" if eth_chg > 0.5 else "↓" if eth_chg < -0.5 else "→"

    mood = "中性"
    if fg_v:
        if fg_v < 25: mood = "极度恐惧"
        elif fg_v < 45: mood = "恐惧"
        elif fg_v > 75: mood = "极度贪婪"
        elif fg_v > 55: mood = "贪婪"
    emoji = "😱" if fg_v and fg_v < 45 else "😈" if fg_v and fg_v > 55 else "😐"

    ns = news["signal"]
    ns_emoji = "🟢" if ns == "BULLISH" else "🔴" if ns == "BEARISH" else "⚪"

    print(f"\n【市场情绪】", flush=True)
    print(f"  {emoji} 恐惧贪婪: {fg_v} ({fg.get('label','?')}) → {mood}", flush=True)
    print(f"  📰 新闻: {ns_emoji}{ns} | 🟢{news['bullish']} 🔴{news['bearish']} 中{news['neutral']}", flush=True)
    if news.get("headlines"):
        print(f"  头条: {news['headlines'][0][:65]}", flush=True)

    print(f"\n【行情数据】", flush=True)
    print(f"  ₿ BTC: ${btc.get('price',0):>10,.0f} {bdir}{btc_chg:+.2f}% | 高{btc.get('high',0):,.0f} 低{btc.get('low',0):,.0f}", flush=True)
    print(f"  Ξ ETH: ${eth.get('price',0):>10,.0f} {edir}{eth_chg:+.2f}% | 高{eth.get('high',0):,.0f} 低{eth.get('low',0):,.0f}", flush=True)
    if btc.get("volume"):
        print(f"  💧 成交: BTC ${btc['volume']/1e9:.1f}B ETH ${eth.get('volume',0)/1e6:.0f}M", flush=True)

    # Browser: 抓 Square 主页
    posts = []
    if not args.fast:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1400, "height": 900})
                try:
                    page.goto("https://www.binance.com/zh-CN/square/fear-and-greed-index",
                              timeout=15000, wait_until="domcontentloaded")
                    page.wait_for_timeout(7000)
                    # 滚动加载更多内容
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.6)")
                    page.wait_for_timeout(2000)
                    body_text = page.inner_text("body")
                    posts = parse_square_snapshot(body_text)
                    print(f"\n🔥 抓取到 {len(posts)} 个热门帖子", flush=True)
                finally:
                    browser.close()
        except Exception as e:
            print(f"\n⚠️ Browser 异常: {e}", flush=True)

    if posts:
        # 聚合
        bullish_cnt = sum(1 for p in posts if p.get("sentiment") == "看涨")
        bearish_cnt = sum(1 for p in posts if p.get("sentiment") == "看跌")
        all_coins = []
        for p in posts:
            for c in p.get("coins", []):
                if c not in EXCLUDED:
                    all_coins.append(c)
        coin_counts = {}
        for c in all_coins:
            coin_counts[c] = coin_counts.get(c, 0) + 1
        top_coins = sorted(coin_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        total_views = sum(p.get("views", 0) for p in posts)

        print(f"\n【热门帖子】(共{len(posts)}帖, {total_views:,}总浏览)", flush=True)
        print(f"  帖子情绪: 🟢看多{bullish_cnt} | 🔴看空{bearish_cnt} | ⚪中立{len(posts)-bullish_cnt-bearish_cnt}", flush=True)
        if top_coins:
            print(f"  高频币种: " + " ".join(f"{c}({n})" for c,n in top_coins), flush=True)
        print(f"  帖子摘要:", flush=True)
        for i, p in enumerate(posts[:5]):
            sent = "🟢" if p.get("sentiment") == "看涨" else "🔴" if p.get("sentiment") == "看跌" else "⚪"
            pnl_s = f"${p['pnl']:+,}" if p.get("pnl") is not None else ""
            coins_s = " ".join(f"${c}" for c in p.get("coins", [])[:3])
            views_s = f"👁{p.get('views',0):,}" if p.get('views') else ""
            print(f"    [{i+1}] {sent} {pnl_s:>12s} {views_s:>8s} {p['text'][:50]} {coins_s}", flush=True)

    # 信号
    print(f"\n【信号判断】", flush=True)
    signals = []
    if btc_chg < -3: signals.append(f"₿ BTC急跌 {btc_chg:+.1f}%")
    elif btc_chg < -1.5 and news["signal"] == "BEARISH": signals.append(f"₿ BTC下跌+新闻偏空")
    if eth_chg < -4: signals.append(f"Ξ ETH急跌 {eth_chg:+.1f}%")
    if news["signal"] == "BEARISH" and news["bearish"] > news["bullish"] * 2:
        signals.append(f"📰 新闻偏空({news['bearish']}v{news['bullish']})")
    if posts:
        pnl_posts = [p for p in posts if p.get("pnl") is not None]
        if pnl_posts:
            total_pnl = sum(p["pnl"] for p in pnl_posts)
            if total_pnl > 0: signals.append(f"🐋 大户总盈利 ${total_pnl:,.0f}")
            else: signals.append(f"🐋 大户总亏损 ${total_pnl:,.0f}")
    if not signals:
        signals.append("无特殊信号，等待机会")
    for s in signals:
        print(f"  → {s}", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"📋 {now} | Browser: {'✅开启' if not args.fast else '⚠️纯API'}", flush=True)
    print(f"{'='*60}", flush=True)

    with open("/tmp/hunt_signals.json", "w") as f:
        json.dump({
            "scan_time": now, "fear_greed": fg, "market_mood": mood,
            "btc": btc, "eth": eth, "news": news,
            "posts": posts, "signals": signals,
        }, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
