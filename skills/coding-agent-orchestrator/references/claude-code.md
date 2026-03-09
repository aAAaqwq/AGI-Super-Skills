# Claude Code CLI Reference

Detailed reference for Claude Code as a fallback when Codex is unavailable, or as primary CLI for Claude-based workflows.

## Plan-First Gate

For non-trivial tasks:
1. Plan first.
2. Wait for explicit `APPROVE`.
3. Execute with Claude commands after approval.

## Contents
- Non-interactive mode flags
- Session resume (non-interactive)
- Model selection
- Permission modes
- Budget controls
- Output formats
- Examples
- Codex → Claude mapping

---

## Non-Interactive Mode (-p/--print)

The `-p` flag runs Claude in non-interactive mode: it processes the prompt and exits.

```bash
claude -p "Your prompt here"
```

**Note:** The `-p` flag skips workspace trust dialogs. Only use in trusted directories.

---

## Flags Reference

| Flag | Description |
|------|-------------|
| `-p, --print` | Non-interactive mode, print and exit |
| `--model <model>` | Model: `sonnet`, `opus`, `haiku`, or full name |
| `--permission-mode <mode>` | Permission handling (see below) |
| `--dangerously-skip-permissions` | Skip all permission checks |
| `--max-budget-usd <amount>` | Cap API spending |
| `--fallback-model <model>` | Auto-fallback if primary overloaded |
| `--output-format <format>` | Output: `text`, `json`, `stream-json` |
| `--add-dir <dirs>` | Additional directories to allow access |
| `-c, --continue` | Continue most recent conversation |
| `-r, --resume <id>` | Resume specific session |
| `--resume` | Interactive session picker (no ID = browse) |

---

## Session Resume (Non-Interactive)

Session resume restores full conversation context from disk. Use this for multi-phase workflows where context must persist across separate CLI invocations.

### Continue Most Recent Session

```bash
# Continue the last conversation with a new prompt
claude -p -c "Fix the review findings from the previous session"

# Continue without a new prompt (re-runs last context)
claude -p -c
```

### Resume Specific Session

```bash
# Browse sessions interactively to find the ID
claude --resume

# Resume a specific session by ID
claude -p --resume abc123 "Address the security concern raised in review"
```

### Session Storage

Sessions persist to `~/.claude/projects/<project>/sessions/`. Each session contains the full conversation history, tool calls, and file context.

### When to Use Resume

| Scenario | Command |
|----------|---------|
| Fix review findings | `claude -p -c "Fix the issues from code review"` |
| Continue implementation | `claude -p --resume <id> "Continue implementing the auth module"` |
| Follow-up on same PR | `claude -p -c "Now add tests for the changes"` |
| Unrelated new task | `claude -p "New task prompt"` (fresh session) |

### Multi-Phase Example

```bash
# Phase 1: Implement
claude -p --permission-mode acceptEdits "Implement JWT auth middleware"

# Phase 2: Fix review findings (context preserved)
claude -p -c --permission-mode acceptEdits "Fix the review findings: add token expiry check"

# Phase 3: Add tests (context preserved)
claude -p -c --permission-mode acceptEdits "Add unit tests for the JWT middleware"
```

---

## Permission Modes

| Mode | Behavior |
|------|----------|
| `default` | Prompt for approval (interactive) |
| `acceptEdits` | Auto-accept file edits |
| `bypassPermissions` | Skip all permission checks |
| `dontAsk` | Don't ask, but still enforce permissions |
| `plan` | Planning mode only |

```bash
# Auto-accept edits (recommended for automation)
claude -p --permission-mode acceptEdits "Fix the bug"

# Explicit bypass (only when user asks to bypass approvals)
claude -p --permission-mode bypassPermissions "Build the feature"
```

---

## Model Selection

```bash
# Use Opus for complex tasks
claude -p --model opus "Design the database schema"

# Use Haiku for quick/cheap tasks
claude -p --model haiku "Add a docstring"

# Use Sonnet (default, balanced)
claude -p --model sonnet "Refactor this function"

# With fallback
claude -p --model opus --fallback-model sonnet "Complex task"
```

**Models:**
- `opus` - Most capable, highest cost
- `sonnet` - Balanced (default)
- `haiku` - Fastest, lowest cost

---

## Budget Controls

```bash
# Cap spending at $5
claude -p --max-budget-usd 5 "Build a REST API"

# Combine with fallback for cost optimization
claude -p --model opus --fallback-model haiku --max-budget-usd 2 "Review this code"
```

---

## Output Formats

```bash
# Plain text (default)
claude -p "Summarize this file"

# JSON (single result)
claude -p --output-format json "List the functions in this file"

# Streaming JSON (for real-time processing)
claude -p --output-format stream-json "Analyze this codebase"
```

---

## Working Directory

```bash
# Add specific directories for file access
claude -p --add-dir ~/project --add-dir ~/shared "Refactor across both directories"
```

---

## Session Management

```bash
# Continue last conversation
claude -p -c "Follow up on the previous task"

# Resume specific session
claude -p -r session-id "Continue from here"

# Browse/pick sessions interactively
claude --resume
```

---

## Examples

### Quick Code Fix
```bash
claude -p --permission-mode acceptEdits "Fix the null pointer exception in src/api.ts"
```

### Full Auto Build
```bash
claude -p --permission-mode acceptEdits "Build a REST API with CRUD endpoints for users"
```

### Code Review with Budget
```bash
claude -p --model opus --max-budget-usd 1 "Review this PR for security issues"
```

### Multi-Phase Implementation
```bash
# Phase 1: Implement
claude -p --permission-mode acceptEdits "Implement the user registration endpoint"

# Phase 2: Fix issues (resume context)
claude -p -c --permission-mode acceptEdits "Fix the validation error in registration"

# Phase 3: Add tests
claude -p -c --permission-mode acceptEdits "Add integration tests for registration"
```

---

## Codex → Claude Mapping

| Codex | Claude |
|-------|--------|
| `codex exec "prompt"` | `claude -p "prompt"` |
| `codex exec --full-auto "prompt"` | `claude -p --permission-mode acceptEdits "prompt"` |
| `codex exec --dangerously-bypass-approvals-and-sandbox "prompt"` | `claude -p --permission-mode bypassPermissions "prompt"` |
| `codex review --base <base>` | `claude -p "Review changes vs <base> branch"` |
| `codex exec resume --last` | `claude -p -c "prompt"` |
| `codex exec resume <id>` | `claude -p --resume <id> "prompt"` |
