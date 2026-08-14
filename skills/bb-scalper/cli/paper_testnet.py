#!/usr/bin/env python3
"""cli/paper_testnet.py — 币安 Testnet 模拟盘(真实行情 + testnet 真实撮合)

在 paper.py 的 WS 实时模拟盘基础上, 把「本地模拟成交」换成「币安测试网真实下单」:
策略信号(三重过滤/实时价 %B/止损冷却/深跌保护)复用 cli/paper.PaperEngine.check_signal,
成交、持仓、平仓全部走 testnet 的 BinanceClient(虚拟资金、真实撮合)。全程不碰主网、不碰真钱。

用法:
  export BINANCE_TESTNET_API_KEY=...        # 从 testnet.binancefuture.com 申请
  export BINANCE_TESTNET_API_SECRET=...
  python cli/paper_testnet.py --symbol NEARUSDT
  python cli/paper_testnet.py --symbols NEARUSDT,DOTUSDT --poll-interval 3

下单流程(信号触发后, 由 TestnetExecutor 对 testnet 真实下单):
  1. set_leverage(symbol, leverage)             # 默认 10x(来自 config.trade.leverage)
  2. 余额校验(margin = notional/leverage) + 持仓防重(同仓拒绝)
  3. MARKET 入场(reduceOnly=False), 取 avgPrice 作为真实成交价
  4. STOP_MARKET(止损) / TAKE_PROFIT_MARKET(止盈) reduceOnly 条件单(优先 Algo API,
     失败降级普通单; 仍失败则立即市价平掉入场, 不留裸仓)
  5. 轮询 get_position_risk, positionAmt 归零 = 已平仓 → 记录真实成交

安全:
  - 默认只连 https://testnet.binancefuture.com; 检测到主网 fapi.binance.com 会拒绝,
    除非显式传 --allow-mainnet
  - testnet 同样有持仓防重/余额校验/精度修正; 无 key 时给出申请指引, 不崩溃
"""
import argparse
import asyncio
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import websockets  # noqa: E402

from cli.paper import PaperEngine, PaperStreamer, MAX_POS, _load_config  # noqa: E402
from cli.testnet_exec import TestnetExecutor, _f  # noqa: E402
from cli.trade_exec import LiveTrader  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger("paper_testnet")

DEFAULT_TESTNET_BASE = "https://testnet.binancefuture.com"
DEFAULT_TESTNET_WS = "wss://fstream.binancefuture.com/ws"


class TestnetEngine(PaperEngine):
    """testnet 引擎: 复用 PaperEngine 的信号生成, 成交/持仓走真实 testnet。

    - on_tick 只更新现价(不做本地模拟止盈止损, 由交易所条件单处理)
    - poll() 轮询 get_position_risk, positionAmt 归零 = 已平仓 → 复用 close() 记账
    - on_bar 超时(MAX_POS 根 15m)时市价平仓
    """

    def __init__(self, symbol: str, config: dict, executor: TestnetExecutor,
                 log_path: Optional[str] = None):
        super().__init__(symbol, config, capital=0.0, log_path=log_path)
        self.executor = executor
        self._sl_client_id = ""
        self._tp_client_id = ""
        self._real_position_amt = 0.0
        self._last_price_ts = 0.0
        self._open_fail_until_ts = 0.0
        # 开仓保护期: 下MARKET单到置位position的间隙, poll不接管(防误伤自己刚开的仓)
        self._opening_until_ts = 0.0

    # ── 覆盖价格触发: 不在本地模拟成交 ──
    def on_tick(self, price: float):
        self.cur_price = price
        self._last_price_ts = time.time()
        return None

    def on_bar(self, low, high, ts):
        self._bar_seq += 1
        if not self.position:
            return None
        if self._bar_seq - self.position["opened_bar"] >= MAX_POS:
            return self._timeout_close()
        return None

    def _timeout_close(self):
        p = self.position
        try:
            res = self.executor.close_position_market(self.symbol, p["dir"], p.get("qty", 0))
            # 优先取本次市价单的真实成交价(加权均价); 取不到回退现价
            exit_price = _f(res.get("avgPrice") or res.get("price")) or \
                self.executor.get_real_close_price(self.symbol, p) or \
                self.cur_price or p["entry"]
            return self.close("TIMEOUT", exit_price)
        except Exception as e:
            logger.error("[%s] 超时平仓失败(稍后由轮询兜底): %s", self.symbol, e)
            return None

    # ── 轮询: 交易所真实持仓 ──
    def poll(self):
        """轮询 testnet 真实持仓: 管理引擎已知仓位, 并发现/接管残留裸仓。"""
        try:
            amt = self.executor.get_real_position_amt(self.symbol)
        except Exception as e:
            logger.warning("[%s] 持仓轮询失败: %s", self.symbol, e)
            return None
        # 发现 testnet 有仓位但引擎不认识(残留/接管) → 置位 position 管理它
        # 开仓保护期内不接管: 避免把自己刚下的单误判为残留仓立即平掉
        if not self.position and abs(amt) > 1e-12:
            if time.time() < self._opening_until_ts:
                return None
            # 有最近开仓的 client_id 说明是引擎自己开的(可能条件单还没挂完), 不接管
            if self._sl_client_id or self._tp_client_id:
                return None
            logger.warning("[%s] 发现残留仓位 amt=%s, 接管管理(无保护, 将尽快平掉)",
                           self.symbol, amt)
            self.position = {
                "dir": "LONG" if amt > 0 else "SHORT",
                "entry": self.cur_price or 0.0,
                "sl": None, "tp": None,
                "opened_bar": self._bar_seq,
                "opened_ts": datetime.now(timezone.utc).isoformat(),
                "notional": abs(amt) * (self.cur_price or 0),
                "leverage": 1,
                "qty": abs(amt),
                "_bare": True,
            }
            self._sl_client_id = None
            self._tp_client_id = None
            # 残留仓无保护 → 立即市价平掉
            return self._timeout_close()
        if not self.position:
            return None
        # 无保护仓(bare=True, 条件单没挂上) → 不能裸持, 立即市价平掉
        if self.position.get("_bare") and abs(amt) > 1e-12:
            logger.warning("[%s] 无保护仓 bare=True, 立即市价平掉", self.symbol)
            return self._timeout_close()
        if abs(amt) < 1e-12:
            p = self.position
            # 先判断平仓类型(SL/TP), 再用对应触发价作为平仓价(条件单触发价≈真实成交)
            # 比回退现价更准(现价在跳空时偏离成交价很大)
            result = self._classify_close(self.cur_price or p["entry"])
            if result == "SL":
                exit_price = p.get("sl") or self.cur_price or p["entry"]
            elif result == "TP":
                exit_price = p.get("tp") or self.cur_price or p["entry"]
            else:
                # EXIT(超时/其他): 用真实平仓成交价(weighted avg), 不再回退现价
                exit_price = self.executor.get_real_close_price(self.symbol, p) or \
                    self.cur_price or p["entry"]
            try:
                self.executor.cancel_symbol_orders(self.symbol)
            except Exception:
                pass
            return self.close(result, exit_price)
        self._real_position_amt = amt
        return None

    def _classify_close(self, exit_price: float) -> str:
        """判断平仓结果: 优先看哪个条件单被触发, 兜底按价格归类。"""
        p = self.position
        try:
            ids = self.executor.list_open_order_client_ids(self.symbol)
            if self._sl_client_id and self._tp_client_id and ids is not None:
                sl_still = self._sl_client_id in ids
                tp_still = self._tp_client_id in ids
                if not sl_still and tp_still:
                    return "SL"
                if sl_still and not tp_still:
                    return "TP"
        except Exception:
            pass
        if p["dir"] == "LONG":
            if exit_price <= p["sl"]:
                return "SL"
            if exit_price >= p["tp"]:
                return "TP"
        else:
            if exit_price >= p["sl"]:
                return "SL"
            if exit_price <= p["tp"]:
                return "TP"
        return "EXIT"


class TestnetStreamer(PaperStreamer):
    """testnet WS 订阅 + 事件分发: 复用 paper 的订阅, 换 testnet 地址 + 真实下单。"""

    def __init__(self, engines: dict, config: dict,
                 ws_url: str = DEFAULT_TESTNET_WS,
                 rest_base: str = DEFAULT_TESTNET_BASE,
                 poll_interval: float = 3.0):
        super().__init__(engines, config)
        self.ws_url = ws_url
        self.rest_base = rest_base
        self._poll_interval = poll_interval

    async def run(self):
        symbols = list(self.engines.keys())
        streams = []
        for s in symbols:
            streams += [f"{s.lower()}@kline_15m",
                        f"{s.lower()}@kline_1h",
                        f"{s.lower()}@trade"]
        url = self.ws_url + "/" + "/".join(streams)
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
        """周期轮询: 价格兜底(WS 稀疏时) + 交易所持仓检查。"""
        import requests
        while True:
            await asyncio.sleep(self._poll_interval)
            for sym, eng in self.engines.items():
                if eng.cur_price is None or time.time() - eng._last_price_ts > 30:
                    try:
                        resp = requests.get(self.rest_base + "/fapi/v1/ticker/price",
                                            params={"symbol": sym}, timeout=8)
                        resp.raise_for_status()
                        eng.on_tick(float(resp.json()["price"]))
                    except Exception as e:
                        logger.warning("[%s] 兜底询价失败: %s", sym, e)
                try:
                    ev = eng.poll()
                except Exception as e:
                    logger.warning("[%s] 持仓轮询失败: %s", sym, e)
                    continue
                if ev:
                    self._report(eng, ev)

    def _maybe_open(self, eng: TestnetEngine):
        """信号触发 → 对 testnet 真实下单。失败 30s 冷却防 API 轰炸。"""
        if getattr(eng, "_open_fail_until_ts", 0) > time.time():
            return
        sig = eng.check_signal()
        if sig is None:
            return
        direction, pos = sig
        # 按币波动率覆盖杠杆: config.trade.leverage_by_symbol 优先, 否则用默认
        lev_map = (self.cfg.get("trade", {}) or {}).get("leverage_by_symbol", {}) or {}
        pos["leverage"] = lev_map.get(eng.symbol, pos.get("leverage", 10))
        # 开仓保护期: 下MARKET单到置位position的间隙, poll不得接管(防误伤)
        eng._opening_until_ts = time.time() + 3.0
        try:
            # 两步开仓: 先下MARKET单(place_only), 立即置位position, 再挂SL/TP
            res = eng.executor.open_position(
                eng.symbol, direction, pos["entry"], pos["sl"], pos["tp"],
                pos["notional"], pos["leverage"], place_only=True)
        except Exception as e:
            logger.error("[%s] testnet 开仓失败(30s内不再尝试): %s", eng.symbol, e)
            # 裸仓预警: 入场单可能已成交但无SL/TP且兜底平仓失败 → 置位position让poll接管平仓
            if "裸仓预警" in str(e) or "平仓失败" in str(e):
                pos["entry"] = pos.get("entry", 0)
                pos["qty"] = pos.get("qty", 0)
                pos["_bare"] = True  # 标记无保护仓, poll 平掉后记录
                eng.position = pos
                eng._sl_client_id = None
                eng._tp_client_id = None
                logger.error("[%s] ⚠️ 已标记待接管裸仓, poll 将尽快市价平掉", eng.symbol)
            eng._open_fail_until_ts = time.time() + 30
            return
        # 立即置位 position(在挂条件单前), 缩小 poll 误判残留的竞态窗口
        pos["entry"] = res["entry"]
        pos["qty"] = res["qty"]
        pos["_bare"] = True  # 条件单挂上前标记无保护, 避免 poll 当成正常持仓
        eng.position = pos
        # 再挂止损/止盈
        cond = eng.executor.place_conditional_after_open(
            eng.symbol, direction, res["qty"], res["sl"], res["tp"])
        eng._sl_client_id = cond["sl_client_id"]
        eng._tp_client_id = cond["tp_client_id"]
        if not eng._sl_client_id:
            pos["_bare"] = True  # 条件单没挂上, 保持无保护标记, poll 接管
            logger.error("[%s] ⚠️ 止损单未挂上, 标记无保护, poll 将接管", eng.symbol)
        else:
            pos["_bare"] = False
        logger.info("[%s] ✅ testnet 开仓 %s @%.6f qty=%s sl=%.6f tp=%.6f bare=%s",
                    eng.symbol, direction, res["entry"], res["qty"],
                    res["sl"], res["tp"], pos["_bare"])

    def _report(self, eng: TestnetEngine, trade: dict):
        if not trade:
            return
        try:
            bal = eng.executor.get_usdt_balance()
            bal_str = "%.2f USDT" % bal
        except Exception:
            bal_str = "?"
        print(f"[{eng.symbol}] {trade['closed_ts'][11:19]} {trade['dir']:5s} "
              f"{trade['result']:8s} 入{trade['entry']:.4f} → 出{trade['exit']:.4f} "
              f"PnL {trade['pnl_pct']:+.2f}% | USDT {bal_str}")
        logger.info("[%s] testnet 平仓 %s %s @%.4f PnL %+.2f%%", eng.symbol,
                    trade["dir"], trade["result"], trade["exit"], trade["pnl_pct"])


def _warmup(eng: TestnetEngine, rest_base: str):
    """拉 testnet 历史 K 线暖机(15m + 1h)。"""
    import requests
    try:
        resp = requests.get(rest_base + "/fapi/v1/klines",
                            params={"symbol": eng.symbol, "interval": "15m", "limit": 400},
                            timeout=15)
        resp.raise_for_status()
        eng.closes_15m = [float(k[4]) for k in resp.json()]
    except Exception as e:
        logger.error("[%s] 15m 历史K线失败: %s", eng.symbol, e)
    try:
        resp = requests.get(rest_base + "/fapi/v1/klines",
                            params={"symbol": eng.symbol, "interval": "1h", "limit": 200},
                            timeout=15)
        resp.raise_for_status()
        eng.closes_1h = [float(k[4]) for k in resp.json()]
    except Exception as e:
        logger.error("[%s] 1h 历史K线失败: %s", eng.symbol, e)
    logger.info("[%s] testnet 历史K线暖机 (15m:%d, 1h:%d)",
                eng.symbol, len(eng.closes_15m), len(eng.closes_1h))


def main():
    p = argparse.ArgumentParser(
        description="BB套利 - 币安 Testnet 模拟盘(真实行情 + testnet 真实撮合, 虚拟资金)")
    p.add_argument("--symbol", default="NEARUSDT")
    p.add_argument("--symbols", help="多币逗号分隔(实验)")
    p.add_argument("--log", default="testnet_trades.json", help="成交记录文件(默认 testnet_trades.json)")
    p.add_argument("--no-log", action="store_true", help="不落盘成交")
    p.add_argument("--poll-interval", type=float, default=3.0, help="持仓/价格轮询秒数")
    p.add_argument("--base-url", default=None, help="覆盖 API 基础地址(默认 testnet.binancefuture.com)")
    p.add_argument("--ws-url", default=None, help="覆盖行情 WS 地址")
    p.add_argument("--rest-url", default=None, help="覆盖行情 REST 基础地址")
    p.add_argument("--allow-mainnet", action="store_true",
                   help="显式允许连接主网 fapi.binance.com(默认拒绝)")
    args = p.parse_args()

    config = _load_config()
    bc = config.get("binance", {}) or {}
    base_url = (args.base_url or bc.get("testnet_base_url") or DEFAULT_TESTNET_BASE).rstrip("/")
    ws_url = args.ws_url or bc.get("testnet_ws_url") or DEFAULT_TESTNET_WS
    rest_url = (args.rest_url or bc.get("testnet_rest_url") or base_url).rstrip("/")

    # 安全: 默认只连 testnet, 主网需显式确认
    if "fapi.binance.com" in base_url and "testnet" not in base_url and not args.allow_mainnet:
        print(f"❌ 检测到主网 API 地址 {base_url}。testnet 模式默认只连 testnet.binancefuture.com。")
        print("   如确需主网请显式传 --allow-mainnet。")
        sys.exit(1)

    api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print("❌ 缺少 testnet 密钥。")
        print("   请到 https://testnet.binancefuture.com 申请(虚拟资金, 无需真钱), 然后设置:")
        print("   export BINANCE_TESTNET_API_KEY=<your-key>")
        print("   export BINANCE_TESTNET_API_SECRET=<your-secret>")
        sys.exit(1)

    syms = [s.strip().upper() for s in (args.symbols or args.symbol).split(",") if s.strip()]
    try:
        trader = LiveTrader(api_key, api_secret, base_url=base_url)
    except Exception as e:
        logger.error("创建 testnet 客户端失败: %s", e)
        print(f"❌ {e}")
        sys.exit(1)
    executor = TestnetExecutor(trader)

    log_path = None if args.no_log else args.log
    engines = {}
    for s in syms:
        eng = TestnetEngine(s, config, executor, log_path=log_path)
        _warmup(eng, rest_url)
        if len(eng.closes_15m) < 20:
            logger.warning("[%s] testnet 历史K线不足 20 根(%d), 需等 WS 累积后再出信号",
                           s, len(eng.closes_15m))
        engines[s] = eng

    print(f"🟢 币安 Testnet 模拟盘启动 | 币种: {syms} | API: {base_url}")
    print(f"   成交记录: {log_path if log_path else '不落盘'} | 轮询: {args.poll_interval}s")
    print("   真实行情 + testnet 真实撮合(虚拟资金). Ctrl+C 退出并打印汇总.\n")

    streamer = TestnetStreamer(engines, config, ws_url=ws_url, rest_base=rest_url,
                               poll_interval=args.poll_interval)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def on_exit(signum, frame):
        print("\n\n📊 testnet 模拟盘汇总:")
        for s, eng in engines.items():
            sm = eng.summary()
            if sm.get("total", 0) == 0:
                print(f"  {s}: 无交易")
            else:
                print(f"  {s}: {sm['total']}笔 | TP {sm['tp']} SL {sm['sl']} "
                      f"| 胜率 {sm['win_rate']}% | 累计 {sm['total_pnl_pct']:+.2f}%")
        try:
            bal = executor.get_usdt_balance()
            print(f"  真实 testnet USDT 余额: {bal:.2f}")
        except Exception:
            pass
        logger.info("testnet 模拟盘退出")
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
