#!/usr/bin/env python3
"""
plan_visual_notes.py — 长文知识拆解 + 分镜规划 + Prompt 生成

Pipeline:
  文章 .md / text → 知识拆解 → 分镜规划 → 4-module 英文 Prompt → 输出文件

Usage:
  python3 plan_visual_notes.py --article article.md --style mixed --count 4
  python3 plan_visual_notes.py --text "$(cat article.txt)" --output out/

Author: Daniel Li · 2026-06-10
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ─── Constants ──────────────────────────────────────────────
SKILL_DIR = Path.home() / ".openclaw" / "skills" / "article-to-infographic"
TEMPLATE_FILE = SKILL_DIR / "references" / "prompt-template.md"

PROMPT_MAX_CHARS = 900  # Fit within image model 1000-char limit

STYLE_MAP = {
    "hand-written": "Hand-written Note",
    "mind-map": "Mind Map",
    "architecture": "Architecture / Logic Diagram",
    "comparison": "Comparison Chart",
    "mixed": "Mixed (auto-select)",
}

DEFAULT_FRAME_PLAN = [
    (1, "核心概念与定调", "hand-written", "概念定调/标题/核心隐喻"),
    (2, "核心竞争力与数据矩阵", "comparison", "对比矩阵/跑分数据/对标"),
    (3, "逻辑拆解与竞争分析", "mind-map", "思维导图/能力拆解/双边对比"),
    (4, "趋势演进与判断", "architecture", "架构图/趋势总结/行动建议"),
]

# ─── Content Extraction ─────────────────────────────────────
def extract_article_text(article_path: Optional[str], text_input: Optional[str]) -> str:
    """Load article from file or direct text input."""
    if text_input:
        return text_input.strip()
    if article_path:
        p = Path(article_path)
        if not p.exists():
            raise FileNotFoundError(f"Article not found: {article_path}")
        return p.read_text(encoding="utf-8").strip()
    raise ValueError("Either --article or --text is required")


def extract_sections(text: str) -> list[Tuple[str, str, str]]:
    """
    Extract key sections from Markdown article.
    Returns list of (heading, content, type) tuples.
    """
    sections = []
    # Match ## headings and their content
    pattern = r'(?:^|\n)(#{1,3})\s+(.+?)\n(.*?)(?=\n#{1,3}\s|\Z)'
    matches = list(re.finditer(pattern, text, re.DOTALL))

    if not matches:
        # No headings found → treat as single section
        sections.append(("全文", text[:2000], "text"))
        return sections

    for m in matches:
        level = m.group(1)
        title = m.group(2).strip()
        content = m.group(3).strip()
        # Determine section type
        section_type = "text"
        if any(kw in title + content for kw in ["跑分", "benchmark", "性能", "数据", "对比", "vs"]):
            section_type = "comparison"
        elif any(kw in title + content for kw in ["架构", "流程", "技术", "系统", "实现", "代码"]):
            section_type = "architecture"
        elif any(kw in title + content for kw in ["战略", "分析", "判断", "建议", "定价", "成本"]):
            section_type = "strategy"
        elif any(kw in title + content for kw in ["总结", "结论", "核心", "关键"]):
            section_type = "summary"

        # Truncate content for extraction
        short = content[:300] + ("..." if len(content) > 300 else "")
        sections.append((title, short, section_type))

    return sections


def extract_key_data(text: str) -> dict:
    """Extract key data points: numbers, benchmark scores, names, prices."""
    data = {
        "title": "",
        "subtitle": "",
        "benchmarks": [],    # (name, score)
        "comparisons": [],   # (label, value1, value2)
        "prices": [],        # (label, price)
        "key_terms": [],     # important proper nouns
        "conclusion": "",    # final takeaway line
    }

    # Extract H1 title
    h1_match = re.search(r'^#\s+(.+?)$', text, re.MULTILINE)
    if h1_match:
        data["title"] = h1_match.group(1).strip()

    # Extract subtitle/lead
    subtitle_match = re.search(r'^>\s*(.+?)$', text, re.MULTILINE)
    if subtitle_match:
        data["subtitle"] = subtitle_match.group(1).strip()[:100]

    # Extract benchmark scores (patterns like "80.3%" or "88.0%")
    for m in re.finditer(r'(\S+)\s*[：:]\s*\*{0,2}(\d+\.?\d*%)\*{0,2}', text):
        data["benchmarks"].append((m.group(1).strip()[-40:], m.group(2)))

    # Extract A vs B comparisons
    for m in re.finditer(r'(\S+?)\s*(?:是|不是|vs|VS|vs\.)\s*(\S+)', text):
        data["comparisons"].append((m.group(1).strip()[:30], "", m.group(2).strip()[:30]))

    # Extract prices ($XX/M or 元)
    for m in re.finditer(r'(\$\d+/\w+|¥\d+|人民币\s*\d+)', text):
        data["prices"].append(("价格", m.group(1)))

    # Extract key proper nouns (Capitalized terms, 2+ chars)
    seen = set()
    for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
        term = m.group(1)[:40]
        if term not in seen and len(term) > 5:
            data["key_terms"].append(term)
            seen.add(term)

    # Extract key Chinese terms (quoted or bold)
    for m in re.finditer(r'[「「]([^」」]{2,20})[」」]', text):
        data["key_terms"].append(f"「{m.group(1)}」")

    # Extract conclusion (last 200 chars often contain summary)
    data["conclusion"] = text.strip()[-200:].split("\n")[-1][:120]

    return data


# ─── Prompt Generation ──────────────────────────────────────
def generate_frame_prompt(
    frame_num: int,
    frame_theme: str,
    style: str,
    data: dict,
    sections: list,
) -> str:
    """
    Generate a 4-module English prompt for a single visual note frame.

    Args:
        frame_num: 1-based frame number
        frame_theme: Chinese theme name (e.g., "核心概念与定调")
        style: visual style key
        data: extracted data dict
        sections: extracted sections list

    Returns:
        Complete 4-module English prompt string.
    """
    title = data.get("title", "Article Analysis")
    subtitle = data.get("subtitle", "")

    STYLE_TEMPLATES = {
        "hand-written": _build_hand_written_prompt,
        "mind-map": _build_mind_map_prompt,
        "architecture": _build_architecture_prompt,
        "comparison": _build_comparison_prompt,
    }

    builder = STYLE_TEMPLATES.get(style, _build_hand_written_prompt)
    return builder(frame_num, frame_theme, title, subtitle, data, sections)


def _build_hand_written_prompt(frame_num, theme, title, subtitle, data, sections):
    """Build prompt for hand-written note style."""
    benchmarks_text = ""
    if data["benchmarks"]:
        items = [f"{name}: {score} ★" for name, score in data["benchmarks"][:4]]
        benchmarks_text = "\n- " + "\n- ".join(items)

    main_title = title if title else "Analysis Note"
    core_theme = theme

    prompt = f"""A photorealistic, ultra-clear, ultra-high-resolution close-up photograph of a dense hand-written study note on textured cream-white paper. The paper rests on a warm wooden desk. Soft natural window light from the upper-left creates gentle shadows. A black gel pen, red highlighter, and blue ballpoint lie beside the paper.

Title (top-center, large handwriting, black ink, bold): "{main_title}"
Subtitle below title (red ink, smaller): "{core_theme}"

Left side — bullet-point key concepts in black ink with red underlining for emphasis:{benchmarks_text if benchmarks_text else '\n- Key concept 1: ...\n- Key concept 2: ...\n- Key concept 3: ...'}

Right side — hand-drawn comparison box with 3-4 rows, blue annotation arrows connecting related points, one row circled in red marker for the most important finding.

Bottom section — horizontal line separator, then a one-sentence conclusion in blue ballpoint: "** CORE INSIGHT: The true value lies not in the headline numbers, but in... **"

Small hand-drawn star next to the most critical data point. Date "2026.06.10" in bottom-right corner.

The paper has slight edge curling, one small coffee stain ring on upper-right, natural imperfections. Shallow depth of field — desk lamp and laptop keyboard blurred in background. Warm afternoon study atmosphere.

Hand-written, dense notes, varied ink colors, black gel pen, red highlighter, blue ballpoint, legible text, natural paper texture, warm lighting, shallow depth of field, photorealistic, 8K, ultra-detailed, macro photography, study-vibe."""

    return prompt[:PROMPT_MAX_CHARS]


def _build_mind_map_prompt(frame_num, theme, title, subtitle, data, sections):
    """Build prompt for mind map style."""
    # Get section titles for branch labels
    branch_labels = [s[0][:20] for s in sections[:5]] if sections else [
        "Historical Context", "Current State", "Key Players", "Future Trends"
    ]
    while len(branch_labels) < 4:
        branch_labels.append("Additional Insight")

    # Build branch content
    branch_content = "\n".join([
        f"Branch 1 ({branch_labels[0] if len(branch_labels) > 0 else 'Overview'}, extending to upper-right, red marker):",
        f"  → Sub-node: various key data points",
        f"  → Sub-node: annotated with small text",
        f"",
        f"Branch 2 ({branch_labels[1] if len(branch_labels) > 1 else 'Analysis'}, extending to upper-left, blue marker):",
        f"  → Sub-node: strategic implications",
        f"  → Sub-node: competitive dynamics",
        f"",
        f"Branch 3 ({branch_labels[2] if len(branch_labels) > 2 else 'Comparison'}, extending to lower-right, green marker):",
        f"  → Sub-node: specific metrics and benchmarks",
        f"  → Sub-node: relative positioning",
        f"",
        f"Branch 4 ({branch_labels[3] if len(branch_labels) > 3 else 'Outlook'}, extending to lower-left, black marker):",
        f"  → Sub-node with star: most important takeaway",
    ])

    core = title[:40] if title else "Core Topic Analysis"

    prompt = f"""A photorealistic, top-down close-up photograph of a hand-drawn mind map on a large whiteboard with thin aluminum frame. Colorful dry-erase markers in red, blue, green, and black rest in the marker tray at bottom. The mind map radiates from a central oval bubble labeled in bold black marker: "{core}".

{branch_content}

Bottom-right corner: small blue handwriting "Author analysis" .

Small eraser smudges visible, markers partially used, subtle surface reflection from overhead lighting. Blurred office chairs in background.

Whiteboard mind map, hand-drawn, colorful markers, clean branching, clear hierarchy, legible text, overhead perspective, office setting, photorealistic, 8K, detailed texture, knowledge visualization."""

    return prompt[:PROMPT_MAX_CHARS]


def _build_architecture_prompt(frame_num, theme, title, subtitle, data, sections):
    """Build prompt for architecture / logic diagram style."""
    core = theme[:30]

    prompt = f"""A photorealistic, high-resolution photograph of a professional hand-drawn architecture diagram on a large sheet of grid paper, taped to a wall. The diagram uses black technical pen for structure and red/blue pens for annotations. Boxes connected by directional arrows show a clear progression flow.

Title (top center, bold black technical pen): "{core}"

Top row — 3 connected boxes with directional arrows (left to right):
Box 1: "Current State" → Box 2: "Transformation Event" → Box 3: "New Paradigm"

Middle row — 2 larger boxes:
Box 4 (left, blue outline): "Capability Layer" — sub-text listing specific capabilities in small handwriting
Box 5 (right, blue outline): "Constraint Layer" — sub-text listing limitations and trade-offs

Dotted-line annotations in red ink connecting specific elements:
- Red arrow pointing to middle of flow: "KEY INSIGHT HERE"
- Red arrow pointing to Box 5: "CRITICAL TRADE-OFF"

Bottom section — horizontal divider line, then summary box in blue pen:
"CONCLUSION: The gap between capability and constraint defines the opportunity space"

Grid paper slightly yellowed, taped with transparent tape at four corners (top-right slightly peeling). Mechanical pencil on wooden desk surface below. Natural daylight creating soft shadow.

Technical diagram, grid paper, precise penmanship, directional arrows, layered architecture, annotations, black technical pen, red correction marks, professional drafting, photorealistic, 8K, detailed line work."""

    return prompt[:PROMPT_MAX_CHARS]


def _build_comparison_prompt(frame_num, theme, title, subtitle, data, sections):
    """Build prompt for comparison matrix style."""
    benchmarks = data.get("benchmarks", [])
    if not benchmarks:
        benchmarks = [("Metric A", "XX%"), ("Metric B", "YY%"), ("Metric C", "ZZ%"), ("Metric D", "WW%")]

    bm_text = "\n".join([
        f'Row {i+1}:     │ "{name[:15]}" │ "{score if isinstance(score, str) else str(score)}" │ "vs" │ "competitor" │ "+XX%" │'
        for i, (name, score) in enumerate(benchmarks[:5])
    ])

    matrix_title = title[:40] if title else "Comparison Matrix"

    prompt = f"""A photorealistic, high-resolution close-up photograph of a dense hand-drawn comparison matrix table on off-white paper. The table is drawn with a black fountain pen, with red ink highlighting the winning values and blue ink for annotations. Each cell contains clear, legible numbers. The paper shows slight wear at the edges.

Title (top center, bold, black fountain pen): "{matrix_title}"

Table Structure (hand-drawn with ruler lines, visible grid):
Headers (bold, red underline):
│          │ "Model A"    │ "Model B"    │ "Model C"    │ "Advantage"  │

{bm_text}

Red ink circles around the highest/winning values in each row. Blue ink annotation arrows pointing to surprising results.

Bottom annotation in small blue handwriting: "Source: Official benchmarks, June 2026"
Large red handwriting at very bottom: "** CORE FINDING: ... **"

The paper lies flat on dark wooden desk. Small coffee ring upper-right. Black fountain pen with gold nib rests diagonally across bottom-right. Warm angled desk-lamp light from the left creates subtle shadows emphasizing the handwritten text. Smartphone blurred at frame edge.

Comparison matrix, hand-drawn table, fountain pen, red highlights, checkmarks, data visualization, legible text, ruler-drawn lines, warm lighting, photorealistic, 8K, detailed paper texture."""

    return prompt[:PROMPT_MAX_CHARS]


# ─── Storyboard Planning ────────────────────────────────────
def plan_storyboard(
    text: str,
    count: int = 4,
    style: str = "mixed",
) -> list[dict]:
    """
    Plan 3-5 visual note frames based on article content.

    Returns list of dicts: {num, theme, style, reason}
    """
    sections = extract_sections(text)
    data = extract_key_data(text)

    frames = []

    # Frame 1: Core concept & title (always hand-written)
    s1 = sections[0] if sections else ("核心概念", text[:200], "text")
    frames.append({
        "num": 1,
        "theme": f"核心概念：{s1[0][:25]}",
        "style": "hand-written",
        "reason": "概念定调与标题页",
    })

    # Frame 2: Comparison matrix (if data available)
    if len(data.get("benchmarks", [])) >= 2 or any(s[2] == "comparison" for s in sections):
        s2 = next((s for s in sections if s[2] == "comparison"), sections[1] if len(sections) > 1 else sections[0])
        frames.append({
            "num": len(frames) + 1,
            "theme": f"数据矩阵：{s2[0][:25]}",
            "style": "comparison",
            "reason": "跑分/对比数据矩阵页",
        })

    # Frame 3: Logic breakdown (mind map)
    if len(sections) > 2:
        s3 = sections[2] if len(sections) > 2 else sections[-1]
        frames.append({
            "num": len(frames) + 1,
            "theme": f"逻辑拆解：{s3[0][:25]}",
            "style": "mind-map",
            "reason": "能力拆解与竞争分析",
        })

    # Frame 4: Strategy/trend (architecture)
    strategy_sections = [s for s in sections if s[2] in ("strategy", "summary")]
    s4 = strategy_sections[0] if strategy_sections else (sections[-1] if len(sections) > 3 else sections[-1])
    frames.append({
        "num": len(frames) + 1,
        "theme": f"战略判断与行动建议",
        "style": "architecture",
        "reason": "趋势演进与决策框架",
    })

    # Frame 5 (optional, if count=5): Takeaways
    if count >= 5 and len(sections) >= 5:
        frames.append({
            "num": len(frames) + 1,
            "theme": "金句与行动清单",
            "style": "hand-written",
            "reason": "核心金句提炼页",
        })

    # Apply mixed style override
    if style != "mixed":
        for f in frames:
            if style in STYLE_MAP:
                f["style"] = style

    return frames[:count]


# ─── Output ─────────────────────────────────────────────────
def output_results(frames: list[dict], data: dict, sections: list, output_dir: Path):
    """Write analysis + prompts to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write Chinese summary
    summary_lines = [
        "# 📊 知识拆解与分镜规划",
        "",
        f"**文章主题**：{data.get('title', '未提取')}",
        f"**提取章节**：{len(sections)} 个",
        f"**规划分镜**：{len(frames)} 张",
        "",
        "---",
        "",
    ]

    for frame in frames:
        summary_lines.append(
            f"- **图 {frame['num']}：{frame['theme']}** — "
            f"[{STYLE_MAP.get(frame['style'], frame['style'])}] — {frame['reason']}"
        )

    summary_lines.extend([
        "",
        "---",
        "",
        "## 🎨 各分镜英文 Prompt",
        "",
    ])

    for frame in frames:
        summary_lines.append(f"- **图 {frame['num']}** → `frame-{frame['num']:02d}-prompt.txt`")

    summary_path = output_dir / "storyboard-summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    # Write individual prompt files
    for frame in frames:
        prompt_text = generate_frame_prompt(
            frame["num"],
            frame["theme"],
            frame["style"],
            data,
            sections,
        )
        prompt_path = output_dir / f"frame-{frame['num']:02d}-prompt.txt"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        print(f"✅ frame-{frame['num']:02d} — {frame['theme'][:30]} [{len(prompt_text)} chars]")

    print(f"\n📁 All outputs → {output_dir}/")
    print(f"   {summary_path.name}")
    for frame in frames:
        print(f"   frame-{frame['num']:02d}-prompt.txt")

    # Print a quick preview to stdout
    print(f"\n{'='*60}")
    print(summary_path.read_text(encoding="utf-8"))
    print(f"{'='*60}")


# ─── Main ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="长文 → 知识视觉笔记套图 Prompt 生成器"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--article", help="文章 Markdown 文件路径")
    input_group.add_argument("--text", help="纯文本输入")
    parser.add_argument("--style", default="mixed",
                        choices=["hand-written", "mind-map", "architecture", "comparison", "mixed"])
    parser.add_argument("--count", type=int, default=4, choices=[3, 4, 5])
    parser.add_argument("--output", default="./visual-notes/",
                        help="输出目录")
    parser.add_argument("--json", action="store_true",
                        help="仅输出 JSON (用于 Swift Agent 调用)")

    args = parser.parse_args()

    # Load article
    try:
        text = extract_article_text(args.article, args.text)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    # Extract
    sections = extract_sections(text)
    data = extract_key_data(text)

    if args.json:
        frames = plan_storyboard(text, args.count, args.style)
        result = {
            "title": data["title"],
            "section_count": len(sections),
            "frame_count": len(frames),
            "frames": frames,
            "data": {k: v for k, v in data.items() if k != "comparisons"},
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Plan storyboard
    frames = plan_storyboard(text, args.count, args.style)

    # Output
    output_dir = Path(args.output)
    output_results(frames, data, sections, output_dir)


if __name__ == "__main__":
    main()
