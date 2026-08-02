from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scanner.authors import load_smart_money_square_identity_evidence
from scanner.profile_pipeline import public_get_profile_contents, run_profile_pipeline


class ProfilePipelineTests(unittest.TestCase):
    def _mapping(self, directory: str, *, provenance: str = "FIXTURE_REPLAY"):
        mapping_path = Path(directory) / "mapping.json"
        mapping_path.write_text(
            json.dumps(
                {
                    "schema": "binance-smart-money-square-identity-mapping/v1",
                    "captured_at_utc": "2026-08-01T12:06:00Z",
                    "provenance": provenance,
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
        return load_smart_money_square_identity_evidence(mapping_path)

    @staticmethod
    def _item(post_id: int, published: datetime) -> dict[str, object]:
        return {
            "id": str(post_id),
            "contentType": "POST",
            "squareUid": "fixture-square-01",
            "firstReleaseTime": int(published.timestamp() * 1000),
        }

    @staticmethod
    def _page(
        items: list[dict[str, object]], next_offset: int | None
    ) -> dict[str, object]:
        return {
            "success": True,
            "data": {"contents": items, "nextTimeOffset": next_offset},
        }

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
        self.assertEqual("BLOCKED_IDENTITY_MAPPING", result.reason)
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

    def test_inactive_identity_evidence_never_fetches_or_exports_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            live_v1 = self._mapping(directory, provenance="LIVE_CAPTURE")
            inactive = (
                live_v1,
                replace(
                    live_v1,
                    schema="binance-smart-money-square-identity-mapping/v2",
                    provenance="FIXTURE_REPLAY",
                    promotion_status="PROPOSED",
                ),
                replace(
                    live_v1,
                    schema="binance-smart-money-square-identity-mapping/v2",
                    promotion_status="REVOKED",
                ),
                replace(
                    live_v1,
                    schema="binance-smart-money-square-identity-mapping/v2",
                    promotion_status="CONFLICT",
                ),
            )
            for evidence in inactive:
                with self.subTest(
                    schema=evidence.schema,
                    provenance=evidence.provenance,
                    promotion_status=evidence.promotion_status,
                ):
                    requested: list[str] = []
                    result = run_profile_pipeline(
                        ("fixture-trader-01",),
                        mapping_evidence=evidence,
                        fetch_profile_contents=lambda square_uid: requested.append(
                            square_uid
                        ) or {"success": True, "data": {"contents": []}},
                        source_capture_time_utc="2026-08-01T12:07:00Z",
                        provenance=evidence.provenance,
                    )

                    self.assertEqual([], requested)
                    self.assertEqual("NOT_ATTEMPTED", result.status)
                    self.assertEqual("BLOCKED_IDENTITY_MAPPING", result.reason)
                    self.assertEqual(0, result.mapping_covered)
                    self.assertEqual((), result.identity_mappings)
                    self.assertEqual((), result.identity_mapping_records())

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

            def failed_fetch(square_uid: str) -> dict[str, object]:
                raise OSError(f"fixture failure for {square_uid}")

            result = run_profile_pipeline(
                ("fixture-trader-01", "fixture-trader-02"),
                mapping_evidence=mapping,
                fetch_profile_contents=failed_fetch,
                source_capture_time_utc="2026-08-01T12:07:00Z",
                provenance="FIXTURE_REPLAY",
            )

        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(("FAILED", "NOT_ATTEMPTED"), tuple(x.status for x in result.outcomes))
        self.assertEqual(0, result.tier_a_eligible)
        self.assertEqual("FIXTURE_REPLAY", result.as_report_contract()["provenance"])

    def test_public_get_is_anonymous_and_uses_exact_profile_endpoint(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"success":true,"data":{"contents":[],"nextTimeOffset":null}}'

        captured = []

        class Opener:
            def open(self, request, *, timeout):
                return open_request(request, timeout=timeout)

        def open_request(request, *, timeout):
            captured.append((request, timeout))
            return Response()

        with patch(
            "scanner.profile_pipeline.urllib.request.build_opener",
            return_value=Opener(),
        ) as build_opener:
            public_get_profile_contents("fixture-square-01", -1)

        build_opener.assert_called_once_with()
        request, timeout = captured[0]
        self.assertEqual("GET", request.get_method())
        self.assertEqual(15, timeout)
        self.assertEqual(
            "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/"
            "queryUserProfilePageContentsWithFilter?targetSquareUid="
            "fixture-square-01&timeOffset=-1&filterType=ALL",
            request.full_url,
        )
        forbidden = {"authorization", "cookie", "x-token", "token"}
        self.assertFalse(forbidden.intersection(key.lower() for key in request.headers))

    def test_profile_pages_20_then_4_then_empty_null_are_complete(self) -> None:
        decision = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
        items = [
            self._item(9000 + index, decision - timedelta(minutes=index + 1))
            for index in range(24)
        ]
        first_offset = items[19]["firstReleaseTime"] - 1
        second_offset = items[-1]["firstReleaseTime"] - 1
        pages = {
            -1: self._page(items[:20], first_offset),
            first_offset: self._page(items[20:], second_offset),
            second_offset: self._page([], None),
        }
        requested: list[tuple[str, int]] = []

        with tempfile.TemporaryDirectory() as directory:
            mapping = self._mapping(directory)

            def fetch(uid: str, offset: int) -> dict[str, object]:
                requested.append((uid, offset))
                return pages[offset]

            result = run_profile_pipeline(
                ("fixture-trader-01",),
                mapping_evidence=mapping,
                fetch_profile_contents=fetch,
                source_capture_time_utc="2026-08-01T12:07:00Z",
                provenance="FIXTURE_REPLAY",
                decision_at=decision,
                max_pages=5,
            )

        self.assertEqual(
            [
                ("fixture-square-01", -1),
                ("fixture-square-01", first_offset),
                ("fixture-square-01", second_offset),
            ],
            requested,
        )
        self.assertEqual("COMPLETE", result.status)
        self.assertEqual(24, len(result.observations))
        self.assertEqual("EMPTY_PAGE", result.outcomes[0].termination_reason)
        self.assertEqual(3, result.outcomes[0].pages_fetched)

    def test_first_release_time_controls_left_closed_right_open_window(self) -> None:
        decision = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
        start = decision - timedelta(hours=24)
        page = self._page(
            [
                self._item(9100, decision),
                self._item(9101, decision - timedelta(seconds=1)),
                self._item(9102, start),
                self._item(9103, start - timedelta(milliseconds=1)),
            ],
            int((start - timedelta(milliseconds=1)).timestamp() * 1000) - 1,
        )
        with tempfile.TemporaryDirectory() as directory:
            result = run_profile_pipeline(
                ("fixture-trader-01",),
                mapping_evidence=self._mapping(directory),
                fetch_profile_contents=lambda _uid, _offset: page,
                source_capture_time_utc="2026-08-01T12:07:00Z",
                provenance="FIXTURE_REPLAY",
                decision_at=decision,
            )

        self.assertEqual(("9101", "9102"), tuple(x.post_id for x in result.observations))
        self.assertEqual("WINDOW_START_CROSSED", result.outcomes[0].termination_reason)

    def test_pinned_old_records_do_not_hide_newer_window_posts_or_stop_pagination(self) -> None:
        decision = datetime(2026, 8, 2, 6, 32, 57, tzinfo=timezone.utc)
        start = decision - timedelta(hours=24)
        first_page = [
            self._item(9300, start - timedelta(days=2)),  # pinned old post
            self._item(9301, decision - timedelta(minutes=5)),
            self._item(9302, decision - timedelta(hours=3)),
            self._item(9303, decision - timedelta(hours=12)),
        ]
        first_offset = first_page[-1]["firstReleaseTime"] - 1
        second_page = [
            self._item(9304, decision - timedelta(hours=18)),
            self._item(9305, start),
            self._item(9306, start - timedelta(milliseconds=1)),
        ]
        second_offset = second_page[-1]["firstReleaseTime"] - 1
        pages = {
            -1: self._page(first_page, first_offset),
            first_offset: self._page(second_page, second_offset),
        }
        requested: list[int] = []

        with tempfile.TemporaryDirectory() as directory:
            result = run_profile_pipeline(
                ("fixture-trader-01",),
                mapping_evidence=self._mapping(directory),
                fetch_profile_contents=lambda _uid, offset: requested.append(offset)
                or pages[offset],
                source_capture_time_utc="2026-08-02T06:33:00Z",
                provenance="FIXTURE_REPLAY",
                decision_at=decision,
            )

        self.assertEqual([-1, first_offset], requested)
        self.assertEqual(("9301", "9302", "9303", "9304", "9305"), tuple(
            item.post_id for item in result.observations
        ))
        self.assertEqual("COMPLETE", result.status)
        self.assertEqual("WINDOW_START_CROSSED", result.outcomes[0].termination_reason)

    def test_cursor_anchor_mismatch_and_missing_tail_watermark_are_partial(self) -> None:
        decision = datetime(2026, 8, 2, 6, 32, 57, tzinfo=timezone.utc)
        item = self._item(9400, decision - timedelta(minutes=1))
        missing_watermark = dict(item)
        del missing_watermark["firstReleaseTime"]
        scenarios = (
            (self._page([item], item["firstReleaseTime"] - 2), "CURSOR_ANCHOR_MISMATCH"),
            (self._page([missing_watermark], 1000), "CURSOR_WATERMARK_MISSING"),
            (self._page([], 1000), "CURSOR_WATERMARK_MISSING"),
        )
        for page, reason in scenarios:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                result = run_profile_pipeline(
                    ("fixture-trader-01",),
                    mapping_evidence=self._mapping(directory),
                    fetch_profile_contents=lambda _uid, _offset: page,
                    source_capture_time_utc="2026-08-02T06:33:00Z",
                    provenance="FIXTURE_REPLAY",
                    decision_at=decision,
                )
                self.assertEqual("PARTIAL", result.status)
                self.assertEqual(reason, result.outcomes[0].termination_reason)

    def test_offset_stagnation_rise_schema_drift_failure_and_page_budget_are_partial(self) -> None:
        decision = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
        one = [self._item(9200, decision - timedelta(minutes=1))]
        first_offset = one[-1]["firstReleaseTime"] - 1
        rising = [self._item(9201, decision - timedelta(seconds=30))]
        rising_offset = rising[-1]["firstReleaseTime"] - 1

        scenarios = {
            "stagnant": ({-1: self._page(one, first_offset), first_offset: self._page(one, first_offset)}, 5, "OFFSET_STAGNANT"),
            "rising": ({-1: self._page(one, first_offset), first_offset: self._page(rising, rising_offset)}, 5, "OFFSET_RISING"),
            "schema": ({-1: {"success": True, "data": {"nextTimeOffset": None}}}, 5, "SCHEMA_DRIFT"),
            "budget": ({-1: self._page(one, first_offset)}, 1, "MAX_PAGES"),
        }
        for label, (pages, max_pages, reason) in scenarios.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                result = run_profile_pipeline(
                    ("fixture-trader-01",),
                    mapping_evidence=self._mapping(directory),
                    fetch_profile_contents=lambda _uid, offset: pages[offset],
                    source_capture_time_utc="2026-08-01T12:07:00Z",
                    provenance="FIXTURE_REPLAY",
                    decision_at=decision,
                    max_pages=max_pages,
                )
                self.assertEqual("PARTIAL", result.status)
                self.assertEqual(reason, result.outcomes[0].termination_reason)

        with tempfile.TemporaryDirectory() as directory:
            result = run_profile_pipeline(
                ("fixture-trader-01",),
                mapping_evidence=self._mapping(directory),
                fetch_profile_contents=lambda _uid, _offset: (_ for _ in ()).throw(OSError("offline")),
                source_capture_time_utc="2026-08-01T12:07:00Z",
                provenance="FIXTURE_REPLAY",
                decision_at=decision,
            )
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual("REQUEST_FAILED", result.outcomes[0].termination_reason)


if __name__ == "__main__":
    unittest.main()
