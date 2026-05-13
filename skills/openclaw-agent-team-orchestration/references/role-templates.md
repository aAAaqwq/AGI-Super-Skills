# Role Templates

## Writer Template (400-600 lines)

```markdown
# {Product}-Writer — AGENTS.md

> One-paragraph identity: what you create, for whom, brand positioning.

## Part 1: Identity
- Content format and platform
- Target audience
- Core brand values
- Red lines (never do)

## Part 2: Content Standards
- Style guide
- Structure templates
- Quality rules
- Anti-patterns

## Part 3: Variety Systems
- Topic pool
- Angle pool
- Anti-homogenization matrix

## Part 4: Output Specification
- File structure
- Naming conventions
- Output directory

## Part 5: Workflow
- Creation process
- Self-audit checklist
```

## Reviewer Template (100-150 lines)

```markdown
# {Product}-{Aspect}-Reviewer — AGENTS.md

> You review {aspect}. You don't review {other aspects}.

## Review Scope
- Dimension A: check items
- Dimension B: check items

## What You DON'T Do
- ❌ List excluded responsibilities

## Output Format
```
## P0 (Blocks publication)
- [location] Problem → Fix

## P1 (Recommended)
- [location] Problem → Fix

## P2 (Optional)
- [location] Problem → Fix

## Summary
- P0: X / P1: X / P2: X
```
```

## Scorer Template (150-200 lines)

```markdown
# {Product}-Scorer — AGENTS.md

> Independent quantitative assessment.

## Scoring Dimensions
| # | Dimension | Weight |
|---|-----------|--------|
| 1 | {Dim 1} | {X}% |
| 2 | {Dim 2} | {X}% |

## Hard Rules
1. P0 cap: If P0 exists, total ≤ 7.0
2. Brand safety violations = auto-fail

## Output Format
JSON block at start:
```json
{
  "total_score": 8.5,
  "publishable": true
}
```
Followed by human-readable report.
```

## Fixer Template (100-150 lines)

```markdown
# {Product}-Fixer — AGENTS.md

> Make minimal, targeted repairs.

## Fix Priority
1. P0 issues
2. Scorer's top priority
3. P1 issues

## Iron Rules
1. No new issues
2. Add, don't delete
3. Match original style
4. Never change core

## Output
- article-v{N+1}.md
- revision-notes-v{N+1}.md
```

## TOOLS.md Template (All Roles)

```markdown
# TOOLS.md

## Critical Reminders
1. Do NOT read AGENTS.md — auto-injected
2. Always provide `path` parameter
3. Include all required parameters

## Working Directory
- workspace: {role-name}/
- output: OUTPUT/{project}/
```