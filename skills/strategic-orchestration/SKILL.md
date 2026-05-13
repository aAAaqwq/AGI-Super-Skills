---
name: strategic-orchestration
description: Coordinate agents toward a unified objective; assign roles, sequence work, prevent conflicts, and define success criteria.
metadata:
  author: Morpheus
  version: 2.0.0
  owner: Morpheus Agent
  category: orchestration
---

# SKILL: strategic-orchestration

## Purpose
Coordinate all agents toward a unified objective with clear roles, sequencing, and success criteria.

## When to Use
- A goal requires multiple agents (Morpheus/Trinity/RedHat/Smith)
- Work is stuck due to unclear ownership or sequencing
- Conflicting actions or duplicated efforts appear

## Inputs
- `objective` (required): the desired outcome in one sentence
- `system_state` (required): current tasks, constraints, risks, and available resources

## Steps
1. Define the goal clearly and state non-goals.
2. Define success criteria (what “done” looks like) and the validation path.
3. Map required agents and assign responsibilities:
   - Morpheus → judgment, direction, risk evaluation
   - RedHat → execution, implementation, verification
   - Trinity → routing/coordination/capital engine (when applicable)
   - Smith → adversarial pressure / stress test (bounded)
4. Define sequence:
   - dependencies first
   - execution second
   - validation checkpoints
5. Define agent-to-agent interfaces:
   - what each agent must deliver to the next
   - what inputs are required
6. Detect conflicts:
   - overlapping ownership
   - governance boundary violations
   - unvalidated leaps
7. Output the orchestration plan and the next immediate messages/actions.

## Validation
- No conflicting actions across agents.
- Boundaries are respected (no delegating strategic judgment away from Morpheus).
- Each step has an owner and an acceptance criterion.

## Output
- `execution_plan` (ordered steps with owners)
- `agent_roles`
- `dependencies`
- `handoff_messages` (drafts to each agent)
- `success_criteria`

## Safety Rules
- Do not authorize irreversible actions without explicit approval and governance alignment.
- Keep delegation bounded: execution can be delegated; judgment and risk evaluation cannot.

## Example
Objective: “Ship a safe MCP + skills update this week.”
Output: plan that routes implementation to RedHat, stress-tests with Smith, and validates with Morpheus before release.

