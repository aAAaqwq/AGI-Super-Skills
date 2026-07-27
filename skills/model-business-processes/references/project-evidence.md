# Project evidence: business process design

## Evidence baseline

- Main baseline reviewed: `origin/main` at `401ad9c`.
- Windows behavior comparison: `codex/win-native-uia-1.1.7` at `526abba`.

## Primary sources

- `docs/process/README.md`: process inventory and shared terminology.
- `docs/process/shared-preconditions.md`: common authorization, browser, configuration, and failure gates.
- `docs/process/pipeline.md`: sequential orchestration and stop/skip behavior.
- `docs/process/greeting.md`: success-count limit semantics and eligibility filtering.
- `docs/process/collect.md`: top-N processing, identity chain, precise/batch gates, attachment evidence, persistence, scoring, and sync.
- `docs/process/chat.md`: stage-aware decision order, rejection states, reply guardrails, terminal states, and manual handoff.
- `docs/process/sync-jobs.md`: overwrite/merge semantics and data-loss protection.
- `docs/process/scoring-ranking.md`: eligibility, idempotent scoring, version checks, and ranking.
- `docs/process/interview-report-sync.md`: explicit human confirmation, appointment state, read-only reporting, and cloud projection.

## Reusable lessons

1. Identical CLI shapes can have different business meanings. One `limit` counts successful greetings; another counts the first N reviewed contacts.
2. Pipeline success requires ordered exit-code contracts. A later step must not run after a failed prerequisite unless an explicit resume/skip option is chosen.
3. Candidate/object identity is a business gate, not only an automation concern. If the visible panel cannot be tied to the target, object-specific reads and writes must stop.
4. “Already sent,” “requested,” “received,” “verified,” and “persisted” are distinct states with different retries and outputs.
5. Existing inbound artifacts should remain collectible even when an outbound-request suitability gate says not to send a new request.
6. Terminal conversation states prevent repeated automated pursuit and transfer responsibility to a human.
7. Scoring and cloud sync are downstream effects. Their failure should not falsify or roll back a correctly committed local collection unless the product explicitly chooses a larger transaction.
8. Dry-run contracts vary. Some workflows are fully read-only; others may navigate, open previews, or place drafts. The process document must state this operation by operation.
9. Logs should expose per-item reason codes and totals that distinguish skipped, failed, pending, already complete, and newly completed outcomes.
