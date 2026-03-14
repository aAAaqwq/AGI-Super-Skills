# CLAUDE.md — Project-Level Working Rules

> Copy this to your project root: `cp ~/.claude/templates/CLAUDE.md ./CLAUDE.md`
> Customize per project. Keep under 30KB to avoid context rot.

## Project Context
- **Project**: [Name]
- **Stack**: [e.g., Next.js 14 / Supabase / TypeScript]
- **Main goal**: [one sentence]

## Workflow Rules
- Use **Plan Mode** for any task >2h or touching >3 files
- `TodoWrite` before executing multi-step changes
- Commit after each logical unit — no giant commits
- Tests pass before moving on

## Context Management
- Window >30KB → open new GSD session
- Model routing: Opus for architecture/debugging, Sonnet for implementation
- CLAUDE.md size limit: 30KB hard cap

## Code Style
- [Your project's conventions here]

## MCP / Tools Available
- gitnexus: code graph queries (`npx gitnexus mcp`)
- [Others as applicable]

## Off-Limits
- No `rm -rf` without explicit confirmation
- No API keys in code — use env vars

---
*Template v1.0 | Source: vault/40-49 Agents/Workflows/claude-code/templates/CLAUDE.md*
