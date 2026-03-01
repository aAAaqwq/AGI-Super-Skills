from __future__ import annotations

import factory_run


def test_slippage_reject_reason_prefers_degraded_context() -> None:
    msg = factory_run._slippage_reject_reason(
        agg={"degraded": True, "degraded_reasons": ["replay_failure", "missing_baseline_level"]},
        reject_bps=20.0,
        flip_sign=False,
    )
    assert msg == "slippage degraded: replay_failure, missing_baseline_level"


def test_slippage_reject_reason_reports_flip_when_not_degraded() -> None:
    msg = factory_run._slippage_reject_reason(
        agg={"degraded": False},
        reject_bps=20.0,
        flip_sign=True,
    )
    assert msg == "slippage flip at 20 bps"


def test_slippage_reject_reason_falls_back_to_aggregate_reason() -> None:
    msg = factory_run._slippage_reject_reason(
        agg={"degraded": False, "reject_reason": "degraded_run"},
        reject_bps=20.0,
        flip_sign=False,
    )
    assert msg == "slippage reject: degraded_run"
