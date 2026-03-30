---
name: agent-patterns
description: "Format SPAWN REQUEST messages to launch parallel agents, generate structured agent status reports, and define communication protocols within the sprint system. Use when the user needs to coordinate multiple agents, format spawn requests, produce agent reports, or establish inter-agent communication patterns."
allowed-tools: Read
version: 1.0.0
author: Damien Laine <damien.laine@gmail.com>
license: MIT
---

# Agent Patterns

Coordinate multi-agent workflows using structured communication protocols. Covers spawn requests, status reports, and inter-agent messaging within the sprint system.

## Spawn Request Format

When launching a parallel agent, use this structure:

```markdown
## SPAWN REQUEST
- **Agent ID**: <unique-id>
- **Role**: <role-name>
- **Task**: <one-line description>
- **Context**: <relevant files or state>
- **Expected Output**: <deliverable format>
- **Timeout**: <max duration>
```

## Agent Report Format

Each agent reports back using:

```markdown
## AGENT REPORT
- **Agent ID**: <id>
- **Status**: completed | failed | blocked
- **Summary**: <one-line result>
- **Output**: <deliverable or file path>
- **Issues**: <blockers or warnings, if any>
- **Duration**: <time taken>
```

## Coordination Workflow

1. **Define tasks** — break work into independent units suitable for parallel execution
2. **Spawn agents** — send SPAWN REQUEST for each task with clear context
3. **Monitor status** — track agent reports as they complete
4. **Handle failures** — retry failed agents or reassign blocked tasks
5. **Merge results** — combine agent outputs into final deliverable, resolving conflicts

## Communication Rules

- Agents communicate through structured reports, not free-form text
- Each message includes agent ID for traceability
- Blocked agents must report immediately rather than waiting silently
- The coordinator agent reviews all reports before merging

## Error Handling

See `references/errors.md` for common failure modes and recovery steps.

## Examples

See `references/examples.md` for complete spawn-and-report workflows.
