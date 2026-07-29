# Product Delivery runbook

This runbook converts a validated user problem into a review-ready software change. It does not authorize deployment, merge, or production access. Runtime outcome evidence is **Validation pending** until a matching receipt exists.

## Input

Provide the user problem, evidence, repository or system context, constraints, non-goals, acceptance criteria, and release boundary. The core is `ceo`, `cpo`, `cto`, `pe`, and `governor`; include `cdo` when schemas, analytics, or data contracts change.

## Waves

1. `ceo` establishes outcome, ownership, decision deadline, and approval gates.
2. `cpo` sharpens the user journey while `cto` identifies architectural constraints and migration seams.
3. `pe` implements through a test-first plan after interfaces stabilize; `cdo` owns data-contract work when selected.
4. `governor` reviews evidence, regression risk, security implications, and rollback before the CEO handoff.

Implementation tasks may run in parallel only after shared Interfaces are frozen and each file has one owner.

## Artifacts

- Product brief and testable acceptance criteria.
- Architecture decision with migration and rollback.
- Working change set and regression evidence.
- Release handoff with limitations and approvals still required.

## Checks

- `acceptance-criteria-testable`: expected behavior is observable.
- `architecture-reviewed`: Interfaces, Seams, and failure modes are recorded.
- `regression-checks-pass`: relevant tests and checks have exact results.
- `rollback-documented`: the safe reversal path is explicit.

## Capability fallback

When subagents are available, keep planning/review workers read-only and assign writes to one implementation owner per file. Without delegation, follow the waves sequentially or route task packets manually. Do not call same-context review independent.

## Human approval

Merge, deployment, production data access, schema mutation, credentials, dependency additions with material risk, and destructive commands require explicit human approval.
