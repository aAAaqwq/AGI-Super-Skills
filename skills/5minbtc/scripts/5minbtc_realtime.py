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
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ENGINE = SKILL / "5minbtc-engine-v5.7.py"
PUSH = SKILL / "scripts" / "telegram_push.py"
PY = "/usr/bin/python3"
PAPER = Path.home() / "bb-auto" / "5minbtc-paper.json"
CST = timezone(timedelta(hours=8))

DIR_CN = {"bull": "看多·收阳", "bear": "看空·收阴"}


def load_env():
    envf = Path.home() / "bb-auto" / "prediction.env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def get_up_down_price():
    """拉当前 BTC 5m 预测市场 UP/DOWN 真实价. 失败返回 (None, None)."""
    try:
        load_env()
        sys.path.insert(0, str(SKILL / "scripts"))
        import importlib
        trader = importlib.import_module("5minbtc_trader")
        found = trader.find_btc_5m_market()
        if not found:
            return None, None
        _, mid, up_tok, dn_tok, _, _ = found
        return trader._token_price(mid, up_tok), trader._token_price(mid, dn_tok)
    except Exception:
        return None, None


def load_paper():
    if PAPER.exists():
        try:
            return json.loads(PAPER.read_text())
        except Exception:
            pass
    return {"bets": [], "realized": 0.0, "bankroll": 100.0,
            "started": datetime.now(CST).isoformat()}


def save_paper(state):
    PAPER.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def has_auto_bet(candle):
    """台账去重: 该 K线是否已自动下单/挂单 (进程重启也不重复)."""
    state = load_paper()
    return any(b.get("candle") == candle and b.get("auto")
               for b in state.get("bets", []))


def record_paper(d, up=None, down=None):
    """重大信号自动记录一笔模拟单到台账 (完整入场快照 + 后续结算回测)."""
    p = d["prediction"]
    c = d["candle"]
    price = d["price"]
    side = "UP" if p["bias"] == "bull" else "DOWN"
    ask = up if side == "UP" else down
    if ask is None:
        # 真实价拿不到, 用引擎预测方向折算近似价
        ask = round(max(0.05, min(0.95, p["confidence"] / 100)), 4)
    state = load_paper()
    bet = {
        "candle": c["iso"], "side": side, "ask": round(ask, 4),
        "amount": 1.0, "fee": 0.01, "status": "open", "mode": "paper",
        "p_est": p["confidence"] / 100, "auto": True,
        "ts": datetime.now(CST).isoformat(),
        "reason": f"重大信号自动记录 conf={p['confidence']}",
        # 入场完整快照 (回测用)
        "entry": {
            "progress": c.get("progress_pct"),
            "open": price["open"],
            "current": price["current"],
            "body": price.get("body"),
            "confidence": p["confidence"],
            "strength": p["strength"],
            "regime": d.get("regime"),
            "mtf": d.get("mtf", {}),
        },
    }
    state["bets"].append(bet)
    save_paper(state)
    return side, ask


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


def record_limit(d, side, limit):
    """重大信号但 ask 追高 → 挂 LIMIT 单(限价=甜区上限), 等回调成交."""
    p = d["prediction"]
    c = d["candle"]
    price = d["price"]
    state = load_paper()
    bet = {
        "candle": c["iso"], "side": side, "limit": round(limit, 4),
        "amount": 1.0, "fee": 0.01, "status": "pending", "mode": "paper",
        "p_est": p["confidence"] / 100, "auto": True,
        "ts": datetime.now(CST).isoformat(),
        "entry": {
            "progress": c.get("progress_pct"),
            "open": price["open"], "current": price["current"],
            "confidence": p["confidence"], "strength": p["strength"],
            "regime": d.get("regime"), "mtf": d.get("mtf", {}),
        },
    }
    state["bets"].append(bet)
    save_paper(state)


def fetch_close(candle_iso):
    """拉该 5min K线的 (open, close). 返回 (open, close) 或 None."""
    try:
        dt = datetime.fromisoformat(candle_iso)
        start_ms = int(dt.timestamp() * 1000)
        url = (f"https://data-api.binance.vision/api/v3/klines"
               f"?symbol=BTCUSDT&interval=5m&startTime={start_ms}&limit=1")
        req = urllib.request.Request(url, headers={"User-Agent": "realtime/1"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if data:
            return float(data[0][1]), float(data[0][4])
    except Exception:
        pass
    return None


def fmt_account(state, last_pnl=None):
    """账户总览: 总资金(权益) + 本次盈亏 + 总盈亏(已实现)."""
    bankroll = state.get("bankroll", 100.0)
    realized = state.get("realized", 0.0)
    up, down = get_up_down_price()
    unrealized = 0.0
    for b in state.get("bets", []):
        if b.get("status") == "open":
            ask = b.get("ask", 0)
            cur = up if b["side"] == "UP" else down
            if cur is not None and ask and ask > 0:
                unrealized += b.get("amount", 1) * (cur - ask) / ask
    equity = bankroll + realized + unrealized
    last_s = f" | 本次 ${last_pnl:+.2f}" if last_pnl is not None else ""
    return (f"💰 总资金 ${equity:.2f}{last_s} | 总盈亏 ${realized:+.2f} "
            f"| 持仓浮盈 ${unrealized:+.2f}")


def settle_open(state, push_enabled=True):
    """结算已收盘的 open 单, 推送结算结果 + 账户总览. 返回结算数."""
    now_ms = int(time.time() * 1000)
    settled = 0
    for b in state.get("bets", []):
        if b.get("status") != "open" or not b.get("auto"):
            continue
        try:
            dt = datetime.fromisoformat(b["candle"])
            close_ms = int(dt.timestamp() * 1000) + 5 * 60 * 1000
        except Exception:
            continue
        if now_ms < close_ms:
            continue
        ohlc = fetch_close(b["candle"])
        if ohlc is None:
            continue
        o, c = ohlc
        won = (b["side"] == "UP" and c > o) or (b["side"] == "DOWN" and c < o)
        b["status"] = "settled"
        b["outcome"] = "win" if won else "loss"
        b["actual_open"] = o
        b["actual_close"] = c
        b["direction_correct"] = won
        amount = b.get("amount", 1.0)
        ask = b.get("ask", 0.0)
        fee = b.get("fee", 0.0)
        # 投入 amount 买 token @ ask: 赢→token变1,赚 amount*(1-ask)/ask; 输→token变0,亏 amount(全额)
        if won:
            b["pnl"] = round(amount * (1 - ask) / ask - amount * fee, 4)
        else:
            b["pnl"] = round(-amount - amount * fee, 4)
        b["pnl_pct"] = round(b["pnl"] / amount * 100, 2) if amount else 0.0
        settled += 1
    # 重建 realized (所有 settled 单 pnl 总和)
    state["realized"] = round(sum(x.get("pnl", 0) for x in state.get("bets", [])
                                  if x.get("status") == "settled"), 4)
    if settled:
        save_paper(state)
        for b in state.get("bets", []):
            if b.get("status") == "settled" and b.get("auto") and not b.get("pushed_final"):
                mark = "✅ 中" if b.get("direction_correct") else "❌ 未中"
                acct = fmt_account(state, b["pnl"])
                push(f"🏁 结算 {b['candle'][5:16]} {b['side']} {mark}\n"
                     f"买入 {b.get('amount', 1):.0f}U @{b['ask']:.2f} | "
                     f"涨跌 {b.get('pnl_pct', 0):+.1f}% | PnL {b['pnl']:+.2f}$\n"
                     f"{acct}", push_enabled)
                b["pushed_final"] = True
        save_paper(state)
    return settled


def check_pending(push_enabled=True):
    """检查挂单: 回调到限价→成交, 收盘未触及→未成交. 返回是否有变化."""
    up, down = get_up_down_price()
    state = load_paper()
    changed = False
    for b in state.get("bets", []):
        if b.get("status") != "pending" or not b.get("auto"):
            continue
        try:
            close_ts = datetime.fromisoformat(b["candle"]).timestamp() + 300
        except Exception:
            continue
        # 收盘未触及 → 未成交
        if time.time() >= close_ts:
            b["status"] = "unfilled"
            changed = True
            print(f"❌ 未成交: {b['side']} 限价{b.get('limit')}", flush=True)
            acct = fmt_account(state)
            push(f"❌ 未成交 | {b['candle'][5:16]} {b['side']} 限价{b.get('limit')} 收盘未触及\n"
                 f"{acct}", push_enabled)
            continue
        # 回调到限价 → 成交 (静默, 结算时统一推送账户)
        ask = up if b["side"] == "UP" else down
        if ask is not None and ask <= b["limit"]:
            b["status"] = "open"
            b["ask"] = round(ask, 4)
            changed = True
            print(f"✅ 成交: {b['side']} @ {ask:.2f} (限价{b.get('limit')})", flush=True)
    if changed:
        save_paper(state)
    return changed


def fmt_skip_knife(d, side, ask):
    """接飞刀跳过的推送 (ask 低于甜区下限, 市场强烈反向)."""
    p = d["prediction"]
    c = d["candle"]
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    ask_s = f"{ask:.2f}" if ask is not None else "?"
    return (f"⚠️ 接飞刀跳过 | {dir_cn}\n"
            f"{c['candle_start']} | {side} ask {ask_s} < 甜区下限 0.40\n"
            f"置信 {p['confidence']} | 市场强烈反向, 不接飞刀")


def fmt_order(d, side, ask, probability=None):
    """概率套利下单推送."""
    p = d["prediction"]
    c = d["candle"]
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    edge_s = f" | edge {probability - ask:+.2f}" if probability is not None and ask is not None else ""
    prob_s = f"概率 {probability:.2f}" if probability is not None else f"置信 {p['confidence']}"
    return (f"🎯 概率套利·下单 | {dir_cn}\n"
            f"{c['candle_start']} | {side} @ {ask:.2f} | 1U\n"
            f"{prob_s} vs 市场 {ask:.2f}{edge_s} | 已记录")


def fmt_prediction(d, side, ask, probability, edge, action):
    """每根K线的预测快照 (方向+概率+市场价+edge+是否下单)."""
    p = d["prediction"]
    c = d["candle"]
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    ask_s = f"{ask:.2f}" if ask is not None else "?"
    edge_s = f"edge {edge:+.2f}" if edge is not None else "edge ?"
    return (f"📊 预测 {dir_cn} | {c['candle_start']} p{c.get('progress_pct', 0):.0f}%\n"
            f"概率 {probability:.2f} | 市场 {side} {ask_s} | {edge_s}\n"
            f"→ {action}")


def fmt_no_edge(d, side, ask, probability):
    """无 edge 跳过推送."""
    p = d["prediction"]
    c = d["candle"]
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    return (f"⏭️ 无edge跳过 | {dir_cn}\n"
            f"{c['candle_start']} | {side} 概率 {probability:.2f} ≤ 市场 {ask:.2f}\n"
            f"无 edge, 不下单")


def fmt_limit(d, side, limit, ask):
    """挂 LIMIT 单的推送."""
    p = d["prediction"]
    c = d["candle"]
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    ask_s = f"{ask:.2f}" if ask is not None else "?"
    return (f"🎯 重大信号·挂单 | {dir_cn}\n"
            f"{c['candle_start']} | {side} 限价 {limit:.2f} (现ask {ask_s})\n"
            f"置信 {p['confidence']} | 等回调成交")


def fmt_signal(d, up=None, down=None):
    p = d["prediction"]
    c = d["candle"]
    price = d["price"]
    open_p = price["open"]
    cur = price["current"]
    chg = cur - open_p
    chg_pct = chg / open_p * 100 if open_p else 0
    dir_cn = DIR_CN.get(p["bias"], p["bias"])
    side = "UP" if p["bias"] == "bull" else "DOWN"
    up_s = f"{up:.2f}" if up is not None else "?"
    down_s = f"{down:.2f}" if down is not None else "?"
    return (f"🎯 [重大信号] {dir_cn}\n"
            f"{c['candle_start']} progress {c['progress_pct']:.0f}% | "
            f"置信 {p['confidence']}\n"
            f"开 {open_p:.2f} → 现 {cur:.2f} ({chg:+.0f}$ {chg_pct:+.3f}%)\n"
            f"预测收 {p['pred_close']:,} | 强度 {p['strength']}\n"
            f"盘口: UP {up_s} | DOWN {down_s}\n"
            f"── 下单指令 ──\n"
            f"模拟: 回复「下单」买入 {side} 1U\n"
            f"真实: 回复「真实下单」买入 {side} 1U (当前5min, 真钱需确认)")


def main():
    ap = argparse.ArgumentParser(description="5minbtc 实时监控(5秒刷新, 捕捉重大信号)")
    ap.add_argument("--conf", type=int, default=70, help="重大信号置信度阈值(默认70)")
    ap.add_argument("--refresh", type=int, default=5, help="刷新间隔秒(默认5)")
    ap.add_argument("--push", action="store_true", help="推送 Telegram")
    ap.add_argument("--active-hours", type=str, default="20,21,22,23",
                    help="只在此时段下单(逗号分隔CST小时)")
    ap.add_argument("--min-edge", type=float, default=0.03,
                    help="最小edge(引擎概率-市场价), 低于此不下单(默认0.03)")
    args = ap.parse_args()

    active_hours = set(int(h) for h in args.active_hours.split(",") if h.strip())

    last_candle = None
    last_signal_conf = 0
    last_bias = None
    print(f"🟢 5minbtc 实时监控启动 | {args.refresh}s刷新 | conf≥{args.conf} | "
          f"下单时段 {sorted(active_hours)}点", flush=True)

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

        now_hour = datetime.now(CST).hour

        # 新K线 → 推预测快照 (每根K线一次: 方向+概率+市场价+edge+是否下单)
        if candle != last_candle:
            last_candle = candle
            last_signal_conf = 0
            last_bias = None
            up0, down0 = get_up_down_price()
            side0 = "UP" if bias == "bull" else "DOWN"
            ask0 = up0 if side0 == "UP" else down0
            prob0 = p.get("probability", p.get("confidence", 50) / 100)
            edge0 = prob0 - ask0 if ask0 is not None else None
            if now_hour not in active_hours:
                action = "非活跃时段"
            elif ask0 is None:
                action = "市场价不可用"
            elif edge0 >= args.min_edge:
                action = "🎯 下单"
            else:
                action = "⏭️ 跳过(无edge)"
            push(fmt_prediction(d, side0, ask0, prob0, edge0, action), args.push)

        # 活跃时段内才下单 (概率套利: 引擎概率 > 市场价才买)
        if now_hour in active_hours:
            if not has_auto_bet(candle):
                side = "UP" if bias == "bull" else "DOWN"
                up, down = get_up_down_price()
                ask = up if side == "UP" else down
                probability = p.get("probability", p.get("confidence", 50) / 100)
                if ask is not None and probability - ask >= args.min_edge:
                    # 概率 > 市场价 → 买 (EV = p - P > 0)
                    record_paper(d, up, down)
                    print(f"📝 概率套利下单: {side} 概率{probability:.2f} > 市场{ask:.2f} "
                          f"(edge {probability-ask:+.2f})", flush=True)
                    push(fmt_order(d, side, ask, probability), args.push)

        # 检查挂单 + 结算已收盘持仓 (每5秒)
        check_pending(args.push)
        settle_open(load_paper(), args.push)

        time.sleep(args.refresh)


if __name__ == "__main__":
    main()
