# Optimization verification

Date: 2026-08-02 UTC

Baseline commit: `c86715eab8ef2ae6874b0bc8686a5fb052ef2457`

Scope: public, credential-free Binance Square shadow Skill. This record distinguishes code verification, live component observations, and unresolved production gates.

## Verified in this optimization

- 200 offline unit, contract, integration, report, lineage, and production-cycle tests pass.
- Feed refresh must precede the radar, reference an immutable byte-identical snapshot, and be no more than ten minutes old.
- Signal inputs accept both `url` and producer-compatible `source_url` while retaining canonical URL validation.
- Production/canary run identity includes an explicit namespace.
- Cross-run new/duplicate baselines are filtered by that same namespace, preventing canary history from contaminating production counts.
- The complete Futures instrument catalog, Smart Money evidence, optional identity mapping, Profile plan, official news, Feed, market evidence, and generated reports are recorded as distinct lineage sources.
- Smart Money identity mapping requires an actual file, its computed SHA-256, explicit `topTraderId` and `squareUid`, one-to-one binding, capture time, and matching live/fixture provenance. Display-name matching is rejected.
- Author SL/TP plans are conservatively replayed from publication to decision time. Stops must also satisfy pre-publication structure and ATR distance rules.
- Direction consensus counts independent stable authors and independent content clusters rather than repeated posts.
- Unconfirmed Bollinger squeezes are downgraded. TOP requires an applied execution-cost model and cost-adjusted main-target RR of at least 2.0; missing costs fail closed to WATCH.
- Reports reconcile five source classes and reject incomplete TOP rows, including missing source/evidence times or unapplied costs.
- The production-cycle wrapper is foreground-only and no-send. This optimization did not install a scheduler, deliver a message, access trading credentials, or place an order.

## Bounded live component observations

These observations were collected in the source environment and are not bundled as fixtures or claimed as an end-to-end production run:

- At `2026-08-02T02:24:12Z`, the public Smart Money collector returned complete 30D PNL and ROI rankings with 30 rows each, 60 unique `topTraderId` values, and 60/60 public trader-detail records.
- At `2026-08-02T02:26:17Z`, the read-only Square Feed refresh produced 74 unique valid posts (73 new, 1 duplicate) after 36 scroll rounds. No cookie, token, local storage, password, or verification code was read.
- The official-news live check was rate-limited with HTTP 429. The collector therefore did not claim a successful live news artifact; the detail-fallback behavior is covered by offline contracts.

## Gates still open

1. Smart Money `topTraderId → squareUid` mapping remains 0/60 until reviewed dual-ID evidence exists. Names, aliases, badges, follower counts, and similar text are insufficient.
2. The default package has no live Square Profile content fetcher, so Profile coverage remains planned but not live-complete.
3. Execution-cost parameters are not exposed through the production CLI; default candidates therefore fail closed to WATCH instead of becoming executable TOP entries.
4. No real 60-day point-in-time author performance history has been wired into production scoring.
5. A full live `run_production_cycle.py` canary was not executed because the observation was outside the allowed first ten minutes of a four-hour UTC slot, while official news was also rate-limited. The timing gate was not weakened.
6. Strategy profitability and forward performance remain unverified. Component success is not a trading recommendation.

## Current decision

The optimized package is suitable for further no-send shadow testing and evidence collection. It is not approved for scheduled delivery, executable trade recommendations, or trading automation until the open gates above are closed and independently reviewed.
