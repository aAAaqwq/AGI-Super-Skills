from __future__ import annotations

import threading
import time

import exchange.meta as meta


class _FakeInfo:
    def __init__(self, *_args, **_kwargs):
        pass

    def meta_and_asset_ctxs(self):
        return [
            {
                "universe": [
                    {"name": "BTC", "szDecimals": 3, "marginTableId": 7},
                ],
                "marginTables": [
                    [7, {"marginTiers": [{"lowerBound": 0, "maxLeverage": 25}]}],
                ],
            },
            [
                {"funding": "0.001", "dayNtlVlm": "12345", "dayBaseVlm": "100", "openInterest": "10"},
            ],
        ]


def test_get_sz_decimals_respects_cache_lock(monkeypatch):
    monkeypatch.setattr(meta, "_ensure_cache", lambda: None)
    monkeypatch.setattr(meta, "_refresh_in_progress", False)
    monkeypatch.setattr(
        meta,
        "_cached_instruments",
        {
            "BTC": meta.PerpInstrument(
                name="BTC",
                sz_decimals=3,
                margin_table_id=1,
                funding_rate=0.0,
                day_ntl_vlm=0.0,
                day_base_vlm=0.0,
                open_interest=0.0,
            )
        },
    )
    monkeypatch.setattr(meta, "_cached_at_s", time.time())
    monkeypatch.setattr(meta, "_next_refresh_allowed_s", None)

    started = threading.Event()
    finished = threading.Event()
    result: dict[str, int] = {}

    def _worker() -> None:
        started.set()
        result["value"] = meta.get_sz_decimals("BTC")
        finished.set()

    with meta._CACHE_LOCK:
        thread = threading.Thread(target=_worker)
        thread.start()
        assert started.wait(timeout=1.0)
        assert not finished.wait(timeout=0.05)

    thread.join(timeout=1.0)
    assert finished.is_set()
    assert result["value"] == 3


def test_refresh_cache_respects_cache_lock(monkeypatch):
    meta_call_started = threading.Event()

    class _GuardedFakeInfo(_FakeInfo):
        def meta_and_asset_ctxs(self):
            meta_call_started.set()
            return super().meta_and_asset_ctxs()

    monkeypatch.setattr(meta, "Info", _GuardedFakeInfo)
    monkeypatch.setattr(meta, "_refresh_in_progress", False)
    monkeypatch.setattr(meta, "_cached_at_s", None)
    monkeypatch.setattr(meta, "_cached_instruments", {})
    monkeypatch.setattr(meta, "_cached_margin_tables", {})
    monkeypatch.setattr(meta, "_next_refresh_allowed_s", None)

    started = threading.Event()
    finished = threading.Event()

    def _worker() -> None:
        started.set()
        meta._refresh_cache()
        finished.set()

    with meta._CACHE_LOCK:
        thread = threading.Thread(target=_worker)
        thread.start()
        assert started.wait(timeout=1.0)
        assert not meta_call_started.wait(timeout=0.05)
        assert not finished.wait(timeout=0.05)

    thread.join(timeout=1.0)
    assert meta_call_started.is_set()
    assert finished.is_set()
    assert meta.get_sz_decimals("BTC") == 3
    assert meta.max_leverage("BTC", 1000.0) == 25.0


def test_refresh_cache_single_flight(monkeypatch):
    calls_lock = threading.Lock()
    refresh_started = threading.Event()
    allow_finish = threading.Event()
    calls = {"n": 0}

    class _BlockingFakeInfo(_FakeInfo):
        def meta_and_asset_ctxs(self):
            with calls_lock:
                calls["n"] += 1
            refresh_started.set()
            assert allow_finish.wait(timeout=1.0)
            return super().meta_and_asset_ctxs()

    monkeypatch.setattr(meta, "Info", _BlockingFakeInfo)
    monkeypatch.setattr(meta, "_refresh_in_progress", False)
    monkeypatch.setattr(meta, "_cached_at_s", None)
    monkeypatch.setattr(meta, "_cached_instruments", {})
    monkeypatch.setattr(meta, "_cached_margin_tables", {})
    monkeypatch.setattr(meta, "_next_refresh_allowed_s", None)

    t1 = threading.Thread(target=meta._refresh_cache)
    t2 = threading.Thread(target=meta._refresh_cache)
    t1.start()
    assert refresh_started.wait(timeout=1.0)
    t2.start()
    time.sleep(0.05)
    with calls_lock:
        assert calls["n"] == 1

    allow_finish.set()
    t1.join(timeout=1.0)
    t2.join(timeout=1.0)
    assert not t1.is_alive()
    assert not t2.is_alive()
    with calls_lock:
        assert calls["n"] == 1
