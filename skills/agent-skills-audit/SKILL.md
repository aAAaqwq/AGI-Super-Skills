---
name: audit-code
description: Run a two-pass, multidisciplinary code audit led by a tie-breaker lead, combining security, performance, UX, DX, and edge-case analysis into one prioritized report with concrete fixes. Use when the user asks to audit code, perform a deep review, stress-test a codebase, or produce a risk-ranked remediation plan across backend, frontend, APIs, infra scripts, and product flows.
---

# Audit Code

## Overview

Run an expert-panel audit with strict sequencing and one unified output document.
Produce findings first, sorted by severity, with file references, exploit/perf/flow impact, and actionable fixes.

Load `references/audit-framework.md` before starting the analysis.

## Required Inputs

Collect or infer the following:
- Audit scope: paths, modules, PR diff, or whole repository.
- Product context: PRD/spec/user stories, trust boundaries, and critical business flows.
- Runtime context: deployment model, queue/cron/background jobs, traffic profile, data sensitivity, and abuse assumptions.
- Constraints: timeline, acceptable risk, and preferred remediation style.

If product context is missing, state assumptions explicitly and continue.

## Team Roles

Use exactly these roles:
- Security expert
- Performance expert
- UX expert
- DX expert
- Edge case master
- Tie-breaker team lead

The tie-breaker lead resolves conflicts, prioritizes issues, and produces the final single report.

## Workflow

Follow this sequence every time:

1. Build Context
Read code + product flows. Identify assets, entry points, high-risk operations, privileged actions, external dependencies, and "failure hurts" journeys.

2. Build Invariant Coverage Matrix
Before specialist pass 1, map critical invariants to every mutating path (HTTP routes, webhooks, async jobs, scripts):
- Data-link invariants: multi-table relationships that must remain consistent.
- Auth lifecycle invariants: disable/revoke semantics for sessions/tokens/API keys.
- Input/transport invariants: validation, content-type policy, body-size/parse behavior.
- Shape invariants: trees/graphs must reject cycles where applicable.
Treat missing parity across equivalent paths as a finding candidate.

3. Pass 1 Specialist Reviews
Run role-specific analysis in this order:
- Security
- Performance
- UX
- DX
- Edge case master
Capture findings using the schema in `references/audit-framework.md`.

4. Tie-Breaker Reconciliation
Resolve disagreements:
- Decide whether contested items are true issues.
- Set severity and confidence.
- Remove duplicates and merge overlapping findings.

5. Cross-Review Pass 2
After edge-case findings, rerun specialists:
- Security/Performance/UX/DX reassess prior findings and new edge-triggered scenarios.
- Edge case master performs a final pass on residual risk after proposed mitigations.

6. Final Report
Publish one document from the tie-breaker lead with:
- Findings first (ordered by severity, then blast radius, then exploitability).
- Open questions/assumptions.
- Remediation plan with priority, owner type, and verification tests.
- Short executive summary at the end.

## Quality Bar

Enforce these requirements:
- Use concrete evidence with file references and line numbers where available.
- Include reproduction steps for security/performance/edge findings when feasible.
- Prefer actionable fixes over abstract advice.
- Separate confirmed defects from speculative risks.
- Mark confidence for each finding.
- Run a cross-route consistency sweep: equivalent endpoints/jobs must enforce equivalent invariants.
- For each High/Critical finding, include at least one focused regression test/check.

## Safety and Policy Guardrails

Apply these guardrails while auditing:
- Do not provide operational abuse instructions or exploit weaponization details.
- Evaluate manipulative UX patterns as legal/trust/reputation risk, not as recommended growth tactics.
- Prioritize user safety, system integrity, and maintainable engineering outcomes.

## Output Format

Follow this response structure:

1. Findings
List only validated issues. Use the finding schema in `references/audit-framework.md`.

2. Open Questions / Assumptions
State missing context that could change priority or validity.

3. Change Summary
Summarize high-impact remediation themes in a few lines.

4. Suggested Verification
List focused tests/checks to confirm each major fix.

## Runtime Heuristics

When the target stack is Bun + SQLite, apply the runtime-specific checklist in `references/audit-framework.md` (`Runtime-Specific Heuristics (Bun + SQLite)`) before finalizing findings.
