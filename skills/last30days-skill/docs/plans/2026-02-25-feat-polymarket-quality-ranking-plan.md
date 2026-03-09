---
title: "feat: Improve Polymarket result ranking with quality signals"
type: feat
status: completed
date: 2026-02-25
---

# feat: Improve Polymarket Result Ranking with Quality Signals

## Overview

When a topic like "OpenAI" returns 163+ Polymarket events, the current implementation ranks results almost entirely by API return position (75% weight on `i`), with only a tiny volume boost (0-15%). This means the scoring doesn't reflect actual market quality - a $1M/month market and a $5K/month market get nearly identical relevance scores if they're adjacent in the API response.

Fix the ranking so the most actively traded, fastest-moving, most contested markets bubble to the top.

## Problem Statement

Current relevance formula in `parse_polymarket_response()` (line 328-330):

```python
rank_score = max(0.3, 1.0 - (i * 0.03))  # 75% weight on position
engagement_boost = min(0.15, math.log1p(volume24hr) / 60)
relevance = min(1.0, rank_score * 0.75 + engagement_boost + 0.1)
```

Issues:
1. **Position dominance**: A market at position 2 with $0 volume scores higher than a market at position 8 with $1M volume
2. **`limit` parameter is a no-op**: The Gamma API always returns exactly 5 events per page regardless of `limit`. Our `DEPTH_CONFIG` values (5, 10, 20) do nothing
3. **Rich quality signals are ignored**: Event-level `volume1mo`, `volume1wk`, `competitive`, `commentCount` fields are available but unused
4. **Price movement is displayed but not scored**: Markets with dramatic price swings get no ranking boost
5. **No text-similarity scoring**: A tangential market that happens to mention "OpenAI" ranks the same as one directly about OpenAI

## API Findings (Verified)

**Pagination**: `?page=N` works as 1-indexed offset. Each page returns exactly 5 events. `hasMore: true` indicates more pages exist. `totalResults` gives total count.

**Event-level quality fields** (confirmed via live API):

| Field | Level | Example | Currently Used |
|-------|-------|---------|----------------|
| `volume24hr` | Event + Market | $13,334 | Market only (for engagement) |
| `volume1wk` | Event + Market | $1,051,626 | No |
| `volume1mo` | Event + Market | $1,133,684 | No |
| `liquidity` | Event + Market | $16,285 | Market only (for filtering) |
| `competitive` | Event + Market | 0.995 | No |
| `commentCount` | Event only | 2 | No |
| `oneDayPriceChange` | Market only | -0.02 | Display only, not scored |
| `oneWeekPriceChange` | Market only | -0.05 | Display only, not scored |
| `oneMonthPriceChange` | Market only | -0.117 | Display only, not scored |

**API naturally sorts well**: Page 1 has active high-volume markets ($1M+ monthly volume), page 3 is all dead historical markets ($0 volume). So the API's own ranking is decent - the problem is our scoring doesn't preserve this quality signal.

## Proposed Solution

### 1. Replace position-based relevance with quality-signal relevance

New formula in `parse_polymarket_response()`:

```python
# Text similarity: does the event title contain the search topic?
core = _extract_core_subject(topic).lower()
title_lower = title.lower()
if core and core in title_lower:
    text_score = 1.0
else:
    # Token overlap fallback
    topic_tokens = set(core.lower().split())
    title_tokens = set(title_lower.split())
    overlap = len(topic_tokens & title_tokens)
    text_score = overlap / max(len(topic_tokens), 1)

# Volume signal: log-scaled monthly volume (most stable signal)
vol_score = min(1.0, math.log1p(event_volume1mo) / 16)  # ~$9M = 1.0

# Liquidity signal
liq_score = min(1.0, math.log1p(event_liquidity) / 14)  # ~$1.2M = 1.0

# Price movement: largest absolute change, capped
max_change = max(
    abs(oneDayPriceChange or 0) * 3,    # Daily weighted 3x
    abs(oneWeekPriceChange or 0) * 2,   # Weekly weighted 2x
    abs(oneMonthPriceChange or 0) * 1,  # Monthly weighted 1x
)
movement_score = min(1.0, max_change * 5)  # 20% change = 1.0

# Competitive bonus: markets near 50/50 are more interesting
competitive_score = event_competitive or 0

# Final relevance
relevance = (
    0.30 * text_score +
    0.30 * vol_score +
    0.15 * liq_score +
    0.15 * movement_score +
    0.10 * competitive_score
)
```

### 2. Fix DEPTH_CONFIG to use pagination

```python
# Pages to fetch per query (API returns 5 events per page)
DEPTH_CONFIG = {
    "quick": 1,    # 5 events/query, ~5-10 unique after dedup
    "default": 2,  # 10 events/query, ~10-15 unique after dedup
    "deep": 3,     # 15 events/query, ~15-25 unique after dedup
}
```

### 3. Use event-level volume fields

Extract `volume1mo`, `volume1wk`, `liquidity`, and `competitive` from the event object (not just the top market). These are more stable signals than market-level `volume24hr`.

### 4. Cap results after re-ranking

After pagination, merge, dedup, and re-ranking, cap at a reasonable number before sending to the scoring pipeline:

```python
RESULT_CAP = {
    "quick": 5,
    "default": 10,
    "deep": 20,
}
```

## Technical Approach

### Implementation Plan

#### Phase 1: Fix pagination and DEPTH_CONFIG

- [x] `scripts/lib/polymarket.py` - Change `DEPTH_CONFIG` to page counts: `{"quick": 1, "default": 2, "deep": 3}`
- [x] `scripts/lib/polymarket.py` - Add `RESULT_CAP` dict: `{"quick": 5, "default": 10, "deep": 20}`
- [x] `scripts/lib/polymarket.py` - Update `_search_single_query()` to accept a `page` parameter
- [x] `scripts/lib/polymarket.py` - Update `search_polymarket()` to fetch multiple pages per query in parallel (fire all `(query, page)` combinations into ThreadPoolExecutor at once)
- [x] `scripts/lib/polymarket.py` - Apply `RESULT_CAP` after merge + dedup, before returning events
- [x] `tests/test_polymarket.py` - Update `TestDepthConfig` tests for new page-count values

#### Phase 2: Extract event-level quality signals

- [x] `scripts/lib/polymarket.py` - In `parse_polymarket_response()`, extract event-level fields: `volume1mo`, `volume1wk`, `liquidity`, `competitive`, `commentCount`
- [x] `scripts/lib/polymarket.py` - Pass `topic` to `parse_polymarket_response()` (already has the parameter, just need to use it)
- [x] `fixtures/polymarket_sample.json` - Add event-level fields: `volume1mo`, `volume1wk`, `competitive`, `commentCount`, `volume24hr`, `liquidity`

#### Phase 3: Replace relevance formula

- [x] `scripts/lib/polymarket.py` - Replace position-based relevance formula with quality-signal formula (text similarity + volume + liquidity + price movement + competitive)
- [x] `scripts/lib/polymarket.py` - Add `_compute_text_similarity(topic, title)` helper
- [x] `tests/test_polymarket.py` - Add `TestTextSimilarity` test class
- [x] `tests/test_polymarket.py` - Add `TestQualityRanking` test: given events with varying volume/liquidity/text-match, verify high-volume title-matching events rank above low-volume tangential ones

#### Phase 4: Update engagement scoring

- [x] `scripts/lib/schema.py` - No changes needed (Engagement already has `volume` and `liquidity`)
- [x] `scripts/lib/polymarket.py` - Use event-level `volume1mo` instead of market-level `volume24hr` for the `volume24hr` field passed to normalization (or add a new field)
- [x] `scripts/lib/normalize.py` - Update `normalize_polymarket_items()` to use `volume1mo` for engagement volume if available, fallback to `volume24hr`

#### Phase 5: Tests and verification

- [x] Run full test suite
- [ ] Manual test: `/last30days "OpenAI" --emit=compact` - verify top markets are the most actively traded
- [ ] Manual test: `/last30days "Anthropic" --emit=compact` - verify quality ranking
- [ ] Manual test: `/last30days "best rap songs 2026" --emit=compact` - verify graceful zero results
- [x] Run `bash scripts/sync.sh` to deploy

## Acceptance Criteria

- [ ] "OpenAI" search surfaces IPO market cap, product announcements, and GPT benchmark markets (high volume) before niche/dead markets
- [x] Markets with $0 monthly volume are filtered out (already handled by liquidity filter, but verify)
- [x] `DEPTH_CONFIG` actually affects result count (quick=~5, default=~10, deep=~20)
- [x] Price movement is factored into ranking (markets with large swings rank higher)
- [x] Text-matching markets rank above tangential keyword matches
- [x] All existing tests pass (71 polymarket + full suite: 218 passed, 5 pre-existing failures)
- [ ] No performance regression - pagination adds latency but stays within timeout budgets

## Dependencies & Risks

**No blockers.** This is a scoring/ranking improvement within the existing Polymarket module. No new API keys, no new dependencies.

**Risk: Over-tuning the formula.** The weights (0.30/0.30/0.15/0.15/0.10) are educated guesses. May need iteration after testing with real queries. Mitigation: the formula is in one place (`parse_polymarket_response`) and easy to adjust.

**Risk: Pagination latency.** Deep mode with 3 pages x 4 queries = 12 API calls. All run in parallel via ThreadPoolExecutor. Gamma API is fast (~200-500ms per call), so worst case ~1-2s total. Well within the 45s deep timeout.

## Sources & References

- Polymarket Gamma API: `GET https://gamma-api.polymarket.com/public-search?q={topic}&page={N}`
- Current implementation: `scripts/lib/polymarket.py`
- Scoring pipeline: `scripts/lib/score.py`
- Original Polymarket plan: `docs/plans/2026-02-25-feat-polymarket-prediction-market-source-plan.md`
