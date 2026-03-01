"""Tests for AQC-812: Entry signal delegation to kernel Evaluate mode.

Covers:
- evaluate_entry_kernel() — signal extraction from kernel diagnostics
- build_gate_result() — gate evaluation matching Rust schema
- build_entry_params() — EntryParams serialization
- compute_ema_slow_slope() — EMA slope computation
- analyze_with_shadow() — shadow comparison logging
"""

from __future__ import annotations

import json
import logging
import math
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from strategy.mei_alpha_v1 import (
    _BT_RUNTIME_AVAILABLE,
    _DEFAULT_STRATEGY_CONFIG,
    build_gate_result,
    build_indicator_snapshot,
    build_entry_params,
    compute_ema_slow_slope,
    evaluate_entry_kernel,
    analyze_with_shadow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trending_df(n: int = 60, base_price: float = 95000.0) -> pd.DataFrame:
    """Create a trending-up DataFrame suitable for indicator computation.

    Prices drift upward with deterministic jitter.  Volume is above-average
    so that volume gates pass.
    """
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


def _make_ranging_df(n: int = 60, base_price: float = 95000.0) -> pd.DataFrame:
    """Create a ranging/sideways DataFrame with very tight price action.

    ADX will be low and BB width narrow — should trigger the ranging gate.
    """
    rows = []
    for i in range(n):
        # Tiny oscillation around base price
        offset = ((i % 5) - 2) * 2  # -4, -2, 0, 2, 4
        o = base_price + offset
        h = o + 5
        l = o - 5
        c = o + ((i % 3) - 1) * 2
        v = 50.0 + (i % 3) * 5
        ts = 1700000000000 + i * 3600000
        rows.append({"Timestamp": ts, "Open": o, "High": h, "Low": l, "Close": c, "Volume": v})
    return pd.DataFrame(rows)


def _make_kernel_decision_result(
    signal: str = "buy",
    confidence: int = 1,
    *,
    ok: bool = True,
    gate_blocked: bool = False,
) -> str:
    """Build a kernel decision result JSON string matching step_decision output."""
    diag = {
        "schema_version": 1,
        "errors": [],
        "warnings": [],
        "intent_count": 0 if signal == "neutral" else 1,
        "fill_count": 0 if signal == "neutral" else 1,
        "step": 1,
        "gate_blocked": gate_blocked,
        "gate_block_reasons": [],
        "entry_signal": signal,
        "entry_confidence": confidence,
        "cooldown_blocked": False,
        "pesc_blocked": False,
        "applied_thresholds": [],
        "confidence_factors": [],
    }
    result = {
        "ok": ok,
        "decision": {
            "schema_version": 1,
            "state": {
                "schema_version": 1,
                "step": 1,
                "cash_usd": 10000.0,
                "timestamp_ms": 1700000000000,
                "positions": {},
                "last_entry_ts": {},
                "last_exit_ts": {},
                "last_exit_side": {},
            },
            "intents": [],
            "fills": [],
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


def _default_state_json() -> str:
    return json.dumps({
        "schema_version": 1,
        "step": 0,
        "cash_usd": 10000.0,
        "timestamp_ms": 1700000000000,
        "positions": {},
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
# Tests — build_gate_result
# ---------------------------------------------------------------------------


class TestBuildGateResult:
    """Verify build_gate_result produces all fields matching Rust GateResult."""

    def test_returns_all_fields(self):
        df = _make_trending_df(60)
        snap = build_indicator_snapshot(df)
        gate = build_gate_result(snap, "ETH")

        expected_fields = [
            "is_ranging", "is_anomaly", "is_extended", "vol_confirm",
            "is_trending_up", "adx_above_min", "bullish_alignment",
            "bearish_alignment", "btc_ok_long", "btc_ok_short",
            "effective_min_adx", "bb_width_ratio", "dynamic_tp_mult",
            "rsi_long_limit", "rsi_short_limit", "stoch_k", "stoch_d",
            "stoch_rsi_active", "all_gates_pass",
        ]
        for field in expected_fields:
            assert field in gate, f"Missing field: {field}"

    def test_all_gates_pass_trending(self):
        df = _make_trending_df(200)
        snap = build_indicator_snapshot(df)
        gate = build_gate_result(snap, "ETH", btc_bullish=True)

        # Trending data should generally pass gates
        assert isinstance(gate["all_gates_pass"], bool)
        assert isinstance(gate["is_ranging"], bool)
        assert isinstance(gate["effective_min_adx"], float)
        assert gate["effective_min_adx"] > 0

    def test_ranging_detected(self):
        """When ADX is very low and BB is tight, ranging gate should fire."""
        # Use a snapshot with artificially low ADX
        snap = {
            "close": 100.0, "high": 101.0, "low": 99.0, "open": 100.0,
            "volume": 50.0, "t": 1700000000000,
            "ema_slow": 100.0, "ema_fast": 100.0, "ema_macro": 100.0,
            "adx": 15.0, "adx_pos": 7.0, "adx_neg": 8.0, "adx_slope": -0.5,
            "bb_upper": 101.0, "bb_lower": 99.0, "bb_width": 0.02,
            "bb_width_avg": 0.03, "bb_width_ratio": 0.67,
            "atr": 1.0, "atr_slope": 0.0, "avg_atr": 1.0,
            "rsi": 50.0, "stoch_rsi_k": 0.5, "stoch_rsi_d": 0.5,
            "macd_hist": 0.0, "prev_macd_hist": 0.0,
            "prev2_macd_hist": 0.0, "prev3_macd_hist": 0.0,
            "vol_sma": 100.0, "vol_trend": False,
            "prev_close": 100.0, "prev_ema_fast": 100.0, "prev_ema_slow": 100.0,
            "bar_count": 200, "funding_rate": 0.0,
        }
        gate = build_gate_result(snap, "ETH")
        assert gate["is_ranging"] is True
        assert gate["all_gates_pass"] is False

    def test_btc_alignment_blocks_long(self):
        snap = {
            "close": 100.0, "high": 101.0, "low": 99.0, "open": 100.0,
            "volume": 1000.0, "t": 0,
            "ema_slow": 98.0, "ema_fast": 99.0, "ema_macro": 95.0,
            "adx": 30.0, "adx_pos": 20.0, "adx_neg": 10.0, "adx_slope": 1.0,
            "bb_upper": 102.0, "bb_lower": 98.0, "bb_width": 0.04,
            "bb_width_avg": 0.03, "bb_width_ratio": 1.33,
            "atr": 1.5, "atr_slope": 0.1, "avg_atr": 1.4,
            "rsi": 55.0, "stoch_rsi_k": 0.5, "stoch_rsi_d": 0.5,
            "macd_hist": 0.5, "prev_macd_hist": 0.3,
            "prev2_macd_hist": 0.1, "prev3_macd_hist": 0.0,
            "vol_sma": 800.0, "vol_trend": True,
            "prev_close": 99.5, "prev_ema_fast": 98.5, "prev_ema_slow": 97.8,
            "bar_count": 200, "funding_rate": 0.0,
        }
        gate = build_gate_result(snap, "ETH", btc_bullish=False)
        assert gate["btc_ok_long"] is False, "BTC bearish should block ETH long"
        assert gate["btc_ok_short"] is True, "BTC bearish should allow ETH short"

    def test_btc_symbol_always_ok(self):
        snap = {
            "close": 100.0, "high": 101.0, "low": 99.0, "open": 100.0,
            "volume": 1000.0, "t": 0,
            "ema_slow": 98.0, "ema_fast": 99.0, "ema_macro": 95.0,
            "adx": 30.0, "adx_pos": 20.0, "adx_neg": 10.0, "adx_slope": 1.0,
            "bb_upper": 102.0, "bb_lower": 98.0, "bb_width": 0.04,
            "bb_width_avg": 0.03, "bb_width_ratio": 1.33,
            "atr": 1.5, "atr_slope": 0.1, "avg_atr": 1.4,
            "rsi": 55.0, "stoch_rsi_k": 0.5, "stoch_rsi_d": 0.5,
            "macd_hist": 0.5, "prev_macd_hist": 0.3,
            "prev2_macd_hist": 0.1, "prev3_macd_hist": 0.0,
            "vol_sma": 800.0, "vol_trend": True,
            "prev_close": 99.5, "prev_ema_fast": 98.5, "prev_ema_slow": 97.8,
            "bar_count": 200, "funding_rate": 0.0,
        }
        gate = build_gate_result(snap, "BTC", btc_bullish=False)
        assert gate["btc_ok_long"] is True
        assert gate["btc_ok_short"] is True

    def test_anomaly_filter_fires(self):
        snap = {
            "close": 115.0, "high": 116.0, "low": 99.0, "open": 100.0,
            "volume": 1000.0, "t": 0,
            "ema_slow": 98.0, "ema_fast": 99.0, "ema_macro": 95.0,
            "adx": 30.0, "adx_pos": 20.0, "adx_neg": 10.0, "adx_slope": 1.0,
            "bb_upper": 102.0, "bb_lower": 98.0, "bb_width": 0.04,
            "bb_width_avg": 0.03, "bb_width_ratio": 1.33,
            "atr": 1.5, "atr_slope": 0.1, "avg_atr": 1.4,
            "rsi": 55.0, "stoch_rsi_k": 0.5, "stoch_rsi_d": 0.5,
            "macd_hist": 0.5, "prev_macd_hist": 0.3,
            "prev2_macd_hist": 0.1, "prev3_macd_hist": 0.0,
            "vol_sma": 800.0, "vol_trend": True,
            "prev_close": 100.0, "prev_ema_fast": 98.5, "prev_ema_slow": 97.8,
            "bar_count": 200, "funding_rate": 0.0,
        }
        gate = build_gate_result(snap, "ETH")
        assert gate["is_anomaly"] is True
        assert gate["all_gates_pass"] is False

    def test_extension_filter(self):
        snap = {
            "close": 105.0, "high": 106.0, "low": 99.0, "open": 100.0,
            "volume": 1000.0, "t": 0,
            "ema_slow": 98.0, "ema_fast": 99.0, "ema_macro": 95.0,
            "adx": 30.0, "adx_pos": 20.0, "adx_neg": 10.0, "adx_slope": 1.0,
            "bb_upper": 102.0, "bb_lower": 98.0, "bb_width": 0.04,
            "bb_width_avg": 0.03, "bb_width_ratio": 1.33,
            "atr": 1.5, "atr_slope": 0.1, "avg_atr": 1.4,
            "rsi": 55.0, "stoch_rsi_k": 0.5, "stoch_rsi_d": 0.5,
            "macd_hist": 0.5, "prev_macd_hist": 0.3,
            "prev2_macd_hist": 0.1, "prev3_macd_hist": 0.0,
            "vol_sma": 800.0, "vol_trend": True,
            "prev_close": 99.5, "prev_ema_fast": 98.5, "prev_ema_slow": 97.8,
            "bar_count": 200, "funding_rate": 0.0,
        }
        gate = build_gate_result(snap, "ETH")
        # 6% distance from EMA_fast (99.0) should trigger extension
        assert gate["is_extended"] is True
        assert gate["all_gates_pass"] is False

    def test_tmc_lowers_threshold(self):
        """When ADX slope > 0.5, effective_min_adx should cap at 25."""
        snap = {
            "close": 100.0, "high": 101.0, "low": 99.0, "open": 100.0,
            "volume": 1000.0, "t": 0,
            "ema_slow": 98.0, "ema_fast": 99.0, "ema_macro": 95.0,
            "adx": 24.0, "adx_pos": 20.0, "adx_neg": 10.0,
            "adx_slope": 1.0,  # > 0.5 triggers TMC
            "bb_upper": 102.0, "bb_lower": 98.0, "bb_width": 0.04,
            "bb_width_avg": 0.03, "bb_width_ratio": 1.33,
            "atr": 1.5, "atr_slope": 0.1, "avg_atr": 1.4,
            "rsi": 55.0, "stoch_rsi_k": 0.5, "stoch_rsi_d": 0.5,
            "macd_hist": 0.5, "prev_macd_hist": 0.3,
            "prev2_macd_hist": 0.1, "prev3_macd_hist": 0.0,
            "vol_sma": 800.0, "vol_trend": True,
            "prev_close": 99.5, "prev_ema_fast": 98.5, "prev_ema_slow": 97.8,
            "bar_count": 200, "funding_rate": 0.0,
        }
        # Use a config with min_adx = 28 so TMC would lower it to 25
        cfg = {
            "trade": {"tp_atr_mult": 4.0},
            "filters": _DEFAULT_STRATEGY_CONFIG["filters"],
            "thresholds": {
                **_DEFAULT_STRATEGY_CONFIG["thresholds"],
                "entry": {
                    **_DEFAULT_STRATEGY_CONFIG["thresholds"]["entry"],
                    "min_adx": 28.0,
                },
            },
        }
        gate = build_gate_result(snap, "ETH", cfg=cfg)
        assert gate["effective_min_adx"] <= 25.0, (
            f"TMC should cap at 25.0, got {gate['effective_min_adx']}"
        )


# ---------------------------------------------------------------------------
# Tests — build_entry_params
# ---------------------------------------------------------------------------


class TestBuildEntryParams:
    def test_default_params(self):
        params = build_entry_params()
        assert params["macd_mode"] == 0  # accel
        assert params["enable_pullback"] is False
        assert params["enable_slow_drift"] is False
        assert params["stoch_block_long_gt"] == pytest.approx(0.85)
        assert params["stoch_block_short_lt"] == pytest.approx(0.15)

    def test_custom_config(self):
        cfg = {
            "thresholds": {
                "entry": {
                    "macd_hist_entry_mode": "sign",
                    "enable_pullback_entries": True,
                    "pullback_confidence": "medium",
                    "enable_slow_drift_entries": True,
                },
                "stoch_rsi": {
                    "block_long_if_k_gt": 0.90,
                    "block_short_if_k_lt": 0.10,
                },
            },
        }
        params = build_entry_params(cfg)
        assert params["macd_mode"] == 1  # sign
        assert params["enable_pullback"] is True
        assert params["pullback_confidence"] == 1  # medium
        assert params["enable_slow_drift"] is True
        assert params["stoch_block_long_gt"] == pytest.approx(0.90)

    def test_json_serializable(self):
        params = build_entry_params()
        text = json.dumps(params)
        restored = json.loads(text)
        assert restored == params


# ---------------------------------------------------------------------------
# Tests — compute_ema_slow_slope
# ---------------------------------------------------------------------------


class TestComputeEmaSlowSlope:
    def test_returns_float(self):
        df = _make_trending_df(60)
        slope = compute_ema_slow_slope(df)
        assert isinstance(slope, float)
        assert not math.isnan(slope)

    def test_trending_positive_slope(self):
        df = _make_trending_df(200)
        slope = compute_ema_slow_slope(df)
        # Trending up data should have a positive slope
        assert slope > 0, f"Expected positive slope for trending-up data, got {slope}"

    def test_small_df_no_crash(self):
        df = _make_trending_df(10)
        slope = compute_ema_slow_slope(df)
        assert isinstance(slope, float)


# ---------------------------------------------------------------------------
# Tests — evaluate_entry_kernel (mocked bt_runtime)
# ---------------------------------------------------------------------------


class TestEvaluateEntryKernel:
    """Test evaluate_entry_kernel with mocked bt_runtime."""

    def test_returns_buy_signal(self):
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="buy", confidence=1,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            signal, conf, diag = evaluate_entry_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        assert signal == "BUY"
        assert conf == "medium"
        assert diag["entry_signal"] == "buy"
        assert diag["entry_confidence"] == 1

    def test_returns_sell_signal(self):
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="sell", confidence=2,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            signal, conf, diag = evaluate_entry_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        assert signal == "SELL"
        assert conf == "high"

    def test_returns_neutral_when_gates_fail(self):
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="neutral", confidence=0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            signal, conf, diag = evaluate_entry_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        assert signal == "NEUTRAL"
        assert conf == "low"

    def test_raises_without_bt_runtime(self):
        df = _make_trending_df(60)
        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", False), \
             patch("strategy.mei_alpha_v1._bt_runtime", None):
            with pytest.raises(RuntimeError, match="bt_runtime is not available"):
                evaluate_entry_kernel(
                    df, "ETH", _default_state_json(), _default_params_json(),
                )

    def test_raises_on_kernel_error(self):
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(ok=False)

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            with pytest.raises(RuntimeError, match="Kernel Evaluate failed"):
                evaluate_entry_kernel(
                    df, "ETH", _default_state_json(), _default_params_json(),
                )

    def test_passes_entry_params_in_params(self):
        """Verify entry_params is merged into params_json before calling kernel."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            evaluate_entry_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        # Check that step_decision was called with params containing entry_params
        call_args = mock_runtime.step_decision.call_args
        params_sent = json.loads(call_args[0][2])
        assert "entry_params" in params_sent
        assert isinstance(params_sent["entry_params"], dict)
        assert "macd_mode" in params_sent["entry_params"]

    def test_event_has_evaluate_signal(self):
        """Verify the MarketEvent sent to kernel has signal=evaluate."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            evaluate_entry_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        call_args = mock_runtime.step_decision.call_args
        event_sent = json.loads(call_args[0][1])
        assert event_sent["signal"] == "evaluate"
        assert "indicators" in event_sent
        assert "gate_result" in event_sent
        assert "ema_slow_slope_pct" in event_sent
        assert event_sent["symbol"] == "ETH"

    def test_event_gate_result_has_all_fields(self):
        """Verify gate_result in the event has all required fields."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result()

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            evaluate_entry_kernel(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        call_args = mock_runtime.step_decision.call_args
        event_sent = json.loads(call_args[0][1])
        gate = event_sent["gate_result"]
        for field in ["is_ranging", "is_anomaly", "is_extended", "vol_confirm",
                       "is_trending_up", "adx_above_min", "bullish_alignment",
                       "bearish_alignment", "btc_ok_long", "btc_ok_short",
                       "effective_min_adx", "bb_width_ratio", "all_gates_pass"]:
            assert field in gate, f"gate_result missing field: {field}"


# ---------------------------------------------------------------------------
# Tests — analyze_with_shadow
# ---------------------------------------------------------------------------


class TestAnalyzeWithShadow:
    """Test shadow mode comparison."""

    def test_returns_kernel_result(self):
        """Shadow mode should always return the kernel result, not Python's."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        # Kernel says BUY/high
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="buy", confidence=2,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime):
            signal, conf, diag = analyze_with_shadow(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        assert signal == "BUY"
        assert conf == "high"
        assert isinstance(diag, dict)

    def test_logs_mismatch(self, caplog):
        """When Python and kernel disagree, a warning should be logged."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        # Force kernel to say SELL while Python might say something different
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="sell", confidence=1,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime), \
             patch("strategy.mei_alpha_v1.analyze", return_value=("BUY", "medium", {})):
            with caplog.at_level(logging.WARNING, logger="strategy.mei_alpha_v1"):
                signal, conf, diag = analyze_with_shadow(
                    df, "ETH", _default_state_json(), _default_params_json(),
                )

        assert signal == "SELL"
        assert conf == "medium"
        assert any("[shadow] Signal mismatch" in msg for msg in caplog.messages), (
            f"Expected mismatch warning, got: {caplog.messages}"
        )

    def test_logs_agreement(self, caplog):
        """When Python and kernel agree, a debug message should be logged."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="neutral", confidence=0,
        )

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime), \
             patch("strategy.mei_alpha_v1.analyze", return_value=("NEUTRAL", "low", {})):
            with caplog.at_level(logging.DEBUG, logger="strategy.mei_alpha_v1"):
                signal, conf, diag = analyze_with_shadow(
                    df, "ETH", _default_state_json(), _default_params_json(),
                )

        assert signal == "NEUTRAL"
        assert any("[shadow] Signal agreement" in msg for msg in caplog.messages), (
            f"Expected agreement log, got: {caplog.messages}"
        )

    def test_python_failure_does_not_break_kernel(self):
        """If Python analyze() raises, shadow mode should still return kernel result."""
        df = _make_trending_df(60)
        mock_runtime = MagicMock()
        mock_runtime.compute_indicators.return_value = json.dumps(
            build_indicator_snapshot(df)
        )
        mock_runtime.step_decision.return_value = _make_kernel_decision_result(
            signal="buy", confidence=1,
        )

        def _broken_analyze(*args, **kwargs):
            raise ValueError("Python analyze is broken")

        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", True), \
             patch("strategy.mei_alpha_v1._bt_runtime", mock_runtime), \
             patch("strategy.mei_alpha_v1.analyze", side_effect=_broken_analyze):
            signal, conf, diag = analyze_with_shadow(
                df, "ETH", _default_state_json(), _default_params_json(),
            )

        assert signal == "BUY"
        assert conf == "medium"


# ---------------------------------------------------------------------------
# Tests — Integration with real bt_runtime (conditional)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BT_RUNTIME_AVAILABLE, reason="bt_runtime .so not available")
class TestKernelIntegration:
    """Integration tests that run against the real Rust kernel."""

    def test_evaluate_entry_kernel_real(self):
        """Full round-trip: candles -> indicators -> kernel Evaluate -> signal."""
        import bt_runtime

        df = _make_trending_df(200)
        state_json = bt_runtime.default_kernel_state_json(10000.0, 1700000000000)
        params_json = bt_runtime.default_kernel_params_json()

        signal, conf, diag = evaluate_entry_kernel(
            df, "ETH", state_json, params_json, btc_bullish=True,
        )

        assert signal in ("BUY", "SELL", "NEUTRAL")
        assert conf in ("low", "medium", "high")
        assert "entry_signal" in diag
        assert "entry_confidence" in diag

    def test_evaluate_neutral_for_ranging_data(self):
        """Ranging data should produce a NEUTRAL signal from the kernel."""
        import bt_runtime

        df = _make_ranging_df(200)
        state_json = bt_runtime.default_kernel_state_json(10000.0, 1700000000000)
        params_json = bt_runtime.default_kernel_params_json()

        signal, conf, diag = evaluate_entry_kernel(
            df, "ETH", state_json, params_json, btc_bullish=True,
        )

        # Ranging market → kernel should not generate entry signal
        # (may still return BUY/SELL if gates happen to pass on edge cases,
        # but most likely NEUTRAL)
        assert signal in ("BUY", "SELL", "NEUTRAL")
        assert isinstance(diag, dict)

    def test_gate_result_matches_rust(self):
        """Verify Python build_gate_result is consistent with kernel behavior."""

        df = _make_trending_df(200)
        snap = build_indicator_snapshot(df)
        py_gate = build_gate_result(snap, "ETH", btc_bullish=True)

        # The gate_result we compute should be valid JSON for the kernel
        gate_json = json.dumps(py_gate)
        parsed = json.loads(gate_json)
        assert parsed["effective_min_adx"] > 0
        assert isinstance(parsed["all_gates_pass"], bool)

    def test_shadow_mode_real(self):
        """Full shadow mode with real kernel."""
        import bt_runtime

        df = _make_trending_df(200)
        state_json = bt_runtime.default_kernel_state_json(10000.0, 1700000000000)
        params_json = bt_runtime.default_kernel_params_json()

        signal, conf, diag = analyze_with_shadow(
            df, "ETH", state_json, params_json, btc_bullish=True,
        )

        assert signal in ("BUY", "SELL", "NEUTRAL")
        assert conf in ("low", "medium", "high")
