#!/usr/bin/env python3
"""Build the deterministic, task-oriented skill catalog."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from repository_model import load_manifest, physical_skill_names
from skill_evidence import build_evidence_index


TAXONOMY_PATH = Path("config/skill-taxonomy.json")
MARKDOWN_PATH = Path("catalog/README.md")
JSON_PATH = Path("catalog/skill-index.json")
MAX_DESCRIPTION = 180
DESCRIPTION_EXCLUDED_PATTERNS = {
    "(?:^|-)agent(?:-|$)",
    "(?:^|-)skills?(?:-|$)",
    "(?:^|-)model(?:-|$)",
    "team",
    "permission",
    "secret",
}
DESCRIPTION_REVIEW_PATTERN = re.compile(
    r"(?i)(?:\bnever lost\b|\bguaranteed\b|\bproduction[- ]ready\b|"
    r"\b100%|\bsave \d+%|this skill provides automated assistance|"
    r"\bTODO\b|输出示例|```|<script|^---$|"
    r"(?:\b(?:and|or|with|to|from|when|for)|\b[a-zA-Z])$)"
)


@dataclass(frozen=True)
class SkillAssignment:
    agent: str
    level: str


@dataclass(frozen=True)
class SkillEntry:
    skill_id: str
    category_id: str
    description: str
    support_level: str
    used_by: tuple[str, ...]
    assignments: tuple[SkillAssignment, ...]
    portability_class: str
    review_signals: tuple[str, ...]
    description_status: str
    classification: str
    classification_details: dict[str, Any]
    provenance: dict[str, Any]
    curation: dict[str, Any]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _frontmatter_description(text: str) -> str:
    if not text.startswith("---"):
        return ""
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return ""

    frontmatter = lines[1:end]
    for index, line in enumerate(frontmatter):
        match = re.match(r"^description\s*:\s*(.*)$", line, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            parts: list[str] = []
            for continuation in frontmatter[index + 1 :]:
                if continuation and not continuation[0].isspace():
                    break
                stripped = continuation.strip()
                if stripped:
                    parts.append(stripped)
            return _normalize(" ".join(parts))
        if value.startswith(("'", '"')) and not value.endswith(value[0]):
            quote = value[0]
            parts = [value[1:]]
            for continuation in frontmatter[index + 1 :]:
                stripped = continuation.strip()
                if stripped.endswith(quote):
                    parts.append(stripped[:-1])
                    break
                parts.append(stripped)
            return _normalize(" ".join(parts))
        return _normalize(_unquote(value))
    return ""


def _body_fallback(text: str, skill_id: str) -> str:
    body = text
    if text.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.DOTALL)
        if match:
            body = text[match.end() :]

    paragraphs = re.split(r"\n\s*\n", body)
    for paragraph in paragraphs:
        candidate = _normalize(paragraph)
        if not candidate:
            continue
        if candidate in {"---", "***"} or candidate.startswith(
            ("<!--", "```", "#", "- ", "* ", ">")
        ):
            continue
        candidate = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", candidate)
        candidate = re.sub(r"[`*_]", "", candidate)
        if candidate:
            return candidate

    heading = re.search(r"(?m)^#{1,6}\s+(.+)$", body)
    if heading:
        return _normalize(re.sub(r"[`*_]", "", heading.group(1)))
    return skill_id.replace("-", " ").title()


def _display_description(path: Path, skill_id: str) -> tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    description = _frontmatter_description(text)
    source = "frontmatter" if description else "fallback"
    if not description:
        description = _body_fallback(text, skill_id)
    description = _normalize(description)
    if len(description) > MAX_DESCRIPTION:
        shortened = description[: MAX_DESCRIPTION - 1].rsplit(" ", 1)[0]
        description = (shortened or description[: MAX_DESCRIPTION - 1]).rstrip() + "…"
    return description, source


def _description_status(description: str) -> str:
    if len(description) < 24 or DESCRIPTION_REVIEW_PATTERN.search(description):
        return "needs-review"
    return "source-text"


def _classification_text(skill_id: str, description: str) -> tuple[str, str]:
    slug = skill_id.lower()
    return slug, f"{slug} {slug.replace('-', ' ')} {description.lower()}"


def _rule_candidates(
    source: str,
    text: str,
    taxonomy: dict[str, Any],
    *,
    pattern_field: str = "patterns",
) -> list[tuple[int, int, str, list[str]]]:
    candidates: list[tuple[int, int, str, list[str]]] = []
    for category in taxonomy["categories"]:
        patterns = category.get(pattern_field, [])
        if category.get("fallback") and not patterns:
            continue
        matched = [
            pattern
            for pattern in patterns
            if not (
                pattern_field == "patterns"
                and source == "description"
                and pattern in DESCRIPTION_EXCLUDED_PATTERNS
            )
            and re.search(pattern, text, re.IGNORECASE)
        ]
        if matched:
            candidates.append(
                (len(matched), category["priority"], category["id"], matched)
            )
    return sorted(candidates, key=lambda item: (-item[0], -item[1], item[2]))


def _candidate_document(
    candidate: tuple[int, int, str, list[str]], best_score: int
) -> dict[str, Any]:
    match_count, priority, category_id, matched_signals = candidate
    return {
        "category_id": category_id,
        "match_count": match_count,
        "matched_signals": matched_signals,
        "priority": priority,
        "tied_for_first": match_count == best_score,
    }


def _classify(
    skill_id: str, description: str, taxonomy: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    priorities = {item["id"]: item["priority"] for item in taxonomy["categories"]}
    slug, combined = _classification_text(skill_id, description)
    overrides = taxonomy.get("overrides", {})
    if skill_id in overrides:
        category_id = str(overrides[skill_id])
        base_source = "fallback"
        base_candidates: list[tuple[int, int, str, list[str]]] = []
        for source, text, pattern_field in (
            ("outcome", description.lower(), "outcomePatterns"),
            ("slug", slug, "patterns"),
            ("description", combined, "patterns"),
        ):
            base_candidates = _rule_candidates(
                source, text, taxonomy, pattern_field=pattern_field
            )
            if base_candidates:
                base_source = source
                break
        best_score = base_candidates[0][0] if base_candidates else 0
        return category_id, "override", {
            "method": "override",
            "winner": {
                "category_id": category_id,
                "match_count": 0,
                "matched_signals": [],
                "priority": priorities[category_id],
                "tie_detected": False,
            },
            "matched_signals": [],
            "runner_ups": [],
            "base_method": base_source,
            "base_candidates": [
                _candidate_document(candidate, best_score)
                for candidate in base_candidates
            ],
            "rationale": taxonomy["overrideRationales"][skill_id],
            "resolution_status": "override",
            "review_state": "unreviewed",
        }

    outcome_candidates = _rule_candidates(
        "outcome",
        description.lower(),
        taxonomy,
        pattern_field="outcomePatterns",
    )
    slug_candidates = _rule_candidates("slug", slug, taxonomy)
    selected: tuple[str, list[tuple[int, int, str, list[str]]]] | None = None
    if outcome_candidates and (
        not slug_candidates
        or outcome_candidates[0][2] == slug_candidates[0][2]
        or outcome_candidates[0][0] >= 2
    ):
        selected = ("outcome", outcome_candidates)
    elif slug_candidates:
        selected = ("slug", slug_candidates)
    else:
        description_candidates = _rule_candidates(
            "description", combined, taxonomy
        )
        if description_candidates:
            selected = ("description", description_candidates)

    if selected:
        source, candidates = selected
        best_score, best_priority, best_category, best_patterns = candidates[0]
        tied = any(item[0] == best_score for item in candidates[1:])
        return best_category, f"{source}:" + ",".join(best_patterns), {
            "method": source,
            "winner": {
                "category_id": best_category,
                "match_count": best_score,
                "matched_signals": best_patterns,
                "priority": best_priority,
                "tie_detected": tied,
            },
            "matched_signals": best_patterns,
            "runner_ups": [
                _candidate_document(item, best_score)
                for item in candidates[1:]
            ],
            "resolution_status": "priority-tie" if tied else "rule-match",
            "review_state": "unreviewed",
        }
    fallback = next(item["id"] for item in taxonomy["categories"] if item.get("fallback"))
    return fallback, "fallback", {
        "method": "fallback",
        "winner": {
            "category_id": fallback,
            "match_count": 0,
            "matched_signals": [],
            "priority": priorities[fallback],
            "tie_detected": False,
        },
        "matched_signals": [],
        "runner_ups": [],
        "resolution_status": "fallback",
        "review_state": "unreviewed",
    }


def _agent_usage(
    root: Path,
) -> tuple[dict[str, set[tuple[str, str]]], dict[str, set[str]]]:
    manifest = load_manifest(root)
    usage: dict[str, set[tuple[str, str]]] = defaultdict(set)
    levels: dict[str, set[str]] = defaultdict(set)
    for agent in manifest["agents"]:
        for level in ("required", "optional", "harnessSpecific"):
            for skill in agent["skills"].get(level, []):
                usage[skill].add((agent["id"].upper(), level))
                levels[skill].add(level)
    return usage, levels


def _portability_class(levels: set[str]) -> str:
    if "required" in levels:
        return "portable-required"
    if "optional" in levels:
        return "portable-optional"
    if "harnessSpecific" in levels:
        return "harness-specific"
    return "catalog-only"


def _validate_taxonomy(taxonomy: dict[str, Any], skill_names: set[str]) -> None:
    if taxonomy.get("$schema") != "./skill-taxonomy.schema.json":
        raise ValueError("taxonomy must reference ./skill-taxonomy.schema.json")
    if taxonomy.get("schemaVersion") != 2:
        raise ValueError("taxonomy schemaVersion must be 2")

    categories = taxonomy.get("categories", [])
    category_ids = [item["id"] for item in categories]
    priorities = [item["priority"] for item in categories]
    if len(category_ids) != len(set(category_ids)):
        raise ValueError("taxonomy category ids must be unique")
    if len(priorities) != len(set(priorities)):
        raise ValueError("taxonomy category priorities must be unique")
    if sum(bool(item.get("fallback")) for item in categories) != 1:
        raise ValueError("taxonomy must define exactly one fallback category")
    for category in categories:
        for pattern in category["patterns"] + category["outcomePatterns"]:
            if not pattern:
                raise ValueError(f"empty pattern in category {category['id']}")
            re.compile(pattern)

    known_categories = set(category_ids)
    overrides = taxonomy.get("overrides", {})
    if set(overrides) - skill_names:
        raise ValueError(f"taxonomy overrides reference missing skills: {sorted(set(overrides) - skill_names)}")
    if set(overrides.values()) - known_categories:
        raise ValueError("taxonomy overrides reference unknown categories")
    override_rationales = taxonomy.get("overrideRationales", {})
    if set(override_rationales) != set(overrides):
        raise ValueError("taxonomy override rationales must exactly match overrides")
    if any(not isinstance(value, str) or len(value.strip()) < 20 for value in override_rationales.values()):
        raise ValueError("taxonomy override rationales must be descriptive strings")

    risk_labels = [item["id"] for item in taxonomy.get("riskLabels", [])]
    if len(risk_labels) != len(set(risk_labels)):
        raise ValueError("risk label ids must be unique")
    risk_overrides = taxonomy.get("riskOverrides", {})
    if set(risk_overrides) - skill_names:
        raise ValueError("risk overrides reference missing skills")
    for signals in risk_overrides.values():
        if set(signals) - set(risk_labels):
            raise ValueError("risk overrides reference unknown labels")

def build_entries(root: Path, taxonomy: dict[str, Any]) -> list[SkillEntry]:
    skill_names = physical_skill_names(root)
    _validate_taxonomy(taxonomy, skill_names)
    usage, levels_by_skill = _agent_usage(root)
    evidence_by_skill = build_evidence_index(root)
    known_risks = {item["id"] for item in taxonomy.get("riskLabels", [])}
    entries: list[SkillEntry] = []
    for skill_id in sorted(skill_names):
        description, metadata_source = _display_description(
            root / "skills" / skill_id / "SKILL.md", skill_id
        )
        category_id, classification, classification_details = _classify(
            skill_id, description, taxonomy
        )
        review_signals = tuple(sorted(taxonomy.get("riskOverrides", {}).get(skill_id, [])))
        unknown_risks = set(review_signals) - known_risks
        if unknown_risks:
            raise ValueError(f"unknown review signal(s) for {skill_id}: {sorted(unknown_risks)}")
        entries.append(
            SkillEntry(
                skill_id=skill_id,
                category_id=category_id,
                description=description,
                support_level=(
                    "pack-required"
                    if "required" in levels_by_skill.get(skill_id, set())
                    else "catalog"
                ),
                used_by=tuple(
                    sorted({agent for agent, _level in usage.get(skill_id, set())})
                ),
                assignments=tuple(
                    SkillAssignment(agent=agent, level=level)
                    for agent, level in sorted(usage.get(skill_id, set()))
                ),
                portability_class=_portability_class(
                    levels_by_skill.get(skill_id, set())
                ),
                review_signals=review_signals,
                description_status=_description_status(description),
                classification=f"{classification};metadata:{metadata_source}",
                classification_details=classification_details,
                provenance=evidence_by_skill[skill_id]["provenance"],
                curation=evidence_by_skill[skill_id]["curation"],
            )
        )
    return entries


def category_counts(
    entries: list[SkillEntry], taxonomy: dict[str, Any]
) -> OrderedDict[str, int]:
    counts = {category["id"]: 0 for category in taxonomy["categories"]}
    for entry in entries:
        counts[entry.category_id] += 1
    return OrderedDict((category["id"], counts[category["id"]]) for category in taxonomy["categories"])


def _escape_markdown(value: str) -> str:
    return html.escape(value, quote=False).replace("|", "\\|").replace("\n", " ")


def _category_label(category: dict[str, Any]) -> str:
    return f"{category['emoji']} {category['title']}"


def _support_label(entry: SkillEntry) -> str:
    labels = {
        "portable-required": "Portable required assignment · structure checked",
        "portable-optional": "Portable optional assignment · structure checked",
        "harness-specific": "Harness-specific assignment · generic installer skips",
        "catalog-only": "Catalog only",
    }
    return labels[entry.portability_class]


def _origin_label(entry: SkillEntry) -> str:
    labels = {
        "project-original": "Project original",
        "adapted": "Adapted",
        "collected": "Collected",
        "unknown": "Unknown",
    }
    label = labels[entry.provenance["origin_kind"]]
    if entry.provenance["review_state"] == "stale":
        return f"{label} · stale review"
    if entry.provenance["review_state"] == "unreviewed":
        return f"{label} · unreviewed"
    return f"{label} · reviewed"


def _curation_label(entry: SkillEntry) -> str:
    status = entry.curation["status"]
    if status == "stale":
        return "Stale · score hidden"
    if status == "unscored":
        return "Unscored"
    return f"{entry.curation['score']}/100 · {entry.curation['tier'].title()}"


def _runtime_label(entry: SkillEntry) -> str:
    return str(entry.curation["runtime_evidence"]).replace("-", " ").title()


def render_markdown(entries: list[SkillEntry], taxonomy: dict[str, Any]) -> str:
    categories = {item["id"]: item for item in taxonomy["categories"]}
    counts = category_counts(entries, taxonomy)
    by_category: dict[str, list[SkillEntry]] = defaultdict(list)
    by_origin: dict[str, list[SkillEntry]] = defaultdict(list)
    for entry in entries:
        by_category[entry.category_id].append(entry)
        by_origin[entry.provenance["origin_kind"]].append(entry)

    lines = [
        "<!-- Generated by scripts/build_skill_catalog.py. Do not edit by hand. -->",
        "",
        "# 🧭 Skill catalog",
        "",
        "Find a skill by the outcome you need. This index is generated from tracked, physical `SKILL.md` entrypoints; catalog inclusion proves structure, not behavior or cross-harness compatibility.",
        "",
        "**Classification evidence:** inspect the fixed [Gold Set methodology](../docs/skill-taxonomy-gold-set.md) and the machine-readable [reviewed-set agreement report](./skill-taxonomy-evaluation.json). The score measures agreement on reviewed primary-outcome labels; it is not a Skill quality or runtime-success score.",
        "",
        "**Curation evidence:** origin labels and the separate **Curation evidence score** come from reviewed authored contracts. `Unknown` and `Unscored` are honest defaults; runtime evidence remains a separate field. See the [methodology](../docs/skill-provenance-and-scoring.md).",
        "",
        "**First-party collection:** browse the generated [Daniel's Original Skills](../skills/original/) view. It includes only digest-backed `project-original + reviewed` provenance and does not imply runtime verification.",
        "",
        "## 🚀 Selected starting points",
        "",
        "Only digest-matched, structurally valid Skills with reviewed provenance and a Curation evidence score of at least 75 appear here. Selection is not runtime verification.",
        "",
        "| Goal | Skill | Origin | Curation evidence | Runtime | Why start here |",
        "|---|---|---|---|---|---|",
    ]
    selected_entries = sorted(
        (entry for entry in entries if entry.curation["status"] == "selected"),
        key=lambda entry: (-int(entry.curation["score"]), entry.skill_id),
    )
    for entry in selected_entries:
        lines.append(
            f"| {_category_label(categories[entry.category_id])} | "
            f"[`{entry.skill_id}`](../skills/{entry.skill_id}/) | "
            f"{_origin_label(entry)} | {_curation_label(entry)} | "
            f"{_runtime_label(entry)} | {_escape_markdown(str(entry.curation['reason']))} |"
        )

    provenance_groups = (
        ("project-original", "project-original-skills", "Project original", "Digest-backed first-party work with reviewed authorship."),
        ("adapted", "adapted-skills", "Adapted", "Modified from a named source with the adaptation recorded."),
        ("collected", "collected-skills", "Collected", "Preserved from a named source with provenance recorded."),
        ("unknown", "unknown-origin-skills", "Unknown origin", "Source review is incomplete; inspect before use."),
    )
    lines.extend(
        [
            "",
            "## ✨ Browse by provenance",
            "",
            "Choose a reviewed origin boundary before browsing by outcome. Provenance and curation evidence remain separate from runtime verification.",
            "",
            "| Origin | Meaning | Entries |",
            "|---|---|---:|",
        ]
    )
    for origin_id, anchor, title, meaning in provenance_groups:
        lines.append(
            f"| [{title}](#{anchor}) | {meaning} | {len(by_origin[origin_id])} |"
        )

    for origin_id, anchor, title, meaning in provenance_groups:
        lines.extend(
            [
                "",
                f'<a id="{anchor}"></a>',
                f"### {title}",
                "",
                meaning,
                "",
            ]
        )
        origin_entries = sorted(by_origin[origin_id], key=lambda entry: entry.skill_id)
        if not origin_entries:
            lines.append("No entries currently meet this provenance contract.")
            continue
        if origin_id == "unknown":
            lines.append(
                f"{len(origin_entries)} entries are awaiting source review. Use the "
                "[machine-readable index](./skill-index.json) or browse by outcome below; "
                "they are not promoted as curated recommendations."
            )
            continue
        lines.extend(
            [
                "| Skill | Outcome category | Provenance | Curation evidence | Runtime |",
                "|---|---|---|---|---|",
            ]
        )
        for entry in origin_entries:
            lines.append(
                f"| [`{entry.skill_id}`](../skills/{entry.skill_id}/) | "
                f"{_category_label(categories[entry.category_id])} | {_origin_label(entry)} | "
                f"{_curation_label(entry)} | {_runtime_label(entry)} |"
            )

    lines.extend(
        [
            "",
            "## 🗂️ Browse by outcome",
            "",
            f"This revision contains {len(entries)} canonical catalog entries. The number is generated here rather than used as a product claim.",
            "",
            "| Category | Use it for | Entries |",
            "|---|---|---:|",
        ]
    )
    for category in taxonomy["categories"]:
        lines.append(
            f"| [{_category_label(category)}](#{category['id']}) | "
            f"{_escape_markdown(category['description'])} | {counts[category['id']]} |"
        )

    for category in taxonomy["categories"]:
        category_id = category["id"]
        lines.extend(
            [
                "",
                f'<a id="{category_id}"></a>',
                f"## {_category_label(category)}",
                "",
                category["description"],
                "",
                "| Skill | What it helps with | Origin | Curation evidence | Support / review signals |",
                "|---|---|---|---|---|",
            ]
        )
        for entry in by_category[category_id]:
            roles = ", ".join(entry.used_by)
            support = _support_label(entry)
            if roles:
                support += f" · {roles}"
            if entry.review_signals:
                support += " · review: " + ", ".join(entry.review_signals)
            description = (
                entry.description
                if entry.description_status == "source-text"
                else "Description needs review; inspect source."
            )
            lines.append(
                f"| [`{entry.skill_id}`](../skills/{entry.skill_id}/) | "
                f"{_escape_markdown(description)} | {_origin_label(entry)} | "
                f"{_curation_label(entry)} | {support} |"
            )

    lines.extend(
        [
            "",
            "## 🛡️ Support, portability, and evidence boundary",
            "",
            "- **Curated:** reviewed and versioned inside a named distribution with its own sync policy.",
            "- **Pack-required:** referenced by an active Agent and covered by repository structure checks.",
            "- **Portable optional:** assigned to an Agent but not required for installation.",
            "- **Harness-specific:** assigned to an Agent but deliberately excluded from the generic installer because it assumes a named runtime or tool.",
            "- **Catalog:** tracked with a physical `SKILL.md`; behavior, dependencies, license, and harness support may still require review.",
            "- **External:** recommended by the manifest but not bundled in this repository.",
            "",
            "Review signals are conservative manual flags, not a complete safety analysis. Their absence does not establish safety. Classification is deterministic but not a quality score.",
            "",
            "A Curation evidence score is a digest-matched review of instruction design, resources, safety, provenance, and outcome evidence. It is not a runtime receipt; stale content hides the number until re-review.",
            "",
            "Inspect the source, permissions, dependencies, provenance, and license before use. Report a wrong category or missing risk flag through [an issue](https://github.com/aaaaqwq/AGI-Super-Team/issues).",
            "",
        ]
    )
    return "\n".join(lines)


def render_json(entries: list[SkillEntry], taxonomy: dict[str, Any]) -> str:
    counts = category_counts(entries, taxonomy)
    document = {
        "$schema": "../config/skill-index.schema.json",
        "schemaVersion": 2,
        "inventorySemantics": "tracked physical top-level directories with SKILL.md",
        "inventoryCount": len(entries),
        "categories": [
            {
                "id": item["id"],
                "emoji": item["emoji"],
                "title": item["title"],
                "description": item["description"],
                "count": counts[item["id"]],
            }
            for item in taxonomy["categories"]
        ],
        "skills": [
            {
                **asdict(entry),
                "used_by": list(entry.used_by),
                "assignments": [asdict(item) for item in entry.assignments],
                "review_signals": list(entry.review_signals),
                "path": f"skills/{entry.skill_id}/SKILL.md",
            }
            for entry in entries
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_or_check(path: Path, content: str, check: bool) -> bool:
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            print(f"STALE {path}", file=sys.stderr)
            return False
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
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
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    print(f"WROTE {path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    taxonomy = json.loads((root / TAXONOMY_PATH).read_text(encoding="utf-8"))
    entries = build_entries(root, taxonomy)
    success = _write_or_check(
        root / MARKDOWN_PATH, render_markdown(entries, taxonomy), arguments.check
    )
    success = _write_or_check(
        root / JSON_PATH, render_json(entries, taxonomy), arguments.check
    ) and success
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
