"""Tests for AQC-815: Broker adapter translating kernel OrderIntent to Hyperliquid orders.

Covers:
- intent_type() — intent classification (open, add, close, partial_close)
- intent_to_hl_side() — side mapping (Long/Short to is_buy)
- apply_slippage() — slippage application for buy/sell
- round_size() — szDecimals truncation
- build_fill_event() — FillEvent schema compliance
- BrokerAdapter.execute_intent() — routed order execution with mock exchange
- BrokerAdapter.execute_intents() — batch execution with rate limiting
"""

from __future__ import annotations

import json
import logging
import time
from unittest.mock import MagicMock

import pytest

from strategy.broker_adapter import (
    BrokerAdapter,
    BrokerAdapterError,
    KERNEL_SCHEMA_VERSION,
    apply_slippage,
    build_fill_event,
    intent_to_hl_side,
    intent_type,
    round_size,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_intent(
    *,
    kind: str = "open",
    symbol: str = "ETH",
    side: str = "long",
    quantity: float = 1.5,
    price: float = 3000.0,
    notional_usd: float = 4500.0,
    fee_rate: float = 0.00035,
    intent_id: int = 1001,
    schema_version: int = KERNEL_SCHEMA_VERSION,
    close_fraction: float | None = None,
) -> dict:
    """Build an OrderIntent dict matching the kernel schema."""
    d = {
        "schema_version": schema_version,
        "intent_id": intent_id,
        "symbol": symbol,
        "kind": kind,
        "side": side,
        "quantity": quantity,
        "price": price,
        "notional_usd": notional_usd,
        "fee_rate": fee_rate,
    }
    if close_fraction is not None:
        d["close_fraction"] = close_fraction
    return d


def _make_exchange_response(
    *,
    avg_px: float = 3000.0,
    total_sz: float = 1.5,
    status: str = "ok",
) -> dict:
    """Build a mock Hyperliquid exchange response."""
    return {
        "status": status,
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {"filled": {"totalSz": str(total_sz), "avgPx": str(avg_px)}}
                ]
            },
        },
    }


def _make_mock_client(
    *,
    open_response: dict | None = None,
    close_response: dict | None = None,
) -> MagicMock:
    """Create a mock exchange client with configurable responses."""
    client = MagicMock()
    if open_response is None:
        open_response = _make_exchange_response()
    if close_response is None:
        close_response = _make_exchange_response()
    client.market_open.return_value = open_response
    client.market_close.return_value = close_response
    return client


# ===========================================================================
# TestIntentClassification
# ===========================================================================


class TestIntentClassification:
    """Test intent_type() classification logic."""

    def test_open_intent(self):
        intent = _make_intent(kind="open")
        assert intent_type(intent) == "open"

    def test_add_intent(self):
        intent = _make_intent(kind="add")
        assert intent_type(intent) == "add"

    def test_close_intent(self):
        intent = _make_intent(kind="close")
        assert intent_type(intent) == "close"

    def test_close_with_full_fraction(self):
        intent = _make_intent(kind="close", close_fraction=1.0)
        assert intent_type(intent) == "close"

    def test_partial_close_intent(self):
        intent = _make_intent(kind="close", close_fraction=0.5)
        assert intent_type(intent) == "partial_close"

    def test_partial_close_small_fraction(self):
        intent = _make_intent(kind="close", close_fraction=0.1)
        assert intent_type(intent) == "partial_close"

    def test_hold_intent(self):
        intent = _make_intent(kind="hold")
        assert intent_type(intent) == "hold"

    def test_reverse_intent(self):
        intent = _make_intent(kind="reverse")
        assert intent_type(intent) == "reverse"

    def test_unknown_kind_raises(self):
        intent = _make_intent(kind="foobar")
        with pytest.raises(ValueError, match="Unknown OrderIntentKind"):
            intent_type(intent)


# ===========================================================================
# TestIntentToHlSide
# ===========================================================================


class TestIntentToHlSide:
    """Test intent_to_hl_side() mapping."""

    def test_long_is_buy(self):
        assert intent_to_hl_side("long") is True

    def test_short_is_sell(self):
        assert intent_to_hl_side("short") is False

    def test_long_case_insensitive(self):
        assert intent_to_hl_side("Long") is True
        assert intent_to_hl_side("LONG") is True

    def test_short_case_insensitive(self):
        assert intent_to_hl_side("Short") is False
        assert intent_to_hl_side("SHORT") is False

    def test_unknown_side_raises(self):
        with pytest.raises(ValueError, match="Unknown PositionSide"):
            intent_to_hl_side("sideways")


# ===========================================================================
# TestSlippage
# ===========================================================================


class TestSlippage:
    """Test apply_slippage() price adjustment."""

    def test_buy_slippage_increases_price(self):
        result = apply_slippage(100.0, is_buy=True, slippage_pct=0.001)
        assert result == pytest.approx(100.1)

    def test_sell_slippage_decreases_price(self):
        result = apply_slippage(100.0, is_buy=False, slippage_pct=0.001)
        assert result == pytest.approx(99.9)

    def test_custom_slippage_percentage(self):
        result = apply_slippage(1000.0, is_buy=True, slippage_pct=0.01)
        assert result == pytest.approx(1010.0)

    def test_zero_slippage(self):
        result = apply_slippage(500.0, is_buy=True, slippage_pct=0.0)
        assert result == pytest.approx(500.0)

        result = apply_slippage(500.0, is_buy=False, slippage_pct=0.0)
        assert result == pytest.approx(500.0)

    def test_negative_slippage_treated_as_zero(self):
        result = apply_slippage(100.0, is_buy=True, slippage_pct=-0.01)
        assert result == pytest.approx(100.0)

    def test_large_slippage(self):
        result = apply_slippage(100.0, is_buy=True, slippage_pct=0.05)
        assert result == pytest.approx(105.0)

        result = apply_slippage(100.0, is_buy=False, slippage_pct=0.05)
        assert result == pytest.approx(95.0)


# ===========================================================================
# TestSizeRounding
# ===========================================================================


class TestSizeRounding:
    """Test round_size() truncation to szDecimals."""

    def test_round_to_two_decimals(self):
        assert round_size(1.567, 2) == pytest.approx(1.56)

    def test_round_to_zero_decimals(self):
        assert round_size(123.999, 0) == pytest.approx(123.0)
        assert round_size(0.9999999999995, 0) == pytest.approx(0.0)

    def test_round_to_four_decimals(self):
        assert round_size(0.12345678, 4) == pytest.approx(0.1234)

    def test_large_quantity_rounding(self):
        assert round_size(99999.99999, 2) == pytest.approx(99999.99)

    def test_zero_quantity(self):
        assert round_size(0.0, 2) == 0.0

    def test_negative_quantity(self):
        assert round_size(-1.5, 2) == 0.0

    def test_exact_decimals_unchanged(self):
        assert round_size(1.50, 2) == pytest.approx(1.50)

    def test_truncates_not_rounds_up(self):
        # 1.999 with 2 decimals should truncate to 1.99, NOT round to 2.00
        assert round_size(1.999, 2) == pytest.approx(1.99)

    def test_binary_float_edge_keeps_expected_precision(self):
        # 0.29 * 100 can become 28.999..., so flooring without epsilon would yield 0.28.
        assert round_size(0.29, 2) == pytest.approx(0.29)
        assert round_size(256.03, 2) == pytest.approx(256.03)
        assert round_size(2.0018, 4) == pytest.approx(2.0018)


# ===========================================================================
# TestBuildFillEvent
# ===========================================================================


class TestBuildFillEvent:
    """Test build_fill_event() schema compliance."""

    def test_all_fields_present(self):
        intent = _make_intent()
        fill = build_fill_event(
            intent=intent, fill_price=3005.0, fill_quantity=1.5, fee_usd=1.575,
        )
        expected_fields = {
            "schema_version", "intent_id", "symbol", "side",
            "quantity", "price", "notional_usd", "fee_usd", "pnl_usd",
        }
        assert set(fill.keys()) == expected_fields

    def test_correct_schema_version(self):
        intent = _make_intent(schema_version=1)
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        assert fill["schema_version"] == 1

    def test_side_mapping_preserved(self):
        intent = _make_intent(side="long")
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        assert fill["side"] == "long"

        intent = _make_intent(side="short")
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        assert fill["side"] == "short"

    def test_fee_included(self):
        intent = _make_intent()
        fill = build_fill_event(
            intent=intent, fill_price=3000.0, fill_quantity=1.0, fee_usd=1.05,
        )
        assert fill["fee_usd"] == pytest.approx(1.05)

    def test_notional_computed(self):
        intent = _make_intent()
        fill = build_fill_event(
            intent=intent, fill_price=2000.0, fill_quantity=5.0,
        )
        assert fill["notional_usd"] == pytest.approx(10000.0)

    def test_pnl_default_zero(self):
        intent = _make_intent()
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        assert fill["pnl_usd"] == pytest.approx(0.0)

    def test_pnl_explicit(self):
        intent = _make_intent()
        fill = build_fill_event(
            intent=intent, fill_price=100.0, fill_quantity=1.0, pnl_usd=50.5,
        )
        assert fill["pnl_usd"] == pytest.approx(50.5)

    def test_intent_id_propagated(self):
        intent = _make_intent(intent_id=42)
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        assert fill["intent_id"] == 42

    def test_symbol_uppercased(self):
        intent = _make_intent(symbol="eth")
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        assert fill["symbol"] == "ETH"


# ===========================================================================
# TestBuildFillEventJson
# ===========================================================================


class TestBuildFillEventJson:
    """Test build_fill_event_json() serialization."""

    def test_valid_json(self):
        intent = _make_intent()
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        json_str = BrokerAdapter.build_fill_event_json(fill)
        parsed = json.loads(json_str)
        assert parsed["symbol"] == "ETH"

    def test_deterministic_output(self):
        intent = _make_intent()
        fill = build_fill_event(intent=intent, fill_price=100.0, fill_quantity=1.0)
        j1 = BrokerAdapter.build_fill_event_json(fill)
        j2 = BrokerAdapter.build_fill_event_json(fill)
        assert j1 == j2


# ===========================================================================
# TestExecuteIntent (with mock exchange)
# ===========================================================================


class TestExecuteIntent:
    """Test BrokerAdapter.execute_intent() with mocked exchange client."""

    def test_open_order(self):
        client = _make_mock_client(
            open_response=_make_exchange_response(avg_px=3005.0, total_sz=1.5),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="open", side="long", quantity=1.5, price=3000.0)

        fill = adapter.execute_intent(intent)

        client.market_open.assert_called_once()
        assert fill["symbol"] == "ETH"
        assert fill["price"] == pytest.approx(3005.0)
        assert fill["quantity"] == pytest.approx(1.5)
        assert fill["side"] == "long"

    def test_close_order(self):
        client = _make_mock_client(
            close_response=_make_exchange_response(avg_px=3100.0, total_sz=2.0),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="close", side="long", quantity=2.0, price=3100.0)

        fill = adapter.execute_intent(intent)

        client.market_close.assert_called_once()
        # Close of a Long position -> is_buy=False (sell to close)
        _, kwargs = client.market_close.call_args
        assert kwargs["is_buy"] is False
        assert fill["quantity"] == pytest.approx(2.0)

    def test_close_short_order(self):
        client = _make_mock_client(
            close_response=_make_exchange_response(avg_px=2900.0, total_sz=1.0),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="close", side="short", quantity=1.0, price=2900.0)

        adapter.execute_intent(intent)

        _, kwargs = client.market_close.call_args
        # Close of a Short position -> is_buy=True (buy to close)
        assert kwargs["is_buy"] is True

    def test_partial_close_order(self):
        client = _make_mock_client(
            close_response=_make_exchange_response(avg_px=3050.0, total_sz=0.75),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(
            kind="close", side="long", quantity=0.75, price=3050.0, close_fraction=0.5,
        )

        fill = adapter.execute_intent(intent)

        client.market_close.assert_called_once()
        assert fill["quantity"] == pytest.approx(0.75)

    def test_add_order(self):
        client = _make_mock_client(
            open_response=_make_exchange_response(avg_px=3010.0, total_sz=0.5),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="add", side="long", quantity=0.5, price=3000.0)

        fill = adapter.execute_intent(intent)

        # Add uses market_open internally
        client.market_open.assert_called_once()
        assert fill["quantity"] == pytest.approx(0.5)

    def test_exchange_rejection_raises(self):
        client = _make_mock_client()
        client.market_open.return_value = None  # rejection
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0, "max_retries": 0})
        intent = _make_intent(kind="open")

        with pytest.raises(BrokerAdapterError, match="rejected"):
            adapter.execute_intent(intent)

    def test_exchange_exception_retried(self):
        client = _make_mock_client()
        # First call raises, second succeeds
        client.market_open.side_effect = [
            ConnectionError("timeout"),
            _make_exchange_response(avg_px=3000.0, total_sz=1.5),
        ]
        adapter = BrokerAdapter(
            client,
            config={"rate_limit_delay_s": 0, "max_retries": 1, "retry_backoff_s": 0.0},
        )
        intent = _make_intent(kind="open")

        fill = adapter.execute_intent(intent)

        assert client.market_open.call_count == 2
        assert fill["price"] == pytest.approx(3000.0)

    def test_exchange_exception_exhausts_retries(self):
        client = _make_mock_client()
        client.market_open.side_effect = ConnectionError("persistent failure")
        adapter = BrokerAdapter(
            client,
            config={"rate_limit_delay_s": 0, "max_retries": 1, "retry_backoff_s": 0.0},
        )
        intent = _make_intent(kind="open")

        with pytest.raises(BrokerAdapterError, match="failed after"):
            adapter.execute_intent(intent)

        # 1 initial + 1 retry = 2 calls
        assert client.market_open.call_count == 2

    def test_hold_intent_no_exchange_call(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="hold")

        fill = adapter.execute_intent(intent)

        client.market_open.assert_not_called()
        client.market_close.assert_not_called()
        assert fill["quantity"] == pytest.approx(0.0)

    def test_size_rounding_applied(self):
        client = _make_mock_client(
            open_response=_make_exchange_response(avg_px=3000.0, total_sz=1.12),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="open", quantity=1.12999)

        symbol_info = {"sz_decimals": 2}
        adapter.execute_intent(intent, symbol_info=symbol_info)

        _, kwargs = client.market_open.call_args
        # quantity should be truncated to 2 decimals
        assert kwargs["sz"] == pytest.approx(1.12)

    def test_slippage_applied_to_buy(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(
            client, config={"rate_limit_delay_s": 0, "slippage_pct": 0.01},
        )
        intent = _make_intent(kind="open", side="long", price=1000.0, quantity=1.0)

        adapter.execute_intent(intent)

        _, kwargs = client.market_open.call_args
        # Buy with 1% slippage: px should be 1010.0
        assert kwargs["px"] == pytest.approx(1010.0)

    def test_zero_quantity_raises(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="open", quantity=0.0, notional_usd=0.0, price=0.0)

        with pytest.raises(BrokerAdapterError, match="quantity is zero"):
            adapter.execute_intent(intent)

    def test_fill_event_schema(self):
        """Verify the returned fill event has all kernel-required fields."""
        client = _make_mock_client()
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent()

        fill = adapter.execute_intent(intent)

        required_fields = {
            "schema_version", "intent_id", "symbol", "side",
            "quantity", "price", "notional_usd", "fee_usd", "pnl_usd",
        }
        assert set(fill.keys()) == required_fields

    def test_quantity_from_notional_when_zero(self):
        """When intent quantity is 0 but notional and price are set, compute quantity."""
        client = _make_mock_client(
            open_response=_make_exchange_response(avg_px=100.0, total_sz=10.0),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})
        intent = _make_intent(kind="open", quantity=0.0, notional_usd=1000.0, price=100.0)

        adapter.execute_intent(intent)

        # 1000 / 100 = 10.0
        _, kwargs = client.market_open.call_args
        assert kwargs["sz"] == pytest.approx(10.0)

    def test_open_rejects_oversized_quantity(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(
            client,
            config={"rate_limit_delay_s": 0, "max_quantity": 1.0, "max_notional_usd": 1_000_000.0},
        )
        intent = _make_intent(kind="open", quantity=1.5, price=3000.0, notional_usd=4500.0)

        with pytest.raises(BrokerAdapterError, match="exceeds max_quantity"):
            adapter.execute_intent(intent)

        client.market_open.assert_not_called()

    def test_open_rejects_oversized_notional(self, caplog: pytest.LogCaptureFixture):
        client = _make_mock_client()
        adapter = BrokerAdapter(
            client,
            config={"rate_limit_delay_s": 0, "max_notional_usd": 500.0, "max_quantity": 1000.0},
        )
        intent = _make_intent(kind="open", quantity=0.0, notional_usd=1000.0, price=100.0)

        with caplog.at_level(logging.ERROR):
            with pytest.raises(BrokerAdapterError, match="exceeds max_notional_usd"):
                adapter.execute_intent(intent)

        client.market_open.assert_not_called()
        assert any("max_notional_usd" in rec.message for rec in caplog.records)


# ===========================================================================
# TestExecuteIntents (batch)
# ===========================================================================


class TestExecuteIntents:
    """Test BrokerAdapter.execute_intents() batch processing."""

    def test_empty_intents_returns_empty(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})

        fills = adapter.execute_intents([])

        assert fills == []
        client.market_open.assert_not_called()

    def test_multiple_intents_processed_in_order(self):
        responses = [
            _make_exchange_response(avg_px=3000.0, total_sz=1.0),
            _make_exchange_response(avg_px=3100.0, total_sz=0.5),
        ]
        client = _make_mock_client()
        client.market_open.side_effect = responses
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})

        intents = [
            _make_intent(kind="open", intent_id=1, quantity=1.0, price=3000.0),
            _make_intent(kind="add", intent_id=2, quantity=0.5, price=3100.0),
        ]

        fills = adapter.execute_intents(intents)

        assert len(fills) == 2
        assert fills[0]["intent_id"] == 1
        assert fills[0]["price"] == pytest.approx(3000.0)
        assert fills[1]["intent_id"] == 2
        assert fills[1]["price"] == pytest.approx(3100.0)

    def test_failure_aborts_batch_by_default(self):
        client = _make_mock_client()
        client.market_open.side_effect = [
            _make_exchange_response(avg_px=3000.0, total_sz=1.0),
            None,  # rejection
        ]
        adapter = BrokerAdapter(
            client,
            config={"rate_limit_delay_s": 0, "max_retries": 0, "abort_batch_on_error": True},
        )

        intents = [
            _make_intent(kind="open", intent_id=1),
            _make_intent(kind="open", intent_id=2),
        ]

        with pytest.raises(BrokerAdapterError):
            adapter.execute_intents(intents)

    def test_failure_continues_when_configured(self):
        client = _make_mock_client()
        client.market_open.side_effect = [
            None,  # rejection (intent 1)
            _make_exchange_response(avg_px=3100.0, total_sz=1.0),  # success (intent 2)
        ]
        adapter = BrokerAdapter(
            client,
            config={"rate_limit_delay_s": 0, "max_retries": 0, "abort_batch_on_error": False},
        )

        intents = [
            _make_intent(kind="open", intent_id=1),
            _make_intent(kind="open", intent_id=2),
        ]

        fills = adapter.execute_intents(intents)

        # Only the second intent succeeded
        assert len(fills) == 1
        assert fills[0]["intent_id"] == 2

    def test_rate_limiting_enforced(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(
            client, config={"rate_limit_delay_s": 0.05},
        )

        intents = [
            _make_intent(kind="open", intent_id=1),
            _make_intent(kind="open", intent_id=2),
        ]

        start = time.monotonic()
        fills = adapter.execute_intents(intents)
        elapsed = time.monotonic() - start

        assert len(fills) == 2
        # Should have waited at least ~0.05s between orders
        # (use generous lower bound to avoid flakiness)
        assert elapsed >= 0.03

    def test_mixed_open_and_close_intents(self):
        client = _make_mock_client(
            open_response=_make_exchange_response(avg_px=3000.0, total_sz=1.0),
            close_response=_make_exchange_response(avg_px=3200.0, total_sz=1.0),
        )
        adapter = BrokerAdapter(client, config={"rate_limit_delay_s": 0})

        intents = [
            _make_intent(kind="open", intent_id=1, side="long"),
            _make_intent(kind="close", intent_id=2, side="long"),
        ]

        fills = adapter.execute_intents(intents)

        assert len(fills) == 2
        client.market_open.assert_called_once()
        client.market_close.assert_called_once()


# ===========================================================================
# TestFillExtraction
# ===========================================================================


class TestFillExtraction:
    """Test _extract_fill_price and _extract_fill_quantity from exchange responses."""

    def test_extract_price_from_response(self):
        res = _make_exchange_response(avg_px=3005.5, total_sz=1.0)
        price = BrokerAdapter._extract_fill_price(res, fallback=3000.0)
        assert price == pytest.approx(3005.5)

    def test_extract_price_fallback_on_none(self):
        price = BrokerAdapter._extract_fill_price(None, fallback=3000.0)
        assert price == pytest.approx(3000.0)

    def test_extract_price_fallback_on_missing_data(self):
        res = {"status": "ok", "response": {}}
        price = BrokerAdapter._extract_fill_price(res, fallback=2500.0)
        assert price == pytest.approx(2500.0)

    def test_extract_quantity_from_response(self):
        res = _make_exchange_response(avg_px=3000.0, total_sz=2.5)
        qty = BrokerAdapter._extract_fill_quantity(res, fallback=1.0)
        assert qty == pytest.approx(2.5)

    def test_extract_quantity_fallback(self):
        qty = BrokerAdapter._extract_fill_quantity(None, fallback=1.0)
        assert qty == pytest.approx(1.0)


# ===========================================================================
# TestFeeEstimation
# ===========================================================================


class TestFeeEstimation:
    """Test _estimate_fee computation."""

    def test_fee_from_rate(self):
        intent = _make_intent(fee_rate=0.00035)
        fee = BrokerAdapter._estimate_fee(3000.0, 1.0, intent)
        # 3000 * 1 * 0.00035 = 1.05
        assert fee == pytest.approx(1.05)

    def test_zero_fee_rate(self):
        intent = _make_intent(fee_rate=0.0)
        fee = BrokerAdapter._estimate_fee(3000.0, 1.0, intent)
        assert fee == pytest.approx(0.0)

    def test_no_fee_rate_key(self):
        intent = {"kind": "open", "symbol": "ETH"}
        fee = BrokerAdapter._estimate_fee(3000.0, 1.0, intent)
        assert fee == pytest.approx(0.0)


# ===========================================================================
# TestAdapterConfig
# ===========================================================================


class TestAdapterConfig:
    """Test BrokerAdapter configuration handling."""

    def test_default_config(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(client)
        assert adapter._slippage_pct == pytest.approx(0.001)
        assert adapter._rate_limit_delay_s == pytest.approx(0.25)
        assert adapter._max_retries == 2

    def test_custom_config(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(client, config={
            "slippage_pct": 0.005,
            "rate_limit_delay_s": 0.1,
            "max_retries": 3,
            "retry_backoff_s": 1.0,
            "abort_batch_on_error": False,
        })
        assert adapter._slippage_pct == pytest.approx(0.005)
        assert adapter._rate_limit_delay_s == pytest.approx(0.1)
        assert adapter._max_retries == 3
        assert adapter._retry_backoff_s == pytest.approx(1.0)
        assert adapter._abort_batch_on_error is False

    def test_none_config_uses_defaults(self):
        client = _make_mock_client()
        adapter = BrokerAdapter(client, config=None)
        assert adapter._slippage_pct == pytest.approx(0.001)
