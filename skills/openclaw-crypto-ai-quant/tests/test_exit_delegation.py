"""Tests for AQC-813: Exit evaluation delegation to kernel PriceUpdate mode.

Covers:
- build_exit_params() -- ExitParams serialization from strategy config
- evaluate_exit_kernel() -- kernel PriceUpdate exit evaluation
- check_exit_with_kernel() -- orchestrator combining kernel + Python smart exits
- check_exit_with_shadow() -- shadow comparison logging
- Integration with real bt_runtime (conditional)
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from strategy.mei_alpha_v1 import (
    _BT_RUNTIME_AVAILABLE,
    _DEFAULT_STRATEGY_CONFIG,
    build_exit_params,
    build_indicator_snapshot,
    evaluate_exit_kernel,
    check_exit_with_kernel,
    check_exit_with_shadow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trending_df(n: int = 60, base_price: float = 95000.0) -> pd.DataFrame:
    """Create a trending-up DataFrame suitable for indicator computation."""
    rows = []
    for i in range(n):
        o = base_price + i * 10 + (i % 7) * 3
        h = o + 500 + (i % 5) * 20
        l = o - 200 - (i % 3) * 15
        c = o + 200 + (i % 11) * 5
        v = 100.0 + i * 2 + (i % 4) * 10
        ts = 1700000000000 + i * 3600000  # 1-hour candles
        rows.append({"Timestamp": ts, "Open": o, "High": h, "Low": l, "Close": c, "Volume": v})
    return pd.DataFrame(rows)


def _make_kernel_step_result(
    *,
    exit_type: str | None = None,
    exit_reason: str | None = None,
    exit_price: float = 0.0,
    entry_price: float = 95000.0,
    profit_atr: float = 0.0,
    is_partial: bool = False,
    ok: bool = True,
) -> str:
    """Build a kernel step_full result JSON matching PriceUpdate output."""
    exit_context = None
    intents = []
    fills = []

    if exit_type is not None:
        exit_context = {
            "exit_type": exit_type,
            "exit_reason": exit_reason or exit_type,
            "exit_price": exit_price,
            "entry_price": entry_price,
            "sl_price": entry_price - 500.0,
            "tp_price": entry_price + 2000.0,
            "trailing_sl": None,
            "profit_atr": profit_atr,
            "duration_bars": 10,
        }
        frac = 0.5 if is_partial else 1.0
        intents.append({
            "kind": "close",
            "symbol": "ETH",
            "side": "long",
            "notional_usd": 10000.0,
            "close_fraction": frac,
        })
        fills.append({
            "symbol": "ETH",
            "side": "long",
            "price": exit_price,
            "notional_usd": 10000.0,
            "close_fraction": frac,
            "fee_usd": 3.5,
        })

    diag = {
        "schema_version": 1,
        "errors": [],
        "warnings": [],
        "intent_count": len(intents),
        "fill_count": len(fills),
        "step": 1,
        "gate_blocked": False,
        "gate_block_reasons": [],
        "entry_signal": None,
        "entry_confidence": None,
        "cooldown_blocked": False,
        "pesc_blocked": False,
        "applied_thresholds": [],
        "exit_context": exit_context,
        "confidence_factors": [],
        "indicator_snapshot": {
            "close": 95200.0, "ema_fast": 95100.0, "ema_slow": 95000.0,
            "adx": 30.0, "rsi": 55.0, "atr": 500.0,
        },
    }

    state = {
        "schema_version": 1,
        "step": 1,
        "cash_usd": 10000.0,
        "timestamp_ms": 1700000000000,
        "positions": {},
        "last_entry_ts": {},
        "last_exit_ts": {},
        "last_exit_side": {},
    }

    result = {
        "ok": ok,
        "decision": {
            "schema_version": 1,
            "state": state,
            "intents": intents,
            "fills": fills,
            "diagnostics": diag,
        },
    }

    if not ok:
        result = {
            "ok": False,
            "error": {
                "code": "TEST_ERROR",
                "message": "test error",
                "details": [],
            },
        }

    return json.dumps(result)


def _default_state_json(*, with_position: bool = False, side: str = "long",
                        entry_price: float = 95000.0,
                        entry_atr: float = 500.0) -> str:
    """Build default kernel state JSON, optionally with a position."""
    positions = {}
    if with_position:
        positions["ETH"] = {
            "side": side,
            "entry_price": entry_price,
            "entry_atr": entry_atr,
            "size": 0.1,
            "notional_usd": 9500.0,
            "margin_usd": 9500.0,
            "open_ts": 1700000000000,
            "open_step": 0,
            "realized_pnl": 0.0,
            "fills": 1,
        }
    return json.dumps({
        "schema_version": 1,
        "step": 0,
        "cash_usd": 10000.0,
        "timestamp_ms": 1700000000000,
        "positions": positions,
        "last_entry_ts": {},
        "last_exit_ts": {},
        "last_exit_side": {},
    })


def _default_params_json() -> str:
    return json.dumps({
        "schema_version": 1,
        "default_notional_usd": 10000.0,
        "min_notional_usd": 10.0,
        "max_notional_usd": 100000.0,
        "maker_fee_bps": 1.0,
        "taker_fee_bps": 3.5,
        "allow_pyramid": False,
        "allow_reverse": False,
        "leverage": 1.0,
    })


# ---------------------------------------------------------------------------
# Tests -- build_exit_params
# ---------------------------------------------------------------------------


class TestBuildExitParams:
    """Verify build_exit_params produces all fields matching Rust ExitParams."""

    def test_default_params_have_all_fields(self):
        """Default params should contain every field in the Rust ExitParams struct."""
        params = build_exit_params()
        required_fields = [
            "sl_atr_mult", "tp_atr_mult", "trailing_start_atr",
            "trailing_distance_atr", "enable_partial_tp", "tp_partial_pct",
            "tp_partial_atr_mult", "tp_partial_min_notional_usd",
            "enable_breakeven_stop", "breakeven_start_atr", "breakeven_buffer_atr",
            "enable_vol_buffered_trailing", "block_exits_on_extreme_dev",
            "glitch_price_dev_pct", "glitch_atr_mult",
            "smart_exit_adx_exhaustion_lt", "tsme_min_profit_atr",
            "tsme_require_adx_slope_negative", "enable_rsi_overextension_exit",
            "rsi_exit_profit_atr_switch", "rsi_exit_ub_lo_profit",
            "rsi_exit_ub_hi_profit", "rsi_exit_lb_lo_profit", "rsi_exit_lb_hi_profit",
            "rsi_exit_ub_lo_profit_low_conf", "rsi_exit_lb_lo_profit_low_conf",
            "rsi_exit_ub_hi_profit_low_conf", "rsi_exit_lb_hi_profit_low_conf",
            "smart_exit_adx_exhaustion_lt_low_conf",
            "require_macro_alignment",
            "trailing_start_atr_low_conf", "trailing_distance_atr_low_conf",
        ]
        for field in required_fields:
            assert field in params, f"Missing ExitParams field: {field}"

    def test_default_values_match_config(self):
        """Default exit params should match _DEFAULT_STRATEGY_CONFIG trade values."""
        params = build_exit_params()
        trade = _DEFAULT_STRATEGY_CONFIG["trade"]
        assert params["sl_atr_mult"] == pytest.approx(trade["sl_atr_mult"])
        assert params["trailing_start_atr"] == pytest.approx(trade["trailing_start_atr"])
        assert params["trailing_distance_atr"] == pytest.approx(trade["trailing_distance_atr"])
        assert params["enable_partial_tp"] is True
        assert params["enable_breakeven_stop"] is True
        assert params["glitch_price_dev_pct"] == pytest.approx(0.40)

    def test_custom_config_maps_correctly(self):
        """Custom config values should override defaults."""
        cfg = {
            "trade": {
                "sl_atr_mult": 3.0,
                "tp_atr_mult": 6.0,
                "trailing_start_atr": 2.0,
                "trailing_distance_atr": 1.5,
                "enable_partial_tp": False,
                "glitch_price_dev_pct": 0.50,
                "glitch_atr_mult": 15.0,
            },
            "filters": {
                "require_macro_alignment": True,
            },
        }
        params = build_exit_params(cfg)
        assert params["sl_atr_mult"] == pytest.approx(3.0)
        assert params["tp_atr_mult"] == pytest.approx(6.0)
        assert params["trailing_start_atr"] == pytest.approx(2.0)
        assert params["enable_partial_tp"] is False
        assert params["require_macro_alignment"] is True
        assert params["glitch_price_dev_pct"] == pytest.approx(0.50)

    def test_json_serializable(self):
        """All exit params must be JSON serializable."""
        params = build_exit_params()
        text = json.dumps(params)
        restored = json.loads(text)
        assert restored == params

    def test_per_confidence_overrides_present(self):
        """Low-confidence trailing and RSI overrides should be included."""
        params = build_exit_params()
        assert "trailing_start_atr_low_conf" in params
        assert "trailing_distance_atr_low_conf" in params
        assert "smart_exit_adx_exhaustion_lt_low_conf" in params
        assert "rsi_exit_ub_lo_profit_low_conf" in params
        assert "rsi_exit_lb_lo_profit_low_conf" in params
        # Default value is 0.0 (meaning "use main value")
        assert params["trailing_start_atr_low_conf"] == pytest.approx(0.0)
        assert params["trailing_distance_atr_low_conf"] == pytest.approx(0.0)

    def test_glitch_guard_params(self):
        """Glitch guard parameters should be present and match defaults."""
        params = build_exit_params()
        assert params["block_exits_on_extreme_dev"] is False
        assert params["glitch_price_dev_pct"] == pytest.approx(0.40)
        assert params["glitch_atr_mult"] == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Tests -- evaluate_exit_kernel (mocked bt_runtime)
# ---------------------------------------------------------------------------


class TestEvaluateExitKernel:
    """Test evaluate_exit_kernel with mocked bt_runtime."""

    def test_hold_when_no_exit_triggered(self):
        """Kernel returning no exit_context should produce 'hold'."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = evaluate_exit_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
                current_price=95200.0, timestamp_ms=1700000060000,
            )

        assert action == "hold"
        assert exit_ctx is None
        assert isinstance(diag, dict)

    def test_full_close_on_stop_loss(self):
        """Kernel returning exit_context with stop_loss should produce 'full_close'."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result(
            exit_type="stop_loss",
            exit_reason="SL hit at 94000.0",
            exit_price=94000.0,
            profit_atr=-2.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = evaluate_exit_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
                current_price=94000.0, timestamp_ms=1700000060000,
            )

        assert action == "full_close"
        assert exit_ctx is not None
        assert exit_ctx["exit_type"] == "stop_loss"
        assert exit_ctx["exit_price"] == 94000.0

    def test_full_close_on_trailing_stop(self):
        """Kernel returning trailing stop exit should produce 'full_close'."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result(
            exit_type="trailing_stop",
            exit_reason="Trailing SL triggered",
            exit_price=96000.0,
            profit_atr=1.5,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = evaluate_exit_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
                current_price=96000.0, timestamp_ms=1700000060000,
            )

        assert action == "full_close"
        assert exit_ctx["exit_type"] == "trailing_stop"

    def test_partial_close_on_tp1(self):
        """Kernel returning partial TP should produce 'partial_close'."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result(
            exit_type="take_profit",
            exit_reason="TP1 partial at 97000.0",
            exit_price=97000.0,
            profit_atr=4.0,
            is_partial=True,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = evaluate_exit_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
                current_price=97000.0, timestamp_ms=1700000060000,
            )

        assert action == "partial_close"
        assert exit_ctx is not None
        assert exit_ctx["exit_type"] == "take_profit"

    def test_raises_without_bt_runtime(self):
        """Should raise RuntimeError when bt_runtime is not available."""
        df = _make_trending_df(60)
        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", False), \
             patch("strategy.mei_alpha_v1._bt_runtime", None):
            with pytest.raises(RuntimeError, match="bt_runtime is not available"):
                evaluate_exit_kernel(
                    df, "ETH", _default_state_json(), _default_params_json(),
                    current_price=95200.0, timestamp_ms=1700000060000,
                )

    def test_raises_on_kernel_error(self):
        """Should raise RuntimeError when kernel returns ok=False."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result(ok=False)

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            with pytest.raises(RuntimeError, match="Kernel PriceUpdate failed"):
                evaluate_exit_kernel(
                    df, "ETH", _default_state_json(), _default_params_json(),
                    current_price=95200.0, timestamp_ms=1700000060000,
                )

    def test_event_has_price_update_signal(self):
        """Verify the MarketEvent sent to kernel has signal=price_update."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            evaluate_exit_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
                current_price=95200.0, timestamp_ms=1700000060000,
            )

        call_args = mock_runtime.step_full.call_args
        event_sent = json.loads(call_args[0][1])
        assert event_sent["signal"] == "price_update"
        assert "indicators" in event_sent
        assert event_sent["symbol"] == "ETH"
        assert event_sent["price"] == 95200.0

    def test_exit_params_passed_to_step_full(self):
        """Verify exit_params JSON is passed as fourth argument to step_full."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            evaluate_exit_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
                current_price=95200.0, timestamp_ms=1700000060000,
            )

        call_args = mock_runtime.step_full.call_args
        exit_params_sent = json.loads(call_args[0][3])
        assert "sl_atr_mult" in exit_params_sent
        assert "trailing_start_atr" in exit_params_sent
        assert "enable_breakeven_stop" in exit_params_sent


# ---------------------------------------------------------------------------
# Tests -- check_exit_with_kernel
# ---------------------------------------------------------------------------


class TestCheckExitWithKernel:
    """Test kernel-only exit orchestration in SSOT mode."""

    def _patch_kernel_exit(self, mock_runtime, result_json):
        """Helper to configure mock bt_runtime for exit evaluation."""
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(_make_trending_df(60))
        )
        mock_runtime.step_full.return_value = result_json

    def test_kernel_full_close_returned_immediately(self):
        """When kernel says full_close, return immediately without checking smart exits."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result(
            exit_type="stop_loss",
            exit_reason="SL hit",
            exit_price=94000.0,
            profit_atr=-2.0,
        ))

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH",
                _default_state_json(with_position=True),
                _default_params_json(),
                current_price=94000.0,
                timestamp_ms=1700000060000,
            )

        assert action == "full_close"
        assert exit_ctx is not None
        assert exit_ctx["exit_type"] == "stop_loss"

    def test_kernel_hold_not_overridden_by_python_adx_exhaustion(self):
        """When kernel holds, Python ADX heuristics must not force an exit."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        # Kernel returns hold
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result())

        # Indicators that would have triggered legacy Python ADX exit.
        indicators = {
            "ADX": 15.0,
            "RSI": 55.0,
            "EMA_fast": 95500.0,
            "EMA_slow": 95000.0,
            "ATR": 500.0,
        }

        # State with a long position that has profit > tsme_min_profit_atr (1.0)
        state_json = _default_state_json(
            with_position=True, side="long",
            entry_price=94000.0, entry_atr=500.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH", state_json, _default_params_json(),
                current_price=95500.0,
                timestamp_ms=1700000060000,
                indicators=indicators,
            )

        assert action == "hold"
        assert exit_ctx is None

    def test_kernel_hold_not_overridden_by_python_rsi_overextension(self):
        """When kernel holds, Python RSI heuristics must not force an exit."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result())

        # Indicators that would have triggered legacy Python RSI exit.
        indicators = {
            "ADX": 30.0,
            "RSI": 85.0,
            "EMA_fast": 95500.0,
            "EMA_slow": 95000.0,
            "ATR": 500.0,
        }

        state_json = _default_state_json(
            with_position=True, side="long",
            entry_price=95000.0, entry_atr=500.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH", state_json, _default_params_json(),
                current_price=95200.0,
                timestamp_ms=1700000060000,
                indicators=indicators,
            )

        assert action == "hold"
        assert exit_ctx is None

    def test_kernel_hold_not_overridden_by_python_trend_breakdown(self):
        """When kernel holds, Python EMA-cross heuristics must not force an exit."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result())

        # Indicators that would have triggered legacy Python EMA-cross exit.
        indicators = {
            "ADX": 30.0,
            "RSI": 50.0,
            "EMA_fast": 94500.0,   # Below EMA_slow => bearish cross
            "EMA_slow": 95000.0,
            "ATR": 500.0,
        }

        state_json = _default_state_json(
            with_position=True, side="long",
            entry_price=95000.0, entry_atr=500.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH", state_json, _default_params_json(),
                current_price=94800.0,
                timestamp_ms=1700000060000,
                indicators=indicators,
            )

        assert action == "hold"
        assert exit_ctx is None

    def test_pure_hold_when_nothing_fires(self):
        """When kernel holds, return hold."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result())

        # Healthy indicators: no smart exits should fire
        indicators = {
            "ADX": 30.0,       # Above exhaustion
            "RSI": 55.0,       # Normal RSI
            "EMA_fast": 95500.0,  # Fast above slow => trend intact
            "EMA_slow": 95000.0,
            "ATR": 500.0,
        }

        state_json = _default_state_json(
            with_position=True, side="long",
            entry_price=95000.0, entry_atr=500.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH", state_json, _default_params_json(),
                current_price=95200.0,  # Small profit, no exit triggers
                timestamp_ms=1700000060000,
                indicators=indicators,
            )

        assert action == "hold"
        assert exit_ctx is None

    def test_kernel_authority_close_overrides_smart_exit(self):
        """Kernel close should be returned even if smart exits might also fire.

        Since kernel is checked first and returns immediately on close,
        smart exits are never evaluated.
        """
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        # Kernel says full_close (SL hit)
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result(
            exit_type="stop_loss",
            exit_reason="SL hit at 93000",
            exit_price=93000.0,
            profit_atr=-4.0,
        ))

        # Indicators that would also trigger smart exits (low ADX + bearish cross)
        indicators = {
            "ADX": 10.0,
            "RSI": 85.0,
            "EMA_fast": 93000.0,
            "EMA_slow": 95000.0,
            "ATR": 500.0,
        }

        state_json = _default_state_json(
            with_position=True, side="long",
            entry_price=95000.0, entry_atr=500.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH", state_json, _default_params_json(),
                current_price=93000.0,
                timestamp_ms=1700000060000,
                indicators=indicators,
            )

        # Kernel's stop_loss should be returned, not a smart exit
        assert action == "full_close"
        assert exit_ctx["exit_type"] == "stop_loss"

    def test_no_position_returns_hold(self):
        """When no position exists for the symbol, should return hold."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result())

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH",
                _default_state_json(with_position=False),  # No position
                _default_params_json(),
                current_price=95200.0,
                timestamp_ms=1700000060000,
            )

        assert action == "hold"
        assert exit_ctx is None

    def test_short_position_python_trend_breakdown_not_applied(self):
        """Kernel hold should not be overridden by Python EMA-cross on shorts."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        self._patch_kernel_exit(mock_runtime, _make_kernel_step_result())

        indicators = {
            "ADX": 30.0,
            "RSI": 50.0,
            "EMA_fast": 95500.0,  # Above EMA_slow => bullish cross
            "EMA_slow": 95000.0,
            "ATR": 500.0,
        }

        state_json = _default_state_json(
            with_position=True, side="short",
            entry_price=95000.0, entry_atr=500.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_kernel(
                df, "ETH", state_json, _default_params_json(),
                current_price=95200.0,
                timestamp_ms=1700000060000,
                indicators=indicators,
            )

        assert action == "hold"
        assert exit_ctx is None


# ---------------------------------------------------------------------------
# Tests -- check_exit_with_shadow
# ---------------------------------------------------------------------------


class TestCheckExitWithShadow:
    """Test shadow comparison logging for exit evaluation."""

    def test_returns_kernel_result(self):
        """Shadow mode should always return the kernel result."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_full.return_value = _make_kernel_step_result(
            exit_type="stop_loss",
            exit_reason="SL hit",
            exit_price=94000.0,
            profit_atr=-2.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            action, exit_ctx, diag = check_exit_with_shadow(
                df, "ETH",
                _default_state_json(with_position=True),
                _default_params_json(),
                current_price=94000.0,
                timestamp_ms=1700000060000,
            )

        assert action == "full_close"
        assert exit_ctx is not None
        assert exit_ctx["exit_type"] == "stop_loss"

    def test_logs_mismatch(self, caplog):
        """When kernel and Python disagree, a WARNING should be logged."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        # Kernel says full_close, but Python (trend-breakdown check) might say hold
        # if EMA_fast > EMA_slow in the snapshot
        mock_runtime.step_full.return_value = _make_kernel_step_result(
            exit_type="stop_loss",
            exit_reason="SL hit",
            exit_price=94000.0,
            profit_atr=-2.0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            with caplog.at_level(logging.WARNING, logger="strategy.mei_alpha_v1"):
                action, exit_ctx, diag = check_exit_with_shadow(
                    df, "ETH",
                    _default_state_json(with_position=True),
                    _default_params_json(),
                    current_price=94000.0,
                    timestamp_ms=1700000060000,
                    # Default snapshot has ema_fast=95100 > ema_slow=95000
                    # so Python will say "hold" for long -> mismatch with kernel "full_close"
                )

        assert action == "full_close"  # Kernel is authoritative
        assert any("[exit-shadow] Exit mismatch" in msg for msg in caplog.messages), (
            f"Expected mismatch warning, got: {caplog.messages}"
        )

    def test_logs_agreement(self, caplog):
        """When kernel and Python agree on hold, a DEBUG message should be logged."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        # Both kernel and Python say hold (no exit triggers, trend intact)
        mock_runtime.step_full.return_value = _make_kernel_step_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            with caplog.at_level(logging.DEBUG, logger="strategy.mei_alpha_v1"):
                action, exit_ctx, diag = check_exit_with_shadow(
                    df, "ETH",
                    _default_state_json(with_position=True),
                    _default_params_json(),
                    current_price=95200.0,
                    timestamp_ms=1700000060000,
                )

        assert action == "hold"
        assert any("[exit-shadow] Exit agreement" in msg for msg in caplog.messages), (
            f"Expected agreement log, got: {caplog.messages}"
        )


# ---------------------------------------------------------------------------
# Tests -- Integration with real bt_runtime (conditional)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BT_RUNTIME_AVAILABLE, reason="bt_runtime .so not available")
class TestKernelIntegration:
    """Integration tests that run against the real Rust kernel."""

    def test_full_round_trip(self):
        """Full round-trip: open position via Buy, then PriceUpdate exit check."""
        import bt_runtime

        df = _make_trending_df(200)

        # Initialize state with some cash
        state_json = bt_runtime.default_kernel_state_json(10000.0, 1700000000000)
        params_json = bt_runtime.default_kernel_params_json()

        # First, open a position via a Buy event (notional_hint_usd required)
        snap = build_indicator_snapshot(df)
        close_price = float(snap.get("close", 95000.0))
        buy_event = {
            "schema_version": 1,
            "event_id": 1700000000000,
            "timestamp_ms": 1700000000000,
            "symbol": "ETH",
            "signal": "buy",
            "price": close_price,
            "notional_hint_usd": 1000.0,
        }
        buy_result_json = bt_runtime.step_decision(
            state_json, json.dumps(buy_event), params_json,
        )
        buy_result = json.loads(buy_result_json)
        assert buy_result.get("ok"), f"Buy failed: {buy_result}"

        # Use updated state for exit evaluation
        new_state = buy_result["decision"]["state"]
        new_state_json = json.dumps(new_state)

        # Verify position exists
        assert "ETH" in new_state.get("positions", {}), "Position should exist"

        # Now evaluate exit at current price (should be hold if price hasn't moved much)
        action, exit_ctx, diag = evaluate_exit_kernel(
            df, "ETH", new_state_json, params_json,
            current_price=close_price,
            timestamp_ms=1700000060000,
        )

        assert action in ("hold", "full_close", "partial_close")
        assert isinstance(diag, dict)

    def test_hold_for_safe_price(self):
        """Price near entry should produce hold (no exit triggered)."""
        import bt_runtime

        df = _make_trending_df(200)
        snap = build_indicator_snapshot(df)
        close = float(snap.get("close", 95000.0))

        state_json = bt_runtime.default_kernel_state_json(10000.0, 1700000000000)
        params_json = bt_runtime.default_kernel_params_json()

        # Open position (notional_hint_usd required to actually fill)
        buy_event = {
            "schema_version": 1,
            "event_id": 1700000000000,
            "timestamp_ms": 1700000000000,
            "symbol": "ETH",
            "signal": "buy",
            "price": close,
            "notional_hint_usd": 1000.0,
        }
        buy_result = json.loads(bt_runtime.step_decision(
            state_json, json.dumps(buy_event), params_json,
        ))
        assert buy_result.get("ok")
        new_state_json = json.dumps(buy_result["decision"]["state"])

        # Price barely moved => should be hold
        action, exit_ctx, diag = evaluate_exit_kernel(
            df, "ETH", new_state_json, params_json,
            current_price=close + 10.0,  # Tiny move
            timestamp_ms=1700000060000,
        )

        assert action == "hold"
        assert exit_ctx is None

    def test_state_update_after_exit(self):
        """After a full close, the position should be removed from state."""
        import bt_runtime

        df = _make_trending_df(200)
        snap = build_indicator_snapshot(df)
        close = float(snap.get("close", 95000.0))

        state_json = bt_runtime.default_kernel_state_json(10000.0, 1700000000000)
        params_json = bt_runtime.default_kernel_params_json()

        # Open position (notional_hint_usd required)
        buy_event = {
            "schema_version": 1,
            "event_id": 1700000000000,
            "timestamp_ms": 1700000000000,
            "symbol": "ETH",
            "signal": "buy",
            "price": close,
            "notional_hint_usd": 1000.0,
        }
        buy_result = json.loads(bt_runtime.step_decision(
            state_json, json.dumps(buy_event), params_json,
        ))
        assert buy_result.get("ok")
        new_state_json = json.dumps(buy_result["decision"]["state"])

        # The kernel position has entry_atr=None, so effective_atr = entry * 0.005.
        # SL = entry - effective_atr * sl_atr_mult (default 2.0).
        # We need to drop the *indicator snapshot close* below the SL price.
        effective_atr = close * 0.005
        crash_price = close - effective_atr * 5.0  # Well below SL

        # Build a modified snapshot with the crashed close price
        crash_snap = dict(snap)
        crash_snap["close"] = crash_price

        exit_params = build_exit_params()
        exit_params_json = json.dumps(exit_params)

        exit_event = {
            "schema_version": 1,
            "event_id": 1700000060000,
            "timestamp_ms": 1700000060000,
            "symbol": "ETH",
            "signal": "price_update",
            "price": crash_price,
            "indicators": crash_snap,
        }

        result_json = bt_runtime.step_full(
            new_state_json, json.dumps(exit_event),
            params_json, exit_params_json,
        )
        result = json.loads(result_json)
        assert result.get("ok"), f"Exit failed: {result}"

        # After SL exit, position should be gone
        post_state = result["decision"]["state"]
        positions = post_state.get("positions", {})
        assert "ETH" not in positions, (
            f"Position should be removed after full close, got: {positions}"
        )
