#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量价能极短线评分 · 历史回测
============================
验证问题: 「5m 脉冲 + 放量 + 15m 同向」的评分, 是否真的能预测
接下来 5min / 15min / 30min 的方向与幅度 (能否到 TP)。

方法 (严格零前视):
  - 取一组高流动性币最近 ~10 天 5m + 15m K线
  - 对每根已收盘的 5m K线, 只用"当时及之前"的数据算分
  - 记录其后 +5m/+15m/+30m 的实际方向与幅度
  - 按评分分档统计: 方向准确率 / 中位幅度 / 到 ±0.5% TP 概率
  - 对比: 高分段 vs 全样本 (评分是否有信息量)

⚠️ 局限: 币的"当期高流动性"取自现在快照, 非历史快照 (会有轻微幸存偏差,
  但不影响"评分是否有预测力"这个核心结论)。

用法:
  python3 backtest.py                 # 默认 16 个币 × 10 天
  python3 backtest.py --coins 24      # 币数
  python3 backtest.py --days 7        # 天数
"""
import argparse, json, statistics, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

import config as C
from scanner import api_get, get_klines  # 复用 API 层

MIN_5M = 3          # 回测样本最少 5m K线数(小于则跳过该币)


# ---------- 取 K 线 (分页) ----------
def get_klines_batch(symbol, interval, start_ms, end_ms):
    """按时间窗分页取全量 K线。返回 list[(open_ms, o, h, l, c, v)]"""
    out, cur = [], start_ms
    while True:
        path = (f"/fapi/v1/klines?symbol={symbol}&interval={interval}"
                f"&startTime={cur}&endTime={end_ms}&limit=1500")
        rows = api_get(path)
        if not rows:
            break
        out.extend(rows)
        last = rows[-1][0]
        if len(rows) < 1500 or last >= end_ms:
            break
        cur = last + 1
        time.sleep(0.1)
    return [(r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
            for r in out]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


# ---------- 某根 5m 收盘时点的评分 (零前视) ----------
def score_at(i, K):
    """K: 5m K线数组 [(ms,o,h,l,c,v)]; i 为已收盘 5m 下标(用 i 及之前数据)"""
    if i < 46:
        return None
    # 量
    vols = [K[j][5] for j in range(i)]
    vol_recent = mean(vols[-3:])
    vol_base = mean(vols[-72:])           # ~6h 基线
    vol_ratio = vol_recent / max(vol_base, 1e-12)
    # 价
    c = K[i][4]; c_prev = K[i - 1][4]
    impulse = (c - c_prev) / c_prev * 100
    c15 = K[i - 3][4]
    mom5 = (c - c15) / c15 * 100
    # 方向 (5m)
    d5 = 1 if mom5 >= 0 else -1
    # ATR5
    rngs = [abs(K[j][4] - K[j - 1][4]) for j in range(i - 13, i)]
    atr5 = mean(rngs)
    atr5_pct = atr5 / c * 100 if c else 0
    move_energy = abs(impulse) * C.W_IMPULSE + abs(mom5) * C.W_MOM
    atr_boost = 1.0 + atr5_pct * 0.05
    score = (vol_ratio ** C.W_VOLUME) * move_energy * atr_boost
    return {"score": score, "d5": d5, "mom5": mom5, "impulse": impulse,
            "vol_ratio": vol_ratio, "c": c, "i": i}


# ---------- 结果 ----------
def outcome_at(i, K, d, horiz):
    """从 K[i].close 起, 未来 horiz 根 5m 的实际移动 %。返回 (dir_correct, move_pct, reached_tp)"""
    if i + horiz >= len(K):
        return None
    c0 = K[i][4]
    cf = K[i + horiz][4]
    move = (cf - c0) / c0 * 100
    correct = 1 if d * move > 0 else 0
    # 到 ±0.5% TP 概率: 未来 horiz 根内, 是否触及过预测方向 0.5%
    reached = 0
    tgt = 0.5
    for j in range(i + 1, i + horiz + 1):
        hi, lo = K[j][2], K[j][3]
        if d > 0 and (hi - c0) / c0 * 100 >= tgt:
            reached = 1; break
        if d < 0 and (c0 - lo) / c0 * 100 >= tgt:
            reached = 1; break
    return correct, move, reached


def analyze_coin(sym, days_ms, coins_n):
    try:
        now = int(time.time() * 1000)
        start = now - days_ms
        K5 = get_klines_batch(sym, "5m", start, now)
        K15raw = get_klines_batch(sym, "15m", start, now)
        if len(K5) < MIN_5M or len(K15raw) < 20:
            return []
        # 15m → 按 5m 收盘时间对齐的 mom15
        def mom15_at(i):
            t5 = K5[i][0]          # 5m K线开始 ms
            # 找覆盖 t5 的最后一根已收盘 15m (close ≤ t5)
            j = 0
            while j < len(K15raw) and K15raw[j][0] + 900_000 <= t5:
                j += 1
            if j < 3:
                return None
            c_last = K15raw[j - 1][4]
            c_ago = K15raw[j - 4][4]
            return (c_last - c_ago) / c_ago * 100
        out = []
        for i in range(46, len(K5) - 7):
            s = score_at(i, K5)
            if s is None:
                continue
            m15 = mom15_at(i)
            if m15 is None:
                continue
            d15 = 1 if m15 >= 0 else -1
            if C.MIN_ALIGN and s["d5"] != d15:
                continue            # 不同向剔除 (与线上一致)
            s["d"] = s["d5"]
            s["mom15"] = m15
            for h in (1, 3, 6):
                oc = outcome_at(i, K5, s["d"], h)
                if oc:
                    correct, move, reached = oc
                    out.append({**s, "horiz": h, "correct": correct,
                                "move": move, "reached": reached})
        return out
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", type=int, default=16)
    ap.add_argument("--days", type=int, default=10)
    args = ap.parse_args()

    days_ms = args.days * 24 * 3600 * 1000
    print(f"⏳ 拉取全市场 ticker, 取 top {args.coins} 候选币 (大波动+高成交混合) ...")
    tickers = {s: t for s, t in get_all_tickers_live().items()
               if is_target_live(s, t)}
    # 与线上扫描器同源: 一半取 24h 大波动, 一半取高成交
    half = args.coins // 2
    by_move = sorted(tickers.items(), key=lambda kv: -abs(kv[1]["chg24"]))[:half]
    by_vol = sorted(tickers.items(), key=lambda kv: -kv[1]["vol"])[:half]
    pool = []
    for s, t in by_move + by_vol:
        if s not in [p for p, _ in pool]:
            pool.append((s, t))
    top = [s for s, _ in pool[:args.coins]]
    print(f"  回测币池: {top}")
    print(f"  窗口: 最近 {args.days} 天 5m/15m (严格零前视)")

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(analyze_coin, s, days_ms, args.coins) for s in top]
    all_rows = []
    for s, f in zip(top, futs):
        rows = f.result()
        print(f"  {s}: {len(rows)} 个带方向信号样本")
        all_rows.extend(rows)

    if not all_rows:
        print("无样本, 可能数据不足或网络异常")
        return

    # ---- 统计 ----
    print("\n" + "=" * 96)
    print(f"总样本: {len(all_rows)} 个时点信号 | 币: {len(top)} | 周期: {args.days}天")
    print("=" * 96)
    for h in (1, 3, 6):
        sub = [r for r in all_rows if r["horiz"] == h]
        if not sub:
            continue
        acc = mean(r["correct"] for r in sub) * 100
        med_move = statistics.median(abs(r["move"]) for r in sub)
        tp = mean(r["reached"] for r in sub) * 100
        lbl = {1: "5min", 3: "15min", 6: "30min"}[h]
        # 高分档 (top 20% score)
        sub_s = sorted(sub, key=lambda r: -r["score"])
        hi = sub_s[: max(1, len(sub_s) // 5)]
        acc_hi = mean(r["correct"] for r in hi) * 100
        tp_hi = mean(r["reached"] for r in hi) * 100
        print(f"\n--- 持仓 {lbl} ({len(sub)} 样本) ---")
        print(f"  全体方向准确率 : {acc:5.1f}%   | 中位移动幅度 {med_move:+.2f}% | 到±0.5% TP {tp:4.1f}%")
        print(f"  高分档(top20%)  : {acc_hi:5.1f}%   | {'':<18} | 到±0.5% TP {tp_hi:4.1f}%")

    # 评分分档方向准确率 (15min 视角)
    sub = [r for r in all_rows if r["horiz"] == 3]
    if sub:
        print("\n--- 评分分档 (持仓15min 方向准确率) ---")
        sub_s = sorted(sub, key=lambda r: -r["score"])
        n = len(sub_s)
        for q in range(5):
            chunk = sub_s[q * n // 5:(q + 1) * n // 5]
            if not chunk:
                continue
            acc = mean(r["correct"] for r in chunk) * 100
            med = statistics.median(abs(r["move"]) for r in chunk)
            print(f"  档 {5 - q}(最高分): {len(chunk):>5} 样本  准确率 {acc:5.1f}%  中位移动 {med:+.2f}%")

        # 方向源对照: 15min动量 vs 最近1根K线(impulse) —— 哪个更准?
        print("\n--- 方向源对照 (持仓15min, 全体/高分档) ---")
        for tag, pool2 in [("全体", sub), ("高分档top20%", sorted(sub, key=lambda r: -r["score"])[:max(1, len(sub)//5)])]:
            acc_mom = mean(1 if (1 if r["mom5"] >= 0 else -1) * r["move"] > 0 else 0 for r in pool2) * 100
            acc_imp = mean(1 if (1 if r["impulse"] >= 0 else -1) * r["move"] > 0 else 0 for r in pool2) * 100
            # 两者同向时的准确率
            both = [r for r in pool2 if (r["impulse"] >= 0) == (r["mom5"] >= 0)]
            acc_both = mean(1 if (1 if r["impulse"] >= 0 else -1) * r["move"] > 0 else 0 for r in both) * 100 if both else 0
            print(f"  {tag:>14}: 用15min动量判向 {acc_mom:5.1f}% | 用最近1根K线判向 {acc_imp:5.1f}% "
                  f"| 两者同向时 {acc_both:5.1f}% ({len(both)}样本)")
        # 放量+脉冲强确认时方向是否更准
        strong = [r for r in sub if r["vol_ratio"] >= 2 and abs(r["impulse"]) >= 0.8]
        if strong:
            acc_s = mean(1 if (1 if r["impulse"] >= 0 else -1) * r["move"] > 0 else 0 for r in strong) * 100
            print(f"\n  强条件(放量≥2x 且 脉冲≥0.8%) 用脉冲判向: 准确率 {acc_s:.1f}% ({len(strong)}样本)")

    # 放量 vs 方向
    print("\n说明: 准确率 50% = 无预测力(等于抛硬币)。>55% 且样本>500 才算初步可用。")


def get_all_tickers_live():
    from scanner import get_all_tickers
    return get_all_tickers()


def is_target_live(sym, t):
    from scanner import is_target
    return is_target(sym, t)


if __name__ == "__main__":
    main()
