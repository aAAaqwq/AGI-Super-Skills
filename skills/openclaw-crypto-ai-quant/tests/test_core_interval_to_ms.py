from engine.core import _interval_to_ms


def test_interval_to_ms_empty_defaults_to_one_hour():
    assert _interval_to_ms("") == 60 * 60 * 1000


def test_interval_to_ms_invalid_returns_zero():
    assert _interval_to_ms("not-an-interval") == 0


def test_interval_to_ms_valid_minutes_and_hours():
    assert _interval_to_ms("3m") == 3 * 60 * 1000
    assert _interval_to_ms("1h") == 60 * 60 * 1000
