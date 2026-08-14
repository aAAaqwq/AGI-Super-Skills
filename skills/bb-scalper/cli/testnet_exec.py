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
from datetime import datetime, timezone
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


def _parse_ts_ms(v) -> Optional[int]:
    """把 opened_ts(ISO 字符串或毫秒时间戳)转成毫秒; 取不到返回 None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return None


class TestnetExecutor:
    """把策略信号转成对币安 testnet 的真实下单。"""

    def __init__(self, trader: LiveTrader):
        self.trader = trader

    def _wait_filled(self, symbol: str, order_res, timeout: float = 5.0,
                     interval: float = 0.5) -> dict:
        """market 单发出后轮询等 FILLED(处理 testnet 撮合延迟)。

        Args:
            symbol: 交易对
            order_res: 下单响应(OrderResult 或 dict, 含 status/orderId/clientOrderId)
            timeout: 最长等待秒数
            interval: 轮询间隔秒数

        Returns:
            最终订单状态 dict(含 status/orderId)
        """
        if hasattr(order_res, "status"):  # OrderResult dataclass
            status = order_res.status
            order_id = order_res.order_id or None
            cid = order_res.client_order_id or None
        else:
            status = order_res.get("status")
            order_id = order_res.get("order_id") or order_res.get("orderId")
            cid = order_res.get("client_order_id") or order_res.get("clientOrderId")
        if status == "FILLED":
            price = getattr(order_res, "price", None)
            if price is None and isinstance(order_res, dict):
                price = order_res.get("price") or order_res.get("avgPrice")
            return {"status": status, "orderId": order_id, "price": price,
                    "avgPrice": price}
        import time as _t
        deadline = _t.time() + timeout
        while _t.time() < deadline:
            try:
                o = (self.trader.get_order(symbol, order_id=int(order_id))
                     if order_id else self.trader.get_order(symbol, orig_client_order_id=str(cid)))
                if o.get("status") == "FILLED":
                    o["orderId"] = o.get("orderId") or order_id
                    return o
                if o.get("status") in ("CANCELED", "EXPIRED", "REJECTED"):
                    break
            except Exception as e:
                logger.warning("[%s] 查单失败(重试): %s", symbol, str(e)[:60])
            _t.sleep(interval)
        return {"status": status or "NEW", "orderId": order_id}  # 超时返回, 由调用方处理

    def open_position(self, symbol: str, direction: str, entry: float,
                      sl: float, tp: float, notional: float, leverage: int,
                      place_only: bool = False) -> dict:
        """对 testnet 真实开仓并挂止损/止盈。返回成交详情 dict。

        place_only=True 时只开仓(下MARKET单)不挂条件单, 供调用方立即置位
        position后再挂SL/TP, 缩小poll误判残留的竞态窗口。
        """
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
        # 轮询等 FILLED(处理 testnet 撮合延迟), 未成交再判失败
        entry_res = self._wait_filled(symbol, entry_res)
        if entry_res.get("status") != "FILLED":
            raise TradeError("testnet 入场未成交 status=%s" % entry_res.get("status"))
        # 入场价: 优先用交易所真实 avgPrice(等单后 get_order 会聚合), 兜底用订单价
        exch_avg = _f(entry_res.get("avgPrice") or entry_res.get("price"))
        fill = exch_avg or entry
        # 立即成交时交易所 avgPrice 常为 0: 用 userTrades 按量加权取真实入场价
        # (只取本单 ts 之后的成交, 避免误吞上一仓的同方向成交)
        if not exch_avg:
            try:
                t = self.trader._call("get_user_trades", symbol, limit=5)
                qty_fill, wsum = 0.0, 0.0
                for x in t or []:
                    if x.get("side") != side:
                        continue
                    if _f(x.get("time") or 0) < ts:
                        continue
                    qty_fill += _f(x.get("qty"))
                    wsum += _f(x.get("qty")) * _f(x.get("price"))
                if qty_fill > 0:
                    fill = wsum / qty_fill
            except Exception as e:
                logger.warning("[%s] 入场价按量加权修正失败(用订单价记账): %s", symbol, e)

        # 只开仓模式: 立即返回, 由调用方置位position后再挂条件单
        if place_only:
            return {"entry": fill, "qty": qty, "sl": sl, "tp": tp,
                    "sl_client_id": None, "tp_client_id": None}

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

    def place_conditional_after_open(self, symbol: str, direction: str,
                                     qty: float, sl: float, tp: float) -> dict:
        """开仓后(已置位position)挂止损/止盈。返回 sl/tp client_id。"""
        long = direction == "LONG"
        close_side = "SELL" if long else "BUY"
        ts = int(time.time() * 1000)
        sl_r = self.trader._round(symbol, sl, "price")
        tp_r = self.trader._round(symbol, tp, "price")
        try:
            sl_res, sl_cid = self._place_conditional(
                symbol, close_side, "STOP_MARKET", qty, sl_r, ts)
            tp_res, tp_cid = self._place_conditional(
                symbol, close_side, "TAKE_PROFIT_MARKET", qty, tp_r, ts)
        except Exception as e:
            logger.error("[%s] 挂条件单失败, 持仓无保护, 将由poll接管平掉: %s", symbol, e)
            return {"sl_client_id": None, "tp_client_id": None}
        return {"sl_client_id": sl_cid, "tp_client_id": tp_cid}

    def get_real_position_amt(self, symbol: str) -> float:
        """查询真实持仓数量; 无持仓返回 0。"""
        pos = self.trader.current_position(symbol)
        if pos is None:
            return 0.0
        return _f(pos.get("positionAmt"))

    def get_fill_price(self, symbol: str, pos: dict,
                       after_ts_ms: Optional[int] = None,
                       before_ts_ms: Optional[int] = None,
                       side: Optional[str] = None,
                       qty_floor: float = 0.0,
                       max_fills: int = 5) -> Optional[float]:
        """取真实成交加权均价(数量加权)。默认取最近一笔、平仓方向(side)的成交。

        Args:
            symbol: 交易对
            pos: 持仓 dict(需含 dir; 有 opened_ts 时自动作为时间下界)
            after_ts_ms: 只取该毫秒时间戳之后的成交; None 用 pos.opened_ts 推导
            before_ts_ms: 只取该毫秒时间戳之前的成交(离线复盘用); None 不限
            side: 过滤成交方向; None 用 pos.dir 推导平仓方向
            qty_floor: >0 时从最近的成交往前累加, 累计量达到该值即停(≈按持仓量
                圈定平仓成交, 避免吞掉后续仓位的同方向成交); <=0 时只取最近 N 笔
            max_fills: 最多取多少笔做加权
        """
        if side is None:
            side = "SELL" if pos.get("dir") == "LONG" else "BUY"
        if after_ts_ms is None:
            after_ts_ms = _parse_ts_ms(pos.get("opened_ts"))
        try:
            trades = self.trader._call("get_user_trades", symbol,
                                       limit=max(50, max_fills))
        except Exception as e:
            logger.warning("[%s] 成交记录查询失败: %s", symbol, e)
            return None
        # qty_floor>0: 按时间正序取 after_ts_ms 之后的第一批 close_side 成交, 累计到
        # 持仓量即停 —— 该批就是本仓的平仓成交(仓位严格串行, 本仓平仓成交永远
        # 早于下一仓的成交), 避免误吞后续仓位的同方向成交。
        order = sorted(trades or [], key=lambda d: d.get("time") or 0,
                       reverse=(qty_floor <= 0))
        picks = []
        acc = 0.0
        for t in order:
            if t.get("side") != side:
                continue
            ttime = t.get("time") or t.get("timestamp") or 0
            if after_ts_ms is not None and _f(ttime) < after_ts_ms:
                continue
            if before_ts_ms is not None and _f(ttime) > before_ts_ms:
                continue
            qty = _f(t.get("qty"))
            if qty <= 0:
                continue
            picks.append((qty, _f(t.get("price"))))
            acc += qty
            if qty_floor > 0 and acc >= qty_floor:
                break
            if len(picks) >= max_fills:
                break
        if not picks:
            return None
        tot = sum(q for q, _ in picks)
        if tot <= 0:
            return None
        return sum(q * p for q, p in picks) / tot

    def get_real_close_price(self, symbol: str, pos: dict) -> Optional[float]:
        """取真实平仓成交价(数量加权均价)。用 pos.opened_ts 之后、平仓方向的
        真实成交(userTrades 的 price), 并按持仓量 qty 圈定最近那笔平仓成交,
        避免误吞后续仓位的同方向成交。取不到返回 None。
        """
        return self.get_fill_price(symbol, pos, qty_floor=_f(pos.get("qty")))

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
        """市价 reduceOnly 平仓(先撤条件单)。返回原始响应 dict(尽量含真实均价)。"""
        side = "SELL" if direction == "LONG" else "BUY"
        try:
            self.cancel_symbol_orders(symbol)
        except Exception:
            pass
        ts = int(time.time() * 1000)
        res = self.trader.place_order(symbol, side, "MARKET", qty, reduce_only=True,
                                      client_order_id="bcx-%s-%d" % (symbol, ts))
        # 轮询等 FILLED(处理 testnet 撮合延迟)
        res_f = self._wait_filled(symbol, res)
        if res_f.get("status") != "FILLED":
            raise TradeError("testnet 平仓未成交 status=%s" % res_f.get("status"))
        # 尽量返回真实成交均价(部分成交时交易所 avgPrice 可能未聚合)
        avg = _f(res_f.get("avgPrice") or res_f.get("price")) or _f(
            getattr(res, "price", None))
        if avg > 0:
            try:
                import dataclasses
                if dataclasses.is_dataclass(res):
                    res = dataclasses.replace(res, price=avg)
                else:
                    res = dict(res)
                    res["avgPrice"] = avg
                    res["price"] = avg
            except Exception:
                pass
        return res
