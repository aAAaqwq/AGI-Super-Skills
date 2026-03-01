from __future__ import annotations

import pytest

from engine.oms import LiveOms


def test_reconcile_unmatched_fills_uses_store_connect_and_closes_on_error(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "oms.db"
    monkeypatch.setenv("AI_QUANT_DB_PATH", str(db_path))
    monkeypatch.setenv("AI_QUANT_OMS_DB_TIMEOUT_S", "3.0")

    oms = LiveOms(db_path=str(db_path))

    calls: dict[str, float | None] = {}

    class _FailingConn:
        def __init__(self):
            self.closed = False

        def cursor(self):
            raise RuntimeError("cursor boom")

        def close(self):
            self.closed = True

    fake_conn = _FailingConn()

    def _fake_connect(*, timeout_s: float | None = None):
        calls["timeout_s"] = timeout_s
        return fake_conn

    monkeypatch.setattr(oms.store, "_connect", _fake_connect)

    with pytest.raises(RuntimeError, match="cursor boom"):
        oms.reconcile_unmatched_fills(trader=None)

    assert calls["timeout_s"] == pytest.approx(3.0)
    assert fake_conn.closed is True
