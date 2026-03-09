# Tooling and Timeouts

## Plan-First Gate

For non-trivial changes:
1. Produce a plan first.
2. Wait for explicit `APPROVE`.
3. Execute implementation commands only after approval.

## Approach Comparison

| Method | Reliability | Output | Best For |
|--------|-------------|--------|----------|
| ACPX (`acpx <agent> exec`) | ⚠️ Medium | Quiet assistant text | ACP harness-first execution and relay flows |
| Direct Codex CLI (`exec` + `resume`) | ✅ High | Text/JSON stream | Most implementation loops and iterative follow-ups |
| tmux transport + Codex CLI | ✅ High | Full TTY + logs | Long-running tasks requiring reattach and terminal durability |
| Claude CLI fallback | ⚠️ Medium | Text stream | When Codex is unavailable |

## Execution Policy Matrix

| Task | Primary | Secondary | Notes |
|------|---------|-----------|-------|
| Plan mode | `scripts/code-plan --engine codex` | `scripts/code-plan --engine claude` | Read-only planning artifact + approval gate |
| Implementation | ACPX (`safe-fallback.sh` ACP-first) | direct/tmux Codex CLI | Use CLI fallback when ACP is unavailable; lower reasoning only for simple/docs or explicit fast/cheap requests |
| PR review | `codex review --base <base>` | ACPX then Claude CLI | Keep timeout >= 600s |
| Long-running implementation | tmux transport | direct `codex -c 'model_reasoning_effort="high"' exec --full-auto` | Use tmux when persistence/reattach is required |

Implementation routing is configurable:

- `CODING_AGENT_IMPL_MODE=direct` -> direct first, tmux second
- `CODING_AGENT_IMPL_MODE=tmux` -> tmux first, direct second
- `CODING_AGENT_IMPL_MODE=auto` -> tmux first only when attached to an interactive TTY and tmux exists

Default behavior: `direct`.

## Direct CLI (Primary)

Agent CLIs support non-interactive execution with session resume and approval-aware modes.

Reasoning defaults for Codex implementation:
- `high` for feature implementation and architectural refactors.
- `medium`/`low` for simple fixes, docs-only work, or explicit fast/cheap requests.

### Codex CLI

| Command | Purpose |
|---------|---------|
| `codex -c 'model_reasoning_effort="high"' exec --full-auto "prompt"` | Guardrailed implementation (feature/refactor default) |
| `codex exec resume --last "follow-up"` | Resume previous context |
| `codex review --base <base>` | Code review against base branch |
| `codex exec --json "prompt"` | Structured event stream for automation |
| `codex exec --output-last-message /tmp/last.txt "prompt"` | Persist final response for wrappers/scripts |

### Claude Code CLI

| Command | Purpose |
|---------|---------|
| `claude -p --permission-mode acceptEdits "prompt"` | Guardrailed implementation fallback |
| `claude -p --model opus "prompt"` | Complex fallback task |
| `claude -p -c "follow up"` | Continue most recent session |
| `claude -p --resume <id> "follow up"` | Resume specific session |
| `claude --resume` | Interactive session picker |

### Approval Modes

| CLI | Flag | Behavior |
|-----|------|----------|
| Codex | `--full-auto` | Lower-friction sandboxed automation |
| Codex | `--dangerously-bypass-approvals-and-sandbox` | Explicit bypass (only by user request) |
| Claude | `--permission-mode acceptEdits` | Auto-accept file edits only |
| Claude | `--permission-mode bypassPermissions` | Explicit bypass (only by user request) |

### Session Management

| CLI | Command | Purpose |
|-----|---------|---------|
| Codex | `codex exec resume --last` | Resume last session |
| Claude | `claude -p -c "prompt"` | Continue most recent conversation |
| Claude | `claude -p --resume <id> "prompt"` | Resume specific session by ID |
| Claude | `claude --resume` | Interactive session picker |

Sessions persist to disk (`~/.codex/sessions/` and `~/.claude/projects/<project>/`) and survive process restarts.

## MCP Clarification

Two MCP modes exist and should not be conflated:

1. `codex mcp ...`
- Adds external MCP tools for Codex to use during a run.

2. `codex mcp-server`
- Exposes Codex itself as an MCP server for another orchestrator.
- Experimental; use behind feature flags/pilots.

## Preflight Checks

Run preflight before wrapper use:

```bash
./scripts/doctor
```

Run CLI drift checks before changing command docs:

```bash
./scripts/doc-drift-check
```

`scripts/doctor` checks:
- `codex`
- `gh`
- `timeout`
- Claude binary resolution in this order: `CODING_AGENT_CLAUDE_BIN` -> `~/.claude/local/claude` -> `claude` in `PATH`
- ACPX discovery in this order: `CODING_AGENT_ACPX_CMD` -> `acpx` in `PATH` (warning-only; CLI fallback remains available)

## Wrapper Scripts (Plan + Implementation)

```bash
# Plan mode wrapper (read-only)
"${CODING_AGENT_DIR:-./}/scripts/code-plan" --engine codex --repo /path/to/repo "Implement feature X"

# Implementation (tmux transport wrapper)
"${CODING_AGENT_DIR:-./}/scripts/code-implement" "Implement feature X in /path/to/repo"

# Execute an approved plan artifact
"${CODING_AGENT_DIR:-./}/scripts/code-implement" --plan /path/to/repo/.ai/plans/<plan>.md
```

For review-first behavior, use direct CLI:

```bash
# Detect base branch: main, master, or trunk (whichever exists)
timeout 600s codex review --base <base> --title "Review PR #N"
```

Validate wrappers locally:

```bash
./scripts/smoke-wrappers.sh
```

## Advanced: tmux Wrapper (Optional)

For durable TTY sessions with logging. Use when you need to monitor long-running tasks or preserve terminal output.

### tmux Conventions (OpenClaw)

- Socket directory: `OPENCLAW_TMUX_SOCKET_DIR` (legacy: `CLAWDBOT_TMUX_SOCKET_DIR`)
- Default socket: `${TMPDIR:-/tmp}/openclaw-tmux-sockets/openclaw.sock`
- Send commands literally: `tmux ... send-keys -l -- "cmd"`
- Always print monitor commands after creating a session

### Direct tmux Usage

```bash
SOCKET_DIR="${OPENCLAW_TMUX_SOCKET_DIR:-${CLAWDBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/openclaw-tmux-sockets}}"
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/openclaw.sock"
SESSION="codex-impl-$(date +%Y%m%d-%H%M%S)"

# Start session and run codex
tmux -S "$SOCKET" new-session -d -s "$SESSION" -n shell
TARGET="$(tmux -S "$SOCKET" list-panes -t "$SESSION" -F "#{session_name}:#{window_index}.#{pane_index}" | head -n 1)"
tmux -S "$SOCKET" send-keys -t "$TARGET" -l -- "codex -c 'model_reasoning_effort=\"high\"' exec --full-auto 'Implement feature X'"
tmux -S "$SOCKET" send-keys -t "$TARGET" Enter

# Monitor
tmux -S "$SOCKET" attach -t "$SESSION"
tmux -S "$SOCKET" capture-pane -p -J -t "$TARGET" -S -200
```

### tmux-run Helper

`scripts/tmux-run` standardizes sockets, logging, and session names. Non-blocking by default unless `--wait` is passed.

```bash
# Run an implementation command in tmux (non-blocking)
CODEX_TMUX_SESSION_PREFIX=codex-impl \
  ./scripts/tmux-run timeout 180s codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature X"

# Run a long implementation in tmux and wait for completion
CODEX_TMUX_SESSION_PREFIX=codex-impl \
  ./scripts/tmux-run --wait timeout 600s codex -c 'model_reasoning_effort="high"' exec --full-auto "Complex multi-file refactor"
```

Logs: `${XDG_STATE_HOME:-$HOME/.local/state}/openclaw/tmux/<session>.log`

Cleanup:
- Kill session: `tmux -S "$SOCKET" kill-session -t "$SESSION"`
- Remove old logs: `find "$LOG_DIR" -type f -mtime +7 -delete`

## Minimum Timeouts

| Task Type | Minimum | Default |
|-----------|---------|---------|
| Code review | 600s | 600s |
| Architectural review | 600s | 600s |
| Single-file implementation | 120s | 180s |
| Multi-file implementation | 300s | 600s |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CODING_AGENT_IMPL_MODE` | Implementation routing policy (`direct|tmux|auto`) | `direct` |
| `CODING_AGENT_ACP_ENABLE` | Enable ACP-first attempt in `safe-fallback.sh` (`0|1`) | `1` |
| `CODING_AGENT_ACP_AGENT` | ACP harness alias for ACPX execution | `codex` |
| `CODING_AGENT_ACPX_CMD` | Explicit ACPX binary path override | unset |
| `CODING_AGENT_VERBOSE` | Execution progress verbosity (`off` by default; truthy: `1|true|on|yes|verbose`) | `off` |
| `CODING_AGENT_CLAUDE_BIN` | Explicit Claude CLI path override | unset |
| `OPENCLAW_TMUX_SOCKET_DIR` | Socket directory (preferred) | `${TMPDIR:-/tmp}/openclaw-tmux-sockets` |
| `CLAWDBOT_TMUX_SOCKET_DIR` | Legacy socket directory | unset |
| `CODEX_TMUX_SOCKET_DIR` | Explicit socket directory override | unset |
| `CODEX_TMUX_SOCKET` | Explicit socket path | `${OPENCLAW_TMUX_SOCKET_DIR}/openclaw.sock` |
| `CODEX_TMUX_SESSION` | Explicit session name | autogenerated |
| `CODEX_TMUX_SESSION_PREFIX` | Session name prefix | `codex` |
| `CODEX_TMUX_LOG_DIR` | Log directory | `${XDG_STATE_HOME:-$HOME/.local/state}/openclaw/tmux` |
| `CODEX_TMUX_WAIT` | Block until command finishes | `0` |
| `CODEX_TMUX_CLEANUP` | Kill session after completion | `0` |
| `CODEX_TMUX_WAIT_TIMEOUT` | Optional wait timeout (seconds) | unset |
| `CODEX_TMUX_DISABLE` | Legacy override: force direct mode | `0` |
| `CODEX_TMUX_REQUIRED` | Legacy override: force tmux mode | `0` |
| `GEMINI_FALLBACK_ENABLE` | Enable Gemini fallback in `safe-fallback.sh` | `0` |
| `CODE_IMPLEMENT_TIMEOUT` | Implement wrapper timeout (ms) | `180000` |
