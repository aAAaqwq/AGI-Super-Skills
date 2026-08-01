import json
from pathlib import Path
import tempfile
import unittest

from scanner.authors import (
    LEADERBOARD_METRICS,
    assess_leaderboard_coverage,
    load_seed_profile_evidence,
    parse_30d_leaderboard,
    parse_author_profile,
)
from scanner.contracts import ContractViolation


FIXTURES = Path(__file__).parent / "fixtures" / "m1b"
PROJECT = Path(__file__).parents[1]
SEED_EVIDENCE = (
    Path(__file__).parent / "fixtures" / "discovery" / "leaderboard_seed_profiles.json"
)


class AuthorProfileTests(unittest.TestCase):
    def test_profile_keeps_stable_id_labels_duration_and_hard_tier_gate(self) -> None:
        public_payload = json.loads(
            (FIXTURES / "profile_public.json").read_text(encoding="utf-8")
        )
        html = (FIXTURES / "profile_live.html").read_text(encoding="utf-8")

        author = parse_author_profile(
            public_payload=public_payload,
            html=html,
            observed_at="2026-08-01T07:03:00Z",
        )

        self.assertEqual("synthetic-square-uid-profile", author.author_id)
        self.assertEqual("FixtureTrader", author.username)
        self.assertEqual("Fixture Analyst", author.display_name)
        self.assertEqual(1314, author.trading_days)
        self.assertEqual("A", author.duration_tier)
        self.assertFalse(author.public_live)
        self.assertEqual(
            "UNQUALIFIED_MISSING_LIVE_OR_LEADERBOARD", author.tier_status
        )
        self.assertIn("High-Frequency Trader", author.visible_labels)
        self.assertIn("Square Verified+", author.visible_labels)
        self.assertEqual(12000, author.follower_count)

    def test_content_quality_is_required_before_external_probation(self) -> None:
        public_payload = json.loads(
            (FIXTURES / "profile_public.json").read_text(encoding="utf-8")
        )
        pending = parse_author_profile(
            public_payload=public_payload,
            html=None,
            observed_at="2026-08-01T07:03:00Z",
            leaderboard_tags=("Top traders by profit in 30D",),
        )
        qualified = parse_author_profile(
            public_payload=public_payload,
            html=None,
            observed_at="2026-08-01T07:03:00Z",
            leaderboard_tags=("Top traders by profit in 30D",),
            analysis_qualified=True,
        )

        self.assertEqual("UNQUALIFIED_PENDING_CONTENT_QUALITY", pending.tier_status)
        self.assertEqual("A_EXTERNAL_VERIFIED_PROBATION", qualified.tier_status)

    def test_seed_evidence_keeps_nine_stable_ids_score_ineligible(self) -> None:
        evidence = load_seed_profile_evidence(SEED_EVIDENCE)

        self.assertEqual(9, len(evidence.profiles))
        self.assertEqual(
            "2f07802a6b32b05746dcadc8f55cf77d8a04109ac3f7bfc547353ebdb90dfaed",
            evidence.sha256_hex,
        )
        self.assertEqual(9, evidence.leaderboard_coverage["verified_seed_profiles"])
        self.assertEqual(0, evidence.leaderboard_coverage["covered"])
        self.assertFalse(evidence.leaderboard_coverage["complete_top30"])
        self.assertEqual(
            9, len({profile.author_id for profile in evidence.profiles})
        )
        self.assertTrue(all(not profile.score_eligible for profile in evidence.profiles))
        self.assertTrue(all(profile.author_score == 0 for profile in evidence.profiles))

    def test_seed_evidence_quarantines_cross_identity_alias_collision(self) -> None:
        payload = json.loads(SEED_EVIDENCE.read_text(encoding="utf-8"))
        payload["profiles"][1]["username"] = payload["profiles"][0]["username"]
        payload["profiles"][1]["profile_url"] = payload["profiles"][0]["profile_url"]
        with tempfile.TemporaryDirectory() as directory:
            collision = Path(directory) / "collision.json"
            collision.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ContractViolation, "ALIAS_COLLISION"):
                load_seed_profile_evidence(collision)


def _leaderboard_payload(metric: str, count: int = 30) -> dict[str, object]:
    return {
        "rankingType": metric,
        "timeRange": "30D",
        "rows": [
            {
                "rank": rank,
                "squareUid": f"stable-author-{rank:02d}",
                "username": f"trader-{rank:02d}",
                "displayName": f"Trader {rank:02d}",
                "value": str(1000 - rank),
            }
            for rank in range(1, count + 1)
        ],
    }


class LeaderboardContractTests(unittest.TestCase):
    def test_named_30d_top30_with_unique_stable_ids_is_complete(self) -> None:
        result = parse_30d_leaderboard(_leaderboard_payload("PNL"))

        self.assertEqual("PNL", result.metric)
        self.assertEqual("30D", result.period)
        self.assertEqual("COMPLETE", result.status)
        self.assertEqual(tuple(range(1, 31)), tuple(row.rank for row in result.rows))
        self.assertEqual(30, result.source_record_count)
        self.assertEqual(30, len(result.rows))
        self.assertEqual(0, len(result.rejected))

    def test_all_four_named_metrics_use_the_same_strict_contract(self) -> None:
        results = tuple(
            parse_30d_leaderboard(_leaderboard_payload(metric))
            for metric in LEADERBOARD_METRICS
        )

        self.assertEqual(
            ("PNL", "ROI", "VOLUME", "WIN_RATE"),
            tuple(result.metric for result in results),
        )
        self.assertTrue(all(result.complete_top30 for result in results))
        coverage = assess_leaderboard_coverage(results)
        self.assertEqual("COMPLETE", coverage.status)
        self.assertEqual(4, coverage.covered)
        self.assertEqual(120, coverage.rendered_rank_rows)

    def test_short_duplicate_or_missing_identity_never_becomes_complete(self) -> None:
        short = parse_30d_leaderboard(_leaderboard_payload("ROI", 29))
        duplicate_rank_payload = _leaderboard_payload("VOLUME")
        duplicate_rank_payload["rows"][-1]["rank"] = 1
        duplicate_rank = parse_30d_leaderboard(duplicate_rank_payload)
        duplicate_author_payload = _leaderboard_payload("WIN_RATE")
        duplicate_author_payload["rows"][-1]["squareUid"] = (
            duplicate_author_payload["rows"][0]["squareUid"]
        )
        duplicate_author = parse_30d_leaderboard(duplicate_author_payload)
        missing_id_payload = _leaderboard_payload("PNL")
        del missing_id_payload["rows"][-1]["squareUid"]
        missing_id = parse_30d_leaderboard(missing_id_payload)

        for result in (short, duplicate_rank, duplicate_author, missing_id):
            with self.subTest(reason=result.reason):
                self.assertFalse(result.complete_top30)
                self.assertNotEqual("COMPLETE", result.status)
                self.assertEqual(
                    result.source_record_count,
                    len(result.rows) + len(result.rejected),
                )

    def test_profile_seeds_remain_zero_of_four_partial_discovery(self) -> None:
        seeds = load_seed_profile_evidence(SEED_EVIDENCE)

        coverage = assess_leaderboard_coverage((), seed_count=len(seeds.profiles))

        self.assertEqual("PARTIAL_SEED_DISCOVERY", coverage.status)
        self.assertEqual(0, coverage.covered)
        self.assertEqual(4, coverage.expected)
        self.assertEqual(0, coverage.rendered_rank_rows)
        self.assertEqual(9, coverage.verified_seed_profiles)
        self.assertFalse(coverage.complete_top30)


if __name__ == "__main__":
    unittest.main()
