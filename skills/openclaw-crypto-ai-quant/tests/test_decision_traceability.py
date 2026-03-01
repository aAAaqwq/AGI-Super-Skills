"""Tests for decision traceability schema and helpers (AQC-801).

Verifies that the new tables (decision_events, decision_context,
gate_evaluations, decision_lineage) are created correctly, and that
the helper functions (create_decision_event, save_decision_context,
save_gate_evaluation, link_decision_to_trade, create_lineage,
complete_lineage) work end-to-end.
"""

from __future__ import annotations

import sqlite3
import sys
import time
import types

import pytest


def _stub_missing_modules():
    """Insert stub modules so that ``strategy.mei_alpha_v1`` can be imported
    even when heavy optional dependencies (websocket-client, ta, hyperliquid
    SDK, etc.) are not installed in the test environment.

    Returns a list of module names that were stubbed so the caller can
    clean them up after the test.
    """
    stubbed: list[str] = []

    # Packages that mei_alpha_v1.py (or its transitive imports) need at
    # import-time but that may not be available in a lightweight CI image.
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
    ]

    for name in optional_packages:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            # Give common callables so attribute access doesn't blow up.
            mod.__dict__.setdefault("send_openclaw_message", lambda *a, **kw: None)
            mod.__dict__.setdefault("ShadowReport", type("ShadowReport", (), {}))
            mod.__dict__.setdefault("emit_event", lambda *a, **kw: None)
            sys.modules[name] = mod
            stubbed.append(name)

    return stubbed


@pytest.fixture()
def strategy(tmp_path, monkeypatch):
    """Import strategy module with DB_PATH pointed at a temp database.

    Heavy third-party deps are stubbed so the module loads without them.
    """
    db_path = str(tmp_path / "test_trading_engine.db")
    monkeypatch.setenv("AI_QUANT_DB_PATH", db_path)

    stubbed = _stub_missing_modules()

    # If already imported, force reload with new DB_PATH.
    mod_name = "strategy.mei_alpha_v1"
    already_loaded = mod_name in sys.modules
    if already_loaded:
        mod = sys.modules[mod_name]
        monkeypatch.setattr(mod, "DB_PATH", db_path)
    else:
        import strategy.mei_alpha_v1 as mod  # type: ignore[import-untyped]
        monkeypatch.setattr(mod, "DB_PATH", db_path)

    mod.ensure_db()

    yield mod

    # Clean up stubs (best-effort; monkeypatch handles setattr revert).
    for name in stubbed:
        sys.modules.pop(name, None)


def _connect(strategy):
    return sqlite3.connect(strategy.DB_PATH)


# ── Schema tests ────────────────────────────────────────────────────────


def test_decision_events_table_exists(strategy):
    conn = _connect(strategy)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_events'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_decision_context_table_exists(strategy):
    conn = _connect(strategy)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_context'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_gate_evaluations_table_exists(strategy):
    conn = _connect(strategy)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='gate_evaluations'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_decision_lineage_table_exists(strategy):
    conn = _connect(strategy)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_lineage'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_indexes_created(strategy):
    conn = _connect(strategy)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    indexes = {row[0] for row in cur.fetchall()}
    conn.close()

    expected = {
        "idx_de_symbol_ts",
        "idx_de_event_type",
        "idx_de_trade_id",
        "idx_ge_decision",
        "idx_dl_entry",
        "idx_dl_exit",
    }
    assert expected.issubset(indexes), f"Missing indexes: {expected - indexes}"


# ── ULID tests ──────────────────────────────────────────────────────────


def test_generate_ulid_format(strategy):
    ulid = strategy.generate_ulid()
    assert len(ulid) == 26
    # All characters should be valid Crockford base32
    valid = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert all(c in valid for c in ulid), f"Invalid ULID characters in {ulid}"


def test_generate_ulid_uniqueness(strategy):
    ulids = {strategy.generate_ulid() for _ in range(100)}
    assert len(ulids) == 100, "ULIDs should be unique"


def test_generate_ulid_time_sortable(strategy):
    ulid1 = strategy.generate_ulid()
    time.sleep(0.002)
    ulid2 = strategy.generate_ulid()
    # Time component (first 10 chars) should be monotonically non-decreasing
    assert ulid1[:10] <= ulid2[:10]


# ── Helper function tests ──────────────────────────────────────────────


def test_create_decision_event(strategy):
    decision_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
        triggered_by="schedule",
        action_taken="open_long",
        context={"rsi": 42.5, "adx": 28.0},
    )
    assert len(decision_id) == 26

    conn = _connect(strategy)
    row = conn.execute(
        "SELECT symbol, event_type, status, decision_phase, triggered_by, action_taken, context_json "
        "FROM decision_events WHERE id = ?",
        (decision_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "ETH"
    assert row[1] == "entry_signal"
    assert row[2] == "executed"
    assert row[3] == "signal_generation"
    assert row[4] == "schedule"
    assert row[5] == "open_long"
    assert '"rsi"' in row[6]


def test_create_decision_event_with_parent(strategy):
    parent_id = strategy.create_decision_event(
        symbol="BTC",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
    )
    child_id = strategy.create_decision_event(
        symbol="BTC",
        event_type="gate_block",
        status="blocked",
        phase="gate_evaluation",
        parent_decision_id=parent_id,
        rejection_reason="ADX too low",
    )

    conn = _connect(strategy)
    row = conn.execute(
        "SELECT parent_decision_id, rejection_reason FROM decision_events WHERE id = ?",
        (child_id,),
    ).fetchone()
    conn.close()

    assert row[0] == parent_id
    assert row[1] == "ADX too low"


def test_save_decision_context(strategy):
    decision_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
    )

    strategy.save_decision_context(
        decision_id=decision_id,
        symbol="ETH",
        indicators={
            "price": 2500.0,
            "rsi": 42.5,
            "adx": 28.0,
            "adx_slope": 1.2,
            "macd_hist": 0.5,
            "ema_fast": 2480.0,
            "ema_slow": 2450.0,
            "atr": 35.0,
        },
        thresholds={
            "rsi_entry_threshold": 40.0,
            "min_adx_threshold": 25.0,
            "sl_price": 2430.0,
            "tp_price": 2600.0,
        },
        gates={
            "gate_ranging": 0,
            "gate_anomaly": 0,
            "gate_adx": 1,
            "gate_volume": 1,
            "bullish_alignment": 1,
            "bearish_alignment": 0,
        },
    )

    conn = _connect(strategy)
    row = conn.execute(
        "SELECT price, rsi, adx, sl_price, gate_adx, bullish_alignment "
        "FROM decision_context WHERE decision_id = ?",
        (decision_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == pytest.approx(2500.0)
    assert row[1] == pytest.approx(42.5)
    assert row[2] == pytest.approx(28.0)
    assert row[3] == pytest.approx(2430.0)
    assert row[4] == 1
    assert row[5] == 1


def test_save_gate_evaluation(strategy):
    decision_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="gate_block",
        status="blocked",
        phase="gate_evaluation",
    )

    strategy.save_gate_evaluation(
        decision_id=decision_id,
        gate_name="adx_rising",
        gate_passed=False,
        metric_value=18.5,
        threshold_value=25.0,
        operator=">",
        explanation="ADX 18.5 below minimum 25.0",
    )
    strategy.save_gate_evaluation(
        decision_id=decision_id,
        gate_name="volume",
        gate_passed=True,
        metric_value=1500000.0,
        threshold_value=1000000.0,
        operator=">",
        explanation="Volume OK",
    )

    conn = _connect(strategy)
    rows = conn.execute(
        "SELECT gate_name, gate_passed, metric_value, threshold_value, operator, explanation "
        "FROM gate_evaluations WHERE decision_id = ? ORDER BY id",
        (decision_id,),
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0][0] == "adx_rising"
    assert rows[0][1] == 0  # False -> 0
    assert rows[0][2] == pytest.approx(18.5)
    assert rows[0][4] == ">"
    assert rows[1][0] == "volume"
    assert rows[1][1] == 1  # True -> 1


def test_link_decision_to_trade(strategy):
    decision_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="fill",
        status="executed",
        phase="execution",
    )

    # Simulate a trade_id
    strategy.link_decision_to_trade(decision_id, trade_id=42)

    conn = _connect(strategy)
    row = conn.execute(
        "SELECT trade_id FROM decision_events WHERE id = ?",
        (decision_id,),
    ).fetchone()
    conn.close()

    assert row[0] == 42


def test_create_and_complete_lineage(strategy):
    signal_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
    )
    exit_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="exit_check",
        status="executed",
        phase="execution",
    )

    lineage_rowid = strategy.create_lineage(
        signal_decision_id=signal_id,
        entry_trade_id=100,
    )
    assert lineage_rowid is not None

    strategy.complete_lineage(
        entry_trade_id=100,
        exit_decision_id=exit_id,
        exit_trade_id=101,
        exit_reason="signal_flip",
        duration_ms=3600000,
    )

    conn = _connect(strategy)
    row = conn.execute(
        "SELECT signal_decision_id, entry_trade_id, exit_decision_id, "
        "exit_trade_id, exit_reason, duration_ms "
        "FROM decision_lineage WHERE entry_trade_id = ?",
        (100,),
    ).fetchone()
    conn.close()

    assert row[0] == signal_id
    assert row[1] == 100
    assert row[2] == exit_id
    assert row[3] == 101
    assert row[4] == "signal_flip"
    assert row[5] == 3600000


# ── End-to-end integration test ─────────────────────────────────────────


def test_full_decision_lifecycle(strategy):
    """Exercise the complete decision lifecycle: signal -> gates -> fill -> lineage."""

    # 1. Entry signal decision
    signal_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
        triggered_by="schedule",
        action_taken="open_long",
        context={"signal": "LONG", "confidence": "high"},
    )

    # 2. Save indicator context
    strategy.save_decision_context(
        decision_id=signal_id,
        symbol="ETH",
        indicators={"price": 2500.0, "rsi": 42.5, "adx": 28.0, "atr": 35.0},
        thresholds={"rsi_entry_threshold": 40.0, "min_adx_threshold": 25.0},
        gates={"gate_adx": 1, "gate_volume": 1, "gate_ranging": 0},
    )

    # 3. Gate evaluations
    for gate_name, passed, metric, threshold in [
        ("adx", True, 28.0, 25.0),
        ("volume", True, 1500000.0, 1000000.0),
        ("ranging", False, 0.85, 0.80),
    ]:
        strategy.save_gate_evaluation(
            decision_id=signal_id,
            gate_name=gate_name,
            gate_passed=passed,
            metric_value=metric,
            threshold_value=threshold,
            operator=">",
        )

    # 4. Fill decision (trade executed)
    _fill_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="fill",
        status="executed",
        phase="execution",
        parent_decision_id=signal_id,
        trade_id=200,
        action_taken="open_long",
    )

    # 5. Link and create lineage
    strategy.link_decision_to_trade(signal_id, trade_id=200)
    strategy.create_lineage(signal_decision_id=signal_id, entry_trade_id=200)

    # 6. Exit decision
    exit_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="exit_check",
        status="executed",
        phase="execution",
        triggered_by="signal_flip",
        action_taken="close_short",
        trade_id=201,
    )

    # 7. Complete lineage
    strategy.complete_lineage(
        entry_trade_id=200,
        exit_decision_id=exit_id,
        exit_trade_id=201,
        exit_reason="signal_flip",
        duration_ms=7200000,
    )

    # Verify full chain
    conn = _connect(strategy)

    # Decision events chain
    events = conn.execute(
        "SELECT id, event_type, status FROM decision_events ORDER BY timestamp_ms"
    ).fetchall()
    assert len(events) == 3  # signal, fill, exit

    # Context snapshot
    ctx = conn.execute(
        "SELECT price, rsi, gate_adx FROM decision_context WHERE decision_id = ?",
        (signal_id,),
    ).fetchone()
    assert ctx[0] == pytest.approx(2500.0)
    assert ctx[2] == 1

    # Gate evaluations
    gates = conn.execute(
        "SELECT gate_name, gate_passed FROM gate_evaluations WHERE decision_id = ? ORDER BY id",
        (signal_id,),
    ).fetchall()
    assert len(gates) == 3

    # Lineage
    lineage = conn.execute(
        "SELECT signal_decision_id, exit_reason, duration_ms FROM decision_lineage WHERE entry_trade_id = ?",
        (200,),
    ).fetchone()
    assert lineage[0] == signal_id
    assert lineage[1] == "signal_flip"
    assert lineage[2] == 7200000

    conn.close()


# ── get_decision_chain tests (AQC-804) ──────────────────────────────────


def test_get_decision_chain_returns_chain_for_lineage(strategy):
    """Create a signal + lineage and verify get_decision_chain returns the event."""
    signal_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
        triggered_by="schedule",
        action_taken="open_long",
    )
    strategy.link_decision_to_trade(signal_id, trade_id=300)
    strategy.create_lineage(signal_decision_id=signal_id, entry_trade_id=300)

    chain = strategy.get_decision_chain(300)
    assert len(chain) >= 1
    ids_in_chain = {e["id"] for e in chain}
    assert signal_id in ids_in_chain
    # Verify chronological ordering
    timestamps = [e["timestamp_ms"] for e in chain]
    assert timestamps == sorted(timestamps)


def test_get_decision_chain_full_lifecycle(strategy):
    """Entry signal -> fill -> exit decision -> exit fill: full chain."""
    # 1. Entry signal
    signal_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="entry_signal",
        status="executed",
        phase="signal_generation",
        triggered_by="schedule",
        action_taken="open_long",
    )
    strategy.link_decision_to_trade(signal_id, trade_id=400)
    strategy.create_lineage(signal_decision_id=signal_id, entry_trade_id=400)

    # 2. Fill event (entry)
    fill_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="fill",
        status="executed",
        phase="execution",
        parent_decision_id=signal_id,
        trade_id=400,
        action_taken="open_long",
    )

    # 3. Exit decision
    exit_id = strategy.create_decision_event(
        symbol="ETH",
        event_type="exit_check",
        status="executed",
        phase="execution",
        triggered_by="stop_loss",
        action_taken="close",
        trade_id=401,
    )

    # 4. Complete lineage
    strategy.complete_lineage(
        entry_trade_id=400,
        exit_decision_id=exit_id,
        exit_trade_id=401,
        exit_reason="stop_loss",
        duration_ms=5000,
    )

    chain = strategy.get_decision_chain(400)
    ids_in_chain = {e["id"] for e in chain}

    # All three decision events should be in the chain.
    assert signal_id in ids_in_chain
    assert fill_id in ids_in_chain
    assert exit_id in ids_in_chain

    # Verify chronological ordering
    timestamps = [e["timestamp_ms"] for e in chain]
    assert timestamps == sorted(timestamps)

    # Also queryable via exit_trade_id
    chain_via_exit = strategy.get_decision_chain(401)
    exit_ids = {e["id"] for e in chain_via_exit}
    assert exit_id in exit_ids


def test_get_decision_chain_nonexistent_trade(strategy):
    """get_decision_chain returns empty list for a trade_id that doesn't exist."""
    chain = strategy.get_decision_chain(999999)
    assert chain == []
