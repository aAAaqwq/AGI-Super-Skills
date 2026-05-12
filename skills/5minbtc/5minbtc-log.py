#!/usr/bin/env python3
"""5minbtc 预测日志 - 记录预测vs实际，用于回测准确率"""
import json, os, sys
from datetime import datetime, timezone, timedelta

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "5minbtc-log.jsonl")
CST = timezone(timedelta(hours=8))

def log_prediction(candle_start_iso, predicted_close, predicted_high, predicted_low, confidence, bias, news_sentiment, vol_pct):
    """记录预测（在K线进行中调用）"""
    entry = {
        "ts": datetime.now(CST).isoformat(timespec="seconds"),
        "candle": candle_start_iso,
        "pred_close": predicted_close,
        "pred_range": [predicted_low, predicted_high],
        "confidence": confidence,
        "bias": bias,
        "news": news_sentiment,
        "vol_pct": vol_pct,
        "actual_close": None,
        "actual_high": None,
        "actual_low": None,
        "settled": False
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"✅ Logged prediction for {candle_start_iso}: ${predicted_close:.0f}")

def settle_candle(candle_start_iso):
    """从Binance API获取已结算K线，填入actual值"""
    import urllib.request
    # Convert candle_start to epoch ms
    dt = datetime.fromisoformat(candle_start_iso)
    start_ms = int(dt.timestamp() * 1000)
    url = f"https://api.binance.me/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start_ms}&limit=1"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if not data:
        print("❌ No candle data")
        return
    candle = data[0]
    actual_high = float(candle[2])
    actual_low = float(candle[3])
    actual_close = float(candle[4])
    close_time = int(candle[6])
    now_ms = int(datetime.now(CST).timestamp() * 1000)
    if now_ms < close_time:
        print(f"⏳ Candle not yet closed (closes at {datetime.fromtimestamp(close_time/1000, tz=CST).isoformat()})")
        return

    # Update log
    if not os.path.exists(LOG_FILE):
        print("❌ No log file")
        return
    lines = []
    updated = False
    with open(LOG_FILE, "r") as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry["candle"] == candle_start_iso and not entry["settled"]:
                entry["actual_close"] = actual_close
                entry["actual_high"] = actual_high
                entry["actual_low"] = actual_low
                entry["settled"] = True
                pred = entry["pred_close"]
                err = actual_close - pred
                err_pct = err / pred * 100
                in_range = entry["pred_range"][0] <= actual_close <= entry["pred_range"][1]
                entry["error"] = round(err, 2)
                entry["error_pct"] = round(err_pct, 2)
                entry["in_range"] = in_range
                direction_ok = (entry["bias"] == "bull" and actual_close > float(candle[1])) or \
                               (entry["bias"] == "bear" and actual_close < float(candle[1])) or \
                               (entry["bias"] == "neutral")
                entry["direction_correct"] = direction_ok
                updated = True
                print(f"✅ Settled {candle_start_iso}: pred=${pred:.0f} actual=${actual_close:.0f} err={err:+.0f} ({err_pct:+.2f}%) range={'✅' if in_range else '❌'} dir={'✅' if direction_ok else '❌'}")
            lines.append(json.dumps(entry) + "\n")
    if updated:
        with open(LOG_FILE, "w") as f:
            f.writelines(lines)
    else:
        print(f"❌ No unsettled prediction found for {candle_start_iso}")

def get_last_unsettled():
    """返回最近一个未结算预测的candle时间（供cron使用）"""
    if not os.path.exists(LOG_FILE):
        print("NO_DATA")
        return
    entries = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            e = json.loads(line.strip())
            entries.append(e)
    # 从后往前找最近一个未结算的
    for e in reversed(entries):
        if not e["settled"]:
            candle = e["candle"]
            pred = e["pred_close"]
            bias = e["bias"]
            print(f"{candle}|{pred:.0f}|{bias}")
            return
    # 如果都结算了，找最后一个已结算的（展示结果）
    for e in reversed(entries):
        if e["settled"]:
            candle = e["candle"]
            pred = e["pred_close"]
            actual = e["actual_close"]
            err = e.get("error", 0)
            rng = "✅" if e["in_range"] else "❌"
            dr = "✅" if e["direction_correct"] else "❌"
            bias = e["bias"]
            print(f"ALL_SETTLED|{candle}|{pred:.0f}|{actual:.0f}|{err:+.0f}|{rng}|{dr}|{bias}")
            return
    print("NO_DATA")

def settle_all_unsettled():
    """结算所有未结算的预测（批量）"""
    if not os.path.exists(LOG_FILE):
        print("NO_DATA")
        return
    settled_count = 0
    lines = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            entry = json.loads(line.strip())
            if not entry["settled"]:
                # 获取该K线数据
                try:
                    import urllib.request
                    dt = datetime.fromisoformat(entry["candle"])
                    start_ms = int(dt.timestamp() * 1000)
                    url = f"https://api.binance.me/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start_ms}&limit=1"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read())
                    if data:
                        candle = data[0]
                        close_time = int(candle[6])
                        now_ms = int(datetime.now(CST).timestamp() * 1000)
                        if now_ms >= close_time:
                            actual_close = float(candle[4])
                            actual_high = float(candle[2])
                            actual_low = float(candle[3])
                            pred = entry["pred_close"]
                            err = actual_close - pred
                            err_pct = err / pred * 100
                            in_range = entry["pred_range"][0] <= actual_close <= entry["pred_range"][1]
                            direction_ok = (entry["bias"] == "bull" and actual_close > float(candle[1])) or \
                                           (entry["bias"] == "bear" and actual_close < float(candle[1])) or \
                                           (entry["bias"] == "neutral")
                            entry["actual_close"] = actual_close
                            entry["actual_high"] = actual_high
                            entry["actual_low"] = actual_low
                            entry["settled"] = True
                            entry["error"] = round(err, 2)
                            entry["error_pct"] = round(err_pct, 2)
                            entry["in_range"] = in_range
                            entry["direction_correct"] = direction_ok
                            settled_count += 1
                            pred_dir = entry['bias'].split('-')[0]  # bull/bear/neutral
                            actual_dir = 'bull' if actual_close > float(candle[1]) else 'bear'
                            dir_sym = '✅' if direction_ok else '❌'
                            rng_sym = '✅' if in_range else '❌'
                            print(f"✅ {entry['candle']}: pred=${pred:.0f} actual=${actual_close:.0f} err={err:+.0f} ({err_pct:+.2f}%)")
                            print(f"   方向: pred={pred_dir} actual={actual_dir} {dir_sym} | 区间: pred=[{entry['pred_range'][0]:.0f},{entry['pred_range'][1]:.0f}] actual=[{actual_low:.0f},{actual_high:.0f}] {rng_sym}")
                except Exception as ex:
                    print(f"⚠️ {entry['candle']}: {ex}")
            lines.append(json.dumps(entry) + "\n")
    with open(LOG_FILE, "w") as f:
        f.writelines(lines)
    if settled_count == 0:
        # Show last settled for verification even when nothing new to settle
        last_settled = None
        for line in lines:
            e = json.loads(line.strip())
            if e.get("settled"):
                last_settled = e
        if last_settled:
            e = last_settled
            rng_sym = '✅' if e['in_range'] else '❌'
            dir_sym = '✅' if e['direction_correct'] else '❌'
            pred_dir = e['bias'].split('-')[0]
            actual_dir = 'bull' if e['actual_close'] > e.get('actual_open', e['pred_close']) else 'bear'
            # Try to infer actual direction from actual_close vs pred_range low (open proxy)
            print(f"📋 Last settled: {e['candle']} pred=${e['pred_close']:.0f} actual=${e['actual_close']:.0f} err={e['error']:+.0f} ({e['error_pct']:+.2f}%)")
            print(f"   方向: pred={pred_dir} actual={actual_dir} {dir_sym} | 区间: pred=[{e['pred_range'][0]:.0f},{e['pred_range'][1]:.0f}] actual=[{e['actual_low']:.0f},{e['actual_high']:.0f}] {rng_sym}")
        else:
            print("No predictions found")
    else:
        print(f"\n📊 Batch settled {settled_count} predictions")

def stats():
    """统计预测准确率"""
    if not os.path.exists(LOG_FILE):
        print("No data")
        return
    entries = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            e = json.loads(line.strip())
            if e["settled"]:
                entries.append(e)
    if not entries:
        print("No settled predictions yet")
        return
    total = len(entries)
    in_range = sum(1 for e in entries if e["in_range"])
    dir_correct = sum(1 for e in entries if e["direction_correct"])
    errors = [e["error_pct"] for e in entries]
    abs_errors = [abs(e) for e in errors]
    mae = sum(abs_errors) / total
    print(f"📊 5minbtc Prediction Stats ({total} settled)")
    print(f"  Direction accuracy: {dir_correct}/{total} = {dir_correct/total*100:.0f}%")
    print(f"  In range: {in_range}/{total} = {in_range/total*100:.0f}%")
    print(f"  MAE: {mae:.3f}%")
    print(f"  Max error: {max(errors):+.3f}% / {min(errors):+.3f}%")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: 5minbtc-log.py log|settle|stats [args...]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "log":
        # log <candle_iso> <pred_close> <pred_high> <pred_low> <confidence> <bias> <news> <vol_pct>
        log_prediction(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]), sys.argv[7], sys.argv[8], float(sys.argv[9]))
    elif cmd == "settle":
        settle_candle(sys.argv[2])
    elif cmd == "last-unsettled":
        get_last_unsettled()
    elif cmd == "settle-all":
        settle_all_unsettled()
    elif cmd == "stats":
        stats()
