from __future__ import annotations

from pathlib import Path

import engine.oms as oms_mod


def test_oms_store_reuses_connection_in_same_thread(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "oms.db"
    store = oms_mod.OmsStore(db_path=str(db_path), timeout_s=1.0)
    store.ensure()
    store.close()

    calls = 0
    real_connect = oms_mod.sqlite3.connect

    def _counting_connect(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(oms_mod.sqlite3, "connect", _counting_connect)

    try:
        assert store.get_intent_by_dedupe_key("OPEN:ETH:BUY:1") is None
        assert store.get_intent_by_dedupe_key("OPEN:ETH:BUY:2") is None
        assert calls == 1
    finally:
        store.close()


def test_oms_store_close_releases_thread_local_connection(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "oms.db"
    store = oms_mod.OmsStore(db_path=str(db_path), timeout_s=1.0)
    store.ensure()
    store.close()

    calls = 0
    real_connect = oms_mod.sqlite3.connect

    def _counting_connect(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(oms_mod.sqlite3, "connect", _counting_connect)

    try:
        assert store.get_intent_by_dedupe_key("OPEN:ETH:BUY:1") is None
        store.close()
        assert store.get_intent_by_dedupe_key("OPEN:ETH:BUY:2") is None
        assert calls == 2
    finally:
        store.close()
