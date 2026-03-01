"""Tests for regime-gate enforcement (B1 fix).

Verifies that when ``_regime_gate_on`` is False, new OPEN / ADD entries are
blocked while CLOSE / REDUCE exits still execute.
"""

from __future__ import annotations

import types

import pytest

from engine.core import KernelDecision, UnifiedEngine


# ── Fakes (same pattern as test_kernel_decision_routing) ──────────────


class FakeStrategyManager:
    def __init__(self) -> None:
        self.snapshot = types.SimpleNamespace(version="B1-test", overrides_sha1="abc")

    def maybe_reload(self) -> None:
        pass

    def get_watchlist(self) -> list[str]:
        return ["ETH"]

    def get_config(self, scope: str) -> dict:
        if scope == "__GLOBAL__":
            return {"engine": {"heartbeat_every_s": "0", "entry_interval": "1m"}}
        return {}

    def analyze(self, *_a, **_kw) -> None:
        raise AssertionError("should not be called")


class FakeMarket:
    def ensure(self, **_kw) -> None:
        return None

    def ws_health(self, *, symbols=None, interval=None):
        return types.SimpleNamespace(mids_age_s=0, candle_age_s=0, bbo_age_s=0)

    def candles_ready(self, *, symbols, interval):
        return (True, [])

    def get_last_closed_candle_key(self, _sym, *, interval, grace_ms=2000):
        return 1700000000000

    def get_latest_candle_open_key(self, _sym, *, interval):
        return 1700000000000

    def get_candles_df(self, _sym, *, interval, min_rows):
        return None

    def get_mid_price(self, _sym, *, max_age_s=10.0, interval=None):
        return types.SimpleNamespace(price=100.0, source="test", age_s=0.0)

    def health(self, *, symbols, interval):
        return {"connected": True, "thread_alive": True}


class FakeDecisionProvider:
    def __init__(self, decisions: list[KernelDecision]) -> None:
        self.decisions = decisions

    def get_decisions(self, **_kw) -> list[KernelDecision]:
        return list(self.decisions)


class FakeTrader:
    """Records every trade call, keyed by (action, symbol)."""

    def __init__(self, *, with_position: bool = False) -> None:
        self.positions: dict[str, dict] = (
            {"ETH": {"type": "LONG", "size": 1.0}} if with_position else {}
        )
        self.calls: list[tuple[str, str]] = []  # (action, symbol)

    def execute_trade(self, symbol, signal, price, timestamp, confidence, *,
                      atr=0.0, indicators=None, action=None,
                      target_size=None, reason=None) -> None:
        self.calls.append((str(action or ""), str(symbol).upper()))

    def close_position(self, symbol, price, timestamp, reason="", **_kw) -> None:
        self.calls.append(("CLOSE", str(symbol).upper()))

    def reduce_position(self, symbol, size, price, timestamp, reason="", **_kw) -> None:
        self.calls.append(("REDUCE", str(symbol).upper()))

    def check_exit_conditions(self, *_a, **_kw) -> None:
        return None


def _make_engine(trader, decisions, monkeypatch, *, freeze_gate: bool = True):
    """Build a UnifiedEngine that exits after one loop iteration.

    When *freeze_gate* is True, ``_update_regime_gate`` is stubbed out so that
    manually-set ``_regime_gate_on`` values survive the loop.
    """
    monkeypatch.setattr("engine.core.time.sleep", lambda *_: (_ for _ in ()).throw(SystemExit))
    monkeypatch.setattr("strategy.mei_alpha_v1.get_strategy_config", lambda _sym: {})

    engine = UnifiedEngine(
        trader=trader,
        strategy=FakeStrategyManager(),
        market=FakeMarket(),
        interval="1m",
        lookback_bars=50,
        mode="paper",
        mode_plugin=None,
        decision_provider=FakeDecisionProvider(decisions),
    )

    if freeze_gate:
        # Prevent the loop from overwriting our manual gate state.
        monkeypatch.setattr(engine, "_update_regime_gate", lambda **_kw: None)

    return engine


# ── Test cases ────────────────────────────────────────────────────────


def test_gate_on_entries_allowed(monkeypatch):
    """When _regime_gate_on is True, OPEN and ADD decisions execute normally."""
    trader = FakeTrader()
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "OPEN", "signal": "BUY",
             "confidence": "high", "score": 10}
        ),
    ]
    engine = _make_engine(trader, decisions, monkeypatch)
    engine._regime_gate_on = True
    engine._regime_gate_reason = "trend_ok"

    with pytest.raises(SystemExit):
        engine.run_forever()

    actions = [c[0] for c in trader.calls]
    assert "OPEN" in actions, f"OPEN should execute when gate is ON; got {actions}"


def test_gate_off_blocks_open_and_add(monkeypatch):
    """When _regime_gate_on is False, OPEN and ADD are blocked."""
    trader = FakeTrader()
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "OPEN", "signal": "BUY",
             "confidence": "high", "score": 10}
        ),
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "ADD", "signal": "BUY",
             "confidence": "high", "score": 5}
        ),
    ]
    engine = _make_engine(trader, decisions, monkeypatch)
    engine._regime_gate_on = False
    engine._regime_gate_reason = "breadth_chop"

    with pytest.raises(SystemExit):
        engine.run_forever()

    actions = [c[0] for c in trader.calls]
    assert "OPEN" not in actions, f"OPEN must be blocked when gate is OFF; got {actions}"
    assert "ADD" not in actions, f"ADD must be blocked when gate is OFF; got {actions}"


def test_gate_off_exits_still_work(monkeypatch):
    """CLOSE and REDUCE must execute even when gate is OFF."""
    trader = FakeTrader(with_position=True)
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "CLOSE", "signal": "SELL",
             "confidence": "high", "score": 10}
        ),
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "REDUCE", "signal": "SELL",
             "confidence": "high", "score": 5, "target_size": 0.5}
        ),
    ]
    engine = _make_engine(trader, decisions, monkeypatch)
    engine._regime_gate_on = False
    engine._regime_gate_reason = "btc_adx_low"

    with pytest.raises(SystemExit):
        engine.run_forever()

    actions = [c[0] for c in trader.calls]
    assert "CLOSE" in actions, f"CLOSE must NOT be blocked by gate; got {actions}"
    assert "REDUCE" in actions, f"REDUCE must NOT be blocked by gate; got {actions}"


def test_gate_disabled_entries_allowed(monkeypatch):
    """When enable_regime_gate is False, _regime_gate_on defaults to True,
    so entries proceed normally."""
    trader = FakeTrader()
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "OPEN", "signal": "BUY",
             "confidence": "high", "score": 10}
        ),
    ]
    engine = _make_engine(trader, decisions, monkeypatch)
    # Simulate disabled gate — _update_regime_gate sets this to True when
    # enable_regime_gate is False.
    engine._regime_gate_on = True
    engine._regime_gate_reason = "disabled"

    with pytest.raises(SystemExit):
        engine.run_forever()

    actions = [c[0] for c in trader.calls]
    assert "OPEN" in actions, f"OPEN should pass when gate is disabled; got {actions}"


def test_fail_open_allows_entries_when_data_missing(monkeypatch):
    """When regime_gate_fail_open is True and data is missing,
    _update_regime_gate sets _regime_gate_on to True — entries proceed."""
    import strategy.mei_alpha_v1 as mei

    trader = FakeTrader()
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "OPEN", "signal": "BUY",
             "confidence": "high", "score": 10}
        ),
    ]
    # Don't freeze the gate — we're testing _update_regime_gate itself.
    engine = _make_engine(trader, decisions, monkeypatch, freeze_gate=False)

    # Invoke _update_regime_gate with fail_open=True + missing breadth.
    monkeypatch.setattr(
        "strategy.mei_alpha_v1.get_strategy_config",
        lambda _sym: {
            "market_regime": {
                "enable_regime_gate": True,
                "regime_gate_fail_open": True,
            },
        },
    )
    engine._market_breadth_pct = None  # breadth missing

    engine._update_regime_gate(
        mei_alpha_v1=mei,
        btc_key_hint=99999,
        btc_df=None,
    )

    assert engine._regime_gate_on is True, (
        f"Gate should be ON with fail_open=True and missing data; "
        f"got gate_on={engine._regime_gate_on} reason={engine._regime_gate_reason}"
    )


def test_fail_open_false_blocks_entries_when_data_missing(monkeypatch):
    """When regime_gate_fail_open is False and data is missing,
    _update_regime_gate sets _regime_gate_on to False — entries blocked."""
    import strategy.mei_alpha_v1 as mei

    trader = FakeTrader()
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "OPEN", "signal": "BUY",
             "confidence": "high", "score": 10}
        ),
    ]
    # Don't freeze the gate — we test _update_regime_gate then run the loop
    # with the gate frozen.
    engine = _make_engine(trader, decisions, monkeypatch, freeze_gate=False)

    monkeypatch.setattr(
        "strategy.mei_alpha_v1.get_strategy_config",
        lambda _sym: {
            "market_regime": {
                "enable_regime_gate": True,
                "regime_gate_fail_open": False,
            },
        },
    )
    engine._market_breadth_pct = None  # breadth missing

    engine._update_regime_gate(
        mei_alpha_v1=mei,
        btc_key_hint=88888,
        btc_df=None,
    )

    assert engine._regime_gate_on is False, (
        f"Gate should be OFF with fail_open=False and missing data; "
        f"got gate_on={engine._regime_gate_on} reason={engine._regime_gate_reason}"
    )

    # Freeze the gate for the loop run so it stays OFF.
    monkeypatch.setattr(engine, "_update_regime_gate", lambda **_kw: None)

    # Now run the engine loop — OPEN should be blocked.
    with pytest.raises(SystemExit):
        engine.run_forever()

    actions = [c[0] for c in trader.calls]
    assert "OPEN" not in actions, f"OPEN must be blocked; got {actions}"
