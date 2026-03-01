from __future__ import annotations

import types

from engine.core import UnifiedEngine


class _FakeStrategy:
    def maybe_reload(self) -> None:
        return

    def get_config(self, scope: str) -> dict:
        if scope == "__GLOBAL__":
            return {"engine": {"heartbeat_every_s": 30.0, "entry_interval": "1m"}}
        return {}


class _FakeTrader:
    positions: dict[str, dict] = {}


class _FakeDecisionProvider:
    def get_decisions(self, **_kwargs):
        return []


class _FakeMarket:
    def __init__(self, *, sidecar_only: bool, mids_age_s, candle_age_s=0.0, bbo_age_s=0.0) -> None:
        self._sidecar_only = bool(sidecar_only)
        self._health = types.SimpleNamespace(
            mids_age_s=mids_age_s,
            candle_age_s=candle_age_s,
            bbo_age_s=bbo_age_s,
        )

    def ws_health(self, *, symbols=None, interval=None):  # noqa: ANN001
        return self._health


def _make_engine(market: _FakeMarket) -> UnifiedEngine:
    return UnifiedEngine(
        trader=_FakeTrader(),
        strategy=_FakeStrategy(),
        market=market,
        interval="1m",
        lookback_bars=50,
        mode="paper",
        mode_plugin=None,
        decision_provider=_FakeDecisionProvider(),
    )


def test_ws_is_stale_when_mids_age_missing_in_non_sidecar_mode() -> None:
    engine = _make_engine(_FakeMarket(sidecar_only=False, mids_age_s=None))
    stale, reason = engine._ws_is_stale(symbols=["BTC"])  # noqa: SLF001
    assert stale is True
    assert reason == "mids_age_s is None"


def test_ws_is_not_stale_when_mids_age_missing_in_sidecar_only_mode() -> None:
    engine = _make_engine(_FakeMarket(sidecar_only=True, mids_age_s=None))
    stale, reason = engine._ws_is_stale(symbols=["BTC"])  # noqa: SLF001
    assert stale is False
    assert reason == "ok"
