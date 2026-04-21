# Architecture Decision Record (ADR)

**ADR ID**: ADR-YYYY-MM-DD-XXX  
**Title**: [Short decision title]  
**Status**: Proposed | Accepted | Rejected | Superseded (link)  
**Date**: YYYY-MM-DD  
**Owner**: [Team / person]  
**Deciders**: [Names / roles]  
**Scope**: [Service / domain / product area]  

---

## Core

### 1. Context

**Problem statement**: What are we deciding, and why now?

**Goals**:
- [Goal 1]
- [Goal 2]

**Non-goals**:
- [Non-goal 1]
- [Non-goal 2]

**Constraints** (REQUIRED):
- Regulatory/compliance:
- Latency/SLO:
- Data residency:
- Platform/runtime:
- Team/operational maturity:

**Assumptions** (mark unvalidated):
- [Assumption] ([Inference] if not verified)

### 2. Decision Drivers (What Matters Most)

Rank the drivers to make tradeoffs explicit.

| Priority | Driver | Why it matters | How we measure |
|---:|---|---|---|
| 1 | Reliability | | SLO, error budget |
| 2 | Security | | Threat model, control coverage |
| 3 | Cost | | Unit cost, infra spend |
| 4 | Delivery speed | | Lead time, deployment frequency |
| 5 | Operability | | On-call load, MTTR |

### 3. Options Considered

| Option | Summary | Pros | Cons | Reversibility |
|---|---|---|---|---|
| A | | | | Easy / Medium / Hard |
| B | | | | Easy / Medium / Hard |
| C | | | | Easy / Medium / Hard |

### 4. Decision

**We choose**: [Option X]

**Why** (1–5 bullets max):
- [Reason]

### 5. Architecture Impact (Implementation-Ready)

**Boundaries and contracts**
- Public APIs/contracts affected:
- Backward compatibility plan:
- Schema evolution strategy:

**Data and consistency**
- Source of truth:
- Consistency model (strong/eventual/mixed):
- Migration strategy (expand/contract, dual writes, backfill):

**Failure modes and resilience**
- Known failure modes:
- Timeouts/retries/backoff policy:
- Idempotency strategy:
- Degradation plan (what still works when dependencies fail):

**Security**
- Threat model summary:
- AuthN/AuthZ model:
- Secret and key management:
- Audit logging requirements:

**Observability**
- SLIs/SLOs:
- Metrics/traces/logs to add:
- Dashboards and alerts:

**Cost and capacity**
- Expected traffic/load:
- Cost model (drivers, main spend areas):
- Capacity plan (limits, scaling triggers):

### 6. Rollout, Validation, and Rollback

**Rollout plan**
- Feature flag / staged rollout:
- Data migration steps:
- Runbook updates:

**Validation plan**
- Tests to add (unit/integration/contract):
- Load/perf tests:
- Chaos/failure injection (if applicable):

**Rollback plan**
- How to revert code:
- How to revert data (or forward-fix):
- Timebox for rollback decision:

### 7. Consequences

**Positive**
- [Benefit]

**Negative / tradeoffs**
- [Cost or risk]

**Follow-ups**
- [Task] (owner, due date)

### 8. Links

- Design doc:
- Diagram(s):
- Tickets/epics:
- Related ADRs:

---

## Optional: AI/Automation

Include only if this ADR affects AI/automation features or AI-assisted workflows.

### AI Risk and Safety

- User impact of wrong output (harm model):
- Human override path and audit trail:
- Data handling (PII/PHI, retention, residency):
- Abuse cases (prompt injection, data exfiltration) [Inference]

### Evaluation and Quality Gates

- Offline evaluation set definition:
- Online metrics and guardrails:
- Rollback triggers for quality regression:

### Operations and Cost

- Latency/cost targets:
- Rate limiting and quotas:
- Observability for model/tool calls:

---

## References

- ADR concept and template rationale: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
