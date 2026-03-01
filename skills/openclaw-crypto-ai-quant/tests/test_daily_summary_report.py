from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tools.daily_summary_report import main


def _ts_ms(y: int, m: int, d: int, hh: int, mm: int) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=timezone.utc).timestamp() * 1000)


def _mk_trading_db(path: Path, *, utc_day: str, start_bal: float, end_bal: float) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, balance REAL, fee_usd REAL)"
        )
        con.execute(
            "INSERT INTO trades (timestamp, balance, fee_usd) VALUES (?, ?, ?)",
            (f"{utc_day}T00:10:00+00:00", float(start_bal), 0.0),
        )
        con.execute(
            "INSERT INTO trades (timestamp, balance, fee_usd) VALUES (?, ?, ?)",
            (f"{utc_day}T12:00:00+00:00", float(end_bal), 1.0),
        )
        con.commit()
    finally:
        con.close()


def _mk_registry_db(path: Path, *, utc_day: str, run_id: str, cfg_id: str) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                generated_at_ms INTEGER NOT NULL,
                run_date_utc TEXT NOT NULL,
                run_dir TEXT NOT NULL,
                git_head TEXT,
                args_json TEXT,
                created_at_ms INTEGER NOT NULL
            );
            CREATE TABLE run_configs (
                run_id TEXT NOT NULL,
                config_id TEXT NOT NULL,
                config_path TEXT NOT NULL,
                total_pnl REAL,
                max_drawdown_pct REAL,
                total_trades INTEGER,
                win_rate REAL,
                profit_factor REAL,
                total_fees REAL,
                verdict TEXT DEFAULT 'unknown',
                deployed INTEGER DEFAULT 0,
                retirement_reason TEXT,
                created_at_ms INTEGER NOT NULL,
                PRIMARY KEY (run_id, config_id)
            );
            """
        )
        con.execute(
            "INSERT INTO runs (run_id, generated_at_ms, run_date_utc, run_dir, git_head, args_json, created_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, 1_700_000_000_000, utc_day, "/tmp/run", "deadbeef", "{}", 1_700_000_000_000),
        )
        con.execute(
            "INSERT INTO run_configs (run_id, config_id, config_path, total_pnl, max_drawdown_pct, total_trades, win_rate, profit_factor, total_fees, created_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, cfg_id, "/tmp/cfg.yaml", 123.0, 0.12, 50, 0.55, 1.23, 4.0, 1_700_000_000_000),
        )
        con.commit()
    finally:
        con.close()


def test_daily_summary_report_writes_markdown(tmp_path) -> None:
    utc_day = "2026-02-10"
    artifacts = tmp_path / "artifacts"
    event_log = artifacts / "events" / "events.jsonl"
    registry_db = artifacts / "registry" / "registry.sqlite"
    paper_db = tmp_path / "paper.db"
    live_db = tmp_path / "live.db"

    artifacts.mkdir(parents=True, exist_ok=True)
    event_log.parent.mkdir(parents=True, exist_ok=True)
    registry_db.parent.mkdir(parents=True, exist_ok=True)

    paper_cfg = "c" * 64
    live_cfg = "d" * 64

    events = [
        {
            "schema": "aiq_event_v1",
            "ts_ms": _ts_ms(2026, 2, 10, 1, 0),
            "ts": "2026-02-10T01:00:00Z",
            "pid": 1,
            "mode": "paper",
            "run_id": "",
            "config_id": paper_cfg,
            "kind": "audit",
            "symbol": "BTC",
            "data": {"event": "RISK_KILL_DRAWDOWN", "level": "warn", "data": {"drawdown_pct": 10.0}},
        },
        {
            "schema": "aiq_event_v1",
            "ts_ms": _ts_ms(2026, 2, 10, 2, 0),
            "ts": "2026-02-10T02:00:00Z",
            "pid": 1,
            "mode": "paper",
            "run_id": "",
            "config_id": paper_cfg,
            "kind": "audit",
            "symbol": "BTC",
            "data": {
                "event": "RISK_KILL_SLIPPAGE",
                "level": "warn",
                "data": {"slippage_median_bps": 35.0, "threshold_median_bps": 20.0, "slippage_window_fills": 20},
            },
        },
        {
            "schema": "aiq_event_v1",
            "ts_ms": _ts_ms(2026, 2, 10, 3, 0),
            "ts": "2026-02-10T03:00:00Z",
            "pid": 1,
            "mode": "live",
            "run_id": "",
            "config_id": live_cfg,
            "kind": "audit",
            "symbol": "ETH",
            "data": {"event": "RISK_KILL_DAILY_LOSS", "level": "warn", "data": {"net_pnl_usd": -50.0}},
        },
    ]
    event_log.write_text("\n".join([json.dumps(e) for e in events]) + "\n", encoding="utf-8")

    _mk_registry_db(registry_db, utc_day=utc_day, run_id="run_x", cfg_id=paper_cfg)
    _mk_trading_db(paper_db, utc_day=utc_day, start_bal=10_000.0, end_bal=10_010.0)
    _mk_trading_db(live_db, utc_day=utc_day, start_bal=20_000.0, end_bal=19_900.0)

    rc = main(
        [
            "--artifacts-dir",
            str(artifacts),
            "--date",
            utc_day,
            "--event-log",
            str(event_log),
            "--registry-db",
            str(registry_db),
            "--paper-db",
            str(paper_db),
            "--live-db",
            str(live_db),
        ]
    )
    assert rc == 0

    out_path = artifacts / "reports" / "daily" / f"{utc_day}.md"
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert f"Daily Summary Report ({utc_day} UTC)" in text
    assert paper_cfg[:12] in text
    assert live_cfg[:12] in text
