from __future__ import annotations

from tools.generate_config import coerce_value


def test_coerce_value_string_fields_force_str() -> None:
    assert coerce_value("interval", 123) == "123"
    assert coerce_value("macd_hist_entry_mode", "accel") == "accel"


def test_coerce_value_confidence_enum_rounding_and_clamp() -> None:
    # Numeric values are rounded and clamped into {low, medium, high}.
    assert coerce_value("entry_min_confidence", 0.0) == "low"
    assert coerce_value("entry_min_confidence", 0.49) == "low"
    assert coerce_value("entry_min_confidence", 0.50) == "medium"
    assert coerce_value("entry_min_confidence", 1.49) == "medium"
    assert coerce_value("entry_min_confidence", 1.50) == "high"
    assert coerce_value("entry_min_confidence", 2.4) == "high"
    assert coerce_value("entry_min_confidence", 3.0) == "high"
    assert coerce_value("entry_min_confidence", -1.0) == "low"

    # Valid string values are normalised to lowercase.
    assert coerce_value("entry_min_confidence", "HIGH") == "high"
    assert coerce_value("entry_min_confidence", "medium") == "medium"


def test_coerce_value_bool_rounding_threshold() -> None:
    assert coerce_value("enable_pyramiding", False) is False
    assert coerce_value("enable_pyramiding", True) is True

    # Numeric thresholding: >= 0.5 => True.
    assert coerce_value("enable_pyramiding", 0.0) is False
    assert coerce_value("enable_pyramiding", 0.49) is False
    assert coerce_value("enable_pyramiding", 0.50) is True
    assert coerce_value("enable_pyramiding", 1.0) is True
    assert coerce_value("enable_pyramiding", -1.0) is False

    # String parsing is accepted for defensive coercion.
    assert coerce_value("enable_pyramiding", "true") is True
    assert coerce_value("enable_pyramiding", "false") is False
    assert coerce_value("enable_pyramiding", "1") is True
    assert coerce_value("enable_pyramiding", "0") is False


def test_coerce_value_int_rounding_half_away_from_zero() -> None:
    assert coerce_value("ema_fast_window", 14.4) == 14
    assert coerce_value("ema_fast_window", 14.5) == 15
    assert coerce_value("ema_fast_window", 14.6) == 15
    assert coerce_value("ema_fast_window", -1.5) == -2


def test_coerce_value_default_numbers_become_float() -> None:
    # Non-special numeric fields should be emitted as floats for YAML stability.
    out = coerce_value("allocation_pct", 1)
    assert isinstance(out, float)
    assert out == 1.0

