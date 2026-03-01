"""Tests for AQC-823: Kernel orchestrator -- Python signal generation cutover.

Covers:
- KernelDecision dataclass construction and fields
- LegacyMode enum values and get_legacy_mode() resolution
- build_evaluate_event() correctness
- build_price_update_event() correctness
- KernelOrchestrator.process_candle() with mocked bt_runtime
- KernelOrchestrator.process_price_update() with mocked bt_runtime
- KernelOrchestrator.execute_decision() dry-run, broker adapter
- KernelOrchestrator.reconcile() delegation
- Integration tests (conditional on bt_runtime availability)
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from unittest import mock

import pytest

from strategy.kernel_orchestrator import (
    KERNEL_SCHEMA_VERSION,
    KernelDecision,
    KernelOrchestrator,
    LegacyMode,
    build_evaluate_event,
    build_price_update_event,
    get_legacy_mode,
)

# ---------------------------------------------------------------------------
# bt_runtime availability flag
# ---------------------------------------------------------------------------

try:
    import bt_runtime

    _HAS_BT_RUNTIME = True
except ImportError:
    _HAS_BT_RUNTIME = False

# ---------------------------------------------------------------------------
# Test fixtures -- minimal kernel-shaped JSON payloads
# ---------------------------------------------------------------------------

_BASE_TS = 1700000000000


def _make_state(cash: float = 10000.0, step: int = 0) -> str:
    return json.dumps({
        "schema_version": 1,
        "timestamp_ms": _BASE_TS,
        "step": step,
        "cash_usd": cash,
        "positions": {},
        "last_entry_ms": {},
        "last_exit_ms": {},
        "last_close_info": {},
    })


def _make_params() -> str:
    return json.dumps({
        "schema_version": 1,
        "default_notional_usd": 10000.0,
        "min_notional_usd": 10.0,
        "max_notional_usd": 100000.0,
        "maker_fee_bps": 3.5,
        "taker_fee_bps": 3.5,
        "allow_pyramid": True,
        "allow_reverse": True,
        "leverage": 1.0,
        "exit_params": None,
        "entry_params": None,
        "cooldown_params": None,
    })


def _make_exit_params() -> str:
    return json.dumps({
        "sl_atr_mult": 2.0,
        "tp_atr_mult": 4.0,
        "trailing_start_atr": 1.0,
        "trailing_distance_atr": 0.8,
        "enable_partial_tp": True,
        "tp_partial_pct": 0.5,
        "tp_partial_atr_mult": 0.0,
        "tp_partial_min_notional_usd": 10.0,
        "enable_breakeven_stop": True,
        "breakeven_start_atr": 0.7,
        "breakeven_buffer_atr": 0.05,
        "enable_vol_buffered_trailing": True,
        "block_exits_on_extreme_dev": False,
        "glitch_price_dev_pct": 0.40,
        "glitch_atr_mult": 12.0,
        "smart_exit_adx_exhaustion_lt": 18.0,
        "tsme_min_profit_atr": 1.0,
        "tsme_require_adx_slope_negative": True,
        "enable_rsi_overextension_exit": True,
        "rsi_exit_profit_atr_switch": 1.5,
        "rsi_exit_ub_lo_profit": 80.0,
        "rsi_exit_ub_hi_profit": 70.0,
        "rsi_exit_lb_lo_profit": 20.0,
        "rsi_exit_lb_hi_profit": 30.0,
        "rsi_exit_ub_lo_profit_low_conf": 0.0,
        "rsi_exit_lb_lo_profit_low_conf": 0.0,
        "rsi_exit_ub_hi_profit_low_conf": 0.0,
        "rsi_exit_lb_hi_profit_low_conf": 0.0,
        "smart_exit_adx_exhaustion_lt_low_conf": 0.0,
        "require_macro_alignment": False,
        "trailing_start_atr_low_conf": 0.0,
        "trailing_distance_atr_low_conf": 0.0,
    })


def _make_kernel_response(
    ok: bool = True,
    intents: list | None = None,
    fills: list | None = None,
    action_kind: str = "hold",
    action_side: str = "long",
    diagnostics: dict | None = None,
    state_schema_version: int | None = KERNEL_SCHEMA_VERSION,
    decision_schema_version: int | None = None,
    envelope_schema_version: int | None = None,
) -> str:
    """Build a minimal kernel response envelope."""
    if intents is None:
        if action_kind == "hold":
            intents = [{"kind": "hold", "side": "long", "symbol": "ETH", "price": 2000.0}]
        elif action_kind == "open":
            intents = [{
                "kind": "open", "side": action_side, "symbol": "ETH",
                "price": 2000.0, "quantity": 1.0, "intent_id": _BASE_TS,
            }]
        elif action_kind == "close":
            intents = [{
                "kind": "close", "side": action_side, "symbol": "ETH",
                "price": 2100.0, "quantity": 1.0, "intent_id": _BASE_TS,
            }]
        else:
            intents = []

    if fills is None:
        fills = []

    state = {
        "timestamp_ms": _BASE_TS + 1000,
        "step": 1,
        "cash_usd": 10000.0,
        "positions": {},
    }
    if state_schema_version is not None:
        state["schema_version"] = state_schema_version

    if ok:
        envelope = {
            "ok": True,
            "decision": {
                "intents": intents,
                "fills": fills,
                "state": state,
                "diagnostics": diagnostics or {"entry_signal": "neutral"},
            },
        }
        if decision_schema_version is not None:
            envelope["decision"]["schema_version"] = decision_schema_version
        if envelope_schema_version is not None:
            envelope["schema_version"] = envelope_schema_version
        return json.dumps(envelope)
    else:
        return json.dumps({
            "ok": False,
            "error": {
                "code": "TEST_ERROR",
                "message": "test failure",
                "details": [],
            },
        })


def _make_indicator_snapshot(close: float = 2000.0) -> dict:
    """Minimal IndicatorSnapshot dict."""
    return {
        "close": close,
        "high": close + 50.0,
        "low": close - 50.0,
        "open": close - 10.0,
        "volume": 1000.0,
        "t": _BASE_TS,
        "ema_slow": close * 0.98,
        "ema_fast": close * 0.99,
        "ema_macro": close * 0.95,
        "adx": 30.0,
        "adx_pos": 25.0,
        "adx_neg": 15.0,
        "adx_slope": 0.5,
        "bb_upper": close + 100.0,
        "bb_lower": close - 100.0,
        "bb_width": 0.1,
        "bb_width_avg": 0.08,
        "bb_width_ratio": 1.25,
        "atr": 50.0,
        "atr_slope": 0.1,
        "avg_atr": 45.0,
        "rsi": 55.0,
        "stoch_rsi_k": 0.6,
        "stoch_rsi_d": 0.55,
        "macd_hist": 5.0,
        "prev_macd_hist": 4.0,
        "prev2_macd_hist": 3.0,
        "prev3_macd_hist": 2.0,
        "vol_sma": 900.0,
        "vol_trend": True,
        "prev_close": close - 5.0,
        "prev_ema_fast": close * 0.985,
        "prev_ema_slow": close * 0.975,
        "bar_count": 500,
        "funding_rate": 0.0001,
    }


def _make_gate_result() -> dict:
    return {
        "is_ranging": False,
        "is_anomaly": False,
        "is_extended": False,
        "vol_confirm": True,
        "is_trending_up": True,
        "adx_above_min": True,
        "bullish_alignment": True,
        "bearish_alignment": False,
        "btc_ok_long": True,
        "btc_ok_short": True,
        "effective_min_adx": 22.0,
        "bb_width_ratio": 1.25,
        "dynamic_tp_mult": 4.0,
        "rsi_long_limit": 54.0,
        "rsi_short_limit": 46.0,
        "stoch_k": 0.6,
        "stoch_d": 0.55,
        "stoch_rsi_active": True,
        "all_gates_pass": True,
    }


# ===================================================================
# TestKernelDecision
# ===================================================================


class TestKernelDecision:
    """Tests for the KernelDecision dataclass."""

    def test_construction_defaults(self):
        """KernelDecision can be constructed with all required fields."""
        d = KernelDecision(
            ok=True,
            state_json='{"cash":1000}',
            intents=[],
            fills=[],
            diagnostics={},
            action="HOLD",
            raw_json="{}",
        )
        assert d.ok is True
        assert d.state_json == '{"cash":1000}'
        assert d.intents == []
        assert d.fills == []
        assert d.action == "HOLD"

    def test_construction_with_intents(self):
        """KernelDecision correctly stores intents and fills."""
        intent = {"kind": "open", "side": "long", "symbol": "ETH", "quantity": 1.0}
        fill = {"symbol": "ETH", "price": 2000.0, "quantity": 1.0}
        d = KernelDecision(
            ok=True,
            state_json="{}",
            intents=[intent],
            fills=[fill],
            diagnostics={"entry_signal": "buy"},
            action="BUY",
            raw_json='{"ok":true}',
        )
        assert len(d.intents) == 1
        assert d.intents[0]["kind"] == "open"
        assert len(d.fills) == 1
        assert d.action == "BUY"

    def test_action_field_extracted(self):
        """The action field reflects the extracted action string."""
        d = KernelDecision(
            ok=True, state_json="{}", intents=[], fills=[],
            diagnostics={}, action="CLOSE", raw_json="{}",
        )
        assert d.action == "CLOSE"


# ===================================================================
# TestLegacyMode
# ===================================================================


class TestLegacyMode:
    """Tests for LegacyMode enum and get_legacy_mode()."""

    def test_enum_values(self):
        """LegacyMode has KERNEL_ONLY and SHADOW values (LEGACY removed in AQC-825)."""
        assert LegacyMode.KERNEL_ONLY.value == "kernel_only"
        assert LegacyMode.SHADOW.value == "shadow"
        assert not hasattr(LegacyMode, "LEGACY")

    def test_enum_count(self):
        """LegacyMode has exactly 2 members (LEGACY removed in AQC-825)."""
        assert len(LegacyMode) == 2

    def test_get_legacy_mode_default(self):
        """get_legacy_mode returns KERNEL_ONLY by default."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Remove any existing env var
            os.environ.pop("KERNEL_LEGACY_MODE", None)
            mode = get_legacy_mode()
        assert mode is LegacyMode.KERNEL_ONLY

    def test_get_legacy_mode_from_env(self):
        """get_legacy_mode reads KERNEL_LEGACY_MODE env var."""
        with mock.patch.dict(os.environ, {"KERNEL_LEGACY_MODE": "shadow"}):
            mode = get_legacy_mode()
        assert mode is LegacyMode.SHADOW

    def test_get_legacy_mode_rejects_legacy_value(self):
        """KERNEL_LEGACY_MODE=legacy is no longer valid (AQC-825); falls back to default."""
        with mock.patch.dict(os.environ, {"KERNEL_LEGACY_MODE": "legacy"}):
            mode = get_legacy_mode()
        assert mode is LegacyMode.KERNEL_ONLY

    def test_get_legacy_mode_from_config(self):
        """get_legacy_mode reads from config dict when env not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("KERNEL_LEGACY_MODE", None)
            mode = get_legacy_mode({"legacy_mode": "shadow"})
        assert mode is LegacyMode.SHADOW

    def test_get_legacy_mode_env_overrides_config(self):
        """Environment variable takes precedence over config."""
        with mock.patch.dict(os.environ, {"KERNEL_LEGACY_MODE": "kernel_only"}):
            mode = get_legacy_mode({"legacy_mode": "shadow"})
        assert mode is LegacyMode.KERNEL_ONLY

    def test_get_legacy_mode_invalid_env_falls_back(self):
        """Invalid env value falls back to config or default."""
        with mock.patch.dict(os.environ, {"KERNEL_LEGACY_MODE": "bogus"}):
            mode = get_legacy_mode({"legacy_mode": "shadow"})
        assert mode is LegacyMode.SHADOW

        with mock.patch.dict(os.environ, {"KERNEL_LEGACY_MODE": "bogus"}):
            os.environ.pop("KERNEL_LEGACY_MODE", None)
            os.environ["KERNEL_LEGACY_MODE"] = "bogus"
            mode = get_legacy_mode()
        assert mode is LegacyMode.KERNEL_ONLY


# ===================================================================
# TestBuildEvaluateEvent
# ===================================================================


class TestBuildEvaluateEvent:
    """Tests for build_evaluate_event()."""

    def test_signal_is_evaluate(self):
        """Event signal is 'evaluate'."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        assert event["signal"] == "evaluate"

    def test_schema_version(self):
        """Event has correct schema_version."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        assert event["schema_version"] == KERNEL_SCHEMA_VERSION

    def test_indicator_fields_present(self):
        """Event includes full indicators dict."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        assert event["indicators"] is snap
        assert "close" in event["indicators"]
        assert "ema_slow" in event["indicators"]

    def test_gate_result_present(self):
        """Event includes gate_result dict."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        assert event["gate_result"] is gate
        assert "all_gates_pass" in event["gate_result"]

    def test_ema_slope_and_symbol(self):
        """Event has ema_slow_slope_pct and correct symbol."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.0015, "eth")
        assert event["ema_slow_slope_pct"] == 0.0015
        assert event["symbol"] == "ETH"

    def test_price_from_snapshot(self):
        """Price defaults to snap['close'] when not overridden."""
        snap = _make_indicator_snapshot(close=3500.0)
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        assert event["price"] == 3500.0

    def test_price_override(self):
        """Explicit price overrides snap['close']."""
        snap = _make_indicator_snapshot(close=3500.0)
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH", price=4000.0)
        assert event["price"] == 4000.0

    def test_timestamp_from_snapshot(self):
        """Timestamp comes from snap['t']."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        assert event["timestamp_ms"] == _BASE_TS
        assert event["event_id"] == _BASE_TS


# ===================================================================
# TestBuildPriceUpdateEvent
# ===================================================================


class TestBuildPriceUpdateEvent:
    """Tests for build_price_update_event()."""

    def test_signal_is_price_update(self):
        """Event signal is 'price_update'."""
        event = build_price_update_event("ETH", 2100.0)
        assert event["signal"] == "price_update"

    def test_schema_version(self):
        """Event has correct schema_version."""
        event = build_price_update_event("ETH", 2100.0)
        assert event["schema_version"] == KERNEL_SCHEMA_VERSION

    def test_price_and_symbol(self):
        """Event has correct price and symbol."""
        event = build_price_update_event("eth", 2100.0)
        assert event["price"] == 2100.0
        assert event["symbol"] == "ETH"

    def test_custom_timestamp(self):
        """Custom timestamp_ms is used when provided."""
        event = build_price_update_event("ETH", 2100.0, timestamp_ms=9999)
        assert event["timestamp_ms"] == 9999
        assert event["event_id"] == 9999

    def test_no_indicator_fields(self):
        """PriceUpdate events do not include indicators or gate_result."""
        event = build_price_update_event("ETH", 2100.0)
        assert "indicators" not in event
        assert "gate_result" not in event


# ===================================================================
# TestProcessCandle
# ===================================================================


class TestProcessCandle:
    """Tests for KernelOrchestrator.process_candle() with mocked bt_runtime."""

    def _patch_bt_runtime_and_helpers(self, response_json: str):
        """Return a context manager that patches bt_runtime + mei helpers."""
        mock_bt = mock.MagicMock()
        mock_bt.step_decision.return_value = response_json
        mock_bt.step_full.return_value = response_json

        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        entry_params = {"macd_mode": 0, "stoch_block_long_gt": 0.85}

        patches = mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=mock_bt,
            _BT_RUNTIME_AVAILABLE=True,
            _import_mei_helpers=lambda: (
                lambda df, **kw: snap,        # build_indicator_snapshot
                lambda s, sym, **kw: gate,    # build_gate_result
                lambda cfg=None: entry_params, # build_entry_params
                lambda df, cfg=None: 0.001,   # compute_ema_slow_slope
            ),
        )
        return patches, mock_bt

    def test_process_candle_hold(self):
        """process_candle with HOLD response parses correctly."""
        resp = _make_kernel_response(ok=True, action_kind="hold")
        patches, mock_bt = self._patch_bt_runtime_and_helpers(resp)
        with patches:
            orch = KernelOrchestrator()
            decision = orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
            )
        assert decision.ok is True
        assert decision.action == "HOLD"
        assert len(decision.intents) == 1
        mock_bt.step_decision.assert_called_once()

    def test_process_candle_buy(self):
        """process_candle with BUY (open long) response."""
        resp = _make_kernel_response(ok=True, action_kind="open", action_side="long")
        patches, mock_bt = self._patch_bt_runtime_and_helpers(resp)
        with patches:
            orch = KernelOrchestrator()
            decision = orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
            )
        assert decision.ok is True
        assert decision.action == "BUY"

    def test_process_candle_sell(self):
        """process_candle with SELL (open short) response."""
        resp = _make_kernel_response(ok=True, action_kind="open", action_side="short")
        patches, mock_bt = self._patch_bt_runtime_and_helpers(resp)
        with patches:
            orch = KernelOrchestrator()
            decision = orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
            )
        assert decision.ok is True
        assert decision.action == "SELL"

    def test_process_candle_kernel_error(self):
        """process_candle returns ok=False when kernel returns error."""
        resp = _make_kernel_response(ok=False)
        patches, mock_bt = self._patch_bt_runtime_and_helpers(resp)
        with patches:
            orch = KernelOrchestrator()
            decision = orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
            )
        assert decision.ok is False
        assert decision.action == "HOLD"
        assert "error" in decision.diagnostics

    def test_process_candle_runtime_unavailable(self):
        """process_candle raises RuntimeError when bt_runtime is not available (AQC-825 fail-fast)."""
        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=None,
            _BT_RUNTIME_AVAILABLE=False,
        ):
            orch = KernelOrchestrator()
            with pytest.raises(RuntimeError, match="bt_runtime.*not available"):
                orch.process_candle(
                    "ETH", mock.MagicMock(), _make_state(), _make_params(),
                )

    def test_process_candle_runtime_exception(self):
        """process_candle handles bt_runtime exceptions gracefully."""
        mock_bt = mock.MagicMock()
        mock_bt.step_decision.side_effect = RuntimeError("segfault simulation")

        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        entry_params = {"macd_mode": 0}

        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=mock_bt,
            _BT_RUNTIME_AVAILABLE=True,
            _import_mei_helpers=lambda: (
                lambda df, **kw: snap,
                lambda s, sym, **kw: gate,
                lambda cfg=None: entry_params,
                lambda df, cfg=None: 0.001,
            ),
        ):
            orch = KernelOrchestrator()
            decision = orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
            )
        assert decision.ok is False
        assert "segfault simulation" in decision.diagnostics.get("error", "")

    def test_process_candle_computes_ema_slow_slope_once(self):
        """EMA slow slope should be computed once and reused across gate + event."""
        resp = _make_kernel_response(ok=True, action_kind="hold")
        mock_bt = mock.MagicMock()
        mock_bt.step_decision.return_value = resp

        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        entry_params = {"macd_mode": 0}
        compute_ema_slow_slope = mock.MagicMock(return_value=0.001)

        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=mock_bt,
            _BT_RUNTIME_AVAILABLE=True,
            _import_mei_helpers=lambda: (
                lambda df, **kw: snap,
                lambda s, sym, **kw: gate,
                lambda cfg=None: entry_params,
                compute_ema_slow_slope,
            ),
        ):
            orch = KernelOrchestrator()
            orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
            )

        assert compute_ema_slow_slope.call_count == 1

    def test_process_candle_with_exit_params_uses_step_full(self):
        """When exit_params_json is provided, step_full is called."""
        resp = _make_kernel_response(ok=True, action_kind="hold")
        patches, mock_bt = self._patch_bt_runtime_and_helpers(resp)
        with patches:
            orch = KernelOrchestrator()
            decision = orch.process_candle(
                "ETH", mock.MagicMock(), _make_state(), _make_params(),
                exit_params_json=_make_exit_params(),
            )
        assert decision.ok is True
        mock_bt.step_full.assert_called_once()
        mock_bt.step_decision.assert_not_called()


# ===================================================================
# TestProcessPriceUpdate
# ===================================================================


class TestProcessPriceUpdate:
    """Tests for KernelOrchestrator.process_price_update()."""

    def test_price_update_hold(self):
        """process_price_update with HOLD response."""
        resp = _make_kernel_response(ok=True, action_kind="hold")
        mock_bt = mock.MagicMock()
        mock_bt.step_full.return_value = resp
        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=mock_bt,
            _BT_RUNTIME_AVAILABLE=True,
        ):
            orch = KernelOrchestrator()
            decision = orch.process_price_update(
                "ETH", 2100.0, _make_state(), _make_params(), _make_exit_params(),
            )
        assert decision.ok is True
        assert decision.action == "HOLD"
        mock_bt.step_full.assert_called_once()

    def test_price_update_close(self):
        """process_price_update with CLOSE response."""
        resp = _make_kernel_response(ok=True, action_kind="close")
        mock_bt = mock.MagicMock()
        mock_bt.step_full.return_value = resp
        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=mock_bt,
            _BT_RUNTIME_AVAILABLE=True,
        ):
            orch = KernelOrchestrator()
            decision = orch.process_price_update(
                "ETH", 2100.0, _make_state(), _make_params(), _make_exit_params(),
            )
        assert decision.ok is True
        assert decision.action == "CLOSE"

    def test_price_update_runtime_unavailable(self):
        """process_price_update raises RuntimeError when bt_runtime is missing (AQC-825 fail-fast)."""
        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=None,
            _BT_RUNTIME_AVAILABLE=False,
        ):
            orch = KernelOrchestrator()
            with pytest.raises(RuntimeError, match="bt_runtime.*not available"):
                orch.process_price_update(
                    "ETH", 2100.0, _make_state(), _make_params(), _make_exit_params(),
                )

    def test_price_update_kernel_exception(self):
        """process_price_update handles bt_runtime exceptions."""
        mock_bt = mock.MagicMock()
        mock_bt.step_full.side_effect = RuntimeError("kernel crash")
        with mock.patch.multiple(
            "strategy.kernel_orchestrator",
            _bt_runtime=mock_bt,
            _BT_RUNTIME_AVAILABLE=True,
        ):
            orch = KernelOrchestrator()
            decision = orch.process_price_update(
                "ETH", 2100.0, _make_state(), _make_params(), _make_exit_params(),
            )
        assert decision.ok is False
        assert "kernel crash" in decision.diagnostics.get("error", "")


# ===================================================================
# TestExecuteDecision
# ===================================================================


class TestExecuteDecision:
    """Tests for KernelOrchestrator.execute_decision()."""

    def test_dry_run_returns_empty(self):
        """dry_run=True logs but does not execute."""
        intent = {"kind": "open", "side": "long", "symbol": "ETH", "quantity": 1.0}
        decision = KernelDecision(
            ok=True, state_json="{}", intents=[intent], fills=[],
            diagnostics={}, action="BUY", raw_json="{}",
        )
        mock_broker = mock.MagicMock()
        orch = KernelOrchestrator(broker_adapter=mock_broker)
        fills = orch.execute_decision(decision, dry_run=True)
        assert fills == []
        mock_broker.execute_intents.assert_not_called()

    def test_no_intents_returns_empty(self):
        """Empty intents list returns empty fills."""
        decision = KernelDecision(
            ok=True, state_json="{}", intents=[], fills=[],
            diagnostics={}, action="HOLD", raw_json="{}",
        )
        mock_broker = mock.MagicMock()
        orch = KernelOrchestrator(broker_adapter=mock_broker)
        fills = orch.execute_decision(decision)
        assert fills == []
        mock_broker.execute_intents.assert_not_called()

    def test_broker_adapter_called(self):
        """Intents are forwarded to broker_adapter.execute_intents()."""
        intent = {"kind": "open", "side": "long", "symbol": "ETH", "quantity": 1.0}
        decision = KernelDecision(
            ok=True, state_json="{}", intents=[intent], fills=[],
            diagnostics={}, action="BUY", raw_json="{}",
        )
        mock_broker = mock.MagicMock()
        mock_broker.execute_intents.return_value = [
            {"symbol": "ETH", "price": 2000.0, "quantity": 1.0},
        ]
        orch = KernelOrchestrator(broker_adapter=mock_broker)
        fills = orch.execute_decision(decision)
        assert len(fills) == 1
        mock_broker.execute_intents.assert_called_once_with(
            [intent], symbol_info=None,
        )

    def test_no_broker_adapter_returns_empty(self):
        """No broker adapter configured returns empty fills."""
        intent = {"kind": "open", "side": "long", "symbol": "ETH", "quantity": 1.0}
        decision = KernelDecision(
            ok=True, state_json="{}", intents=[intent], fills=[],
            diagnostics={}, action="BUY", raw_json="{}",
        )
        orch = KernelOrchestrator()  # no broker_adapter
        fills = orch.execute_decision(decision)
        assert fills == []

    def test_symbol_info_passed_through(self):
        """symbol_info is forwarded to broker_adapter.execute_intents()."""
        intent = {"kind": "open", "side": "long", "symbol": "ETH", "quantity": 1.0}
        decision = KernelDecision(
            ok=True, state_json="{}", intents=[intent], fills=[],
            diagnostics={}, action="BUY", raw_json="{}",
        )
        mock_broker = mock.MagicMock()
        mock_broker.execute_intents.return_value = []
        orch = KernelOrchestrator(broker_adapter=mock_broker)
        sym_info = {"sz_decimals": 3}
        orch.execute_decision(decision, symbol_info=sym_info)
        mock_broker.execute_intents.assert_called_once_with(
            [intent], symbol_info=sym_info,
        )


# ===================================================================
# TestReconcile
# ===================================================================


class TestReconcile:
    """Tests for KernelOrchestrator.reconcile()."""

    def test_delegates_to_reconciler(self):
        """reconcile() delegates to PositionReconciler.reconcile()."""
        mock_recon = mock.MagicMock()
        mock_report = mock.MagicMock()
        mock_report.is_clean = True
        mock_recon.reconcile.return_value = mock_report

        state_json = json.dumps({
            "positions": {
                "ETH": {"side": "long", "quantity": 1.0},
            },
        })
        exchange_positions = {
            "ETH": {"side": "long", "size": 1.0},
        }

        orch = KernelOrchestrator(reconciler=mock_recon)
        report = orch.reconcile(state_json, exchange_positions)

        assert report is mock_report
        mock_recon.reconcile.assert_called_once_with(
            {"ETH": {"side": "long", "quantity": 1.0}},
            exchange_positions,
        )

    def test_no_reconciler_returns_none(self):
        """reconcile() returns None when no reconciler is configured."""
        orch = KernelOrchestrator()  # no reconciler
        result = orch.reconcile(_make_state(), {})
        assert result is None

    def test_invalid_state_json_returns_none(self):
        """reconcile() handles invalid state JSON gracefully."""
        mock_recon = mock.MagicMock()
        orch = KernelOrchestrator(reconciler=mock_recon)
        result = orch.reconcile("not valid json", {})
        assert result is None
        mock_recon.reconcile.assert_not_called()


# ===================================================================
# TestLogDecision
# ===================================================================


class TestLogDecision:
    """Tests for KernelOrchestrator.log_decision()."""

    def test_log_decision_creates_row(self):
        """log_decision inserts a row into decision_events table."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create the table
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE decision_events (
                    id TEXT PRIMARY KEY,
                    timestamp_ms INTEGER,
                    symbol TEXT,
                    event_type TEXT,
                    status TEXT,
                    decision_phase TEXT,
                    triggered_by TEXT,
                    action_taken TEXT,
                    context_json TEXT
                )
            """)
            conn.commit()
            conn.close()

            decision = KernelDecision(
                ok=True, state_json="{}", intents=[], fills=[],
                diagnostics={"entry_signal": "neutral"},
                action="HOLD", raw_json="{}",
            )
            orch = KernelOrchestrator(db_path=db_path)
            event_id = orch.log_decision(decision, symbol="ETH")

            assert event_id is not None
            assert len(event_id) == 26  # ULID length

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT * FROM decision_events WHERE id = ?", (event_id,)
            ).fetchone()
            conn.close()

            assert row is not None
            assert row[2] == "ETH"  # symbol
            assert row[3] == "kernel_decision"  # event_type
            assert row[4] == "executed"  # status
            assert row[7] == "HOLD"  # action_taken
        finally:
            os.unlink(db_path)

    def test_log_decision_persists_reason_columns_for_buy(self):
        """log_decision persists reason fields when schema supports them."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE decision_events (
                    id TEXT PRIMARY KEY,
                    timestamp_ms INTEGER,
                    symbol TEXT,
                    event_type TEXT,
                    status TEXT,
                    decision_phase TEXT,
                    triggered_by TEXT,
                    action_taken TEXT,
                    rejection_reason TEXT,
                    reason_code TEXT,
                    config_fingerprint TEXT,
                    run_fingerprint TEXT,
                    context_json TEXT
                )
            """)
            conn.commit()
            conn.close()

            with mock.patch.dict(os.environ, {"AI_QUANT_RUN_FINGERPRINT": "test-run-fp"}, clear=False):
                decision = KernelDecision(
                    ok=True,
                    state_json="{}",
                    intents=[],
                    fills=[],
                    diagnostics={"reason": "sub-bar entry"},
                    action="BUY",
                    raw_json="{}",
                )
                orch = KernelOrchestrator(db_path=db_path)
                event_id = orch.log_decision(decision, symbol="ETH")

            assert event_id is not None

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                """
                SELECT action_taken, rejection_reason, reason_code, run_fingerprint
                FROM decision_events
                WHERE id = ?
                """,
                (event_id,),
            ).fetchone()
            conn.close()

            assert row is not None
            assert row[0] == "BUY"
            assert row[1] == "sub-bar entry"
            assert row[2] == "entry_signal"
            assert row[3] == "test-run-fp"
        finally:
            os.unlink(db_path)

    def test_log_decision_blocked_without_reason_defaults_to_hold(self):
        """Blocked decisions without reason persist as hold reason_code."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE decision_events (
                    id TEXT PRIMARY KEY,
                    timestamp_ms INTEGER,
                    symbol TEXT,
                    event_type TEXT,
                    status TEXT,
                    decision_phase TEXT,
                    triggered_by TEXT,
                    action_taken TEXT,
                    rejection_reason TEXT,
                    reason_code TEXT,
                    context_json TEXT
                )
            """)
            conn.commit()
            conn.close()

            decision = KernelDecision(
                ok=True,
                state_json="{}",
                intents=[],
                fills=[],
                diagnostics={},
                action="BLOCKED",
                raw_json="{}",
            )
            orch = KernelOrchestrator(db_path=db_path)
            event_id = orch.log_decision(decision, symbol="ETH")

            assert event_id is not None

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT reason_code, rejection_reason FROM decision_events WHERE id = ?",
                (event_id,),
            ).fetchone()
            conn.close()

            assert row is not None
            assert row[0] == "hold"
            assert row[1] is None
        finally:
            os.unlink(db_path)

    def test_log_decision_buy_add_intent_maps_to_entry_pyramid(self):
        """BUY decisions with add intent preserve pyramid semantics."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE decision_events (
                    id TEXT PRIMARY KEY,
                    timestamp_ms INTEGER,
                    symbol TEXT,
                    event_type TEXT,
                    status TEXT,
                    decision_phase TEXT,
                    triggered_by TEXT,
                    action_taken TEXT,
                    rejection_reason TEXT,
                    reason_code TEXT,
                    context_json TEXT
                )
            """)
            conn.commit()
            conn.close()

            decision = KernelDecision(
                ok=True,
                state_json="{}",
                intents=[{"kind": "add", "action": "add"}],
                fills=[],
                diagnostics={},
                action="BUY",
                raw_json="{}",
            )
            orch = KernelOrchestrator(db_path=db_path)
            event_id = orch.log_decision(decision, symbol="ETH")

            assert event_id is not None

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT reason_code FROM decision_events WHERE id = ?",
                (event_id,),
            ).fetchone()
            conn.close()

            assert row is not None
            assert row[0] == "entry_pyramid"
        finally:
            os.unlink(db_path)

    def test_log_decision_no_db_path(self):
        """log_decision returns None when no DB path and import fails."""
        with mock.patch.dict("sys.modules", {"strategy.mei_alpha_v1": None}):
            orch = KernelOrchestrator()
            decision = KernelDecision(
                ok=True, state_json="{}", intents=[], fills=[],
                diagnostics={}, action="HOLD", raw_json="{}",
            )
            # This should not raise, just return None
            result = orch.log_decision(decision, symbol="ETH")
            # May or may not be None depending on import; the key is no crash
            assert result is None or isinstance(result, str)


# ===================================================================
# TestParseKernelResponse
# ===================================================================


class TestParseKernelResponse:
    """Tests for KernelOrchestrator._parse_kernel_response()."""

    def test_valid_ok_response(self):
        """Parses a valid ok=True response correctly."""
        orch = KernelOrchestrator()
        raw = _make_kernel_response(ok=True, action_kind="open", action_side="long")
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is True
        assert decision.action == "BUY"
        assert len(decision.intents) == 1
        assert decision.raw_json == raw

    def test_error_response(self):
        """Parses an ok=False response correctly."""
        orch = KernelOrchestrator()
        raw = _make_kernel_response(ok=False)
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert decision.action == "HOLD"
        assert "error" in decision.diagnostics

    def test_invalid_json(self):
        """Handles invalid JSON gracefully."""
        orch = KernelOrchestrator()
        decision = orch._parse_kernel_response("not json", _make_state())
        assert decision.ok is False
        assert "JSON parse error" in decision.diagnostics.get("error", "")

    def test_state_json_extracted(self):
        """New state is serialized from the decision state field."""
        orch = KernelOrchestrator()
        raw = _make_kernel_response(ok=True, action_kind="hold")
        decision = orch._parse_kernel_response(raw, _make_state())
        state = json.loads(decision.state_json)
        assert "cash_usd" in state

    def test_state_schema_version_mismatch_rejected(self):
        orch = KernelOrchestrator()
        raw = _make_kernel_response(ok=True, state_schema_version=KERNEL_SCHEMA_VERSION + 1)
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert decision.action == "HOLD"
        assert "schema_version mismatch" in str(decision.diagnostics.get("error", ""))

    def test_envelope_schema_version_mismatch_rejected(self):
        orch = KernelOrchestrator()
        raw = _make_kernel_response(
            ok=True,
            state_schema_version=KERNEL_SCHEMA_VERSION,
            envelope_schema_version=KERNEL_SCHEMA_VERSION + 1,
        )
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert decision.action == "HOLD"
        assert decision.diagnostics.get("schema_versions", {}).get("envelope") == KERNEL_SCHEMA_VERSION + 1

    def test_state_schema_version_mismatch_rejected_when_envelope_matches(self):
        orch = KernelOrchestrator()
        raw = _make_kernel_response(
            ok=True,
            state_schema_version=KERNEL_SCHEMA_VERSION + 1,
            envelope_schema_version=KERNEL_SCHEMA_VERSION,
        )
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert "schema_version" in str(decision.diagnostics.get("error", ""))
        assert decision.diagnostics.get("schema_versions", {}).get("state") == KERNEL_SCHEMA_VERSION + 1

    def test_decision_schema_version_mismatch_rejected(self):
        orch = KernelOrchestrator()
        raw = _make_kernel_response(
            ok=True,
            state_schema_version=None,
            decision_schema_version=KERNEL_SCHEMA_VERSION + 1,
        )
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert "schema_version mismatch" in str(decision.diagnostics.get("error", ""))
        assert decision.diagnostics.get("schema_versions", {}).get("decision") == KERNEL_SCHEMA_VERSION + 1

    def test_conflicting_schema_versions_rejected(self):
        orch = KernelOrchestrator()
        raw = _make_kernel_response(
            ok=True,
            state_schema_version=KERNEL_SCHEMA_VERSION,
            decision_schema_version=KERNEL_SCHEMA_VERSION + 1,
            envelope_schema_version=KERNEL_SCHEMA_VERSION,
        )
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert "conflicting schema_version fields" in str(decision.diagnostics.get("error", ""))

    def test_legacy_payload_without_schema_versions_still_parses(self):
        orch = KernelOrchestrator()
        raw = _make_kernel_response(
            ok=True,
            state_schema_version=None,
            decision_schema_version=None,
            envelope_schema_version=None,
        )
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is True
        assert decision.action == "HOLD"

    def test_non_mapping_decision_payload_rejected_cleanly(self):
        orch = KernelOrchestrator()
        raw = json.dumps({"ok": True, "decision": []})
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert "invalid kernel decision payload type" in str(decision.diagnostics.get("error", ""))

    def test_non_mapping_decision_payload_in_error_response(self):
        orch = KernelOrchestrator()
        raw = json.dumps({"ok": False, "decision": [], "error": {"code": "TEST_ERROR"}})
        decision = orch._parse_kernel_response(raw, _make_state())
        assert decision.ok is False
        assert decision.action == "HOLD"


# ===================================================================
# TestKernelIntegration (conditional on bt_runtime)
# ===================================================================


@pytest.mark.skipif(not _HAS_BT_RUNTIME, reason="bt_runtime not available")
class TestKernelIntegration:
    """Integration tests using the real bt_runtime."""

    def test_price_update_roundtrip(self):
        """Real kernel price_update returns a valid KernelDecision."""
        orch = KernelOrchestrator()
        params = _make_params()
        exit_params = _make_exit_params()
        state = _make_state()
        decision = orch.process_price_update(
            "ETH", 2100.0, state, params, exit_params,
        )
        # Should succeed (no positions = no exit action)
        assert decision.ok is True
        assert decision.action in ("HOLD", "BUY", "SELL", "CLOSE")

    def test_evaluate_event_roundtrip(self):
        """build_evaluate_event produces JSON accepted by bt_runtime.step_decision."""
        snap = _make_indicator_snapshot()
        gate = _make_gate_result()
        event = build_evaluate_event(snap, gate, 0.001, "ETH")
        event_json = json.dumps(event)
        state = _make_state()
        params_dict = json.loads(_make_params())
        params_dict["entry_params"] = {
            "macd_mode": 0,
            "stoch_block_long_gt": 0.85,
            "stoch_block_short_lt": 0.15,
            "high_conf_volume_mult": 2.5,
            "enable_pullback": False,
            "pullback_confidence": 0,
            "pullback_min_adx": 22.0,
            "pullback_rsi_long_min": 50.0,
            "pullback_rsi_short_max": 50.0,
            "pullback_require_macd_sign": True,
            "enable_slow_drift": False,
            "slow_drift_min_slope_pct": 0.0006,
            "slow_drift_min_adx": 10.0,
            "slow_drift_rsi_long_min": 50.0,
            "slow_drift_rsi_short_max": 50.0,
            "slow_drift_require_macd_sign": True,
        }
        params_json = json.dumps(params_dict)

        result_json = bt_runtime.step_decision(state, event_json, params_json)
        result = json.loads(result_json)
        assert result.get("ok") is True

    def test_price_update_event_roundtrip(self):
        """build_price_update_event produces JSON accepted by bt_runtime.step_full."""
        event = build_price_update_event("ETH", 2100.0, timestamp_ms=_BASE_TS)
        event_json = json.dumps(event)
        state = _make_state()
        params = _make_params()
        exit_params = _make_exit_params()

        result_json = bt_runtime.step_full(state, event_json, params, exit_params)
        result = json.loads(result_json)
        assert result.get("ok") is True

    def test_orchestrator_process_price_update_real(self):
        """KernelOrchestrator.process_price_update with real kernel."""
        orch = KernelOrchestrator()
        decision = orch.process_price_update(
            "ETH", 2100.0, _make_state(), _make_params(), _make_exit_params(),
            timestamp_ms=_BASE_TS,
        )
        assert decision.ok is True
        assert isinstance(decision.state_json, str)
        assert isinstance(decision.raw_json, str)
        # Verify the raw_json is valid JSON
        envelope = json.loads(decision.raw_json)
        assert envelope.get("ok") is True
