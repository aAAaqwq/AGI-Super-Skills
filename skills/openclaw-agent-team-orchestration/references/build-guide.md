# Build Guide

## Prerequisites

- OpenClaw installed
- Model configured (e.g., kimi/k2p5)
- Access to `~/.openclaw/openclaw.json`

## Phase 1: Plan

Define:
1. **Team name** — e.g., "content-team"
2. **Roles**: Writer (1), Reviewers (1-3), Scorer (1), Fixer (1)
3. **Scoring dimensions** (3-5, weights = 100%)
4. **Threshold** (recommended: 8.0-8.5)
5. **Max fix rounds** (recommended: 3)

## Phase 2: Create Writer Workspace

```bash
mkdir -p ~/.openclaw/workspace-{writer}/OUTPUT
mkdir -p ~/.openclaw/workspace-{writer}/KNOWLEDGE
```

Create `AGENTS.md` (comprehensive) and `TOOLS.md`.

## Phase 3: Create Shell Workspaces

For each non-writer role:
```bash
WRITER_WS="$HOME/.openclaw/workspace-writer"
SHELL_WS="$HOME/.openclaw/workspace-reviewer"

mkdir -p "$SHELL_WS"
ln -s "$WRITER_WS/OUTPUT" "$SHELL_WS/OUTPUT"
ln -s "$WRITER_WS/KNOWLEDGE" "$SHELL_WS/KNOWLEDGE"

# Create AGENTS.md and TOOLS.md
```

## Phase 4: Register Agents

Edit `~/.openclaw/openclaw.json`:
```json
{
  "agents": {
    "list": [
      {"id": "writer", "workspace": "~/.openclaw/workspace-writer"},
      {"id": "reviewer", "workspace": "~/.openclaw/workspace-reviewer"}
    ]
  }
}
```

## Phase 5: Grant Permissions

Add to main agent:
```json
{
  "id": "main",
  "subagents": {
    "allowAgents": ["writer", "reviewer", "scorer", "fixer"]
  }
}
```

## Phase 6: TOOLS.md for All

Every agent needs TOOLS.md with:
1. Don't read AGENTS.md
2. Always provide `path` parameter
3. Include all required parameters

## Phase 7: Smoke Test

1. Spawn writer → verify files appear
2. Spawn reviewer → verify report appears
3. Spawn scorer → verify JSON score report
4. If needed, spawn fixer → verify versioned files

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Spawn permission error | Missing allowAgents | Add to openclaw.json |
| Token = 0 for 5+ min | Tool-call loop | Add TOOLS.md reminders |
| Empty output | Vague task | Re-spawn with explicit requirements |
| Broken symlinks | Relative paths | Recreate with absolute paths |