#!/usr/bin/env python3
"""5minbtc 模拟下单 (paper) — 用户确认重大信号后买入 1U.

跑引擎拿当前方向 + UP/DOWN 真实价, 记录到 paper 台账.
🔒 纯模拟: 只写台账, 绝不调 place_order (LIVE_GATE 硬闸门).

用法:
  python3 5minbtc_order.py --amount 1   # 按当前引擎方向模拟买入
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
ENGINE = SKILL / "5minbtc-engine-v5.7.py"
PAPER = Path.home() / "bb-auto" / "5minbtc-paper.json"
PUSH = SCRIPTS / "telegram_push.py"
PY = "/usr/bin/python3"
CST = timezone(timedelta(hours=8))


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


def run_engine():
    try:
        out = subprocess.run([PY, str(ENGINE)], capture_output=True,
                             text=True, timeout=45)
        return json.loads(out.stdout)
    except Exception:
        return None


def get_up_down_price():
    """拉当前 BTC 5m 预测市场 UP/DOWN 真实价. 失败返回 (None, None)."""
    try:
        sys.path.insert(0, str(SCRIPTS))
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


def push(msg):
    try:
        subprocess.run([PY, str(PUSH), msg], capture_output=True, timeout=20)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="5minbtc 模拟下单 (paper)")
    ap.add_argument("--amount", type=float, default=1.0, help="下单金额 USDT (默认1)")
    args = ap.parse_args()

    load_env()
    d = run_engine()
    if not d:
        print("❌ 引擎失败, 无法下单")
        return 1
    p = d["prediction"]
    c = d["candle"]
    if p["bias"] == "neutral":
        print(f"❌ 当前方向中性, 不下单 (bias={p['bias']})")
        return 0

    side = "UP" if p["bias"] == "bull" else "DOWN"
    up_price, down_price = get_up_down_price()
    ask = up_price if side == "UP" else down_price
    if ask is None:
        print(f"⚠️ 无法获取 {side} 真实价, 用引擎预测价代替")
        ask = round((p["pred_close"] / d["price"]["current"]) - 1 + 0.5, 4)
        ask = max(0.05, min(0.95, ask))

    state = load_paper()
    bet = {
        "candle": c["iso"], "side": side, "ask": round(ask, 4),
        "amount": args.amount, "fee": 0.01, "status": "open", "mode": "paper",
        "p_est": p["confidence"] / 100,
        "manual": True,
        "ts": datetime.now(CST).isoformat(),
        "reason": f"手动确认下单 conf={p['confidence']}",
    }
    state["bets"].append(bet)
    save_paper(state)

    dir_cn = "看多·收阳" if side == "UP" else "看空·收阴"
    msg = (f"✅ 模拟下单已确认\n"
           f"{dir_cn} | {side} @ {ask:.2f} | {args.amount}U\n"
           f"{c['candle_start']} progress {c['progress_pct']:.0f}% | "
           f"置信 {p['confidence']}\n"
           f"(纯模拟, 台账记录, 绝不下真实单)")
    print(msg)
    push(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
