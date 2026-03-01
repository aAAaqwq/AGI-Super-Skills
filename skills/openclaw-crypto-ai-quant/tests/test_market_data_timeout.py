from __future__ import annotations

import sys
import types

from engine.market_data import MarketDataHub


def _install_fake_ws_module(monkeypatch) -> None:
    fake_ws_mod = types.ModuleType("exchange.ws")
    fake_ws_mod.hl_ws = object()
    monkeypatch.setitem(sys.modules, "exchange.ws", fake_ws_mod)


def test_market_data_logs_warning_when_db_timeout_is_clamped(tmp_path, monkeypatch, caplog) -> None:
    _install_fake_ws_module(monkeypatch)

    with caplog.at_level("WARNING"):
        hub = MarketDataHub(db_path=str(tmp_path / "market.db"), db_timeout_s=30.0)

    assert hub._db_timeout_s == 5.0  # noqa: SLF001
    assert any("db_timeout_s clamped" in rec.message for rec in caplog.records)


def test_market_data_does_not_log_warning_when_timeout_within_cap(tmp_path, monkeypatch, caplog) -> None:
    _install_fake_ws_module(monkeypatch)

    with caplog.at_level("WARNING"):
        hub = MarketDataHub(db_path=str(tmp_path / "market.db"), db_timeout_s=2.0)

    assert hub._db_timeout_s == 2.0  # noqa: SLF001
    assert not any("db_timeout_s clamped" in rec.message for rec in caplog.records)
