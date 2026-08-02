# Pre-optimization audit baseline

Date: 2026-08-02 UTC

Skill version: 4.1.0 shadow

Gate: `BLOCKED` for full product-readiness; approved only as a bounded no-send `WAIT` shadow sample.

## Verified baseline

- 169 unit and contract tests pass.
- The reviewed canonical shadow artifact reconciled its processed observations, used closed 15m/1h/4h/1d Futures candles, matched its local manifests, and emitted no delivery intent.
- The Smart Money collector has a strict PNL/ROI TOP30 evidence contract and fails closed when Square identity mapping is absent.

## Material gaps before optimization

1. Feed discovery was not guaranteed to be captured before the report that consumed it; input freshness and source-set reconciliation were not enforced.
2. Curated signal input accepted `url` while the active producer emitted `source_url`.
3. Smart Money ranking, Square identity/Profile content, and canonical market reporting were not joined in one real shadow run.
4. Author plans were not replayed from publication through the decision cutoff, so a previously hit SL/TP could be missed.
5. Author-supplied stops lacked an ATR/structure reasonableness gate; fees, slippage, funding, and depth were not part of net RR.
6. The production pipeline did not consume author/Profile evidence or persisted 60-day performance in scoring.
7. Separate canary ledgers could generate identical logical run/attempt IDs for different artifacts.
8. No scheduler, Telegram send, or trading action was enabled.

This document is a code-review checkpoint, not live Binance evidence, a profitability claim, or an execution recommendation. Dynamic responses, reports, databases, identities, credentials, and account state are intentionally not published.
