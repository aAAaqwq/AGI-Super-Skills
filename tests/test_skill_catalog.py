import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_skill_catalog.py"
TAXONOMY_PATH = ROOT / "config" / "skill-taxonomy.json"
TAXONOMY_SCHEMA_PATH = ROOT / "config" / "skill-taxonomy.schema.json"
CATALOG_PATH = ROOT / "catalog" / "README.md"
INDEX_PATH = ROOT / "catalog" / "skill-index.json"
INDEX_SCHEMA_PATH = ROOT / "config" / "skill-index.schema.json"


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
        schema = json.loads(TAXONOMY_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.taxonomy)
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
            for pattern in category["outcomePatterns"]:
                re.compile(pattern)
        known_categories = set(identifiers)
        self.assertTrue(set(self.taxonomy["overrides"].values()) <= known_categories)
        self.assertEqual(
            set(self.taxonomy["overrideRationales"]),
            set(self.taxonomy["overrides"]),
        )
        known_risks = {item["id"] for item in self.taxonomy["riskLabels"]}
        for signals in self.taxonomy["riskOverrides"].values():
            self.assertTrue(set(signals) <= known_risks)

    def test_catalog_covers_each_canonical_physical_skill_once(self) -> None:
        expected = self.builder.physical_skill_names(ROOT)
        actual = [entry.skill_id for entry in self.entries]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(set(actual), expected)

    def test_unreviewed_inventory_defaults_to_unknown_and_unscored(self) -> None:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        by_id = {item["skill_id"]: item for item in index["skills"]}

        unreviewed = by_id["5minbtc"]
        self.assertEqual(unreviewed["provenance"]["origin_kind"], "unknown")
        self.assertEqual(unreviewed["provenance"]["review_state"], "unreviewed")
        self.assertEqual(unreviewed["curation"]["status"], "unscored")
        self.assertNotIn("score", unreviewed["curation"])

    def test_reviewed_original_can_be_selected_without_claiming_runtime_verification(self) -> None:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        by_id = {item["skill_id"]: item for item in index["skills"]}

        selected = by_id["content-typography"]
        self.assertEqual(selected["provenance"]["origin_kind"], "project-original")
        self.assertEqual(selected["provenance"]["review_state"], "reviewed")
        self.assertEqual(selected["curation"]["status"], "selected")
        self.assertGreaterEqual(selected["curation"]["score"], 75)
        self.assertEqual(selected["curation"]["runtime_evidence"], "pending")
        self.assertNotIn("verified", json.dumps(selected["curation"]).lower())

        unresolved = by_id["agent-team-orchestration"]
        self.assertEqual(unresolved["provenance"]["origin_kind"], "unknown")
        self.assertEqual(unresolved["curation"]["status"], "unscored")

    def test_portability_class_covers_every_manifest_assignment_level(self) -> None:
        self.assertEqual(self.builder._portability_class({"required"}), "portable-required")
        self.assertEqual(self.builder._portability_class({"optional"}), "portable-optional")
        self.assertEqual(self.builder._portability_class({"harnessSpecific"}), "harness-specific")
        self.assertEqual(self.builder._portability_class(set()), "catalog-only")

    def test_every_category_is_used_and_counts_sum_to_inventory(self) -> None:
        counts = self.builder.category_counts(self.entries, self.taxonomy)
        category_ids = [category["id"] for category in self.taxonomy["categories"]]
        self.assertEqual(list(counts), category_ids)
        self.assertTrue(all(count > 0 for count in counts.values()))
        self.assertEqual(sum(counts.values()), len(self.entries))
        fallback_count = counts[self.taxonomy["categories"][-1]["id"]]
        self.assertLess(fallback_count / len(self.entries), 0.10)

    def test_selected_skills_come_from_curation_not_taxonomy(self) -> None:
        self.assertNotIn("featured", self.taxonomy)
        selected = [entry for entry in self.entries if entry.curation["status"] == "selected"]
        self.assertGreaterEqual(len(selected), 2)
        serialized = json.dumps([entry.curation for entry in selected]).lower()
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

    def test_primary_outcome_routes_beat_incidental_tokens(self) -> None:
        by_id = {entry.skill_id: entry for entry in self.entries}
        expected_categories = {
            "agent-browser": "apps-workflow-automation",
            "ai-marketing-videos": "content-media-publishing",
            "api-design-patterns": "software-engineering",
            "business-analyst": "data-analytics-research",
            "datadog-automation": "cloud-devops-reliability",
            "deepwork-tracker": "general-utilities",
            "evomap": "ai-agents-orchestration",
            "file-organizer": "general-utilities",
            "linkedin-cdp": "sales-crm-customer-success",
            "microservices-patterns": "cloud-devops-reliability",
            "provider-key-manager": "security-privacy-legal",
            "quality-convergence-engine": "general-utilities",
            "static-code-analysis": "software-engineering",
            "subagent-driven-development": "ai-agents-orchestration",
            "vcf-annotator": "data-analytics-research",
        }
        for skill_id, category_id in expected_categories.items():
            with self.subTest(skill=skill_id):
                self.assertEqual(by_id[skill_id].category_id, category_id)

    def test_outcome_phrases_precede_weak_slug_tokens(self) -> None:
        category_id, method, details = self.builder._classify(
            "thinking-example",
            "Apply quantitative trading and portfolio risk principles.",
            self.taxonomy,
        )
        self.assertEqual(category_id, "finance-trading-markets")
        self.assertTrue(method.startswith("outcome:"))
        self.assertEqual(details["method"], "outcome")

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
        schema = json.loads(INDEX_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(index)
        known_categories = {
            category["id"]: category for category in self.taxonomy["categories"]
        }
        manifest = self.builder.load_manifest(ROOT)
        expected_assignments = {}
        for agent in manifest["agents"]:
            for level in ("required", "optional", "harnessSpecific"):
                for skill_id in agent["skills"].get(level, []):
                    expected_assignments.setdefault(skill_id, set()).add(
                        (agent["id"].upper(), level)
                    )
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
        for item in index["skills"]:
            decision = item["classification_details"]
            winner = decision["winner"]
            self.assertIn(decision["method"], {"outcome", "slug", "description", "override", "fallback"})
            self.assertIn(decision["resolution_status"], {"rule-match", "priority-tie", "override", "fallback"})
            self.assertEqual(decision["review_state"], "unreviewed")
            self.assertEqual(winner["category_id"], item["category_id"])
            self.assertEqual(winner["match_count"], len(winner["matched_signals"]))
            self.assertEqual(winner["matched_signals"], decision["matched_signals"])
            self.assertIsInstance(winner["priority"], int)
            self.assertIsInstance(decision["matched_signals"], list)
            self.assertIsInstance(decision["runner_ups"], list)
            runner_ids = [runner["category_id"] for runner in decision["runner_ups"]]
            self.assertEqual(len(runner_ids), len(set(runner_ids)))
            self.assertNotIn(item["category_id"], runner_ids)
            for runner_up in decision["runner_ups"]:
                self.assertEqual(
                    set(runner_up),
                    {"category_id", "match_count", "matched_signals", "priority", "tied_for_first"},
                )
                self.assertEqual(
                    runner_up["match_count"], len(runner_up["matched_signals"])
                )
                self.assertIn(runner_up["category_id"], known_categories)
                self.assertEqual(
                    runner_up["priority"],
                    known_categories[runner_up["category_id"]]["priority"],
                )
            tied_runners = [runner for runner in decision["runner_ups"] if runner["tied_for_first"]]
            if decision["resolution_status"] == "priority-tie":
                self.assertTrue(tied_runners)
                self.assertTrue(winner["tie_detected"])
            elif decision["resolution_status"] == "rule-match":
                self.assertFalse(tied_runners)
                self.assertFalse(winner["tie_detected"])
            if decision["method"] == "override":
                self.assertGreaterEqual(len(decision["rationale"]), 20)
                self.assertIn(decision["base_method"], {"outcome", "slug", "description", "fallback"})
                self.assertIsInstance(decision["base_candidates"], list)

            assignments = {
                (assignment["agent"], assignment["level"])
                for assignment in item["assignments"]
            }
            self.assertEqual(assignments, expected_assignments.get(item["skill_id"], set()))
            levels = {level for _agent, level in assignments}
            expected_portability = (
                "portable-required" if "required" in levels
                else "portable-optional" if "optional" in levels
                else "harness-specific" if "harnessSpecific" in levels
                else "catalog-only"
            )
            self.assertEqual(item["portability_class"], expected_portability)
            self.assertEqual(
                item["support_level"],
                "pack-required" if "required" in levels else "catalog",
            )

        by_id = {item["skill_id"]: item for item in index["skills"]}
        api_design = by_id["api-design"]["classification_details"]
        self.assertEqual(api_design["method"], "outcome")
        self.assertEqual(
            api_design["winner"]["category_id"], "software-engineering"
        )
        fallback = next(
            item for item in index["skills"]
            if item["classification_details"]["method"] == "fallback"
        )
        self.assertEqual(fallback["classification_details"]["resolution_status"], "fallback")

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

    def test_generated_write_failure_preserves_previous_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "catalog.json"
            target.write_text("previous-complete-content\n", encoding="utf-8")
            with mock.patch.object(
                self.builder.os, "replace", side_effect=OSError("simulated publish failure")
            ):
                with self.assertRaises(OSError):
                    self.builder._write_or_check(target, "new-content\n", check=False)
            self.assertEqual(
                target.read_text(encoding="utf-8"), "previous-complete-content\n"
            )
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])

    def test_index_schema_rejects_cross_field_semantic_contradictions(self) -> None:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        schema = json.loads(INDEX_SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        override = next(
            item for item in index["skills"]
            if item["classification_details"]["method"] == "override"
        )
        fallback = next(
            item for item in index["skills"]
            if item["classification_details"]["method"] == "fallback"
        )
        assigned = next(item for item in index["skills"] if item["assignments"])

        mutations = []
        forged_override = copy.deepcopy(index)
        forged_override["skills"][index["skills"].index(override)]["classification_details"]["winner"]["tie_detected"] = True
        mutations.append(forged_override)

        forged_fallback = copy.deepcopy(index)
        fallback_details = forged_fallback["skills"][index["skills"].index(fallback)]["classification_details"]
        fallback_details["winner"]["match_count"] = 1
        fallback_details["winner"]["matched_signals"] = ["fabricated"]
        fallback_details["matched_signals"] = ["fabricated"]
        mutations.append(forged_fallback)

        forged_portability = copy.deepcopy(index)
        forged_item = forged_portability["skills"][index["skills"].index(assigned)]
        forged_item["assignments"] = []
        forged_item["portability_class"] = "portable-required"
        forged_item["support_level"] = "pack-required"
        mutations.append(forged_portability)

        unscored = next(item for item in index["skills"] if item["curation"]["status"] == "unscored")
        forged_score = copy.deepcopy(index)
        forged_score["skills"][index["skills"].index(unscored)]["curation"]["score"] = 100
        mutations.append(forged_score)

        unknown_origin = next(item for item in index["skills"] if item["provenance"]["origin_kind"] == "unknown")
        forged_origin = copy.deepcopy(index)
        forged_origin["skills"][index["skills"].index(unknown_origin)]["provenance"]["review_state"] = "reviewed"
        mutations.append(forged_origin)

        for mutation in mutations:
            with self.subTest(skill=assigned["skill_id"]):
                self.assertTrue(list(validator.iter_errors(mutation)))

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
