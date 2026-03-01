# Live-Canonical Alignment Master Plan

> **Status**: Implemented. See `docs/state_sync/` for individual component specs.

## 1. Ultimate Objective

Build financial-grade deterministic alignment across `live`, `paper`, and `backtester`, with `live` as the canonical behaviour.

Given the same state and market inputs, `paper` and `backtester` must reproduce what `live` did, except for explicitly tagged non-simulatable OMS/exchange effects.

## 2. Non-Negotiable Principles

- `live` is the source of truth for behavioural parity.
- Every decision and action must be auditable and traceable.
- Unknown drift is unacceptable; every mismatch must be classified.
- Numeric tolerance must be as strict as practical, defaulting to the tightest safe threshold.
- All changes are delivered via atomic PRs into `master`.

## 3. Canonical Data Strategy (Best Available Source)

Use a layered canonical source model:

1. Exchange-confirmed outcomes captured by the live execution path (fills, closures, realised PnL, balance effects).
2. Live OMS intent and decision trail recorded locally.
3. Market data stream used by live at decision time.

If any canonical field is missing today, add explicit capture so replay is complete and deterministic.

## 4. Foundation First: State Sync (Part 1)

Before further parity hardening, implement state synchronisation from `live` to `paper` and `backtester`.

### 4.1 Snapshot Contract

Define a versioned snapshot schema including at minimum:

- account balances and equity components
- per-symbol positions (size, side, entry basis, realised/unrealised context)
- open orders and protective order state
- cooldown/re-entry state
- strategy runtime gates needed for deterministic continuation
- risk and kill-switch flags
- watermark/timestamps needed for deterministic resume

### 4.2 Export/Import Pipeline

- `live`: export canonical snapshot + event cursor.
- `paper`: import snapshot as runtime seed.
- `backtester`: import snapshot as initial engine state.

### 4.3 Replay Harness

Build replay capability:

- Input: snapshot + bounded historical market data window.
- Output: canonical ledger and decision trace.
- Goal: reproduce recent `live` trades under equivalent state.

## 5. Parity Hardening Sequence (After State Sync)

1. Decision parity: gates, thresholds, ranking, reversal, ATR floor, regime filters.
2. Event parity: entry/add/partial/close event ordering and semantics.
3. Numeric parity: realised PnL, fees, balance deltas, rounding policy.
4. GPU parity against CPU SSOT: event-by-event and numeric convergence.

## 6. Mismatch Taxonomy

Every mismatch must be tagged as one of:

- deterministic logic divergence (bug)
- numeric policy divergence (rounding/precision)
- state initialisation gap
- market data alignment gap
- non-simulatable exchange/OMS effect (explicitly accepted)

Only the last category may remain as an accepted residual.

## 7. Acceptance Criteria (Financial Grade)

- `paper` and `backtester` can replay recent `live` trades from synced state.
- All decisions have reason codes and trace artifacts.
- Event parity is exact for simulatable paths.
- Numeric parity meets strict thresholds; exceptions are documented and approved.
- Residual mismatches are fully classified and auditable.

## 8. Delivery Protocol (Atomic)

For each successful change set:

1. Open an atomic PR to `master`.
2. Run reviewer subagent review.
3. Merge only if review is acceptable.
4. Clean up only the current agent/session branch and worktree (local + remote).
5. Continue to the next axis.

## 9. Current Delivery Status (as of 2026-02-17)

Completed foundations and parity controls:

1. State sync foundation is live:
   - canonical snapshot export/import for `live -> paper`
   - backtester init-state v2 loading with runtime cooldown maps
   - state alignment audit across live/paper/snapshot
2. Deterministic replay bundle is live:
   - bundle build with fixed inputs and manifest
   - scripted sequence for seed, replay, audits, and strict gate
3. Backtester parity audits are live:
   - exit-trade reconciliation report
   - action-level reconciliation report
   - configurable timestamp bucketing with strict default (`1ms`)
4. Live/paper parity audit is live:
   - action-level reconciliation report against live and paper DB trade logs
   - strict mismatch mode (`--fail-on-mismatch`) for automation
5. Bundle hard gate is live:
   - unified gate across state + trade + action reports
   - deterministic pass/fail output for CI/manual enforcement

## 10. Remaining Critical Work (Next Axes)

1. Decision-reason canonicalisation:
   - align live reason text with canonical reason codes used by replay outputs
   - enforce machine-readable reason parity checks in audits
2. Market data determinism hardening:
   - record and validate replay candle provenance (window hash / universe lock)
   - remove remaining market-data alignment ambiguity
3. Paper deterministic replay harness:
   - provide reproducible paper replay path from canonical snapshot + bounded data window
   - verify event ordering parity against live baseline under equal state
4. CPU/GPU parity continuation on synced-state baseline:
   - continue axis-by-axis validation with zero deterministic/numeric drift tolerance
   - classify any residual mismatch with the approved taxonomy
5. Operational enforcement:
   - automate replay bundle gate + live/paper reconcile in scheduled checks
   - treat gate failures as release blockers for strategy/runtime changes
