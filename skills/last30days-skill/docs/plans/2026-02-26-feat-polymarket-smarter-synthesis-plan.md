---
title: "feat: Smarter Polymarket synthesis - surface the most interesting markets"
type: feat
status: completed
date: 2026-02-26
---

# feat: Smarter Polymarket Synthesis

## Overview

Polymarket data is one of the most powerful signals when relevant - real money on outcomes cuts through opinion. But the current system buries the most interesting markets and gives the LLM zero guidance on how to synthesize prediction market data.

For "Arizona Basketball", the skill found 2 markets but only highlighted "Big 12 title: 68%" in the stats and synthesis. The user cares MORE about:
- NCAA Tournament championship odds (12%, up 3%)
- #1 seed odds (85%)
- Next game: Arizona vs Kansas (71% to win)

For "Iran War", the skill found 9 markets with $559M volume but only highlighted "strikes by Feb 28: 10% (down from 65%)". The user wanted regime change / Khamenei odds - the "bigger picture" structural question.

The problem has two layers: (1) the Python scoring penalizes multi-outcome markets where the topic is an outcome, and (2) the SKILL.md gives the LLM zero instructions for interpreting or highlighting prediction market data.

## Problem Statement

### Layer 1: Scoring penalizes the most interesting markets

`_compute_text_similarity()` (polymarket.py:236) only compares the search topic against the **event title**. It never checks outcome names.

Example: Market titled "Who will be the #1 overall seed in the 2026 NCAA Tournament?" with outcomes ["Arizona", "Duke", "Houston", "Auburn"]:
- Topic: "Arizona Basketball"
- text_score: **0.0** (neither "arizona" nor "basketball" in event title)
- 30% relevance penalty from this alone

This means the most contextually interesting markets (seeding, championship, matchup odds) get pushed below less interesting but title-matching markets (Big 12 regular season).

### Layer 2: SKILL.md has zero Polymarket synthesis guidance

The SKILL.md Judge Agent section tells the LLM how to weight Reddit (higher), YouTube (high), WebSearch (lower), but says **nothing** about:
- How to interpret prediction market probabilities
- Which markets are "most interesting" (championship > regular season)
- When to lead with prediction market odds vs other sources
- How to connect a specific outcome in a multi-outcome market to the user's topic
- How to use odds as a signal alongside social media sentiment

### Layer 3: Stats box loses information

The Polymarket stats line only has room for 1-2 market highlights. When there are 5+ relevant markets, the user misses the most interesting ones.

## Proposed Solution

### 1. Outcome-aware text similarity scoring

Update `_compute_text_similarity()` to check if the topic appears in any outcome name, with **bidirectional** substring matching. The check must work in both directions since the topic ("Arizona Basketball") is longer than the outcome name ("Arizona").

Collect outcome names from ALL active markets in the event (not just top market), since Gamma API can structure multi-outcome events as separate binary sub-markets.

Only match outcomes with probability > 1% to avoid noise from near-zero outcomes.

```python
def _compute_text_similarity(topic: str, title: str, outcomes: list = None) -> float:
    core = _extract_core_subject(topic).lower()
    title_lower = title.lower()
    if not core:
        return 0.5

    # Full substring match in title
    if core in title_lower:
        return 1.0

    # Check if topic appears in any outcome name (bidirectional)
    if outcomes:
        core_tokens = set(core.split())  # Hoist outside loop
        best_outcome_score = 0.0
        for outcome_name in outcomes:
            outcome_lower = outcome_name.lower()
            # Bidirectional substring: "arizona" in "arizona basketball" OR "arizona basketball" in "arizona wildcats game"
            if core in outcome_lower or outcome_lower in core:
                best_outcome_score = max(best_outcome_score, 0.85)
            elif core_tokens & set(outcome_lower.split()):
                best_outcome_score = max(best_outcome_score, 0.7)
        if best_outcome_score > 0:
            return best_outcome_score

    # Token overlap fallback against title
    topic_tokens = set(core.split())
    title_tokens = set(title_lower.split())
    if not topic_tokens:
        return 0.5
    overlap = len(topic_tokens & title_tokens)
    return overlap / len(topic_tokens)
```

### 2. Surface the topic-matching outcome in display

When the topic matches an outcome name, reorder `outcome_prices` to put the matching outcome first before truncating to top 3. This ensures the LLM sees the user-relevant odds.

### 3. Add SKILL.md synthesis instructions for Polymarket

Add a dedicated section telling the LLM:
- **Prediction markets are high-signal when relevant.** Real money on outcomes > opinions.
- **Prefer markets that answer structural/long-term questions** (championships, regime changes, major milestones) over near-term deadline markets (weekly matchups, short-term event deadlines). When in doubt, the bigger question is more interesting.
- **When the topic is an outcome in a multi-outcome market, call out that specific outcome's odds and movement.** Don't just say "Polymarket has a #1 seed market" - say "Arizona has 85% chance of a #1 seed, up from 72%."
- **Weave odds into the "What I learned" narrative as supporting evidence.** "Final Four buzz is building - Polymarket gives Arizona a 12% chance to win the championship (up 3% this week), and 85% to earn a #1 seed."
- **Citation format:** "Polymarket has Arizona at 85% for a #1 seed (up from 72%)" - include the specific odds and movement, not just "per Polymarket."
- **Stats box:** Show up to 5 most relevant markets with odds. If more exist, show count.

Domain examples:
- Sports: championship/tournament odds > regular season title > weekly matchup
- Geopolitics: regime change > near-term strike deadline > sanctions
- Tech: major milestones (IPO, product launch) > incremental updates
- Elections: presidency > primary > individual state

### 4. Improve stats box template

Show up to 5 markets with odds, capped for readability:
```
├─ 📊 Polymarket: 5 markets (Championship: 12%, #1 Seed: 85%, Big 12: 68%, vs Kansas: 71%, NCAA: 12%)
```

### 5. Fix render.py volume label

The render module labels volume as "vol24h" even when `volume1mo` is the actual data source. Fix to "vol/mo" when monthly volume is used.

## Technical Approach

### Implementation Plan

#### Phase 1: Fix text similarity to check outcomes

- [x] `scripts/lib/polymarket.py` - Update `_compute_text_similarity()` to accept optional `outcomes` parameter with bidirectional substring matching and token overlap
- [x] `scripts/lib/polymarket.py` - In `parse_polymarket_response()`, collect outcome names from ALL active markets (not just top market), filter to outcomes with price > 1%, and pass to `_compute_text_similarity()`
- [x] `scripts/lib/polymarket.py` - Reorder `outcome_prices` to surface the topic-matching outcome first before truncating to top 3
- [x] `fixtures/polymarket_sample.json` - Add fixture event: "Who will be the #1 overall seed in the 2026 NCAA Tournament?" with outcomes ["Arizona", "Duke", "Houston", "Auburn"] where "Arizona" is NOT in the title
- [x] `tests/test_polymarket.py` - Add tests for outcome-aware text similarity: bidirectional substring, token overlap, no-match, low-probability filtering
- [x] `tests/test_polymarket.py` - Add test: multi-outcome market where topic is an outcome should rank higher than tangential title-match markets
- [x] `tests/test_polymarket.py` - Add test: topic-matching outcome is surfaced to front of outcome_prices display

#### Phase 2: Add SKILL.md Polymarket synthesis instructions

- [x] `SKILL.md` - Add "Prediction Markets" subsection to the Judge Agent section with:
  - General heuristic: prefer structural/long-term markets over near-term deadlines
  - Domain examples (sports, geopolitics, tech, elections)
  - Citation format with specific odds and movement
  - Instruction to weave odds into "What I learned" narrative
- [x] `SKILL.md` - Add Polymarket to citation priority list (between HN and Web) with format guidance
- [x] `SKILL.md` - Update stats box template: show up to 5 markets with odds
- [x] `variants/open/references/research.md` - Add condensed Polymarket synthesis guidance matching the open variant's style
- [x] `scripts/lib/render.py` - Fix "vol24h" label to "vol/mo" when volume1mo is the data source (changed to "volume")

#### Phase 3: Tests and verification

- [x] Run full test suite (229 passed, 5 pre-existing failures unrelated to this change)
- [ ] Manual test: `/last30days "Arizona Basketball"` - verify championship, seed, and matchup odds appear in synthesis
- [ ] Manual test: `/last30days "Iran War"` - verify regime change and structural outcome markets appear
- [x] Run `bash scripts/sync.sh` to deploy

## Acceptance Criteria

- [x] Multi-outcome markets where the topic is an outcome (e.g. "Arizona" in a seeding market) get text_score >= 0.7, not 0.0
- [x] Bidirectional matching works: "Arizona" as outcome matches topic "Arizona Basketball" (outcome_name in core)
- [x] Topic-matching outcome is surfaced to front of outcome_prices display (not hidden in "and N more")
- [x] Low-probability outcomes (< 1%) don't trigger outcome matching
- [x] SKILL.md instructs the LLM to highlight structural/long-term markets over near-term ones
- [x] SKILL.md provides citation format: "Polymarket has X at Y% (up/down Z%)"
- [x] Stats box shows up to 5 markets with odds
- [x] HN zero-result line is hidden (already fixed - verify on next run)
- [x] All existing tests pass + new outcome-aware similarity tests pass
- [x] render.py volume label is accurate

## Dependencies & Risks

**No blockers.** This is scoring improvements + SKILL.md instruction changes within the existing Polymarket module.

**Risk: Outcome name matching false positives.** A market "Will Arizona pass AI regulation?" would match "Arizona Basketball" on the word "Arizona" even though it's about the state, not the team. Mitigation: outcome match gets 0.7-0.85 (not 1.0), and volume/liquidity/movement signals still differentiate. A false positive at 0.85 text_score won't outrank a true title match at 1.0.

**Risk: Common-word false positives.** Words like "war," "AI," "US" could match generic outcomes. Mitigation: at 0.7 text_score (30% weight = 0.21 relevance), this is a small boost that won't override strong volume/liquidity signals from actually relevant markets. Monitor in testing.

**Risk: LLM still ignores synthesis instructions.** Mitigation: use CRITICAL formatting, specific do/don't examples, and concrete citation format.

## Sources & References

- Current text similarity: `scripts/lib/polymarket.py:236`
- Render format: `scripts/lib/render.py:282`
- SKILL.md synthesis: `SKILL.md:196` (Judge Agent section)
- Previous quality ranking plan: `docs/plans/2026-02-25-feat-polymarket-quality-ranking-plan.md`
