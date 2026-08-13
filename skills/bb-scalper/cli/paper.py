"""
cli/paper.py — WebSocket 实时模拟盘（Paper Trading）

用币安实时行情(ws 流)驱动策略: 订阅 K 线 + 逐笔成交(trade)流,
按当前价/K线高低点判断止盈/止损/超时平仓。全程虚拟资金, 不碰真钱。

用法:
  python cli/paper.py --symbol NEARUSDT              # 单币模拟盘
  python cli/paper.py --symbol NEARUSDT --capital 500
  python cli/paper.py --symbols NEARUSDT,BTCUSDT     # 多币(实验)

数据源: wss://fstream.binance.com
  kline_15m   : 15m K线(用于 BB/RSI/三重过滤/市场分类)
  kline_1h    : 1h K线(用于趋势过滤的中轨斜率)
  trade       : 逐笔成交(秒级触发)

安全: 只读行情流, 无任何下单/资金操作。
"""
import argparse
import asyncio
import json
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.logger import get_logger  # noqa: E402

try:
    import websockets
except ImportError:
    print("需要 websockets 库: pip install websockets")
    sys.exit(1)

logger = get_logger("paper")

WS_URL = "wss://fstream.binance.com/ws"

DEFAULT_CAPITAL = 500.0
MAX_POS = 12  # 最大持仓 15m K 线数(3h)
FEE_RATE = 0.0004  # taker 手续费 0.04%


def _load_config(path: str = None) -> dict:
    try:
        import yaml
        p = path or os.path.join(ROOT, "config.yaml")
        with open(p) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ── 指标(与 core.strategy 一致) ──
def calc_bollinger(closes, period=20, std_mult=2.0, live_price=None):
    if len(closes) < period:
        return None
    sma = float(np.mean(closes[-period:]))
    std = float(np.std(closes[-period:], ddof=1))
    upper, lower = sma + std_mult * std, sma - std_mult * std
    width = (upper - lower) / sma
    slope = 0.0
    if len(closes) >= 8:
        y = closes[-8:]
        slope = float(np.polyfit(np.arange(len(y)), y, 1)[0]) / sma
    # live_price 提供时用实时价计算 pct_b(信号判断), 否则用最后收盘
    price_for_pct = live_price if live_price is not None else closes[-1]
    pct_b = (price_for_pct - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
    return {"middle": sma, "upper": upper, "lower": lower,
            "width": width, "slope": slope, "pct_b": pct_b, "std": std}


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-period - 1:])
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


class PaperEngine:
    """单币 WS 模拟盘引擎"""

    def __init__(self, symbol: str, config: dict, capital: float = DEFAULT_CAPITAL,
                 log_path: Optional[str] = None):
        self.symbol = symbol.upper()
        self.cfg = config
        self.capital = capital
        self.log_path = log_path
        self.closes_15m = []
        self.closes_1h = []
        self.cur_price = None
        self.position = None  # {"dir","entry","tp","sl","opened_bar","opened_ts","qty_notional"}
        self.last_sl_bar = -999
        self.trades = self._load_trades()
        # 重启后恢复资金: 用历史交易的 PnL 重放 close() 的资金公式
        # capital += notional * pnl_pct / 100
        for t in self.trades:
            notional = t.get("notional", self.cfg.get("risk", {}).get("max_position_usd", 100))
            self.capital += notional * t.get("pnl_pct", 0) / 100
        self._bar_seq = 0
        self._tick_count = 0
        self._last_heartbeat = 0.0
        # 止损冷却: SL 后 _sl_cooldown_secs 秒内禁止重开, 防插针死循环
        # 默认按 config cooldown_candles(3根15m K线≈2700s)而非60s, 强趋势中避免快速重开
        self._cooldown_until_ts = 0.0
        cool_candles = self.cfg.get("filters", {}).get("cooldown_candles", 3)
        self._sl_cooldown_secs = cool_candles * 15 * 60
        # 每根15m K线最多触发一次入场: 防止同一固定下轨(收盘价序列滞后)在
        # 15分钟内被实时价反复触发同一入场价(DOT 10连亏根因)
        self._signal_fired_this_bar = False

    def _trades_path(self) -> Optional[str]:
        """每币独立落盘文件(防多币共享文件互相覆盖)。"""
        if not self.log_path:
            return None
        base, ext = os.path.splitext(self.log_path)
        return f"{base}_{self.symbol}{ext}"

    def _load_trades(self) -> list:
        """启动时加载本币已有的模拟交易记录(进程重启不丢历史)。"""
        path = self._trades_path()
        if not path or not os.path.exists(path):
            return []
        try:
            with open(path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError) as e:
            logger.error("[%s] 加载模拟交易记录失败: %s", self.symbol, e)
            return []

    def _persist_trades(self):
        """把本币模拟交易写入独立 JSON(含已恢复的历史)。"""
        path = self._trades_path()
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump(self.trades, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("[%s] 保存模拟交易记录失败: %s", self.symbol, e)

    # ── 信号 ──
    def check_signal(self):
        """有持仓返回 None; 无持仓时按三重过滤生成新信号。"""
        if self.position:
            return None
        # 本根15m K线已触发过入场 → 不再重复(防止同一固定下轨反复触发)
        if self._signal_fired_this_bar:
            return None
        # 止损冷却期内禁止重开(防插针死循环)
        if time.time() < self._cooldown_until_ts:
            return None
        # 用实时价(而非最后收盘)判断 %B, 否则会错过贴轨道瞬间
        bb = calc_bollinger(self.closes_15m, live_price=self.cur_price)
        if bb is None:
            return None
        rsi = calc_rsi(self.closes_15m)
        if rsi is None:
            return None
        slope_1h = self._slope_1h()
        w, pct, r = bb["width"], bb["pct_b"], rsi
        sweet_min = self.cfg.get("bb", {}).get("sweet_min", 0.008)
        sweet_max = self.cfg.get("bb", {}).get("sweet_max", 0.025)
        slope_max = self.cfg.get("filters", {}).get("trend_slope_max", 0.0003)
        slope_loose = self.cfg.get("filters", {}).get("trend_slope_loose", 0.0006)
        rsi_long_max = self.cfg.get("filters", {}).get("rsi_long_max", 55)
        rsi_short_min = self.cfg.get("filters", {}).get("rsi_short_min", 45)
        stop_buf = self.cfg.get("trade", {}).get("stop_buffer", 0.0015)
        entry_th = self.cfg.get("trade", {}).get("entry_threshold", 0.002)
        leverage = self.cfg.get("trade", {}).get("leverage", 10)

        if not (sweet_min <= w <= sweet_max):
            return None

        def _open(direction, entry, sl, tp):
            return {"dir": direction, "entry": entry, "sl": sl, "tp": tp,
                    "opened_bar": self._bar_seq,
                    "opened_ts": datetime.now(timezone.utc).isoformat(),
                    "notional": self.cfg.get("risk", {}).get("max_position_usd", 100),
                    "leverage": leverage}

        if pct < 0.15 and slope_1h > -slope_loose and rsi <= rsi_long_max:
            # 深跌保护: pct_b 太负(价格远跌破下轨)说明下跌动能强, 禁止接飞刀
            if pct < -0.5:
                return None
            entry = bb["lower"] * (1 + entry_th / 2)
            return ("LONG", _open("LONG", entry, bb["lower"] * (1 - stop_buf), bb["upper"]))
        if pct > 0.85 and slope_1h < slope_loose and rsi >= rsi_short_min:
            if pct > 1.5:  # 深涨保护
                return None
            entry = bb["upper"] * (1 - entry_th / 2)
            return ("SHORT", _open("SHORT", entry, bb["upper"] * (1 + stop_buf), bb["lower"]))
        return None

    def _slope_1h(self) -> float:
        if len(self.closes_1h) < 8:
            return 0.0
        y = self.closes_1h[-8:]
        return float(np.polyfit(np.arange(len(y)), y, 1)[0]) / float(np.mean(y))

    # ── 价格触发 ──
    def on_tick(self, price: float):
        """逐笔成交回调: 秒级判断触发。"""
        self.cur_price = price
        if not self.position:
            return None
        p = self.position
        if p["dir"] == "LONG":
            if price <= p["sl"]:
                # 止损单按止损价成交(模拟真实市价止损, 而非越过后第一个tick价)
                return self.close("SL", p["sl"])
            if price >= p["tp"]:
                return self.close("TP", p["tp"])
        else:
            if price >= p["sl"]:
                return self.close("SL", p["sl"])
            if price <= p["tp"]:
                return self.close("TP", p["tp"])
        return None

    def on_bar(self, low, high, ts):
        """每根 15m K线结束: 用 K线高低点判断穿透 + 超时平仓。"""
        self._bar_seq += 1
        # 新K线: 重置"本K线已触发"标记, 允许基于新轨道再次判断
        self._signal_fired_this_bar = False
        if not self.position:
            return None
        p = self.position
        if p["dir"] == "LONG":
            if low <= p["sl"]:
                return self.close("SL", p["sl"])
            if high >= p["tp"]:
                return self.close("TP", p["tp"])
        else:
            if high >= p["sl"]:
                return self.close("SL", p["sl"])
            if low <= p["tp"]:
                return self.close("TP", p["tp"])
        # 超时平仓
        if self._bar_seq - p["opened_bar"] >= MAX_POS:
            return self.close("TIMEOUT", self.cur_price or p["entry"])
        return None

    def _record_open(self):
        """记录建仓(OPEN状态), 作为复盘证据; 平仓时由 close() 更新为最终结果。"""
        p = self.position
        if p is None:
            return
        trade = {
            "symbol": self.symbol, "dir": p["dir"],
            "entry": p["entry"], "exit": None, "result": "OPEN",
            "pnl_pct": None, "sl": p.get("sl"), "tp": p.get("tp"),
            "notional": p["notional"], "leverage": p.get("leverage", 10),
            "opened_ts": p["opened_ts"], "closed_ts": None,
        }
        self.trades.append(trade)
        self._persist_trades()

    def close(self, result: str, exit_price: float) -> dict:
        p = self.position
        entry, lev = p["entry"], p["leverage"]
        pnl_pct = (exit_price - entry) / entry * lev * 100 * (1 if p["dir"] == "LONG" else -1)
        pnl_pct -= FEE_RATE * 100 * 2  # 双边手续费
        trade = {
            "symbol": self.symbol, "dir": p["dir"], "entry": entry,
            "exit": exit_price, "result": result, "pnl_pct": round(pnl_pct, 2),
            "notional": p["notional"], "leverage": lev,
            "opened_ts": p["opened_ts"],
            "closed_ts": datetime.now(timezone.utc).isoformat(),
        }
        self.capital += p["notional"] * pnl_pct / 100
        # 更新对应的 OPEN 建仓记录为最终结果(复盘证据: 建仓+平仓一条记录)
        for t in reversed(self.trades):
            if t.get("result") == "OPEN" and t.get("symbol") == self.symbol:
                t.update(trade)
                break
        else:
            self.trades.append(trade)
        self._persist_trades()  # 每笔平仓立即落盘
        if result == "SL":
            self.last_sl_bar = self._bar_seq
            # 止损冷却: 防止价格在止损位附近插针导致"平仓→立刻重开"死循环
            self._cooldown_until_ts = time.time() + self._sl_cooldown_secs
        self.position = None
        return trade

    def summary(self) -> dict:
        if not self.trades:
            return {"total": 0}
        wins = [t for t in self.trades if t["result"] == "TP"]
        losses = [t for t in self.trades if t["result"] == "SL"]
        total = len(self.trades)
        wr = len(wins) / total * 100
        avg_w = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
        avg_l = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
        return {"total": total, "tp": len(wins), "sl": len(losses),
                "win_rate": round(wr, 1),
                "avg_win": round(avg_w, 2), "avg_loss": round(avg_l, 2),
                "capital": round(self.capital, 2),
                "total_pnl_pct": round(sum(t["pnl_pct"] for t in self.trades), 2)}


class PaperStreamer:
    """WS 订阅 + 事件分发"""

    def __init__(self, engines: dict, config: dict):
        self.engines = engines  # symbol -> PaperEngine
        self.cfg = config
        self._kline_buf = defaultdict(list)  # (symbol, interval) -> partial bars

    async def run(self):
        symbols = list(self.engines.keys())
        streams = []
        for s in symbols:
            streams += [f"{s.lower()}@kline_15m",
                        f"{s.lower()}@kline_1h",
                        f"{s.lower()}@trade"]
        url = WS_URL + "/" + "/".join(streams)
        logger.info("连接 %s (streams: %d)", url, len(streams))
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    poll = asyncio.create_task(self._poll_prices())
                    try:
                        await self._listen(ws)
                    finally:
                        poll.cancel()
            except Exception as e:
                logger.error("WS 断开: %s, 3s 后重连", e)
                await asyncio.sleep(3)

    async def _poll_prices(self):
        """trade 流稀疏时兜底: 每 30s 拉一次现价检查触发(弥补秒级缺口)。"""
        import requests
        while True:
            await asyncio.sleep(30)
            for sym, eng in self.engines.items():
                try:
                    resp = requests.get("https://fapi.binance.com/fapi/v1/ticker/price",
                                        params={"symbol": sym}, timeout=8)
                    resp.raise_for_status()
                    price = float(resp.json()["price"])
                except Exception as e:
                    logger.warning("[%s] 兜底询价失败: %s", sym, e)
                    continue
                eng.cur_price = price
                trade = eng.on_tick(price)
                if trade:
                    self._report(eng, trade)

    async def _listen(self, ws):
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            data = msg.get("data", msg)
            stream = msg.get("stream", "")
            if "kline_15m" in stream or (data.get("k") and data["k"].get("i") == "15m"):
                self._on_kline(data, "15m")
            elif "kline_1h" in stream or (data.get("k") and data["k"].get("i") == "1h"):
                self._on_kline(data, "1h")
            elif "trade" in stream or data.get("e") == "trade":
                self._on_trade(data)

    def _on_kline(self, data, interval):
        k = data.get("k", {})
        sym = k.get("s", "").upper()
        eng = self.engines.get(sym)
        if eng is None:
            return
        if k.get("x"):  # 已收盘K线 → 追加
            close = float(k["c"])
            if interval == "15m":
                eng.closes_15m.append(close)
                eng.closes_15m = eng.closes_15m[-400:]
                trade = eng.on_bar(float(k["l"]), float(k["h"]), k["t"])
                self._report(eng, trade)
            else:
                eng.closes_1h.append(close)
                eng.closes_1h = eng.closes_1h[-200:]
        else:
            key = (sym, interval)
            self._kline_buf[key] = [float(k["c"]), float(k["l"]), float(k["h"]), k["t"]]

    def _on_trade(self, data):
        sym = data.get("s", "").upper()
        price = float(data.get("p", 0))
        eng = self.engines.get(sym)
        if eng is None or price <= 0:
            return
        eng._tick_count += 1
        now = time.time()
        if now - eng._last_heartbeat >= 60:
            eng._last_heartbeat = now
            logger.info("[%s] 行情心跳: %.6f USDT (累计 %d tick, 持仓=%s)",
                        sym, price, eng._tick_count,
                        eng.position["dir"] if eng.position else "无")
        trade = eng.on_tick(price)
        if trade:
            self._report(eng, trade)
        else:
            self._maybe_open(eng)

    def _maybe_open(self, eng: PaperEngine):
        sig = eng.check_signal()
        if sig is None:
            return
        direction, pos = sig
        # 标记本K线已触发, 防止同一固定下轨反复开仓
        eng._signal_fired_this_bar = True
        logger.info("[%s] 📈 新信号 %s @%.6f (sl=%.6f tp=%.6f) 名义 %.0f",
                    eng.symbol, direction, pos["entry"], pos["sl"], pos["tp"], pos["notional"])
        eng.position = pos
        eng._record_open()  # 建仓即落盘(OPEN), 作为复盘证据

    def _report(self, eng: PaperEngine, trade):
        if not trade:
            return
        print(f"[{eng.symbol}] {trade['closed_ts'][11:19]} "
              f"{trade['dir']:5s} {trade['result']:8s} "
              f"入{ trade['entry']:.4f} → 出{ trade['exit']:.4f} "
              f"PnL {trade['pnl_pct']:+.2f}% | 资金 {eng.capital:.2f} USDT")
        logger.info("[%s] 平仓 %s %s @%.4f PnL %+.2f%%", eng.symbol,
                    trade["dir"], trade["result"], trade["exit"], trade["pnl_pct"])


def main():
    parser = argparse.ArgumentParser(description="BB套利 - WS实时模拟盘(不碰真钱)")
    parser.add_argument("--symbol", default="NEARUSDT")
    parser.add_argument("--symbols", help="多币逗号分隔(实验)")
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    parser.add_argument("--log", default="paper_trades.json",
                        help="模拟交易记录文件 (默认 paper_trades.json)")
    parser.add_argument("--no-log", action="store_true", help="不落盘模拟交易")
    args = parser.parse_args()

    config = _load_config()
    syms = [s.strip().upper() for s in (args.symbols or args.symbol).split(",") if s.strip()]
    log_path = None if args.no_log else args.log
    engines = {s: PaperEngine(s, config, args.capital, log_path) for s in syms}

    # 先拉历史K线暖机
    import requests
    for s in syms:
        try:
            resp = requests.get("https://fapi.binance.com/fapi/v1/klines",
                                params={"symbol": s, "interval": "15m", "limit": 400},
                                timeout=15)
            resp.raise_for_status()
            engines[s].closes_15m = [float(k[4]) for k in resp.json()]
            resp = requests.get("https://fapi.binance.com/fapi/v1/klines",
                                params={"symbol": s, "interval": "1h", "limit": 200},
                                timeout=15)
            resp.raise_for_status()
            engines[s].closes_1h = [float(k[4]) for k in resp.json()]
            logger.info("%s: 历史K线暖机完成 (15m:%d, 1h:%d)",
                        s, len(engines[s].closes_15m), len(engines[s].closes_1h))
        except Exception as e:
            logger.error("%s 历史K线获取失败: %s", s, e)

    print(f"🟡 WS 实时模拟盘启动 | 币种: {syms} | 虚拟资金: ${args.capital:.0f}")
    print(f"   交易记录: {log_path if log_path else '不落盘'}")
    print("   只读行情流, 无真实下单. Ctrl+C 退出并打印汇总.\n")

    streamer = PaperStreamer(engines, config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def on_exit(signum, frame):
        print("\n\n📊 模拟盘汇总:")
        for s, eng in engines.items():
            sm = eng.summary()
            if sm.get("total", 0) == 0:
                print(f"  {s}: 无交易")
            else:
                print(f"  {s}: {sm['total']}笔 | TP {sm['tp']} SL {sm['sl']} "
                      f"| 胜率 {sm['win_rate']}% | 累计 {sm['total_pnl_pct']:+.2f}% "
                      f"| 资金 ${sm['capital']:.2f}")
        logger.info("模拟盘退出")
        loop.stop()
        os._exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: on_exit(s, None))
        except NotImplementedError:
            signal.signal(sig, on_exit)

    try:
        loop.run_until_complete(streamer.run())
    except KeyboardInterrupt:
        on_exit(None, None)


if __name__ == "__main__":
    main()
