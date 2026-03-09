# Setup Guide for AI Agents

This skill is designed for OpenClaw but the orchestration pattern can be adapted to any AI agent platform that supports subagent spawning and async coordination.

## Prerequisites

- **OpenClaw** installed and running (see [openclaw.ai](https://openclaw.ai))
- **GitHub CLI** (`gh`) authenticated: `gh auth login`
- A project with tests and a linter (Python/pytest+ruff, Rust/cargo+clippy, etc.)
- Access to OpenClaw tools: `sessions_spawn`, `cron`, `subagents`, `sessions_history`

---

## Step 1: Install the Skill

Copy `SKILL.md` to your OpenClaw workspace:

```bash
mkdir -p ~/.openclaw/workspace/skills/full-cycle
cp SKILL.md ~/.openclaw/workspace/skills/full-cycle/SKILL.md
```

OpenClaw will auto-discover the skill from the `skills/` directory.

---

## Step 2: Create Role Prompts

Create the prompts directory structure:

```bash
mkdir -p /opt/projects/llm-review-prompts/prompts/{developer,architect,tester,reviewer,security}
```

### developer/python.md (template)

```markdown
# Developer Review — Python

You are a senior Python developer reviewing a pull request diff.

Your job: identify code quality issues that BLOCK merge.

## What to check
- Correctness: logic errors, wrong assumptions
- Error handling: unhandled exceptions, missing validation
- Code style: PEP8 compliance, naming conventions
- DRY: duplicate code that should be extracted
- Edge cases: null/empty inputs, boundary conditions
- Dependencies: unnecessary imports, version constraints

## Scope rule
ONLY check changes in the DIFF provided. Do NOT report on pre-existing code issues.
Pre-existing issues → list with [pre-existing] tag in MINOR section.

## Output format
```
BLOCKING:
- [description] file.py:42 → fix: [specific fix]

MINOR:
- [description] file.py:15

Итого: X blocking, Y minor.
```
```

### architect/python.md (template)

```markdown
# Architect Review — Python

You are a software architect reviewing a pull request diff.

## What to check
- Design decisions: is the approach the right one?
- SOLID principles: SRP, OCP, LSP, ISP, DIP
- Coupling: tight coupling, circular dependencies
- Scalability: will this work at 10x load?
- ROADMAP alignment: does this fit the project direction?

## Scope rule
ONLY check changes in the DIFF.

## Output format
```
BLOCKING:
- [description] file.py:42 → fix: [specific fix]

MINOR:
- [description]

Итого: X blocking, Y minor.
```
```

### tester/autotests.md (template)

```markdown
# Tester Review — Autotests

You are a QA engineer reviewing test coverage for a pull request.

## What to check
- AC coverage: are all acceptance criteria covered by tests?
- Test quality: do tests actually validate the right things?
- Edge cases: negative tests, boundary values, error paths
- Test isolation: no side effects between tests
- Missing tests: which scenarios have zero coverage?

## Severity
- MUST HAVE: missing test for acceptance criteria → BLOCKING
- SHOULD HAVE: missing edge case test → issue
- NICE TO HAVE: additional coverage → suggestion

## Scope rule
ONLY check new/changed tests and untested new code in DIFF.

## Output format
```
MUST HAVE (blocking):
- [test description] covers AC: [which AC]

SHOULD HAVE (issue):
- [test description]

Итого: X must have, Y should have.
```
```

### security/general.md (template)

```markdown
# Security Review

You are a security engineer reviewing a pull request diff.

## What to check
- Injection: SQL, command, path traversal, template injection
- Authentication / Authorization: missing auth checks, privilege escalation
- Secrets: hardcoded credentials, API keys in code
- Input validation: unsanitized user input
- Cryptography: weak algorithms, improper use
- Dependencies: known CVEs in added packages

## Severity
- CRITICAL: remote code execution, auth bypass → BLOCKING
- HIGH: sensitive data exposure, privilege escalation → BLOCKING
- MEDIUM: info disclosure, DoS potential → issue
- LOW: defense-in-depth improvements → ignore for MR

## Scope rule
ONLY check changes in the DIFF. Pre-existing vulnerabilities:
- NOT BLOCKING for this MR
- Note with [pre-existing] tag

## Output format
```
CRITICAL/HIGH (blocking):
- [description] file.py:42 → fix: [specific fix]

MEDIUM (issue):
- [description]

LOW (ignore):
- [description]

Итого: X blocking, Y medium.
```
```

### reviewer/general.md (template)

```markdown
# Final Reviewer

You are the final reviewer aggregating inputs from 4 specialist reviewers.

## Your job
1. Read all 4 reviews (Developer, Architect, Tester, Security)
2. Identify unique BLOCKING findings (deduplicate overlapping ones)
3. Verify scope: are all blocking findings actually in the DIFF?
4. Render final verdict: APPROVE or REQUEST_CHANGES

## Output format
```
## Final Verdict: APPROVE ✅ / REQUEST_CHANGES ⚠️

Total unique BLOCKING: N
- [description] (from Developer/Architect/Tester/Security)

Unique MINOR: M (→ single issue)
```
```

---

## Step 3: Configure for Your Project

Update these values in `SKILL.md` when using it:

| Setting | Value | Where |
|---------|-------|-------|
| Project path | `/opt/projects/<your-project>` | developer/fix subagent tasks |
| Push command | `git push https://<user>:$(gh auth token)@github.com/<org>/<repo>.git <branch>` | fix subagent task |
| Test command | `pytest tests/ -q` | developer/fix subagent tasks |
| Lint command | `ruff check src/ tests/` | developer/fix subagent tasks |
| Prompt stack | `developer/python.md` | Step 4 |

---

## Step 4: Adapting Roles to Your Stack

| Command | Python | Rust | .NET | Go |
|---------|--------|------|------|-----|
| Test | `pytest tests/ -q` | `cargo test -- --quiet` | `dotnet test` | `go test ./...` |
| Lint | `ruff check src/ tests/` | `cargo clippy` | `dotnet format --verify-no-changes` | `golangci-lint run` |
| Developer prompt | `developer/python.md` | `developer/rust.md` | `developer/dotnet.md` | `developer/go.md` |

---

## Step 5: Trigger

In OpenClaw chat:

```
full cycle для <project> <task description>
```

Examples:
```
full cycle для my-api implement rate limiting
full cycle для my-service fix authentication bug (#23)
full cycle для my-app add export to CSV feature
```

---

## How the Anti-Freeze Cron Works

The main session may "freeze" after spawning subagents — completion events aren't guaranteed to resume it. The cron pattern provides insurance:

```
1. Main session spawns 4 review subagents
2. Immediately schedules 2 crons:
   cron_1 at T + 23min (primary)
   cron_2 at T + 26min (backup)
3. Crons fire and check if subagents are still running:
   - All done → aggregate results → proceed
   - Still running → reschedule cron to now+5min
4. Eventually subagents finish → pipeline continues
```

See [cron-anti-freeze.md](cron-anti-freeze.md) for full details and code examples.

---

## Minimal Viable Setup

If you want the simplest version without 4 roles:

```
1. Developer subagent: write code + tests + lint
2. Single reviewer subagent: general code review
3. Cron for anti-freeze
4. Fix if blocking > 0
5. Create PR
```

Role prompt for single reviewer:
```markdown
Review this diff as a senior developer. 
Check: correctness, security basics, test coverage, code quality.
Scope: ONLY changes in DIFF.
Output: BLOCKING (must fix) / MINOR (create issue) / APPROVE.
```

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Subagent froze | async timeout | cron will trigger at T+N, reschedule if needed |
| Tests red | implementation error | dev subagent won't commit, reports error |
| Max rounds exceeded | complex blocking issue | report to user with blocking list, manual fix |
| False alarm BLOCKING | reviewer analyzed diff without context | verify in real code before spawning fix-subagent |
| Cron not triggering | misconfigured schedule | check cron list, manually trigger session |
| Push fails | auth token expired | `gh auth refresh` then re-trigger |
| Lint errors after fix | fix introduced new issues | fix-subagent must run lint after every change |
