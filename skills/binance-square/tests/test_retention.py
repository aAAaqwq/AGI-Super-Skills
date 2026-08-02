from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scanner.contracts import ContractViolation
from scanner.retention import ArtifactKind, RetentionArtifact, plan_retention


UTC = timezone.utc


class RetentionTests(unittest.TestCase):
    def test_day_60_is_kept_day_61_is_cleanup_and_author_history_is_long_term(self) -> None:
        as_of = datetime(2026, 8, 1, tzinfo=UTC)
        artifacts = (
            RetentionArtifact(Path("raw/day-60.json"), ArtifactKind.RAW_POST, as_of - timedelta(days=60)),
            RetentionArtifact(Path("candles/day-61.json"), ArtifactKind.CANDLE, as_of - timedelta(days=61)),
            RetentionArtifact(Path("authors/lifetime.json"), ArtifactKind.AUTHOR_DAILY_AGGREGATE, as_of - timedelta(days=600)),
            RetentionArtifact(Path("authors/tier-history.json"), ArtifactKind.TIER_HISTORY, as_of - timedelta(days=600)),
        )

        plan = plan_retention(
            artifacts,
            as_of=as_of,
            aggregate_before="sha256:same",
            aggregate_after="sha256:same",
        )

        self.assertTrue(plan.dry_run)
        self.assertEqual((artifacts[1],), plan.cleanup_candidates)
        self.assertEqual((artifacts[0], artifacts[2], artifacts[3]), plan.retained)

    def test_cleanup_is_refused_when_long_term_aggregate_reconciliation_fails(self) -> None:
        with self.assertRaises(ContractViolation):
            plan_retention(
                (),
                as_of=datetime(2026, 8, 1, tzinfo=UTC),
                aggregate_before="sha256:before",
                aggregate_after="sha256:after",
            )

    def test_cleanup_cli_defaults_to_dry_run_and_does_not_remove_fixture(self) -> None:
        project = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_file = root / "raw" / "old.json"
            old_file.parent.mkdir()
            old_file.write_text("evidence", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "aggregate_before": "sha256:same",
                        "aggregate_after": "sha256:same",
                        "artifacts": [
                            {
                                "path": "raw/old.json",
                                "kind": "RAW_POST",
                                "created_at": "2026-05-01T00:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(project / "scripts" / "cleanup_retention.py"),
                    "--manifest",
                    str(manifest),
                    "--root",
                    str(root),
                    "--as-of",
                    "2026-08-01T00:00:00Z",
                ],
                cwd=project,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(old_file.exists())
            payload = json.loads(completed.stdout)
            self.assertEqual("DRY_RUN", payload["mode"])
            self.assertEqual(1, payload["cleanup_candidate_count"])


if __name__ == "__main__":
    unittest.main()
