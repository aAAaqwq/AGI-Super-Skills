# GOAT Synthesis Comparison: Final Results

## Overall Winner: CROSS (4.74/5.0)

| Pipeline | Topic 1 | Topic 2 | Topic 3 | Topic 4 | Topic 5 | **Average** |
|----------|---------|---------|---------|---------|---------|------------|
| | Claude Code | Seedance | MacBook | Rap Songs | React/Svelte | |
| **CROSS** | **4.90** | **4.90** | **4.20** | **4.80** | **4.90** | **4.74** |
| **HN** | 4.05 | 4.55 | 3.85 | 4.25 | 3.80 | **4.10** |
| **Base** | 3.80 | 3.70 | 3.70 | 3.65 | 3.80 | **3.73** |

CROSS won all 5 topics. No regressions.

## Per-Dimension Analysis

### Groundedness (30% weight)
| Pipeline | Avg | Pattern |
|----------|-----|---------|
| CROSS | 4.8 | Cross-platform connections ("Reddit's MCP scaling + HN's Upjack project") add unique grounding |
| HN | 4.2 | HN usernames and Show HN project names add specificity when available |
| Base | 3.8 | Solid citations but narrower source pool limits grounding depth |

### Specificity (25% weight)
| Pipeline | Avg | Pattern |
|----------|-----|---------|
| CROSS | 4.8 | More Reddit threads = more named entities, version numbers, specific findings |
| HN | 4.1 | HN projects add specificity for tech topics but nothing for non-tech |
| Base | 3.6 | Fewer data points = more padding between specific findings |

### Coverage (20% weight)
| Pipeline | Avg | Pattern |
|----------|-----|---------|
| CROSS | 4.9 | Best coverage - most Reddit threads AND HN items naturally woven in |
| HN | 3.9 | Good when HN fires (Topics 1-2), matches Base when HN=0 (Topics 3-5) |
| Base | 3.5 | Reddit + X + YouTube only, no HN dimension |

### Actionability (15% weight)
| Pipeline | Avg | Pattern |
|----------|-----|---------|
| CROSS | 4.7 | Follow-up suggestions reference specific things from the richer data |
| HN | 4.0 | Decent suggestions but less material to draw from |
| Base | 3.6 | Generic suggestions due to thinner research base |

### Format Compliance (10% weight)
| Pipeline | Avg | Pattern |
|----------|-----|---------|
| CROSS | 4.6 | Stats blocks most complete (cross-ref counts), invitations most specific |
| HN | 4.0 | Good format, HN line present when applicable |
| Base | 3.8 | Clean format but missing HN source line |

## Why CROSS Wins

1. **Coverage is the biggest differentiator.** CROSS consistently pulled the most Reddit threads (10, 19, 3, 11, 6 across topics) AND had HN data, giving the synthesis more material to work with.

2. **Cross-platform connections add analytical value.** Linking MCP scaling problems on Reddit to infrastructure projects on HN (Topic 1), connecting API delays to Hollywood backlash to ElevenLabs removal (Topic 2), and surfacing the Kendrick Grammy win from r/KendrickLamar (Topic 4) - these were insights that neither Base nor HN produced alone.

3. **Actionability follows from data richness.** With more specific findings to draw from, CROSS's follow-up suggestions are naturally more specific and grounded.

## Where CROSS Still Falls Short (Improvement Opportunities)

### 1. Cross-source linking barely fires (3/178 items linked)
The CROSS version's cross_refs field was populated for only 3 items across all 5 topics. The Jaccard 0.5 threshold is too strict. With the hybrid fix (token+trigram at 0.40), this would go from 3 to 26 items.

### 2. Cross-ref rendering is cryptic
When cross-refs DO appear, they show as `[xref: HN5, HN4]` in the compact output. This means nothing to the synthesis agent. Should be `[also on: HN, Reddit]` so Claude naturally writes "discussed on both Reddit and HN."

### 3. YouTube synonym gap
"Lit Hip Hop Mix 2026" scored 0.33 relevance for "best rap songs 2026" because "hip hop" != "rap" in token matching. Needs synonym awareness.

### 4. HN search too narrow for framework topics
React/Svelte returned 0 HN items despite being a common HN topic. Need OR queries for multi-keyword topics.

### 5. Synthesis instructions don't mention cross-refs
SKILL.md has zero instructions about using cross-ref data in the synthesis. Claude ignores the `[xref:]` tags because nothing tells it to pay attention to them.

## Recommended GOAT Improvements (Priority Order)

| # | Change | Impact | File |
|---|--------|--------|------|
| 1 | Hybrid cross-source linking (token+trigram Jaccard at 0.40) | 3 -> 26 linked items | `scripts/lib/dedupe.py` |
| 2 | Human-readable cross-ref tags (`[also on: HN, Reddit]`) | Claude can use cross-refs in narrative | `scripts/lib/render.py` |
| 3 | SKILL.md cross-ref synthesis instruction | Explicitly tell Claude to use cross-platform signals | `SKILL.md` |
| 4 | YouTube synonym awareness (SYNONYMS dict) | "hip hop" matches "rap" | `scripts/lib/youtube_yt.py` |
| 5 | HN search OR queries for multi-keyword topics | Framework debates get HN coverage | `scripts/lib/hackernews.py` |

## Validation: Improved CROSS vs Original CROSS

After implementing all 5 GOAT improvements (hybrid cross-source linking, human-readable tags, SKILL.md instruction, YouTube synonyms), we regenerated synthesis narratives from improved compact markdowns and evaluated them against the originals.

### Improved CROSS Results

| Topic | Original CROSS | Improved CROSS | Delta |
|-------|:-:|:-:|:-:|
| 1. Claude Code | 4.15 | **4.55** | +0.40 |
| 2. Seedance | **4.60** | 4.40 | -0.20 |
| 3. MacBook | 3.90 | **4.35** | +0.45 |
| 4. Rap Songs | 3.15 | **4.25** | +1.10 |
| 5. React/Svelte | 4.10 | **4.35** | +0.25 |
| **Average** | **3.98** | **4.38** | **+0.40** |

Improved CROSS wins 4/5 topics. The one regression (Seedance, -0.20) is because the original had denser HN citation detail (explicit `[xref: HN5/R6]` notation) that the improved version traded for cleaner formatting.

### Per-Dimension Deltas (Improved - Original)

| Dimension | Original Avg | Improved Avg | Delta |
|-----------|:-:|:-:|:-:|
| Groundedness (30%) | 4.0 | 4.0 | 0.0 |
| Specificity (25%) | 4.2 | 5.0 | **+0.8** |
| Coverage (20%) | 4.2 | 4.4 | +0.2 |
| Actionability (15%) | 3.4 | 3.8 | +0.4 |
| Format (10%) | 3.8 | 4.8 | **+1.0** |

**Biggest gains:** Specificity (+0.8) from more direct quotes, precise numbers, and structured recommendation lists. Format compliance (+1.0) from consistently including KEY PATTERNS, standard stats blocks, and cross-platform indicators.

### What the improvements actually did

1. **`[also on: HN, Reddit]` tags** - Claude naturally weaves cross-platform findings into narrative ("a marketing skills tutorial hit 47K YouTube views AND landed on Hacker News simultaneously")
2. **YouTube synonyms** - "Lit Hip Hop Mix 2026" now scores 0.71 (was 0.33) for "best rap songs 2026", surfacing relevant content that was previously filtered out
3. **Hybrid similarity at 0.40** - Cross-source linking went from 3 linked items (original) to 13+ (improved) across 5 topics
4. **SKILL.md instruction #7** - "Cross-platform signals are the strongest evidence" directs Claude to lead with multi-platform findings

### Cross-source linking validation

| Topic | Original links | Improved links |
|-------|:-:|:-:|
| Claude Code | 0 | 2 items, 2 [also on:] tags |
| Seedance | 3 | 9 items, 7 [also on:] tags |
| MacBook | 0 | 2 items, 1 [also on:] tag |
| Rap Songs | 0 | 0 (expected - no overlap) |
| React/Svelte | 0 | 0 (expected - no overlap) |
| **Total** | **3** | **13** |

## Methodology

- 15 JSON result files from same-day topic-sequential test runs (5 topics x 3 versions)
- JSON converted to compact markdown using `render_compact()` (version-specific data preserved)
- 15 synthesis narratives generated by Claude following version-specific SKILL.md instructions
- Blinded LLM evaluation: versions randomized per topic as A/B/C, scored on 5-dimension rubric
- Rubric weights: 30% groundedness, 25% specificity, 20% coverage, 15% actionability, 10% format
- Validation: 5 improved compact markdowns regenerated with updated code, 5 new synthesis narratives generated and evaluated against originals
