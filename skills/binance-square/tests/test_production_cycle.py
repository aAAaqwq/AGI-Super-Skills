from pathlib import Path
import json
import tempfile
import unittest

from scripts.run_production_cycle import (
    ProductionCycleConfig,
    _arguments,
    run_production_cycle,
)


class ProductionCycleTests(unittest.TestCase):
    def test_no_send_cycle_refreshes_feed_before_smart_money_radar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[tuple[str, ...]] = []
            immutable = root / "data" / "history" / "feed-immutable.json"

            def runner(command: list[str]) -> None:
                calls.append(tuple(command))
                if len(calls) == 1:
                    immutable.parent.mkdir(parents=True)
                    payload = {
                        "status": "ok",
                        "scanned_at": "2026-08-01T08:00:01Z",
                        "snapshot_file": str(immutable),
                        "count": 0,
                        "posts": [],
                        "coverage_contract_version": "square-feed-coverage/v1",
                        "discovery_result": {
                            "coverage_status": "PARTIAL",
                            "termination_reason": "STAGNANT",
                            "started_from_top": True,
                            "reached_bottom": True,
                            "bottom_geometry_stable": True,
                            "source_observation_count": 0,
                            "valid_url_observation_count": 0,
                            "invalid_url_observation_count": 0,
                            "unique_candidate_post_count": 0,
                            "same_run_duplicate_observation_count": 0,
                            "preferred_minimum": 100,
                            "hard_limit": 200,
                            "minimum_target_met": False,
                            "truncated": False,
                            "scroll_rounds": 10,
                            "consecutive_no_new": 10,
                            "required_consecutive_no_new": 10,
                        },
                    }
                    content = json.dumps(payload).encode("utf-8")
                    immutable.write_bytes(content)
                    latest = root / "data" / "binance_raw_posts.json"
                    latest.parent.mkdir(parents=True, exist_ok=True)
                    latest.write_bytes(content)

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
            self.assertTrue(calls[1][-1].endswith("scripts/run_radar.py") or "--real" in calls[1])
            self.assertIn("--real", calls[1])
            self.assertIn("--smart-money", calls[1])
            self.assertIn("--no-send", calls[1])
            self.assertIn("canary-test", calls[1])
            mapping_index = (
                calls[1].index("--smart-money-square-mapping-evidence") + 1
            )
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
                    signals_json=root / "signals.json",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    smart_money_square_mapping_catalog=root / "catalog.json",
                ),
                runner=runner,
            )
            catalog_index = calls[3].index(
                "--smart-money-square-mapping-catalog"
            ) + 1
            self.assertEqual(str(root / "catalog.json"), calls[3][catalog_index])

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
