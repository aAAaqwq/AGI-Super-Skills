# Codex CLI Reference

Canonical Codex guidance for `plan-issue` + `coding-agent`.

## Plan-First Gate

For non-trivial tasks:
1. Plan first (`plan-issue` behavior).
2. Wait for explicit `APPROVE`.
3. Execute with Codex (`coding-agent` behavior).

Do not perform writes before `APPROVE`.

Preferred plan artifact flow:

```bash
./scripts/plan --engine codex --repo /path/to/repo "Implement feature X"
./scripts/plan-review --repo /path/to/repo
./scripts/plan-review-live --repo /path/to/repo
```

## Default Strategy

Use single-agent Codex for most work:
1. `codex -c 'model_reasoning_effort="high"' exec --full-auto "..."` for feature implementation/refactors after approval.
2. `codex exec resume --last "..."` for follow-up work.
3. Use tmux only when persistence/reattach is required.

Reasoning default policy:
- Use `high` for feature implementation and architectural refactors.
- Use `medium`/`low` only for simple fixes/docs tasks or explicit fast/cheap requests.

## Core Commands

### Implementation (post-approval)

```bash
codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature X according to the approved plan."
```

### Resume previous context

```bash
codex exec resume --last "Address review findings from the previous run"
```

### Review against base branch

```bash
timeout 600s codex review --base <base> --title "PR #N Review"
```

### Review latest generated plan (read-only)

```bash
./scripts/plan-review --repo /path/to/repo
```

### Review latest generated plan (interactive checkpoints)

```bash
./scripts/plan-review-live --repo /path/to/repo
# Optional: force legacy engine
./scripts/plan-review-live --engine legacy --repo /path/to/repo
```

`code-implement --plan` enforces latest per-plan review metadata readiness.
If blocking decisions remain unresolved, run `plan-review-live` first or use `--force` to bypass explicitly.

### Structured non-interactive output

```bash
codex exec --json --output-last-message /tmp/last.txt "Summarize changes"
```

Useful automation flags:
- `--json`
- `--output-schema <FILE>`
- `--output-last-message <FILE>`
- `--skip-git-repo-check`

## Safety Profiles

- Guardrailed default: `codex exec --full-auto "..."`
- Explicit bypass (only when user asks to bypass approvals):

```bash
codex exec --dangerously-bypass-approvals-and-sandbox "..."
```

## Execution Policy Matrix

| Task | Primary | Secondary | Notes |
|------|---------|-----------|-------|
| Implementation | direct `codex -c 'model_reasoning_effort=\"high\"' exec --full-auto` | tmux transport | Use `resume` for iterative loops; lower reasoning only for simple/docs or explicit fast/cheap requests |
| PR review | `codex review --base` | Claude CLI fallback | Keep timeout >= 600s |
| Long-running implementation | tmux transport | direct `codex -c 'model_reasoning_effort=\"high\"' exec --full-auto` | For reattach/log durability |

Implementation-mode env var:
- `CODING_AGENT_IMPL_MODE=direct|tmux|auto`
- `direct`: run Codex directly first
- `tmux`: run tmux transport first
- `auto`: tmux first only when attached to TTY and tmux is available

## MCP Clarification

1. `codex mcp ...`: configure external MCP tools for Codex runs.
2. `codex mcp-server`: expose Codex itself as an MCP server.

## Official Sources

- https://developers.openai.com/codex/cli/reference
- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/mcp
- https://developers.openai.com/codex/multi-agent
