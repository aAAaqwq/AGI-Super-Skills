#!/usr/bin/env python3
"""
Polymarket 赔率历史追踪
记录赔率变化，支持动量策略和回测
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path("/home/aa/clawd/skills/polymarket-profit/data")
ODDS_DIR = DATA_DIR / "odds"


def record_snapshot(markets):
    """记录当前市场赔率快照"""
    ODDS_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    snapshot_file = ODDS_DIR / f"{date_str}.jsonl"
    
    records = []
    for m in markets:
        records.append({
            "ts": now.isoformat(),
            "time": time_str,
            "id": m.get("id"),
            "question": m.get("question", "")[:80],
            "outcomes": m.get("outcomes", {}),
            "volume": m.get("volume", 0),
            "days_left": m.get("days_left"),
        })
    
    with open(snapshot_file, "a") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    return len(records)


def load_history(market_id, days=7):
    """加载某个市场的历史赔率"""
    from datetime import timedelta
    
    history = []
    now = datetime.now(timezone.utc)
    
    for i in range(days):
        date = now - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        snapshot_file = ODDS_DIR / f"{date_str}.jsonl"
        
        if snapshot_file.exists():
            with open(snapshot_file) as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if record.get("id") == market_id:
                            history.append(record)
                    except json.JSONDecodeError:
                        continue
    
    history.sort(key=lambda x: x.get("ts", ""))
    return history


def detect_momentum(market_id, days=3):
    """检测赔率动量（趋势方向和强度）"""
    history = load_history(market_id, days=days)
    
    if len(history) < 2:
        return {"trend": "unknown", "strength": 0, "data_points": len(history)}
    
    # 取 Yes 概率的变化
    yes_prices = []
    for h in history:
        outcomes = h.get("outcomes", {})
        yes_pct = outcomes.get("Yes", outcomes.get("yes", None))
        if yes_pct is not None:
            yes_prices.append({"ts": h["ts"], "pct": y})
    
    if len(yes_prices) < 2:
        return {"trend": "unknown", "strength": 0}
    
    # 计算趋势
    first = yes_prices[0]["pct"]
    last = yes_prices[-1]["pct"]
    change = last - first
    
    # 计算波动率
    changes = [yes_prices[i]["pct"] - yes_prices[i-1]["pct"] for i in range(1, len(yes_prices))]
    avg_change = sum(changes) / len(changes) if changes else 0
    
    if change > 5:
        trend = "strong_up"
    elif change > 2:
        trend = "up"
    elif change < -5:
        trend = "strong_down"
    elif change < -2:
        trend = "down"
    else:
        trend = "sideways"
    
    return {
        "trend": trend,
        "total_change": round(change, 1),
        "avg_change_per_snapshot": round(avg_change, 2),
        "data_points": len(yes_prices),
        "first_pct": first,
        "last_pct": last,
    }


def find_momentum_opportunities(markets, days=3, min_change=5):
    """找到有明显动量的市场"""
    opportunities = []
    
    for m in markets:
        market_id = m.get("id")
        if not market_id:
            continue
        
        momentum = detect_momentum(market_id, days=days)
        
        if abs(momentum.get("total_change", 0)) >= min_change:
            opportunities.append({
                "market": m.get("question", ""),
                "id": market_id,
                "slug": m.get("slug", ""),
                "momentum": momentum,
                "current_outcomes": m.get("outcomes", {}),
                "volume": m.get("volume", 0),
                "days_left": m.get("days_left"),
            })
    
    opportunities.sort(key=lambda x: abs(x["momentum"]["total_change"]), reverse=True)
    return opportunities


if __name__ == "__main__":
    from fetcher import get_top_markets
    
    print("📸 记录赔率快照...")
    markets = get_top_markets(limit=50)
    count = record_snapshot(markets)
    print(f"  已记录 {count} 个市场的赔率")
    
    print("\n📈 检测动量信号...")
    opps = find_momentum_opportunities(markets)
    if opps:
        for o in opps[:5]:
            m = o["momentum"]
            print(f"  {o['market'][:50]}")
            print(f"    趋势: {m['trend']} | 变化: {m['total_change']:+.1f}% | 当前: {o['current_outcomes']}")
    else:
        print("  暂无明显动量信号（需要积累更多历史数据）")
