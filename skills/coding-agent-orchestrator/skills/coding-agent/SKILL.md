---
name: coding-agent
description: "Implementation/review workflow for approved plans. Route ACP-first, then CLI fallback. Use after explicit APPROVE."
disable-model-invocation: true
metadata: {"openclaw":{"emoji":"💻","requires":{"bins":["gh"],"anyBins":["codex","claude"],"env":[]}}}
---

# Coding-Agent Skill

## Entry Gate

Only execute this skill after explicit approval in the current conversation context:
- `APPROVE`

Approval must correspond to the latest pending plan in-context.
If no matching approved plan exists, stop and request:
`Run /plan first, then reply APPROVE.`

## Execution Workflow

1. Verify toolchain before major workflows:
- `command -v codex && codex --version`
- `command -v timeout`
- `command -v gh`
- `command -v claude || test -x ~/.claude/local/claude`
2. Gather read-only context first (`rg`, `git status`, `git diff`, docs).
3. Execute the approved implementation plan.
4. Run relevant validation:
- formatting/lint
- typecheck
- unit/integration/e2e tests as applicable
5. Report exact commands run, outcomes, and residual risk.

### Review Routing Contract (Hard Rule)

- Plan artifact review must run via `scripts/plan-review` or `scripts/plan-review-live`.
- PR/code review must run via `codex review --base ...` (or `safe-review.sh` wrapper).
- Do not publish a manual review summary before running the review command/wrapper.

## ACP-First Routing

For harness-style implementation/review requests, ACP routing is mode-specific:

- Implementation uses ACP first (via `acpx`) with CLI fallback.
- Review keeps review-native `codex review --base` first, then ACP fallback.
- CLI fallback chain remains mandatory if ACP is unavailable.
- Disable ACP-first per run with `CODING_AGENT_ACP_ENABLE=0`.
- Override ACPX binary path with `CODING_AGENT_ACPX_CMD`.
- Override ACP agent alias with `CODING_AGENT_ACP_AGENT` (default: `codex`).

## Verbosity Mode (Progress Updates)

`CODING_AGENT_VERBOSE` controls execution progress verbosity. Default is off.

- `off` (default): concise progress updates.
- `on`: include structured progress updates with `Now`, `Why`, and `Next`.

Accepted truthy values (case-insensitive): `1`, `true`, `on`, `yes`, `verbose`.
Accepted falsy values: unset, `0`, `false`, `off`, `no`.

When verbose mode is on:
- Send kickoff execution status in `Now/Why/Next` format.
- For long-running tasks, send periodic status updates.
- Send a completion update with outcome and blockers (if any).

Verbosity must not block execution. After explaining intent, proceed immediately
unless waiting on a required user decision or an explicit approval gate.
Status updates are not a wait state: if the next step is executable, run it in the same turn.

### Long-Run Hard-Fail Policy

For wrapper/CLI runs expected to exceed 30 seconds:
- Emit `RUN_EVENT start`.
- Emit `RUN_EVENT heartbeat` every 20 seconds while running.
- Emit `RUN_EVENT interrupted` immediately on signal/timeout/interruption.
- Emit `RUN_EVENT failed` on non-interruption errors.
- Emit `RUN_EVENT done` on success.
## Guardrails

- No bypass-by-default. Do not use approval-bypass flags unless the user explicitly requests bypass.
- Use feature branches for code changes.
- Keep changes scoped to the approved plan.

## Reference Loading

Open only the references needed for the current task:
- `references/WORKFLOW.md`
- `references/STANDARDS.md`
- `references/tooling.md`
- `references/codex-cli.md`
- `references/claude-code.md`
- `references/reviews.md`
