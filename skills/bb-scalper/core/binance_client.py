#!/usr/bin/env python3
"""
core/binance_client.py — 币安 USDT 永续合约 REST 客户端

统一签名 + 错误处理，供 cli/trade_exec.py 等上层模块调用。

签名方式（Binance 要求）:
  - params 加入 timestamp（以及 recvWindow=10000）后按字母序排序
  - 用 urllib.parse.urlencode 生成 query string（不手工拼接）
  - HMAC-SHA256 对 query string 签名，结果作为 signature 参数

用法:
  from core.binance_client import BinanceClient
  client = BinanceClient(api_key, api_secret)
  client.set_leverage("NEARUSDT", 10)
  client.place_order("NEARUSDT", "BUY", "LIMIT", 6, price=1.592)
"""
import hashlib
import hmac
import os
import sys
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import get_logger


class BinanceAPIError(Exception):
    """币安接口返回的业务错误（HTTP 非 2xx）。"""

    def __init__(self, code: Any, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"Binance API error (HTTP {status}, code {code}): {message}")


class BinanceConnectionError(Exception):
    """网络层/连接层错误（requests 异常包装）。"""

    def __init__(self, message: str, original: Optional[Exception] = None) -> None:
        self.original = original
        if original is not None:
            message = f"{message} ({original})"
        super().__init__(f"Binance connection error: {message}")


class BinanceClient:
    """币安 USDT 永续合约 REST 客户端。

    Args:
        api_key: Binance API Key
        api_secret: Binance API Secret
        base_url: API 基础地址，默认币安期货 https://fapi.binance.com
        timeout: 请求超时（秒）
    """

    def __init__(self, api_key: str, api_secret: str,
                 base_url: str = "https://fapi.binance.com",
                 timeout: int = 15) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = get_logger("binance_client")
        self._symbol_info_cache: Dict[str, dict] = {}

    # ── 内部方法 ──

    def _signed_request(self, method: str, path: str,
                        params: Optional[Dict[str, Any]] = None,
                        signed: bool = True) -> Any:
        """统一签名 + 请求 + 错误处理。

        signed=True 时：
          - 自动加入 timestamp 与 recvWindow=10000
          - urlencode(排序后的 params) 作为待签 query string
          - HMAC-SHA256 签名，signature 追加到 query string
        GET 请求把 query string 作为 requests 的 params 参数直接发送。

        Raises:
            BinanceAPIError: 币安返回非 2xx 状态码
            BinanceConnectionError: 网络层异常
        """
        params = dict(params or {})
        url = f"{self.base_url}{path}"
        headers: Dict[str, str] = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 10000
            query = urllib.parse.urlencode(sorted(params.items()))
            signature = hmac.new(
                self.api_secret.encode(), query.encode(), hashlib.sha256
            ).hexdigest()
            query += f"&signature={signature}"
            headers["X-MBX-APIKEY"] = self.api_key
        else:
            query = urllib.parse.urlencode(sorted(params.items())) if params else ""

        try:
            if method == "GET":
                resp = requests.get(url, params=query, headers=headers, timeout=self.timeout)
            elif method == "POST":
                resp = requests.post(url, params=query, headers=headers, timeout=self.timeout)
            elif method == "DELETE":
                resp = requests.delete(url, params=query, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.RequestException as e:
            self.logger.error("%s %s 网络错误: %s", method, url, e)
            raise BinanceConnectionError(f"{method} {path} 请求失败", original=e) from e

        if resp.status_code >= 400:
            code: Any = resp.status_code
            message = resp.text or "unknown error"
            try:
                body = resp.json()
                code = body.get("code", code)
                message = body.get("msg", message)
            except ValueError:
                pass
            self.logger.error("%s %s 失败: HTTP %s code=%s msg=%s",
                              method, url, resp.status_code, code, message)
            raise BinanceAPIError(code=code, message=message, status=resp.status_code)

        self.logger.debug("%s %s -> %s", method, url, resp.status_code)
        try:
            return resp.json()
        except ValueError:
            return {}

    # ── 公开 API 方法 ──

    def place_order(self, symbol: str, side: str, order_type: str,
                    quantity: float, price: Optional[float] = None,
                    stop_price: Optional[float] = None,
                    reduce_only: bool = False, test: bool = False) -> dict:
        """下单。

        Args:
            symbol: 交易对（如 NEARUSDT）
            side: BUY / SELL（自动转大写）
            order_type: LIMIT / MARKET / STOP_MARKET / TAKE_PROFIT_MARKET（自动转大写）
            quantity: 数量
            price: 限价单价格；传入时自动补 timeInForce=GTC
            stop_price: 触发价（STOP/TAKE_PROFIT 类型）
            reduce_only: 是否只减仓单
            test: True 走 /fapi/v1/order/test 下单校验，不真实成交

        Returns:
            币安原始下单响应 dict
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if price is not None:
            params["price"] = price
            params["timeInForce"] = "GTC"
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if reduce_only:
            params["reduceOnly"] = "true"

        path = "/fapi/v1/order/test" if test else "/fapi/v1/order"
        return self._signed_request("POST", path, params)

    def place_conditional_order(self, symbol: str, side: str, order_type: str,
                                quantity: float, stop_price: float,
                                reduce_only: bool = True,
                                test: bool = False) -> dict:
        """下条件单（止损/止盈）。

        币安已把 STOP_MARKET / TAKE_PROFIT_MARKET 迁到 Algo Order API
        （/fapi/v1/algo/order），普通 /fapi/v1/order 会返回 -4120。

        Args:
            symbol: 交易对
            side: BUY / SELL（自动转大写）
            order_type: STOP_MARKET / TAKE_PROFIT_MARKET
            quantity: 数量
            stop_price: 触发价
            reduce_only: 是否只减仓单（默认 True，风控要求）
            test: True 优先走 /fapi/v1/algo/order/test；若该端点不存在(404)
                  则降级为本地参数校验，绝不发真实单

        Returns:
            币安响应 dict；test 降级时为 {"status": "VALIDATED", ...}
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "stopPrice": stop_price,
        }
        if reduce_only:
            params["reduceOnly"] = "true"

        path = "/fapi/v1/algo/order/test" if test else "/fapi/v1/algo/order"
        try:
            return self._signed_request("POST", path, params)
        except BinanceAPIError as e:
            if test and e.status == 404:
                self.logger.warning(
                    "algo test 端点不可用(HTTP 404), 降级为本地参数校验: %s %s qty=%s stop=%s red=%s",
                    symbol, order_type, quantity, stop_price, reduce_only)
                return self._validate_conditional_params(params)
            raise

    @staticmethod
    def _validate_conditional_params(params: Dict[str, Any]) -> dict:
        """本地校验条件单参数（algo test 端点不可用时的演练降级）。"""
        problems = []
        if not params.get("symbol"):
            problems.append("symbol 缺失")
        if params.get("type") not in ("STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"):
            problems.append("type 不支持: %s" % params.get("type"))
        if not params.get("quantity") or float(params["quantity"]) <= 0:
            problems.append("quantity 必须为正")
        if not params.get("stopPrice") or float(params["stopPrice"]) <= 0:
            problems.append("stopPrice 必须为正")
        notional = float(params.get("quantity", 0)) * float(params.get("stopPrice", 0))
        if notional < 5 and params.get("reduceOnly") != "true":
            problems.append("名义 %.2f < 最小 5 USDT" % notional)
        if problems:
            raise BinanceAPIError(code=-1, message="; ".join(problems), status=400)
        return {"status": "VALIDATED",
                "symbol": params["symbol"], "type": params["type"],
                "quantity": params["quantity"], "stopPrice": params["stopPrice"]}

    def cancel_order(self, symbol: str, order_id: Optional[int] = None,
                     orig_client_order_id: Optional[str] = None) -> dict:
        """撤销订单。order_id 与 orig_client_order_id 至少给一个。

        Returns:
            被撤销订单的响应 dict
        """
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if orig_client_order_id is not None:
            params["origClientOrderId"] = orig_client_order_id
        return self._signed_request("DELETE", "/fapi/v1/order", params)

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """查询当前挂单。

        Args:
            symbol: 交易对；None 查询全部

        Returns:
            挂单列表
        """
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return self._signed_request("GET", "/fapi/v1/openOrders", params)

    def get_user_trades(self, symbol: str, limit: int = 5) -> list:
        """查询用户成交记录(含真实成交价 avgPrice 由 price 字段体现)。

        Args:
            symbol: 交易对
            limit: 返回条数(默认5)

        Returns:
            成交记录列表, 每条含 price/qty/side/time
        """
        params: Dict[str, Any] = {"symbol": symbol, "limit": limit}
        return self._signed_request("GET", "/fapi/v1/userTrades", params)

    def get_position_risk(self, symbol: Optional[str] = None) -> list:
        """查询持仓风险（含 positionAmt/entryPrice/unRealizedProfit）。

        Args:
            symbol: 交易对；None 查询全部

        Returns:
            持仓列表
        """
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return self._signed_request("GET", "/fapi/v2/positionRisk", params)

    def get_balance(self, asset: str = "USDT") -> dict:
        """查询资产余额。

        Args:
            asset: 资产名（默认 USDT）

        Returns:
            该资产的余额 dict（含 balance/availableBalance）；未找到时返回 0 余额
        """
        data = self._signed_request("GET", "/fapi/v2/balance", {})
        for item in data:
            if item.get("asset") == asset:
                return item
        return {"asset": asset, "balance": "0", "availableBalance": "0"}

    def get_symbol_info(self, symbol: str) -> dict:
        """查询合约信息（含 pricePrecision/quantityPrecision）。

        Args:
            symbol: 交易对（如 NEARUSDT）

        Returns:
            该合约的 exchangeInfo 条目 dict

        Raises:
            ValueError: 未在 exchangeInfo 中找到该 symbol
        """
        if symbol in self._symbol_info_cache:
            return self._symbol_info_cache[symbol]

        data = self._signed_request("GET", "/fapi/v1/exchangeInfo", {}, signed=False)
        for item in data.get("symbols", []):
            if item.get("symbol") == symbol:
                self._symbol_info_cache[symbol] = item
                return item
        raise ValueError(f"Symbol not found in exchangeInfo: {symbol}")

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """设置合约杠杆。

        Args:
            symbol: 交易对
            leverage: 杠杆倍数

        Returns:
            杠杆设置结果 dict
        """
        params: Dict[str, Any] = {"symbol": symbol, "leverage": int(leverage)}
        return self._signed_request("POST", "/fapi/v1/leverage", params)

    # ── 精度处理 ──

    def _round_price(self, symbol: str, price: float) -> float:
        """按合约 pricePrecision 将价格四舍五入到正确小数位。"""
        precision = int(self.get_symbol_info(symbol).get("pricePrecision", 8))
        return round(float(price), precision)

    def _round_qty(self, symbol: str, quantity: float) -> float:
        """按合约 quantityPrecision 将数量四舍五入到正确小数位。"""
        precision = int(self.get_symbol_info(symbol).get("quantityPrecision", 8))
        return round(float(quantity), precision)
