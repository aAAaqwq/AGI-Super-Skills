from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scanner.authors import load_smart_money_square_identity_evidence
from scanner.profile_pipeline import run_profile_pipeline


class ProfilePipelineTests(unittest.TestCase):
    def test_missing_identity_evidence_is_zero_coverage_and_never_fetches(self) -> None:
        def forbidden_fetch(square_uid: str) -> dict[str, object]:
            self.fail(f"unmapped identity must not be fetched: {square_uid}")

        result = run_profile_pipeline(
            ("fixture-trader-01", "fixture-trader-02"),
            mapping_evidence=None,
            fetch_profile_contents=forbidden_fetch,
            source_capture_time_utc="2026-08-01T12:07:00Z",
            provenance="FIXTURE_REPLAY",
        )

        self.assertEqual("NOT_ATTEMPTED", result.status)
        self.assertEqual(0, result.mapping_covered)
        self.assertEqual(2, result.mapping_expected)
        self.assertEqual(0, result.tier_a_eligible)
        self.assertTrue(all(item.square_uid is None for item in result.outcomes))
        self.assertTrue(all(item.status == "NOT_ATTEMPTED" for item in result.outcomes))
        contract = result.as_report_contract()
        self.assertEqual(
            "0/2",
            contract["square_identity_mapping_coverage"]["label"],
        )
        self.assertEqual("FIXTURE_REPLAY", contract["provenance"])

    def test_explicit_mapping_fetches_by_square_uid_and_reconciles_posts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mapping_path = Path(directory) / "mapping.json"
            mapping_path.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "captured_at_utc": "2026-08-01T12:06:00Z",
                        "provenance": "FIXTURE_REPLAY",
                        "mappings": [
                            {
                                "topTraderId": "fixture-trader-01",
                                "squareUid": "fixture-square-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            mapping = load_smart_money_square_identity_evidence(mapping_path)
            requested: list[str] = []

            def fetch(square_uid: str) -> dict[str, object]:
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

            result = run_profile_pipeline(
                ("fixture-trader-01",),
                mapping_evidence=mapping,
                fetch_profile_contents=fetch,
                source_capture_time_utc="2026-08-01T12:07:00Z",
                provenance="FIXTURE_REPLAY",
            )

        self.assertEqual(["fixture-square-01"], requested)
        self.assertEqual("COMPLETE", result.status)
        self.assertEqual(1, result.mapping_covered)
        self.assertEqual("COMPLETE", result.outcomes[0].status)
        self.assertEqual("fixture-square-01", result.observations[0].author_id)
        self.assertEqual("2026-08-01T12:07:00Z", result.source_capture_time_utc)
        self.assertEqual(
            {
                "top_trader_id": "fixture-trader-01",
                "author_id": "fixture-square-01",
                "verified_at": "2026-08-01T12:06:00Z",
                "evidence_path": str(mapping_path),
                "evidence_sha256": mapping.evidence_sha256,
            },
            result.identity_mapping_records()[0],
        )

    def test_partial_mapping_and_fetch_failure_never_promote_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mapping_path = Path(directory) / "mapping.json"
            mapping_path.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "captured_at_utc": "2026-08-01T12:06:00Z",
                        "provenance": "LIVE_CAPTURE",
                        "mappings": [
                            {
                                "topTraderId": "fixture-trader-01",
                                "squareUid": "fixture-square-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            mapping = load_smart_money_square_identity_evidence(mapping_path)

            def failed_fetch(square_uid: str) -> dict[str, object]:
                raise OSError(f"fixture failure for {square_uid}")

            result = run_profile_pipeline(
                ("fixture-trader-01", "fixture-trader-02"),
                mapping_evidence=mapping,
                fetch_profile_contents=failed_fetch,
                source_capture_time_utc="2026-08-01T12:07:00Z",
                provenance="LIVE_CAPTURE",
            )

        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(("FAILED", "NOT_ATTEMPTED"), tuple(x.status for x in result.outcomes))
        self.assertEqual(0, result.tier_a_eligible)
        self.assertEqual("LIVE_CAPTURE", result.as_report_contract()["provenance"])


if __name__ == "__main__":
    unittest.main()
