import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import tools.check_funding_rates_db as chk


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_rates (
    symbol TEXT NOT NULL,
    time INTEGER NOT NULL,
    funding_rate REAL NOT NULL,
    premium REAL,
    PRIMARY KEY (symbol, time)
);
"""


def _mk_db(tmp_path: Path) -> Path:
    db = tmp_path / "funding_rates.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(DB_SCHEMA)
        con.commit()
    finally:
        con.close()
    return db


def _insert_rows(db: Path, rows: list[tuple[str, int, float]]) -> None:
    con = sqlite3.connect(str(db))
    try:
        con.executemany(
            "INSERT OR REPLACE INTO funding_rates (symbol, time, funding_rate, premium) VALUES (?, ?, ?, NULL)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def _thresholds(**kwargs) -> chk.Thresholds:
    base = dict(
        lookback_hours=72.0,
        expected_interval_hours=1.0,
        interval_tolerance_seconds=1.0,
        max_age_warn_hours=8.0,
        max_age_fail_hours=12.0,
        max_gap_warn_hours=2.0,
        max_gap_fail_hours=4.0,
        abs_rate_warn=0.01,
        abs_rate_fail=0.02,
        delta_rate_warn=0.01,
        delta_rate_fail=0.02,
    )
    base.update(kwargs)
    return chk.Thresholds(**base)


def test_check_pass(tmp_path):
    db = _mk_db(tmp_path)
    now_ms = 1_700_000_000_000
    h = 3_600_000

    rows: list[tuple[str, int, float]] = []
    for sym in ["BTC", "ETH"]:
        # Cover the full lookback window (12h) so we do not trigger a leading gap warning.
        for i in range(0, 13):
            rows.append((sym, now_ms - (12 - i) * h, 0.001))
    _insert_rows(db, rows)

    res = chk.check_funding_rates_db(db, symbols=None, now_ms=now_ms, thresholds=_thresholds(lookback_hours=12.0))
    assert res["status"] == chk.Status.PASS
    assert res["summary"]["issues_total"] == 0
    assert res["summary"]["journal_mode"] == "wal"
    assert res["symbols"]["BTC"]["status"] == chk.Status.PASS


def test_check_warns_when_journal_mode_is_not_wal(tmp_path):
    db = tmp_path / "funding_rates.db"
    con = sqlite3.connect(str(db))
    try:
        con.executescript(DB_SCHEMA)
        con.commit()
    finally:
        con.close()

    now_ms = 1_700_000_000_000
    h = 3_600_000
    rows = [("BTC", now_ms - 2 * h, 0.001), ("BTC", now_ms - h, 0.001), ("BTC", now_ms, 0.001)]
    _insert_rows(db, rows)

    res = chk.check_funding_rates_db(
        db,
        symbols=["BTC"],
        now_ms=now_ms,
        thresholds=_thresholds(lookback_hours=4.0, max_gap_fail_hours=10.0),
    )

    assert res["status"] == chk.Status.WARN
    assert any(i["type"] == "journal_mode" and i["severity"] == chk.Status.WARN for i in res["issues"])
    assert res["summary"]["journal_mode"] == "delete"


def test_check_gap_fail(tmp_path):
    db = _mk_db(tmp_path)
    now_ms = 1_700_000_000_000
    h = 3_600_000

    # 6h gap should fail when max_gap_fail_hours=4.
    rows = [
        ("BTC", now_ms - 10 * h, 0.0),
        ("BTC", now_ms - 9 * h, 0.0),
        ("BTC", now_ms - 3 * h, 0.0),
        ("BTC", now_ms - 2 * h, 0.0),
        ("BTC", now_ms - 1 * h, 0.0),
        ("BTC", now_ms, 0.0),
    ]
    _insert_rows(db, rows)

    res = chk.check_funding_rates_db(db, symbols=["BTC"], now_ms=now_ms, thresholds=_thresholds(lookback_hours=12.0))
    assert res["status"] == chk.Status.FAIL
    assert any(i["type"] == "gap" and i["severity"] == chk.Status.FAIL for i in res["issues"])
    assert res["symbols"]["BTC"]["gaps"]


def test_check_abs_rate_warn(tmp_path):
    db = _mk_db(tmp_path)
    now_ms = 1_700_000_000_000
    h = 3_600_000

    rows = [
        ("BTC", now_ms - 2 * h, 0.0),
        ("BTC", now_ms - 1 * h, 0.015),  # warn only
        ("BTC", now_ms, 0.0),
    ]
    _insert_rows(db, rows)

    res = chk.check_funding_rates_db(
        db, symbols=["BTC"], now_ms=now_ms, thresholds=_thresholds(lookback_hours=4.0, max_gap_fail_hours=10.0)
    )
    assert res["status"] == chk.Status.WARN
    assert any(i["type"] == "abs_rate" and i["severity"] == chk.Status.WARN for i in res["issues"])


def test_check_delta_rate_fail(tmp_path):
    db = _mk_db(tmp_path)
    now_ms = 1_700_000_000_000
    h = 3_600_000

    rows = [
        ("BTC", now_ms - 2 * h, 0.0),
        ("BTC", now_ms - 1 * h, 0.03),
        ("BTC", now_ms, 0.03),
    ]
    _insert_rows(db, rows)

    res = chk.check_funding_rates_db(
        db,
        symbols=["BTC"],
        now_ms=now_ms,
        thresholds=_thresholds(abs_rate_warn=1.0, abs_rate_fail=2.0, lookback_hours=4.0, max_gap_fail_hours=10.0),
    )
    assert res["status"] == chk.Status.FAIL
    assert any(i["type"] == "delta_rate" and i["severity"] == chk.Status.FAIL for i in res["issues"])


def test_cli_json_and_exit_codes(tmp_path):
    db = _mk_db(tmp_path)
    now_ms = 1_700_000_000_000
    h = 3_600_000

    # WARN due to abs-rate.
    _insert_rows(
        db,
        [
            ("BTC", now_ms - 1 * h, 0.015),
            ("BTC", now_ms, 0.0),
        ],
    )

    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "tools/check_funding_rates_db.py",
        "--db",
        str(db),
        "--symbols",
        "BTC",
        "--lookback-hours",
        "4",
        "--max-gap-hours",
        "10",
        "--now-ms",
        str(now_ms),
    ]
    p = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    assert p.returncode == 0
    payload = json.loads(p.stdout.strip().splitlines()[-1])
    assert payload["status"] == chk.Status.WARN

    # WARN should exit non-zero when --fail-on-warn is set.
    p2 = subprocess.run(cmd + ["--fail-on-warn"], cwd=str(root), capture_output=True, text=True)
    assert p2.returncode == 1
