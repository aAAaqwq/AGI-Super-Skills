from __future__ import annotations

from engine.core import _normalise_kernel_target_size


def test_normalise_kernel_target_size_prefers_notional_price():
    size = _normalise_kernel_target_size(1.5, 300.0, 200.0)
    assert size == 1.5


def test_normalise_kernel_target_size_falls_back_to_quantity():
    size = _normalise_kernel_target_size(2.25, "bad", 200.0)
    assert size == 2.25


def test_normalise_kernel_target_size_returns_none_when_invalid():
    assert _normalise_kernel_target_size("bad", "bad", "bad") is None


def test_normalise_kernel_target_size_rejects_non_positive_price():
    assert _normalise_kernel_target_size("bad", 100.0, 0.0) is None
