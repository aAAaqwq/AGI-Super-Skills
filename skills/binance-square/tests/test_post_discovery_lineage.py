from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from scanner.contracts import ContractViolation
from scanner.pipeline import MIGRATIONS, PipelineConfig, run_shadow_radar
from scanner.storage import (
    PostDiscoveryObservationInput,
    SQLiteRunLedger,
)
from tests.test_derivation import complete_market


PROJECT = Path(__file__).parents[1]
DETAIL_FIXTURE = PROJECT / "tests" / "fixtures" / "m1b" / "post_detail_public.json"
SEED_EVIDENCE = (
    PROJECT
    / "tests"
    / "fixtures"
    / "discovery"
    / "leaderboard_seed_profiles.json"
)


class PostDiscoveryLineageTests(unittest.TestCase):
    @staticmethod
    def _open_attempt(ledger: SQLiteRunLedger):
        run = ledger.create_or_open_replay_run(
            replay_namespace="post-discovery-lineage-test",
            source_logical_run_id="fixture:post-discovery-lineage",
            pipeline_version="4.1.0",
            now="2026-08-01T12:00:00Z",
        )
        attempt = ledger.start_next_attempt(
            run.logical_run_id,
            started_at="2026-08-01T12:00:01Z",
        )
        return run, attempt

    def _run_cross_channel_real_pipeline(self, root: Path):
        decision = datetime(2026, 8, 1, 12, 6, 10, tzinfo=timezone.utc)
        profile_post_id = "990000000000101"
        feed_post_id = "990000000000102"
        profile_author_id = "synthetic-square-uid-01"
        released_ms = int(
            datetime(2026, 8, 1, 11, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        urls = {
            post_id: f"https://www.binance.com/en/square/post/{post_id}"
            for post_id in (profile_post_id, feed_post_id)
        }
        snapshot = root / "feed-snapshot.json"
        snapshot_payload = {
            "status": "ok",
            "scanned_at": "2026-08-01T12:06:08Z",
            "snapshot_file": str(snapshot),
            "count": 2,
            "posts": [{"url": urls[profile_post_id]}, {"url": urls[feed_post_id]}],
            "coverage_contract_version": "square-feed-coverage/v1",
            "discovery_result": {
                "coverage_status": "PARTIAL",
                "termination_reason": "STAGNANT",
                "started_from_top": True,
                "reached_bottom": True,
                "bottom_geometry_stable": True,
                "source_observation_count": 2855,
                "valid_url_observation_count": 2855,
                "invalid_url_observation_count": 0,
                "unique_candidate_post_count": 2,
                "same_run_duplicate_observation_count": 2853,
                "preferred_minimum": 100,
                "hard_limit": 200,
                "minimum_target_met": False,
                "truncated": False,
                "scroll_rounds": 10,
                "consecutive_no_new": 10,
                "required_consecutive_no_new": 10,
            },
        }
        snapshot.write_text(json.dumps(snapshot_payload), encoding="utf-8")
        signals = root / "signals.json"
        signals.write_text(
            json.dumps(
                [
                    {
                        "source_url": urls[profile_post_id],
                        "symbol": "BTC",
                        "direction": "long",
                        "entry": "62000",
                        "sl": "61000",
                        "tp": "65000",
                    }
                ]
            ),
            encoding="utf-8",
        )

        profile_calls: list[tuple[str, int]] = []

        def fetch_profile(square_uid: str, offset: int) -> dict[str, object]:
            profile_calls.append((square_uid, offset))
            contents = []
            if square_uid == profile_author_id:
                contents.append(
                    {
                        "id": profile_post_id,
                        "webLink": urls[profile_post_id],
                        "contentType": "POST",
                        "squareUid": profile_author_id,
                        "firstReleaseTime": released_ms,
                    }
                )
            return {
                "success": True,
                "data": {"contents": contents, "nextTimeOffset": None},
            }

        detail_template = json.loads(DETAIL_FIXTURE.read_text(encoding="utf-8"))
        detail_calls: list[str] = []

        def fetch_detail(url: str) -> dict[str, object]:
            detail_calls.append(url)
            post_id = url.rsplit("/", 1)[1]
            payload = deepcopy(detail_template)
            payload["response"]["data"].update(
                {
                    "id": int(post_id),
                    "webLink": url,
                    "squareUid": (
                        profile_author_id
                        if post_id == profile_post_id
                        else "feed-only-square-uid"
                    ),
                    "firstReleaseTime": released_ms,
                    "bodyTextOnly": "market context only",
                }
            )
            return payload

        result = run_shadow_radar(
            PipelineConfig(
                mode="real",
                output_dir=root / "runs",
                database=root / "radar.sqlite",
                decision_at=decision,
                input_snapshot=snapshot,
                signals_json=signals,
                leaderboard_seed_evidence=SEED_EVIDENCE,
                limit=2,
            ),
            clock=lambda: decision,
            detail_fetcher=fetch_detail,
            market_client=SimpleNamespace(
                fetch_futures_catalog=lambda: SimpleNamespace(
                    server_time_ms=int(decision.timestamp() * 1000),
                    captured_at=decision,
                    contracts={},
                ),
                fetch_snapshot=lambda _symbol, **_kwargs: complete_market(),
            ),
            profile_content_fetcher=fetch_profile,
            profile_capture_time="2026-08-01T12:06:09Z",
        )
        return result, detail_calls, profile_calls, snapshot_payload

    def test_real_raw_preserves_selected_cross_channel_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, detail_calls, _, snapshot_payload = (
                self._run_cross_channel_real_pipeline(root)
            )
            raw = json.loads(result.raw_json.read_text(encoding="utf-8"))
            report = json.loads(result.report_json.read_text(encoding="utf-8"))

            observations = raw["discovery_observations"]
            self.assertEqual(4, len(observations))
            self.assertEqual(
                ["PROFILE", "CURATED_SIGNAL", "FEED"],
                [
                    item["source_channel"]
                    for item in observations
                    if item["post_id"] == "990000000000101"
                ],
            )
            self.assertEqual(
                [0, 1, 2, 3],
                [item["source_record_ordinal"] for item in observations],
            )
            self.assertEqual(
                4,
                raw["counts"]["deduplicated_post_candidates"]
                + raw["counts"]["duplicate_source_records"],
            )
            self.assertEqual(
                2, raw["counts"]["deduplicated_post_candidates"]
            )
            self.assertEqual(2, raw["counts"]["duplicate_source_records"])
            self.assertEqual(2, len(detail_calls))
            self.assertEqual(2, len(set(detail_calls)))
            self.assertEqual(4, report["post_counts"]["source_observations"])
            self.assertEqual(2, report["post_counts"]["deduplicated_candidates"])
            self.assertEqual(2, report["post_counts"]["discovered"])
            self.assertEqual(
                2855,
                snapshot_payload["discovery_result"]["source_observation_count"],
            )

    def test_real_database_reconciles_to_raw_discovery_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, _, _, _ = self._run_cross_channel_real_pipeline(root)
            raw = json.loads(result.raw_json.read_text(encoding="utf-8"))
            ledger = SQLiteRunLedger(root / "radar.sqlite", PROJECT / "migrations")
            self.addCleanup(ledger.close)

            stored = ledger.list_post_discovery_observations(
                attempt_id=result.attempt_id
            )

            self.assertEqual(len(raw["discovery_observations"]), len(stored))
            self.assertEqual(
                [
                    (
                        result.logical_run_id,
                        result.attempt_id,
                        item["source_record_ordinal"],
                        item["source_channel"],
                        item["post_id"],
                        item["canonical_post_url"],
                        item["expected_author_id"],
                        item["expected_first_release_time_ms"],
                        item["source_profile_url"],
                    )
                    for item in raw["discovery_observations"]
                ],
                [
                    (
                        item.logical_run_id,
                        item.attempt_id,
                        item.source_record_ordinal,
                        item.source_channel,
                        item.post_id,
                        item.canonical_post_url,
                        item.expected_author_id,
                        item.expected_first_release_time_ms,
                        item.source_profile_url,
                    )
                    for item in stored
                ],
            )

    def test_ledger_replays_exact_discovery_batch_and_rejects_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteRunLedger(Path(directory) / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            run, attempt = self._open_attempt(ledger)
            observations = (
                PostDiscoveryObservationInput(
                    post_id="101",
                    canonical_post_url=(
                        "https://www.binance.com/en/square/post/101"
                    ),
                    source_channel="PROFILE",
                    source_record_ordinal=0,
                    expected_author_id="square-101",
                    expected_first_release_time_ms=1_785_571_200_000,
                    source_profile_url=(
                        "https://www.binance.com/en/square/profile/author-101"
                    ),
                ),
                PostDiscoveryObservationInput(
                    post_id="101",
                    canonical_post_url=(
                        "https://www.binance.com/en/square/post/101"
                    ),
                    source_channel="FEED",
                    source_record_ordinal=1,
                ),
            )
            recorded = ledger.record_post_discovery_observations(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                observations=observations,
                canonical_candidate_count=1,
                same_run_duplicate_count=1,
                observed_at="2026-08-01T12:00:02Z",
            )
            replayed = ledger.record_post_discovery_observations(
                logical_run_id=run.logical_run_id,
                attempt_id=attempt.attempt_id,
                observations=observations,
                canonical_candidate_count=1,
                same_run_duplicate_count=1,
                observed_at="2026-08-01T12:00:02Z",
            )
            self.assertEqual(recorded, replayed)

            with self.assertRaises(ContractViolation):
                ledger.record_post_discovery_observations(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    observations=(
                        observations[0],
                        PostDiscoveryObservationInput(
                            post_id="101",
                            canonical_post_url=(
                                "https://www.binance.com/en/square/post/101"
                            ),
                            source_channel="CURATED_SIGNAL",
                            source_record_ordinal=1,
                        ),
                    ),
                    canonical_candidate_count=1,
                    same_run_duplicate_count=1,
                    observed_at="2026-08-01T12:00:02Z",
                )
            self.assertEqual(
                recorded,
                ledger.list_post_discovery_observations(
                    attempt_id=attempt.attempt_id
                ),
            )

    def test_ledger_rejects_discovery_writes_after_attempt_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteRunLedger(Path(directory) / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            run, attempt = self._open_attempt(ledger)
            ledger.finish_attempt(
                attempt.attempt_id,
                status="SUCCEEDED",
                finished_at="2026-08-01T12:00:02Z",
            )

            with self.assertRaises(ContractViolation):
                ledger.record_post_discovery_observations(
                    logical_run_id=run.logical_run_id,
                    attempt_id=attempt.attempt_id,
                    observations=(),
                    canonical_candidate_count=0,
                    same_run_duplicate_count=0,
                    observed_at="2026-08-01T12:00:03Z",
                )


if __name__ == "__main__":
    unittest.main()
