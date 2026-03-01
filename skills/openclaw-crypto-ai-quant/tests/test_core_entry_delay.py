from __future__ import annotations

from engine.core import ENTRY_MAX_DELAY_MS_HARD_MAX, _resolve_entry_max_delay_ms


def test_resolve_entry_max_delay_prefers_ms():
    value_ms, clamped = _resolve_entry_max_delay_ms(raw_ms="1500", raw_s="5")
    assert value_ms == 1500
    assert clamped is False


def test_resolve_entry_max_delay_uses_seconds_fallback():
    value_ms, clamped = _resolve_entry_max_delay_ms(raw_ms="0", raw_s="2.5")
    assert value_ms == 2500
    assert clamped is False


def test_resolve_entry_max_delay_clamps_to_hard_max():
    over_max = ENTRY_MAX_DELAY_MS_HARD_MAX + 1000
    value_ms, clamped = _resolve_entry_max_delay_ms(raw_ms=str(over_max), raw_s="0")
    assert value_ms == ENTRY_MAX_DELAY_MS_HARD_MAX
    assert clamped is True


def test_resolve_entry_max_delay_invalid_values_disable_guard():
    value_ms, clamped = _resolve_entry_max_delay_ms(raw_ms="not-a-number", raw_s="also-bad")
    assert value_ms == 0
    assert clamped is False


def test_resolve_entry_max_delay_non_finite_values_disable_guard():
    value_ms, clamped = _resolve_entry_max_delay_ms(raw_ms="1e309", raw_s="inf")
    assert value_ms == 0
    assert clamped is False
