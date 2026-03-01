from __future__ import annotations

from engine.risk import RiskManager


def test_note_fill_continues_when_daily_loss_refresh_raises() -> None:
    risk = RiskManager()
    called: list[str] = []

    def _fail_daily_loss(**_kwargs) -> None:
        called.append("daily")
        raise RuntimeError("daily_loss_failed")

    def _ok_slippage(**_kwargs) -> None:
        called.append("slippage")

    def _ok_perf(**_kwargs) -> None:
        called.append("perf")

    risk._refresh_daily_loss = _fail_daily_loss  # type: ignore[method-assign]
    risk._refresh_slippage_guard = _ok_slippage  # type: ignore[method-assign]
    risk._refresh_perf_stop = _ok_perf  # type: ignore[method-assign]

    risk.note_fill(ts_ms=1, symbol="BTC", action="OPEN", pnl_usd=0.0, fee_usd=0.0)

    assert called == ["daily", "slippage", "perf"]


def test_note_fill_continues_when_slippage_refresh_raises() -> None:
    risk = RiskManager()
    called: list[str] = []

    def _ok_daily_loss(**_kwargs) -> None:
        called.append("daily")

    def _fail_slippage(**_kwargs) -> None:
        called.append("slippage")
        raise RuntimeError("slippage_failed")

    def _ok_perf(**_kwargs) -> None:
        called.append("perf")

    risk._refresh_daily_loss = _ok_daily_loss  # type: ignore[method-assign]
    risk._refresh_slippage_guard = _fail_slippage  # type: ignore[method-assign]
    risk._refresh_perf_stop = _ok_perf  # type: ignore[method-assign]

    risk.note_fill(ts_ms=1, symbol="BTC", action="OPEN", pnl_usd=0.0, fee_usd=0.0)

    assert called == ["daily", "slippage", "perf"]


def test_note_fill_swallows_perf_stop_refresh_errors() -> None:
    risk = RiskManager()
    called: list[str] = []

    def _ok_daily_loss(**_kwargs) -> None:
        called.append("daily")

    def _ok_slippage(**_kwargs) -> None:
        called.append("slippage")

    def _fail_perf(**_kwargs) -> None:
        called.append("perf")
        raise RuntimeError("perf_stop_failed")

    risk._refresh_daily_loss = _ok_daily_loss  # type: ignore[method-assign]
    risk._refresh_slippage_guard = _ok_slippage  # type: ignore[method-assign]
    risk._refresh_perf_stop = _fail_perf  # type: ignore[method-assign]

    risk.note_fill(ts_ms=1, symbol="BTC", action="OPEN", pnl_usd=0.0, fee_usd=0.0)

    assert called == ["daily", "slippage", "perf"]
