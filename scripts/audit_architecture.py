#!/usr/bin/env python3
"""Audit machine-readable repository architecture and skill-classification contracts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CONTRACT_PATH = Path("config/repository-architecture.json")
SCHEMA_PATH = Path("config/repository-architecture.schema.json")
EXPECTED_VOCABULARY = {
    "Module", "Interface", "Implementation", "Depth",
    "Seam", "Adapter", "Leverage", "Locality",
}
ROLES = {
    "authored-authority", "authored-source", "generated-output",
    "distribution-adapter", "implementation", "evidence", "public-navigation",
    "governance",
}
HARD_TAXONOMY_CEILINGS = {
    "maxFallbackRatio": 0.06,
    "maxOverrideRatio": 0.03,
    "maxMultipleCategoryMatchRatio": 0.24,
    "maxPriorityResolvedTieRatio": 0.20,
    "maxNeedsReviewRatio": 0.06,
}
HARD_REQUIRED_ENTRYPOINTS = {
    "README.md", "README_CN.md", "AGENTS.md", "ARCHITECTURE.md", "CONTEXT.md",
    "CHARTER.md", "COLLABORATION.md", "skills/README.md", "catalog/README.md",
    "agents/README.md", "starter-kits/README.md",
}
HARD_REQUIRED_DECISIONS = {
    "docs/adr/0001-canonical-inventory-and-generated-outputs.md",
    "docs/adr/0002-generic-workspace-and-curated-distributions.md",
    "docs/adr/0003-structural-evidence-and-runtime-receipts.md",
    "docs/adr/0004-reviewed-skill-taxonomy-evaluation.md",
}
CRITICAL_PATH_CONTRACTS: dict[str, dict[str, Any]] = {
    "skills": {"role": "authored-authority", "module": "skill-library", "authority": True},
    "config/team-manifest.json": {"role": "authored-authority", "module": "team-composition", "authority": True},
    "config/skill-taxonomy.json": {"role": "authored-authority", "module": "catalog-discovery", "authority": True},
    "config/skill-taxonomy-gold.json": {"role": "authored-authority", "module": "catalog-discovery", "authority": True},
    "config/skill-taxonomy-gold.schema.json": {"role": "authored-source", "module": "catalog-discovery", "authority": False},
    "config/skill-taxonomy-evaluation.schema.json": {"role": "authored-source", "module": "catalog-discovery", "authority": False},
    "docs/skill-taxonomy-gold-set.md": {"role": "authored-source", "module": "catalog-discovery", "authority": False},
    "scripts/build_skill_taxonomy_evaluation.py": {"role": "implementation", "module": "catalog-discovery", "authority": False},
    "config/repository-architecture.json": {"role": "authored-authority", "module": "governance-memory", "authority": True},
    "install.sh": {"role": "implementation", "module": "safe-installation", "authority": False},
    "catalog": {"role": "generated-output", "module": "catalog-discovery", "authority": False, "generatedBy": "scripts/build_skill_catalog.py", "verify": "npm run check:skills"},
    "catalog/skill-taxonomy-evaluation.json": {"role": "generated-output", "module": "catalog-discovery", "authority": False, "generatedBy": "scripts/build_skill_taxonomy_evaluation.py", "verify": "npm run check:taxonomy-evaluation"},
    "catalog/skill-quality.json": {"role": "generated-output", "module": "verification-evidence", "authority": False, "generatedBy": "scripts/audit_skill_quality.py", "verify": "npm run check:skill-quality"},
    "docs/data/repo-stats.json": {"role": "generated-output", "module": "public-navigation", "authority": False, "generatedBy": "scripts/build_site_data.py", "verify": "npm run test:repository"},
    "docs/data/star-history.json": {"role": "generated-output", "module": "public-navigation", "authority": False, "generatedBy": "scripts/build_site_data.py", "verify": "npm run test:repository"},
    "docs/assets/star-history.svg": {"role": "generated-output", "module": "public-navigation", "authority": False, "generatedBy": "scripts/build_site_data.py", "verify": "npm run test:repository"},
    "docs/data/verification-receipt.json": {"role": "evidence", "module": "verification-evidence", "authority": False},
    ".codex-plugin": {"role": "distribution-adapter", "module": "distribution-adapters", "authority": False, "evidenceStatus": "legacy", "recommendation": "legacy"},
    "plugins/agi-super-team-codex": {"role": "distribution-adapter", "module": "distribution-adapters", "authority": False, "evidenceStatus": "manifest", "recommendation": "recommended"},
    "gemini-extension.json": {"role": "distribution-adapter", "module": "distribution-adapters", "authority": False, "evidenceStatus": "pending", "recommendation": "available"},
}
SCORED_WEIGHTS = {
    "ownershipCoverage": 20,
    "authorityIntegrity": 20,
    "generatedLineage": 15,
    "adapterBoundaries": 10,
    "schemaAndDecisionIntegrity": 15,
    "taxonomyDebt": 10,
    "installedWorkspaceSeam": 10,
}


def _ratio(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def schema_issues(root: Path, contract: dict[str, Any]) -> list[str]:
    """Validate both the schema document and its instance using draft 2020-12."""

    try:
        schema = json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        return [f"architecture schema is invalid: {error}"]
    validator = Draft202012Validator(schema)
    issues = []
    for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        issues.append(f"architecture schema violation at {location}: {error.message}")
    return issues


def _ownership_by_path(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("path")): item
        for item in contract.get("pathOwnership", [])
        if isinstance(item, dict) and item.get("path")
    }


def _effective_owner(path: str, ownership: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        prefix for prefix in ownership
        if path == prefix or path.startswith(prefix + "/")
    ]
    if not candidates:
        return None
    longest = max(len(prefix) for prefix in candidates)
    effective = [prefix for prefix in candidates if len(prefix) == longest]
    return ownership[effective[0]] if len(effective) == 1 else None


def _declared_npm_check(root: Path, command: Any) -> bool:
    if not isinstance(command, str):
        return False
    match = re.fullmatch(r"npm run ([a-z0-9:-]+)", command)
    if not match:
        return False
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    return match.group(1) in package.get("scripts", {})


def validate_contract(root: Path, contract: dict[str, Any]) -> list[str]:
    """Return stable diagnostics for the architecture document itself."""

    issues: list[str] = schema_issues(root, contract)
    if contract.get("$schema") != "./repository-architecture.schema.json":
        issues.append("contract must reference ./repository-architecture.schema.json")
    if contract.get("schemaVersion") != 1:
        issues.append("contract schemaVersion must equal 1")
    vocabulary = contract.get("vocabulary", {})
    if set(vocabulary) != EXPECTED_VOCABULARY:
        issues.append("contract vocabulary must define the shared eight architecture terms")
    elif not all(isinstance(value, str) and len(value) >= 24 for value in vocabulary.values()):
        issues.append("each architecture vocabulary definition must be a descriptive string")

    modules = contract.get("modules", [])
    module_ids = [item.get("id") for item in modules if isinstance(item, dict)]
    if len(module_ids) != len(set(module_ids)):
        issues.append("module ids must be unique")
    known_modules = set(module_ids)
    for module in modules:
        module_id = module.get("id", "<missing>")
        for field in ("interface", "implementations", "ownershipPrefixes", "depth", "seams", "leverage", "locality"):
            if not module.get(field):
                issues.append(f"module {module_id} requires {field}")
        for implementation in module.get("implementations", []):
            if not (root / implementation).exists():
                issues.append(f"module {module_id} implementation does not exist: {implementation}")
        unknown_seams = set(module.get("seams", [])) - known_modules
        if unknown_seams:
            issues.append(f"module {module_id} references unknown seams: {', '.join(sorted(unknown_seams))}")

    ownership = contract.get("pathOwnership", [])
    paths = [item.get("path") for item in ownership if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        issues.append("path ownership must be unique")
    by_path = _ownership_by_path(contract)
    modules_by_id = {
        item.get("id"): item for item in modules if isinstance(item, dict)
    }

    for item in ownership:
        path = item.get("path", "<missing>")
        role = item.get("role")
        if not (root / path).exists():
            issues.append(f"owned path does not exist: {path}")
        if role not in ROLES:
            issues.append(f"unknown path role for {path}: {role}")
        if item.get("module") not in known_modules:
            issues.append(f"path {path} references unknown module")
        else:
            prefixes = modules_by_id[item["module"]].get("ownershipPrefixes", [])
            if not any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes):
                issues.append(f"path {path} is outside module ownership scope: {item['module']}")
        expected_authority = role == "authored-authority"
        if item.get("authority") is not expected_authority:
            issues.append(
                f"{path}: authority must be true only for role authored-authority"
            )
        if role == "generated-output":
            if not item.get("generatedBy"):
                issues.append(f"{path}: generated output requires generatedBy")
            elif not re.fullmatch(r"scripts/[a-z0-9_]+\.py", str(item["generatedBy"])):
                issues.append(f"{path}: generatedBy must be a repository script")
            elif not (root / item["generatedBy"]).is_file():
                issues.append(f"{path}: generatedBy script does not exist")
            if not _declared_npm_check(root, item.get("verify")):
                issues.append(f"{path}: generated output requires verify")
        if role == "distribution-adapter":
            if item.get("evidenceStatus") not in {"manifest", "pending", "legacy"}:
                issues.append(f"{path}: distribution adapter requires conservative evidenceStatus")
            if item.get("recommendation") not in {"recommended", "available", "legacy"}:
                issues.append(f"{path}: distribution adapter requires recommendation")

    for path, expected in CRITICAL_PATH_CONTRACTS.items():
        actual = by_path.get(path)
        if actual is None:
            issues.append(f"critical path contract missing: {path}")
            continue
        for field, value in expected.items():
            if actual.get(field) != value:
                issues.append(f"critical path contract mismatch: {path}.{field}")

    for module in modules:
        module_id = module.get("id", "<missing>")
        for implementation in module.get("implementations", []):
            owner = _effective_owner(implementation, by_path)
            if owner is None or owner.get("module") != module_id:
                issues.append(
                    f"module {module_id} implementation lacks matching ownership: {implementation}"
                )

    gates = contract.get("qualityGates", {})
    taxonomy_gates = gates.get("taxonomy", {})
    for gate, hard_ceiling in HARD_TAXONOMY_CEILINGS.items():
        configured = taxonomy_gates.get(gate)
        if not isinstance(configured, (int, float)):
            issues.append(f"taxonomy gate is missing: {gate}")
        elif configured > hard_ceiling:
            issues.append(
                f"taxonomy gate {gate} cannot exceed hard ceiling {hard_ceiling:.2%}"
            )
    entrypoints = set(gates.get("requiredEntrypoints", []))
    decisions = set(gates.get("requiredDecisions", []))
    if not HARD_REQUIRED_ENTRYPOINTS <= entrypoints:
        issues.append("requiredEntrypoints cannot omit hard repository entrypoints")
    if not HARD_REQUIRED_DECISIONS <= decisions:
        issues.append("requiredDecisions cannot omit accepted architecture decisions")
    for path in entrypoints:
        if not (root / path).is_file():
            issues.append(f"required entrypoint does not exist: {path}")
    for path in decisions:
        if not (root / path).is_file():
            issues.append(f"required decision does not exist: {path}")
    return sorted(set(issues))


def repository_ownership_issues(root: Path, contract: dict[str, Any]) -> list[str]:
    """Require one effective longest-prefix owner for every repository file."""

    commands = (
        ["git", "ls-files", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    )
    files: set[str] = set()
    for command in commands:
        result = subprocess.run(command, cwd=root, capture_output=True, check=False)
        if result.returncode != 0:
            return ["git repository-file inventory is unavailable"]
        files.update(
            encoded.decode("utf-8", errors="replace")
            for encoded in result.stdout.split(b"\0")
            if encoded
        )
    ownership = _ownership_by_path(contract)
    issues: list[str] = []
    for path in sorted(files):
        if path == ".planning" or path.startswith(".planning/"):
            continue
        candidates = [
            prefix for prefix in ownership
            if prefix and (path == prefix or path.startswith(prefix + "/"))
        ]
        if not candidates:
            issues.append(f"repository path has no owner: {path}")
            continue
        longest = max(len(prefix) for prefix in candidates)
        effective = [prefix for prefix in candidates if len(prefix) == longest]
        if len(effective) != 1:
            issues.append(f"repository path has ambiguous owners: {path}")
    return sorted(issues)


def tracked_ownership_issues(root: Path, contract: dict[str, Any]) -> list[str]:
    """Compatibility alias for the stricter repository-file ownership audit."""

    return repository_ownership_issues(root, contract)


def taxonomy_metrics(root: Path) -> dict[str, Any]:
    """Measure deterministic category health without treating priority as semantic proof."""

    scripts = str(root / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import build_skill_catalog as builder

    taxonomy = json.loads((root / builder.TAXONOMY_PATH).read_text(encoding="utf-8"))
    entries = builder.build_entries(root, taxonomy)
    fallback = override = needs_review = multiple_matches = priority_ties = 0

    for entry in entries:
        classification_source = entry.classification.split(";", 1)[0]
        fallback += classification_source == "fallback"
        override += classification_source == "override"
        needs_review += entry.description_status == "needs-review"
        if classification_source in {"fallback", "override"}:
            continue

        source = classification_source.split(":", 1)[0]
        slug, combined = builder._classification_text(entry.skill_id, entry.description)
        text = (
            slug
            if source == "slug"
            else entry.description.lower()
            if source == "outcome"
            else combined
        )
        pattern_field = "outcomePatterns" if source == "outcome" else "patterns"
        scores: list[tuple[int, int, str]] = []
        for category in taxonomy["categories"]:
            patterns = category.get(pattern_field, [])
            if category.get("fallback") and not patterns:
                continue
            matched = [
                pattern for pattern in patterns
                if not (
                    pattern_field == "patterns"
                    and source == "description"
                    and pattern in builder.DESCRIPTION_EXCLUDED_PATTERNS
                )
                and re.search(pattern, text, re.IGNORECASE)
            ]
            if matched:
                scores.append((len(matched), category["priority"], category["id"]))
        if len(scores) > 1:
            multiple_matches += 1
        if scores:
            top_score = max(item[0] for item in scores)
            if sum(item[0] == top_score for item in scores) > 1:
                priority_ties += 1

    total = len(entries)
    return {
        "inventoryCount": total,
        "fallbackCount": fallback,
        "fallbackRatio": _ratio(fallback, total),
        "overrideCount": override,
        "overrideRatio": _ratio(override, total),
        "needsReviewCount": needs_review,
        "needsReviewRatio": _ratio(needs_review, total),
        "multipleCategoryMatchCount": multiple_matches,
        "multipleCategoryMatchRatio": _ratio(multiple_matches, total),
        "priorityResolvedTopScoreTies": priority_ties,
        "priorityResolvedTopScoreTieRatio": _ratio(priority_ties, total),
        "deterministicTieBreakFailures": 0,
        "unreviewedPriorityResolvedTies": priority_ties,
        "tieSemantics": "Unique category priorities resolve equal pattern counts deterministically; this is not semantic verification.",
    }


def installed_workspace_issues(root: Path) -> list[str]:
    """Reject host/runtime assumptions anywhere in the generic installer payload."""

    scripts = str(root / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from repository_model import load_manifest

    copied_names = ("SOUL.md", "AGENTS.md", "IDENTITY.md", "USER.md", "TOOLS.md")
    files = [
        root / "CHARTER.md",
        root / "COLLABORATION.md",
        root / "agents" / "BOOTSTRAP.md",
        root / "agents" / "WORKFLOW.md",
    ]
    for agent_directory in sorted((root / "agents").iterdir()):
        if not agent_directory.is_dir():
            continue
        files.extend(agent_directory / name for name in copied_names if (agent_directory / name).is_file())
    manifest = load_manifest(root)
    for agent in manifest.get("agents", []):
        for level in ("required", "optional"):
            for skill_id in agent.get("skills", {}).get(level, []):
                skill_root = root / "skills" / skill_id
                if not skill_root.is_dir():
                    files.append(skill_root / "SKILL.md")
                    continue
                files.extend(
                    path for path in sorted(skill_root.rglob("*"))
                    if path.is_file() and not path.is_symlink()
                )
    forbidden_patterns = (
        re.compile(r"sessions_(?:send|spawn)"),
        re.compile(r"\bclawhub(?:\s|$)", re.IGNORECASE),
        re.compile(r"(?:await\s+)?\bTask\s*\(\s*[\"'`]"),
        re.compile(r"Claude Code(?:'s|’s) Task tool", re.IGNORECASE),
        re.compile(r"openclaw\s+(?:cron|gateway)", re.IGNORECASE),
        re.compile(r"openclaw\s+browser", re.IGNORECASE),
        re.compile(r"profile\s*=\s*[\"']?openclaw", re.IGNORECASE),
        re.compile(r"/tmp/openclaw"),
        re.compile(r"~/\.openclaw|~/openclaw|~/clawd"),
        re.compile(r"/home/aa"),
        re.compile(r"/Users/[A-Za-z_]"),
    )
    issues = []
    for file_path in sorted(set(files)):
        if not file_path.is_file():
            issues.append(
                f"installed workspace source is missing: {file_path.relative_to(root)}"
            )
            continue
        text = file_path.read_text(encoding="utf-8", errors="replace")
        match = next((pattern.search(text) for pattern in forbidden_patterns if pattern.search(text)), None)
        if match is not None:
            issues.append(
                f"installed workspace source assumes host/runtime capability: "
                f"{file_path.relative_to(root)} ({match.group(0)})"
            )
    installer = (root / "install.sh").read_text(encoding="utf-8")
    if "openclaw gateway restart" in installer or "~/.openclaw/workspace-<agent>" in installer:
        issues.append("installer next steps contain a deprecated or destination-ignoring route")
    return sorted(issues)


def audit_repository(root: Path, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return deterministic classification score, issues, and supporting measurements."""

    root = root.resolve()
    if contract is None:
        contract = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    initial_schema_issues = schema_issues(root, contract)
    if initial_schema_issues:
        metrics = taxonomy_metrics(root)
        return {
            "schemaVersion": 1,
            "classificationContractScore": 0,
            "scoreSemantics": "automated architecture-classification contracts",
            "runtimeEvidenceIncluded": False,
            "checks": {name: False for name in SCORED_WEIGHTS},
            "weights": SCORED_WEIGHTS,
            "contractChecksPassed": 0,
            "contractChecksTotal": len(SCORED_WEIGHTS),
            "taxonomy": metrics,
            "issues": sorted(set(initial_schema_issues)),
        }
    contract_issues = validate_contract(root, contract)
    issues = list(contract_issues)
    ownership_issues = repository_ownership_issues(root, contract)
    issues.extend(ownership_issues)
    workspace_issues = installed_workspace_issues(root)
    issues.extend(workspace_issues)
    metrics = taxonomy_metrics(root)
    taxonomy_gates = contract.get("qualityGates", {}).get("taxonomy", {})
    comparisons = (
        ("fallbackRatio", "maxFallbackRatio"),
        ("overrideRatio", "maxOverrideRatio"),
        ("multipleCategoryMatchRatio", "maxMultipleCategoryMatchRatio"),
        ("priorityResolvedTopScoreTieRatio", "maxPriorityResolvedTieRatio"),
        ("needsReviewRatio", "maxNeedsReviewRatio"),
    )
    for metric, gate in comparisons:
        if metrics[metric] > taxonomy_gates.get(gate, -1):
            issues.append(
                f"taxonomy {metric} {metrics[metric]:.2%} exceeds {gate} "
                f"{taxonomy_gates.get(gate, -1):.2%}"
            )
    ownership = contract.get("pathOwnership", [])
    by_path = _ownership_by_path(contract)
    authority_ok = all(
        item.get("authority") is (item.get("role") == "authored-authority")
        for item in ownership
    ) and all(
        all(by_path.get(path, {}).get(field) == value for field, value in expected.items())
        for path, expected in CRITICAL_PATH_CONTRACTS.items()
        if expected.get("authority")
    )
    generated_items = [item for item in ownership if item.get("role") == "generated-output"]
    lineage_ok = all(
        re.fullmatch(r"scripts/[a-z0-9_]+\.py", str(item.get("generatedBy", "")))
        and (root / item["generatedBy"]).is_file()
        and _declared_npm_check(root, item.get("verify"))
        for item in generated_items
    ) and all(
        all(by_path.get(path, {}).get(field) == value for field, value in expected.items())
        for path, expected in CRITICAL_PATH_CONTRACTS.items()
        if expected.get("role") == "generated-output"
    )
    adapter_items = [item for item in ownership if item.get("role") == "distribution-adapter"]
    adapter_ok = all(
        item.get("evidenceStatus") in {"manifest", "pending", "legacy"}
        and item.get("recommendation") in {"recommended", "available", "legacy"}
        for item in adapter_items
    ) and all(
        all(by_path.get(path, {}).get(field) == value for field, value in expected.items())
        for path, expected in CRITICAL_PATH_CONTRACTS.items()
        if expected.get("role") == "distribution-adapter"
    )
    gates = contract.get("qualityGates", {})
    module_ids = {item.get("id") for item in contract.get("modules", [])}
    schema_decisions_ok = (
        not schema_issues(root, contract)
        and HARD_REQUIRED_ENTRYPOINTS <= set(gates.get("requiredEntrypoints", []))
        and HARD_REQUIRED_DECISIONS <= set(gates.get("requiredDecisions", []))
        and all(set(item.get("seams", [])) <= module_ids for item in contract.get("modules", []))
    )
    taxonomy_ok = all(
        metrics[metric] <= taxonomy_gates.get(gate, -1)
        for metric, gate in comparisons
    ) and all(
        taxonomy_gates.get(gate, 2) <= ceiling
        for gate, ceiling in HARD_TAXONOMY_CEILINGS.items()
    )
    checks = {
        "ownershipCoverage": not ownership_issues,
        "authorityIntegrity": authority_ok,
        "generatedLineage": lineage_ok,
        "adapterBoundaries": adapter_ok,
        "schemaAndDecisionIntegrity": schema_decisions_ok,
        "taxonomyDebt": taxonomy_ok,
        "installedWorkspaceSeam": not workspace_issues,
    }
    score = sum(SCORED_WEIGHTS[name] for name, passed in checks.items() if passed)
    critical = (
        checks["ownershipCoverage"],
        checks["authorityIntegrity"],
        checks["generatedLineage"],
        checks["schemaAndDecisionIntegrity"],
    )
    if not all(critical):
        score = min(score, 60)
    elif issues:
        score = min(score, 90)
    return {
        "schemaVersion": 1,
        "classificationContractScore": score,
        "scoreSemantics": "automated architecture-classification contracts",
        "runtimeEvidenceIncluded": False,
        "checks": checks,
        "weights": SCORED_WEIGHTS,
        "contractChecksPassed": sum(checks.values()),
        "contractChecksTotal": len(checks),
        "taxonomy": metrics,
        "issues": sorted(set(issues)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    result = audit_repository(arguments.root)
    if arguments.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Architecture classification contracts: {result['classificationContractScore']}/100")
        taxonomy = result["taxonomy"]
        print(
            "Taxonomy: "
            f"fallback={taxonomy['fallbackCount']}/{taxonomy['inventoryCount']} "
            f"override={taxonomy['overrideCount']}/{taxonomy['inventoryCount']} "
            f"priority-ties={taxonomy['priorityResolvedTopScoreTies']}/{taxonomy['inventoryCount']}"
        )
        for issue in result["issues"]:
            print(f"ERROR {issue}")
    if arguments.check and (result["issues"] or result["classificationContractScore"] < 95):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
