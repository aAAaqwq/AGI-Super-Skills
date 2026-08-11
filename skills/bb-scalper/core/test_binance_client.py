"""core/test_binance_client.py — BinanceClient 单元测试（不触网）"""
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.binance_client import (  # noqa: E402
    BinanceAPIError,
    BinanceClient,
    BinanceConnectionError,
)


class _FakeResp:
    def __init__(self, status, json_data=None, text=""):
        self.status_code = status
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def _parse_qs(qs: str) -> dict:
    """解析 requests 收到的 query string 为 dict。"""
    from urllib.parse import parse_qs
    return {k: v[0] for k, v in parse_qs(qs).items()}


@pytest.fixture
def client():
    return BinanceClient("test-key", "test-secret", base_url="https://fapi.binance.com")


def test_signature_matches_binance_doc(client, monkeypatch):
    """签名可由 hmac 独立重算一致(键排序+urlencode+HMAC-SHA256)。"""
    secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
    c = BinanceClient("vmPUZE6mv9SD5VNHk4HlWFsOr6hKE0H8NCjSx9xZ", secret)

    captured = {}

    def fake_post(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResp(200, {"orderId": 1})

    monkeypatch.setattr("requests.post", fake_post)
    c.place_order("LTCBTC", "BUY", "LIMIT", 1, price=0.1)

    assert captured["headers"]["X-MBX-APIKEY"] == "vmPUZE6mv9SD5VNHk4HlWFsOr6hKE0H8NCjSx9xZ"
    qs = captured["params"]
    q = qs.split("&signature=")[0]
    sig = qs.split("signature=")[-1]
    # 独立重算: 排序键 + urlencode + HMAC-SHA256(secret)
    import hashlib, hmac, urllib.parse
    expected = hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()
    assert sig == expected
    # 键按字母序
    keys = [kv.split("=")[0] for kv in q.split("&")]
    assert keys == sorted(keys)


def test_signature_changes_with_timestamp(client, monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResp(200, {})

    monkeypatch.setattr("requests.get", fake_get)
    # 直接构造两个不同 timestamp 的签名请求, 验证签名随 timestamp 变化
    import hashlib, hmac, urllib.parse

    def make_sig(ts):
        p = {"symbol": "NEARUSDT", "timestamp": ts}
        q = urllib.parse.urlencode(sorted(p.items()))
        return hmac.new("test-secret".encode(), q.encode(), hashlib.sha256).hexdigest()

    assert make_sig(1000) != make_sig(2000)


def test_place_order_params(client, monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResp(200, {"orderId": 99, "status": "FILLED"})

    monkeypatch.setattr("requests.post", fake_post)
    resp = client.place_order(
        "NEARUSDT", "buy", "limit", 6, price=1.592, stop_price=None,
        reduce_only=True, test=True,
    )
    assert captured["url"].endswith("/fapi/v1/order/test")
    params = _parse_qs(captured["params"])
    assert params["symbol"] == "NEARUSDT"
    assert params["side"] == "BUY"
    assert params["type"] == "LIMIT"
    assert params["quantity"] == "6"
    assert params["price"] == "1.592"
    assert params["timeInForce"] == "GTC"
    assert params["reduceOnly"] == "true"
    assert "timestamp" in params
    assert "signature" in params
    assert resp["orderId"] == 99


def test_place_order_stop_market(client, monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResp(200, {"orderId": 5})

    monkeypatch.setattr("requests.post", fake_post)
    client.place_order("NEARUSDT", "SELL", "STOP_MARKET", 6,
                       stop_price=1.589, reduce_only=True)
    params = _parse_qs(captured["params"])
    assert params["type"] == "STOP_MARKET"
    assert params["stopPrice"] == "1.589"
    assert "price" not in params  # 触发单不该带限价
    assert "timeInForce" not in params


def test_get_balance_asset_not_found(client, monkeypatch):
    monkeypatch.setattr(
        "requests.get",
        lambda url, params=None, headers=None, timeout=None: _FakeResp(
            200, [{"asset": "BTC", "balance": "1", "availableBalance": "1"}]
        ),
    )
    bal = client.get_balance("USDT")
    assert bal["balance"] == "0"


def test_get_symbol_info_not_found(client, monkeypatch):
    monkeypatch.setattr(
        "requests.get",
        lambda url, params=None, headers=None, timeout=None: _FakeResp(
            200, {"symbols": [{"symbol": "BTCUSDT"}]}
        ),
    )
    with pytest.raises(ValueError):
        client.get_symbol_info("NEARUSDT")


def test_api_error_raises(client, monkeypatch):
    monkeypatch.setattr(
        "requests.post",
        lambda url, params=None, headers=None, timeout=None: _FakeResp(
            400, {"code": -2015, "msg": "Invalid API-key"}, text="{\"code\":-2015}"
        ),
    )
    with pytest.raises(BinanceAPIError) as exc:
        client.place_order("NEARUSDT", "BUY", "LIMIT", 6, price=1.592)
    assert exc.value.code == -2015
    assert exc.value.status == 400


def test_connection_error_raises(client, monkeypatch):
    import requests

    def boom(url, params=None, headers=None, timeout=None):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("requests.post", boom)
    with pytest.raises(BinanceConnectionError):
        client.place_order("NEARUSDT", "BUY", "LIMIT", 6, price=1.592)


def test_round_precision(client, monkeypatch):
    info = {"symbol": "NEARUSDT", "pricePrecision": 4, "quantityPrecision": 2,
            "filters": []}
    monkeypatch.setattr(client, "_signed_request",
                        lambda method, path, params, signed=False: {"symbols": [info]})
    assert client._round_price("NEARUSDT", 1.592123) == 1.5921
    # round() 对 .5 是银行家舍入: 6.555 -> 6.55 (浮点表示)
    assert client._round_qty("NEARUSDT", 6.555) == 6.55
