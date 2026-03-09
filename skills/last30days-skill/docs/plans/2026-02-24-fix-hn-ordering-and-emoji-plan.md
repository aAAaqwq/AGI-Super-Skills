---
title: "fix: HN ordering and stats block emoji formatting"
type: fix
status: completed
date: 2026-02-24
---

# fix: HN Ordering and Stats Block Emoji Formatting

## Overview

HN source appears before YouTube in several places (stats block, sort priority, source status) but should be last among the main sources (after YouTube, before Web). The test skill SKILL.md also has plain ASCII instead of box-drawing characters and colored circle emojis.

Desired order everywhere: Reddit > X > YouTube > HN > Web

## Problem Statement / Motivation

When testing `/last30daysHN`, the stats block output shows:
- No ✅ emoji, no 🟠 🔵 🟡 🔴 🌐 🗣️ colored circles
- Plain `|-` instead of `├─` and `|` instead of `│`
- HN appears before YouTube in the stats

The canonical format (established in commit `7c36866`) is:
```
---
✅ All agents reported back!
├─ 🟠 Reddit: {N} threads │ {N} upvotes │ {N} comments
├─ 🔵 X: {N} posts │ {N} likes │ {N} reposts
├─ 🔴 YouTube: {N} videos │ {N} views │ {N} with transcripts
├─ 🟡 HN: {N} stories │ {N} points │ {N} comments
├─ 🌐 Web: {N} pages (supplementary)
└─ 🗣️ Top voices: @{handle1} ({N} likes), @{handle2} │ r/{sub1}, r/{sub2}
---
```

## Technical Approach

### Files to Modify

#### `scripts/lib/score.py` - sort_items()

- [x] Swap HN and YouTube priority in `sort_items()`:
  - YouTube: priority 2 (was 3)
  - HN: priority 3 (was 2)

#### `scripts/lib/render.py` - render_source_status()

- [x] Move HN section (lines ~318-324) to AFTER YouTube section (lines ~326-334)
- [x] Verify render_compact() already has correct order (YouTube before HN) - no change expected

#### `SKILL.md` (private repo root)

- [x] Move the 🟡 HN stats line AFTER the 🔴 YouTube stats line in the template
- [x] Move HN line after YouTube in the footer summary template too

#### `~/.claude/skills/last30daysHN/SKILL.md` (test skill)

- [x] Restore full emoji + box-drawing stats template with correct ordering
- [x] Use canonical format: ✅ ├─ 🟠 🔵 🔴 🟡 🌐 🗣️ └─ │

#### `scripts/lib/ui.py` - show_complete()

- [x] Move HN output after YouTube in both TTY and non-TTY code paths

### Files that are already correct (no change needed)

- `render_compact()` in render.py - already YouTube before HN
- `render_context_snippet()` - score-based ordering, no fixed order
- `last30days.py` pipeline - processing order doesn't affect display

## Acceptance Criteria

- [x] Stats block shows: Reddit > X > YouTube > HN > Web (in that order)
- [x] Stats block has all emojis: ✅ 🟠 🔵 🔴 🟡 🌐 🗣️
- [x] Stats block uses box-drawing chars: ├─ └─ │
- [x] sort_items() tiebreaker: YouTube before HN
- [x] render_source_status() shows YouTube before HN
- [x] ui.py show_complete() shows YouTube before HN
- [x] All existing tests still pass
- [x] Run sync.sh to deploy after fixes

## Sources & References

- Canonical emoji format established in commit `7c36866` ("Fix v2 output quality")
- YouTube emoji added in commit `c66ca7f` ("feat: Add YouTube as 4th research source")
- HN added in commit `38a7ea2` ("feat(hackernews): add Hacker News as 5th research source")
