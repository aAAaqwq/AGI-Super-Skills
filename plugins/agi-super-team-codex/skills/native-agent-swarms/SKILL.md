---
name: native-agent-swarms
description: Coordinate small teams of specialized Codex agents with bounded parallelism, explicit ownership, native messaging, and evidence-based synthesis. Use when two or more independent investigations, reviews, or implementation streams can run concurrently without sharing writable files, or when the user asks for swarm, team, parallel agent, or multi-reviewer execution.
---

# Native Agent Swarms

Use Codex-native collaboration instead of Claude TeamCreate, TaskCreate, SendMessage, tmux, or shared team-state conventions. Keep orchestration in the parent agent and use specialists as leaf workers.

## Gate delegation

Delegate only when the user or applicable project instructions authorize subagents. Delegation never expands the user's requested scope or permission to change external state.

Before spawning, confirm:

- At least two work streams are genuinely independent.
- Each worker has a bounded objective and sufficient starting evidence.
- Writable files have exactly one owner.
- The expected speed or quality gain exceeds coordination overhead.
- Available thread capacity can accommodate the team; prefer 2-3 workers and never exceed the configured limit.

Stay sequential when tasks share state, one result determines the next, or workers would edit the same files.

## Compose the team

Select the narrowest installed custom agents. Typical choices include `planner`, `architect`, `code-reviewer`, `security-reviewer`, `quality-engineer`, `hypothesis-debugger`, `performance-reviewer`, `database-reviewer`, `accessibility-reviewer`, and language reviewers.

Use `team-coordinator` only to advise on decomposition. The parent agent remains responsible for spawning, monitoring, resolving conflicts, and final verification. Keep nesting depth at one unless the user explicitly asks for recursive delegation and the runtime configuration safely allows it.

## Write dispatch contracts

Every worker task must include:

```markdown
Objective: one concrete result.
Scope: exact subsystem, files, or hypothesis.
Ownership: writable files; all other files are read-only.
Starting evidence: errors, requirements, paths, and relevant constraints.
Acceptance criteria: observable completion conditions.
Safety: no commit, push, deploy, external messages, secret access, or destructive commands.
Output: findings or changes, evidence, commands run, gaps, and a concise handoff.
```

Use `spawn_agent` for independent work. Use direct `send_message` only for relevant evidence or interface updates, `followup_task` for a new bounded assignment after a worker becomes idle, `wait_agent` for progress, `interrupt_agent` only when work is obsolete or unsafe, and `list_agents` to audit active capacity.

## Coordinate execution

1. Record the task-to-agent and file-ownership matrix.
2. Spawn independent tasks close together so they run concurrently.
3. Continue useful parent-only work while agents run.
4. Relay only evidence that materially changes another worker's task.
5. Stop fan-out when results converge, capacity is saturated, or coordination cost rises.
6. Never let two implementation agents modify the same file or mutable external resource.

For specialized patterns, read only the relevant reference:

- Multi-dimensional review: [review-swarms.md](references/review-swarms.md)
- Competing-hypothesis debugging: [debug-swarms.md](references/debug-swarms.md)
- Parallel feature implementation: [feature-swarms.md](references/feature-swarms.md)

## Synthesize and verify

The parent agent must inspect worker evidence rather than concatenate summaries.

- Deduplicate overlapping findings and retain the strongest evidence.
- Resolve disagreements by checking source files, tests, or command output.
- Review all shared-worktree changes for overlap and unintended edits.
- Run integration-level verification after individual checks pass.
- Report which agents ran, their scopes, final evidence, and unresolved gaps.

Do not claim success merely because all workers returned. Completion requires integrated verification proportional to risk.

Source patterns adapted from `wshobson/agents` commit `767d969a73ce6608d10ac713e52be9ac7f061ab9` (MIT), rewritten for native Codex collaboration and permission boundaries.
