#!/usr/bin/env python3
"""
加密货币新闻爬虫 v1.0
基于 RSS  feeds，无需 API key
"""
import os
import sys
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 清除所有代理
for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

RSS_FEEDS = [
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Bitcoinist", "https://bitcoinist.com/feed/"),
]

BULLISH_KEYWORDS = [
    "surge", "rally", "breakout", "bullish", "all-time high", "ath",
    "soar", "jump", "gain", "rise", "growth", "adoption", "buy",
    "support", "upgrade", "etf", "institutional", "launch",
    "positive", "optimistic", "record", "high", "climb", "bid",
]

BEARISH_KEYWORDS = [
    "crash", "plunge", "bearish", "sell", "hack", "scam", "ban",
    "regulation", "risk", "crackdown", "collapse", "fear", "drop",
    "warn", "investigation", "probe", "security", "breach", "exploit",
    "loses", "loss", "plunge", "tumble", "slide", "slump", "death",
]


def strip_tags(text):
    """去除HTML标签"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&nbsp;', ' ', text)
    return text.strip()


def parse_rss_feed(url, name, timeout=10):
    """解析单个RSS源"""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            xml_data = r.read()
            root = ET.fromstring(xml_data)
            # 尝试多种RSS格式
            items = root.findall('.//item')
            if not items:
                items = root.findall('.//entry')
            if not items:
                # 尝试 Atom 格式
                items = root.findall('.//atom:entry', {'atom': 'http://www.w3.org/2005/Atom'})
                if not items:
                    items = root.findall('.//{http://www.w3.org/2005/Atom}entry')

            news_list = []
            for item in items:
                title_el = item.find('title')
                desc_el = item.find('description') or item.find('summary') or item.find('content')
                link_el = item.find('link')
                date_el = item.find('pubDate') or item.find('published') or item.find('updated')

                title = strip_tags(title_el.text) if title_el is not None else ""
                desc = strip_tags(desc_el.text) if desc_el is not None else ""
                link = link_el.text if link_el is not None else (link_el.get('href') if isinstance(link_el, object) and hasattr(link_el, 'get') else "")

                if title:
                    news_list.append({
                        "title": title,
                        "body": desc[:300],
                        "source": name,
                        "url": link,
                        "published": date_el.text if date_el is not None else "",
                    })
            return news_list
    except Exception as e:
        return []


def classify_sentiment(news_list):
    """情绪分类"""
    bullish = bearish = neutral = 0
    btc_news = eth_news = 0

    for n in news_list:
        text = (n.get("title", "") + " " + n.get("body", "")).lower()

        # 统计关键词
        b_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
        be_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)

        if be_count > b_count:
            bearish += 1
        elif b_count > be_count:
            bullish += 1
        else:
            neutral += 1

        # 币种统计
        if any(w in text for w in ['bitcoin', 'btc', 'satoshi']):
            btc_news += 1
        if any(w in text for w in ['ethereum', 'eth', 'ether']):
            eth_news += 1

    total = bullish + bearish + neutral
    if total == 0:
        return {"bullish": 0, "bearish": 0, "neutral": 0, "signal": "NEUTRAL", "btc_count": 0, "eth_count": 0}

    if bullish > bearish * 1.5:
        signal = "BULLISH"
    elif bearish > bullish * 1.5:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    return {
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "signal": signal,
        "bullish_pct": round(bullish / total * 100, 1),
        "bearish_pct": round(bearish / total * 100, 1),
        "btc_count": btc_news,
        "eth_count": eth_news,
    }


def main():
    print("📰 抓取加密新闻 (RSS)...", flush=True)

    all_news = []

    # 并行抓取所有源
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(parse_rss_feed, url, name): name for name, url in RSS_FEEDS}
        for future in as_completed(futures):
            name = futures[future]
            try:
                news = future.result()
                all_news.extend(news)
                print(f"  ✅ {name}: {len(news)} 条", flush=True)
            except Exception as e:
                print(f"  ❌ {name}: {e}", flush=True)

    if not all_news:
        print("❌ 未能获取任何新闻")
        return

    # 去重（按标题前50字符）
    seen = set()
    unique_news = []
    for n in all_news:
        key = n["title"][:50].lower()
        if key and key not in seen:
            seen.add(key)
            unique_news.append(n)

    # 按时间排序（把有时间戳的排前面）
    unique_news.sort(key=lambda x: x.get("published", ""), reverse=True)

    sentiment = classify_sentiment(unique_news)

    print(f"\n{'='*60}", flush=True)
    print(f"📊 情绪分析 ({len(unique_news)} 条，去重后)", flush=True)
    print(f"  🟢 看涨: {sentiment['bullish']} ({sentiment['bullish_pct']}%)", flush=True)
    print(f"  🔴 看跌: {sentiment['bearish']} ({sentiment['bearish_pct']}%)", flush=True)
    print(f"  ⚪ 中性: {sentiment['neutral']}", flush=True)
    print(f"  📌 信号: {sentiment['signal']}", flush=True)
    print(f"  ₿  BTC新闻: {sentiment['btc_count']}条 | Ξ ETH新闻: {sentiment['eth_count']}条", flush=True)

    print(f"\n📰 最新新闻:", flush=True)
    for n in unique_news[:8]:
        title = n["title"][:60]
        src = n["source"]
        pub = n.get("published", "")[:16]
        print(f"  [{src:12s}] {title}...", flush=True)

    # 来源统计
    sources = {}
    for n in unique_news:
        sources[n["source"]] = sources.get(n["source"], 0) + 1
    print(f"\n📡 来源: " + " | ".join(f"{k}={v}" for k, v in sorted(sources.items(), key=lambda x: x[1], reverse=True)), flush=True)
    print(f"{'='*60}", flush=True)

    # 输出JSON
    output = {
        "scan_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(unique_news),
        "sentiment": sentiment,
        "news": unique_news[:20],
        "sources": sources,
    }

    out_file = "/tmp/crypto_news.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON: {out_file}", flush=True)

    summary = f"📰 {len(unique_news)}条新闻 | 信号:{sentiment['signal']} | 🟢{sentiment['bullish']} 🔴{sentiment['bearish']} ⚪{sentiment['neutral']}"
    print(f"📋 {summary}", flush=True)


if __name__ == "__main__":
    main()
