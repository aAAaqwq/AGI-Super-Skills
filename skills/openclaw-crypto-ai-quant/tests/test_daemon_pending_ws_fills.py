from __future__ import annotations

import json
from types import SimpleNamespace

from engine import daemon


class _FakeRestInfo:
    def __init__(self, *, should_raise: bool = False):
        self.calls: list[tuple[str, int, int, bool]] = []
        self.should_raise = should_raise

    def user_fills_by_time(
        self,
        address: str,
        start_ms: int,
        end_ms: int,
        *,
        aggregate_by_time: bool,
    ) -> list[dict]:
        self.calls.append((address, start_ms, end_ms, aggregate_by_time))
        if self.should_raise:
            raise RuntimeError("boom")
        return []


def _build_rest_sync_plugin(*, should_raise: bool) -> tuple[daemon.LivePlugin, _FakeRestInfo]:
    plugin = daemon.LivePlugin.__new__(daemon.LivePlugin)
    rest = _FakeRestInfo(should_raise=should_raise)
    plugin._rest_sync_s = 60.0
    plugin._last_rest_fills_sync = 1000.0
    plugin._force_rest_fills_sync = True
    plugin._last_rest_fills_ms = 10_000
    plugin._last_rest_fills_err_s = 0.0
    plugin._rest_info = rest
    plugin.main_address = "0xabc"
    plugin._oms = None
    plugin._lt = SimpleNamespace(process_user_fills=lambda _trader, _fills: 0)
    plugin.trader = SimpleNamespace(sync_from_exchange=lambda **_kwargs: None)
    plugin._err_last_s = {}
    plugin._err_log_every_s = 0.0
    return plugin, rest


def test_ws_fill_overflow_persists_keys_and_sets_force_backfill(tmp_path, capsys):
    plugin = daemon.LivePlugin.__new__(daemon.LivePlugin)
    plugin._max_pending_ws_fills = 2
    plugin._pending_ws_fills = [
        {"coin": "BTC", "time": 1000, "tid": 11, "hash": "h11"},
        {"coin": "ETH", "time": 2000, "tid": 22, "hash": "h22"},
        {"coin": "SOL", "time": 3000, "tid": 33, "hash": "h33"},
    ]
    plugin._ws_fills_overflow_path = tmp_path / "ws_fills_overflow.jsonl"
    plugin._force_rest_fills_sync = False
    plugin._err_last_s = {}
    plugin._err_log_every_s = 0.0

    plugin._handle_ws_fills_overflow()

    assert plugin._force_rest_fills_sync is True
    assert [f.get("coin") for f in plugin._pending_ws_fills] == ["ETH", "SOL"]

    rows = [json.loads(line) for line in plugin._ws_fills_overflow_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC"
    assert rows[0]["time_ms"] == 1000
    assert rows[0]["tid"] == 11
    assert rows[0]["hash"] == "h11"

    out = capsys.readouterr().out
    assert "samples=BTC@1000" in out
    assert "forcing REST backfill" in out


def test_forced_rest_backfill_runs_immediately_and_clears_force_flag():
    plugin, rest = _build_rest_sync_plugin(should_raise=False)

    plugin._sync_rest_fills(now=1001.0)

    assert len(rest.calls) == 1
    assert plugin._force_rest_fills_sync is False
    assert plugin._last_rest_fills_sync == 1001.0


def test_forced_rest_backfill_runs_when_periodic_sync_is_disabled():
    plugin, rest = _build_rest_sync_plugin(should_raise=False)
    plugin._rest_sync_s = 0.0

    plugin._sync_rest_fills(now=1001.0)

    assert len(rest.calls) == 1
    assert plugin._force_rest_fills_sync is False


def test_forced_rest_backfill_failure_keeps_force_flag_for_retry():
    plugin, rest = _build_rest_sync_plugin(should_raise=True)

    plugin._sync_rest_fills(now=1001.0)

    assert len(rest.calls) == 1
    assert plugin._force_rest_fills_sync is True
