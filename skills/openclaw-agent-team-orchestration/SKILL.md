---
name: agent-team-orchestration-v3-public
description: "Build and run multi-agent content production teams on OpenClaw with single-repo architecture, symlink-based file sharing, role-specialized AGENTS.md, and automated review-fix-score loops. Use when: (1) Setting up a team of 3+ agents with writer/reviewer/scorer/fixer roles for content creation, (2) Creating a quality-controlled publishing pipeline, (3) Bootstrapping agent workspaces with symlinks and tool configs from scratch, (4) Running multi-round review→fix→score cycles until a quality threshold is met, (5) Debugging agent spawn permissions, tool-call loops, or symlink issues. Based on real production experience building a 6-agent content team (2026-03-30)."
---

# Agent Team Orchestration V3 (Public)

Production-proven playbook for building multi-agent content production teams on OpenClaw. Covers architecture, setup, role design, orchestration workflow, and hard-won debugging lessons.

## Architecture in 30 Seconds

**Single-repo + multi-role**. One writer owns the real `OUTPUT/` directory. All other roles (reviewers, scorer, fixer) are lightweight shell workspaces with symlinks pointing to the writer's OUTPUT. The orchestrator (main agent) dispatches work and controls flow — sub-agents never talk to each other.

```
Main Agent (Orchestrator)
  ├── spawn → Writer → writes to OUTPUT/
  ├── spawn → Fact-Reviewer ──┐
  ├── spawn → Style-Reviewer ─┤ read OUTPUT/ via symlinks
  ├── spawn → Data-Reviewer ──┤
  ├── spawn → Scorer ─────────┤
  └── spawn → Fixer ──────────┘ writes versioned files to OUTPUT/
```

Five axioms:
1. File system = state center (no API, no DB)
2. AGENTS.md = role definition (auto-loaded at spawn)
3. Orchestrator = sole dispatcher (agentToAgent OFF)
4. Score threshold = quality gate (e.g., 8.5/10)
5. TOOLS.md = mandatory guardrails (prevents model tool-call loops)

## Quick Start

### 1. Run the setup script

```bash
# Creates workspaces, symlinks, and TOOLS.md for all roles
scripts/setup-team.sh {writer-id} {fact-reviewer-id} {style-reviewer-id} {data-reviewer-id} {scorer-id} {fixer-id}
```

### 2. Register agents in openclaw.json

Add each agent to `agents.list` and grant spawn permissions to the main agent. The script prints the exact JSON to add.

### 3. Write AGENTS.md for each role

Use the templates in `references/role-templates.md`. The writer gets a comprehensive domain manual (400-600 lines). Reviewers, scorer, and fixer get focused role definitions (100-200 lines each).

### 4. Run the pipeline

```
Spawn writer → wait → parallel spawn reviewers → wait → spawn scorer → read score
  → pass? done. fail? spawn fixer → loop back to reviewers.
```

## Reference Files

| File | Read when... |
|------|-------------|
| [references/architecture.md](references/architecture.md) | Understanding the single-repo design, directory layout, symlink mechanism, and OpenClaw configuration |
| [references/build-guide.md](references/build-guide.md) | Setting up a team from scratch — step-by-step phases from planning to smoke test |
| [references/workflow.md](references/workflow.md) | Running the pipeline — spawn patterns, score parsing, decision gates, batch production, monitoring |
| [references/role-templates.md](references/role-templates.md) | Writing AGENTS.md and TOOLS.md for each role — templates and principles |
| [references/lessons-learned.md](references/lessons-learned.md) | Debugging — k2p5 tool-call loops, spawn permissions, symlink issues, performance benchmarks |

## The Review-Fix Loop

```
[1] Spawn Writer → announce → verify OUTPUT/{project}/
[2] Parallel: Reviewers (fact, style, data) → all announce
[3] Spawn Scorer → announce → parse JSON from score-report.md
[4] total_score >= 8.5 → ✅ notify human
    total_score < 8.5 AND round < 3 → Spawn Fixer → back to [2]
    total_score < 8.5 AND round >= 3 → ❌ escalate to human
```

See `references/workflow.md` for spawn command patterns and edge case handling.

## Critical Lessons (Save Hours)

**1. TOOLS.md prevents infinite loops**: Some models (k2p5 confirmed) will try to `read` their own AGENTS.md even though it's auto-injected, causing infinite tool-call retries. Adding three lines to TOOLS.md eliminates this completely.

**2. `allowAgents` is required**: The main agent cannot spawn sub-agents without explicit `subagents.allowAgents` in openclaw.json. This is the #1 setup mistake.

**3. Use absolute paths in symlinks**: Relative symlinks break when the working directory changes during agent context switches.

**4. Version filenames explicitly in tasks**: When running round 2, tell the reviewer to read `article-v2.md`, not "the article". Ambiguous paths cause agents to review the old version.

See `references/lessons-learned.md` for full details and performance benchmarks.

## Scripts

| Script | Usage |
|--------|-------|
| `scripts/setup-team.sh` | `./setup-team.sh <writer-id> <role-1> <role-2> ...` — Creates all workspaces, symlinks, and TOOLS.md files |