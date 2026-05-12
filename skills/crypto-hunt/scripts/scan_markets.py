#!/usr/bin/env python3
"""
Market Scanner v10.0
并发版: ThreadPoolExecutor 10线程并发扫描，速度提升5-8x。
5天 × 7币种 × 3类型 = 105个slug，串行~90s → 并发~15s。
"""
import os, sys, json, re, datetime, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# === 保留本地代理(127.0.0.1)，不阻断 ===
# Polymarket需要走本地代理才能访问，不要清除

# DNS patch已不需要：本地代理处理DNS+路由

import requests

GAMMA_API = "https://gamma-api.polymarket.com"
MAX_WORKERS = 10  # 并发线程数
REQUEST_TIMEOUT = 8  # 单个请求超时

MONTHS = ['january','february','march','april','may','june',
          'july','august','september','october','november','december']

COINS = [
    ('BTC',  'bitcoin',  'btc'),
    ('ETH',  'ethereum', 'eth'),
    ('SOL',  'solana',   'sol'),
    ('XRP',  'xrp',      'xrp'),
    ('BNB',  'bnb',      'bnb'),
    ('DOGE', 'dogecoin', 'doge'),
    ('HYPE', 'hype',     'hype'),
]

# 共享session（连接池复用TCP）
_session = None
def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = False
    return _session

def resolve_slug(slug):
    """解析单个slug，返回(slug, event_data)或(slug, None)，带retry+429 backoff"""
    s = get_session()
    for attempt in range(3):
        try:
            r = s.get(f"{GAMMA_API}/events/slug/{slug}", timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return (slug, r.json())
            elif r.status_code == 429:
                time.sleep(1 * (attempt + 1))
                continue
        except Exception:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    return (slug, None)

def calc_hours_left(end_date_str):
    try:
        end = datetime.datetime.fromisoformat(end_date_str.replace('Z','+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        return max(0, (end - now).total_seconds() / 3600)
    except:
        return None

def extract_threshold(question):
    m = re.search(r'(?:above|below|over|under)\s+\$?([\d,]+(?:\.\d+)?)', question, re.IGNORECASE)
    return m.group(1).replace(',', '') if m else None

def determine_type(question, slug):
    q, s = question.lower(), slug.lower()
    if 'above' in s or '>' in q: return 'ABOVE'
    if 'below' in s or '<' in q: return 'BELOW'
    if 'up or down' in s or 'higher or lower' in q: return 'UPDOWN'
    return 'UNKNOWN'

def parse_market(m, slug):
    """从Gamma API market对象提取标准化数据"""
    q = m.get('question', '')
    end_date = m.get('endDate', '')
    hours_left = calc_hours_left(end_date)
    if hours_left is None:
        return None

    coin = next((c for c, ak, uk in COINS if ak in slug.lower() or uk in slug.lower()), '?')
    mtype = determine_type(q, slug)
    threshold = extract_threshold(q)

    try:
        prices = json.loads(m.get('outcomePrices', '[]'))
        yes_p = float(prices[0]) if len(prices) >= 1 else None
        no_p  = float(prices[1]) if len(prices) >= 2 else None
    except:
        yes_p = no_p = None

    clob_tokens = m.get('clobTokenIds', [])
    if isinstance(clob_tokens, str):
        try: clob_tokens = json.loads(clob_tokens)
        except: clob_tokens = []
    tokens = m.get('tokens', [])
    yes_token = clob_tokens[0] if len(clob_tokens) > 0 else (tokens[0].get('token_id', '') if tokens else '')
    no_token  = clob_tokens[1] if len(clob_tokens) > 1 else (tokens[1].get('token_id', '') if len(tokens) > 1 else '')

    mkt_slug = m.get('slug', slug)
    if (not mkt_slug or mkt_slug == slug) and threshold and mtype in ('ABOVE', 'BELOW'):
        mkt_slug = f"{slug}-{mtype.lower()}-{threshold}"

    return {
        'slug': slug,
        'market_slug': mkt_slug,
        'question': q[:80],
        'coin': coin,
        'type': mtype,
        'threshold': threshold,
        'hours_left': round(hours_left, 1),
        'end_date': end_date[:16],
        'yes_price': yes_p,
        'no_price': no_p,
        'yes_token': yes_token,
        'no_token': no_token,
        'condition_id': m.get('conditionId', ''),
        'volume': float(m.get('volume', 0)),
        'liquidity': float(m.get('liquidity', 0)),
    }

def scan_markets():
    now = datetime.datetime.now(datetime.timezone.utc)
    cst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    t0 = time.time()
    print(f"Market Scan v11.0 — {cst.strftime('%H:%M')} CST ({now.isoformat()} UTC)")

    ACTIONABLE_MAX = 12.0
    WATCHLIST_MAX  = 48.0

    SKILL_DIR = Path(__file__).parent.parent
    data_dir = SKILL_DIR / "data"
    data_dir.mkdir(exist_ok=True)

    # 1. 生成所有slug
    all_slugs = []
    for offset in range(5):
        dt = now + datetime.timedelta(days=offset)
        month = MONTHS[dt.month - 1]
        day = dt.day
        year = dt.year
        for coin, above_kw, updown_kw in COINS:
            all_slugs += [
                f"{above_kw}-above-on-{month}-{day}",
                f"{above_kw}-below-on-{month}-{day}",
                f"{updown_kw}-up-or-down-on-{month}-{day}-{year}",
            ]

    # 2. 并发请求
    slug_to_event = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(resolve_slug, s): s for s in all_slugs}
        for fut in as_completed(futures):
            slug, event = fut.result()
            if event is not None:
                slug_to_event[slug] = event

    # 3. 解析markets
    all_markets = []
    for slug, event in slug_to_event.items():
        for m in event.get('markets', []):
            parsed = parse_market(m, slug)
            if parsed:
                all_markets.append(parsed)

    # 4. Noise filters
    filtered_low_price = 0
    filtered_low_liquidity = 0
    filtered_dedup = 0

    # Price range filter: skip markets with no information content
    price_filtered = []
    for m in all_markets:
        yp = m['yes_price']
        if yp is not None and (yp < 0.02 or yp > 0.98):
            filtered_low_price += 1
            continue
        price_filtered.append(m)

    # Liquidity filter: skip low-liquidity markets
    liq_filtered = []
    for m in price_filtered:
        vol = m.get('volume', 0)
        liq = m.get('liquidity', 0)
        if vol < 1000 and liq < 500:
            filtered_low_liquidity += 1
            continue
        liq_filtered.append(m)

    # Dedup by (coin, type, threshold) keeping closest expiry
    dedup_map = {}
    for m in liq_filtered:
        coin = m.get('coin', '?')
        mtype = m.get('type', '')
        thresh = m.get('threshold', '')
        key = (coin, mtype, thresh)
        if key not in dedup_map or m['hours_left'] < dedup_map[key]['hours_left']:
            dedup_map[key] = m
    deduped = list(dedup_map.values())
    filtered_dedup = len(liq_filtered) - len(deduped)

    deduped.sort(key=lambda x: x['hours_left'])

    actionable = [m for m in deduped if m['hours_left'] < ACTIONABLE_MAX]
    watchlist  = [m for m in deduped if ACTIONABLE_MAX <= m['hours_left'] < WATCHLIST_MAX]
    blocked    = [m for m in deduped if m['hours_left'] >= WATCHLIST_MAX]

    # 5. 写文件
    (data_dir / "actionable").write_text(json.dumps(actionable, indent=2, ensure_ascii=False))
    (data_dir / "watchlist").write_text(json.dumps(watchlist, indent=2, ensure_ascii=False))
    (data_dir / "blocked").write_text(json.dumps(blocked, indent=2, ensure_ascii=False))

    log_entry = {
        'ts': now.isoformat(),
        'actionable': len(actionable),
        'watchlist': len(watchlist),
        'blocked': len(blocked),
        'scan_time_s': round(time.time() - t0, 1),
        'markets': [{k: m[k] for k in ['slug','market_slug','coin','type','threshold','hours_left','yes_price','no_price'] if k in m} for m in (actionable + watchlist)],
    }
    with open(data_dir / "hunt-log.jsonl", 'a') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    elapsed = round(time.time() - t0, 1)
    print(f"  Scanned {len(all_markets)} markets → price-filtered: {filtered_low_price}, liq-filtered: {filtered_low_liquidity}, deduped: {filtered_dedup}")
    print(f"  → {len(actionable)} actionable (<{ACTIONABLE_MAX}h), {len(watchlist)} watchlist (<{WATCHLIST_MAX}h), {len(blocked)} blocked")

    if actionable:
        print("\n  ★ ACTIONABLE MARKETS:")
        for m in actionable:
            thresh_str = f" @{m['threshold']}" if m.get('threshold') else ''
            print(f"    [{m['hours_left']}h] {m['coin']} {m['type']}{thresh_str} YES:{m['yes_price']} NO:{m['no_price']} | {m['question'][:50]}")

    if watchlist:
        print(f"\n  👀 WATCHLIST ({len(watchlist)} markets):")
        for m in watchlist[:10]:
            print(f"    [{m['hours_left']}h] {m['coin']} {m['type']} YES:{m['yes_price']} | {m['question'][:50]}")
        if len(watchlist) > 10:
            print(f"    ... and {len(watchlist)-10} more")

    return 0 if actionable else 1

if __name__ == '__main__':
    sys.exit(scan_markets())
