#!/usr/bin/env python3
"""Canonical, deterministic repository model for validation and automation."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


AVAILABLE_CHECKS = (
    "workflows",
    "structured",
    "manifest",
    "symlinks",
    "references",
    "counts",
)
MANIFEST_PATH = Path("config/team-manifest.json")
MANIFEST_SCHEMA_PATH = Path("config/team-manifest.schema.json")
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Issue:
    """One observable repository contract violation."""

    severity: str
    check: str
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


@dataclass
class ValidationReport:
    """Collected validation results with stable serialization."""

    issues: list[Issue] = field(default_factory=list)
    passes: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _sort_key(issue: Issue) -> tuple[int, int, str, str, str]:
        try:
            check_rank = AVAILABLE_CHECKS.index(issue.check)
        except ValueError:
            check_rank = len(AVAILABLE_CHECKS)
        code_rank = 0 if issue.code == "symlink.forbidden" else 1
        return (
            0 if issue.severity == "error" else 1,
            check_rank,
            issue.path,
            f"{code_rank}:{issue.code}",
            issue.message,
        )

    @property
    def sorted_issues(self) -> list[Issue]:
        return sorted(self.issues, key=self._sort_key)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    def add(
        self,
        severity: str,
        check: str,
        code: str,
        message: str,
        path: str | Path = "",
    ) -> None:
        self.issues.append(Issue(severity, check, code, message, str(path)))

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)
        self.passes.update(other.passes)

    def to_dict(self, max_details: int | None = None) -> dict[str, Any]:
        issues = _bounded_issues(self.sorted_issues, max_details)
        return {
            "issues": [issue.to_dict() for issue in issues],
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
            },
        }


def _bounded_issues(issues: Sequence[Issue], maximum: int | None) -> list[Issue]:
    if maximum is None:
        return list(issues)
    errors = [issue for issue in issues if issue.severity == "error"][:maximum]
    warnings = [issue for issue in issues if issue.severity == "warning"][:maximum]
    return errors + warnings


def _git_index(root: Path, pathspecs: Sequence[str] = ()) -> list[tuple[str, str]] | None:
    command = ["git", "ls-files", "--stage", "-z"]
    if pathspecs:
        command.extend(["--", *pathspecs])
    result = subprocess.run(command, cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        return None

    entries: list[tuple[str, str]] = []
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, encoded_path = entry.split(b"\t", 1)
        mode = metadata.split(b" ", 1)[0].decode("ascii")
        entries.append((mode, os.fsdecode(encoded_path)))
    return sorted(entries, key=lambda entry: entry[1])


def _physical_skill_names(root: Path) -> set[str]:
    entries = _git_index(root, ("skills",))
    if entries is not None:
        return {
            parts[1]
            for mode, path in entries
            if mode != "120000"
            and len(parts := path.split("/")) == 3
            and parts[0] == "skills"
            and parts[2] == "SKILL.md"
        }

    skills_root = root / "skills"
    if not skills_root.is_dir():
        return set()
    return {
        directory.name
        for directory in skills_root.iterdir()
        if directory.is_dir()
        and not directory.is_symlink()
        and (directory / "SKILL.md").is_file()
        and not (directory / "SKILL.md").is_symlink()
    }


def physical_skill_names(root: Path) -> set[str]:
    """Return canonical tracked, physical, top-level skill identifiers."""

    return _physical_skill_names(root)


def _agent_names(root: Path) -> set[str]:
    entries = _git_index(root, ("agents",))
    if entries is not None:
        return {
            parts[1]
            for mode, path in entries
            if mode != "120000"
            and len(parts := path.split("/")) >= 3
            and parts[0] == "agents"
        }

    agents_root = root / "agents"
    if not agents_root.is_dir():
        return set()
    return {
        directory.name
        for directory in agents_root.iterdir()
        if directory.is_dir() and not directory.is_symlink()
    }


def tracked_inventory_counts(root: Path) -> tuple[int, int]:
    """Return physical top-level skill entrypoints and physical agent directories."""

    return len(_physical_skill_names(root)), len(_agent_names(root))


def load_manifest(root: Path) -> dict[str, Any]:
    """Load the canonical manifest through its repository-relative public path."""

    with (root / MANIFEST_PATH).open(encoding="utf-8") as file_handle:
        manifest = json.load(file_handle)
    if not isinstance(manifest, dict):
        raise ValueError("team manifest must be a JSON object")
    return manifest


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def validate_workflows(root: Path) -> ValidationReport:
    report = ValidationReport()
    workflow_directory = root / ".github" / "workflows"
    workflow_files = sorted(
        [*workflow_directory.glob("*.yml"), *workflow_directory.glob("*.yaml")]
    )
    if not workflow_files:
        report.add(
            "error",
            "workflows",
            "workflow.no_files",
            "contains no YAML workflow files",
            ".github/workflows",
        )
        return report

    ruby = shutil.which("ruby")
    if ruby is None:
        report.add(
            "error",
            "workflows",
            "workflow.parser_unavailable",
            "Ruby is required for offline workflow YAML parsing",
        )
        return report

    for workflow_file in workflow_files:
        relative_path = _relative(root, workflow_file)
        result = subprocess.run(
            [
                ruby,
                "-e",
                'require "psych"; Psych.parse_file(ARGV.fetch(0))',
                str(workflow_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            report.add(
                "error",
                "workflows",
                "workflow.invalid_yaml",
                "YAML parse failed",
                relative_path,
            )
            continue

        content = workflow_file.read_text(encoding="utf-8")
        missing_keys = [
            key
            for key in ("name", "on", "jobs")
            if re.search(rf"(?m)^{key}:", content) is None
        ]
        if missing_keys:
            report.add(
                "error",
                "workflows",
                "workflow.missing_key",
                f"missing top-level key(s): {', '.join(missing_keys)}",
                relative_path,
            )
        if re.search(r"(?<![A-Za-z0-9:])/(?:home|Users|runner)/", content):
            report.add(
                "error",
                "workflows",
                "workflow.runner_absolute_path",
                "runner-specific absolute path; use $GITHUB_WORKSPACE",
                relative_path,
            )

    if not report.issues:
        report.passes["workflows"] = (
            f"{len(workflow_files)} workflow file(s) parsed"
        )
    return report


def validate_structured_files(root: Path) -> ValidationReport:
    report = ValidationReport()
    entries = _git_index(root, ("*.json", "*.toml"))
    if entries is not None:
        structured_files = [
            root / path
            for mode, path in entries
            if mode != "120000" and Path(path).suffix.lower() in {".json", ".toml"}
        ]
    else:
        structured_files = sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in {".json", ".toml"}
            and not {".git", "node_modules"}.intersection(
                path.relative_to(root).parts
            )
        )

    for structured_file in structured_files:
        relative_path = _relative(root, structured_file)
        try:
            if structured_file.suffix.lower() == ".json":
                with structured_file.open(encoding="utf-8") as file_handle:
                    json.load(file_handle)
            else:
                with structured_file.open("rb") as file_handle:
                    tomllib.load(file_handle)
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
            format_name = structured_file.suffix[1:].upper()
            report.add(
                "error",
                "structured",
                f"structured.invalid_{format_name.lower()}",
                f"{format_name} parse failed: {error}",
                relative_path,
            )

    if not report.issues:
        report.passes["structured"] = (
            f"{len(structured_files)} JSON/TOML file(s) parsed"
        )
    return report


def _expect_exact_keys(
    report: ValidationReport,
    value: Any,
    expected: set[str],
    location: str,
) -> bool:
    if not isinstance(value, dict):
        report.add(
            "error",
            "manifest",
            "manifest.schema_type",
            "must be an object",
            location,
        )
        return False
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        report.add(
            "error",
            "manifest",
            "manifest.schema_required",
            f"missing required field(s): {', '.join(missing)}",
            location,
        )
    if extra:
        report.add(
            "error",
            "manifest",
            "manifest.schema_additional_property",
            f"unexpected field(s): {', '.join(extra)}",
            location,
        )
    return not missing and not extra


def _validate_skill_list(
    report: ValidationReport, value: Any, location: str
) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        report.add(
            "error",
            "manifest",
            "manifest.schema_skill_list",
            "must be an array of skill identifiers",
            location,
        )
        return None
    invalid = sorted(item for item in value if not IDENTIFIER_PATTERN.fullmatch(item))
    if invalid:
        report.add(
            "error",
            "manifest",
            "manifest.schema_identifier",
            f"invalid skill identifier(s): {', '.join(invalid)}",
            location,
        )
    duplicates = sorted({item for item in value if value.count(item) > 1})
    if duplicates:
        report.add(
            "error",
            "manifest",
            "manifest.duplicate_skill",
            f"duplicate skill identifier(s): {', '.join(duplicates)}",
            location,
        )
    return value


def validate_manifest(root: Path) -> ValidationReport:
    report = ValidationReport()
    manifest_file = root / MANIFEST_PATH
    schema_file = root / MANIFEST_SCHEMA_PATH
    for path, code, label in (
        (manifest_file, "manifest.missing", "team manifest"),
        (schema_file, "manifest.schema_missing", "team manifest schema"),
    ):
        if not path.is_file():
            report.add("error", "manifest", code, f"{label} is missing", _relative(root, path))
    if report.issues:
        return report

    try:
        manifest = load_manifest(root)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        report.add(
            "error",
            "manifest",
            "manifest.invalid_json",
            f"team manifest JSON parse failed: {error}",
            MANIFEST_PATH,
        )
        return report
    try:
        with schema_file.open(encoding="utf-8") as file_handle:
            schema = json.load(file_handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        report.add(
            "error",
            "manifest",
            "manifest.schema_invalid_json",
            f"team manifest schema JSON parse failed: {error}",
            MANIFEST_SCHEMA_PATH,
        )
        return report
    if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        report.add(
            "error",
            "manifest",
            "manifest.schema_dialect",
            "schema must declare JSON Schema draft 2020-12",
            MANIFEST_SCHEMA_PATH,
        )

    top_keys = {"$schema", "schemaVersion", "inventory", "agents", "kits"}
    _expect_exact_keys(report, manifest, top_keys, str(MANIFEST_PATH))
    if manifest.get("$schema") != "./team-manifest.schema.json":
        report.add(
            "error",
            "manifest",
            "manifest.schema_reference",
            "must reference ./team-manifest.schema.json",
            MANIFEST_PATH,
        )
    if manifest.get("schemaVersion") != 1:
        report.add(
            "error",
            "manifest",
            "manifest.schema_version",
            "schemaVersion must be 1",
            MANIFEST_PATH,
        )

    inventory = manifest.get("inventory")
    inventory_keys = {
        "agentCount",
        "physicalSkillCount",
        "skillEntrypoint",
        "symlinkPolicy",
    }
    inventory_valid = _expect_exact_keys(
        report, inventory, inventory_keys, f"{MANIFEST_PATH}:inventory"
    )
    if inventory_valid:
        if inventory.get("skillEntrypoint") != "SKILL.md":
            report.add(
                "error",
                "manifest",
                "manifest.skill_entrypoint",
                "skillEntrypoint must be SKILL.md",
                f"{MANIFEST_PATH}:inventory",
            )
        if inventory.get("symlinkPolicy") != "forbid":
            report.add(
                "error",
                "manifest",
                "manifest.symlink_policy",
                "symlinkPolicy must be forbid",
                f"{MANIFEST_PATH}:inventory",
            )
        for count_field in ("agentCount", "physicalSkillCount"):
            value = inventory.get(count_field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                report.add(
                    "error",
                    "manifest",
                    "manifest.schema_count",
                    f"{count_field} must be a non-negative integer",
                    f"{MANIFEST_PATH}:inventory",
                )

    agents = manifest.get("agents")
    if not isinstance(agents, list) or not agents:
        report.add(
            "error",
            "manifest",
            "manifest.schema_agents",
            "agents must be a non-empty array",
            MANIFEST_PATH,
        )
        agents = []
    agent_ids: list[str] = []
    physical_skills = _physical_skill_names(root)
    for index, agent in enumerate(agents):
        location = f"{MANIFEST_PATH}:agents[{index}]"
        if not _expect_exact_keys(report, agent, {"id", "name", "path", "skills"}, location):
            continue
        agent_id = agent.get("id")
        name = agent.get("name")
        path = agent.get("path")
        if not isinstance(agent_id, str) or not IDENTIFIER_PATTERN.fullmatch(agent_id):
            report.add(
                "error", "manifest", "manifest.schema_identifier", "invalid agent id", location
            )
            continue
        agent_ids.append(agent_id)
        if not isinstance(name, str) or not name.strip():
            report.add(
                "error", "manifest", "manifest.schema_name", "name must be non-empty", location
            )
        expected_path = f"agents/{agent_id}"
        if path != expected_path:
            report.add(
                "error",
                "manifest",
                "manifest.agent_path",
                f"path must be {expected_path}",
                location,
            )
        elif not (root / expected_path).is_dir():
            report.add(
                "error",
                "manifest",
                "manifest.agent_missing",
                "agent directory is missing",
                expected_path,
            )

        skills = agent.get("skills")
        if not _expect_exact_keys(
            report,
            skills,
            {"required", "optional", "harnessSpecific", "recommendedExternal"},
            f"{location}:skills",
        ):
            continue
        categories: dict[str, list[str]] = {}
        skill_categories = (
            "required", "optional", "harnessSpecific", "recommendedExternal"
        )
        for category in skill_categories:
            parsed = _validate_skill_list(
                report, skills.get(category), f"{location}:skills.{category}"
            )
            if parsed is not None:
                categories[category] = parsed
        for left_index, left in enumerate(skill_categories):
            for right in skill_categories[left_index + 1 :]:
                overlap = sorted(
                    set(categories.get(left, [])) & set(categories.get(right, []))
                )
                if overlap:
                    report.add(
                        "error",
                        "manifest",
                        "manifest.skill_category_overlap",
                        f"{left} and {right} overlap: {', '.join(overlap)}",
                        f"{location}:skills",
                    )
        for category in ("required", "optional", "harnessSpecific"):
            for skill in categories.get(category, []):
                if skill not in physical_skills:
                    report.add(
                        "error",
                        "manifest",
                        f"manifest.{category}_skill_missing",
                        f"{category} local skill is missing a physical SKILL.md",
                        f"skills/{skill}/SKILL.md",
                    )

    duplicate_agent_ids = sorted({item for item in agent_ids if agent_ids.count(item) > 1})
    if duplicate_agent_ids:
        report.add(
            "error",
            "manifest",
            "manifest.duplicate_agent",
            f"duplicate agent id(s): {', '.join(duplicate_agent_ids)}",
            MANIFEST_PATH,
        )

    kits = manifest.get("kits")
    if not isinstance(kits, list) or not kits:
        report.add(
            "error",
            "manifest",
            "manifest.schema_kits",
            "kits must be a non-empty array",
            MANIFEST_PATH,
        )
        kits = []
    kit_ids: list[str] = []
    for index, kit in enumerate(kits):
        location = f"{MANIFEST_PATH}:kits[{index}]"
        if not _expect_exact_keys(report, kit, {"id", "agents"}, location):
            continue
        kit_id = kit.get("id")
        members = kit.get("agents")
        if not isinstance(kit_id, str) or not IDENTIFIER_PATTERN.fullmatch(kit_id):
            report.add(
                "error", "manifest", "manifest.schema_identifier", "invalid kit id", location
            )
        else:
            kit_ids.append(kit_id)
        if not isinstance(members, list) or not members or any(
            not isinstance(member, str) for member in members
        ):
            report.add(
                "error",
                "manifest",
                "manifest.schema_kit_agents",
                "agents must be a non-empty array of agent ids",
                location,
            )
            continue
        duplicates = sorted({member for member in members if members.count(member) > 1})
        if duplicates:
            report.add(
                "error",
                "manifest",
                "manifest.duplicate_kit_agent",
                f"duplicate kit agent(s): {', '.join(duplicates)}",
                location,
            )
        unknown = sorted(set(members) - set(agent_ids))
        if unknown:
            report.add(
                "error",
                "manifest",
                "manifest.kit_unknown_agent",
                f"unknown agent(s): {', '.join(unknown)}",
                location,
            )
    duplicate_kit_ids = sorted({item for item in kit_ids if kit_ids.count(item) > 1})
    if duplicate_kit_ids:
        report.add(
            "error",
            "manifest",
            "manifest.duplicate_kit",
            f"duplicate kit id(s): {', '.join(duplicate_kit_ids)}",
            MANIFEST_PATH,
        )

    physical_skill_count, physical_agent_count = tracked_inventory_counts(root)
    if inventory_valid:
        expected_agents = inventory.get("agentCount")
        expected_skills = inventory.get("physicalSkillCount")
        if isinstance(expected_agents, int) and not isinstance(expected_agents, bool):
            if expected_agents != len(set(agent_ids)):
                report.add(
                    "error",
                    "manifest",
                    "manifest.agent_count",
                    f"declares {expected_agents} agents but lists {len(set(agent_ids))}",
                    MANIFEST_PATH,
                )
            if expected_agents != physical_agent_count:
                report.add(
                    "error",
                    "manifest",
                    "manifest.agent_inventory_drift",
                    f"declares {expected_agents} agents; physical inventory has {physical_agent_count}",
                    MANIFEST_PATH,
                )
        if isinstance(expected_skills, int) and not isinstance(expected_skills, bool):
            if expected_skills != physical_skill_count:
                report.add(
                    "error",
                    "manifest",
                    "manifest.skill_inventory_drift",
                    f"declares {expected_skills} physical skills; inventory has {physical_skill_count}",
                    MANIFEST_PATH,
                )

    unlisted_agents = sorted(_agent_names(root) - set(agent_ids))
    if unlisted_agents:
        report.add(
            "error",
            "manifest",
            "manifest.agent_unlisted",
            f"physical agent(s) absent from manifest: {', '.join(unlisted_agents)}",
            MANIFEST_PATH,
        )

    if not report.issues:
        report.passes["manifest"] = (
            f"{len(agent_ids)} agents, {len(kit_ids)} kits, "
            f"{physical_skill_count} physical skill(s)"
        )
    return report


def validate_tracked_symlinks(root: Path) -> ValidationReport:
    report = ValidationReport()
    entries = _git_index(root)
    if entries is None:
        report.add(
            "error",
            "symlinks",
            "symlink.git_required",
            "symlink validation requires a Git work tree",
        )
        return report

    symlink_paths = [root / path for mode, path in entries if mode == "120000"]
    for symlink_path in symlink_paths:
        relative_path = _relative(root, symlink_path)
        report.add(
            "error",
            "symlinks",
            "symlink.forbidden",
            "tracked symlinks are forbidden by inventory policy",
            relative_path,
        )
        try:
            target = os.readlink(symlink_path)
        except OSError:
            report.add(
                "error",
                "symlinks",
                "symlink.unreadable",
                "tracked symlink cannot be read from the work tree",
                relative_path,
            )
            continue
        if Path(target).is_absolute():
            report.add(
                "error",
                "symlinks",
                "symlink.absolute",
                f"tracked absolute symlink -> {target}",
                relative_path,
            )
        if not symlink_path.exists():
            report.add(
                "error",
                "symlinks",
                "symlink.broken",
                f"tracked broken symlink -> {target}",
                relative_path,
            )

    if not report.issues:
        report.passes["symlinks"] = "0 tracked symlink(s); policy=forbid"
    return report


def validate_references(root: Path) -> ValidationReport:
    report = ValidationReport()
    tools_files = sorted((root / "agents").glob("*/TOOLS.md"))
    reference_pattern = re.compile(r"(?<!\.)((?:\.\./)+skills/[A-Za-z0-9_.-]+/?)")
    reference_count = 0
    for tools_file in tools_files:
        content = tools_file.read_text(encoding="utf-8")
        for match in reference_pattern.finditer(content):
            reference_count += 1
            reference = match.group(1).rstrip("/")
            referenced_path = tools_file.parent / reference
            if not referenced_path.is_dir():
                report.add(
                    "error",
                    "references",
                    "reference.skill_missing",
                    f"broken skill reference {reference}",
                    _relative(root, tools_file),
                )

    installer = root / "install.sh"
    installer_reference_count = 0
    if installer.is_file():
        installer_content = installer.read_text(encoding="utf-8")
        map_match = re.search(
            r"declare\s+-A\s+AGENT_MAP=\(\s*(.*?)^\)",
            installer_content,
            flags=re.DOTALL | re.MULTILINE,
        )
        if map_match:
            for mapping in re.finditer(
                r"\[([A-Za-z0-9_-]+)\]=(?:\"([^\"]+)\"|([A-Za-z0-9_.-]+))",
                map_match.group(1),
            ):
                installer_reference_count += 1
                alias = mapping.group(1)
                target = mapping.group(2) or mapping.group(3)
                if not (root / "agents" / target).is_dir():
                    report.add(
                        "error",
                        "references",
                        "reference.installer_agent_missing",
                        f"installer agent mapping {alias} -> agents/{target} is missing",
                        "install.sh",
                    )
        skills_match = re.search(
            r"declare\s+-A\s+AGENT_SKILLS=\(\s*(.*?)^\)",
            installer_content,
            flags=re.DOTALL | re.MULTILINE,
        )
        if skills_match:
            for mapping in re.finditer(
                r"\[([A-Za-z0-9_-]+)\]=\"([^\"]*)\"", skills_match.group(1)
            ):
                agent = mapping.group(1)
                for skill in mapping.group(2).split():
                    installer_reference_count += 1
                    if not (root / "skills" / skill).is_dir():
                        report.add(
                            "error",
                            "references",
                            "reference.installer_skill_missing",
                            f"installer skill reference {agent} -> skills/{skill} is missing",
                            "install.sh",
                        )
        skills_function_match = re.search(
            r"^agent_skills\(\)\s*\{(.*?)^\}",
            installer_content,
            flags=re.DOTALL | re.MULTILINE,
        )
        if skills_function_match:
            for mapping in re.finditer(
                r"^\s*([A-Za-z0-9_|-]+)\)\s+printf\s+'[^']*'\s+\"([^\"]*)\"",
                skills_function_match.group(1),
                flags=re.MULTILINE,
            ):
                agents = mapping.group(1).split("|")
                for skill in mapping.group(2).split():
                    installer_reference_count += len(agents)
                    if not (root / "skills" / skill).is_dir():
                        for agent in agents:
                            report.add(
                                "error",
                                "references",
                                "reference.installer_skill_missing",
                                f"installer skill reference {agent} -> skills/{skill} is missing",
                                "install.sh",
                            )

    if not report.issues:
        total = reference_count + installer_reference_count
        report.passes["references"] = f"{total} repository reference(s) resolve"
    return report


def validate_counts(root: Path) -> ValidationReport:
    report = ValidationReport()
    canonical_skill_count, canonical_agent_count = tracked_inventory_counts(root)
    claim_sources = (
        "package.json",
        "README.md",
        "README_CN.md",
        "CLAUDE.md",
        "install.sh",
        "agents/README.md",
        "agents/TEAM_ROSTER.md",
        "docs/skills-matrix.md",
        "SKILL-AGENT-MATRIX.md",
    )
    patterns = (
        (re.compile(r"(?i)(\d[\d,]*)\s*(\+)?\s*skills\b"), "skills", canonical_skill_count),
        (re.compile(r"(\d[\d,]*)\s*(\+)?\s*个技能"), "skills", canonical_skill_count),
        (re.compile(r"(?i)(\d[\d,]*)\s*(\+)?\s*agents\b"), "agents", canonical_agent_count),
        (re.compile(r"(\d[\d,]*)\s*(\+)?\s*个\s*C-Suite Agent"), "agents", canonical_agent_count),
    )
    for relative_source in claim_sources:
        source = root / relative_source
        if not source.is_file():
            continue
        content = source.read_text(encoding="utf-8")
        seen_inventories: set[str] = set()
        for line_number, line in enumerate(content.splitlines(), start=1):
            for pattern, inventory_name, canonical_count in patterns:
                if inventory_name in seen_inventories:
                    continue
                for match in pattern.finditer(line):
                    seen_inventories.add(inventory_name)
                    claimed_count = int(match.group(1).replace(",", ""))
                    is_minimum = match.group(2) == "+"
                    current = (
                        canonical_count >= claimed_count
                        if is_minimum
                        else canonical_count == claimed_count
                    )
                    if not current:
                        qualifier = "at least " if is_minimum else ""
                        report.add(
                            "warning",
                            "counts",
                            "count.drift",
                            f"claims {qualifier}{claimed_count} {inventory_name}; "
                            f"canonical inventory has {canonical_count}",
                            f"{relative_source}:{line_number}",
                        )

    if not report.issues:
        report.passes["counts"] = (
            "aggregate claims match canonical tracked inventory "
            f"({canonical_skill_count} skills, {canonical_agent_count} agents)"
        )
    return report


VALIDATORS = {
    "workflows": validate_workflows,
    "structured": validate_structured_files,
    "manifest": validate_manifest,
    "symlinks": validate_tracked_symlinks,
    "references": validate_references,
    "counts": validate_counts,
}


def validate_repository(root: Path, checks: Iterable[str] = AVAILABLE_CHECKS) -> ValidationReport:
    """Validate selected repository contracts without producing output or mutations."""

    root = root.resolve()
    requested = list(checks)
    unknown = sorted(set(requested) - set(AVAILABLE_CHECKS))
    if unknown:
        raise ValueError(f"unknown check(s): {', '.join(unknown)}")
    report = ValidationReport()
    for check in AVAILABLE_CHECKS:
        if check in requested:
            report.extend(VALIDATORS[check](root))
    return report


def render_text(report: ValidationReport, max_details: int = 25) -> str:
    """Render stable human-readable output with bounded error and warning details."""

    lines = [
        f"PASS {check}: {report.passes[check]}"
        for check in AVAILABLE_CHECKS
        if check in report.passes
    ]
    sorted_issues = report.sorted_issues
    for severity in ("error", "warning"):
        issues = [issue for issue in sorted_issues if issue.severity == severity]
        for issue in issues[:max_details]:
            location = f" {issue.path}:" if issue.path else ""
            lines.append(
                f"{severity.upper()}{location} {issue.message} [{issue.code}]"
            )
        omitted = len(issues) - max_details
        if omitted > 0:
            lines.append(
                f"{severity.upper()} ... {omitted} additional {severity}(s) omitted"
            )
    lines.append(
        f"SUMMARY errors={report.error_count} warnings={report.warning_count}"
    )
    return "\n".join(lines) + "\n"


def render_json(report: ValidationReport, max_details: int = 25) -> str:
    """Render stable machine-readable output with full summary counts."""

    return json.dumps(
        report.to_dict(max_details=max_details),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
