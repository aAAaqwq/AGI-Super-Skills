#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5minbtc-monitor.py — BTC 5min 预测监控 (Claude Code 适配版 v1.0)

在每根 5min BTC K线的第 2/3/4 分钟采样 5minbtc-engine-v5.7.py 的预测,
把事件以「一行一条」流式输出到 stdout — Claude Code 的 Monitor 工具
会把每行转发为实时通知;命中「明确信号」即自动退出。

事件行:
  START        首次采样,记录基线 bias
  DIR-CHANGE   bias 在 bull/neutral/bear 间翻转
  CLEAR-SIGNAL 达到明确信号门槛 → 退出 (exit 0)
  ENGINE-ERR   引擎调用失败 (打印后继续, 不崩溃)
  TIMEOUT      达到 --hours 上限仍无明确信号 → 退出 (exit 2)

用法:
  python3 scripts/5minbtc-monitor.py                 # 默认: 最多 20 次采样, 命中明确信号即停
  python3 scripts/5minbtc-monitor.py --max-runs 100  # 采样次数上限
  python3 scripts/5minbtc-monitor.py --hours 2 --min-conf 55
  python3 scripts/5minbtc-monitor.py --settle        # 每次采样前 settle 上一根
  python3 scripts/5minbtc-monitor.py --dry-run       # 单次采样打印当前状态后退出

路径: 脚本用 __file__ 定位引擎, 与 cwd 无关; 任意目录可调用。
退出码: 0=CLEAR-SIGNAL, 2=达上限/超时, 1=异常。

Claude Code 用法 (后台持续监控, 每根K线第2/3分钟采样):
  Monitor 工具 挂起:  python3 scripts/5minbtc-monitor.py --max-runs 20
  配合 --persistent 可无限运行, 由用户/会话结束或 --max-runs 兜底停止。
"""
import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "5minbtc-engine-v5.7.py"
SETTLE = ROOT / "5minbtc-log.py"

# 每根 5min K线内的采样分钟 (progress ~40-80%: 第2/3分钟早捕捉, 第4分钟=原版半K线成熟期)
DEFAULT_SAMPLE_MINUTES = (2, 3, 4)
# 明确信号的 strength 集合 — 实测引擎会输出 weak / medium (而非文档的 moderate), 两者都收
DEFAULT_STRENGTHS = ("medium", "moderate", "strong")
SAMPLE_SECOND = 5
ENGINE_TIMEOUT = 45


def run_engine():
    try:
        out = subprocess.run(["python3", str(ENGINE)], capture_output=True,
                             text=True, timeout=ENGINE_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("ENGINE-ERR TimeoutExpired(45s)", flush=True)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"ENGINE-ERR {type(e).__name__}: {e}", flush=True)
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as e:
        print(f"ENGINE-ERR JSONDecode {e}; stderr={out.stderr.strip()[:200]}", flush=True)
        return None


def emit(tag, d):
    p = d["prediction"]
    c = d["candle"]
    tb = d["factors"].get("taker_buy")
    tb_s = f" tb={tb:+.2f}" if tb is not None else ""
    print(f"{tag} [{c.get('iso')} p{c.get('progress_pct', 0):.0f}%] "
          f"{p['bias']}/{p['strength']} conf={p['confidence']} "
          f"px={d['price']['current']} regime={d.get('regime')} "
          f"fng={d.get('fng', {}).get('value')}{tb_s}", flush=True)


def next_sample(now):
    """返回下一个采样时刻: minute%5 ∈ SAMPLE_MINUTES 且秒=SAMPLE_SECOND, 至少 6s 后。"""
    for i in range(0, 12):
        t = now + datetime.timedelta(minutes=i)
        if t.minute % 5 in SAMPLE_MINUTES:
            t = t.replace(second=SAMPLE_SECOND, microsecond=0)
            if t - now >= datetime.timedelta(seconds=6):
                return t
    return now + datetime.timedelta(minutes=12)


def main():
    ap = argparse.ArgumentParser(description="BTC 5min 引擎监控 (Claude Code 适配)")
    ap.add_argument("--max-runs", type=int, default=20,
                    help="采样次数上限(默认 20; 0=无限, 配 --persistent 由用户/会话结束)")
    ap.add_argument("--hours", type=float, default=None, help="监控时长上限(小时); 默认无")
    ap.add_argument("--min-conf", type=int, default=50, help="明确信号置信度门槛, 默认 50")
    ap.add_argument("--strengths", nargs="*", default=list(DEFAULT_STRENGTHS),
                    help="明确信号 strength 集合")
    ap.add_argument("--sample-minutes", type=int, nargs="*", default=list(DEFAULT_SAMPLE_MINUTES),
                    help="每根K线内采样分钟 (默认 2 3 4)")
    ap.add_argument("--settle", action="store_true", help="每次采样前 settle 上一根 K线")
    ap.add_argument("--dry-run", action="store_true", help="单次采样打印当前状态后退出")
    ap.add_argument("--loop-rounds", type=int, default=0,
                    help="命中 CLEAR-SIGNAL 后自动进入下一轮(每轮重计 max-runs); 0=命中即退出; -1=无限续轮直到手动停")
    args = ap.parse_args()

    strengths = set(args.strengths)
    global SAMPLE_MINUTES
    SAMPLE_MINUTES = tuple(args.sample_minutes)
    deadline = time.time() + args.hours * 3600 if args.hours else None
    last_bias = None
    last_tb = None
    runs = 0

    def settle():
        if args.settle:
            subprocess.run(["python3", str(SETTLE), "settle-all"],
                           capture_output=True, text=True, timeout=30)

    while True:
        if args.max_runs and runs >= args.max_runs:
            print(f"MAX-RUNS reached ({runs}) no-clear-signal", flush=True)
            return 2
        if deadline and time.time() > deadline:
            print("TIMEOUT no-clear-signal", flush=True)
            return 2
        runs += 1
        settle()
        d = run_engine()
        if d is None:
            time.sleep(15)
            continue
        p = d["prediction"]
        if args.dry_run:
            emit("DRY", d)
            return 0
        clear = (p["bias"] != "neutral" and p["strength"] in strengths
                 and p["confidence"] >= args.min_conf)
        if clear:
            emit("CLEAR-SIGNAL", d)
            loop = args.loop_rounds  # -1=无限, N>0=再续N轮, 0=退出
            if loop != 0:
                if loop > 0:
                    args.loop_rounds -= 1
                runs = 0
                emit("ROUND", d)
                now = datetime.datetime.now()
                t = next_sample(now)
                time.sleep(max(10, (t - now).total_seconds()))
                continue
            return 0
        if p["bias"] != last_bias:
            emit("DIR-CHANGE" if last_bias is not None else "START", d)
            last_bias = p["bias"]
        # v5.8: taker_buy 正负翻转报警 (方向未变但主动买卖力翻转)
        tb = d["factors"].get("taker_buy")
        if tb is not None and last_tb is not None:
            if (tb >= 0) != (last_tb >= 0):
                emit("TB-FLIP", d)
        if tb is not None:
            last_tb = tb
        now = datetime.datetime.now()
        t = next_sample(now)
        time.sleep(max(10, (t - now).total_seconds()))


if __name__ == "__main__":
    sys.exit(main())
