from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scanner.contracts import ContractViolation
from scanner.pipeline import PipelineConfig, run_shadow_radar
from scanner.runner import (
    AttemptContext,
    AttemptStatus,
    CycleMode,
    CycleStatus,
    DeliveryDraft,
    FailureStage,
    IntentStatus,
    SendPolicy,
    StageFailure,
    build_held_delivery_intent,
    cycle_result_to_dict,
    next_utc_slot,
    retry_cycle_from_dict,
    run_scheduled_retry,
    run_shadow_cycle,
    slot_at_or_before,
    utc_slots_for_day,
)
from scanner.storage import SQLiteRunLedger


UTC = timezone.utc
PROJECT = Path(__file__).parents[1]
FIXTURE = PROJECT / "tests" / "fixtures" / "m1b"
MIGRATION = PROJECT / "migrations"


class ShadowRunnerTests(unittest.TestCase):
    def test_daily_slots_are_the_six_fixed_utc_hours(self) -> None:
        slots = utc_slots_for_day(date(2026, 8, 1))

        self.assertEqual([0, 4, 8, 12, 16, 20], [item.hour for item in slots])
        self.assertTrue(all(item.tzinfo is UTC for item in slots))
        self.assertEqual(
            slots,
            utc_slots_for_day("2026-08-01T12:00:00-07:00"),
        )

    def test_slot_floor_and_next_slot_are_deterministic_across_midnight(self) -> None:
        self.assertEqual(
            datetime(2026, 8, 1, 20, tzinfo=UTC),
            slot_at_or_before("2026-08-01T23:59:59Z"),
        )
        self.assertEqual(
            datetime(2026, 8, 2, 0, tzinfo=UTC),
            next_utc_slot("2026-08-01T23:59:59Z"),
        )
        self.assertEqual(
            datetime(2026, 8, 1, 8, tzinfo=UTC),
            slot_at_or_before("2026-08-01T01:30:00-07:00"),
        )

    def test_each_fixed_slot_passes_the_injected_clock_and_no_send_context(self) -> None:
        contexts = []
        for slot in utc_slots_for_day("2026-08-01"):
            result = run_shadow_cycle(
                mode=CycleMode.PRODUCTION_SHADOW,
                scheduled_for_utc=slot,
                execute_attempt=lambda context: contexts.append(context),
                clock=lambda slot=slot: slot,
            )
            self.assertEqual(CycleStatus.SUCCEEDED, result.status)

        self.assertEqual([1] * 6, [item.attempt_no for item in contexts])
        self.assertEqual(
            [f"2026-08-01T{hour:02d}:00:00Z" for hour in (0, 4, 8, 12, 16, 20)],
            [item.slot_utc for item in contexts],
        )
        self.assertTrue(all(item.no_send for item in contexts))

    def test_first_failure_only_plans_one_retry_at_plus_ten_minutes(self) -> None:
        calls = []

        def fail(context: object) -> None:
            calls.append(context)
            raise StageFailure(FailureStage.CHROME, "CDP endpoint unavailable")

        result = run_shadow_cycle(
            mode=CycleMode.PRODUCTION_SHADOW,
            scheduled_for_utc="2026-08-01T04:00:00Z",
            execute_attempt=fail,
            clock=lambda: datetime(2026, 8, 1, 4, 0, 7, tzinfo=UTC),
        )

        self.assertEqual(1, len(calls))
        self.assertEqual("2026-08-01T04:00:07Z", calls[0].decision_at_utc)
        self.assertEqual(CycleStatus.RETRY_SCHEDULED, result.status)
        self.assertEqual("2026-08-01T04:10:07Z", result.retry_plan.scheduled_for_utc)
        self.assertEqual(600, result.retry_plan.delay_seconds)
        self.assertFalse(result.retry_plan.scheduler_write_enabled)
        self.assertIsNone(result.alert_intent)
        self.assertIsNone(result.delivery_intent)
        self.assertEqual(FailureStage.CHROME, result.attempts[0].failure.stage)

    def test_retry_is_not_executed_early_and_runner_never_sleeps(self) -> None:
        prior = self._failed_first_attempt()
        calls = []

        with self.assertRaisesRegex(ContractViolation, "never sleeps"):
            run_scheduled_retry(
                prior,
                execute_attempt=lambda context: calls.append(context),
                clock=lambda: datetime(2026, 8, 1, 4, 9, 59, tzinfo=UTC),
            )

        self.assertEqual([], calls)

    def test_retry_success_is_recovered_silently_with_no_intents(self) -> None:
        prior = self._failed_first_attempt()
        contexts = []

        recovered = run_scheduled_retry(
            prior,
            execute_attempt=lambda context: contexts.append(context),
            clock=lambda: datetime(2026, 8, 1, 4, 10, tzinfo=UTC),
        )

        self.assertEqual(CycleStatus.SUCCEEDED, recovered.status)
        self.assertTrue(recovered.recovered_silently)
        self.assertEqual([1, 2], [item.attempt_no for item in recovered.attempts])
        self.assertEqual(AttemptStatus.SUCCEEDED, recovered.attempts[1].status)
        self.assertIsNone(recovered.alert_intent)
        self.assertIsNone(recovered.delivery_intent)
        self.assertEqual(1, len(contexts))
        self.assertEqual(prior.decision_at_utc, contexts[0].decision_at_utc)

    def test_retry_success_keeps_normal_held_report_delivery_intent(self) -> None:
        prior = self._failed_first_attempt()
        draft = DeliveryDraft(
            logical_run_id="prod-slot-0400",
            report_sha256="c" * 64,
            payload_path="runs/prod-slot-0400/report.json",
            payload={"text": "recovered local shadow report"},
        )

        recovered = run_scheduled_retry(
            prior,
            execute_attempt=lambda _: "local-result",
            delivery_factory=lambda value: draft,
            clock=lambda: datetime(2026, 8, 1, 4, 10, tzinfo=UTC),
        )

        self.assertEqual(CycleStatus.SUCCEEDED, recovered.status)
        self.assertTrue(recovered.recovered_silently)
        self.assertIsNone(recovered.alert_intent)
        self.assertIsNotNone(recovered.delivery_intent)
        self.assertEqual(IntentStatus.HELD, recovered.delivery_intent.status)
        self.assertEqual(SendPolicy.NO_SEND, recovered.delivery_intent.send_policy)
        self.assertFalse(recovered.delivery_intent.external_write_enabled)

    def test_runner_retry_integrates_with_real_pipeline_frozen_decision(self) -> None:
        empty_raw = {
            "schema_version": "4.1.0",
            "source_system": "test",
            "source_mode": "test-empty",
            "decision_at_utc": "2026-08-01T08:00:07Z",
            "counts": {
                "discovered_source_records": 0,
                "deduplicated_post_candidates": 0,
                "duplicate_source_records": 0,
                "accepted_observations": 0,
                "quarantined_source_records": 0,
                "dq_quarantined_source_records": 0,
                "window_excluded_source_records": 0,
            },
            "accepted": [],
            "discovery_observations": [],
            "quarantine": [],
            "authors": [],
            "ranking_discovery_status": "BLOCKED",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"

            def pipeline_attempt(context: AttemptContext):
                observed_at = (
                    context.decision_at_utc
                    if context.attempt_no == 1
                    else context.planned_for_utc
                )
                return run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=database,
                        decision_at=context.decision_at_utc,
                        input_snapshot=None,
                        signals_json=None,
                        scheduled_retry=context.attempt_no == 2,
                    ),
                    market_client=SimpleNamespace(
                        fetch_futures_catalog=lambda: SimpleNamespace(
                            server_time_ms=int(
                                datetime.fromisoformat(
                                    observed_at.replace("Z", "+00:00")
                                ).timestamp()
                                * 1000
                            )
                        )
                    ),  # type: ignore[arg-type]
                    clock=lambda: datetime.fromisoformat(
                        observed_at.replace("Z", "+00:00")
                    ),
                )

            with patch(
                "scanner.pipeline._collect_live_urls",
                side_effect=RuntimeError("injected fetch failure"),
            ):
                prior = run_shadow_cycle(
                    mode=CycleMode.PRODUCTION_SHADOW,
                    scheduled_for_utc="2026-08-01T08:00:00Z",
                    execute_attempt=pipeline_attempt,
                    clock=lambda: datetime(2026, 8, 1, 8, 0, 7, tzinfo=UTC),
                )

            self.assertEqual(CycleStatus.RETRY_SCHEDULED, prior.status)
            self.assertEqual("2026-08-01T08:00:07Z", prior.decision_at_utc)
            with patch("scanner.pipeline._collect_live_urls", return_value=empty_raw):
                recovered = run_scheduled_retry(
                    prior,
                    execute_attempt=pipeline_attempt,
                    clock=lambda: datetime(2026, 8, 1, 8, 10, 7, tzinfo=UTC),
                )

            self.assertEqual(CycleStatus.SUCCEEDED, recovered.status)
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            logical_run = ledger.list_logical_runs()[0]
            self.assertEqual(
                ["FAILED", "SUCCEEDED"],
                [
                    item.status
                    for item in ledger.list_attempts(logical_run.logical_run_id)
                ],
            )

    def test_second_failure_terminates_with_structured_held_alert(self) -> None:
        prior = self._failed_first_attempt()

        def fail_market(_: object) -> None:
            raise StageFailure(FailureStage.MARKET_API, "Futures timeout")

        failed = run_scheduled_retry(
            prior,
            execute_attempt=fail_market,
            clock=lambda: datetime(2026, 8, 1, 4, 10, tzinfo=UTC),
        )

        self.assertEqual(CycleStatus.FAILED_TERMINAL, failed.status)
        self.assertIsNone(failed.retry_plan)
        self.assertEqual(2, len(failed.attempts))
        self.assertEqual(FailureStage.MARKET_API, failed.alert_intent.failure.stage)
        self.assertEqual(IntentStatus.HELD, failed.alert_intent.status)
        self.assertEqual(SendPolicy.NO_SEND, failed.alert_intent.send_policy)
        self.assertFalse(failed.alert_intent.external_write_enabled)
        with self.assertRaisesRegex(ContractViolation, "RETRY_SCHEDULED"):
            run_scheduled_retry(
                failed,
                execute_attempt=lambda _: None,
                clock=lambda: datetime(2026, 8, 1, 4, 20, tzinfo=UTC),
            )

    def test_initial_local_report_success_builds_only_a_held_delivery_dto(self) -> None:
        draft = DeliveryDraft(
            logical_run_id="prod-slot-0400",
            report_sha256="a" * 64,
            payload_path="runs/prod-slot-0400/report.json",
            payload={"text": "local shadow report"},
        )
        result = run_shadow_cycle(
            mode=CycleMode.PRODUCTION_SHADOW,
            scheduled_for_utc="2026-08-01T04:00:00Z",
            execute_attempt=lambda _: "local-result",
            delivery_factory=lambda value: draft,
            clock=lambda: datetime(2026, 8, 1, 4, tzinfo=UTC),
        )

        intent = result.delivery_intent
        self.assertIsNotNone(intent)
        self.assertEqual(IntentStatus.HELD, intent.status)
        self.assertEqual(SendPolicy.NO_SEND, intent.send_policy)
        self.assertFalse(intent.external_write_enabled)
        self.assertEqual("HELD", intent.outbox_payload["status"])
        self.assertIn("schema has no HELD", intent.hold_reason)
        self.assertFalse(result.persistence_writes_enabled)
        self.assertFalse(result.external_actions_enabled)

    def test_replay_never_builds_a_production_delivery_intent(self) -> None:
        factory_calls = []

        def forbidden_factory(_: object) -> DeliveryDraft:
            factory_calls.append(True)
            raise AssertionError("delivery factory must not run for replay")

        result = run_shadow_cycle(
            mode=CycleMode.REPLAY,
            scheduled_for_utc="2026-08-01T08:00:00Z",
            execute_attempt=lambda _: "fixture-result",
            delivery_factory=forbidden_factory,
            clock=lambda: datetime(2026, 8, 1, 8, tzinfo=UTC),
        )
        direct = build_held_delivery_intent(
            DeliveryDraft("replay", "b" * 64, "report.json", {}),
            mode=CycleMode.REPLAY,
        )

        self.assertEqual([], factory_calls)
        self.assertIsNone(result.delivery_intent)
        self.assertIsNone(direct)

    def test_retry_state_round_trips_without_enabling_writes(self) -> None:
        original = self._failed_first_attempt()
        payload = cycle_result_to_dict(original)
        restored = retry_cycle_from_dict(json.loads(json.dumps(payload)))

        self.assertEqual(original, restored)
        self.assertFalse(restored.external_actions_enabled)
        self.assertFalse(restored.persistence_writes_enabled)

    def test_non_slot_schedule_is_rejected_before_attempt_execution(self) -> None:
        calls = []
        with self.assertRaisesRegex(ContractViolation, "00/04/08/12/16/20"):
            run_shadow_cycle(
                mode=CycleMode.PRODUCTION_SHADOW,
                scheduled_for_utc="2026-08-01T05:00:00Z",
                execute_attempt=lambda context: calls.append(context),
                clock=lambda: datetime(2026, 8, 1, 5, tzinfo=UTC),
            )
        self.assertEqual([], calls)

    def test_production_first_attempt_over_ten_minutes_late_is_rejected(self) -> None:
        calls = []
        with self.assertRaisesRegex(ContractViolation, r"within \+10 minutes"):
            run_shadow_cycle(
                mode=CycleMode.PRODUCTION_SHADOW,
                scheduled_for_utc="2026-08-01T08:00:00Z",
                execute_attempt=lambda context: calls.append(context),
                clock=lambda: datetime(2026, 8, 1, 8, 10, 1, tzinfo=UTC),
            )
        self.assertEqual([], calls)

    def test_cli_runs_offline_fixture_without_delivery_or_scheduler(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "scripts" / "run_shadow_cycle.py"),
                    "--fixture",
                    str(FIXTURE),
                    "--clock",
                    "2026-07-31T04:00:00Z",
                    "--limit",
                    "5",
                    "--output-dir",
                    str(root / "runs"),
                    "--database",
                    str(root / "radar.sqlite"),
                ],
                cwd=PROJECT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertEqual("REPLAY", receipt["cycle"]["mode"])
            self.assertEqual("SUCCEEDED", receipt["cycle"]["status"])
            self.assertIsNone(receipt["cycle"]["delivery_intent"])
            self.assertFalse(receipt["scheduler_installed"])
            self.assertFalse(receipt["external_write_enabled"])
            self.assertTrue(receipt["no_send"])

    @staticmethod
    def _failed_first_attempt():
        return run_shadow_cycle(
            mode=CycleMode.PRODUCTION_SHADOW,
            scheduled_for_utc="2026-08-01T04:00:00Z",
            execute_attempt=lambda _: (_ for _ in ()).throw(
                StageFailure(FailureStage.FETCH, "detail fetch failed")
            ),
            clock=lambda: datetime(2026, 8, 1, 4, tzinfo=UTC),
        )


if __name__ == "__main__":
    unittest.main()
