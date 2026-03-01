# Agentic SDLC Workflow

## Overview

Fully agentic software development lifecycle for the `openclaw-crypto-ai-quant` project. User does NOT review PRs — full agentic cycle handles planning, implementation, validation, review, testing, and merge.

**Repository**: `fol2/openclaw-crypto-ai-quant`
**Branch**: `master` (production)
**Workspace**: `/home/fol2hk/openclaw-plugins/ai_quant`
**Branch protection**: feature branch → PR → admin merge to `master` (no direct push)

---

## Team Structure (5 Roles)

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **Team Lead** | main agent | Sprint planning, task assignment, blocker resolution, merge gate, GitHub issue lifecycle, sprint retro |
| **Dev Agent(s)** | general-purpose | Implement code changes + write unit tests, produce review brief |
| **Validator Agent** | general-purpose | Axis-by-axis parity checks, precision tier verification, intermediate value comparison |
| **Reviewer Agent** | general-purpose | Code review on diff (NOT the same agent that wrote the code), acceptance criteria audit |
| **Tester Agent** | Bash | Full build + test suite, regression gate, acceptance criteria sign-off |

### Role Separation Rules
- **Dev ≠ Reviewer**: the agent that wrote the code must NEVER review it
- **Dev ≠ Validator**: validation requires independent verification
- **Validator ≠ Tester**: validator checks logic parity; tester checks build/suite/CI
- **Team Lead** can fill any role in emergencies but should avoid combining Dev + Reviewer

---

## Lifecycle Per Ticket (7 Phases)

```
Phase 1: PLAN (Team Lead)
  - Read GitHub issue + acceptance criteria
  - Read target files + dependency tickets
  - Identify precision tier requirements (T0–T4, see below)
  - Create feature branch: feat/AQC-xxx from master
  - Create TaskList with sub-tasks, assign to Dev
  - Create worktree if parallel dev needed

Phase 2: PRE-IMPL CHECKPOINT (Dev Agent → Team Lead)
  - Dev reads task + target files + related source
  - Dev outputs understanding brief:
    • What will change (files, functions, line ranges)
    • Edge cases identified
    • Precision tier assignment for numeric outputs
    • Open questions
  - Team Lead confirms alignment OR redirects before any code is written
  - This prevents wasted effort on misunderstood requirements

Phase 3: IMPLEMENT (Dev Agent)
  - Implement changes + write tests
  - cargo test -p <crate> (quick local check)
  - Commit to feature branch with structured message:
    feat(kernel): AQC-xxx: <description>

    [REVIEW-BRIEF]
    - Changed: <files and functions>
    - Impact: <what behavior changed>
    - Edge cases: <handled / known limitations>
    - Precision: <T0-T4 tier for numeric outputs>
  - Signal "ready for validation"

Phase 4: VALIDATE (Validator Agent — NOT the Dev)
  Only for tickets with paired validation ticket (AQC-126x series).
  For tickets without validation pair, skip to Phase 5.
  - Run axis-by-axis comparison (each config field isolated)
  - Compare intermediate values, not just final output
  - Verify precision within declared tier tolerance
  - Produce validation report:
    • Axes tested / total axes
    • Max divergence per tier
    • Any tier violations (FAIL if divergence exceeds tier tolerance)
  - Verdict: VALIDATED / VALIDATION_FAILED + divergence details
  - If VALIDATION_FAILED → back to Phase 3 with specific axis/value feedback

Phase 5: REVIEW (Reviewer Agent — NOT the Dev or Validator)
  - git diff master...feat/AQC-xxx
  - Check: acceptance criteria, edge cases, regressions, security, test coverage
  - Verify REVIEW-BRIEF in commit message is accurate
  - Check validation report (if applicable) for completeness
  - Severity classification for findings:
    • BLOCKER: incorrect logic, data loss, security issue
    • MAJOR: missing edge case, test gap, precision tier wrong
    • MINOR: style, naming, documentation
  - Verdict: APPROVE / REQUEST_CHANGES(severity) + feedback
  - If REQUEST_CHANGES(BLOCKER|MAJOR) → back to Phase 3

Phase 6: TEST + REGRESSION (Tester Agent)
  - cargo test --release (full suite)
  - cargo build --release
  - Run ALL previously-passing parity tests (regression gate)
  - Validate acceptance criteria checklist item-by-item
  - Verdict: PASS / FAIL
  - If any previously-passing test now fails → REGRESSION → back to Phase 3

Phase 7: MERGE (Team Lead)
  - Confirm: Validation VALIDATED + Review APPROVED + Tests PASSED
  - Push feature branch, create PR via gh
  - Merge PR to master (admin merge)
  - Delete feature branch + worktree
  - gh issue close with summary comment including:
    • Validation report summary
    • Reviewer verdict
    • Test suite result
    • Any accepted trade-offs
  - Update divergence registry if applicable
  - Pick next ticket
```

---

## Precision Tiers (f32/f64 Validation)

Numeric outputs from GPU (f32) vs CPU (f64) are validated against tier-specific tolerances:

| Tier | Name | Tolerance | Example Fields |
|------|------|-----------|----------------|
| T0 | Exact | 0 (bit-identical) | Booleans, enums, gate pass/fail, signal direction |
| T1 | Threshold | f32 round-trip (≈1.19e-7 relative) | Config lookups, direct comparisons |
| T2 | Simple | ≤ 1e-6 relative | Single arithmetic ops, ATR ratios |
| T3 | Chained | ≤ 1e-5 relative | Multi-step chains (EMA dev, ADX interpolation) |
| T4 | Accumulated | ≤ 1e-3 relative | Running sums, equity curves, cumulative PnL |

**Empirical finding (AQC-1260)**: T4 relaxed from 1e-4 to **1e-3** — catastrophic cancellation
when subtracting correlated large f32 values (e.g., EMA_12 - EMA_26 at BTC ~50000) produces
1e-4 to 5e-4 relative error. MACD histogram over 30 bars measured 3.76e-4. Fundamental f32
limitation, not a bug.

**Rules**:
- Every validation ticket MUST declare tier per output field
- Reviewer verifies tier assignment is correct (not too loose)
- Tier violations are BLOCKER severity

---

## Handoff Protocols

### Dev → Validator Handoff
```
Message format:
  Subject: "AQC-xxx ready for validation"
  Body:
  - Feature branch: feat/AQC-xxx
  - Commit: <sha>
  - Functions changed: <list>
  - Fixture data location: <path>
  - Expected precision tiers: <table>
  - Known edge cases: <list>
```

### Dev → Reviewer Handoff
```
REVIEW-BRIEF in commit message (see Phase 3 above)
Plus: validation report from Phase 4 (if applicable)
```

### Reviewer → Team Lead Handoff
```
Review verdict with:
  - Severity-classified findings
  - Acceptance criteria checklist (checked/unchecked)
  - Recommendation: merge / needs work / needs discussion
```

---

## Worktree Rules

**Each active Dev agent MUST have its own git worktree.** Sharing a worktree between concurrent dev agents causes race conditions.

```
ai_quant/                ← Team Lead ONLY (merge ops, branch creation, production)
ai_quant_wt/dev-a/       ← Dev Agent A (exclusive)
ai_quant_wt/dev-b/       ← Dev Agent B (exclusive)
```

### Setup per sprint
```bash
# Team Lead creates worktrees before spawning dev agents
git -C /home/fol2hk/openclaw-plugins/ai_quant worktree add ../ai_quant_wt/dev-a -b feat/AQC-xxx master
git -C /home/fol2hk/openclaw-plugins/ai_quant worktree add ../ai_quant_wt/dev-b -b feat/AQC-yyy master
```

### Rules
1. **1 worktree per active dev agent** — never share between concurrent agents
2. **Team Lead owns `ai_quant/`** — only used for merges, branch ops, no dev work
3. **Reviewer/Validator** read `git diff` output — do NOT need their own worktree
4. **Tester agents** checkout the feature branch in dev's worktree — reuse after dev is idle
5. **Cleanup after merge**: `git worktree remove ../ai_quant_wt/dev-a` + delete feature branch
6. **Sequential reuse OK**: dev finishes ticket A, starts ticket B → same worktree, switch branch
7. **Concurrent reuse NOT OK**: two dev agents must never share one worktree simultaneously

### Lessons Learned

**V8 M2**: dev-703 and dev-708 shared worktree — worked by luck (sequential timing) but violated isolation. Could cause corrupted state if agents overlap.

**M8 Phase 0 Sprint 1**: AQC-1200 and AQC-1201 agents ran without separate worktrees (both in `ai_quant/`). AQC-1201 agent picked up AQC-1200's uncommitted files, creating an implicit dependency. Worked because file changes didn't overlap, but violated isolation principle. **Always create worktrees BEFORE spawning parallel dev agents.** The Team Lead must:
1. `git worktree add ../ai_quant_wt/dev-a -b feat/AQC-xxx master`
2. `git worktree add ../ai_quant_wt/dev-b -b feat/AQC-yyy master`
3. Specify worktree path in each agent's prompt
4. Only then spawn the agents

---

## Parallel Execution Strategy

### Within a Phase
- Independent tickets run in parallel (separate feature branches, **separate worktrees**)
- Reviewer/Validator/Tester serve multiple tickets sequentially

### Across Phases (Pipeline Overlap)
- Phase N validation can overlap with Phase N+1 implementation (different tickets)
- Example: while AQC-1261 (gates validation) runs, AQC-1220 (SL codegen) implementation starts
- Constraint: integration tickets (AQC-1212, 1225, 1232) MUST wait for ALL prerequisite validations

### Batch Optimization
- Similar tickets (e.g., 5 exit codegen tickets) can be batch-reviewed
- Shared fixture data built once, cached for all parity tests
- Pair-dev for complex tickets: AQC-1223 (smart exits, 8 sub-checks) benefits from two dev agents splitting sub-checks

---

## Quality Gates

### Gate 1: Pre-Impl (before coding starts)
- [ ] Dev understanding brief reviewed by Team Lead
- [ ] Precision tiers declared for all numeric outputs
- [ ] Feature branch created from latest master

### Gate 2: Post-Impl (before validation/review)
- [ ] All acceptance criteria addressed in code
- [ ] Unit tests added for new logic
- [ ] `cargo test -p <crate>` passes locally
- [ ] REVIEW-BRIEF in commit message

### Gate 3: Post-Validation (before review)
- [ ] All axes tested
- [ ] Max divergence within declared tier tolerance
- [ ] Intermediate values compared (not just final output)
- [ ] Validation report produced

### Gate 4: Post-Review (before testing)
- [ ] Zero BLOCKER findings
- [ ] Zero MAJOR findings (or explicitly accepted with rationale)
- [ ] Acceptance criteria checklist fully checked

### Gate 5: Pre-Merge (before PR merge)
- [ ] Full test suite passes (`cargo test --release`)
- [ ] Build succeeds (`cargo build --release`)
- [ ] **Regression gate**: ALL previously-passing parity tests still pass
- [ ] No new compiler warnings in changed files

---

## Audit Trail

### Decision Log
Record architectural choices in the plan document:
```markdown
| Date | Decision | Options Considered | Rationale |
|------|----------|-------------------|-----------|
| 2026-02-16 | Option A: string-template codegen | A: string-template, B: proc-macro, C: LLVM IR | Simplest, proven in AQC-761, no proc-macro dep |
```

### Divergence Registry
Track all known CPU↔GPU divergences and their resolution:
```markdown
| Divergence | Status | Resolved By | Residual |
|-----------|--------|-------------|----------|
| Confidence: DRE vs volume | OPEN | AQC-1211 | — |
| Anomaly: bb_width vs price_change | OPEN | AQC-1210 | — |
```
Update status to RESOLVED when the ticket merges and validation passes.

### Sprint Retrospective
After each phase completion:
- What went well
- What went wrong (bugs found late, validation failures, wasted effort)
- Process improvements for next phase
- Metrics: tickets/day, review rounds per ticket, validation failure rate

---

## Commit Format

```
<type>(<scope>): AQC-xxx: <description>

[REVIEW-BRIEF]
- Changed: <files and functions>
- Impact: <what behavior changed>
- Edge cases: <handled / known limitations>
- Precision: <T0-T4 tier for numeric outputs>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`
Scopes: `kernel`, `gpu`, `codegen`, `sweep`, `config`, `ci`

---

## Critical Rules

1. **Branch**: all work branches from and merges back to `master` via PR
2. **Branch protection**: no direct push to `master` — feature branch + PR + admin merge
3. **Rust sidecar + candle DB**: use the main machine's shared sidecar and candle DB
4. **Self-contained**: user does NOT review PRs — full agentic cycle handles everything
5. **Regression is a BLOCKER**: any previously-passing test that now fails blocks merge
6. **Precision tier violations are BLOCKERs**: divergence exceeding declared tier tolerance blocks merge
7. **No silent failures**: every validation/review/test produces a structured verdict message

---

## Current Active Milestone

**M8: GPU Decision Logic Codegen** — 37 tickets (26 impl + 11 validation), ~29.5 dev-days
See `backtester/plan/5/gpu-decision-codegen.md` for full plan and dependency graph.

### Historical Milestones (Completed)
- M1–M7: V8 SSOT kernel migration (36 tickets, #235-#270) — COMPLETE, tag `v8.0.0`
