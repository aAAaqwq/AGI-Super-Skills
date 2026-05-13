# Architecture: Single-Repo Multi-Role Agent Team

## Core Architecture

**Single-repo + multi-role**, not distributed microservices.

Five design axioms:

1. **File system is the state center** — The writer's `OUTPUT/` is the single source of truth. All other roles read/write through symlinks. No API, no database, no message queue.
2. **AGENTS.md is the role definition** — Each role's responsibilities, standards, and domain knowledge live in its own AGENTS.md. Loaded automatically at spawn. No runtime configuration needed.
3. **Flow is code** — The orchestrator (main agent) is the only dispatcher. Sub-agents cannot spawn each other. Flow is controllable and predictable.
4. **Scoring is the quality gate** — The score threshold (e.g. 8.5/10) is a business bar, not a technical bar. It ensures output is shippable.
5. **agentToAgent must be OFF** — Sub-agents never talk to each other directly. All coordination goes through the orchestrator.

## Directory Layout

```
~/.openclaw/
├── openclaw.json                          # Global config
├── workspace/                             # Main agent (orchestrator)
│   ├── AGENTS.md
│   ├── TOOLS.md
│   └── MEMORY.md
│
├── workspace-{writer}/                    # Writer workspace (PRIMARY)
│   ├── AGENTS.md                          # Writer role definition
│   ├── TOOLS.md
│   ├── OUTPUT/                            # ← REAL directory
│   │   └── {project-name}/
│   │       ├── article.md
│   │       ├── metadata.md
│   │       └── design-notes.md
│   └── KNOWLEDGE/                         # Shared knowledge
│
├── workspace-{reviewer-1}/                # Reviewer (SHELL)
│   ├── AGENTS.md
│   ├── TOOLS.md
│   ├── OUTPUT -> ../workspace-{writer}/OUTPUT
│   └── KNOWLEDGE -> ../workspace-{writer}/KNOWLEDGE
│
├── workspace-{scorer}/                    # Scorer (SHELL)
│   ├── AGENTS.md
│   ├── TOOLS.md
│   ├── OUTPUT -> ../workspace-{writer}/OUTPUT
│   └── KNOWLEDGE -> ../workspace-{writer}/KNOWLEDGE
│
└── workspace-{fixer}/                     # Fixer (SHELL)
    ├── AGENTS.md
    ├── TOOLS.md
    ├── OUTPUT -> ../workspace-{writer}/OUTPUT
    └── KNOWLEDGE -> ../workspace-{writer}/KNOWLEDGE
```

## Symlink Mechanism

Create symlinks from each shell workspace to the writer workspace:

```bash
ln -s /absolute/path/to/workspace-{writer}/OUTPUT OUTPUT
ln -s /absolute/path/to/workspace-{writer}/KNOWLEDGE KNOWLEDGE
```

**Important**: Use absolute paths in symlinks.

## OpenClaw Configuration

```json
{
  "agents": {
    "list": [
      {
        "id": "main",
        "subagents": {
          "allowAgents": ["writer", "reviewer", "scorer", "fixer"]
        }
      },
      {
        "id": "writer",
        "workspace": "~/.openclaw/workspace-writer"
      }
    ]
  }
}
```

**Critical**: `subagents.allowAgents` must list all agent IDs the orchestrator can spawn.

## Permission Model

| Action | Who can do it |
|--------|---------------|
| Spawn sub-agents | Only the main agent |
| Read/write OUTPUT/ | All agents via symlinks |
| Talk to each other | ❌ Never |
| Update AGENTS.md | ❌ Only human |