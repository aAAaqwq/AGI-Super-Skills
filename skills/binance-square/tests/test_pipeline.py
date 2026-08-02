from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scanner.contracts import ContractViolation
from scanner.authors import load_seed_profile_evidence
from scanner.market import ContractRecord, FailureKind, MarketApiError, MarketSource
from scanner.pipeline import (
    PipelineConfig,
    _publish_latest,
    repair_latest_from_succeeded_attempt,
    run_shadow_radar,
)
from scanner.smart_money import collect_smart_money, verify_evidence_integrity
from scanner.storage import SQLiteRunLedger
from tests.test_derivation import complete_market
from tests.test_smart_money import FakeSmartMoneyApi
from tests.test_authors import write_v2_identity_evidence
from scripts.build_identity_mapping_catalog import build_identity_mapping_catalog
from scripts.run_radar import _arguments as radar_arguments


PROJECT = Path(__file__).parents[1]
MIGRATION = PROJECT / "migrations"
FIXTURE = PROJECT / "tests" / "fixtures" / "m1b"
SEED_EVIDENCE = (
    Path(__file__).parent / "fixtures" / "discovery" / "leaderboard_seed_profiles.json"
)


def catalog_only(value: str) -> SimpleNamespace:
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return SimpleNamespace(
        fetch_futures_catalog=lambda: SimpleNamespace(
            server_time_ms=int(observed.timestamp() * 1000)
        )
    )


def resign_smart_money(document: dict[str, object]) -> dict[str, object]:
    unsigned = {key: value for key, value in document.items() if key != "integrity"}
    digest = sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    document["integrity"] = {
        "algorithm": "SHA256",
        "scope": "canonical top-level JSON excluding integrity",
        "payload_sha256": digest,
    }
    return document


class ShadowPipelineTests(unittest.TestCase):
    def test_cli_accepts_one_catalog_and_rejects_catalog_plus_single_mapping(self) -> None:
        catalog = Path("fixture-catalog.json")
        parsed = radar_arguments(
            [
                "--fixture",
                str(FIXTURE),
                "--smart-money-square-mapping-catalog",
                str(catalog),
            ]
        )
        self.assertEqual(catalog, parsed.smart_money_square_mapping_catalog)
        with self.assertRaises(SystemExit):
            radar_arguments(
                [
                    "--fixture",
                    str(FIXTURE),
                    "--smart-money-square-mapping-catalog",
                    str(catalog),
                    "--smart-money-square-mapping-evidence",
                    "single.json",
                ]
            )

    def test_smart_money_catalog_fetches_two_approved_square_profiles(self) -> None:
        evidence = self._smart_money_evidence()
        trader_ids = [
            evidence["rankings"][0]["rows"][index]["source_id"]
            for index in range(2)
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            members = []
            for index, trader_id in enumerate(reversed(trader_ids), start=1):
                member = root / f"member-{index}"
                member.mkdir()
                path, _, _ = write_v2_identity_evidence(
                    str(member),
                    promotion_status="APPROVED",
                    top_trader_id=trader_id,
                    square_uid=f"fixture-square-{trader_id}",
                    provenance="FIXTURE_REPLAY",
                )
                members.append((path, sha256(path.read_bytes()).hexdigest()))
            catalog_path = root / "identity-catalog.json"
            build_identity_mapping_catalog(
                artifacts=members,
                output_path=catalog_path,
                receipt_path=root / "identity-catalog.receipt.json",
            )
            requested: list[str] = []

            def fetch_profile(square_uid: str, offset: int) -> dict[str, object]:
                requested.append(square_uid)
                return {
                    "success": True,
                    "data": {"contents": [], "nextTimeOffset": None},
                }

            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    smart_money_enabled=True,
                    smart_money_square_mapping_catalog=catalog_path,
                    limit=5,
                ),
                smart_money_collector=lambda: deepcopy(evidence),
                profile_content_fetcher=fetch_profile,
                profile_capture_time="2026-07-31T05:48:35Z",
            )

            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual(
                sorted(f"fixture-square-{value}" for value in trader_ids),
                sorted(requested),
            )
            self.assertEqual(2, report["profile_channel"]["empty_authors"])
            self.assertEqual(
                "2/60 (3.3%)",
                report["smart_money"]["square_identity_mapping_coverage"]["label"],
            )
            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            catalog_manifest = next(
                item
                for item in ledger.list_manifests(result.logical_run_id)
                if item.artifact_path == str(catalog_path)
            )
            self.assertEqual(2, catalog_manifest.record_count)
            self.assertEqual(sha256(catalog_path.read_bytes()).hexdigest(), catalog_manifest.sha256_hex)
            mapped_square_uids = tuple(
                sorted(f"fixture-square-{value}" for value in trader_ids)
            )
            placeholders = ",".join("?" for _ in mapped_square_uids)
            authors = ledger._connection.execute(  # noqa: SLF001 - audit receipt
                f"SELECT * FROM author_entity WHERE author_id IN ({placeholders}) "
                "ORDER BY author_id",
                mapped_square_uids,
            ).fetchall()
            self.assertEqual(2, len(authors))
            self.assertTrue(
                all(
                    row["identity_source"]
                    == "BINANCE_SQUARE_UID_DIRECT_IDENTITY_EVIDENCE"
                    for row in authors
                )
            )
            artifacts = ledger._connection.execute(  # noqa: SLF001 - audit receipt
                "SELECT * FROM smart_money_identity_artifact ORDER BY artifact_path"
            ).fetchall()
            self.assertEqual(2, len(artifacts))
            self.assertEqual(
                {str(path.resolve()) for path, _ in members},
                {row["artifact_path"] for row in artifacts},
            )
            self.assertTrue(
                all(
                    row["promotion_status"] == "APPROVED"
                    and row["verification_status"] == "DIRECT_VERIFIED"
                    and row["request_manifest_sha256"]
                    and row["raw_response_sha256"]
                    and row["top_trader_id_pointer"] == "/data/topTraderId"
                    and row["square_uid_pointer"] == "/data/squareUid"
                    and json.loads(row["review_json"])["decision"] == "APPROVE"
                    for row in artifacts
                )
            )
            self.assertEqual(
                2,
                ledger._connection.execute(  # noqa: SLF001 - audit receipt
                    "SELECT COUNT(*) FROM smart_money_identity_mapping_event "
                    "WHERE event_type = 'LINK'"
                ).fetchone()[0],
            )
            self.assertEqual(
                sorted(trader_ids),
                sorted(
                    item.top_trader_id
                    for item in ledger.list_smart_money_square_identity_mappings()
                ),
            )

    def test_identity_catalog_proposed_conflict_and_missing_trader_fail_closed(self) -> None:
        evidence = self._smart_money_evidence()
        known_traders = [
            evidence["rankings"][0]["rows"][index]["source_id"]
            for index in range(2)
        ]
        for case in ("proposed", "conflict", "missing_trader"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                members: list[Path] = []
                if case == "proposed":
                    member = root / "member-proposed"
                    member.mkdir()
                    path, _, _ = write_v2_identity_evidence(
                        str(member),
                        top_trader_id=known_traders[0],
                        square_uid="fixture-square-proposed",
                        provenance="FIXTURE_REPLAY",
                    )
                    members.append(path)
                elif case == "conflict":
                    for index, trader_id in enumerate(known_traders):
                        member = root / f"member-conflict-{index}"
                        member.mkdir()
                        path, _, _ = write_v2_identity_evidence(
                            str(member),
                            promotion_status="APPROVED",
                            top_trader_id=trader_id,
                            square_uid="fixture-square-conflict",
                            provenance="FIXTURE_REPLAY",
                        )
                        members.append(path)
                else:
                    member = root / "member-missing"
                    member.mkdir()
                    path, _, _ = write_v2_identity_evidence(
                        str(member),
                        promotion_status="APPROVED",
                        top_trader_id="fixture-trader-not-in-smart-money",
                        square_uid="fixture-square-missing",
                        provenance="FIXTURE_REPLAY",
                    )
                    members.append(path)
                catalog_path = root / "identity-catalog.json"
                catalog_path.write_text(
                    json.dumps(
                        {
                            "schema": "binance-smart-money-square-identity-catalog/v1",
                            "tenant_id": "fixture-tenant",
                            "provenance": "FIXTURE_REPLAY",
                            "artifacts": [
                                {
                                    "path": str(path),
                                    "sha256": sha256(path.read_bytes()).hexdigest(),
                                }
                                for path in members
                            ],
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )

                with self.assertRaises(ContractViolation):
                    run_shadow_radar(
                        PipelineConfig(
                            mode="fixture",
                            output_dir=root / "runs",
                            database=root / "radar.sqlite",
                            decision_at="2026-07-31T05:48:36Z",
                            fixture_dir=FIXTURE,
                            smart_money_enabled=True,
                            smart_money_square_mapping_catalog=catalog_path,
                            limit=5,
                        ),
                        smart_money_collector=lambda: deepcopy(evidence),
                    )

                ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
                self.addCleanup(ledger.close)
                self.assertEqual(
                    ["FAILED"],
                    [
                        row[0]
                        for row in ledger._connection.execute(  # noqa: SLF001
                            "SELECT status FROM run_attempt ORDER BY attempt_no"
                        )
                    ],
                )
                self.assertEqual(
                    (0, 0, 0),
                    (
                        ledger._connection.execute(  # noqa: SLF001
                            "SELECT COUNT(*) FROM smart_money_identity_artifact"
                        ).fetchone()[0],
                        ledger._connection.execute(  # noqa: SLF001
                            "SELECT COUNT(*) FROM smart_money_identity_mapping_event"
                        ).fetchone()[0],
                        len(ledger.list_smart_money_square_identity_mappings()),
                    ),
                )

    def test_seed_profiles_fetch_independently_while_zero_smart_money_mapping_stays_blocked(self) -> None:
        evidence = self._smart_money_evidence()
        seed_uids = {
            profile.author_id
            for profile in load_seed_profile_evidence(SEED_EVIDENCE).profiles
        }
        requested: list[tuple[str, int]] = []

        def fetch_profile(square_uid: str, offset: int) -> dict[str, object]:
            requested.append((square_uid, offset))
            return {
                "success": True,
                "data": {"contents": [], "nextTimeOffset": None},
            }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    leaderboard_seed_evidence=SEED_EVIDENCE,
                    smart_money_enabled=True,
                    limit=5,
                ),
                smart_money_collector=lambda: deepcopy(evidence),
                profile_content_fetcher=fetch_profile,
                profile_capture_time="2026-07-31T05:48:35Z",
            )
            report = json.loads(result.report_json.read_text(encoding="utf-8"))

        self.assertEqual(seed_uids, {uid for uid, _ in requested})
        self.assertEqual(len(seed_uids), len(requested))
        self.assertTrue(all(offset == -1 for _, offset in requested))
        cohorts = report["profile_channel"]
        self.assertEqual("PARTIAL", cohorts["status"])
        self.assertEqual(
            {"smart_money_profiles": 60, "seed_profiles": 9},
            cohorts["cohort_denominators"],
        )
        self.assertEqual(9, cohorts["seed_profiles"]["planned_authors"])
        self.assertEqual("EMPTY", cohorts["seed_profiles"]["status"])
        self.assertEqual(60, cohorts["smart_money_profiles"]["planned_authors"])
        self.assertEqual(
            "BLOCKED_IDENTITY_MAPPING",
            cohorts["smart_money_profiles"]["reason"],
        )
        self.assertEqual(0, report["smart_money"]["square_identity_mapping_coverage"]["covered"])

    def _smart_money_evidence(
        self, ranking_types: tuple[str, ...] = ("PNL", "ROI")
    ) -> dict[str, object]:
        api = FakeSmartMoneyApi()
        api.test_case = self
        base = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
        ticks = 0

        def clock() -> datetime:
            nonlocal ticks
            ticks += 1
            return base + timedelta(milliseconds=ticks * 100)

        return collect_smart_money(
            ranking_types=ranking_types,
            get_json=api,
            captured_at="2026-08-01T12:05:00Z",
            clock=clock,
        )

    def test_standard_smart_money_import_rejects_one_of_two_rankings(self) -> None:
        evidence = self._smart_money_evidence(("PNL",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(
                ContractViolation, r"complete PNL\+ROI rankings"
            ):
                run_shadow_radar(
                    PipelineConfig(
                        mode="fixture",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at="2026-07-31T05:48:36Z",
                        fixture_dir=FIXTURE,
                        smart_money_enabled=True,
                        limit=5,
                    ),
                    smart_money_collector=lambda: deepcopy(evidence),
                )

    def test_resigned_smart_money_fixture_contract_tampering_is_rejected(self) -> None:
        evidence = self._smart_money_evidence()

        def contract_time_range(document: dict[str, object]) -> None:
            document["contract"]["time_range"] = "7D"  # type: ignore[index]

        def ranking_time_range(document: dict[str, object]) -> None:
            document["rankings"][0]["time_range"] = "7D"  # type: ignore[index]

        def contract_rows(document: dict[str, object]) -> None:
            document["contract"]["rows_per_page"] = 30  # type: ignore[index]

        def page_request_rows(document: dict[str, object]) -> None:
            document["rankings"][0]["pages"][0]["request"]["rows"] = 30  # type: ignore[index]

        def contract_pages(document: dict[str, object]) -> None:
            document["contract"]["pages"] = [1, 2]  # type: ignore[index]

        def actual_pages(document: dict[str, object]) -> None:
            document["rankings"][0]["pages"].pop()  # type: ignore[index]

        def contract_filter(document: dict[str, object]) -> None:
            document["contract"]["fixed_filters"][  # type: ignore[index]
                "onlyShowSignalEnabled"
            ] = False

        def page_request_filter(document: dict[str, object]) -> None:
            document["rankings"][0]["pages"][0]["request"][  # type: ignore[index]
                "onlyShowSharingPosition"
            ] = False

        cases = (
            ("contract-time-range", contract_time_range),
            ("ranking-time-range", ranking_time_range),
            ("contract-rows", contract_rows),
            ("page-request-rows", page_request_rows),
            ("contract-pages", contract_pages),
            ("actual-pages", actual_pages),
            ("contract-filter", contract_filter),
            ("page-request-filter", page_request_filter),
        )
        for label, mutate in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                tampered = deepcopy(evidence)
                mutate(tampered)
                resign_smart_money(tampered)
                self.assertTrue(verify_evidence_integrity(tampered))
                fixture_path = root / f"{label}.json"
                fixture_path.write_text(
                    json.dumps(tampered, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(ContractViolation, "Smart Money"):
                    run_shadow_radar(
                        PipelineConfig(
                            mode="fixture",
                            output_dir=root / "runs",
                            database=root / "radar.sqlite",
                            decision_at="2026-07-31T05:48:36Z",
                            fixture_dir=FIXTURE,
                            smart_money_enabled=True,
                            smart_money_fixture=fixture_path,
                            limit=5,
                        )
                    )

    def test_smart_money_stage_persists_two_top30_rankings_and_profiles(self) -> None:
        evidence = self._smart_money_evidence()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=database,
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    smart_money_enabled=True,
                    limit=5,
                ),
                smart_money_collector=lambda: deepcopy(evidence),
            )

            self.assertIsNotNone(result.smart_money_json)
            assert result.smart_money_json is not None
            saved = json.loads(result.smart_money_json.read_text(encoding="utf-8"))
            self.assertTrue(verify_evidence_integrity(saved))
            self.assertEqual(
                result.smart_money_json.read_bytes(),
                (root / "runs" / "latest" / "smart_money.json").read_bytes(),
            )
            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            markdown = result.report_markdown.read_text(encoding="utf-8")
            self.assertEqual("2/2 (100.0%)", report["leaderboard_coverage"]["label"])
            self.assertNotIn("0/4", markdown)
            self.assertEqual(
                "OBSERVED_WINDOW", report["smart_money"]["observation_semantics"]
            )
            self.assertEqual(
                60, report["smart_money"]["ranking_coverage"]["rendered_rank_rows"]
            )
            self.assertEqual(
                "60/60 (100.0%)",
                report["smart_money"]["profile_detail_coverage"]["label"],
            )
            self.assertEqual(
                "0/60 (0.0%)",
                report["smart_money"]["square_identity_mapping_coverage"]["label"],
            )
            self.assertEqual(0, report["smart_money"]["tier_a_eligible"])
            self.assertEqual(0, report["candidate_audit"][0]["author_score_assumption"])
            self.assertIn("Tier A eligible=0", markdown)

            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            captures = ledger.list_smart_money_leaderboard_captures(
                attempt_id=result.attempt_id
            )
            self.assertEqual(["PNL", "ROI"], [item.ranking_type for item in captures])
            self.assertTrue(
                all(item.snapshot_semantics == "OBSERVED_WINDOW" for item in captures)
            )
            self.assertEqual(
                [30, 30],
                [len(ledger.list_smart_money_leaderboard_rows(item.smart_money_capture_id)) for item in captures],
            )
            self.assertEqual(
                60,
                len(ledger.list_smart_money_profile_observations(attempt_id=result.attempt_id)),
            )
            manifest = next(
                item
                for item in ledger.list_manifests(result.logical_run_id)
                if item.artifact_path == str(result.smart_money_json)
            )
            self.assertEqual(60, manifest.record_count)
            self.assertEqual(
                manifest.sha256_hex,
                sha256(result.smart_money_json.read_bytes()).hexdigest(),
            )
            self.assertTrue(
                all(item.evidence_file_sha256 == manifest.sha256_hex for item in captures)
            )
            self.assertTrue(
                all(
                    item.payload_sha256 == evidence["integrity"]["payload_sha256"]
                    for item in captures
                )
            )

    def test_smart_money_profile_mapping_is_consumed_without_name_inference(self) -> None:
        evidence = self._smart_money_evidence()
        top_trader_id = evidence["rankings"][0]["rows"][0]["source_id"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mapping_path = root / "identity-mapping.json"
            mapping_path.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "captured_at_utc": "2026-07-31T05:47:00Z",
                        "provenance": "FIXTURE_REPLAY",
                        "mappings": [
                            {
                                "topTraderId": top_trader_id,
                                "squareUid": "fixture-square-mapped-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            requested: list[str] = []

            def fetch_profile(square_uid: str) -> dict[str, object]:
                requested.append(square_uid)
                return {
                    "success": True,
                    "data": {
                        "contents": [
                            {
                                "id": "123456789",
                                "contentType": "POST",
                                "squareUid": square_uid,
                            }
                        ]
                    },
                }

            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    smart_money_enabled=True,
                    smart_money_square_mapping_evidence=mapping_path,
                    limit=5,
                ),
                smart_money_collector=lambda: deepcopy(evidence),
                profile_content_fetcher=fetch_profile,
                profile_capture_time="2026-07-31T05:48:35Z",
            )

            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual(["fixture-square-mapped-01"], requested)
            self.assertEqual("PARTIAL", report["profile_channel"]["status"])
            self.assertEqual(60, report["profile_channel"]["planned_authors"])
            self.assertEqual(1, report["profile_channel"]["complete_authors"])
            self.assertEqual(59, report["profile_channel"]["not_attempted_authors"])
            self.assertEqual(
                "1/60 (1.7%)",
                report["smart_money"]["square_identity_mapping_coverage"]["label"],
            )
            self.assertEqual("PARTIAL", report["source_coverage"]["PROFILE"]["status"])
            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            self.assertTrue(
                any(
                    item.artifact_path == str(mapping_path)
                    for item in ledger.list_manifests(result.logical_run_id)
                )
            )

    def test_smart_money_failure_is_audited_and_does_not_move_latest(self) -> None:
        evidence = self._smart_money_evidence()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            output = root / "runs"
            first = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=output,
                    database=database,
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    smart_money_enabled=True,
                    limit=5,
                ),
                smart_money_collector=lambda: deepcopy(evidence),
            )
            previous_latest = first.latest_json.read_bytes()

            def fail_collection() -> dict[str, object]:
                raise ContractViolation("Smart Money fixture failure")

            with self.assertRaisesRegex(ContractViolation, "fixture failure"):
                run_shadow_radar(
                    PipelineConfig(
                        mode="fixture",
                        output_dir=output,
                        database=database,
                        decision_at="2026-07-31T06:48:36Z",
                        fixture_dir=FIXTURE,
                        smart_money_enabled=True,
                        limit=5,
                    ),
                    smart_money_collector=fail_collection,
                )
            self.assertEqual(previous_latest, first.latest_json.read_bytes())
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            failed = [
                attempt
                for run in ledger.list_logical_runs()
                for attempt in ledger.list_attempts(run.logical_run_id)
                if attempt.status == "FAILED"
            ]
            self.assertEqual(1, len(failed))
            self.assertEqual("smart_money", failed[0].failed_stage)

    def test_fixture_run_writes_auditable_reports_and_run_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"

            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=database,
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    limit=5,
                )
            )

            raw = json.loads(result.raw_json.read_text(encoding="utf-8"))
            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            markdown = result.report_markdown.read_text(encoding="utf-8")
            self.assertEqual(1, raw["counts"]["accepted_observations"])
            self.assertEqual(4, report["post_counts"]["discovered"])
            self.assertEqual(1, report["post_counts"]["total"])
            self.assertEqual(1, report["post_counts"]["unique_accepted"])
            self.assertIsNone(report["post_counts"]["new"])
            self.assertEqual("BLOCKED", report["leaderboard_coverage"]["status"])
            self.assertEqual("0/4 (0.0%)", report["leaderboard_coverage"]["label"])
            self.assertEqual(
                "https://www.binance.com/en/square/post/990000000000101",
                report["candidate_audit"][0]["source_post_url"],
            )
            self.assertIn("990000000000101", markdown)
            self.assertIn("报告生成时间 UTC：", markdown)
            self.assertIn("行情证据：", markdown)
            self.assertEqual(
                result.report_json.read_bytes(), result.latest_json.read_bytes()
            )
            self.assertEqual(
                result.report_markdown.read_bytes(), result.latest_markdown.read_bytes()
            )

            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            self.assertEqual(1, len(ledger.list_logical_runs()))
            self.assertEqual(4, len(ledger.list_manifests(result.logical_run_id)))
            manifests = ledger.list_manifests(result.logical_run_id)
            raw_manifest = next(
                item for item in manifests if item.artifact_path == str(result.raw_json)
            )
            report_manifest = next(
                item for item in manifests if item.artifact_path == str(result.report_json)
            )
            self.assertEqual(4, raw_manifest.record_count)
            self.assertEqual("2026-07-30T05:48:36Z", raw_manifest.event_start_utc)
            self.assertEqual("2026-07-30T05:48:36Z", raw_manifest.event_end_utc)
            self.assertEqual(1, report_manifest.record_count)
            market = json.loads(result.market_json.read_text(encoding="utf-8"))
            self.assertEqual({}, market["snapshots"])
            attempts = ledger.list_attempts(result.logical_run_id)
            self.assertEqual("SUCCEEDED", attempts[0].status)
            self.assertIsNotNone(attempts[0].finished_at_utc)
            observations = ledger.list_post_observations(result.logical_run_id)
            self.assertEqual(["990000000000101"], [item.post_id for item in observations])

    def test_seed_evidence_is_manifested_but_never_adds_author_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=database,
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    leaderboard_seed_evidence=SEED_EVIDENCE,
                    limit=5,
                )
            )

            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual(
                "PARTIAL_SEED_DISCOVERY",
                report["leaderboard_coverage"]["status"],
            )
            self.assertEqual(9, report["leaderboard_coverage"]["verified_seed_profiles"])
            self.assertEqual(0, report["leaderboard_coverage"]["rendered_rank_rows"])
            self.assertEqual(
                0, report["candidate_audit"][0]["author_score_assumption"]
            )

            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            manifests = ledger.list_manifests(result.logical_run_id)
            self.assertEqual(5, len(manifests))
            seed_manifest = next(
                item for item in manifests if item.artifact_path == str(SEED_EVIDENCE)
            )
            self.assertEqual(9, seed_manifest.record_count)
            self.assertEqual(
                "2026-08-01T08:50:34Z", seed_manifest.event_start_utc
            )

    def test_cli_fixture_defaults_to_local_no_send_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "scripts" / "run_radar.py"),
                    "--fixture",
                    str(FIXTURE),
                    "--clock",
                    "2026-07-31T05:48:36Z",
                    "--leaderboard-seed-evidence",
                    str(SEED_EVIDENCE),
                    "--output-dir",
                    str(root / "runs"),
                    "--database",
                    str(root / "radar.sqlite"),
                    "--limit",
                    "5",
                ],
                cwd=PROJECT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertTrue(receipt["no_send"])
            self.assertTrue(Path(receipt["report_json"]).exists())
            self.assertTrue((root / "runs" / "latest.md").exists())
            report = json.loads(
                Path(receipt["report_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                "PARTIAL_SEED_DISCOVERY",
                report["leaderboard_coverage"]["status"],
            )

    def test_cli_smart_money_fixture_is_explicit_and_network_free(self) -> None:
        evidence = self._smart_money_evidence()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_path = root / "smart-money-fixture.json"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False), encoding="utf-8"
            )
            mapping_path = root / "identity-mapping.json"
            mapping_path.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "captured_at_utc": "2026-07-31T05:47:00Z",
                        "provenance": "FIXTURE_REPLAY",
                        "mappings": [
                            {
                                "topTraderId": evidence["rankings"][0]["rows"][0][
                                    "source_id"
                                ],
                                "squareUid": "fixture-square-cli-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "scripts" / "run_radar.py"),
                    "--fixture",
                    str(FIXTURE),
                    "--clock",
                    "2026-07-31T05:48:36Z",
                    "--smart-money-fixture",
                    str(evidence_path),
                    "--smart-money-square-mapping-evidence",
                    str(mapping_path),
                    "--output-dir",
                    str(root / "runs"),
                    "--database",
                    str(root / "radar.sqlite"),
                    "--limit",
                    "5",
                ],
                cwd=PROJECT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertTrue(receipt["no_send"])
            self.assertTrue(Path(receipt["smart_money_json"]).is_file())
            report = json.loads(
                Path(receipt["report_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual("2/2 (100.0%)", report["leaderboard_coverage"]["label"])
            self.assertEqual(0, report["smart_money"]["tier_a_eligible"])
            self.assertEqual(
                "1/60 (1.7%)",
                report["smart_money"]["square_identity_mapping_coverage"]["label"],
            )
            self.assertEqual("NOT_ATTEMPTED", report["profile_channel"]["status"])

    def test_real_mode_merges_urls_refreshes_details_and_uses_market_seam(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_url = "https://www.binance.com/en/square/post/990000000000101"
            signal_url = "https://www.binance.com/en/square/post/990000000000102"
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({
                "count": 1,
                "posts": [{"url": snapshot_url, "text": "old", "time": "old", "author": "LIVE", "is_new": True}],
                "new_posts": [],
                "scanned_at": "2026-07-31T07:59:30Z",
                "snapshot_file": str(snapshot),
            }), encoding="utf-8")
            signals = root / "signals.json"
            signals.write_text(json.dumps([{
                "source_url": signal_url, "symbol": "BTC", "direction": "long",
                "entry": "62000 - 62500", "sl": "61000",
                "tp": "65000 / 67000", "time": "old", "author": "untrusted",
            }]), encoding="utf-8")
            base = json.loads((FIXTURE / "post_detail_public.json").read_text(encoding="utf-8"))
            refreshed: list[str] = []

            def fetch_detail(url: str) -> dict:
                refreshed.append(url)
                value = deepcopy(base)
                post_id = int(url.rsplit("/", 1)[1])
                value["response"]["data"].update({
                    "id": post_id,
                    "webLink": url,
                    "firstReleaseTime": 1785476916000,
                })
                if url == snapshot_url:
                    value["response"]["data"]["bodyTextOnly"] = "market news only"
                return value

            class MarketSeam:
                def __init__(self) -> None:
                    self.symbols: list[str] = []

                def fetch_futures_catalog(self) -> SimpleNamespace:
                    contract = ContractRecord(
                        symbol="BTCUSDT",
                        status="TRADING",
                        contract_type="PERPETUAL",
                        base_asset="BTC",
                        quote_asset="USDT",
                        margin_asset="USDT",
                    )
                    return SimpleNamespace(
                        server_time_ms=1785484800000,
                        captured_at=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
                        contracts={"BTCUSDT": contract},
                    )

                def fetch_snapshot(
                    self,
                    symbol: str,
                    *,
                    catalog: object,
                    decision_time_ms: int,
                ) -> SimpleNamespace:
                    self.symbols.append(symbol)
                    self.decision_time_ms = decision_time_ms
                    return SimpleNamespace(
                        symbol=symbol,
                        contract=SimpleNamespace(symbol=symbol, status="TRADING"),
                        last_price=Decimal("63000"),
                        source=MarketSource.FUTURES,
                        captured_at=datetime(2026, 7, 31, 5, 47, tzinfo=timezone.utc),
                        missing_fields=(), candles={}, decision_time_ms=1785390516000,
                    )

            market = MarketSeam()
            result = run_shadow_radar(
                PipelineConfig(
                    mode="real", output_dir=root / "runs", database=root / "radar.sqlite",
                    decision_at="2026-07-31T08:00:00Z", input_snapshot=snapshot,
                    signals_json=signals, limit=2, official_news_enabled=True,
                ),
                detail_fetcher=fetch_detail,
                market_client=market,  # type: ignore[arg-type]
                official_news_collector=lambda: {
                    "schema_version": "binance-official-news/v1",
                    "source_system": "binance_official_announcement_cms",
                    "status": "COMPLETE",
                    "decision_at_utc": "2026-07-31T08:00:00Z",
                    "window_start_utc": "2026-07-30T08:00:00Z",
                    "captured_at_utc": "2026-07-31T08:00:01Z",
                    "record_count": 1,
                    "records": [{
                        "article_id": "official-one",
                        "title": "Official market update",
                        "published_at_utc": "2026-07-31T07:30:00Z",
                        "captured_at_utc": "2026-07-31T08:00:01Z",
                        "source_url": "https://www.binance.com/en/support/announcement/detail/official-one",
                    }],
                },
                clock=lambda: datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
            )

            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual([signal_url, snapshot_url], refreshed)
            self.assertEqual(["BTCUSDT"], market.symbols)
            self.assertEqual(1785484800000, market.decision_time_ms)
            self.assertEqual("AUTHOR_LEGACY_EXTRACTED", report["candidate_audit"][0]["parameter_mapping"])
            self.assertEqual("0/2 (0.0%)", report["leaderboard_coverage"]["label"])
            self.assertNotIn("0/4", result.report_markdown.read_text(encoding="utf-8"))
            self.assertEqual("2026-07-31T05:47:00Z", report["candidate_audit"][0]["market_captured_at"])
            market_artifact = json.loads(result.market_json.read_text(encoding="utf-8"))
            self.assertIn("BTCUSDT", market_artifact["snapshots"])
            self.assertIsNotNone(result.market_catalog_json)
            assert result.market_catalog_json is not None
            catalog_artifact = json.loads(result.market_catalog_json.read_text(encoding="utf-8"))
            self.assertEqual(1, catalog_artifact["record_count"])
            self.assertEqual(
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "contractType": "PERPETUAL",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "marginAsset": "USDT",
                },
                catalog_artifact["records"][0],
            )
            self.assertEqual(64, len(catalog_artifact["records_sha256"]))
            self.assertIsNotNone(result.official_news_json)
            assert result.official_news_json is not None
            self.assertEqual(
                "COMPLETE",
                report["source_coverage"]["BINANCE_OFFICIAL_NEWS"]["status"],
            )
            self.assertEqual(
                ("PARTIAL", "LEGACY_UNVERIFIED", "LEGACY_UNVERIFIED"),
                (
                    report["source_coverage"]["FEED"]["status"],
                    report["source_coverage"]["FEED"]["coverage_status"],
                    report["source_coverage"]["FEED"]["termination_reason"],
                ),
            )
            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            self.assertEqual(
                "2026-07-31T08:00:00Z",
                ledger.list_logical_runs()[0].scheduled_for_utc,
            )
            self.assertEqual(
                {
                    "scheduled_for_utc": "2026-07-31T08:00:00Z",
                    "decision_at_utc": "2026-07-31T08:00:00Z",
                    "decision_lag_seconds": 0,
                    "maximum_production_lag_seconds": 600,
                },
                report["run_timing"],
            )
            self.assertEqual(
                "2026-07-31T07:59:30Z",
                report["input_lineage"]["discovery_snapshot"]["captured_at_utc"],
            )
            self.assertEqual(str(snapshot), report["input_lineage"]["discovery_snapshot"]["path"])
            self.assertEqual(str(signals), report["input_lineage"]["signal_input"]["path"])
            manifested_paths = {
                item.artifact_path for item in ledger.list_manifests(result.logical_run_id)
            }
            self.assertIn(str(snapshot), manifested_paths)
            self.assertIn(str(signals), manifested_paths)
            self.assertIn(str(result.official_news_json), manifested_paths)

    def test_real_failure_marks_attempt_failed_without_replacing_latest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_url = "https://www.binance.com/en/square/post/990000000000101"
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({
                "count": 1,
                "posts": [{"url": snapshot_url}],
                "new_posts": [],
                "scanned_at": "2026-07-31T07:59:30Z",
                "snapshot_file": str(snapshot),
            }), encoding="utf-8")
            signals = root / "signals.json"
            signals.write_text(json.dumps([{
                "url": snapshot_url, "symbol": "BTC", "direction": "long",
                "entry": "62000", "sl": "61000", "tp": "65000 / 67000",
            }]), encoding="utf-8")
            runs = root / "runs"
            runs.mkdir()
            (runs / "latest.json").write_bytes(b"previous-json")
            (runs / "latest.md").write_bytes(b"previous-markdown")
            base = json.loads((FIXTURE / "post_detail_public.json").read_text(encoding="utf-8"))

            def fetch_detail(url: str) -> dict:
                value = deepcopy(base)
                value["response"]["data"].update({
                    "id": int(url.rsplit("/", 1)[1]),
                    "webLink": url,
                    "firstReleaseTime": 1785476916000,
                })
                return value

            class FailingMarket:
                def fetch_futures_catalog(self) -> SimpleNamespace:
                    return SimpleNamespace(server_time_ms=1785484800000)

                def fetch_snapshot(
                    self,
                    symbol: str,
                    *,
                    catalog: object,
                    decision_time_ms: int,
                ) -> object:
                    raise RuntimeError("injected market failure")

            database = root / "radar.sqlite"
            with self.assertRaisesRegex(RuntimeError, "injected market failure"):
                run_shadow_radar(
                    PipelineConfig(
                        mode="real", output_dir=runs, database=database,
                        decision_at="2026-07-31T08:00:00Z", input_snapshot=snapshot,
                        signals_json=signals, limit=1,
                    ),
                    detail_fetcher=fetch_detail,
                    market_client=FailingMarket(),  # type: ignore[arg-type]
                    clock=lambda: datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
                )

            self.assertEqual(b"previous-json", (runs / "latest.json").read_bytes())
            self.assertEqual(b"previous-markdown", (runs / "latest.md").read_bytes())
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            logical_run = ledger.list_logical_runs()[0]
            attempt = ledger.list_attempts(logical_run.logical_run_id)[0]
            self.assertEqual("FAILED", attempt.status)
            self.assertEqual("analysis", attempt.failed_stage)

    def test_latest_pointer_atomically_switches_json_and_markdown_as_one_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "run-one"
            second = root / "run-two"
            for run, label in ((first, "one"), (second, "two")):
                run.mkdir()
                (run / "report.json").write_text(f"json-{label}", encoding="utf-8")
                (run / "report.md").write_text(f"md-{label}", encoding="utf-8")

            _publish_latest(root, first, "attempt-one")
            self.assertTrue((root / "latest").is_symlink())
            self.assertEqual("json-one", (root / "latest.json").read_text())
            self.assertEqual("md-one", (root / "latest.md").read_text())

            with patch("scanner.pipeline.os.replace", side_effect=OSError("injected pointer failure")):
                with self.assertRaisesRegex(OSError, "injected pointer failure"):
                    _publish_latest(root, second, "attempt-two")

            self.assertEqual("json-one", (root / "latest.json").read_text())
            self.assertEqual("md-one", (root / "latest.md").read_text())

            _publish_latest(root, second, "attempt-two-retry")
            self.assertEqual("json-two", (root / "latest.json").read_text())
            self.assertEqual("md-two", (root / "latest.md").read_text())

    def test_real_limit_never_evicts_curated_signal_urls_for_snapshot_noise(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({
                "count": 2,
                "posts": [
                    {"url": "https://www.binance.com/en/square/post/990000000000110"},
                    {"url": "https://www.binance.com/en/square/post/990000000000111"},
                ],
                "new_posts": [],
                "scanned_at": "2026-07-31T05:00:00Z",
            }), encoding="utf-8")
            signals = root / "signals.json"
            signal_url = "https://www.binance.com/en/square/post/990000000000199"
            signals.write_text(json.dumps([{
                "url": signal_url, "symbol": "BTC", "direction": "long",
                "entry": "62000", "sl": "61000", "tp": "65000 / 67000",
            }]), encoding="utf-8")

            from scanner.pipeline import _load_legacy_signals, _real_discovery

            config = PipelineConfig(
                mode="real", output_dir=root / "runs", database=root / "radar.sqlite",
                input_snapshot=snapshot, signals_json=signals, limit=1,
            )
            discovered = _real_discovery(config, _load_legacy_signals(signals))

            self.assertEqual(
                (signal_url,),
                tuple(post.post_url for post in discovered.posts),
            )
            self.assertEqual(
                ("CURATED_SIGNAL",), discovered.posts[0].channels
            )

    def test_pipeline_and_cli_limit_default_covers_current_full_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = PipelineConfig(
                mode="fixture",
                output_dir=root / "runs",
                database=root / "radar.sqlite",
                fixture_dir=FIXTURE,
            )
            self.assertEqual(200, config.limit)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "scripts" / "run_radar.py"),
                    "--fixture",
                    str(FIXTURE),
                    "--clock",
                    "2026-07-31T05:48:36Z",
                    "--output-dir",
                    str(root / "cli-runs"),
                    "--database",
                    str(root / "cli.sqlite"),
                ],
                cwd=PROJECT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)

    def test_production_dedup_uses_only_prior_succeeded_slots(self) -> None:
        raw = {
            "schema_version": "4.1.0",
            "source_system": "fixture",
            "source_mode": "test-profile",
            "decision_at_utc": "2026-08-01T00:00:00Z",
            "counts": {
                "discovered_source_records": 1,
                "deduplicated_post_candidates": 1,
                "duplicate_source_records": 0,
                "accepted_observations": 1,
                "quarantined_source_records": 0,
                "dq_quarantined_source_records": 0,
                "window_excluded_source_records": 0,
            },
            "accepted": [{
                "post_id": "990000000000101",
                "post_url": "https://www.binance.com/en/square/post/990000000000101",
                "author_id": "opaque-author",
                "username": "author",
                "display_name": "Author",
                "profile_url": "https://www.binance.com/en/square/profile/author",
                "published_at": "2026-07-31T23:00:00Z",
                "published_precision": "exact_millisecond",
                "content": "market commentary without structured parameters",
                "content_hash": "a" * 64,
                "text_authority": "detail",
                "source_class": "SQUARE_UGC",
                "observed_at": "2026-07-31T23:01:00Z",
                "edit_count": 0,
            }],
            "discovery_observations": [{
                "post_id": "990000000000101",
                "canonical_post_url": (
                    "https://www.binance.com/en/square/post/990000000000101"
                ),
                "source_channel": "PROFILE",
                "source_record_ordinal": 0,
                "expected_author_id": "opaque-author",
                "expected_first_release_time_ms": 1785538800000,
                "source_profile_url": (
                    "https://www.binance.com/en/square/profile/author"
                ),
            }],
            "quarantine": [],
            "authors": [],
            "ranking_discovery_status": "BLOCKED",
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from scanner.contracts import ContractViolation

            with patch("scanner.pipeline._collect_live_urls", return_value=raw), patch(
                "scanner.pipeline.extract_signal",
                side_effect=ContractViolation("no structured signal"),
            ):
                first = run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at="2026-08-01T00:00:00Z",
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=catalog_only("2026-08-01T00:00:00Z"),  # type: ignore[arg-type]
                    clock=lambda: datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc),
                )
                second = run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at="2026-08-01T04:00:00Z",
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=catalog_only("2026-08-01T04:00:00Z"),  # type: ignore[arg-type]
                    clock=lambda: datetime(2026, 8, 1, 4, 0, 1, tzinfo=timezone.utc),
                )

            first_report = json.loads(first.report_json.read_text(encoding="utf-8"))
            second_report = json.loads(second.report_json.read_text(encoding="utf-8"))
            self.assertEqual("COMPUTED", first_report["post_counts"]["dedup_status"])
            self.assertEqual((1, 0), (
                first_report["post_counts"]["new"],
                first_report["post_counts"]["duplicate"],
            ))
            self.assertEqual((0, 1), (
                second_report["post_counts"]["new"],
                second_report["post_counts"]["duplicate"],
            ))

    def test_replay_computes_dedup_only_with_an_explicit_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                    dedup_baseline_post_ids=frozenset({"990000000000101"}),
                ),
                clock=lambda: datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
            )

            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual("COMPUTED", report["post_counts"]["dedup_status"])
            self.assertEqual(0, report["post_counts"]["new"])
            self.assertEqual(1, report["post_counts"]["duplicate"])

    def test_cli_accepts_an_explicit_replay_dedup_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "scripts" / "run_radar.py"),
                    "--fixture",
                    str(FIXTURE),
                    "--clock",
                    "2026-07-31T05:48:36Z",
                    "--dedup-baseline-post-id",
                    "990000000000101",
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
            report = json.loads(
                Path(receipt["report_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual("COMPUTED", report["post_counts"]["dedup_status"])
            self.assertEqual(1, report["post_counts"]["duplicate"])

    def test_latest_publication_observes_succeeded_attempt_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            observed_statuses: list[str] = []

            def publish_after_commit(
                output_dir: Path, run_dir: Path, attempt_id: str
            ) -> tuple[Path, Path, Path]:
                ledger = SQLiteRunLedger(database, MIGRATION)
                try:
                    observed_statuses.append(ledger.get_attempt(attempt_id).status)
                finally:
                    ledger.close()
                return (
                    output_dir / "latest.json",
                    output_dir / "latest.md",
                    output_dir / "latest",
                )

            with patch(
                "scanner.pipeline._publish_latest", side_effect=publish_after_commit
            ):
                run_shadow_radar(
                    PipelineConfig(
                        mode="fixture",
                        output_dir=root / "runs",
                        database=database,
                        decision_at="2026-07-31T05:48:36Z",
                        fixture_dir=FIXTURE,
                    ),
                    clock=lambda: datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
                )

            self.assertEqual(["SUCCEEDED"], observed_statuses)

    def test_failed_latest_publication_is_repaired_without_another_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            config = PipelineConfig(
                mode="fixture",
                output_dir=root / "runs",
                database=database,
                decision_at="2026-07-31T05:48:36Z",
                fixture_dir=FIXTURE,
            )
            with patch(
                "scanner.pipeline._publish_latest",
                side_effect=OSError("injected publish failure"),
            ):
                with self.assertRaisesRegex(OSError, "injected publish failure"):
                    run_shadow_radar(
                        config,
                        clock=lambda: datetime(
                            2026, 8, 1, 8, tzinfo=timezone.utc
                        ),
                    )

            ledger = SQLiteRunLedger(database, MIGRATION)
            logical_run = ledger.list_logical_runs()[0]
            attempts_before = ledger.list_attempts(logical_run.logical_run_id)
            ledger.close()
            self.assertEqual(1, len(attempts_before))
            self.assertEqual("SUCCEEDED", attempts_before[0].status)
            self.assertFalse((root / "runs" / "latest").exists())

            repaired = repair_latest_from_succeeded_attempt(
                config,
                logical_run_id=logical_run.logical_run_id,
            )

            self.assertEqual(
                repaired.report_json.read_bytes(), repaired.latest_json.read_bytes()
            )
            self.assertEqual(
                repaired.report_markdown.read_bytes(),
                repaired.latest_markdown.read_bytes(),
            )
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            attempts_after = ledger.list_attempts(logical_run.logical_run_id)
            self.assertEqual(attempts_before, attempts_after)

    def test_latest_repair_rejects_manifest_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = PipelineConfig(
                mode="fixture",
                output_dir=root / "runs",
                database=root / "radar.sqlite",
                decision_at="2026-07-31T05:48:36Z",
                fixture_dir=FIXTURE,
            )
            result = run_shadow_radar(
                config,
                clock=lambda: datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
            )
            result.report_json.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ContractViolation, "hash mismatch"):
                repair_latest_from_succeeded_attempt(
                    config,
                    logical_run_id=result.logical_run_id,
                )

    def test_latest_repair_cli_is_idempotent_and_creates_no_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            output_dir = root / "runs"
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=output_dir,
                    database=database,
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                ),
                clock=lambda: datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "scripts" / "repair_latest.py"),
                    "--logical-run-id",
                    result.logical_run_id,
                    "--output-dir",
                    str(output_dir),
                    "--database",
                    str(database),
                ],
                cwd=PROJECT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertTrue(receipt["repair_only"])
            self.assertTrue(receipt["no_send"])
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            self.assertEqual(
                1,
                len(ledger.list_attempts(result.logical_run_id)),
            )

    def test_real_mode_rejects_a_decision_cutoff_over_ten_minutes_late(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ContractViolation, r"within \+10 minutes"):
                run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at="2026-08-01T11:05:00Z",
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=SimpleNamespace(),  # type: ignore[arg-type]
                    clock=lambda: datetime(
                        2026, 8, 1, 11, 5, tzinfo=timezone.utc
                    ),
                )

    def test_real_mode_allows_the_single_plus_ten_minute_retry_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_shadow_radar(
                PipelineConfig(
                    mode="real",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at="2026-08-01T08:10:00Z",
                    input_snapshot=None,
                    signals_json=None,
                ),
                market_client=catalog_only("2026-08-01T08:10:00Z"),  # type: ignore[arg-type]
                clock=lambda: datetime(
                    2026, 8, 1, 8, 10, tzinfo=timezone.utc
                ),
            )

            raw = json.loads(result.raw_json.read_text(encoding="utf-8"))
            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            self.assertEqual(
                "2026-08-01T08:00:00Z",
                ledger.list_logical_runs()[0].scheduled_for_utc,
            )
            self.assertEqual("2026-08-01T08:10:00Z", raw["decision_at_utc"])
            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual(600, report["run_timing"]["decision_lag_seconds"])
            self.assertIn("延迟 600s / 上限 600s", result.report_markdown.read_text())

    def test_real_mode_rejects_a_historical_cutoff_as_a_live_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(
                ContractViolation,
                "captured at this attempt start",
            ):
                run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at="2026-08-01T08:00:00Z",
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=SimpleNamespace(),  # type: ignore[arg-type]
                    clock=lambda: datetime(
                        2026, 8, 1, 9, 0, tzinfo=timezone.utc
                    ),
                )

    def test_fetch_failure_is_durable_and_retry_reuses_frozen_decision(self) -> None:
        raw = {
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
            output_dir = root / "runs"
            output_dir.mkdir()
            (output_dir / "latest.json").write_bytes(b"previous-json")
            (output_dir / "latest.md").write_bytes(b"previous-markdown")
            first_config = PipelineConfig(
                mode="real",
                output_dir=output_dir,
                database=database,
                decision_at="2026-08-01T08:00:07Z",
                input_snapshot=None,
                signals_json=None,
            )
            with patch(
                "scanner.pipeline._collect_live_urls",
                side_effect=RuntimeError("injected fetch failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "injected fetch failure"):
                    run_shadow_radar(
                        first_config,
                        market_client=catalog_only("2026-08-01T08:00:07Z"),  # type: ignore[arg-type]
                        clock=lambda: datetime(
                            2026, 8, 1, 8, 0, 7, tzinfo=timezone.utc
                        ),
                    )

            ledger = SQLiteRunLedger(database, MIGRATION)
            logical_run = ledger.list_logical_runs()[0]
            first_attempt = ledger.list_attempts(logical_run.logical_run_id)[0]
            ledger.close()
            self.assertEqual("FAILED", first_attempt.status)
            self.assertEqual("fetch", first_attempt.failed_stage)
            self.assertEqual(b"previous-json", (output_dir / "latest.json").read_bytes())
            self.assertEqual(
                b"previous-markdown",
                (output_dir / "latest.md").read_bytes(),
            )

            with self.assertRaisesRegex(ContractViolation, "frozen cutoff"):
                run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=output_dir,
                        database=database,
                        decision_at="2026-08-01T08:05:00Z",
                        input_snapshot=None,
                        signals_json=None,
                        scheduled_retry=True,
                    ),
                    market_client=catalog_only("2026-08-01T08:10:07Z"),  # type: ignore[arg-type]
                    clock=lambda: datetime(
                        2026, 8, 1, 8, 10, 7, tzinfo=timezone.utc
                    ),
                )
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.assertEqual(
                1,
                len(ledger.list_attempts(logical_run.logical_run_id)),
            )
            ledger.close()

            with patch("scanner.pipeline._collect_live_urls", return_value=raw):
                recovered = run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=output_dir,
                        database=database,
                        decision_at="2026-08-01T08:00:07Z",
                        input_snapshot=None,
                        signals_json=None,
                        scheduled_retry=True,
                    ),
                    market_client=catalog_only("2026-08-01T08:10:07Z"),  # type: ignore[arg-type]
                    clock=lambda: datetime(
                        2026, 8, 1, 8, 10, 7, tzinfo=timezone.utc
                    ),
                )

            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            attempts = ledger.list_attempts(logical_run.logical_run_id)
            self.assertEqual([1, 2], [item.attempt_no for item in attempts])
            self.assertEqual(["FAILED", "SUCCEEDED"], [item.status for item in attempts])
            self.assertEqual(
                "2026-08-01T08:00:07Z",
                json.loads(recovered.raw_json.read_text())["decision_at_utc"],
            )

    def test_real_pipeline_rejects_missing_discovery_lineage(self) -> None:
        raw = {
            "schema_version": "4.1.0",
            "source_system": "test",
            "source_mode": "test-missing-lineage",
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
            "quarantine": [],
            "authors": [],
            "ranking_discovery_status": "BLOCKED",
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "scanner.pipeline._collect_live_urls", return_value=raw
        ):
            root = Path(directory)
            with self.assertRaisesRegex(
                ContractViolation,
                "discovery_observations",
            ):
                run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at="2026-08-01T08:00:07Z",
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=catalog_only("2026-08-01T08:00:07Z"),  # type: ignore[arg-type]
                    clock=lambda: datetime(
                        2026, 8, 1, 8, 0, 7, tzinfo=timezone.utc
                    ),
                )

    def test_binance_server_time_failure_is_a_durable_catalog_failure(self) -> None:
        class FailedCatalog:
            def fetch_futures_catalog(self) -> object:
                raise MarketApiError(FailureKind.UPSTREAM_UNAVAILABLE)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "radar.sqlite"
            with self.assertRaises(MarketApiError) as caught:
                run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=database,
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=FailedCatalog(),  # type: ignore[arg-type]
                    clock=lambda: datetime(
                        2026, 8, 1, 8, 0, 7, tzinfo=timezone.utc
                    ),
                )

            self.assertEqual(FailureKind.UPSTREAM_UNAVAILABLE, caught.exception.kind)
            ledger = SQLiteRunLedger(database, MIGRATION)
            self.addCleanup(ledger.close)
            logical_run = ledger.list_logical_runs()[0]
            attempt = ledger.list_attempts(logical_run.logical_run_id)[0]
            self.assertEqual("FAILED", attempt.status)
            self.assertEqual("market_catalog", attempt.failed_stage)
            self.assertFalse((root / "runs" / "latest").exists())

    def test_attempt_and_manifest_times_follow_artifact_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ticks = iter(
                (
                    datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc),
                    datetime(2026, 8, 1, 8, 1, 0, tzinfo=timezone.utc),
                    datetime(2026, 8, 1, 8, 2, 0, tzinfo=timezone.utc),
                    datetime(2026, 8, 1, 8, 3, 0, tzinfo=timezone.utc),
                )
            )
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at="2026-07-31T05:48:36Z",
                    fixture_dir=FIXTURE,
                ),
                clock=lambda: next(ticks),
            )

            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            attempt = ledger.list_attempts(result.logical_run_id)[0]
            manifests = ledger.list_manifests(result.logical_run_id)
            self.assertEqual("2026-08-01T08:00:00Z", attempt.started_at_utc)
            self.assertEqual("2026-08-01T08:03:00Z", attempt.finished_at_utc)
            self.assertTrue(all(
                item.created_at_utc == "2026-08-01T08:02:00Z"
                for item in manifests
            ))

    def test_real_pipeline_applies_rederivation_and_copy_safe_consensus(self) -> None:
        decision_at = "2026-08-01T08:00:00Z"
        raw = {
            "schema_version": "4.1.0",
            "source_system": "fixture",
            "source_mode": "test-profile-feed",
            "decision_at_utc": decision_at,
            "counts": {
                "discovered_source_records": 2,
                "deduplicated_post_candidates": 2,
                "duplicate_source_records": 0,
                "accepted_observations": 2,
                "quarantined_source_records": 0,
                "dq_quarantined_source_records": 0,
                "window_excluded_source_records": 0,
            },
            "accepted": [
                {
                    "post_id": str(9001 + index),
                    "post_url": (
                        "https://www.binance.com/en/square/post/"
                        f"{9001 + index}"
                    ),
                    "author_id": f"stable-author-{index}",
                    "username": f"author-{index}",
                    "display_name": f"Author {index}",
                    "profile_url": (
                        "https://www.binance.com/en/square/profile/"
                        f"author-{index}"
                    ),
                    "published_at": "2026-08-01T07:00:00Z",
                    "published_precision": "exact_millisecond",
                    "content": (
                        "BTCUSDT LONG\nBullish continuation structure "
                        f"variant {index}"
                    ),
                    "content_hash": str(index + 1) * 64,
                    "text_authority": "detail",
                    "source_class": "SQUARE_UGC",
                    "observed_at": "2026-08-01T07:01:00Z",
                    "edit_count": 0,
                }
                for index in range(2)
            ],
            "discovery_observations": [
                {
                    "post_id": str(9001 + index),
                    "canonical_post_url": (
                        "https://www.binance.com/en/square/post/"
                        f"{9001 + index}"
                    ),
                    "source_channel": "PROFILE" if index == 0 else "FEED",
                    "source_record_ordinal": index,
                    "expected_author_id": f"stable-author-{index}",
                    "expected_first_release_time_ms": 1785567600000,
                    "source_profile_url": (
                        "https://www.binance.com/en/square/profile/"
                        f"author-{index}"
                    ),
                }
                for index in range(2)
            ],
            "quarantine": [],
            "authors": [],
            "ranking_discovery_status": "BLOCKED",
        }

        class CompleteMarketSeam:
            def fetch_futures_catalog(self) -> SimpleNamespace:
                return SimpleNamespace(server_time_ms=1785571200000)

            def fetch_snapshot(
                self,
                symbol: str,
                *,
                catalog: object,
                decision_time_ms: int,
            ) -> object:
                self.assert_symbol = symbol
                self.assert_decision_time_ms = decision_time_ms
                return complete_market()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("scanner.pipeline._collect_live_urls", return_value=raw):
                result = run_shadow_radar(
                    PipelineConfig(
                        mode="real",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                        decision_at=decision_at,
                        input_snapshot=None,
                        signals_json=None,
                    ),
                    market_client=CompleteMarketSeam(),  # type: ignore[arg-type]
                    clock=lambda: datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
                )

            report = json.loads(result.report_json.read_text(encoding="utf-8"))
            self.assertEqual(2, len(report["candidate_audit"]))
            self.assertTrue(all(
                item["parameter_mapping"] == "SYSTEM_REDERIVED_V1"
                for item in report["candidate_audit"]
            ))
            self.assertTrue(all(
                item["derivation_disposition"] == "SYSTEM_REDERIVED"
                for item in report["candidate_audit"]
            ))
            self.assertEqual(
                [1, 1],
                sorted(
                    item["consensus_distinct_other_authors"]
                    for item in report["candidate_audit"]
                ),
            )
            self.assertEqual("SHADOW_ONLY", report["tracking"]["status"])
            self.assertEqual("PENDING_MARKET_REPLAY", report["tracking"]["evaluation_status"])
            self.assertEqual(1, report["tracking"]["persisted_revision_count"])
            self.assertEqual(1, report["tracking"]["pending_evaluation_count"])
            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATION)
            self.addCleanup(ledger.close)
            self.assertEqual(
                1,
                len(ledger.list_current_signal_revisions(as_of=decision_at)),
            )
            self.assertEqual(
                1,
                len(ledger.list_pending_signal_revisions(as_of=decision_at)),
            )


if __name__ == "__main__":
    unittest.main()
