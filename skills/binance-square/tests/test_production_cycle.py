from pathlib import Path
import json
import tempfile
import unittest

from scripts.run_production_cycle import ProductionCycleConfig, run_production_cycle


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
            self.assertNotIn("telegram", " ".join(calls[1]).lower())


if __name__ == "__main__":
    unittest.main()
