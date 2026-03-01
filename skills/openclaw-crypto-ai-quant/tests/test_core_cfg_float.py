from __future__ import annotations

from engine.core import _finite_float_or_default


def test_finite_float_or_default_accepts_finite_values() -> None:
    assert _finite_float_or_default("12.5", 3.0) == 12.5
    assert _finite_float_or_default(7, 3.0) == 7.0


def test_finite_float_or_default_falls_back_for_non_finite() -> None:
    assert _finite_float_or_default("nan", 2.5) == 2.5
    assert _finite_float_or_default("inf", 2.5) == 2.5
    assert _finite_float_or_default("-inf", 2.5) == 2.5


def test_finite_float_or_default_falls_back_for_invalid_value() -> None:
    assert _finite_float_or_default("not-a-float", 4.0) == 4.0
