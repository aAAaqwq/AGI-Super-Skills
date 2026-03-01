from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

import tools.prune_runtime_logs as prune_runtime_logs


def _create_runtime_logs_db(path: Path, *, ts_values_ms: list[int]) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE runtime_logs (ts_ms INTEGER NOT NULL, level TEXT, message TEXT)")
        con.executemany(
            "INSERT INTO runtime_logs(ts_ms, level, message) VALUES (?, ?, ?)",
            [(int(ts), "INFO", "entry") for ts in ts_values_ms],
        )
        con.commit()
    finally:
        con.close()


def test_prune_runtime_logs_deletes_rows_older_than_keep_window(tmp_path):
    db_path = tmp_path / "runtime.db"
    now_ms = int(time.time() * 1000.0)
    old_ts = now_ms - int(2 * 86400 * 1000)
    fresh_ts = now_ms - int(5 * 60 * 1000)
    _create_runtime_logs_db(db_path, ts_values_ms=[old_ts, fresh_ts])

    rc = prune_runtime_logs.prune_runtime_logs(
        db_path=db_path,
        keep_days=1.0,
        dry_run=False,
        vacuum=False,
    )
    assert rc == 0

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT ts_ms FROM runtime_logs ORDER BY ts_ms").fetchall()
    finally:
        con.close()

    assert rows == [(fresh_ts,)]


def test_prune_runtime_logs_runs_vacuum_when_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime.db"
    now_ms = int(time.time() * 1000.0)
    old_ts = now_ms - int(2 * 86400 * 1000)
    _create_runtime_logs_db(db_path, ts_values_ms=[old_ts])

    real_connect = prune_runtime_logs.sqlite3.connect
    executed_sql: list[str] = []
    connect_timeouts: list[float] = []

    class _ConnProxy:
        def __init__(self, con: sqlite3.Connection) -> None:
            self._con = con

        def execute(self, sql: str, params=()):
            executed_sql.append(str(sql))
            return self._con.execute(sql, params)

        def commit(self):
            return self._con.commit()

        def close(self):
            return self._con.close()

    def _connect(path: str, timeout: float = prune_runtime_logs.SQLITE_TIMEOUT_S):
        connect_timeouts.append(float(timeout))
        return _ConnProxy(real_connect(path, timeout=timeout))

    monkeypatch.setattr(prune_runtime_logs.sqlite3, "connect", _connect)

    rc = prune_runtime_logs.prune_runtime_logs(
        db_path=db_path,
        keep_days=1.0,
        dry_run=False,
        vacuum=True,
    )
    assert rc == 0
    assert any(sql.strip().upper() == "VACUUM" for sql in executed_sql)
    assert connect_timeouts and all(t == prune_runtime_logs.SQLITE_TIMEOUT_S for t in connect_timeouts)
    assert any(sql.strip().upper() == "PRAGMA JOURNAL_MODE=WAL" for sql in executed_sql)
    assert any(sql.strip().upper().startswith("PRAGMA BUSY_TIMEOUT=") for sql in executed_sql)


def test_prune_runtime_logs_returns_zero_when_table_is_missing(tmp_path):
    db_path = tmp_path / "runtime.db"
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE other_table (id INTEGER PRIMARY KEY)")
        con.commit()
    finally:
        con.close()

    rc = prune_runtime_logs.prune_runtime_logs(
        db_path=db_path,
        keep_days=1.0,
        dry_run=False,
        vacuum=False,
    )
    assert rc == 0


def test_prune_runtime_logs_retries_on_lock_contention_and_succeeds(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime.db"
    now_ms = int(time.time() * 1000.0)
    old_ts = now_ms - int(2 * 86400 * 1000)
    _create_runtime_logs_db(db_path, ts_values_ms=[old_ts])

    real_connect = prune_runtime_logs.sqlite3.connect
    lock_state = {"raised": False}
    sleep_calls: list[float] = []

    class _LockOnceConnProxy:
        def __init__(self, con: sqlite3.Connection) -> None:
            self._con = con

        def execute(self, sql: str, params=()):
            stmt = str(sql).strip().upper()
            if stmt.startswith("DELETE FROM RUNTIME_LOGS") and not bool(lock_state["raised"]):
                lock_state["raised"] = True
                raise sqlite3.OperationalError("database is locked")
            return self._con.execute(sql, params)

        def commit(self):
            return self._con.commit()

        def close(self):
            return self._con.close()

    def _connect(path: str, timeout: float = prune_runtime_logs.SQLITE_TIMEOUT_S):
        return _LockOnceConnProxy(real_connect(path, timeout=timeout))

    monkeypatch.setattr(prune_runtime_logs.sqlite3, "connect", _connect)
    monkeypatch.setattr(prune_runtime_logs.time, "sleep", lambda s: sleep_calls.append(float(s)))

    rc = prune_runtime_logs.prune_runtime_logs(
        db_path=db_path,
        keep_days=1.0,
        dry_run=False,
        vacuum=False,
    )
    assert rc == 0
    assert sleep_calls

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT ts_ms FROM runtime_logs").fetchall()
    finally:
        con.close()
    assert rows == []


def test_prune_runtime_logs_raises_when_database_is_locked(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime.db"
    now_ms = int(time.time() * 1000.0)
    old_ts = now_ms - int(2 * 86400 * 1000)
    _create_runtime_logs_db(db_path, ts_values_ms=[old_ts])

    lock_con = sqlite3.connect(db_path)
    lock_con.execute("BEGIN EXCLUSIVE")

    real_connect = prune_runtime_logs.sqlite3.connect

    def _connect(path: str, timeout: float = 2.0):
        return real_connect(path, timeout=0.05)

    monkeypatch.setattr(prune_runtime_logs.sqlite3, "connect", _connect)
    monkeypatch.setattr(prune_runtime_logs, "SQLITE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(prune_runtime_logs, "LOCK_RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(prune_runtime_logs, "LOCK_RETRY_SLEEP_S", 0.0)
    monkeypatch.setattr(prune_runtime_logs.time, "sleep", lambda _s: None)

    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            prune_runtime_logs.prune_runtime_logs(
                db_path=db_path,
                keep_days=1.0,
                dry_run=False,
                vacuum=False,
            )
    finally:
        lock_con.rollback()
        lock_con.close()
