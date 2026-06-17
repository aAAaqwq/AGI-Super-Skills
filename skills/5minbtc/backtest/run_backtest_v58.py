#!/usr/bin/env python3
"""5minbtc Engine v5.7 回测 — 用真实1分钟K线构建半K线状态 (零前视偏差)

核心改进 (v5.8回测方法):
  - 对每根5分钟K线[i], 找到其对应的**前2-3根1分钟K线**
  - 用这些1分钟K线的真实OHLCV构建"半K线"状态
  - 模拟实盘场景: 在第3分钟时, 你确实看到了前2.5分钟的价格走势
  - 零前视偏差 — 不使用当前5分钟K线的close/high/low

对比:
  - v5.6 baseline: progress=0.01 (开盘预测)
  - v5.7 有前视偏差: 用 (open+actual_close)/2 (已知最终方向)
  - v5.7 无偏差(旧): 用前一根5min K线body模拟
  - **v5.8 (本脚本): 用真实1min K线前2根** ← 唯一正确方法

用法:
  python run_backtest_v58.py                    # 完整回测
  python run_backtest_v58.py --sample 6         # 每6根取1根 (30分钟间隔)
  python run_backtest_v58.py --fast             # 快速模式: sample=6 + 180天
  python run_backtest_v58.py --compare          # 同时跑v5.6 baseline
  python run_backtest_v58.py --half 3           # 用前3根1min (默认2)
"""

import json, math, os, sys, time, importlib.util, argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ENGINE_V57 = os.path.join(SKILL_DIR, "5minbtc-engine-v5.7.py")
ENGINE_V56 = os.path.join(SKILL_DIR, "5minbtc-engine-v5.py")
DATA_5M = os.path.join(SCRIPT_DIR, "data", "btcusdt_5m.json")
DATA_1M = os.path.join(SCRIPT_DIR, "data", "btcusdt_1m.json")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

CST = timezone(timedelta(hours=8))
WARMUP = 200


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


# ======================== 1min -> 5min Half-Candle ========================

def build_1m_index(candles_1m):
    """构建 1min open_time -> candle 的索引"""
    idx = {}
    for c in candles_1m:
        idx[c["ot"]] = c
    return idx


def find_1m_for_5m(candle_5m, idx_1m):
    """找到对应5分钟K线的所有1分钟K线 (5根)
    
    5min K线 open_time 总是 5的整数倍分钟
    对应的1min K线: open_time, open_time+60000, ... open_time+240000
    """
    base_ot = candle_5m["ot"]
    result = []
    for offset_min in range(5):
        ot = base_ot + offset_min * 60000
        if ot in idx_1m:
            result.append(idx_1m[ot])
    return result


def build_half_candle_from_1m(candle_5m, candles_1m_slice, n_half=2):
    """用前n_half根1分钟K线构建半K线状态
    
    这完全模拟实盘: 在5分钟K线的第3分钟, 你已经看到了前2根1分钟K线的完整数据
    
    Args:
        candle_5m: 当前5分钟K线原始数据
        candles_1m_slice: 对应的5根1分钟K线 (按时间排序)
        n_half: 用前几根1分钟K线 (默认2 = 前2分钟)
    
    Returns:
        模拟的半K线 OHLCV
    """
    if not candles_1m_slice:
        # 没有对应的1分钟数据, fallback到open状态
        return None
    
    half_1m = candles_1m_slice[:n_half]
    
    open_price = candle_5m["o"]  # 5min open 就是第一根1min的open
    
    # 用1分钟数据构建半程OHLCV
    all_highs = [c["h"] for c in half_1m]
    all_lows = [c["l"] for c in half_1m]
    last_close = half_1m[-1]["c"]
    total_vol = sum(c["v"] for c in half_1m)
    
    half_high = max(open_price, max(all_highs))
    half_low = min(open_price, min(all_lows))
    
    return {
        "o": open_price,
        "h": half_high,
        "l": half_low,
        "c": last_close,
        "v": total_vol,
        "ct": half_1m[-1]["ct"],
        "ot": candle_5m["ot"],
    }


def simulate_open_candle(raw):
    """模拟K线刚开盘(v5.6 baseline用)"""
    open_price = raw["o"]
    return {
        "o": open_price, "h": open_price, "l": open_price,
        "c": open_price, "v": 0.0, "ct": raw["ct"], "ot": raw["ot"],
    }


# ======================== Backtest Core ========================

def _ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=CST).strftime("%Y-%m-%d %H:%M")


def run_backtest_single(engine, candles_5m, idx_1m, sample_rate=1,
                        max_days=None, n_half=2, mode="half_1m",
                        verbose=True):
    """单引擎回测
    
    mode:
      "half_1m"  — 用前n_half根1min K线 (零前视偏差)
      "open"     — progress=0.01 (v5.6 baseline)
    """
    # 时间范围筛选
    start_idx = WARMUP
    if max_days and len(candles_5m) > WARMUP + 100:
        cutoff_ms = candles_5m[-1]["ct"] - max_days * 24 * 3600 * 1000
        for i in range(WARMUP, len(candles_5m)):
            if candles_5m[i]["ot"] >= cutoff_ms:
                start_idx = i
                break
        start_idx = max(start_idx, WARMUP)

    total = len(candles_5m) - start_idx
    total_samples = (total + sample_rate - 1) // sample_rate

    if verbose:
        label = {
            "half_1m": f"v5.7+1min半K线(前{n_half}根1min)",
            "open": "v5.6 开盘baseline",
        }[mode]
        print(f"\n🔄 开始回测 ({label})")
        print(f"   数据范围: {_ts(candles_5m[start_idx]['ot'])} ~ {_ts(candles_5m[-1]['ct'])}")
        print(f"   总5min K线: {total:,} | 采样: {total_samples:,} (rate={sample_rate})")
        print()

    results = []
    t0 = time.time()
    skipped_no_1m = 0

    for idx, i in enumerate(range(start_idx, len(candles_5m), sample_rate)):
        window = candles_5m[i - WARMUP:i]
        raw = candles_5m[i]

        if mode == "half_1m":
            # 用真实1分钟K线构建半K线
            all_1m = find_1m_for_5m(raw, idx_1m)
            simulated = build_half_candle_from_1m(raw, all_1m, n_half=n_half)
            if simulated is None:
                skipped_no_1m += 1
                continue
            progress = 0.5  # 引擎内half_body因子在≥0.45激活
        elif mode == "open":
            simulated = simulate_open_candle(raw)
            progress = 0.01

        full_candles = window + [simulated]
        closes = [c["c"] for c in full_candles]

        atr_val = engine.atr_wilder(full_candles)
        vr = engine.vol_regime_ratio(closes)

        bias, strength, confidence, score, factors, regime = engine.direction_rule_v5(
            full_candles, closes, atr_val, vr,
            depth_data=None, candle_progress=progress
        )

        actual_close = raw["c"]
        prev_close = candles_5m[i - 1]["c"]
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
            "sim_high": simulated["h"],
            "sim_low": simulated["l"],
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

        if verbose and (idx + 1) % 2000 == 0:
            elapsed = time.time() - t0
            rate = (idx + 1) / elapsed
            eta = (total_samples - idx - 1) / rate if rate > 0 else 0
            directional = sum(1 for r in results if r["dir_correct"] is not None)
            correct = sum(1 for r in results if r["dir_correct"] is True)
            acc = correct / directional * 100 if directional > 0 else 0
            print(f"  [{idx+1}/{total_samples}] acc={acc:.1f}% "
                  f"({correct}/{directional}) | "
                  f"{rate:.0f}根/s | ETA {eta:.0f}s"
                  f"{f' | skip_1m={skipped_no_1m}' if skipped_no_1m else ''}")

    elapsed = time.time() - t0
    if verbose:
        if skipped_no_1m:
            print(f"   ⚠️ 跳过{skipped_no_1m}根(无对应1min数据)")
        print(f"   ✅ 回测完成: {len(results):,}根 | {elapsed:.1f}s")

    return results


# ======================== Analysis ========================

def analyze_results(results, label=""):
    """分析回测结果"""
    if not results:
        return {}

    directional = [r for r in results if r["dir_correct"] is not None]
    correct = sum(1 for r in directional if r["dir_correct"] is True)
    total_dir = len(directional)
    accuracy = correct / total_dir * 100 if total_dir > 0 else 0

    # 连胜/连败
    streaks = []
    current_streak = 0
    last_correct = None
    for r in directional:
        if r["dir_correct"] == last_correct:
            current_streak += 1
        else:
            if last_correct is not None:
                streaks.append((last_correct, current_streak))
            current_streak = 1
            last_correct = r["dir_correct"]
    if last_correct is not None:
        streaks.append((last_correct, current_streak))

    win_streaks = [s for c, s in streaks if c]
    lose_streaks = [s for c, s in streaks if not c]

    # 按月分析
    monthly = defaultdict(lambda: {"total": 0, "correct": 0, "neutral": 0})
    for r in results:
        dt = datetime.fromtimestamp(r["ts"] / 1000, tz=CST)
        key = dt.strftime("%Y-%m")
        if r["dir_correct"] is not None:
            monthly[key]["total"] += 1
            if r["dir_correct"]:
                monthly[key]["correct"] += 1
        else:
            monthly[key]["neutral"] += 1

    # half_body因子分析
    hb_active = sum(1 for r in results if abs(r.get("half_body", 0)) > 0.05)
    hb_directional = [r for r in results
                      if r["dir_correct"] is not None and abs(r.get("half_body", 0)) > 0.05]
    hb_correct = sum(1 for r in hb_directional if r["dir_correct"] is True)

    # confidence分析
    conf_buckets = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in directional:
        bucket = round(r["confidence"] * 10) / 10  # 0.1步长
        conf_buckets[bucket]["total"] += 1
        if r["dir_correct"]:
            conf_buckets[bucket]["correct"] += 1

    # 因子贡献分析
    factor_names = set()
    for r in results:
        factor_names.update(r["factors"].keys())
    factor_correlation = {}
    for fn in sorted(factor_names):
        vals = [(r["factors"].get(fn, 0), r["dir_correct"]) for r in directional]
        # 简单: 因子方向与实际方向一致的比例
        factor_dir_correct = 0
        factor_dir_total = 0
        for fv, dc in vals:
            if dc is None or abs(fv) < 0.1:
                continue
            factor_dir_total += 1
            if (fv > 0 and dc) or (fv < 0 and not dc):
                factor_dir_correct += 1
        if factor_dir_total > 0:
            factor_correlation[fn] = {
                "acc": round(factor_dir_correct / factor_dir_total * 100, 1),
                "count": factor_dir_total,
            }

    stats = {
        "label": label,
        "total_candles": len(results),
        "directional": total_dir,
        "correct": correct,
        "wrong": total_dir - correct,
        "neutral": len(results) - total_dir,
        "accuracy": round(accuracy, 1),
        "edge_vs_random": round(accuracy - 50, 1),
        "max_win_streak": max(win_streaks) if win_streaks else 0,
        "max_lose_streak": max(lose_streaks) if lose_streaks else 0,
        "avg_win_streak": round(sum(win_streaks) / len(win_streaks), 1) if win_streaks else 0,
        "avg_lose_streak": round(sum(lose_streaks) / len(lose_streaks), 1) if lose_streaks else 0,
        "half_body_active": hb_active,
        "half_body_active_pct": round(hb_active / len(results) * 100, 1),
        "half_body_dir": len(hb_directional),
        "half_body_correct": hb_correct,
        "half_body_acc": round(hb_correct / len(hb_directional) * 100, 1) if hb_directional else 0,
        "monthly": dict(sorted(monthly.items())),
        "factor_correlation": factor_correlation,
    }

    return stats


def print_report(stats, compact=False):
    """打印报告"""
    if not stats:
        print("❌ 无结果")
        return

    print(f"\n{'='*60}")
    print(f"📊 {stats['label']}")
    print(f"{'='*60}")
    print(f"  总K线: {stats['total_candles']:,}")
    print(f"  方向性: {stats['directional']:,} | 中性: {stats['neutral']:,}")
    print(f"  正确: {stats['correct']:,} | 错误: {stats['wrong']:,}")
    print(f"  ★ 准确率: {stats['accuracy']}%")
    print(f"  Edge vs random: {stats['edge_vs_random']:+.1f}pp")
    print(f"  最长连胜: {stats['max_win_streak']} | 最长连败: {stats['max_lose_streak']}")
    print(f"  平均连胜: {stats['avg_win_streak']} | 平均连败: {stats['avg_lose_streak']}")
    print(f"  half_body激活: {stats['half_body_active']} ({stats['half_body_active_pct']}%)")

    if stats['half_body_dir'] > 0:
        print(f"  half_body方向性: {stats['half_body_dir']} | "
              f"准确率: {stats['half_body_acc']}%")

    if not compact:
        print(f"\n  📅 月度准确率:")
        for month, data in stats["monthly"].items():
            if data["total"] > 0:
                acc = data["correct"] / data["total"] * 100
                bar = "█" * int(acc / 2) + "░" * (50 - int(acc / 2))
                print(f"    {month}: {acc:5.1f}% ({data['correct']:3d}/{data['total']:3d}) {bar}")

        # 因子贡献排名
        fc = stats.get("factor_correlation", {})
        if fc:
            print(f"\n  🔬 因子方向准确率排名:")
            sorted_factors = sorted(fc.items(), key=lambda x: x[1]["acc"], reverse=True)
            for name, info in sorted_factors:
                marker = "✅" if info["acc"] > 52 else ("⚠️" if info["acc"] < 48 else "  ")
                print(f"    {marker} {name:18s}: {info['acc']:5.1f}% (n={info['count']})")

    print(f"{'='*60}")


# ======================== Main ========================

def main():
    parser = argparse.ArgumentParser(description="v5.8 1min真实半K线回测")
    parser.add_argument("--sample", type=int, default=1, help="采样率")
    parser.add_argument("--days", type=int, default=None, help="只回测最近N天")
    parser.add_argument("--fast", action="store_true", help="快速: sample=6 + 180天")
    parser.add_argument("--compare", action="store_true", help="同时跑v5.6 baseline")
    parser.add_argument("--half", type=int, default=2, help="用前几根1min (默认2)")
    parser.add_argument("--full-report", action="store_true", help="完整报告")
    parser.add_argument("--save", action="store_true", default=True, help="保存结果")
    args = parser.parse_args()

    if args.fast:
        args.sample = max(args.sample, 6)
        args.days = args.days or 180

    # 加载数据
    print("📂 加载5分钟K线数据...")
    with open(DATA_5M) as f:
        candles_5m = json.load(f)
    print(f"   5min: {len(candles_5m):,} 根")

    print("📂 加载1分钟K线数据...")
    with open(DATA_1M) as f:
        candles_1m = json.load(f)
    print(f"   1min: {len(candles_1m):,} 根")

    # 构建1min索引
    print("🔨 构建1min索引...")
    idx_1m = build_1m_index(candles_1m)
    print(f"   索引大小: {len(idx_1m):,}")

    # 验证覆盖
    sample_5m = candles_5m[WARMUP]
    sample_1m = find_1m_for_5m(sample_5m, idx_1m)
    print(f"   覆盖验证: 5min {_ts(sample_5m['ot'])} → 找到{len(sample_1m)}根1min")

    # 加载引擎
    print("⚙️ 加载v5.7引擎...")
    engine_57 = load_engine(ENGINE_V57)

    # ---- Run 1: v5.7 + 真实1min半K线 ----
    results_1m = run_backtest_single(
        engine_57, candles_5m, idx_1m,
        sample_rate=args.sample, max_days=args.days,
        n_half=args.half, mode="half_1m", verbose=True,
    )

    stats_1m = analyze_results(results_1m,
                               label=f"v5.7 + 真实1min半K线(前{args.half}根)")

    compact = not args.full_report
    print_report(stats_1m, compact=compact)

    # ---- Run 2: v5.6 baseline (可选) ----
    stats_open = None
    if args.compare:
        print("\n⚙️ 加载v5.6引擎...")
        engine_56 = load_engine(ENGINE_V56)

        results_open = run_backtest_single(
            engine_56, candles_5m, idx_1m,
            sample_rate=args.sample, max_days=args.days,
            mode="open", verbose=True,
        )
        stats_open = analyze_results(results_open, label="v5.6 开盘baseline")
        print_report(stats_open, compact=compact)

    # ---- 对比摘要 ----
    if stats_open:
        print(f"\n{'='*60}")
        print(f"📊 对比摘要")
        print(f"{'='*60}")
        print(f"  {'':30s} {'v5.7+1min':>10s} {'v5.6开盘':>10s} {'差异':>8s}")
        print(f"  {'-'*58}")
        print(f"  {'准确率':30s} {stats_1m['accuracy']:>9.1f}% {stats_open['accuracy']:>9.1f}% "
              f"{stats_1m['accuracy']-stats_open['accuracy']:>+7.1f}pp")
        print(f"  {'方向性':30s} {stats_1m['directional']:>10,} {stats_open['directional']:>10,}")
        print(f"  {'Edge vs random':30s} {stats_1m['edge_vs_random']:>+9.1f}pp "
              f"{stats_open['edge_vs_random']:>+9.1f}pp "
              f"{stats_1m['edge_vs_random']-stats_open['edge_vs_random']:>+7.1f}pp")
        print(f"  {'最长连胜':30s} {stats_1m['max_win_streak']:>10} {stats_open['max_win_streak']:>10}")
        print(f"  {'最长连败':30s} {stats_1m['max_lose_streak']:>10} {stats_open['max_lose_streak']:>10}")
        print(f"{'='*60}")

    # ---- 保存结果 ----
    if args.save:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        ts = datetime.now(CST).strftime("%Y%m%d_%H%M")
        
        full_result = {
            "version": "v5.8-1min-half",
            "timestamp": ts,
            "n_half": args.half,
            "sample_rate": args.sample,
            "max_days": args.days,
            "stats_1m": stats_1m,
        }
        if stats_open:
            full_result["stats_open"] = stats_open

        path_full = os.path.join(RESULTS_DIR, f"backtest_v58_1min_{ts}.json")
        with open(path_full, "w") as f:
            json.dump(full_result, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 已保存: {path_full}")

        # summary
        summary = {
            "version": "v5.8-1min-half",
            "timestamp": ts,
            "n_half": args.half,
            "accuracy_1m": stats_1m["accuracy"],
            "edge_vs_random": stats_1m["edge_vs_random"],
            "directional": stats_1m["directional"],
            "correct": stats_1m["correct"],
            "half_body_acc": stats_1m["half_body_acc"],
            "max_win_streak": stats_1m["max_win_streak"],
            "max_lose_streak": stats_1m["max_lose_streak"],
        }
        if stats_open:
            summary["accuracy_open"] = stats_open["accuracy"]
            summary["edge_diff"] = round(stats_1m["accuracy"] - stats_open["accuracy"], 1)

        path_summary = os.path.join(RESULTS_DIR, "latest_v58_1min_summary.json")
        with open(path_summary, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"💾 摘要: {path_summary}")


if __name__ == "__main__":
    main()
