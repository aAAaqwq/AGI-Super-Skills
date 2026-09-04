#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应 TP 规律挖掘 — "够得到"的目标位
=======================================
R2 信号 (单根≥0.5% + 放量≥2x) 进场后, 测不同 TP 档位在 15/30min 内
先于止损(-1%) 被触及的真实比例 —— 找出按币的波动(ATR5) 该定多高的 TP,
避免"定太高踏空、定太低白做"。

输出: 每档 TP 的命中率(先到TP vs 先到-1%) + 按 ATR5 分桶的可达 TP
规则建议: TP% ≈ clip(倍数 × ATR5%, 下限, 上限)
"""
import argparse, statistics, time
from concurrent.futures import ThreadPoolExecutor

import config as C
from backtest import get_klines_batch, mean
from pattern_1pct import get_universe

STOP = -0.01          # 止损: 反向 -1%
TP_CANDS = [0.003, 0.005, 0.007, 0.01, 0.015]   # 0.3% ~ 1.5%
WIN_15 = 3            # 15min = 3根5m
WIN_30 = 6            # 30min = 6根5m


def r2_at(i, K5):
    """判定 i 收盘是否 R2。返回方向 1/-1 或 0"""
    if i < 46:
        return 0
    c = K5[i][4]; c0 = K5[i - 1][4]
    body = (c - c0) / c0 * 100
    if abs(body) < C.R2_BODY_PCT:
        return 0
    vols = [K5[j][5] for j in range(i - 72, i)]
    vr = mean(vols[-3:]) / max(mean(vols), 1e-12)
    if vr < C.R2_VOL_RATIO:
        return 0
    return 1 if body > 0 else -1


def first_touch(i, K5, d, tp_frac, stop_frac, horiz):
    """进场=K5[i]收盘, 未来 horiz 根内谁先到: 方向TP 还是 反向stop。
    返回 'tp' / 'stop' / 'none'"""
    if i + horiz >= len(K5):
        return 'none'
    e = K5[i][4]
    for j in range(i + 1, i + horiz + 1):
        h, l = K5[j][2], K5[j][3]
        if d > 0:
            if h >= e * (1 + tp_frac): return 'tp'
            if l <= e * (1 + stop_frac): return 'stop'
        else:
            if l <= e * (1 - tp_frac): return 'tp'
            if h >= e * (1 - stop_frac): return 'stop'
    return 'none'


def analyze_coin(sym, days_ms):
    try:
        now = int(time.time() * 1000)
        K5 = get_klines_batch(sym, "5m", now - days_ms, now)
        if len(K5) < 800:
            return []
        out = []
        for i in range(46, len(K5) - WIN_30 - 1):
            d = r2_at(i, K5)
            if d == 0:
                continue
            # 该币 ATR5
            rngs = [abs(K5[j][4] - K5[j - 1][4]) for j in range(i - 13, i)]
            atr5 = mean(rngs)
            atr5_pct = atr5 / K5[i][4] * 100
            rec = {"atr5": atr5_pct}
            for tp in TP_CANDS:
                r15 = first_touch(i, K5, d, tp, STOP, WIN_15)
                r30 = first_touch(i, K5, d, tp, STOP, WIN_30)
                rec[f"tp{tp}_15"] = r15
                rec[f"tp{tp}_30"] = r30
            out.append(rec)
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
    print(f"池: {pool} | 窗口 {args.days}天 | 止损 -1%")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {s: ex.submit(analyze_coin, s, days_ms) for s in pool}
    rows = []
    for s, f in futs.items():
        rows.extend(f.result())
    rows = [r for r in rows if r]
    print(f"R2 信号样本: {len(rows)}")

    print("\n" + "=" * 100)
    print(f"{'TP档位':>8} {'15min 命中':>14} {'15min 止损':>10} {'30min 命中':>14} {'30min 止损':>10} {'到TP率(30m)':>11}")
    print("-" * 100)
    for tp in TP_CANDS:
        l15 = [r for r in rows if r[f"tp{tp}_15"] in ('tp', 'stop')]
        l30 = [r for r in rows if r[f"tp{tp}_30"] in ('tp', 'stop')]
        n15, n30 = len(rows), len(rows)
        h15 = sum(1 for r in rows if r[f"tp{tp}_15"] == 'tp')
        s15 = sum(1 for r in rows if r[f"tp{tp}_15"] == 'stop')
        h30 = sum(1 for r in rows if r[f"tp{tp}_30"] == 'tp')
        s30 = sum(1 for r in rows if r[f"tp{tp}_30"] == 'stop')
        # 到TP率 = 到TP / 全部(含没触发的)
        print(f"{tp*100:>6.1f}%  {h15/n15*100:>12.1f}% {s15/n15*100:>10.1f}% {h30/n30*100:>12.1f}% {s30/n30*100:>10.1f}% {h30/n30*100:>9.1f}%")

    # 按 ATR5 分桶 (低/中/高) 看 30min 到 0.5% 与 0.75%
    print("\n" + "-" * 100)
    print("按币波动 ATR5% 分桶 → 30min 内『够得到』的可达 TP 水平:")
    lo = [r for r in rows if r["atr5"] < 0.3]
    mid = [r for r in rows if 0.3 <= r["atr5"] < 0.6]
    hi = [r for r in rows if r["atr5"] >= 0.6]
    for tag, grp in [("低波动 ATR<0.3%", lo), ("中波动 0.3-0.6%", mid), ("高波动 ≥0.6%", hi)]:
        if not grp:
            continue
        line = f"{tag:<16} n={len(grp):>5}: "
        for tp in TP_CANDS:
            h30 = sum(1 for r in grp if r[f"tp{tp}_30"] == 'tp')
            line += f"TP{tp*100:.1f}%→{h30/len(grp)*100:.0f}%  "
        print(line)
    print("\n结论: 选 到TP率≥60-65% 的那档为自适应 TP(够得到); 波动小就降TP别等1%踏空。")


if __name__ == "__main__":
    main()
