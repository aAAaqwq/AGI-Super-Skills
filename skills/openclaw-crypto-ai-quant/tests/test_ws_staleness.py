from __future__ import annotations

import logging
import time

import pytest

from exchange.ws import HyperliquidWS
from live import trader as live_trader


def test_ws_on_close_keeps_market_snapshots_for_bounded_staleness():
    ws = HyperliquidWS()
    now = time.time()

    with ws._lock:
        ws._mids["ETH"] = 100.0
        ws._mids_updated_at["ETH"] = now - 2.0
        ws._bbo["ETH"] = (99.0, 101.0)
        ws._bbo_updated_at["ETH"] = now - 2.0
        ws._connected = True

    ws._on_close(None, 1006, "test close")

    assert ws.get_mid("ETH", max_age_s=10.0) == pytest.approx(100.0)
    assert ws.get_mid("ETH", max_age_s=0.1) is None
    assert ws.get_bbo("ETH", max_age_s=10.0) == pytest.approx((99.0, 101.0))
    disconnect_age = ws.get_ws_disconnect_age_s()
    assert disconnect_age is not None
    assert disconnect_age >= 0.0


class _FakeWs:
    def __init__(
        self,
        *,
        mid: float | None,
        bbo: tuple[float, float] | None = None,
        mid_age_s: float | None = None,
        disconnect_age_s: float | None = None,
    ):
        self._mid = mid
        self._bbo = bbo
        self._mid_age_s = mid_age_s
        self._disconnect_age_s = disconnect_age_s

    def get_mid(self, _symbol: str, max_age_s: float | None = None) -> float | None:
        return self._mid

    def get_bbo(self, _symbol: str, max_age_s: float | None = None) -> tuple[float, float] | None:
        return self._bbo

    def get_mid_age_s(self, _symbol: str) -> float | None:
        return self._mid_age_s

    def get_ws_disconnect_age_s(self) -> float | None:
        return self._disconnect_age_s


def test_estimate_margin_used_uses_fresh_mid_without_fallback(monkeypatch: pytest.MonkeyPatch):
    fake_ws = _FakeWs(mid=125.0, bbo=None, mid_age_s=1.0, disconnect_age_s=None)
    monkeypatch.setattr(live_trader.hyperliquid_ws, "hl_ws", fake_ws)

    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    pos = {"leverage": 5.0, "size": 2.0, "entry_price": 100.0}

    margin = trader._estimate_margin_used("ETH", pos)
    assert margin == pytest.approx(50.0)


def test_estimate_margin_used_warns_and_falls_back_to_entry_price(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    fake_ws = _FakeWs(mid=None, bbo=None, mid_age_s=45.0, disconnect_age_s=6.0)
    monkeypatch.setattr(live_trader.hyperliquid_ws, "hl_ws", fake_ws)

    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    pos = {"leverage": 2.0, "size": 3.0, "entry_price": 100.0}

    with caplog.at_level(logging.WARNING):
        margin = trader._estimate_margin_used("ETH", pos)

    assert margin == pytest.approx(150.0)
    assert any("margin estimate using entry price" in rec.message for rec in caplog.records)
