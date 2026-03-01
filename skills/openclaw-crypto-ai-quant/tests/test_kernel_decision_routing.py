from __future__ import annotations

import json
import os
import hashlib
import types
from dataclasses import dataclass
import importlib
from collections.abc import Mapping
from typing import Any

import pytest
from unittest.mock import Mock

from engine.core import (
    KernelDecision,
    UnifiedEngine,
    KernelDecisionRustBindingProvider,
    KernelDecisionFileProvider,
    NoopDecisionProvider,
    _build_default_decision_provider,
)
from live.trader import LiveTrader


class FakeStrategyManager:
    def __init__(self) -> None:
        self.snapshot = types.SimpleNamespace(version="tkt-004", overrides_sha1="sha1")
        self.reload_calls = 0

    def maybe_reload(self) -> None:
        self.reload_calls += 1

    def get_watchlist(self) -> list[str]:
        return ["ETH"]

    def get_config(self, scope: str) -> dict[str, object]:
        if str(scope) == "__GLOBAL__":
            return {
                "engine": {
                    "heartbeat_every_s": "0",
                    "entry_interval": "1m",
                }
            }
        return {}

    def analyze(self, *_args, **_kwargs) -> None:
        raise AssertionError("Kernel decision path should not call analyze")


class FakeMarket:
    def ensure(self, *, symbols, interval, candle_limit, user) -> None:
        return None

    def ws_health(self, symbols) -> object:
        class _S:
            mids_age_s = 0
            candle_age_s = 0
            bbo_age_s = 0

        return _S()

    def candles_ready(self, *, symbols, interval):
        return (True, [])

    def get_last_closed_candle_key(self, symbol, *, interval, grace_ms=2000) -> int:
        return 1700000000000

    def get_latest_candle_open_key(self, symbol, *, interval) -> int:
        return 1700000000000

    def get_candles_df(self, symbol, *, interval, min_rows) -> None:
        return None

    def get_mid_price(self, symbol, *, max_age_s=10.0, interval=None):
        return types.SimpleNamespace(price=123.0, source="test", age_s=0.0)

    def health(self, *, symbols, interval) -> dict[str, object]:
        return {"connected": True, "thread_alive": True}


class FakeDecisionProvider:
    def __init__(self, decisions: list[KernelDecision]) -> None:
        self.decisions = decisions

    def get_decisions(
        self,
        *,
        symbols: list[str],
        watchlist: list[str],
        open_symbols: list[str],
        market: object,
        interval: str,
        lookback_bars: int,
        mode: str,
        not_ready_symbols: set[str],
        strategy: object,
        now_ms: int,
    ) -> list[KernelDecision]:
        return self.decisions


class _FakeKernelStrategy:
    def __init__(self, *, sha1: str, symbol_cfg: dict[str, Any] | None = None) -> None:
        self.snapshot = types.SimpleNamespace(version="v-test", overrides_sha1=str(sha1))
        self._symbol_cfg = symbol_cfg or {}
        self.get_config_calls: list[str] = []

    def get_config(self, scope: str) -> dict[str, Any]:
        key = str(scope or "").strip().upper()
        self.get_config_calls.append(key)
        if key == "__GLOBAL__":
            return {
                "thresholds": {
                    "entry": {
                        "macd_hist_entry_mode": "accel",
                    }
                },
                "trade": {
                    "sl_atr_mult": 2.0,
                    "tp_atr_mult": 4.0,
                },
                "filters": {},
            }
        return dict(self._symbol_cfg) if isinstance(self._symbol_cfg, dict) else {}


class FakeTrader:
    def __init__(self) -> None:
        self.positions: dict[str, dict[str, object]] = {}
        self.calls: list[tuple[str, str, float | None, str]] = []

    def execute_trade(
        self,
        symbol,
        signal,
        price,
        timestamp,
        confidence,
        atr=0.0,
        indicators=None,
        *,
        action: str | None = None,
        target_size: float | None = None,
        reason: str | None = None,
    ) -> None:
        self.calls.append((str(action or ""), str(signal), float(target_size) if target_size is not None else None, str(confidence)))

    def check_exit_conditions(self, *args, **kwargs) -> None:
        return None


class LegacyKernelTrader:
    def __init__(self, has_position: bool = False) -> None:
        self.positions: dict[str, dict[str, object]] = {"ETH": {"type": "LONG", "size": 1.0}} if has_position else {}
        self.execute_trade_calls: int = 0
        self.add_calls: int = 0
        self.close_calls: int = 0
        self.reduce_calls: int = 0

    def execute_trade(self, symbol, signal, price, timestamp, confidence, atr=0.0, indicators=None, *args, **kwargs) -> None:
        self.execute_trade_calls += 1
        raise TypeError("legacy action signature")

    def add_to_position(self, *args, **kwargs) -> None:
        self.add_calls += 1

    def close_position(self, *args, **kwargs) -> None:
        self.close_calls += 1

    def reduce_position(self, *args, **kwargs) -> None:
        self.reduce_calls += 1


def test_unified_engine_routes_kernel_decisions_to_trader(monkeypatch) -> None:
    monkeypatch.setattr("engine.core.time.sleep", lambda *_: (_ for _ in ()).throw(SystemExit))
    monkeypatch.setattr("strategy.mei_alpha_v1.get_strategy_config", lambda _symbol: {})

    strategy = FakeStrategyManager()
    market = FakeMarket()
    trader = FakeTrader()
    decisions = [
        KernelDecision.from_raw(
            {
                "symbol": "ETH",
                "action": "OPEN",
                "signal": "BUY",
                "confidence": "high",
                "score": 10.0,
                "target_size": 12.5,
            }
        ),
        KernelDecision.from_raw(
            {
                "symbol": "ETH",
                "action": "REDUCE",
                "signal": "BUY",
                "confidence": "high",
                "score": 5.0,
                "target_size": 0.75,
            }
        ),
    ]

    provider = FakeDecisionProvider([d for d in decisions if d is not None])
    engine = UnifiedEngine(
        trader=trader,
        strategy=strategy,
        market=market,
        interval="1m",
        lookback_bars=50,
        mode="paper",
        mode_plugin=None,
        decision_provider=provider,
    )

    with pytest.raises(SystemExit):
        engine.run_forever()

    assert [c[0] for c in trader.calls] == ["OPEN", "REDUCE"]
    assert [c[2] for c in trader.calls] == [12.5, 0.75]


def test_unified_engine_explicit_action_fallback_for_legacy_execute_trade(monkeypatch) -> None:
    monkeypatch.setattr("engine.core.time.sleep", lambda *_: (_ for _ in ()).throw(SystemExit))
    monkeypatch.setattr("strategy.mei_alpha_v1.get_strategy_config", lambda _symbol: {})

    strategy = FakeStrategyManager()
    market = FakeMarket()
    trader = LegacyKernelTrader()
    decisions = [
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "ADD", "signal": "BUY", "confidence": "high", "score": 1.0, "target_size": 1.0}
        ),
        KernelDecision.from_raw(
            {"symbol": "ETH", "action": "OPEN", "signal": "BUY", "confidence": "high", "score": 1.0, "target_size": 1.0}
        ),
    ]
    provider = FakeDecisionProvider([d for d in decisions if d is not None])
    engine = UnifiedEngine(
        trader=trader,
        strategy=strategy,
        market=market,
        interval="1m",
        lookback_bars=50,
        mode="paper",
        mode_plugin=None,
        decision_provider=provider,
    )

    with pytest.raises(SystemExit):
        engine.run_forever()

    # Legacy execute_trade() raising TypeError must not silently route OPEN as signal-only execute_trade.
    assert trader.add_calls == 1
    assert trader.reduce_calls == 0
    assert trader.close_calls == 0
    assert trader.execute_trade_calls >= 1


class DummyExecutor:
    def __init__(self) -> None:
        self.update_leverage_calls: list[tuple[str, float, bool]] = []
        self.market_open_calls: list[tuple] = []
        self.last_order_error = {}

    def account_snapshot(self, force: bool = False):  # pragma: no cover - tiny test stub
        from types import SimpleNamespace

        return SimpleNamespace(
            account_value_usd=100000.0,
            withdrawable_usd=100000.0,
            total_margin_used_usd=0.0,
        )

    def get_positions(self, force: bool = False):  # pragma: no cover - tiny test stub
        return {}

    def update_leverage(self, symbol, leverage, is_cross=True):
        self.update_leverage_calls.append((str(symbol).strip().upper(), float(leverage), bool(is_cross)))
        return True

    def market_open(
        self,
        symbol,
        is_buy,
        sz,
        px,
        slippage_pct,
        cloid=None,
    ):
        self.market_open_calls.append((str(symbol).strip().upper(), bool(is_buy), float(sz), float(px), float(slippage_pct), cloid))
        return True


@dataclass
class _KernelSizing:
    leverage: float
    desired_notional_usd: float


def test_live_execute_trade_action_routing(monkeypatch) -> None:
    monkeypatch.setattr("live.trader.log_live_signal", lambda **kwargs: None)
    trader = LiveTrader(executor=DummyExecutor())
    trader.positions = {
        "BTC": {
            "type": "LONG",
            "size": 1.0,
            "entry_price": 100.0,
            "entry_atr": 2.0,
            "tp1_taken": 0,
            "leverage": 2,
        }
    }

    mock_add = Mock(return_value=True)
    mock_close = Mock(return_value=True)
    mock_reduce = Mock(return_value=True)
    monkeypatch.setattr(trader, "add_to_position", mock_add)
    monkeypatch.setattr(trader, "close_position", mock_close)
    monkeypatch.setattr(trader, "reduce_position", mock_reduce)

    trader.execute_trade(
        "BTC",
        "BUY",
        101.0,
        1700000000000,
        "high",
        action="CLOSE",
        reason="kernel-close",
    )
    assert mock_close.call_count == 1
    assert mock_close.call_args.args == ("BTC", 101.0, 1700000000000)
    assert mock_close.call_args.kwargs.get("reason") == "kernel-close"
    assert mock_add.call_count == 0

    trader.execute_trade(
        "BTC",
        "SELL",
        101.0,
        1700000000000,
        "high",
        action="ADD",
        target_size=7.5,
        reason="kernel-add",
    )
    mock_add.assert_called_once_with(
        "BTC", 101.0, 1700000000000, "high", atr=0.0, indicators=None, target_size=7.5, reason="kernel-add"
    )
    assert mock_reduce.call_count == 0

    trader.execute_trade(
        "BTC",
        "BUY",
        101.0,
        1700000000000,
        "high",
        action="REDUCE",
        target_size=0.5,
        reason="kernel-reduce",
    )
    assert mock_reduce.call_count == 1
    assert mock_reduce.call_args.args == ("BTC", 0.5, 101.0, 1700000000000)
    assert mock_reduce.call_args.kwargs.get("reason") == "kernel-reduce"


def test_live_execute_trade_open_action_uses_open_kernel_path(monkeypatch) -> None:
    monkeypatch.setattr("live.trader.log_live_signal", lambda **kwargs: None)
    monkeypatch.setattr("live.trader.mei_alpha_v1.compute_entry_sizing", lambda *args, **kwargs: _KernelSizing(2.0, 200.0))
    monkeypatch.setattr(
        "live.trader.mei_alpha_v1._get_fill_price",
        lambda *a, **k: float((a[2] if len(a) > 2 else k.get("price", 0.0)) or 0.0),
    )
    monkeypatch.setattr("live.trader.mei_alpha_v1.get_strategy_config", lambda _symbol: {})
    monkeypatch.setattr("live.trader.mei_alpha_v1.log_audit_event", lambda *a, **k: None)
    monkeypatch.setattr("live.trader.hyperliquid_meta.max_leverage", lambda symbol, notional: 100.0)
    monkeypatch.setattr("live.trader.hyperliquid_meta.round_size", lambda symbol, sz: float(sz))
    monkeypatch.setattr("live.trader.hyperliquid_meta.min_size_for_notional", lambda symbol, min_notional, price: float(min_notional) / float(price))
    monkeypatch.setattr(
        "live.trader.LiveTrader._live_trade_cfg",
        lambda self, symbol: {
            "enable_ssf_filter": False,
            "enable_reef_filter": False,
            "max_notional_usd_per_order": 10000.0,
            "size_multiplier": 1.0,
            "max_open_positions": 1,
        },
    )
    monkeypatch.setattr("live.trader.live_entries_enabled", lambda: True)
    monkeypatch.setattr("live.trader.live_mode", lambda: "live")
    monkeypatch.setattr("live.trader.live_orders_enabled", lambda: True)

    trader = LiveTrader(executor=DummyExecutor())
    trader._account_value_usd = 100000.0
    trader.balance = 100000.0
    trader.positions = {}
    trader._entry_budget_remaining = 1
    trader._total_margin_used_usd = 0.0

    mock_add = Mock(return_value=False)
    mock_close = Mock(return_value=False)
    mock_reduce = Mock(return_value=False)
    monkeypatch.setattr(trader, "add_to_position", mock_add)
    monkeypatch.setattr(trader, "close_position", mock_close)
    monkeypatch.setattr(trader, "reduce_position", mock_reduce)

    trader.execute_trade("ETH", "BUY", 101.0, 1700000000000, "high", action="OPEN", target_size=120.0, reason="kernel-open")

    assert mock_add.call_count == 0
    assert mock_close.call_count == 0
    assert mock_reduce.call_count == 0
    assert len(trader.executor.market_open_calls) == 1


class _FakeKernelRuntime:
    def __init__(self, intents: list[dict[str, Any]] | None = None) -> None:
        self._decision_intents = intents or [
            {
                "schema_version": 1,
                "intent_id": 1001,
                "symbol": "ETH",
                "kind": "open",
                "side": "long",
                "quantity": 0.25,
                "price": 400.0,
                "notional_usd": 100.0,
                "fee_rate": 0.0,
            }
        ]
        self.default_state = {
            "schema_version": 1,
            "timestamp_ms": 1700000000000,
            "step": 1,
            "cash_usd": 10_000.0,
            "positions": {},
        }
        self.default_params = {
            "schema_version": 1,
            "default_notional_usd": 10_000.0,
            "min_notional_usd": 10.0,
            "max_notional_usd": 100_000.0,
            "maker_fee_bps": 3.5,
            "taker_fee_bps": 3.5,
            "allow_pyramid": True,
            "allow_reverse": True,
        }
        self.step_params: list[dict[str, Any]] = []
        self.step_decision_calls: int = 0
        self.step_full_calls: int = 0

    def default_kernel_state_json(self, initial_cash_usd: float, timestamp_ms: int) -> str:
        state = dict(self.default_state)
        state["cash_usd"] = float(initial_cash_usd)
        state["timestamp_ms"] = int(timestamp_ms)
        return json.dumps(state)

    def default_kernel_params_json(self) -> str:
        return json.dumps(self.default_params)

    def load_state(self, path: str) -> str:
        raise OSError(f"state not found: {path}")

    def save_state(self, state_json: str, path: str) -> None:
        parent = os.path.dirname(str(path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    def step_decision(self, state_json: str, event_json: str, params_json: str) -> str:
        self.step_decision_calls += 1
        event = json.loads(event_json)
        if not isinstance(event, dict):
            return json.dumps({"ok": False, "error": {"code": "INVALID_EVENT", "message": "invalid", "details": []}})

        params = json.loads(params_json)
        if not isinstance(params, dict):
            params = {}
        self.step_params.append(dict(params))

        symbol = str(event.get("symbol", "")).strip().upper()
        if not symbol:
            return json.dumps({"ok": False, "error": {"code": "INVALID_EVENT", "message": "missing symbol", "details": []}})

        price = float(event.get("price", 0.0))
        intent_id = 1001

        state = json.loads(state_json)
        if not isinstance(state, dict):
            state = dict(self.default_state)

        state["step"] = int(state.get("step", 0)) + 1
        state["timestamp_ms"] = int(event.get("timestamp_ms", 0))

        exit_bounds = None
        positions = state.get("positions")
        exit_params = params.get("exit_params")
        signal = str(event.get("signal", "")).strip().lower()
        allow_exit_eval = signal == "price_update"
        if allow_exit_eval and isinstance(positions, dict) and isinstance(exit_params, Mapping):
            pos = positions.get(symbol)
            if isinstance(pos, dict):
                try:
                    entry_price = float(pos.get("avg_entry_price", 0.0) or 0.0)
                except Exception:
                    entry_price = 0.0
                side = str(pos.get("side", "long") or "long").strip().lower()
                try:
                    entry_atr = float(pos.get("entry_atr", 0.0) or 0.0)
                except Exception:
                    entry_atr = 0.0
                if entry_atr <= 0.0 and entry_price > 0.0:
                    entry_atr = entry_price * 0.005
                if entry_price > 0.0 and entry_atr > 0.0:
                    try:
                        sl_mult = float(exit_params.get("sl_atr_mult", 2.0) or 2.0)
                    except Exception:
                        sl_mult = 2.0
                    try:
                        tp_mult = float(exit_params.get("tp_atr_mult", 4.0) or 4.0)
                    except Exception:
                        tp_mult = 4.0
                    if side == "short":
                        lower_full = entry_price - (tp_mult * entry_atr)
                        upper_full = entry_price + (sl_mult * entry_atr)
                    else:
                        lower_full = entry_price - (sl_mult * entry_atr)
                        upper_full = entry_price + (tp_mult * entry_atr)
                    exit_bounds = {
                        "upper_full": float(upper_full),
                        "upper_partial": float(upper_full),
                        "lower_full": float(lower_full),
                    }

        intents = []
        for offset, raw_intent in enumerate(self._decision_intents, start=1):
            if not isinstance(raw_intent, Mapping):
                continue
            intent = dict(raw_intent)
            intent["schema_version"] = 1
            intent["symbol"] = symbol
            intent.setdefault("intent_id", intent_id + offset - 1)
            intent.setdefault("side", "long")
            intent.setdefault("quantity", 0.25)
            intent.setdefault("price", price)
            if "notional_usd" not in intent:
                try:
                    intent["notional_usd"] = float(intent["quantity"]) * float(intent["price"])
                except Exception:
                    intent["notional_usd"] = float(price) * 0.25
            intent.setdefault("fee_rate", 0.0)
            intents.append(intent)

        decision = {
            "schema_version": 1,
            "state": state,
            "intents": intents,
            "fills": [],
            "diagnostics": {
                "schema_version": 1,
                "errors": [],
                "warnings": [],
                "intent_count": len(intents),
                "fill_count": 0,
                "step": 2,
                "exit_bounds": exit_bounds,
                "applied_thresholds": 1 if isinstance(exit_bounds, Mapping) else 0,
            },
        }
        return json.dumps({"ok": True, "decision": decision})

    def step_full(self, state_json: str, event_json: str, params_json: str, exit_params_json: str) -> str:
        self.step_full_calls += 1
        params = json.loads(params_json)
        if not isinstance(params, dict):
            params = {}
        exit_params = json.loads(exit_params_json)
        if not isinstance(exit_params, dict):
            exit_params = {}
        merged = dict(params)
        merged["exit_params"] = dict(exit_params)
        merged["__step_full__"] = True
        return self.step_decision(state_json, event_json, json.dumps(merged))


@pytest.mark.parametrize(
    (
        "raw",
        "expected_action",
        "expected_signal",
        "expected_size",
        "expected_entry_key",
    ),
    [
        ({"symbol": "ETH", "action": "OPEN", "signal": "BUY", "target_size": 2.5, "entry_key": "11"}, "OPEN", "BUY", 2.5, 11),
        ({"symbol": "ETH", "action": "add", "signal": "SELL", "target_size": 0.5, "candle_key": "22"}, "ADD", "SELL", 0.5, 22),
        ({"symbol": "ETH", "action": "CLOSE", "signal": "NEUTRAL", "target_size": 1.2, "entry_candle_key": "33"}, "CLOSE", "NEUTRAL", 1.2, 33),
        ({"symbol": "ETH", "action": "REVERSE", "signal": "BUY", "target_size": 1.8}, "CLOSE", "BUY", 1.8, None),
        ({"symbol": "ETH", "action": "OPEN", "target_size": 2.0}, "OPEN", "OPEN", 2.0, None),
        ({"symbol": "ETH", "action": "OPEN", "target_size": "2", "notional_hint_usd": 100, "price": 200}, "OPEN", "OPEN", 0.5, None),
        ({"symbol": "ETH", "kind": "open", "side": "long", "quantity": 3.0, "price": 200, "intent_id": "401"}, "OPEN", "BUY", 3.0, 401),
        ({"symbol": "ETH", "kind": "add", "side": "short", "notional_usd": 120, "price": 200}, "ADD", "SELL", 0.6, None),
        ({"symbol": "ETH", "kind": "close", "side": "long", "quantity": 2.4, "price": 100}, "CLOSE", "BUY", 2.4, None),
        ({"symbol": "ETH", "kind": "reverse", "side": "short", "quantity": 1.5, "price": 10, "notional_usd": 15}, "CLOSE", "SELL", 1.5, None),
        ({"symbol": "ETH", "kind": "hold", "side": "long", "quantity": 1.0, "price": 10}, None, None, None, None),
        ({"symbol": "ETH", "kind": "open", "side": "long", "notional_usd": 0.0, "price": 10, "quantity": 0}, "OPEN", "BUY", None, None),
        ({"symbol": "", "kind": "open", "side": "long", "quantity": 1, "price": 10}, None, None, None, None),
    ],
)
def test_kernel_decision_from_raw_supports_legacy_and_canonical_input_schemas(
    raw,
    expected_action,
    expected_signal,
    expected_size,
    expected_entry_key,
) -> None:
    dec = KernelDecision.from_raw(raw)
    if expected_action is None:
        assert dec is None
        return

    assert dec is not None
    assert dec.action == expected_action
    assert dec.signal == expected_signal
    assert dec.target_size == expected_size
    assert dec.entry_key == expected_entry_key


def test_rust_binding_provider_converts_kernel_intents(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "schema_version": 1,
                    "symbol": "ETH",
                    "action": "OPEN",
                    "signal": "BUY",
                    "price": 100.0,
                    "timestamp_ms": 1700000000000,
                    "notional_hint_usd": 2500.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = KernelDecisionRustBindingProvider(path=str(payload_path))
    decisions = list(
        provider.get_decisions(
            symbols=["ETH"],
            watchlist=["ETH"],
            open_symbols=[],
            market=None,
            interval="1m",
            lookback_bars=50,
            mode="paper",
            not_ready_symbols=set(),
            strategy=None,
            now_ms=1700000000000,
        )
    )

    assert len(decisions) == 1
    assert decisions[0].action == "OPEN"
    assert decisions[0].symbol == "ETH"
    assert decisions[0].target_size == 0.25
    assert decisions[0].confidence == "medium"


def test_rust_binding_provider_merges_entry_exit_params_from_strategy_and_caches(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "schema_version": 1,
                    "symbol": "ETH",
                    "signal": "evaluate",
                    "price": 100.0,
                    "timestamp_ms": 1700000000000,
                    "indicators": {"close": 100.0, "atr": 2.0, "ema_fast": 101.0, "ema_slow": 99.0},
                    "gate_result": {"allow_trade": True, "confidence": "high", "reasons": []},
                    "ema_slow_slope_pct": 0.001,
                },
                {
                    "schema_version": 1,
                    "symbol": "ETH",
                    "signal": "evaluate",
                    "price": 101.0,
                    "timestamp_ms": 1700000001000,
                    "indicators": {"close": 101.0, "atr": 2.1, "ema_fast": 101.5, "ema_slow": 99.5},
                    "gate_result": {"allow_trade": True, "confidence": "high", "reasons": []},
                    "ema_slow_slope_pct": 0.001,
                },
            ]
        ),
        encoding="utf-8",
    )
    runtime = _FakeKernelRuntime(intents=[])
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: runtime)

    provider = KernelDecisionRustBindingProvider(path=str(payload_path))
    strategy = _FakeKernelStrategy(
        sha1="4c021600d43a799ffc326ff70b375fee4a731119",
        symbol_cfg={
            "thresholds": {
                "entry": {
                    "macd_hist_entry_mode": "sign",
                }
            },
            "trade": {
                "sl_atr_mult": 1.8,
                "tp_atr_mult": 3.2,
            },
            "filters": {},
        },
    )

    _ = list(
        provider.get_decisions(
            symbols=["ETH"],
            watchlist=["ETH"],
            open_symbols=[],
            market=None,
            interval="1m",
            lookback_bars=50,
            mode="paper",
            not_ready_symbols=set(),
            strategy=strategy,
            now_ms=1700000000000,
        )
    )

    assert len(runtime.step_params) == 2
    assert runtime.step_full_calls == 2
    first = runtime.step_params[0]
    assert isinstance(first.get("entry_params"), Mapping)
    assert isinstance(first.get("exit_params"), Mapping)
    assert int(first["entry_params"]["macd_mode"]) == 1
    assert float(first["exit_params"]["sl_atr_mult"]) == pytest.approx(1.8)
    assert float(first["exit_params"]["tp_atr_mult"]) == pytest.approx(3.2)
    assert strategy.get_config_calls.count("ETH") == 1


def test_rust_binding_provider_can_fail_closed_when_exit_params_missing(monkeypatch, tmp_path, caplog) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "schema_version": 1,
                    "symbol": "ETH",
                    "signal": "evaluate",
                    "price": 100.0,
                    "timestamp_ms": 1700000000000,
                    "indicators": {"close": 100.0, "atr": 2.0, "ema_fast": 101.0, "ema_slow": 99.0},
                    "gate_result": {"allow_trade": True, "confidence": "high", "reasons": []},
                    "ema_slow_slope_pct": 0.001,
                }
            ]
        ),
        encoding="utf-8",
    )
    runtime = _FakeKernelRuntime(intents=[])
    monkeypatch.setenv("AI_QUANT_KERNEL_REQUIRE_EXIT_PARAMS", "1")
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: runtime)
    monkeypatch.setattr("strategy.mei_alpha_v1.build_exit_params", lambda *_args, **_kwargs: None)

    provider = KernelDecisionRustBindingProvider(path=str(payload_path))
    strategy = _FakeKernelStrategy(sha1="4c021600d43a799ffc326ff70b375fee4a731119")
    with caplog.at_level("WARNING", logger="engine.core"):
        decisions = list(
            provider.get_decisions(
                symbols=["ETH"],
                watchlist=["ETH"],
                open_symbols=[],
                market=None,
                interval="1m",
                lookback_bars=50,
                mode="paper",
                not_ready_symbols=set(),
                strategy=strategy,
                now_ms=1700000000000,
            )
        )

    assert decisions == []
    assert runtime.step_params == []
    assert "missing exit_params" in caplog.text


def test_rust_binding_provider_persists_exit_tunnel_when_exit_bounds_available(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "schema_version": 1,
                    "symbol": "ETH",
                    "signal": "evaluate",
                    "price": 102.0,
                    "timestamp_ms": 1700000000000,
                    "indicators": {"close": 102.0, "atr": 2.0, "ema_fast": 103.0, "ema_slow": 99.0},
                    "gate_result": {"allow_trade": True, "confidence": "high", "reasons": []},
                    "ema_slow_slope_pct": 0.001,
                }
            ]
        ),
        encoding="utf-8",
    )
    runtime = _FakeKernelRuntime(intents=[])
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: runtime)
    db_path = tmp_path / "paper.db"
    provider = KernelDecisionRustBindingProvider(path=str(payload_path), db_path=str(db_path))

    state = json.loads(provider._state_json)
    state["positions"] = {
        "ETH": {
            "schema_version": 1,
            "symbol": "ETH",
            "side": "long",
            "avg_entry_price": 100.0,
            "quantity": 1.0,
            "entry_atr": 2.0,
        }
    }
    provider._state_json = json.dumps(state)

    strategy = _FakeKernelStrategy(
        sha1="4c021600d43a799ffc326ff70b375fee4a731119",
        symbol_cfg={
            "trade": {"sl_atr_mult": 2.0, "tp_atr_mult": 4.0},
            "filters": {},
        },
    )
    _ = list(
        provider.get_decisions(
            symbols=["ETH"],
            watchlist=["ETH"],
            open_symbols=["ETH"],
            market=None,
            interval="1m",
            lookback_bars=50,
            mode="paper",
            not_ready_symbols=set(),
            strategy=strategy,
            now_ms=1700000000000,
        )
    )

    import sqlite3

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT symbol, upper_full, lower_full, entry_price, pos_type FROM exit_tunnel ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "ETH"
    assert float(row[1]) > float(row[2])
    assert float(row[3]) == pytest.approx(100.0)
    assert row[4] == "LONG"


def test_rust_binding_provider_uses_instance_tagged_state_path(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text("[]", encoding="utf-8")
    state_dir = tmp_path / "state"

    monkeypatch.setenv("AI_QUANT_INSTANCE_TAG", "v8-paper1")
    monkeypatch.setenv("AI_QUANT_KERNEL_STATE_DIR", str(state_dir))
    monkeypatch.delenv("AI_QUANT_KERNEL_STATE_PATH", raising=False)
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = KernelDecisionRustBindingProvider(path=str(payload_path))

    assert provider._state_path == str(state_dir / "kernel_state_v8-paper1.json")


def test_rust_binding_provider_uses_db_scoped_state_path_without_tag(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text("[]", encoding="utf-8")
    state_dir = tmp_path / "state"
    db_path = tmp_path / "trading_engine_v8_paper2.db"
    db_path.write_text("", encoding="utf-8")

    monkeypatch.delenv("AI_QUANT_INSTANCE_TAG", raising=False)
    monkeypatch.setenv("AI_QUANT_KERNEL_STATE_DIR", str(state_dir))
    monkeypatch.delenv("AI_QUANT_KERNEL_STATE_PATH", raising=False)
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = KernelDecisionRustBindingProvider(path=str(payload_path), db_path=str(db_path))
    db_real = str(db_path.expanduser().resolve())
    db_hash = hashlib.sha1(db_real.encode("utf-8")).hexdigest()[:12]
    expected = state_dir / f"kernel_state_trading_engine_v8_paper2_{db_hash}.json"
    assert provider._state_path == str(expected)


def test_rust_binding_provider_legacy_fallback_disabled_by_default(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text("[]", encoding="utf-8")
    monkeypatch.delenv("AI_QUANT_KERNEL_STATE_LEGACY_FALLBACK", raising=False)
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = KernelDecisionRustBindingProvider(path=str(payload_path))
    assert provider._allow_legacy_state_fallback is False


def test_rust_binding_provider_bootstraps_positions_from_db_when_state_empty(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text("[]", encoding="utf-8")
    state_dir = tmp_path / "state"
    db_path = tmp_path / "paper.db"

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            type TEXT,
            action TEXT,
            price REAL,
            size REAL,
            confidence TEXT,
            entry_atr REAL,
            leverage REAL,
            margin_used REAL,
            balance REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE position_state (
            symbol TEXT PRIMARY KEY,
            open_trade_id INTEGER,
            trailing_sl REAL,
            last_funding_time INTEGER,
            adds_count INTEGER,
            tp1_taken INTEGER,
            last_add_time INTEGER,
            entry_adx_threshold REAL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO trades (id, timestamp, symbol, type, action, price, size, confidence, entry_atr, leverage, margin_used)
        VALUES (101, '2026-02-15T19:00:00+00:00', 'ETH', 'LONG', 'OPEN', 100.0, 1.0, 'medium', 2.0, 5.0, 20.0)
        """
    )
    conn.execute(
        """
        INSERT INTO trades (id, timestamp, symbol, type, action, price, size, confidence, entry_atr, leverage, margin_used, balance)
        VALUES (102, '2026-02-15T19:30:00+00:00', 'ETH', 'LONG', 'ADD', 110.0, 0.5, 'medium', 2.2, 5.0, 11.0, 321.5)
        """
    )
    conn.execute(
        """
        INSERT INTO position_state (symbol, open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold)
        VALUES ('ETH', 101, 95.0, 1771185600000, 1, 0, 1771183800000, 18.5)
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("AI_QUANT_INSTANCE_TAG", "v8-paper1")
    monkeypatch.setenv("AI_QUANT_KERNEL_STATE_DIR", str(state_dir))
    monkeypatch.delenv("AI_QUANT_KERNEL_STATE_PATH", raising=False)
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = KernelDecisionRustBindingProvider(path=str(payload_path), db_path=str(db_path))
    state = json.loads(provider._state_json)
    positions = state.get("positions") if isinstance(state, dict) else None

    assert isinstance(positions, dict)
    assert "ETH" in positions
    assert positions["ETH"]["symbol"] == "ETH"
    assert positions["ETH"]["side"] == "long"
    assert positions["ETH"]["quantity"] == pytest.approx(1.5)
    assert positions["ETH"]["adds_count"] == 1
    assert state["cash_usd"] == pytest.approx(321.5)


def test_rust_binding_provider_skips_bootstrap_without_matching_position_state(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text("[]", encoding="utf-8")
    state_dir = tmp_path / "state"
    db_path = tmp_path / "paper.db"

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            type TEXT,
            action TEXT,
            price REAL,
            size REAL,
            confidence TEXT,
            entry_atr REAL,
            leverage REAL,
            margin_used REAL,
            balance REAL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO trades (id, timestamp, symbol, type, action, price, size, confidence, entry_atr, leverage, margin_used, balance)
        VALUES (1, '2026-02-15T19:00:00+00:00', 'ETH', 'LONG', 'OPEN', 100.0, 1.0, 'medium', 2.0, 5.0, 20.0, 111.0)
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("AI_QUANT_KERNEL_STATE_DIR", str(state_dir))
    monkeypatch.delenv("AI_QUANT_INSTANCE_TAG", raising=False)
    monkeypatch.delenv("AI_QUANT_KERNEL_STATE_PATH", raising=False)
    monkeypatch.setenv("AI_QUANT_KERNEL_BOOTSTRAP_REQUIRE_POSITION_STATE", "1")
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = KernelDecisionRustBindingProvider(path=str(payload_path), db_path=str(db_path))
    state = json.loads(provider._state_json)
    positions = state.get("positions") if isinstance(state, dict) else None

    assert isinstance(positions, dict)
    assert positions == {}

@pytest.mark.parametrize(
    ("intents", "expected_actions", "expected_sizes"),
    [
        (
            [{"kind": "open", "side": "long", "quantity": 1.0, "price": 100.0}],
            ["OPEN"],
            [1.0],
        ),
        (
            [{"kind": "add", "side": "short", "quantity": 0.5, "price": 80.0}],
            ["ADD"],
            [0.5],
        ),
        (
            [{"kind": "close", "side": "long", "quantity": 2.0, "price": 110.0}],
            ["CLOSE"],
            [2.0],
        ),
        (
            [{"kind": "reverse", "side": "short", "quantity": 1.0, "price": 95.0}],
            ["CLOSE"],
            [1.0],
        ),
        (
            [{"kind": "hold", "side": "long", "quantity": 1.0, "price": 90.0}],
            [],
            [],
        ),
        (
            [{"kind": "open", "side": "long", "quantity": 2.0, "notional_usd": 100.0, "price": 50.0}],
            ["OPEN"],
            [2.0],
        ),
        (
            [{"kind": "open", "side": "long", "notional_usd": 90.0, "price": 30.0}],
            ["OPEN"],
            [3.0],
        ),
        (
            [{"kind": "open", "side": "long", "notional_usd": 90.0, "price": 0.0}],
            ["OPEN"],
            [None],
        ),
        (
            [
                {"kind": "open", "side": "long", "quantity": 1.0, "price": 40.0},
                {"kind": "close", "side": "long", "quantity": 1.0, "price": 41.0},
                {"kind": "reverse", "side": "long", "quantity": 2.0, "price": 42.0},
            ],
            ["OPEN", "CLOSE", "CLOSE"],
            [1.0, 1.0, 2.0],
        ),
    ],
)
def test_rust_binding_provider_converts_kernel_intents_with_canonical_variants(
    monkeypatch, tmp_path, intents, expected_actions, expected_sizes
) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "schema_version": 1,
                    "symbol": "ETH",
                    "signal": "BUY",
                    "price": 100.0,
                    "timestamp_ms": 1700000000000,
                    "notional_hint_usd": 2500.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "engine.core._load_kernel_runtime_module",
        lambda *_args, **_kwargs: _FakeKernelRuntime(intents=intents),
    )

    provider = KernelDecisionRustBindingProvider(path=str(payload_path))
    decisions = list(
        provider.get_decisions(
            symbols=["ETH"],
            watchlist=["ETH"],
            open_symbols=[],
            market=None,
            interval="1m",
            lookback_bars=50,
            mode="paper",
            not_ready_symbols=set(),
            strategy=None,
            now_ms=1700000000000,
        )
    )

    assert [d.action for d in decisions] == expected_actions
    assert [d.target_size for d in decisions] == expected_sizes


def test_kernel_file_provider_rejects_oversized_payload(monkeypatch, tmp_path, caplog) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "ETH",
                    "action": "OPEN",
                    "signal": "BUY",
                    "price": 100.0,
                    "timestamp_ms": 1700000000000,
                    "target_size": 1.0,
                    "confidence": "medium",
                    "pad": "x" * 5000,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_FILE_MAX_BYTES", "1024")
    provider = KernelDecisionFileProvider(str(payload_path))

    with caplog.at_level("WARNING", logger="engine.core"):
        decisions = list(
            provider.get_decisions(
                symbols=["ETH"],
                watchlist=["ETH"],
                open_symbols=[],
                market=None,
                interval="1m",
                lookback_bars=50,
                mode="paper",
                not_ready_symbols=set(),
                strategy=None,
                now_ms=1700000000000,
            )
        )

    assert decisions == []
    assert "decision file too large" in caplog.text


def test_bt_runtime_binding_returns_schema_mismatch_error_code() -> None:
    try:
        bt_runtime = importlib.import_module("bt_runtime")
    except Exception:
        pytest.skip("bt_runtime extension is not available in the test environment")

    state_json = bt_runtime.default_kernel_state_json(10_000.0, 1_700_000_000_000)
    event_json = json.dumps(
        {
            "schema_version": 2,
            "event_id": 1,
            "timestamp_ms": 1_700_000_000_100,
            "symbol": "ETH",
            "signal": "BUY",
            "price": 100.0,
            "notional_hint_usd": 1000.0,
        }
    )
    params_json = bt_runtime.default_kernel_params_json()

    response = json.loads(bt_runtime.step_decision(state_json, event_json, params_json))
    assert isinstance(response, dict)
    assert response.get("ok") is False
    error = response.get("error", {})
    assert error.get("code") == "SCHEMA_VERSION_MISMATCH"


def test_bt_runtime_binding_invalid_json_returns_explicit_error_code() -> None:
    try:
        bt_runtime = importlib.import_module("bt_runtime")
    except Exception:
        pytest.skip("bt_runtime extension is not available in the test environment")

    response = json.loads(bt_runtime.step_decision("{not-json", "{} {}", "{}"))
    assert isinstance(response, dict)
    assert response.get("ok") is False
    error = response.get("error", {})
    assert error.get("code") == "INVALID_JSON"


def test_build_default_decision_provider_prefers_rust_when_available(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text("[]", encoding="utf-8")
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_PROVIDER", raising=False)
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_FILE", raising=False)
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = _build_default_decision_provider()
    assert isinstance(provider, KernelDecisionRustBindingProvider)


def test_build_default_decision_provider_falls_back_to_file_if_rust_not_available(monkeypatch, tmp_path) -> None:
    payload_path = tmp_path / "events.json"
    payload_path.write_text(
                json.dumps(
                [
                    {
                        "schema_version": 1,
                        "symbol": "ETH",
                        "action": "OPEN",
                        "signal": "BUY",
                        "price": 100.0,
                        "timestamp_ms": 1700000000000,
                        "notional_hint_usd": 2500.0,
                    }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_PROVIDER", raising=False)
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_FILE", str(payload_path))
    monkeypatch.setattr(
        "engine.core._load_kernel_runtime_module",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ImportError("missing bt_runtime")),
    )

    provider = _build_default_decision_provider()
    assert isinstance(provider, KernelDecisionFileProvider)
    decisions = list(
        provider.get_decisions(
            symbols=["ETH"],
            watchlist=["ETH"],
            open_symbols=[],
            market=None,
            interval="1m",
            lookback_bars=50,
            mode="paper",
            not_ready_symbols=set(),
            strategy=None,
            now_ms=1700000000000,
        )
        )
    assert len(decisions) == 1
    assert decisions[0].action == "OPEN"


def test_build_default_decision_provider_fails_fast_when_bt_runtime_unavailable(monkeypatch) -> None:
    """After AQC-825, auto-mode raises SystemExit when bt_runtime is unavailable
    instead of falling back to PythonAnalyzeDecisionProvider."""
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_PROVIDER", raising=False)
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_FILE", raising=False)
    monkeypatch.setattr(
        "engine.core._load_kernel_runtime_module",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ImportError("missing bt_runtime")),
    )

    with pytest.raises(SystemExit):
        _build_default_decision_provider()


def test_build_default_decision_provider_rejects_python_mode(monkeypatch) -> None:
    """AI_QUANT_KERNEL_DECISION_PROVIDER=python is no longer accepted (AQC-825)."""
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_PROVIDER", "python")
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_FILE", raising=False)

    with pytest.raises(SystemExit):
        _build_default_decision_provider()


def test_build_default_decision_provider_accepts_kernel_only_mode(monkeypatch) -> None:
    """AI_QUANT_KERNEL_DECISION_PROVIDER=kernel_only works as alias for rust."""
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_PROVIDER", "kernel_only")
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_FILE", raising=False)
    monkeypatch.setattr("engine.core._load_kernel_runtime_module", lambda *_args, **_kwargs: _FakeKernelRuntime())

    provider = _build_default_decision_provider()
    assert isinstance(provider, KernelDecisionRustBindingProvider)


def test_build_default_decision_provider_rust_mode_fails_fast_without_bt_runtime(monkeypatch) -> None:
    """AI_QUANT_KERNEL_DECISION_PROVIDER=rust fails fast when bt_runtime is missing."""
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_PROVIDER", "rust")
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_FILE", "/tmp/fake_events.json")
    monkeypatch.setattr(
        "engine.core._load_kernel_runtime_module",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ImportError("missing bt_runtime")),
    )

    with pytest.raises(SystemExit):
        _build_default_decision_provider()


def test_build_default_decision_provider_respects_noop_mode(monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_KERNEL_DECISION_PROVIDER", "none")
    monkeypatch.delenv("AI_QUANT_KERNEL_DECISION_FILE", raising=False)

    provider = _build_default_decision_provider()
    assert isinstance(provider, NoopDecisionProvider)
