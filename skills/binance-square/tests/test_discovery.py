import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import unittest

from scanner.authors import load_seed_profile_evidence
from scanner.discovery import (
    ProfileFetchOutcome,
    deduplicate_post_observations,
    observations_from_feed_cards,
    parse_profile_content_response,
    plan_profile_fetches,
    reconcile_profile_fetch_plan,
)
from scanner.square import parse_feed_cards


PROJECT = Path(__file__).parents[1]
SEED_EVIDENCE = (
    Path(__file__).parent / "fixtures" / "discovery" / "leaderboard_seed_profiles.json"
)
DISCOVERY_FIXTURES = Path(__file__).parent / "fixtures" / "discovery"
M1B_FIXTURES = Path(__file__).parent / "fixtures" / "m1b"


class ProfileFetchPlanTests(unittest.TestCase):
    def test_seed_registry_becomes_a_stable_profile_plan(self) -> None:
        seeds = load_seed_profile_evidence(SEED_EVIDENCE)

        plan = plan_profile_fetches(seeds.profiles)

        self.assertEqual("available", plan.availability)
        self.assertEqual("NOT_ATTEMPTED", plan.status)
        self.assertEqual(9, len(plan.targets))
        self.assertEqual(9, len({target.author_id for target in plan.targets}))
        self.assertTrue(all(target.author_id for target in plan.targets))
        self.assertTrue(
            all("/en/square/profile/" in target.profile_url for target in plan.targets)
        )

    def test_profile_outcomes_cover_every_contract_status(self) -> None:
        seeds = load_seed_profile_evidence(SEED_EVIDENCE)
        plan = plan_profile_fetches(seeds.profiles[:2])
        first, second = (target.author_id for target in plan.targets)

        complete = reconcile_profile_fetch_plan(
            plan,
            (
                ProfileFetchOutcome(first, "COMPLETE", 2),
                ProfileFetchOutcome(second, "COMPLETE", 1),
            ),
        )
        empty = reconcile_profile_fetch_plan(
            plan,
            (
                ProfileFetchOutcome(first, "EMPTY", 0),
                ProfileFetchOutcome(second, "EMPTY", 0),
            ),
        )
        failed = reconcile_profile_fetch_plan(
            plan,
            (
                ProfileFetchOutcome(first, "FAILED", 0, "fixture error"),
                ProfileFetchOutcome(second, "FAILED", 0, "fixture error"),
            ),
        )
        partial = reconcile_profile_fetch_plan(
            plan, (ProfileFetchOutcome(first, "COMPLETE", 2),)
        )
        not_attempted = reconcile_profile_fetch_plan(plan, ())
        unavailable = reconcile_profile_fetch_plan(plan_profile_fetches(None), ())

        self.assertEqual("COMPLETE", complete.status)
        self.assertEqual("EMPTY", empty.status)
        self.assertEqual("FAILED", failed.status)
        self.assertEqual("PARTIAL", partial.status)
        self.assertEqual("NOT_ATTEMPTED", not_attempted.status)
        self.assertEqual("NOT_ATTEMPTED", unavailable.status)
        self.assertEqual("unavailable", unavailable.availability)


class CrossChannelDiscoveryTests(unittest.TestCase):
    def test_profile_and_feed_deduplicate_by_post_id_and_keep_observations(self) -> None:
        feed_payload = json.loads(
            (M1B_FIXTURES / "feed_cards_live.json").read_text(encoding="utf-8")
        )
        profile_payload = json.loads(
            (DISCOVERY_FIXTURES / "profile_contents_public.json").read_text(
                encoding="utf-8"
            )
        )
        feed = observations_from_feed_cards(parse_feed_cards(feed_payload))
        profile = parse_profile_content_response(
            profile_payload,
            author_id="synthetic-square-uid-01",
        )

        merged = deduplicate_post_observations((*feed, *profile))

        self.assertEqual(5, merged.source_record_count)
        self.assertEqual(4, merged.unique_post_count)
        self.assertEqual(1, merged.duplicate_source_records)
        shared = next(
            post for post in merged.posts if post.post_id == "990000000000201"
        )
        self.assertEqual(("FEED", "PROFILE"), shared.channels)
        self.assertEqual(2, len(shared.observations))
        self.assertTrue(
            all(
                item.post_url
                == "https://www.binance.com/en/square/post/990000000000201"
                for item in shared.observations
            )
        )


class AuthorDiscoveryCliTests(unittest.TestCase):
    def test_cli_reads_seed_and_fixture_evidence_without_mutating_inputs(self) -> None:
        project = Path(__file__).parents[1]
        fixture = DISCOVERY_FIXTURES / "leaderboards_empty.json"
        before = {
            path: sha256(path.read_bytes()).hexdigest()
            for path in (SEED_EVIDENCE, fixture)
        }

        completed = subprocess.run(
            [
                sys.executable,
                str(project / "scripts" / "discover_authors.py"),
                "--evidence",
                str(SEED_EVIDENCE),
                "--fixture",
                str(fixture),
            ],
            cwd=project,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(9, payload["profile_plan"]["target_count"])
        self.assertEqual("NOT_ATTEMPTED", payload["profile_coverage"]["status"])
        self.assertEqual(
            "PARTIAL_SEED_DISCOVERY", payload["leaderboard_coverage"]["status"]
        )
        self.assertEqual(0, payload["leaderboard_coverage"]["covered"])
        self.assertEqual(4, payload["leaderboard_coverage"]["expected"])
        self.assertEqual(
            before,
            {path: sha256(path.read_bytes()).hexdigest() for path in before},
        )


if __name__ == "__main__":
    unittest.main()
