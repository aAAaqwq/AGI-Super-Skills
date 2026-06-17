#!/usr/bin/env python3
"""5minbtc Engine v5.6 Backtester — 历史回测引擎

核心逻辑:
  - 对每根K线[i], 使用 candles[i-warmup:i] (200根已完成K线) 计算因子
  - 附加 candles[i] 并屏蔽为 "刚开盘" 状态 (c=h=l=open, v=0)
  - 用引擎 v5.6 全套因子体系预测方向
  - 对比实际方向: candles[i].c vs candles[i-1].c

用法:
  python run_backtest.py                    # 完整回测 (每根K线)
  python run_backtest.py --sample 6         # 每6根K线取1根 (30分钟间隔)
  python run_backtest.py --days 90          # 只回测最近90天
  python run_backtest.py --fast             # 快速模式: sample=12 + 最近180天
  python run_backtest.py --full-report      # 输出完整因子分析报告
"""

import json, math, os, sys, time, importlib.util
from collections import defaultdict
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ENGINE_PATH = os.path.join(SKILL_DIR, "5minbtc-engine-v5.py")
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "btcusdt_5m.json")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

CST = timezone(timedelta(hours=8))
WARMUP = 200  # 因子计算所需的最少历史K线数


# ======================== Engine Import ========================

def load_engine():
    """动态导入引擎模块（避免 __name__ == '__main__' 执行 run()）"""
    if not os.path.exists(ENGINE_PATH):
        print(f"❌ 引擎文件不存在: {ENGINE_PATH}")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("engine_v5", ENGINE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ======================== Backtest Core ========================

def run_backtest(engine, candles, sample_rate=1, max_days=None, 
                 candle_progress=0.01, verbose=True):
    """
    回测主循环
    
    参数:
      engine: 引擎模块
      candles: K线数据列表
      sample_rate: 采样率 (1=每根, 6=每30分钟, 12=每小时)
      max_days: 最多回测多少天 (None=全部)
      verbose: 是否输出进度
    
    返回:
      results: 预测结果列表
      stats: 统计摘要
    """
    # 截取时间范围
    if max_days and len(candles) > WARMUP + 100:
        cutoff_ms = candles[-1]["ct"] - max_days * 24 * 3600 * 1000
        start_idx = WARMUP
        for i in range(WARMUP, len(candles)):
            if candles[i]["ot"] >= cutoff_ms:
                start_idx = i
                break
        # 确保至少有 warmup 根历史
        start_idx = max(start_idx, WARMUP)
    else:
        start_idx = WARMUP

    total = len(candles) - start_idx
    total_samples = (total + sample_rate - 1) // sample_rate

    if verbose:
        print(f"\n🔄 开始回测")
        print(f"   数据范围: {_ts(candles[start_idx]['ot'])} ~ {_ts(candles[-1]['ct'])}")
        print(f"   总K线: {total:,} | 采样: {total_samples:,} (rate={sample_rate})")
        print(f"   引擎: v{getattr(engine, '__doc__', '').split('v5.')[1].split()[0] if 'v5.' in getattr(engine, '__doc__', '') else '5.6'}")
        print()

    results = []
    t0 = time.time()

    for idx, i in enumerate(range(start_idx, len(candles), sample_rate)):
        # 200 根已完成 K线
        window = candles[i - WARMUP:i]

        # 当前K线模拟"刚开盘" — 屏蔽 price/volume 信息
        raw = candles[i]
        open_price = raw["o"]
        simulated = {
            "o": open_price, "h": open_price, "l": open_price,
            "c": open_price, "v": 0.0, "ct": raw["ct"], "ot": raw["ot"]
        }

        full_candles = window + [simulated]
        closes = [c["c"] for c in full_candles]

        # ---- 指标计算 (与引擎 run() 一致) ----
        atr_val = engine.atr_wilder(full_candles)
        vr = engine.vol_regime_ratio(closes)

        # ---- 方向预测 (无 orderbook, candle_progress 由参数控制) ----
        bias, strength, confidence, score, factors, regime = engine.direction_rule_v5(
            full_candles, closes, atr_val, vr,
            depth_data=None, candle_progress=candle_progress
        )

        # ---- 实际结果 ----
        actual_close = raw["c"]
        prev_close = candles[i - 1]["c"]
        price_chg = actual_close - prev_close
        actual_dir = "UP" if price_chg > 0 else ("DOWN" if price_chg < 0 else "FLAT")

        # 方向正确性
        if bias == "neutral":
            dir_correct = None  # neutral 不计入方向统计
        elif bias == "bull" and actual_dir == "UP":
            dir_correct = True
        elif bias == "bear" and actual_dir == "DOWN":
            dir_correct = True
        else:
            dir_correct = False

        # 冲突检测标记
        mom_val = factors.get("momentum", 0)
        decel_val = factors.get("decel", 0)
        conflict = abs(mom_val) > 0.7 and abs(decel_val) > 0.8 and mom_val * decel_val < 0

        results.append({
            "idx": i,
            "ts": raw["ot"],
            "open": open_price,
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
            "factors": {k: round(v, 4) if isinstance(v, float) else v
                        for k, v in factors.items()},
        })

        # 进度报告
        if verbose and (idx + 1) % max(1, total_samples // 20) == 0:
            elapsed = time.time() - t0
            pct = (idx + 1) / total_samples * 100
            eta = elapsed / (idx + 1) * (total_samples - idx - 1)
            # 实时方向准确率
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

    stats = compute_stats(results)
    return results, stats


# ======================== Statistics ========================

def compute_stats(results):
    """计算全面统计"""
    if not results:
        return {}

    # ---- 基础统计 ----
    directional = [r for r in results if r["dir_correct"] is not None]
    n_dir = len(directional)
    n_correct = sum(1 for r in directional if r["dir_correct"])
    n_wrong = n_dir - n_correct

    # ---- Bias 分布 ----
    bull_all = [r for r in directional if r["bias"] == "bull"]
    bear_all = [r for r in directional if r["bias"] == "bear"]
    neutral_all = [r for r in results if r["bias"] == "neutral"]
    bull_correct = sum(1 for r in bull_all if r["dir_correct"])
    bear_correct = sum(1 for r in bear_all if r["dir_correct"])

    # ---- Regime 统计 ----
    regime_stats = {}
    for rg in ["TREND", "RANGE", "HIGH_VOL", "LOW_VOL"]:
        subset = [r for r in directional if r["regime"] == rg]
        if subset:
            correct = sum(1 for r in subset if r["dir_correct"])
            regime_stats[rg] = {
                "n": len(subset),
                "correct": correct,
                "accuracy": round(correct / len(subset) * 100, 1),
            }

    # ---- 置信度分层 ----
    conf_buckets = defaultdict(lambda: {"n": 0, "correct": 0})
    for r in directional:
        bucket = (r["confidence"] // 5) * 5  # 5分一档
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

    # ---- 月度统计 ----
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

    # ---- 连胜/连败 ----
    streaks = _compute_streaks(directional)
    
    # ---- Baseline 对比 ----
    actual_up = sum(1 for r in directional if r["actual_dir"] == "UP")
    baseline_bull = round(actual_up / n_dir * 100, 1) if n_dir > 0 else 0
    baseline_bear = round((n_dir - actual_up) / n_dir * 100, 1) if n_dir > 0 else 0

    # ---- 冲突检测统计 ----
    conflict_all = [r for r in directional if r.get("conflict")]
    conflict_correct = sum(1 for r in conflict_all if r["dir_correct"])

    # ---- 因子贡献分析 ----
    factor_contribution = _analyze_factors(directional)

    # ---- 合成 ----
    stats = {
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
            "wrong": n_wrong,
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
    }
    return stats


def _compute_streaks(directional):
    """计算连胜/连败"""
    win_streak, lose_streak = 0, 0
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

    return {
        "max_win_streak": max_win,
        "max_lose_streak": max_lose,
    }


def _analyze_factors(directional):
    """分析每个因子对正确/错误预测的贡献"""
    factor_names = ["momentum", "meanrev", "rsi", "volume", "fatigue",
                    "imbalance", "microprice", "decel", "position",
                    "v_reversal", "vol_breakout"]

    analysis = {}
    for fn in factor_names:
        correct_vals = [abs(r["factors"].get(fn, 0)) for r in directional
                       if r["dir_correct"] and fn in r.get("factors", {})]
        wrong_vals = [abs(r["factors"].get(fn, 0)) for r in directional
                     if not r["dir_correct"] and fn in r.get("factors", {})]

        avg_c = sum(correct_vals) / len(correct_vals) if correct_vals else 0
        avg_w = sum(wrong_vals) / len(wrong_vals) if wrong_vals else 0

        # 因子方向一致性: 因子值>0时实际上涨的比例
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


# ======================== Report ========================

def print_report(stats, verbose=False):
    """输出回测报告"""
    s = stats
    o = s["overall"]
    m = s["meta"]

    print("\n" + "=" * 65)
    print("📊 5minbtc Engine v5.6 — 回测报告")
    print("=" * 65)

    print(f"\n📅 回测区间: {m['backtest_period']}")
    print(f"   总预测: {m['total_predictions']:,} | "
          f"方向性: {m['directional_predictions']:,} | "
          f"Neutral: {m['neutral_predictions']:,}")

    # ---- 总体方向准确率 ----
    print(f"\n🎯 方向准确率: {o['direction_accuracy']}% "
          f"({o['correct']:,}/{m['directional_predictions']:,})")

    # ---- vs Baseline ----
    bl = s["baseline"]
    print(f"   vs Always-Bull: {bl['always_bull_accuracy']}%")
    print(f"   vs Always-Bear: {bl['always_bear_accuracy']}%")
    print(f"   vs Random(50%): +{bl['edge_vs_random']}pp edge")

    # ---- Bull/Bear 分项 ----
    bb = s["bias_breakdown"]
    print(f"\n🐂 Bull: {bb['bull']['accuracy']}% ({bb['bull']['correct']}/{bb['bull']['n']})")
    print(f"🐻 Bear: {bb['bear']['accuracy']}% ({bb['bear']['correct']}/{bb['bear']['n']})")
    if bb["neutral_n"] > 0:
        print(f"⚖️  Neutral: {bb['neutral_n']}")

    # ---- Regime ----
    print(f"\n🌊 Regime 分析:")
    for rg, rs in s["regime_stats"].items():
        bar = "█" * int(rs["accuracy"] / 2) + "░" * (50 - int(rs["accuracy"] / 2))
        print(f"   {rg:10s}: {rs['accuracy']:5.1f}% ({rs['correct']}/{rs['n']:,}) {bar}")

    # ---- 冲突检测 ----
    cd = s["conflict_detection"]
    if cd["triggered_n"] > 0:
        print(f"\n⚡ Momentum/Decel 冲突检测:")
        print(f"   触发次数: {cd['triggered_n']:,}")
        print(f"   冲突时准确率: {cd['accuracy']}% (整体: {cd['overall_accuracy']}%)")

    # ---- 置信度 ----
    print(f"\n📈 置信度分层:")
    for bucket, cs in s["confidence_stats"].items():
        if cs["n"] >= 10:
            marker = "✅" if cs["accuracy"] > 55 else ("⚠️" if cs["accuracy"] > 50 else "❌")
            print(f"   conf {bucket}: {cs['accuracy']:5.1f}% ({cs['n']:,}) {marker}")

    # ---- 月度趋势 ----
    ms = s["monthly_stats"]
    if len(ms) > 1:
        print(f"\n📅 月度趋势:")
        for month, md in ms.items():
            bar = "▓" * int(md["accuracy"] / 2)
            print(f"   {month}: {md['accuracy']:5.1f}% ({md['n']:>5,}) bull={md['bull_ratio']:.0f}% {bar}")

    # ---- 连胜/连败 ----
    sk = s["streaks"]
    print(f"\n🔥 最长连胜: {sk['max_win_streak']} | 💀 最长连败: {sk['max_lose_streak']}")

    # ---- 因子分析 (verbose) ----
    if verbose:
        print(f"\n🔬 因子贡献分析:")
        fc = s["factor_contribution"]
        # 按信号强度差异排序
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


def save_results(results, stats, sample_rate, max_days):
    """保存回测结果到文件"""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    ts = datetime.now(CST).strftime("%Y%m%d_%H%M")
    result_file = os.path.join(RESULTS_DIR, f"backtest_{ts}.json")
    summary_file = os.path.join(RESULTS_DIR, "latest_summary.json")

    # 完整结果 (不含因子详情以节省空间, 可选)
    output = {
        "timestamp": ts,
        "engine": "v5.6",
        "sample_rate": sample_rate,
        "max_days": max_days,
        "stats": stats,
        "predictions_count": len(results),
        # 完整预测列表 — 太大则只保留统计
        "predictions": results if len(results) <= 50000 else [
            r for i, r in enumerate(results) if i % (len(results) // 50000 + 1) == 0
        ],
    }

    with open(result_file, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=None)

    # 摘要文件 (总是最新)
    with open(summary_file, "w") as f:
        json.dump({"timestamp": ts, "stats": stats}, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(result_file) / 1024 / 1024
    print(f"\n💾 结果已保存:")
    print(f"   完整结果: {result_file} ({size_mb:.1f} MB)")
    print(f"   摘要文件: {summary_file}")

    return result_file


# ======================== Helpers ========================

def _ts(ms):
    """毫秒时间戳转可读字符串"""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000))


# ======================== Main ========================

def main():
    args = sys.argv[1:]

    # 参数解析
    sample_rate = 1
    max_days = None
    candle_progress = 0.01  # 默认: K线刚开盘 (最保守)
    verbose = "--full-report" in args
    force = "--force" in args

    if "--fast" in args:
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
        elif a == "--progress" and i + 1 < len(args):
            candle_progress = float(args[i + 1])
        elif a.startswith("--progress="):
            candle_progress = float(a.split("=")[1])

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

    # 加载引擎
    print("⚙️  加载引擎 v5.6...")
    engine = load_engine()
    print(f"   OK — {ENGINE_PATH}")

    # 运行回测
    results, stats = run_backtest(
        engine, candles,
        sample_rate=sample_rate,
        max_days=max_days,
        candle_progress=candle_progress,
        verbose=True,
    )

    # 输出报告
    print_report(stats, verbose=verbose)

    # 保存结果
    save_results(results, stats, sample_rate, max_days)

    return stats


if __name__ == "__main__":
    main()
