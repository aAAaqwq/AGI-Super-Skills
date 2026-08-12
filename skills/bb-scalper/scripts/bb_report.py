#!/usr/bin/env python3
"""bb-scalper 模拟盘 6h 报告 → Telegram (可移植版, 放在本 skill scripts/ 内)

读取 paper.py 持续写入的模拟平仓记录 (默认 ~/bb-auto/paper_trades.json,
可用环境变量 BB_PAPER_TRADES 覆盖), 生成汇总 (胜率/PnL/分币种/最近几笔/实时价格)
并通过 scripts/telegram_push.py 推送。

用法:
  python3 scripts/bb_report.py
  BB_PAPER_TRADES=/path/to/paper_trades.json python3 scripts/bb_report.py
"""
import json
import os
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL = SCRIPT_DIR.parent
TRADES = os.environ.get("BB_PAPER_TRADES", os.path.expanduser("~/bb-auto/paper_trades.json"))
PUSH = SCRIPT_DIR / "telegram_push.py"
SYMBOLS = ["SOLUSDT", "BTCUSDT", "XRPUSDT", "NEARUSDT", "DOTUSDT"]
CAPITAL = 500.0


def fetch_price(symbol):
    try:
        url = f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
        req = urllib.request.Request(url, headers={"User-Agent": "bb-scalper/1"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return float(json.loads(r.read())["price"])
    except Exception:
        return None


def push(msg):
    try:
        subprocess.run(["/usr/bin/python3", str(PUSH), msg], timeout=20,
                       capture_output=True)
    except Exception:
        pass


def main():
    trades = []
    if os.path.exists(TRADES):
        try:
            with open(TRADES) as f:
                trades = json.load(f)
        except Exception:
            trades = []

    by_sym = defaultdict(list)
    capital = CAPITAL
    for t in trades:
        notional = t.get("notional", 100)
        capital += notional * t.get("pnl_pct", 0) / 100
        by_sym[t.get("symbol")].append(t)

    total = len(trades)
    tp = sum(1 for t in trades if t.get("result") == "TP")
    sl = sum(1 for t in trades if t.get("result") == "SL")
    wins = [t for t in trades if t.get("result") == "TP"]
    total_pnl = sum(t.get("pnl_pct", 0) for t in trades)
    win_rate = tp / total * 100 if total else 0.0
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0.0

    lines = []
    lines.append(f"📊 BB 模拟盘 6h 报告  {datetime.now(timezone.utc).strftime('%m-%d %H:%M')} UTC")
    lines.append("━" * 24)
    lines.append(f"标的: SOL/BTC/XRP/NEAR/DOT | 本金 ${CAPITAL:.0f} | 10x")
    if total:
        lines.append(f"已平仓 {total} 笔 | TP {tp} / SL {sl} | 胜率 {win_rate:.1f}%")
        lines.append(f"累计 PnL {total_pnl:+.2f}% | 模拟资金 ${capital:.2f} | 均盈 {avg_win:+.2f}%")
    else:
        lines.append("暂无平仓记录")
    lines.append("━" * 24)
    for s in SYMBOLS:
        st = by_sym.get(s, [])
        px = fetch_price(s)
        px_s = f"${px:,.2f}" if px else "—"
        if st:
            s_tp = sum(1 for t in st if t.get("result") == "TP")
            s_pnl = sum(t.get("pnl_pct", 0) for t in st)
            lines.append(f"{s.replace('USDT','')}: {len(st)}笔 {s_pnl:+.1f}% (TP{s_tp}/SL{len(st)-s_tp}) 现价{px_s}")
        else:
            lines.append(f"{s.replace('USDT','')}: 无信号 现价{px_s}")
    recent = sorted(trades, key=lambda t: t.get("closed_ts", ""), reverse=True)[:3]
    if recent:
        lines.append("━" * 24)
        lines.append("最近平仓:")
        for t in recent:
            d = t.get("dir", "?"); r = t.get("result", "?")
            lines.append(f"  {t.get('symbol','?').replace('USDT','')} {d:5s} {r:4s} "
                         f"入{t.get('entry',0):.4f}→出{t.get('exit',0):.4f} "
                         f"PnL {t.get('pnl_pct',0):+.2f}%")
    lines.append("━" * 24)
    lines.append("下期报告 6h 后 | 实时模拟, 非投资建议")

    push("\n".join(lines))


if __name__ == "__main__":
    main()
