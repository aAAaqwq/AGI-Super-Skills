"""cli/test_trade_exec.py — trade_exec 安全机制与流程单元测试（不触网）"""
import importlib.util
import os
import sys
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cli.trade_exec as te  # noqa: E402


def _load_module():
    spec = importlib.util.spec_from_file_location("binance_client", os.path.join(ROOT, "core", "binance_client.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validate_long_ok():
    te._validate(1.588, 1.610, 1.583, "LONG")  # 不抛


def test_validate_short_ok():
    te._validate(1.610, 1.588, 1.623, "SHORT")


def test_validate_long_bad_order():
    with pytest.raises(te.TradeError):
        te._validate(1.588, 1.580, 1.583, "LONG")  # tp < entry


def test_validate_negative():
    with pytest.raises(te.TradeError):
        te._validate(-1.0, 1.6, 1.49, "LONG")


def test_params_compute_qty():
    params = te._params(
        mock.Mock(symbol="NEARUSDT", side="LONG", entry=1.588, tp=1.610,
                  sl=1.583, qty=50, leverage=None),
        {"trade": {"leverage": 10}},
    )
    assert params["notional_usd"] == 50
    assert params["qty"] == pytest.approx(50 / 1.588)
    assert params["leverage"] == 10


def test_current_position_ignores_zero():
    bc = _load_module()
    trader = te.LiveTrader("k", "s")
    trader.client = mock.Mock()
    trader.client.get_position_risk.return_value = [
        {"symbol": "NEARUSDT", "positionAmt": "0"},
        {"symbol": "NEARUSDT", "positionAmt": "5"},
    ]
    pos = trader.current_position("NEARUSDT")
    assert pos is not None and pos["positionAmt"] == "5"


def test_inject_client_id_no_support():
    bc = _load_module()
    trader = te.LiveTrader("k", "s")
    trader.client.place_order = lambda *a, **k: None  # 无该参数
    kwargs = {}
    with mock.patch.object(te.logger, "warning") as w:
        trader._inject_client_id(kwargs, "bsl-NEARUSDT-1")
    assert "clientOrderId" not in kwargs
    w.assert_called_once()


def test_round_fallback_qty_ceil():
    bc = _load_module()
    trader = te.LiveTrader("k", "s")
    trader.client = mock.Mock()
    trader.client.get_symbol_info.return_value = {
        "symbol": "NEARUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.1"}],
    }
    # 数量向上取整到步长: 6.01 → 6.1
    assert trader._round("NEARUSDT", 6.01, "qty") == pytest.approx(6.1)


def test_execute_happy_path(tmp_path, monkeypatch):
    bc = _load_module()
    trader = te.LiveTrader("k", "s")
    calls = []

    class FakeClient:
        def set_leverage(self, symbol, lev):
            calls.append(("leverage", symbol, lev)); return {}

        def get_balance(self, asset="USDT"):
            return {"asset": "USDT", "availableBalance": "1000"}

        def get_position_risk(self, symbol):
            return [{"symbol": symbol, "positionAmt": "0"}]

        def get_symbol_info(self, symbol):
            return {"symbol": symbol, "pricePrecision": 4, "quantityPrecision": 2,
                    "filters": []}

        def _round_price(self, symbol, price):
            return round(price, 4)

        def _round_qty(self, symbol, qty):
            return round(qty, 2)

        def place_order(self, symbol, side, order_type, quantity, **kw):
            calls.append(("order", symbol, side, order_type, quantity, kw))
            st = "FILLED" if order_type == "LIMIT" else "NEW"
            return {"status": st, "orderId": len(calls), "avgPrice": str(kw.get("price", 0))}

        def place_conditional_order(self, symbol, side, order_type, quantity,
                                    stop_price, **kw):
            calls.append(("cond", symbol, side, order_type, quantity, stop_price, kw))
            return {"status": "VALIDATED", "orderId": len(calls),
                    "stopPrice": str(stop_price)}

    trader.client = FakeClient()
    p = {"symbol": "NEARUSDT", "side": "LONG", "entry": 1.588, "tp": 1.610,
         "sl": 1.583, "notional_usd": 50, "qty": 50 / 1.588, "leverage": 10,
         "algo": True}

    db = tmp_path / "trades.json"
    monkeypatch.setattr(te.log_trade, "__defaults__", (str(db),))
    monkeypatch.setattr(te, "log_trade", lambda **kw: kw)

    te._execute(trader, p, test=True, no_log=False)

    types = [c[0] for c in calls]
    assert types == ["leverage", "order", "cond", "cond"]
    limit = calls[1]
    assert limit[3] == "LIMIT"
    assert limit[5]["price"] == 1.588
    assert limit[5]["reduce_only"] is False
    # 止损/止盈走条件单(cond), reduceOnly, stop_price 作为位置参数
    for i in (2, 3):
        assert calls[i][0] == "cond"
        assert calls[i][3] in ("STOP_MARKET", "TAKE_PROFIT_MARKET")
        assert calls[i][6]["reduce_only"] is True
    # 条件单数量与入场一致, 止损/止盈触发价正确(经精度修正)
    assert calls[2][4] == limit[4]
    assert calls[3][4] == limit[4]
    assert calls[2][5] == pytest.approx(1.583)
    assert calls[3][5] == pytest.approx(1.61)


def test_execute_same_direction_position_rejected(tmp_path):
    bc = _load_module()
    trader = te.LiveTrader("k", "s")

    class FakeClient:
        def set_leverage(self, symbol, lev):
            return {}

        def get_balance(self, asset="USDT"):
            return {"availableBalance": "1000"}

        def get_position_risk(self, symbol):
            return [{"symbol": symbol, "positionAmt": "5"}]  # 已有多头

    trader.client = FakeClient()
    p = {"symbol": "NEARUSDT", "side": "LONG", "entry": 1.588, "tp": 1.610,
         "sl": 1.583, "notional_usd": 50, "qty": 50 / 1.588, "leverage": 10,
         "algo": True}
    with pytest.raises(te.TradeError, match="同向持仓"):
        te._execute(trader, p, test=True, no_log=False)


def test_execute_insufficient_balance_rejected(tmp_path):
    bc = _load_module()
    trader = te.LiveTrader("k", "s")

    class FakeClient:
        def set_leverage(self, symbol, lev):
            return {}

        def get_balance(self, asset="USDT"):
            return {"availableBalance": "10"}

        def get_position_risk(self, symbol):
            return [{"symbol": symbol, "positionAmt": "0"}]

    trader.client = FakeClient()
    # 名义 500, 10x → 保证金 50 > 可用 10 → 拒绝
    p = {"symbol": "NEARUSDT", "side": "LONG", "entry": 1.588, "tp": 1.610,
         "sl": 1.583, "notional_usd": 500, "qty": 500 / 1.588, "leverage": 10,
         "algo": True}
    with pytest.raises(te.TradeError, match="所需保证金"):
        te._execute(trader, p, test=True, no_log=False)
