# Solo Founder runbook

This runbook coordinates a small product-to-launch evaluation. It packages instructions and handoffs; it does not start Agents or prove an outcome. Runtime status remains **Validation pending** until a matching harness receipt exists.

## Input

Provide the problem, target user, evidence already available, constraints, non-goals, desired delivery horizon, and actions that require human approval. The `ceo` converts this brief into a bounded decision. The minimum core is `ceo`, `cpo`, `pe`, and `governor`; use `cco` and `cmo` only when launch work is in scope.

## Waves

1. `ceo` records assumptions, alternatives, owners, and approval gates.
2. `cpo` defines the user problem and testable acceptance criteria while `pe` inspects feasibility and delivery risks.
3. When needed, `cco` drafts sourced assets and `cmo` defines a measurable distribution experiment.
4. `governor` independently challenges evidence, safety, and completion claims before CEO synthesis.

Parallel work is allowed only for independent tasks with non-overlapping ownership. The coordinator owns shared artifacts and final synthesis.

## Artifacts

- Product decision memo with assumptions and rejected alternatives.
- Test-first delivery plan with explicit rollback.
- Optional launch evidence pack with claim provenance.
- Governor gate decision and executive handoff.

## Checks

- `scope-approved`: success, non-goals, and approval boundaries are explicit.
- `implementation-plan-reviewed`: acceptance tests and rollback are named.
- `launch-claims-sourced`: every material claim has evidence or a placeholder.
- `governor-gate-recorded`: dissent and unresolved risks are preserved.

## Capability fallback

If native delegation exists, the root coordinator may dispatch bounded tasks and wait for observable handoffs. Otherwise, produce task packets for manual routing. In a single context, execute roles sequentially and label Governor review as same-context review, not independent review.

## Human approval

A human must approve publishing, account access, purchases, deployments, merges, destructive changes, and any use of credentials. Missing approval or evidence stops the relevant wave.
