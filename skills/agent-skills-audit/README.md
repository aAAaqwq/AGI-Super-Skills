# audit-code skill

Single-source `SKILL.md` repository for multi-agent distribution.

## What this skill is

`audit-code` is a structured, two-pass multidisciplinary code-audit skill. It guides an expert-panel audit (security, performance, UX, DX, edge cases) with tie-breaker reconciliation and a prioritized final report.

## What this skill does

- Produces findings-first audits with severity, confidence, evidence, and concrete fixes.
- Uses an invariant coverage matrix to catch cross-route parity issues.
- Emphasizes operationally realistic verification plans.
- Includes Bun + SQLite heuristics for common hidden failure modes.

## Goal

Keep one canonical skill repository and install/sync it into:
- Codex: `~/.codex/skills/<skill-name>`
- Claude Code: `~/.claude/skills/<skill-name>`
- Cursor: `~/.cursor/skills/<skill-name>`

## Why this layout

- Claude Agent Skills are filesystem-based directories centered on `SKILL.md` with optional resources.
- Cursor Agent Skills are also `SKILL.md`-based and dynamically loaded.
- Open skills tooling (`npx skills`) supports multiple agents and both `copy` and `symlink` install methods.

Given current ecosystem behavior, **copy is the safest default** for broad compatibility (especially for global/home installs), while symlink remains optional for local developer workflows.

## Sync script

Use the included script to fan out from this canonical repo:

```bash
scripts/sync-to-agents.sh
```

Options:

```bash
# default: copy to codex, claude, cursor
scripts/sync-to-agents.sh

# symlink mode (optional)
scripts/sync-to-agents.sh --method symlink

# subset of agents
scripts/sync-to-agents.sh --agents codex,claude
```

## Optional: install via `npx skills`

If this repo is published remotely, you can install/update with the open installer:

```bash
npx skills add <owner>/<repo> -a codex -a claude-code -a cursor --method copy
```

(Use `--method symlink` only when you explicitly want linked working copies.)

## Recommended workflow

1. Edit only this canonical repo.
2. Run `scripts/sync-to-agents.sh` after changes.
3. Keep `copy` as default for portability.
4. Use `symlink` only for local development convenience.

## References

- Claude docs: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Cursor docs entry point: https://cursor.com/docs/context/skills
- Cursor official usage details: https://cursor.com/blog/agent-best-practices and https://cursor.com/changelog/2-4
- Open skills installer: https://github.com/vercel-labs/skills
