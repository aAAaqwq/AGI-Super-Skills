import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import parse_qs, urlsplit

from scanner.contracts import ContractViolation
from scanner.smart_money import (
    EVIDENCE_SCHEMA_VERSION,
    PROFILE_ENDPOINT,
    RANK_SOURCE,
    SmartMoneyRequest,
    collect_smart_money,
    default_evidence_filename,
    verify_evidence_integrity,
    write_evidence_atomic,
)


FIXTURES = Path(__file__).parent / "fixtures" / "smart_money"


class FakeSmartMoneyApi:
    def __init__(self) -> None:
        self.page_template = json.loads(
            (FIXTURES / "page_template.json").read_text(encoding="utf-8")
        )
        self.profile_template = json.loads(
            (FIXTURES / "profile_template.json").read_text(encoding="utf-8")
        )
        self.responses: dict[tuple[str, str, int], dict[str, object]] = {}
        self.profile_failures: set[str] = set()
        self.profile_id_overrides: dict[str, str] = {}
        self.urls: list[str] = []
        for ranking_type in ("PNL", "ROI"):
            for page in (1, 2, 3):
                payload = copy.deepcopy(self.page_template)
                start = (page - 1) * 10 + 1
                payload["data"]["rows"] = [
                    {
                        "topTraderId": f"{ranking_type.lower()}-{rank:02d}",
                        "traderName": f"{ranking_type} Trader {rank:02d}",
                        "accountName": f"Account {rank:02d}",
                        "subscribers": 1000 - rank,
                        "roi": rank / 100,
                        "pnl": 100000 - rank,
                    }
                    for rank in range(start, start + 10)
                ]
                self.responses[(ranking_type, "30D", page)] = payload

    def __call__(self, url: str, timeout: float) -> dict[str, object]:
        self.urls.append(url)
        self.test_case.assertGreater(timeout, 0)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.path == urlsplit(PROFILE_ENDPOINT).path:
            source_id = query["topTraderId"][0]
            if source_id in self.profile_failures:
                raise OSError("fixture profile unavailable")
            payload = copy.deepcopy(self.profile_template)
            payload["data"]["topTraderId"] = self.profile_id_overrides.get(
                source_id, source_id
            )
            payload["data"]["traderName"] = f"Profile {source_id}"
            return payload
        key = (
            query["rankingType"][0],
            query["timeRange"][0],
            int(query["page"][0]),
        )
        self.test_case.assertEqual(["DESC"], query["order"])
        self.test_case.assertEqual(["10"], query["rows"])
        self.test_case.assertEqual(["false"], query["onlyShowSharingPosition"])
        self.test_case.assertEqual(["false"], query["onlyShowSignalEnabled"])
        return copy.deepcopy(self.responses[key])


class SmartMoneyCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeSmartMoneyApi()
        self.api.test_case = self

    def test_pnl_and_roi_three_pages_become_strict_top30(self) -> None:
        document = collect_smart_money(
            get_json=self.api,
            captured_at="2026-08-01T12:00:00Z",
        )

        self.assertEqual(EVIDENCE_SCHEMA_VERSION, document["evidence_schema_version"])
        self.assertEqual("COMPLETE", document["status"])
        self.assertTrue(verify_evidence_integrity(document))
        self.assertEqual(60, document["unique_top_trader_count"])
        self.assertEqual(60, document["profile_enrichment"]["completed"])
        self.assertEqual(66, len(self.api.urls))
        self.assertEqual("OBSERVED_WINDOW", document["snapshot_semantics"])
        self.assertEqual(
            "OBSERVED_WINDOW",
            document["leaderboard_observed_window"]["snapshot_semantics"],
        )
        self.assertEqual(
            {
                "onlyShowSharingPosition": "false",
                "onlyShowSignalEnabled": "false",
            },
            document["contract"]["fixed_filters"],
        )
        for ranking in document["rankings"]:
            self.assertEqual("COMPLETE", ranking["status"])
            self.assertEqual(30, len(ranking["rows"]))
            self.assertEqual(
                list(range(1, 31)), [row["rank"] for row in ranking["rows"]]
            )
            self.assertTrue(
                all(row["rank_source"] == RANK_SOURCE for row in ranking["rows"])
            )
            self.assertEqual("OBSERVED_WINDOW", ranking["snapshot_semantics"])
            for page in ranking["pages"]:
                self.assertIn("request_started_at_utc", page)
                self.assertIn("response_received_at_utc", page)
            self.assertTrue(
                all(
                    row["source_id"] == row["source_row"]["topTraderId"]
                    for row in ranking["rows"]
                )
            )

    def test_fixture_replay_provenance_is_integrity_protected(self) -> None:
        document = collect_smart_money(
            ranking_types=("PNL",),
            include_profiles=False,
            get_json=self.api,
            captured_at="2026-08-01T12:00:00Z",
            provenance="FIXTURE_REPLAY",
        )

        self.assertEqual("FIXTURE_REPLAY", document["provenance"])
        self.assertTrue(verify_evidence_integrity(document))
        document["provenance"] = "LIVE_CAPTURE"
        self.assertFalse(verify_evidence_integrity(document))

    def test_cross_ranking_duplicate_ids_fetch_one_profile_each(self) -> None:
        for page in (1, 2, 3):
            pnl_rows = self.api.responses[("PNL", "30D", page)]["data"]["rows"]
            roi_rows = self.api.responses[("ROI", "30D", page)]["data"]["rows"]
            for pnl, roi in zip(pnl_rows, roi_rows):
                roi["topTraderId"] = pnl["topTraderId"]

        document = collect_smart_money(get_json=self.api)

        self.assertEqual(30, document["unique_top_trader_count"])
        self.assertEqual(30, document["profile_enrichment"]["completed"])
        self.assertEqual(36, len(self.api.urls))

    def test_api_error_is_rejected(self) -> None:
        self.api.responses[("PNL", "30D", 2)]["success"] = False
        self.api.responses[("PNL", "30D", 2)]["code"] = "100001"

        with self.assertRaisesRegex(ContractViolation, "API failed"):
            collect_smart_money(
                ranking_types=("PNL",),
                include_profiles=False,
                get_json=self.api,
            )

    def test_short_or_missing_page_is_rejected(self) -> None:
        self.api.responses[("PNL", "30D", 2)]["data"]["rows"].pop()

        with self.assertRaisesRegex(ContractViolation, "exactly 10"):
            collect_smart_money(
                ranking_types=("PNL",),
                include_profiles=False,
                get_json=self.api,
            )

    def test_duplicate_id_across_pages_is_rejected(self) -> None:
        first = self.api.responses[("PNL", "30D", 1)]["data"]["rows"][0]
        last = self.api.responses[("PNL", "30D", 3)]["data"]["rows"][-1]
        last["topTraderId"] = first["topTraderId"]

        with self.assertRaisesRegex(ContractViolation, "duplicate topTraderId"):
            collect_smart_money(
                ranking_types=("PNL",),
                include_profiles=False,
                get_json=self.api,
            )

    def test_last_update_time_drift_between_pages_is_rejected(self) -> None:
        self.api.responses[("PNL", "30D", 3)]["data"]["lastUpdateTime"] += 1

        with self.assertRaisesRegex(ContractViolation, "lastUpdateTime changed"):
            collect_smart_money(
                ranking_types=("PNL",),
                include_profiles=False,
                get_json=self.api,
            )

    def test_last_update_time_drift_between_rankings_is_rejected(self) -> None:
        for page in (1, 2, 3):
            self.api.responses[("ROI", "30D", page)]["data"][
                "lastUpdateTime"
            ] += 1

        with self.assertRaisesRegex(ContractViolation, "requested rankings"):
            collect_smart_money(include_profiles=False, get_json=self.api)

    def test_only_pnl_and_roi_are_valid_and_rows_30_is_invalid(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "PNL or ROI"):
            SmartMoneyRequest("VOLUME")
        with self.assertRaisesRegex(ContractViolation, "rows=30"):
            SmartMoneyRequest("PNL", rows=30)
        with self.assertRaisesRegex(ContractViolation, "rows=30"):
            collect_smart_money(
                ranking_types=("PNL",), rows_per_page=30, get_json=self.api
            )

    def test_profile_id_mismatch_is_explicit_partial_failure(self) -> None:
        self.api.profile_id_overrides["pnl-01"] = "different-id"

        document = collect_smart_money(
            ranking_types=("PNL",), get_json=self.api
        )

        coverage = document["profile_enrichment"]
        self.assertEqual("PARTIAL_PROFILE_ENRICHMENT", document["status"])
        self.assertEqual("PARTIAL", coverage["status"])
        self.assertEqual(30, coverage["expected"])
        self.assertEqual(29, coverage["completed"])
        self.assertEqual(1, coverage["failed"])
        self.assertIn("does not match", coverage["failures"][0]["reason"])

    def test_partial_profile_transport_failure_is_not_hidden(self) -> None:
        self.api.profile_failures.update({"roi-02", "roi-17"})

        document = collect_smart_money(
            ranking_types=("ROI",), get_json=self.api
        )

        coverage = document["profile_enrichment"]
        self.assertEqual("PARTIAL", coverage["status"])
        self.assertEqual(28, coverage["completed"])
        self.assertEqual(2, coverage["failed"])
        self.assertAlmostEqual(28 / 30, coverage["coverage_ratio"])
        self.assertEqual(
            {"roi-02", "roi-17"},
            {failure["source_id"] for failure in coverage["failures"]},
        )

    def test_profile_enrichment_can_be_explicitly_disabled(self) -> None:
        document = collect_smart_money(
            ranking_types=("PNL",),
            include_profiles=False,
            get_json=self.api,
        )

        coverage = document["profile_enrichment"]
        self.assertEqual("NOT_REQUESTED", coverage["status"])
        self.assertEqual(30, coverage["expected"])
        self.assertEqual(0, coverage["completed"])
        self.assertEqual(3, len(self.api.urls))

    def test_atomic_evidence_is_immutable_and_integrity_is_verifiable(self) -> None:
        document = collect_smart_money(
            ranking_types=("PNL",),
            include_profiles=False,
            get_json=self.api,
            captured_at="2026-08-01T12:00:00Z",
        )
        with TemporaryDirectory() as directory:
            output = Path(directory) / default_evidence_filename(document)
            receipt = write_evidence_atomic(document, output)
            saved = json.loads(output.read_text(encoding="utf-8"))

            self.assertTrue(verify_evidence_integrity(saved))
            self.assertEqual(receipt.payload_sha256, saved["integrity"]["payload_sha256"])
            self.assertEqual(64, len(receipt.file_sha256))
            with self.assertRaisesRegex(ContractViolation, "already exists"):
                write_evidence_atomic(document, output)

            saved["rankings"][0]["rows"][0]["rank"] = 99
            self.assertFalse(verify_evidence_integrity(saved))

    def test_request_clock_cannot_move_backwards(self) -> None:
        moments = iter(
            (
                datetime(2026, 8, 1, 12, 0, 10, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 12, 0, 9, tzinfo=timezone.utc),
            )
        )
        with self.assertRaisesRegex(ContractViolation, "cannot move backwards"):
            collect_smart_money(
                ranking_types=("PNL",),
                include_profiles=False,
                get_json=self.api,
                clock=lambda: next(moments),
            )

    def test_captured_at_cannot_precede_observed_window(self) -> None:
        current = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

        def advancing_clock() -> datetime:
            nonlocal current
            current += timedelta(seconds=1)
            return current

        with self.assertRaisesRegex(ContractViolation, "cannot precede"):
            collect_smart_money(
                ranking_types=("PNL",),
                include_profiles=False,
                get_json=self.api,
                captured_at="2026-08-01T12:00:00Z",
                clock=advancing_clock,
            )


if __name__ == "__main__":
    unittest.main()
