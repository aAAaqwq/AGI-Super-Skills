from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest

from scanner.pipeline import MIGRATIONS, PipelineConfig, run_shadow_radar
from scanner.contracts import ContractViolation
from scanner.smart_money import collect_smart_money
from scanner.storage import ProfileFetchOutcomeInput, SQLiteRunLedger
from tests.test_smart_money import FakeSmartMoneyApi


PROJECT = Path(__file__).parents[1]
FIXTURE = PROJECT / "tests" / "fixtures" / "m1b"
SEED_EVIDENCE = (
    PROJECT
    / "tests"
    / "fixtures"
    / "discovery"
    / "leaderboard_seed_profiles.json"
)
TERMINAL_FETCH_STATUSES = {
    "COMPLETE",
    "EMPTY",
    "PARTIAL",
    "FAILED",
    "NOT_ATTEMPTED",
}


class ProfileCoveragePersistenceContractTests(unittest.TestCase):
    def _smart_money_evidence(self) -> dict[str, object]:
        api = FakeSmartMoneyApi()
        api.test_case = self
        base = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
        ticks = 0

        def clock() -> datetime:
            nonlocal ticks
            ticks += 1
            return base + timedelta(milliseconds=ticks * 100)

        return collect_smart_money(
            get_json=api,
            captured_at="2026-08-01T12:05:00Z",
            clock=clock,
        )

    @staticmethod
    def _write_feed_snapshot(path: Path) -> None:
        payload = {
            "status": "ok",
            "scanned_at": "2026-08-01T12:06:08Z",
            "snapshot_file": str(path),
            "count": 0,
            "posts": [],
            "coverage_contract_version": "square-feed-coverage/v1",
            "discovery_result": {
                "coverage_status": "PARTIAL",
                "termination_reason": "STAGNANT",
                "started_from_top": True,
                "reached_bottom": True,
                "bottom_geometry_stable": True,
                "source_observation_count": 0,
                "valid_url_observation_count": 0,
                "invalid_url_observation_count": 0,
                "unique_candidate_post_count": 0,
                "same_run_duplicate_observation_count": 0,
                "preferred_minimum": 100,
                "hard_limit": 200,
                "minimum_target_met": False,
                "truncated": False,
                "scroll_rounds": 10,
                "consecutive_no_new": 10,
                "required_consecutive_no_new": 10,
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_schema_supports_one_terminal_outcome_per_planned_profile_author(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteRunLedger(Path(directory) / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            columns = {
                row[1]
                for row in ledger._connection.execute(  # noqa: SLF001 - schema audit
                    "PRAGMA table_info(profile_fetch_outcome)"
                )
            }
            ddl = ledger._connection.execute(  # noqa: SLF001 - schema audit
                "SELECT sql FROM sqlite_master WHERE name = 'profile_fetch_outcome'"
            ).fetchone()[0]
            run = ledger.create_or_open_replay_run(
                replay_namespace="profile-fetch-schema-test",
                source_logical_run_id="fixture:profile-fetch-schema",
                pipeline_version="4.1.0",
                now="2026-08-01T12:00:00Z",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id,
                started_at="2026-08-01T12:00:01Z",
            )

            def insert_outcome(
                row_id: str,
                planned_author_id: str,
                status: str,
                post_count: int,
                pages_fetched: int,
                *,
                logical_run_id: str = run.logical_run_id,
                attempt_id: str = attempt.attempt_id,
            ) -> None:
                ledger._connection.execute(  # noqa: SLF001 - constraint audit
                    """
                    INSERT INTO profile_fetch_outcome (
                        profile_fetch_outcome_id, logical_run_id, attempt_id,
                        profile_cohort, planned_author_id, planned_id_type,
                        resolved_author_id, fetch_status, post_count,
                        pages_fetched, termination_reason, error_detail,
                        observed_at_utc, schema_version, source_system,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, 'SEED_PROFILE', ?, 'SQUARE_UID', ?, ?, ?, ?,
                              'FIXTURE_TERMINATION', NULL, ?, '4.1.0',
                              'profile_fetch_schema_test', ?, ?)
                    """,
                    (
                        row_id,
                        logical_run_id,
                        attempt_id,
                        planned_author_id,
                        planned_author_id,
                        status,
                        post_count,
                        pages_fetched,
                        "2026-08-01T12:00:02Z",
                        "2026-08-01T12:00:02Z",
                        "2026-08-01T12:00:02Z",
                    ),
                )

            valid_counts = {
                "COMPLETE": (1, 1),
                "EMPTY": (0, 1),
                "PARTIAL": (0, 1),
                "FAILED": (0, 0),
                "NOT_ATTEMPTED": (0, 0),
            }
            for index, (status, counts) in enumerate(valid_counts.items()):
                insert_outcome(
                    f"outcome-{index}",
                    f"fixture-square-{index}",
                    status,
                    *counts,
                )
            ledger._connection.commit()  # noqa: SLF001 - constraint audit

            with self.assertRaises(sqlite3.IntegrityError):
                insert_outcome(
                    "duplicate-outcome",
                    "fixture-square-0",
                    "COMPLETE",
                    1,
                    1,
                )
            with self.assertRaises(sqlite3.IntegrityError):
                insert_outcome(
                    "invalid-status",
                    "fixture-square-invalid-status",
                    "BLOCKED",
                    0,
                    0,
                )
            with self.assertRaises(sqlite3.IntegrityError):
                insert_outcome(
                    "invalid-count",
                    "fixture-square-invalid-count",
                    "COMPLETE",
                    0,
                    1,
                )
            with self.assertRaises(sqlite3.IntegrityError):
                insert_outcome(
                    "invalid-foreign-key",
                    "fixture-square-invalid-fk",
                    "EMPTY",
                    0,
                    1,
                    logical_run_id="missing-run",
                    attempt_id="missing-attempt",
                )

        self.assertTrue(
            {
                "profile_cohort",
                "planned_author_id",
                "planned_id_type",
                "resolved_author_id",
                "fetch_status",
                "post_count",
                "pages_fetched",
                "termination_reason",
                "error_detail",
            }.issubset(columns)
        )
        for status in TERMINAL_FETCH_STATUSES:
            with self.subTest(status=status):
                self.assertIn(f"'{status}'", ddl)

    def test_ledger_records_and_exactly_replays_profile_fetch_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteRunLedger(Path(directory) / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_replay_run(
                replay_namespace="profile-fetch-ledger-test",
                source_logical_run_id="fixture:profile-fetch-ledger",
                pipeline_version="4.1.0",
                now="2026-08-01T12:00:00Z",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id,
                started_at="2026-08-01T12:00:01Z",
            )
            outcomes = (
                ProfileFetchOutcomeInput(
                    profile_cohort="SEED_PROFILE",
                    planned_author_id="seed-square-1",
                    planned_id_type="SQUARE_UID",
                    resolved_author_id="seed-square-1",
                    fetch_status="EMPTY",
                    post_count=0,
                    pages_fetched=1,
                    termination_reason="NO_NEXT_CURSOR",
                ),
                ProfileFetchOutcomeInput(
                    profile_cohort="SMART_MONEY_PROFILE",
                    planned_author_id="top-trader-1",
                    planned_id_type="TOP_TRADER_ID",
                    resolved_author_id=None,
                    fetch_status="NOT_ATTEMPTED",
                    post_count=0,
                    pages_fetched=0,
                    error_detail="MAPPING_NOT_FOUND",
                ),
            )

            recorded = ledger.record_profile_fetch_outcomes(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                outcomes=outcomes,
                observed_at="2026-08-01T12:00:02Z",
            )
            replayed = ledger.record_profile_fetch_outcomes(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                outcomes=outcomes,
                observed_at="2026-08-01T12:00:02Z",
            )

            self.assertEqual(recorded, replayed)
            self.assertEqual(
                recorded,
                ledger.list_profile_fetch_outcomes(attempt_id=attempt.attempt_id),
            )

    def test_ledger_rolls_back_whole_batch_when_idempotent_evidence_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteRunLedger(Path(directory) / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_replay_run(
                replay_namespace="profile-fetch-conflict-test",
                source_logical_run_id="fixture:profile-fetch-conflict",
                pipeline_version="4.1.0",
                now="2026-08-01T12:00:00Z",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id,
                started_at="2026-08-01T12:00:01Z",
            )
            original = ProfileFetchOutcomeInput(
                profile_cohort="SEED_PROFILE",
                planned_author_id="seed-square-1",
                planned_id_type="SQUARE_UID",
                resolved_author_id="seed-square-1",
                fetch_status="EMPTY",
                post_count=0,
                pages_fetched=1,
            )
            ledger.record_profile_fetch_outcomes(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                outcomes=(original,),
                observed_at="2026-08-01T12:00:02Z",
            )

            with self.assertRaises(ContractViolation):
                ledger.record_profile_fetch_outcomes(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    outcomes=(
                        ProfileFetchOutcomeInput(
                            profile_cohort="SEED_PROFILE",
                            planned_author_id="seed-square-0",
                            planned_id_type="SQUARE_UID",
                            resolved_author_id="seed-square-0",
                            fetch_status="EMPTY",
                            post_count=0,
                            pages_fetched=1,
                        ),
                        ProfileFetchOutcomeInput(
                            profile_cohort="SEED_PROFILE",
                            planned_author_id="seed-square-1",
                            planned_id_type="SQUARE_UID",
                            resolved_author_id="seed-square-1",
                            fetch_status="FAILED",
                            post_count=0,
                            pages_fetched=0,
                        ),
                    ),
                    observed_at="2026-08-01T12:00:02Z",
                )

            self.assertEqual(
                ["seed-square-1"],
                [
                    row.planned_author_id
                    for row in ledger.list_profile_fetch_outcomes(
                        attempt_id=attempt.attempt_id
                    )
                ],
            )

    def test_ledger_rejects_invalid_identity_types_and_terminal_attempt_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteRunLedger(Path(directory) / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_replay_run(
                replay_namespace="profile-fetch-validation-test",
                source_logical_run_id="fixture:profile-fetch-validation",
                pipeline_version="4.1.0",
                now="2026-08-01T12:00:00Z",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id,
                started_at="2026-08-01T12:00:01Z",
            )
            with self.assertRaises(ContractViolation):
                ledger.record_profile_fetch_outcomes(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    outcomes=(
                        ProfileFetchOutcomeInput(
                            profile_cohort="SMART_MONEY_PROFILE",
                            planned_author_id="top-trader-invalid",
                            planned_id_type="SQUARE_UID",
                            resolved_author_id=None,
                            fetch_status="NOT_ATTEMPTED",
                            post_count=0,
                            pages_fetched=0,
                        ),
                    ),
                    observed_at="2026-08-01T12:00:02Z",
                )
            self.assertEqual([], ledger.list_profile_fetch_outcomes())

            ledger.finish_attempt(
                attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T12:00:03Z",
            )
            with self.assertRaises(ContractViolation):
                ledger.record_profile_fetch_outcomes(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    outcomes=(
                        ProfileFetchOutcomeInput(
                            profile_cohort="SEED_PROFILE",
                            planned_author_id="seed-square-late",
                            planned_id_type="SQUARE_UID",
                            resolved_author_id="seed-square-late",
                            fetch_status="EMPTY",
                            post_count=0,
                            pages_fetched=1,
                        ),
                    ),
                    observed_at="2026-08-01T12:00:04Z",
                )
            self.assertEqual([], ledger.list_profile_fetch_outcomes())

    def test_production_persists_smart_money_and_seed_outcome_for_every_planned_author(self) -> None:
        now = datetime(2026, 8, 1, 12, 6, 10, tzinfo=timezone.utc)
        smart_money = self._smart_money_evidence()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "feed-snapshot.json"
            database = root / "radar.sqlite"
            self._write_feed_snapshot(snapshot)
            market_client = SimpleNamespace(
                fetch_futures_catalog=lambda: SimpleNamespace(
                    server_time_ms=int(now.timestamp() * 1000),
                    captured_at=now,
                    contracts={},
                )
            )

            result = run_shadow_radar(
                PipelineConfig(
                    mode="real",
                    output_dir=root / "runs",
                    database=database,
                    decision_at=now,
                    input_snapshot=snapshot,
                    leaderboard_seed_evidence=SEED_EVIDENCE,
                    smart_money_enabled=True,
                ),
                clock=lambda: now,
                market_client=market_client,
                smart_money_collector=lambda: smart_money,
                profile_content_fetcher=lambda _uid, _offset: {
                    "success": True,
                    "data": {"contents": [], "nextTimeOffset": None},
                },
                profile_capture_time="2026-08-01T12:06:09Z",
            )

            with closing(sqlite3.connect(database)) as connection:
                persisted_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM profile_fetch_outcome
                    WHERE attempt_id = ?
                    """,
                    (result.attempt_id,),
                ).fetchone()[0]
                self.assertEqual(69, persisted_count)
                grouped = connection.execute(
                    """
                    SELECT profile_cohort, fetch_status, COUNT(*), SUM(post_count)
                    FROM profile_fetch_outcome
                    WHERE attempt_id = ?
                    GROUP BY profile_cohort, fetch_status
                    """,
                    (result.attempt_id,),
                ).fetchall()

        self.assertEqual(
            {
                ("SEED_PROFILE", "EMPTY", 9, 0),
                ("SMART_MONEY_PROFILE", "NOT_ATTEMPTED", 60, 0),
            },
            set(grouped),
        )

    def test_fixture_without_profile_fetcher_handles_empty_and_seed_plans(self) -> None:
        now = datetime(2026, 8, 1, 12, 6, 10, tzinfo=timezone.utc)
        cases = (
            ("empty-plan", None, []),
            ("seed-plan", SEED_EVIDENCE, [("SEED_PROFILE", "NOT_ATTEMPTED", 9)]),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for label, seed_evidence, expected in cases:
                with self.subTest(label=label):
                    database = root / f"{label}.sqlite"
                    result = run_shadow_radar(
                        PipelineConfig(
                            mode="fixture",
                            fixture_dir=FIXTURE,
                            output_dir=root / label,
                            database=database,
                            decision_at=now,
                            leaderboard_seed_evidence=seed_evidence,
                        ),
                        clock=lambda: now,
                    )
                    with closing(sqlite3.connect(database)) as connection:
                        grouped = connection.execute(
                            """
                            SELECT profile_cohort, fetch_status, COUNT(*)
                            FROM profile_fetch_outcome
                            WHERE attempt_id = ?
                            GROUP BY profile_cohort, fetch_status
                            """,
                            (result.attempt_id,),
                        ).fetchall()
                    self.assertEqual(expected, grouped)


if __name__ == "__main__":
    unittest.main()
