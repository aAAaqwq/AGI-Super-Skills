---
title: "feat: YouTube relevance scoring and cross-source linking"
type: feat
status: active
date: 2026-02-25
---

# feat: YouTube Relevance Scoring and Cross-Source Linking

## Overview

Two output quality improvements for the last30days monthiversary:

1. **YouTube relevance scoring** - Replace the hardcoded `relevance: 0.7` with real token-overlap scoring so relevant niche videos beat viral off-topic ones.
2. **Cross-source linking** - When the same story appears on Reddit + HN + X, annotate items with `[xref: R3, HN5]` so Claude can synthesize cross-platform discussion.

## Problem Statement / Motivation

**YouTube scoring is broken.** Every YouTube video starts with `relevance: 0.7` (70/100 subscore). Since the scoring formula is `45% relevance + 25% recency + 30% engagement`, all YouTube items share the same 31.5pt relevance floor. Ranking is purely engagement-driven - a viral off-topic video beats a niche relevant one.

**Cross-source coverage is invisible.** The same story often appears across Reddit, HN, and X (e.g., a product launch). Currently each source is deduped independently, but there's no signal telling Claude "these items are about the same thing." Claude has to manually notice the overlap, and often doesn't.

## Technical Approach

### Feature 1: YouTube Relevance Scoring

**Where:** `youtube_yt.py` (compute), `normalize.py` (pass through - already works)

**Algorithm:** Token ratio overlap between `core_topic` and video title.

```python
# youtube_yt.py - new function
STOPWORDS = {'the', 'a', 'an', 'to', 'for', 'how', 'is', 'in', 'of', 'on',
             'and', 'with', 'from', 'by', 'at', 'this', 'that', 'it', 'my',
             'your', 'i', 'me', 'we', 'you', 'what', 'are', 'do', 'can'}

def _compute_relevance(query: str, title: str) -> float:
    """Compute relevance as ratio of query tokens found in title.

    Uses ratio overlap (intersection / query_length) so short queries
    score higher when fully represented in the title. Floors at 0.1.
    """
    q_tokens = {w for w in query.lower().split() if w not in STOPWORDS and len(w) > 1}
    t_tokens = {w for w in re.sub(r'[^\w\s]', ' ', title.lower()).split()
                if w not in STOPWORDS and len(w) > 1}

    if not q_tokens:
        return 0.5  # Neutral fallback

    overlap = len(q_tokens & t_tokens)
    ratio = overlap / len(q_tokens)
    return max(0.1, min(1.0, ratio))
```

**Key decisions:**
- **Use `core_topic`** (already stripped of noise words by `_extract_core_subject()`) - not the raw verbose query
- **Ratio overlap** (intersection/query_length), not strict Jaccard - so "Claude Code" (2 tokens) vs "Claude Code Tutorial" (3 tokens) = 2/2 = 1.0, not 2/3 = 0.67
- **Stopword removal** on both sides - prevents "How To Use Claude Code For Beginners" from diluting the match
- **Floor at 0.1** - even zero-match videos get `rel_score=10` not 0, consistent with other sources' defaults
- **No LLM call** - this is pure string matching, zero latency/cost

**Files to modify:**

#### `scripts/lib/youtube_yt.py`

- [x] Add `STOPWORDS` set and `_compute_relevance(query, title)` function
- [x] In `search_youtube()`, replace `"relevance": 0.7` (line 186) with `"relevance": _compute_relevance(core_topic, video.get("title", ""))`
- [x] Update `"why_relevant"` to be more descriptive: `f"YouTube: {title_excerpt}"`

#### `scripts/lib/normalize.py`

- No changes needed - already passes through `item.get("relevance", 0.7)` at line 196

#### `scripts/lib/score.py`

- No changes needed - `score_youtube_items()` already reads `item.relevance` correctly

### Feature 2: Cross-Source Linking

**Where:** `dedupe.py` (new function), `schema.py` (new field), `render.py` (display), `last30days.py` (call site)

**Algorithm:** Reuse existing Jaccard char-trigram similarity from `dedupe.py`. Compare items across sources at threshold 0.5 (lower than within-source 0.7 since titles differ more across platforms). Bidirectional - both items get the cross-ref.

**Key decisions:**
- **Link, don't merge** - keep items separate with `cross_refs: ["R3", "HN5"]`. Let Claude handle the narrative.
- **Bidirectional** - if R3 links to HN5, HN5 also links to R3. Claude reads source-by-source and needs to see the link from either direction.
- **Threshold 0.5** for cross-source (vs 0.7 within-source). Lower because the same story has different titles across platforms. Still high enough to avoid false positives.
- **Truncate X text to 100 chars** for comparison - full tweets dilute Jaccard against short Reddit/HN titles
- **Just IDs in cross_refs** - no similarity scores (noise for Claude's synthesis)
- **Include WebSearchItem** - add to `get_item_text()` using `item.title`
- **Don't persist to SQLite** - cross_refs are cheap to recompute, not worth a schema migration

**Performance:** With 45 items total (typical) and 10 source pairs, ~1000 char-trigram comparisons. Sub-millisecond. Even --deep mode (~150 items) is <12K comparisons - trivial.

**Files to modify:**

#### `scripts/lib/schema.py`

- [x] Add `cross_refs: List[str] = field(default_factory=list)` to all 5 item types (RedditItem, XItem, YouTubeItem, HackerNewsItem, WebSearchItem)
- [x] Update `to_dict()` on each item type to include `cross_refs` (only when non-empty)
- [x] Update `Report.from_dict()` to deserialize `cross_refs` for each item type

#### `scripts/lib/dedupe.py`

- [x] Update `get_item_text()` type hints to include `WebSearchItem` and handle it (use `item.title`)
- [x] Add `get_cross_source_text()` function - same as `get_item_text()` but truncates X text to 100 chars
- [x] Add `cross_source_link()` function:

```python
def cross_source_link(
    *source_lists: List[Union[schema.RedditItem, schema.XItem, schema.YouTubeItem,
                              schema.HackerNewsItem, schema.WebSearchItem]],
    threshold: float = 0.5,
) -> None:
    """Annotate items with cross-source references.

    Compares items across different source types. When similarity exceeds
    threshold, adds bidirectional cross_refs with the related item's ID.
    Modifies items in-place.
    """
    all_items = []
    for source_list in source_lists:
        all_items.extend(source_list)

    if len(all_items) <= 1:
        return

    # Pre-compute trigrams using cross-source text extraction
    ngrams = [get_ngrams(get_cross_source_text(item)) for item in all_items]

    for i in range(len(all_items)):
        for j in range(i + 1, len(all_items)):
            # Skip same-source comparisons (already handled by per-source dedupe)
            if type(all_items[i]) == type(all_items[j]):
                continue

            similarity = jaccard_similarity(ngrams[i], ngrams[j])
            if similarity >= threshold:
                # Bidirectional cross-reference
                if all_items[j].id not in all_items[i].cross_refs:
                    all_items[i].cross_refs.append(all_items[j].id)
                if all_items[i].id not in all_items[j].cross_refs:
                    all_items[j].cross_refs.append(all_items[i].id)
```

#### `scripts/last30days.py`

- [x] After the dedupe step (after line ~1107), call `dedupe.cross_source_link()`:

```python
# Cross-source linking
dedupe.cross_source_link(
    deduped_reddit, deduped_x, deduped_youtube, deduped_hn, deduped_web,
)
```

#### `scripts/lib/render.py`

- [x] In `render_compact()`, append `[xref: ...]` to items that have cross_refs:

```python
# After the existing item line
if hasattr(item, 'cross_refs') and item.cross_refs:
    xref_str = ', '.join(item.cross_refs)
    line += f" [xref: {xref_str}]"
```

#### `SKILL.md`

- [x] Add a note in the synthesis instructions about cross-refs:
  "Items tagged `[xref: ...]` reference the same story on another platform. Use these to triangulate: 'This was widely discussed - Reddit thread (R3) with 142 comments, HN discussion (HN5) with 89 points, and several X posts (X12).'"

### Tests

#### `tests/test_youtube_relevance.py` (new)

- [x] Test exact match: query "Claude Code" vs title "Claude Code" = 1.0
- [x] Test partial match: query "Claude Code" vs title "Claude Code Tutorial" = 1.0 (ratio)
- [x] Test low match: query "Claude Code" vs title "Python Web Scraping" = 0.1 (floor)
- [x] Test empty query: returns 0.5
- [x] Test empty title: returns 0.1
- [x] Test stopword handling: query "how to use Claude" vs title "Using Claude" = high match
- [x] Test integration: search_youtube returns varied relevance scores (mock yt-dlp)

#### `tests/test_cross_source.py` (new)

- [x] Test no cross-refs: unrelated items across sources
- [x] Test bidirectional: matching Reddit + HN items both get cross_refs
- [x] Test multi-source: same story on 3+ sources
- [x] Test same-source skip: items from same source type are not cross-linked
- [x] Test X text truncation: long tweet vs short Reddit title
- [x] Test empty lists: no crash on empty source lists
- [x] Test schema round-trip: cross_refs survive to_dict() / from_dict()

## Acceptance Criteria

- [x] YouTube items have varied relevance scores (not all 0.7)
- [x] A video with title matching the query scores higher than one without
- [x] Cross-source items about the same story have `cross_refs` pointing to each other
- [x] Cross-refs are bidirectional
- [x] Compact output shows `[xref: ...]` tags on linked items
- [x] SKILL.md tells Claude how to use cross-refs in synthesis
- [x] All existing tests still pass
- [x] New tests cover YouTube relevance edge cases
- [x] New tests cover cross-source linking edge cases
- [x] Run sync.sh to deploy after changes

## Dependencies & Risks

**Low risk:**
- Both features add fields/functions without changing existing logic
- YouTube relevance is a drop-in replacement for a hardcoded value
- Cross-source linking only adds metadata (cross_refs) without modifying item order or scores
- All existing tests should pass unchanged

**Edge cases:**
- CJK/non-English titles: token splitting works but relevance may be less accurate. Acceptable for v1.
- Very short queries (1 token): ratio overlap = 0 or 1. The 0.1 floor handles the 0 case.
- Clickbait YouTube titles with no query overlap: these correctly get low relevance now (improvement over blindly getting 0.7)

## Sources & References

- YouTube relevance: Currently hardcoded at `youtube_yt.py:186`
- Dedupe infrastructure: `dedupe.py` - Jaccard similarity on char trigrams
- Score weights: `score.py:8-10` - 45% relevance + 25% recency + 30% engagement
- Existing HN plan as template: `docs/plans/2026-02-24-fix-hn-ordering-and-emoji-plan.md`
