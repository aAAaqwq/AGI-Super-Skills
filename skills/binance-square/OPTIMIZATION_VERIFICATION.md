# Optimization verification

Date: 2026-08-02 UTC

Base commit before this optimization: `524dbbfc8dd2b1f129f345d172b3ec0e1bcbc328`

Scope: public, credential-free Binance Square shadow Skill. This record separates reproducible code verification, bounded live component evidence, and production gates that remain open.

## Verified in this optimization

- The full Skill suite passes 291 offline unit, contract, integration, report, storage, migration, CLI, and production-cycle tests on the clean v4.2.3 candidate tree.
- Feed discovery now emits `square-feed-coverage/v1`, starts from the top, records scroll geometry and two-phase lazy-load triggers, and distinguishes `BOUNDED_COMPLETE`, `PARTIAL`, `CAPPED`, and `BLOCKED`. A fresh legacy snapshot is `LEGACY_UNVERIFIED`, never silently `COMPLETE`.
- The previous false-stagnation defect is covered: moving rounds with no new post do not count as exhaustion, and leaving/returning to the bottom occurs in separate browser evaluation phases.
- Public Square Profile pagination is wired into the real pipeline with an independent anonymous HTTP client. It filters each item by `firstReleaseTime` in `[decision_at-24h, decision_at)`, handles pinned old posts, validates cursor anchors, and fails closed on offset/schema/request/page-budget uncertainty.
- Profile observations are primary; Feed is a bounded supplement. Deduplication is by canonical `post_id`, all channel observations are retained, and each canonical post receives one detail request. Profile/detail author or time conflicts are quarantined.
- Selected Profile, Feed, and curated-signal source observations remain distinct through raw JSON and the `post_discovery_observation` ledger. The contract enforces `source observations = canonical candidates + same-run duplicates`; raw rows and database rows share run/attempt, channel, ordinal, post identity, URL, and expected Profile identity/time evidence.
- Smart Money and independent seed Profile cohorts keep separate denominators. Seed coverage cannot be presented as Smart Money mapping coverage.
- Identity mapping/v2 binds a single anonymous Binance response, raw bytes, request manifest, SHA-256, and `/data/topTraderId` plus `/data/squareUid` JSON Pointers. The collector only creates `PROPOSED`; offline explicit review creates a new immutable `APPROVED` artifact and external receipt.
- A hash-bound mapping catalog supports multiple approved artifacts in one pipeline run while retaining the old single-artifact path. Catalog members must share tenant and provenance, be `DIRECT_VERIFIED + APPROVED`, and remain one-to-one.
- A single approved v2 artifact and a multi-member approved catalog now use the same storage projection. Proposed v2 and legacy v1 fixture evidence remain non-activating.
- Storage revalidates the full identity evidence graph. Only approved links occupy the active bijection; inactive proposals remain auditable but do not block corrections. Backdated revocation before the active link is rejected.
- An approved catalog is persisted member-by-member only after Smart Money trader entities exist. Each member can create its directly evidenced Square UID author entity and then records the immutable identity artifact plus LINK event; proposals, missing source entities, and conflicts fail closed.
- Profile fetch outcomes now have a separate per-author ledger. Every planned Smart Money or seed author receives exactly one `COMPLETE`, `EMPTY`, `PARTIAL`, `FAILED`, or `NOT_ATTEMPTED` terminal row with cohort, resolved identity, post/page counts, termination reason, and error evidence. The older A/B aggregate table remains intact.
- The production wrapper remains foreground-only and `--no-send`. No scheduler, message delivery, account mutation, trading credential access, or order placement was added.
- Fees and slippage were intentionally excluded from this coverage milestone; the existing nominal-versus-net reporting boundary was not expanded or weakened.
- Feed completion is explicitly DOM-surface-only: current captures emit `coverage_scope=BINANCE_SQUARE_DISCOVER_DOM`, `global_denominator_known=false`, and `pagination_api_exhaustion_verified=false`. A `BOUNDED_COMPLETE` result without that exact fail-closed scope is rejected.
- Feed persistence now separates the current observed capture from the last coverage-eligible capture. Partial observations remain immutable and visible, but cannot advance the eligible pointer; lock contention returns a non-zero result and cannot consume stale latest state.
- The production wrapper no longer consumes the mutable legacy signal file by default, and its CLI path defaults no longer depend on slotted-dataclass member descriptors. Binance server-time validation now happens before Profile, Smart Money, or detail network collection and the verified catalog is reused.
- The production wrapper now performs at most two independent Feed captures by default and stops at the first strict coverage-eligible result. Every attempt must refresh observed latest, match its own immutable snapshot byte-for-byte, and pass the v1 coverage contract; eligible results must also match the eligible pointer byte-for-byte. If both valid captures remain non-eligible, only the latest capture enters radar as the bounded Feed supplement, without cross-attempt union or reading the older eligible pointer. Malformed, error, unchanged, or inconsistent captures still fail closed.
- Profile reports now fail closed on missing cohort denominators, mismatched planned/status totals, missing attempted-author outcomes, duplicate outcome identities, summary/detail disagreement, or a top-level/source status that contradicts the cohort aggregate. Coverage is reported as `(COMPLETE + EMPTY) / planned`; `PARTIAL` never enters the completed numerator, while an exhausted all-`EMPTY` cohort is normalized to `COMPLETE`.
- A live Feed observation exposed an isolated UTF-16 surrogate from browser DOM text. The ingress path now combines valid surrogate pairs, replaces only malformed units with `U+FFFD`, and reports the replacement count. Recursive JSON sanitization is retained as a final compatibility boundary, and failed atomic writes remove their exact temporary file. Native emoji, CJK, Arabic, and existing coverage semantics remain unchanged.
- Production command supervision now emits a flushed heartbeat every 30 seconds while a child is alive, terminates the child if the wrapper is interrupted, and converts radar `SIGTERM` into the existing fail-closed exception path so a reserved attempt becomes terminal `FAILED`. A credential-free renderer exposes the already-validated Telegram contract for one committed report without enabling delivery inside the Skill.

## Bounded live component evidence

These artifacts are local operational evidence and are not bundled into the public Skill package.

- Smart Money evidence captured on 2026-08-01 has SHA-256 `e74fbbb0ad485a7d1b09d284ea9f2650ed1f2b4e1194a2eaf5e315253d8ede3e`: PNL 30 + ROI 30, 60 unique `topTraderId`, and 60/60 public trader-detail records.
- Two direct dual-ID responses were independently reviewed and approved:
  - `5002917326304805120 → GQUlO4HbUDkRVzImNKf5Wg`
  - `4653587280651442944 → QsDXDJe8oPVDORHkTMgozw`
- The remaining 58 leaderboard identities were each queried once through the same anonymous public collector, with a five-second minimum interval and no retries. All 58 responses lacked `/data/topTraderId`, so the collector failed closed and created no inferred mapping. The local 60/60 collection ledger has SHA-256 `d7e9c1f6b9a742c963993018ae4e8157a25a56e0b7c5d7203af7e52be8ec0279`.
- The two approved artifacts are referenced by local catalog SHA-256 `dcf9862ee6314e8a1b8f035e4d98d84c4f87772808ad87039fde2e14817a3fc2`. A real component replay reports mapping coverage `2/60`; both mapped Profiles were successfully exhausted for the current 24-hour window and returned zero current posts.
- At decision probe `2026-08-02T06:50:57Z`, all 9 independent seed Profiles produced a valid `WINDOW_START_CROSSED` termination proof and 12 unique posts inside the strict 24-hour window.
- At `2026-08-02T07:19:12Z`, one component probe exposed only 4 unique Feed posts from 64 valid URL observations after 9 two-phase load-trigger attempts; 60 observations were same-run repeats. It was correctly recorded as `PARTIAL/STAGNANT`.
- A time-legal no-send production canary froze its decision at `2026-08-02T08:01:33.093818Z` for the `08:00Z` slot. Its Feed snapshot contained 83 unique posts from 2,855 valid URL observations, with 2,772 same-run repeats, 51 scroll rounds, and 11 load triggers. Because the preferred minimum of 100 was not met and the stop reason was `STAGNANT`, the result remained `PARTIAL`, not coverage-complete.
- The same canary reconciled `97 candidates = 61 accepted + 36 window-excluded + 0 DQ`; both Smart Money ranking types and all 60 trader details completed; the 9 seed Profiles reached terminal outcomes and contributed 12 source records; the 2 mapped Smart Money Profiles were valid `EMPTY` outcomes while the other 58 stayed `NOT_ATTEMPTED`. Official news and the 851-contract market catalog completed, nine market snapshots had no fetch failure, and the final result was `WAIT` with zero TOP/WATCH opportunities and zero delivery rows.
- The immutable canary report SHA-256 is `796609310a422f7591a2f095526c73e1d16fe569c2605076c19c6b4b162634fb`; its Markdown SHA-256 is `0fbff14a0f6701f03ef79f2d7191dbbdab13de5a50a9efb6cf3c27531646ea02`. SQLite reported `integrity_check=ok`, no foreign-key violations, and a `SUCCEEDED` attempt.
- No Cookie, Authorization header, browser storage, password, verification code, or trading secret was read for these component checks.

## Gates still open

1. Smart Money-to-Square mapping is 2/60, not complete. The remaining 58 identities were attempted through the public direct-binding endpoint but returned no `topTraderId`; they must stay unmapped. Name, avatar, badge, follower, or alias similarity is insufficient.
2. The latest time-legal Feed evidence is `PARTIAL` with 83 unique posts. The Skill can report bounded surface evidence but cannot claim all Binance Square posts.
3. The time-legal canary preceded the final identity/Profile persistence wiring. The report content is real, but a later legal UTC slot is still required to prove those new database rows on the final frozen tree; offline production integration requires exactly 69 Profile terminal rows and 2 approved identity mappings.
4. No real 60-day point-in-time author performance history has been wired into production scoring, and strategy profitability remains unverified.
5. Dynamic identity, Profile, Feed, report, and SQLite artifacts remain local by publication design; a clean install defaults to no active mapping evidence.
6. The 2026-08-03 12:00Z live canary attempts exposed the production-wrapper default-path and late server-time defects fixed above. Those attempts failed closed before report publication and produced no delivery, but a later legal UTC slot is still required to prove the fixes and the final persistence path together.
7. A controlled read-only CDP probe on 2026-08-05 produced two independent current captures with 74 and 90 unique posts. Both remained truthful `PARTIAL/STAGNANT`, retained attempt `1/2` and `2/2` lineage, were not unioned, and did not advance eligible. This proves the retry mechanism operates, not that the Feed stability SLO has passed.

## Current decision

The tree is suitable for continued no-send shadow use and a time-legal production canary. It is not evidence of platform-wide post coverage, complete top-trader identity coverage, scheduled operation, executable trade recommendations, or future profitability.
