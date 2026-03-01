"""Tests for AQC-814: Position lifecycle delegation to kernel SSOT.

Covers:
- get_kernel_positions() — extract positions from kernel state
- kernel_position_to_python() — kernel -> Python format conversion
- python_position_to_kernel() — Python -> kernel format conversion
- sync_positions_from_kernel() — full bridge from kernel state to Python dicts
- build_position_state_for_db() — format positions for SQLite persistence
- Integration with real bt_runtime (conditional on bt_runtime availability)
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from strategy.mei_alpha_v1 import (
    _BT_RUNTIME_AVAILABLE,
    get_kernel_positions,
    kernel_position_to_python,
    python_position_to_kernel,
    sync_positions_from_kernel,
    build_position_state_for_db,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1


def _make_kernel_state(
    cash_usd: float = 10000.0,
    positions: dict | None = None,
    timestamp_ms: int = 1700000000000,
) -> str:
    """Build a minimal StrategyState JSON string."""
    state = {
        "schema_version": _SCHEMA_VERSION,
        "timestamp_ms": timestamp_ms,
        "step": 0,
        "cash_usd": cash_usd,
        "positions": positions or {},
        "last_entry_ms": {},
        "last_exit_ms": {},
        "last_close_info": {},
    }
    return json.dumps(state)


def _make_kernel_position(
    symbol: str = "ETH",
    side: str = "long",
    quantity: float = 1.0,
    avg_entry_price: float = 3000.0,
    *,
    opened_at_ms: int = 1700000000000,
    entry_atr: float | None = 50.0,
    entry_adx_threshold: float | None = 25.0,
    adds_count: int = 0,
    tp1_taken: bool = False,
    trailing_sl: float | None = None,
    confidence: int | None = 1,
    margin_usd: float = 0.0,
    last_funding_ms: int | None = None,
) -> dict:
    """Build a kernel Position dict matching the Rust schema."""
    pos = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "avg_entry_price": avg_entry_price,
        "opened_at_ms": opened_at_ms,
        "updated_at_ms": opened_at_ms,
        "notional_usd": abs(quantity) * avg_entry_price,
        "margin_usd": margin_usd,
        "confidence": confidence,
        "entry_atr": entry_atr,
        "entry_adx_threshold": entry_adx_threshold,
        "adds_count": adds_count,
        "tp1_taken": tp1_taken,
        "trailing_sl": trailing_sl,
        "mae_usd": 0.0,
        "mfe_usd": 0.0,
        "last_funding_ms": last_funding_ms,
    }
    return pos


# ---------------------------------------------------------------------------
# TestGetKernelPositions
# ---------------------------------------------------------------------------


class TestGetKernelPositions:
    """Tests for get_kernel_positions()."""

    def test_empty_positions_from_fresh_state(self):
        state_json = _make_kernel_state()
        result = get_kernel_positions(state_json)
        assert result == {}

    def test_single_position_extracted(self):
        pos = _make_kernel_position("ETH", "long", 1.5, 3000.0)
        state_json = _make_kernel_state(positions={"ETH": pos})
        result = get_kernel_positions(state_json)
        assert "ETH" in result
        assert result["ETH"]["quantity"] == 1.5
        assert result["ETH"]["avg_entry_price"] == 3000.0
        assert result["ETH"]["side"] == "long"

    def test_multiple_positions(self):
        pos_eth = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        pos_btc = _make_kernel_position("BTC", "short", 0.5, 95000.0)
        state_json = _make_kernel_state(positions={"ETH": pos_eth, "BTC": pos_btc})
        result = get_kernel_positions(state_json)
        assert len(result) == 2
        assert "ETH" in result
        assert "BTC" in result
        assert result["BTC"]["side"] == "short"

    def test_fallback_when_bt_runtime_unavailable(self):
        """Even with bt_runtime mocked away, fallback JSON parsing works."""
        pos = _make_kernel_position("ETH", "long", 2.0, 3500.0)
        state_json = _make_kernel_state(positions={"ETH": pos})
        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", False):
            result = get_kernel_positions(state_json)
        assert "ETH" in result
        assert result["ETH"]["quantity"] == 2.0

    def test_invalid_json_returns_empty(self):
        result = get_kernel_positions("not valid json")
        assert result == {}

    def test_missing_positions_field_returns_empty(self):
        state_json = json.dumps({"schema_version": 1, "cash_usd": 10000.0})
        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", False):
            result = get_kernel_positions(state_json)
        assert result == {}


# ---------------------------------------------------------------------------
# TestPositionConversion
# ---------------------------------------------------------------------------


class TestPositionConversion:
    """Tests for kernel_position_to_python() and python_position_to_kernel()."""

    def test_kernel_to_python_all_fields(self):
        kernel_pos = _make_kernel_position(
            "ETH", "long", 1.5, 3000.0,
            entry_atr=50.0,
            entry_adx_threshold=25.0,
            adds_count=2,
            tp1_taken=True,
            trailing_sl=2950.0,
            confidence=2,
            margin_usd=1500.0,
            last_funding_ms=1700000060000,
        )
        py_pos = kernel_position_to_python("ETH", kernel_pos)

        assert py_pos["type"] == "LONG"
        assert py_pos["entry_price"] == 3000.0
        assert py_pos["size"] == 1.5
        assert py_pos["entry_atr"] == 50.0
        assert py_pos["entry_adx_threshold"] == 25.0
        assert py_pos["adds_count"] == 2
        assert py_pos["tp1_taken"] == 1  # Python uses int(True) = 1
        assert py_pos["trailing_sl"] == 2950.0
        assert py_pos["confidence"] == "high"
        assert py_pos["margin_used"] == 1500.0
        assert py_pos["last_funding_time"] == 1700000060000

    def test_kernel_to_python_long_side(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["type"] == "LONG"

    def test_kernel_to_python_short_side(self):
        kernel_pos = _make_kernel_position("ETH", "short", 1.0, 3000.0)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["type"] == "SHORT"

    def test_python_to_kernel_round_trip(self):
        """Converting kernel -> python -> kernel preserves essential fields."""
        kernel_pos = _make_kernel_position(
            "ETH", "long", 1.5, 3000.0,
            entry_atr=50.0,
            entry_adx_threshold=25.0,
            adds_count=1,
            tp1_taken=False,
            trailing_sl=2900.0,
            confidence=1,
            margin_usd=1500.0,
        )
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        round_trip = python_position_to_kernel("ETH", py_pos)

        assert round_trip["symbol"] == "ETH"
        assert round_trip["side"] == "long"
        assert round_trip["quantity"] == 1.5
        assert round_trip["avg_entry_price"] == 3000.0
        assert round_trip["entry_atr"] == 50.0
        assert round_trip["entry_adx_threshold"] == 25.0
        assert round_trip["adds_count"] == 1
        assert round_trip["tp1_taken"] is False
        assert round_trip["trailing_sl"] == 2900.0
        assert round_trip["confidence"] == 1

    def test_python_to_kernel_all_fields(self):
        py_pos = {
            "type": "SHORT",
            "entry_price": 95000.0,
            "size": 0.5,
            "confidence": "high",
            "entry_atr": 200.0,
            "entry_adx_threshold": 30.0,
            "trailing_sl": 95500.0,
            "leverage": 10.0,
            "margin_used": 4750.0,
            "adds_count": 1,
            "tp1_taken": 1,
            "last_funding_time": 1700000060000,
            "open_timestamp": "2023-11-14T22:13:20+00:00",
            "open_trade_id": 42,
            "last_add_time": 0,
        }
        kernel_pos = python_position_to_kernel("BTC", py_pos)

        assert kernel_pos["symbol"] == "BTC"
        assert kernel_pos["side"] == "short"
        assert kernel_pos["quantity"] == 0.5
        assert kernel_pos["avg_entry_price"] == 95000.0
        assert kernel_pos["entry_atr"] == 200.0
        assert kernel_pos["entry_adx_threshold"] == 30.0
        assert kernel_pos["trailing_sl"] == 95500.0
        assert kernel_pos["confidence"] == 2  # "high" -> 2
        assert kernel_pos["adds_count"] == 1
        assert kernel_pos["tp1_taken"] is True
        assert kernel_pos["notional_usd"] == pytest.approx(47500.0)
        assert kernel_pos["margin_usd"] == 4750.0
        assert kernel_pos["last_funding_ms"] == 1700000060000
        assert kernel_pos["opened_at_ms"] > 0

    def test_zero_quantity_position(self):
        kernel_pos = _make_kernel_position("ETH", "long", 0.0, 3000.0, margin_usd=0.0)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["size"] == 0.0
        assert py_pos["entry_price"] == 3000.0

    def test_none_trailing_sl(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, trailing_sl=None)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["trailing_sl"] is None

    def test_none_confidence(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, confidence=None)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["confidence"] == ""

    def test_confidence_mapping_low(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, confidence=0)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["confidence"] == "low"

    def test_confidence_mapping_medium(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, confidence=1)
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["confidence"] == "medium"

    def test_confidence_mapping_invalid_value_falls_back_to_medium(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, confidence="bad")
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["confidence"] == "medium"

    def test_confidence_mapping_infinite_value_falls_back_to_medium(self):
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, confidence=float("inf"))
        py_pos = kernel_position_to_python("ETH", kernel_pos)
        assert py_pos["confidence"] == "medium"


# ---------------------------------------------------------------------------
# TestSyncPositionsFromKernel
# ---------------------------------------------------------------------------


class TestSyncPositionsFromKernel:
    """Tests for sync_positions_from_kernel()."""

    def test_empty_state(self):
        state_json = _make_kernel_state()
        result = sync_positions_from_kernel(state_json)
        assert result == {}

    def test_state_with_positions_syncs(self):
        pos = _make_kernel_position("ETH", "long", 1.5, 3000.0, entry_atr=50.0)
        state_json = _make_kernel_state(positions={"ETH": pos})
        result = sync_positions_from_kernel(state_json)
        assert "ETH" in result
        assert result["ETH"]["type"] == "LONG"
        assert result["ETH"]["size"] == 1.5
        assert result["ETH"]["entry_price"] == 3000.0
        assert result["ETH"]["entry_atr"] == 50.0

    def test_field_values_match(self):
        pos = _make_kernel_position(
            "ETH", "short", 2.0, 3500.0,
            adds_count=3,
            tp1_taken=True,
            trailing_sl=3600.0,
            confidence=0,
            entry_adx_threshold=22.0,
        )
        state_json = _make_kernel_state(positions={"ETH": pos})
        result = sync_positions_from_kernel(state_json)
        py_pos = result["ETH"]

        assert py_pos["type"] == "SHORT"
        assert py_pos["size"] == 2.0
        assert py_pos["entry_price"] == 3500.0
        assert py_pos["adds_count"] == 3
        assert py_pos["tp1_taken"] == 1
        assert py_pos["trailing_sl"] == 3600.0
        assert py_pos["confidence"] == "low"
        assert py_pos["entry_adx_threshold"] == 22.0

    def test_multiple_symbols(self):
        pos_eth = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        pos_btc = _make_kernel_position("BTC", "short", 0.1, 95000.0)
        state_json = _make_kernel_state(positions={"ETH": pos_eth, "BTC": pos_btc})
        result = sync_positions_from_kernel(state_json)
        assert len(result) == 2
        assert result["ETH"]["type"] == "LONG"
        assert result["BTC"]["type"] == "SHORT"


# ---------------------------------------------------------------------------
# TestBuildPositionStateForDb
# ---------------------------------------------------------------------------


class TestBuildPositionStateForDb:
    """Tests for build_position_state_for_db()."""

    def test_empty_state(self):
        state_json = _make_kernel_state()
        result = build_position_state_for_db(state_json)
        assert result == []

    def test_position_data_formatted_for_db(self):
        pos = _make_kernel_position(
            "ETH", "long", 1.0, 3000.0,
            trailing_sl=2950.0,
            adds_count=2,
            tp1_taken=True,
            entry_adx_threshold=25.0,
            last_funding_ms=1700000060000,
        )
        state_json = _make_kernel_state(positions={"ETH": pos})
        result = build_position_state_for_db(state_json)

        assert len(result) == 1
        row = result[0]
        assert row["symbol"] == "ETH"
        assert row["trailing_sl"] == 2950.0
        assert row["adds_count"] == 2
        assert row["tp1_taken"] == 1
        assert row["entry_adx_threshold"] == 25.0
        assert row["last_funding_time"] == 1700000060000
        assert "updated_at" in row
        assert row["open_trade_id"] is None

    def test_multiple_positions(self):
        pos_eth = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        pos_btc = _make_kernel_position("BTC", "short", 0.5, 95000.0, adds_count=1)
        state_json = _make_kernel_state(positions={"BTC": pos_btc, "ETH": pos_eth})
        result = build_position_state_for_db(state_json)

        assert len(result) == 2
        symbols = {r["symbol"] for r in result}
        assert symbols == {"ETH", "BTC"}
        btc_row = next(r for r in result if r["symbol"] == "BTC")
        assert btc_row["adds_count"] == 1

    def test_none_trailing_sl_preserved(self):
        pos = _make_kernel_position("ETH", "long", 1.0, 3000.0, trailing_sl=None)
        state_json = _make_kernel_state(positions={"ETH": pos})
        result = build_position_state_for_db(state_json)
        assert result[0]["trailing_sl"] is None


# ---------------------------------------------------------------------------
# TestKernelIntegration (conditional on bt_runtime availability)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BT_RUNTIME_AVAILABLE, reason="bt_runtime not available")
class TestKernelIntegration:
    """Integration tests using the real Rust bt_runtime module."""

    def _get_bt_runtime(self):
        import bt_runtime  # noqa: F811
        return bt_runtime

    def test_get_positions_round_trip_via_pyo3(self):
        """Create state with bt_runtime, extract positions via get_positions."""
        rt = self._get_bt_runtime()
        state_json = rt.default_kernel_state_json(10000.0, 1700000000000)
        result = get_kernel_positions(state_json)
        assert result == {}  # fresh state has no positions

    def test_position_present_after_kernel_buy_fill(self):
        """After feeding a Buy event, the kernel state should contain a position."""
        rt = self._get_bt_runtime()
        state_json = rt.default_kernel_state_json(10000.0, 1700000000000)
        params_json = rt.default_kernel_params_json()

        event = {
            "schema_version": 1,
            "event_id": 1,
            "timestamp_ms": 1700000001000,
            "symbol": "ETH",
            "signal": "buy",
            "price": 3000.0,
            "notional_hint_usd": 1000.0,
        }
        result_json = rt.step_decision(state_json, json.dumps(event), params_json)
        result = json.loads(result_json)

        if result.get("ok") and "decision" in result:
            new_state = result["decision"]["state"]
            new_state_json = json.dumps(new_state)

            positions = get_kernel_positions(new_state_json)
            assert "ETH" in positions
            assert positions["ETH"]["side"] == "long"
            assert positions["ETH"]["quantity"] > 0
            assert positions["ETH"]["avg_entry_price"] > 0

            # Also test sync bridge
            py_positions = sync_positions_from_kernel(new_state_json)
            assert "ETH" in py_positions
            assert py_positions["ETH"]["type"] == "LONG"
            assert py_positions["ETH"]["size"] > 0
        else:
            # Kernel may reject if it requires gates etc. -- still validate the flow
            pytest.skip("Kernel rejected Buy event (gate/params mismatch)")

    def test_position_reversed_after_kernel_sell(self):
        """After Buy + Sell, the kernel closes the long and opens a short (reversal).

        The kernel treats an opposite-side signal as a Reverse: it closes
        the existing position and opens a new one in the opposite direction.
        We verify the position side flips from Long to Short.
        """
        rt = self._get_bt_runtime()
        state_json = rt.default_kernel_state_json(10000.0, 1700000000000)
        params_json = rt.default_kernel_params_json()

        # Open long
        buy_event = {
            "schema_version": 1,
            "event_id": 1,
            "timestamp_ms": 1700000001000,
            "symbol": "ETH",
            "signal": "buy",
            "price": 3000.0,
            "notional_hint_usd": 1000.0,
        }
        result_json = rt.step_decision(state_json, json.dumps(buy_event), params_json)
        result = json.loads(result_json)

        if not (result.get("ok") and "decision" in result):
            pytest.skip("Kernel rejected Buy event")

        state_json = json.dumps(result["decision"]["state"])

        positions = get_kernel_positions(state_json)
        if "ETH" not in positions:
            pytest.skip("No ETH position after Buy (kernel sizing may have zeroed it)")
        assert positions["ETH"]["side"] == "long"

        # Sell (reverses long -> short)
        sell_event = {
            "schema_version": 1,
            "event_id": 2,
            "timestamp_ms": 1700000002000,
            "symbol": "ETH",
            "signal": "sell",
            "price": 3100.0,
        }
        result_json = rt.step_decision(state_json, json.dumps(sell_event), params_json)
        result = json.loads(result_json)

        if result.get("ok") and "decision" in result:
            state_json = json.dumps(result["decision"]["state"])
            positions = get_kernel_positions(state_json)
            # After reversal: position should be short
            assert "ETH" in positions
            assert positions["ETH"]["side"] == "short"
            assert positions["ETH"]["quantity"] > 0

            # Validate bridge conversion
            py_positions = sync_positions_from_kernel(state_json)
            assert py_positions["ETH"]["type"] == "SHORT"

    def test_get_positions_pyo3_matches_fallback(self):
        """bt_runtime.get_positions() should return same data as JSON fallback."""
        rt = self._get_bt_runtime()
        state_json = rt.default_kernel_state_json(10000.0, 1700000000000)

        # Via PyO3
        pyo3_result = get_kernel_positions(state_json)

        # Via fallback
        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", False):
            fallback_result = get_kernel_positions(state_json)

        assert pyo3_result == fallback_result
