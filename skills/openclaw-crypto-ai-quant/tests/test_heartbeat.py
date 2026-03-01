import sqlite3

import monitor.heartbeat as hb


def test_safe_read_text_tail_nonexistent(tmp_path):
    p = tmp_path / "missing.log"
    assert hb._safe_read_text_tail(p) == ""


def test_safe_read_text_tail_directory(tmp_path):
    d = tmp_path / "dir"
    d.mkdir()
    # Opening a directory should fail and be caught.
    assert hb._safe_read_text_tail(d) == ""


def test_parse_last_heartbeat_missing(tmp_path):
    db_path = tmp_path / "missing.db"
    log_path = tmp_path / "missing.log"
    out = hb.parse_last_heartbeat(db_path, log_path)
    assert out["ok"] is False
    assert out["error"] == "heartbeat_missing"


def test_parse_last_heartbeat_text_log_not_found(tmp_path):
    db_path = tmp_path / "missing.db"
    log_path = tmp_path / "engine.log"
    log_path.write_text("no heartbeats here\n", encoding="utf-8")
    out = hb.parse_last_heartbeat(db_path, log_path)
    assert out["ok"] is False
    assert out["error"] == "heartbeat_not_found"


def test_parse_last_heartbeat_text_log_parsing(tmp_path):
    db_path = tmp_path / "missing.db"
    log_path = tmp_path / "engine.log"
    line = (
        "2026-02-09T00:00:00Z 🫀 engine ok wall=1.23s errors=2 symbols=50 open_pos=1 "
        "ws_connected=True ws_thread_alive=False ws_restarts=3 "
        "strategy_mode=fallback "
        "regime_gate=off regime_reason=breadth_chop "
        "slip_enabled=1 slip_n=3 slip_win=20 slip_thr_bps=5.000 slip_last_bps=10.000 slip_median_bps=7.500"
    )
    log_path.write_text(f"old line\n{line}\n", encoding="utf-8")
    out = hb.parse_last_heartbeat(db_path, log_path)
    assert out["ok"] is True
    assert out["source"] == "text_log"
    assert out["loop_s"] == 1.23
    assert out["errors"] == 2
    assert out["symbols"] == 50
    assert out["open_pos"] == 1
    assert out["ws_connected"] is True
    assert out["ws_thread_alive"] is False
    assert out["ws_restarts"] == 3
    assert out["strategy_mode"] == "fallback"
    assert out["regime_gate"] is False
    assert out["regime_reason"] == "breadth_chop"
    assert out["slip_enabled"] is True
    assert out["slip_n"] == 3
    assert out["slip_win"] == 20
    assert out["slip_thr_bps"] == 5.0
    assert out["slip_last_bps"] == 10.0
    assert out["slip_median_bps"] == 7.5


def test_parse_last_heartbeat_sqlite(tmp_path):
    db_path = tmp_path / "engine.db"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("CREATE TABLE runtime_logs (ts_ms INTEGER, message TEXT)")
        con.execute(
            "INSERT INTO runtime_logs (ts_ms, message) VALUES (?, ?)",
            (
                123,
                "🫀 engine ok loop=0.25s errors=0 symbols=3 open_pos=0 ws_connected=False ws_thread_alive=True ws_restarts=0",
            ),
        )
        con.commit()
    finally:
        con.close()

    out = hb.parse_last_heartbeat(db_path, tmp_path / "unused.log")
    assert out["ok"] is True
    assert out["source"] == "sqlite"
    assert out["ts_ms"] == 123
    assert out["loop_s"] == 0.25
    assert out["errors"] == 0
    assert out["symbols"] == 3
    assert out["open_pos"] == 0
    assert out["ws_connected"] is False
    assert out["ws_thread_alive"] is True
    assert out["ws_restarts"] == 0


def test_parse_last_heartbeat_parses_kill_and_config_id(tmp_path):
    db_path = tmp_path / "missing.db"
    log_path = tmp_path / "engine.log"
    cid = "a" * 64
    line = (
        "2026-02-09T00:00:00Z 🫀 engine ok loop=0.25s errors=0 symbols=3 open_pos=0 "
        "ws_connected=False ws_thread_alive=True ws_restarts=0 "
        "kill=close_only kill_reason=drawdown "
        "strategy_mode=primary "
        "regime_gate=on regime_reason=trend_ok "
        f"config_id={cid}"
    )
    log_path.write_text(f"{line}\n", encoding="utf-8")
    out = hb.parse_last_heartbeat(db_path, log_path)
    assert out["ok"] is True
    assert out["kill_mode"] == "close_only"
    assert out["kill_reason"] == "drawdown"
    assert out["strategy_mode"] == "primary"
    assert out["regime_gate"] is True
    assert out["regime_reason"] == "trend_ok"
    assert out["config_id"] == cid


def test_heartbeat_line_from_db_missing_table(tmp_path):
    # File exists but doesn't have runtime_logs: should fail gracefully and return None.
    db_path = tmp_path / "empty.db"
    sqlite3.connect(str(db_path)).close()
    assert hb._heartbeat_line_from_db(db_path) is None


def test_heartbeat_line_from_db_connect_fails(tmp_path):
    # A directory "exists" but cannot be opened as a SQLite file in read-only mode.
    db_path = tmp_path / "not_a_db"
    db_path.mkdir()
    assert hb._heartbeat_line_from_db(db_path) is None


def test_heartbeat_line_from_db_no_matching_row(tmp_path):
    db_path = tmp_path / "no_rows.db"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("CREATE TABLE runtime_logs (ts_ms INTEGER, message TEXT)")
        con.execute("INSERT INTO runtime_logs (ts_ms, message) VALUES (?, ?)", (1, "not a heartbeat"))
        con.commit()
    finally:
        con.close()
    assert hb._heartbeat_line_from_db(db_path) is None


def test_heartbeat_line_from_db_bad_ts_ms(tmp_path):
    # SQLite is typeless; store a non-int ts_ms to hit the except path.
    db_path = tmp_path / "bad_ts.db"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("CREATE TABLE runtime_logs (ts_ms, message TEXT)")
        con.execute("INSERT INTO runtime_logs (ts_ms, message) VALUES (?, ?)", ("nope", "🫀 engine ok loop=1.0s"))
        con.commit()
    finally:
        con.close()
    ts_ms, line = hb._heartbeat_line_from_db(db_path)  # type: ignore[assignment]
    assert ts_ms == 0
    assert "engine ok" in line.lower()
