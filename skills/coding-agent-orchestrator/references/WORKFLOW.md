# Coding Workflow & Operations

## Contents
- Overview
- Git Workflow
- Hard Requirements (Violation = Task Failure)
- Self-Audit Protocol
- GitHub CLI (gh)
- Agent Workflow
- Multi-Phase Workflow (Session Resume)
- Agent CLI Reference
- Agent Utilization

## Overview

**Roles:**
- **@kesslerIO (Martin)**: Human Owner. Approves P0/P1 changes.
- **@niemandBot (Niemand)**: AI Agent. Reviews code, runs checks, implements features.

**Philosophy:**
- **Plan First**: Always discuss approach before implementation.
- **Approval Gate**: For non-trivial changes, wait for explicit `APPROVE` before writing files.
- **Surface Decisions**: Present options with trade-offs.
- **Confirm Alignment**: Ensure agreement before coding.
- **No Direct Edits**: Use agent CLIs (Codex/Claude) to write code.

### Channel Alias Notes

Some channels expose aliases (`/coding`, `/plan`, `/plan-review`, `/plan-review-live`, `/review_pr`).
These aliases do not change core policy:
- Plan-first for non-trivial work
- Explicit approval gate before writes
- No bypass-by-default flags unless the user explicitly requests bypass.
- Plan completion is approved through explicit `APPROVE` reply (there is no separate `ExitPlanMode` tool call in this repo flow).

### Review Routing + Run Status (Hard Rules)

- Plan artifact reviews must use wrappers first: `scripts/plan-review` or `scripts/plan-review-live`.
- PR/code reviews must use `codex review --base ...` (or `safe-review.sh` wrapper).
- Do not send manual review findings before the matching review command executes.
- For runs >30 seconds, emit wrapper status updates every 20 seconds.
- On interruption/timeout/signal, emit immediate interruption status with exit code and remediation command.

## Git Workflow

**Note:** Niemand does NOT create branches, commit code, or merge PRs unless explicitly requested.

### Standard Flow
1. **Create Branch**: `git checkout -b type/description`
2. **Implement**: Use agent CLI (see below)
3. **Commit**: `git commit -m "type(scope): description"`
4. **Push**: `git push -u origin branch-name`
5. **PR**: `gh pr create`
6. **Review**: Run code review (see below)
7. **Fix**: Address issues (resume session for context)
8. **Merge**: `gh pr merge`

### Commit Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting (no code change)
- `refactor`: Restructuring code (no API change)
- `test`: Adding tests
- `chore`: Build/tooling changes

## Hard Requirements (Violation = Task Failure)

These are non-negotiable requirements. Violating any of these means the task has FAILED.

### 1. Branch Requirement
- **MUST** create feature branch before any code changes
- **MUST NOT** commit directly to main
- **Violation Response**: Stop and ask user to confirm branch creation

### 2. PR Requirement
- **MUST** create PR before code can be considered "done"
- **MUST** post review to PR before merge
- **MUST** include PR URL in task completion message
- **Violation Response**: Refuse to mark task complete without PR URL

### 3. Tool Usage Requirement
- When user specifies "use claude/codex/gemini": **MUST** use that CLI tool when available/configured
- **MUST** use agent CLI (direct or tmux wrappers) — not direct file edits
- For reviews: use direct `codex review --base <base>` or `claude -p`
- For implementation: prefer direct CLI (`codex -c 'model_reasoning_effort="high"' exec --full-auto`) or `scripts/code-implement`
- When using `scripts/safe-fallback.sh`, wrappers attempt ACP first (`acpx`) and then use CLI fallback chain.
- Default reasoning policy: use `high` for feature implementation and architectural refactors; use `medium`/`low` only for simple fixes/docs or explicit fast/cheap requests
- **MUST NOT** use direct file edits when agent CLI is specified
- **MUST** document which tool was used in PR description
- **Violation Response**: Stop and switch to specified tool

### 4. Review Requirement
- **MUST** run code review before merge
- **MUST** run standards review (references/STANDARDS.md) before merge
- **MUST** post both reviews to GitHub PR
- **Violation Response**: Block merge until reviews are posted

### 5. Self-Audit Requirement
- **MUST** run self-audit before reporting completion when code/config/docs commands were changed
- **MUST** use findings-first format with severity order and file:line references for review tasks
- **MUST** verify changed command examples or explicitly mark them unverified
- **Violation Response**: Do not mark complete; run audit and report gaps

### Self-Check Before Completion
Before reporting task complete, verify:
- [ ] Changes on feature branch (not main)?
- [ ] PR created and URL available?
- [ ] Correct tools used (agent CLI, direct or tmux)?
- [ ] Code review completed and posted?
- [ ] Standards review completed and posted?
- [ ] User-facing long-form text passed through `/humanizer` (or explicit fallback noted)?
- [ ] Self-audit completed (or explicit skip reason documented)?

## Self-Audit Protocol

Run this before final response unless skip conditions apply.

### When Required
- Code/config changed.
- Tests changed or should have changed.
- Review requested by user.
- Docs changed with executable commands/examples.

### Skip Conditions
- Informational response only, no repo changes.
- User requested raw command output only.

If skipped, explicitly state why.

### Phase 1: Implementation Audit
- [ ] Requirement coverage checked against user request.
- [ ] Edge cases and failure paths reviewed.
- [ ] Tests added/updated or explicit rationale for none.
- [ ] Risky assumptions called out.

### Phase 2: Review Audit
- [ ] Findings ordered by severity (P0-P3).
- [ ] Every finding includes file:line reference.
- [ ] Regressions/unintended side effects checked.
- [ ] Changed docs commands/examples verified; if not run, mark `UNVERIFIED`.

### Final Response Contract

Use this block in completion messages:

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

## GitHub CLI (gh)

### Authentication
- **Check status**: `gh auth status`
- **Login**: `gh auth login` (uses PAT or browser)
- **Switch account**: `gh auth switch --user <username>`

### Common Commands
- **Create PR**: `gh pr create --title "feat: ..." --body "..."`
- **View PR**: `gh pr view <number>`
- **Checkout PR**: `gh pr checkout <number>`
- **Review PR**: `gh pr review <number> --approve`
- **Merge PR**: `gh pr merge <number> --admin --merge --delete-branch`

### Issue/PR Hygiene (Required)
- Keep one logical change per PR.
- Search before opening issues: `gh issue list --search "<keywords>"`.
- PR title default: `type(scope): imperative summary` (unless repo override).
- Issue title defaults:
  - Feature: `feat: <capability> (for <surface>)`
  - Bug: `bug: <symptom> when <condition>`
  - Tracking: `TODO: <cleanup> after <dependency>`
- PR body sections (required): `What`, `Why`, `Tests`, `AI Assistance`.
- `Tests`: list exact commands run.
- `AI Assistance`: used/not used, testing level, prompt/session log link, and "I understand this code."

## Agent Workflow

### Primary: Direct CLI

Use agent CLIs directly for most tasks. Session resume preserves full context across phases and is preferred over spawning sub-agents for routine implementation.

```bash
# Implementation (Codex)
codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature X according to approved plan."

# Implementation (Claude)
claude -p --permission-mode acceptEdits "Implement feature X"

# Review (Codex)
codex review --base <base> --title "PR Review"

# Review (Claude)
claude -p --model opus "Review changes vs main branch for bugs, security, quality"
```

### Secondary: tmux Wrappers

For durable implementation sessions with logging and monitoring:

```bash
# Implementation (tmux)
./scripts/code-implement "Implement feature X in /path/to/repo"
```

### Plan Mode Wrapper

For non-trivial work, generate a plan artifact before implementation:

```bash
./scripts/plan --engine codex --repo /path/to/repo "Implement feature X"
./scripts/plan-review --repo /path/to/repo
./scripts/plan-review-live --repo /path/to/repo
# Force legacy engine (bypass Lobster workflow path)
./scripts/plan-review-live --engine legacy --repo /path/to/repo
# Non-TTY/chat-safe finalization:
./scripts/plan-review-live --repo /path/to/repo --decisions "1A,2B,3A,4A" --blocking none
# Or:
./scripts/plan-review-live --repo /path/to/repo --resolve-file /path/to/decisions.json
./scripts/code-implement --plan /path/to/repo/.ai/plans/<plan>.md
```

`code-implement --plan` now enforces the latest per-plan review metadata gate. `plan-review-live`
uses the in-repo Lobster workflow by default and falls back to the legacy live-review engine when
Lobster is unavailable. Use `plan-review-live` to resolve blocking decisions before execution, or
`--force` to bypass explicitly.

### Code Review Process

**Hierarchy:**
1. **Codex**: Primary reviewer (`codex review --base <base>`).
2. **ACPX**: Review fallback path through harness routing.
3. **Claude**: Secondary CLI fallback if Codex is unavailable.
4. **Gemini (optional)**: Only if explicitly enabled (`GEMINI_FALLBACK_ENABLE=1`).
5. **Sub-agent**: Last resort for orchestration.

**Step 1: Code Review (Logic/Bugs)**
```bash
gh pr checkout <PR>
timeout 600s codex review --base <base> --title "PR #N Review"
```

**Step 2: Standards Review (Required)**
```bash
codex exec --full-auto --model gpt-5.3-codex \
  -c model_reasoning_effort="medium" "Review against STANDARDS.md..."
```

**Step 3: Posting Results**
```bash
gh pr review <PR> --comment --body "$(cat review.md)"
```

## Multi-Phase Workflow (Session Resume)

For complex tasks spanning multiple phases, use session resume to preserve full context:

### Issue → Implement → PR → Review → Fix → Merge

```bash
# Phase 1: Implement from issue
codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature described in issue #42 according to approved plan."

# Phase 2: Create PR
gh pr create --title "feat(auth): add JWT validation" --body "..."

# Phase 3: Review
timeout 600s codex review --base <base> --title "Review PR #N"

# Phase 4: Fix review findings (resume preserves context)
codex exec resume --last
# Or with Claude:
claude -p --resume <session-id> "Fix the review findings"

# Phase 5: Re-review after fixes
timeout 600s codex review --base <base> --title "Re-review PR #N"

# Phase 6: Merge
gh pr merge --merge --delete-branch
```

### Session Resume Commands

| Phase | Codex | Claude Code |
|-------|-------|-------------|
| Resume last | `codex exec resume --last` | `claude -p -c "prompt"` |
| Resume specific | `codex exec resume <id>` | `claude -p --resume <id> "prompt"` |
| List/pick session | — | `claude --resume` (interactive picker) |

Codex resume compatibility note:
- Preferred: `codex exec resume --last` or `codex exec resume <id>`.
- If your installed Codex build does not support `resume`, start a fresh run and reference the prior issue/PR context explicitly.

### When to Resume vs Start Fresh

- **Resume**: Fix review findings, continue implementation, follow-up on same codebase
- **Fresh**: New issue, different repo, unrelated task

### Base Branch Detection (`<base>`)

Use this order:

```bash
# Primary
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'

# Fallback (when origin/HEAD is unset)
git remote show origin | sed -n '/HEAD branch/s/.*: //p'
```

### Prompt Engineering Best Practices
- **Be Specific**: "Implement X using Y library" vs "Add X".
- **Use Explicit Gate**: "Plan first; execute only after I reply APPROVE."
- **Small Batches**: Don't change 50 files at once.
- **Clear Exit**: "Reply with DONE when finished."

## Agent CLI Reference

### Codex CLI

For automated runs after approval:

```bash
# Implementation (post-approval)
codex -c 'model_reasoning_effort="high"' exec --full-auto "Implement feature X based on approved plan."

# Simple fix/docs or explicit fast/cheap request
codex -c 'model_reasoning_effort="medium"' exec --full-auto "Fix typo in one file"
codex -c 'model_reasoning_effort="low"' exec --full-auto "Update README command example quickly"

# Resume last session
codex exec resume --last
```

### Claude Code CLI

```bash
# Implementation (post-approval)
claude -p --permission-mode acceptEdits "Implement feature X"

# With model selection
claude -p --model opus --permission-mode acceptEdits "Complex task"

# Resume/continue
claude -p -c "Follow up on the previous task"
claude -p --resume <session-id> "Continue from here"
```

See `references/claude-code.md` for full Claude Code reference.
See `references/codex-cli.md` for canonical Codex execution policy (`exec`, `resume`, MCP distinctions).
See `references/tooling.md` for tmux wrappers, timeouts, and environment variables.

## Agent Utilization

Delegate specific tasks to focused agents only when decomposition is clear and parallelizable:

- **requirements-specialist**: Specs → GitHub Issues
- **implementation-architect**: API/UI Design
- **quality-assurance-specialist**: Tests, Security, Perf
- **docs-architect**: Documentation updates

**Trigger**: Use sub-agents for independent tracks (for example: separate security/performance/test review streams). Keep single-agent `codex exec` + `codex exec resume` as the default path for implementation loops.

Sub-agent note:
- Codex multi-agent workflows are experimental.
- Non-interactive approval handling can fail if sub-agents request escalation unexpectedly.
