#!/usr/bin/env python3
"""
5minbtc-news.py — 快速新闻抓取 for BTC 5min预测

高质量新闻源（实时性验证过的）：
  ✅ CoinDesk RSS        — ~14min 延迟
  ✅ Cointelegraph TG    — ~3min  延迟（最快！）
  ✅ TreeNews Telegram   — ~120min（依赖tree_channel编辑推送）
  ⚠️  Binance Square     — 需要API key，暂无

已移除（验证失效）：
  ❌ CoinTelegraph RSS — 144min+，天然延迟高
  ❌ NewsData.io      — 20h前数据，完全失效
  ❌ TheBlock         — SSL封锁
  ❌ BitcoinMagazine  — 连接重置
  ❌ Fear&Greed      — 连接重置
  ❌ CryptoCompare    — 需要API key
"""
import json, os, sys, subprocess, re
from datetime import datetime, timezone, timedelta

# ─── 路径配置 ───
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # workspace-cqo
DATA_DIR = os.path.join(WORKSPACE, "data")
NEWS_RISK_FILE = os.path.join(DATA_DIR, "news-risk-level.json")
NEWS_SIGNALS_FILE = os.path.join(DATA_DIR, "news-signals.jsonl")
CST = timezone(timedelta(hours=8))

# ─── API Keys (从.bashrc读取) ───
def load_env():
    """从.bashrc加载API keys"""
    env_file = os.path.expanduser("~/.bashrc")  # or use .env file
    if not os.path.exists(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export ") and "_API_KEY" in line:
                k, v = line[7:].split("=", 1)
                v = v.strip('"').strip("'")
                os.environ[k] = v

load_env()
COINDESK_KEY = os.environ.get("COINDESK_API_KEY", "")
NEWSDATA_KEY = os.environ.get("NEWSDATA_API_KEY", "")

# ─── 工具函数 ───
def fetch_url(url, headers=None, timeout=10):
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except:
        return ""

def cst_now():
    return datetime.now(CST)

def parse_rss_time(date_str, cutoff_hours=24):
    """解析RSS时间，返回CST datetime或None"""
    if not date_str:
        return None
    # RFC 822: 'Mon, 11 May 2026 20:30:00 +0000'
    try:
        dt = datetime.strptime(date_str.strip(), "%a, %d %b %Y %H:%M:%S %z")
        dt = dt.astimezone(CST)
        return dt
    except:
        pass
    # ISO 8601
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        dt = dt.astimezone(CST)
        return dt
    except:
        pass
    return None

# ─── 分类引擎 ───
def classify(headline, body="", categories=""):
    text = (headline + " " + body + " " + categories).lower()
    danger = [
        "hawkish","rate hike","higher for longer","inflation ris","war escalat",
        "military conflict","sanction","hack","exploit","flash crash","bankrupt",
        "sec charg","recession","sell-off","bloodbath","plunge","whale dump",
        "regulation crackdown","iran","conflict","missile","nuclear","attack",
        "arrest","fraud","collapse","default"
    ]
    opp = [
        "dovish","rate cut","etf approved","inflow record","institutional adopt",
        "regulatory clarity","breakout","rally","surge","partnership",
        "bitcoin etf","blackrock","clarity act","bullish","ath","new high",
        "adopted by","legal tender","approval","approve"
    ]
    caution = [
        "cpi","fed meeting","nfp","ppi","nonfarm","awaiting","uncertain",
        "volatile","consolidation","resistance","support","mixed",
        "caution","review","probe","investigation"
    ]
    d = [w for w in danger if w in text]
    o = [w for w in opp if w in text]
    c = [w for w in caution if w in text]
    if d and len(d) >= len(o):
        return "bearish", min(10, 5 + len(d))
    elif o and len(o) > len(d):
        return "bullish", min(10, 4 + len(o))
    elif c:
        return "caution", min(10, 3 + len(c))
    return "neutral", 1

def assets_from_text(text):
    text = text.lower()
    assets = []
    if any(w in text for w in ["bitcoin","btc","₿"]): assets.append("BTC")
    if any(w in text for w in ["ethereum","eth","ether"]): assets.append("ETH")
    if any(w in text for w in ["solana","sol"]): assets.append("SOL")
    if any(w in text for w in ["gold","xau"]): assets.append("GOLD")
    if any(w in text for w in ["oil","crude","cl=f"]): assets.append("OIL")
    if any(w in text for w in ["fed","inflation","macro","rate"]): assets.extend(["BTC","ETH","SOL"])
    return list(dict.fromkeys(assets)) if assets else ["CRYPTO"]

# ─── 新闻源 ───
def scan_cryptocompare():
    """CryptoCompare News API — 需要key"""
    # 检查key是否在环境变量里
    cc_key = os.environ.get("CRYPTOCOMPARE_KEY","")
    results = []
    if not cc_key:
        return results
    url = f"https://min-api.cryptocompare.com/data/v2/news/?lang=EN&limit=20&api_key={cc_key}"
    data = fetch_url(url)
    if not data:
        return results
    try:
        d = json.loads(data)
        now_ts = datetime.utcnow().timestamp()
        for a in d.get("Data", [])[:20]:
            age_min = (now_ts - a.get("published_on", now_ts)) / 60
            if age_min > 120:  # 2小时内
                continue
            sentiment_raw = a.get("sentiment", "").lower()
            sentiment = "bullish" if "bullish" in sentiment_raw else "bearish" if "bearish" in sentiment_raw else "neutral"
            categories = a.get("categories", "")
            impact = "high" if any(c in categories.upper() for c in ["BTC","ETH","MACRO"]) else "medium"
            results.append({
                "ts": datetime.utcfromtimestamp(a["published_on"]).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "source": "CryptoCompare",
                "title": a.get("title","")[:200],
                "sentiment": sentiment,
                "impact": 7 if impact == "high" else 5,
                "categories": categories
            })
    except:
        pass
    return results

def scan_coindesk():
    """CoinDesk API"""
    results = []
    if not COINDESK_KEY:
        # Fallback to RSS
        return scan_coindesk_rss()
    url = f"https://gateway.coindesk.com/v1/content/rss?apiKey={COINDESK_KEY}"
    data = fetch_url(url)
    if not data:
        return scan_coindesk_rss()
    try:
        d = json.loads(data)
        now = cst_now()
        cutoff = now - timedelta(hours=24)
        for item in d.get("data", [])[:30]:
            try:
                dt = datetime.fromtimestamp(item.get("published_on", 0), tz=CST)
            except:
                dt = now
            if dt < cutoff:
                continue
            sentiment, impact = classify(item.get("title",""), item.get("body",""))
            results.append({
                "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "source": "CoinDesk",
                "title": item.get("title","")[:200],
                "sentiment": sentiment,
                "impact": impact,
                "categories": ""
            })
    except:
        return scan_coindesk_rss()
    return results

def scan_coindesk_rss():
    """CoinDesk RSS fallback"""
    results = []
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    data = fetch_url(url)
    if not data:
        return results
    now = cst_now()
    cutoff = now - timedelta(hours=24)
    items = re.findall(r"<item>(.*?)</item>", data, re.DOTALL)
    for item in items[:30]:
        title_m = re.search(r"<title><!\[CDATA\[([^\]]+)\]\]></title>", item)
        date_m = re.search(r"<pubDate>([^<]+)</pubDate>", item)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        dt = parse_rss_time(date_m.group(1) if date_m else "")
        if not dt or dt < cutoff:
            continue
        sentiment, impact = classify(title)
        results.append({
            "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "CoinDesk",
            "title": title[:200],
            "sentiment": sentiment,
            "impact": impact,
            "categories": ""
        })
    return results

def scan_cointelegraph():
    """CoinTelegraph RSS"""
    results = []
    url = "https://cointelegraph.com/rss"
    data = fetch_url(url)
    if not data:
        return results
    now = cst_now()
    cutoff = now - timedelta(hours=24)
    items = re.findall(r"<item>(.*?)</item>", data, re.DOTALL)
    for item in items[:20]:
        title_m = re.search(r"<title><!\[CDATA\[([^\]]+)\]\]></title>", item)
        if not title_m:
            title_m = re.search(r"<title>([^<]+)</title>", item)
        date_m = re.search(r"<pubDate>([^<]+)</pubDate>", item)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        dt = parse_rss_time(date_m.group(1) if date_m else "")
        if not dt or dt < cutoff:
            continue
        sentiment, impact = classify(title)
        results.append({
            "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "CoinTelegraph",
            "title": title[:200],
            "sentiment": sentiment,
            "impact": impact,
            "categories": ""
        })
    return results

def scan_theblock():
    """TheBlock RSS"""
    results = []
    url = "https://api.theblock.io/rss/news"
    data = fetch_url(url)
    if not data:
        return results
    now = cst_now()
    cutoff = now - timedelta(hours=24)
    items = re.findall(r"<item>(.*?)</item>", data, re.DOTALL)
    for item in items[:15]:
        title_m = re.search(r"<title>([^<]+)</title>", item)
        date_m = re.search(r"<pubDate>([^<]+)</pubDate>", item)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        dt = parse_rss_time(date_m.group(1) if date_m else "")
        if not dt or dt < cutoff:
            continue
        sentiment, impact = classify(title)
        results.append({
            "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "TheBlock",
            "title": title[:200],
            "sentiment": sentiment,
            "impact": impact,
            "categories": ""
        })
    return results

def scan_bitcoinmagazine():
    """Bitcoin Magazine RSS"""
    results = []
    url = "https://bitcoinmagazine.com/rss"
    data = fetch_url(url)
    if not data:
        return results
    now = cst_now()
    cutoff = now - timedelta(hours=24)
    items = re.findall(r"<entry>(.*?)</entry>", data, re.DOTALL)
    for item in items[:15]:
        title_m = re.search(r"<title>([^<]+)</title>", item)
        date_m = re.search(r"<published>([^<]+)</published>", item)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        dt = parse_rss_time(date_m.group(1) if date_m else "")
        if not dt or dt < cutoff:
            continue
        sentiment, impact = classify(title)
        results.append({
            "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "BitcoinMagazine",
            "title": title[:200],
            "sentiment": sentiment,
            "impact": impact,
            "categories": ""
        })
    return results

def scan_binance():
    """Binance Blog RSS"""
    results = []
    url = "https://www.binance.com/en/blog/rss"
    data = fetch_url(url)
    if not data:
        return results
    now = cst_now()
    cutoff = now - timedelta(hours=24)
    items = re.findall(r"<item>(.*?)</item>", data, re.DOTALL)
    for item in items[:10]:
        title_m = re.search(r"<title><!\[CDATA\[([^\]]+)\]\]></title>", item)
        date_m = re.search(r"<pubDate>([^<]+)</pubDate>", item)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        dt = parse_rss_time(date_m.group(1) if date_m else "")
        if not dt or dt < cutoff:
            continue
        sentiment, impact = classify(title)
        results.append({
            "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "Binance",
            "title": title[:200],
            "sentiment": sentiment,
            "impact": impact,
            "categories": ""
        })
    return results

def scan_fear_and_greed():
    """Fear & Greed Index"""
    results = []
    url = "https://alternative.me/crypto/fear-and-greed-index/"
    data = fetch_url(url)
    if not data:
        return results
    # 找最新的FGI值
    val_m = re.search(r'class="fgi-number">(\d+)</span>', data)
    label_m = re.search(r'class="fgi-label">([^<]+)</p>', data)
    if val_m and label_m:
        val = int(val_m.group(1))
        label = label_m.group(1).strip().lower()
        sentiment = "bearish" if val < 40 else "bullish" if val > 65 else "neutral"
        results.append({
            "ts": cst_now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "Fear&Greed",
            "title": f"Fear & Greed Index: {val} ({label})",
            "sentiment": sentiment,
            "impact": 5,
            "categories": "SENTIMENT"
        })
    return results

def scan_newsdata():
    """NewsData.io API — 最近24h BTC相关"""
    results = []
    if not NEWSDATA_KEY:
        return results
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_KEY}&q=bitcoin&language=en&category=business"
    data = fetch_url(url)
    if not data:
        return results
    try:
        d = json.loads(data)
        now = cst_now()
        cutoff = now - timedelta(hours=24)
        for item in d.get("results", [])[:20]:
            pub = item.get("pubDate", "")
            try:
                dt = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
            except:
                dt = now
            if dt < cutoff:
                continue
            title = item.get("title", "")
            sentiment, impact = classify(title, item.get("description", ""))
            results.append({
                "ts": dt.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "source": "NewsData",
                "title": title[:200],
                "sentiment": sentiment,
                "impact": impact,
                "categories": ""
            })
    except:
        pass
    return results

def scan_treenews():
    """TreeNews Telegram群消息 — 通过 telegram-treenews.py 脚本获取"""
    results = []
    script_path = os.path.join(WORKSPACE, "scripts", "telegram-treenews.py")
    if not os.path.exists(script_path):
        return results
    try:
        result = subprocess.run(
            [sys.executable, script_path, "30"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PYTHONPATH": "<python-path>"}
        )
        if result.returncode != 0 or not result.stdout.strip():
            return results
        articles = json.loads(result.stdout)
        for a in articles:
            sentiment, impact = classify(a.get("title", ""), a.get("full_text", ""))
            results.append({
                "ts": a.get("ts", cst_now().strftime("%Y-%m-%dT%H:%M:%S+08:00")),
                "source": "TreeNews",
                "title": a.get("title", "")[:200],
                "sentiment": sentiment,
                "impact": impact,
                "categories": ""
            })
    except Exception as e:
        print(f"TreeNews fetch error: {e}", file=sys.stderr)
    return results

# ─── 主扫描 ───
def scan_cointelegraph_tg():
    """Cointelegraph Telegram频道 — ~3min延迟，最快的加密新闻源"""
    results = []
    script_path = os.path.join(WORKSPACE, "scripts", "telegram-cointelegraph.py")
    if not os.path.exists(script_path):
        return results
    try:
        result = subprocess.run(
            [sys.executable, script_path, "15"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 or not result.stdout.strip():
            return results
        articles = json.loads(result.stdout)
        for a in articles:
            sentiment, impact = classify(a.get("title", ""), a.get("full_text", ""))
            results.append({
                "ts": a.get("ts", cst_now().strftime("%Y-%m-%dT%H:%M:%S+08:00")),
                "source": "Cointelegraph",
                "title": a.get("title", "")[:200],
                "sentiment": sentiment,
                "impact": impact,
                "categories": ""
            })
    except Exception as e:
        print(f"Cointelegraph TG error: {e}", file=sys.stderr)
    return results

def scan_all():
    sources = [
        ("CoinDesk", scan_coindesk),
        ("Cointelegraph", scan_cointelegraph_tg),
        ("TreeNews", scan_treenews),
    ]
    all_articles = []
    source_stats = {}
    for name, fn in sources:
        try:
            arts = fn()
            source_stats[name] = len(arts)
            all_articles.extend(arts)
        except Exception as e:
            source_stats[name] = f"error: {e}"
    # 去重（按title前100字符）
    seen = set()
    unique = []
    for a in all_articles:
        key = a["title"][:100]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    # 按时间排序
    unique.sort(key=lambda x: x["ts"], reverse=True)
    return unique, source_stats

# ─── 更新风险文件 ───
def update_risk(articles, max_age_minutes=30):
    """计算风险等级，只计入 max_age_minutes 内的新文章"""
    now = cst_now()
    
    # 过滤：只保留 max_age_minutes 内的新文章
    fresh = []
    stale = []
    for a in articles:
        try:
            dt = datetime.strptime(a["ts"], "%Y-%m-%dT%H:%M:%S+08:00")
            dt = dt.replace(tzinfo=CST)  # 补上时区信息
            age_min = (now - dt).total_seconds() / 60
            a["_age_min"] = age_min
            if age_min <= max_age_minutes:
                fresh.append(a)
            else:
                stale.append(a)
        except Exception as e:
            stale.append(a)
    
    # 只用新鲜文章计算情绪
    bullish = [a for a in fresh if a["sentiment"] == "bullish"]
    bearish = [a for a in fresh if a["sentiment"] == "bearish"]
    high_impact = [a for a in fresh if a["impact"] >= 6]
    nb, nl = len(bearish), len(bullish)
    
    # 情绪判断规则
    if nb >= 2 and nb > nl:
        risk_level, sentiment = "HIGH_VOL", "BEARISH"
    elif nl >= 2 and nl > nb:
        risk_level, sentiment = "LOW_RISK", "BULLISH"
    elif nb >= 2 and nl >= 2:
        risk_level, sentiment = "ELEVATED", "NEUTRAL"
    elif nb == 1:
        risk_level, sentiment = "ELEVATED", "NEUTRAL"
    else:
        risk_level, sentiment = "NORMAL", "NEUTRAL"
    
    risk_data = {
        "risk_level": risk_level,
        "sentiment": sentiment,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "article_count": len(fresh),        # 只统计30min内
        "total_count": len(articles),       # 全部文章
        "high_impact_count": len(high_impact),
        "max_age_minutes": max_age_minutes,
        "stale_count": len(stale),
        "newest_article_age_min": fresh[0]["_age_min"] if fresh else None
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NEWS_RISK_FILE, "w") as f:
        json.dump(risk_data, f, indent=2)
    # 追加signals（只追加新鲜的）
    with open(NEWS_SIGNALS_FILE, "w") as f:  # 覆盖，不累积
        for a in articles:
            f.write(json.dumps(a) + "\n")
    return risk_data

# ─── CLI ───
if __name__ == "__main__":
    print(f"📰 5minbtc News Scanner — {cst_now().strftime('%H:%M:%S')}")
    print("-" * 40)
    articles, stats = scan_all()
    for src, cnt in stats.items():
        emoji = "✅" if isinstance(cnt, int) and cnt > 0 else "❌"
        print(f"  {emoji} {src}: {cnt}")
    print("-" * 40)
    risk = update_risk(articles)
    age_info = f"{risk['newest_article_age_min']:.0f}min前" if risk['newest_article_age_min'] is not None else "无文章"
    print(f"📊 Sentiment: {risk['sentiment']} | Risk: {risk['risk_level']}")
    print(f"📝 Fresh({risk['max_age_minutes']}min内): {risk['article_count']} | 🟢{risk['bullish_count']} | 🔴{risk['bearish_count']} | 最新:{age_info}")
    if risk['stale_count'] > 0:
        print(f"   ⚠️  另有 {risk['stale_count']} 篇超过{risk['max_age_minutes']}min（不计入情绪）")
    # 显示最新3条
    for a in articles[:3]:
        print(f"  • [{a['source']}] {a['title'][:80]}")
