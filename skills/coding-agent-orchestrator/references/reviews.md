# Reviews and Standards

## Review Workflow

### New Features (Issue → PR)
1. Implement with agent CLI.
2. Create PR.
3. Run Codex review.
4. Run standards review (references/STANDARDS.md) — required.
5. Fix issues, push updates to same branch.

### Existing PRs
1. Checkout PR.
2. Run Codex review locally.
3. Run standards review.
4. Post both reviews to GitHub.
5. Fix issues, push updates.

### Codebase Reviews
1. Run full review (Codex or Claude CLI with long timeout).
2. Classify findings by severity (P0–P3).
3. Create issues with file:line references.

### PR Intake (`/review_pr`)
1. If no PR number/URL is provided, run `gh pr list` and ask user to choose one PR.
2. If a PR number is provided, run `gh pr view <number>` to gather PR metadata.
3. Run `gh pr diff <number>` and review the actual patch before issuing findings.

## Review Focus Checklist (Required)

- Code correctness
- Architecture and dependency boundaries
- Project conventions and style
- Performance implications
- Test coverage quality and gaps
- Security considerations

## Configuration Safety Review (Required When Triggered)

Run a configuration safety section in the review output when the PR touches any of:
- `.env`, `.env.*`
- `*.yml`, `*.yaml`, `*.json`, `*.toml`, `*.ini`, `*.conf`, `*.properties`
- `Dockerfile`, `docker-compose*`
- `.github/workflows/*`
- `config/`, `infra/`, `deploy/`, `k8s/`, `helm/`

Treat numeric/config value changes as risky until justified. For each flagged config change, require:
- Load-test evidence (or explicit "not tested")
- Rollback method and expected rollback time
- Monitoring signals/alerts to detect regressions
- Dependency/limit interaction analysis (upstream/downstream/system caps)
- Historical context (similar prior incidents or "none known")

## Review Output Contract (Required)

- List findings first, ordered by severity (`P0` -> `P3`).
- Include concrete file:line reference for each finding.
- Include open questions/assumptions after findings.
- Include a short PR overview after findings (what changed and why).
- Include specific improvement suggestions and key risks.
- When configuration safety is triggered, include a dedicated `Configuration Safety` subsection with evidence.
- If command/docs examples were changed, label each as:
  - `VERIFIED` (executed) or
  - `UNVERIFIED` (not executed)
- Never imply a command was validated when it was not run.

### Self-Audit Summary Block (Required in final review response)
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

## Issue/PR Authoring Standard (Peter-style)

### PR Titles
- Default: `type(scope): imperative summary`
- Use repo-specific override only when documented (e.g., `Type: Description #issue`)

### Issue Titles
- Feature: `feat: <capability> (for <surface>)`
- Bug: `bug: <symptom> when <condition>`
- Tracking: `TODO: <cleanup> after <dependency>`

### PR Body Sections (required)
1. `What` (3-6 concrete bullets)
2. `Why` (impact/reason)
3. `Tests` (exact commands run)
4. `AI Assistance` (used/not used, testing level, prompt/session log, understanding confirmation)

## Review Commands

```bash
# If PR number is missing, list open PRs first
gh pr list

# Load PR metadata
gh pr view <PR>

# Inspect patch before review output
gh pr diff <PR>

# Optional: list changed file paths to detect config-safety trigger
gh pr view <PR> --json files --jq '.files[].path'

# Code review (direct CLI)
timeout 600s codex review --base <base> --title "PR #N Review"

# Standards review (direct CLI, preferred)
timeout 1200s codex --yolo exec -c model_reasoning_effort="medium" \
  "Review against coding standards in references/STANDARDS.md. Report PASS/FAIL per category with file:line refs."

# Standards review (tmux transport, optional for persistence)
./scripts/tmux-run timeout 1200s codex --yolo exec -c model_reasoning_effort="medium" \
  "Review against coding standards in references/STANDARDS.md. Report PASS/FAIL per category with file:line refs."
```

## Posting Reviews to GitHub

```bash
# Approve
gh pr review <PR> --approve --body "LGTM"

# Request changes
gh pr review <PR> --request-changes --body "Found issues that need fixing"

# Comment only
gh pr review <PR> --comment --body "Suggestions and notes"
```

## Standards Review Output Format

```markdown
## references/STANDARDS.md Standards Review ✅|⚠️|❌

### ✅ PASSED
- Code Quality: Functions under 40 lines

### ⚠️ WARNINGS (P2)
- [file:23] Function has 7 parameters (limit: 4)

### ❌ ISSUES (P1)
- [file:8] Commit uses wrong format

### Assumptions / Open Questions
- Assumption: ...

### Command/Docs Verification
- VERIFIED: `timeout 600s codex review --base main`
- UNVERIFIED: `claude ...`

### Recommendation: APPROVE / REQUEST_CHANGES
```
