# Evidence First design QA

## Source and implementation

- Selected reference: `/Users/danielli/.codex/generated_images/019f83e4-109d-7311-87bd-10c77a7f6266/exec-ed311408-9751-418d-b10d-08b89d564615.png`
- Local implementation: `http://127.0.0.1:8765/`
- Side-by-side comparison: `/tmp/agi-super-team-design-comparison-final.png`

The implementation keeps the reference's evidence-first hierarchy, dark technical palette, large outcome statement, receipt panel, restrained violet accents, and dense but quiet supporting sections. Copy, version, counts, and verification state were replaced with repository-backed values or an explicit pending state.

## Viewports and states checked

- 1536×1024, dark theme: hero, header, live star enhancement, receipt, primary actions.
- 1440×1024, light theme: contrast, card hierarchy, theme toggle.
- 390×844, dark theme: responsive hero, 44px targets, mobile navigation, no horizontal overflow.
- 390×844 guide index: readable navigation, single-column article, one primary CTA, no horizontal overflow.
- JavaScript disabled/default DOM: cached-data explanation remains visible; no zero-count fallback.
- GitHub API failure, timeout, 429, stale cache, and invalid payload: exercised by site-data and site-contract tests.

## Resolved differences

- P0: none.
- P1: fixed primary CTA contrast, mobile guide navigation, progressive no-JS navigation, and programmatic status announcements.
- P2: fixed secondary text contrast, visible star-history summary/table, table scopes, link affordance, and mobile control sizing.

All visible assets are generated or vendored files: the constellation hero, RGBA logo family, self-hosted fonts, and Phosphor icons. No placeholder art, third-party icon CDN, or remote dynamic badge is required.

final result: passed
