from __future__ import annotations

import tools.generate_config as generate_config


def test_normalise_overrides_accepts_dict_shape() -> None:
    raw = {"trade.leverage": 3.0, "indicators.ema_fast_window": 10}
    normalised = generate_config.normalise_overrides(raw)
    assert normalised == [("trade.leverage", 3.0), ("indicators.ema_fast_window", 10)]


def test_normalise_overrides_accepts_list_shape() -> None:
    raw = [["trade.leverage", 3.0], ["indicators.ema_fast_window", 10]]
    normalised = generate_config.normalise_overrides(raw)
    assert normalised == [("trade.leverage", 3.0), ("indicators.ema_fast_window", 10)]


def test_normalise_overrides_returns_empty_for_invalid_shape() -> None:
    assert generate_config.normalise_overrides(None) == []
    assert generate_config.normalise_overrides(123) == []
