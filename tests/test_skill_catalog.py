import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_skill_catalog.py"
TAXONOMY_PATH = ROOT / "config" / "skill-taxonomy.json"
CATALOG_PATH = ROOT / "catalog" / "README.md"
INDEX_PATH = ROOT / "catalog" / "skill-index.json"


def load_builder():
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("build_skill_catalog", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load skill catalog builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkillCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_builder()
        cls.taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        cls.entries = cls.builder.build_entries(ROOT, cls.taxonomy)

    def test_taxonomy_has_unique_ordered_categories_and_final_fallback(self) -> None:
        categories = self.taxonomy["categories"]
        identifiers = [category["id"] for category in categories]
        self.assertGreaterEqual(len(categories), 8)
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(categories[-1]["fallback"])
        self.assertTrue(all("fallback" not in item for item in categories[:-1]))
        priorities = [category["priority"] for category in categories]
        self.assertEqual(len(priorities), len(set(priorities)))
        emojis = [category["emoji"] for category in categories]
        self.assertTrue(all(emoji.strip() for emoji in emojis))
        self.assertEqual(len(emojis), len(set(emojis)))
        for category in categories:
            for pattern in category["patterns"]:
                re.compile(pattern)
        known_categories = set(identifiers)
        self.assertTrue(set(self.taxonomy["overrides"].values()) <= known_categories)
        known_risks = {item["id"] for item in self.taxonomy["riskLabels"]}
        for signals in self.taxonomy["riskOverrides"].values():
            self.assertTrue(set(signals) <= known_risks)

    def test_catalog_covers_each_canonical_physical_skill_once(self) -> None:
        expected = self.builder.physical_skill_names(ROOT)
        actual = [entry.skill_id for entry in self.entries]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(set(actual), expected)

    def test_every_category_is_used_and_counts_sum_to_inventory(self) -> None:
        counts = self.builder.category_counts(self.entries, self.taxonomy)
        category_ids = [category["id"] for category in self.taxonomy["categories"]]
        self.assertEqual(list(counts), category_ids)
        self.assertTrue(all(count > 0 for count in counts.values()))
        self.assertEqual(sum(counts.values()), len(self.entries))
        fallback_count = counts[self.taxonomy["categories"][-1]["id"]]
        self.assertLess(fallback_count / len(self.entries), 0.10)

    def test_featured_skills_exist_and_are_not_presented_as_verified(self) -> None:
        by_id = {entry.skill_id: entry for entry in self.entries}
        featured = self.taxonomy["featured"]
        self.assertGreaterEqual(len(featured), 6)
        for item in featured:
            with self.subTest(skill=item["skill"]):
                self.assertIn(item["skill"], by_id)
                self.assertEqual(item["category"], by_id[item["skill"]].category_id)
                self.assertEqual(item["supportLevel"], by_id[item["skill"]].support_level)
                self.assertIn(item["supportLevel"], {"curated", "pack-required", "catalog"})
        serialized = json.dumps(featured).lower()
        self.assertNotIn("verified", serialized)
        self.assertNotIn("production-ready", serialized)

    def test_ambiguous_and_high_risk_examples_have_reviewed_outcomes(self) -> None:
        by_id = {entry.skill_id: entry for entry in self.entries}
        expected_categories = {
            "ads-agent": "marketing-seo-growth",
            "ai-trader-arena": "finance-trading-markets",
            "backtesting-frameworks": "finance-trading-markets",
            "bash-pro": "software-engineering",
            "bazi-fortune": "general-utilities",
            "duckdb-cli-ai-skills": "data-analytics-research",
            "geo-agent": "marketing-seo-growth",
            "invoice-generator-agent": "finance-trading-markets",
        }
        for skill_id, category_id in expected_categories.items():
            with self.subTest(skill=skill_id):
                self.assertEqual(by_id[skill_id].category_id, category_id)

        expected_signals = {
            "clanker": "financial-action",
            "openhr": "personal-data",
            "relayer-trade": "financial-action",
            "security-audit": "system-change",
        }
        for skill_id, signal in expected_signals.items():
            with self.subTest(skill=skill_id):
                self.assertIn(signal, by_id[skill_id].review_signals)

    def test_generated_catalog_is_current_and_uses_portable_links(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILDER_PATH), "--root", str(ROOT), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        catalog = CATALOG_PATH.read_text(encoding="utf-8")
        self.assertIn("<!-- Generated by scripts/build_skill_catalog.py", catalog)
        self.assertNotIn("/Users/", catalog)
        self.assertNotIn("/home/", catalog)
        self.assertIn("review: system-change", catalog)
        self.assertIn("Description needs review; inspect source.", catalog)
        for category in self.taxonomy["categories"]:
            self.assertIn(f'<a id="{category["id"]}"></a>', catalog)

    def test_machine_index_matches_markdown_membership_and_runtime_counts(self) -> None:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        indexed_ids = [item["skill_id"] for item in index["skills"]]
        self.assertEqual(index["inventoryCount"], len(self.entries))
        self.assertEqual(indexed_ids, [entry.skill_id for entry in self.entries])
        self.assertEqual(
            sum(category["count"] for category in index["categories"]),
            len(self.entries),
        )
        self.assertTrue(all(category["emoji"] for category in index["categories"]))
        self.assertTrue(
            all(item["path"] == f"skills/{item['skill_id']}/SKILL.md" for item in index["skills"])
        )

    def test_rendering_is_stable_across_hash_seed_and_timezone(self) -> None:
        script = """
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
import build_skill_catalog as builder
root = Path.cwd()
taxonomy = json.loads((root / 'config/skill-taxonomy.json').read_text())
entries = builder.build_entries(root, taxonomy)
payload = builder.render_markdown(entries, taxonomy) + builder.render_json(entries, taxonomy)
print(hashlib.sha256(payload.encode()).hexdigest())
"""
        hashes = []
        for seed, timezone in (("1", "UTC"), ("777", "America/Los_Angeles")):
            environment = os.environ.copy()
            environment.update({"PYTHONHASHSEED": seed, "TZ": timezone})
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            hashes.append(result.stdout.strip())
        self.assertEqual(hashes[0], hashes[1])

    def test_readmes_route_users_to_outcomes_and_the_generated_catalog(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README_CN.md").read_text(encoding="utf-8")
        skills_readme = (ROOT / "skills" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Browse skills by outcome", readme)
        self.assertIn("按成果浏览技能", chinese)
        self.assertIn("../catalog/", skills_readme)
        self.assertNotIn("[Skill matrix](../docs/skills-matrix.md)", skills_readme)


if __name__ == "__main__":
    unittest.main()
