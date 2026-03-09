---
title: "feat: GOAT Synthesis Output - 15-Test Comparison and CROSS Improvement"
type: feat
status: completed
date: 2026-02-25
origin: docs/plans/2026-02-25-analysis-cross-source-comparison-plan.md
---

# GOAT Synthesis Output - 15-Test Comparison and CROSS Improvement

## Overview

The synthesis output - the "What I learned" / "I'm now an expert on X" narrative - is the ONLY thing that matters. All data collection, scoring, deduplication, and rendering exist solely to produce the best possible synthesis. This plan runs 15 synthesis comparisons (5 topics x 3 versions), judges which version produces the best final output, and creates concrete changes to make CROSS the GOAT.

## Problem Statement / Motivation

The previous 15-test comparison analyzed the data layer (JSON files, item counts, YouTube scores, cross-ref counts). That analysis showed CROSS wins on data quality metrics. But data quality != output quality. The user's exact words: "that's all that matters... all DATA/methods/etc. should be about making it the best fucking results ever."

The paper.design example shows what great output looks like:
- "Paper Desktop + MCP is the big story" - a specific, grounded finding
- "per @stephenhaney" / "per r/UXDesign" - actual source citations
- "698 likes on X" - real engagement numbers woven into narrative
- "KEY PATTERNS from the research:" - structured patterns, not vague summaries
- "---I'm now an expert on paper.design" - confident, actionable invitation

We need to see what Base, HN, and CROSS actually produce as narratives, side-by-side, for the same topics. Then fix CROSS until its output is undeniably the best.

## Approach: Controlled Synthesis Comparison

### Why not re-run `claude --print "/last30days X"` 15 times?

Three problems:
1. **WebSearch non-determinism** - Claude's WebSearch tool returns different results per run, confounding version comparison
2. **QUERY_TYPE non-determinism** - Claude classifies "best rap songs 2026" as RECOMMENDATIONS one run and GENERAL the next, producing structurally different outputs
3. **Reddit API non-determinism** - The existing JSON data shows Base got 4 Reddit items for Claude Code while CROSS got 10, purely from API timing

### The controlled approach

Reuse the 15 JSON files already captured (same-day, topic-sequential, verified clean). For each:

1. Convert JSON to compact markdown using each version's `render_compact()` (preserving version-specific rendering like CROSS's `[xref:]` tags)
2. Feed the compact markdown to Claude with the synthesis instructions from each version's SKILL.md
3. Hardcode QUERY_TYPE per topic to eliminate classification variance
4. Exclude WebSearch to isolate Python pipeline differences
5. Save all 15 synthesis outputs for side-by-side comparison

This gives us 15 synthesis narratives produced from identical underlying data, with only the version's rendering and synthesis instructions varying. The fairest possible comparison.

## The 5 Topics and Their QUERY_TYPEs

| # | Topic | QUERY_TYPE | Rationale |
|---|-------|------------|-----------|
| 1 | "Claude Code skills and MCP servers" | GENERAL | Broad understanding, not a ranked list |
| 2 | "Seedance AI video generation" | NEWS | Recent product launch, what's happening |
| 3 | "M4 MacBook Pro review" | RECOMMENDATIONS | "review" implies evaluation/ranking |
| 4 | "best rap songs 2026" | RECOMMENDATIONS | "best" triggers ranked list |
| 5 | "React vs Svelte 2026" | GENERAL | Framework debate, not ranked |

## Technical Approach

### Phase 1: Setup and Data Preservation

#### 1a. Copy JSON data to repo (CRITICAL - `/tmp` is ephemeral)

```bash
mkdir -p docs/comparison-results/json
cp /tmp/last30days-comparison/full/*.json docs/comparison-results/json/
```

- [x] Copy all 15 JSON files to `docs/comparison-results/json/`
- [x] Verify all 15 files are present and non-empty

#### 1b. Build JSON-to-compact converter

The render pipeline differs per version. We need each version's `render_compact()` to produce the compact markdown that version would actually show Claude.

**Script: `scripts/generate-synthesis-inputs.py`**

```python
"""
For each of the 15 JSON result files, render compact markdown
using that version's render_compact() function.

The JSON files store raw data. Each version's render.py formats
it differently (CROSS adds [xref:] tags, relevance scores, etc.).
"""
import json
import sys
sys.path.insert(0, 'scripts')
from lib.render import render_compact
from lib.schema import Report

for json_file in sorted(glob('docs/comparison-results/json/*.json')):
    data = json.load(open(json_file))
    report = Report.from_dict(data)
    compact = render_compact(report)
    # Save as .md alongside the JSON
    md_file = json_file.replace('/json/', '/compact/').replace('.json', '.md')
    open(md_file, 'w').write(compact)
```

Problem: `render_compact()` differs across Base/HN/CROSS. Solution: run the converter 3 times, once per git checkout, only for that version's files.

- [x] Write `scripts/generate-synthesis-inputs.py`
- [x] Run on Base checkout for `base-*.json` files -> `docs/comparison-results/compact/base-*.md`
- [x] Run on HN checkout for `hn-*.json` files -> `docs/comparison-results/compact/hn-*.md`
- [x] Run on CROSS checkout for `cross-*.json` files -> `docs/comparison-results/compact/cross-*.md`
- [x] Clean `__pycache__` between every git checkout

#### 1c. Extract synthesis prompts from each version's SKILL.md

Each version's SKILL.md contains the instructions Claude uses to synthesize the compact data into the narrative. These differ across versions (CROSS has cross-ref instructions, HN has HN citation rules, etc.).

- [x] Check out Base (427a4e4), copy SKILL.md synthesis section (Judge Agent + Display phases) to `docs/comparison-results/prompts/base-synthesis-prompt.md`
- [x] Check out HN (main), copy to `docs/comparison-results/prompts/hn-synthesis-prompt.md`
- [x] Check out CROSS (feat/youtube-relevance-cross-source), copy to `docs/comparison-results/prompts/cross-synthesis-prompt.md`
- [x] For each, prepend the hardcoded QUERY_TYPE and topic name

### Phase 2: Generate 15 Synthesis Outputs

#### 2a. Write the synthesis runner

**Script: `scripts/run-synthesis-comparison.py`**

For each of the 15 (topic, version) pairs:
1. Read the compact markdown from `docs/comparison-results/compact/{version}-{n}-{slug}.md`
2. Read the synthesis prompt from `docs/comparison-results/prompts/{version}-synthesis-prompt.md`
3. Call the Anthropic API (Claude Sonnet 4.6 for cost/speed, or Opus 4.6 for max quality - configurable)
4. Template: "You are running /last30days. The user asked about '{topic}'. QUERY_TYPE = {query_type}. Here is the research data:\n\n{compact_markdown}\n\n{synthesis_prompt}"
5. Save response to `docs/comparison-results/synthesis/{version}-{n}-{slug}.md`

```python
"""
Generate synthesis narratives for all 15 test cases.
Uses Anthropic API directly to control the synthesis environment.
"""
import anthropic
import os
from pathlib import Path

client = anthropic.Anthropic()

TOPICS = [
    (1, 'claude-code', 'Claude Code skills and MCP servers', 'GENERAL'),
    (2, 'seedance', 'Seedance AI video generation', 'NEWS'),
    (3, 'macbook', 'M4 MacBook Pro review', 'RECOMMENDATIONS'),
    (4, 'rap', 'best rap songs 2026', 'RECOMMENDATIONS'),
    (5, 'react-svelte', 'React vs Svelte 2026', 'GENERAL'),
]
VERSIONS = ['base', 'hn', 'cross']

for version in VERSIONS:
    prompt_text = Path(f'docs/comparison-results/prompts/{version}-synthesis-prompt.md').read_text()
    for num, slug, topic, qtype in TOPICS:
        compact = Path(f'docs/comparison-results/compact/{version}-{num}-{slug}.md').read_text()

        user_msg = f"""You are the /last30days skill. The user asked: "{topic}"

Parsed intent:
- TOPIC = {topic}
- TARGET_TOOL = unknown
- QUERY_TYPE = {qtype}

Here is the research output from the Python pipeline:

{compact}

Now synthesize this research into your expert narrative following these instructions:

{prompt_text}"""

        response = client.messages.create(
            model=os.environ.get('SYNTHESIS_MODEL', 'claude-sonnet-4-6-20250514'),
            max_tokens=4096,
            messages=[{"role": "user", "content": user_msg}]
        )

        output = response.content[0].text
        out_path = Path(f'docs/comparison-results/synthesis/{version}-{num}-{slug}.md')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output)
        print(f'  {version}-{num}-{slug}: {len(output)} chars')
```

- [x] Write `scripts/run-synthesis-comparison.py`
- [x] Run it (15 API calls, ~2-3 min total)
- [x] Verify all 15 synthesis files exist and are non-empty

#### 2b. Quality check synthesis outputs

Spot-check 3 outputs (one per version) for:
- Did Claude actually produce a "What I learned" narrative?
- Are there real citations (per @handle, per r/subreddit)?
- Is the stats block present?
- Is there an invitation at the end?

If any output is broken (e.g., Claude refused or produced meta-commentary instead of synthesis), adjust the prompt and re-run that one.

- [x] Spot-check `cross-1-claude-code.md`, `hn-2-seedance.md`, `base-4-rap.md`
- [x] Fix any prompt issues and re-run failed outputs

### Phase 3: Evaluate - Which Version Produces the Best Output?

#### 3a. Define evaluation rubric (BEFORE reading any outputs)

Score each synthesis 1-5 on these dimensions:

| Dimension | Weight | 1 (Bad) | 3 (OK) | 5 (Great) |
|-----------|--------|---------|--------|-----------|
| **Groundedness** | 30% | Generic statements, no citations | Some citations but mixed with pre-trained knowledge | Every finding backed by specific source (per @handle, per r/sub, per channel) |
| **Specificity** | 25% | Vague ("AI video tools are improving") | Some specifics but also filler | Named entities, exact numbers, product versions ("Seedance 2.0 added lip sync per @aifilmmaker") |
| **Coverage** | 20% | Only mentions 1-2 sources | Mentions most sources but unevenly | Weaves findings from Reddit, X, YouTube, HN naturally into narrative |
| **Actionability** | 15% | "This is interesting" with no next step | Generic suggestions | Specific, research-derived suggestions ("I can show you Seedance 2.0's lip sync workflow") |
| **Format Compliance** | 10% | Missing stats block, no invitation | Partial stats, generic invitation | Perfect stats block with real counts, source-specific invitation |

Total: weighted average, 1.0 to 5.0

#### 3b. LLM-as-judge evaluation (blinded)

**Script: `scripts/evaluate-synthesis.py`**

For each topic (5 total), present all 3 versions to an evaluator LLM with version labels stripped. Ask it to score each on the rubric above.

```python
"""
Blinded LLM evaluation of synthesis outputs.
Strips version labels, presents as Version A/B/C in random order.
"""
import anthropic
import random

RUBRIC = """Score each version 1-5 on these dimensions:

1. GROUNDEDNESS (30%): Does the narrative cite specific sources?
   Look for: "per @handle", "per r/subreddit", "per [channel] on YouTube"
   1 = generic, no citations. 5 = every finding has a source.

2. SPECIFICITY (25%): Are findings specific or vague?
   1 = "AI video is trending". 5 = "Seedance 2.0 added lip sync, 698 likes per @paper"

3. COVERAGE (20%): Does it represent findings from all available sources?
   1 = only Reddit mentioned. 5 = Reddit, X, YouTube, HN woven naturally.

4. ACTIONABILITY (15%): Does the invitation give specific next steps based on research?
   1 = "let me know if you want more". 5 = "I can walk you through Seedance 2.0's workflow"

5. FORMAT COMPLIANCE (10%): Stats block present with real counts? Citation format correct?
   1 = missing stats. 5 = perfect stats block + source counts + top voices.

For each version, output:
- Groundedness: X/5
- Specificity: X/5
- Coverage: X/5
- Actionability: X/5
- Format: X/5
- Weighted Total: X.X/5.0
- One sentence on what makes this version better or worse than the others.
"""

# For each topic, randomly shuffle version order to prevent position bias
for topic in TOPICS:
    versions = ['base', 'hn', 'cross']
    random.shuffle(versions)
    label_map = {v: chr(65+i) for i, v in enumerate(versions)}  # A, B, C

    # Present to evaluator
    prompt = f"Topic: {topic}\n\n"
    for v in versions:
        text = read_synthesis(v, topic)
        prompt += f"=== VERSION {label_map[v]} ===\n{text}\n\n"
    prompt += RUBRIC

    # Call evaluator (use Opus for best judgment)
    response = evaluate(prompt)
    # Map labels back to versions
    save_evaluation(topic, response, label_map)
```

- [x] Write `scripts/evaluate-synthesis.py`
- [x] Run evaluation (5 API calls, one per topic)
- [x] Collect scores into summary table

#### 3c. Human spot-check

Read 3 synthesis outputs yourself (one per version, same topic) and verify the LLM evaluation makes sense. If the LLM scores don't match your gut, investigate.

- [x] Read all 3 versions for topic 1 (Claude Code) side-by-side
- [x] Read all 3 versions for topic 2 (Seedance) side-by-side
- [x] Verify LLM scores align with human judgment

#### 3d. Compile verdict

| Topic | Base | HN | CROSS | Winner |
|-------|------|-----|-------|--------|
| Claude Code | X.X | X.X | X.X | ? |
| Seedance | X.X | X.X | X.X | ? |
| MacBook | X.X | X.X | X.X | ? |
| Rap songs | X.X | X.X | X.X | ? |
| React/Svelte | X.X | X.X | X.X | ? |
| **Overall** | **X.X** | **X.X** | **X.X** | **?** |

Plus per-dimension breakdown:
- Which version is best at Groundedness?
- Which version is best at Specificity?
- Which version is best at Coverage?
- Which version is best at Actionability?
- Which version is best at Format Compliance?

- [x] Build summary table with scores
- [x] Identify per-dimension winners
- [x] Write verdict paragraph

### Phase 4: Make CROSS the GOAT

Based on the evaluation, identify the specific synthesis weaknesses and fix them. Changes fall into two buckets:

#### Bucket A: Data pipeline changes (score.py, dedupe.py, render.py, youtube_yt.py)

These affect what compact markdown Claude sees. From the previous JSON analysis, known issues:

1. **Cross-source linking nearly broken** (3/178 items linked at 0.5 threshold)
   - Fix: hybrid similarity (token + trigram Jaccard) at 0.40 threshold
   - File: `scripts/lib/dedupe.py`
   - Expected impact: 26 items linked instead of 3

2. **Cross-ref rendering cryptic** (`[xref: HN5, HN4]` is meaningless)
   - Fix: Show `[also on: HN, Reddit]` with source names
   - File: `scripts/lib/render.py`
   - Expected impact: Claude can naturally say "discussed on both Reddit and HN"

3. **YouTube synonym gap** ("hip hop" != "rap" in relevance scoring)
   - Fix: SYNONYMS dict in youtube_yt.py
   - File: `scripts/lib/youtube_yt.py`
   - Expected impact: "Lit Hip Hop Mix 2026" gets 0.67+ instead of 0.33

4. **HN search too narrow** (React/Svelte returns 0 HN items)
   - Fix: Split multi-keyword topics into OR queries for HN Algolia
   - File: `scripts/lib/hackernews.py` (or wherever HN search lives)
   - Expected impact: Framework debate topics get HN coverage

#### Bucket B: Synthesis instruction changes (SKILL.md)

These affect how Claude interprets the data. Specific changes to discover from the 15-output comparison:

5. **Cross-source narrative instruction** - If CROSS data has `[also on: HN, Reddit]` tags but Claude ignores them, add explicit instruction: "When items appear across multiple platforms, lead with that cross-platform signal - it's the strongest evidence of importance."

6. **YouTube transcript utilization** - CROSS provides transcript snippets. If Claude's synthesis doesn't use them, add: "YouTube transcripts contain direct quotes and technical details. Weave 1-2 transcript quotes into your synthesis."

7. **Source weighting for synthesis** - Current: Reddit/X > YouTube > Web. Should HN be weighted higher for tech topics? Should YouTube transcript content elevate YouTube's synthesis weight?

8. **Citation density tuning** - The paper.design example has ~1 citation per paragraph. If any version over-cites (every sentence) or under-cites (no sources), adjust the citation frequency instruction.

9. **Stats block accuracy** - Verify each version's stats block matches actual data. If counts are wrong, the render output may need to include pre-computed stats that Claude can copy directly.

10. **Invitation quality** - The best invitations reference specific things from the research ("I can walk you through Seedance 2.0's lip sync workflow"). If a version produces generic invitations ("let me know if you want to know more"), strengthen the instruction.

Changes 5-10 are discovered from Phase 3 analysis. They may or may not apply.

- [x] Implement Bucket A changes (data pipeline fixes from JSON analysis)
- [x] Analyze Phase 3 results to identify Bucket B changes needed
- [x] Implement Bucket B changes (SKILL.md synthesis instruction improvements)
- [x] Run `bash scripts/sync.sh` to deploy updated skill

### Phase 5: Validate

Re-run 5 synthesis outputs (one per topic, CROSS-after only) using the improved CROSS code, and compare against CROSS-before.

- [x] Generate 5 new compact markdowns from JSON data using improved render.py
- [x] Generate 5 new synthesis outputs using improved SKILL.md
- [x] Score with same rubric (LLM-as-judge, blinded against CROSS-before)
- [x] Verify improvement on every dimension, or iterate

## File Structure

```
docs/comparison-results/
  json/                          # 15 JSON files (already exist at /tmp, need copying)
    base-1-claude-code.json
    hn-1-claude-code.json
    cross-1-claude-code.json
    ... (15 total)
  compact/                       # 15 compact markdown files (rendered per-version)
    base-1-claude-code.md
    hn-1-claude-code.md
    cross-1-claude-code.md
    ... (15 total)
  prompts/                       # 3 synthesis prompts (extracted from each SKILL.md)
    base-synthesis-prompt.md
    hn-synthesis-prompt.md
    cross-synthesis-prompt.md
  synthesis/                     # 15 synthesis narratives (the actual output!)
    base-1-claude-code.md
    hn-1-claude-code.md
    cross-1-claude-code.md
    ... (15 total)
  evaluation/                    # 5 evaluation results (one per topic, blinded)
    eval-1-claude-code.md
    eval-2-seedance.md
    eval-3-macbook.md
    eval-4-rap.md
    eval-5-react-svelte.md
  summary.md                     # Final verdict with all scores and improvement plan

scripts/
  generate-synthesis-inputs.py   # JSON -> compact converter
  run-synthesis-comparison.py    # Compact + prompt -> synthesis via Claude API
  evaluate-synthesis.py          # Blinded LLM evaluation
```

## Acceptance Criteria

- [x] All 15 JSON files preserved in `docs/comparison-results/json/`
- [x] All 15 compact markdowns generated (version-specific rendering preserved)
- [x] All 3 synthesis prompts extracted from version-specific SKILL.md files
- [x] All 15 synthesis narratives generated and saved
- [x] All 15 syntheses scored on 5-dimension rubric (blinded, LLM-as-judge)
- [x] Summary table shows per-topic and overall winner
- [x] At least 3 synthesis outputs human-spot-checked against LLM scores
- [x] CROSS improvement plan includes both data pipeline (Bucket A) and synthesis instruction (Bucket B) changes
- [x] Bucket A changes implemented with tests
- [x] Bucket B changes implemented and deployed via sync.sh
- [x] 5 validation synthesis outputs show improvement over CROSS-before
- [x] Final summary.md documents everything: scores, verdict, changes, validation

## Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| `/tmp` data loss before copying | Phase 1a is the first action - copy immediately |
| Claude API rate limits during synthesis | 15 calls is well under limits; add 2s sleep between calls |
| LLM evaluator bias toward longer outputs | Rubric weights specificity and groundedness, not length |
| QUERY_TYPE affecting output format | Hardcoded per topic in synthesis prompt |
| Reddit item-count variance confounding comparison | Note caveat; flag topics where counts differ >30% |
| render_compact() crash on JSON data | Test converter on 1 file before batch run |

## Technical Considerations

### Why Anthropic API instead of `claude --print`?

1. **Controlled environment** - Same model, same temperature, same max_tokens for all 15
2. **No WebSearch confound** - API calls don't have tool access unless we grant it
3. **Reproducible** - Can re-run with different models or prompts
4. **Faster** - API call takes ~10s vs ~3min for full `claude --print` with tools

### Why reuse JSON data instead of re-running the pipeline?

1. **Eliminates temporal non-determinism** - Same Reddit/X/YouTube data for all comparisons
2. **No rate limiting** - Zero API calls to source platforms
3. **Already validated** - 15 files verified clean, zero errors
4. **Still tests rendering differences** - Each version's render_compact() runs on its checkout

### What about the WebSearch step?

The full skill pipeline includes Claude doing WebSearch after the Python script. We deliberately exclude this because:
1. WebSearch results vary per run (different web results each time)
2. WebSearch is identical across all 3 versions (no version difference to test)
3. Including it would confound the comparison with noise
4. The Python pipeline data is where version differences live

## Sources & References

- Previous JSON analysis: [docs/plans/2026-02-25-analysis-cross-source-comparison-plan.md](docs/plans/2026-02-25-analysis-cross-source-comparison-plan.md) - data-layer comparison with scoring verdict
- Previous test plan: [docs/plans/2026-02-25-feat-15-test-comparison-make-cross-goat-plan.md](docs/plans/2026-02-25-feat-15-test-comparison-make-cross-goat-plan.md) - execution protocol for 15 JSON test runs
- SKILL.md synthesis instructions: `SKILL.md` lines 165-320 (Judge Agent + Display phases)
- Scoring weights: `scripts/lib/score.py` - 45% relevance + 25% recency + 30% engagement
- Render pipeline: `scripts/lib/render.py:57` - `render_compact()` function
- Cross-source linking: `scripts/lib/dedupe.py:160` - `cross_source_link()` function
- YouTube relevance: `scripts/lib/youtube_yt.py` - `_compute_relevance()` token overlap
- Existing test harness: `scripts/test-v1-vs-v2.sh:104` - `claude --print` approach
- YouTube display bug: `docs/plans/2026-02-15-fix-youtube-display-and-search-quality-plan.md`
- Output formatting fixes: `docs/plans/2026-02-06-fix-last30days-v2-formatting-reddit-citations-plan.md`
