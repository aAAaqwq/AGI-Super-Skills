# PRD Engine — Product Requirements That Ship

Complete product requirements methodology: from idea to spec to shipped feature. Not just a JSON template — a full system for writing PRDs that developers actually follow and stakeholders actually approve.

## When to Use This Skill

- Turning a vague idea into a buildable specification
- Writing PRDs for new features, products, or major refactors
- Reviewing/improving existing PRDs before sprint planning
- Breaking epics into right-sized user stories
- Creating technical design documents alongside product specs
- Preparing specs for AI coding agents (Claude Code, Cursor, Copilot)

---

## Phase 1: Discovery Brief

Before writing a single requirement, answer these questions. Skip this and you'll rewrite the PRD 3 times.

### Problem Validation Checklist

```yaml
discovery_brief:
  problem:
    statement: "" # One sentence. If you need two, you don't understand it yet.
    who_has_it: "" # Specific persona, not "users"
    frequency: "" # Daily? Weekly? Once? (daily problems > occasional ones)
    current_workaround: "" # What do they do today? (no workaround = maybe not a real problem)
    evidence:
      - type: "" # support_ticket | user_interview | analytics | churned_user | sales_objection
        detail: ""
        date: ""

  impact:
    users_affected: "" # Number or percentage
    revenue_impact: "" # $ at risk or $ opportunity
    strategic_alignment: "" # Which company goal does this serve?

  constraints:
    deadline: "" # Hard date or flexible?
    budget: "" # Engineering weeks available
    dependencies: "" # What must exist first?
    regulatory: "" # Any compliance requirements?

  success_metrics:
    primary: "" # ONE metric that defines success
    secondary: [] # 2-3 supporting metrics
    measurement_method: "" # How will you actually measure this?
    target: "" # Specific number, not "improve"
    timeframe: "" # When do you expect to see results?
```

### Problem Statement Formula

**[Persona] needs [capability] because [reason], but currently [blocker], which causes [measurable impact].**

Examples:
- ❌ "Users need better onboarding" (vague, unmeasurable)
- ✅ "New free-trial users (500/month) need to reach their first 'aha moment' within 10 minutes because 73% who don't will churn within 48 hours, but currently the average time-to-value is 34 minutes due to a 12-step setup wizard, which costs us ~$18K/month in lost conversions."

### Kill Criteria

Before proceeding, check these. If any are true, STOP and push back:

| Signal | Action |
|--------|--------|
| No evidence of the problem (just someone's opinion) | Demand evidence. Opinions aren't requirements. |
| Solution already decided ("just build X") | Rewind to the problem. Solutions without problems = features nobody uses. |
| Success metric is unmeasurable | Define how you'll measure it or don't build it. |
| Affects <1% of users with no revenue impact | Deprioritize. Small problems with small impact = small returns. |
| Scope keeps expanding during discovery | Scope lock. If everything is in scope, nothing is. |

---

## Phase 2: PRD Document

### PRD Template

```markdown
# PRD: [Feature Name]

**Author:** [Name]
**Status:** Draft | In Review | Approved | In Progress | Shipped
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**Approvers:** [Names + roles]

## 1. Problem & Opportunity

[Problem statement from discovery brief — one paragraph max]

### Evidence
- [Evidence point 1 — with data]
- [Evidence point 2 — with data]

### Impact
- Users affected: [number]
- Revenue impact: [$ amount or % change]
- Strategic goal: [which one]

## 2. Solution Overview

[2-3 paragraphs max. What are we building and why this approach?]

### What This Is
- [Bullet list of what's in scope]

### What This Is NOT
- [Explicit exclusions — this prevents scope creep]

### Key Decisions Made
| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| [Decision 1] | A, B, C | B | [Why] |

## 3. User Stories

[See Phase 3 below for story writing methodology]

## 4. Design & UX

### User Flow
1. User [action] →
2. System [response] →
3. User sees [outcome]

### Wireframes/Mockups
[Link to Figma/screenshots or describe key screens]

### Edge Cases
| Scenario | Expected Behavior |
|----------|------------------|
| [Edge case 1] | [What happens] |
| [Edge case 2] | [What happens] |
| Empty state | [What user sees with no data] |
| Error state | [What user sees on failure] |
| Slow connection | [Loading behavior] |

## 5. Technical Considerations

### Architecture Notes
- [Key technical decisions]
- [New services/APIs needed]
- [Database changes]

### Dependencies
- [External service X]
- [Team Y's API]
- [Library Z]

### Performance Requirements
- Page load: <[X]ms
- API response: <[X]ms
- Concurrent users: [X]

### Security & Privacy
- [Data handling requirements]
- [Auth/permissions needed]
- [PII considerations]

## 6. Release Plan

### Rollout Strategy
- [ ] Feature flag: [flag name]
- [ ] Beta group: [who]
- [ ] % rollout: [10% → 50% → 100%]
- [ ] Rollback plan: [how]

### Launch Checklist
- [ ] QA sign-off
- [ ] Analytics events implemented
- [ ] Monitoring/alerts configured
- [ ] Documentation updated
- [ ] Support team briefed
- [ ] Stakeholders notified

## 7. Success Criteria

| Metric | Current | Target | Timeframe |
|--------|---------|--------|-----------|
| [Primary metric] | [X] | [Y] | [Z weeks] |
| [Secondary metric] | [X] | [Y] | [Z weeks] |

### Post-Launch Review
- **1-week check:** [What to look at]
- **1-month review:** [What to measure]
- **Kill/iterate decision:** [Criteria for each]
```

### PRD Quality Rubric (score before sharing)

| Dimension | 0-2 (Weak) | 3-4 (Adequate) | 5 (Strong) | Weight |
|-----------|-----------|----------------|------------|--------|
| **Problem clarity** | Vague, no data | Clear but thin evidence | Sharp statement + multiple evidence points | x4 |
| **Scope discipline** | Everything in scope | Some boundaries | Explicit in/out + "what this is NOT" | x3 |
| **Story quality** | Vague tasks | Stories with some criteria | INVEST stories + verifiable acceptance criteria | x4 |
| **Edge cases** | None listed | Happy path + 1-2 edges | Comprehensive: empty, error, slow, permissions, concurrent | x3 |
| **Success metrics** | "Improve X" | Metric + target | Metric + baseline + target + timeframe + measurement method | x3 |
| **Technical feasibility** | No tech section | Architecture notes | Dependencies, performance, security, migration plan | x2 |
| **Release plan** | None | "Ship it" | Feature flag + rollout % + rollback + launch checklist | x1 |

**Scoring:** Sum (score × weight). Max = 100.
- **80-100:** Ship-ready. Get approvals.
- **60-79:** Solid but missing pieces. Fill gaps before review.
- **40-59:** Needs work. Major sections incomplete.
- **<40:** Start over or go back to discovery.

---

## Phase 3: User Story Methodology

### Story Format

```yaml
story:
  id: "US-001"
  title: "" # Action-oriented: "Add priority field to tasks table"
  persona: "" # Who benefits
  narrative: "As a [persona], I want [capability] so that [benefit]"
  acceptance_criteria:
    - criterion: "" # Verifiable statement
      type: "functional" # functional | performance | security | ux
  priority: 1 # Execution order (dependencies first)
  size: "" # XS | S | M | L | XL
  status: "todo" # todo | in_progress | review | done
  notes: "" # Runtime observations
  depends_on: [] # Story IDs this depends on
  blocked_by: [] # External blockers
```

### INVEST Checklist (every story must pass)

| Letter | Criterion | Test |
|--------|-----------|------|
| **I** — Independent | Can be built without other incomplete stories | No circular dependencies |
| **N** — Negotiable | Details can flex (the "what" is fixed, the "how" is flexible) | Multiple implementation approaches exist |
| **V** — Valuable | Delivers user or business value on its own | Would a user/stakeholder care if only this shipped? |
| **E** — Estimable | Team can size it | No major unknowns (if unknowns exist, add a spike first) |
| **S** — Small | Completable in one sprint (or one context window for AI agents) | 1-3 days of work max |
| **T** — Testable | Has verifiable acceptance criteria | Can write a test for each criterion |

### Acceptance Criteria Rules

**Good criteria are:**
- Binary (pass/fail, not subjective)
- Specific (numbers, not adjectives)
- Independent (testable in isolation)

| ❌ Bad | ✅ Good |
|--------|---------|
| "Works correctly" | "Returns 200 with JSON body containing `id`, `name`, `status` fields" |
| "Fast enough" | "API responds in <200ms at p95 with 100 concurrent users" |
| "User-friendly" | "Form shows inline validation errors within 100ms of field blur" |
| "Secure" | "Endpoint returns 403 for users without `admin` role" |
| "Handles errors" | "On network timeout, shows retry button + cached data if available" |

**Always include these universal criteria:**
- `Typecheck passes (tsc --noEmit --strict)` (for TypeScript projects)
- `All existing tests still pass`
- `New functionality has test coverage`

### Story Sizing Guide

| Size | Scope | Time | Example |
|------|-------|------|---------|
| **XS** | Config change, copy update, env var | <2 hours | "Update error message text" |
| **S** | Single component/function, no new deps | 2-4 hours | "Add date picker to form" |
| **M** | Feature slice: DB + API + UI | 1-2 days | "Add task priority with filter" |
| **L** | Multi-component feature, new patterns | 2-3 days | "Add real-time notifications" |
| **XL** | **Too big. Split it.** | — | — |

### Story Ordering: The Dependency Pyramid

Always order stories bottom-up:

```
Level 1: Schema & Data (migrations, models, seed data)
    ↑
Level 2: Backend Logic (services, APIs, business rules)
    ↑
Level 3: Integration (API routes, auth, middleware)
    ↑
Level 4: UI Components (forms, tables, modals)
    ↑
Level 5: UX Polish (animations, empty states, loading)
    ↑
Level 6: Analytics & Monitoring (events, dashboards)
```

Each level depends ONLY on levels below it. Never build UI before the API exists.

### Splitting Strategies

When a story is too big, split using one of these patterns:

| Strategy | When to Use | Example |
|----------|------------|---------|
| **By layer** | Full-stack feature | "Add schema" → "Add API" → "Add UI" |
| **By operation** | CRUD feature | "Create task" → "Read/list tasks" → "Update task" → "Delete task" |
| **By persona** | Multi-role feature | "Admin creates template" → "User fills template" → "Viewer sees results" |
| **By happy/sad path** | Complex flows | "Successful payment" → "Payment declined" → "Payment timeout" |
| **By platform** | Cross-platform | "iOS support" → "Android support" → "Web support" |
| **Spike + implement** | High uncertainty | "Spike: evaluate auth libraries (2h)" → "Implement auth with chosen library" |

---

## Phase 4: PRD for AI Coding Agents

When the PRD will be executed by AI agents (Claude Code, Cursor, Copilot Workspace, etc.), add these adaptations:

### Agent-Optimized Story Format

```yaml
agent_story:
  id: "US-001"
  title: "Add priority field to tasks table"
  context: |
    The tasks table is in src/db/schema.ts using Drizzle ORM.
    Priority values should be: high, medium, low (default: medium).
    See existing fields for naming conventions.
  acceptance_criteria:
    - "Add `priority` column to `tasks` table in src/db/schema.ts"
    - "Type: enum('high', 'medium', 'low'), default 'medium', not null"
    - "Generate migration: `npx drizzle-kit generate`"
    - "Run migration: `npx drizzle-kit push`"
    - "Verify: `tsc --noEmit --strict` passes"
    - "Verify: existing tests pass (`npm test`)"
  files_to_touch:
    - src/db/schema.ts
    - drizzle/ (generated migration)
  commands_to_run:
    - "npx drizzle-kit generate"
    - "npx drizzle-kit push"
    - "tsc --noEmit --strict"
    - "npm test"
  done_when: "All verify commands pass with exit code 0"
```

### Agent-Specific Rules

1. **Be explicit about file paths.** Agents can't guess your project structure.
2. **Include verification commands.** Agents need a "definition of done" they can check.
3. **One context window per story.** If a story needs the agent to remember more than ~50 files, it's too big.
4. **List files to touch.** Reduces agent exploration time and prevents hallucination.
5. **Order matters even more.** Agents execute sequentially — wrong order = compounding errors.
6. **Include the commands.** Don't say "run the migration" — say `npx drizzle-kit push`.

### Project Context File

For AI agent execution, create a `PROJECT_CONTEXT.md` alongside the PRD:

```markdown
# Project Context

## Stack
- Framework: [Next.js 14 / Express / etc.]
- Language: [TypeScript strict mode]
- Database: [PostgreSQL via Drizzle ORM]
- Testing: [Vitest + Testing Library]
- Styling: [Tailwind CSS]

## Key Directories
- src/db/ — Database schema and migrations
- src/api/ — API routes
- src/components/ — React components
- src/lib/ — Shared utilities
- tests/ — Test files (mirror src/ structure)

## Conventions
- File naming: kebab-case
- Component naming: PascalCase
- Max file length: 300 lines
- Max function length: 50 lines
- All exports typed, no `any`

## Commands
- `npm run dev` — Start dev server
- `npm test` — Run tests
- `npm run build` — Production build
- `tsc --noEmit --strict` — Type check
- `npx drizzle-kit generate` — Generate migration
- `npx drizzle-kit push` — Apply migration

## Current State
- [What exists today relevant to the PRD]
- [Any tech debt or gotchas the agent should know]
```

---

## Phase 5: Review & Approval

### Review Checklist (before sharing the PRD)

**Completeness:**
- [ ] Problem statement has evidence (not just opinion)
- [ ] "What this is NOT" section exists and is specific
- [ ] Every story has ≥3 acceptance criteria
- [ ] Edge cases table covers: empty state, error state, permissions, concurrent access
- [ ] Success metrics have baseline + target + timeframe
- [ ] Technical section addresses: performance, security, dependencies

**Quality:**
- [ ] No story larger than "L" (split XL stories)
- [ ] All acceptance criteria are binary (pass/fail)
- [ ] No circular dependencies between stories
- [ ] Dependency pyramid ordering is correct
- [ ] Release plan includes rollback strategy

**Readability:**
- [ ] Executive summary is <3 sentences
- [ ] Non-engineers can understand the problem section
- [ ] Engineers can start building from the stories section alone
- [ ] No jargon without definition

### Approval Flow

```
Author writes PRD
    ↓
Self-review (score with rubric — must be ≥60)
    ↓
Peer review (another PM or tech lead)
    ↓
Engineering review (feasibility + sizing)
    ↓
Stakeholder approval (PM lead or product director)
    ↓
Status → Approved
    ↓
Sprint planning (stories → backlog)
```

### Common Review Feedback (and how to fix it)

| Feedback | Fix |
|----------|-----|
| "What problem does this solve?" | Your problem statement is weak. Add evidence. |
| "This is too big" | Split into phases. Ship the smallest valuable slice first (MVP). |
| "How do we know it worked?" | Your success metrics are vague. Add numbers + timeframe. |
| "What about [edge case]?" | Your edge case table is incomplete. Add it. |
| "When does this ship?" | Add timeline with milestones, not just a deadline. |
| "Who approved this?" | Add approvers field and get explicit sign-offs. |

---

## Phase 6: Tracking & Iteration

### PRD Status Lifecycle

```
Draft → In Review → Approved → In Progress → Shipped → Post-Launch Review
                ↓                                              ↓
            Rejected                                    Iterate / Kill
```

### Progress Tracking

Track story completion in the PRD itself or a linked tracker:

```yaml
progress:
  total_stories: 12
  done: 7
  in_progress: 2
  blocked: 1
  todo: 2
  completion: "58%"
  
  blocked_items:
    - story: "US-008"
      blocker: "Waiting for payments API access from finance team"
      since: "2025-01-15"
      escalation: "Pinged finance lead, follow up Friday"

  velocity:
    stories_per_week: 3.5
    estimated_completion: "2025-02-01"
```

### Post-Launch Review Template

```yaml
post_launch:
  shipped_date: ""
  review_date: "" # 2-4 weeks after ship

  metrics:
    primary:
      metric: ""
      baseline: ""
      target: ""
      actual: ""
      verdict: "" # hit | miss | exceeded

    secondary:
      - metric: ""
        actual: ""
        verdict: ""

  qualitative:
    user_feedback: []
    support_tickets: "" # count related to this feature
    unexpected_outcomes: []

  process_retro:
    what_went_well: []
    what_didnt: []
    estimation_accuracy: "" # actual vs estimated effort
    scope_changes: "" # what changed after approval

  decision: "" # iterate | maintain | deprecate | expand
  next_actions: []
```

---

## Quick Commands

| Command | What It Does |
|---------|-------------|
| "Write a PRD for [feature]" | Full PRD from discovery through stories |
| "Break this into stories" | Takes a feature description → user stories |
| "Review this PRD" | Scores against quality rubric + gives specific feedback |
| "Make this agent-ready" | Converts PRD stories to agent-optimized format |
| "What's missing from this PRD?" | Gap analysis against the template |
| "Split this story" | Takes a large story → smaller INVEST-compliant stories |
| "Score this PRD" | Quality rubric scoring with dimension breakdown |
| "Create project context for [project]" | Generates PROJECT_CONTEXT.md for AI agent execution |
| "Post-launch review for [feature]" | Generates review template with metrics |
| "Track progress" | Updates completion stats from story statuses |
