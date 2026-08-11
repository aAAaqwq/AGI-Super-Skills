#!/usr/bin/env python3
"""
cli/trade_log.py — 交易记录与统计

用法:
  python cli/trade_log.py --list                     # 列出所有交易
  python cli/trade_log.py --summary                  # 统计摘要
  python cli/trade_log.py --export-csv trades.csv    # 导出 CSV
  python cli/trade_log.py --today                    # 今日交易
  python cli/trade_log.py --symbol NEARUSDT          # 按币种筛选

数据格式 (trades.json):
  [
    {
      "time": "2026-08-11T05:30:00Z",
      "symbol": "NEARUSDT",
      "direction": "LONG",
      "entry": 1.592,
      "exit": 1.610,
      "result": "TP",
      "pnl_pct": 11.3,
      "pnl_usd": 11.3,
      "leverage": 10,
      "notes": ""
    }
  ]

TODO:
  - [ ] Supabase 云端存储（替代本地 JSON）
  - [ ] 实时盈亏计算（根据当前价格更新 OPEN 状态订单）
  - [ ] 批量导入/导出
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import get_logger

logger = get_logger("trade_log")

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "trades.json")


def load_trades(path: str = DEFAULT_DB) -> list:
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("加载交易记录失败 %s: %s", path, e)
            return []
    return []


def save_trades(trades: list, path: str = DEFAULT_DB):
    try:
        with open(path, "w") as f:
            json.dump(trades, f, indent=2, default=str)
    except OSError as e:
        logger.error("保存交易记录失败 %s: %s", path, e)


def log_trade(symbol: str, direction: str, entry: float, exit_price: float,
              result: str, pnl_pct: float, leverage: int = 10,
              notes: str = "", path: str = DEFAULT_DB) -> dict:
    """记录一笔已完成交易"""
    trades = load_trades(path)
    trade = {
        "time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "exit": exit_price,
        "result": result,  # TP / SL / MANUAL
        "pnl_pct": round(pnl_pct, 4),
        "pnl_usd": round(pnl_pct / 100 * entry, 2),
        "leverage": leverage,
        "notes": notes,
    }
    trades.append(trade)
    save_trades(trades, path)
    logger.info(
        "新交易 %s %s 入场=%.4f 出场=%.4f 结果=%s PnL=%+.2f%% (%.2f USD)",
        symbol, direction, entry, exit_price, result, pnl_pct, trade["pnl_usd"],
    )
    return trade


def compute_summary(trades: list) -> dict:
    """计算交易统计摘要"""
    closed = [t for t in trades if t.get("result") != "OPEN"]
    if not closed:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_win_pct": 0,
            "avg_loss_pct": 0,
            "total_pnl_pct": 0,
            "total_pnl_usd": 0,
            "expectancy": 0,
        }

    wins = [t for t in closed if t["result"] == "TP"]
    losses = [t for t in closed if t["result"] == "SL"]
    total = len(closed)
    wr = len(wins) / total * 100 if total > 0 else 0
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    total_pnl = sum(t["pnl_pct"] for t in closed)
    total_usd = sum(t.get("pnl_usd", 0) for t in closed)

    # 期望值 = WR * avg_win + (1-WR) * avg_loss
    ev = (wr / 100 * avg_win + (1 - wr / 100) * avg_loss) if total > 0 else 0

    return {
        "total": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(wr, 1),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "total_pnl_pct": round(total_pnl, 2),
        "total_pnl_usd": round(total_usd, 2),
        "expectancy": round(ev, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="BB套利 - 交易记录")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--today", action="store_true")
    parser.add_argument("--symbol")
    parser.add_argument("--export-csv")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    trades = load_trades(args.db)

    if args.symbol:
        trades = [t for t in trades if t.get("symbol") == args.symbol]

    if args.today:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        trades = [t for t in trades if t.get("time","").startswith(today)]

    if args.summary:
        s = compute_summary(trades)
        print("┌──────────────────────────────┐")
        print(f"│ 📊 交易统计                    │")
        print(f"├──────────────────────────────┤")
        print(f"│ 总交易: {s['total']:>4d}                   │")
        print(f"│ TP: {s.get('wins',0):>4d}  SL: {s.get('losses',0):>4d}              │")
        print(f"│ 胜率: {s['win_rate']:.0f}%                    │")
        print(f"│ 均盈: {s['avg_win_pct']:+.1f}%                  │")
        print(f"│ 均亏: {s['avg_loss_pct']:+.1f}%                  │")
        print(f"│ 期望值: {s['expectancy']:+.1f}%                 │")
        print(f"│ 总PnL: {s['total_pnl_pct']:+.1f}%  (${s['total_pnl_usd']:+.0f})     │")
        print(f"└──────────────────────────────┘")
        return

    if args.export_csv:
        import csv
        with open(args.export_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["time","symbol","direction",
                "entry","exit","result","pnl_pct","pnl_usd","leverage","notes"])
            writer.writeheader()
            for t in trades:
                writer.writerow({k: t.get(k,"") for k in writer.fieldnames})
        print(f"✅ 导出 {len(trades)} 条 → {args.export_csv}")
        logger.info("导出 %d 条交易 → %s", len(trades), args.export_csv)
        return

    # 默认 --list
    print(f"{'时间':22s} {'币种':10s} {'方向':6s} {'入场':>8s} {'出场':>8s} {'结果':4s} {'PnL':>7s}")
    print("-" * 75)
    for t in trades[-args.limit:]:
        ts = t.get("time","")[:19].replace("T"," ")
        print(f"{ts:22s} {t['symbol']:10s} {t['direction']:6s} "
              f"{t['entry']:8.4f} {t['exit']:8.4f} "
              f"{t['result']:4s} {t.get('pnl_pct',0):+6.1f}%")
    print(f"\n  {min(args.limit, len(trades))}/{len(trades)} 条记录")


if __name__ == "__main__":
    main()
