#!/usr/bin/env python3
"""Generate deterministic structural evidence for canonical Skill entrypoints."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from repository_model import physical_skill_names


FRONTMATTER_END = re.compile(r"(?m)^---\s*$")
LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
PERSONAL_PATH = re.compile(r"(?:/Users/[^/\s]+|/home/[^/\s]+)")
RESOURCE_DIRS = ("references", "scripts", "assets")
TEST_NAMES = re.compile(r"(?:^|[-_.])(test|tests|spec|fixture)(?:[-_.]|$)", re.I)
EXECUTABLE_TEST_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx"}
_TRACKED_FILES_CACHE: dict[Path, dict[str, tuple[Path, ...]] | None] = {}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class SkillEvidence:
    skill_id: str
    path: str
    structure_status: str
    disclosure_status: str
    execution_status: str
    issues: tuple[str, ...]


def canonical_skill_paths(root: Path) -> list[Path]:
    return [root / "skills" / skill_id / "SKILL.md" for skill_id in sorted(physical_skill_names(root))]


def tracked_skill_files(root: Path, skill_root: Path) -> list[Path]:
    root = root.resolve()
    skill_root = skill_root.resolve()
    if root not in _TRACKED_FILES_CACHE:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "skills"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            grouped: dict[str, list[Path]] = {}
            for item in result.stdout.split(b"\0"):
                if not item:
                    continue
                path = root / Path(item.decode())
                relative = path.relative_to(root)
                if len(relative.parts) >= 2 and relative.parts[0] == "skills":
                    grouped.setdefault(relative.parts[1], []).append(path)
            _TRACKED_FILES_CACHE[root] = {
                skill_id: tuple(sorted(paths)) for skill_id, paths in grouped.items()
            }
        else:
            _TRACKED_FILES_CACHE[root] = None
    tracked = _TRACKED_FILES_CACHE[root]
    if tracked is not None:
        return list(tracked.get(skill_root.name, ()))
    return sorted(
        item
        for item in skill_root.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and item.suffix.lower() not in {".pyc", ".pyo"}
    )


def frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    issues: list[str] = []
    if not text.startswith("---\n"):
        return {}, ["missing-frontmatter"]
    endings = list(FRONTMATTER_END.finditer(text, 4))
    if not endings:
        return {}, ["unclosed-frontmatter"]
    block = text[4 : endings[0].start()]
    try:
        document = yaml.load(block, Loader=UniqueKeyLoader)
    except yaml.YAMLError:
        return {}, ["invalid-frontmatter-yaml"]
    if not isinstance(document, dict):
        return {}, ["invalid-frontmatter-mapping"]
    values: dict[str, str] = {}
    for key in ("name", "description"):
        value = document.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"missing-{key}")
            continue
        values[key] = re.sub(r"\s+", " ", value).strip()
    return values, issues


def local_link_issues(root: Path, path: Path, text: str) -> list[str]:
    issues = []
    root = root.resolve()
    for target in LINK.findall(text):
        target = target.strip().split(maxsplit=1)[0].strip("<>")
        if target.lower() in {"url", "path", "link"}:
            continue
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target_path = (path.parent / target.split("#", 1)[0]).resolve()
        if root != target_path and root not in target_path.parents:
            issues.append("link-outside-repository")
            break
        if not target_path.exists():
            issues.append("unresolved-local-link")
            break
    return issues


def tree_integrity_issues(root: Path, skill_root: Path) -> list[str]:
    issues: list[str] = []
    for path in tracked_skill_files(root, skill_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if PERSONAL_PATH.search(text):
            issues.append("personal-absolute-path")
        if path.suffix.lower() in {".md", ".mdx"}:
            issues.extend(local_link_issues(root, path, text))
    return sorted(set(issues))


def resource_issues(root: Path, path: Path, text: str) -> tuple[list[str], bool, bool]:
    issues: list[str] = []
    has_scripts = False
    has_tests = False
    for directory in RESOURCE_DIRS:
        resource_root = (path.parent / directory).resolve()
        if not resource_root.is_dir():
            continue
        files = [item for item in tracked_skill_files(root, path.parent) if resource_root in item.parents]
        if directory == "scripts" and files:
            has_scripts = True
        for item in files:
            relative = item.relative_to(path.parent.resolve()).as_posix()
            if relative not in text and item.name not in text:
                issues.append(f"unmentioned-{directory}")
                break
            if TEST_NAMES.search(item.name) and item.suffix.lower() in EXECUTABLE_TEST_SUFFIXES:
                has_tests = True
    for item in path.parent.iterdir():
        if item.is_file() and TEST_NAMES.search(item.name) and item.suffix.lower() in EXECUTABLE_TEST_SUFFIXES:
            has_tests = True
    return issues, has_scripts, has_tests


def inspect_skill(root: Path, path: Path) -> SkillEvidence:
    skill_id = path.parent.name
    relative = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return SkillEvidence(skill_id, relative, "invalid", "warn", "review-required", ("invalid-utf8",))

    metadata, issues = frontmatter(text)
    if metadata.get("name") and metadata["name"] != skill_id:
        issues.append("name-folder-mismatch")
    issues.extend(tree_integrity_issues(root, path.parent))
    resource_findings, has_scripts, has_tests = resource_issues(root, path, text)
    issues.extend(resource_findings)
    if len(text.splitlines()) > 500:
        issues.append("over-500-lines")
    description = metadata.get("description", "")
    if description and len(description) > 180:
        issues.append("description-over-180")
    if description and not re.search(r"(?i)\b(use|when|for)\b|适用|用于|触发", description):
        issues.append("description-missing-trigger")
    if has_scripts and not has_tests:
        issues.append("scripts-without-test-evidence")

    structural = {
        "missing-frontmatter",
        "unclosed-frontmatter",
        "missing-name",
        "missing-description",
        "invalid-frontmatter-yaml",
        "invalid-frontmatter-mapping",
        "invalid-utf8",
        "name-folder-mismatch",
        "unresolved-local-link",
        "link-outside-repository",
    }
    disclosure = {
        "over-500-lines",
        "description-over-180",
        "description-missing-trigger",
        "unmentioned-references",
        "unmentioned-scripts",
        "unmentioned-assets",
        "personal-absolute-path",
    }
    execution = {"scripts-without-test-evidence", "unmentioned-scripts"}
    issue_set = set(issues)
    return SkillEvidence(
        skill_id=skill_id,
        path=relative,
        structure_status="invalid" if issue_set & structural else "pass",
        disclosure_status="warn" if issue_set & disclosure else "pass",
        execution_status=(
            "review-required"
            if issue_set & execution
            else "test-evidence-present"
            if has_scripts
            else "not-applicable"
        ),
        issues=tuple(sorted(issue_set)),
    )


def build_report(root: Path) -> dict[str, object]:
    evidence = [inspect_skill(root, path) for path in canonical_skill_paths(root)]
    issue_counts: dict[str, int] = {}
    for item in evidence:
        for issue in item.issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    summary = {
        "inventoryCount": len(evidence),
        "structureInvalid": sum(item.structure_status == "invalid" for item in evidence),
        "disclosureWarnings": sum(item.disclosure_status == "warn" for item in evidence),
        "executionReviewRequired": sum(item.execution_status == "review-required" for item in evidence),
        "issueCounts": dict(sorted(issue_counts.items())),
    }
    return {
        "schemaVersion": 1,
        "scope": "deterministic-structural-evidence-not-semantic-verification",
        "summary": summary,
        "skills": [asdict(item) for item in evidence if item.issues],
    }


def baseline_regressions(report: dict[str, object], baseline: dict[str, object]) -> list[str]:
    summary = report["summary"]
    assert isinstance(summary, dict)
    errors: list[str] = []
    for key in ("structureInvalid", "disclosureWarnings", "executionReviewRequired"):
        maximum = baseline.get(key)
        actual = summary.get(key)
        if isinstance(maximum, int) and isinstance(actual, int) and actual > maximum:
            errors.append(f"{key} regressed: maximum {maximum}, got {actual}")
    issue_counts = summary.get("issueCounts", {})
    maximum_issues = baseline.get("issueCounts", {})
    if isinstance(issue_counts, dict) and isinstance(maximum_issues, dict):
        unexpected = sorted(set(issue_counts) - set(maximum_issues))
        errors.extend(f"unregistered issue type: {issue}" for issue in unexpected)
        for issue, maximum in maximum_issues.items():
            actual = issue_counts.get(issue, 0)
            if isinstance(maximum, int) and isinstance(actual, int) and actual > maximum:
                errors.append(f"{issue} regressed: maximum {maximum}, got {actual}")
    return errors


def validate_baseline(baseline: object) -> list[str]:
    if not isinstance(baseline, dict):
        return ["baseline must be a JSON object"]
    errors: list[str] = []
    allowed = {
        "$schema",
        "schemaVersion",
        "scope",
        "structureInvalid",
        "disclosureWarnings",
        "executionReviewRequired",
        "issueCounts",
    }
    unexpected = sorted(set(baseline) - allowed)
    errors.extend(f"unexpected baseline key: {key}" for key in unexpected)
    if baseline.get("$schema") != "./skill-quality-baseline.schema.json":
        errors.append("baseline $schema must reference ./skill-quality-baseline.schema.json")
    if baseline.get("schemaVersion") != 1:
        errors.append("baseline schemaVersion must equal 1")
    if not isinstance(baseline.get("scope"), str) or not baseline["scope"].strip():
        errors.append("baseline scope must be a non-empty string")
    for key in ("structureInvalid", "disclosureWarnings", "executionReviewRequired"):
        value = baseline.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"baseline {key} must be a non-negative integer")
    counts = baseline.get("issueCounts")
    if not isinstance(counts, dict) or not counts:
        errors.append("baseline issueCounts must be a non-empty object")
    elif any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts.values()):
        errors.append("baseline issueCounts values must be non-negative integers")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("catalog/skill-quality.json"))
    parser.add_argument("--baseline", type=Path, default=Path("config/skill-quality-baseline.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    baseline_path = args.baseline if args.baseline.is_absolute() else root / args.baseline
    report = build_report(root)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(f"Skill quality report is stale: {output}", file=sys.stderr)
            return 1
        if not baseline_path.is_file():
            print(f"Skill quality baseline is missing: {baseline_path}", file=sys.stderr)
            return 1
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            print(f"Skill quality baseline is unreadable: {error}", file=sys.stderr)
            return 1
        baseline_errors = validate_baseline(baseline)
        regressions = baseline_regressions(report, baseline) if not baseline_errors else []
        if baseline_errors or regressions:
            for regression in baseline_errors + regressions:
                print(f"Skill quality baseline: {regression}", file=sys.stderr)
            return 1
        print(f"Skill quality report is current: {output}")
        return 0
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
