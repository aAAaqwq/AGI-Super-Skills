from __future__ import annotations

import datetime
import sqlite3


def _iso(ts: datetime.datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError("tz-aware required")
    return ts.isoformat().replace("+00:00", "Z")


def _make_db(path):
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, action TEXT, pnl REAL, fee_usd REAL, balance REAL)"
    )
    cur.execute(
        "CREATE TABLE audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, event TEXT)"
    )
    con.commit()
    con.close()


def test_gate_pass_min_trades_pf_dd_and_no_kills(tmp_path):
    db = tmp_path / "paper.db"
    _make_db(db)

    start = datetime.datetime(2026, 2, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t1 = start + datetime.timedelta(hours=1)
    t2 = start + datetime.timedelta(hours=2)

    con = sqlite3.connect(str(db))
    cur = con.cursor()
    # balance column is treated as an equity curve (best-effort).
    cur.execute("INSERT INTO trades (timestamp, action, pnl, fee_usd, balance) VALUES (?, ?, ?, ?, ?)", (_iso(t1), "CLOSE", 10.0, 1.0, 1009.0))
    cur.execute("INSERT INTO trades (timestamp, action, pnl, fee_usd, balance) VALUES (?, ?, ?, ?, ?)", (_iso(t2), "CLOSE", 6.0, 1.0, 1014.0))
    con.commit()
    con.close()

    from tools.promote_to_live import GateConfig, evaluate_paper_gates

    res = evaluate_paper_gates(
        paper_db=db,
        since_epoch_s=start.timestamp(),
        cfg=GateConfig(
            min_trades=2,
            min_hours=24.0,
            min_profit_factor=1.2,
            max_drawdown_pct=10.0,
            max_config_slippage_bps=20.0,
            max_kill_events=0,
        ),
        config_yaml_text="global:\n  trade:\n    slippage_bps: 10\n",
    )

    assert res.passed is True
    assert res.reasons == []
    assert res.metrics["close_trades"] == 2


def test_gate_fails_min_run_when_no_trades_and_short_elapsed(tmp_path):
    db = tmp_path / "paper.db"
    _make_db(db)

    start = datetime.datetime(2026, 2, 10, 0, 0, tzinfo=datetime.timezone.utc)

    from tools.promote_to_live import GateConfig, evaluate_paper_gates

    res = evaluate_paper_gates(
        paper_db=db,
        since_epoch_s=start.timestamp(),
        cfg=GateConfig(
            min_trades=1,
            min_hours=9999.0,
            min_profit_factor=0.0,
            max_drawdown_pct=999.0,
            max_config_slippage_bps=None,
            max_kill_events=0,
        ),
        config_yaml_text="global:\n  trade:\n    slippage_bps: 10\n",
    )

    assert res.passed is False
    assert any("min_run not met" in r for r in res.reasons)


def test_gate_fails_when_kill_events_present(tmp_path):
    db = tmp_path / "paper.db"
    _make_db(db)

    start = datetime.datetime(2026, 2, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t1 = start + datetime.timedelta(hours=1)

    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("INSERT INTO audit_events (timestamp, event) VALUES (?, ?)", (_iso(t1), "RISK_KILL_DRAWDOWN"))
    con.commit()
    con.close()

    from tools.promote_to_live import GateConfig, evaluate_paper_gates

    res = evaluate_paper_gates(
        paper_db=db,
        since_epoch_s=start.timestamp(),
        cfg=GateConfig(
            min_trades=0,
            min_hours=0.0,
            min_profit_factor=0.0,
            max_drawdown_pct=999.0,
            max_config_slippage_bps=None,
            max_kill_events=0,
        ),
        config_yaml_text="global:\n  trade:\n    slippage_bps: 10\n",
    )

    assert res.passed is False
    assert any("kill_events" in r for r in res.reasons)

