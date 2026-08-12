#!/usr/bin/env python3
"""5minbtc 预测市场 · 免密钥模拟盘 (keyless paper) — 无需币安 API 密钥.

用公开 BTC 数据 (data-api.binance.vision) 模拟 UP/DOWN token 价:
    P_up = sigmoid(1.7 × 当前涨跌幅 / ATR)     # 纯价格走势模型 = "市场"定价
引擎信号 (含订单簿/taker 信息) = 你的 edge;  当 P_up < p 时买入 = EV+.

与真实 paper 监控同一套 LIMIT 单/成交/结算/账户节奏, 只是价格源换成模拟价.
真实市场价源 (需要密钥) 就绪后, 切换回 5minbtc_trader.py --paper-monitor.

用法:
  python3 5minbtc_keyless_paper.py [--up-max 0.65] [--down-max 0.50]
      [--amount 1] [--bankroll 100] [--push]

每根 5min K 线节奏:
  第0分钟: 结算上一轮 → 推送获利 + 账户权益
  第2分钟: 引擎确认方向+入场价 → 设模拟 LIMIT (方向锁定)
  第2分钟后: 轮询 spot → P_up 更新 → ask≤限价 → 成交记录 + 实时涨跌幅
  第3分钟: 只预测, 不改变 LIMIT 方向
  收盘: 按实际 BTC 收盘结算
"""
import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
PAPER_FILE = Path.home() / "bb-auto" / "5minbtc-paper-keyless.json"
PUSH = SCRIPTS / "telegram_push.py"
SPOT_URL = "https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT"
SAMPLE_SECOND = 5
SIGMOID_K = 1.7          # 走势→价格灵敏度 (可调: 越大价格越随走势走)


def _trader():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("5minbtc_trader")


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def _spot():
    try:
        req = urllib.request.Request(SPOT_URL, headers={"User-Agent": "keyless/1"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return float(json.loads(r.read())["price"])
    except Exception:
        return None


def _sim_up_price(open_, atr, spot):
    """模拟 UP token 价 = P(收阳 | 当前走势). DOWN 价 = 1 − UP 价."""
    move_price = spot - open_
    z = (move_price / max(atr, 1e-9)) * SIGMOID_K
    return max(0.02, min(0.98, _sigmoid(z)))


def _push(msg, push=True):
    if not push:
        return
    try:
        subprocess.run(["/usr/bin/python3", str(PUSH), msg], capture_output=True,
                       timeout=20)
    except Exception:
        pass


def _load_state():
    t = _trader()
    state = t.load_paper(str(PAPER_FILE))
    return state


def _save_state(state):
    _trader().save_paper(str(PAPER_FILE), state)


def _settle(state, fee):
    return _trader().settle_paper(state, fee)


def _equity(state, bankroll):
    return bankroll + state.get("realized", 0.0)


def main():
    ap = argparse.ArgumentParser(description="5minbtc 免密钥预测市场模拟盘")
    ap.add_argument("--up-max", type=float, default=0.65, help="UP 模拟价上限")
    ap.add_argument("--down-max", type=float, default=0.50, help="DOWN 模拟价上限")
    ap.add_argument("--amount", type=float, default=1.0, help="每注 USDT")
    ap.add_argument("--bankroll", type=float, default=100.0, help="模拟本金")
    ap.add_argument("--fee", type=float, default=0.0, help="手续费比例")
    ap.add_argument("--p-up", type=float, default=0.74, help="UP 信号预估概率 p")
    ap.add_argument("--p-down", type=float, default=0.57, help="DOWN 信号预估概率 p")
    ap.add_argument("--poll", type=int, default=10, help="轮询秒数 (keyless 用 spot)")
    ap.add_argument("--push", action="store_true", help="推送到 Telegram")
    ap.add_argument("--push-every", type=int, default=60)
    ap.add_argument("--push-delta", type=float, default=5.0)
    args = ap.parse_args()

    t = _trader()
    state = _load_state()
    if state.get("bankroll", 0) <= 0:
        state["bankroll"] = args.bankroll

    cur_candle = None
    did_2 = did_3 = False
    candle_open = None
    candle_atr = None
    last_pnl = {}
    last_live_ts = {}

    _push(f"🟢 免密钥模拟盘启动 | 本金 ${args.bankroll:.0f} 每注 {args.amount}U "
          f"| UP≤{args.up_max:.2f} DOWN≤{args.down_max:.2f} | 模拟价(无需密钥)", args.push)

    def _active_for(candle):
        return any(b.get("candle") == candle and b.get("status") in ("open", "pending")
                   for b in state["bets"])

    def _candle_remain(b):
        try:
            close_ts = datetime.fromisoformat(b["candle"]).timestamp() + 300
            return close_ts - time.time()
        except Exception:
            return 999.0

    def _token_price_for(b, spot, open_, atr):
        up = _sim_up_price(open_, atr, spot)
        return up if b.get("side") == "UP" else (1 - up)

    while True:
        now = datetime.now()
        minute = now.minute % 5

        # 第0分钟: 结算 + 账户
        if minute == 0 and now.second < 20:
            settled = _settle(state, args.fee)
            if settled:
                for b in state["bets"]:
                    if b.get("status") == "settled" and not b.get("pushed_final"):
                        pnl_pct = ((1 - b["ask"]) / b["ask"] * 100 - args.fee * 100
                                   if b.get("outcome") == "win" else -100 - args.fee * 100)
                        mark = "✅ 中" if b.get("outcome") == "win" else "❌ 未中"
                        _push(f"🏁 结算 {b['candle'][5:16]} {b['side']} @{b['ask']:.2f} {mark}\n"
                              f"获利 {pnl_pct:+.1f}% | ${b.get('pnl', 0):+.2f}", args.push)
                        b["pushed_final"] = True
                eq = _equity(state, args.bankroll)
                br = state.get("bankroll", args.bankroll)
                _push(f"💼 账户 ${br:.0f} → ${eq:.2f} "
                      f"({(eq - br) / br * 100:+.2f}%)", args.push)
                _save_state(state)

        # 第2/3分钟: 引擎
        if minute in (2, 3) and now.second >= SAMPLE_SECOND:
            d = t._load_engine()
            if d:
                candle = d["candle"]["iso"]
                if candle != cur_candle:
                    cur_candle = candle
                    did_2 = did_3 = False
                    candle_open = d["price"]["open"]
                    candle_atr = d["indicators"].get("atr") or 40.0
                side, reason = t._signal(d, min_conf=0, tb_filter=False,
                                         strength_gate=False)
                spot = _spot()

                def _place(side_, reason_, tag):
                    """设模拟 LIMIT 单 (立即成交或挂单). 返回是否下单."""
                    if not side_ or _active_for(candle) or spot is None:
                        return False
                    p_est = args.p_up if side_ == "UP" else args.p_down
                    limit = args.up_max if side_ == "UP" else args.down_max
                    p_up = _sim_up_price(candle_open, candle_atr, spot)
                    ask = p_up if side_ == "UP" else (1 - p_up)
                    if ask <= limit:
                        state["bets"].append({
                            "candle": candle, "side": side_, "ask": round(ask, 4),
                            "amount": args.amount, "fee": args.fee, "status": "open",
                            "p_est": p_est,
                            "ts": datetime.now().isoformat(), "reason": reason_,
                        })
                        _save_state(state)
                        _push(f"✅ 立即成交 | {candle[5:16]} {tag} {side_}\n"
                              f"模拟价 {ask:.2f} (限价 {limit:.2f}内) | p={p_est:.2f}\n"
                              f"持仓 {args.amount}U | 涨跌幅 0% 起算", args.push)
                    else:
                        state["bets"].append({
                            "candle": candle, "side": side_,
                            "limit": round(limit, 4), "status": "pending",
                            "p_est": p_est,
                            "ts": datetime.now().isoformat(), "reason": reason_,
                        })
                        _save_state(state)
                        _push(f"📋 LIMIT | {candle[5:16]} {tag}\n"
                              f"{side_} 限价 {limit:.2f} (p={p_est:.2f}) | "
                              f"模拟现价 {ask:.2f}\n"
                              f"成交时 EV {p_est - limit:+.2f} | 等回调 | {args.amount}U", args.push)
                    return True

                if minute == 2 and not did_2:
                    did_2 = True
                    _place(side, reason, "第2min")
                elif minute == 3 and not did_3:
                    did_3 = True
                    if not _active_for(candle):
                        # 第2分钟中性 → 第3分钟第二次机会下单
                        if not _place(side, reason, "第3min"):
                            p = d["prediction"]
                            _push(f"🔎 第3分钟预测 | {candle[5:16]}\n"
                                  f"现价 {d['price']['current']:,.2f} | "
                                  f"{p['bias']}/{p['strength']} conf {p['confidence']}\n"
                                  f"(仍无信号, 不设LIMIT)", args.push)
                    # 已有活跃单: LIMIT 方向锁定, 静默

        # 成交检测 + 实时涨跌幅 (用 spot → 模拟价)
        now_ts = time.time()
        spot = _spot()
        has_pending = False
        if spot is not None and candle_open is not None:
            for b in state["bets"]:
                if b.get("status") == "pending":
                    has_pending = True
                    ask = _token_price_for(b, spot, candle_open, candle_atr)
                    if ask <= b["limit"]:
                        b["status"] = "open"
                        b["ask"] = round(ask, 4)
                        b["amount"] = args.amount
                        b["fee"] = args.fee
                        _save_state(state)
                        _push(f"✅ 成交 | {b['candle'][5:16]} {b['side']} @ {ask:.2f} "
                              f"(限价 {b['limit']:.2f})\n"
                              f"持仓 {args.amount}U | 涨跌幅 0% 起算 | 等结算", args.push)
                    elif _candle_remain(b) <= 0:
                        b["status"] = "unfilled"
                        _save_state(state)
                        _push(f"❌ 未成交 | {b['candle'][5:16]} {b['side']}\n"
                              f"限价 {b['limit']:.2f} 收盘未触及 | 放弃", args.push)
                    continue
                if b.get("status") != "open":
                    continue
                ask = b["ask"]
                cur = _token_price_for(b, spot, candle_open, candle_atr)
                pnl_pct = (cur - ask) / ask * 100
                last = last_pnl.get(str(b.get("token_id") or b.get("candle")))
                key = str(b.get("candle")) + b.get("side", "")
                last = last_pnl.get(key)
                if (last is None or abs(pnl_pct - last) >= args.push_delta
                        or now_ts - last_live_ts.get(key, 0) >= args.push_every):
                    remain = _candle_remain(b)
                    _push(f"📡 {b['side']} @{ask:.2f} → 模拟价 {cur:.2f}\n"
                          f"涨跌幅 {pnl_pct:+.1f}% | 剩余 "
                          f"{int(max(remain, 0)) // 60}m{int(max(remain, 0)) % 60:02d}s", args.push)
                    last_pnl[key] = pnl_pct
                    last_live_ts[key] = now_ts

        time.sleep(10 if has_pending else args.poll)


if __name__ == "__main__":
    main()
