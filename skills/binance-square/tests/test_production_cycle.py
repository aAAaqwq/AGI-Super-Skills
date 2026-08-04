import io
from pathlib import Path
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

from scripts.run_production_cycle import (
    PROJECT_DIR,
    ProductionCycleConfig,
    _arguments,
    _subprocess_runner,
    run_production_cycle,
)


def _eligible_feed_payload(immutable: Path, *, scanned_at: str) -> dict:
    posts = [
        {"url": f"https://www.binance.com/en/square/post/{index}"}
        for index in range(1, 5)
    ]
    return {
        "status": "ok",
        "scanned_at": scanned_at,
        "snapshot_file": str(immutable),
        "eligible_for_coverage_promotion": True,
        "eligible_snapshot_file": str(immutable),
        "count": len(posts),
        "posts": posts,
        "coverage_contract_version": "square-feed-coverage/v1",
        "discovery_result": {
            "coverage_scope": "BINANCE_SQUARE_DISCOVER_DOM",
            "global_denominator_known": False,
            "pagination_api_exhaustion_verified": False,
            "coverage_status": "BOUNDED_COMPLETE",
            "termination_reason": "EXHAUSTED",
            "started_from_top": True,
            "reached_bottom": True,
            "bottom_geometry_stable": True,
            "source_observation_count": 12,
            "valid_url_observation_count": 12,
            "invalid_url_observation_count": 0,
            "unique_candidate_post_count": len(posts),
            "same_run_duplicate_observation_count": 8,
            "preferred_minimum": len(posts),
            "hard_limit": 200,
            "minimum_target_met": True,
            "truncated": False,
            "scroll_rounds": 3,
            "consecutive_no_new": 2,
            "required_consecutive_no_new": 2,
        },
    }


def _write_eligible_feed_cycle(
    root: Path, immutable: Path, *, scanned_at: str
) -> bytes:
    payload = _eligible_feed_payload(immutable, scanned_at=scanned_at)
    content = json.dumps(payload).encode("utf-8")
    immutable.parent.mkdir(parents=True, exist_ok=True)
    immutable.write_bytes(content)
    latest = root / "data" / "binance_raw_posts.json"
    latest.write_bytes(content)
    eligible = root / "data" / "binance_raw_posts_eligible.json"
    eligible.write_bytes(content)
    return content


class ProductionCycleTests(unittest.TestCase):
    def test_long_silent_child_emits_progress_heartbeats(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            _subprocess_runner(
                [sys.executable, "-c", "import time; time.sleep(0.12)"],
                heartbeat_interval_seconds=0.03,
            )

        output = stderr.getvalue()
        self.assertIn("[HEARTBEAT]", output)
        self.assertIn("elapsed_seconds=", output)

    def test_cli_defaults_do_not_consume_legacy_signals(self) -> None:
        args = _arguments([])

        self.assertIsNone(args.signals_json)
        self.assertEqual(
            {
                "output_dir": PROJECT_DIR / "data" / "v4" / "runs",
                "database": PROJECT_DIR / "data" / "v4" / "radar.sqlite",
            },
            {
                "output_dir": args.output_dir,
                "database": args.database,
            },
        )
        self.assertTrue(
            all(
                isinstance(value, Path) and value.is_relative_to(PROJECT_DIR)
                for value in (args.output_dir, args.database)
            )
        )

    def test_no_send_cycle_refreshes_feed_before_smart_money_radar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[tuple[str, ...]] = []
            immutable = root / "data" / "history" / "feed-immutable.json"

            def runner(command: list[str]) -> None:
                calls.append(tuple(command))
                if len(calls) == 1:
                    _write_eligible_feed_cycle(
                        root,
                        immutable,
                        scanned_at="2026-08-01T08:00:01Z",
                    )
                elif len(calls) == 3:
                    _write_eligible_feed_cycle(
                        root,
                        root / "data" / "history" / "feed-immutable-second.json",
                        scanned_at="2026-08-01T08:00:02Z",
                    )

            run_production_cycle(
                ProductionCycleConfig(
                    project_dir=root,
                    signals_json=root / "signals.json",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    job_namespace="canary-test",
                    production_job_id="binance-radar-4h",
                    leaderboard_seed_evidence=root / "seed-profiles.json",
                    smart_money_square_mapping_evidence=root / "mapping.json",
                ),
                runner=runner,
            )

            self.assertEqual(2, len(calls))
            self.assertTrue(calls[0][-1].endswith("scripts/binance_scraper.py"))
            self.assertTrue(
                calls[1][-1].endswith("scripts/run_radar.py") or "--real" in calls[1]
            )
            self.assertIn("--real", calls[1])
            self.assertIn("--smart-money", calls[1])
            self.assertIn("--no-send", calls[1])
            self.assertIn("canary-test", calls[1])
            mapping_index = calls[1].index("--smart-money-square-mapping-evidence") + 1
            self.assertEqual(str(root / "mapping.json"), calls[1][mapping_index])
            snapshot_index = calls[1].index("--input-snapshot") + 1
            self.assertEqual(str(immutable), calls[1][snapshot_index])
            signals_value_index = calls[1].index("--signals-json") + 1
            self.assertEqual(str(root / "signals.json"), calls[1][signals_value_index])
            self.assertEqual(
                (
                    "--leaderboard-seed-evidence",
                    str(root / "seed-profiles.json"),
                    "--output-dir",
                ),
                calls[1][signals_value_index + 1 : signals_value_index + 4],
            )
            self.assertNotIn("telegram", " ".join(calls[1]).lower())

            run_production_cycle(
                ProductionCycleConfig(
                    project_dir=root,
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    smart_money_square_mapping_catalog=root / "catalog.json",
                ),
                runner=runner,
            )
            catalog_index = calls[3].index("--smart-money-square-mapping-catalog") + 1
            self.assertEqual(str(root / "catalog.json"), calls[3][catalog_index])
            self.assertNotIn("--signals-json", calls[3])

    def test_partial_observation_fails_closed_without_reusing_stale_eligible(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[tuple[str, ...]] = []
            stale_immutable = root / "data" / "history" / "stale-eligible.json"
            _write_eligible_feed_cycle(
                root,
                stale_immutable,
                scanned_at="2026-08-01T08:00:00Z",
            )

            def runner(command: list[str]) -> None:
                calls.append(tuple(command))
                if len(calls) != 1:
                    return
                current_immutable = (
                    root / "data" / "history" / "partial-observation.json"
                )
                payload = _eligible_feed_payload(
                    current_immutable,
                    scanned_at="2026-08-01T08:00:01Z",
                )
                payload["eligible_for_coverage_promotion"] = False
                payload["eligible_snapshot_file"] = None
                payload["discovery_result"].update(
                    {
                        "coverage_status": "PARTIAL",
                        "termination_reason": "STAGNANT",
                        "minimum_target_met": False,
                        "preferred_minimum": 100,
                    }
                )
                content = json.dumps(payload).encode("utf-8")
                current_immutable.write_bytes(content)
                (root / "data" / "binance_raw_posts.json").write_bytes(content)

            with self.assertRaisesRegex(
                RuntimeError,
                "not eligible for coverage promotion",
            ):
                run_production_cycle(
                    ProductionCycleConfig(
                        project_dir=root,
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                    ),
                    runner=runner,
                )

            self.assertEqual(1, len(calls))
            self.assertEqual(
                _eligible_feed_payload(
                    stale_immutable,
                    scanned_at="2026-08-01T08:00:00Z",
                ),
                json.loads(
                    (root / "data" / "binance_raw_posts_eligible.json").read_text(
                        encoding="utf-8"
                    )
                ),
            )

    def test_stale_eligible_pointer_fails_closed_before_radar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[tuple[str, ...]] = []
            _write_eligible_feed_cycle(
                root,
                root / "data" / "history" / "stale-eligible.json",
                scanned_at="2026-08-01T08:00:00Z",
            )

            def runner(command: list[str]) -> None:
                calls.append(tuple(command))
                if len(calls) != 1:
                    return
                immutable = root / "data" / "history" / "current-observation.json"
                payload = _eligible_feed_payload(
                    immutable,
                    scanned_at="2026-08-01T08:00:01Z",
                )
                content = json.dumps(payload).encode("utf-8")
                immutable.write_bytes(content)
                (root / "data" / "binance_raw_posts.json").write_bytes(content)

            with self.assertRaisesRegex(RuntimeError, "eligible Feed pointer"):
                run_production_cycle(
                    ProductionCycleConfig(
                        project_dir=root,
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                    ),
                    runner=runner,
                )

            self.assertEqual(1, len(calls))

    def test_successful_scraper_exit_cannot_reuse_previous_observed_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[tuple[str, ...]] = []
            _write_eligible_feed_cycle(
                root,
                root / "data" / "history" / "previous-observation.json",
                scanned_at="2026-08-01T08:00:00Z",
            )

            def runner(command: list[str]) -> None:
                calls.append(tuple(command))

            with self.assertRaisesRegex(
                RuntimeError,
                "did not refresh the observed latest snapshot",
            ):
                run_production_cycle(
                    ProductionCycleConfig(
                        project_dir=root,
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                    ),
                    runner=runner,
                )

            self.assertEqual(1, len(calls))

    def test_coverage_promotion_metadata_mismatch_fails_closed(self) -> None:
        mismatches = {
            "promotion flag": {"eligible_for_coverage_promotion": False},
            "eligible snapshot": {"eligible_snapshot_file": "other.json"},
        }
        for label, mismatch in mismatches.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                calls: list[tuple[str, ...]] = []

                def runner(command: list[str]) -> None:
                    calls.append(tuple(command))
                    if len(calls) != 1:
                        return
                    immutable = root / "data" / "history" / "current.json"
                    payload = _eligible_feed_payload(
                        immutable,
                        scanned_at="2026-08-01T08:00:01Z",
                    )
                    payload.update(mismatch)
                    content = json.dumps(payload).encode("utf-8")
                    immutable.parent.mkdir(parents=True, exist_ok=True)
                    immutable.write_bytes(content)
                    (root / "data" / "binance_raw_posts.json").write_bytes(content)
                    (root / "data" / "binance_raw_posts_eligible.json").write_bytes(
                        content
                    )

                with self.assertRaisesRegex(
                    RuntimeError,
                    "not eligible for coverage promotion",
                ):
                    run_production_cycle(
                        ProductionCycleConfig(
                            project_dir=root,
                            output_dir=root / "runs",
                            database=root / "radar.sqlite",
                        ),
                        runner=runner,
                    )

                self.assertEqual(1, len(calls))

    def test_missing_eligible_pointer_fails_closed_before_radar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[tuple[str, ...]] = []

            def runner(command: list[str]) -> None:
                calls.append(tuple(command))
                if len(calls) != 1:
                    return
                immutable = root / "data" / "history" / "current.json"
                payload = _eligible_feed_payload(
                    immutable,
                    scanned_at="2026-08-01T08:00:01Z",
                )
                content = json.dumps(payload).encode("utf-8")
                immutable.parent.mkdir(parents=True, exist_ok=True)
                immutable.write_bytes(content)
                (root / "data" / "binance_raw_posts.json").write_bytes(content)

            with self.assertRaisesRegex(
                RuntimeError,
                "did not produce an eligible Feed pointer",
            ):
                run_production_cycle(
                    ProductionCycleConfig(
                        project_dir=root,
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                    ),
                    runner=runner,
                )

            self.assertEqual(1, len(calls))

    def test_cli_parses_leaderboard_seed_evidence_path(self) -> None:
        args = _arguments(
            [
                "--signals-json",
                "signals.json",
                "--leaderboard-seed-evidence",
                "seed-profiles.json",
            ]
        )

        self.assertEqual(Path("signals.json"), args.signals_json)
        self.assertEqual(Path("seed-profiles.json"), args.leaderboard_seed_evidence)

    def test_fresh_legacy_snapshot_cannot_enter_production_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            immutable = root / "data" / "history" / "feed-immutable.json"

            def runner(_command: list[str]) -> None:
                immutable.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "status": "ok",
                    "scanned_at": "2026-08-01T08:00:01Z",
                    "snapshot_file": str(immutable),
                    "count": 4,
                    "posts": [
                        {
                            "url": (
                                "https://www.binance.com/en/square/post/"
                                f"99000000000020{index}"
                            )
                        }
                        for index in range(1, 5)
                    ],
                }
                content = json.dumps(payload).encode("utf-8")
                immutable.write_bytes(content)
                latest = root / "data" / "binance_raw_posts.json"
                latest.parent.mkdir(parents=True, exist_ok=True)
                latest.write_bytes(content)

            with self.assertRaisesRegex(RuntimeError, "coverage contract"):
                run_production_cycle(
                    ProductionCycleConfig(
                        project_dir=root,
                        signals_json=root / "signals.json",
                        output_dir=root / "runs",
                        database=root / "radar.sqlite",
                    ),
                    runner=runner,
                )


if __name__ == "__main__":
    unittest.main()
