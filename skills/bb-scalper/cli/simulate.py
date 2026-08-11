#!/usr/bin/env python3
"""
cli/simulate.py — 历史回测 + 实时模拟交易

用法:
  python cli/simulate.py --symbol NEARUSDT --hours 168    # 历史回测
  python cli/simulate.py --scan                             # 扫 20 币短回测
  python cli/simulate.py --paper                            # 实时模拟（不下单）
  python cli/simulate.py --symbol AVAXUSDT --hours 72 --verbose

模拟 vs 实盘:
  --backtest  : 历史数据回测（纯离线，不涉及钱）
  --paper     : 实时数据 + 模拟下单（验证策略，不涉及钱）
  --live 要通过 cli/trade_exec.py 执行

TODO:
  - [ ] 回测引擎核心（逐根遍历 + 三重过滤 + 冷却）
  - [ ] 多币种并发回测
  - [ ] 模拟订单簿滑点
  - [ ] 手续费模拟
  - [ ] 最大回撤 / 夏普比率 计算
  - [ ] 输出回测报告 JSON
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Simulator:
    """回测引擎"""

    def __init__(self, config: dict):
        self.cfg = config
        self.trades = []
        self.capital = config.get("risk", {}).get("simulated_capital", 500)
        self.last_sl_index = -999

    def fetch_klines(self, symbol: str, interval: str, limit: int) -> list:
        """获取 K 线数据"""
        import requests
        resp = requests.get("https://fapi.binance.com/fapi/v1/klines", params={
            "symbol": symbol, "interval": interval, "limit": limit
        }, timeout=15)
        resp.raise_for_status()
        return [{"open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
                 "close": float(k[4]), "volume": float(k[5]), "time": int(k[0])}
                for k in resp.json()]

    def calc_bb(self, closes: np.ndarray, period=20, std=2.0) -> Optional[dict]:
        if len(closes) < period:
            return None
        sma = np.mean(closes[-period:])
        s = np.std(closes[-period:], ddof=1)
        upper, lower = sma + std * s, sma - std * s
        width = (upper - lower) / sma
        slope = 0.0
        if len(closes) >= 8:
            y = closes[-8:]
            slope = np.polyfit(np.arange(len(y)), y, 1)[0] / sma
        pct_b = (closes[-1] - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
        return {"middle": sma, "upper": upper, "lower": lower,
                "width": width, "slope": slope, "pct_b": pct_b, "std": s}

    def calc_rsi(self, closes: np.ndarray, period=14) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-period-1:])
        gains = np.maximum(deltas, 0)
        losses = np.maximum(-deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) if avg_loss > 0 else 100.0

    def simulate_trade(self, closes, idx, entry, stop, tp, direction, ts):
        """逐根模拟一笔交易到 TP/SL 或超时"""
        future = closes[idx+1:idx+49]
        for fc in future:
            if direction == "LONG":
                if fc <= stop:
                    return {"time": ts, "dir": direction, "entry": entry, "exit": stop,
                            "pnl_pct": (stop-entry)/entry*10, "result": "SL"}
                if fc >= tp:
                    return {"time": ts, "dir": direction, "entry": entry, "exit": tp,
                            "pnl_pct": (tp-entry)/entry*10, "result": "TP"}
            else:
                if fc >= stop:
                    return {"time": ts, "dir": direction, "entry": entry, "exit": stop,
                            "pnl_pct": (entry-stop)/entry*10, "result": "SL"}
                if fc <= tp:
                    return {"time": ts, "dir": direction, "entry": entry, "exit": tp,
                            "pnl_pct": (entry-tp)/entry*10, "result": "TP"}
        exit_price = future[-1] if len(future) > 0 else closes[idx]
        return {"time": ts, "dir": direction, "entry": entry, "exit": exit_price,
                "pnl_pct": (exit_price-entry)/entry*10*(1 if direction=="LONG" else -1),
                "result": "OPEN"}

    def backtest(self, symbol: str, hours: int, verbose: bool = False) -> dict:
        """执行回测，返回摘要"""
        print(f"🔍 {symbol} 回溯 {hours}h | 三重过滤 | 10x 杠杆\n")
        bars = self.fetch_klines(symbol, "15m", limit=hours*4+100)
        closes = np.array([b["close"] for b in bars])

        # 构建 1h 近似
        closes_1h = np.array([bars[i]["close"] for i in range(0, len(bars), 4)])

        bb_period = self.cfg.get("bb", {}).get("period", 20)
        sweet_min = self.cfg.get("bb", {}).get("sweet_min", 0.008)
        sweet_max = self.cfg.get("bb", {}).get("sweet_max", 0.025)
        stop_buf = self.cfg.get("trade", {}).get("stop_buffer", 0.0015)
        entry_th = self.cfg.get("trade", {}).get("entry_threshold", 0.002)
        slope_max = self.cfg.get("filters", {}).get("trend_slope_max", 0.0003)
        slope_loose = self.cfg.get("filters", {}).get("trend_slope_loose", 0.0006)
        rsi_long = self.cfg.get("filters", {}).get("rsi_long_max", 55)
        rsi_short = self.cfg.get("filters", {}).get("rsi_short_min", 45)
        cool = self.cfg.get("filters", {}).get("cooldown_candles", 3)

        trades = []
        last_sl = -cool - 1

        for i in range(bb_period + 10, len(bars) - 24):
            window = closes[:i+1]
            bb = self.calc_bb(window)
            rsi = self.calc_rsi(window)
            if bb is None or rsi is None:
                continue

            # 🔧 三重过滤
            if bb["width"] < sweet_min or bb["width"] > sweet_max:
                continue

            h_idx = i // 4
            slope_1h = 0.0
            if h_idx >= 8 and h_idx < len(closes_1h):
                y = closes_1h[max(0,h_idx-8):h_idx+1]
                if len(y) >= 4:
                    slope_1h = np.polyfit(np.arange(len(y)), y, 1)[0] / np.mean(y)

            if i - last_sl < cool:
                continue

            lower, upper = bb["lower"], bb["upper"]

            if bb["pct_b"] < 0.15:
                if slope_1h < -slope_loose or rsi > rsi_long:
                    continue
                entry = lower * (1 + entry_th / 2)
                t = self.simulate_trade(closes, i, entry, lower*(1-stop_buf), upper, "LONG", bars[i]["time"])
                trades.append(t)
                if t["result"] == "SL":
                    last_sl = i

            if bb["pct_b"] > 0.85:
                if slope_1h > slope_loose or rsi < rsi_short:
                    continue
                entry = upper * (1 - entry_th / 2)
                t = self.simulate_trade(closes, i, entry, upper*(1+stop_buf), lower, "SHORT", bars[i]["time"])
                trades.append(t)
                if t["result"] == "SL":
                    last_sl = i

        if not trades:
            print(f"  📭 {hours}h 内无符合三重过滤的信号")
            return {"symbol": symbol, "total": 0, "win_rate": 0, "total_pnl": 0}

        wins = [t for t in trades if t["result"]=="TP"]
        losses = [t for t in trades if t["result"]=="SL"]
        total = len(trades)
        wr = len(wins)/(len(wins)+len(losses))*100 if len(wins)+len(losses)>0 else 0
        avg_w = np.mean([t["pnl_pct"]*100 for t in wins]) if wins else 0
        avg_l = np.mean([t["pnl_pct"]*100 for t in losses]) if losses else 0
        total_pnl = sum(t["pnl_pct"]*100 for t in trades)
        ev = wr/100*avg_w + (1-wr/100)*avg_l if len(wins)+len(losses)>0 else 0

        print(f"  📊 {symbol}")
        print(f"     信号: {total} | TP: {len(wins)} | SL: {len(losses)}")
        print(f"     胜率: {wr:.0f}% | 均盈: {avg_w:+.1f}% | 均亏: {avg_l:+.1f}%")
        print(f"     期望值: {ev:+.2f}% | 累计: {total_pnl:+.1f}%")

        if verbose and trades:
            print(f"\n  📋 信号明细:")
            for t in trades[-15:]:
                ts = datetime.fromtimestamp(t["time"]/1000, tz=timezone.utc)
                bar = "✅" if t["result"]=="TP" else "❌"
                pnl = t["pnl_pct"]*100
                print(f"    {ts.strftime('%m-%d %H:%M')} {t['dir']:5s} {bar} {pnl:+.1f}% ({t['entry']:.4f}→{t['exit']:.4f})")

        return {"symbol": symbol, "total": total, "win_rate": wr,
                "total_pnl": total_pnl, "avg_win": avg_w, "avg_loss": avg_l, "expectancy": ev}


def main():
    parser = argparse.ArgumentParser(description="BB套利 - 模拟交易")
    parser.add_argument("--symbol", default="NEARUSDT")
    parser.add_argument("--hours", type=int, default=168)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--paper", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--config", default=os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config.yaml"))
    args = parser.parse_args()

    # 加载配置
    try:
        import yaml
        with open(args.config) as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}

    sim = Simulator(config)

    if args.scan:
        symbols = ["NEARUSDT","AVAXUSDT","INJUSDT","DOGEUSDT","SUIUSDT",
                    "BTCUSDT","ETHUSDT","SOLUSDT","LINKUSDT","LTCUSDT"]
        total_results = []
        for sym in symbols:
            try:
                r = sim.backtest(sym, 72, verbose=False)
                if r["total"] > 0:
                    total_results.append(r)
                time.sleep(0.2)
            except Exception as e:
                print(f"  ❌ {sym}: {e}")

        print(f"\n{'─'*60}")
        print(f"📊 扫描总结 ({len(total_results)} 个有信号币种)")
        print(f"{'─'*60}")
        total_results.sort(key=lambda r: r["total_pnl"], reverse=True)
        for r in total_results:
            print(f"  {r['symbol']:10s} {r['total']:3d}笔 | {r['win_rate']:.0f}% WR | {r['total_pnl']:+.1f}% PnL")
        return

    if args.paper:
        print("🟡 模拟模式启动（实时数据 + 虚拟下单）")
        print("   每 30s 扫一次...")
        print("   TODO: 实时 WebSocket 监听")
        return

    sim.backtest(args.symbol, args.hours, verbose=args.verbose)


if __name__ == "__main__":
    main()
