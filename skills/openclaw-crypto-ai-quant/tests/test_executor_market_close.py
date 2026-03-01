from __future__ import annotations

import logging

import pytest

from exchange.executor import HyperliquidLiveExecutor


class _FakeExchange:
    def __init__(self, *, slippage_result=None, slippage_exc: Exception | None = None):
        self._slippage_result = slippage_result
        self._slippage_exc = slippage_exc
        self.order_calls: list[tuple[str, dict]] = []

    def _slippage_price(self, *_args, **_kwargs):
        if self._slippage_exc is not None:
            raise self._slippage_exc
        return self._slippage_result

    def order(self, symbol: str, **kwargs):
        # Mirror SDK float_to_wire precision behaviour.
        limit_px = float(kwargs.get("limit_px"))
        rounded = float(f"{limit_px:.8f}")
        if abs(rounded - limit_px) >= 1e-12:
            raise ValueError("float_to_wire causes rounding")
        self.order_calls.append((symbol, kwargs))
        return {"status": "ok", "response": {"data": {"statuses": [{"filled": {}}]}}}


class _FakeInfo:
    def __init__(self, mids: dict[str, str] | None = None):
        self._mids = mids or {}

    def all_mids(self):
        return dict(self._mids)


def _build_executor(
    fake_exchange: _FakeExchange,
    *,
    info: _FakeInfo | None = None,
) -> HyperliquidLiveExecutor:
    ex = HyperliquidLiveExecutor.__new__(HyperliquidLiveExecutor)
    ex._exchange = fake_exchange
    ex._info = info
    ex.last_order_error = None
    return ex


def test_market_close_falls_back_to_local_slippage_when_sdk_method_raises(caplog: pytest.LogCaptureFixture):
    fake = _FakeExchange(slippage_exc=RuntimeError("no private helper"))
    ex = _build_executor(fake)

    with caplog.at_level(logging.WARNING):
        res = ex.market_close("ETH", is_buy=True, sz=1.0, px=100.0, slippage_pct=0.01)

    assert res is not None
    assert len(fake.order_calls) == 1
    _, kwargs = fake.order_calls[0]
    assert kwargs["limit_px"] == pytest.approx(101.0)
    assert any("local slippage fallback" in rec.message for rec in caplog.records)


def test_market_close_falls_back_to_local_slippage_when_sdk_returns_none():
    fake = _FakeExchange(slippage_result=None)
    ex = _build_executor(fake)

    res = ex.market_close("ETH", is_buy=False, sz=1.0, px=100.0, slippage_pct=0.01)

    assert res is not None
    assert len(fake.order_calls) == 1
    _, kwargs = fake.order_calls[0]
    assert kwargs["limit_px"] == pytest.approx(99.0)


def test_market_close_blocks_when_no_price_for_local_fallback():
    fake = _FakeExchange(slippage_result=None)
    ex = _build_executor(fake)

    res = ex.market_close("ETH", is_buy=True, sz=1.0, px=None, slippage_pct=0.01)

    assert res is None
    assert fake.order_calls == []
    assert ex.last_order_error is not None
    assert ex.last_order_error.get("kind") == "preflight"


def test_market_close_uses_all_mids_when_sdk_returns_none_and_px_missing(
    caplog: pytest.LogCaptureFixture,
):
    fake = _FakeExchange(slippage_result=None)
    ex = _build_executor(fake, info=_FakeInfo({"ETH": "200.0"}))

    with caplog.at_level(logging.WARNING):
        res = ex.market_close("ETH", is_buy=True, sz=1.0, px=None, slippage_pct=0.01)

    assert res is not None
    assert len(fake.order_calls) == 1
    _, kwargs = fake.order_calls[0]
    assert kwargs["limit_px"] == pytest.approx(202.0)
    assert any("_slippage_price returned None" in rec.message for rec in caplog.records)
    assert any("all_mids reference px" in rec.message for rec in caplog.records)


def test_market_close_local_fallback_normalises_limit_px_to_wire_precision():
    fake = _FakeExchange(slippage_result=None)
    ex = _build_executor(fake)

    res = ex.market_close("ETH", is_buy=True, sz=1.0, px=0.00012345, slippage_pct=0.01)

    assert res is not None
    assert len(fake.order_calls) == 1
    _, kwargs = fake.order_calls[0]
    assert kwargs["limit_px"] == pytest.approx(0.00012469)


def test_market_open_preflight_invalid_size_logs_warning(caplog: pytest.LogCaptureFixture):
    fake = _FakeExchange(slippage_result=100.0)
    ex = _build_executor(fake)

    with caplog.at_level(logging.WARNING):
        res = ex.market_open("ETH", is_buy=True, sz=0.0, px=100.0, slippage_pct=0.01)

    assert res is None
    assert any("market_open blocked: invalid sz" in rec.message for rec in caplog.records)
