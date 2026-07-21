#!/usr/bin/env python3
"""Build the deterministic, task-oriented skill catalog."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from repository_model import load_manifest, physical_skill_names


TAXONOMY_PATH = Path("config/skill-taxonomy.json")
MARKDOWN_PATH = Path("catalog/README.md")
JSON_PATH = Path("catalog/skill-index.json")
MAX_DESCRIPTION = 180
DESCRIPTION_EXCLUDED_PATTERNS = {
    "(?:^|-)agent(?:-|$)",
    "(?:^|-)skills?(?:-|$)",
    "(?:^|-)model(?:-|$)",
    "team",
}
DESCRIPTION_REVIEW_PATTERN = re.compile(
    r"(?i)(?:\bnever lost\b|\bguaranteed\b|\bproduction[- ]ready\b|"
    r"\b100%|\bsave \d+%|this skill provides automated assistance|"
    r"\bTODO\b|输出示例|```|<script|^---$|"
    r"(?:\b(?:and|or|with|to|from|when|for)|\b[a-zA-Z])$)"
)


@dataclass(frozen=True)
class SkillEntry:
    skill_id: str
    category_id: str
    description: str
    support_level: str
    used_by: tuple[str, ...]
    review_signals: tuple[str, ...]
    description_status: str
    classification: str


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


def _classify(
    skill_id: str, description: str, taxonomy: dict[str, Any]
) -> tuple[str, str]:
    overrides = taxonomy.get("overrides", {})
    if skill_id in overrides:
        return str(overrides[skill_id]), "override"

    slug, combined = _classification_text(skill_id, description)
    for source, text in (("slug", slug), ("description", combined)):
        best_category = ""
        best_score = 0
        best_priority = -1
        best_patterns: list[str] = []
        for category in taxonomy["categories"]:
            if category.get("fallback"):
                continue
            matched = [
                pattern
                for pattern in category["patterns"]
                if not (source == "description" and pattern in DESCRIPTION_EXCLUDED_PATTERNS)
                and re.search(pattern, text, re.IGNORECASE)
            ]
            score = len(matched)
            priority = category["priority"]
            if score and (score, priority) > (best_score, best_priority):
                best_score = score
                best_priority = priority
                best_category = category["id"]
                best_patterns = matched
        if best_category:
            return best_category, f"{source}:" + ",".join(best_patterns)
    fallback = next(item["id"] for item in taxonomy["categories"] if item.get("fallback"))
    return fallback, "fallback"


def _agent_usage(root: Path) -> tuple[dict[str, set[str]], set[str]]:
    manifest = load_manifest(root)
    usage: dict[str, set[str]] = defaultdict(set)
    required: set[str] = set()
    for agent in manifest["agents"]:
        for skill in agent["skills"]["required"]:
            usage[skill].add(agent["id"].upper())
            required.add(skill)
        for skill in agent["skills"].get("optional", []):
            usage[skill].add(agent["id"].upper())
    return usage, required


def _validate_taxonomy(taxonomy: dict[str, Any], skill_names: set[str]) -> None:
    if taxonomy.get("$schema") != "./skill-taxonomy.schema.json":
        raise ValueError("taxonomy must reference ./skill-taxonomy.schema.json")
    if taxonomy.get("schemaVersion") != 1:
        raise ValueError("taxonomy schemaVersion must be 1")

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
        for pattern in category["patterns"]:
            if not pattern:
                raise ValueError(f"empty pattern in category {category['id']}")
            re.compile(pattern)

    known_categories = set(category_ids)
    overrides = taxonomy.get("overrides", {})
    if set(overrides) - skill_names:
        raise ValueError(f"taxonomy overrides reference missing skills: {sorted(set(overrides) - skill_names)}")
    if set(overrides.values()) - known_categories:
        raise ValueError("taxonomy overrides reference unknown categories")

    risk_labels = [item["id"] for item in taxonomy.get("riskLabels", [])]
    if len(risk_labels) != len(set(risk_labels)):
        raise ValueError("risk label ids must be unique")
    risk_overrides = taxonomy.get("riskOverrides", {})
    if set(risk_overrides) - skill_names:
        raise ValueError("risk overrides reference missing skills")
    for signals in risk_overrides.values():
        if set(signals) - set(risk_labels):
            raise ValueError("risk overrides reference unknown labels")

    featured_ids = [item["skill"] for item in taxonomy.get("featured", [])]
    if len(featured_ids) != len(set(featured_ids)):
        raise ValueError("featured skill ids must be unique")
    if set(featured_ids) - skill_names:
        raise ValueError("featured list references missing skills")


def build_entries(root: Path, taxonomy: dict[str, Any]) -> list[SkillEntry]:
    skill_names = physical_skill_names(root)
    _validate_taxonomy(taxonomy, skill_names)
    usage, required = _agent_usage(root)
    known_risks = {item["id"] for item in taxonomy.get("riskLabels", [])}
    entries: list[SkillEntry] = []
    for skill_id in sorted(skill_names):
        description, metadata_source = _display_description(
            root / "skills" / skill_id / "SKILL.md", skill_id
        )
        category_id, classification = _classify(skill_id, description, taxonomy)
        review_signals = tuple(sorted(taxonomy.get("riskOverrides", {}).get(skill_id, [])))
        unknown_risks = set(review_signals) - known_risks
        if unknown_risks:
            raise ValueError(f"unknown review signal(s) for {skill_id}: {sorted(unknown_risks)}")
        entries.append(
            SkillEntry(
                skill_id=skill_id,
                category_id=category_id,
                description=description,
                support_level="pack-required" if skill_id in required else "catalog",
                used_by=tuple(sorted(usage.get(skill_id, set()))),
                review_signals=review_signals,
                description_status=_description_status(description),
                classification=f"{classification};metadata:{metadata_source}",
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


def render_markdown(entries: list[SkillEntry], taxonomy: dict[str, Any]) -> str:
    categories = {item["id"]: item for item in taxonomy["categories"]}
    counts = category_counts(entries, taxonomy)
    by_category: dict[str, list[SkillEntry]] = defaultdict(list)
    by_id = {entry.skill_id: entry for entry in entries}
    for entry in entries:
        by_category[entry.category_id].append(entry)

    lines = [
        "<!-- Generated by scripts/build_skill_catalog.py. Do not edit by hand. -->",
        "",
        "# Skill catalog",
        "",
        "Find a skill by the outcome you need. This index is generated from tracked, physical `SKILL.md` entrypoints; catalog inclusion proves structure, not behavior or cross-harness compatibility.",
        "",
        "## Suggested starting points",
        "",
        "For a first run, prefer a [starter kit](../starter-kits/) or the [Codex package](../.codex/INDEX.md). These are navigation aids, not claims of behavioral verification or a ranking of the full library.",
        "",
        "| Goal | Skill | Support | Why start here |",
        "|---|---|---|---|",
    ]
    for item in taxonomy["featured"]:
        entry = by_id[item["skill"]]
        support = (
            "Referenced by active Agent · structure checked"
            if entry.support_level == "pack-required"
            else "Catalog only"
        )
        if entry.review_signals:
            support += " · review: " + ", ".join(entry.review_signals)
        lines.append(
            f"| {categories[item['category']]['title']} | "
            f"[`{entry.skill_id}`](../skills/{entry.skill_id}/) | "
            f"{support} | {_escape_markdown(item['reason'])} |"
        )

    lines.extend(
        [
            "",
            "## Browse by outcome",
            "",
            f"This revision contains {len(entries)} canonical catalog entries. The number is generated here rather than used as a product claim.",
            "",
            "| Category | Use it for | Entries |",
            "|---|---|---:|",
        ]
    )
    for category in taxonomy["categories"]:
        lines.append(
            f"| [{category['title']}](#{category['id']}) | "
            f"{_escape_markdown(category['description'])} | {counts[category['id']]} |"
        )

    for category in taxonomy["categories"]:
        category_id = category["id"]
        lines.extend(
            [
                "",
                f'<a id="{category_id}"></a>',
                f"## {category['title']}",
                "",
                category["description"],
                "",
                "| Skill | What it helps with | Support / review signals |",
                "|---|---|---|",
            ]
        )
        for entry in by_category[category_id]:
            roles = ", ".join(entry.used_by)
            support = (
                "Referenced by active Agent · structure checked"
                if entry.support_level == "pack-required"
                else "Catalog only"
            )
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
                f"{_escape_markdown(description)} | {support} |"
            )

    lines.extend(
        [
            "",
            "## Support levels and evidence boundary",
            "",
            "- **Curated:** reviewed and versioned inside a named distribution with its own sync policy.",
            "- **Pack-required:** referenced by an active Agent and covered by repository structure checks.",
            "- **Catalog:** tracked with a physical `SKILL.md`; behavior, dependencies, license, and harness support may still require review.",
            "- **External:** recommended by the manifest but not bundled in this repository.",
            "",
            "Review signals are conservative manual flags, not a complete safety analysis. Their absence does not establish safety. Classification is deterministic but not a quality score.",
            "",
            "Inspect the source, permissions, dependencies, provenance, and license before use. Report a wrong category or missing risk flag through [an issue](https://github.com/aaaaqwq/AGI-Super-Team/issues).",
            "",
        ]
    )
    return "\n".join(lines)


def render_json(entries: list[SkillEntry], taxonomy: dict[str, Any]) -> str:
    counts = category_counts(entries, taxonomy)
    document = {
        "schemaVersion": 1,
        "inventorySemantics": "tracked physical top-level directories with SKILL.md",
        "inventoryCount": len(entries),
        "categories": [
            {
                "id": item["id"],
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
    path.write_text(content, encoding="utf-8")
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
