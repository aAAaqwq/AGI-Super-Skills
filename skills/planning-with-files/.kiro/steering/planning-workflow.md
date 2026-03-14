# Planning with Files Workflow

Use persistent markdown files as your "working memory on disk" — the Manus pattern that made a $2B acquisition.

## The Core Pattern

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## Required Files

Create these three files in your project root before starting complex tasks:

| File | Purpose | When to Update |
|------|---------|----------------|
| `task_plan.md` | Phases, progress, decisions | After each phase |
| `findings.md` | Research, discoveries | After ANY discovery |
| `progress.md` | Session log, test results | Throughout session |

## Quick Start

1. **Create `task_plan.md`** with goal, phases, and status tracking
2. **Create `findings.md`** for research and technical decisions
3. **Create `progress.md`** for session logging
4. **Re-read plan before decisions** — keeps goals in attention
5. **Update after each phase** — mark complete, log errors

## When to Use This Pattern

**Use for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups
