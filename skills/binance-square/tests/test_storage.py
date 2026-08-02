from pathlib import Path
from hashlib import sha256
import json
import sqlite3
import tempfile
import unittest

from datetime import datetime, timezone
from decimal import Decimal

from scanner.contracts import AcceptedPostObservation, ContractViolation, RunNamespace
from scanner.opportunities import Direction, ParameterSource
from scanner.storage import SQLiteRunLedger, SmartMoneyLeaderboardRowInput
from scanner.tracking import Outcome


MIGRATION = Path(__file__).parents[1] / "migrations"
SMART_MONEY_PAGE_FIXTURE = (
    Path(__file__).parent / "fixtures" / "smart_money" / "page_template.json"
)
SMART_MONEY_PROFILE_FIXTURE = (
    Path(__file__).parent / "fixtures" / "smart_money" / "profile_template.json"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def accepted(post_id: str, ordinal: int = 0) -> AcceptedPostObservation:
    return AcceptedPostObservation(
        post_id=post_id,
        canonical_post_url=f"https://www.binance.com/en/square/post/{post_id}",
        author_id="opaque-author-id",
        published_at=datetime(2026, 8, 1, 3, tzinfo=timezone.utc),
        observed_at=datetime(2026, 8, 1, 3, 1, tzinfo=timezone.utc),
        content_hash=(post_id[-1] if post_id[-1] in "abcdef" else "a") * 64,
        source_channel="PROFILE",
        source_record_ordinal=ordinal,
    )


def signal_revision(
    ledger: SQLiteRunLedger,
    logical_run_id: str,
    attempt_id: str,
    *,
    post_id: str = "9001",
    decision_at: str = "2026-08-01T00:00:00Z",
    now: str = "2026-08-01T00:00:01Z",
):
    return ledger.record_signal_revision(
        logical_run_id=logical_run_id,
        attempt_id=attempt_id,
        post_id=post_id,
        symbol="BTCUSDT",
        direction=Direction.LONG,
        decision_at=decision_at,
        parameter_source=ParameterSource.AUTHOR,
        entry_low=Decimal("62000.00"),
        entry_high=Decimal("62500.00"),
        stop_loss=Decimal("61000.00"),
        tp1=Decimal("65000.00"),
        tp2=Decimal("67000.00"),
        original_signal_status="VALID",
        dq_score=95,
        quality_flags=("DETAIL_BACKED", "POINT_IN_TIME"),
        now=now,
    )


def smart_money_rows() -> list[SmartMoneyLeaderboardRowInput]:
    return [
        SmartMoneyLeaderboardRowInput(
            rank_no=rank,
            top_trader_id=f"top-{rank:02d}",
            pnl=Decimal(f"{1000 - rank}.125"),
            roi=Decimal(f"{100 - rank}.50"),
            assets=["BTC", "ETH"] if rank == 1 else ["BTC"],
            subscribers=1000 - rank,
            position_status="OPEN" if rank % 2 else "CLOSED",
            signal_lead_on=rank % 2 == 1,
            raw={"rank": rank, "topTraderId": f"top-{rank:02d}"},
        )
        for rank in range(1, 31)
    ]


class RunLedgerTests(unittest.TestCase):
    def test_production_identity_is_scoped_by_explicit_job_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)

            production = ledger.create_or_open_production_run(
                job_namespace="production",
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.1.0",
            )
            canary = ledger.create_or_open_production_run(
                job_namespace="canary-a",
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.1.0",
            )
            production_attempt = ledger.start_next_attempt(
                production.logical_run_id,
                started_at="2026-08-01T04:00:01Z",
            )
            canary_attempt = ledger.start_next_attempt(
                canary.logical_run_id,
                started_at="2026-08-01T04:00:01Z",
            )

            self.assertNotEqual(production.logical_run_id, canary.logical_run_id)
            self.assertNotEqual(production_attempt.attempt_id, canary_attempt.attempt_id)
            self.assertEqual("production", production.job_namespace)
            self.assertEqual("canary-a", canary.job_namespace)

    def test_legacy_smart_money_schema_fails_closed_with_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "radar.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                """
                CREATE TABLE smart_money_leaderboard_capture (
                    smart_money_capture_id TEXT PRIMARY KEY,
                    evidence_path TEXT NOT NULL
                )
                """
            )
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(
                ContractViolation, "legacy Smart Money schema is incompatible"
            ):
                SQLiteRunLedger(database, MIGRATION)

    def test_production_slot_is_unique_across_pipeline_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)

            first = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
                now="2026-08-01T04:00:01Z",
            )
            after_upgrade = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00+00:00",
                pipeline_version="4.1.0",
                now="2026-08-01T04:10:01Z",
            )

            self.assertEqual(first.logical_run_id, after_upgrade.logical_run_id)
            self.assertEqual(RunNamespace.PRODUCTION, first.run_namespace)
            self.assertEqual("4.0.0", after_upgrade.pipeline_version)
            self.assertEqual(1, len(ledger.list_logical_runs()))

    def test_replay_identity_has_an_independent_versioned_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            production = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
            )

            replay_v4 = ledger.create_or_open_replay_run(
                replay_namespace="offline-contract-tests",
                source_logical_run_id=production.logical_run_id,
                pipeline_version="4.0.0",
            )
            same_replay = ledger.create_or_open_replay_run(
                replay_namespace="offline-contract-tests",
                source_logical_run_id=production.logical_run_id,
                pipeline_version="4.0.0",
            )
            replay_v41 = ledger.create_or_open_replay_run(
                replay_namespace="offline-contract-tests",
                source_logical_run_id=production.logical_run_id,
                pipeline_version="4.1.0",
            )

            self.assertEqual(RunNamespace.REPLAY, replay_v4.run_namespace)
            self.assertEqual(replay_v4.logical_run_id, same_replay.logical_run_id)
            self.assertNotEqual(production.logical_run_id, replay_v4.logical_run_id)
            self.assertNotEqual(replay_v4.logical_run_id, replay_v41.logical_run_id)
            self.assertEqual(3, len(ledger.list_logical_runs()))

    def test_logical_run_allows_only_attempts_one_and_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            logical_run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
            )

            first = ledger.record_attempt(
                logical_run.logical_run_id,
                attempt_no=1,
                started_at="2026-08-01T04:00:01Z",
            )
            same_first = ledger.record_attempt(
                logical_run.logical_run_id,
                attempt_no=1,
                started_at="2026-08-01T04:00:01Z",
            )
            second = ledger.record_attempt(
                logical_run.logical_run_id,
                attempt_no=2,
                started_at="2026-08-01T04:10:01Z",
            )

            self.assertEqual(first.attempt_id, same_first.attempt_id)
            self.assertEqual([1, 2], [first.attempt_no, second.attempt_no])
            self.assertEqual(2, len(ledger.list_attempts(logical_run.logical_run_id)))
            with self.assertRaises(ContractViolation):
                ledger.record_attempt(
                    logical_run.logical_run_id,
                    attempt_no=3,
                    started_at="2026-08-01T04:20:01Z",
                )

    def test_attempts_finish_once_with_terminal_audit_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            logical_run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
            )
            attempt = ledger.record_attempt(
                logical_run.logical_run_id,
                attempt_no=1,
                started_at="2026-08-01T04:00:01Z",
            )

            finished = ledger.finish_attempt(
                attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T04:00:03Z",
            )

            self.assertEqual("SUCCEEDED", finished.status)
            self.assertEqual("2026-08-01T04:00:03Z", finished.finished_at_utc)
            self.assertIsNone(finished.failed_stage)
            with self.assertRaises(ContractViolation):
                ledger.finish_attempt(
                    attempt.attempt_id,
                    status="FAILED",
                    finished_at="2026-08-01T04:00:04Z",
                    failed_stage="render",
                )

    def test_bronze_manifest_records_hash_source_schema_and_event_range(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            logical_run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
            )
            attempt = ledger.record_attempt(
                logical_run.logical_run_id,
                attempt_no=1,
                started_at="2026-08-01T04:00:01Z",
            )

            manifest = ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path="bronze/posts/date=2026-08-01/posts.json",
                sha256_hex="a" * 64,
                source_system="binance_square_v3",
                payload_schema_version="3.1-compat",
                event_start="2026-07-31T04:00:00Z",
                event_end="2026-08-01T03:59:59Z",
                record_count=199,
                now="2026-08-01T04:00:02Z",
            )

            self.assertEqual("a" * 64, manifest.sha256_hex)
            self.assertEqual("3.1-compat", manifest.payload_schema_version)
            self.assertEqual(199, manifest.record_count)
            self.assertEqual(
                [manifest], ledger.list_manifests(logical_run.logical_run_id)
            )

    def test_replay_runs_cannot_write_the_production_delivery_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            production = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
            )
            replay = ledger.create_or_open_replay_run(
                replay_namespace="offline-contract-tests",
                source_logical_run_id=production.logical_run_id,
                pipeline_version="4.0.0",
            )

            queued = ledger.enqueue_delivery(
                logical_run_id=production.logical_run_id,
                report_sha256="b" * 64,
                payload_path="reports/production.json",
                now="2026-08-01T04:01:00Z",
            )
            with self.assertRaises(ContractViolation):
                ledger.enqueue_delivery(
                    logical_run_id=replay.logical_run_id,
                    report_sha256="c" * 64,
                    payload_path="reports/replay.json",
                    now="2026-08-01T04:01:01Z",
                )

            self.assertEqual(
                [queued], ledger.list_delivery_outbox()
            )

    def test_sqlite_integrity_and_foreign_keys_are_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            logical_run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.0.0",
            )
            ledger.record_attempt(
                logical_run.logical_run_id,
                attempt_no=1,
                started_at="2026-08-01T04:00:01Z",
            )

            self.assertEqual("ok", ledger.integrity_check())
            self.assertEqual([], ledger.foreign_key_check())

    def test_additive_contract_freeze_creates_all_v41_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)

            tables = {
                row[0]
                for row in ledger._connection.execute(  # noqa: SLF001 - schema receipt
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

            self.assertTrue({
                "author_entity",
                "author_profile_observation",
                "leaderboard_capture",
                "leaderboard_row",
                "post_observation",
                "author_fetch_coverage",
                "signal_family",
                "signal_revision",
                "tracking_evaluation",
                "production_run_cutoff",
                "smart_money_trader_entity",
                "smart_money_leaderboard_capture",
                "smart_money_leaderboard_row",
                "smart_money_profile_observation",
                "smart_money_square_identity_mapping",
            }.issubset(tables))

    def test_smart_money_complete_capture_is_atomic_idempotent_and_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            arguments = dict(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                ranking_type="pnl",
                captured_at="2026-08-01T08:00:02Z",
                snapshot_semantics="OBSERVED_WINDOW",
                observed_start="2026-08-01T08:00:00Z",
                observed_end="2026-08-01T08:00:01Z",
                last_update_time_ms=1785571200000,
                capture_status="complete",
                evidence_path=str(SMART_MONEY_PAGE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PAGE_FIXTURE),
                payload_sha256="f" * 64,
                rows=smart_money_rows(),
                now="2026-08-01T08:00:03Z",
            )

            capture, rows = ledger.record_smart_money_leaderboard_capture(**arguments)
            same_capture, same_rows = ledger.record_smart_money_leaderboard_capture(
                **{**arguments, "now": "2026-08-01T08:00:04Z"}
            )

            self.assertEqual(capture, same_capture)
            self.assertEqual(rows, same_rows)
            self.assertEqual("PNL", capture.ranking_type)
            self.assertEqual("OBSERVED_WINDOW", capture.snapshot_semantics)
            self.assertEqual("2026-08-01T08:00:00Z", capture.observed_start_utc)
            self.assertEqual("2026-08-01T08:00:01Z", capture.observed_end_utc)
            self.assertEqual(
                file_sha256(SMART_MONEY_PAGE_FIXTURE),
                capture.evidence_file_sha256,
            )
            self.assertEqual("f" * 64, capture.payload_sha256)
            self.assertEqual(30, capture.rendered_rows)
            self.assertEqual(list(range(1, 31)), [row.rank_no for row in rows])
            self.assertEqual("top-01", rows[0].top_trader_id)
            self.assertEqual("999.125", rows[0].pnl_decimal)
            self.assertEqual(["BTC", "ETH"], rows[0].assets)
            self.assertTrue(rows[0].signal_lead_on)
            self.assertEqual(
                [capture],
                ledger.list_smart_money_leaderboard_captures(
                    logical_run_id=run.logical_run_id, ranking_type="PNL"
                ),
            )
            self.assertEqual(
                list(rows),
                ledger.list_smart_money_leaderboard_rows(
                    capture.smart_money_capture_id
                ),
            )
            self.assertEqual(
                30,
                ledger._connection.execute(  # noqa: SLF001 - storage receipt
                    "SELECT COUNT(*) FROM smart_money_trader_entity"
                ).fetchone()[0],
            )

    def test_smart_money_capture_rejects_invalid_sets_hash_and_failed_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            base = dict(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                ranking_type="PNL",
                captured_at="2026-08-01T08:00:02Z",
                snapshot_semantics="OBSERVED_WINDOW",
                observed_start="2026-08-01T08:00:00Z",
                observed_end="2026-08-01T08:00:01Z",
                last_update_time_ms=1785571200000,
                capture_status="COMPLETE",
                evidence_path=str(SMART_MONEY_PAGE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PAGE_FIXTURE),
                now="2026-08-01T08:00:03Z",
            )
            with self.assertRaisesRegex(ContractViolation, "last_update_time_ms"):
                ledger.record_smart_money_leaderboard_capture(
                    **{**base, "last_update_time_ms": None}, rows=smart_money_rows()
                )
            with self.assertRaisesRegex(ContractViolation, "requires 30"):
                ledger.record_smart_money_leaderboard_capture(
                    **base, rows=smart_money_rows()[:29]
                )
            duplicates = smart_money_rows()
            duplicates[-1] = SmartMoneyLeaderboardRowInput(
                rank_no=30,
                top_trader_id="top-01",
                pnl=Decimal("970.125"),
                roi=Decimal("70.50"),
                raw={"rank": 30, "topTraderId": "top-01"},
            )
            with self.assertRaisesRegex(ContractViolation, "duplicate topTraderId"):
                ledger.record_smart_money_leaderboard_capture(**base, rows=duplicates)
            duplicate_ranks = smart_money_rows()
            duplicate_ranks[-1] = SmartMoneyLeaderboardRowInput(
                rank_no=29,
                top_trader_id="top-30",
                pnl=Decimal("970.125"),
                roi=Decimal("70.50"),
                raw={"rank": 29, "topTraderId": "top-30"},
            )
            with self.assertRaisesRegex(ContractViolation, "duplicate rank"):
                ledger.record_smart_money_leaderboard_capture(
                    **base, rows=duplicate_ranks
                )
            mismatched_raw_id = smart_money_rows()
            mismatched_raw_id[0] = SmartMoneyLeaderboardRowInput(
                rank_no=1,
                top_trader_id="top-01",
                pnl=Decimal("999.125"),
                roi=Decimal("99.50"),
                raw={"rank": 1, "topTraderId": "top-other"},
            )
            with self.assertRaisesRegex(ContractViolation, "raw.topTraderId"):
                ledger.record_smart_money_leaderboard_capture(
                    **base, rows=mismatched_raw_id
                )
            with self.assertRaisesRegex(ContractViolation, "64 hexadecimal"):
                ledger.record_smart_money_leaderboard_capture(
                    **{**base, "evidence_file_sha256": "bad"},
                    rows=smart_money_rows(),
                )
            with self.assertRaisesRegex(ContractViolation, "does not match"):
                ledger.record_smart_money_leaderboard_capture(
                    **{**base, "evidence_file_sha256": "0" * 64},
                    rows=smart_money_rows(),
                )
            with self.assertRaisesRegex(ContractViolation, "payload_sha256"):
                ledger.record_smart_money_leaderboard_capture(
                    **{**base, "payload_sha256": "bad"},
                    rows=smart_money_rows(),
                )
            self.assertEqual([], ledger.list_smart_money_leaderboard_captures())
            self.assertEqual(
                0,
                ledger._connection.execute(  # noqa: SLF001 - atomicity receipt
                    "SELECT COUNT(*) FROM smart_money_trader_entity"
                ).fetchone()[0],
            )

            ledger.finish_attempt(
                attempt.attempt_id,
                status="FAILED",
                failed_stage="smart_money",
                finished_at="2026-08-01T08:00:04Z",
            )
            with self.assertRaisesRegex(ContractViolation, "FAILED"):
                ledger.record_smart_money_leaderboard_capture(
                    **{**base, "now": "2026-08-01T08:00:05Z"},
                    rows=smart_money_rows(),
                )

    def test_smart_money_capture_rejects_invalid_observed_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            base = dict(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                ranking_type="PNL",
                captured_at="2026-08-01T08:00:04Z",
                snapshot_semantics="OBSERVED_WINDOW",
                observed_start="2026-08-01T08:00:02Z",
                observed_end="2026-08-01T08:00:03Z",
                last_update_time_ms=1785571200000,
                capture_status="COMPLETE",
                evidence_path=str(SMART_MONEY_PAGE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PAGE_FIXTURE),
                rows=smart_money_rows(),
                now="2026-08-01T08:00:05Z",
            )

            invalid_cases = (
                ({"snapshot_semantics": "POINT_IN_TIME"}, "OBSERVED_WINDOW"),
                (
                    {
                        "observed_start": "2026-08-01T08:00:03Z",
                        "observed_end": "2026-08-01T08:00:02Z",
                    },
                    "observed_start <= observed_end <= captured_at",
                ),
                (
                    {"observed_end": "2026-08-01T08:00:05Z"},
                    "observed_start <= observed_end <= captured_at",
                ),
            )
            for overrides, message in invalid_cases:
                with self.subTest(overrides=overrides):
                    with self.assertRaisesRegex(ContractViolation, message):
                        ledger.record_smart_money_leaderboard_capture(
                            **{**base, **overrides}
                        )

            self.assertEqual([], ledger.list_smart_money_leaderboard_captures())

    def test_smart_money_pnl_capture_requires_pnl_for_every_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            rows = smart_money_rows()
            rows[0] = SmartMoneyLeaderboardRowInput(
                rank_no=1,
                top_trader_id="top-01",
                pnl=None,
                roi=Decimal("99.50"),
                raw={"rank": 1, "topTraderId": "top-01"},
            )

            with self.assertRaisesRegex(ContractViolation, "PNL rows require pnl"):
                ledger.record_smart_money_leaderboard_capture(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    ranking_type="PNL",
                    captured_at="2026-08-01T08:00:04Z",
                    snapshot_semantics="OBSERVED_WINDOW",
                    observed_start="2026-08-01T08:00:02Z",
                    observed_end="2026-08-01T08:00:03Z",
                    last_update_time_ms=1785571200000,
                    capture_status="COMPLETE",
                    evidence_path=str(SMART_MONEY_PAGE_FIXTURE),
                    evidence_file_sha256=file_sha256(SMART_MONEY_PAGE_FIXTURE),
                    rows=rows,
                    now="2026-08-01T08:00:05Z",
                )

    def test_smart_money_roi_capture_requires_roi_for_every_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            rows = smart_money_rows()
            rows[0] = SmartMoneyLeaderboardRowInput(
                rank_no=1,
                top_trader_id="top-01",
                pnl=Decimal("999.125"),
                roi=None,
                raw={"rank": 1, "topTraderId": "top-01"},
            )

            with self.assertRaisesRegex(ContractViolation, "ROI rows require roi"):
                ledger.record_smart_money_leaderboard_capture(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    ranking_type="ROI",
                    captured_at="2026-08-01T08:00:04Z",
                    snapshot_semantics="OBSERVED_WINDOW",
                    observed_start="2026-08-01T08:00:02Z",
                    observed_end="2026-08-01T08:00:03Z",
                    last_update_time_ms=1785571200000,
                    capture_status="COMPLETE",
                    evidence_path=str(SMART_MONEY_PAGE_FIXTURE),
                    evidence_file_sha256=file_sha256(SMART_MONEY_PAGE_FIXTURE),
                    rows=rows,
                    now="2026-08-01T08:00:05Z",
                )

    def test_smart_money_failed_capture_is_auditable_without_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            capture, rows = ledger.record_smart_money_leaderboard_capture(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                ranking_type="ROI",
                captured_at="2026-08-01T08:00:02Z",
                snapshot_semantics="OBSERVED_WINDOW",
                observed_start="2026-08-01T08:00:00Z",
                observed_end="2026-08-01T08:00:01Z",
                last_update_time_ms=None,
                capture_status="FAILED",
                evidence_path=str(SMART_MONEY_PAGE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PAGE_FIXTURE),
                rows=[],
                failure_reason="HTTP_429",
                now="2026-08-01T08:00:03Z",
            )
            self.assertEqual("FAILED", capture.capture_status)
            self.assertEqual("HTTP_429", capture.failure_reason)
            self.assertEqual(0, capture.rendered_rows)
            self.assertEqual((), rows)

    def test_smart_money_profiles_are_point_in_time_and_allow_audited_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            complete = ledger.record_smart_money_profile_observation(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                top_trader_id="top-01",
                observation_status="COMPLETE",
                captured_at="2026-08-01T08:00:02Z",
                days_active=513,
                mdd=Decimal("0.1250"),
                win_rate=Decimal("0.6789"),
                um_margin_balance=Decimal("12345.6700"),
                cm_margin_balance=Decimal("8.500"),
                net_transfer=Decimal("-250.25"),
                sharing_position={"BTCUSDT": "LONG"},
                sharing_history=[{"symbol": "ETHUSDT"}],
                latest_record={"symbol": "BTCUSDT"},
                is_ai=False,
                is_pm_user=True,
                copy_trade_portfolio_ids=["portfolio-1"],
                evidence_path=str(SMART_MONEY_PROFILE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PROFILE_FIXTURE),
                raw_profile={"topTraderId": "top-01", "daysActive": 513},
                now="2026-08-01T08:00:03Z",
            )
            failed = ledger.record_smart_money_profile_observation(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                top_trader_id="top-02",
                observation_status="FAILED",
                captured_at="2026-08-01T08:00:02Z",
                evidence_path=str(SMART_MONEY_PROFILE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PROFILE_FIXTURE),
                failure_reason="PROFILE_TIMEOUT",
                raw_profile={"code": "TIMEOUT"},
                now="2026-08-01T08:00:03Z",
            )
            same = ledger.record_smart_money_profile_observation(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                top_trader_id="top-01",
                observation_status="COMPLETE",
                captured_at="2026-08-01T08:00:02Z",
                days_active=513,
                mdd=Decimal("0.1250"),
                win_rate=Decimal("0.6789"),
                um_margin_balance=Decimal("12345.6700"),
                cm_margin_balance=Decimal("8.500"),
                net_transfer=Decimal("-250.25"),
                sharing_position={"BTCUSDT": "LONG"},
                sharing_history=[{"symbol": "ETHUSDT"}],
                latest_record={"symbol": "BTCUSDT"},
                is_ai=False,
                is_pm_user=True,
                copy_trade_portfolio_ids=["portfolio-1"],
                evidence_path=str(SMART_MONEY_PROFILE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PROFILE_FIXTURE),
                raw_profile={"topTraderId": "top-01", "daysActive": 513},
                now="2026-08-01T08:00:04Z",
            )
            self.assertEqual(complete, same)
            self.assertEqual("0.1250", complete.mdd_decimal)
            self.assertEqual("12345.6700", complete.um_margin_balance_decimal)
            self.assertEqual(["portfolio-1"], complete.copy_trade_portfolio_ids)
            self.assertEqual("FAILED", failed.observation_status)
            self.assertEqual(
                [complete, failed],
                ledger.list_smart_money_profile_observations(
                    logical_run_id=run.logical_run_id
                ),
            )
            with self.assertRaisesRegex(ContractViolation, "raw_profile.topTraderId"):
                ledger.record_smart_money_profile_observation(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    top_trader_id="top-03",
                    observation_status="COMPLETE",
                    captured_at="2026-08-01T08:00:02Z",
                    evidence_path=str(SMART_MONEY_PROFILE_FIXTURE),
                    evidence_file_sha256=file_sha256(SMART_MONEY_PROFILE_FIXTURE),
                    raw_profile={"topTraderId": "top-other"},
                    now="2026-08-01T08:00:05Z",
                )
            with self.assertRaisesRegex(ContractViolation, "different evidence"):
                ledger.record_smart_money_profile_observation(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    top_trader_id="top-01",
                    observation_status="COMPLETE",
                    captured_at="2026-08-01T08:00:02Z",
                    days_active=514,
                    evidence_path=str(SMART_MONEY_PROFILE_FIXTURE),
                    evidence_file_sha256=file_sha256(SMART_MONEY_PROFILE_FIXTURE),
                    raw_profile={"topTraderId": "top-01", "daysActive": 514},
                    now="2026-08-01T08:00:05Z",
                )

    def test_smart_money_square_mapping_requires_explicit_entities_and_conflict_free_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(Path(temporary_directory) / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="smart-money",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T08:00:01Z"
            )
            ledger.record_smart_money_profile_observation(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                top_trader_id="top-01",
                observation_status="FAILED",
                captured_at="2026-08-01T08:00:02Z",
                evidence_path=str(SMART_MONEY_PROFILE_FIXTURE),
                evidence_file_sha256=file_sha256(SMART_MONEY_PROFILE_FIXTURE),
                failure_reason="NO_PROFILE",
                now="2026-08-01T08:00:03Z",
            )
            ledger.record_accepted_post_observations(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                observations=[accepted("1004")],
                now="2026-08-01T08:00:03Z",
            )
            missing_evidence = Path(temporary_directory) / "missing-mapping.json"
            with self.assertRaisesRegex(ContractViolation, "existing readable file"):
                ledger.record_smart_money_square_identity_mapping(
                    top_trader_id="top-01",
                    author_id="opaque-author-id",
                    verified_at="2026-08-01T08:00:03Z",
                    evidence_path=str(missing_evidence),
                    evidence_sha256="1" * 64,
                    now="2026-08-01T08:00:04Z",
                )
            evidence_file = Path(temporary_directory) / "explicit-id-link.json"
            evidence_file.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "topTraderId": "top-01",
                        "squareUid": "opaque-author-id",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractViolation, "does not match"):
                ledger.record_smart_money_square_identity_mapping(
                    top_trader_id="top-01",
                    author_id="opaque-author-id",
                    verified_at="2026-08-01T08:00:03Z",
                    evidence_path=str(evidence_file),
                    evidence_sha256="0" * 64,
                    now="2026-08-01T08:00:04Z",
                )
            name_only_evidence = Path(temporary_directory) / "name-only-link.json"
            name_only_evidence.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "traderName": "same display name",
                        "squareDisplayName": "same display name",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ContractViolation, "topTraderId and squareUid"
            ):
                ledger.record_smart_money_square_identity_mapping(
                    top_trader_id="top-01",
                    author_id="opaque-author-id",
                    verified_at="2026-08-01T08:00:03Z",
                    evidence_path=str(name_only_evidence),
                    evidence_sha256=file_sha256(name_only_evidence),
                    now="2026-08-01T08:00:04Z",
                )
            mismatched_id_evidence = (
                Path(temporary_directory) / "mismatched-id-link.json"
            )
            mismatched_id_evidence.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "topTraderId": "top-other",
                        "squareUid": "opaque-author-id",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ContractViolation, "does not bind"):
                ledger.record_smart_money_square_identity_mapping(
                    top_trader_id="top-01",
                    author_id="opaque-author-id",
                    verified_at="2026-08-01T08:00:03Z",
                    evidence_path=str(mismatched_id_evidence),
                    evidence_sha256=file_sha256(mismatched_id_evidence),
                    now="2026-08-01T08:00:04Z",
                )
            mapping = ledger.record_smart_money_square_identity_mapping(
                top_trader_id="top-01",
                author_id="opaque-author-id",
                verified_at="2026-08-01T08:00:03Z",
                evidence_path=str(evidence_file),
                evidence_sha256=file_sha256(evidence_file),
                now="2026-08-01T08:00:04Z",
            )
            same = ledger.record_smart_money_square_identity_mapping(
                top_trader_id="top-01",
                author_id="opaque-author-id",
                verified_at="2026-08-01T08:00:03Z",
                evidence_path=str(evidence_file),
                evidence_sha256=file_sha256(evidence_file),
                now="2026-08-01T08:00:05Z",
            )
            self.assertEqual(mapping, same)
            self.assertEqual([mapping], ledger.list_smart_money_square_identity_mappings())
            with self.assertRaisesRegex(ContractViolation, "explicit source evidence"):
                ledger.record_smart_money_square_identity_mapping(
                    top_trader_id="top-01",
                    author_id="opaque-author-id",
                    verified_at="2026-08-01T08:00:03Z",
                    evidence_path="evidence/name-match.json",
                    evidence_sha256="2" * 64,
                    verification_method="NAME_MATCH",
                    now="2026-08-01T08:00:06Z",
                )
            with self.assertRaisesRegex(ContractViolation, "conflict"):
                conflicting_evidence = Path(temporary_directory) / "different-link.json"
                conflicting_evidence.write_text(
                    evidence_file.read_text(encoding="utf-8") + "\n",
                    encoding="utf-8",
                )
                ledger.record_smart_money_square_identity_mapping(
                    top_trader_id="top-01",
                    author_id="opaque-author-id",
                    verified_at="2026-08-01T08:00:03Z",
                    evidence_path=str(conflicting_evidence),
                    evidence_sha256=file_sha256(conflicting_evidence),
                    now="2026-08-01T08:00:06Z",
                )

    def test_production_decision_cutoff_is_immutable_across_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite",
                MIGRATION,
            )
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="radar",
                scheduled_for_utc="2026-08-01T08:00:00Z",
                pipeline_version="4.1.0",
                now="2026-08-01T08:00:07Z",
            )

            first = ledger.freeze_production_decision(
                run.logical_run_id,
                decision_at="2026-08-01T08:00:07Z",
                now="2026-08-01T08:00:07Z",
            )
            same = ledger.freeze_production_decision(
                run.logical_run_id,
                decision_at="2026-08-01T08:00:07+00:00",
                now="2026-08-01T08:10:07Z",
            )

            self.assertEqual(first, same)
            self.assertEqual(
                first,
                ledger.get_production_decision(run.logical_run_id),
            )
            with self.assertRaisesRegex(ContractViolation, "frozen cutoff"):
                ledger.freeze_production_decision(
                    run.logical_run_id,
                    decision_at="2026-08-01T08:05:00Z",
                    now="2026-08-01T08:10:07Z",
                )

    def test_next_attempt_is_atomic_and_never_uses_row_count_as_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.1.0",
            )

            first = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T04:00:01Z"
            )
            with self.assertRaisesRegex(ContractViolation, "RUNNING"):
                ledger.start_next_attempt(
                    run.logical_run_id, started_at="2026-08-01T04:00:02Z"
                )
            ledger.finish_attempt(
                first.attempt_id,
                status="FAILED",
                failed_stage="fetch",
                finished_at="2026-08-01T04:00:03Z",
            )
            second = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T04:10:03Z"
            )
            self.assertEqual(2, second.attempt_no)
            ledger.finish_attempt(
                second.attempt_id,
                status="FAILED",
                failed_stage="fetch",
                finished_at="2026-08-01T04:10:04Z",
            )
            with self.assertRaisesRegex(ContractViolation, "exhausted"):
                ledger.start_next_attempt(
                    run.logical_run_id, started_at="2026-08-01T04:20:04Z"
                )

    def test_dedup_baseline_requires_prior_succeeded_production_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)

            first_run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T00:00:00Z",
                pipeline_version="4.1.0",
            )
            first_attempt = ledger.start_next_attempt(
                first_run.logical_run_id, started_at="2026-08-01T00:00:01Z"
            )
            ledger.record_accepted_post_observations(
                logical_run_id=first_run.logical_run_id,
                attempt_id=first_attempt.attempt_id,
                observations=[accepted("1001")],
                now="2026-08-01T00:00:02Z",
            )
            # RUNNING observations are not yet a committed baseline.
            self.assertEqual(
                frozenset(),
                ledger.prior_succeeded_production_post_ids(
                    job_namespace="default",
                    production_job_id="binance-radar-4h",
                    scheduled_for_utc="2026-08-01T04:00:00Z",
                ),
            )
            ledger.finish_attempt(
                first_attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T00:00:03Z",
            )

            failed_run = ledger.create_or_open_production_run(
                production_job_id="binance-radar-4h",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.1.0",
            )
            failed_attempt = ledger.start_next_attempt(
                failed_run.logical_run_id, started_at="2026-08-01T04:00:01Z"
            )
            ledger.record_accepted_post_observations(
                logical_run_id=failed_run.logical_run_id,
                attempt_id=failed_attempt.attempt_id,
                observations=[accepted("1002")],
                now="2026-08-01T04:00:02Z",
            )
            ledger.finish_attempt(
                failed_attempt.attempt_id,
                status="FAILED",
                failed_stage="report",
                finished_at="2026-08-01T04:00:03Z",
            )

            self.assertEqual(
                frozenset({"1001"}),
                ledger.prior_succeeded_production_post_ids(
                    job_namespace="default",
                    production_job_id="binance-radar-4h",
                    scheduled_for_utc="2026-08-01T08:00:00Z",
                ),
            )
            # The failed 04:00 attempt is also excluded from its same-slot retry.
            self.assertEqual(
                frozenset({"1001"}),
                ledger.prior_succeeded_production_post_ids(
                    job_namespace="default",
                    production_job_id="binance-radar-4h",
                    scheduled_for_utc="2026-08-01T04:00:00Z",
                ),
            )

    def test_dedup_baseline_is_isolated_by_job_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)

            for namespace, post_id in (("production", "2001"), ("canary", "3001")):
                run = ledger.create_or_open_production_run(
                    job_namespace=namespace,
                    production_job_id="binance-radar-4h",
                    scheduled_for_utc="2026-08-01T00:00:00Z",
                    pipeline_version="4.1.0",
                )
                attempt = ledger.start_next_attempt(
                    run.logical_run_id,
                    started_at="2026-08-01T00:00:01Z",
                )
                ledger.record_accepted_post_observations(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    observations=[accepted(post_id)],
                    now="2026-08-01T00:00:02Z",
                )
                ledger.finish_attempt(
                    attempt.attempt_id,
                    status="SUCCEEDED",
                    finished_at="2026-08-01T00:00:03Z",
                )

            self.assertEqual(
                frozenset({"2001"}),
                ledger.prior_succeeded_production_post_ids(
                    job_namespace="production",
                    production_job_id="binance-radar-4h",
                    scheduled_for_utc="2026-08-01T04:00:00Z",
                ),
            )

    def test_observations_cannot_be_appended_after_attempt_terminal_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_replay_run(
                replay_namespace="test",
                source_logical_run_id="source",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T00:00:00Z"
            )
            ledger.finish_attempt(
                attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T00:00:01Z",
            )

            with self.assertRaisesRegex(ContractViolation, "RUNNING"):
                ledger.record_accepted_post_observations(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    observations=[accepted("1003")],
                )

    def test_signal_family_and_revisions_are_atomic_deterministic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            first_run = ledger.create_or_open_production_run(
                production_job_id="tracking",
                scheduled_for_utc="2026-08-01T00:00:00Z",
                pipeline_version="4.1.0",
            )
            first_attempt = ledger.start_next_attempt(
                first_run.logical_run_id, started_at="2026-08-01T00:00:00Z"
            )

            first = signal_revision(
                ledger, first_run.logical_run_id, first_attempt.attempt_id
            )
            same = signal_revision(
                ledger,
                first_run.logical_run_id,
                first_attempt.attempt_id,
                now="2026-08-01T00:00:02Z",
            )

            self.assertEqual("9001:BTCUSDT:LONG", first.signal_family_id)
            self.assertEqual(first.signal_revision_id, same.signal_revision_id)
            self.assertEqual(1, first.revision_no)
            self.assertEqual("62000.00", first.entry_low_decimal)
            self.assertEqual(
                ("DETAIL_BACKED", "POINT_IN_TIME"), first.quality_flags
            )
            self.assertEqual(
                1,
                ledger._connection.execute(  # noqa: SLF001 - storage receipt
                    "SELECT COUNT(*) FROM signal_family"
                ).fetchone()[0],
            )
            self.assertEqual(
                1,
                ledger._connection.execute(  # noqa: SLF001 - storage receipt
                    "SELECT COUNT(*) FROM signal_revision"
                ).fetchone()[0],
            )
            with self.assertRaisesRegex(ContractViolation, "different evidence"):
                ledger.record_signal_revision(
                    logical_run_id=first_run.logical_run_id,
                    attempt_id=first_attempt.attempt_id,
                    post_id="9001",
                    symbol="BTCUSDT",
                    direction="LONG",
                    decision_at="2026-08-01T00:00:00Z",
                    parameter_source="AUTHOR",
                    entry_low=Decimal("62001"),
                    entry_high=Decimal("62500"),
                    stop_loss=Decimal("61000"),
                    tp1=Decimal("65000"),
                    tp2=Decimal("67000"),
                    original_signal_status="VALID",
                    dq_score=95,
                    quality_flags=("DETAIL_BACKED", "POINT_IN_TIME"),
                    now="2026-08-01T00:00:03Z",
                )

            ledger.finish_attempt(
                first_attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T00:00:04Z",
            )
            second_run = ledger.create_or_open_production_run(
                production_job_id="tracking",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.1.0",
            )
            second_attempt = ledger.start_next_attempt(
                second_run.logical_run_id, started_at="2026-08-01T04:00:00Z"
            )
            second = signal_revision(
                ledger,
                second_run.logical_run_id,
                second_attempt.attempt_id,
                decision_at="2026-08-01T04:00:00Z",
                now="2026-08-01T04:00:01Z",
            )

            self.assertEqual(2, second.revision_no)
            family = ledger._connection.execute(  # noqa: SLF001 - storage receipt
                "SELECT * FROM signal_family WHERE signal_family_id = ?",
                (first.signal_family_id,),
            ).fetchone()
            self.assertEqual(first_run.logical_run_id, family["first_logical_run_id"])
            self.assertEqual(first_attempt.attempt_id, family["first_attempt_id"])

    def test_tracking_evaluation_maps_outcomes_and_persists_decimal_strings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            run = ledger.create_or_open_production_run(
                production_job_id="tracking",
                scheduled_for_utc="2026-08-01T00:00:00Z",
                pipeline_version="4.1.0",
            )
            attempt = ledger.start_next_attempt(
                run.logical_run_id, started_at="2026-08-01T00:00:00Z"
            )
            revision = signal_revision(ledger, run.logical_run_id, attempt.attempt_id)

            tracking = ledger.record_tracking_evaluation(
                signal_revision_id=revision.signal_revision_id,
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                evaluated_at="2026-08-01T01:00:00Z",
                evaluation_status=Outcome.TRACKING,
                nominal_r=Decimal("0.2500"),
                mfe_r=Decimal("0.5000"),
                mae_r=Decimal("0.1250"),
                quality_flags=("CLOSED_CANDLES",),
                now="2026-08-01T01:00:01Z",
            )
            same = ledger.record_tracking_evaluation(
                signal_revision_id=revision.signal_revision_id,
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                evaluated_at="2026-08-01T01:00:00Z",
                evaluation_status="TRACKING",
                nominal_r=Decimal("0.2500"),
                mfe_r=Decimal("0.5000"),
                mae_r=Decimal("0.1250"),
                quality_flags=("CLOSED_CANDLES",),
                now="2026-08-01T01:00:02Z",
            )

            self.assertEqual(tracking.tracking_evaluation_id, same.tracking_evaluation_id)
            self.assertEqual("TRIGGERED", tracking.evaluation_status)
            self.assertEqual("0.2500", tracking.nominal_r_decimal)
            self.assertEqual("0.5000", tracking.mfe_r_decimal)
            self.assertEqual("0.1250", tracking.mae_r_decimal)

            expired = ledger.record_tracking_evaluation(
                signal_revision_id=revision.signal_revision_id,
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                evaluated_at="2026-08-01T02:00:00Z",
                evaluation_status=Outcome.TIMEOUT,
                net_r=Decimal("-0.123400"),
                cost_model_version="fees-slippage-v1",
                now="2026-08-01T02:00:01Z",
            )
            self.assertEqual("EXPIRED", expired.evaluation_status)
            self.assertEqual("-0.123400", expired.net_r_decimal)

            with self.assertRaisesRegex(ContractViolation, "cost model"):
                ledger.record_tracking_evaluation(
                    signal_revision_id=revision.signal_revision_id,
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    evaluated_at="2026-08-01T03:00:00Z",
                    evaluation_status="EXPIRED",
                    net_r=Decimal("0.1"),
                    now="2026-08-01T03:00:01Z",
                )
            with self.assertRaisesRegex(ContractViolation, "future"):
                ledger.record_tracking_evaluation(
                    signal_revision_id=revision.signal_revision_id,
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    evaluated_at="2026-08-01T04:00:01Z",
                    evaluation_status="PENDING",
                    now="2026-08-01T04:00:00Z",
                )
            with self.assertRaisesRegex(ContractViolation, "precede"):
                ledger.record_tracking_evaluation(
                    signal_revision_id=revision.signal_revision_id,
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    evaluated_at="2026-07-31T23:59:59Z",
                    evaluation_status="PENDING",
                    now="2026-08-01T04:00:00Z",
                )

    def test_point_in_time_queries_exclude_future_and_failed_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            first_run = ledger.create_or_open_production_run(
                production_job_id="tracking",
                scheduled_for_utc="2026-08-01T00:00:00Z",
                pipeline_version="4.1.0",
            )
            first_attempt = ledger.start_next_attempt(
                first_run.logical_run_id, started_at="2026-08-01T00:00:00Z"
            )
            first = signal_revision(
                ledger, first_run.logical_run_id, first_attempt.attempt_id
            )
            ledger.record_tracking_evaluation(
                signal_revision_id=first.signal_revision_id,
                logical_run_id=first_run.logical_run_id,
                attempt_id=first_attempt.attempt_id,
                evaluated_at="2026-08-01T01:00:00Z",
                evaluation_status=Outcome.TRACKING,
                now="2026-08-01T01:00:01Z",
            )
            ledger.record_tracking_evaluation(
                signal_revision_id=first.signal_revision_id,
                logical_run_id=first_run.logical_run_id,
                attempt_id=first_attempt.attempt_id,
                evaluated_at="2026-08-01T02:00:00.500000Z",
                evaluation_status=Outcome.TRACKING,
                now="2026-08-01T02:00:01Z",
            )
            ledger.record_tracking_evaluation(
                signal_revision_id=first.signal_revision_id,
                logical_run_id=first_run.logical_run_id,
                attempt_id=first_attempt.attempt_id,
                evaluated_at="2026-08-01T03:00:00Z",
                evaluation_status=Outcome.STOPPED,
                nominal_r=Decimal("-1"),
                now="2026-08-01T03:00:01Z",
            )
            ledger.finish_attempt(
                first_attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T03:00:02Z",
            )

            second_run = ledger.create_or_open_production_run(
                production_job_id="tracking",
                scheduled_for_utc="2026-08-01T04:00:00Z",
                pipeline_version="4.1.0",
            )
            second_attempt = ledger.start_next_attempt(
                second_run.logical_run_id, started_at="2026-08-01T04:00:00Z"
            )
            second = signal_revision(
                ledger,
                second_run.logical_run_id,
                second_attempt.attempt_id,
                decision_at="2026-08-01T04:00:00Z",
                now="2026-08-01T04:00:01Z",
            )

            self.assertEqual(
                [first.signal_revision_id],
                [
                    value.signal_revision_id
                    for value in ledger.list_current_signal_revisions(
                        as_of="2026-08-01T02:00:00Z"
                    )
                ],
            )
            self.assertEqual(
                ["TRIGGERED"],
                [
                    value.evaluation_status
                    for value in ledger.list_tracking_evaluations(
                        as_of="2026-08-01T02:00:00Z"
                    )
                ],
            )
            self.assertEqual(
                [],
                ledger.list_pending_signal_revisions(
                    as_of="2026-08-01T03:30:00Z"
                ),
            )
            self.assertEqual(
                [second.signal_revision_id],
                [
                    value.signal_revision_id
                    for value in ledger.list_pending_signal_revisions(
                        as_of="2026-08-01T04:00:00Z"
                    )
                ],
            )

            ledger.finish_attempt(
                second_attempt.attempt_id,
                status="FAILED",
                failed_stage="tracking",
                finished_at="2026-08-01T04:00:02Z",
            )
            self.assertEqual(
                [first.signal_revision_id],
                [
                    value.signal_revision_id
                    for value in ledger.list_current_signal_revisions(
                        as_of="2026-08-01T05:00:00Z"
                    )
                ],
            )

    def test_state_writes_reject_mismatched_and_failed_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger = SQLiteRunLedger(
                Path(temporary_directory) / "radar.sqlite", MIGRATION
            )
            self.addCleanup(ledger.close)
            first_run = ledger.create_or_open_production_run(
                production_job_id="tracking-a",
                scheduled_for_utc="2026-08-01T00:00:00Z",
                pipeline_version="4.1.0",
            )
            first_attempt = ledger.start_next_attempt(
                first_run.logical_run_id, started_at="2026-08-01T00:00:00Z"
            )
            second_run = ledger.create_or_open_production_run(
                production_job_id="tracking-b",
                scheduled_for_utc="2026-08-01T00:00:00Z",
                pipeline_version="4.1.0",
            )
            second_attempt = ledger.start_next_attempt(
                second_run.logical_run_id, started_at="2026-08-01T00:00:00Z"
            )
            with self.assertRaisesRegex(ContractViolation, "exact run attempt"):
                ledger.record_signal_family(
                    logical_run_id=first_run.logical_run_id,
                    attempt_id=second_attempt.attempt_id,
                    post_id="9001",
                    symbol="BTCUSDT",
                    direction="LONG",
                    now="2026-08-01T00:00:01Z",
                )

            failed_revision = signal_revision(
                ledger, first_run.logical_run_id, first_attempt.attempt_id
            )
            ledger.finish_attempt(
                first_attempt.attempt_id,
                status="FAILED",
                failed_stage="tracking",
                finished_at="2026-08-01T00:00:02Z",
            )
            with self.assertRaisesRegex(ContractViolation, "FAILED"):
                signal_revision(
                    ledger,
                    first_run.logical_run_id,
                    first_attempt.attempt_id,
                    post_id="9002",
                    now="2026-08-01T00:00:03Z",
                )
            with self.assertRaisesRegex(ContractViolation, "failed revision"):
                ledger.record_tracking_evaluation(
                    signal_revision_id=failed_revision.signal_revision_id,
                    logical_run_id=second_run.logical_run_id,
                    attempt_id=second_attempt.attempt_id,
                    evaluated_at="2026-08-01T01:00:00Z",
                    evaluation_status="PENDING",
                    now="2026-08-01T01:00:01Z",
                )

            self.assertEqual("ok", ledger.integrity_check())
            self.assertEqual([], ledger.foreign_key_check())


if __name__ == "__main__":
    unittest.main()
