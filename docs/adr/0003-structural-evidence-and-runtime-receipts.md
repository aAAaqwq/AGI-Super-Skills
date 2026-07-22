# ADR-0003: Structural evidence and runtime receipts

- Status: Accepted
- Date: 2026-07-21

## Context

Repository tests can prove deterministic structure, safe copy behavior, and generated-output freshness. They cannot by themselves prove semantic skill quality, business outcomes, or compatibility with every harness.

## Decision

Structural evidence and runtime evidence are separate scorecards. A runtime claim requires a receipt naming commit SHA, package or harness version, fixture, checks, result, and limitations. A webpage may display `Verified` only when its receipt matches the current main commit and every required check passed.

## Consequences

- Architecture-classification contract scores are not runtime scores.
- Skill catalog inclusion is not a safety or compatibility claim.
- Missing, stale, or mismatched receipts degrade to `Validation pending`.
- Runtime fixtures and external beta receipts remain release gates, not documentation decorations.
