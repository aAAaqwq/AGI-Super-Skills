from __future__ import annotations

import json

from tools import replay_equivalence


TRACE_LEFT = {
    "decision_diagnostics": [
        {
            "event_id": 1,
            "source": "fixture-open",
            "timestamp_ms": 1_700_000_000_000,
            "symbol": "BTC",
            "signal": "BUY",
            "requested_notional_usd": 1000.0,
            "requested_price": 100.0,
            "schema_version": 1,
            "step": 1,
            "state_step": 1,
            "state_cash_usd": 10000.0,
            "state_positions": 0,
            "warnings": [],
            "errors": [],
            "intents": [
                {
                    "kind": "open",
                    "side": "long",
                    "symbol": "BTC",
                    "quantity": 0.1,
                    "price": 100.0,
                    "notional_usd": 10.0,
                    "fee_rate": 0.0,
                }
            ],
            "fills": [],
            "applied_to_kernel_state": True,
        }
    ]
}


def test_replay_equivalence_matches_identical_payloads() -> None:
    left = replay_equivalence.extract_decision_trace(TRACE_LEFT)
    right = replay_equivalence.extract_decision_trace(TRACE_LEFT)
    ok, diffs, summary = replay_equivalence.compare_traces(left, right, tolerance=1e-12)
    assert ok
    assert diffs == []
    assert summary["status"] == "match"


def test_replay_equivalence_detects_differences() -> None:
    changed = json.loads(json.dumps(TRACE_LEFT))
    changed["decision_diagnostics"][0]["event_id"] = 2
    left = replay_equivalence.extract_decision_trace(TRACE_LEFT)
    right = replay_equivalence.extract_decision_trace(changed)
    ok, diffs, summary = replay_equivalence.compare_traces(left, right, tolerance=1e-12, max_diffs=5)
    assert not ok
    assert summary["status"] == "mismatch"
    assert diffs
    assert any(item["path"].endswith("event_id") for item in diffs)


def test_replay_equivalence_ignores_float_noise_with_tolerance() -> None:
    changed = json.loads(json.dumps(TRACE_LEFT))
    changed["decision_diagnostics"][0]["state_cash_usd"] = 10000.0 + 1e-11
    left = replay_equivalence.extract_decision_trace(TRACE_LEFT)
    right = replay_equivalence.extract_decision_trace(changed)
    ok, diffs, summary = replay_equivalence.compare_traces(left, right, tolerance=1e-9)
    assert ok
    assert not diffs
    assert summary["left_len"] == summary["right_len"] == 1
