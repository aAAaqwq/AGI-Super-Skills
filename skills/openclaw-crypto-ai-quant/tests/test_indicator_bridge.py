"""Tests for AQC-811: IndicatorSnapshot bridge (Python candles to Rust JSON)."""

from __future__ import annotations

import json
import math
from unittest.mock import patch

import pandas as pd
import pytest

from strategy.mei_alpha_v1 import (
    _BT_RUNTIME_AVAILABLE,
    _INDICATOR_SNAPSHOT_FIELDS,
    build_indicator_snapshot,
    _build_indicator_snapshot_python,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SNAPSHOT_FIELD_NAMES = [name for name, _ in _INDICATOR_SNAPSHOT_FIELDS]


def _make_btc_df(n: int = 60, base_price: float = 95000.0) -> pd.DataFrame:
    """Create a realistic-ish BTC DataFrame with *n* candles.

    Prices drift upward with small random-looking jitter (deterministic via
    simple arithmetic so tests are reproducible).
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
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Tests — field completeness
# ---------------------------------------------------------------------------


class TestBuildIndicatorSnapshotFields:
    """Verify all expected fields are present and have the correct types."""

    def test_returns_all_fields(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)

        for name, _ in _INDICATOR_SNAPSHOT_FIELDS:
            assert name in snap, f"Missing field: {name}"

    def test_no_extra_fields(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)

        expected = set(_SNAPSHOT_FIELD_NAMES)
        actual = set(snap.keys())
        extra = actual - expected
        assert not extra, f"Unexpected extra fields: {extra}"

    def test_field_types(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)

        for name, expected_type in _INDICATOR_SNAPSHOT_FIELDS:
            val = snap[name]
            if expected_type is float:
                assert isinstance(val, (int, float)), f"{name}: expected numeric, got {type(val)}"
                # No NaN allowed
                assert not math.isnan(float(val)), f"{name} is NaN"
            elif expected_type is int:
                assert isinstance(val, int), f"{name}: expected int, got {type(val)}"
            elif expected_type is bool:
                assert isinstance(val, bool), f"{name}: expected bool, got {type(val)}"

    def test_bar_count_value(self):
        n = 60
        df = _make_btc_df(n)
        snap = build_indicator_snapshot(df)
        # Rust counts bars fed before the latest snapshot (0-indexed),
        # so bar_count should be n-1 after feeding n candles.
        assert snap["bar_count"] == n - 1

    def test_close_matches_last_row(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)
        assert snap["close"] == pytest.approx(float(df["Close"].iloc[-1]), rel=1e-9)

    def test_timestamp_matches_last_row(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)
        assert snap["t"] == int(df["Timestamp"].iloc[-1])

    def test_empty_df_raises(self):
        df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "Timestamp"])
        with pytest.raises(ValueError, match="empty"):
            build_indicator_snapshot(df)


# ---------------------------------------------------------------------------
# Tests — Rust path (conditional)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BT_RUNTIME_AVAILABLE, reason="bt_runtime .so not available")
class TestRustPath:
    """Tests that run only when the Rust bt_runtime is importable."""

    def test_rust_compute_indicators_basic(self):
        import bt_runtime

        candles = [
            {
                "t": 1700000000000 + i * 3600000,
                "open": 95000.0 + i * 10,
                "high": 95500.0 + i * 10,
                "low": 94800.0 + i * 10,
                "close": 95200.0 + i * 10,
                "volume": 100.0 + i,
            }
            for i in range(60)
        ]
        result_json = bt_runtime.compute_indicators(json.dumps(candles), "{}")
        snap = json.loads(result_json)

        # Verify it has all fields
        for name, _ in _INDICATOR_SNAPSHOT_FIELDS:
            assert name in snap, f"Rust snapshot missing field: {name}"

    def test_rust_path_called_when_available(self):
        # Patching `bt_runtime` also affects `_bt_runtime` in mei_alpha_v1
        # because they are the same module object (imported as alias).
        df = _make_btc_df(60)
        import bt_runtime

        with patch.object(bt_runtime, "compute_indicators", wraps=bt_runtime.compute_indicators) as mock_ci:
            # Re-import to get the patched version — but since the module is
            # already imported, we just call the function directly.
            snap = build_indicator_snapshot(df)
            assert mock_ci.called, "Expected Rust compute_indicators to be called"
            assert "close" in snap

    def test_rust_empty_candles_raises(self):
        import bt_runtime

        with pytest.raises(ValueError, match="empty"):
            bt_runtime.compute_indicators("[]", "{}")

    def test_rust_custom_config(self):
        import bt_runtime

        candles = [
            {
                "t": 1700000000000 + i * 3600000,
                "open": 95000.0 + i * 10,
                "high": 95500.0 + i * 10,
                "low": 94800.0 + i * 10,
                "close": 95200.0 + i * 10,
                "volume": 100.0 + i,
            }
            for i in range(60)
        ]
        config = {"ema_slow_window": 30, "ema_fast_window": 10, "atr_window": 7}
        result_json = bt_runtime.compute_indicators(json.dumps(candles), json.dumps(config))
        snap = json.loads(result_json)
        assert "ema_slow" in snap
        assert snap["close"] == pytest.approx(95790.0)


# ---------------------------------------------------------------------------
# Tests — Python fallback
# ---------------------------------------------------------------------------


class TestPythonFallback:
    """Test the pure-Python indicator computation path."""

    def test_python_fallback_returns_all_fields(self):
        df = _make_btc_df(60)
        timestamps = df["Timestamp"].values
        snap = _build_indicator_snapshot_python(df, timestamps, config=None)

        for name, _ in _INDICATOR_SNAPSHOT_FIELDS:
            assert name in snap, f"Python fallback missing field: {name}"

    def test_python_fallback_no_nan(self):
        df = _make_btc_df(60)
        timestamps = df["Timestamp"].values
        snap = _build_indicator_snapshot_python(df, timestamps, config=None)

        for name, expected_type in _INDICATOR_SNAPSHOT_FIELDS:
            val = snap[name]
            if expected_type is float:
                assert not math.isnan(float(val)), f"Python fallback {name} is NaN"

    def test_python_fallback_zero_close_keeps_bb_width_finite(self):
        df = _make_btc_df(60)
        df.loc[df.index[-1], "Close"] = 0.0
        timestamps = df["Timestamp"].values
        snap = _build_indicator_snapshot_python(df, timestamps, config=None)

        assert snap["bb_width"] == pytest.approx(0.0)
        assert snap["bb_width_avg"] > 0.0
        assert snap["bb_width_ratio"] == pytest.approx(0.0)

    def test_python_fallback_custom_config(self):
        df = _make_btc_df(60)
        timestamps = df["Timestamp"].values
        config = {"ema_slow_window": 30, "ema_fast_window": 10}
        snap = _build_indicator_snapshot_python(df, timestamps, config=config)
        assert "ema_slow" in snap
        assert isinstance(snap["ema_slow"], float)

    def test_python_fallback_used_when_rust_unavailable(self):
        """When _BT_RUNTIME_AVAILABLE is False, the Python path is used."""
        df = _make_btc_df(60)
        with patch("strategy.mei_alpha_v1._BT_RUNTIME_AVAILABLE", False):
            snap = build_indicator_snapshot(df)
            assert "close" in snap
            for name, _ in _INDICATOR_SNAPSHOT_FIELDS:
                assert name in snap, f"Fallback snap missing {name}"

    def test_python_fallback_prev_fields(self):
        df = _make_btc_df(60)
        timestamps = df["Timestamp"].values
        snap = _build_indicator_snapshot_python(df, timestamps, config=None)

        # prev_close should match second-to-last row
        assert snap["prev_close"] == pytest.approx(float(df["Close"].iloc[-2]))

    def test_python_fallback_vol_trend_is_bool(self):
        df = _make_btc_df(60)
        timestamps = df["Timestamp"].values
        snap = _build_indicator_snapshot_python(df, timestamps, config=None)
        assert isinstance(snap["vol_trend"], bool)

    def test_python_fallback_small_df(self):
        """Minimum viable DataFrame for ta library (needs >= 2*adx_window + 1 bars)."""
        # ta's ADXIndicator internally needs 2*window rows for its smoothing.
        # With default adx_window=14, we need ~30 bars to avoid IndexError.
        df = _make_btc_df(30)
        timestamps = df["Timestamp"].values
        snap = _build_indicator_snapshot_python(df, timestamps, config=None)
        for name, _ in _INDICATOR_SNAPSHOT_FIELDS:
            assert name in snap, f"Small DF missing field: {name}"


# ---------------------------------------------------------------------------
# Tests — JSON round-trip
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    """Verify the snapshot serialises and deserialises cleanly."""

    def test_json_serializable(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)
        # Should not raise
        text = json.dumps(snap)
        restored = json.loads(text)
        assert restored == snap

    def test_funding_rate_is_zero(self):
        df = _make_btc_df(60)
        snap = build_indicator_snapshot(df)
        assert snap["funding_rate"] == 0.0


# ---------------------------------------------------------------------------
# Tests — cross-validation (Rust vs Python)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _BT_RUNTIME_AVAILABLE, reason="bt_runtime not available")
class TestCrossValidation:
    def test_rust_vs_python_snapshot_agreement(self):
        """Verify Rust and Python paths produce similar results for same input."""
        df = _make_btc_df(200)  # enough warmup for convergence
        timestamps = df["Timestamp"].values

        # Rust path
        rust_snap = build_indicator_snapshot(df)

        # Python fallback (forced)
        py_snap = _build_indicator_snapshot_python(df, timestamps, config=None)

        # Fields that should be exact
        assert rust_snap["close"] == py_snap["close"]
        assert rust_snap["t"] == py_snap["t"]
        assert rust_snap["bar_count"] == py_snap["bar_count"]
        assert rust_snap["funding_rate"] == py_snap["funding_rate"]

        # Indicator fields should be close after warmup
        # (EMA uses incremental vs rolling, so not exact)
        for field in ["ema_slow", "ema_fast", "rsi", "atr", "adx", "macd_hist", "bb_width", "vol_sma"]:
            assert rust_snap[field] == pytest.approx(py_snap[field], rel=0.05), (
                f"{field}: rust={rust_snap[field]}, python={py_snap[field]}"
            )
