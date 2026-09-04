#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1% 目标竞速 · 高确定性规律挖掘
================================
问题: 进场后 15min(3根5m)内, 价格先触及 +1%(目标) 还是先触及 -1%(止损/爆仓附近)?
目标是找到能把「先到+1%」概率抬到 60-70%+ 的高确定性状态 —— 供 50x-100x 杠杆
单方向吃 1% 用 (1%×75x = +75% 本金; -1% 止损 = -75% 本金, 接近爆仓)。

进场时点: 某根 5m K线收盘后 (只用已收盘数据, 零前视)
方向: 由"当前状态"的规则决定 (测多条规则)

输出: 每条规则的 命中率(+1先到) / 触发次数 / 各币一致性
说明: 命中率>60% 且样本>300 才算初步值得上杠杆; 这表是找规律, 不是保证。
"""
import argparse, statistics, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

import config as C
from scanner import api_get
from backtest import get_klines_batch, mean

HORIZON = 3        # 看未来 3 根 5m = 15min
TP = 0.01          # +1%
SL = -0.01         # -1%


def get_universe(n):
    from scanner import get_all_tickers, is_target
    tickers = get_all_tickers()
    cands = {s: t for s, t in tickers.items() if is_target(s, t)}
    half = n // 2
    by_move = sorted(cands.items(), key=lambda kv: -abs(kv[1]["chg24"]))[:half]
    by_vol = sorted(cands.items(), key=lambda kv: -kv[1]["vol"])[:half]
    pool = []
    for s, t in by_move + by_vol:
        if s not in [p for p, _ in pool]:
            pool.append((s, t))
    return [s for s, _ in pool[:n]]


# ---------- 候选规则: 返回方向 +1/-1/0(不触发) ----------
def rules_at(i, K5):
    """K5: 5m (ms,o,h,l,c,v). 返回 dict rule->(dir or 0). 全基于 i 及之前。"""
    if i < 46:
        return {}
    c = K5[i][4]; c0 = K5[i - 1][4]; c3 = K5[i - 3][4]
    body = (c - c0) / c0 * 100                    # 上一根K线涨跌幅
    mom5 = (c - c3) / c3 * 100
    vols = [K5[j][5] for j in range(i - 72, i)]
    vol_r = mean(vols[-3:]) / max(mean(vols), 1e-12)
    rngs = [abs(K5[j][4] - K5[j - 1][4]) for j in range(i - 13, i)]
    atr5 = mean(rngs); atr5_pct = atr5 / c * 100 if c else 0
    # 15m 趋势方向 (用已有特征近似: mom5 近 15min)
    d15 = 1 if mom5 >= 0 else -1
    db = 1 if body >= 0 else -1
    r = {}
    # R0 基线: 全跟上一根方向
    r["R0_基线"] = db
    # R1 放量+有方向
    if vol_r >= 1.5 and abs(body) >= 0.3: r["R1_放量>1.5+体>0.3"] = db
    # R2 强放量+强体
    if vol_r >= 2.0 and abs(body) >= 0.5: r["R2_放量>2+体>0.5"] = db
    # R3 同向确认 (上一根 与 5m短动量同向)
    if db == d15 and abs(body) >= 0.3: r["R3_方向一致"] = db
    # R4 放量+同向 (方向一致 + 放量)
    if db == d15 and vol_r >= 2.0 and abs(body) >= 0.4: r["R4_放量2x+同向"] = db
    # R5 挤压后爆发 (低ATR后突然大放量) — atr在近低位+现放量
    atr_hist = mean([abs(K5[j][4] - K5[j - 1][4]) for j in range(i - 72, i - 14)])
    if vol_r >= 2.5 and abs(body) >= 0.6: r["R5_超强放量>2.5+体>0.6"] = db
    # R6 高动量延续 (mom5 大且方向一致)
    if abs(mom5) >= 1.2 and db == (1 if mom5 >= 0 else -1) and vol_r >= 1.5: r["R6_高动量+放量"] = db
    return r


def simulate(i, K5, d):
    """进场=K5[i]收盘。未来 HORIZON 根内, +1%先到? -1%先到? 超时?"""
    if d == 0 or i + HORIZON >= len(K5):
        return None
    entry = K5[i][4]
    hi_t, lo_t = entry * (1 + TP), entry * (1 + SL)
    # 若 d<0 则目标是 -1%(先到下方), 止损是 +1%
    if d < 0:
        hi_t, lo_t = entry * (1 - TP), entry * (1 + TP)  # lo = 目标, hi = 止损
        # 注意: lo_t 是目标(更低), hi_t 是止损(更高)
    for j in range(i + 1, i + HORIZON + 1):
        h, l = K5[j][2], K5[j][3]
        if d > 0:
            if h >= hi_t: return "win"
            if l <= lo_t: return "loss"
        else:
            if l <= lo_t: return "win"
            if h >= hi_t: return "loss"
    return "timeout"


def analyze_coin(sym, days_ms):
    try:
        now = int(time.time() * 1000)
        t0 = now - days_ms
        K5 = get_klines_batch(sym, "5m", t0, now)
        if len(K5) < 800:
            return []
        mid = t0 + days_ms // 2
        rows = []
        for i in range(46, len(K5) - HORIZON - 1):
            rs = rules_at(i, K5)
            half = 0 if K5[i][0] < mid else 1
            for name, d in rs.items():
                res = simulate(i, K5, d)
                if res:
                    rows.append((name, res, half))
        return rows
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", type=int, default=14)
    ap.add_argument("--days", type=int, default=10)
    args = ap.parse_args()
    days_ms = args.days * 24 * 3600 * 1000

    pool = get_universe(args.coins)
    print(f"池: {pool} | 窗口 {args.days}天 | 目标 +1% vs 止损 -1% @ {HORIZON*5}min")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {s: ex.submit(analyze_coin, s, days_ms) for s in pool}
    all_rows = []
    for s, f in futs.items():
        rows = f.result()
        all_rows.extend(rows)
        print(f"  {s}: {len(rows)} 触发")

    # 分规则统计 (诚实口径: 超时 = 没到TP, 计入分母)
    import collections
    agg = collections.defaultdict(list)
    for name, res, half in all_rows:
        agg[name].append((res, half))
    print("\n" + "=" * 96)
    print(f"{'规则':<24} {'触发':>6} {'到+1%TP':>8} {'到-1%':>7} {'超时':>6} {'实际到TP率':>10}  评级")
    print("-" * 96)
    for name, lst in agg.items():
        n = len(lst)
        w = sum(1 for x, _ in lst if x == "win")
        l = sum(1 for x, _ in lst if x == "loss")
        t = sum(1 for x, _ in lst if x == "timeout")
        tp_rate = w / n * 100 if n else 0      # 实际到 TP 率 (含超时)
        grade = "✅可用" if (tp_rate >= 65 and n >= 300) else ("🟡参考" if (tp_rate >= 58 and n >= 200) else "❌不足")
        print(f"{name:<24} {n:>6} {w:>8} {l:>7} {t:>6} {tp_rate:>9.1f}%  {grade}")
    print("=" * 96)
    print("实际到TP率 = 到+1% / 全部触发 (超时=没到±1%, 按没吃到TP算)。")
    print("✅ = 到TP率≥65% 且样本≥300; 仍需前向验证 + 对震荡行情单独检验。")

    # 稳定性: 前后两半窗口 到TP率 对比 (关键规则)
    print("\n" + "-" * 96)
    print("稳定性检验 (前5天 vs 后5天, 实际到TP率含超时) — 规律是否只活在某段行情:")
    for name in ["R0_基线", "R2_放量>2+体>0.5", "R4_放量2x+同向", "R6_高动量+放量"]:
        l0 = [x for x, h in agg[name] if h == 0]
        l1 = [x for x, h in agg[name] if h == 1]
        def tp(l):
            n = len(l)
            if n == 0: return None, 0
            w = sum(1 for x in l if x == "win")
            return w / n * 100, n
        h0, n0 = tp(l0); h1, n1 = tp(l1)
        s0 = f"{h0:.1f}%({n0})" if h0 is not None else "-"
        s1 = f"{h1:.1f}%({n1})" if h1 is not None else "-"
        diff = f"  差 {abs(h0-h1):.1f}pp" if h0 and h1 else ""
        print(f"  {name:<24}: 前段 {s0:>14} | 后段 {s1:>14} {diff}")
    print("  ※ 前后到TP率差 <8pp 且都>55% = 规律较稳; 若一段高一段崩 = 过拟合/吃行情红利")


if __name__ == "__main__":
    main()
