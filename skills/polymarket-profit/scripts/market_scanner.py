#!/usr/bin/env python3
"""Polymarket market scanner - finds profitable opportunities."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
import requests

API_URL = "https://gamma-api.polymarket.com/markets"
DATA_DIR = os.path.expanduser("~/clawd/skills/polymarket-profit/data")


def fetch_markets():
    markets = []
    offset = 0
    while True:
        r = requests.get(API_URL, params={
            "closed": "false", "limit": 100, "offset": offset,
            "order": "volume24hr", "ascending": "false"
        }, timeout=60)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        markets.extend(batch)
        print(f"  ...fetched {len(markets)} markets")
        if len(batch) < 100 or len(markets) >= 500:
            break
        offset += 100
    return markets


def score_certainty(price):
    """0-40: how close price is to 0 or 1."""
    deviation = min(price, 1 - price)  # 0 = certain, 0.5 = uncertain
    return round(40 * (1 - 2 * deviation))  # 0.5->0, 0->40


def score_timeliness(end_date_str):
    """0-20: closer expiry = higher score."""
    if not end_date_str:
        return 0
    try:
        end = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        days = (end - datetime.now(timezone.utc)).days
        if days < 0:
            return 0
        if days < 7:
            return 20
        if days < 30:
            return 15
        if days < 60:
            return 10
        return max(0, 5 - days // 60)
    except Exception:
        return 0


def score_liquidity(vol24):
    """0-20: higher volume = higher score."""
    if vol24 <= 0:
        return 0
    if vol24 >= 100000:
        return 20
    if vol24 >= 50000:
        return 17
    if vol24 >= 10000:
        return 14
    if vol24 >= 1000:
        return 10
    if vol24 >= 100:
        return 5
    return 2


def score_value(price, certainty_score):
    """0-20: return rate weighted by certainty."""
    if price <= 0 or price >= 1:
        return 0
    ret = (1 - price) / price
    raw = min(20, ret * 5)
    weight = certainty_score / 40  # higher certainty = more valuable
    return round(raw * weight)


def analyze_market(m):
    outcomes = []
    try:
        prices = json.loads(m.get("outcomePrices", "[]"))
        names = json.loads(m.get("outcomes", "[]"))
    except (json.JSONDecodeError, TypeError):
        return []

    vol24 = float(m.get("volume24hr", 0) or 0)
    end_date = m.get("endDate")
    slug = m.get("slug", "")
    question = m.get("question", "")
    liq_score = score_liquidity(vol24)
    time_score = score_timeliness(end_date)

    for i, (name, price_str) in enumerate(zip(names, prices)):
        price = float(price_str)
        if price <= 0 or price >= 1:
            continue
        cert = score_certainty(price)
        val = score_value(price, cert)
        total = cert + time_score + liq_score + val

        outcomes.append({
            "question": question,
            "outcome": name,
            "price": round(price, 4),
            "return_rate": round((1 - price) / price, 2),
            "score": total,
            "scores": {"certainty": cert, "timeliness": time_score, "liquidity": liq_score, "value": val},
            "volume24hr": vol24,
            "end_date": end_date,
            "url": f"https://polymarket.com/event/{slug}",
            "condition_id": m.get("conditionId", ""),
        })
    return outcomes


def run(args):
    print("Fetching markets from Gamma API...")
    markets = fetch_markets()
    print(f"Fetched {len(markets)} markets")

    all_outcomes = []
    for m in markets:
        all_outcomes.extend(analyze_market(m))

    # CLOB strategy: price <= 0.19
    clob = sorted([o for o in all_outcomes if o["price"] <= 0.19],
                  key=lambda x: x["score"], reverse=True)[:args.top]

    # Website strategy: any price
    website = sorted([o for o in all_outcomes if o["score"] >= args.min_score],
                     key=lambda x: x["score"], reverse=True)[:args.top]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_markets": len(markets),
        "total_outcomes": len(all_outcomes),
        "clob_strategy": {"budget": 1, "max_price": 0.19, "count": len(clob), "opportunities": clob},
        "website_strategy": {"budget": args.budget, "count": len(website), "opportunities": website},
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, "scan_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*60}")
    print(f"CLOB Strategy (budget=$1, price<=¢19) - Top {len(clob)}")
    print(f"{'='*60}")
    for i, o in enumerate(clob[:10], 1):
        print(f"{i:2}. [{o['score']:3}pts] ¢{o['price']*100:.1f} | {o['outcome']}: {o['question'][:60]}")
        print(f"    Return: {o['return_rate']}x | Vol24h: ${o['volume24hr']:,.0f} | {o['url']}")

    print(f"\n{'='*60}")
    print(f"Website Strategy (budget=${args.budget}) - Top {len(website)}")
    print(f"{'='*60}")
    for i, o in enumerate(website[:10], 1):
        print(f"{i:2}. [{o['score']:3}pts] ¢{o['price']*100:.1f} | {o['outcome']}: {o['question'][:60]}")
        print(f"    Return: {o['return_rate']}x | Vol24h: ${o['volume24hr']:,.0f} | {o['url']}")

    print(f"\nResults saved to {out_path}")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Polymarket Market Scanner")
    p.add_argument("--budget", type=float, default=6, help="Website strategy budget (default: 6)")
    p.add_argument("--min-score", type=int, default=30, help="Min score filter (default: 30)")
    p.add_argument("--top", type=int, default=20, help="Top N results (default: 20)")
    run(p.parse_args())
