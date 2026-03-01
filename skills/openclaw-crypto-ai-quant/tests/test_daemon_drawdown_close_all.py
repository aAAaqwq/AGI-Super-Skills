from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest

from engine import daemon


class _FakeWs:
    def __init__(
        self,
        *,
        fresh_mid: float | None,
        stale_mid: float | None = None,
        mid_age_s: float | None = None,
        disconnect_age_s: float | None = None,
    ):
        self.fresh_mid = fresh_mid
        self.stale_mid = stale_mid
        self.mid_age_s = mid_age_s
        self.disconnect_age_s = disconnect_age_s
        self.calls: list[tuple[str, float | None]] = []

    def get_mid(self, symbol: str, max_age_s: float | None = None) -> float | None:
        self.calls.append((symbol, max_age_s))
        if max_age_s is None:
            if self.stale_mid is not None:
                return self.stale_mid
            return self.fresh_mid
        return self.fresh_mid

    def get_mid_age_s(self, _symbol: str) -> float | None:
        return self.mid_age_s

    def get_ws_disconnect_age_s(self) -> float | None:
        return self.disconnect_age_s


class _FakeTrader:
    def __init__(self):
        self.positions = {"ETH": {"size": 1.0}}
        self.close_calls: list[tuple[str, float, float, str]] = []

    def close_position(self, symbol: str, price: float, ts_s: float, *, reason: str, meta: dict) -> None:
        self.close_calls.append((symbol, price, ts_s, reason))


def _build_plugin(
    *,
    ws_fresh_mid: float | None,
    ws_stale_mid: float | None = None,
    ws_mid_age_s: float | None = None,
    ws_disconnect_age_s: float | None = None,
) -> tuple[daemon.LivePlugin, _FakeTrader, _FakeWs]:
    plugin = daemon.LivePlugin.__new__(daemon.LivePlugin)
    plugin._risk = SimpleNamespace(
        kill_mode="close_only",
        kill_reason="drawdown breach",
        drawdown_reduce_policy="close_all",
        kill_since_s=1234.0,
    )
    plugin._last_drawdown_reduce_kill_since_s = None
    trader = _FakeTrader()
    ws = _FakeWs(
        fresh_mid=ws_fresh_mid,
        stale_mid=ws_stale_mid,
        mid_age_s=ws_mid_age_s,
        disconnect_age_s=ws_disconnect_age_s,
    )
    plugin.trader = trader
    plugin._ws = ws
    return plugin, trader, ws


def test_drawdown_close_all_uses_bounded_mid_age():
    plugin, trader, ws = _build_plugin(ws_fresh_mid=150.0)

    plugin._maybe_reduce_risk_on_drawdown_kill()

    assert ws.calls == [("ETH", 10.0)]
    assert len(trader.close_calls) == 1
    symbol, px, ts_s, reason = trader.close_calls[0]
    assert symbol == "ETH"
    assert px == pytest.approx(150.0)
    assert ts_s <= time.time()
    assert "drawdown kill" in reason


def test_drawdown_close_all_skips_when_mid_stale(
    caplog: pytest.LogCaptureFixture,
):
    plugin, trader, ws = _build_plugin(
        ws_fresh_mid=None,
        ws_stale_mid=150.0,
        ws_mid_age_s=120.0,
        ws_disconnect_age_s=120.0,
    )

    with caplog.at_level(logging.WARNING):
        plugin._maybe_reduce_risk_on_drawdown_kill()

    assert ws.calls == [("ETH", 10.0), ("ETH", None)]
    assert trader.close_calls == []
    assert any("missing/stale WS mid" in rec.message for rec in caplog.records)


def test_drawdown_close_all_uses_recent_stale_mid_fallback():
    plugin, trader, ws = _build_plugin(
        ws_fresh_mid=None,
        ws_stale_mid=147.0,
        ws_mid_age_s=20.0,
        ws_disconnect_age_s=5.0,
    )

    plugin._maybe_reduce_risk_on_drawdown_kill()

    assert ws.calls == [("ETH", 10.0), ("ETH", None)]
    assert len(trader.close_calls) == 1
    _, px, _, _ = trader.close_calls[0]
    assert px == pytest.approx(147.0)
