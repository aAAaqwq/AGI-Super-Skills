"""Tests for AQC-822: Decision parity test — backtest vs live kernel.

Covers:
- DecisionParityHarness.record_decision / replay_decision / replay_all
- DecisionParityHarness.verify_determinism
- DecisionParityHarness.compare_results
- DecisionParityHarness.build_fixture / load_fixture
- extract_action()
- normalize_result_for_comparison()
- Integration tests (conditional on bt_runtime availability)
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest import mock

import pytest

from strategy.parity_test import (
    DecisionParityHarness,
    DeterminismResult,
    ParityReport,
    ParityResult,
    extract_action,
    normalize_result_for_comparison,
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
# Test fixtures — minimal kernel-shaped JSON payloads
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


def _make_event(signal: str = "buy", price: float = 2000.0) -> str:
    return json.dumps({
        "schema_version": 1,
        "event_id": _BASE_TS + 1,
        "timestamp_ms": _BASE_TS + 1,
        "symbol": "ETH",
        "signal": signal,
        "price": price,
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


def _make_result(
    intents: list | None = None,
    fills: list | None = None,
    diagnostics: dict | None = None,
    state: dict | None = None,
) -> str:
    """Build a minimal DecisionResult envelope."""
    return json.dumps({
        "ok": True,
        "decision": {
            "schema_version": 1,
            "state": state or {
                "schema_version": 1,
                "timestamp_ms": _BASE_TS + 1,
                "step": 1,
                "cash_usd": 10000.0,
                "positions": {},
                "last_entry_ms": {},
                "last_exit_ms": {},
                "last_close_info": {},
            },
            "intents": intents or [],
            "fills": fills or [],
            "diagnostics": diagnostics or {
                "schema_version": 1,
                "errors": [],
                "warnings": [],
                "intent_count": 0,
                "fill_count": 0,
                "step": 1,
                "gate_blocked": False,
                "gate_block_reasons": [],
                "entry_signal": None,
                "entry_confidence": None,
                "cooldown_blocked": False,
                "pesc_blocked": False,
                "indicator_snapshot": None,
                "applied_thresholds": [],
                "exit_context": None,
                "confidence_factors": [],
            },
        },
    })


def _make_result_with_intent(
    kind: str = "open",
    side: str = "long",
) -> str:
    """Build a result with one OrderIntent.

    Real kernel schema: ``kind`` is one of ``"open"`` / ``"add"`` /
    ``"close"`` / ``"hold"`` / ``"reverse"``; ``side`` is ``"long"`` /
    ``"short"`` (PositionSide, snake_case).
    """
    return _make_result(intents=[{
        "schema_version": 1,
        "intent_id": _BASE_TS,
        "symbol": "ETH",
        "kind": kind,
        "side": side,
        "quantity": 1.0,
        "price": 2000.0,
        "notional_usd": 2000.0,
        "fee_rate": 0.00035,
    }])


def _make_result_with_fill(side: str = "long") -> str:
    """Build a result with one FillEvent.

    Real kernel schema: ``FillEvent.side`` is ``PositionSide``
    (``"long"`` / ``"short"``), NOT composite values like ``"close_long"``.
    To represent a close, pass a close intent alongside the fill.
    """
    return _make_result(fills=[{
        "schema_version": 1,
        "intent_id": _BASE_TS,
        "symbol": "ETH",
        "side": side,
        "quantity": 1.0,
        "price": 2100.0,
        "notional_usd": 2100.0,
        "fee_usd": 0.735,
        "pnl_usd": 99.265,
    }])


def _make_result_with_close_fill(side: str = "long") -> str:
    """Build a result with a close intent AND its corresponding fill.

    This correctly models the real kernel output for a position close:
    the intent has ``kind: "close"`` and the fill has ``side: "long"``
    (the side of the position being closed).
    """
    return _make_result(
        intents=[{
            "schema_version": 1,
            "intent_id": _BASE_TS,
            "symbol": "ETH",
            "kind": "close",
            "side": side,
            "quantity": 1.0,
            "price": 2100.0,
            "notional_usd": 2100.0,
            "fee_rate": 0.00035,
        }],
        fills=[{
            "schema_version": 1,
            "intent_id": _BASE_TS,
            "symbol": "ETH",
            "side": side,
            "quantity": 1.0,
            "price": 2100.0,
            "notional_usd": 2100.0,
            "fee_usd": 0.735,
            "pnl_usd": 99.265,
        }],
    )


def _make_exit_params() -> str:
    return json.dumps({
        "atr_sl_mult": 2.0,
        "atr_tp_mult": 3.0,
        "trailing_activation_mult": 1.5,
        "trailing_callback_pct": 0.02,
        "max_hold_bars": 100,
    })


# ---------------------------------------------------------------------------
# Mock bt_runtime for unit tests
# ---------------------------------------------------------------------------

def _make_mock_bt_runtime(return_json: str | None = None):
    """Create a mock bt_runtime module with step_decision and step_full."""
    m = mock.MagicMock()
    if return_json is not None:
        m.step_decision.return_value = return_json
        m.step_full.return_value = return_json
    return m


# ===========================================================================
# TestRecordAndReplay
# ===========================================================================


class TestRecordAndReplay:
    """Record a decision, replay through mocked bt_runtime, check parity."""

    def test_record_and_replay_match(self):
        """Record a decision, replay with identical kernel output -> match."""
        result_json = _make_result()
        harness = DecisionParityHarness()
        rid = harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_json,
        )
        assert rid == 0

        mock_rt = _make_mock_bt_runtime(result_json)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            pr = harness.replay_decision(rid)

        assert isinstance(pr, ParityResult)
        assert pr.is_match is True
        assert pr.diffs == []
        assert pr.original_action == "HOLD"
        assert pr.replayed_action == "HOLD"

    def test_multiple_recordings_replayed(self):
        """Multiple recordings can each be replayed independently."""
        result1 = _make_result()
        result2 = _make_result_with_intent("open", "long")

        harness = DecisionParityHarness()
        rid1 = harness.record_decision(
            _make_state(), _make_event(), _make_params(), result1,
        )
        rid2 = harness.record_decision(
            _make_state(), _make_event("sell"), _make_params(), result2,
        )
        assert rid1 == 0
        assert rid2 == 1

        # Replay first recording
        mock_rt = _make_mock_bt_runtime(result1)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            pr1 = harness.replay_decision(rid1)
        assert pr1.is_match is True

        # Replay second recording
        mock_rt2 = _make_mock_bt_runtime(result2)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt2), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            pr2 = harness.replay_decision(rid2)
        assert pr2.is_match is True

    def test_replay_detects_mismatch(self):
        """Replay detects when the kernel returns a different result."""
        original = _make_result()
        different = _make_result_with_intent("open", "long")

        harness = DecisionParityHarness()
        rid = harness.record_decision(
            _make_state(), _make_event(), _make_params(), original,
        )

        mock_rt = _make_mock_bt_runtime(different)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            pr = harness.replay_decision(rid)

        assert pr.is_match is False
        assert len(pr.diffs) > 0
        assert pr.original_action == "HOLD"
        assert pr.replayed_action == "BUY"

    def test_exit_params_uses_step_full(self):
        """Recording with exit_params replays via step_full."""
        result_json = _make_result()
        harness = DecisionParityHarness()
        rid = harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_json,
            exit_params_json=_make_exit_params(),
        )

        mock_rt = _make_mock_bt_runtime(result_json)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            pr = harness.replay_decision(rid)

        assert pr.is_match is True
        mock_rt.step_full.assert_called_once()
        mock_rt.step_decision.assert_not_called()

    def test_no_exit_params_uses_step_decision(self):
        """Recording without exit_params replays via step_decision."""
        result_json = _make_result()
        harness = DecisionParityHarness()
        rid = harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_json,
        )

        mock_rt = _make_mock_bt_runtime(result_json)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            pr = harness.replay_decision(rid)

        assert pr.is_match is True
        mock_rt.step_decision.assert_called_once()
        mock_rt.step_full.assert_not_called()

    def test_replay_all_aggregates(self):
        """replay_all returns a ParityReport with correct aggregates."""
        result_ok = _make_result()

        harness = DecisionParityHarness()
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_ok,
        )
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_ok,
        )

        mock_rt = _make_mock_bt_runtime(result_ok)
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            report = harness.replay_all()

        assert isinstance(report, ParityReport)
        assert report.total_decisions == 2
        assert report.matches == 2
        assert report.mismatches == 0
        assert report.match_rate == 1.0
        assert report.is_perfect_parity is True
        assert report.mismatch_details == []

    def test_replay_all_with_mismatches(self):
        """replay_all correctly reports mismatches."""
        result_ok = _make_result()
        result_different = _make_result_with_intent("open", "short")

        harness = DecisionParityHarness()
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_ok,
        )
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), result_ok,
        )

        # Kernel returns different result on second call
        call_count = {"n": 0}
        original_result_ok = result_ok
        original_result_diff = result_different

        def side_effect_step(s, e, p):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return original_result_ok
            return original_result_diff

        mock_rt = mock.MagicMock()
        mock_rt.step_decision.side_effect = side_effect_step

        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            report = harness.replay_all()

        assert report.total_decisions == 2
        assert report.matches == 1
        assert report.mismatches == 1
        assert report.is_perfect_parity is False
        assert len(report.mismatch_details) == 1

    def test_replay_unknown_recording_raises(self):
        """Replaying a non-existent recording_id raises ValueError."""
        harness = DecisionParityHarness()
        mock_rt = _make_mock_bt_runtime(_make_result())
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            with pytest.raises(ValueError, match="recording 999 not found"):
                harness.replay_decision(999)


# ===========================================================================
# TestVerifyDeterminism
# ===========================================================================


class TestVerifyDeterminism:
    """Verify that the kernel produces identical results across N runs."""

    def test_deterministic_kernel(self):
        """All iterations return same result -> is_deterministic=True."""
        result_json = _make_result()
        mock_rt = _make_mock_bt_runtime(result_json)

        harness = DecisionParityHarness()
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            dr = harness.verify_determinism(
                _make_state(), _make_event(), _make_params(),
                iterations=5,
            )

        assert isinstance(dr, DeterminismResult)
        assert dr.iterations == 5
        assert dr.is_deterministic is True
        assert dr.variations == []

    def test_non_deterministic_detected(self):
        """Different results across iterations -> is_deterministic=False."""
        result_a = _make_result()
        result_b = _make_result_with_intent("open", "long")

        call_count = {"n": 0}

        def side_effect(s, e, p):
            call_count["n"] += 1
            return result_a if call_count["n"] <= 2 else result_b

        mock_rt = mock.MagicMock()
        mock_rt.step_decision.side_effect = side_effect

        harness = DecisionParityHarness()
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            dr = harness.verify_determinism(
                _make_state(), _make_event(), _make_params(),
                iterations=5,
            )

        assert dr.is_deterministic is False
        assert len(dr.variations) > 0

    def test_custom_iteration_count(self):
        """Custom iteration count is respected."""
        result_json = _make_result()
        mock_rt = _make_mock_bt_runtime(result_json)

        harness = DecisionParityHarness()
        with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
            dr = harness.verify_determinism(
                _make_state(), _make_event(), _make_params(),
                iterations=20,
            )

        assert dr.iterations == 20
        # Baseline call + 19 comparison calls = 20 total calls
        assert mock_rt.step_decision.call_count == 20

    def test_raises_without_bt_runtime(self):
        """verify_determinism raises RuntimeError when bt_runtime absent."""
        harness = DecisionParityHarness()
        with mock.patch("strategy.parity_test._bt_runtime", None), \
             mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="bt_runtime is not available"):
                harness.verify_determinism(
                    _make_state(), _make_event(), _make_params(),
                )


# ===========================================================================
# TestCompareResults
# ===========================================================================


class TestCompareResults:
    """Deep comparison of two DecisionResult JSON strings."""

    def setup_method(self):
        self.harness = DecisionParityHarness()

    def test_identical_results_match(self):
        """Two identical results produce is_match=True, no diffs."""
        r = _make_result()
        is_match, diffs = self.harness.compare_results(r, r)
        assert is_match is True
        assert diffs == []

    def test_different_intents_detected(self):
        """Different intents are reported."""
        r1 = _make_result()
        r2 = _make_result_with_intent("open", "long")
        is_match, diffs = self.harness.compare_results(r1, r2)
        assert is_match is False
        assert any("intents differ" in d for d in diffs)

    def test_different_fills_detected(self):
        """Different fills are reported."""
        r1 = _make_result()
        r2 = _make_result_with_close_fill("long")
        is_match, diffs = self.harness.compare_results(r1, r2)
        assert is_match is False
        assert any("fills differ" in d for d in diffs)

    def test_ignores_non_deterministic_fields(self):
        """timestamp_ms, step, event_id differences are ignored."""
        r1 = _make_result()
        # Change only non-deterministic fields
        data = json.loads(r1)
        data["decision"]["state"]["timestamp_ms"] = _BASE_TS + 9999
        data["decision"]["diagnostics"]["step"] = 42
        r2 = json.dumps(data)

        is_match, diffs = self.harness.compare_results(r1, r2)
        assert is_match is True
        assert diffs == []

    def test_state_differences_detected(self):
        """Differences in state (cash, positions) are reported."""
        r1 = _make_result()
        data = json.loads(r1)
        data["decision"]["state"]["cash_usd"] = 5000.0
        r2 = json.dumps(data)

        is_match, diffs = self.harness.compare_results(r1, r2)
        assert is_match is False
        assert any("state differs" in d for d in diffs)

    def test_diagnostics_differences_detected(self):
        """Differences in diagnostics are reported."""
        r1 = _make_result()
        data = json.loads(r1)
        data["decision"]["diagnostics"]["gate_blocked"] = True
        data["decision"]["diagnostics"]["gate_block_reasons"] = ["anomaly"]
        r2 = json.dumps(data)

        is_match, diffs = self.harness.compare_results(r1, r2)
        assert is_match is False
        assert any("diagnostics differ" in d for d in diffs)

    def test_intent_id_ignored(self):
        """intent_id is stripped (timestamp-based); only kind/side matter."""
        r1 = _make_result_with_intent("open", "long")
        data = json.loads(r1)
        data["decision"]["intents"][0]["intent_id"] = 9999999
        r2 = json.dumps(data)

        is_match, diffs = self.harness.compare_results(r1, r2)
        assert is_match is True
        assert diffs == []


# ===========================================================================
# TestFixtures
# ===========================================================================


class TestFixtures:
    """Build and load JSON fixture files."""

    def test_build_fixture_creates_valid_json(self):
        """build_fixture writes a JSON array with correct schema."""
        harness = DecisionParityHarness()
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), _make_result(),
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            path = fh.name

        try:
            harness.build_fixture(output_path=path)
            with open(path) as f:
                items = json.load(f)
            assert isinstance(items, list)
            assert len(items) == 1
            assert "state" in items[0]
            assert "event" in items[0]
            assert "params" in items[0]
            assert "expected_result" in items[0]
        finally:
            os.unlink(path)

    def test_load_fixture_populates_recordings(self):
        """load_fixture reads a fixture and creates recordings."""
        harness = DecisionParityHarness()
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), _make_result(),
        )
        harness.record_decision(
            _make_state(), _make_event("sell"), _make_params(),
            _make_result_with_intent("open", "short"),
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            path = fh.name

        try:
            harness.build_fixture(output_path=path)

            new_harness = DecisionParityHarness()
            count = new_harness.load_fixture(path)
            assert count == 2
        finally:
            os.unlink(path)

    def test_round_trip_build_load_replay(self):
        """Build fixture -> load -> replay reproduces original parity."""
        original_result = _make_result()
        harness = DecisionParityHarness()
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), original_result,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            path = fh.name

        try:
            harness.build_fixture(output_path=path)

            new_harness = DecisionParityHarness()
            new_harness.load_fixture(path)

            mock_rt = _make_mock_bt_runtime(original_result)
            with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
                 mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
                report = new_harness.replay_all()

            assert report.is_perfect_parity is True
            assert report.total_decisions == 1
        finally:
            os.unlink(path)

    def test_empty_fixture_handled(self):
        """An empty fixture loads zero recordings."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False,
        ) as fh:
            json.dump([], fh)
            path = fh.name

        try:
            harness = DecisionParityHarness()
            count = harness.load_fixture(path)
            assert count == 0
        finally:
            os.unlink(path)

    def test_fixture_with_exit_params(self):
        """Fixture round-trip preserves exit_params."""
        harness = DecisionParityHarness()
        harness.record_decision(
            _make_state(), _make_event(), _make_params(), _make_result(),
            exit_params_json=_make_exit_params(),
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            path = fh.name

        try:
            harness.build_fixture(output_path=path)
            with open(path) as f:
                items = json.load(f)
            assert "exit_params" in items[0]
            assert items[0]["exit_params"]["atr_sl_mult"] == 2.0

            new_harness = DecisionParityHarness()
            new_harness.load_fixture(path)

            mock_rt = _make_mock_bt_runtime(_make_result())
            with mock.patch("strategy.parity_test._bt_runtime", mock_rt), \
                 mock.patch("strategy.parity_test._BT_RUNTIME_AVAILABLE", True):
                new_harness.replay_decision(0)
            mock_rt.step_full.assert_called_once()
        finally:
            os.unlink(path)


# ===========================================================================
# TestExtractAction
# ===========================================================================


class TestExtractAction:
    """extract_action() resolves the primary action from a DecisionResult."""

    def test_buy_intent(self):
        """open long intent -> BUY."""
        r = _make_result_with_intent("open", "long")
        assert extract_action(r) == "BUY"

    def test_sell_intent(self):
        """open short intent -> SELL."""
        r = _make_result_with_intent("open", "short")
        assert extract_action(r) == "SELL"

    def test_close_fill(self):
        """close intent + fill -> CLOSE."""
        r = _make_result_with_close_fill("long")
        assert extract_action(r) == "CLOSE"

    def test_no_intents_no_fills_hold(self):
        """Empty intents and fills -> HOLD."""
        r = _make_result()
        assert extract_action(r) == "HOLD"

    def test_multiple_intents_first_wins(self):
        """Multiple intents: first intent's action is returned."""
        r = _make_result(intents=[
            {"schema_version": 1, "intent_id": 1, "symbol": "ETH",
             "kind": "open", "side": "long", "quantity": 1.0,
             "price": 2000.0, "notional_usd": 2000.0, "fee_rate": 0.00035},
            {"schema_version": 1, "intent_id": 2, "symbol": "ETH",
             "kind": "open", "side": "short", "quantity": 0.5,
             "price": 2000.0, "notional_usd": 1000.0, "fee_rate": 0.00035},
        ])
        assert extract_action(r) == "BUY"

    def test_close_short_fill(self):
        """close intent + short fill -> CLOSE."""
        r = _make_result_with_close_fill("short")
        assert extract_action(r) == "CLOSE"

    def test_add_long_intent(self):
        """add long intent -> BUY."""
        r = _make_result_with_intent("add", "long")
        assert extract_action(r) == "BUY"

    def test_close_intent_only(self):
        """close intent without fill -> CLOSE."""
        r = _make_result_with_intent("close", "long")
        assert extract_action(r) == "CLOSE"

    def test_hold_intent(self):
        """hold intent -> HOLD."""
        r = _make_result_with_intent("hold", "long")
        assert extract_action(r) == "HOLD"

    def test_reverse_long_intent(self):
        """reverse to long -> BUY."""
        r = _make_result_with_intent("reverse", "long")
        assert extract_action(r) == "BUY"


# ===========================================================================
# TestNormalizeResult
# ===========================================================================


class TestNormalizeResult:
    """normalize_result_for_comparison strips non-deterministic fields."""

    def test_strips_timestamp_ms_from_state(self):
        """timestamp_ms is removed from decision.state."""
        r = _make_result()
        norm = normalize_result_for_comparison(r)
        state = norm["decision"]["state"]
        assert "timestamp_ms" not in state

    def test_strips_step_from_diagnostics(self):
        """step counter is removed from diagnostics."""
        r = _make_result()
        norm = normalize_result_for_comparison(r)
        diag = norm["decision"]["diagnostics"]
        assert "step" not in diag

    def test_preserves_decision_relevant_fields(self):
        """Intents, fills, cash, positions, gate data are preserved."""
        r = _make_result_with_intent("open", "long")
        norm = normalize_result_for_comparison(r)
        dec = norm["decision"]

        # Intents preserved (minus intent_id)
        assert len(dec["intents"]) == 1
        assert dec["intents"][0]["kind"] == "open"
        assert dec["intents"][0]["side"] == "long"
        assert "intent_id" not in dec["intents"][0]

        # State cash preserved
        assert dec["state"]["cash_usd"] == 10000.0

        # Diagnostics fields preserved
        assert "gate_blocked" in dec["diagnostics"]
        assert "errors" in dec["diagnostics"]

    def test_strips_intent_id(self):
        """intent_id is stripped from intents and fills."""
        r = _make_result_with_close_fill("long")
        norm = normalize_result_for_comparison(r)
        for fill in norm["decision"]["fills"]:
            assert "intent_id" not in fill

    def test_does_not_mutate_original(self):
        """Normalization returns a deep copy; original is untouched."""
        r = _make_result()
        data_before = json.loads(r)
        _ = normalize_result_for_comparison(r)
        data_after = json.loads(r)
        assert data_before == data_after


# ===========================================================================
# TestKernelIntegration (conditional on bt_runtime)
# ===========================================================================


@pytest.mark.skipif(not _HAS_BT_RUNTIME, reason="bt_runtime not available")
class TestKernelIntegration:
    """Integration tests using the real Rust kernel via bt_runtime."""

    def test_real_kernel_deterministic(self):
        """Real kernel produces identical results across 10 iterations."""
        state = bt_runtime.default_kernel_state_json(10000.0, _BASE_TS)
        params = bt_runtime.default_kernel_params_json()
        event_json = _make_event("buy", 2000.0)

        harness = DecisionParityHarness()
        dr = harness.verify_determinism(
            state, event_json, params, iterations=10,
        )
        assert dr.is_deterministic is True
        assert dr.variations == []

    def test_real_kernel_record_replay(self):
        """Record a real kernel decision then replay -> parity."""
        state = bt_runtime.default_kernel_state_json(10000.0, _BASE_TS)
        params = bt_runtime.default_kernel_params_json()
        event_json = _make_event("buy", 2000.0)

        result = bt_runtime.step_decision(state, event_json, params)

        harness = DecisionParityHarness()
        rid = harness.record_decision(state, event_json, params, result)
        pr = harness.replay_decision(rid)

        assert pr.is_match is True
        assert pr.diffs == []

    def test_real_kernel_fixture_round_trip(self):
        """Record -> fixture -> load -> replay with real kernel."""
        state = bt_runtime.default_kernel_state_json(10000.0, _BASE_TS)
        params = bt_runtime.default_kernel_params_json()
        event_json = _make_event("buy", 2000.0)

        result = bt_runtime.step_decision(state, event_json, params)

        harness = DecisionParityHarness()
        harness.record_decision(state, event_json, params, result)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            path = fh.name

        try:
            harness.build_fixture(output_path=path)

            new_harness = DecisionParityHarness()
            new_harness.load_fixture(path)
            report = new_harness.replay_all()

            assert report.is_perfect_parity is True
            assert report.total_decisions == 1
        finally:
            os.unlink(path)
