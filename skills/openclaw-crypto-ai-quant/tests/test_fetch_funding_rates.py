from __future__ import annotations

import sqlite3

import tools.fetch_funding_rates as fetch_funding_rates


class _FakeInfo:
    def __init__(self, payload=None, *, exc: Exception | None = None) -> None:
        self._payload = payload if payload is not None else []
        self._exc = exc
        self.calls: list[tuple[str, int, int]] = []

    def funding_history(self, symbol: str, start_ms: int, end_ms: int):
        self.calls.append((symbol, int(start_ms), int(end_ms)))
        if self._exc is not None:
            raise self._exc
        return list(self._payload)


class _FakeInfoSequence:
    def __init__(self, steps) -> None:
        self._steps = list(steps)
        self.calls: list[tuple[str, int, int]] = []

    def funding_history(self, symbol: str, start_ms: int, end_ms: int):
        self.calls.append((symbol, int(start_ms), int(end_ms)))
        if not self._steps:
            return []
        nxt = self._steps.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return list(nxt)


class _TransientApiError(Exception):
    def __init__(self, status_code: int, msg: str = "transient") -> None:
        super().__init__(msg)
        self.status_code = int(status_code)


def _conn_with_schema() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(fetch_funding_rates.DB_SCHEMA)
    return con


def test_get_symbols_prefers_ai_quant_symbols_env(monkeypatch):
    monkeypatch.setenv("AI_QUANT_SYMBOLS", " btc, eth ,SOL ")
    assert fetch_funding_rates.get_symbols() == ["BTC", "ETH", "SOL"]


def test_get_symbols_reads_sidecar_universe_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_QUANT_SYMBOLS", raising=False)
    env_file = tmp_path / "ai-quant-universe.env"
    env_file.write_text("AI_QUANT_SIDECAR_SYMBOLS=arb, btc\n", encoding="utf-8")
    monkeypatch.setattr(fetch_funding_rates.os.path, "expanduser", lambda _: str(env_file))

    assert fetch_funding_rates.get_symbols() == ["ARB", "BTC"]


def test_get_symbols_uses_absolute_fallback_when_no_env_sources(monkeypatch):
    monkeypatch.delenv("AI_QUANT_SYMBOLS", raising=False)
    monkeypatch.setattr(fetch_funding_rates.os.path, "expanduser", lambda _: "/tmp/definitely-missing.env")
    monkeypatch.setattr(fetch_funding_rates.os.path, "isfile", lambda _: False)
    assert fetch_funding_rates.get_symbols() == ["BTC", "ETH", "SOL"]


def test_get_last_time_returns_latest_timestamp_for_symbol():
    con = _conn_with_schema()
    try:
        assert fetch_funding_rates.get_last_time(con, "BTC") is None
        con.execute(
            "INSERT INTO funding_rates (symbol, time, funding_rate, premium) VALUES (?, ?, ?, ?)",
            ("BTC", 1000, 0.001, 0.0),
        )
        con.execute(
            "INSERT INTO funding_rates (symbol, time, funding_rate, premium) VALUES (?, ?, ?, ?)",
            ("BTC", 1500, 0.002, 0.0),
        )
        con.commit()
        assert fetch_funding_rates.get_last_time(con, "BTC") == 1500
    finally:
        con.close()


def test_fetch_and_store_inserts_valid_entries_and_skips_bad_rows():
    con = _conn_with_schema()
    info = _FakeInfo(
        payload=[
            {"time": "1000", "fundingRate": "0.001", "premium": "0.002"},
            {"time": "1001", "fundingRate": "0.003"},
            {"time": "not-a-number", "fundingRate": "0.004"},
            {"fundingRate": "0.005"},
        ]
    )
    try:
        count = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 9999)
        assert count == 2

        rows = con.execute(
            "SELECT symbol, time, funding_rate, premium FROM funding_rates ORDER BY time ASC"
        ).fetchall()
        assert rows == [
            ("BTC", 1000, 0.001, 0.002),
            ("BTC", 1001, 0.003, None),
        ]
    finally:
        con.close()


def test_fetch_and_store_is_idempotent_via_insert_or_ignore():
    con = _conn_with_schema()
    info = _FakeInfo(payload=[{"time": 1000, "fundingRate": "0.001", "premium": "0.0"}])
    try:
        first = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 2000)
        second = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 2000)
        assert first == 1
        assert second == 0
        row = con.execute("SELECT COUNT(*) FROM funding_rates WHERE symbol = 'BTC'").fetchone()
        assert int(row[0] if row else 0) == 1
    finally:
        con.close()


def test_fetch_and_store_returns_zero_on_api_error():
    con = _conn_with_schema()
    info = _FakeInfo(exc=RuntimeError("boom"))
    try:
        count = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 9999)
        assert count == 0
        row = con.execute("SELECT COUNT(*) FROM funding_rates").fetchone()
        assert int(row[0] if row else 0) == 0
    finally:
        con.close()


def test_fetch_and_store_retries_transient_errors_then_succeeds(monkeypatch):
    con = _conn_with_schema()
    info = _FakeInfoSequence(
        [
            _TransientApiError(429, "rate limited"),
            _TransientApiError(503, "service unavailable"),
            [{"time": "1000", "fundingRate": "0.001"}],
        ]
    )

    sleeps: list[float] = []
    monkeypatch.setattr(fetch_funding_rates.time, "sleep", lambda s: sleeps.append(float(s)))

    try:
        count = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 9999)
        assert count == 1
        assert len(info.calls) == 3
        assert sleeps == [0.5, 1.0]
    finally:
        con.close()


def test_fetch_and_store_does_not_retry_non_retryable_error(monkeypatch):
    con = _conn_with_schema()
    info = _FakeInfo(exc=RuntimeError("invalid symbol"))

    sleeps: list[float] = []
    monkeypatch.setattr(fetch_funding_rates.time, "sleep", lambda s: sleeps.append(float(s)))

    try:
        count = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 9999)
        assert count == 0
        assert len(info.calls) == 1
        assert sleeps == []
    finally:
        con.close()


def test_fetch_and_store_does_not_retry_numeric_substring_false_positive(monkeypatch):
    con = _conn_with_schema()
    info = _FakeInfo(exc=RuntimeError("remote code 5030: permanent failure"))

    sleeps: list[float] = []
    monkeypatch.setattr(fetch_funding_rates.time, "sleep", lambda s: sleeps.append(float(s)))

    try:
        count = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 9999)
        assert count == 0
        assert len(info.calls) == 1
        assert sleeps == []
    finally:
        con.close()


def test_fetch_and_store_stops_after_retry_budget(monkeypatch):
    con = _conn_with_schema()
    info = _FakeInfoSequence([_TransientApiError(429, "rate limited")] * 5)

    sleeps: list[float] = []
    monkeypatch.setattr(fetch_funding_rates.time, "sleep", lambda s: sleeps.append(float(s)))

    try:
        count = fetch_funding_rates.fetch_and_store(info, con, "BTC", 0, 9999)
        assert count == 0
        # initial attempt + 3 retries
        assert len(info.calls) == 4
        assert sleeps == [0.5, 1.0, 2.0]
    finally:
        con.close()
