#!/usr/bin/env python3
"""5minbtc 持续监控 → Telegram 推送 (可移植版, 放在本 skill scripts/ 内)

每根 5min BTC K线的第 2/3/4 分钟运行 5minbtc-engine-v5.7.py 采样:

- 记录: 每根K线记录第一次成功采样的预测到 SKILL/logs/5minbtc-log.jsonl
        (通过 5minbtc-log.py log, 供日后验证战绩)
- 结算: 新K线开始时 settle-all 上一根已收盘K线, 写入实际收盘/方向/区间命中
- 推送: 事件驱动 (START/DIR-CHANGE/CLEAR-SIGNAL/TB-FLIP) + 每小时心跳
        + 每日 00:00 前后推送前一天战绩汇总 (5minbtc_day_stats.py --push)
- 可选: --every-candle 每根K线都推完整预测

用法:
  python3 scripts/5minbtc_watch.py                 # 默认: 事件+心跳+每日战绩
  python3 scripts/5minbtc_watch.py --every-candle  # 每次采样都推完整预测
  python3 scripts/5minbtc_watch.py --min-conf 60
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
ENGINE = SKILL / "5minbtc-engine-v5.7.py"
SETTLE = SKILL / "5minbtc-log.py"
PUSH = SCRIPTS / "telegram_push.py"
DAY_STATS = SCRIPTS / "5minbtc_day_stats.py"
PY = "/usr/bin/python3"
CST = datetime.timezone(datetime.timedelta(hours=8))

SAMPLE_MINUTES = (2, 3, 4)      # 每根K线内采样分钟
SAMPLE_SECOND = 5
STRENGTHS = {"medium", "moderate", "strong"}
MIN_CONF = 50
HEARTBEAT_SEC = 3600

EMOJI = {"bull": "🟢", "neutral": "⚪", "bear": "🔴"}
DIR_CN = {"bull": "看多", "neutral": "中性", "bear": "看空"}


# ── 预测市场 UP/DOWN 实时价 + 模拟持仓 (可选增强, 无密钥优雅降级) ──

def _load_predict_env():
    """从 ~/bb-auto/prediction.env 载入币安预测API密钥 (供取 UP/DOWN 实时价)."""
    envf = Path.home() / "bb-auto" / "prediction.env"
    if not envf.exists():
        return
    try:
        for line in envf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass


def fetch_predict_prices():
    """返回 (up_price, down_price) 或 (None, None). 需币安预测API密钥.
    实时价格表 = 轮询 order-book (非 RSS; RSS 是文章流, 分钟级延迟)."""
    try:
        import importlib
        _load_predict_env()
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        trader = importlib.import_module("5minbtc_trader")
        found = trader.find_btc_5m_market()
        if not found:
            return None, None
        _, market_id, up_tok, down_tok, _, _ = found
        return trader._token_price(market_id, up_tok), trader._token_price(market_id, down_tok)
    except Exception:
        return None, None


def paper_positions():
    """读取 paper 台账, 返回当前模拟持仓/挂单行列表 (无则 None)."""
    pf = Path.home() / "bb-auto" / "5minbtc-paper.json"
    if not pf.exists():
        return None
    try:
        state = json.loads(pf.read_text())
    except Exception:
        return None
    open_ = [b for b in state.get("bets", []) if b.get("status") == "open"]
    pending = [b for b in state.get("bets", []) if b.get("status") == "pending"]
    if not open_ and not pending:
        return None
    lines = []
    for b in open_:
        lines.append(f"  ✅ {b.get('side')} @{b.get('ask', 0):.2f} 待结算")
    for b in pending:
        lines.append(f"  📋 {b.get('side')} 限价 {b.get('limit', 0):.2f} 挂单")
    return lines


def market_line():
    """组合 UP/DOWN 实时价 + 模拟持仓 文本块."""
    up, down = fetch_predict_prices()
    out = []
    if up is not None:
        out.append(f"预测市场: UP {up:.2f} | DOWN {down:.2f}")
    else:
        out.append("预测市场: (未连/无密钥)")
    pos = paper_positions()
    if pos:
        out.append("模拟持仓:")
        out.extend(pos)
    else:
        out.append("模拟持仓: 无")
    return "\n".join(out)


def push(msg):
    try:
        subprocess.run([PY, str(PUSH), msg], timeout=20, capture_output=True)
    except Exception:
        pass


def run_engine():
    try:
        out = subprocess.run([PY, str(ENGINE)], capture_output=True,
                             text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return None, "TimeoutExpired(45s)"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    try:
        return json.loads(out.stdout), None
    except json.JSONDecodeError as e:
        return None, f"JSONDecode {e}; stderr={out.stderr.strip()[:200]}"


def run_settle_all():
    try:
        subprocess.run([PY, str(SETTLE), "settle-all"], capture_output=True,
                       text=True, timeout=90)
    except Exception:
        pass


def already_logged(candle_iso):
    logf = SKILL / "logs" / "5minbtc-log.jsonl"
    if not logf.exists():
        return False
    try:
        with open(logf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("candle") == candle_iso and not e.get("settled"):
                    return True
    except Exception:
        return False
    return False


def log_prediction(d, candle_iso):
    p = d["prediction"]
    ind = d["indicators"]
    try:
        subprocess.run([PY, str(SETTLE), "log", candle_iso,
                        str(p["pred_close"]), str(p["pred_high"]), str(p["pred_low"]),
                        str(p["confidence"]), p["bias"],
                        str(d.get("news_risk", "UNKNOWN")), str(ind.get("vol_pct", 0))],
                       capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def fmt_event(tag, d):
    p = d["prediction"]
    c = d["candle"]
    px = d["price"]["current"]
    tb = d["factors"].get("taker_buy")
    tb_s = f" | 买力 tb={tb:+.2f}" if tb is not None else ""
    fng = d.get("fng", {})
    fng_s = f" | FNG {fng.get('value')} {fng.get('label', '')}" if fng.get("value") is not None else ""
    head = f"{EMOJI.get(p['bias'], '⚪')} [5minbtc] {tag} {c.get('iso')} p{c.get('progress_pct', 0):.0f}%"
    line = (
        f"{head}\n"
        f"方向: {DIR_CN.get(p['bias'], p['bias'])} ({p['strength']}) | 置信 {p['confidence']}\n"
        f"现价 {px:,.2f} | 预测收 {p['pred_close']:,} (低{p['pred_low']:,}/高{p['pred_high']:,})\n"
        f"regime {d.get('regime')}{fng_s}{tb_s}"
    )
    if tag == "CLEAR-SIGNAL":
        line += "\n⚠️ 达到明确信号门槛 — 人工复核后再考虑动作, 非投资建议"
    if d.get("black_swan_warning"):
        line += "\n🚨 黑天鹅警告: 方向不可靠"
    line += "\n── 预测市场 ──\n" + market_line()
    return line


def next_sample(now):
    for i in range(0, 12):
        t = now + datetime.timedelta(minutes=i)
        if t.minute % 5 in SAMPLE_MINUTES:
            t = t.replace(second=SAMPLE_SECOND, microsecond=0)
            if t - now >= datetime.timedelta(seconds=6):
                return t
    return now + datetime.timedelta(minutes=12)


def main():
    ap = argparse.ArgumentParser(description="5minbtc 监控→Telegram daemon (含记录/结算)")
    ap.add_argument("--every-candle", action="store_true",
                    help="每次采样都推完整预测 (默认仅事件+心跳)")
    ap.add_argument("--min-conf", type=int, default=MIN_CONF)
    ap.add_argument("--heartbeat", type=int, default=HEARTBEAT_SEC)
    ap.add_argument("--no-daily-stats", action="store_true",
                    help="关闭每日战绩汇总推送")
    args = ap.parse_args()

    mode = "每根K线推预测" if args.every_candle else \
        f"事件驱动+每{args.heartbeat // 3600}h心跳"
    push(f"🟢 5minbtc 监控已启动 | 每5min采样引擎 | {mode}\n"
         f"已启用预测记录+收盘结算 | 每日战绩推送"
         f"{' (已关闭)' if args.no_daily_stats else ''}")

    last_bias = None
    last_tb = None
    last_heart = time.time()
    err_streak = 0
    cur_candle = None
    logged_this_candle = False
    last_day = datetime.datetime.now(CST).strftime("%Y-%m-%d")

    while True:
        d, err = run_engine()
        if d is None:
            err_streak += 1
            if err_streak in (1, 3, 6, 10):
                push(f"⚠️ [5minbtc] 引擎采样失败 x{err_streak}: {err}")
            time.sleep(15)
            continue
        err_streak = 0
        p = d["prediction"]
        candle_iso = d["candle"]["iso"]

        # ── 新K线: 结算上一根 + 重置记录标记 ──
        if candle_iso != cur_candle:
            if cur_candle is not None:
                run_settle_all()   # 上一根已收盘 → 写入实际结果
            cur_candle = candle_iso
            logged_this_candle = False

        # ── 记录预测: 每根K线一次 (首次成功采样) ──
        if not logged_this_candle and not already_logged(candle_iso):
            log_prediction(d, candle_iso)
            logged_this_candle = True

        # ── 事件推送 ──
        clear = (p["bias"] != "neutral" and p["strength"] in STRENGTHS
                 and p["confidence"] >= args.min_conf)
        if clear:
            push(fmt_event("CLEAR-SIGNAL", d))
        if p["bias"] != last_bias:
            tag = "START" if last_bias is None else "DIR-CHANGE"
            push(fmt_event(tag, d))
            last_bias = p["bias"]
        tb = d["factors"].get("taker_buy")
        if tb is not None and last_tb is not None and (tb >= 0) != (last_tb >= 0):
            push(fmt_event("TB-FLIP", d))
        if tb is not None:
            last_tb = tb
        if args.every_candle:
            push(fmt_event("PREDICT", d))

        # ── 每小时心跳 ──
        if time.time() - last_heart >= args.heartbeat:
            push(fmt_event("心跳", d))
            last_heart = time.time()

        # ── 每日战绩汇总 (日期切换时推前一天) ──
        today = datetime.datetime.now(CST).strftime("%Y-%m-%d")
        if not args.no_daily_stats and today != last_day:
            try:
                subprocess.run([PY, str(DAY_STATS), "--date", last_day, "--push"],
                               capture_output=True, timeout=60)
            except Exception:
                pass
            last_day = today

        t = next_sample(datetime.datetime.now())
        time.sleep(max(10, (t - datetime.datetime.now()).total_seconds()))


if __name__ == "__main__":
    main()
