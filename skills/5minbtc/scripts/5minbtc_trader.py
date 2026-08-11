#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/5minbtc_trader.py - 5minbtc 预测 → 币安合约自动交易桥接

读取 5minbtc 引擎 JSON 预测, 判定交易信号, 调用 bb-scalper 的
cli/trade_exec.py 执行 (默认 --test 演练; --live 需显式指定).

安全契约 (铁律):
- 每笔下单前必须用户输入 y 确认 (确认闸门 _confirm), 绝不自动下单
- 默认演练 (币安 test 接口, 不真实成交); --live 实盘另需密钥 + yes
- 止盈止损: 由 trade_exec 下 STOP_MARKET/TAKE_PROFIT_MARKET reduceOnly 条件单
  (入场 LIMIT 成交后自动挂单, 见 bb-scalper/cli/trade_exec.py _execute)

设计要点 (对齐 bb-scalper 安全模型):
- 信号门槛: conf >= MIN_CONF 且 strength 达标才触发, 减少区间横跳磨损
- taker_buy 过滤: 方向必须与主动买卖方向一致 (bear+tb<0 / bull+tb>0)
- 单仓原则: 已持有则不开新仓 (依赖 trade_exec 持仓防重兜底)
- 止盈/止损: 用引擎 pred 区间 + ATR 计算, 交给 trade_exec 条件单
- 幂等: 每根K线只尝试一次开仓, clientOrderId 由 trade_exec 管理

用法:
  # 演练 (默认, 走币安 test 接口, 不真实成交)
  python3 scripts/5minbtc_trader.py --once            # 单次判断+演练下单
  python3 scripts/5minbtc_trader.py --loop            # 持续监控(每根K线2/3/4分钟)
  # 实盘 (危险! 需 BINANCE_API_KEY/SECRET + 显式 --live + 交互确认)
  python3 scripts/5minbtc_trader.py --once --live     # 真实下单前会二次确认

环境变量: BINANCE_API_KEY / BINANCE_API_SECRET (trade_exec 需要)
非投资建议 — 仅供量化研究与演练, 市场风险自负.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # = skill 根 (5minbtc/)
ENGINE = ROOT / "5minbtc-engine-v5.7.py"
# bb-scalper 项目 (含 trade_exec.py), 与 AGI-Super-Team 同级
BB_SCALPER = ROOT.parent.parent.parent / "projects" / "bb-scalper"
TRADE_EXEC = BB_SCALPER / "cli" / "trade_exec.py"

# 信号门槛
MIN_CONF = 55          # conf >= 55 才触发 (低于此区间横跳无意义)
ALLOWED_STRENGTHS = ("medium", "moderate", "strong")
TB_FILTER = True       # 方向必须与 taker_buy 一致

# 仓位 (演练默认小仓, 不碰 config 的 10x)
DEFAULT_QTY = 100      # 名义金额 USDT
DEFAULT_LEVERAGE = 3   # 演练用 3x, 实盘请自己改成 config 值

SAMPLE_MINUTES = (2, 3, 4)   # 每根 5min K线采样分钟
SAMPLE_SECOND = 5


def _load_engine():
    """运行引擎, 返回 dict 或 None."""
    if not ENGINE.exists():
        print(f"ERROR engine not found: {ENGINE}", file=sys.stderr)
        return None
    try:
        out = subprocess.run(["python3", str(ENGINE)],
                             capture_output=True, text=True, timeout=45)
        return json.loads(out.stdout)
    except Exception as e:  # noqa: BLE001
        print(f"engine error: {e}", file=sys.stderr)
        return None


def _signal(d):
    """从引擎输出判定交易信号. 返回 (side, reason) 或 (None, reason)."""
    p = d["prediction"]
    f = d["factors"]
    bias, strength, conf = p["bias"], p["strength"], p["confidence"]
    tb = f.get("taker_buy", 0.0)

    if conf < MIN_CONF:
        return None, f"conf {conf} < {MIN_CONF}"
    if strength not in ALLOWED_STRENGTHS:
        return None, f"strength {strength} 不足"
    if bias == "neutral":
        return None, "neutral"

    if TB_FILTER:
        if bias == "bear" and tb >= 0:
            return None, f"bear 但 taker_buy {tb:+.2f} ≥ 0, 方向不一致"
        if bias == "bull" and tb <= 0:
            return None, f"bull 但 taker_buy {tb:+.2f} ≤ 0, 方向不一致"

    side = "SHORT" if bias == "bear" else "LONG"
    return side, f"{bias}/{strength} conf={conf} tb={tb:+.2f}"


def _params(d, side):
    """从引擎输出计算 入场/止盈/止损/数量. 返回 dict 或 None."""
    p = d["prediction"]
    i = d["indicators"]
    cur = d["price"]["current"]
    atr = i.get("atr", 0)
    if atr <= 0:
        print("ERROR atr<=0, 无法计算止损", file=sys.stderr)
        return None

    pred_close = p["pred_close"]
    # 止盈: 预测收盘方向一侧 (轨对轨思路)
    if side == "LONG":
        tp = max(pred_close, cur + 1.5 * atr)
        sl = cur - 1.0 * atr
    else:
        tp = min(pred_close, cur - 1.5 * atr)
        sl = cur + 1.0 * atr

    return {
        "symbol": "BTCUSDT",
        "side": side,
        "entry": round(cur, 1),
        "tp": round(tp, 1),
        "sl": round(sl, 1),
        "qty": DEFAULT_QTY,
        "leverage": DEFAULT_LEVERAGE,
    }


def _confirm(params, live):
    """人工确认闸门: 打印交易计划, 等用户输入 y/N. 返回 True=同意."""
    mode = "实盘" if live else "演练"
    print(f"\n--- 待确认 {mode} 交易计划 ---")
    print(f"  方向: {params['side']}  {params['symbol']}")
    print(f"  入场: {params['entry']}   止盈: {params['tp']}   止损: {params['sl']}")
    print(f"  名义: {params['qty']} USDT  杠杆: {params['leverage']}x")
    print("  (演练=币安test接口, 不真实成交)")
    try:
        ans = input(f"  同意下单? [y/N]: ").strip().lower()
    except EOFError:
        ans = ""
    return ans in ("y", "yes")


def _trade(params, test, live=False):
    """调用 trade_exec.py. test=True 演练; live=True 实盘(需 env + 确认)."""
    if not TRADE_EXEC.exists():
        print(f"ERROR trade_exec not found: {TRADE_EXEC}", file=sys.stderr)
        return False
    cmd = [
        "python3", str(TRADE_EXEC),
        "--symbol", params["symbol"],
        "--side", params["side"],
        "--entry", str(params["entry"]),
        "--tp", str(params["tp"]),
        "--sl", str(params["sl"]),
        "--qty", str(params["qty"]),
        "--leverage", str(params["leverage"]),
    ]
    if live:
        cmd.append("--live")
        # trade_exec 内部会要求输入 yes 确认; 这里不注入, 让用户看到
    else:
        cmd.append("--test")

    print(f"\n==> 调用 trade_exec: {'实盘' if live else '演练'} {params['side']} "
          f"@{params['entry']} tp={params['tp']} sl={params['sl']} qty={params['qty']}")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print(out.stdout)
        if out.stderr:
            print(out.stderr, file=sys.stderr)
        return out.returncode == 0
    except Exception as e:  # noqa: BLE001
        print(f"trade_exec error: {e}", file=sys.stderr)
        return False


def _now_minute_ok():
    """当前是否处于采样分钟 (第 2/3/4 分钟)."""
    now = datetime.datetime.now()
    return now.minute % 5 in SAMPLE_MINUTES and now.second >= SAMPLE_SECOND


def once(live=False):
    """单次: 判断 + (可选)下单."""
    d = _load_engine()
    if not d:
        return 1
    side, reason = _signal(d)
    c = d["candle"]
    p = d["prediction"]
    print(f"[{c.get('iso')} p{c.get('progress_pct',0):.0f}%] "
          f"{p['bias']}/{p['strength']} conf={p['confidence']} "
          f"px={d['price']['current']} tb={d['factors'].get('taker_buy'):+.2f}")
    print(f"信号: {side or '无'}  ({reason})")
    if not side:
        return 0
    params = _params(d, side)
    if not params:
        return 1
    if not _confirm(params, live):
        print("已取消下单")
        return 0
    _trade(params, test=not live, live=live)
    return 0


def loop(live=False, rounds=None):
    """持续监控: 每根K线第2/3/4分钟采样判断+下单."""
    seen = set()
    n = 0
    while rounds is None or n < rounds:
        now = datetime.datetime.now()
        if _now_minute_ok():
            d = _load_engine()
            if d:
                c = d["candle"]
                key = (c["iso"], now.minute // 5)  # 每根K线每5分钟块只处理一次
                if key not in seen:
                    seen.add(key)
                    n += 1
                    side, reason = _signal(d)
                    p = d["prediction"]
                    print(f"\n[{c.get('iso')} p{c.get('progress_pct',0):.0f}%] "
                          f"{p['bias']}/{p['strength']} conf={p['confidence']} "
                          f"px={d['price']['current']} tb={d['factors'].get('taker_buy'):+.2f}")
                    print(f"信号: {side or '无'}  ({reason})")
                    if side:
                        params = _params(d, side)
                        if params:
                            if _confirm(params, live):
                                _trade(params, test=not live, live=live)
                            else:
                                print("已取消下单")
            time.sleep(20)
        else:
            time.sleep(10)
    return 0


def main():
    ap = argparse.ArgumentParser(description="5minbtc→币安合约 桥接 (默认演练)")
    ap.add_argument("--once", action="store_true", help="单次判断+演练下单")
    ap.add_argument("--loop", action="store_true", help="持续监控(每根K线2/3/4分钟)")
    ap.add_argument("--live", action="store_true", help="实盘模式(危险! 需密钥+确认)")
    ap.add_argument("--rounds", type=int, default=None, help="loop 轮数上限(默认无限)")
    args = ap.parse_args()

    if args.live:
        if not os.environ.get("BINANCE_API_KEY") or not os.environ.get("BINANCE_API_SECRET"):
            print("❌ 实盘需 BINANCE_API_KEY/BINANCE_API_SECRET 环境变量")
            return 1
        print("\n⚠️⚠️  实盘模式! 将真实下单。\n")
        try:
            confirm = input("确认真实下单? 输入 yes: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm != "yes":
            print("已取消")
            return 0

    if args.once:
        return once(live=args.live)
    if args.loop:
        return loop(live=args.live, rounds=args.rounds)

    print("用法: --once 单次 | --loop 持续 | 加 --live 实盘(危险)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
