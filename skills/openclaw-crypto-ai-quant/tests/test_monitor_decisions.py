"""Tests for decision trace API endpoints in monitor (AQC-805).

Verifies the four new endpoints:
  - GET /api/v2/decisions          — list with filters + pagination
  - GET /api/v2/decisions/{id}     — single decision with context + gates
  - GET /api/v2/trades/{id}/decision-trace — entry-to-exit chain
  - GET /api/v2/decisions/{id}/gates — gate evaluations for a decision
"""

from __future__ import annotations

import json
import sqlite3
import sys
import types

import pytest

_FIXED_TS_MS = 1_700_000_000_000  # 2023-11-14T22:13:20Z — stable test anchor


def _stub_missing_modules():
    """Insert stub modules so heavy optional deps don't block import."""
    stubbed: list[str] = []
    optional_packages = [
        "websocket",
        "ta",
        "ta.momentum",
        "ta.trend",
        "ta.volatility",
        "ta.volume",
        "exchange",
        "exchange.ws",
        "exchange.meta",
        "exchange.sidecar",
        "engine",
        "engine.alerting",
        "engine.kernel_shadow_report",
        "engine.event_logger",
        "hyperliquid",
        "hyperliquid.utils",
        "hyperliquid.info",
        "hyperliquid.exchange",
        "eth_account",
        "bt_runtime",
        "heartbeat",
    ]
    for name in optional_packages:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__dict__.setdefault("send_openclaw_message", lambda *a, **kw: None)
            mod.__dict__.setdefault("ShadowReport", type("ShadowReport", (), {}))
            mod.__dict__.setdefault("emit_event", lambda *a, **kw: None)
            mod.__dict__.setdefault("parse_last_heartbeat", lambda *a, **kw: {"ok": False})
            sys.modules[name] = mod
            stubbed.append(name)
    return stubbed


@pytest.fixture()
def monitor_db(tmp_path, monkeypatch):
    """Create a temp DB with decision traceability tables and seed data.

    Returns (db_path, module) where module is monitor.server reloaded to
    point at the temp DB.
    """
    db_path = tmp_path / "trading_engine.db"
    monkeypatch.setenv("AIQ_MONITOR_PAPER_DB", str(db_path))

    stubbed = _stub_missing_modules()

    # Create the DB and schema.
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE IF NOT EXISTS decision_events (
            id TEXT PRIMARY KEY,
            timestamp_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            decision_phase TEXT NOT NULL,
            parent_decision_id TEXT,
            trade_id INTEGER,
            triggered_by TEXT,
            action_taken TEXT,
            rejection_reason TEXT,
            context_json TEXT
        );
        CREATE TABLE IF NOT EXISTS decision_context (
            decision_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            price REAL, rsi REAL, adx REAL, adx_slope REAL,
            macd_hist REAL, ema_fast REAL, ema_slow REAL, ema_macro REAL,
            bb_width_ratio REAL, stoch_k REAL, stoch_d REAL,
            atr REAL, atr_slope REAL, volume REAL, vol_sma REAL,
            rsi_entry_threshold REAL,
            min_adx_threshold REAL,
            sl_price REAL, tp_price REAL, trailing_sl REAL,
            gate_ranging INTEGER, gate_anomaly INTEGER, gate_extension INTEGER,
            gate_adx INTEGER, gate_volume INTEGER, gate_adx_rising INTEGER,
            gate_btc_alignment INTEGER,
            bullish_alignment INTEGER, bearish_alignment INTEGER,
            FOREIGN KEY (decision_id) REFERENCES decision_events(id)
        );
        CREATE TABLE IF NOT EXISTS gate_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,
            gate_name TEXT NOT NULL,
            gate_passed INTEGER NOT NULL,
            metric_value REAL,
            threshold_value REAL,
            operator TEXT,
            explanation TEXT,
            FOREIGN KEY (decision_id) REFERENCES decision_events(id)
        );
        CREATE TABLE IF NOT EXISTS decision_lineage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_decision_id TEXT,
            entry_trade_id INTEGER,
            exit_decision_id TEXT,
            exit_trade_id INTEGER,
            exit_reason TEXT,
            duration_ms INTEGER,
            FOREIGN KEY (signal_decision_id) REFERENCES decision_events(id),
            FOREIGN KEY (exit_decision_id) REFERENCES decision_events(id)
        );
        CREATE INDEX IF NOT EXISTS idx_de_symbol_ts ON decision_events(symbol, timestamp_ms);
        CREATE INDEX IF NOT EXISTS idx_de_event_type ON decision_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_de_trade_id ON decision_events(trade_id);
        CREATE INDEX IF NOT EXISTS idx_ge_decision ON gate_evaluations(decision_id);
        CREATE INDEX IF NOT EXISTS idx_dl_entry ON decision_lineage(entry_trade_id);
        CREATE INDEX IF NOT EXISTS idx_dl_exit ON decision_lineage(exit_trade_id);
    """)
    con.commit()
    con.close()

    # Import (or reload) the monitor server module.
    mod_name = "monitor.server"
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        import monitor.server as mod  # type: ignore[import-untyped]

    yield str(db_path), mod

    for name in stubbed:
        sys.modules.pop(name, None)


def _seed_decision_events(db_path: str, events: list[dict]) -> None:
    """Insert decision_events rows."""
    con = sqlite3.connect(db_path)
    for e in events:
        con.execute(
            """
            INSERT INTO decision_events
            (id, timestamp_ms, symbol, event_type, status, decision_phase,
             parent_decision_id, trade_id, triggered_by, action_taken,
             rejection_reason, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["id"],
                e["timestamp_ms"],
                e["symbol"],
                e["event_type"],
                e["status"],
                e["decision_phase"],
                e.get("parent_decision_id"),
                e.get("trade_id"),
                e.get("triggered_by"),
                e.get("action_taken"),
                e.get("rejection_reason"),
                e.get("context_json"),
            ),
        )
    con.commit()
    con.close()


def _seed_decision_context(db_path: str, rows: list[dict]) -> None:
    """Insert decision_context rows."""
    con = sqlite3.connect(db_path)
    for r in rows:
        con.execute(
            """
            INSERT INTO decision_context
            (decision_id, symbol, price, rsi, adx, atr, gate_adx, gate_volume,
             bullish_alignment, bearish_alignment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["decision_id"],
                r["symbol"],
                r.get("price"),
                r.get("rsi"),
                r.get("adx"),
                r.get("atr"),
                r.get("gate_adx"),
                r.get("gate_volume"),
                r.get("bullish_alignment"),
                r.get("bearish_alignment"),
            ),
        )
    con.commit()
    con.close()


def _seed_gate_evaluations(db_path: str, rows: list[dict]) -> None:
    """Insert gate_evaluations rows."""
    con = sqlite3.connect(db_path)
    for r in rows:
        con.execute(
            """
            INSERT INTO gate_evaluations
            (decision_id, gate_name, gate_passed, metric_value, threshold_value, operator, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["decision_id"],
                r["gate_name"],
                r["gate_passed"],
                r.get("metric_value"),
                r.get("threshold_value"),
                r.get("operator"),
                r.get("explanation"),
            ),
        )
    con.commit()
    con.close()


def _seed_lineage(db_path: str, rows: list[dict]) -> None:
    """Insert decision_lineage rows."""
    con = sqlite3.connect(db_path)
    for r in rows:
        con.execute(
            """
            INSERT INTO decision_lineage
            (signal_decision_id, entry_trade_id, exit_decision_id, exit_trade_id, exit_reason, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                r.get("signal_decision_id"),
                r.get("entry_trade_id"),
                r.get("exit_decision_id"),
                r.get("exit_trade_id"),
                r.get("exit_reason"),
                r.get("duration_ms"),
            ),
        )
    con.commit()
    con.close()


# ── GET /api/v2/decisions (list) ─────────────────────────────────────────


class TestDecisionsList:
    def test_empty_table(self, monitor_db):
        db_path, mod = monitor_db
        result = mod.build_decisions_list("paper")
        assert result["data"] == []
        assert result["total"] == 0
        assert result["limit"] == 100
        assert result["offset"] == 0

    def test_list_all(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D001",
                    "timestamp_ms": now_ms - 2000,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                },
                {
                    "id": "D002",
                    "timestamp_ms": now_ms - 1000,
                    "symbol": "BTC",
                    "event_type": "gate_block",
                    "status": "blocked",
                    "decision_phase": "gate_evaluation",
                },
                {
                    "id": "D003",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "fill",
                    "status": "executed",
                    "decision_phase": "execution",
                },
            ],
        )
        result = mod.build_decisions_list("paper")
        assert result["total"] == 3
        assert len(result["data"]) == 3
        # Results ordered by timestamp_ms DESC.
        assert result["data"][0]["id"] == "D003"
        assert result["data"][2]["id"] == "D001"

    def test_filter_by_symbol(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D001",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                },
                {
                    "id": "D002",
                    "timestamp_ms": now_ms,
                    "symbol": "BTC",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                },
            ],
        )
        result = mod.build_decisions_list("paper", symbol="ETH")
        assert result["total"] == 1
        assert result["data"][0]["symbol"] == "ETH"

    def test_filter_by_time_window(self, monitor_db):
        db_path, mod = monitor_db
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D001",
                    "timestamp_ms": 1000,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                },
                {
                    "id": "D002",
                    "timestamp_ms": 2000,
                    "symbol": "ETH",
                    "event_type": "fill",
                    "status": "executed",
                    "decision_phase": "execution",
                },
                {
                    "id": "D003",
                    "timestamp_ms": 3000,
                    "symbol": "ETH",
                    "event_type": "exit_check",
                    "status": "executed",
                    "decision_phase": "execution",
                },
            ],
        )
        result = mod.build_decisions_list("paper", start_ms=1500, end_ms=2500)
        assert result["total"] == 1
        assert result["data"][0]["id"] == "D002"

    def test_filter_by_event_type(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D001",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                },
                {
                    "id": "D002",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "gate_block",
                    "status": "blocked",
                    "decision_phase": "gate_evaluation",
                },
            ],
        )
        result = mod.build_decisions_list("paper", event_type="gate_block")
        assert result["total"] == 1
        assert result["data"][0]["event_type"] == "gate_block"

    def test_filter_by_status(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D001",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                },
                {
                    "id": "D002",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "gate_block",
                    "status": "blocked",
                    "decision_phase": "gate_evaluation",
                },
            ],
        )
        result = mod.build_decisions_list("paper", status="blocked")
        assert result["total"] == 1
        assert result["data"][0]["status"] == "blocked"

    def test_pagination(self, monitor_db):
        db_path, mod = monitor_db
        events = [
            {
                "id": f"D{i:03d}",
                "timestamp_ms": 1000 + i,
                "symbol": "ETH",
                "event_type": "entry_signal",
                "status": "executed",
                "decision_phase": "signal_generation",
            }
            for i in range(10)
        ]
        _seed_decision_events(db_path, events)

        # Page 1: limit=3, offset=0
        result = mod.build_decisions_list("paper", limit=3, offset=0)
        assert result["total"] == 10
        assert len(result["data"]) == 3
        assert result["limit"] == 3
        assert result["offset"] == 0

        # Page 2: limit=3, offset=3
        result2 = mod.build_decisions_list("paper", limit=3, offset=3)
        assert result2["total"] == 10
        assert len(result2["data"]) == 3
        # No overlap with page 1.
        ids_p1 = {r["id"] for r in result["data"]}
        ids_p2 = {r["id"] for r in result2["data"]}
        assert ids_p1.isdisjoint(ids_p2)

    def test_limit_clamped(self, monitor_db):
        db_path, mod = monitor_db
        result = mod.build_decisions_list("paper", limit=5000)
        assert result["limit"] == 1000

        result2 = mod.build_decisions_list("paper", limit=-5)
        assert result2["limit"] == 1

    def test_db_missing(self, monitor_db, monkeypatch):
        _db_path, mod = monitor_db
        monkeypatch.setenv("AIQ_MONITOR_PAPER_DB", "/nonexistent/path/db.sqlite")
        result = mod.build_decisions_list("paper")
        assert result["data"] == []
        assert result["total"] == 0
        assert result.get("error") == "db_missing"


# ── GET /api/v2/decisions/{id} (detail) ──────────────────────────────────


class TestDecisionDetail:
    def test_not_found(self, monitor_db):
        _db_path, mod = monitor_db
        result = mod.build_decision_detail("paper", "NONEXISTENT")
        assert result is None

    def test_found_with_context_and_gates(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D100",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                    "triggered_by": "schedule",
                    "action_taken": "open_long",
                    "context_json": json.dumps({"rsi": 42.5}),
                },
            ],
        )
        _seed_decision_context(
            db_path,
            [
                {
                    "decision_id": "D100",
                    "symbol": "ETH",
                    "price": 2500.0,
                    "rsi": 42.5,
                    "adx": 28.0,
                    "atr": 35.0,
                    "gate_adx": 1,
                    "gate_volume": 1,
                    "bullish_alignment": 1,
                    "bearish_alignment": 0,
                },
            ],
        )
        _seed_gate_evaluations(
            db_path,
            [
                {
                    "decision_id": "D100",
                    "gate_name": "adx",
                    "gate_passed": 1,
                    "metric_value": 28.0,
                    "threshold_value": 25.0,
                    "operator": ">",
                    "explanation": "ADX OK",
                },
                {
                    "decision_id": "D100",
                    "gate_name": "volume",
                    "gate_passed": 1,
                    "metric_value": 1500000.0,
                    "threshold_value": 1000000.0,
                    "operator": ">",
                    "explanation": "Volume OK",
                },
            ],
        )

        result = mod.build_decision_detail("paper", "D100")
        assert result is not None
        assert result["decision"]["id"] == "D100"
        assert result["decision"]["symbol"] == "ETH"
        assert result["decision"]["event_type"] == "entry_signal"
        assert len(result["context"]) == 1
        assert result["context"][0]["price"] == 2500.0
        assert len(result["gates"]) == 2
        assert result["gates"][0]["gate_name"] == "adx"
        assert result["gates"][1]["gate_name"] == "volume"

    def test_found_without_context_or_gates(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "D200",
                    "timestamp_ms": now_ms,
                    "symbol": "BTC",
                    "event_type": "fill",
                    "status": "executed",
                    "decision_phase": "execution",
                },
            ],
        )
        result = mod.build_decision_detail("paper", "D200")
        assert result is not None
        assert result["decision"]["id"] == "D200"
        assert result["context"] == []
        assert result["gates"] == []


# ── GET /api/v2/trades/{id}/decision-trace ───────────────────────────────


class TestTradeDecisionTrace:
    def test_no_lineage(self, monitor_db):
        db_path, mod = monitor_db
        result = mod.build_trade_decision_trace("paper", 999)
        assert result["chain"] == []
        assert result["lineage"] is None

    def test_full_chain(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS

        # Signal -> Fill (entry) -> Exit decision
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "SIG01",
                    "timestamp_ms": now_ms - 3000,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                    "trade_id": 500,
                },
                {
                    "id": "FILL01",
                    "timestamp_ms": now_ms - 2000,
                    "symbol": "ETH",
                    "event_type": "fill",
                    "status": "executed",
                    "decision_phase": "execution",
                    "trade_id": 500,
                    "parent_decision_id": "SIG01",
                },
                {
                    "id": "EXIT01",
                    "timestamp_ms": now_ms - 1000,
                    "symbol": "ETH",
                    "event_type": "exit_check",
                    "status": "executed",
                    "decision_phase": "execution",
                    "trade_id": 501,
                },
            ],
        )
        _seed_lineage(
            db_path,
            [
                {
                    "signal_decision_id": "SIG01",
                    "entry_trade_id": 500,
                    "exit_decision_id": "EXIT01",
                    "exit_trade_id": 501,
                    "exit_reason": "stop_loss",
                    "duration_ms": 2000,
                },
            ],
        )

        result = mod.build_trade_decision_trace("paper", 500)
        assert result["lineage"] is not None
        assert result["lineage"]["entry_trade_id"] == 500
        assert result["lineage"]["exit_trade_id"] == 501
        assert result["lineage"]["exit_reason"] == "stop_loss"
        assert result["lineage"]["duration_ms"] == 2000

        # Chain should contain all 3 decision events in chronological order.
        assert len(result["chain"]) == 3
        chain_ids = [e["id"] for e in result["chain"]]
        assert chain_ids == ["SIG01", "FILL01", "EXIT01"]

    def test_chain_via_exit_trade(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "SIG02",
                    "timestamp_ms": now_ms - 2000,
                    "symbol": "BTC",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "signal_generation",
                    "trade_id": 600,
                },
                {
                    "id": "EXIT02",
                    "timestamp_ms": now_ms - 1000,
                    "symbol": "BTC",
                    "event_type": "exit_check",
                    "status": "executed",
                    "decision_phase": "execution",
                    "trade_id": 601,
                },
            ],
        )
        _seed_lineage(
            db_path,
            [
                {
                    "signal_decision_id": "SIG02",
                    "entry_trade_id": 600,
                    "exit_decision_id": "EXIT02",
                    "exit_trade_id": 601,
                    "exit_reason": "signal_flip",
                    "duration_ms": 1000,
                },
            ],
        )

        # Query via exit trade_id.
        result = mod.build_trade_decision_trace("paper", 601)
        assert result["lineage"] is not None
        chain_ids = {e["id"] for e in result["chain"]}
        assert "EXIT02" in chain_ids

    def test_db_missing(self, monitor_db, monkeypatch):
        _db_path, mod = monitor_db
        monkeypatch.setenv("AIQ_MONITOR_PAPER_DB", "/nonexistent/path/db.sqlite")
        result = mod.build_trade_decision_trace("paper", 100)
        assert result["chain"] == []
        assert result.get("error") == "db_missing"


# ── GET /api/v2/decisions/{id}/gates ─────────────────────────────────────


class TestDecisionGates:
    def test_not_found(self, monitor_db):
        _db_path, mod = monitor_db
        result = mod.build_decision_gates("paper", "NONEXISTENT")
        assert result is None

    def test_gates_returned(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "G001",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "gate_block",
                    "status": "blocked",
                    "decision_phase": "gate_evaluation",
                },
            ],
        )
        _seed_gate_evaluations(
            db_path,
            [
                {
                    "decision_id": "G001",
                    "gate_name": "adx_rising",
                    "gate_passed": 0,
                    "metric_value": 18.5,
                    "threshold_value": 25.0,
                    "operator": ">",
                    "explanation": "ADX too low",
                },
                {
                    "decision_id": "G001",
                    "gate_name": "volume",
                    "gate_passed": 1,
                    "metric_value": 1500000.0,
                    "threshold_value": 1000000.0,
                    "operator": ">",
                    "explanation": "Volume OK",
                },
                {
                    "decision_id": "G001",
                    "gate_name": "ranging",
                    "gate_passed": 0,
                    "metric_value": 0.85,
                    "threshold_value": 0.80,
                    "operator": "<",
                    "explanation": "In ranging regime",
                },
            ],
        )

        result = mod.build_decision_gates("paper", "G001")
        assert result is not None
        assert len(result["gates"]) == 3
        assert result["gates"][0]["gate_name"] == "adx_rising"
        assert result["gates"][0]["gate_passed"] == 0
        assert result["gates"][1]["gate_name"] == "volume"
        assert result["gates"][1]["gate_passed"] == 1
        assert result["gates"][2]["gate_name"] == "ranging"

    def test_decision_exists_no_gates(self, monitor_db):
        db_path, mod = monitor_db
        now_ms = _FIXED_TS_MS
        _seed_decision_events(
            db_path,
            [
                {
                    "id": "G002",
                    "timestamp_ms": now_ms,
                    "symbol": "ETH",
                    "event_type": "fill",
                    "status": "executed",
                    "decision_phase": "execution",
                },
            ],
        )
        result = mod.build_decision_gates("paper", "G002")
        assert result is not None
        assert result["gates"] == []


# ── POST /api/v2/decisions/replay (AQC-806) ─────────────────────────────


def _make_step_decision_stub(
    intents: list | None = None,
    fills: list | None = None,
    gate_blocked: bool = False,
    applied_thresholds: list | None = None,
):
    """Return a callable that mimics bt_runtime.step_decision."""
    result = {
        "schema_version": 8,
        "state": {
            "schema_version": 8,
            "timestamp_ms": 0,
            "step": 1,
            "cash_usd": 10000.0,
            "positions": {},
            "last_entry_ms": {},
            "last_exit_ms": {},
            "last_close_info": {},
        },
        "intents": intents or [],
        "fills": fills or [],
        "diagnostics": {
            "schema_version": 8,
            "errors": [],
            "warnings": [],
            "intent_count": len(intents or []),
            "fill_count": len(fills or []),
            "step": 1,
            "gate_blocked": gate_blocked,
            "gate_block_reasons": [],
            "applied_thresholds": applied_thresholds or [],
        },
    }

    def _stub(_state_json: str, _event_json: str, _params_json: str) -> str:
        return json.dumps(result)

    return _stub


@pytest.fixture()
def replay_db(tmp_path, monkeypatch):
    """Create a temp DB with decision data and stub bt_runtime for replay tests.

    Returns (db_path, module, bt_runtime_stub_module).
    """
    db_path = tmp_path / "trading_engine.db"
    monkeypatch.setenv("AIQ_MONITOR_PAPER_DB", str(db_path))

    # Create a kernel state file next to the DB.
    state_path = tmp_path / "kernel_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 8,
                "timestamp_ms": 0,
                "step": 0,
                "cash_usd": 10000.0,
                "positions": {},
                "last_entry_ms": {},
                "last_exit_ms": {},
                "last_close_info": {},
            }
        )
    )

    stubbed = _stub_missing_modules()

    # Create the DB and schema.
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE IF NOT EXISTS decision_events (
            id TEXT PRIMARY KEY,
            timestamp_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            decision_phase TEXT NOT NULL,
            parent_decision_id TEXT,
            trade_id INTEGER,
            triggered_by TEXT,
            action_taken TEXT,
            rejection_reason TEXT,
            context_json TEXT
        );
        CREATE TABLE IF NOT EXISTS decision_context (
            decision_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            price REAL, rsi REAL, adx REAL, adx_slope REAL,
            macd_hist REAL, ema_fast REAL, ema_slow REAL, ema_macro REAL,
            bb_width_ratio REAL, stoch_k REAL, stoch_d REAL,
            atr REAL, atr_slope REAL, volume REAL, vol_sma REAL,
            rsi_entry_threshold REAL,
            min_adx_threshold REAL,
            sl_price REAL, tp_price REAL, trailing_sl REAL,
            gate_ranging INTEGER, gate_anomaly INTEGER, gate_extension INTEGER,
            gate_adx INTEGER, gate_volume INTEGER, gate_adx_rising INTEGER,
            gate_btc_alignment INTEGER,
            bullish_alignment INTEGER, bearish_alignment INTEGER,
            FOREIGN KEY (decision_id) REFERENCES decision_events(id)
        );
        CREATE TABLE IF NOT EXISTS gate_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,
            gate_name TEXT NOT NULL,
            gate_passed INTEGER NOT NULL,
            metric_value REAL,
            threshold_value REAL,
            operator TEXT,
            explanation TEXT,
            FOREIGN KEY (decision_id) REFERENCES decision_events(id)
        );
    """)
    con.commit()
    con.close()

    # Import (or reload) the monitor server module.
    mod_name = "monitor.server"
    if mod_name in sys.modules:
        mod = sys.modules[mod_name]
    else:
        import monitor.server as mod  # type: ignore[import-untyped]

    # Install the bt_runtime stub into the module.
    bt_stub = sys.modules.get("bt_runtime")
    if bt_stub is None:
        bt_stub = types.ModuleType("bt_runtime")
        sys.modules["bt_runtime"] = bt_stub

    yield str(db_path), mod, bt_stub

    for name in stubbed:
        sys.modules.pop(name, None)


def _seed_replay_decision(db_path: str, *, decision_id: str = "R001") -> None:
    """Insert a complete decision event with context and gates for replay."""
    now_ms = _FIXED_TS_MS
    _seed_decision_events(
        db_path,
        [
            {
                "id": decision_id,
                "timestamp_ms": now_ms,
                "symbol": "BTCUSDT",
                "event_type": "entry_signal",
                "status": "executed",
                "decision_phase": "signal_generation",
                "action_taken": "open_long",
            },
        ],
    )
    _seed_decision_context(
        db_path,
        [
            {
                "decision_id": decision_id,
                "symbol": "BTCUSDT",
                "price": 95000.0,
                "rsi": 45.2,
                "adx": 28.0,
                "atr": 1200.0,
                "gate_adx": 1,
                "gate_volume": 1,
                "bullish_alignment": 1,
                "bearish_alignment": 0,
            },
        ],
    )
    _seed_gate_evaluations(
        db_path,
        [
            {
                "decision_id": decision_id,
                "gate_name": "adx",
                "gate_passed": 1,
                "metric_value": 28.0,
                "threshold_value": 25.0,
                "operator": ">",
                "explanation": "ADX OK",
            },
            {
                "decision_id": decision_id,
                "gate_name": "volume",
                "gate_passed": 1,
                "metric_value": 5000000.0,
                "threshold_value": 3000000.0,
                "operator": ">",
                "explanation": "Volume OK",
            },
            {
                "decision_id": decision_id,
                "gate_name": "ranging",
                "gate_passed": 1,
                "metric_value": 0.5,
                "threshold_value": 0.8,
                "operator": "<",
                "explanation": "Not ranging",
            },
        ],
    )


class TestDecisionReplay:
    def test_replay_valid_decision(self, replay_db):
        db_path, mod, bt_stub = replay_db
        _seed_replay_decision(db_path)

        # Stub step_decision to return an approved result.
        intent = {
            "schema_version": 8,
            "intent_id": 1,
            "symbol": "BTCUSDT",
            "kind": "Open",
            "side": "Long",
            "quantity": 0.1,
            "price": 95000.0,
            "notional_usd": 9500.0,
            "fee_rate": 0.00045,
        }
        stub_fn = _make_step_decision_stub(
            intents=[intent],
            applied_thresholds=[
                {"name": "adx", "actual": 28.0, "threshold": 25.0, "passed": True},
                {"name": "volume", "actual": 5000000.0, "threshold": 3000000.0, "passed": True},
            ],
        )
        bt_stub.step_decision = stub_fn
        bt_stub.load_state = lambda path: json.dumps(
            {
                "schema_version": 8,
                "timestamp_ms": 0,
                "step": 0,
                "cash_usd": 10000.0,
                "positions": {},
                "last_entry_ms": {},
                "last_exit_ms": {},
                "last_close_info": {},
            }
        )
        bt_stub.default_kernel_params_json = lambda: json.dumps({"schema_version": 8})

        # Ensure module sees bt_runtime.
        orig_ok = mod._BT_RUNTIME_OK
        orig_rt = mod._bt_runtime
        mod._BT_RUNTIME_OK = True
        mod._bt_runtime = bt_stub
        try:
            result = mod.build_decision_replay("paper", "R001")
        finally:
            mod._BT_RUNTIME_OK = orig_ok
            mod._bt_runtime = orig_rt

        assert result["ok"] is True
        assert result["decision_id"] == "R001"
        assert result["original"]["event_type"] == "entry_signal"
        assert result["original"]["status"] == "executed"
        assert result["original"]["action_taken"] == "open_long"
        assert "indicators" in result["original"]
        assert len(result["original"]["gates"]) == 3

        assert len(result["replayed"]["intents"]) == 1
        assert result["replayed"]["intents"][0]["symbol"] == "BTCUSDT"
        assert "diagnostics" in result["replayed"]

        assert result["diff"]["outcome_match"] is True
        assert result["diff"]["gates_match"] is True
        assert result["diff"]["details"] == []

    def test_replay_missing_decision(self, replay_db):
        _db_path, mod, bt_stub = replay_db

        bt_stub.step_decision = _make_step_decision_stub()
        bt_stub.load_state = lambda path: "{}"
        bt_stub.default_kernel_params_json = lambda: '{"schema_version":8}'

        orig_ok = mod._BT_RUNTIME_OK
        orig_rt = mod._bt_runtime
        mod._BT_RUNTIME_OK = True
        mod._bt_runtime = bt_stub
        try:
            result = mod.build_decision_replay("paper", "NONEXISTENT")
        finally:
            mod._BT_RUNTIME_OK = orig_ok
            mod._bt_runtime = orig_rt

        assert result["ok"] is False
        assert result["error"] == "not_found"
        assert result["decision_id"] == "NONEXISTENT"

    def test_replay_without_bt_runtime(self, replay_db):
        _db_path, mod, _bt_stub = replay_db

        orig_ok = mod._BT_RUNTIME_OK
        mod._BT_RUNTIME_OK = False
        try:
            result = mod.build_decision_replay("paper", "R001")
        finally:
            mod._BT_RUNTIME_OK = orig_ok

        assert result["ok"] is False
        assert result["error"] == "bt_runtime_not_available"

    def test_replay_with_state_override(self, replay_db):
        db_path, mod, bt_stub = replay_db
        _seed_replay_decision(db_path)

        # Track the state JSON passed to step_decision.
        captured_args: list[tuple] = []

        def _capturing_step(state_json, event_json, params_json):
            captured_args.append((state_json, event_json, params_json))
            return _make_step_decision_stub()(state_json, event_json, params_json)

        bt_stub.step_decision = _capturing_step
        bt_stub.load_state = lambda path: json.dumps({"schema_version": 8})
        bt_stub.default_kernel_params_json = lambda: '{"schema_version":8}'

        custom_state = json.dumps(
            {
                "schema_version": 8,
                "timestamp_ms": 999,
                "step": 42,
                "cash_usd": 50000.0,
                "positions": {},
                "last_entry_ms": {},
                "last_exit_ms": {},
                "last_close_info": {},
            }
        )

        orig_ok = mod._BT_RUNTIME_OK
        orig_rt = mod._bt_runtime
        mod._BT_RUNTIME_OK = True
        mod._bt_runtime = bt_stub
        try:
            result = mod.build_decision_replay(
                "paper",
                "R001",
                state_override_json=custom_state,
            )
        finally:
            mod._BT_RUNTIME_OK = orig_ok
            mod._bt_runtime = orig_rt

        assert result["ok"] is True
        # Verify the custom state was passed through.
        assert len(captured_args) == 1
        passed_state = json.loads(captured_args[0][0])
        assert passed_state["cash_usd"] == 50000.0
        assert passed_state["step"] == 42

    def test_replay_diff_detects_gate_mismatch(self, replay_db):
        db_path, mod, bt_stub = replay_db
        _seed_replay_decision(db_path)

        # Stub returns a result where adx gate did NOT pass (mismatch with original).
        stub_fn = _make_step_decision_stub(
            intents=[],
            gate_blocked=True,
            applied_thresholds=[
                {"name": "adx", "actual": 22.0, "threshold": 25.0, "passed": False},
                {"name": "volume", "actual": 5000000.0, "threshold": 3000000.0, "passed": True},
            ],
        )
        bt_stub.step_decision = stub_fn
        bt_stub.load_state = lambda path: json.dumps(
            {
                "schema_version": 8,
                "timestamp_ms": 0,
                "step": 0,
                "cash_usd": 10000.0,
                "positions": {},
                "last_entry_ms": {},
                "last_exit_ms": {},
                "last_close_info": {},
            }
        )
        bt_stub.default_kernel_params_json = lambda: '{"schema_version":8}'

        orig_ok = mod._BT_RUNTIME_OK
        orig_rt = mod._bt_runtime
        mod._BT_RUNTIME_OK = True
        mod._bt_runtime = bt_stub
        try:
            result = mod.build_decision_replay("paper", "R001")
        finally:
            mod._BT_RUNTIME_OK = orig_ok
            mod._bt_runtime = orig_rt

        assert result["ok"] is True
        assert result["diff"]["gates_match"] is False
        assert result["diff"]["outcome_match"] is False
        assert len(result["diff"]["details"]) >= 1
        # Should mention gate mismatch.
        gate_detail = [d for d in result["diff"]["details"] if "adx" in d]
        assert len(gate_detail) >= 1
        # Should mention outcome mismatch.
        outcome_detail = [d for d in result["diff"]["details"] if "outcome" in d]
        assert len(outcome_detail) == 1

    def test_replay_event_json_structure(self, replay_db):
        """Verify the MarketEvent JSON sent to the kernel has correct structure."""
        db_path, mod, bt_stub = replay_db
        _seed_replay_decision(db_path)

        captured_events: list[dict] = []

        def _capturing_step(state_json, event_json, params_json):
            captured_events.append(json.loads(event_json))
            return _make_step_decision_stub()(state_json, event_json, params_json)

        bt_stub.step_decision = _capturing_step
        bt_stub.load_state = lambda path: json.dumps(
            {
                "schema_version": 8,
                "timestamp_ms": 0,
                "step": 0,
                "cash_usd": 10000.0,
                "positions": {},
                "last_entry_ms": {},
                "last_exit_ms": {},
                "last_close_info": {},
            }
        )
        bt_stub.default_kernel_params_json = lambda: '{"schema_version":8}'

        orig_ok = mod._BT_RUNTIME_OK
        orig_rt = mod._bt_runtime
        mod._BT_RUNTIME_OK = True
        mod._bt_runtime = bt_stub
        try:
            mod.build_decision_replay("paper", "R001")
        finally:
            mod._BT_RUNTIME_OK = orig_ok
            mod._bt_runtime = orig_rt

        assert len(captured_events) == 1
        ev = captured_events[0]
        assert ev["schema_version"] == 8
        assert ev["symbol"] == "BTCUSDT"
        assert ev["signal"] == "Buy"
        assert ev["price"] == 95000.0
        # entry_signal with action open_long → Buy → gate_result present, indicators absent.
        assert ev["gate_result"] is not None
        assert ev["indicators"] is None
        assert ev["gate_result"]["adx_above_min"] is True
        assert ev["gate_result"]["vol_confirm"] is True
        assert ev["gate_result"]["is_ranging"] is False
