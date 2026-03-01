from __future__ import annotations

import engine.market_data as market_data_mod
import exchange.ws as ws_mod


class _DummyWS:
    def __init__(self) -> None:
        self.calls = 0

    def get_mid(self, _symbol: str, max_age_s: float | None = None):  # noqa: ARG002
        self.calls += 1
        return 123.45


def test_hl_ws_is_lazy_singleton(monkeypatch) -> None:
    calls = {"n": 0}
    dummy = _DummyWS()

    def _fake_make_default_ws():
        calls["n"] += 1
        return dummy

    monkeypatch.setattr(ws_mod, "_default_ws_singleton", None)
    monkeypatch.setattr(ws_mod, "_make_default_ws", _fake_make_default_ws)

    assert calls["n"] == 0
    assert ws_mod.hl_ws.get_mid("ETH", max_age_s=1.0) == 123.45
    assert calls["n"] == 1
    assert ws_mod.hl_ws.get_mid("BTC", max_age_s=1.0) == 123.45
    assert calls["n"] == 1
    assert dummy.calls == 2


class _RestartableWS:
    def __init__(self, label: str) -> None:
        self.label = label
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


def test_market_data_restart_ws_replaces_lazy_singleton(monkeypatch) -> None:
    old_ws = _RestartableWS("old")
    new_ws = _RestartableWS("new")

    monkeypatch.setattr(ws_mod, "_default_ws_singleton", old_ws)
    monkeypatch.setattr(ws_mod, "HyperliquidWS", lambda: new_ws)

    hub = market_data_mod.MarketDataHub.__new__(market_data_mod.MarketDataHub)
    hub._ws_mod = ws_mod
    hub._ws = ws_mod.hl_ws
    hub.ensure = lambda **_kwargs: None

    market_data_mod.MarketDataHub.restart_ws(hub, symbols=["ETH"], interval="1m", candle_limit=200, user=None)

    assert old_ws.stop_calls == 1
    assert ws_mod._get_default_ws_singleton() is new_ws
    assert hub._ws is new_ws
