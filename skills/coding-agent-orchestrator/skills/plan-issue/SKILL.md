---
name: plan-issue
description: "Plan-only workflow for issue/repo changes. Use when user asks to plan, scope, estimate, or design."
metadata: {"openclaw":{"emoji":"🧭"}}
---

# Plan-Issue Skill

## Use This Skill When

- The user asks to plan implementation.
- The user asks for scope, sequencing, risks, or rollout strategy.
- The task is non-trivial and would change files, infra, or workflows.

### Proactive Trigger Matrix

Use `/plan` proactively when any of these apply:
- New feature implementation with non-obvious design choices.
- Multiple valid approaches exist and tradeoff selection matters.
- Changes are likely to touch more than 2-3 files.
- Existing behavior/architecture will change.
- Requirements are partially unclear and need repo exploration first.
- User preference materially affects implementation direction.

Skip `/plan` for:
- Trivial typo or obvious one-line fixes.
- Small deterministic edits with no architectural impact.
- Pure information lookup requests (no implementation intent).

## Required Workflow

1. Gather context using read-only operations first.
2. Build a concrete implementation plan that includes:
- Goal and acceptance criteria.
- In-scope and out-of-scope.
- Step-by-step execution plan.
- Assumptions and risks/failure modes.
- Test/validation checklist.
- At least one alternative with tradeoffs.
3. End with a hard gate:
- `Reply APPROVE to execute this plan.`

## Hard Limits

- No file writes.
- No package installation.
- No commits, PRs, or system-changing commands.
- If the user requests immediate implementation, still provide the plan unless they explicitly say to skip planning.

## Command Alias

`/plan` is a channel alias for this skill.

## Handoff Contract

At the end of every plan response, include:
- `Reply APPROVE to execute this plan.`

If the user sends `APPROVE` in the same conversation context, execution may proceed via `coding-agent`.
