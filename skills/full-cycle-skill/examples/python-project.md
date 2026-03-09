# Example: Python Project (gitlab-reviewer)

Real-world example from the `gitlab-reviewer` project — a FastAPI service that reviews GitLab MRs using LLMs.

## Project Context

- **Stack:** Python 3.12, FastAPI, pytest, ruff
- **Task:** Fix ruff lint errors (issue #11)
- **Branch:** `fix/ruff-lint-11`

---

## Developer Subagent — Full Task Prompt

```
## DEVELOPER SUBAGENT — gitlab-reviewer fix ruff lint (#11)

INIT:
- cd /opt/projects/gitlab-reviewer
- git fetch origin && git pull origin main
- git checkout -b fix/ruff-lint-11
- Read AGENTS.md to understand project structure
- Read src/ directory structure

TASK_CONTEXT:
Issue #11: ruff check finds 47 lint errors across src/ and tests/.
Main categories: E501 (line too long), F401 (unused imports), 
E711 (comparison to None), B007 (unused loop variable).

DEVELOP:
- Run: python3 -m ruff check src/ tests/ 2>&1 | head -60
- Fix each category systematically:
  * F401: remove unused imports
  * E501: wrap long lines (max 88 chars)
  * E711: use `is None` / `is not None`
  * B007: rename unused loop vars to `_`
- Do NOT change logic, only lint fixes

TEST:
- python3 -m pytest tests/ -q 2>&1 | tail -20
- All tests must pass after lint fixes
- If any test breaks — investigate and fix without changing behavior

LINT (verify):
- python3 -m ruff check src/ tests/ 2>&1
- Must return: "All checks passed."

DOCS:
- Update AGENTS.md: Status section → mark #11 as fixed
- Add to Pitfalls: "E501 lines were wrapped but logic unchanged"

git add -A
git commit -m "fix: resolve 47 ruff lint errors (issue #11)"
git push https://KoshelevDV:$(gh auth token)@github.com/KoshelevDV/gitlab-reviewer.git fix/ruff-lint-11

Output:
BRANCH: fix/ruff-lint-11
STACK: python
TESTS: 23 passed
LINT: ruff clean
DOCS: AGENTS.md updated
DIFF_SUMMARY: Fixed 47 ruff errors: removed 12 unused imports, wrapped 28 long lines, fixed 5 None comparisons, renamed 2 unused loop vars
```

---

## Security Review Subagent — Full Task Prompt

```
## SECURITY REVIEW

You are a security engineer reviewing a pull request diff.

### What to check
- Injection: SQL, command, path traversal, template injection
- Authentication / Authorization: missing auth checks, privilege escalation
- Secrets: hardcoded credentials, API keys in code
- Input validation: unsanitized user input
- Cryptography: weak algorithms, improper use

### Severity
- CRITICAL: remote code execution, auth bypass → BLOCKING
- HIGH: sensitive data exposure → BLOCKING
- MEDIUM: info disclosure, DoS potential → issue
- LOW: defense-in-depth → ignore for MR

### Scope rule
ONLY check changes in DIFF. Pre-existing issues → [pre-existing] in MINOR.

---

PROJECT_CONTEXT:
# AGENTS.md — gitlab-reviewer
## What is this
FastAPI service that fetches GitLab MR diffs and sends them to LLM for code review.
Uses GitLab API (token from env), OpenAI API (key from env).

## Stack
Python 3.12, FastAPI, httpx, python-gitlab, openai SDK

## Critical Rules
- Never log API tokens
- All GitLab/OpenAI tokens from environment variables only
- No hardcoded credentials anywhere

---

TASK_CONTEXT:
Fix ruff lint errors (issue #11). Pure style fixes — no logic changes.
AC: ruff check returns 0 errors. All 23 tests pass.

---

DIFF:
diff --git a/src/gitlab_reviewer/client.py b/src/gitlab_reviewer/client.py
index a3b2c1d..f4e5678 100644
--- a/src/gitlab_reviewer/client.py
+++ b/src/gitlab_reviewer/client.py
@@ -1,7 +1,5 @@
 import os
-import json
-import sys
 from typing import Optional
 
 class GitLabClient:
@@ -45,7 +43,7 @@ class GitLabClient:
-        for key, value in headers.items():
+        for _, value in headers.items():
             if value is None:
                 continue

---

Верни findings одним блоком в конце:
[BLOCKING/MINOR/CRITICAL/HIGH/MEDIUM]: описание, файл:строка, fix
Итого: X blocking, Y minor.
```

---

## Actual Cycle Output

```
✅ Full cycle завершён — gitlab-reviewer / fix/ruff-lint-11

Tests:   23 passed / 23 total
Commits: 2

Self-review:
  Developer  — 0 blocking, 0 minor
  Architect  — 0 blocking (lint-only change, no design impact)
  QA/Manual  — 23 ACs covered (all existing tests pass)
  Security   — CLEAR (no security-relevant changes in diff)
  Final      — APPROVE ✅

PR: https://github.com/KoshelevDV/gitlab-reviewer/pull/12
Issues: none
```

**Timeline:**
- T+0: full cycle triggered
- T+2min: developer subagent started
- T+8min: developer subagent done (fix + tests + lint)
- T+8min: 4 review subagents spawned (parallel)
- T+8min: cron_1 scheduled at T+31min
- T+23min: all 4 reviewers done (async)
- T+23min: final review inline → APPROVE, 0 blocking
- T+24min: PR created → output sent to user

**Cron was not needed** — all 4 subagents completed and triggered session resume before cron_1 fired. Cron_1 fired at T+31min → found 0 active subagents + PR already exists → no-op.

---

## What the Fix Covered

```
ruff check src/ tests/ (before):
  src/gitlab_reviewer/client.py:3:8: F401 [*] `json` imported but unused
  src/gitlab_reviewer/client.py:4:8: F401 [*] `sys` imported but unused
  src/gitlab_reviewer/client.py:45:14: B007 Loop control variable `key` not used
  src/gitlab_reviewer/reviewer.py:12:5: E711 Comparison to `None` (use `is None`)
  ... (43 more)

ruff check src/ tests/ (after):
  All checks passed.
```

---

## Lessons Learned (from AGENTS.md)

```markdown
## Pitfalls

- **ruff E501**: When wrapping long lines, watch for string concatenation 
  that breaks semantics. Always run tests after wrapping.
- **B007 fix**: Renaming loop variable to `_` is correct, but if the variable 
  is used in inner scope, this causes NameError. Verify before renaming.
- **F401 in __init__.py**: Some imports in __init__.py exist for re-export. 
  Use `# noqa: F401` to suppress, don't delete.
```
