from __future__ import annotations

import live.trader as live_trader


def _build_trader_with_pending(symbol: str, items: list[dict]) -> live_trader.LiveTrader:
    trader = live_trader.LiveTrader.__new__(live_trader.LiveTrader)
    trader._pending_context = {symbol: list(items)}
    return trader


def test_pop_pending_missing_created_timestamp_is_not_treated_as_epoch(monkeypatch):
    monkeypatch.setenv("AI_QUANT_LIVE_PENDING_CTX_TTL_S", "1")
    monkeypatch.setattr(live_trader.time, "time", lambda: 1_700_000_000.0)

    trader = _build_trader_with_pending("BTC", [{"id": "first"}, {"id": "second"}])

    out = trader.pop_pending("BTC")

    assert out == {"id": "first"}


def test_pop_pending_drops_negative_and_stale_entries_then_returns_first_non_stale(monkeypatch):
    monkeypatch.setenv("AI_QUANT_LIVE_PENDING_CTX_TTL_S", "10")
    monkeypatch.setattr(live_trader.time, "time", lambda: 1_000.0)

    trader = _build_trader_with_pending(
        "ETH",
        [
            {"id": "negative", "_created_at_s": -1.0},
            {"id": "stale", "_created_at_s": 1.0},
            {"id": "fresh", "_created_at_s": 995.0},
        ],
    )

    out = trader.pop_pending("ETH")

    assert out == {"id": "fresh", "_created_at_s": 995.0}
