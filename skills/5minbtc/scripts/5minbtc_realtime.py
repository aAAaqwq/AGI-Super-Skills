#!/usr/bin/env python3
"""5minbtc 实时监控 — 5秒刷新, 捕捉重大确定性信号.

每 5 秒跑一次引擎, 判定"重大确定性信号":
  - 方向明确 (bias != neutral)
  - 高延续概率 (confidence ≥ 阈值, v5.9.2 半K线延续概率)
命中时推送 Telegram. 同一根K线去重(仅置信度显著提升或方向翻转才重推).

用法:
  python3 5minbtc_realtime.py [--conf 70] [--refresh 5] [--push]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ENGINE = SKILL / "5minbtc-engine-v5.7.py"
PUSH = SKILL / "scripts" / "telegram_push.py"
PY = "/usr/bin/python3"

DIR_CN = {"bull": "看多·收阳", "bear": "看空·收阴"}


def run_engine():
    try:
        out = subprocess.run([PY, str(ENGINE)], capture_output=True,
                             text=True, timeout=45)
        return json.loads(out.stdout)
    except Exception:
        return None


def push(msg, enabled=True):
    if not enabled:
        return
    try:
        subprocess.run([PY, str(PUSH), msg], capture_output=True, timeout=20)
    except Exception:
        pass


def fmt_signal(d):
    p = d["prediction"]
    c = d["candle"]
    price = d["price"]
    open_p = price["open"]
    cur = price["current"]
    chg = (cur - open_p) / open_p * 100 if open_p else 0
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    return (f"🎯 [重大信号] {dir_cn}\n"
            f"{c['candle_start']} progress {c['progress_pct']:.0f}% | "
            f"置信 {p['confidence']}\n"
            f"开 {open_p:.2f} → 现 {cur:.2f} ({chg:+.3f}%)\n"
            f"预测收 {p['pred_close']:,} | 强度 {p['strength']}\n"
            f"── 模拟下单(1U) ──\n"
            f"回复「下单」确认买入, 回复「跳过」忽略")


def main():
    ap = argparse.ArgumentParser(description="5minbtc 实时监控(5秒刷新, 捕捉重大信号)")
    ap.add_argument("--conf", type=int, default=70, help="重大信号置信度阈值(默认70)")
    ap.add_argument("--refresh", type=int, default=5, help="刷新间隔秒(默认5)")
    ap.add_argument("--push", action="store_true", help="推送 Telegram")
    args = ap.parse_args()

    last_candle = None
    last_signal_conf = 0
    last_bias = None
    print(f"🟢 5minbtc 实时监控启动 | {args.refresh}s刷新 | 重大信号阈值 conf≥{args.conf}", flush=True)

    while True:
        d = run_engine()
        if d is None:
            time.sleep(args.refresh)
            continue
        p = d["prediction"]
        c = d["candle"]
        candle = c["iso"]
        bias = p["bias"]
        conf = p["confidence"]

        # 新K线重置去重状态
        if candle != last_candle:
            last_candle = candle
            last_signal_conf = 0
            last_bias = None

        # 重大确定性信号: 方向明确 + 高延续概率
        is_signal = bias != "neutral" and conf >= args.conf

        if is_signal:
            # 去重: 首次命中 / 置信度显著提升(≥5) / 方向翻转 才推
            new_peak = conf >= last_signal_conf + 5 or last_bias is None
            flip = bias != last_bias and last_bias is not None
            if new_peak or flip:
                push(fmt_signal(d), args.push)
                print(fmt_signal(d), flush=True)
                print("─" * 40, flush=True)
                last_signal_conf = conf
                last_bias = bias

        time.sleep(args.refresh)


if __name__ == "__main__":
    main()
