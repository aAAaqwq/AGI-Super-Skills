from __future__ import annotations

from engine.oms_reconciler import LiveOmsReconciler


def _build_reconciler_with_executor(executor):
    reconciler = LiveOmsReconciler.__new__(LiveOmsReconciler)
    reconciler.executor = executor
    return reconciler


def test_cancel_exchange_order_does_not_fallback_to_cancel_all_orders():
    class _Executor:
        def __init__(self) -> None:
            self.cancel_all_calls = 0

        def cancel_all_orders(self, **_kwargs):
            self.cancel_all_calls += 1
            return {"status": "ok"}

    executor = _Executor()
    reconciler = _build_reconciler_with_executor(executor)

    ok, why = reconciler._cancel_exchange_order(symbol="BTC", exchange_order_id="123", client_order_id=None)

    assert ok is False
    assert why == "no_method"
    assert executor.cancel_all_calls == 0


def test_cancel_exchange_order_still_uses_targeted_cancel_order():
    class _Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def cancel_order(self, symbol: str, oid: str):
            self.calls.append((symbol, oid))
            return {"status": "ok"}

    executor = _Executor()
    reconciler = _build_reconciler_with_executor(executor)

    ok, why = reconciler._cancel_exchange_order(symbol="ETH", exchange_order_id="999", client_order_id=None)

    assert ok is True
    assert why == "ok"
    assert executor.calls == [("ETH", "999")]
