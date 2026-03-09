# How It Works — Full Cycle Pipeline

## ASCII Pipeline Diagram

```
User trigger: "full cycle для <project> <task>"
                         │
                         ▼
         ┌───────────────────────────────────┐
         │     MAIN SESSION (Orchestrator)    │
         │           [SILENT]                 │
         └───────────────────────────────────┘
                         │
         ┌───────────────▼───────────────────┐
         │  STEP 1-3: DEVELOP                 │
         │  ┌─────────────────────────────┐  │
         │  │  Developer Subagent          │  │
         │  │  • git checkout -b branch    │  │
         │  │  • Read AGENTS.md + docs/    │  │
         │  │  • memory_search(context)    │  │
         │  │  • Implement feature         │  │
         │  │  • Write tests (green ✅)    │  │
         │  │  • Fix lint (clean ✅)       │  │
         │  │  • Update AGENTS.md + README │  │
         │  │  • git commit + push         │  │
         │  └─────────────────────────────┘  │
         │  Output: BRANCH, STACK, DIFF       │
         └───────────────────────────────────┘
                         │
         ┌───────────────▼───────────────────┐
         │  STEP 4: REVIEW (parallel × 4)     │
         │                                    │
         │  ┌──────────┐  ┌──────────────┐   │
         │  │ Developer│  │  Architect   │   │
         │  │  review  │  │   review     │   │
         │  └────┬─────┘  └──────┬───────┘   │
         │       │               │            │
         │  ┌────┴─────┐  ┌──────┴───────┐   │
         │  │  Tester  │  │   Security   │   │
         │  │  review  │  │   review     │   │
         │  └────┬─────┘  └──────┬───────┘   │
         │       └───────┬───────┘            │
         │               ▼                    │
         │  STEP 4e: Final Review (inline)    │
         │  Orchestrator reads all 4 reviews  │
         │  → APPROVE or REQUEST_CHANGES      │
         └───────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         BLOCKING = 0         BLOCKING > 0
              │                     │
              ▼          ┌──────────▼──────────┐
         STEP 6          │  STEP 5: FIX         │
                         │  Fix Subagent         │
                         │  • Fix BLOCKING list  │
                         │  • Tests green ✅     │
                         │  • Lint clean ✅      │
                         │  • git commit + push  │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │ repeat STEP 4 (re-review)│
                         │ max 3 rounds           │
                         └──────────┬────────────┘
                                    │
         ┌──────────────────────────▼────────────┐
         │  STEP 6: PUSH + OUTPUT                 │
         │  • gh pr create                        │
         │  • Single message to user              │
         │  ✅ Full cycle done — PR: <url>        │
         └────────────────────────────────────────┘
```

---

## Step-by-Step Details

### Steps 1-3: Developer Subagent

**Purpose:** Implement the feature from scratch on a new branch.

**Actions:**
1. `git fetch origin && git pull origin main && git checkout -b <branch>`
2. Read `AGENTS.md`, `docs/`, `ROADMAP.md` (project context)
3. `memory_search()` for relevant architecture decisions
4. Read role prompt from `prompts/developer/<stack>.md`
5. Implement the feature following Critical Rules in `AGENTS.md`
6. Read `prompts/tester/autotests.md` and write tests
7. Run tests — must be **green** before committing
8. Run linter — must be **clean** before committing
9. **Update docs (mandatory):**
   - `AGENTS.md`: status, new decisions, pitfalls
   - `README.md`: if public API/CLI changed
   - `ROADMAP.md`: mark completed item ✅
10. `git commit` and push

**Output block:**
```
BRANCH: feat/my-feature
STACK: python
TESTS: 42 passed
LINT: ruff clean
DOCS: AGENTS.md updated / README updated
DIFF_SUMMARY: Added JWT auth middleware, 3 new endpoints, tests cover happy path + errors
```

**Timeout:** 900 seconds

---

### Step 4: 4 Parallel Review Subagents

**Purpose:** Independent review of the diff from 4 specialist perspectives.

All 4 subagents are spawned **simultaneously** with:
- Full role prompt text
- `PROJECT_CONTEXT` (AGENTS.md content)
- `TASK_CONTEXT` (task description + acceptance criteria)
- `DIFF` (git diff output, max 400 lines)

#### Reviewer Roles

| Role | What they check |
|------|----------------|
| **Developer** | Code quality, naming, patterns, DRY, edge cases, error handling |
| **Architect** | Design decisions, coupling, scalability, SOLID principles, ROADMAP alignment |
| **Tester / QA** | Test coverage, AC completeness, missing test cases, edge cases |
| **Security** | Injection risks, auth/authz, secrets handling, input validation, CVEs |

#### Severity Table

| Role | = BLOCKING (fix before PR) | → Issue (create, don't block) |
|------|---------------------------|-------------------------------|
| Developer | BLOCKING | MINOR, SUGGESTION |
| Architect | BLOCKING | MINOR |
| Tester | MUST HAVE | SHOULD HAVE, NICE TO HAVE |
| Security | CRITICAL, HIGH | MEDIUM, LOW |

> **Note:** `MUST HAVE` from Tester = BLOCKING. A missing test for an AC = incomplete feature.

#### Scope Rule ⚠️

**All reviewers must ONLY check changes in the DIFF.**

Pre-existing issues that existed before this MR:
- → NOT BLOCKING
- → List in MINOR section with `[pre-existing]` tag
- Security especially: do NOT block PR for issues not introduced by current change

#### Step 4e: Final Review (Inline)

The orchestrator (main session) reads all 4 reviews and renders its own final verdict:
- Reads `prompts/reviewer/general.md`
- Aggregates findings from all roles
- Verdicts: `APPROVE ✅` or `REQUEST_CHANGES ⚠️`
- Counts total `blocking_count`

**Timeout per subagent:** 1200 seconds

---

### Step 5: Fix Subagent

**Purpose:** Fix all BLOCKING findings from the review.

**Actions:**
1. Receive explicit numbered list of BLOCKING findings (file:line + fix description)
2. Fix each finding
3. Run tests after each fix — must stay green
4. Run linter — must stay clean
5. Update `AGENTS.md` with discovered pitfalls
6. `git commit -m "fix: ..."` and push
7. Create a single combined issue for all MINOR/MEDIUM findings

**Verification rule:** Before spawning fix-subagent, orchestrator must **verify findings in real code**:
- Open the files mentioned in BLOCKING findings
- Confirm the issue actually exists (reviewers analyze by diff and can have false positives)
- Skip false alarms — don't fix what isn't broken

**Timeout:** 600 seconds

#### Fix → Review Loop

```
review_round = 1
MAX_ROUNDS = 3

while blocking_count > 0:
    if review_round > MAX_ROUNDS:
        report to user: "Could not resolve all BLOCKING in 3 iterations"
        break
    spawn fix_subagent(blocking_list)
    review_round += 1
    repeat full Step 4 (all 4 roles + 4e)
    update blocking_count
```

After each fix — **mandatory full re-review** (all 4 roles + final). Never consider branch clean based on "fix was applied" alone — new changes may introduce new BLOCKING.

---

### Step 6: PR + Output

**Actions:**
```bash
gh pr create \
  --title "<type>: <description>" \
  --body "## Summary\n...\n## Changes\n...\n## Testing\n..." \
  --base main --head <branch>
```

**Single message to user:**
```
✅ Full cycle done — my-project / feat/my-feature

Tests:   42 passed / 42 total
Commits: 3

Self-review:
  Developer  — 2 blocking fixed, 1 minor → issue #42
  Architect  — 0 blocking
  QA/Manual  — 5 ACs covered, 1 SHOULD HAVE → issue #42
  Security   — CLEAR
  Final      — APPROVE ✅

PR: https://github.com/org/my-project/pull/15
Issues: https://github.com/org/my-project/issues/42
```

---

## DOCS Rule

**Why AGENTS.md + README are mandatory updates:**

The developer subagent must update docs **before** the final commit because:

1. **AGENTS.md** is the AI context for the next session — stale docs = wrong decisions
2. **README** represents public API/CLI contract — undocumented changes = broken UX
3. **ROADMAP** alignment — orchestrator and architect need to know what's done

Skipping docs update = the feature is incomplete.

---

## Interruption Rules

The orchestrator **must NOT** send intermediate messages to the user during:
- develop → review transition
- review → fix transition
- fix → re-review transition

**Only valid interruptions:**
1. MAX_ROUNDS exceeded — explain what failed, pass control to user
2. Fatal error — tests red and fix-subagent can't resolve in 3 attempts
3. Task ambiguity that requires user decision

All other cases: silently proceed to next step.
