# Operations Response runbook

This runbook coordinates a bounded incident or delivery failure from impact assessment through recovery review. It does not grant production access or authorize changes. Runtime effectiveness is **Validation pending** until a matching receipt exists.

## Input

Provide the observable symptom, affected users and systems, start time, current evidence, recent changes, available telemetry, access limits, and approved containment actions. The core is `ceo`, `coo`, `cto`, `pe`, and `governor`; use `cdo` for data integrity and `clo` for notification or regulatory risk.

## Waves

1. `ceo` fixes the decision authority and user-impact priority; `coo` becomes incident coordinator.
2. `cto` maps failure domains while `pe` gathers reversible diagnostic evidence.
3. `cdo` checks data impact and `clo` identifies notification obligations when applicable.
4. After human approval, the accountable owner performs the smallest containment or recovery action and verifies it.
5. `governor` reviews evidence, residual risk, and the post-incident claims.

Do not parallelize dependent diagnosis and recovery steps. Independent hypotheses may run in parallel only with read-only evidence and distinct ownership.

## Artifacts

- Timestamped incident scope and impact statement.
- Containment and recovery plan with owners and rollback.
- Verification evidence for observed recovery.
- Post-incident review with corrective actions.

## Checks

- `impact-bounded`: affected journeys, systems, and uncertainty are explicit.
- `writes-human-approved`: production or external mutations have named approval.
- `recovery-verified`: health is checked through observable signals.
- `follow-up-owners-assigned`: corrective actions have owners and due conditions.

## Capability fallback

With native workers, assign one falsifiable hypothesis per read-only investigator and keep recovery writes under one accountable owner. Without them, work hypotheses sequentially or route manual packets. Lack of telemetry or access must be reported as a gap.

## Human approval

Production commands, deploys, rollbacks, data repair, customer notification, credential use, and destructive actions require explicit human approval and a verified rollback path.
