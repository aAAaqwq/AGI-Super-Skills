#!/usr/bin/env python3
"""5minbtc Engine v5.7 半K线回测 — 在K线50%进度处预测

核心逻辑:
  - 对每根K线[i], 使用 candles[i-warmup:i] (200根已完成K线) 计算因子
  - 模拟progress=0.5的半K线状态:
    - close = K线中点价格 (open + (close-open)*0.5 的近似)
    - high/low 使用实际值的前50%估计
    - volume 使用实际值的50%
  - half_body因子在progress=0.5时激活(≥0.45)
  - ATR乘数×0.55, half_range=0.40 (已内置于v5.7引擎)
  - 对比实际方向: candles[i].c vs candles[i-1].c

用法:
  python run_backtest_v57.py                    # 完整回测 (每根K线)
  python run_backtest_v57.py --sample 6         # 每6根K线取1根 (30分钟间隔)
  python run_backtest_v57.py --days 180         # 只回测最近180天
  python run_backtest_v57.py --fast             # 快速模式: sample=12 + 最近180天
  python run_backtest_v57.py --full-report      # 输出完整因子分析报告
  python run_backtest_v57.py --compare          # 同时跑v5.6 baseline对比
"""

import json, math, os, sys, time, importlib.util, random
from collections import defaultdict
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ENGINE_V57 = os.path.join(SKILL_DIR, "5minbtc-engine-v5.7.py")
ENGINE_V56 = os.path.join(SKILL_DIR, "archive", "engines", "5minbtc-engine-v5.py")
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "btcusdt_5m.json")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

CST = timezone(timedelta(hours=8))
WARMUP = 200
PROGRESS = 0.5  # 半K线


# ======================== Engine Import ========================

def load_engine(path):
    """动态导入引擎模块"""
    if not os.path.exists(path):
        print(f"❌ 引擎文件不存在: {path}")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("engine", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ======================== Half-Candle Simulation ========================

def simulate_half_candle(raw):
    """模拟K线执行到50%时的状态
    
    策略: 用实际OHLCV的中间状态近似
    - open: 保持不变
    - close: 用 (open + actual_close) / 2 近似中点价格
    - high: 取 open 和 mid_close 中的较大值 * 1.001 (模拟半程波动)
    - low: 取 open 和 mid_close 中的较小值 * 0.999
    - volume: 实际量的50%
    """
    open_price = raw["o"]
    actual_close = raw["c"]
    actual_high = raw["h"]
    actual_low = raw["l"]
    actual_vol = raw["v"]
    
    # 中点价格: 假设价格线性移动(简化假设)
    mid_close = (open_price + actual_close) / 2
    
    # 半程high/low: 取实际范围的一半 + open
    range_full = actual_high - actual_low
    if actual_close >= open_price:
        # 阳线: 先跌后涨, 半程low更接近open, high在中间
        mid_low = min(open_price, mid_close) - range_full * 0.1
        mid_high = max(open_price, mid_close) + range_full * 0.15
    else:
        # 阴线: 先涨后跌, 半程high更接近open, low在中间
        mid_high = max(open_price, mid_close) + range_full * 0.1
        mid_low = min(open_price, mid_close) - range_full * 0.15
    
    # 用实际数据约束: 不超过实际范围
    mid_high = min(mid_high, actual_high)
    mid_low = max(mid_low, actual_low)
    
    # 至少包含open
    mid_high = max(mid_high, open_price)
    mid_low = min(mid_low, open_price)
    
    return {
        "o": open_price,
        "h": mid_high,
        "l": mid_low,
        "c": mid_close,
        "v": actual_vol * 0.5,
        "ct": raw["ct"],
        "ot": raw["ot"],
    }


def simulate_open_candle(raw):
    """模拟K线刚开盘(v5.6 baseline用)"""
    open_price = raw["o"]
    return {
        "o": open_price, "h": open_price, "l": open_price,
        "c": open_price, "v": 0.0, "ct": raw["ct"], "ot": raw["ot"],
    }


# ======================== Backtest Core ========================

def run_backtest_single(engine, candles, sample_rate=1, max_days=None,
                        progress=0.5, verbose=True):
    """单引擎回测"""
    if max_days and len(candles) > WARMUP + 100:
        cutoff_ms = candles[-1]["ct"] - max_days * 24 * 3600 * 1000
        start_idx = WARMUP
        for i in range(WARMUP, len(candles)):
            if candles[i]["ot"] >= cutoff_ms:
                start_idx = i
                break
        start_idx = max(start_idx, WARMUP)
    else:
        start_idx = WARMUP

    total = len(candles) - start_idx
    total_samples = (total + sample_rate - 1) // sample_rate

    use_half = (progress >= 0.45)

    if verbose:
        ver = "v5.7 半K线" if use_half else "v5.6 开盘"
        print(f"\n🔄 开始回测 ({ver}, progress={progress})")
        print(f"   数据范围: {_ts(candles[start_idx]['ot'])} ~ {_ts(candles[-1]['ct'])}")
        print(f"   总K线: {total:,} | 采样: {total_samples:,} (rate={sample_rate})")
        print()

    results = []
    t0 = time.time()

    for idx, i in enumerate(range(start_idx, len(candles), sample_rate)):
        window = candles[i - WARMUP:i]
        raw = candles[i]

        if use_half:
            simulated = simulate_half_candle(raw)
        else:
            simulated = simulate_open_candle(raw)

        full_candles = window + [simulated]
        closes = [c["c"] for c in full_candles]

        atr_val = engine.atr_wilder(full_candles)
        vr = engine.vol_regime_ratio(closes)

        bias, strength, confidence, score, factors, regime = engine.direction_rule_v5(
            full_candles, closes, atr_val, vr,
            depth_data=None, candle_progress=progress
        )

        actual_close = raw["c"]
        prev_close = candles[i - 1]["c"]
        price_chg = actual_close - prev_close
        actual_dir = "UP" if price_chg > 0 else ("DOWN" if price_chg < 0 else "FLAT")

        if bias == "neutral":
            dir_correct = None
        elif bias == "bull" and actual_dir == "UP":
            dir_correct = True
        elif bias == "bear" and actual_dir == "DOWN":
            dir_correct = True
        else:
            dir_correct = False

        mom_val = factors.get("momentum", 0)
        decel_val = factors.get("decel", 0)
        conflict = abs(mom_val) > 0.7 and abs(decel_val) > 0.8 and mom_val * decel_val < 0

        half_body_val = factors.get("half_body", 0)

        results.append({
            "idx": i,
            "ts": raw["ot"],
            "open": raw["o"],
            "sim_close": simulated["c"],
            "actual_close": actual_close,
            "prev_close": prev_close,
            "price_chg": price_chg,
            "actual_dir": actual_dir,
            "bias": bias,
            "strength": strength,
            "confidence": confidence,
            "score": score,
            "regime": regime,
            "dir_correct": dir_correct,
            "conflict": conflict,
            "half_body": round(half_body_val, 4),
            "factors": {k: round(v, 4) if isinstance(v, float) else v
                        for k, v in factors.items()},
        })

        if verbose and (idx + 1) % max(1, total_samples // 20) == 0:
            elapsed = time.time() - t0
            pct = (idx + 1) / total_samples * 100
            eta = elapsed / (idx + 1) * (total_samples - idx - 1)
            recent = [r for r in results[-200:] if r["dir_correct"] is not None]
            if recent:
                acc = sum(1 for r in recent if r["dir_correct"]) / len(recent) * 100
            else:
                acc = 0
            print(f"   [{pct:5.1f}%] {idx+1:,}/{total_samples:,} | "
                  f"近期方向准确率: {acc:.1f}% | ETA: {eta:.0f}s")

    elapsed = time.time() - t0
    if verbose:
        print(f"\n✅ 回测完成! 耗时 {elapsed:.1f}s ({len(results):,} 条预测)")

    return results


# ======================== Statistics ========================

def compute_stats(results, label="v5.7"):
    if not results:
        return {}

    directional = [r for r in results if r["dir_correct"] is not None]
    n_dir = len(directional)
    n_correct = sum(1 for r in directional if r["dir_correct"])

    bull_all = [r for r in directional if r["bias"] == "bull"]
    bear_all = [r for r in directional if r["bias"] == "bear"]
    neutral_all = [r for r in results if r["bias"] == "neutral"]
    bull_correct = sum(1 for r in bull_all if r["dir_correct"])
    bear_correct = sum(1 for r in bear_all if r["dir_correct"])

    regime_stats = {}
    for rg in ["TREND", "RANGE", "HIGH_VOL", "LOW_VOL"]:
        subset = [r for r in directional if r["regime"] == rg]
        if subset:
            correct = sum(1 for r in subset if r["dir_correct"])
            regime_stats[rg] = {
                "n": len(subset), "correct": correct,
                "accuracy": round(correct / len(subset) * 100, 1),
            }

    conf_buckets = defaultdict(lambda: {"n": 0, "correct": 0})
    for r in directional:
        bucket = (r["confidence"] // 5) * 5
        conf_buckets[bucket]["n"] += 1
        if r["dir_correct"]:
            conf_buckets[bucket]["correct"] += 1
    conf_stats = {}
    for bucket in sorted(conf_buckets.keys()):
        b = conf_buckets[bucket]
        conf_stats[f"{bucket}-{bucket+4}"] = {
            "n": b["n"],
            "accuracy": round(b["correct"] / b["n"] * 100, 1) if b["n"] > 0 else 0,
        }

    monthly = defaultdict(lambda: {"n": 0, "correct": 0, "bull": 0, "bear": 0})
    for r in directional:
        month = time.strftime("%Y-%m", time.localtime(r["ts"] / 1000))
        monthly[month]["n"] += 1
        if r["dir_correct"]:
            monthly[month]["correct"] += 1
        if r["bias"] == "bull":
            monthly[month]["bull"] += 1
        else:
            monthly[month]["bear"] += 1
    monthly_stats = {}
    for m in sorted(monthly.keys()):
        monthly_stats[m] = {
            "n": monthly[m]["n"],
            "accuracy": round(monthly[m]["correct"] / monthly[m]["n"] * 100, 1),
            "bull_ratio": round(monthly[m]["bull"] / monthly[m]["n"] * 100, 1),
        }

    streaks = _compute_streaks(directional)

    actual_up = sum(1 for r in directional if r["actual_dir"] == "UP")
    baseline_bull = round(actual_up / n_dir * 100, 1) if n_dir > 0 else 0
    baseline_bear = round((n_dir - actual_up) / n_dir * 100, 1) if n_dir > 0 else 0

    conflict_all = [r for r in directional if r.get("conflict")]
    conflict_correct = sum(1 for r in conflict_all if r["dir_correct"])

    factor_contribution = _analyze_factors(directional)

    # half_body 特殊分析
    half_body_stats = _analyze_half_body(directional)

    return {
        "label": label,
        "meta": {
            "total_predictions": len(results),
            "directional_predictions": n_dir,
            "neutral_predictions": len(neutral_all),
            "backtest_period": (
                f"{_ts(results[0]['ts'])} ~ {_ts(results[-1]['ts'])}"
            ),
        },
        "overall": {
            "direction_accuracy": round(n_correct / n_dir * 100, 1) if n_dir > 0 else 0,
            "correct": n_correct,
            "wrong": n_dir - n_correct,
        },
        "bias_breakdown": {
            "bull": {"n": len(bull_all), "correct": bull_correct,
                     "accuracy": round(bull_correct / len(bull_all) * 100, 1) if bull_all else 0},
            "bear": {"n": len(bear_all), "correct": bear_correct,
                     "accuracy": round(bear_correct / len(bear_all) * 100, 1) if bear_all else 0},
            "neutral_n": len(neutral_all),
        },
        "baseline": {
            "always_bull_accuracy": baseline_bull,
            "always_bear_accuracy": baseline_bear,
            "random_50": 50.0,
            "edge_vs_random": round(n_correct / n_dir * 100 - 50, 1) if n_dir > 0 else 0,
        },
        "regime_stats": regime_stats,
        "confidence_stats": conf_stats,
        "monthly_stats": monthly_stats,
        "streaks": streaks,
        "conflict_detection": {
            "triggered_n": len(conflict_all),
            "accuracy": round(conflict_correct / len(conflict_all) * 100, 1) if conflict_all else 0,
            "overall_accuracy": round(n_correct / n_dir * 100, 1) if n_dir > 0 else 0,
        },
        "factor_contribution": factor_contribution,
        "half_body_analysis": half_body_stats,
    }


def _compute_streaks(directional):
    max_win, max_lose = 0, 0
    current_win, current_lose = 0, 0
    for r in directional:
        if r["dir_correct"]:
            current_win += 1
            current_lose = 0
            max_win = max(max_win, current_win)
        else:
            current_lose += 1
            current_win = 0
            max_lose = max(max_lose, current_lose)
    return {"max_win_streak": max_win, "max_lose_streak": max_lose}


def _analyze_factors(directional):
    factor_names = ["momentum", "meanrev", "rsi", "volume", "fatigue",
                    "imbalance", "microprice", "decel", "position",
                    "v_reversal", "vol_breakout", "half_body"]
    analysis = {}
    for fn in factor_names:
        correct_vals = [abs(r["factors"].get(fn, 0)) for r in directional
                       if r["dir_correct"] and fn in r.get("factors", {})]
        wrong_vals = [abs(r["factors"].get(fn, 0)) for r in directional
                     if not r["dir_correct"] and fn in r.get("factors", {})]
        avg_c = sum(correct_vals) / len(correct_vals) if correct_vals else 0
        avg_w = sum(wrong_vals) / len(wrong_vals) if wrong_vals else 0
        pos_signals = [r for r in directional if r["factors"].get(fn, 0) > 0.1]
        if pos_signals:
            pos_up = sum(1 for r in pos_signals if r["actual_dir"] == "UP")
            consistency = round(pos_up / len(pos_signals) * 100, 1)
        else:
            consistency = None
        analysis[fn] = {
            "avg_when_correct": round(avg_c, 4),
            "avg_when_wrong": round(avg_w, 4),
            "signal_strength_diff": round(avg_c - avg_w, 4),
            "directional_consistency": consistency,
            "n_positive_signals": len(pos_signals) if pos_signals else 0,
        }
    return analysis


def _analyze_half_body(directional):
    """half_body因子专项分析"""
    activated = [r for r in directional if abs(r.get("half_body", 0)) > 0.01]
    if not activated:
        return {"activated_n": 0}

    activated_correct = sum(1 for r in activated if r["dir_correct"])
    
    # 按half_body值分桶
    strong_bull = [r for r in activated if r["half_body"] > 0.3]
    strong_bear = [r for r in activated if r["half_body"] < -0.3]
    weak = [r for r in activated if abs(r["half_body"]) <= 0.3]
    
    def acc(lst):
        if not lst:
            return {"n": 0, "accuracy": 0}
        c = sum(1 for r in lst if r["dir_correct"])
        return {"n": len(lst), "accuracy": round(c / len(lst) * 100, 1)}
    
    # half_body方向一致性: half_body>0时实际UP的比例
    hb_pos = [r for r in activated if r["half_body"] > 0.05]
    hb_neg = [r for r in activated if r["half_body"] < -0.05]
    
    hb_pos_up = sum(1 for r in hb_pos if r["actual_dir"] == "UP") if hb_pos else 0
    hb_neg_down = sum(1 for r in hb_neg if r["actual_dir"] == "DOWN") if hb_neg else 0
    
    return {
        "activated_n": len(activated),
        "activated_pct": round(len(activated) / len(directional) * 100, 1) if directional else 0,
        "activated_accuracy": round(activated_correct / len(activated) * 100, 1),
        "strong_bull": acc(strong_bull),
        "strong_bear": acc(strong_bear),
        "weak_signal": acc(weak),
        "direction_consistency": {
            "pos_predicts_up": round(hb_pos_up / len(hb_pos) * 100, 1) if hb_pos else 0,
            "neg_predicts_down": round(hb_neg_down / len(hb_neg) * 100, 1) if hb_neg else 0,
        },
    }


# ======================== Report ========================

def print_report(stats, verbose=False):
    s = stats
    o = s["overall"]
    m = s["meta"]
    label = s.get("label", "v5.7")

    print("\n" + "=" * 65)
    print(f"📊 5minbtc {label} — 半K线回测报告")
    print("=" * 65)

    print(f"\n📅 回测区间: {m['backtest_period']}")
    print(f"   总预测: {m['total_predictions']:,} | "
          f"方向性: {m['directional_predictions']:,} | "
          f"Neutral: {m['neutral_predictions']:,}")

    print(f"\n🎯 方向准确率: {o['direction_accuracy']}% "
          f"({o['correct']:,}/{m['directional_predictions']:,})")

    bl = s["baseline"]
    edge_emoji = "✅" if bl['edge_vs_random'] > 0 else "❌"
    print(f"   vs Always-Bull: {bl['always_bull_accuracy']}%")
    print(f"   vs Always-Bear: {bl['always_bear_accuracy']}%")
    print(f"   vs Random(50%): {bl['edge_vs_random']:+.1f}pp edge {edge_emoji}")

    bb = s["bias_breakdown"]
    print(f"\n🐂 Bull: {bb['bull']['accuracy']}% ({bb['bull']['correct']}/{bb['bull']['n']})")
    print(f"🐻 Bear: {bb['bear']['accuracy']}% ({bb['bear']['correct']}/{bb['bear']['n']})")
    if bb["neutral_n"] > 0:
        print(f"⚖️  Neutral: {bb['neutral_n']}")

    print(f"\n🌊 Regime 分析:")
    for rg, rs in s["regime_stats"].items():
        bar = "█" * int(rs["accuracy"] / 2) + "░" * (50 - int(rs["accuracy"] / 2))
        print(f"   {rg:10s}: {rs['accuracy']:5.1f}% ({rs['correct']}/{rs['n']:,}) {bar}")

    cd = s["conflict_detection"]
    if cd["triggered_n"] > 0:
        print(f"\n⚡ Momentum/Decel 冲突检测:")
        print(f"   触发次数: {cd['triggered_n']:,}")
        print(f"   冲突时准确率: {cd['accuracy']}% (整体: {cd['overall_accuracy']}%)")

    # half_body 专项
    hb = s.get("half_body_analysis", {})
    if hb.get("activated_n", 0) > 0:
        print(f"\n🔬 half_body 因子分析:")
        print(f"   激活次数: {hb['activated_n']:,} ({hb['activated_pct']}%)")
        print(f"   激活时准确率: {hb['activated_accuracy']}%")
        if hb.get("strong_bull", {}).get("n", 0) > 0:
            print(f"   强bull信号(>0.3): {hb['strong_bull']['accuracy']}% ({hb['strong_bull']['n']})")
        if hb.get("strong_bear", {}).get("n", 0) > 0:
            print(f"   强bear信号(<-0.3): {hb['strong_bear']['accuracy']}% ({hb['strong_bear']['n']})")
        dc = hb.get("direction_consistency", {})
        if dc:
            print(f"   方向一致性: pos→UP={dc.get('pos_predicts_up', 0)}%, neg→DOWN={dc.get('neg_predicts_down', 0)}%")

    print(f"\n📈 置信度分层:")
    for bucket, cs in s["confidence_stats"].items():
        if cs["n"] >= 10:
            marker = "✅" if cs["accuracy"] > 55 else ("⚠️" if cs["accuracy"] > 50 else "❌")
            print(f"   conf {bucket}: {cs['accuracy']:5.1f}% ({cs['n']:,}) {marker}")

    ms = s["monthly_stats"]
    if len(ms) > 1:
        print(f"\n📅 月度趋势:")
        for month, md in ms.items():
            bar = "▓" * int(md["accuracy"] / 2)
            marker = "✅" if md["accuracy"] > 50 else "❌"
            print(f"   {month}: {md['accuracy']:5.1f}% ({md['n']:>5,}) bull={md['bull_ratio']:.0f}% {bar} {marker}")

    sk = s["streaks"]
    print(f"\n🔥 最长连胜: {sk['max_win_streak']} | 💀 最长连败: {sk['max_lose_streak']}")

    if verbose:
        print(f"\n🔬 因子贡献分析:")
        fc = s["factor_contribution"]
        sorted_factors = sorted(fc.items(),
                               key=lambda x: abs(x[1]["signal_strength_diff"]),
                               reverse=True)
        for fn, fa in sorted_factors:
            diff_marker = "↑" if fa["signal_strength_diff"] > 0 else "↓"
            cons_str = (f"一致性={fa['directional_consistency']}%"
                       if fa["directional_consistency"] is not None else "N/A")
            print(f"   {fn:15s}: 正确时avg={fa['avg_when_correct']:.3f} "
                  f"错误时avg={fa['avg_when_wrong']:.3f} "
                  f"diff={fa['signal_strength_diff']:+.3f}{diff_marker} "
                  f"{cons_str}")

    print("\n" + "=" * 65)


def print_comparison(stats_57, stats_56):
    """v5.7 vs v5.6 对比"""
    o57 = stats_57["overall"]
    o56 = stats_56["overall"]
    m57 = stats_57["meta"]
    m56 = stats_56["meta"]

    print("\n" + "=" * 65)
    print("📊 v5.7 半K线 vs v5.6 开盘 — A/B 对比")
    print("=" * 65)
    print(f"\n{'指标':<25s} {'v5.7 半K线':>12s} {'v5.6 开盘':>12s} {'差值':>10s}")
    print("-" * 65)
    
    acc57 = o57["direction_accuracy"]
    acc56 = o56["direction_accuracy"]
    print(f"{'方向准确率':<25s} {acc57:>11.1f}% {acc56:>11.1f}% {acc57-acc56:>+9.1f}pp")
    
    bl57 = stats_57["baseline"]["edge_vs_random"]
    bl56 = stats_56["baseline"]["edge_vs_random"]
    print(f"{'Edge vs Random':<25s} {bl57:>+10.1f}pp {bl56:>+10.1f}pp {bl57-bl56:>+9.1f}pp")
    
    bb57 = stats_57["bias_breakdown"]
    bb56 = stats_56["bias_breakdown"]
    print(f"{'Bull准确率':<25s} {bb57['bull']['accuracy']:>11.1f}% {bb56['bull']['accuracy']:>11.1f}%")
    print(f"{'Bear准确率':<25s} {bb57['bear']['accuracy']:>11.1f}% {bb56['bear']['accuracy']:>11.1f}%")
    print(f"{'Neutral数':<25s} {bb57['neutral_n']:>12,} {bb56['neutral_n']:>12,}")
    
    sk57 = stats_57["streaks"]
    sk56 = stats_56["streaks"]
    print(f"{'最长连胜':<25s} {sk57['max_win_streak']:>12} {sk56['max_win_streak']:>12}")
    print(f"{'最长连败':<25s} {sk57['max_lose_streak']:>12} {sk56['max_lose_streak']:>12}")
    
    # 月度对比
    ms57 = stats_57["monthly_stats"]
    ms56 = stats_56["monthly_stats"]
    common_months = sorted(set(ms57.keys()) & set(ms56.keys()))
    if common_months:
        print(f"\n📅 月度准确率对比:")
        print(f"   {'月份':<12s} {'v5.7':>8s} {'v5.6':>8s} {'差值':>8s}")
        for m in common_months:
            a57 = ms57[m]["accuracy"]
            a56 = ms56[m]["accuracy"]
            emoji = "✅" if a57 > a56 else "❌"
            print(f"   {m:<12s} {a57:>7.1f}% {a56:>7.1f}% {a57-a56:>+7.1f}pp {emoji}")

    print("\n" + "=" * 65)


# ======================== Helpers ========================

def _ts(ms):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000))


# ======================== Main ========================

def main():
    args = sys.argv[1:]

    sample_rate = 1
    max_days = 180  # 默认半年
    verbose = "--full-report" in args
    compare_mode = "--compare" in args

    if "--fast" in args:
        sample_rate = 6
        max_days = 180
    if "--very-fast" in args:
        sample_rate = 12
        max_days = 180

    for i, a in enumerate(args):
        if a == "--sample" and i + 1 < len(args):
            sample_rate = int(args[i + 1])
        elif a.startswith("--sample="):
            sample_rate = int(a.split("=")[1])
        elif a == "--days" and i + 1 < len(args):
            max_days = int(args[i + 1])
        elif a.startswith("--days="):
            max_days = int(a.split("=")[1])

    # 加载数据
    if not os.path.exists(DATA_FILE):
        print("❌ 无数据文件, 请先运行: python fetch_data.py")
        sys.exit(1)

    print("📂 加载K线数据...")
    with open(DATA_FILE) as f:
        candles = json.load(f)
    print(f"   {len(candles):,} 根K线 | {_ts(candles[0]['ot'])} ~ {_ts(candles[-1]['ct'])}")
    if max_days:
        print(f"   限制回测最近 {max_days} 天")

    # ---- v5.7 半K线回测 ----
    print("\n⚙️  加载引擎 v5.7 (半K线, progress=0.5)...")
    engine57 = load_engine(ENGINE_V57)
    results57 = run_backtest_single(
        engine57, candles,
        sample_rate=sample_rate,
        max_days=max_days,
        progress=PROGRESS,
        verbose=True,
    )
    stats57 = compute_stats(results57, label="v5.7 半K线")

    # ---- v5.6 baseline (可选) ----
    stats56 = None
    if compare_mode:
        print("\n⚙️  加载引擎 v5.6 (开盘 baseline, progress=0.01)...")
        engine56 = load_engine(ENGINE_V56)
        results56 = run_backtest_single(
            engine56, candles,
            sample_rate=sample_rate,
            max_days=max_days,
            progress=0.01,
            verbose=True,
        )
        stats56 = compute_stats(results56, label="v5.6 开盘")

    # 输出报告
    print_report(stats57, verbose=verbose)

    if stats56:
        print_comparison(stats57, stats56)
        print_report(stats56, verbose=False)

    # 保存结果
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(CST).strftime("%Y%m%d_%H%M")
    
    output = {
        "timestamp": ts,
        "engine": "v5.7 半K线",
        "sample_rate": sample_rate,
        "max_days": max_days,
        "progress": PROGRESS,
        "stats_v57": stats57,
        "stats_v56": stats56,
        "predictions_count": len(results57),
    }
    
    result_file = os.path.join(RESULTS_DIR, f"backtest_v57_{ts}.json")
    with open(result_file, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=None)
    
    summary_file = os.path.join(RESULTS_DIR, "latest_v57_summary.json")
    with open(summary_file, "w") as f:
        json.dump({
            "timestamp": ts,
            "stats_v57": stats57,
            "stats_v56": stats56,
        }, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(result_file) / 1024 / 1024
    print(f"\n💾 结果已保存:")
    print(f"   完整结果: {result_file} ({size_mb:.1f} MB)")
    print(f"   摘要文件: {summary_file}")

    return stats57


if __name__ == "__main__":
    main()
