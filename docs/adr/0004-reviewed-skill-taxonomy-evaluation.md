# ADR-0004: Reviewed Skill taxonomy evaluation

- Status: Accepted
- Date: 2026-07-21

## Context

The generated catalog previously used broad, equal-weight regular expressions and category priority as a semantic tie-break. A deterministic result was reproducible, but it did not establish that the primary outcome category agreed with manual review. Substring matches such as `data` in Datadog and `defi` in “define” created systematic errors.

## Decision

Maintain a fixed, category-balanced Gold Set of 140 independently reviewed labels. Its exact membership, baseline routes, and published 112/28 development/validation split are protected by a candidate-set digest and fail-closed evaluator checks.

Taxonomy schema v2 separates high-precision `outcomePatterns` from legacy keyword `patterns`. The classifier considers outcome phrases across the Skill ID and source description first, but a single conflicting phrase cannot replace an existing slug route; it requires agreement with that route or at least two outcome signals. Exact overrides remain bounded exceptions with written rationales.

Publish a `reviewedSetAgreementScore` only when exact accuracy, macro-F1, category coverage, and the published-validation gate pass. The score is not called human-verified while `humanApproved` is false, and it is not an inventory-wide confidence interval or runtime-quality score.

## Consequences

- Category changes receive deterministic, inspectable evidence rather than priority-only justification.
- Gold membership cannot be expanded or re-split to inflate the score without changing an explicit contract.
- Changed `SKILL.md` entrypoints invalidate their labels until they are reviewed again.
- The public validation slice is a regression check, not a permanently unseen benchmark.
- Safety, portability, runtime behavior, and business value remain separate evidence domains.
