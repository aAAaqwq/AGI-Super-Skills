#!/usr/bin/env python3
"""
cli/backtest_daily.py — 按天分桶的一周回测

每个币回测一周(默认7天), 把每笔交易按自然天分桶, 统计:
  - 每日交易次数分布(判断哪些币每天都有稳定信号)
  - 每日 TP/SL 数 + 每日 PnL
  - 按"日均交易次数 >= --min-daily"筛选, 输出适合高频节奏的币

用法:
  python cli/backtest_daily.py                       # 全部币, 默认日均>=2次
  python cli/backtest_daily.py --symbols NEARUSDT,XRPUSDT
  python cli/backtest_daily.py --days 7 --min-daily 3
  python cli/backtest_daily.py --min-daily 0 --detail   # 看全部+每日明细

数据来源: 币安 fapi K线(15m), 策略逻辑与 simulate.py 一致(三重过滤+轨对轨)。
"""
import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load_symbols(config_path: str, explicit: str = None) -> list:
    if explicit:
        return [s.strip().upper() for s in explicit.split(",") if s.strip()]
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg["scan"]["symbols"]
    except Exception:
        return ["NEARUSDT", "XRPUSDT", "DOTUSDT", "ATOMUSDT"]


def fetch_klines(symbol, interval, limit, step=1500):
    """分页拉取 K 线(币安单次 limit 上限 1500)。"""
    import requests
    bars = []
    remaining = limit
    end_time = None
    while remaining > 0:
        n = min(step, remaining)
        params = {"symbol": symbol, "interval": interval, "limit": n}
        if end_time:
            params["endTime"] = end_time
        resp = requests.get("https://fapi.binance.com/fapi/v1/klines",
                            params=params, timeout=15)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        bars = [{"open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
                 "close": float(k[4]), "volume": float(k[5]), "time": int(k[0])}
                for k in batch] + bars
        remaining -= len(batch)
        end_time = batch[0][0] - 1  # 前移到本批最早一根之前
        if len(batch) < n:
            break
    return bars


def calc_bb(closes, period=20, std=2.0):
    if len(closes) < period:
        return None
    sma = float(np.mean(closes[-period:]))
    s = float(np.std(closes[-period:], ddof=1))
    upper, lower = sma + std * s, sma - std * s
    width = (upper - lower) / sma
    slope = 0.0
    if len(closes) >= 8:
        y = closes[-8:]
        slope = float(np.polyfit(np.arange(len(y)), y, 1)[0]) / sma
    pct_b = (closes[-1] - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
    return {"middle": sma, "upper": upper, "lower": lower,
            "width": width, "slope": slope, "pct_b": pct_b}


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-period - 1:])
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) if avg_loss > 0 else 100.0


def simulate_trade(closes, idx, entry, stop, tp, direction, ts, leverage=10):
    """逐根模拟一笔交易到 TP/SL 或超时(48根)。返回带时间戳的记录。"""
    future = closes[idx + 1:idx + 49]
    for fc in future:
        if direction == "LONG":
            if fc <= stop:
                return {"time": ts, "dir": "LONG", "entry": entry, "exit": stop,
                        "pnl_pct": (stop - entry) / entry * leverage * 100, "result": "SL"}
            if fc >= tp:
                return {"time": ts, "dir": "LONG", "entry": entry, "exit": tp,
                        "pnl_pct": (tp - entry) / entry * leverage * 100, "result": "TP"}
        else:
            if fc >= stop:
                return {"time": ts, "dir": "SHORT", "entry": entry, "exit": stop,
                        "pnl_pct": (entry - stop) / entry * leverage * 100, "result": "SL"}
            if fc <= tp:
                return {"time": ts, "dir": "SHORT", "entry": entry, "exit": tp,
                        "pnl_pct": (entry - tp) / entry * leverage * 100, "result": "TP"}
    exit_price = future[-1] if len(future) > 0 else closes[idx]
    pnl = (exit_price - entry) / entry * leverage * 100
    if direction == "SHORT":
        pnl = -pnl
    return {"time": ts, "dir": direction, "entry": entry, "exit": exit_price,
            "pnl_pct": pnl, "result": "TIMEOUT"}


def backtest_symbol(symbol, days, params):
    """回测一个币, 返回按天分桶的交易统计。"""
    hours = days * 24
    bars = fetch_klines(symbol, "15m", limit=hours * 4 + 120)
    closes = np.array([b["close"] for b in bars])
    closes_1h = np.array([bars[i]["close"] for i in range(0, len(bars), 4)])

    bb_p = params["bb_period"]
    sweet_min, sweet_max = params["sweet_min"], params["sweet_max"]
    stop_buf, entry_th = params["stop_buffer"], params["entry_threshold"]
    slope_loose = params["slope_loose"]
    rsi_long, rsi_short = params["rsi_long"], params["rsi_short"]
    cool = params["cooldown"]

    trades = []
    last_sl = -cool - 1
    for i in range(bb_p + 10, len(bars) - 24):
        window = closes[:i + 1]
        bb = calc_bb(window)
        rsi = calc_rsi(window)
        if bb is None or rsi is None:
            continue
        if bb["width"] < sweet_min or bb["width"] > sweet_max:
            continue
        h_idx = i // 4
        slope_1h = 0.0
        if h_idx >= 8 and h_idx < len(closes_1h):
            y = closes_1h[max(0, h_idx - 8):h_idx + 1]
            if len(y) >= 4:
                slope_1h = float(np.polyfit(np.arange(len(y)), y, 1)[0]) / float(np.mean(y))
        if i - last_sl < cool:
            continue
        lower, upper = bb["lower"], bb["upper"]
        if bb["pct_b"] < 0.15 and slope_1h > -slope_loose and rsi <= rsi_long:
            entry = lower * (1 + entry_th / 2)
            t = simulate_trade(closes, i, entry, lower * (1 - stop_buf), upper,
                               "LONG", bars[i]["time"])
            trades.append(t)
            if t["result"] == "SL":
                last_sl = i
        if bb["pct_b"] > 0.85 and slope_1h < slope_loose and rsi >= rsi_short:
            entry = upper * (1 - entry_th / 2)
            t = simulate_trade(closes, i, entry, upper * (1 + stop_buf), lower,
                               "SHORT", bars[i]["time"])
            trades.append(t)
            if t["result"] == "SL":
                last_sl = i

    # 按自然天分桶
    days_map = defaultdict(list)
    for t in trades:
        day = datetime.fromtimestamp(t["time"] / 1000, tz=timezone.utc).strftime("%m-%d")
        days_map[day].append(t)

    daily = {}
    for day, ts in sorted(days_map.items()):
        tp = sum(1 for t in ts if t["result"] == "TP")
        sl = sum(1 for t in ts if t["result"] == "SL")
        to = sum(1 for t in ts if t["result"] == "TIMEOUT")
        daily[day] = {"n": len(ts), "tp": tp, "sl": sl, "timeout": to,
                      "pnl": round(sum(t["pnl_pct"] for t in ts), 2)}

    total = len(trades)
    tp_n = sum(1 for t in trades if t["result"] == "TP")
    sl_n = sum(1 for t in trades if t["result"] == "SL")
    total_pnl = sum(t["pnl_pct"] for t in trades)
    avg_daily = total / days if days > 0 else 0
    wr = tp_n / (tp_n + sl_n) * 100 if (tp_n + sl_n) > 0 else 0

    # 最大回撤: 基于资金曲线(初始100, 每笔按 notional=100 的百分比增减)
    # 与策略 max_position_usd=100 一致; 反映最坏连续亏损段
    capital = 100.0
    peak = 100.0
    max_dd = 0.0
    max_dd_start = 0.0
    for t in trades:
        capital += 100.0 * t["pnl_pct"] / 100
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_start = capital
    return {
        "symbol": symbol, "total": total, "tp": tp_n, "sl": sl_n,
        "win_rate": round(wr, 1), "total_pnl": round(total_pnl, 1),
        "avg_daily": round(avg_daily, 1), "daily": daily,
        "days_with_trades": len(daily),
        "max_drawdown_pct": round(max_dd, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="BB套利 - 按天分桶一周回测")
    parser.add_argument("--symbols", help="逗号分隔, 默认 config 全部")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--min-daily", type=float, default=2.0,
                        help="日均交易次数下限(用于筛选)")
    parser.add_argument("--detail", action="store_true", help="显示每日明细")
    args = parser.parse_args()

    config_path = os.path.join(ROOT, "config.yaml")
    symbols = load_symbols(config_path, args.symbols)
    params = {
        "bb_period": 20, "sweet_min": 0.008, "sweet_max": 0.025,
        "stop_buffer": 0.0015, "entry_threshold": 0.002,
        "slope_loose": 0.0006, "rsi_long": 55, "rsi_short": 45, "cooldown": 3,
    }

    print(f"🔍 按天分桶一周回测 | {args.days}天 | 日均交易>={args.min_daily} | {len(symbols)}币\n")
    results = []
    for sym in symbols:
        try:
            r = backtest_symbol(sym, args.days, params)
            results.append(r)
            time.sleep(0.15)
        except Exception as e:
            print(f"  ❌ {sym}: {e}")

    # 按日均交易筛选 + PnL 排序
    ranked = [r for r in results if r["avg_daily"] >= args.min_daily]
    ranked.sort(key=lambda r: r["total_pnl"], reverse=True)

    print(f"\n{'─'*86}")
    print(f"📊 满足「日均交易 ≥ {args.min_daily}」的币 (按累计PnL排序)")
    print(f"{'─'*86}")
    print(f"{'币种':10s} {'总信号':>6s} {'日均':>6s} {'TP/SL':>8s} {'胜率':>7s} {'累计PnL':>10s} {'有交易天数':>10s} {'最大回撤':>8s}")
    print(f"{'─'*86}")
    for r in ranked:
        print(f"{r['symbol']:10s} {r['total']:>6d} {r['avg_daily']:>6.1f} "
              f"{r['tp']:>3d}/{r['sl']:<3d} {r['win_rate']:>6.0f}% "
              f"{r['total_pnl']:>+9.1f}% {r['days_with_trades']:>5d}/{args.days} "
              f"{r.get('max_drawdown_pct',0):>7.1f}%")

    if not ranked:
        print("  (无币满足日均交易下限)")

    # 未满足的币单独列出
    skipped = [r for r in results if r["avg_daily"] < args.min_daily]
    if skipped:
        skipped.sort(key=lambda r: r["avg_daily"], reverse=True)
        print(f"\n{'─'*78}")
        print(f"❌ 未满足日均≥{args.min_daily} 的币 (交易太稀疏, 不计入)")
        print(f"{'─'*78}")
        for r in skipped:
            print(f"{r['symbol']:10s} 日均 {r['avg_daily']:.1f} | {r['total']}笔 | {r['total_pnl']:+.1f}%")

    # 每日明细
    if args.detail:
        print(f"\n{'─'*78}")
        print("📅 每日交易明细 (日期: 笔数[TP/SL/超时] PnL%)")
        print(f"{'─'*78}")
        for r in ranked:
            print(f"\n  {r['symbol']}  (日均 {r['avg_daily']})")
            for day, d in r["daily"].items():
                print(f"    {day}: {d['n']:>2d}笔 [{d['tp']}/{d['sl']}/{d['timeout']}] PnL {d['pnl']:+.1f}%")


if __name__ == "__main__":
    main()
