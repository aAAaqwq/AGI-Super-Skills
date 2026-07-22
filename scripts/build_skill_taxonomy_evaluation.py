#!/usr/bin/env python3
"""Build deterministic semantic evaluation evidence from reviewed Skill labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


GOLD_PATH = Path("config/skill-taxonomy-gold.json")
INDEX_PATH = Path("catalog/skill-index.json")
TAXONOMY_PATH = Path("config/skill-taxonomy.json")
REPORT_PATH = Path("catalog/skill-taxonomy-evaluation.json")


def _stable_hash(seed: str, category_id: str, skill_id: str) -> str:
    return hashlib.sha256(
        f"{seed}\0{category_id}\0{skill_id}".encode("utf-8")
    ).hexdigest()


def select_candidates(
    index: dict[str, Any], *, per_category: int, seed: str
) -> list[dict[str, str]]:
    """Select a deterministic, category-balanced, difficulty-aware review sample."""

    if per_category < 1:
        raise ValueError("per_category must be positive")
    difficulty = {
        "priority-tie": 0,
        "override": 1,
        "fallback": 2,
        "rule-match": 4,
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for skill in index.get("skills", []):
        grouped[skill["category_id"]].append(skill)

    selected: list[dict[str, str]] = []
    category_ids = [item["id"] for item in index.get("categories", [])]
    for category_id in category_ids:
        candidates = grouped.get(category_id, [])
        if len(candidates) < per_category:
            raise ValueError(
                f"category {category_id} has only {len(candidates)} candidates"
            )
        ranked = sorted(
            candidates,
            key=lambda item: (
                difficulty.get(
                    item["classification_details"]["resolution_status"], 3
                ),
                0 if item.get("description_status") == "needs-review" else 1,
                _stable_hash(seed, category_id, item["skill_id"]),
            ),
        )
        chosen = ranked[:per_category]
        validation_count = max(1, per_category // 5)
        validation_ids = {
            item["skill_id"]
            for item in sorted(
                chosen,
                key=lambda item: _stable_hash(
                    "semantic-gold-holdout-v1", category_id, item["skill_id"]
                ),
            )[:validation_count]
        }
        for item in chosen:
            selected.append(
                {
                    "skill_id": item["skill_id"],
                    "category_id": category_id,
                    "resolution_status": item["classification_details"][
                        "resolution_status"
                    ],
                    "description_status": item["description_status"],
                    "split": (
                        "validation"
                        if item["skill_id"] in validation_ids
                        else "development"
                    ),
                }
            )
    return selected


def gold_candidate_set_sha256(labels: Iterable[dict[str, Any]]) -> str:
    """Hash the frozen membership, baseline route, and published split."""

    manifest = sorted(
        (
            {
                "skill_id": item["skill_id"],
                "baseline_predicted_category": item[
                    "baseline_predicted_category"
                ],
                "baseline_resolution_status": item[
                    "baseline_resolution_status"
                ],
                "split": item["split"],
            }
            for item in labels
        ),
        key=lambda item: item["skill_id"],
    )
    payload = json.dumps(
        manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def gold_label_set_sha256(labels: Iterable[dict[str, Any]]) -> str:
    """Hash the reviewed annotation evidence independently of sample routing."""

    fields = (
        "skill_id",
        "expected_category",
        "rationale",
        "confidence",
        "reviewers",
        "review_status",
        "reviewed_at",
        "source_sha256",
    )
    annotations = sorted(
        ({field: item[field] for field in fields} for item in labels),
        key=lambda item: item["skill_id"],
    )
    payload = json.dumps(
        annotations, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_frozen_baseline(root: Path, gold: dict[str, Any]) -> dict[str, Any]:
    revision = gold["sampling"]["baseCommit"]
    result = subprocess.run(
        ["git", "show", f"{revision}:catalog/skill-index.json"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"Gold Set base commit is unavailable: {revision}")
    actual_digest = hashlib.sha256(result.stdout).hexdigest()
    if actual_digest != gold["sampling"]["baseCatalogSha256"]:
        raise ValueError("Gold Set base catalog digest does not match")
    return json.loads(result.stdout.decode("utf-8"))


def _validate_gold_contract(
    root: Path, gold: dict[str, Any], categories: list[str]
) -> None:
    labels = gold.get("labels", [])
    if len(labels) != 140:
        raise ValueError("Gold Set must contain exactly 140 labels")
    skill_ids = [item["skill_id"] for item in labels]
    if len(skill_ids) != len(set(skill_ids)):
        raise ValueError("Gold Set skill IDs must be unique")

    actual_digest = gold_candidate_set_sha256(labels)
    expected_digest = gold.get("sampling", {}).get("candidateSetSha256")
    if actual_digest != expected_digest:
        raise ValueError("Gold Set candidate set digest does not match")
    actual_label_digest = gold_label_set_sha256(labels)
    expected_label_digest = gold.get("annotation", {}).get("labelSetSha256")
    if actual_label_digest != expected_label_digest:
        raise ValueError("Gold Set label set digest does not match")

    baseline = _load_frozen_baseline(root, gold)
    frozen_sample = select_candidates(
        baseline,
        per_category=gold["sampling"]["perPredictedCategory"],
        seed=gold["sampling"]["seed"],
    )
    expected_candidates = {
        item["skill_id"]: (
            item["category_id"],
            item["resolution_status"],
            item["split"],
        )
        for item in frozen_sample
    }
    actual_candidates = {
        item["skill_id"]: (
            item["baseline_predicted_category"],
            item["baseline_resolution_status"],
            item["split"],
        )
        for item in labels
    }
    if actual_candidates != expected_candidates:
        raise ValueError("Gold Set candidates do not match the frozen baseline sample")

    by_baseline_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label in labels:
        by_baseline_category[label["baseline_predicted_category"]].append(label)
        reviewers = label["reviewers"]
        status = label["review_status"]
        required_reviewers = {
            "primary": 1,
            "cross-reviewed": 2,
            "adjudicated": 3,
        }[status]
        if len(reviewers) < required_reviewers:
            raise ValueError(
                f"Gold label lacks review evidence: {label['skill_id']}"
            )
        needs_cross_review = (
            label["confidence"] != "high"
            or label["expected_category"]
            != label["baseline_predicted_category"]
        )
        if needs_cross_review and status == "primary":
            raise ValueError(
                f"Gold label requires cross-review: {label['skill_id']}"
            )

    if set(by_baseline_category) != set(categories):
        raise ValueError("Gold Set baseline category coverage does not match taxonomy")
    for category_id, category_labels in by_baseline_category.items():
        split_counts = {
            split: sum(item["split"] == split for item in category_labels)
            for split in ("development", "validation")
        }
        if len(category_labels) != 10 or split_counts != {
            "development": 8,
            "validation": 2,
        }:
            raise ValueError(
                "Gold Set requires 8 development and 2 validation labels "
                f"for baseline category {category_id}"
            )


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def classification_metrics(
    *, expected: Iterable[str], predicted: Iterable[str], categories: Iterable[str]
) -> dict[str, Any]:
    expected_values = list(expected)
    predicted_values = list(predicted)
    category_values = list(categories)
    if len(expected_values) != len(predicted_values):
        raise ValueError("expected and predicted lengths differ")
    if len(category_values) != len(set(category_values)):
        raise ValueError("categories must be unique")

    per_category: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for category_id in category_values:
        true_positive = sum(
            actual == category_id and guess == category_id
            for actual, guess in zip(expected_values, predicted_values, strict=True)
        )
        false_positive = sum(
            actual != category_id and guess == category_id
            for actual, guess in zip(expected_values, predicted_values, strict=True)
        )
        false_negative = sum(
            actual == category_id and guess != category_id
            for actual, guess in zip(expected_values, predicted_values, strict=True)
        )
        precision = _safe_ratio(true_positive, true_positive + false_positive)
        recall = _safe_ratio(true_positive, true_positive + false_negative)
        f1 = _safe_ratio(2 * precision * recall, precision + recall)
        f1_values.append(f1)
        per_category[category_id] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": sum(value == category_id for value in expected_values),
            "predicted": sum(value == category_id for value in predicted_values),
        }

    correct = sum(
        actual == guess
        for actual, guess in zip(expected_values, predicted_values, strict=True)
    )
    accuracy = _safe_ratio(correct, len(expected_values))
    macro_f1 = _safe_ratio(
        sum(f1_values),
        len(category_values),
    )
    return {
        "total": len(expected_values),
        "correct": correct,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_category": per_category,
    }


def wilson_lower_bound(successes: int, total: int, z: float = 1.959963984540054) -> float:
    if total <= 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt(
        (proportion * (1 - proportion) + z * z / (4 * total)) / total
    )
    return (centre - margin) / denominator


def skill_source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_gold_set(
    root: Path,
    gold: dict[str, Any],
    index: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    root = root.resolve()
    categories = [item["id"] for item in taxonomy["categories"]]
    _validate_gold_contract(root, gold, categories)
    known_categories = set(categories)
    indexed = {item["skill_id"]: item for item in index["skills"]}
    expected: list[str] = []
    predicted: list[str] = []
    split_values: list[str] = []
    errors: list[dict[str, str]] = []

    for label in gold["labels"]:
        skill_id = label["skill_id"]
        if skill_id not in indexed:
            raise ValueError(f"gold label references missing skill: {skill_id}")
        if label["expected_category"] not in known_categories:
            raise ValueError(f"gold label references unknown category: {skill_id}")
        current_digest = skill_source_digest(root / "skills" / skill_id / "SKILL.md")
        if label["source_sha256"] != current_digest:
            raise ValueError(f"gold label is stale: {skill_id}")
        actual = label["expected_category"]
        guess = indexed[skill_id]["category_id"]
        expected.append(actual)
        predicted.append(guess)
        split_values.append(label["split"])
        if actual != guess:
            errors.append(
                {
                    "skill_id": skill_id,
                    "expected_category": actual,
                    "predicted_category": guess,
                    "split": label["split"],
                }
            )

    metrics = classification_metrics(
        expected=expected,
        predicted=predicted,
        categories=categories,
    )
    split_metrics = {}
    for split in ("development", "validation"):
        positions = [
            index for index, value in enumerate(split_values) if value == split
        ]
        split_result = classification_metrics(
            expected=[expected[index] for index in positions],
            predicted=[predicted[index] for index in positions],
            categories=categories,
        )
        split_metrics[split] = {
            **split_result,
            "accuracyWilsonLower95": round(
                wilson_lower_bound(
                    split_result["correct"], split_result["total"]
                ),
                6,
            ),
        }
    accuracy_gate = metrics["accuracy"] >= 0.80
    macro_f1_gate = metrics["macro_f1"] >= 0.80
    sample_gate = metrics["total"] >= 140
    coverage_gate = all(
        item["support"] > 0 for item in metrics["per_category"].values()
    )
    validation_gate = split_metrics["validation"]["accuracy"] >= 0.75
    validation_macro_f1_gate = (
        split_metrics["validation"]["macro_f1"] >= 0.75
    )
    validation_coverage_gate = all(
        item["support"] > 0
        for item in split_metrics["validation"]["per_category"].values()
    )
    raw_score = math.floor(
        100 * min(float(metrics["accuracy"]), float(metrics["macro_f1"]))
    )
    passed = (
        sample_gate
        and accuracy_gate
        and macro_f1_gate
        and coverage_gate
        and validation_gate
        and validation_macro_f1_gate
        and validation_coverage_gate
    )
    semantic_score = raw_score if passed else min(raw_score, 79)
    gold_path = root / GOLD_PATH
    return {
        "$schema": "../config/skill-taxonomy-evaluation.schema.json",
        "schemaVersion": 1,
        "sampleSize": metrics["total"],
        "categoryCount": len(categories),
        "goldSetSha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        "annotationMode": gold["annotation"]["mode"],
        "humanApproved": gold["annotation"]["humanApproved"],
        "metrics": {
            **metrics,
            "accuracyWilsonLower95": round(
                wilson_lower_bound(metrics["correct"], metrics["total"]), 6
            ),
        },
        "splits": split_metrics,
        "gates": {
            "sampleAtLeast140": sample_gate,
            "accuracyAtLeast80": accuracy_gate,
            "macroF1AtLeast80": macro_f1_gate,
            "allCategoriesRepresented": coverage_gate,
            "validationAccuracyAtLeast75": validation_gate,
            "validationMacroF1AtLeast75": validation_macro_f1_gate,
            "validationAllCategoriesRepresented": validation_coverage_gate,
            "passed": passed,
        },
        "reviewedSetAgreementScore": semantic_score,
        "scoreSemantics": "floored minimum of exact accuracy and macro-F1 on the fixed, manually reviewed Gold Set; not an inventory-wide confidence interval",
        "runtimeEvidenceIncluded": False,
        "errors": sorted(errors, key=lambda item: item["skill_id"]),
    }


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--shard", type=int, choices=range(1, 5))
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    index = json.loads((root / INDEX_PATH).read_text(encoding="utf-8"))
    if arguments.sample:
        candidates = select_candidates(
            index, per_category=10, seed="semantic-gold-v1"
        )
        if arguments.shard:
            candidates = [
                item
                for position, item in enumerate(candidates)
                if position % 4 == arguments.shard - 1
            ]
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return 0

    gold = json.loads((root / GOLD_PATH).read_text(encoding="utf-8"))
    taxonomy = json.loads((root / TAXONOMY_PATH).read_text(encoding="utf-8"))
    report = evaluate_gold_set(root, gold, index, taxonomy)
    content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    report_path = root / REPORT_PATH
    if arguments.check:
        if not report_path.is_file() or report_path.read_text(encoding="utf-8") != content:
            print(f"STALE {report_path}")
            return 1
    else:
        _write_atomic(report_path, content)
        print(f"WROTE {report_path}")
    return 0 if report["gates"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
