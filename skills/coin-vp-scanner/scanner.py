#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量价能结构突破扫描器 v4 · 确定性逻辑, 非黑箱
==============================================
判定规则 (全是 if-then, 可复核):
  量价能突破信号 成立 ⇔ 全部满足:
    1) 最近一根收盘 5m K线 放量:  vol_ratio ≥ R2_VOL_RATIO(2x 基线)
    2) 该K线实体够强:             |body| ≥ R2_BODY_PCT(0.5%)
    3) 结构突破 (关键!):  UP→收盘 破 前12根(1h) 高点; DOWN→收盘 破 前低
       且 K线开盘价 未远离该位 (从位内/贴位起爆, 不是跳空追高)
    4) 方向与 15m 短趋势同向 (TREND_FILTER)

输出: 每个信号一条带"判定链"的理由 —— 为什么是/不是真突破, 全透明。

用法:
  python3 scanner.py               # 只报真突破信号 + 理由链
  python3 scanner.py --no-trend    # 关 15m 趋势过滤
  python3 scanner.py --telegram
"""
import argparse, json, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

import config as C

STRUCT_N = 12          # 结构位回看 12 根 5m (1h 高点/低点)
# 到TP耗时参考 (回测 time_to_tp.py): tp% -> (中位耗时min, 到TP率)
TIME_TP_REF = {0.3: (5, 79), 0.5: (5, 67), 0.7: (5, 56), 1.0: (5, 47)}


def api_get(path):
    req = urllib.request.Request(C.FAPI_BASE + path,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def get_all_tickers():
    data = api_get("/fapi/v1/ticker/24hr")
    out = {}
    for d in data:
        s = d["symbol"]
        if s.endswith("USDT"):
            out[s] = {"price": float(d["lastPrice"]),
                      "chg24": float(d["priceChangePercent"]),
                      "vol": float(d["quoteVolume"])}
    return out


def get_klines(sym, iv, limit):
    rows = api_get(f"/fapi/v1/klines?symbol={sym}&interval={iv}&limit={limit}")
    return [(r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
            for r in rows]   # ms,o,h,l,c,v


def is_target(sym, t):
    if sym in C.STABLES or any(x in sym for x in C.EXCLUDE_SUBSTR):
        return False
    if re.search(r"\d[LS]USDT$", sym) or len(sym) > 14:
        return False
    return t["vol"] >= C.MIN_QUOTE_VOLUME and t["price"] >= C.MIN_PRICE


def adapt_tp(atr5_pct):
    """自适应目标(回测): 别等1%踏空, 目标跟着波动走"""
    if atr5_pct < 0.3:  return 0.3, 0.5, 0.76   # TP%, SL%, 参考命中
    if atr5_pct < 0.6:  return 0.5, 0.8, 0.64
    if atr5_pct < 1.0:  return 0.7, 1.1, 0.70
    return 1.0, 1.5, 0.60


def detect(sym, t):
    """检测: 是否 量价能结构突破。返回带完整判定链的 dict 或 None。"""
    try:
        k5 = get_klines(sym, C.PRIMARY_IV, C.PRIMARY_CLOSES)
        k15 = get_klines(sym, C.TREND_IV, C.TREND_CLOSES)
        k1h = get_klines(sym, C.CONTEXT_IV, C.CONTEXT_CLOSES)
        if len(k5) < 60 or len(k15) < 20 or len(k1h) < 10:
            return None

        now_ms = int(time.time() * 1000)
        idx = len(k5) - 1
        if k5[idx][0] + 300_000 > now_ms:   # 末根未收盘
            idx -= 1
        if idx < STRUCT_N + 3:
            return None

        # --- 信号 K线 (已收盘): ms,o,h,l,c,v ---
        sig_ms, sig_o, sig_h, sig_l, sig_c, sig_v = k5[idx]
        prev_c = k5[idx - 1][4]
        body_pct = (sig_c - prev_c) / prev_c * 100
        # 量能
        vols = [k5[j][5] for j in range(idx - 72, idx)]
        vol_base = sum(vols) / len(vols) if vols else 1e-9
        vol_ratio = sig_v / max(vol_base, 1e-12)
        price = sig_c

        # --- 结构位: 前 STRUCT_N 根(不含信号)的高/低 ---
        ph = max(k5[j][2] for j in range(idx - STRUCT_N, idx))
        pl = min(k5[j][3] for j in range(idx - STRUCT_N, idx))

        # --- 15m / 1h 趋势 ---
        j15 = len(k15) - 1
        if k15[j15][0] + 900_000 > now_ms:
            j15 -= 1
        mom15 = (k15[j15][4] - k15[max(0, j15 - 3)][4]) / k15[max(0, j15 - 3)][4] * 100
        j1 = len(k1h) - 1
        if k1h[j1][0] + 3_600_000 > now_ms:
            j1 -= 1
        mom1h = (k1h[j1][4] - k1h[max(0, j1 - 5)][4]) / k1h[max(0, j1 - 5)][4] * 100

        # --- ATR5 ---
        rngs = [abs(k5[j][4] - k5[j - 1][4]) for j in range(idx - 13, idx)]
        atr5 = sum(rngs) / len(rngs) if rngs else 0
        atr5_pct = atr5 / price * 100 if price else 0

        # ========= 确定性判定链 =========
        checks = []
        # ① 放量
        ok_vol = vol_ratio >= C.R2_VOL_RATIO
        checks.append(f"放量{vol_ratio:.1f}x≥{C.R2_VOL_RATIO}x: {'✓' if ok_vol else '✗'}")
        # ② 实体
        ok_body = abs(body_pct) >= C.R2_BODY_PCT
        checks.append(f"实体{abs(body_pct):.2f}%≥{C.R2_BODY_PCT}%: {'✓' if ok_body else '✗'}")
        if not (ok_vol and ok_body):
            return None

        # ③ 结构突破
        if body_pct > 0:
            broke = sig_c > ph and sig_o <= ph * 1.001   # 收盘破前高, 且从位下起爆
            level = ph
            kind = "向上破前高"
        else:
            broke = sig_c < pl and sig_o >= pl * 0.999
            level = pl
            kind = "向下破前低"
        over_pct = (sig_c - level) / level * 100 if body_pct > 0 else (level - sig_c) / level * 100
        checks.append(f"结构突破({kind} {level:.6g}): {'✓' if broke else '✗'} 越过{abs(over_pct):.2f}%")
        if not broke:
            return None   # 非结构突破 → 丢弃 (不做区间噪声)

        # ④ 趋势同向
        dir15 = 1 if mom15 >= 0 else -1
        d = 1 if body_pct > 0 else -1
        align = d == dir15
        if C.TREND_FILTER and not align:
            return None
        checks.append(f"15m趋势同向({'+' if mom15 >= 0 else '-'}{abs(mom15):.2f}%): {'✓' if align else '✗'}")

        tp_rec, sl_rec, hit_ref = adapt_tp(atr5_pct)
        # 资金费率
        funding = None
        try:
            fr = api_get(f"/fapi/v1/premiumIndex?symbol={sym}")
            funding = float(fr["lastFundingRate"]) * 100
        except Exception:
            pass
        return {
            "symbol": sym, "dir": "UP" if d == 1 else "DOWN", "price": price,
            "body_pct": body_pct, "vol_ratio": vol_ratio,
            "kind": kind, "level": level, "over_pct": abs(over_pct),
            "mom15": mom15, "mom1h": mom1h, "atr5_pct": atr5_pct,
            "tp_rec": tp_rec, "sl_rec": sl_rec, "hit_ref": hit_ref,
            "checks": checks, "chg24": t["chg24"], "extended": abs(t["chg24"]) > C.MAX_EXTENDED_24H,
            "sig_time": time.strftime("%H:%M", time.localtime(sig_ms / 1000)),
            "funding": funding,
        }
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--no-trend", action="store_true")
    ap.add_argument("--telegram", action="store_true")
    ap.add_argument("--risk", type=float, default=12,
                    help="单笔风险预算 % (止损×杠杆=该值)。默认12, 想开大杠杆可设 20/25, 但风险更大")
    ap.add_argument("--min-vol", default=None, help="24h成交额下限, 如 10m/5m (更宽=更多币)")
    ap.add_argument("--vol-min", type=float, default=C.R2_VOL_RATIO, help="放量倍数门槛(默认2x)")
    ap.add_argument("--body-min", type=float, default=C.R2_BODY_PCT, help="实体%门槛(默认0.5)")
    args = ap.parse_args()
    if args.no_trend:
        C.TREND_FILTER = False
    C.R2_VOL_RATIO = args.vol_min
    C.R2_BODY_PCT = args.body_min
    if args.min_vol:
        v = args.min_vol.lower()
        mul = {"k": 1e3, "m": 1e6, "b": 1e9}
        C.MIN_QUOTE_VOLUME = float(v.rstrip("kmb")) * mul.get(v[-1], 1)

    print(f"⏳ 全量扫描 量价能结构突破 ... 判定: 放量≥{C.R2_VOL_RATIO}x + 实体≥{C.R2_BODY_PCT}% "
          f"+ 收盘破1h结构位 + {'15m同向' if C.TREND_FILTER else '(不过滤趋势)'}")
    tickers = get_all_tickers()
    cands = {s: t for s, t in tickers.items() if is_target(s, t)}
    pool = list(cands.items())                       # 全量: 不漏掉刚启动的币
    print(f"  全市场 {len(tickers)} 个 USDT 永续 → 流动性筛选后深扫 {len(pool)} 个 (无 top-N 截断)")

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [(s, ex.submit(detect, s, t)) for s, t in pool]
    sigs = [(s, f.result()) for s, f in futs]
    sigs = [r for s, r in sigs if r]

    if not sigs:
        print("\n😴 当前没有币完成『量价能结构突破』的完整判定链。")
        print("   要求苛刻(放量+强体+破位+同向)是刻意为之——只给高确定性, 不给噪声。")
        return

    sigs.sort(key=lambda x: -(x["body_pct"] * x["vol_ratio"]))
    print(f"\n✅ 共 {len(sigs)} 个真突破信号 (统一交易卡格式):\n")
    for i, r in enumerate(sigs[: args.top], 1):
        entry = r["price"]
        up = r["dir"] == "UP"
        tp_price = entry * (1 + (1 if up else -1) * r["tp_rec"] / 100)
        sl_price = entry * (1 - (1 if up else -1) * r["sl_rec"] / 100)
        rec_lev = max(1, int(args.risk / r["sl_rec"]))
        win_pct = r["tp_rec"] * rec_lev
        risk_pct = r["sl_rec"] * rec_lev
        ext = "  ⚠️24h已动大" if r["extended"] else ""
        fund = f"{r['funding']:+.3f}%" if r["funding"] is not None else "-"
        print(f"[{i}] {r['symbol']} {r['dir']} @ {entry:.6g}  (信号{kind_ts(r)}){ext}")
        print(f"    入场 {entry:.6g} | TP {tp_price:.6g} ({'+' if up else '-'}{r['tp_rec']}%) "
              f"| SL {sl_price:.6g} ({'-' if up else '+'}{r['sl_rec']}%)")
        print(f"    杠杆 {rec_lev}x → 目标 +{win_pct:.1f}% / 止损亏 -{risk_pct:.0f}% "
              f"| 现价{entry:.6g} | ATR{r['atr5_pct']:.2f}% | 量能{r['vol_ratio']:.1f}x | 资金费率{fund}")
        print(f"    趋势: 15m{'↑' if r['mom15']>=0 else '↓'}{abs(r['mom15']):.2f}% "
              f"1h{'↑' if r['mom1h']>=0 else '↓'}{abs(r['mom1h']):.2f}% 24h{r['chg24']:+.1f}% "
              f"| 参考命中 {int(r['hit_ref']*100)}%")
        print(f"    时间: 到TP中位~5min → 10min未到TP也未止损就平(不傻等)")
        print(f"    判定链: " + " → ".join(r["checks"]))
        print()
    print("铁律: 止损距离×杠杆≤风险预算 · 命中率是回测值非保证 · paper先验证。")

    if args.telegram:
        try:
            import subprocess
            lines = [f"🔥 量价能突破 {time.strftime('%m-%d %H:%M')}"]
            for r in sigs[:6]:
                lines.append(f"{r['symbol']} {r['dir']} {r['kind']} TP{r['tp_rec']}% 命中{r['hit_ref']:.0f}%")
            subprocess.run(["python3", "/Users/daniel/bb-auto/scripts/telegram_push.py",
                            "--msg", "\n".join(lines)], timeout=30)
        except Exception:
            pass


def kind_ts(r):
    return time.strftime("%H:%M")


if __name__ == "__main__":
    main()
