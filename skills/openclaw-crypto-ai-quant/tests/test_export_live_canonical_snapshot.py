from __future__ import annotations

import sqlite3

import pytest

import tools.export_live_canonical_snapshot as export_snapshot


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    return con


def test_max_id_returns_latest_id_for_valid_table() -> None:
    con = _conn()
    try:
        con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, value TEXT)")
        con.executemany("INSERT INTO trades(id, value) VALUES (?, ?)", [(1, "a"), (7, "b"), (3, "c")])
        con.commit()
        assert export_snapshot._max_id(con, "trades") == 7
    finally:
        con.close()


def test_max_id_returns_none_for_missing_table() -> None:
    con = _conn()
    try:
        assert export_snapshot._max_id(con, "missing_table") is None
    finally:
        con.close()


def test_max_id_rejects_invalid_identifier() -> None:
    con = _conn()
    try:
        con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY)")
        con.commit()
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            export_snapshot._max_id(con, "trades; DROP TABLE trades;")
    finally:
        con.close()
