import hashlib
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_skill_taxonomy_evaluation import (  # noqa: E402
    classification_metrics,
    evaluate_gold_set,
    gold_candidate_set_sha256,
    gold_label_set_sha256,
    select_candidates,
    skill_source_digest,
    wilson_lower_bound,
)


class SkillTaxonomyEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = json.loads(
            (ROOT / "catalog" / "skill-index.json").read_text(encoding="utf-8")
        )
        cls.taxonomy = json.loads(
            (ROOT / "config" / "skill-taxonomy.json").read_text(encoding="utf-8")
        )

    def test_candidate_selection_is_deterministic_stratified_and_difficulty_aware(self) -> None:
        selected = select_candidates(
            self.index,
            per_category=10,
            seed="semantic-gold-v1",
        )
        reversed_index = {**self.index, "skills": list(reversed(self.index["skills"]))}
        selected_again = select_candidates(
            reversed_index,
            per_category=10,
            seed="semantic-gold-v1",
        )
        self.assertEqual(selected, selected_again)
        self.assertEqual(len(selected), 140)
        self.assertEqual(len(selected), len({item["skill_id"] for item in selected}))

        counts = {}
        for item in selected:
            counts[item["category_id"]] = counts.get(item["category_id"], 0) + 1
        self.assertEqual(set(counts), {item["id"] for item in self.taxonomy["categories"]})
        self.assertTrue(all(count == 10 for count in counts.values()))
        split_counts = {
            split: sum(item["split"] == split for item in selected)
            for split in ("development", "validation")
        }
        self.assertEqual(split_counts, {"development": 112, "validation": 28})
        for category_id in counts:
            category_items = [
                item for item in selected if item["category_id"] == category_id
            ]
            self.assertEqual(
                sum(item["split"] == "validation" for item in category_items), 2
            )
        hard = {
            "priority-tie",
            "override",
            "fallback",
        }
        self.assertGreaterEqual(
            sum(item["resolution_status"] in hard for item in selected),
            50,
        )

    def test_metrics_and_wilson_bound_are_mathematically_stable(self) -> None:
        metrics = classification_metrics(
            expected=["a", "b", "b"],
            predicted=["a", "a", "b"],
            categories=["a", "b"],
        )
        self.assertAlmostEqual(metrics["accuracy"], 2 / 3)
        self.assertAlmostEqual(metrics["macro_f1"], 2 / 3)
        self.assertEqual(metrics["correct"], 2)
        self.assertEqual(metrics["total"], 3)
        self.assertAlmostEqual(wilson_lower_bound(80, 100), 0.7111708, places=6)
        self.assertEqual(wilson_lower_bound(0, 0), 0.0)

    def test_gold_set_and_generated_report_are_schema_valid_and_fresh(self) -> None:
        gold_path = ROOT / "config" / "skill-taxonomy-gold.json"
        gold_schema_path = ROOT / "config" / "skill-taxonomy-gold.schema.json"
        report_path = ROOT / "catalog" / "skill-taxonomy-evaluation.json"
        report_schema_path = ROOT / "config" / "skill-taxonomy-evaluation.schema.json"

        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        gold_schema = json.loads(gold_schema_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_schema = json.loads(report_schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(gold_schema)
        Draft202012Validator(
            gold_schema, format_checker=FormatChecker()
        ).validate(gold)
        Draft202012Validator.check_schema(report_schema)
        Draft202012Validator(report_schema).validate(report)

        self.assertGreaterEqual(len(gold["labels"]), 140)
        self.assertEqual(
            len(gold["labels"]),
            len({item["skill_id"] for item in gold["labels"]}),
        )
        known_categories = {item["id"] for item in self.taxonomy["categories"]}
        gold_categories = {item["expected_category"] for item in gold["labels"]}
        self.assertEqual(gold_categories, known_categories)
        self.assertEqual(len(gold["labels"]), 140)
        self.assertEqual(
            sum(item["split"] == "development" for item in gold["labels"]),
            112,
        )
        self.assertEqual(
            sum(item["split"] == "validation" for item in gold["labels"]),
            28,
        )
        self.assertEqual(
            gold["sampling"]["candidateSetSha256"],
            gold_candidate_set_sha256(gold["labels"]),
        )
        self.assertEqual(
            gold["annotation"]["labelSetSha256"],
            gold_label_set_sha256(gold["labels"]),
        )
        self.assertTrue(
            all(len(item["rationale"].strip()) >= 20 for item in gold["labels"])
        )
        for item in gold["labels"]:
            self.assertEqual(
                item["source_sha256"],
                skill_source_digest(ROOT / "skills" / item["skill_id"] / "SKILL.md"),
            )

        evaluated = evaluate_gold_set(ROOT, gold, self.index, self.taxonomy)
        self.assertEqual(report, evaluated)
        self.assertGreaterEqual(report["metrics"]["accuracy"], 0.80)
        self.assertGreaterEqual(report["metrics"]["macro_f1"], 0.80)
        self.assertGreaterEqual(report["splits"]["validation"]["accuracy"], 0.75)
        self.assertTrue(report["gates"]["validationAccuracyAtLeast75"])
        self.assertTrue(report["gates"]["validationMacroF1AtLeast75"])
        self.assertTrue(
            report["gates"]["validationAllCategoriesRepresented"]
        )
        self.assertGreaterEqual(report["reviewedSetAgreementScore"], 80)
        self.assertFalse(report["runtimeEvidenceIncluded"])
        self.assertGreater(
            report["splits"]["validation"]["accuracyWilsonLower95"], 0
        )
        self.assertEqual(
            report["goldSetSha256"],
            hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        )

    def test_gold_contract_rejects_sample_growth_split_changes_and_label_drift(self) -> None:
        gold = json.loads(
            (ROOT / "config" / "skill-taxonomy-gold.json").read_text(
                encoding="utf-8"
            )
        )

        expanded = deepcopy(gold)
        expanded["labels"].append(deepcopy(expanded["labels"][0]))
        expanded["labels"][-1]["skill_id"] = "not-a-real-gold-skill"
        with self.assertRaisesRegex(ValueError, "exactly 140"):
            evaluate_gold_set(ROOT, expanded, self.index, self.taxonomy)

        moved = deepcopy(gold)
        moved["labels"][0]["split"] = "validation"
        with self.assertRaisesRegex(ValueError, "candidate set digest"):
            evaluate_gold_set(ROOT, moved, self.index, self.taxonomy)

        relabeled_baseline = deepcopy(gold)
        relabeled_baseline["labels"][0]["baseline_predicted_category"] = (
            "general-utilities"
        )
        with self.assertRaisesRegex(ValueError, "candidate set digest"):
            evaluate_gold_set(
                ROOT, relabeled_baseline, self.index, self.taxonomy
            )

        relabeled_gold = deepcopy(gold)
        relabeled_gold["labels"][0]["expected_category"] = "general-utilities"
        with self.assertRaisesRegex(ValueError, "label set digest"):
            evaluate_gold_set(ROOT, relabeled_gold, self.index, self.taxonomy)

    def test_failed_validation_gate_caps_the_public_score(self) -> None:
        gold = json.loads(
            (ROOT / "config" / "skill-taxonomy-gold.json").read_text(
                encoding="utf-8"
            )
        )
        validation_ids = {
            item["skill_id"]
            for item in gold["labels"]
            if item["split"] == "validation"
        }
        degraded_index = deepcopy(self.index)
        for item in degraded_index["skills"]:
            if item["skill_id"] in validation_ids:
                item["category_id"] = "general-utilities"
        report = evaluate_gold_set(
            ROOT, gold, degraded_index, self.taxonomy
        )
        self.assertFalse(report["gates"]["passed"])
        self.assertFalse(report["gates"]["validationAccuracyAtLeast75"])
        self.assertLessEqual(report["reviewedSetAgreementScore"], 79)


if __name__ == "__main__":
    unittest.main()
