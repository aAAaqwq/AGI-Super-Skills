#!/usr/bin/env python3
"""
Polymarket 数据抓取模块
从 Gamma API 获取市场数据、赔率、交易量等信息
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

GAMMA_API = "https://gamma-api.polymarket.com"


def fetch_markets(limit=50, active=True, closed=False, order="volumeNum", ascending=False):
    """获取市场列表"""
    params = {
        "limit": limit,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
        "order": order,
        "ascending": str(ascending).lower(),
    }
    url = f"{GAMMA_API}/markets?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "PolyProfit/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_events(limit=20, active=True, closed=False, order="volume", ascending=False):
    """获取事件列表（事件包含多个市场）"""
    params = {
        "limit": limit,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
        "order": order,
        "ascending": str(ascending).lower(),
    }
    url = f"{GAMMA_API}/events?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "PolyProfit/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def search_markets(query, limit=10):
    """搜索特定市场"""
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "q": query,
    }
    url = f"{GAMMA_API}/markets?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "PolyProfit/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def parse_market(market):
    """解析单个市场数据"""
    outcomes = json.loads(market.get("outcomes", "[]")) if isinstance(market.get("outcomes"), str) else market.get("outcomes", [])
    prices = json.loads(market.get("outcomePrices", "[]")) if isinstance(market.get("outcomePrices"), str) else market.get("outcomePrices", [])

    outcome_data = {}
    for i, outcome in enumerate(outcomes):
        price = float(prices[i]) if i < len(prices) else 0
        outcome_data[outcome] = round(price * 100, 1)

    end_date = market.get("endDate", "")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            days_left = (end_dt - datetime.now(timezone.utc)).days
        except Exception:
            days_left = None
    else:
        days_left = None

    return {
        "id": market.get("id"),
        "question": market.get("question", ""),
        "slug": market.get("slug", ""),
        "volume": market.get("volumeNum", 0),
        "outcomes": outcome_data,
        "end_date": end_date[:10] if end_date else "",
        "days_left": days_left,
        "active": market.get("active", False),
        "closed": market.get("closed", False),
        "url": f"https://polymarket.com/event/{market.get('slug', '')}",
    }


def get_top_markets(limit=30):
    """获取热门活跃市场"""
    raw = fetch_markets(limit=limit, active=True, closed=False)
    return [parse_market(m) for m in raw if not m.get("closed")]


def get_fed_markets():
    """获取 Fed 利率相关市场"""
    results = search_markets("Fed interest rate", limit=20)
    return [parse_market(m) for m in results if not m.get("closed")]


def get_ai_markets():
    """获取 AI 相关市场"""
    results = search_markets("Claude GPT AI release", limit=20)
    return [parse_market(m) for m in results if not m.get("closed")]


def get_politics_markets():
    """获取政治相关市场"""
    results = search_markets("government shutdown Trump", limit=20)
    return [parse_market(m) for m in results if not m.get("closed")]


if __name__ == "__main__":
    print("=== Top Markets ===")
    for m in get_top_markets(10):
        print(f"  ${m['volume']:>12,.0f} | {m['end_date']} | {m['question'][:60]}")
        for outcome, pct in m['outcomes'].items():
            print(f"    {outcome}: {pct}%")
        print()

    print("\n=== Fed Markets ===")
    for m in get_fed_markets()[:5]:
        print(f"  {m['question'][:60]} | {m['outcomes']}")

    print("\n=== AI Markets ===")
    for m in get_ai_markets()[:5]:
        print(f"  {m['question'][:60]} | {m['outcomes']}")
