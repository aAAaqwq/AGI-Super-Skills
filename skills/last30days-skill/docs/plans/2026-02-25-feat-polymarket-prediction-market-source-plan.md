---
title: "feat: Add Polymarket prediction market search as 6th source"
type: feat
status: completed
date: 2026-02-25
---

# feat: Add Polymarket Prediction Market Search

## Overview

Add Polymarket as a 6th research source to last30days. When researching any topic, search Polymarket's public API for relevant prediction markets - surfacing what people are putting real money on alongside what they're saying on Reddit/X/YouTube/HN/Web.

Example: "/last30days Arizona Basketball" would find markets on tournament seeding, Big 12 title odds, and March Madness outcomes. The signal is unique - betting odds reflect conviction, not just opinions.

## Proposed Solution

Hit Polymarket's Gamma API with **smart multi-query search** - not just the raw topic, but expanded related keywords to find markets a human researcher would think of. Show price movement context ("down from 23.7% peak") using the API's built-in price change fields. No API key needed.

Also: hide sources with zero results from the stats box (all sources, not just Polymarket).

## Technical Approach

### API Details

**Endpoint:** `GET https://gamma-api.polymarket.com/public-search?q={topic}&limit={N}`

- No authentication required (free, public, read-only)
- Rate limit: 350 req/10s (very generous)
- Returns `{"events": [...], "pagination": {...}}`
- Events contain nested `markets` arrays
- `outcomePrices` is a JSON-encoded string - must `json.loads()` it
- `volume` and `liquidity` are strings at market level, floats at event level
- **Price movement fields on every market:** `oneDayPriceChange`, `oneWeekPriceChange`, `oneMonthPriceChange` - these are free, no extra API calls

### Intelligence Layer: Smart Query Expansion

A single keyword search is dumb. "Iran" should find markets about Iran strikes, nuclear program, sanctions, oil prices, Khamenei. "Arizona Basketball" should find NCAA tournament odds, Big 12 title, March Madness seeding.

**How it works:**

1. **Extract core subject** using `_extract_core_subject(topic)` (already exists for YouTube/X)
2. **Generate 2-4 expanded queries** from the topic:
   - The raw topic itself: `"Arizona Basketball"`
   - Broader context: `"Arizona NCAA"`, `"Arizona Big 12"`
   - For people/entities: add key associated terms (e.g., "Iran" -> "Iran strikes", "Khamenei", "Iran nuclear")
3. **Run all queries in parallel** against `/public-search` (rate limit is 350/10s, we're using 3-4)
4. **Merge and dedupe** results across queries (same event ID = same market)
5. **Score by relevance to original topic** - markets found by the raw topic query get a relevance boost over expanded-query matches

**Query expansion strategy:**

```python
def _expand_polymarket_queries(topic: str) -> List[str]:
    """Generate 2-4 search queries to cast a wider net."""
    core = _extract_core_subject(topic)
    queries = [core]  # Always include the core topic

    # Split multi-word topics into component searches
    words = core.split()
    if len(words) >= 2:
        # Try the first significant word alone (e.g., "Arizona" from "Arizona Basketball")
        queries.append(words[0])

    # Add the full topic if different from core
    if topic.lower() != core.lower():
        queries.append(topic)

    return list(dict.fromkeys(queries))[:4]  # Dedupe, cap at 4
```

This is the same approach as YouTube synonym expansion and X handle resolution - cast a wider net, then score by relevance.

### Price Movement Context

The API gives us price change data for free. Use it to make the output actually useful:

```
Will Arizona win the NCAA Tournament?
  Yes: 12% (down 11.7% this month) | No: 88%
  $342K vol24h | $2.1M liquidity
```

**Fields available:**
- `oneDayPriceChange` - "up 3% today"
- `oneWeekPriceChange` - "down 5% this week"
- `oneMonthPriceChange` - "down 11.7% this month"

Show the most significant movement (largest absolute change). Only show if change > 1% to avoid noise.

### Key Design Decisions

**Event-level granularity (not market-level).** Each event becomes one `PolymarketItem` showing its title and top 3 markets by volume. A "Trump" query returns 10 events, not 40+ individual markets. This keeps item counts manageable.

**Smart multi-query search with dedup.** Don't rely on one keyword search. Expand the topic into 2-4 related queries, run them all, merge by event ID. This catches markets that use different terminology than the user's query.

**Price movement context by default.** Show the most significant price change (day/week/month) inline with outcome prices. This makes prediction markets actually useful as a research signal - not just "Yes 65%" but "Yes 65%, up 12% this week."

**Date filtering uses `active=true` + `volume1mo > 0`.** Markets can be created months ago but still actively traded. Filter by recent trading activity, not creation date. Set `date` to `updatedAt` for recency scoring. Set `date_confidence` to "high" (API provides exact timestamps).

**Sort priority: below HN, above WebSearch.** Priority 4 (Reddit=0 > X=1 > YouTube=2 > HN=3 > Polymarket=4 > WebSearch=5). Prediction markets are supplementary signal.

**Multi-outcome markets: show top 3 outcomes by price.** Binary markets show "Yes: 65%, No: 35%". Multi-candidate markets truncate to top 3 with "and N more".

**Exclude closed/resolved markets for v1.** Only show `active=true, closed=false`.

**Link to event pages** (not individual market pages) - shows all related markets in context.

### Implementation Plan

#### Phase 1: Hide zero-result sources (separate commit)

- [x] `scripts/lib/render.py` - In `render_source_status()`, skip lines where count is 0
- [x] `SKILL.md` - Remove "(no results this cycle)" instructions, replace with "omit sources with zero results"
- [x] `variants/open/references/research.md` - Same update
- [x] `~/.claude/skills/last30daysCROSS/SKILL.md` - Same update (via sync.sh)
- [x] Test: run a query where HN returns 0, verify it's hidden

#### Phase 2: Polymarket source module

- [x] `scripts/lib/polymarket.py` - New file:
  - `DEPTH_CONFIG = {"quick": 5, "default": 10, "deep": 20}` (event count per query)
  - `_expand_queries(topic)` - generate 2-4 search queries from topic:
    - Raw topic: `"Arizona Basketball"`
    - Core subject extracted: `"Arizona"` (via `_extract_core_subject`)
    - Component words for multi-word topics: first significant word alone
    - Cap at 4 queries, dedupe
  - `search_polymarket(topic, from_date, to_date, depth)` - run all expanded queries against `/public-search` in parallel (ThreadPoolExecutor), merge results by event ID, dedupe
  - `parse_polymarket_response(response)` - extract events, flatten top markets per event
  - `_format_price_movement(market)` - pick most significant price change from `oneDayPriceChange`, `oneWeekPriceChange`, `oneMonthPriceChange`, format as "up/down X% this day/week/month", skip if < 1%
  - URL-encode query params with `urllib.parse.urlencode`
  - Filter: `active=true, closed=false, volume1mo > 0`
  - Parse `outcomePrices` with `json.loads()`, handle malformed/missing gracefully
  - Handle mixed types: `float(volume)` with try/except
  - Relevance scoring: markets from raw topic query get 1.0 base, expanded queries get 0.7 base, then decay by position
  - Return `{"items": [...]}` or `{"items": [], "error": "message"}`

#### Phase 3: Schema + normalization + scoring

- [x] `scripts/lib/schema.py` - Add `PolymarketItem` dataclass:
  - `id`, `title` (event title), `question` (top market question), `url` (event URL)
  - `outcome_prices: List[Tuple[str, float]]` (parsed, e.g. [("Yes", 0.65), ("No", 0.35)])
  - `price_movement: Optional[str]` (formatted, e.g. "down 11.7% this month")
  - `volume24hr: float`, `liquidity: float`, `end_date: Optional[str]`
  - Standard fields: `date`, `date_confidence`, `engagement`, `relevance`, `why_relevant`, `subs`, `score`, `cross_refs`
  - Add `volume: Optional[float]` and `liquidity: Optional[float]` to `Engagement` dataclass
  - Add `polymarket: List[PolymarketItem]` and `polymarket_error: Optional[str]` to `Report`
  - Update `Report.to_dict()` and `Report.from_dict()` (handle missing key for backward compat)

- [x] `scripts/lib/normalize.py` - Add `normalize_polymarket_items()`:
  - Map raw API events to `PolymarketItem` instances
  - Set `date` from `updatedAt`, `date_confidence = "high"`
  - Build `Engagement(volume=volume24hr, liquidity=liquidity)`
  - Update `TypeVar` to include `PolymarketItem`

- [x] `scripts/lib/score.py` - Add scoring:
  - `compute_polymarket_engagement_raw()`: `0.60 * log1p(volume24hr) + 0.40 * log1p(liquidity)`
  - `score_polymarket_items()`: standard 45/25/30 weights (relevance/recency/engagement)
  - Update `sort_items()`: Polymarket priority = 4

#### Phase 4: Dedupe + render + UI

- [x] `scripts/lib/dedupe.py`:
  - Add `PolymarketItem` to `AnyItem` union
  - Add `dedupe_polymarket()` function
  - Update `get_item_text()` for `PolymarketItem` (return `title + " " + question`)
  - Update `_get_cross_source_text()` for cross-source linking

- [x] `scripts/lib/render.py`:
  - Add `_xref_tag()` prefix: `PM` -> `Polymarket`
  - Add Polymarket section to `render_compact()`:
    ```
    ### Prediction Markets (Polymarket)

    **PM1** (score:72) [$342K vol24h, $2.1M liquidity]
      Will Arizona win the NCAA Tournament?
      Yes: 12% (down 11.7% this month) | No: 88%
      https://polymarket.com/event/arizona-ncaa-tournament

    **PM2** (score:65) [$89K vol24h, $450K liquidity]
      Will Arizona win the Big 12 Tournament?
      Yes: 28% (up 4% this week) | No: 72%
      https://polymarket.com/event/arizona-big-12
    ```
  - Add to `render_source_status()` (with zero-result hiding from Phase 1)
  - Add to `render_full_report()` and `render_context_snippet()`
  - Add to `_assess_data_freshness()`

- [x] `scripts/lib/ui.py`:
  - Add `POLYMARKET_MESSAGES` list
  - Add `start_polymarket()` / `end_polymarket()` methods
  - Update `show_complete()` to accept `polymarket_count`

#### Phase 5: Wire into main pipeline

- [x] `scripts/last30days.py`:
  - Import `from lib import polymarket`
  - Add `_search_polymarket()` wrapper function
  - Add `polymarket_future` to `TIMEOUT_PROFILES` (15s - API is fast)
  - In `run_research()`: submit polymarket future to ThreadPoolExecutor, increment max_workers
  - Collect results with timeout, add to processing pipeline (normalize -> filter -> score -> sort -> dedupe)
  - Feed into `cross_source_link()` call
  - Assign to `report.polymarket` / `report.polymarket_error`
  - Update `--diagnose` output: `"polymarket": True` (always available)
  - Update `--store` persistence loop for Polymarket items
  - Update `show_complete()` call with `len(deduped_pm)`

- [x] `scripts/lib/env.py` - Add `is_polymarket_available()` -> always `True`

#### Phase 6: Documentation + deploy

- [x] `SKILL.md` - Update "6 sources", add Polymarket to stats box template, update Security section with `gamma-api.polymarket.com`
- [x] `variants/open/references/research.md` - Same source count + stats updates
- [x] `README.md` - Add Polymarket to feature list, update source count references
- [x] `SPEC.md` - Add `polymarket.py` to architecture list
- [x] Run `bash scripts/sync.sh` to deploy

#### Phase 7: Tests

- [x] `tests/test_polymarket.py` - New file:
  - `TestParsePolymarketResponse` - binary markets, multi-outcome, malformed outcomePrices, missing fields
  - `TestNormalizePolymarketItems` - schema mapping, date handling, type coercion
  - `TestScorePolymarketItems` - engagement formula, zero volume, high volume
- [x] `fixtures/polymarket_sample.json` - Representative API response with edge cases
- [x] `tests/test_cross_source.py` - Add Polymarket-to-Reddit linking test case

## Acceptance Criteria

- [x] `/last30days "Arizona Basketball"` shows relevant Polymarket prediction markets with odds and volume
- [x] `/last30days "best rap songs 2026"` gracefully returns no Polymarket results (and hides the PM line from stats)
- [x] Sources with zero results are hidden from stats box (all sources, not just PM)
- [x] `--diagnose` shows `"polymarket": true`
- [x] Multi-outcome markets show top 3 outcomes
- [x] Polymarket items participate in cross-source linking
- [x] No API key required - works out of the box for all users
- [x] `--quick`, `--deep` flags affect Polymarket result count
- [x] Older cached reports without `polymarket` key load without errors

## Dependencies & Risks

**No blockers.** The Gamma API is free, unauthenticated, and has generous rate limits (350 req/10s). No new dependencies needed - just stdlib `urllib` (already used by HN module).

**Risk: API availability.** Polymarket could change or restrict their API. Mitigation: the source is optional and fails gracefully (returns empty list, hidden from stats).

**Risk: Relevance mismatch.** Many topics won't have prediction markets. The hide-zero-sources change ensures this doesn't pollute the output.

## Sources & References

- Polymarket Gamma API docs: https://docs.polymarket.com/developers/gamma-markets-api/overview
- Polymarket CLI: https://github.com/Polymarket/polymarket-cli
- HN source plan (pattern to follow): `docs/plans/2026-02-24-feat-hacker-news-source-plan.md`
- HN source implementation (most recent similar feature): `scripts/lib/hackernews.py`
- Schema: `scripts/lib/schema.py`
- Main pipeline: `scripts/last30days.py`
