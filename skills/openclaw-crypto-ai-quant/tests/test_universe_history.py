import sqlite3

from tools.sync_universe_history import apply_snapshot, ensure_schema


def _listings(conn: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    rows = conn.execute("SELECT symbol, first_seen_ms, last_seen_ms FROM universe_listings ORDER BY symbol").fetchall()
    return {str(sym): (int(first), int(last)) for (sym, first, last) in rows}


def test_apply_snapshot_derives_first_and_last_seen() -> None:
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)

    ts1 = 1_700_000_000_000
    apply_snapshot(conn, ts_ms=ts1, symbols=["btc", "ETH", "ETH", "  sol  ", ""])

    got1 = _listings(conn)
    assert got1 == {
        "BTC": (ts1, ts1),
        "ETH": (ts1, ts1),
        "SOL": (ts1, ts1),
    }

    ts2 = ts1 + 60_000
    apply_snapshot(conn, ts_ms=ts2, symbols=["btc", "eth", "DOGE"])

    got2 = _listings(conn)
    assert got2 == {
        "BTC": (ts1, ts2),
        "DOGE": (ts2, ts2),
        "ETH": (ts1, ts2),
        "SOL": (ts1, ts1),
    }


def test_apply_snapshot_is_order_independent() -> None:
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)

    ts1 = 1_700_000_000_000
    ts2 = ts1 + 60_000

    apply_snapshot(conn, ts_ms=ts2, symbols=["AAA"])
    apply_snapshot(conn, ts_ms=ts1, symbols=["AAA"])

    got = _listings(conn)
    assert got == {"AAA": (ts1, ts2)}


def test_apply_snapshot_is_idempotent_for_same_ts() -> None:
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)

    ts = 1_700_000_000_000
    apply_snapshot(conn, ts_ms=ts, symbols=["BTC", "ETH"])
    apply_snapshot(conn, ts_ms=ts, symbols=["BTC", "ETH"])

    (n_rows,) = conn.execute("SELECT COUNT(*) FROM universe_snapshots").fetchone()
    assert int(n_rows) == 2
