from __future__ import annotations

import pytest

import exchange.meta as meta


def test_meta_round_size_handles_binary_float_edge(monkeypatch):
    monkeypatch.setattr(meta, "get_sz_decimals", lambda _symbol: 2)
    assert meta.round_size("BTC", 0.29) == pytest.approx(0.29)
    assert meta.round_size("BTC", 256.03) == pytest.approx(256.03)


def test_meta_round_size_still_truncates_down(monkeypatch):
    monkeypatch.setattr(meta, "get_sz_decimals", lambda _symbol: 2)
    assert meta.round_size("BTC", 1.239) == pytest.approx(1.23)


def test_meta_round_size_zero_decimal_boundary(monkeypatch):
    monkeypatch.setattr(meta, "get_sz_decimals", lambda _symbol: 0)
    assert meta.round_size("BTC", 0.9999999999995) == pytest.approx(0.0)
