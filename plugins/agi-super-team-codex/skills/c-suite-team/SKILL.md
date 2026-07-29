---
name: c-suite-team
description: Run an outcome-oriented C-suite team in Codex with the parent acting as CEO, bounded specialist leaves, a Governor review gate, and honest manual or sequential fallbacks. Use when the user asks for an executive team, starter kit, CEO-led swarm, or cross-functional plan and delivery.
---

# C-suite Team

Run the smallest C-suite team that can produce the requested outcome. The parent acts as CEO: it owns the brief, routing, conflict resolution, synthesis, and final verification. It does not spawn another CEO.

The packaged structural contract is [references/team-contracts.json](references/team-contracts.json). Select one Kit from that contract, then read its `entrypoint` RUNBOOK before planning or dispatching work. Read only the role contracts needed for the task. Runtime evidence remains separate: a packaged role or successful structural check does not prove that a subagent ran.

## 1. Select a Kit and execution mode

Choose the closest Kit, then state its outcome, coordinator, independent reviewer, expected artifacts, checks, and human approval gates. Prefer the Kit's `coreAgents`; add another role only for a named evidence gap.

Negotiate capability before dispatch:

- **Native:** `spawn_agent`, messaging, and wait capabilities exist, and the mapped `ast-*` leaf roles are installed.
- **Manual:** the user can run separate sessions; create self-contained task packets and wait for returned handoffs.
- **Sequential:** only one context exists; read each role contract in order and label the result as a simulated role pass, not independent review.
- **Blocked:** a required mapping, permission, or reviewer is absent and substitution would change the decision.

Never claim native delegation in manual or sequential mode.

## 2. CEO routing plan

Create a dispatch table before spawning:

| Role | Objective | Owned artifacts/files | Dependencies | Acceptance checks |
|---|---|---|---|---|

Use no more than three concurrent leaves. A leaf receives one bounded task and must not spawn more agents. Shared writable files have one owner. External publishing, deployment, trading, credentials, destructive changes, commits, pushes, merges, and PR creation require explicit human approval.

## 3. Dispatch and handoff

In native mode, use `spawn_agent` with the adapter's mapped `ast-*` agent. Codex custom Agent types cannot be combined with a full-history fork: when `agent_type` is an `ast-*` role, set `fork_turns` to `"none"` and put all required context in the self-contained task packet below. Treat a rejected spawn as a failed attempt, not an observed role handoff. Every task includes:

```markdown
Objective: one observable result.
Scope and non-goals: exact boundaries.
Ownership: writable files or response-only artifacts.
Starting evidence: paths, facts, and constraints.
Dependencies: what must arrive first.
Acceptance checks: commands or review criteria.
Safety: approval gates and forbidden external actions.
Output: artifacts, evidence, limitations, and next action.
```

Use messages only for evidence that changes another task. Wait for each required handoff. A returned status is not evidence that the artifact exists or passes its checks.

In manual mode, create the same self-contained packets and ask the user to run each in a separate session. Do not continue as if a role ran: wait for the user to return the complete handoff, record that response under `rolesObserved`, and leave missing roles `pending`.

## 4. Governor gate

After specialist work is integrated, dispatch `ast-governor` as an independent leaf in native mode. The Governor receives the original brief, integrated artifacts, checks, and known limitations—not the CEO's desired conclusion. It returns approve, revise, or blocked with evidence.

In manual mode, create a separate Governor packet with the same evidence, require the user to run it in an independent session, and wait for its returned review. If the review is not returned, report `Review pending`; do not substitute the CEO's judgment. In sequential mode, call this a `Governor-style review pass`; do not call it independent. If the Governor mapping is unavailable in native mode, report `Review pending`.

## 5. CEO synthesis and verification receipt

Resolve disagreements using source evidence and fresh checks. Do not concatenate handoffs. Finish with a verification receipt containing:

```json
{
  "kit": "selected-kit",
  "mode": "native|manual|sequential|blocked",
  "rolesRequested": [],
  "rolesObserved": [],
  "artifacts": [],
  "checks": [],
  "governorReview": "approve|revise|blocked|pending|sequential-pass",
  "humanApprovalsPending": [],
  "limitations": [],
  "runtimeEvidence": "observed|pending"
}
```

Only `observed` means the active Harness returned inspectable subagent handoffs. It does not imply business outcomes, cross-harness compatibility, or automatic verification.

## Stop conditions

Stop and report the exact gap when a required role is missing, task ownership overlaps, evidence cannot be accessed safely, the Governor requests revision, a check fails, or new authority is required. Preserve partial artifacts and make the next safe action explicit.
