import sqlite3

from tools.flat_now import close_paper_positions, write_kill_switch_file


def test_write_kill_switch_file(tmp_path):
    p = tmp_path / "kill.txt"
    write_kill_switch_file(p, "close_only")
    assert p.exists()
    assert (p.read_text(encoding="utf-8") or "").strip() == "close_only"


def test_close_paper_positions_clears_state_and_inserts_close_trades(tmp_path):
    db_path = tmp_path / "paper.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                type TEXT,
                action TEXT,
                reason TEXT,
                balance REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE position_state (
                symbol TEXT PRIMARY KEY
            )
            """
        )
        conn.execute(
            "INSERT INTO trades (timestamp, symbol, type, action, reason, balance) VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-01-01T00:00:00Z", "BTC", "SYSTEM", "OPEN", "seed", 123.45),
        )
        conn.execute("INSERT INTO position_state (symbol) VALUES (?)", ("BTC",))
        conn.execute("INSERT INTO position_state (symbol) VALUES (?)", ("ETH",))
        conn.commit()
    finally:
        conn.close()

    n = close_paper_positions(db_path, reason="flat_now test")
    assert n == 2

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT symbol FROM position_state").fetchall()
        assert rows == []

        closes = conn.execute("SELECT symbol, type, action, reason FROM trades WHERE action='CLOSE' ORDER BY id").fetchall()
        assert len(closes) == 2
        assert {r[0] for r in closes} == {"BTC", "ETH"}
        assert all(r[1] == "SYSTEM" for r in closes)
        assert all(r[2] == "CLOSE" for r in closes)
        assert all("flat_now" in str(r[3]) for r in closes)
    finally:
        conn.close()

