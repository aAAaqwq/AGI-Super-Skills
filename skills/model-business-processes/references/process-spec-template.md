# Executable process specification template

## 1. Header

- Name and identifier
- Owner and actors
- Trigger and frequency
- Goal and explicit non-goals
- Version/platform scope
- Source requirements/code/tests

## 2. Inputs and semantics

Define every input, default, range, normalization, and business meaning. For count/limit values, state whether skipped, filtered, failed, duplicate, or already-complete items consume the limit.

## 3. Preconditions

Classify preconditions:

- authorization and user approval;
- environment and external service;
- page/system state;
- target identity and data freshness;
- configuration and credentials;
- concurrency and existing task state.

Assign each failure a stop, skip, wait, retry, or manual-handoff policy.

## 4. State model

List states and allowed transitions. Include terminal states, retryable states, and manual states. Define the evidence required for each transition and prohibit impossible transitions.

## 5. Main flow

For each numbered step record:

| Step | Business intent | Required evidence | Side effect | Postcondition | Failure policy |
|---|---|---|---|---|---|

Keep technical adapters in a separate implementation note unless they alter business semantics.

## 6. Decision tables

Use a table when several conditions combine. Example columns:

| Identity valid | Eligible | Already complete | User approved | Action | Persisted state |
|---|---|---|---|---|---|

Ensure every combination either has a defined result or is explicitly impossible.

## 7. Dry-run contract

List separately:

- allowed reads and navigation;
- allowed local drafts or previews;
- forbidden external actions;
- forbidden persistence/sync;
- diagnostics and counters still produced;
- cleanup required after preview.

## 8. Failure and recovery

Define bounded retry, state reacquisition, idempotency key, duplicate detection, compensation, batch stop conditions, resume/skip flags, and operator instructions. Do not use one generic “failed” result for identity, authorization, external limit, and technical timeout.

## 9. Data effects

List read/write stores, fields, provenance, transaction boundary, file artifacts, outbox events, notifications, AI inputs, cloud projection, retention, and privacy classification.

## 10. Observability

Define structured reason codes, per-item outcome, batch totals, timings, retry count, identity evidence, artifact hash, and redacted diagnostic bundle. Summary counts must reconcile with item-level results.

## 11. Acceptance matrix

Cover happy path, boundary values, duplicate/retry, stale state, identity conflict, unavailable dependency, partial failure, interruption, dry-run, cleanup, and real external-system behavior. Label synthetic and real-system evidence separately.
