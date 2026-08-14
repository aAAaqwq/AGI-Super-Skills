#!/usr/bin/env python3
"""scripts/fix_testnet_exit_prices.py — 用 testnet 真实成交修正落盘中的失真记录

背景: cli/paper_testnet.py 旧版在 EXIT(超时/其他)平仓时取不到真实成交价就回退
现价(cur_price), 导致出场价失真(如 ZEC LONG EXIT 两笔都记成 491.67, 真实成交
分别是 494.13 和 489.65)。本脚本用 Binance testnet 的 userTrades 真实成交价
修正这些 EXIT 记录, 并重算 PnL。

设计:
  - 只修 result == "EXIT" 的记录的 exit 价格(超时/其他平仓真实成交);
    SL/TP 记录按设计用触发价记账, 不动。
  - 真实平仓成交 = 平仓方向(side)、时间在 [opened_ts, closed_ts] 窗口内的
    userTrades 数量加权均价 —— 用 closed_ts 做上界, 避免误吞后续仓位的成交。
  - 不动 entry(入场价由策略信号/开仓单记录, 离线重算有误配风险)。
  - 不改策略逻辑, 不触碰运行中的进程。

用法:
  export BINANCE_TESTNET_API_KEY=...   # 或已在 shell/zshrc 中
  export BINANCE_TESTNET_API_SECRET=...
  python scripts/fix_testnet_exit_prices.py --file testnet_trades_ZECUSDT.json [--apply]

不带 --apply 时只打印拟修正内容(DRY RUN); 带 --apply 才写回文件。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cli.trade_exec import LiveTrader  # noqa: E402

FEE_RATE = 0.0004  # 与 cli/paper.py 一致: taker 双边手续费 0.04%


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_ts_ms(v) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return None


def weight_avg(picks) -> float:
    tot = sum(q for q, _ in picks)
    if tot <= 0:
        return 0.0
    return sum(q * p for q, p in picks) / tot


def fetch_trades(trader, symbol: str, limit: int = 100) -> list:
    return trader.get_user_trades(symbol, limit=limit) or []


def real_exit_fill(trades, opened_ts: str, closed_ts: str, close_side: str,
                   max_fills: int = 5) -> float:
    """在 [opened_ts, closed_ts] 窗口内取平仓方向的数量加权真实成交价。"""
    opened_ms = parse_ts_ms(opened_ts) or 0
    closed_ms = parse_ts_ms(closed_ts) or (opened_ms + 24 * 3600 * 1000)
    picks = []
    for t in sorted(trades, key=lambda d: d.get("time") or 0, reverse=True):
        if t.get("side") != close_side:
            continue
        ttime = _f(t.get("time") or t.get("timestamp") or 0)
        if ttime and (ttime < opened_ms or ttime > closed_ms):
            continue
        qty = _f(t.get("qty"))
        if qty > 0:
            picks.append((qty, _f(t.get("price"))))
        if len(picks) >= max_fills:
            break
    return weight_avg(picks)


def pnl_pct(entry: float, exit_: float, dir_: str, leverage: float) -> float:
    if entry <= 0:
        return 0.0
    raw = (exit_ - entry) / entry * leverage * 100 * (1 if dir_ == "LONG" else -1)
    raw -= FEE_RATE * 100 * 2
    return round(raw, 2)


def main() -> None:
    p = argparse.ArgumentParser(description="用 testnet 真实成交修正落盘中的失真 EXIT 记录")
    p.add_argument("--file", required=True, help="落盘 JSON(如 testnet_trades_ZECUSDT.json)")
    p.add_argument("--apply", action="store_true", help="写回文件(默认 DRY RUN)")
    args = p.parse_args()

    api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print("❌ 缺少 BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET 环境变量")
        sys.exit(1)

    path = os.path.join(ROOT, args.file)
    with open(path) as f:
        records = json.load(f)
    if not isinstance(records, list) or not records:
        print("记录为空或格式不正确:", path)
        sys.exit(1)

    trader = LiveTrader(api_key, api_secret,
                        base_url="https://testnet.binancefuture.com")
    trades_by_symbol = {r["symbol"]: fetch_trades(trader, r["symbol"]) for r in records}

    changes = 0
    for i, r in enumerate(records):
        if r.get("result") != "EXIT":
            continue
        sym = r["symbol"]
        dir_ = r.get("dir")
        if dir_ not in ("LONG", "SHORT"):
            continue
        close_side = "SELL" if dir_ == "LONG" else "BUY"
        entry = _f(r.get("entry"))
        old_exit = _f(r.get("exit"))
        if entry <= 0:
            continue
        real_exit = real_exit_fill(trades_by_symbol.get(sym, []),
                                   r.get("opened_ts"), r.get("closed_ts"), close_side)
        if real_exit <= 0:
            print(f"  ⚠️  #{i} {sym} {dir_} 取不到窗口内真实平仓成交, 跳过")
            continue
        pnl = pnl_pct(entry, real_exit, dir_, _f(r.get("leverage", 10)))
        if abs(real_exit - old_exit) < 1e-9 and abs(pnl - _f(r.get("pnl_pct"))) < 1e-9:
            continue
        print(f"  #{i} {sym} {dir_:5s} EXIT  (opened={r.get('opened_ts', '')[:19]}, "
              f"closed={r.get('closed_ts', '')[:19]})")
        print(f"      exit : {old_exit:.6f} → {real_exit:.6f}")
        print(f"      pnl% : {r.get('pnl_pct')} → {pnl}")
        if args.apply:
            r["exit"] = real_exit
            r["pnl_pct"] = pnl
        changes += 1

    if changes == 0:
        print("无 EXIT 记录需要修正。")
        return

    total = sum(_f(x.get("pnl_pct")) for x in records)
    if not args.apply:
        print(f"\n共 {changes} 条将被修正(DRY RUN, 加 --apply 写回)。")
        print(f"   修正后累计 PnL(预测): {total:+.2f}%")
        return

    with open(path, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 已修正 {changes} 条 → {path}")
    print(f"   修正后累计 PnL: {total:+.2f}%")


if __name__ == "__main__":
    main()
