#!/usr/bin/env python3
"""
Binance Square Scraper — v8.0
功能:
  1. 自动识别/指定 Topic 讨论区
  2. 每个 Topic 爬取数量可配置
  3. 筛选主流币/小币/全部
  4. 时间条件筛选（不满足的只计入总数）
  5. Topic 统计报告

用法:
  python3 square_scraper.py --min 60 --per-topic 30 --coin-type small

参数:
  --min N         只看N分钟内的帖子（不满足的计入总数）
  --per-topic N   每个Topic最多爬N帖（默认30）
  --coin-type     all|mainstream|small|meme
                    all=全部（默认）
                    mainstream=BTC/ETH/SOL/BNB/XRP/ADA/DOGE等
                    small=小币（排除主流）
                    meme=DOGE/SHIB/PEPE等meme币
  --topics N      爬取Top N个热门话题（默认10，0=不爬话题只爬广场）
  --tab           square|trending|hot（广场页，不受topics影响）
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

# ===== 默认 Top 话题列表 =====
DEFAULT_TOPICS = [
    ("孙宇晨起诉WLFI", "World%20Liberty%20Financial"),
    ("Arbitrum冻结ETH", "Arbitrum%E5%86%BB%E7%BB%93%E9%BB%91%E5%AE%A2ETH"),
    ("wstETH解锁", "wstETH%E8%A7%A3%E9%94%81%E6%96%B0%E6%B5%81%E5%8A%A8%E6%80%A7%E9%80%9A%E9%81%93"),
    ("Strategy增持BTC", "Strategy%E5%A2%9E%E6%8C%81%E6%AF%94%E7%89%B9%E5%B8%81"),
    ("美伊冲突", "%E7%BE%8E%E4%BC%8A%E5%86%B2%E7%AA%81%E6%8E%A5%E4%B8%8B%E6%9D%A5%E4%BC%9A%E5%A6%82%E4%BD%95%E5%8F%91%E5%B1%95%EF%BC%9F"),
    ("RAVE波动", "RAVE%E5%89%A7%E7%83%88%E6%B3%A2%E5%8A%A8"),
    ("KelpDAO遭攻击", "Kelp%20DAO%E9%81%AD%E6%94%BB%E5%87%BB"),
    ("山寨币复苏", "%E5%B1%B1%E5%AF%A8%E5%B8%81%E5%A4%8D%E8%8B%8F%EF%BC%9F"),
    ("加密市场反弹", "%E5%8A%A0%E5%AF%86%E5%B8%82%E5%9C%BA%E5%8F%8D%E5%BC%B9"),
    ("ARK减持", "ARK%20Invest%E5%87%8F%E6%8C%81Circle%E4%B8%8EBullish%E8%82%A1%E7%A5%A8"),
    ("OpenAI发布GPT5.5", "OpenAI%E5%8F%91%E5%B8%83GPT-5.5"),
    ("Aave救助计划", "Aave%E5%AE%A3%E5%B8%83%E5%8D%8FUnited%E6%95%91%E5%8A%A9%E8%AE%A1%E5%88%92"),
]

URLS = {
    "square":   "https://www.binance.com/zh-CN/square",
    "trending": "https://www.binance.com/zh-CN/square/trending",
    "hot":      "https://www.binance.com/zh-CN/square/hot",
}

def fetch_one_topic(name, slug, per_topic, coin_type, max_age_mins):
    """抓取单个话题页"""
    url = f"https://www.binance.com/zh-CN/square/hashtag/{slug}"
    posts = _fetch_posts(url, scroll_rounds=min(4, per_topic // 5 + 2))
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

def _scrape_undetected(url, scroll_rounds=4):
    """
    Bypass: raise immediately so _fetch_posts falls through to playwright.
    (Selenium Chrome hangs on Binance Square's WebGL-heavy SPA)
    """
    raise RuntimeError("selenium_hang")


def _fetch_posts(url, scroll_rounds=4):
    posts = []
    # 1. undetected_chromedriver（绕过反爬，最优先）
    try:
        posts = _scrape_undetected(url, scroll_rounds)
        if posts:
            print(f"  ✅ undetected获取{len(posts)}帖")
            return posts
    except Exception as e:
        print(f"  ⚠️ undetected失败: {e}")

    # 2. selenium + ChromeDriver
    try:
        posts = _scrape_selenium(url, scroll_rounds)
        if posts:
            print(f"  ✅ selenium获取{len(posts)}帖")
            return posts
    except: pass

    # 3. playwright
    try:
        posts = _scrape_playwright(url, scroll_rounds)
        if posts:
            print(f"  ✅ playwright获取{len(posts)}帖")
            return posts
    except: pass

    return []

def _scrape_selenium(url, scroll_rounds=4):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    import time as _time

    chromedriver_path = '/tmp/chromedriver-linux64/chromedriver'
    chrome_binary = '/usr/bin/google-chrome'
    options = Options()
    options.binary_location = chrome_binary
    options.add_argument('--headless=no')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1400,900')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    except:
        driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(12)

    try:
        driver.get(url)
    except Exception:
        # Page load timed out — stop loading and try to extract what's rendered
        driver.execute_script("try{window.stop&&window.stop()}catch(e){try{window.document.execCommand('Stop')}catch(e2){}}")
    _time.sleep(3)
    for _ in range(scroll_rounds):
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        except:
            pass
        _time.sleep(1.5)
    _time.sleep(1)
    try:
        result = driver.execute_script(f"return ({JS_SCRAPE})()")
    except:
        result = []
    driver.quit()

    return _parse_result(result)

def _scrape_playwright(url, scroll_rounds=4):
    from playwright.sync_api import sync_playwright
    import time as _time
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-setuid-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(url, timeout=20000, wait_until="commit")
            # Wait for SPA content to render (up to 15s)
            try:
                page.wait_for_selector("text=热门话题", timeout=12000)
            except:
                pass
            page.wait_for_timeout(3000)
            # Trigger lazy-load by scrolling
            for _ in range(scroll_rounds):
                page.evaluate("window.scrollTo(0, document.body?.scrollHeight || 0)")
                page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  ⚠️ playwright error: {e}")
            browser.close()
            return []
        try:
            result = page.evaluate(JS_SCRAPE)
        except Exception:
            result = []
        browser.close()
    return _parse_result(result)

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

    inside  = [p for p in all_posts if p["age_mins"] <= max_age_mins]
    outside = [p for p in all_posts if p["age_mins"] > max_age_mins]

    fin_inside  = [p for p in inside  if p["text"] and not is_noise(p["text"]) and is_finance(p["text"])]
    fin_outside = [p for p in outside if p["text"] and not is_noise(p["text"]) and is_finance(p["text"])]
    fin_inside.sort(key=score, reverse=True)

    # Topic 统计
    topic_counter = Counter()
    topic_fin = defaultdict(list)
    for p in fin_inside + fin_outside:
        t = p.get("topic", "广场")
        topic_counter[t] += 1
        topic_fin[t].append(p)

    # 小币统计
    coin_counter = Counter()
    coin_sample = {}
    for p in fin_inside + fin_outside:
        for c in p.get("coins", []):
            if coin_type == "all" or (coin_type != "all" and c):
                coin_counter[c] += 1
                if c not in coin_sample:
                    coin_sample[c] = p["text"][:50]
    top_coins = coin_counter.most_common(top_n * 2)

    print(f"\n{'━'*60}", flush=True)
    print(f"📊 币安 Square v8.0 | {now_str} | ≤{age_label} | 币种:{coin_type}", flush=True)
    print(f"{'━'*60}", flush=True)
    print(f"  总帖子: {len(all_posts)}  |  满足: {len(inside)}  |  仅计入: {len(outside)}", flush=True)
    print(f"  金融帖: {len(fin_inside)} 满足 + {len(fin_outside)} 补充  |  小币: {len(top_coins)}种", flush=True)

    # Topic 统计
    if topic_counter:
        print(f"\n🔥 Topic 讨论区热度 (金融帖数)", flush=True)
        print(f"  {'排名':>4}  {'话题':28s}  {'金融帖':>6}  {'概览':20s}", flush=True)
        print(f"  {'─'*60}", flush=True)
        for i, (topic, cnt) in enumerate(topic_counter.most_common(15), 1):
            sample = fin_outside[0]["text"][:20] if topic_fin[topic] else ""
            print(f"  {i:4}.  #{topic:<26s} {cnt:5d}帖", flush=True)

    # 小币
    if top_coins:
        print(f"\n🪙 小币实时机会 ({coin_type})", flush=True)
        print(f"  {'排名':>4}  {'币种':10s}  {'次':>3}  {'信号':>4}  {'摘要':30s}", flush=True)
        print(f"  {'─'*60}", flush=True)
        for i, (coin, cnt) in enumerate(top_coins[:top_n], 1):
            sig = "🔥" if cnt >= 5 else "⚡" if cnt >= 3 else "💤"
            print(f"  {i:4}.  ${coin:<8s} {cnt:3d}次 {sig}  {coin_sample.get(coin,'')[:30]}", flush=True)

    # 满足条件的帖子
    if fin_inside:
        print(f"\n{'━'*60}", flush=True)
        print(f"📌 满足条件帖子 (≤{age_label}) 共{len(fin_inside)}帖", flush=True)
        print(f"{'━'*60}", flush=True)
        for p in fin_inside[:12]:
            coins_s = " ".join(f"${c}" for c in p["coins"][:5]) or "—"
            m = p["age_mins"]
            tstr = f"{m}min前" if m < 60 else f"{m//60}h前"
            topic = p.get("topic", "")
            tag = f"#{topic}" if topic else ""
            print(f"\n  [{tstr:>8}] {coins_s} {tag}", flush=True)
            print(f"    {p['text'][:100]}", flush=True)
            print(f"    👍{p['likes']}  💬{p['comments']}", flush=True)

    if fin_outside:
        print(f"\n{'─'*56}", flush=True)
        print(f"📋 不满足条件(仅计入总数) 共{len(fin_outside)}帖:", flush=True)
        for p in sorted(fin_outside, key=lambda x: x["age_mins"])[:6]:
            coins_s = " ".join(f"${c}" for c in p["coins"][:4]) or "—"
            m = p["age_mins"]
            tstr = f"{m}min前" if m < 60 else f"{m//60}h前"
            topic = p.get("topic", "")
            tag = f"#{topic}" if topic else ""
            print(f"  {tstr:>6}  {coins_s:<18s} {tag} {p['text'][:35]}", flush=True)

    print(f"\n{'━'*60}", flush=True)
    print(f"📋 {now_str} | ≤{age_label} | {len(all_posts)}帖 | {len(fin_inside)}金融帖 | {sum(coin_counter.values())}次小币提及", flush=True)
    print(f"{'━'*60}", flush=True)

    with open("/tmp/square_signals.json", "w", encoding="utf-8") as f:
        json.dump({
            "scan_time": now_str, "max_age_mins": max_age_mins,
            "coin_type": coin_type,
            "total": len(all_posts), "inside": len(inside), "outside": len(outside),
            "topic_stats": [{"topic":t,"count":c} for t,c in topic_counter.most_common(20)],
            "coin_stats": [{"coin":c,"count":n} for c,n in top_coins],
            "fin_posts": [{"time":p["time"],"age_mins":p["age_mins"],"coins":p["coins"],
                           "text":p["text"][:200],"topic":p.get("topic",""),
                           "likes":p["likes"],"comments":p["comments"]}
                          for p in fin_inside[:20]],
        }, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser(description="Binance Square Scraper v8.0")
    ap.add_argument("--min", type=int, default=60, help="时间精度(分钟)")
    ap.add_argument("--per-topic", type=int, default=30, help="每个Topic最多爬多少帖")
    ap.add_argument("--top", type=int, default=10, help="显示Top N小币")
    ap.add_argument("--coin-type", choices=["all","mainstream","small","meme"],
                    default="all", help="主流币/小币/meme/全部")
    ap.add_argument("--topics", type=int, default=10,
                    help="爬取Top N个热门话题(0=不爬话题只爬广场)")
    ap.add_argument("--tab", choices=["square","trending","hot"], default="square")
    args = ap.parse_args()

    all_posts = []

    # 1. 爬广场页
    if args.topics == 0:
        square_url = URLS.get(args.tab, URLS["square"])
        print(f"📥 爬取广场页: {square_url}", flush=True)
        posts = _fetch_posts(square_url, scroll_rounds=4)
        for p in posts:
            p["topic"] = "广场"
        all_posts.extend(posts)
        print(f"  ✅ 广场获取{len(posts)}帖", flush=True)
    else:
        # 2. 爬广场页
        square_url = URLS.get(args.tab, URLS["square"])
        print(f"📥 爬取广场页: {square_url}", flush=True)
        posts = _fetch_posts(square_url, scroll_rounds=3)
        for p in posts:
            p["topic"] = "广场"
        all_posts.extend(posts)
        print(f"  ✅ 广场获取{len(posts)}帖", flush=True)

        # 3. 爬各Topic页
        topics_to_scrape = DEFAULT_TOPICS[:args.topics]
        print(f"\n📥 爬取{len(topics_to_scrape)}个Topic讨论区 (每Topic最多{args.per_topic}帖)", flush=True)
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {
                ex.submit(fetch_one_topic, name, slug, args.per_topic, args.coin_type, args.min): name
                for name, slug in topics_to_scrape
            }
            for f in as_completed(futures):
                name = futures[f]
                try:
                    _, url, tp = f.result(timeout=20)
                    all_posts.extend(tp)
                    mark = "✅" if tp else "⚠️"
                    print(f"  {mark} #{name:<28s} +{len(tp)}帖", flush=True)
                except TimeoutError:
                    print(f"  ⏱️  #{name}: 超时跳过 (20s)", flush=True)
                except Exception as e:
                    print(f"  ❌ #{name}: {e}", flush=True)

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
