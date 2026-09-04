#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
到 TP 耗时分布 — R2 破位信号实际多久能到目标?
=============================================
对历史 R2+破位信号, 记录"若最终到TP, 是在第几分钟触达"(5/10/15/20/25/30min)。
输出: 到TP率 + 到TP者中位耗时 + 各时间点累计到TP率。
"""
import argparse, statistics, time
from concurrent.futures import ThreadPoolExecutor

import config as C
from backtest import get_klines_batch, mean
from pattern_1pct import get_universe

STRUCT_N = 12
MAX_WIN = 6        # 最多看 30min (6根5m)
TP_CANDS = [0.003, 0.005, 0.007, 0.010]
SL = 0.01          # 固定参考止损 -1%


def analyze_coin(sym, days_ms):
    try:
        now = int(time.time() * 1000)
        K = get_klines_batch(sym, "5m", now - days_ms, now)
        if len(K) < 900:
            return []
        out = []
        for i in range(72, len(K) - MAX_WIN - 1):
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
            if d > 0 and not (c > ph and o <= ph * 1.001):
                continue
            if d < 0 and not (c < pl and o >= pl * 0.999):
                continue
            e = K[i][4]
            for tp in TP_CANDS:
                # 记录到TP时刻(第几根), 若先触-1%止损则记为没到
                touch_t = None
                stopped = False
                for j in range(i + 1, i + MAX_WIN + 1):
                    h, l = K[j][2], K[j][3]
                    if d > 0:
                        if h >= e * (1 + tp): touch_t = j - i; break
                        if l <= e * (1 - SL): stopped = True; break
                    else:
                        if l <= e * (1 - tp): touch_t = j - i; break
                        if h >= e * (1 - SL): stopped = True; break
                out.append({"tp": tp, "touch": touch_t, "stopped": stopped,
                            "atr5": None})
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
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {s: ex.submit(analyze_coin, s, days_ms) for s in pool}
    rows = []
    for s, f in futs.items():
        rows.extend(f.result())
    print(f"池 {args.coins} 币 | {args.days}天 | 止损 -1%\n")
    print("=' 到TP耗时的真实分布 (只看 最终到TP 的信号) =")
    for tp in TP_CANDS:
        sub = [r for r in rows if r["tp"] == tp]
        n = len(sub)
        touched = [r for r in sub if r["touch"] is not None]
        hit_rate = len(touched) / n * 100
        if not touched:
            continue
        med = statistics.median(r["touch"] for r in touched) * 5
        # 各时间点累计
        def cum(minutes):
            return sum(1 for r in touched if r["touch"] * 5 <= minutes) / n * 100
        print(f"TP {tp*100:.1f}%: 到TP率 {hit_rate:.0f}% | 到TP者中位 {med:.0f}min | "
              f"累计: 5m {cum(5):.0f}% 10m {cum(10):.0f}% 15m {cum(15):.0f}% 20m {cum(20):.0f}% 30m {cum(30):.0f}%")
    print("\n读法: 例 TP0.5% → 到TP率72%, 其中一半在X分钟内到; 到不了的就是假突破/横盘。")


if __name__ == "__main__":
    main()
