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
from scanner.market import FailureKind, MarketApiError, MarketSource
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
                "scanned_at": "2026-07-31T04:00:00Z",
            }), encoding="utf-8")
            signals = root / "signals.json"
            signals.write_text(json.dumps([{
                "url": signal_url, "symbol": "BTC", "direction": "long",
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
                    return SimpleNamespace(server_time_ms=1785484800000)

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
                    signals_json=signals, limit=2,
                ),
                detail_fetcher=fetch_detail,
                market_client=market,  # type: ignore[arg-type]
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

    def test_real_failure_marks_attempt_failed_without_replacing_latest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_url = "https://www.binance.com/en/square/post/990000000000101"
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({
                "count": 1,
                "posts": [{"url": snapshot_url}],
                "new_posts": [],
                "scanned_at": "2026-07-31T04:00:00Z",
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

            self.assertEqual((signal_url,), discovered)

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
