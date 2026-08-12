#!/usr/bin/env python3
"""5minbtc 预测战绩查询 → 可选推送 Telegram (可移植版, 放在本 skill scripts/ 内)

记录由 5minbtc_watch.py 写入 SKILL/logs/5minbtc-log.jsonl;
结算(actual close/direction/range)由 watch 在新K线时对已收盘K线自动结算,
也可手动: python3 <SKILL>/5minbtc-log.py settle-all

用法:
  python3 scripts/5minbtc_day_stats.py              # 今日战绩
  python3 scripts/5minbtc_day_stats.py --date 2026-08-12
  python3 scripts/5minbtc_day_stats.py --all        # 全部历史
  python3 scripts/5minbtc_day_stats.py --push       # 推送到 Telegram
"""
import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL = SCRIPT_DIR.parent
LOG = SKILL / "logs" / "5minbtc-log.jsonl"
PUSH = SCRIPT_DIR / "telegram_push.py"
CST = timezone(timedelta(hours=8))


def load():
    if not os.path.exists(LOG):
        return []
    out = []
    with open(LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def fmt_stats(entries, label):
    settled = [e for e in entries if e.get("settled")]
    lines = [f"📈 5minbtc 预测战绩 | {label}"]
    lines.append("━" * 24)
    if not entries:
        lines.append("暂无预测记录")
        return "\n".join(lines)
    lines.append(f"记录预测 {len(entries)} 条")
    if not settled:
        lines.append("暂无已结算(收盘确认)记录")
        lines.append("(K线收盘后自动结算, 以最终确认结果为准)")
        return "\n".join(lines)
    total = len(settled)
    dir_ok = sum(1 for e in settled if e.get("direction_correct"))
    in_rng = sum(1 for e in settled if e.get("in_range"))
    errs = [e.get("error_pct", 0) for e in settled]
    mae = sum(abs(x) for x in errs) / total
    pred_dir = Counter(e.get("bias", "?").split("-")[0] for e in settled)
    lines.append(f"已结算 {total} 条 | 方向命中 {dir_ok}/{total} = {dir_ok / total * 100:.0f}%")
    lines.append(f"收盘在预测区间 {in_rng}/{total} = {in_rng / total * 100:.0f}%")
    lines.append(f"MAE {mae:.3f}% | 方向分布 {dict(pred_dir)}")
    lines.append("━" * 24)
    lines.append("最近结算:")
    for e in settled[-3:]:
        d = "✅" if e.get("direction_correct") else "❌"
        r = "✅" if e.get("in_range") else "❌"
        lines.append(
            f"  {e.get('candle', '?')[5:16]} {e.get('bias', '?'):6s} "
            f"pred {e.get('pred_close', 0):.0f} → 实际 {e.get('actual_close', 0):.0f} "
            f"({e.get('error_pct', 0):+.2f}%) 方向{d} 区间{r}"
        )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="5minbtc 预测战绩查询")
    ap.add_argument("--date", help="YYYY-MM-DD")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()

    entries = load()
    today = datetime.now(CST).strftime("%Y-%m-%d")
    if args.all:
        label, sel = "全部历史", entries
    elif args.date:
        label, sel = args.date, [e for e in entries if e.get("candle", "").startswith(args.date)]
    else:
        label, sel = f"今日 {today}", [e for e in entries if e.get("candle", "").startswith(today)]

    msg = fmt_stats(sel, label)
    print(msg)
    if args.push:
        subprocess.run(["/usr/bin/python3", str(PUSH), msg], capture_output=True, timeout=20)


if __name__ == "__main__":
    main()
