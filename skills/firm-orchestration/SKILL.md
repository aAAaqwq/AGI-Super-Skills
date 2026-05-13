---
name: firm-orchestration
version: 1.0.0
description: >
  Pyramid multi-agent orchestration for OpenClaw: routes objectives from a CEO agent
  down through departments, services and employees via sessions_send / sessions_spawn,
  collects and merges results, enforces handoff contracts, and writes the final
  deliverable back to the originating session.
author: romainsantoli-web
license: MIT
metadata:
  openclaw:
    requires:
      env: []
      bins: []
    tools:
      - sessions_list
      - sessions_send
      - sessions_spawn
      - sessions_history
    primaryEnv: ""
tags:
  - orchestration
  - multi-agent
  - a2a
  - firm
  - pyramid
  - enterprise
---

# firm-orchestration

This skill implements the **A2A (Agent-to-Agent) pyramid** pattern for OpenClaw.

## Architecture

```
CEO Agent (orchestrator)
 ├── Department Strategy
 │   └── Service Planning → Employee Analyst
 ├── Department Engineering
 │   └── Service Backend  → Employee Implementer
 ├── Department Quality
 │   └── Service Testing  → Employee Auditor
 └── Department Operations
     └── Service Release  → Employee Coordinator
```

## Usage

Send this to your OpenClaw session to trigger a full firm orchestration run:

```
@firm-orchestration run
  objective: "Build a payment API"
  departments: ["engineering", "quality"]
  delivery_format: "github_pr"
```

## Tools activated

| Tool | Purpose |
|---|---|
| `sessions_list` | Discover active department/service sessions |
| `sessions_spawn` | Spawn missing sessions per pyramid level |
| `sessions_send` | Delegate objectives down the hierarchy |
| `sessions_history` | Collect results from child sessions |

## Handoff contract

Each delegation payload follows this schema:

```json
{
  "from": "ceo",
  "to": "department:engineering",
  "objective": "...",
  "constraints": ["...", "..."],
  "definition_of_done": "...",
  "context_ref": "memory:delivery/latest",
  "reply_session": "main"
}
```

## Merge strategy

Results from all departments are:
1. Collected via `sessions_history` with a 30-second deadline
2. Deduplicated by `objective_key`
3. Merged in dependency order (Strategy → Engineering → Quality → Ops)
4. Formatted according to `delivery_format`

## Operating Protocol (Anthropic-style)

*Based on real Anthropic team practices — "How Anthropic teams use Claude Code"*

### Phase 1 — Parallel dispatch (never sequential)
Fan-out simultaneously to all departments via `sessions_send`. Never wait for one department
before launching the next. Each session receives the full handoff contract and maintains its
own complete context. Store all `reply_session` refs for convergence.

```
Objective received →
  sessions_send(engineering) ‖ sessions_send(quality) ‖ sessions_send(ops) ‖ sessions_send(strategy)
→ wait(deadline=30s)
→ collect via sessions_history
```

### Phase 2 — Iterative loop on blockers
If a department returns `status: blocked`, do NOT resolve it yourself. Spawn a joint
resolution session with the two conflicting departments and let them iterate:

```
engineering blocked by legal →
  sessions_spawn(participants=[engineering, legal], objective="resolve_blocker") →
  wait(max_iterations=2) →
  collect resolution
```

Maximum 2 re-delegation cycles before escalating to CEO with explicit blocker report.

### Phase 3 — Convergence with partial acceptance
30-second hard deadline. After deadline: accept partial results, mark missing department
outputs as `status: timeout`, include them in final report as open items.
Never block delivery on a single department.

### Phase 4 — Validate before merge
Before merging each department output into the final deliverable:
1. Check output satisfies its `definition_of_done`
2. If DoD not met: flag as `quality: partial` — do not silently drop
3. Merge in dependency order only: Strategy → Engineering → Quality → Ops

### Phase 5 — Deliver + document
After every completed orchestration, automatically append:
1. Run summary (1 paragraph)
2. Departments that delivered / timed out / were blocked
3. Architecture/process decisions made
4. Suggestions for improving the next similar run

All final outputs carry the mandatory disclaimer:
> ⚠️ Contenu généré par IA — validation humaine requise avant utilisation en production.

### Phase 6 — Git checkpoints (when Engineering is involved)
Require Engineering to commit after each sub-task — not only at end of run.
Reject PRs that are not draft + labelled `needs-review`.
Never allow direct merge to `main`.

## Security

- All inter-session calls use `reply_session: "main"` to avoid orphaned sessions
- `sessions_spawn` is rate-limited: max 20 spawns per orchestration run
- Payloads are validated against the handoff schema before dispatch
- No external network calls — pure Gateway WebSocket routing

## Example prompt

```
Use the firm-orchestration skill to:
  objective: "Audit the authentication module"
  departments: ["quality", "engineering"]
  constraints: ["read-only access only", "no production changes"]
  definition_of_done: "Security report with CVSS scores and fix recommendations"
  delivery_format: "markdown_report"
```

---

## 💎 Support

Si ce skill vous est utile, vous pouvez soutenir le développement :

**Dogecoin** : `DQBggqFNWsRNTPb6kkiwppnMo1Hm8edfWq`
