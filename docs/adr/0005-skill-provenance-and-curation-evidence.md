# ADR-0005: Skill provenance and curation evidence

- Status: Accepted
- Date: 2026-07-28

## Context

Catalog inclusion proves that a tracked physical Skill exists, not that it is original, safely licensed, useful, or runtime-verified. Existing author, source, homepage, and registry metadata are inconsistent and often incomplete. Removed-link tombstones intentionally contain unresolved source fields.

The taxonomy previously also owned a featured list. That mixed outcome classification with promotion and allowed structurally invalid or high-risk Skills to appear as suggested starting points.

## Decision

Maintain two authored contracts:

- `config/skill-provenance.json` owns reviewed `project-original`, `adapted`, `collected`, or `unknown` origin evidence.
- `config/skill-curation.json` owns digest-matched reviews, selection status, limitations, and the separately named **Curation evidence score**.

Unreviewed inventory defaults to `Unknown` and `Unscored`. Taxonomy no longer owns featured Skills. A selected review requires reviewed non-Unknown provenance, structural validity, no pending execution review, and a score of at least 75.

Skill-tree digest changes make provenance review stale and hide the curation number. Runtime evidence remains a separate status governed by ADR-0003 receipts.

## Consequences

- Original authorship is never inferred from a Git committer or free-form author field alone.
- Collected and adapted claims require a pinned upstream repository, subpath, commit, and license.
- Catalog and Agent indexes can expose honest origin and evidence labels without making generated outputs authoritative.
- The score is not a runtime-success, safety, compatibility, or business-outcome guarantee.
- Promotion becomes intentionally sparse until provenance and outcome evidence improve.
