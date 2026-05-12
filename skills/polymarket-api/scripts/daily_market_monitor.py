#!/usr/bin/env python3
"""
Polymarket 每日盘口监控
- 每日 08:00 CST 检查新上架的 BTC/ETH 日盘
- 评估概率是否在 90-97% 范围
- 有符合条件的立即推送信号
"""
import urllib.request
import json
import os
from datetime import datetime, timezone, timedelta

# 清除 proxy 变量（SSL EOF 问题）
for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = "YOUR_TELEGRAM_CHAT_ID"

def fetch(url, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Fetch error: {e}")
        return None

def telegram(msg):
    if not TELEGRAM_TOKEN:
        print(msg)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except:
        pass

def main():
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    print(f"[{now_cst.strftime('%H:%M')}] Polymarket 日盘监控...")

    data = fetch("https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=50")
    if not data:
        telegram("⚠️ Polymarket API 连接失败")
        return

    results = []
    for m in data:
        q = m.get("question", "").lower()
        bid = float(m.get("bestBid") or 0)
        slug = m.get("slug", "")
        end_str = m.get("endDate", "")[:10]
        vol = int(float(m.get("volume24hr", 0) or 0))

        # 关键词过滤
        crypto_kw = ["bitcoin", "btc", "eth", "ether", "sol", "crypto"]
        is_crypto = any(k in q for k in crypto_kw)

        # 结算日期过滤（今天或明天的日盘）
        try:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_out = (end_dt - datetime.now(timezone.utc)).days
            is_daily = days_out in [0, 1]
        except:
            is_daily = False

        if is_crypto and is_daily and bid > 0:
            prob = bid * 100
            results.append({
                "prob": prob,
                "bid": bid,
                "q": m.get("question", ""),
                "slug": slug,
                "end": end_str,
                "vol": vol,
                "days": days_out
            })

    if not results:
        msg = f"📊 Polymarket 日监控 [{now_cst.strftime('%H:%M')}]\n"
        msg += "⚠️ 今日无BTC/ETH日盘上架\n"
        msg += f"活跃市场共{len(data)}个，但无加密短期盘\n"
        msg += "→ 每小时继续监控"
        print(msg)
        telegram(msg)
        return

    results.sort(key=lambda x: -x["prob"])
    msg = f"📊 Polymarket 日监控 [{now_cst.strftime('%H:%M')}]\n"
    msg += f"发现 {len(results)} 个加密日盘：\n\n"
    for r in results:
        status = "🟢 可交易" if 90 <= r["prob"] <= 97 else "🟡 观察"
        side = "YES" if r["prob"] >= 50 else "NO"
        msg += f"{status} {side}={r['prob']:.1f}%\n"
        msg += f"  竞价={r['bid']:.3f} | 结算={r['end']} | vol={r['vol']:,}\n"
        msg += f"  {r['q'][:60]}\n"
        if 90 <= r["prob"] <= 97:
            size = min(5, 19.64 * 0.25)  # 最多$5或25%现金
            msg += f"  ⚡ 建议: ${size:.0f} {side}\n"
        msg += "\n"

    print(msg)
    telegram(msg)

if __name__ == "__main__":
    main()
