#!/usr/bin/env python3
"""Run one offline fixture attempt under the shadow cycle contract.

This command neither installs a schedule nor sleeps for retries.  A failed
first attempt prints a serializable +10 minute retry plan.  Pass that JSON
back with ``--retry-state`` when an external scheduler reaches the due time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.contracts import format_utc, parse_utc
from scanner.pipeline import PipelineConfig, PipelineResult, run_shadow_radar
from scanner.runner import (
    CycleMode,
    CycleStatus,
    AttemptContext,
    cycle_result_to_dict,
    retry_cycle_from_dict,
    run_scheduled_retry,
    run_shadow_cycle,
    slot_at_or_before,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        required=True,
        help="offline Square fixture directory; live mode is intentionally absent",
    )
    parser.add_argument(
        "--clock",
        required=True,
        help="aware timestamp injected as the attempt observation time",
    )
    parser.add_argument(
        "--slot",
        help="fixed UTC slot; defaults to the 4-hour slot at or before --clock",
    )
    parser.add_argument(
        "--retry-state",
        type=Path,
        help="JSON receipt from a prior RETRY_SCHEDULED invocation",
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "data" / "v4" / "shadow-cycle-runs",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_DIR / "data" / "v4" / "shadow-cycle.sqlite",
    )
    return parser.parse_args(argv)


def _pipeline_receipt(result: PipelineResult | None) -> dict[str, str] | None:
    if result is None:
        return None
    return {
        "logical_run_id": result.logical_run_id,
        "attempt_id": result.attempt_id,
        "raw_json": str(result.raw_json),
        "market_json": str(result.market_json),
        "report_json": str(result.report_json),
        "report_markdown": str(result.report_markdown),
        "latest_pointer": str(result.latest_pointer),
    }


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    observed = parse_utc(args.clock)
    pipeline_result: PipelineResult | None = None

    if args.retry_state is not None:
        prior_payload: Any = json.loads(
            args.retry_state.read_text(encoding="utf-8")
        )
        if isinstance(prior_payload, dict) and "cycle" in prior_payload:
            prior_payload = prior_payload["cycle"]
        prior = retry_cycle_from_dict(prior_payload)
        slot = parse_utc(prior.slot_utc)
    else:
        slot = parse_utc(args.slot) if args.slot else slot_at_or_before(observed)

    def execute(context: AttemptContext) -> PipelineResult:
        nonlocal pipeline_result
        pipeline_result = run_shadow_radar(
            PipelineConfig(
                mode="fixture",
                output_dir=args.output_dir,
                database=args.database,
                decision_at=format_utc(slot),
                fixture_dir=args.fixture,
                limit=args.limit,
                no_send=True,
                scheduled_retry=context.attempt_no == 2,
            ),
            clock=lambda: observed,
        )
        return pipeline_result

    if args.retry_state is None:
        cycle = run_shadow_cycle(
            mode=CycleMode.REPLAY,
            scheduled_for_utc=slot,
            execute_attempt=execute,
            clock=lambda: observed,
        )
    else:
        cycle = run_scheduled_retry(
            prior,
            execute_attempt=execute,
            clock=lambda: observed,
        )

    print(
        json.dumps(
            {
                "cycle": cycle_result_to_dict(cycle),
                "pipeline": _pipeline_receipt(pipeline_result),
                "shadow_only": True,
                "no_send": True,
                "scheduler_installed": False,
                "external_write_enabled": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if cycle.status is CycleStatus.SUCCEEDED:
        return 0
    if cycle.status is CycleStatus.RETRY_SCHEDULED:
        return 75
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
