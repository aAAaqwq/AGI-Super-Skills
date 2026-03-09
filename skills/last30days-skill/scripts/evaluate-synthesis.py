#!/usr/bin/env python3
"""Evaluate synthesis outputs using a blinded comparison rubric.

Reads from docs/comparison-results/synthesis/, evaluates each topic's
3 versions (base, hn, cross) on a 5-dimension rubric.

Since we can't call the Anthropic API directly (no SDK installed),
this script formats the evaluation prompts for manual evaluation
and provides a framework for scoring.
"""
import random
from pathlib import Path

SYNTHESIS_DIR = Path(__file__).parent.parent / "docs" / "comparison-results" / "synthesis"
EVAL_DIR = Path(__file__).parent.parent / "docs" / "comparison-results" / "evaluation"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

TOPICS = [
    (1, 'claude-code', 'Claude Code skills and MCP servers', 'GENERAL'),
    (2, 'seedance', 'Seedance AI video generation', 'NEWS'),
    (3, 'macbook', 'M4 MacBook Pro review', 'RECOMMENDATIONS'),
    (4, 'rap', 'best rap songs 2026', 'RECOMMENDATIONS'),
    (5, 'react-svelte', 'React vs Svelte 2026', 'GENERAL'),
]
VERSIONS = ['base', 'hn', 'cross']

RUBRIC = """## Evaluation Rubric

Score each version 1-5 on these dimensions:

### 1. GROUNDEDNESS (30%)
Does the narrative cite specific sources from the research data?
- 1: Generic statements, no citations, could be written without any research
- 3: Some citations but mixed with pre-existing knowledge filler
- 5: Every finding backed by a specific source ("per @handle", "per r/sub", "per [channel]")

### 2. SPECIFICITY (25%)
Are findings specific (named entities, exact numbers) or vague?
- 1: Vague generalities ("AI video tools are improving", "developers are debating frameworks")
- 3: Some specifics mixed with generic padding
- 5: Named products, exact numbers, version names ("Seedance 2.0 added lip sync", "698 likes")

### 3. COVERAGE (20%)
Does the synthesis represent findings from all available data sources?
- 1: Only mentions 1-2 sources, ignores others
- 3: Mentions most sources but unevenly weighted
- 5: Naturally weaves Reddit, X, YouTube (and HN if available) into the narrative

### 4. ACTIONABILITY (15%)
Does the invitation give specific, research-derived next steps?
- 1: Generic "let me know if you want more info"
- 3: Somewhat specific but not clearly grounded in research findings
- 5: Each suggestion references a specific thing from the research ("I can compare Seedance 2.0 vs Kling")

### 5. FORMAT COMPLIANCE (10%)
Does it follow the expected output format?
- 1: Missing stats block, no invitation, wrong structure
- 3: Partial stats block, generic invitation
- 5: Perfect stats block with real counts, source box-drawing chars, top voices identified
"""

for num, slug, topic, qtype in TOPICS:
    # Randomly assign labels to prevent position bias
    versions_shuffled = list(VERSIONS)
    random.seed(num * 42)  # Deterministic but different per topic
    random.shuffle(versions_shuffled)
    label_map = {v: chr(65 + i) for i, v in enumerate(versions_shuffled)}
    reverse_map = {chr(65 + i): v for i, v in enumerate(versions_shuffled)}

    lines = []
    lines.append(f"# Evaluation: {topic}")
    lines.append(f"")
    lines.append(f"**Query Type:** {qtype}")
    lines.append(f"**Label Map (REVEAL AFTER SCORING):** {reverse_map}")
    lines.append(f"")
    lines.append(RUBRIC)
    lines.append("")

    for v in versions_shuffled:
        label = label_map[v]
        synthesis_file = SYNTHESIS_DIR / f"{v}-{num}-{slug}.md"
        if synthesis_file.exists():
            content = synthesis_file.read_text()
        else:
            content = f"[FILE NOT FOUND: {synthesis_file}]"

        lines.append(f"---")
        lines.append(f"## VERSION {label}")
        lines.append(f"")
        lines.append(content)
        lines.append(f"")

    lines.append("---")
    lines.append("## SCORES")
    lines.append("")
    for v in versions_shuffled:
        label = label_map[v]
        lines.append(f"### Version {label}")
        lines.append(f"- Groundedness: /5")
        lines.append(f"- Specificity: /5")
        lines.append(f"- Coverage: /5")
        lines.append(f"- Actionability: /5")
        lines.append(f"- Format: /5")
        lines.append(f"- **Weighted Total**: /5.0")
        lines.append(f"- Best/worst aspect: ")
        lines.append(f"")

    lines.append("## VERDICT")
    lines.append("")
    lines.append(f"**Winner for {topic}:** ")
    lines.append(f"**Why:** ")
    lines.append("")
    lines.append(f"**Reveal:** {reverse_map}")

    eval_file = EVAL_DIR / f"eval-{num}-{slug}.md"
    eval_file.write_text("\n".join(lines))
    print(f"  {eval_file.name}: {len(lines)} lines, labels: {reverse_map}")

print(f"\n{len(TOPICS)} evaluation files written to {EVAL_DIR}")
print("Next step: Read each file, score the versions, fill in SCORES section")
