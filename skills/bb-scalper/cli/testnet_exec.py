#!/usr/bin/env python3
"""cli/testnet_exec.py — 币安 Testnet 下单执行器

把策略信号转成对币安 testnet 的真实下单(虚拟资金、真实撮合)。
封装 cli.trade_exec.LiveTrader, 复用其精度修正/余额校验/持仓防重/错误归一化:

  set_leverage → 余额校验(margin=notional/leverage) → 持仓防重(同仓拒绝)
  → MARKET 入场(reduceOnly=False) → STOP_MARKET/TAKE_PROFIT_MARKET reduceOnly 条件单
  → 条件单挂失败立即市价平掉入场(不留裸仓)

安全:
  - 平仓/减仓一律 reduceOnly, 绝不开反向裸仓
  - 条件单优先 Algo API, 失败降级普通单
  - 撤单优先 clientOrderId, 兜底 orderId
"""
import os
import sys
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cli.trade_exec import LiveTrader, TradeError  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger("testnet_exec")


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


class TestnetExecutor:
    """把策略信号转成对币安 testnet 的真实下单。"""

    def __init__(self, trader: LiveTrader):
        self.trader = trader

    def open_position(self, symbol: str, direction: str, entry: float,
                      sl: float, tp: float, notional: float, leverage: int) -> dict:
        """对 testnet 真实开仓并挂止损/止盈。返回成交详情 dict。"""
        long = direction == "LONG"
        side = "BUY" if long else "SELL"
        close_side = "SELL" if long else "BUY"
        ts = int(time.time() * 1000)

        logger.info("设置杠杆 %s %dx", symbol, leverage)
        # 逐仓模式: 每笔仓位独立保证金, 亏损锁死在该仓, 符合策略"小仓扛连亏"风控
        try:
            self.trader.set_margin_type(symbol, "ISOLATED")
        except Exception as e:
            logger.warning("[%s] 设逐仓模式失败(可能已是逐仓): %s", symbol, str(e)[:80])
        self.trader._call("set_leverage", symbol, leverage)

        bal = self.trader._call("get_balance", asset="USDT") or {}
        available = _f(bal.get("availableBalance", bal.get("available")))
        margin_needed = notional / leverage
        if available < margin_needed:
            raise TradeError("可用余额 %.2f < 所需保证金 %.2f, 拒绝开仓"
                             % (available, margin_needed))

        pos = self.trader.current_position(symbol)
        if pos is not None:
            raise TradeError("已存在持仓 %s amt=%s, 拒绝重复开仓"
                             % (symbol, pos.get("positionAmt")))

        qty = self.trader._round(symbol, notional / entry, "qty")
        entry_res = self.trader.place_order(symbol, side, "MARKET", qty,
                                            client_order_id="bse-%s-%d" % (symbol, ts))
        if entry_res.status != "FILLED":
            raise TradeError("testnet 入场未成交 status=%s" % entry_res.status)
        fill = _f(entry_res.price) or entry

        sl_r = self.trader._round(symbol, sl, "price")
        tp_r = self.trader._round(symbol, tp, "price")
        try:
            sl_res, sl_cid = self._place_conditional(
                symbol, close_side, "STOP_MARKET", qty, sl_r, ts)
            tp_res, tp_cid = self._place_conditional(
                symbol, close_side, "TAKE_PROFIT_MARKET", qty, tp_r, ts)
        except Exception as e:
            # 止损/止盈没挂上 → 立即市价平掉入场, 避免无保护裸仓
            logger.error("[%s] 条件单挂单失败, 立即市价平掉入场以防裸仓: %s", symbol, e)
            close_ok = False
            try:
                self.trader.place_order(symbol, close_side, "MARKET", qty,
                                        reduce_only=True,
                                        client_order_id="bcl-%s-%d" % (symbol, ts))
                close_ok = True
            except Exception as ce:
                # 平仓兜底也失败 → 记录裸仓预警, 让 poll 层能检测并接管
                logger.error("[%s] 平仓兜底失败, 存在无SL/TP裸仓风险! 请立即手动平仓. 错误: %s",
                             symbol, ce)
            raise TradeError(
                "%s 条件单挂单失败且%s平仓: %s"
                % (symbol, "已市价平掉" if close_ok else "平仓失败(裸仓预警!)", e))
        logger.info("[%s] testnet 条件单已挂 sl=%.6f tp=%.6f qty=%s", symbol, sl_r, tp_r, qty)
        return {"entry": fill, "qty": qty, "sl": sl_r, "tp": tp_r,
                "sl_client_id": sl_cid, "tp_client_id": tp_cid}

    def _place_conditional(self, symbol: str, side: str, order_type: str,
                           qty: float, stop_price: float, ts: int):
        """优先 Algo API 条件单, 失败降级普通 STOP/TAKE_PROFIT 单。"""
        cid = ("bssl-%s-%d" % (symbol, ts) if order_type == "STOP_MARKET"
               else "bstp-%s-%d" % (symbol, ts))
        try:
            res = self.trader.place_conditional_order(
                symbol, side, order_type, qty, stop_price=stop_price,
                reduce_only=True, client_order_id=cid)
        except TradeError:
            logger.warning("[%s] algo 条件单失败, 降级普通 %s", symbol, order_type)
            res = self.trader.place_order(symbol, side, order_type, qty,
                                          stop_price=stop_price, reduce_only=True,
                                          client_order_id=cid)
        return res, cid

    def get_real_position_amt(self, symbol: str) -> float:
        """查询真实持仓数量; 无持仓返回 0。"""
        pos = self.trader.current_position(symbol)
        if pos is None:
            return 0.0
        return _f(pos.get("positionAmt"))

    def get_real_close_price(self, symbol: str, pos: dict) -> Optional[float]:
        """取最近一笔平仓成交价(真实 avgPrice), 供 poll 记账用; 取不到返回 None。"""
        try:
            trades = self.trader._call("get_user_trades", symbol, limit=5)
        except Exception as e:
            logger.warning("[%s] 成交记录查询失败, 用轮询现价记账: %s", symbol, e)
            return None
        # 取最近一笔 reduceOnly 平仓方向的成交价
        close_side = "SELL" if pos.get("dir") == "LONG" else "BUY"
        for t in trades or []:
            if t.get("side") == close_side and t.get("qty"):
                return _f(t.get("price"))
        return None

    def get_usdt_balance(self) -> float:
        bal = self.trader._call("get_balance", asset="USDT") or {}
        return _f(bal.get("balance") or bal.get("availableBalance"))

    def list_open_order_client_ids(self, symbol: str):
        orders = self.trader._call("get_open_orders", symbol) or []
        return {str(o.get("clientOrderId") or "") for o in orders}

    def cancel_symbol_orders(self, symbol: str):
        """撤掉该 symbol 全部挂单(含条件单触发后残留的 reduceOnly 单)。"""
        orders = self.trader._call("get_open_orders", symbol) or []
        for o in orders:
            cid = o.get("clientOrderId")
            try:
                if cid:
                    self.trader._call("cancel_order", symbol, orig_client_order_id=cid)
                elif o.get("orderId"):
                    self.trader._call("cancel_order", symbol, order_id=int(o["orderId"]))
            except Exception as e:
                logger.warning("[%s] 撤单失败 %s: %s", symbol, cid or o.get("orderId"), e)

    def close_position_market(self, symbol: str, direction: str, qty: float):
        """市价 reduceOnly 平仓(先撤条件单)。"""
        side = "SELL" if direction == "LONG" else "BUY"
        try:
            self.cancel_symbol_orders(symbol)
        except Exception:
            pass
        ts = int(time.time() * 1000)
        res = self.trader.place_order(symbol, side, "MARKET", qty, reduce_only=True,
                                      client_order_id="bcx-%s-%d" % (symbol, ts))
        if res.status != "FILLED":
            raise TradeError("testnet 平仓未成交 status=%s" % res.status)
        return res
