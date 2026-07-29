# Executive Team runbook

This is the portable orchestration contract for all 14 role packs. The active root coordinator follows `ceo` behavior, selects specialists, collects evidence, and routes independent review to `governor`. Files alone do not start a swarm; harness execution remains **Validation pending** until a matching receipt exists.

## Input

Provide one bounded company outcome, evidence, constraints, non-goals, deadline, risk tolerance, desired artifacts, and actions requiring human approval. The standing core is `ceo`, `coo`, and `governor`; all other roles are available but selected only when their domain materially affects the outcome.

## Waves

1. `ceo` classifies the brief, records decisions and approvals, and chooses the smallest relevant subset of roles.
2. `coo` proposes task ownership, dependencies, merge order, and capacity. Never start all 14 roles at once.
3. The coordinator dispatches at most 2–3 independent workers concurrently unless the observable harness limit is lower. Shared files and mutable resources have one owner.
4. Specialists return artifacts, exact evidence, limitations, and rollback. A returned task is not automatically accepted as complete.
5. `governor` independently challenges material claims, checks, and unresolved risk.
6. `ceo` synthesizes accepted evidence into an executive handoff and stops at the human approval gate.

Route by need: `cto` and `pe` for engineering; `cpo` for product; `cqo` for quantitative research; `cdo` for data; `cco` and `cmo` for content and growth; `cfo` for economics; `cro` for research; `cso` for revenue; and `clo` for legal risk.

## Artifacts

- Executive routing plan with selected roles and exclusions.
- Task contracts with non-overlapping ownership and acceptance checks.
- Specialist artifacts and observable handoffs.
- Governor review and verified executive handoff.

## Checks

- `minimum-team-selected`: each selected role has a material responsibility.
- `ownership-non-overlapping`: concurrent writes have exactly one owner.
- `specialist-evidence-reviewed`: the CEO verifies evidence rather than concatenating reports.
- `human-approval-recorded`: external or irreversible actions remain pending until approved.

## Capability fallback

Use native delegation only when the harness visibly exposes spawn, messaging, waiting, and capacity controls. If delegation is unavailable, the CEO generates manual task packets for role workspaces. If only one context exists, run roles sequentially and label Governor review as same-context, not independent. Never invent task IDs, worker completion, schedules, tools, or parallel execution.

## Human approval

Publishing, messages, purchases, financial transactions, credential use, deployment, merge, production changes, legal filings, and destructive operations require explicit human authorization. Delegation does not broaden that authority.
