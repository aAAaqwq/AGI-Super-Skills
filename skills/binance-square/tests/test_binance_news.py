from datetime import datetime, timezone
import unittest

from scanner.binance_news import collect_binance_official_news
from scanner.contracts import ContractViolation


class BinanceOfficialNewsTests(unittest.TestCase):
    def test_live_list_rows_without_dates_are_verified_through_article_detail(self) -> None:
        list_payload = {
            "code": "000000",
            "success": True,
            "data": {
                "total": 2,
                "articles": [
                    {"code": "new-item", "title": "New", "publishDate": None},
                    {"code": "old-item", "title": "Old", "publishDate": None},
                ],
            },
        }
        detail_dates = {
            "new-item": 1785567600000,
            "old-item": 1785484799000,
        }

        document = collect_binance_official_news(
            decision_at="2026-08-01T08:00:00Z",
            get_json=lambda page: list_payload,
            get_detail_json=lambda code: {
                "code": "000000",
                "success": True,
                "data": {
                    "code": code,
                    "title": code,
                    "publishDate": detail_dates[code],
                },
            },
            clock=lambda: datetime(2026, 8, 1, 8, 0, 5, tzinfo=timezone.utc),
        )

        self.assertEqual("COMPLETE", document["status"])
        self.assertEqual(["new-item"], [item["article_id"] for item in document["records"]])
        self.assertEqual(2, document["coverage"]["detail_requests"])
        self.assertTrue(document["coverage"]["exhaustive_until_window_start"])

    def test_schema_drift_does_not_masquerade_as_a_complete_empty_capture(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "missing"):
            collect_binance_official_news(
                decision_at="2026-08-01T08:00:00Z",
                get_json=lambda page: {"data": {"unexpected": []}},
            )

    def test_collector_keeps_only_official_items_in_strict_24h_window(self) -> None:
        payload = {
            "code": "000000",
            "success": True,
            "data": {
                "total": 3,
                "articles": [
                    {"code": "at-cutoff", "title": "Future boundary", "publishDate": 1785571200000},
                    {"code": "in-window", "title": "Listing update", "publishDate": 1785567600000},
                    {"code": "too-old", "title": "Old", "publishDate": 1785484799000},
                ],
            },
        }

        document = collect_binance_official_news(
            decision_at="2026-08-01T08:00:00Z",
            get_json=lambda page: payload,
            clock=lambda: datetime(2026, 8, 1, 8, 0, 5, tzinfo=timezone.utc),
        )

        self.assertEqual("COMPLETE", document["status"])
        self.assertEqual(1, document["record_count"])
        self.assertEqual("in-window", document["records"][0]["article_id"])
        self.assertEqual(
            "https://www.binance.com/en/support/announcement/detail/in-window",
            document["records"][0]["source_url"],
        )
        self.assertEqual("2026-08-01T07:00:00Z", document["records"][0]["published_at_utc"])
        self.assertEqual("2026-08-01T08:00:05Z", document["captured_at_utc"])
        self.assertEqual(3, document["coverage"]["returned_rows"])
        self.assertTrue(document["coverage"]["exhaustive_until_window_start"])


if __name__ == "__main__":
    unittest.main()
