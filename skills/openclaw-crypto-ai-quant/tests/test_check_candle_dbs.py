import json
import sqlite3
from pathlib import Path

from tools.check_candle_dbs import main


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    t INTEGER NOT NULL,
    t_close INTEGER,
    o REAL,
    h REAL,
    l REAL,
    c REAL,
    v REAL,
    n INTEGER,
    updated_at TEXT,
    PRIMARY KEY (symbol, interval, t)
);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_t
ON candles(symbol, interval, t);
"""


def _mk_db(tmp_path: Path, *, interval: str) -> Path:
    db = tmp_path / f"candles_{interval}.db"
    con = sqlite3.connect(str(db))
    try:
        con.executescript(DB_SCHEMA)
        con.commit()
    finally:
        con.close()
    return db


def _insert_times(db: Path, *, symbol: str, interval: str, times_ms: list[int], interval_ms: int) -> None:
    rows = [(symbol, interval, t, t + interval_ms) for t in times_ms]
    con = sqlite3.connect(str(db))
    try:
        con.executemany(
            "INSERT OR REPLACE INTO candles (symbol, interval, t, t_close) VALUES (?, ?, ?, ?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def _ceil_div(a: int, b: int) -> int:
    return -(-int(a) // int(b))


def _window_open_bounds(*, now_ms: int, interval_ms: int, grace_ms: int, lookback_ms: int) -> tuple[int, int]:
    start_open = _ceil_div(int(now_ms) - int(lookback_ms), int(interval_ms)) * int(interval_ms)
    end_open = ((int(now_ms) - int(grace_ms) - int(interval_ms)) // int(interval_ms)) * int(interval_ms)
    return int(start_open), int(end_open)


def test_ok_no_gaps(capsys, tmp_path):
    interval = "1m"
    interval_ms = 60_000
    now_ms = 1_700_000_123_456

    db = _mk_db(tmp_path, interval=interval)

    lookback_ms = 3_600_000
    grace_ms = 5_000
    start_open, end_open = _window_open_bounds(
        now_ms=now_ms,
        interval_ms=interval_ms,
        grace_ms=grace_ms,
        lookback_ms=lookback_ms,
    )

    times = list(range(start_open, end_open + interval_ms, interval_ms))
    # Also insert the currently-open candle to validate that freshness ignores a future t_close.
    current_open = (now_ms // interval_ms) * interval_ms
    if current_open not in times:
        times.append(current_open)
        times.sort()

    _insert_times(db, symbol="BTC", interval=interval, times_ms=times, interval_ms=interval_ms)

    rc = main(
        [
            "--db-glob",
            str(tmp_path / "candles_*.db"),
            "--lookback-hours",
            "1",
            "--now-ms",
            str(now_ms),
            "--gap-warn-bars",
            "1",
            "--gap-fail-bars",
            "3",
            "--missing-warn-bars",
            "1",
            "--missing-fail-bars",
            "10",
        ]
    )
    out = capsys.readouterr()

    assert rc == 0
    rep = json.loads(out.out)
    assert rep["overall_status"] == "OK"
    assert rep["dbs"][0]["status"] == "OK"

    sym = rep["dbs"][0]["intervals"][0]["symbols"][0]
    assert sym["symbol"] == "BTC"
    assert sym["status"] == "OK"
    assert sym["lookback"]["gaps"]["missing_bars"] == 0
    assert sym["lookback"]["gaps"]["max_gap_bars"] == 0

    assert "[OK]" in out.err


def test_fail_on_gap(capsys, tmp_path):
    interval = "1m"
    interval_ms = 60_000
    now_ms = 1_700_000_123_456

    db = _mk_db(tmp_path, interval=interval)

    lookback_ms = 3_600_000
    grace_ms = 5_000
    start_open, end_open = _window_open_bounds(
        now_ms=now_ms,
        interval_ms=interval_ms,
        grace_ms=grace_ms,
        lookback_ms=lookback_ms,
    )

    times = list(range(start_open, end_open + interval_ms, interval_ms))
    # Remove a single expected candle open to create a 1-bar gap.
    if len(times) >= 10:
        times.pop(len(times) // 2)

    _insert_times(db, symbol="BTC", interval=interval, times_ms=times, interval_ms=interval_ms)

    rc = main(
        [
            "--db-glob",
            str(tmp_path / "candles_*.db"),
            "--lookback-hours",
            "1",
            "--now-ms",
            str(now_ms),
            "--gap-warn-bars",
            "0",
            "--gap-fail-bars",
            "1",
            "--missing-warn-bars",
            "0",
            "--missing-fail-bars",
            "1",
        ]
    )
    out = capsys.readouterr()

    assert rc == 2
    rep = json.loads(out.out)
    assert rep["overall_status"] == "FAIL"
    assert rep["dbs"][0]["status"] == "FAIL"

    sym = rep["dbs"][0]["intervals"][0]["symbols"][0]
    assert sym["symbol"] == "BTC"
    assert sym["lookback"]["gaps"]["missing_bars"] == 1
    assert sym["lookback"]["gaps"]["max_gap_bars"] == 1
    assert sym["lookback"]["gaps"]["gap_ranges"]

    assert "[FAIL]" in out.err


def test_fail_on_staleness_without_gap_window(capsys, tmp_path):
    interval = "1h"
    interval_ms = 3_600_000
    now_ms = 1_700_000_123_456

    db = _mk_db(tmp_path, interval=interval)

    # Insert a single candle that is far behind now.
    t = now_ms - 10 * interval_ms
    _insert_times(db, symbol="ETH", interval=interval, times_ms=[t], interval_ms=interval_ms)

    # Use a lookback smaller than the interval so the expected bar window is empty.
    rc = main(
        [
            "--db-glob",
            str(tmp_path / "candles_*.db"),
            "--lookback-hours",
            "0.1",
            "--now-ms",
            str(now_ms),
            "--freshness-warn-mult",
            "2",
            "--freshness-fail-mult",
            "4",
            "--gap-fail-bars",
            "999999",
            "--missing-fail-bars",
            "999999",
        ]
    )
    out = capsys.readouterr()

    assert rc == 2
    rep = json.loads(out.out)
    assert rep["overall_status"] == "FAIL"
    assert rep["dbs"][0]["status"] == "FAIL"

    assert "[FAIL]" in out.err
