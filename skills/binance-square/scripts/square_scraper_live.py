#!/usr/bin/env python3
"""
Binance Square Scraper — v9.0 (CDP Live Session)
Uses Playwright CDP to connect to User's existing Chrome session,
extracting full content from Binance Square with login state.
"""
import re, json, argparse, time, ast
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict

# ===== 词表 =====
MAINSTREAM = {"BTC","ETH","SOL","BNB","XRP","ADA","DOGE","XLM","USDT",
              "BUSD","USDC","DOT","AVAX","LINK","MATIC","SHIB","LTC"}
MEME = {"DOGE","SHIB","PEPE","WIF","BONK","FLOKI","ELON","TRUMP","MAGA"}
EXCLUDED = {
    "BTC","ETH","SOL","BNB","XRP","ADA","DOGE","XLM","USDT","BUSD",
    "USDC","DAI","DOT","AVAX","LINK","MATIC","SHIB","LTC","FTT","UNI",
    "OKB","USDP","TUSD","AE","LEVER","ONG","SXP","YFI","COMP","MKR",
    "ZEC","ENJ","MANA","BAT","AXS","BLZ","CHZ","HBAR","ALGO","VET",
    "FTM","THETA","EOS","IOTA","NEO","WAVES","ZIL","KAVA","AUDIO",
}
FIN_KW = [
    "做多","做空","开仓","平仓","止损","止盈","买入","卖出","合约",
    "永续","杠杆","多头","空头","爆仓","强平","建仓","补仓","仓位",
    "多单","空单","多空","抄底","逃顶","涨幅","跌幅","暴涨","暴跌",
    "盈利","亏损","本金","浮亏","浮盈","反弹","回调","趋势","信号",
    "预测","阻力","支撑","突破","牛市","熊市","梭哈","上车","下车",
    "做空","看跌","看涨","止损","止盈","买入","卖出","挂单","现价",
]
NOISE_KW = [
    "女生记住","婚姻","男朋友","高嫁","低嫁","问界","M9","华为","手机",
    "特斯拉","抖音","小红书","瑜伽","人民公园","美女","相亲","约会",
    "婚礼","装修","考研","考公","留学","移民","工资","裁员","面试",
]

def coin_filter(coins, coin_type):
    if coin_type == "all":
        return coins
    elif coin_type == "mainstream":
        return [c for c in coins if c in MAINSTREAM]
    elif coin_type == "small":
        return [c for c in coins if c not in MAINSTREAM and c not in EXCLUDED]
    elif coin_type == "meme":
        return [c for c in coins if c in MEME]
    return coins

def extract_coins(text):
    return list({c for c in re.findall(r'\$([A-Z]{2,10})', text) if c not in EXCLUDED})

def is_noise(text):
    if any(kw in text for kw in NOISE_KW):
        return not any(kw in text for kw in FIN_KW)
    return False

def is_finance(text):
    return any(kw in text for kw in FIN_KW)

def score(p):
    recency = max(0, 30 - (p["age_mins"] or 999)) * 2
    return recency + (p.get("likes", 0) + p.get("comments", 0) * 3) / 100 + len(p.get("coins", []))

JS_SCRAPE = """
function() {
    var results = [];
    var seen = new Set();
    var timeRegex = /(\\d+)\\s*(分钟|小时|天)/;
    var lines = document.body.innerText.split('\\n');
    var current = null;
    for (var i = 0; i < lines.length; i++) {
        var trimmed = lines[i].trim();
        if (!trimmed || trimmed.length > 200) continue;
        var timeMatch = trimmed.match(timeRegex);
        if (timeMatch) {
            if (current && current.text && current.text.length > 3) {
                var key = current.text.slice(0, 60);
                if (!seen.has(key)) { seen.add(key); results.push(current); }
            }
            var val = parseInt(timeMatch[1]);
            var unit = timeMatch[2];
            current = {
                time: trimmed,
                age_mins: unit==='分钟' ? val : unit==='小时' ? val*60 : val*1440,
                text: '', likes: 0, comments: 0, views: 0
            };
        } else if (current) {
            var numMatch = trimmed.match(/^(\\d+(?:,\\d+)*)$/);
            if (numMatch) {
                var n = parseInt(numMatch[1].replace(',',''));
                if (!current.likes) current.likes = n;
                else if (!current.comments) current.comments = n;
                else if (!current.views) current.views = n;
            } else {
                current.text += ' ' + trimmed;
            }
        }
    }
    if (current && current.text && current.text.length > 3) {
        var key = current.text.slice(0, 60);
        if (!seen.has(key)) seen.add(key), results.push(current);
    }
    var coinsFn = function(text) {
        var m = text.match(/\\$[A-Z]{2,10}/g) || [];
        return [...new Set(m)];
    };
    return results.slice(0, 80).map(function(r) {
        return {
            time: r.time,
            age_mins: r.age_mins,
            coins: coinsFn(r.text).join(','),
            text: r.text.replace(/\\$[A-Z]{2,10}/g,'').slice(0, 140),
            likes: r.likes || 0,
            comments: r.comments || 0
        };
    });
}
"""

URLS = {
    "square":   "https://www.binance.com/zh-CN/square",
    "trending": "https://www.binance.com/zh-CN/square/trending",
    "hot":      "https://www.binance.com/zh-CN/square/hot",
}

def _scrape_cdp(url, scroll_rounds=3):
    """Connect via CDP to User's Chrome session and scrape Binance Square."""
    from playwright.sync_api import sync_playwright
    
    cdp_url = "http://127.0.0.1:18800"
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            print(f"  ⚠️ CDP连接失败: {e}")
            return []
        
        try:
            # Find square page
            square_page = None
            for page in browser.contexts[0].pages:
                if 'square' in page.url.lower():
                    square_page = page
                    break
            
            if not square_page:
                print("  ⚠️ 未找到Square页面")
                browser.disconnect()
                return []
            
            # Navigate if needed
            if square_page.url != url:
                try:
                    square_page.goto(url, wait_until='commit', timeout=10000)
                    square_page.wait_for_timeout(4000)
                except:
                    pass
            
            # Scroll to load posts
            for i in range(scroll_rounds):
                square_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                square_page.wait_for_timeout(2000)
            
            # Extract
            result = square_page.evaluate(JS_SCRAPE)
            browser.disconnect()
            return result or []
        except Exception as e:
            print(f"  ⚠️ CDP scrape error: {e}")
            try:
                browser.disconnect()
            except:
                pass
            return []

def fetch_one_topic(name, slug, per_topic, coin_type, max_age_mins):
    url = f"https://www.binance.com/zh-CN/square/hashtag/{slug}"
    posts = _scrape_cdp(url, scroll_rounds=min(3, per_topic // 5 + 2))
    topic_posts = []
    for p in posts:
        if p["age_mins"] > max_age_mins:
            continue
        filtered_coins = coin_filter(p.get("coins", []), coin_type)
        if coin_type != "all" and not filtered_coins:
            continue
        p["coins"] = filtered_coins
        p["topic"] = name
        topic_posts.append(p)
    return name, url, topic_posts

def _parse_result(raw):
    if not raw:
        return []
    if isinstance(raw, str):
        try: raw = ast.literal_eval(raw)
        except: return []
    posts = []
    for item in (raw or []):
        age = item.get("age_mins", 999)
        coins = [c.replace("$","") for c in (item.get("coins","") or "").split(",") if c]
        posts.append({
            "time": item.get("time",""),
            "age_mins": age,
            "coins": coins,
            "text": item.get("text","").strip(),
            "likes": item.get("likes", 0) or 0,
            "comments": item.get("comments", 0) or 0,
        })
    return posts

def report(all_posts, max_age_mins, top_n, coin_type):
    now = datetime.now(timezone(timedelta(hours=8)))
    now_str = now.strftime("%Y-%m-%d %H:%M")
    age_label = f"{max_age_mins}min"
    
    recent = [p for p in all_posts if p["age_mins"] <= max_age_mins]
    older   = [p for p in all_posts if p["age_mins"] > max_age_mins]
    finance_recent = [p for p in recent if is_finance(p["text"]) and not is_noise(p["text"])]
    finance_older  = [p for p in older   if is_finance(p["text"]) and not is_noise(p["text"])]
    
    all_coins = []
    for p in all_posts:
        for c in p.get("coins", []):
            if coin_filter([c], coin_type):
                all_coins.append(c)
    coin_cnt = Counter(all_coins)
    
    print(f"\n{'━'*60}")
    print(f"📊 币安 Square v9.0 CDP | {now_str} | ≤{max_age_mins}min | 币种:{coin_type}")
    print(f"{'━'*60}")
    print(f"  总帖子: {len(all_posts)}  |  满足: {len(recent)}  |  仅计入: {len(older)}")
    print(f"  金融帖: {len(finance_recent)} 满足 + {len(finance_older)} 补充  |  小币: {len(coin_cnt)}种")
    
    # Topic heat
    topics = defaultdict(list)
    for p in all_posts:
        topics[p.get("topic","")].append(p)
    topic_finance = {t: [p for p in ps if is_finance(p["text"]) and not is_noise(p["text"])]
                     for t, ps in topics.items()}
    sorted_topics = sorted(topic_finance.items(), key=lambda x: len(x[1]), reverse=True)
    if sorted_topics:
        print(f"\n🔥 Topic 讨论区热度 (金融帖数)")
        print(f"    排名  话题                               金融帖  概览                  ")
        print(f"  ────────────────────────────────────────────────────────────")
        for i, (t, ps) in enumerate(sorted_topics[:8], 1):
            sample = ps[0]["text"][:20] if ps else ""
            print(f"  {i:>2}.  #{t:<30s} {len(ps)}帖")
    
    # Coin opportunities
    if coin_cnt:
        print(f"\n🪙 小币实时机会 ({coin_type})")
        print(f"    排名  币种            次    信号  摘要                            ")
        print(f"  ────────────────────────────────────────────────────────────")
        for i, (c, cnt) in enumerate(coin_cnt.most_common(top_n), 1):
            samples = [p["text"] for p in all_posts if c in p.get("coins",[]) and is_finance(p["text"])]
            sample = samples[0][:30] if samples else ""
            sig = "⚡" if any(is_finance(p["text"]) and not is_noise(p["text"]) for p in all_posts if c in p.get("coins",[])) else "💤"
            print(f"  {i:>2}.  ${c:<10s}{cnt:>3d}次 {sig}  {sample}")
    
    # Recent posts
    if recent:
        print(f"\n📌 满足条件帖子 (≤{max_age_mins}min) 共{len(recent)}帖")
        print("━"*60)
        for p in sorted(recent, key=lambda x: x["age_mins"])[:20]:
            coins_str = " ".join(f"${c}" for c in p["coins"][:3])
            age = f"{p['age_mins']:.0f}min" if p['age_mins'] < 60 else f"{p['age_mins']//60}h前"
            finance_tag = "📈" if is_finance(p["text"]) and not is_noise(p["text"]) else "  "
            print(f"  [{age:>8s}] {finance_tag} {coins_str:<20s} {p['text'][:60]}")
    
    # Older posts
    older_fin = [p for p in finance_older if coin_filter(p.get("coins",[]), coin_type)]
    if older_fin:
        print(f"\n📋 不满足条件(仅计入总数) 共{len(older_fin)}帖:")
        for p in older_fin[:10]:
            coins_str = " ".join(f"${c}" for c in p["coins"][:3])
            age = f"{p['age_mins']//60}h前" if p['age_mins'] >= 60 else f"{p['age_mins']}min前"
            print(f"  {age:<8s} {coins_str:<20s} {p['text'][:50]}")
    
    print(f"\n{'━'*60}")
    print(f"📋 {now_str} | ≤{max_age_mins}min | {len(all_posts)}帖 | {len(finance_recent)}金融帖 | {sum(coin_cnt.values())}次小币提及")
    print(f"{'━'*60}")

def main():
    ap = argparse.ArgumentParser(description="Binance Square Scraper v9.0 CDP")
    ap.add_argument("--min", type=int, default=60, help="时间精度(分钟)")
    ap.add_argument("--per-topic", type=int, default=30, help="每个Topic最多爬多少帖")
    ap.add_argument("--top", type=int, default=10, help="显示Top N小币")
    ap.add_argument("--coin-type", choices=["all","mainstream","small","meme"],
                    default="all", help="主流币/小币/meme/全部")
    ap.add_argument("--topics", type=int, default=0,
                    help="爬取Top N个热门话题(0=不爬话题只爬广场)")
    ap.add_argument("--tab", choices=["square","trending","hot"], default="square")
    args = ap.parse_args()

    all_posts = []
    square_url = URLS.get(args.tab, URLS["square"])
    print(f"📥 爬取广场页(CDP): {square_url}", flush=True)
    
    posts = _scrape_cdp(square_url, scroll_rounds=3)
    for p in posts:
        p["topic"] = "广场"
    all_posts.extend(posts)
    print(f"  ✅ 广场获取{len(posts)}帖", flush=True)

    if args.topics > 0 and posts:
        topics_to_scrape = [
            ("孙宇晨起诉WLFI", "World%20Liberty%20Financial"),
            ("Arbitrum冻结ETH", "Arbitrum%E5%86%BB%E7%BB%93%E9%BB%98%E5%AE%A2ETH"),
            ("wstETH解锁", "wstETH%E8%A7%A3%E9%94%81%E6%96%B0%E6%B5%81%E5%8A%A8%E6%80%A7%E9%80%9A%E9%81%93"),
            ("Strategy增持BTC", "Strategy%E5%A2%9E%E6%8C%81%E6%AF%94%E7%89%B9%E5%B8%81"),
            ("山寨币复苏", "%E5%B1%B1%E5%AF%A8%E5%B8%81%E5%A4%8D%E8%8B%8F%EF%BC%9F"),
        ][:args.topics]
        print(f"\n📥 爬取{len(topics_to_scrape)}个Topic讨论区 (每Topic最多{args.per_topic}帖)")
        for name, slug in topics_to_scrape:
            name2, url, tp = fetch_one_topic(name, slug, args.per_topic, args.coin_type, args.min)
            all_posts.extend(tp)
            mark = "✅" if tp else "⚠️"
            print(f"  {mark} #{name:<28s} +{len(tp)}帖", flush=True)

    if not all_posts:
        print("⚠️ 未获取到任何数据"); return

    # 去重
    seen, unique = set(), []
    for p in all_posts:
        key = p["text"][:60] if p["text"] else ""
        if key and key not in seen:
            seen.add(key); unique.append(p)
    all_posts = unique

    report(all_posts, max_age_mins=args.min, top_n=args.top, coin_type=args.coin_type)

if __name__ == "__main__":
    main()
