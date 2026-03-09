---
title: "feat: Resolve X handles for topic entities"
type: feat
status: completed
date: 2026-02-25
---

# feat: Resolve X handles for topic entities

## Overview

When a user searches for a person, brand, or creator (e.g., "Dor Brothers", "Jason Calacanis"), the skill should automatically resolve their X handle and search their posts directly. Currently, Phase 1 only finds posts that *mention* the topic keywords, and Phase 2 only drills into handles that appeared in Phase 1 results. This misses the entity's own posts entirely when they don't literally include the topic string.

## Problem Statement

**The Dor Brothers example:** Searching "Dor Brothers" found 30 X posts with 149 likes - all posts *about* them. But the Dor Brothers' own account posts constantly about their AI films, tools, and collabs. Those posts wouldn't appear in Phase 1 because the Dor Brothers don't write "Dor Brothers" in every tweet. Phase 2 can't help because entity_extract only finds handles already @mentioned in Phase 1 results.

**The Jason Calacanis example:** His handle is @jason - completely unguessable from his name. No amount of keyword searching or @mention extraction would discover it. You need an actual lookup.

**What's missing:** A handle resolution step that maps `"topic name" -> @handle`, then searches that handle's recent posts directly (without requiring topic keywords in the tweet text).

## User Base Constraints

- **80% Claude Code** - agent is Claude, has WebSearch tool
- **20% OpenClaw** - agent has web search capability
- **Most users have:** OPENAI_API_KEY
- **Some users have:** XAI_API_KEY, Bird (browser cookies)
- **Few users have:** BRAVE_API_KEY, PARALLEL_API_KEY, OPENROUTER_API_KEY
- **Everyone has:** Claude (it's the runtime)

**Critical constraint:** The Python script's web search backends (`brave_search.py`, `parallel_search.py`, `openrouter_search.py`) ALL filter out x.com URLs via `EXCLUDED_DOMAINS`. Building handle resolution inside the Python script would require bypassing this filter, and most users don't have the API keys for those backends anyway.

## Proposed Solution

Move handle resolution to the **SKILL.md agent layer**. The agent (Claude or OpenClaw) already has `WebSearch` as an allowed tool. It does a single WebSearch before running the Python script, extracts the handle, and passes it as a CLI argument.

### Architecture

```
SKILL.md Agent Flow (revised):

1. Parse intent (existing)
2. NEW: If topic looks like a person/brand, WebSearch("{topic} X twitter handle")
3. NEW: Extract @handle from results (agent intelligence, not regex)
4. Run script: python3 last30days.py "Dor Brothers" --x-handle=TheDorBrothers --emit=compact
5. Script uses --x-handle in Phase 2: from:TheDorBrothers (no topic filter)
6. WebSearch supplementary (existing Step 2)
7. Synthesize (existing)
```

### Why agent-level, not Python-level

| Approach | Works for | Problem |
|----------|-----------|---------|
| Brave API in Python | Users with BRAVE_API_KEY (~5%) | Almost nobody has the key |
| OpenAI Responses API in Python | Users with OPENAI_API_KEY (~90%) | Costs money, adds complexity, x.com URLs may be filtered |
| Agent WebSearch (SKILL.md) | **100% of users** | Adds ~5-8 sec before script |
| xAI API in Python | Users with XAI_API_KEY (~30%) | Not universal |

The agent approach wins because:
1. **100% availability** - Claude/OpenClaw always has WebSearch
2. **Zero API key requirements** - WebSearch is built into the agent runtime
3. **Smarter parsing** - Claude is better at "find the X handle for Dor Brothers" than any regex
4. **Simpler implementation** - SKILL.md instruction + `--x-handle` CLI arg, no new Python module
5. **No EXCLUDED_DOMAINS problem** - agent WebSearch is independent of the Python web search backends

The ~5-8 second latency is negligible against the 2-3 minute script runtime.

### SKILL.md Changes (Claude Code variant)

Add between intent parsing and Step 1:

```markdown
## Step 0.5: Resolve X Handle (if topic is a person/brand)

If TOPIC looks like a person, creator, brand, or specific account (1-3 words, proper noun),
do ONE WebSearch to find their X handle:

WebSearch("{TOPIC} X twitter handle")

From the results, extract the X/Twitter handle. Look for:
- Profile URLs: x.com/{handle} or twitter.com/{handle}
- Mentions like "@handle" in bios, articles, or social profiles
- "Follow @handle on X" patterns

If you find a clear, unambiguous handle, pass it to the script:
  --x-handle={handle}

If ambiguous or not found, omit the flag. The script works fine without it.

Skip this step if:
- TOPIC is clearly not an entity (e.g., "best rap songs 2026", "how to use Docker")
- TOPIC already contains @ (e.g., "@elonmusk")
- Using --quick depth
```

### OpenClaw Variant Changes

Same instruction added to `variants/open/references/research.md` (or inline in the open SKILL.md routing). OpenClaw agents also have WebSearch available.

### Python Script Changes

**`last30days.py` - Add `--x-handle` argument:**

```python
parser.add_argument('--x-handle', type=str, default=None,
                    help='Resolved X handle for topic entity (without @)')
```

Pass `resolved_handle` to `_run_supplemental()`.

**`_run_supplemental()` - Accept and use resolved handle:**

```python
def _run_supplemental(
    topic, reddit_items, x_items, from_date, to_date,
    depth, x_source, progress=None, skip_reddit=False,
    resolved_handle=None,  # NEW
):
    # Extract entities from Phase 1 (existing)
    entities = entity_extract.extract_entities(...)

    # Add resolved handle if not already in entity list
    if resolved_handle and resolved_handle.lower() not in {h.lower() for h in entities["x_handles"]}:
        # Search resolved handle separately - unfiltered (no topic keywords)
        # This is the key difference from entity-extracted handles
        resolved_future = executor.submit(
            bird_x.search_handles,
            [resolved_handle],
            None,  # topic=None means unfiltered search
            from_date,
            count_per=10,
        )
```

**`bird_x.search_handles()` - Optional topic parameter:**

```python
def search_handles(handles, topic, from_date, count_per=5):
    # topic is now Optional[str]
    for handle in handles:
        handle = handle.lstrip("@")
        if topic:
            core_topic = _extract_core_subject(topic)
            query = f"from:{handle} {core_topic} since:{from_date}"
        else:
            # Unfiltered: get all recent posts from this handle
            query = f"from:{handle} since:{from_date}"
```

### Why no topic filter for resolved handles

This is the key insight. When you resolve that @DorBrothers IS the Dor Brothers, you want ALL their recent posts - not just ones that literally contain "Dor Brothers." Their post about the Logan Paul collab says "our new AI film with @LoganPaul" - no mention of "Dor Brothers" anywhere. With topic filtering, you'd miss it. Without it, you get their full recent activity, which is exactly what the user wants.

## Technical Considerations

### Handle resolution requires Bird or xAI for Phase 2

The `--x-handle` is only useful if the script can search `from:{handle}`. Currently:
- **Bird:** supports `from:handle` via Twitter GraphQL (free)
- **xAI:** does NOT support `from:handle` (Grok semantic search only)

If the user only has xAI (no Bird), the resolved handle can't be searched in Phase 2. Options:
1. Skip Phase 2 handle search when `x_source == "xai"` (current behavior for entity handles too)
2. Future: Add handle search to xai_x.py using `allowed_x_handles` filter

For v1, accept this limitation. Bird is free and most X-enabled users have it.

### Relevance scoring for unfiltered handle posts

Bird-parsed items default to `relevance: 0.7`. Unfiltered resolved-handle posts have no topic-keyword signal. Set `relevance: 0.5` for these so engagement and recency drive ranking, preventing off-topic viral posts from the entity from outranking genuinely relevant Phase 1 results.

### Stats block display

When `--x-handle` is used and produces results, show it in the stats:

```
├─ 🔵 X: 38 posts │ 782+ likes │ 36+ reposts │ via @TheDorBrothers + keyword search
```

Add `resolved_x_handle` field to `Report` schema for this.

### Skip conditions for the agent

The SKILL.md instruction tells the agent to skip handle resolution when:
- Topic is clearly not an entity (multi-word generic phrases)
- Topic already contains @ (user provided the handle)
- Using `--quick` depth
- Agent judges it would be wasted effort

The agent's judgment here is a feature, not a bug. Claude is good at deciding "Dor Brothers = probably has an X account" vs "best rap songs 2026 = definitely not an entity."

## Acceptance Criteria

- [x] SKILL.md updated with Step 0.5 handle resolution instructions
- [x] OpenClaw variant updated with same instructions
- [x] `last30days.py` accepts `--x-handle` argument
- [x] `_run_supplemental()` accepts `resolved_handle` parameter
- [x] `bird_x.search_handles()` accepts `topic=None` for unfiltered search
- [x] Resolved handle searched with `from:{handle}` (no topic filter) when Bird is available
- [x] `Report` schema includes `resolved_x_handle` field
- [x] Stats block shows resolved handle when used
- [x] Graceful when `--x-handle` is provided but Bird is not available (skips silently)
- [ ] "Dor Brothers" search resolves handle and finds their direct posts (requires live test)
- [ ] "Jason Calacanis" search resolves @jason (requires live test)
- [ ] "best rap songs 2026" does NOT trigger handle resolution (agent judgment, not code)

## Test Plan

### Manual test cases

| # | Query | Expected | What it tests |
|---|-------|----------|---------------|
| 1 | "Dor Brothers" | Agent resolves handle, passes --x-handle, script finds their posts | Full happy path |
| 2 | "Jason Calacanis" | Agent resolves @jason (non-obvious handle) | Handle != name |
| 3 | "best rap songs 2026" | Agent skips handle resolution entirely | Non-entity detection |
| 4 | "OpenAI" | Agent may or may not resolve (judgment call) | Generic entity edge case |
| 5 | "Linus Ekenstam" | Agent resolves @LinusEkenstam | Person with matching handle |
| 6 | "Dor Brothers" with `--quick` | No handle resolution | Skip condition |
| 7 | "Dor Brothers" with xAI only (no Bird) | Handle resolved but Phase 2 skips it | Graceful degradation |

### Automated tests (`tests/`)

```python
# test_bird_x.py - new tests
def test_search_handles_unfiltered_mode():
    """bird_x.search_handles(topic=None) omits topic keywords from query."""

def test_search_handles_with_topic():
    """bird_x.search_handles(topic="AI films") includes topic in query (existing behavior)."""

# test_last30days.py - integration
def test_x_handle_arg_parsed():
    """--x-handle=TheDorBrothers is parsed and passed to _run_supplemental."""

def test_resolved_handle_dedup_with_entity_extract():
    """Resolved handle already in entity list is not double-searched."""

def test_resolved_handle_skipped_when_xai_only():
    """When x_source='xai', resolved handle is not searched (no from: support)."""

def test_resolved_handle_relevance_set_lower():
    """Items from resolved handle search get relevance 0.5, not 0.7."""
```

### E2E validation

```bash
# Run with explicit handle to test Python-side changes
python3 scripts/last30days.py "Dor Brothers" --x-handle=TheDorBrothers --emit=compact 2>&1 | grep -E "\[Phase|handle"

# Expected:
# [Phase 2] Drilling into @TheDorBrothers (resolved) + @handle1, @handle2 (extracted)
# [Phase 2] +0 Reddit, +8 X (5 from resolved handle)
```

```bash
# Full agent test (runs SKILL.md flow including handle resolution WebSearch)
claude --print "/last30days Dor Brothers" 2>&1 | grep -i "handle\|x-handle\|resolved"
```

## Files Modified

| File | Change |
|---|---|
| `SKILL.md` | Add Step 0.5: handle resolution via WebSearch |
| `variants/open/references/research.md` | Same handle resolution instructions for OpenClaw |
| `scripts/last30days.py` | Add `--x-handle` CLI arg, pass to `_run_supplemental()` |
| `scripts/lib/bird_x.py` | `search_handles()` gets `topic: Optional[str]` param |
| `scripts/lib/schema.py` | Add `resolved_x_handle: Optional[str]` to `Report` |
| `scripts/lib/render.py` | Show resolved handle in stats block |
| `tests/test_bird_x.py` | Tests for unfiltered search_handles mode |
| `tests/test_last30days.py` | Tests for --x-handle arg handling |

**NOT modified:** No new `handle_resolve.py` module. Resolution is agent intelligence, not Python code.

## Dependencies & Risks

- **Bird availability:** Resolved handle can only be searched when Bird is the X source. xAI doesn't support `from:handle` queries. ~70% of X-enabled users have Bird (free, browser cookies).
- **Agent judgment:** The agent decides whether a topic is an entity worth resolving. Claude is good at this, but it's non-deterministic. Some edge cases will be missed. This is acceptable - the feature is additive (no regression when it doesn't fire).
- **WebSearch latency:** Adds ~5-8 seconds before the script starts. Negligible against 2-3 minute script runtime.
- **Handle accuracy:** The agent could resolve to the wrong handle. Mitigated by the agent's ability to evaluate results (unlike a regex, Claude can tell if a result actually belongs to the queried entity).

## Sources

- Existing entity extraction: `scripts/lib/entity_extract.py`
- Phase 2 supplemental search: `scripts/last30days.py:387-513`
- Bird search handles: `scripts/lib/bird_x.py:273-346`
- SKILL.md agent flow: `SKILL.md:82-120`
- OpenClaw variant: `variants/open/SKILL.md`
- Smart supplemental search plan: `docs/plans/2026-02-07-feat-smart-supplemental-search-plan.md`
