# Skill taxonomy Gold Set

The Gold Set is a versioned semantic-evaluation sample for the catalog's single primary outcome category. It measures classification agreement; it does not establish Skill safety, quality, portability, or runtime behavior.

## Annotation source

Version 1 is manually reviewed by independent repository agents and adjudicated by the maintaining root agent. It is explicitly marked `humanApproved: false`; no page may describe it as human-verified until a maintainer reviews and signs the labels.

## Sampling

- Base revision: the merged PR #10 classifier state.
- Seed: `semantic-gold-v1`.
- Size: 10 candidates from each of 14 predicted categories, 140 total.
- Ranking: priority ties, overrides, fallbacks, and descriptions needing review are considered before ordinary rule matches; stable hashes choose within each stratum.
- Labels are never changed merely to agree with classifier output. Taxonomy rules may change after errors are reviewed.
- A stable secondary hash freezes two entries per predicted category as a published validation slice (28 total); the other 112 labels form the development slice.
- The validation slice is public and therefore is not described as an unseen or private benchmark. It is a regression check, not permission to tune individual Skill IDs.
- The exact 140-entry membership, baseline routes, and 112/28 split are covered by a fixed candidate-set digest. The evaluator rejects additions, removals, split changes, and baseline-label drift.
- A separate fixed label-set digest covers expected categories, rationales, confidence, reviewers, review status, review date, and source digest. Relabeling reviewed answers without an explicit contract change fails closed.
- The evaluator restores the recorded base catalog from Git, verifies its SHA-256, reruns the deterministic sampler, and requires exact membership, baseline routes, and splits.

## Primary-outcome rubric

1. Read the Skill entrypoint far enough to identify its promised user outcome, required inputs, and produced artifact or decision.
2. Ignore its current predicted category until after choosing a label.
3. Choose one category only. Prefer what the user receives over incidental tools, frameworks, or keywords.
4. Use `apps-workflow-automation` when controlling an external application is the central outcome; use the domain category when automation only supports a more specific outcome.
5. Use `chinese-platform-workflows` when operating a named Chinese platform is the defining workflow, not merely the audience language.
6. Use `security-privacy-legal` for assurance, legal constraints, privacy, or risk review; use `software-engineering` when security is only one implementation concern.
7. Use `finance-trading-markets` for valuation, trading, portfolios, market risk, or financial operations; do not collapse these into generic data analysis.
8. Use `general-utilities` only when no more specific primary outcome fits.

Record a concrete rationale, confidence, reviewer identifiers, source digest, and disagreement status. Low-confidence and cross-category cases must be cross-reviewed or adjudicated rather than silently omitted.

## Metrics and release gate

- Exact accuracy must be at least 0.80.
- Macro-F1 across all 14 categories must be at least 0.80.
- Every category must appear in Gold labels.
- Published-validation exact accuracy must be at least 0.75.
- Published-validation macro-F1 must be at least 0.75 and every category must remain represented.
- The report publishes the 95% Wilson lower bound for reviewed-set agreement as uncertainty evidence. Because the sample deliberately overrepresents difficult routes, that bound is not an inventory-wide accuracy interval.
- `reviewedSetAgreementScore` is the floored minimum of accuracy and macro-F1, multiplied by 100. A failed gate cannot be reported as 80+.

Build or check the generated report:

```bash
npm run build:taxonomy-evaluation
npm run check:taxonomy-evaluation
```
