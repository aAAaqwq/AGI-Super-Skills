---
title: "feat: Add Hacker News as a 5th research source"
type: feat
status: completed
date: 2026-02-24
---

# feat: Add Hacker News as a 5th Research Source

## Overview

Add Hacker News as a source to the last30days skill, using the free Algolia HN Search API (`hn.algolia.com/api/v1`). HN provides high-signal content from a technical audience — stories with high point counts and active comment threads are strong indicators of what the developer community actually cares about. No API key required.

## Problem Statement / Motivation

The skill currently covers Reddit, X, YouTube, and web. Hacker News is missing — and for technical topics, HN often surfaces discussions that don't appear on Reddit or X. HN's upvote system and comment culture produce high-quality signal: a 500-point story with 200 comments means the developer community is genuinely engaged. Community contributor @wkbaran proposed this in PR #26 alongside YouTube and Product Hunt. YouTube shipped in v2.1; now it's time for HN.

## Proposed Solution

Add `scripts/lib/hackernews.py` following the exact same pattern as `youtube_yt.py` (the simplest existing source — no API key, just HTTP calls). Use the Algolia HN Search API for discovery, then optionally fetch top comments from high-scoring stories for enrichment (like Reddit enrichment, but using the `/items/:id` endpoint instead of Reddit's JSON API).

### Two-phase approach (matches existing Reddit pattern):

1. **Phase 1 — Search**: Query Algolia for stories matching the topic within the date range. Get titles, URLs, points, comment counts.
2. **Phase 2 — Enrichment** (optional, top N stories): Fetch the `/items/:id` endpoint for the highest-scoring stories to get top-level comments. This gives "comment_insights" like Reddit enrichment does.

## Technical Approach

### Files to Create

#### `scripts/lib/hackernews.py`

The main source module. Pattern matches `youtube_yt.py` (simplest source).

```python
# scripts/lib/hackernews.py
"""Hacker News search via Algolia API (free, no auth required)."""

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ALGOLIA_SEARCH_BY_DATE_URL = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items"

DEPTH_CONFIG = {
    "quick": 15,
    "default": 30,
    "deep": 60,
}

ENRICH_LIMITS = {
    "quick": 3,
    "default": 5,
    "deep": 10,
}
```

Key functions:

- `search_hackernews(topic, from_date, to_date, depth="default") -> Dict[str, Any]`
  - Calls `hn.algolia.com/api/v1/search?query={topic}&tags=story&numericFilters=created_at_i>{from_ts},created_at_i<{to_ts}&hitsPerPage={count}`
  - Uses `http.get()` — stdlib only, matches existing pattern
  - Returns raw Algolia response

- `parse_hackernews_response(response: Dict) -> List[Dict]`
  - Extracts hits, maps to raw dicts with fields: `id` (prefix "HN"), `title`, `url`, `hn_url`, `author`, `date`, `engagement` (points, num_comments), `why_relevant`, `relevance`
  - `relevance` estimated from Algolia rank + engagement boost (same pattern as Bill's PR)

- `enrich_top_stories(items, depth="default") -> List[Dict]`
  - Fetches `/items/{objectID}` for top N stories (by points)
  - Extracts top-level comments (author, text, points)
  - Adds `top_comments` and `comment_insights` fields (same structure as Reddit enrichment)
  - Uses `ThreadPoolExecutor` for parallel fetching

- `_date_to_unix(date_str: str) -> int` — Helper, converts YYYY-MM-DD to Unix timestamp

#### `tests/test_hackernews.py`

Standard unittest pattern matching existing tests.

- Test `parse_hackernews_response` with sample Algolia response
- Test `_date_to_unix` conversion
- Test empty response handling
- Test enrichment parsing
- Test score integration with `score.py`

### Files to Modify

#### `scripts/lib/schema.py`

- [x] Add `HackerNewsItem` dataclass:
  ```python
  @dataclass
  class HackerNewsItem:
      id: str           # "HN1", "HN2", ...
      title: str
      url: str          # Original article URL
      hn_url: str       # news.ycombinator.com/item?id=...
      author: str       # HN username
      date: Optional[str]
      date_confidence: str  # Always "high" (Algolia provides exact timestamps)
      engagement: Optional[Engagement]  # points + num_comments
      top_comments: List[Comment]       # From enrichment
      comment_insights: List[str]       # From enrichment
      relevance: float
      why_relevant: str
      subs: SubScores
      score: int
  ```
- [x] Add `hackernews: List[HackerNewsItem] = field(default_factory=list)` to `Report`
- [x] Add `hackernews_error: Optional[str] = None` to `Report`
- [x] Update `Report.to_dict()` and `Report.from_dict()`

#### `scripts/lib/normalize.py`

- [x] Add `normalize_hackernews_items(items: List[Dict], from_date, to_date) -> List[schema.HackerNewsItem]`
  - Maps raw dicts to `HackerNewsItem` dataclass instances
  - Sets `date_confidence = "high"` (Algolia provides `created_at_i` exact timestamps)
  - Converts `engagement` dict to `schema.Engagement(score=points, num_comments=num_comments)`

#### `scripts/lib/score.py`

- [x] Add `compute_hackernews_engagement_raw(engagement) -> float`
  - Formula: `0.55 * log1p(points) + 0.45 * log1p(num_comments)`
  - Points are the primary signal on HN; comments indicate depth of discussion
- [x] Add `score_hackernews_items(items) -> List[schema.HackerNewsItem]`
  - Uses standard 45/25/30 weights (relevance/recency/engagement) — same as Reddit/X/YouTube
- [x] Update `sort_items()` to handle `HackerNewsItem`
  - Source priority: Reddit > X > **HN** > YouTube > WebSearch
  - HN slots between X and YouTube: higher signal than YouTube (curated upvotes vs raw views), but X has real-time pulse

#### `scripts/lib/dedupe.py`

- [x] Add `dedupe_hackernews(items, threshold=0.7) -> List[schema.HackerNewsItem]`
- [x] Update `get_item_text()` to handle `HackerNewsItem` (return `title`)
- [x] Consider cross-source dedup: HN stories often link to the same URLs that appear in web search results. Dedupe by URL match across `hackernews` and `websearch` items.

#### `scripts/lib/render.py`

- [x] Add HN section to `render_compact()`:
  ```
  ### Hacker News Stories

  **HN1** (score:85) hn/username (2026-02-15) [350pts, 127cmt]
    Story title here
    https://news.ycombinator.com/item?id=12345
    *Why relevant*
  ```
- [x] Add to `render_source_status()`:
  ```
  ✅ HN: {N} stories
  ```
- [x] Add to `render_full_report()` and `render_context_snippet()`
- [x] Update `_assess_data_freshness()` to include HN items

#### `scripts/last30days.py`

- [x] Import: `from lib import hackernews`
- [x] Add `_search_hackernews(topic, from_date, to_date, depth) -> (items, error)` wrapper function
  - Calls `hackernews.search_hackernews()`, then `hackernews.parse_hackernews_response()`
  - Returns `(items, None)` or `([], error_string)`
- [x] Add to `TIMEOUT_PROFILES`: `"hackernews_future": 60` (default), `30` (quick), `90` (deep)
- [x] Add HN to `ThreadPoolExecutor` in `run_research()`:
  ```python
  if do_hackernews:
      hn_future = executor.submit(_search_hackernews, topic, from_date, to_date, depth)
  ```
  - Increment `max_workers` by 1 when HN is enabled
- [x] Collect results: `hn_items, hn_error = hn_future.result(timeout=hn_timeout)`
- [x] Add HN enrichment phase (after Reddit enrichment, before Phase 2):
  ```python
  if hn_items:
      hn_items = hackernews.enrich_top_stories(hn_items, depth=depth)
  ```
- [x] Add to processing pipeline: normalize -> filter_by_date_range -> score -> sort -> dedupe
- [x] Assign to `report.hackernews` and `report.hackernews_error`
- [x] Update status UI: add `⏳ 🟡 HN Searching Hacker News...` and `✓ 🟡 HN Found {N} stories`

#### `scripts/lib/env.py`

- [x] HN is always available (no API key, no binary dependency)
- [x] Update `get_available_sources()` to include HN in the source list
- [x] Update `validate_sources()` to accept `hn` as a valid source name
- [x] Add `hn` to the `--search` flag documentation

#### `SKILL.md`

- [x] Update description: "Sources: Reddit, X, YouTube, **Hacker News**, and web"
- [x] Add HN to stats block template:
  ```
  ├─ 🟡 HN: {N} stories │ {N} points │ {N} comments
  ```
- [x] Update `metadata.clawdbot.tags` to include `hackernews`
- [x] Update Security section: add `hn.algolia.com` to endpoints list
- [x] Update citation priority to include HN: Reddit > X > YouTube > HN > Web

## Acceptance Criteria

- [x] `python3 scripts/last30days.py "AI coding agents" --emit=compact` shows HN section with stories, points, and comment counts
- [x] HN stories include `hn_url` linking to the HN discussion page (not just the article URL)
- [x] Top stories are enriched with top comments (like Reddit enrichment)
- [x] HN runs in parallel with Reddit/X/YouTube (no serial bottleneck)
- [x] Scoring uses standard 45/25/30 weights with engagement formula tuned for HN metrics
- [x] Stats block shows: `├─ 🟡 HN: {N} stories │ {N} points │ {N} comments`
- [x] `--search=hn` works to run HN only; `--search=reddit,hn` works for combos
- [x] `--quick`, `--deep` flags adjust HN result count (15/30/60)
- [x] All existing tests still pass
- [x] New `tests/test_hackernews.py` with tests for parse, normalize, score, enrichment
- [x] No API key required — works out of the box
- [x] Cross-source URL dedup: HN stories linking to same URL as web results get deduped
- [x] SKILL.md updated with HN in stats block, security section, and citation priority

## Dependencies & Risks

**Low risk:**
- Algolia HN API is free, public, no auth, well-established (used since 2014)
- No new dependencies — uses existing `http.py` (stdlib urllib)
- Pattern is identical to YouTube source (simplest existing source)

**Medium risk:**
- Algolia has no officially documented rate limit, but aggressive use could get throttled
  - Mitigation: Existing `http.py` exponential backoff handles 429s
  - Default depth only requests 30 items (1 API call for search + N for enrichment)
- Comment enrichment adds N API calls (one per story) which could slow down quick mode
  - Mitigation: Limit enrichment to top 3/5/10 stories by depth; use ThreadPoolExecutor

**Compatibility:**
- HN always available — doesn't break anything when other sources are missing
- Existing `--search` flag needs extension but is backward-compatible

## Sources & References

- PR #26 by @wkbaran: [HN implementation reference](https://github.com/mvanhorn/last30days-skill/pull/26)
- Algolia HN API docs: `https://hn.algolia.com/api`
- Existing patterns: `scripts/lib/youtube_yt.py` (simplest source), `scripts/lib/openai_reddit.py` (enrichment pattern)
- Scoring reference: `scripts/lib/score.py:compute_reddit_engagement_raw()`
- Schema reference: `scripts/lib/schema.py:RedditItem` (closest analog to HN)
