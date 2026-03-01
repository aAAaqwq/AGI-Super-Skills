from __future__ import annotations

import threading
from types import SimpleNamespace

import live.trader as live_trader


class _FakeCursor:
    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return None


class _FakeConn:
    def __init__(self):
        self.closed = False
        self.executed_sql: list[str] = []

    def cursor(self):
        return _FakeCursor()

    def execute(self, *_args, **_kwargs):
        if _args:
            self.executed_sql.append(str(_args[0]))
        return None

    def commit(self):
        return None

    def close(self):
        self.closed = True


class _FakeExecutor:
    def account_snapshot(self, *, force: bool = False):
        return SimpleNamespace(
            account_value_usd=100.0,
            withdrawable_usd=80.0,
            total_margin_used_usd=20.0,
        )

    def get_positions(self, *, force: bool = False):
        return {}


def test_configure_live_db_connection_applies_wal_pragmas():
    conn = _FakeConn()

    live_trader._configure_live_db_connection(conn)

    assert conn.executed_sql == [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
    ]


def test_configure_live_db_connection_swallows_pragma_errors():
    class _FailingConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    live_trader._configure_live_db_connection(_FailingConn())


def test_sync_from_exchange_configures_wal(monkeypatch):
    conn = _FakeConn()
    wal_calls: list[_FakeConn] = []

    monkeypatch.setattr(live_trader.sqlite3, "connect", lambda *_args, **_kwargs: conn)
    monkeypatch.setattr(live_trader, "_configure_live_db_connection", lambda c: wal_calls.append(c))

    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    trader.executor = _FakeExecutor()
    trader.positions = {}
    trader._total_margin_used_usd = 0.0
    trader._pending_open_lock = threading.Lock()
    trader._pending_open_sent_at_s = {}
    trader._last_leverage_set = {}
    trader._prune_pending_opens = lambda: None
    trader._reconcile_position_state = lambda _open_symbols: None
    trader.upsert_position_state = lambda _sym: None

    trader.sync_from_exchange(force=True)

    assert wal_calls == [conn]
    assert conn.closed is True


def test_upsert_position_state_configures_wal(monkeypatch):
    conn = _FakeConn()
    wal_calls: list[_FakeConn] = []

    monkeypatch.setattr(live_trader.sqlite3, "connect", lambda *_args, **_kwargs: conn)
    monkeypatch.setattr(live_trader, "_configure_live_db_connection", lambda c: wal_calls.append(c))

    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    trader.positions = {
        "BTC": {
            "open_trade_id": "abc",
            "trailing_sl": None,
            "last_funding_time": 0,
            "adds_count": 0,
            "tp1_taken": 0,
            "last_add_time": 0,
            "entry_adx_threshold": 0.0,
        }
    }

    trader.upsert_position_state("BTC")

    assert wal_calls == [conn]
    assert conn.closed is True


def test_clear_position_state_configures_wal(monkeypatch):
    conn = _FakeConn()
    wal_calls: list[_FakeConn] = []

    monkeypatch.setattr(live_trader.sqlite3, "connect", lambda *_args, **_kwargs: conn)
    monkeypatch.setattr(live_trader, "_configure_live_db_connection", lambda c: wal_calls.append(c))

    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    trader.clear_position_state("BTC")

    assert wal_calls == [conn]
    assert conn.closed is True


def test_reconcile_position_state_configures_wal(monkeypatch):
    conn = _FakeConn()
    wal_calls: list[_FakeConn] = []

    monkeypatch.setattr(live_trader.sqlite3, "connect", lambda *_args, **_kwargs: conn)
    monkeypatch.setattr(live_trader, "_configure_live_db_connection", lambda c: wal_calls.append(c))

    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    trader._reconcile_position_state({"BTC"})

    assert wal_calls == [conn]
    assert conn.closed is True
