#!/usr/bin/env python3
"""Load fail-closed Skill provenance and curation evidence contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from audit_skill_quality import inspect_skill
from repository_model import physical_skill_names


PROVENANCE_PATH = Path("config/skill-provenance.json")
PROVENANCE_SCHEMA_PATH = Path("config/skill-provenance.schema.json")
CURATION_PATH = Path("config/skill-curation.json")
CURATION_SCHEMA_PATH = Path("config/skill-curation.schema.json")

DIMENSION_MAXIMUMS = {
    "instruction_design": 15,
    "resource_integrity": 15,
    "safety_and_reversibility": 20,
    "provenance_and_license": 20,
    "outcome_evidence": 30,
}
RUNTIME_PENDING_SCORE_CAP = 84


def _load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def _validate_schema(document: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(error.message for error in errors[:5])
        raise ValueError(f"invalid {label} contract: {details}")


def _tracked_skill_files(root: Path, skill_id: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", f"skills/{skill_id}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return sorted(
            root / Path(item.decode())
            for item in result.stdout.split(b"\0")
            if item
        )
    skill_root = root / "skills" / skill_id
    return sorted(path for path in skill_root.rglob("*") if path.is_file())


def skill_tree_digest(root: Path, skill_id: str) -> str:
    """Hash the tracked working-tree content of one canonical Skill."""

    digest = hashlib.sha256()
    paths = _tracked_skill_files(root, skill_id)
    if not paths:
        raise ValueError(f"cannot digest missing Skill: {skill_id}")
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _tier(score: int) -> str:
    if score >= 95:
        return "exemplary"
    if score >= 85:
        return "recommended"
    if score >= 75:
        return "selected"
    if score >= 60:
        return "candidate"
    return "hold"


def _unique_entries(document: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for entry in document["entries"]:
        skill_id = entry["skill_id"]
        if skill_id in entries:
            raise ValueError(f"duplicate {label} entry: {skill_id}")
        entries[skill_id] = entry
    return entries


def load_contracts(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    provenance = _load_json(root / PROVENANCE_PATH)
    provenance_schema = _load_json(root / PROVENANCE_SCHEMA_PATH)
    curation = _load_json(root / CURATION_PATH)
    curation_schema = _load_json(root / CURATION_SCHEMA_PATH)
    _validate_schema(provenance, provenance_schema, "Skill provenance")
    _validate_schema(curation, curation_schema, "Skill curation")
    return provenance, curation


def _validate_semantics(
    root: Path,
    provenance_entries: dict[str, dict[str, Any]],
    curation_entries: dict[str, dict[str, Any]],
) -> None:
    canonical = physical_skill_names(root)
    unknown = sorted((set(provenance_entries) | set(curation_entries)) - canonical)
    if unknown:
        raise ValueError(f"Skill evidence references missing canonical Skills: {unknown}")

    for skill_id, review in curation_entries.items():
        score = review["score"]
        dimensions = review["dimensions"]
        if any(dimensions[key] > maximum for key, maximum in DIMENSION_MAXIMUMS.items()):
            raise ValueError(f"curation dimensions exceed score model for {skill_id}")
        if score != sum(dimensions.values()):
            raise ValueError(f"curation score does not equal dimension sum for {skill_id}")
        if review["tier"] != _tier(score):
            raise ValueError(f"curation tier does not match score for {skill_id}")
        if review["runtime_evidence"] == "pending" and score > RUNTIME_PENDING_SCORE_CAP:
            raise ValueError(f"pending runtime evidence score exceeds cap for {skill_id}")
        if review["status"] == "selected":
            provenance = provenance_entries.get(skill_id)
            if not provenance or provenance["review_state"] != "reviewed":
                raise ValueError(f"selected Skill lacks reviewed provenance: {skill_id}")
            if provenance["origin_kind"] == "unknown":
                raise ValueError(f"selected Skill has unknown origin: {skill_id}")
            if score < 75:
                raise ValueError(f"selected Skill score is below 75: {skill_id}")
            evidence = inspect_skill(root, root / "skills" / skill_id / "SKILL.md")
            if evidence.structure_status != "pass":
                raise ValueError(f"selected Skill is structurally invalid: {skill_id}")
            if evidence.execution_status == "review-required":
                raise ValueError(f"selected Skill needs execution review: {skill_id}")


def build_evidence_index(root: Path) -> dict[str, dict[str, Any]]:
    """Return provenance and curation evidence for every canonical Skill."""

    provenance, curation = load_contracts(root)
    provenance_entries = _unique_entries(provenance, "provenance")
    curation_entries = _unique_entries(curation, "curation")
    _validate_semantics(root, provenance_entries, curation_entries)

    evidence: dict[str, dict[str, Any]] = {}
    for skill_id in sorted(physical_skill_names(root)):
        provenance_entry = provenance_entries.get(skill_id)
        curation_entry = curation_entries.get(skill_id)
        current_digest = (
            skill_tree_digest(root, skill_id)
            if provenance_entry is not None or curation_entry is not None
            else None
        )
        if provenance_entry is None:
            provenance_view: dict[str, Any] = {
                "origin_kind": "unknown",
                "review_state": "unreviewed",
            }
        else:
            provenance_view = {
                key: value
                for key, value in provenance_entry.items()
                if key not in {"skill_id", "local_tree_digest"}
            }
            if (
                provenance_entry.get("local_tree_digest") is not None
                and provenance_entry["local_tree_digest"] != current_digest
            ):
                provenance_view["review_state"] = "stale"

        if curation_entry is None:
            curation_view: dict[str, Any] = {
                "status": "unscored",
                "runtime_evidence": "pending",
            }
        elif curation_entry["source_digest"] != current_digest:
            curation_view = {
                "status": "stale",
                "runtime_evidence": curation_entry["runtime_evidence"],
                "limitations": ["Skill content changed after review; score hidden until re-review."],
            }
        else:
            curation_view = {
                key: value
                for key, value in curation_entry.items()
                if key not in {"skill_id", "source_digest"}
            }
        evidence[skill_id] = {
            "provenance": provenance_view,
            "curation": curation_view,
        }
    return evidence
