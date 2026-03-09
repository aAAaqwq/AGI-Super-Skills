# coding-agent Reference

## Contents
- Plan-First Execution Gate
- STOP-AND-VERIFY (Before ANY Implementation)
- Self-Audit Triggers (Option A)
- Forbidden Flags & Minimum Timeouts
- Tool Fallback Chain
- Direct CLI Commands (Primary)
- Plan Mode Commands
- Wrapper Scripts (Secondary)
- Preflight Checks
- Pre-Completion Checklist
- Quick Reference
- Command Reference
- Code Quality Standards
- Issue Priority (P0-P3)
- tmux for Interactive Sessions (Optional)

## Plan-First Execution Gate

For non-trivial requests:
1. Run planning flow first.
2. Wait for explicit `APPROVE`.
3. Execute implementation only after approval.

## STOP-AND-VERIFY (Before ANY Implementation)

**Say this out loud before writing/changing any code:**
```
STOP. Before I proceed, let me verify:
□ Am I using an agent CLI (Codex/Claude)? (not Edit/Write tools)
□ Am I on a feature branch? (not main)
□ Will I create a PR before completing this task?
□ Am I using adequate timeout? (minimum: 600s for reviews)
□ Am I avoiding --max-turns? (let it complete naturally)
```
**If any box is unchecked → STOP and fix before proceeding.**

## Self-Audit Triggers (Option A)

Run self-audit before final response when:
- code/config changed,
- tests changed (or should have changed),
- review requested,
- docs commands/examples changed.

Skip only when:
- informational response with zero repo changes, or
- user asks for raw output only.

## Forbidden Flags & Minimum Timeouts

```
❌ FORBIDDEN: --max-turns (any value)
❌ FORBIDDEN: timeout < 600s for reviews

✅ Reviews: TIMEOUT=600 minimum
✅ Architecture: TIMEOUT=600 minimum
```

## Review Routing + Run Events (Hard Rules)

- Plan artifact review: `./scripts/plan-review` or `./scripts/plan-review-live`
- PR/code review: `timeout 600s codex review --base <base> --title "PR #N Review"` or `safe-review.sh`
- Never produce manual review output before running the matching command.
- Required wrapper events:
  - `RUN_EVENT start`
  - `RUN_EVENT heartbeat` every 20s after 30s elapsed
  - `RUN_EVENT interrupted` or `RUN_EVENT failed`
  - `RUN_EVENT done`

## Tool Fallback Chain

```
Implementation: ACPX → Codex CLI (direct) → Codex CLI (tmux) → Claude CLI → BLOCKED
Reviews:        Codex CLI (direct) → ACPX → Claude CLI → BLOCKED

⛔ NEVER skip to direct edits — request user override instead
```

Implementation mode routing:
- `CODING_AGENT_IMPL_MODE=direct|tmux|auto` (default: `direct`)
- `auto` -> tmux-first only in interactive TTY + tmux available; otherwise direct-first
- ACP-first toggle: `CODING_AGENT_ACP_ENABLE=1|0` (default: `1`)
- ACPX binary override: `CODING_AGENT_ACPX_CMD=/path/to/acpx`

## Direct CLI Commands (Primary)

### Codex

```bash
# Implementation default (feature work / architectural refactor)
codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature X based on approved plan."

# Simple fix/docs or explicit fast/cheap request
codex -c 'model_reasoning_effort="medium"' exec --full-auto "Fix typo in one file"
codex -c 'model_reasoning_effort="low"' exec --full-auto "Update README command example quickly"

# Resume last session (context preserved)
codex exec resume --last
```

### Claude Code

```bash
# Implementation (post-approval)
claude -p --permission-mode acceptEdits "Implement feature X"

# Complex task with Opus
claude -p --model opus --permission-mode acceptEdits "Complex refactor..."

# Continue most recent session
claude -p -c "Fix the review findings"

# Resume specific session
claude -p --resume <session-id> "Continue implementation"

# List sessions
claude --resume
```

## Plan Mode Commands

```bash
# Generate read-only plan (Codex)
./scripts/plan --engine codex --repo /path/to/repo --base main "Implement feature X"

# Generate strict plan mode output (Claude)
./scripts/plan --engine claude --model sonnet --repo /path/to/repo "Implement feature X"

# Review latest plan with Codex read-only mode (or pass --plan)
./scripts/plan-review --repo /path/to/repo

# Interactive section-by-section review with decision checkpoints
./scripts/plan-review-live --repo /path/to/repo

# Force legacy live-review engine
./scripts/plan-review-live --engine legacy --repo /path/to/repo

# Non-TTY/chat-safe finalization (no interactive prompts)
./scripts/plan-review-live --repo /path/to/repo --decisions "1A,2B,3A,4A" --blocking none

# Resolve from machine-readable file
./scripts/plan-review-live --repo /path/to/repo --resolve-file /path/to/decisions.json

# Resume a paused Lobster run
./scripts/plan-review-live --resume-token <token> --output /path/to/repo/.ai/plan-reviews/<same-file>.md

# Execute approved plan (prompts for approval if still PENDING)
# Requires latest plan-review metadata to be ready unless --force is used.
./scripts/code-implement --plan /path/to/repo/.ai/plans/<plan>.md
```

## Wrapper Scripts (Secondary)

```bash
# Implementation (3 min timeout, tmux)
./scripts/code-implement "Implement feature X"

# Enforcement wrappers
TIMEOUT=600 ./scripts/safe-review.sh codex review --base <base> --title "PR Review"
TIMEOUT=180 ./scripts/safe-impl.sh codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature X"
```

## Preflight Checks

```bash
# Verify local prerequisites and Claude binary resolution
./scripts/doctor

# Verify Codex command/flag drift before editing command docs
./scripts/doc-drift-check

# Validate wrapper behavior
./scripts/smoke-wrappers.sh
```

Claude is resolved in this order: `CODING_AGENT_CLAUDE_BIN` → `~/.claude/local/claude` → `claude` in `PATH`.

## Pre-Completion Checklist

Before marking ANY task complete:
- [ ] On feature branch? (not main)
- [ ] PR created with URL?
- [ ] Used agent CLI (direct or tmux)? (not direct edits)
- [ ] Code review posted to PR?
- [ ] Standards review posted to PR?
- [ ] Implementation audit completed?
- [ ] Review audit completed?
- [ ] User-facing long-form text passed through `/humanizer` (or fallback explicitly noted)?
- [ ] PR body includes `What`, `Why`, `Tests`, `AI Assistance`?
- [ ] Issue/PR title follows repo conventions?

**Unchecked box = Task NOT complete.**

---

## Quick Reference

### Activate
Use `/coding` in OpenClaw to activate this skill.
For plan-first flow, use `/plan <task>` (maps to `scripts/plan`), `/plan-review` (batch), and `/plan-review-live` (Lobster workflow by default with legacy fallback; pass `--decisions/--blocking` or `--resolve-file` in non-TTY chat flows).

### Agent CLI Commands

**Codex — guarded implementation:**
```bash
codex -c 'model_reasoning_effort="high"' exec --full-auto "Your approved task."
```

**Codex — resume session:**
```bash
codex exec resume --last
```

**Claude Code — guarded implementation:**
```bash
claude -p --permission-mode acceptEdits "Your task"
```

**Claude Code — resume session:**
```bash
claude -p -c "Follow up prompt"
```

**PR Review (direct CLI):**
```bash
cd /path/to/repo
timeout 600s codex review --base <base> --title "Review PR #N"
```

**PR Review config-safety trigger check:**
```bash
gh pr view <PR> --json files --jq '.files[].path'
```

### Git Workflow
```bash
# If no PR arg was provided, list and select one PR first
gh pr list --repo owner/repo

# Checkout and review
gh pr checkout <PR> --repo owner/repo
gh pr view <PR> --repo owner/repo
gh pr diff <PR> --repo owner/repo
timeout 600s codex review --base <base> --title "Review PR #<PR>"

# Merge (Martin only)
gh pr merge <PR> --repo owner/repo --admin --merge
```

### Issue/PR Title Patterns
```text
PR:    type(scope): imperative summary
Issue: feat: <capability> (for <surface>)
Issue: bug: <symptom> when <condition>
Issue: TODO: <cleanup> after <dependency>
```

### PR Body Skeleton
```markdown
## What
- ...

## Why
- ...

## Tests
- `command 1`
- `command 2`

## AI Assistance
- AI-assisted: yes/no
- Testing level: untested/lightly tested/fully tested
- Prompt/session log: <link or note>
- I understand this code: yes
```

### Self-Audit Response Skeleton
```markdown
## Self-Audit Summary
- Audit status: complete | skipped (reason)
- Tests run:
  - `command ...`
- Residual risks:
  - ...
- Assumptions:
  - ...
- Command/docs verification:
  - VERIFIED: ...
  - UNVERIFIED: ...
```

Definitions:
- `VERIFIED`: command/example was executed in this session.
- `UNVERIFIED`: command/example was not executed in this session.

### Configuration Safety Checklist (`/review_pr`)

Trigger when changed files include:
- `.env`, `.env.*`
- `*.yml`, `*.yaml`, `*.json`, `*.toml`, `*.ini`, `*.conf`, `*.properties`
- `Dockerfile`, `docker-compose*`
- `.github/workflows/*`
- `config/`, `infra/`, `deploy/`, `k8s/`, `helm/`

For each flagged config change, include:
- Load-test evidence (or explicit "not tested")
- Rollback method + expected rollback time
- Monitoring signals/alerts
- Dependency/limit interactions
- Historical context (incidents or none known)

## Command Reference

| Task | Command |
|------|---------|
| List PRs | `gh pr list --repo owner/repo` |
| View PR | `gh pr view <PR> --json number,title,state` |
| List PR files | `gh pr view <PR> --json files --jq '.files[].path'` |
| Diff PR | `gh pr diff <PR> --repo owner/repo` |
| Checkout PR | `gh pr checkout <PR>` |
| Review PR | `timeout 600s codex review --base <base> --title "PR #N Review"` |
| Preflight wrappers | `./scripts/doctor` |
| Codex doc drift check | `./scripts/doc-drift-check` |
| Wrapper smoke tests | `./scripts/smoke-wrappers.sh` |
| Check CI | `gh pr checks <PR> --repo owner/repo` |
| Merge PR | `gh pr merge <PR> --repo owner/repo --admin --merge` |
| Resume Codex | `codex exec resume --last` |
| Resume Claude | `claude -p -c "prompt"` |
| Pick Claude session | `claude --resume` (interactive) |

## Code Quality Standards

- Functions: max 30-40 lines
- Classes: max 500 lines
- Files: max 500 lines
- KISS, YAGNI, DRY, SRP principles

## Issue Priority (P0-P3)

- **P0**: Critical (security, data loss)
- **P1**: High (major feature broken)
- **P2**: Medium (minor features)
- **P3**: Low (nice-to-have)

## tmux for Interactive Sessions (Optional)

For durable TTY sessions with logging. See `references/tooling.md` for full tmux documentation.

```bash
SOCKET_DIR="${OPENCLAW_TMUX_SOCKET_DIR:-${CLAWDBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/openclaw-tmux-sockets}}"
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/openclaw.sock"
SESSION=codex-impl

tmux -S "$SOCKET" new-session -d -s "$SESSION" -n shell
TARGET="$(tmux -S "$SOCKET" list-panes -t "$SESSION" -F "#{session_name}:#{window_index}.#{pane_index}" | head -n 1)"
tmux -S "$SOCKET" send-keys -t "$TARGET" -l -- "codex exec --full-auto 'Implement feature X'"
tmux -S "$SOCKET" send-keys -t "$TARGET" Enter

# Monitor
tmux -S "$SOCKET" attach -t "$SESSION"
tmux -S "$SOCKET" capture-pane -p -J -t "$TARGET" -S -200

# Cleanup
tmux -S "$SOCKET" kill-session -t "$SESSION"
```
