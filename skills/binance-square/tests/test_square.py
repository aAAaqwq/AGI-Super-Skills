import json
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scanner.square import (
    discover_snapshot_post_urls,
    parse_feed_cards,
    parse_post_detail,
    parse_post_json_ld,
    select_strict_24h,
    try_parse_post_detail,
)


FIXTURES = Path(__file__).parent / "fixtures" / "m1b"


class SquareFeedTests(unittest.TestCase):
    def test_feed_fixture_keeps_live_as_a_label_not_the_author(self) -> None:
        payload = json.loads(
            (FIXTURES / "feed_cards_live.json").read_text(encoding="utf-8")
        )

        cards = parse_feed_cards(payload)

        self.assertEqual(3, len(cards))
        live_card = cards[0]
        self.assertEqual("990000000000201", live_card.post_id)
        self.assertEqual("Fixture Feed Author 1", live_card.author_name)
        self.assertNotEqual("LIVE", live_card.author_name.upper())
        self.assertEqual(("LIVE",), live_card.visible_labels)
        self.assertEqual("feed_card_summary", live_card.text_authority)
        self.assertIsNone(live_card.published_at)


class SquarePostDetailTests(unittest.TestCase):
    def test_json_ld_detail_exposes_exact_time_and_full_structured_text(self) -> None:
        html = (FIXTURES / "post_detail_live.html").read_text(encoding="utf-8")

        structured = parse_post_json_ld(html)

        self.assertEqual("990000000000101", structured.post_id)
        self.assertEqual("2026-07-30T05:48:36Z", structured.published_at)
        self.assertIn("TP3: 0.0205", structured.content)
        self.assertEqual("Fixture Analyst", structured.author_name)
        self.assertEqual("fixturetrader", structured.profile_slug)
        self.assertEqual("json_ld_text", structured.text_authority)

    def test_public_detail_supplies_stable_author_time_and_authoritative_body(self) -> None:
        public_payload = json.loads(
            (FIXTURES / "post_detail_public.json").read_text(encoding="utf-8")
        )
        html = (FIXTURES / "post_detail_live.html").read_text(encoding="utf-8")

        post = parse_post_detail(
            public_payload=public_payload,
            html=html,
            observed_at="2026-08-01T07:03:00Z",
        )

        expected_body = public_payload["response"]["data"]["bodyTextOnly"]
        self.assertEqual("990000000000101", post.post_id)
        self.assertEqual("synthetic-square-uid-profile", post.author_id)
        self.assertEqual("FixtureTrader", post.username)
        self.assertEqual("Fixture Analyst", post.display_name)
        self.assertEqual("2026-07-30T05:48:36Z", post.published_at)
        self.assertEqual(expected_body, post.content)
        self.assertEqual("friendly_body_text_only", post.text_authority)
        self.assertEqual(
            sha256(expected_body.encode("utf-8")).hexdigest(), post.content_hash
        )
        self.assertEqual("SQUARE_UGC", post.source_class)

    def test_strict_24h_is_left_closed_and_quarantines_the_decision_boundary(self) -> None:
        public_payload = json.loads(
            (FIXTURES / "post_detail_public.json").read_text(encoding="utf-8")
        )
        base = parse_post_detail(
            public_payload=public_payload,
            observed_at="2026-07-31T05:48:36Z",
        )
        at_start = replace(base, published_at="2026-07-30T05:48:36Z")
        at_end = replace(
            base,
            post_id="990000000000102",
            post_url="https://www.binance.com/en/square/post/990000000000102",
            published_at="2026-07-31T05:48:36Z",
        )

        result = select_strict_24h(
            (at_start, at_end), decision_at="2026-07-31T05:48:36Z"
        )

        self.assertEqual((at_start,), result.accepted)
        self.assertEqual(1, len(result.quarantined))
        self.assertEqual("not_before_decision_at", result.quarantined[0].reason)
        self.assertEqual(at_end.published_at, result.quarantined[0].published_at)
        self.assertEqual(at_end.observed_at, result.quarantined[0].observed_at)
        self.assertEqual(at_end.author_id, result.quarantined[0].author_id)
        self.assertEqual(at_end.content_hash, result.quarantined[0].content_hash)

    def test_missing_stable_author_id_is_quarantined_with_a_reason(self) -> None:
        payload = json.loads(
            (FIXTURES / "post_detail_public.json").read_text(encoding="utf-8")
        )
        missing_author = deepcopy(payload)
        del missing_author["response"]["data"]["squareUid"]

        result = try_parse_post_detail(
            post_url="https://www.binance.com/en/square/post/990000000000101",
            public_payload=missing_author,
            observed_at="2026-08-01T07:03:00Z",
        )

        self.assertIsNone(result.post)
        self.assertIsNotNone(result.quarantine)
        self.assertEqual("missing_stable_author_id", result.quarantine.reason)


class SquareCollectorTests(unittest.TestCase):
    def test_v3_snapshot_is_a_bounded_discovery_source(self) -> None:
        project = Path(__file__).parents[1]

        urls = discover_snapshot_post_urls(
            project / "tests" / "fixtures" / "history" / "v3_snapshot_01.json",
            limit=2,
        )

        self.assertEqual(2, len(urls))
        self.assertTrue(
            all(url.startswith("https://www.binance.com/en/square/post/") for url in urls)
        )
        self.assertNotEqual(urls[0], urls[1])

    def test_fixture_cli_writes_reconciled_strict_24h_output(self) -> None:
        project = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixture-result.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(project / "scripts" / "collect_square_v4.py"),
                    "--fixture",
                    str(FIXTURES),
                    "--clock",
                    "2026-07-31T05:48:36Z",
                    "--limit",
                    "5",
                    "--output",
                    str(output),
                ],
                cwd=project,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(4, payload["counts"]["discovered_source_records"])
            self.assertEqual(1, payload["counts"]["accepted_observations"])
            self.assertEqual(3, payload["counts"]["quarantined_source_records"])
            self.assertEqual(3, payload["counts"]["dq_quarantined_source_records"])
            self.assertEqual(0, payload["counts"]["window_excluded_source_records"])
            self.assertEqual(
                payload["counts"]["discovered_source_records"],
                payload["counts"]["accepted_observations"]
                + payload["counts"]["quarantined_source_records"],
            )
            self.assertEqual(
                "synthetic-square-uid-profile", payload["accepted"][0]["author_id"]
            )
            self.assertEqual(
                "synthetic-square-uid-profile", payload["authors"][0]["author_id"]
            )
            self.assertTrue(
                all(item["reason"] for item in payload["quarantine"])
            )

    def test_fixture_collector_reconciles_profile_and_feed_source_records(self) -> None:
        project = Path(__file__).parents[1]
        discovery_fixture = Path(__file__).parent / "fixtures" / "discovery"
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            fixture.mkdir()
            for source in (
                FIXTURES / "feed_cards_live.json",
                FIXTURES / "post_detail_public.json",
                FIXTURES / "post_detail_live.html",
                discovery_fixture / "profile_contents_public.json",
            ):
                shutil.copyfile(source, fixture / source.name)
            output = Path(directory) / "result.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(project / "scripts" / "collect_square_v4.py"),
                    "--fixture",
                    str(fixture),
                    "--clock",
                    "2026-07-31T05:48:36Z",
                    "--limit",
                    "10",
                    "--output",
                    str(output),
                ],
                cwd=project,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            counts = payload["counts"]
            self.assertEqual(6, counts["discovered_source_records"])
            self.assertEqual(5, counts["deduplicated_post_candidates"])
            self.assertEqual(1, counts["duplicate_source_records"])
            self.assertEqual(
                counts["discovered_source_records"],
                counts["deduplicated_post_candidates"]
                + counts["duplicate_source_records"],
            )
            self.assertEqual(
                counts["deduplicated_post_candidates"],
                counts["accepted_observations"]
                + counts["quarantined_source_records"],
            )


if __name__ == "__main__":
    unittest.main()
