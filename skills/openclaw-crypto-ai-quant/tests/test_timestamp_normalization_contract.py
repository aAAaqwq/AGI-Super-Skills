import datetime

from engine import oms


def test_coerce_ts_ms_accepts_naive_and_utc_strings() -> None:
    # Naive datetime should be treated as UTC.
    naive = datetime.datetime(2026, 1, 2, 3, 4, 5)
    expected_naive = int(naive.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert oms._coerce_ts_ms(naive) == expected_naive

    # ISO strings with Z are parsed as UTC.
    assert oms._coerce_ts_ms("2026-01-02T03:04:05Z") == expected_naive


def test_coerce_ts_ms_distinguishes_ms_and_seconds() -> None:
    seconds = 1_700_000_000
    ms = 1_700_000_000_000

    assert oms._coerce_ts_ms(seconds) == seconds * 1000
    assert oms._coerce_ts_ms(ms) == ms


def test_coerce_ts_ms_keeps_historical_epoch_ms_as_ms() -> None:
    # 2000-01-01T00:00:00Z in milliseconds.
    historical_ms = 946_684_800_000
    assert oms._coerce_ts_ms(historical_ms) == historical_ms


def test_coerce_ts_ms_handles_invalid_values() -> None:
    assert oms._coerce_ts_ms(None) is None
    assert oms._coerce_ts_ms("") is None
    assert oms._coerce_ts_ms("not-a-timestamp") is None
    assert oms._coerce_ts_ms(float("inf")) is None
