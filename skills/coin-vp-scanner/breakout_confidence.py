#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
突破置信度验证 — 哪些确认条件能真正抬高"是真突破"的把握?
========================================================
在全部 R2 结构破位信号上, 测不同"确认层"各自把命中率抬到多少:
  L0 现规则: 收盘破位即可 (基准)
  L1 加超越幅度: 收盘须超出结构位 ≥0.3% (不是贴线假破)
  L2 加持有确认: L1 + 信号后下一根未立刻跌回位内 (排除即日假突破/诱多)
  L3 加放量级:   L1 + 量能≥3x (更真实的大资金)
  L4 全叠:      L2 + L3
并统计每层的"假突破率"(先触止损比例), 给你可量化的把握证据。
"""
import argparse, time
from concurrent.futures import ThreadPoolExecutor

import config as C
from backtest import get_klines_batch, mean
from pattern_1pct import get_universe

STRUCT_N = 12
HORIZ = 6          # 30min
MARGIN = 0.003     # L1 超越幅度 ≥0.3%


def adapt(atr5_pct):
    if atr5_pct < 0.3:  return 0.003, 0.005
    if atr5_pct < 0.6:  return 0.005, 0.008
    if atr5_pct < 1.0:  return 0.007, 0.011
    return 0.010, 0.015


def outcome(i, K, d, tp_f, sl_f):
    e = K[i][4]
    for j in range(i + 1, i + HORIZ + 1):
        h, l = K[j][2], K[j][3]
        if d > 0:
            if h >= e * (1 + tp_f): return 'tp'
            if l <= e * (1 - sl_f): return 'sl'
        else:
            if l <= e * (1 - tp_f): return 'tp'
            if h >= e * (1 - sl_f): return 'sl'
    return 'none'


def analyze_coin(sym, days_ms):
    try:
        now = int(time.time() * 1000)
        K = get_klines_batch(sym, "5m", now - days_ms, now)
        if len(K) < 900:
            return []
        out = []
        for i in range(72, len(K) - HORIZ - 2):
            c = K[i][4]; c0 = K[i - 1][4]
            body = (c - c0) / c0 * 100
            vols = [K[j][5] for j in range(i - 72, i)]
            vr = mean(vols[-3:]) / max(mean(vols), 1e-12)
            if abs(body) < C.R2_BODY_PCT or vr < C.R2_VOL_RATIO:
                continue
            d = 1 if body > 0 else -1
            ph = max(K[j][2] for j in range(i - STRUCT_N, i))
            pl = min(K[j][3] for j in range(i - STRUCT_N, i))
            o = K[i][1]
            if d > 0:
                broke = c > ph and o <= ph * 1.001
                margin_ok = (c - ph) / ph >= MARGIN
                level = ph
            else:
                broke = c < pl and o >= pl * 0.999
                margin_ok = (pl - c) / pl >= MARGIN
                level = pl
            if not broke:
                continue
            rngs = [abs(K[j][4] - K[j - 1][4]) for j in range(i - 13, i)]
            atr5 = mean(rngs)
            tp_f, sl_f = adapt(atr5 / c * 100 if c else 0)
            res0 = outcome(i, K, d, tp_f, sl_f)
            res1 = res0 if margin_ok else None
            # L2: 下一根是否仍站住 (没立刻跌回位内)  — 对 UP: K[i+1].l > level
            hold = None
            if margin_ok and i + 1 < len(K):
                if d > 0:
                    hold = K[i + 1][3] > level
                else:
                    hold = K[i + 1][2] < level
                res2 = res0 if hold else None
            else:
                res2 = None
            res3 = res0 if (margin_ok and vr >= 3.0) else None
            res4 = res0 if (hold and vr >= 3.0) else None
            out.append((res0, res1, res2, res3, res4))
        return out
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", type=int, default=14)
    ap.add_argument("--days", type=int, default=10)
    args = ap.parse_args()
    days_ms = args.days * 24 * 3600 * 1000
    pool = get_universe(args.coins)
    print(f"池: {pool} | {args.days}天 | 自适应TP/1.5×TP止损 | 30min\n")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {s: ex.submit(analyze_coin, s, days_ms) for s in pool}
    rows = []
    for s, f in futs.items():
        rows.extend(f.result())

    labels = ["L0 收盘破位(基准)", "L1 +超越幅度≥0.3%", "L2 +下一根站住",
              "L3 +放量≥3x", "L4 全叠(L2+L3)"]
    print("=" * 92)
    for k, tag in enumerate(labels):
        l = [r[k] for r in rows if r[k] is not None]
        n = len(l)
        if n == 0:
            print(f"  {tag:<20}: 无样本"); continue
        tp = sum(1 for x in l if x == 'tp')
        sl = sum(1 for x in l if x == 'sl')
        none = sum(1 for x in l if x == 'none')
        fake = sl / n * 100
        print(f"  {tag:<20}: 样本{n:>4} | 到TP率 {tp/n*100:5.1f}% | 假突破率(触止损) {fake:4.1f}% "
              f"| 未触发 {none:>4}")
    print("=" * 92)
    print("结论看: 到TP率是否随确认层上升 = 该确认有真实价值; 若不变/样本骤减 = 只是自我安慰。")


if __name__ == "__main__":
    main()
