#!/usr/bin/env python3
"""cli/trade_exec.py - 币安 USDT 永续合约实盘/演练交易 CLI

用法: python cli/trade_exec.py --symbol NEARUSDT --side LONG --entry 1.592 \
  --tp 1.610 --sl 1.589 --qty 100 [--test | --live [--force]] [--no-log]
--test=test接口演练(不真实成交); --live=真实下单(需密钥+输入yes确认);
默认模式仅打印订单信息, 不发任何请求。安全机制: 密钥闸/交互确认(含杠杆后
PnL)/参数校验/持仓防重/余额校验/精度修正/LIMIT入场FILLED后才下reduceOnly
止盈止损/幂等clientOrderId。契约差异适配见代码。
"""
import argparse, inspect, json, os, sys, time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cli.trade_log import log_trade  # noqa: E402
from core.logger import get_logger   # noqa: E402

DEFAULT_CONFIG = os.path.join(ROOT, "config.yaml")
logger = get_logger("trade_exec")

class TradeError(Exception):
    """交易流程错误(触发安全退出)"""

def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0

@dataclass
class OrderResult:
    symbol: str
    side: str
    order_type: str
    price: float
    quantity: float
    status: str
    order_id: str
    client_order_id: str = ""
    error: Optional[str] = None

class LiveTrader:
    """实盘/演练执行器(封装 core.binance_client.BinanceClient)"""

    def __init__(self, api_key: str, api_secret: str,
                 base_url: str = "https://fapi.binance.com", timeout: int = 15):
        self.api_key, self.api_secret, self.base_url, self.timeout = \
            api_key, api_secret, base_url, timeout
        try:
            from core import binance_client as bc
        except ImportError as exc:
            raise TradeError("缺少 core/binance_client.py, 无法实盘/演练") from exc
        self.client = bc.BinanceClient(api_key, api_secret,
                                       base_url=base_url, timeout=timeout)

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        fn = getattr(self.client, name, None)
        if fn is None:
            raise TradeError("BinanceClient 缺少方法 %s" % name)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.error("币安调用 %s 失败: %s", name, exc)
            raise TradeError("币安调用 %s 失败: %s" % (name, exc)) from exc

    def current_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        resp = self._call("get_position_risk", symbol)
        ps = resp if isinstance(resp, list) else ([resp] if isinstance(resp, dict) else [])
        return next((p for p in ps if _f(p.get("positionAmt")) != 0.0), None)

    def get_user_trades(self, symbol: str, limit: int = 5) -> list:
        """查询用户成交记录(真实成交价), 供 testnet poll 记账。"""
        return self._call("get_user_trades", symbol, limit)

    def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        """设置保证金模式(逐仓/全仓)。"""
        return self._call("set_margin_type", symbol, margin_type)

    def get_order(self, symbol: str, order_id: int = None,
                  orig_client_order_id: str = None) -> dict:
        """查询订单状态(用于成交确认)。"""
        if order_id is not None:
            return self._call("get_order", symbol, order_id=order_id)
        return self._call("get_order", symbol, orig_client_order_id=orig_client_order_id)

    def _round(self, symbol: str, value: float, kind: str) -> float:
        """价格/数量按合约精度修正; 优先 client._round_*, 失败本地兜底

        数量(kind="qty")向上取整到最小步长, 保证名义下单额达标(含币安最小
        名义约束); 价格四舍五入到 tickSize。
        """
        if kind == "qty":
            step = self._step(symbol, kind)
            if step > 0:
                import math
                qty = float(value)
                return float(math.ceil(qty / step) * step)
            return float(value)
        fn = getattr(self.client, "_round_price", None)
        if callable(fn):
            try:
                return float(fn(symbol, value))
            except Exception as exc:
                logger.warning("价格精度修正失败, 本地兜底: %s", exc)
        step = self._step(symbol, kind)
        if step <= 0:
            return float(value)
        return round(value / step) * step

    def _step(self, symbol: str, kind: str) -> float:
        try:
            info = self._call("get_symbol_info", symbol) or {}
            f = {i.get("filterType"): i for i in info.get("filters", []) or []}.get(
                "PRICE_FILTER" if kind == "price" else "LOT_SIZE") or {}
            return _f(f.get("tickSize" if kind == "price" else "stepSize"))
        except TradeError:
            return 0.0

    def _inject_client_id(self, kwargs: Dict[str, Any], cid: str) -> None:
        try:
            params = inspect.signature(self.client.place_order).parameters
        except (TypeError, ValueError):
            params = {}
        for k in ("new_client_order_id", "client_order_id", "clientOrderId", "params"):
            if k in params:
                kwargs[k] = {"clientOrderId": cid} if k == "params" else cid
                return
        logger.warning("place_order 不支持 clientOrderId, 防重复靠持仓校验兜底")

    def place_order(self, symbol: str, side: str, order_type: str,
                    quantity: float, price: Optional[float] = None,
                    stop_price: Optional[float] = None,
                    reduce_only: bool = False, test: bool = False,
                    client_order_id: Optional[str] = None) -> OrderResult:
        kwargs: Dict[str, Any] = {"reduce_only": reduce_only, "test": test}
        if price is not None:
            kwargs["price"] = price
        if stop_price is not None:
            kwargs["stop_price"] = stop_price
        if client_order_id:
            self._inject_client_id(kwargs, client_order_id)
        logger.info("下单 %s %s %s qty=%s price=%s stop=%s red=%s test=%s cid=%s",
                    symbol, side, order_type, quantity, price, stop_price,
                    reduce_only, test, client_order_id)
        resp = self._call("place_order", symbol, side, order_type, quantity, **kwargs)
        if isinstance(resp, OrderResult):
            return resp
        resp = resp if isinstance(resp, dict) else {}
        return OrderResult(
            symbol=symbol, side=side, order_type=order_type,
            price=_f(resp.get("price") or resp.get("avgPrice") or resp.get("stopPrice")),
            quantity=_f(resp.get("origQty") or resp.get("quantity")),
            status=str(resp.get("status") or "NEW"),
            order_id=str(resp.get("orderId") or resp.get("clientOrderId") or ""),
            client_order_id=str(resp.get("clientOrderId") or ""),
            error=resp.get("error") or resp.get("msg"))

    def place_conditional_order(self, symbol: str, side: str, order_type: str,
                                quantity: float, stop_price: float,
                                reduce_only: bool = True, test: bool = False,
                                client_order_id: Optional[str] = None) -> OrderResult:
        """止损/止盈条件单(Algo Order API)转发, 统一错误处理与结果归一化。"""
        kwargs: Dict[str, Any] = {"reduce_only": reduce_only, "test": test}
        if client_order_id:
            self._inject_client_id(kwargs, client_order_id)
        logger.info("条件单 %s %s %s qty=%s stop=%s red=%s test=%s cid=%s",
                    symbol, side, order_type, quantity, stop_price,
                    reduce_only, test, client_order_id)
        resp = self._call("place_conditional_order", symbol, side, order_type,
                          quantity, stop_price, **kwargs)
        if isinstance(resp, OrderResult):
            return resp
        resp = resp if isinstance(resp, dict) else {}
        return OrderResult(
            symbol=symbol, side=side, order_type=order_type,
            price=_f(resp.get("stopPrice") or resp.get("price") or 0),
            quantity=_f(resp.get("quantity") or resp.get("origQty")),
            status=str(resp.get("status") or "NEW"),
            order_id=str(resp.get("orderId") or resp.get("algoId") or ""),
            client_order_id=str(resp.get("clientOrderId") or ""),
            error=resp.get("error") or resp.get("msg"))

class PaperTrader:
    """模拟交易执行器(不实际下单, 记录到 JSON)"""

    def __init__(self, log_path: str = "paper_trades.json"):
        self.log_path = log_path
        self.trades = self._load()

    def _load(self) -> list:
        if os.path.exists(self.log_path):
            with open(self.log_path) as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.log_path, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)

    def execute(self, signal) -> dict:
        trade = {
            "time": datetime.utcnow().isoformat(),
            "symbol": signal.symbol,
            "direction": signal.direction,
            "entry": (signal.entry_low + signal.entry_high) / 2,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "quantity": signal.position_usd,
            "leverage": signal.leverage,
            "status": "OPEN",
            "pnl": None,
        }
        self.trades.append(trade)
        self._save()
        return trade

def _load_config(path: str) -> dict:
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def _validate(entry: float, tp: float, sl: float, side: str) -> None:
    if min(entry, tp, sl) <= 0:
        raise TradeError("entry/tp/sl 必须为正数")
    if side == "LONG" and not (tp > entry > sl) or side == "SHORT" and not (tp < entry < sl):
        raise TradeError("tp/sl 相对 entry 方向不合法")

def _params(args, config: dict) -> dict:
    _validate(args.entry, args.tp, args.sl, args.side)
    lev = args.leverage or (config.get("trade", {}) or {}).get("leverage") or 10
    return {"symbol": args.symbol, "side": args.side, "entry": args.entry,
            "tp": args.tp, "sl": args.sl, "notional_usd": args.qty,
            "qty": args.qty / args.entry, "leverage": lev}

def _box(params: dict, live: bool) -> None:
    move = abs(params["tp"] - params["entry"]) / params["entry"] * 100
    print("=" * 58, "%s 订单: %s %s" % ("实盘" if live else "演练", params["symbol"], params["side"]),
          "  入场 %g | 止盈 %g | 止损 %g" % (params["entry"], params["tp"], params["sl"]),
          "  名义 %.2f USDT | 合约量 %.6g | 杠杆 %dx | 杠杆后 PnL ±%.2f%%" % (
              params["notional_usd"], params["qty"], params["leverage"], move * params["leverage"]),
          "=" * 58, sep="\n")

def _execute(trader: LiveTrader, p: dict, test: bool, no_log: bool) -> None:
    symbol, side = p["symbol"], p["side"]
    entry, tp, sl = p["entry"], p["tp"], p["sl"]
    notional, lev = p["notional_usd"], p["leverage"]
    long = side == "LONG"
    buy_side, close_side = ("BUY", "SELL") if long else ("SELL", "BUY")
    tag = "演练" if test else "实盘"
    ts = int(time.time() * 1000)

    logger.info("设置杠杆 %s %dx", symbol, lev)
    trader._call("set_leverage", symbol, lev)

    bal = trader._call("get_balance", asset="USDT") or {}
    available = _f(bal.get("availableBalance", bal.get("available")))
    # 合约开仓实际冻结的是保证金 = 名义/杠杆, 用保证金校验余额更贴近真实占用
    margin_needed = notional / lev
    if available < margin_needed:
        raise TradeError("可用余额 %.2f USDT < 所需保证金 %.2f USDT, 拒绝开仓"
                         % (available, margin_needed))
    logger.info("%s: 余额校验通过 available=%.2f >= 保证金=%.2f (名义 %.2f, %dx)",
                tag, available, margin_needed, notional, lev)
    pos = trader.current_position(symbol)
    if pos is not None:
        amt = _f(pos.get("positionAmt"))
        if (amt > 0) == long:
            raise TradeError("已存在同向持仓 %s amt=%s, 拒绝重复开仓" % (symbol, amt))
        logger.warning("%s: 反向持仓 %s amt=%s, 开仓后双向持仓, 注意风控", tag, symbol, amt)
    entry_r = trader._round(symbol, entry, "price")
    sl_r = trader._round(symbol, sl, "price")
    tp_r = trader._round(symbol, tp, "price")
    qty_r = trader._round(symbol, notional / entry, "qty")

    entry_res = trader.place_order(symbol, buy_side, "LIMIT", qty_r,
                                   price=entry_r,
                                   client_order_id="bsl-%s-%d" % (symbol, ts), test=test)
    print("[%s] 入场单 %s #%s" % (tag, entry_res.status, entry_res.order_id))
    if not (test or entry_res.status == "FILLED"):
        raise TradeError(
            "入场单未成交(status=%s), 未下止盈止损. 请成交后手动补单: "
            "STOP_MARKET %s / TAKE_PROFIT_MARKET %s reduceOnly"
            % (entry_res.status, sl_r, tp_r))
    for otype, label, stp in (("STOP_MARKET", "止损", sl_r),
                              ("TAKE_PROFIT_MARKET", "止盈", tp_r)):
        try:
            cid = "%s-%s-%d" % ("bssl" if otype == "STOP_MARKET" else "bstp", symbol, ts)
            if p.get("algo", True):
                res = trader.place_conditional_order(
                    symbol, close_side, otype, qty_r, stop_price=stp,
                    reduce_only=True, test=test,
                    client_order_id=cid)
            else:
                res = trader.place_order(symbol, close_side, otype, qty_r,
                                         stop_price=stp, reduce_only=True,
                                         test=test, client_order_id=cid)
            print("[%s] %s单 %s #%s" % (tag, label, res.status, res.order_id))
        except TradeError as exc:
            logger.error("%s: %s单下单失败: %s", tag, label, exc)
            print("[%s] ❌ %s单失败: %s —— 请手动补 %s %s reduceOnly" % (tag, label, exc, otype, stp))

    if no_log:
        return
    try:
        fill = _f(entry_res.price) or entry
        log_trade(symbol=symbol, direction=side, entry=fill,
                  exit_price=fill, result="OPEN", pnl_pct=0.0,
                  leverage=lev, notes="%s mode sl=%s tp=%s" % (tag, sl, tp))
        logger.info("%s: 已记录 OPEN 交易 %s %s", tag, symbol, side)
    except Exception as exc:
        logger.error("%s: 记录交易失败: %s", tag, exc)

def main():
    p = argparse.ArgumentParser(description="BB套利 - 实盘/演练交易执行")
    p.add_argument("--symbol", required=True)
    p.add_argument("--side", required=True, choices=["LONG", "SHORT"])
    p.add_argument("--entry", type=float, required=True, help="入场价")
    p.add_argument("--tp", type=float, required=True, help="止盈价")
    p.add_argument("--sl", type=float, required=True, help="止损价")
    p.add_argument("--qty", type=float, required=True, help="名义金额(USDT)")
    p.add_argument("--leverage", type=int, default=None, help="杠杆(默认 config)")
    p.add_argument("--test", action="store_true", help="test 订单演练(不真实成交)")
    p.add_argument("--live", action="store_true", help="真实下单")
    p.add_argument("--force", action="store_true", help="跳过确认(仅配合 --live)")
    p.add_argument("--no-log", action="store_true", help="不写 trades.json")
    p.add_argument("--algo", action="store_true",
                   help="止损止盈走 Algo Order API(条件单, 默认 True 自动启用)")
    p.set_defaults(algo=True)
    args = p.parse_args()

    config = _load_config(DEFAULT_CONFIG)
    try:
        params = _params(args, config)
    except TradeError as exc:
        logger.error("参数校验失败: %s", exc)
        print("❌ %s" % exc)
        sys.exit(1)

    if not args.live and not args.test:
        _box(params, live=False)
        print("\n未指定模式, 仅展示订单信息.\n  --test  走币安 test 接口演练(不真实成交)\n  --live  真实下单(需密钥 + 输入 yes 确认)")
        return

    api_key = os.environ.get("BINANCE_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        logger.error("缺少 BINANCE_API_KEY/BINANCE_API_SECRET 环境变量")
        print("❌ 缺少 BINANCE_API_KEY / BINANCE_API_SECRET 环境变量, 拒绝执行")
        sys.exit(1)

    if args.live and not args.force:
        _box(params, live=True)
        try:
            confirm = input("\n⚠️  确认实盘下单? [yes/no]: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm != "yes":
            print("已取消, 未发送任何请求")
            return
        logger.info("用户确认实盘下单")

    base_url = (config.get("binance", {}) or {}).get("base_url", "https://fapi.binance.com")
    try:
        trader = LiveTrader(api_key, api_secret, base_url=base_url)
        _execute(trader, params, test=args.test, no_log=args.no_log)
        print("\n✅ 流程完成(%s)" % ("演练" if args.test else "实盘"))
    except TradeError as exc:
        logger.error("交易流程中止: %s", exc)
        print("\n❌ %s" % exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("未预期错误")
        print("\n❌ 未预期错误: %s" % exc)
        sys.exit(1)

if __name__ == "__main__":
    main()
