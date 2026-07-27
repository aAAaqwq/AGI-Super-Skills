---
name: model-business-processes
description: Discover, model, document, and validate executable business processes from product requirements, code, tests, logs, and operator behavior. Use when creating process documentation, workflow maps, state machines, pipeline orchestration, limit semantics, identity gates, dry-run rules, side-effect policies, failure handling, observability, handoffs, or acceptance criteria for multi-step automated or human-in-the-loop operations.
---

# Model Business Processes

Describe what the business operation means before describing how automation clicks through it. Make every side effect, identity gate, terminal state, and failure branch explicit.

## Workflow

1. **Set the boundary.** Name the process, actor, trigger, goal, start/end states, included systems, excluded decisions, and success metric.
2. **Collect evidence.** Read requirements, current code, configuration, tests, logs, database states, UI behavior, and operator instructions. Mark disagreements instead of averaging them.
3. **Define business semantics.** Specify inputs, `limit` meaning, ordering, eligibility, identity, deduplication, state transitions, and what counts as processed, attempted, completed, verified, or persisted.
4. **Separate layers.** Keep business decisions, orchestration, platform automation, persistence, external projection, and human approval as distinct lanes.
5. **Order gates before side effects.** Validate authorization, page/system state, target identity, eligibility, duplicate status, and external prerequisites before any irreversible action.
6. **Model the happy path and all exits.** Include skip, retry, wait, manual handoff, batch stop, rollback, compensation, and partial-success behavior.
7. **Define dry-run precisely.** State what remains read-only, what navigation or draft mutation still occurs, what external writes are forbidden, and what evidence is produced.
8. **Design observability.** Give each result a reason code, evidence fields, counters, and operator-facing summary. Never report success from intent alone.
9. **Map tests.** Link each branch and invariant to unit, integration, installed-app, or real-system acceptance evidence.
10. **Review with stakeholders.** Confirm business owners understand limits, human decisions, data effects, and failure handling; confirm engineers can implement the process without guessing.

## Required process invariants

- Stable identity must be established before reading or writing object-specific data.
- A state-changing action must have a fresh postcondition.
- Retries must reacquire state and remain idempotent.
- Batch counters must use one documented semantic.
- Individual failure versus batch-stop conditions must be distinct.
- Persist only evidence-backed outcomes; do not reuse stale panel/context data.
- External sync, scoring, or reporting must not corrupt the primary business transaction.
- Human approval must be explicit for actions that materially affect people or commitments.

## Deliverables

Produce a concise process spec, one useful flow/state visualization, decision tables for complex gates, reason codes, data/state effects, and an acceptance matrix. Avoid duplicating code line by line.

## References

- Read [process-spec-template.md](references/process-spec-template.md) when creating or reviewing a process document.
- Read [project-evidence.md](references/project-evidence.md) for process patterns and failure lessons extracted from this repository.
