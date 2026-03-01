import sqlite3

from engine.oms import LiveOms


def test_mark_submit_unknown_makes_intent_matchable_by_time_proximity(tmp_path, monkeypatch):
    db_path = tmp_path / "oms.db"
    monkeypatch.setenv("AI_QUANT_DB_PATH", str(db_path))

    oms = LiveOms(db_path=str(db_path))
    intent = oms.create_intent(
        symbol="BTC",
        action="ADD",
        side="BUY",
        requested_size=1.0,
        requested_notional=100.0,
        leverage=3.0,
        decision_ts=1700000000000,
        reason="test",
        confidence="high",
        entry_atr=None,
        meta=None,
        dedupe_open=False,
    )

    oms.mark_submit_unknown(
        intent,
        symbol="BTC",
        side="BUY",
        order_type="market_open",
        reduce_only=False,
        requested_size=1.0,
        error="timeout",
    )

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("SELECT status, sent_ts_ms FROM oms_intents WHERE intent_id = ? LIMIT 1", (intent.intent_id,))
    row = cur.fetchone()
    con.close()
    assert row is not None
    status, sent_ts_ms = row
    assert status == "UNKNOWN"
    assert sent_ts_ms is not None and int(sent_ts_ms) > 0

    found = oms.store.find_pending_intent(
        symbol="BTC",
        action="ADD",
        side="BUY",
        t_ms=int(sent_ts_ms),
        ttl_ms=60_000,
    )
    assert found == intent.intent_id


def test_expire_old_sent_intents_expires_unknown_intents(tmp_path, monkeypatch):
    db_path = tmp_path / "oms.db"
    monkeypatch.setenv("AI_QUANT_DB_PATH", str(db_path))

    oms = LiveOms(db_path=str(db_path))
    intent = oms.create_intent(
        symbol="BTC",
        action="ADD",
        side="BUY",
        requested_size=1.0,
        requested_notional=100.0,
        leverage=3.0,
        decision_ts=1700000000000,
        reason="test",
        confidence="high",
        entry_atr=None,
        meta=None,
        dedupe_open=False,
    )
    oms.mark_submit_unknown(
        intent,
        symbol="BTC",
        side="BUY",
        order_type="market_open",
        reduce_only=False,
        requested_size=1.0,
        error="timeout",
    )

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("SELECT sent_ts_ms FROM oms_intents WHERE intent_id = ? LIMIT 1", (intent.intent_id,))
    sent_ts_ms = int(cur.fetchone()[0])
    con.close()

    n = oms.store.expire_old_sent_intents(older_than_ms=sent_ts_ms + 1)
    assert n == 1

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("SELECT status FROM oms_intents WHERE intent_id = ? LIMIT 1", (intent.intent_id,))
    status = cur.fetchone()[0]
    con.close()
    assert status == "EXPIRED"
