import sqlite3
import uuid

import pytest

from engine.oms import LiveOms


def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except Exception:
        return False


def test_create_intent_generates_valid_hyperliquid_cloid(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "oms.db"
    monkeypatch.setenv("AI_QUANT_DB_PATH", str(db_path))
    monkeypatch.setenv("AI_QUANT_OMS_CLOID_PREFIX", "aiq_")

    oms = LiveOms(db_path=str(db_path))
    h = oms.create_intent(
        symbol="BTC",
        action="OPEN",
        side="BUY",
        requested_size=1.0,
        requested_notional=100.0,
        leverage=3.0,
        decision_ts=1700000000000,
        reason="test",
        confidence="high",
        entry_atr=1.0,
        meta=None,
        dedupe_open=True,
    )

    assert h.client_order_id is not None
    assert h.client_order_id.startswith("0x")
    assert len(h.client_order_id) == 34
    assert _is_hex(h.client_order_id[2:])

    b = bytes.fromhex(h.client_order_id[2:])
    assert b.startswith(b"aiq_")


def test_create_intent_dedupe_upgrades_invalid_client_order_id(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "oms.db"
    monkeypatch.setenv("AI_QUANT_DB_PATH", str(db_path))
    monkeypatch.setenv("AI_QUANT_OMS_CLOID_PREFIX", "aiq_")

    oms = LiveOms(db_path=str(db_path))
    oms.store.ensure()

    existing_id = uuid.uuid4().hex
    decision_ms = 1700000000000
    dedupe_key = f"OPEN:BTC:BUY:{decision_ms}"

    # Insert a legacy/bad row that cannot be sent to the Hyperliquid SDK as a cloid.
    oms.store.insert_intent(
        intent_id=existing_id,
        client_order_id="aiq_not_hex",
        created_ts_ms=decision_ms,
        symbol="BTC",
        action="OPEN",
        side="BUY",
        requested_size=1.0,
        requested_notional=100.0,
        entry_atr=None,
        leverage=3.0,
        decision_ts_ms=decision_ms,
        strategy_version="test",
        strategy_sha1=None,
        reason="test",
        confidence="high",
        status="NEW",
        dedupe_key=dedupe_key,
        meta_json=None,
    )

    h = oms.create_intent(
        symbol="BTC",
        action="OPEN",
        side="BUY",
        requested_size=1.0,
        requested_notional=100.0,
        leverage=3.0,
        decision_ts=decision_ms,
        reason="test",
        confidence="high",
        entry_atr=1.0,
        meta=None,
        dedupe_open=True,
    )

    assert h.duplicate is True
    assert h.intent_id == existing_id
    assert h.client_order_id is not None
    assert h.client_order_id.startswith("0x")
    assert len(h.client_order_id) == 34
    assert _is_hex(h.client_order_id[2:])

    # Verify it was upgraded in DB.
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("SELECT client_order_id FROM oms_intents WHERE intent_id = ? LIMIT 1", (existing_id,))
    row = cur.fetchone()
    con.close()
    assert row and row[0] == h.client_order_id
