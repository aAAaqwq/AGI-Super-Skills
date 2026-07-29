# Content Creator runbook

This runbook turns approved evidence into reviewable content and measurement artifacts. It never publishes automatically. Harness behavior and outcome quality remain **Validation pending** without a matching receipt.

## Input

Provide licensed source material, audience, channel, desired action, factual constraints, brand guidance, and prohibited claims. The core is `ceo`, `cro`, `cco`, `cmo`, and `governor`; add `cdo` when the work relies on datasets or analytics instrumentation.

## Waves

1. `ceo` fixes the outcome, owners, approval boundary, and success criteria.
2. `cro` builds the evidence map; `cdo` profiles supplied data when applicable.
3. `cco` creates channel-aware drafts from approved evidence while `cmo` defines positioning and the ethical measurement plan.
4. `governor` checks provenance, unsupported claims, platform risk, and the manual publishing gate.

Only source analysis and measurement design may run in parallel when their inputs and writable artifacts do not overlap.

## Artifacts

- Evidence brief with resolvable citations and known gaps.
- Channel-ready draft set with provenance notes.
- Measurement plan with hypothesis, metric, stop condition, and owner.
- Claims review and manual publishing checklist.

## Checks

- `sources-resolve`: cited sources are accessible and appropriate to use.
- `claims-trace-to-evidence`: material claims map to evidence or are removed.
- `channel-rules-reviewed`: consent, attribution, and platform rules are addressed.
- `manual-publish-gate-recorded`: no post or reply is sent automatically.

## Capability fallback

With native delegation, dispatch evidence, drafting, and measurement tasks as separate owned packets. Without it, route packets manually to the named role workspaces. A single-context pass may review completeness but must not be described as independent review.

## Human approval

An authorized human reviews and sends every external post, message, upload, or campaign change. Credentials, private audience data, and restricted source material stay outside the repository and task artifacts.
