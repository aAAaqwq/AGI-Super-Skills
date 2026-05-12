#!/usr/bin/env python3
"""
Binance Square Scraper v12.0 — CDP Live Session + Multi-Topic + Concurrent
工作流程：
  1. 打开 trends 页面 → 解析话题列表（含 slug + 名称）
  2. 爬取广场页（实时帖子流）
  3. 并发进入话题页 → 滚动加载最新帖子（可配置并发数）
  4. 合并所有话题的帖子 → 分析 → 汇报
"""
import re, argparse, time, threading
from datetime import datetime, timezone, timedelta
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
    "看跌","看涨","挂单","现价",
]
NOISE_KW = [
    "女生记住","婚姻","男朋友","高嫁","低嫁","问界","M9","华为","手机",
    "特斯拉","抖音","小红书","瑜伽","人民公园","美女","相亲","约会",
    "婚礼","装修","考研","考公","留学","移民","工资","裁员","面试",
]

def coin_filter(coins, coin_type):
    if coin_type == "all": return coins
    elif coin_type == "mainstream": return [c for c in coins if c in MAINSTREAM]
    elif coin_type == "small": return [c for c in coins if c not in MAINSTREAM and c not in EXCLUDED]
    elif coin_type == "meme": return [c for c in coins if c in MEME]
    return coins

def is_noise(text):
    return any(kw in text for kw in NOISE_KW) and not any(kw in text for kw in FIN_KW)

def is_finance(text):
    return any(kw in text for kw in FIN_KW)

def parse_posts_from_text(text):
    results = []
    seen = set()
    time_regex = re.compile(r'(\d+)\s*(分钟|小时|天)')
    lines = text.split('\n')
    current = None
    for line in lines:
        line = line.strip()
        if not line or len(line) > 300:
            continue
        m = time_regex.search(line)
        if m:
            if current and current['text'] and len(current['text']) > 5:
                key = current['text'][:60]
                if key not in seen:
                    seen.add(key)
                    results.append(current)
            val, unit = int(m.group(1)), m.group(2)
            age = val if unit == '分钟' else val * 60 if unit == '小时' else val * 1440
            current = {'time': line, 'age_mins': age, 'text': '', 'coins': [], 'likes': 0, 'comments': 0}
        elif current:
            coins = re.findall(r'\$([A-Z]{2,10})', line)
            if coins:
                current['coins'].extend(coins)
            num = re.match(r'^(\d{1,5})$', line)
            if num:
                n = int(num.group(1))
                if not current['likes']: current['likes'] = n
                elif not current['comments']: current['comments'] = n
            else:
                current['text'] += ' ' + line
    if current and current['text'] and len(current['text']) > 5:
        key = current['text'][:60]
        if key not in seen:
            results.append(current)
    return results

from urllib.parse import unquote

def parse_trends_page(text, html):
    """解析 trends 页面，提取话题名称 + slug（需要 innerText + HTML）"""
    topics = []
    
    # 方式1: 标准格式 #话题名 + 数字 人讨论中/次浏览
    pattern1 = re.compile(r'#([^\n#]{2,50}?)\s*\n?\s*([\d,]+)\s*(?:人讨论中|次浏览)', re.MULTILINE)
    for m in pattern1.finditer(text):
        name = m.group(1).strip()
        count = int(m.group(2).replace(',', ''))
        topics.append((name, count))
    
    # 如果方式1结果少，尝试方式2: 从HTML中直接提取
    # 格式: /zh-CN/square/hashtag/slug 后面跟着话题名
    slug_pattern = re.compile(r'/zh-CN/square/hashtag/([^"\'&\s]+)')
    slugs = slug_pattern.findall(html)
    
    # 方式2补充: 如果 slugs 比 topics 多，用 slug 名作为话题名
    if len(slugs) > len(topics):
        existing_names = {t[0].lower().replace(' ','').replace('-','') for t in topics}
        for slug in slugs:
            # slug 可能是 URL 编码的中文或英文
            slug_name = unquote(slug).replace('-', ' ')
            if slug_name.lower().replace(' ','') not in existing_names:
                topics.append((slug_name, 0))
                existing_names.add(slug_name.lower().replace(' ',''))
    
    # 为每个 topic 匹配 slug（按名称模糊匹配，不用位置）
    result = []
    used_slugs = set()
    for name, count in topics:
        name_clean = unquote(name).lower().replace(' ', '').replace('#', '')
        best_slug = ''
        for s in slugs:
            if s in used_slugs:
                continue
            s_clean = unquote(s).lower().replace(' ', '').replace('-', '')
            # 完全匹配
            if s_clean == name_clean:
                best_slug = s
                break
            if s_clean in name_clean or name_clean in s_clean:
                overlap_len = min(len(s_clean), len(name_clean))
                longer_len = max(len(s_clean), len(name_clean))
                if longer_len == 0 or overlap_len / longer_len >= 0.5:
                    best_slug = s
                    break
        if not best_slug:
            continue  # 匹配不到slug则丢弃该话题
        used_slugs.add(best_slug)
        result.append({'name': name, 'slug': best_slug, 'count': count})
    return result

def scrape_topic_page_cdp(cdp_url, topic_name, slug, scroll_rounds=2, per_topic=10):
    """独立连接CDP，爬取单个话题页（线程安全）"""
    from playwright.sync_api import sync_playwright
    
    posts = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else None
            if not context:
                browser.close()
                return []
            
            page = context.new_page()
            url = f"https://www.binance.com/zh-CN/square/hashtag/{slug}"
            
            try:
                page.goto(url, wait_until='commit', timeout=15000)
                page.wait_for_timeout(4000)
            except Exception as e:
                print(f"    ⚠️ #{topic_name} 导航失败: {e}", flush=True)
                page.close()
                browser.close()
                return []

            # 切换到"最新内容" tab
            try:
                latest_tab = page.get_by_text("最新内容", exact=True)
                latest_tab.click()
                page.wait_for_timeout(3000)
            except:
                pass

            # 滚动加载
            for i in range(scroll_rounds):
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                except:
                    break

            text = page.inner_text('body')
            raw_posts = parse_posts_from_text(text)
            
            # 按参数截断
            raw_posts = raw_posts[:per_topic]

            for item in raw_posts:
                coins = list(set(c for c in item.get('coins', []) if c not in EXCLUDED))
                posts.append({
                    'time': item.get('time', ''),
                    'age_mins': item.get('age_mins', 999),
                    'coins': coins,
                    'text': item.get('text', '').strip(),
                    'likes': item.get('likes', 0) or 0,
                    'comments': item.get('comments', 0) or 0,
                    'topic': topic_name,
                })
            page.close()
            browser.close()
    except Exception as e:
        print(f"    ⚠️ #{topic_name} 异常: {e}", flush=True)
    
    return posts

def report(all_posts, max_age_mins, top_n, coin_type, elapsed_secs):
    recent = [p for p in all_posts if p['age_mins'] <= max_age_mins]
    older = [p for p in all_posts if p['age_mins'] > max_age_mins]
    fin_recent = [p for p in recent if is_finance(p['text']) and not is_noise(p['text'])]
    fin_older = [p for p in older if is_finance(p['text']) and not is_noise(p['text'])]
    coin_cnt = Counter(c for p in all_posts for c in p.get('coins', []))
    topics = defaultdict(list)
    for p in all_posts:
        topics[p.get('topic', '')].append(p)
    topic_fin = {t: [p for p in ps if is_finance(p['text']) and not is_noise(p['text'])]
                 for t, ps in topics.items()}
    now = datetime.now(timezone(timedelta(hours=8)))
    now_str = now.strftime('%Y-%m-%d %H:%M')
    
    print(f"\n{'━'*60}")
    print(f"📊 币安 Square v12.0 CDP | {now_str} | ≤{max_age_mins}min | {coin_type}")
    print(f"{'━'*60}")
    print(f"  总帖子: {len(all_posts)}  |  满足: {len(recent)}  |  仅计入: {len(older)}")
    print(f"  金融帖: {len(fin_recent)} 满足 + {len(fin_older)} 补充  |  小币: {len(coin_cnt)}种")
    print(f"  话题: {len(topics)} 个")
    
    # Topic heat
    if topic_fin:
        sorted_topics = sorted(topic_fin.items(), key=lambda x: len(x[1]), reverse=True)
        print(f"\n🔥 Topic 讨论区热度 (金融帖数)")
        print(f"    排名  话题                               金融帖  总帖")
        print(f"  ─────────────────────────────────────────────────────")
        for i, (t, ps) in enumerate(sorted_topics[:10], 1):
            print(f"  {i:>2}.  #{t:<32s} {len(ps):>3d}帖  {len(topics[t])}帖")
    
    # Coin opportunities
    if coin_cnt:
        print(f"\n🪙 小币机会 (Top {top_n})")
        print(f"  排名  币种           次    信号  摘要")
        print(f"  ──────────────────────────────────────────────")
        for i, (c, cnt) in enumerate(coin_cnt.most_common(top_n), 1):
            sig = "⚡" if any(is_finance(p['text']) and not is_noise(p['text']) for p in all_posts if c in p.get('coins',[])) else "💤"
            sample = next((p['text'][:25] for p in all_posts if c in p.get('coins',[]) and is_finance(p['text']) and not is_noise(p['text'])), "")
            print(f"  {i:>2}.  ${c:<12s}{cnt:>3d}次 {sig}  {sample}")
    
    if recent:
        print(f"\n📌 满足条件帖子 (≤{max_age_mins}min) 共{len(recent)}帖")
        print("━"*60)
        for p in sorted(recent, key=lambda x: x['age_mins'])[:20]:
            coins_str = ' '.join(f'${c}' for c in p['coins'][:3])
            age = f"{p['age_mins']:.0f}min" if p['age_mins'] < 60 else f"{p['age_mins']//60}h前"
            fin = "📈" if is_finance(p['text']) and not is_noise(p['text']) else "  "
            print(f"  [{age:>8s}] {fin} {coins_str:<18s} {p['text'][:55]}")
    
    print(f"\n{'━'*60}")
    print(f"⏱️ 运行耗时: {elapsed_secs:.1f}s")
    print(f"📋 {now_str} | ≤{max_age_mins}min | {len(all_posts)}帖 | {len(fin_recent)}金融帖 | {sum(coin_cnt.values())}次小币")

def main():
    ap = argparse.ArgumentParser(description="Binance Square Scraper v12.0 CDP Multi-Topic Concurrent")
    ap.add_argument("--min", type=int, default=60)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--coin-type", choices=["all","mainstream","small","meme"], default="all")
    ap.add_argument("--topics", type=int, default=10, help="最多爬取 N 个话题（0=只爬广场）")
    ap.add_argument("--per-topic", type=int, default=10, help="每个话题最多爬 N 帖")
    ap.add_argument("--scrolls", type=int, default=2, help="每话题滚动次数")
    ap.add_argument("--concurrency", type=int, default=5, help="并发话题数（默认5）")
    ap.add_argument("--cdp-port", type=int, default=9222, help="CDP端口（默认9222，OpenClaw用18800）")
    args = ap.parse_args()

    t_start = time.time()
    cdp_url = f"http://127.0.0.1:{args.cdp_port}"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            print(f"⚠️ CDP连接失败: {e}")
            print("  请确保 Chrome 已打开 binance.com/zh-CN/square")
            return

        # ── Step 0: 检查登录状态 ──
        ctx = browser.contexts[0]
        check_page = ctx.new_page()
        try:
            check_page.goto('https://www.binance.com/zh-CN/my/dashboard', wait_until='domcontentloaded', timeout=15000)
            time.sleep(2)
            final_url = check_page.url
            body_text = check_page.inner_text('body')[:500]
            if 'login' in final_url.lower() or '登录' in body_text[:200] or 'register' in final_url.lower():
                print("⚠️ Binance 未登录或 cookie 已过期（Square 公开内容仍可爬取，但部分功能受限）")
            print("✅ Binance 登录状态正常", flush=True)
        except Exception as e:
            print(f"⚠️ 登录检测跳过（{e}），继续运行...", flush=True)
        finally:
            try: check_page.close()
            except: pass

        # ── Step 1: 获取 trends 话题列表 ──
        print("📥 Step 1: 获取热门话题列表...", flush=True)
        trends_url = "https://www.binance.com/zh-CN/square/trends"
        
        trends_page = None
        for page in browser.contexts[0].pages:
            if 'trends' in page.url:
                trends_page = page
                break
        
        if not trends_page:
            for page in browser.contexts[0].pages:
                if 'square' in page.url.lower():
                    try:
                        page.goto(trends_url, wait_until='commit', timeout=10000)
                        trends_page = page
                        break
                    except:
                        pass
        
        trends_text = ""
        trends_html = ""
        if trends_page:
            try:
                trends_page.goto(trends_url, wait_until='commit', timeout=10000)
            except:
                pass
            # 多滚动确保加载完整话题列表
            for _ in range(6):
                try:
                    trends_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    trends_page.wait_for_timeout(1500)
                except:
                    break
            trends_text = trends_page.inner_text('body')
            trends_html = trends_page.content()
        
        topics = parse_trends_page(trends_text, trends_html)
        print(f"  ✅ 动态发现 {len(topics)} 个话题", flush=True)
        for i, t in enumerate(topics):
            print(f"     {i+1}. #{t['name']} ({t['count']:,} 人讨论) slug={t.get('slug','')}")
        
        crawl_count = min(args.topics, len(topics)) if args.topics > 0 else 0
        print(f"  📌 将爬取前 {crawl_count} 个话题", flush=True)
        topics = topics[:crawl_count]
        topics_with_slug = [t for t in topics if t.get('slug')]
        
        # ── Step 2: 爬广场页 ──
        print(f"\n📥 Step 2: 爬取广场页...", flush=True)
        all_posts = []
        
        square_page = None
        for page in browser.contexts[0].pages:
            if 'square' in page.url.lower() and 'trends' not in page.url:
                square_page = page
                break
        
        if square_page:
            try:
                square_page.goto("https://www.binance.com/zh-CN/square", wait_until='commit', timeout=10000)
            except:
                pass
            square_page.wait_for_timeout(4000)
            for _ in range(args.scrolls + 1):
                try:
                    square_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    square_page.wait_for_timeout(2000)
                except:
                    break
            text = square_page.inner_text('body')
            raw = parse_posts_from_text(text)
            for item in raw:
                coins = list(set(c for c in item.get('coins', []) if c not in EXCLUDED))
                filtered = coin_filter(coins, args.coin_type) if args.coin_type != 'all' else coins
                all_posts.append({
                    'time': item.get('time', ''),
                    'age_mins': item.get('age_mins', 999),
                    'coins': filtered,
                    'text': item.get('text', '').strip(),
                    'likes': item.get('likes', 0) or 0,
                    'comments': item.get('comments', 0) or 0,
                    'topic': '广场',
                })
            print(f"  ✅ 广场获取 {len(raw)} 帖")
        
        browser.close()

    # ── Step 3: 并发爬取话题页 ──
    if topics_with_slug:
        print(f"\n📥 Step 3: 并发爬取 {len(topics_with_slug)} 个话题页 (并发={args.concurrency})...", flush=True)
        
        topic_results = {}
        topic_lock = threading.Lock()
        
        def worker(topic):
            posts = scrape_topic_page_cdp(cdp_url, topic['name'], topic['slug'],
                                          scroll_rounds=args.scrolls, per_topic=args.per_topic)
            # 过滤币种
            for item in posts:
                filtered = coin_filter(item['coins'], args.coin_type) if args.coin_type != 'all' else item['coins']
                item['coins'] = filtered
            with topic_lock:
                topic_results[topic['name']] = posts
            mark = "✅" if posts else "⚠️"
            print(f"    {mark} #{topic['name']}: +{len(posts)} 帖", flush=True)
        
        # 分批并发
        for batch_start in range(0, len(topics_with_slug), args.concurrency):
            batch = topics_with_slug[batch_start:batch_start + args.concurrency]
            threads = []
            for topic in batch:
                t = threading.Thread(target=worker, args=(topic,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join(timeout=60)
            batch_ids = [t['name'] for t in batch]
            done = sum(1 for name in batch_ids if name in topic_results)
            print(f"  批次 [{batch_start+1}-{batch_start+len(batch)}] 完成: {done}/{len(batch)}", flush=True)
        
        for topic in topics_with_slug:
            all_posts.extend(topic_results.get(topic['name'], []))
        
        skipped = len(topics) - len(topics_with_slug)
        if skipped:
            print(f"  ⏭️ 跳过 {skipped} 个无slug话题")

    elapsed = time.time() - t_start

    if not all_posts:
        print("⚠️ 未获取到任何数据")
        return

    # ── Step 4: 去重 + 汇报 ──
    seen, unique = set(), []
    for p in all_posts:
        key = p['text'][:60] if p['text'] else ''
        if key and key not in seen:
            seen.add(key); unique.append(p)
    all_posts = unique

    report(all_posts, max_age_mins=args.min, top_n=args.top, coin_type=args.coin_type, elapsed_secs=elapsed)

if __name__ == "__main__":
    main()
