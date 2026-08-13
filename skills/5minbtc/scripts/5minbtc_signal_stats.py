#!/usr/bin/env python3
"""重大信号模拟单 — 结算 + 按时间分类回测.

读 paper 台账的 auto 单 (realtime 重大信号自动记录):
1. 结算已收盘的 open 单 (拉真实 K线收盘价, 判定方向对错)
2. 按时间分类统计胜率/PnL (日期 / 小时)
3. 可选推送到 Telegram

用法:
  python3 5minbtc_signal_stats.py            # 结算 + 统计
  python3 5minbtc_signal_stats.py --push     # 推送 Telegram
  python3 5minbtc_signal_stats.py --by-hour  # 按小时分桶
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

PAPER = Path.home() / "bb-auto" / "5minbtc-paper.json"
PUSH = Path(__file__).resolve().parent / "telegram_push.py"
PY = "/usr/bin/python3"
CST = timezone(timedelta(hours=8))
KLINE_URL = "https://data-api.binance.vision/api/v3/klines"


def fetch_close(candle_iso):
    """拉该 5min K线的 open/close. 返回 (open, close) 或 None."""
    try:
        dt = datetime.fromisoformat(candle_iso)
        start_ms = int(dt.timestamp() * 1000)
        url = f"{KLINE_URL}?symbol=BTCUSDT&interval=5m&startTime={start_ms}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "signal-stats/1"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if data:
            return float(data[0][1]), float(data[0][4])
    except Exception:
        pass
    return None


def settle_bets(state):
    """结算已收盘的 open 单 (pending 单由 realtime check_pending 处理). 返回本次结算数."""
    now_ms = int(datetime.now(CST).timestamp() * 1000)
    settled = 0
    for b in state.get("bets", []):
        if b.get("status") != "open":
            continue
        try:
            dt = datetime.fromisoformat(b["candle"])
            close_ms = int(dt.timestamp() * 1000) + 5 * 60 * 1000
        except Exception:
            continue
        if now_ms < close_ms:
            continue
        ohlc = fetch_close(b["candle"])
        if ohlc is None:
            continue
        o, c = ohlc
        side = b["side"]
        won = (side == "UP" and c > o) or (side == "DOWN" and c < o)
        b["status"] = "settled"
        b["outcome"] = "win" if won else "loss"
        b["actual_open"] = o
        b["actual_close"] = c
        b["direction_correct"] = won
        b["pnl"] = round((b.get("amount", 1) * (1 - b["ask"]) - b.get("amount", 1) * b.get("fee", 0.01))
                          if won else (-b.get("amount", 1) * b["ask"] - b.get("amount", 1) * b.get("fee", 0.01)), 4)
        settled += 1
    return settled


def load_state():
    if PAPER.exists():
        try:
            return json.loads(PAPER.read_text())
        except Exception:
            pass
    return {"bets": []}


def save_state(state):
    PAPER.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def fmt_report(state, by_hour=False):
    auto = [b for b in state.get("bets", []) if b.get("auto")]
    settled = [b for b in auto if b.get("status") == "settled"]
    pending = [b for b in auto if b.get("status") == "pending"]
    unfilled = [b for b in auto if b.get("status") == "unfilled"]
    open_ = [b for b in auto if b.get("status") == "open"]
    lines = ["📊 重大信号回测 | " + ("按小时" if by_hour else "按日期")]
    lines.append("━" * 26)
    lines.append(f"信号 {len(auto)} | 已结算 {len(settled)} | 挂单 {len(pending)} | "
                 f"未成交 {len(unfilled)} | 持仓 {len(open_)}")

    # 下单统计
    if settled:
        wins = sum(1 for b in settled if b.get("direction_correct"))
        pnl = sum(b.get("pnl", 0) for b in settled)
        avg_ask = sum(b.get("ask", 0) for b in settled) / len(settled)
        lines.append(f"✅下单: 胜率 {wins}/{len(settled)} = {wins/len(settled)*100:.0f}% | "
                     f"PnL ${pnl:+.2f} | 均ask {avg_ask:.2f}")

    if not settled:
        lines.append("暂无已结算信号")
        return "\n".join(lines)

    # 按时间分类 (仅下单)
    key_fn = (lambda b: b["candle"][11:13] + ":00") if by_hour else (lambda b: b["candle"][:10])
    groups = defaultdict(list)
    for b in settled:
        groups[key_fn(b)].append(b)
    if groups:
        lines.append("━" * 26)
        for k in sorted(groups):
            g = groups[k]
            w = sum(1 for b in g if b.get("direction_correct"))
            p = sum(b.get("pnl", 0) for b in g)
            avg_ask = sum(b.get("ask", 0) for b in g) / len(g)
            lines.append(f"{k}: {len(g)}笔 胜率{w/len(g)*100:.0f}% PnL${p:+.2f} 均ask{avg_ask:.2f}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="重大信号回测(结算+按时间分类)")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--by-hour", action="store_true")
    args = ap.parse_args()

    state = load_state()
    settled = settle_bets(state)
    save_state(state)
    if settled:
        print(f"本次结算 {settled} 笔")

    report = fmt_report(state, by_hour=args.by_hour)
    print(report)
    if args.push:
        subprocess.run([PY, str(PUSH), report], capture_output=True, timeout=20)


if __name__ == "__main__":
    main()
