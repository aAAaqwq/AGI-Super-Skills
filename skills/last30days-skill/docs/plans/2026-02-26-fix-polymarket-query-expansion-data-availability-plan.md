---
title: "fix: Polymarket query expansion - find markets where topic is an outcome, not just a title"
type: fix
status: active
date: 2026-02-26
---

# fix: Polymarket Query Expansion & Data Availability

## Overview

The Polymarket module misses the most interesting markets when the search topic is an **outcome** in a broader market rather than appearing in the event title. For "Arizona Basketball", the NCAA Tournament Winner (30 open markets) and #1 Seed (20 open markets) are invisible because "Arizona" only appears as an outcome, never in the event title. The Gamma API only searches titles/slugs.

The outcome-aware scoring (from the prior plan) works perfectly on fixture data - it correctly ranks markets where Arizona is an outcome. The problem is upstream: those markets never reach the scoring layer because the Gamma API never returns them.

## Problem Statement

### Root Cause: Gamma API is title/slug search only

`gamma-api.polymarket.com/public-search?q=X` only matches against event titles and slugs. It does NOT search outcome names, market descriptions, or tags.

**Live API verification** (2026-02-26):

| Query | Events returned | Arizona-relevant open markets |
|-------|----------------|-------------------------------|
| "Arizona Basketball" | 5 | 2 (Big 12 Champion, NAU vs Idaho) |
| "Arizona" | 5 | 0 (all political/closed) |
| "NCAA Tournament" | 5 | 2 (Tournament Winner: 30 open, #1 Seed: 20 open) |
| "Basketball" | 5 | 5 (conference champions, no NCAA) |
| "college basketball" | 5 | 1 (#1 seed) |

The championship and seeding markets that the user wants (`NCAA Tournament Winner`, `#1 Seed`) are only findable by searching "NCAA Tournament" or "NCAA" - terms that don't appear in "Arizona Basketball".

### Contributing Factor 1: Query expansion too narrow

`_expand_queries("Arizona Basketball")` generates only `["Arizona Basketball", "Arizona"]`.

It only tries the **first word** as a standalone query. The second word "Basketball" is never searched independently. This means conference-adjacent and tournament markets are invisible.

### Contributing Factor 2: No domain bridging

Even searching "Basketball" (all individual words) only returns conference champions. The leap from "Basketball" to "NCAA Tournament" requires discovering the domain context from initial results. Currently there is no second-pass expansion.

### Contributing Factor 3: Shallow default depth

`DEPTH_CONFIG["default"] = 2` pages (10 events per query). With 3 queries that's 30 raw events, but heavy dedup and closed-event filtering reduces this to 2-5 usable results.

### What works (don't break it)

- "Iran War" returned 9 perfect markets because "Iran" and "War" appear directly in event titles
- Outcome-aware scoring correctly ranks Arizona-outcome markets when they reach the scoring layer
- Topic-matching outcome reordering surfaces the right outcome first

## Proposed Solution

Three changes, all generic (no hardcoded domain knowledge):

### 1. Search ALL individual words, not just the first

Currently `_expand_queries()` only adds `words[0]` as a standalone query. Change to add **every word** as a standalone query, then dedupe.

For "Arizona Basketball": `["Arizona Basketball", "Arizona", "Basketball"]`
For "Iran War": `["Iran War", "Iran", "War"]` (same as before since both are short)
For "AI video generation tools": `["AI video generation tools", "AI", "video", "generation", "tools"]` (capped at 6)

Raise query cap from 4 to 6 to accommodate.

```python
def _expand_queries(topic: str) -> List[str]:
    core = _extract_core_subject(topic)
    queries = [core]

    words = core.split()
    if len(words) >= 2:
        # Add ALL individual words (not just first)
        for word in words:
            if len(word) > 2:  # skip very short words ("AI", "vs")
                queries.append(word)

    if topic.lower().strip() != core.lower():
        queries.append(topic.strip())

    # Dedupe, cap at 6
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q.strip())
    return unique[:6]
```

Note: "AI" is only 2 chars but is meaningful. Lower the threshold to `len(word) > 1` to catch it. Single-char words (rare) get filtered.

### 2. Second-pass context expansion from first-pass results

After the first-pass search, extract domain-indicator terms from event titles and run a focused second-pass search.

Algorithm:
1. Collect ALL event titles from first-pass results (including closed events)
2. Tokenize titles into bigrams (two-word sequences)
3. Count bigrams across events, filter out bigrams containing topic words
4. Take the top 1-2 most frequent non-topic bigrams as "domain indicators"
5. Search each domain indicator (1 page each)
6. Merge with first-pass results, dedupe, re-rank

**Example for "Arizona Basketball":**

First-pass titles include:
- "Big 12 Men's College Basketball 2025-2026 Regular Season Champion"
- "SEC Men's College Basketball 2025-2026 Regular Season Champion"
- "ACC Men's College Basketball 2025-2026 Regular Season Champion"
- "Big East Men's College Basketball 2025-2026 Regular Season Champion"

Frequent bigrams (excluding topic words): "college basketball" (4x), "regular season" (4x), "season champion" (4x)

Top domain indicator: **"college basketball"**

Searching "college basketball" returns: **"#1 seed in NCAA Tournament"** (20 open markets with Arizona as outcome!)

**Example for "Iran War":** First-pass already finds everything via title matches. Second-pass bigrams would be things like "iran strikes", "khamenei out" - searching these finds the same events (deduped). No regression.

```python
def _extract_domain_queries(topic: str, events: List[Dict]) -> List[str]:
    """Extract domain-indicator search terms from first-pass event titles."""
    topic_words = set(_extract_core_subject(topic).lower().split())

    # Collect bigrams from all event titles
    bigram_counts = {}
    for event in events:
        title = event.get("title", "").lower()
        words = re.findall(r'[a-z]+', title)
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            # Skip if both words are in topic (we already search the topic)
            if words[i] in topic_words and words[i+1] in topic_words:
                continue
            # Skip very common filler
            if any(w in ("the", "of", "in", "to", "a", "and", "vs", "will", "be") for w in (words[i], words[i+1])):
                continue
            bigram_counts[bigram] = bigram_counts.get(bigram, 0) + 1

    # Return bigrams appearing in 2+ event titles
    domain_queries = [bg for bg, count in sorted(bigram_counts.items(), key=lambda x: -x[1]) if count >= 2]
    return domain_queries[:2]
```

### 3. Increase depth and result caps

```python
DEPTH_CONFIG = {
    "quick": 1,
    "default": 3,   # was 2 (50% more raw results)
    "deep": 4,       # was 3
}

RESULT_CAP = {
    "quick": 5,
    "default": 15,   # was 10 (more room for cross-domain markets)
    "deep": 25,       # was 20
}
```

This gives default searches 3 queries x 3 pages = 45 raw events (up from 2 queries x 2 pages = 20), plus 2 domain-indicator queries x 1 page = 10 more.

## Technical Approach

### Implementation Plan

#### Phase 1: Expand query generation

- [x] `scripts/lib/polymarket.py` - Update `_expand_queries()` to add ALL individual words (len > 1), raise cap from 4 to 6
- [x] `tests/test_polymarket.py` - Test: `_expand_queries("Arizona Basketball")` returns `["Arizona Basketball", "Arizona", "Basketball"]`
- [x] `tests/test_polymarket.py` - Test: `_expand_queries("Iran War")` returns `["Iran War", "Iran", "War"]`
- [x] `tests/test_polymarket.py` - Test: short words excluded, cap at 6

#### Phase 2: Second-pass context expansion (evolved: tags instead of bigrams)

- [x] `scripts/lib/polymarket.py` - Add `_extract_domain_queries()` using event TAGS (not bigrams - tags are more reliable, contain "NCAA CBB" etc.)
- [x] `scripts/lib/polymarket.py` - Update `search_polymarket()` with `_run_queries_parallel()` helper for two-pass search
- [x] `scripts/lib/polymarket.py` - Add `_shorten_question()` to extract team names from neg-risk binary market questions
- [x] `scripts/lib/polymarket.py` - Synthesize outcome_prices from binary sub-market questions (detects Yes/No pattern, not just negRisk flag)
- [x] `scripts/lib/polymarket.py` - Updated outcome reordering to use token-based matching for long question strings
- [x] `scripts/lib/polymarket.py` - Also pass market questions to `_compute_text_similarity()` for neg-risk events
- [x] `tests/test_polymarket.py` - Tests for tag-based domain extraction: frequent tags, generic tag filtering, topic word filtering, min frequency, cap, empty events

#### Phase 3: Increase depth and caps

- [x] `scripts/lib/polymarket.py` - Update `DEPTH_CONFIG`: default 2 -> 3, deep 3 -> 4
- [x] `scripts/lib/polymarket.py` - Update `RESULT_CAP`: default 10 -> 15, deep 20 -> 25

#### Phase 4: Tests and verification

- [x] Run full test suite (238 passed, 5 pre-existing failures unrelated)
- [x] `bash scripts/sync.sh` to deploy to CROSS
- [x] Live API test: "Arizona Basketball" - finds NCAA Tournament Winner (Arizona: 12%), #1 Seed (Arizona: 88%), Big 12 (Arizona: 69%)
- [x] Live API test: "Iran War" - 15 markets, no regression (domain expansion found "Geopolitics", "Middle East")
- [ ] Manual test: `/last30daysCROSS "Arizona Basketball"` - end-to-end with LLM synthesis
- [ ] Manual test: `/last30daysCROSS "Duke Basketball"` - verify NCAA Tournament markets appear for another team

## Acceptance Criteria

- [x] `_expand_queries()` searches ALL individual words, not just the first
- [x] Query cap raised from 4 to 6
- [x] Second-pass context expansion discovers domain-indicator terms from first-pass event tags
- [x] "Arizona Basketball" search finds NCAA Tournament Winner AND #1 Seed markets (via "NCAA" tag domain expansion)
- [x] "Iran War" search still returns 9+ markets (15 - no regression)
- [x] All existing tests pass + new query expansion tests pass (91 polymarket tests)
- [x] No hardcoded domain knowledge (uses event tags, not hardcoded terms)
- [x] Default depth increased to 3 pages per query
- [x] Default result cap increased to 15
- [x] Neg-risk binary markets show team names instead of Yes/No (via question extraction)
- [x] Topic-matching team surfaced first in outcome display

## Dependencies & Risks

**No blockers.** Changes are internal to `polymarket.py` and don't affect other modules.

**Risk: Second-pass adds latency.** 2 extra queries x 1 page each, at ~200ms per call = ~400ms additional latency. The queries run after first-pass completes (serial), so total Polymarket time goes from ~1.5s to ~2s. Acceptable since other sources (YouTube, X) take 10-30s.

**Risk: Bigram extraction produces noise.** Common title patterns like "regular season" or "2025-2026" could become domain queries. Mitigation: filter filler words, require 2+ title appearances, and cap at 2 queries. A noisy domain query just returns irrelevant events that get scored low by the existing relevance ranker.

**Risk: Individual word queries return unrelated events.** "Basketball" returns European basketball, "War" returns non-Iran conflicts. Mitigation: the outcome-aware scoring already handles this - events without topic-matching outcomes get low text_score (token overlap only) and sort to the bottom.

**Risk: Rate limiting.** Adding 4-6 extra API calls per search. Gamma API allows 350 req/10s, so even aggressive searching stays well under limits.

## Sources & References

- Query expansion: `scripts/lib/polymarket.py:60` (`_expand_queries`)
- Search orchestration: `scripts/lib/polymarket.py:109` (`search_polymarket`)
- Event filtering: `scripts/lib/polymarket.py:302-306`
- Depth config: `scripts/lib/polymarket.py:20-31`
- Previous outcome-aware scoring plan: `docs/plans/2026-02-26-feat-polymarket-smarter-synthesis-plan.md`
- Live Gamma API test results from 2026-02-26 (documented above)
