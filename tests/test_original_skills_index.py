import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_original_skills_index.py"
INDEX = ROOT / "skills" / "original" / "index.json"
README = ROOT / "skills" / "original" / "README.md"
PROVENANCE = ROOT / "config" / "skill-provenance.json"


class OriginalSkillsIndexTests(unittest.TestCase):
    def test_generated_original_collection_is_current_and_provenance_bounded(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILDER), "--root", str(ROOT), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        index = json.loads(INDEX.read_text(encoding="utf-8"))
        provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
        reviewed_originals = {
            entry["skill_id"]
            for entry in provenance["entries"]
            if entry["origin_kind"] == "project-original"
            and entry["review_state"] == "reviewed"
        }
        indexed = {entry["skill_id"] for entry in index["skills"]}

        self.assertEqual(reviewed_originals, indexed)
        self.assertTrue(
            {
                "binance-square",
                "5minbtc",
                "daily-gzh-content",
                "daily-xhs-content",
                "daily-douyin-content",
                "daniel-x-writer",
            }
            <= indexed
        )
        self.assertEqual(len(indexed), index["inventoryCount"])
        self.assertEqual(
            sorted(indexed), [entry["skill_id"] for entry in index["skills"]]
        )
        by_id = {entry["skill_id"]: entry for entry in index["skills"]}
        self.assertEqual("finance-trading-markets", by_id["5minbtc"]["category_id"])
        self.assertEqual("finance-trading-markets", by_id["binance-square"]["category_id"])
        markdown = README.read_text(encoding="utf-8")
        for skill_id in indexed:
            self.assertIn(f"../{skill_id}/", markdown)
        self.assertNotIn("Unknown", markdown)
        self.assertNotIn("Collected", markdown)

    def test_original_collection_is_discoverable_and_part_of_skill_build_checks(self) -> None:
        skills_readme = (ROOT / "skills" / "README.md").read_text(encoding="utf-8")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertIn("original/", skills_readme)
        self.assertIn("build_original_skills_index.py", package["scripts"]["build:skills"])
        self.assertIn("build_original_skills_index.py", package["scripts"]["check:skills"])


if __name__ == "__main__":
    unittest.main()
