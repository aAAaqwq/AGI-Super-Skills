#!/usr/bin/env python3
"""
5minbtc-news.py -- BTC 5min prediction news scanner

当前在用源 (scan_all):
  scan_coindesk (RSS fallback) -- ~14min 延迟 (唯一稳定源)

已移除源 (验证失效, 2026-07-05 清理):
  - Cointelegraph RSS/TG  -- 0 results
  - TreeNews TG            -- scripts/telegram-treenews.py 不存在
  - TheBlock RSS           -- SSL 封锁
  - BitcoinMagazine RSS    -- 连接重置
  - NewsData.io API        -- 无 API key
  - CryptoCompare API      -- 无 API key
  - Binance Blog RSS       -- 未在 scan_all 调用
  - alternative.me FGI     -- 引擎 _fetch_fng() 已独立获取, 此处冗余
"""
import json, os, re
from datetime import datetime, timezone, timedelta

# ─── 路径配置 ───
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SKILL_DIR, "data")
NEWS_RISK_FILE = os.path.join(DATA_DIR, "news-risk-level.json")
NEWS_SIGNALS_FILE = os.path.join(DATA_DIR, "news-signals.jsonl")
CST = timezone(timedelta(hours=8))

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

def parse_rss_time(date_str):
    """解析 RSS 时间，返回 CST datetime 或 None"""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.astimezone(CST)
    except:
        pass
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(CST)
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

# ─── 新闻源 ───
def scan_coindesk_rss():
    """CoinDesk RSS -- 唯一在用源, ~14min 延迟"""
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

def scan_coindesk():
    """CoinDesk -- 当前直接走 RSS (无 API key)"""
    return scan_coindesk_rss()

# ─── 主扫描 ───
def scan_all():
    sources = [
        ("CoinDesk", scan_coindesk),
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
    # 去重
    seen = set()
    unique = []
    for a in all_articles:
        key = a["title"][:100]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    unique.sort(key=lambda x: x["ts"], reverse=True)
    return unique, source_stats

# ─── 更新风险文件 ───
def update_risk(articles, max_age_minutes=30):
    """计算风险等级，只计入 max_age_minutes 内的新文章"""
    now = cst_now()
    fresh = []
    stale = []
    for a in articles:
        try:
            dt = datetime.strptime(a["ts"], "%Y-%m-%dT%H:%M:%S+08:00")
            dt = dt.replace(tzinfo=CST)
            age_min = (now - dt).total_seconds() / 60
            a["_age_min"] = age_min
            if age_min <= max_age_minutes:
                fresh.append(a)
            else:
                stale.append(a)
        except Exception:
            stale.append(a)
    bullish = [a for a in fresh if a["sentiment"] == "bullish"]
    bearish = [a for a in fresh if a["sentiment"] == "bearish"]
    high_impact = [a for a in fresh if a["impact"] >= 6]
    nb, nl = len(bearish), len(bullish)
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
        "article_count": len(fresh),
        "total_count": len(articles),
        "high_impact_count": len(high_impact),
        "max_age_minutes": max_age_minutes,
        "stale_count": len(stale),
        "newest_article_age_min": fresh[0]["_age_min"] if fresh else None
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NEWS_RISK_FILE, "w") as f:
        json.dump(risk_data, f, indent=2)
    with open(NEWS_SIGNALS_FILE, "w") as f:
        for a in articles:
            f.write(json.dumps(a) + "\n")
    return risk_data

# ─── CLI ───
if __name__ == "__main__":
    print(f"5minbtc News Scanner -- {cst_now().strftime('%H:%M:%S')}")
    print("-" * 40)
    articles, stats = scan_all()
    for src, cnt in stats.items():
        mark = "OK" if isinstance(cnt, int) and cnt > 0 else "FAIL"
        print(f"  [{mark}] {src}: {cnt}")
    print("-" * 40)
    risk = update_risk(articles)
    age_info = f"{risk['newest_article_age_min']:.0f}min ago" if risk['newest_article_age_min'] is not None else "no articles"
    print(f"Sentiment: {risk['sentiment']} | Risk: {risk['risk_level']}")
    print(f"Fresh({risk['max_age_minutes']}min): {risk['article_count']} | bull={risk['bullish_count']} | bear={risk['bearish_count']} | newest: {age_info}")
    if risk['stale_count'] > 0:
        print(f"  Note: {risk['stale_count']} articles older than {risk['max_age_minutes']}min (excluded from sentiment)")
    for a in articles[:3]:
        print(f"  - [{a['source']}] {a['title'][:80]}")
