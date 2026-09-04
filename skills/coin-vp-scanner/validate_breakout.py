#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客观验证: 破位条件是否真的提高到 TP 命中率
===========================================
对比三条规则 (同一批历史数据, 零前视, 自适应TP/止损, 30min窗口):
  A. R2 仅放量强K线 (旧规则, 无破位)          —— 对照
  B. R2 + 结构破位 (收盘破前1h高低) 无趋势过滤 —— 破位是否加分?
  C. R2 + 破位 + 15m趋势同向 (现扫描器)        —— 完整规则

命中 = 30min内先到自适应TP 未先触止损(1.5×TP)。
结果若 B/C 显著高于 A → 破位条件有客观价值; 若 ≈A → 破位不提供增量, 需如实承认。
"""
import argparse, statistics, time
from concurrent.futures import ThreadPoolExecutor

import config as C
from backtest import get_klines_batch, mean
from pattern_1pct import get_universe

STRUCT_N = 12
HORIZ = 6                 # 30min


def adapt(atr5_pct):
    if atr5_pct < 0.3:  return 0.003, 0.005
    if atr5_pct < 0.6:  return 0.005, 0.008
    if atr5_pct < 1.0:  return 0.007, 0.011
    return 0.010, 0.015


def first_touch(i, K, d, tp_f, sl_f):
    if i + HORIZ >= len(K):
        return 'none'
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
        K = get_klines_batch(sym, "5m", now - days_ms, now)   # ms,o,h,l,c,v
        if len(K) < 900:
            return []
        out = []
        for i in range(72, len(K) - HORIZ - 1):
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
            else:
                broke = c < pl and o >= pl * 0.999
            # 15m 趋势 (近3根15m动量近似: 用5m近45min动量)
            c45 = K[max(0, i - 9)][4]
            mom45 = (c - c45) / c45 * 100
            align = (d == (1 if mom45 >= 0 else -1))
            # ATR5 + 自适应TP
            rngs = [abs(K[j][4] - K[j - 1][4]) for j in range(i - 13, i)]
            atr5 = mean(rngs)
            atr5_pct = atr5 / c * 100 if c else 0
            tp_f, sl_f = adapt(atr5_pct)
            # 三条规则各自判定
            resA = first_touch(i, K, d, tp_f, sl_f)          # 仅R2
            resB = first_touch(i, K, d, tp_f, sl_f) if broke else None
            resC = resB if (broke and align) else None
            out.append((resA, resB, resC))
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
    print(f"池: {pool} | {args.days}天 | 自适应TP/1.5×TP止损 | 30min窗口 | 零前视\n")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {s: ex.submit(analyze_coin, s, days_ms) for s in pool}
    rows = []
    for s, f in futs.items():
        rows.extend(f.result())
    nA = [r[0] for r in rows if r[0]]
    nB = [r[1] for r in rows if r[1]]
    nC = [r[2] for r in rows if r[2]]

    def report(tag, l):
        n = len(l)
        if n == 0:
            print(f"  {tag:<34}: 无样本"); return
        tp = sum(1 for x in l if x == 'tp')
        sl = sum(1 for x in l if x == 'sl')
        none = sum(1 for x in l if x == 'none')
        print(f"  {tag:<34}: 样本{n:>5} | 到TP {tp:>5} | 触止损 {sl:>4} | 未触发 {none:>5} | "
              f"到TP率 {tp/n*100:5.1f}%")

    print("=" * 88)
    print("A. R2 仅放量强K线 (无破位条件) —— 旧规则基线")
    report("", nA)
    print("\nB. R2 + 结构破位 (无趋势过滤) —— 破位是否加分?")
    report("", nB)
    print("\nC. R2 + 破位 + 趋势同向 —— 现扫描器完整规则")
    report("", nC)
    print("=" * 88)
    print("\n判定: B> A = 破位有增量 | C ≥ B = 趋势过滤也加分 | 都≈A = 条件无效需重设计")
    # 补充: A 里非破位的命中率 (直接展示"破位 vs 不破位")
    # A的触发里, 拆出同时有破位结果(B非None)和没破位(None)
    a_broke = [r[0] for r in rows if r[1] is not None]    # A中满足破位(即B触发)
    a_nobroke = [r[0] for r in rows if r[0] and r[1] is None]  # A中触发但没破位
    print("\n补充 — 同一批强K线里拆开看破位 vs 不破位:")
    report("A 中『有破位』的子集", a_broke)
    report("A 中『没破位』的子集(区间噪声)", a_nobroke)


if __name__ == "__main__":
    main()
