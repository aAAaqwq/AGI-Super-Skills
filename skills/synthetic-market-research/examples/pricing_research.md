# Example: Pricing Research

## Research Question
"At what price point does a premium project management tool for remote teams lose purchase intent? Testing $15/mo, $29/mo, and $49/mo per user."

## Concept Description
**FlowSpace** — A project management tool built specifically for async remote teams. Features: timezone-aware task scheduling, async video standups, AI meeting summaries, automatic progress reports. Replaces Slack+Asana+Loom with one integrated tool.

## Method: Comparative Mode

Testing 3 price tiers with the same persona set for fair comparison.

## Personas

| # | Age | Income | Location | Profile |
|---|-----|--------|----------|---------|
| 1 | 29 | $75K | Portland | Remote software engineer, IC at a 50-person startup |
| 2 | 38 | $130K | Austin | Engineering manager, leads a distributed team of 12 |
| 3 | 45 | $90K | Boise | Operations manager at a mid-size company, newly remote |
| 4 | 26 | $55K | Philadelphia | Junior PM, first remote job, manages 2 small projects |
| 5 | 34 | $110K | Seattle | Product manager, uses 5+ tools daily, integration fatigue |

## Results by Price Tier

### $15/month per user

| Persona | P(1) | P(2) | P(3) | P(4) | P(5) | E[score] |
|---------|------|------|------|------|------|----------|
| 1 (Engineer, 29) | 0.02 | 0.04 | 0.15 | 0.38 | 0.41 | 4.12 |
| 2 (EM, 38) | 0.01 | 0.03 | 0.10 | 0.35 | 0.51 | 4.32 |
| 3 (Ops, 45) | 0.03 | 0.08 | 0.22 | 0.40 | 0.27 | 3.80 |
| 4 (Jr PM, 26) | 0.02 | 0.06 | 0.18 | 0.42 | 0.32 | 3.96 |
| 5 (PM, 34) | 0.01 | 0.04 | 0.12 | 0.36 | 0.47 | 4.24 |

**Overall Mean: 4.09** | Strong purchase intent across all segments.

### $29/month per user

| Persona | P(1) | P(2) | P(3) | P(4) | P(5) | E[score] |
|---------|------|------|------|------|------|----------|
| 1 (Engineer, 29) | 0.03 | 0.08 | 0.22 | 0.38 | 0.29 | 3.82 |
| 2 (EM, 38) | 0.02 | 0.05 | 0.15 | 0.40 | 0.38 | 4.07 |
| 3 (Ops, 45) | 0.05 | 0.12 | 0.30 | 0.35 | 0.18 | 3.49 |
| 4 (Jr PM, 26) | 0.06 | 0.14 | 0.28 | 0.34 | 0.18 | 3.44 |
| 5 (PM, 34) | 0.02 | 0.06 | 0.18 | 0.40 | 0.34 | 3.98 |

**Overall Mean: 3.76** | Still positive but noticeable drop from $15. Budget-constrained personas (Jr PM, Ops) show the steepest decline.

### $49/month per user

| Persona | P(1) | P(2) | P(3) | P(4) | P(5) | E[score] |
|---------|------|------|------|------|------|----------|
| 1 (Engineer, 29) | 0.08 | 0.15 | 0.30 | 0.30 | 0.17 | 3.33 |
| 2 (EM, 38) | 0.04 | 0.08 | 0.20 | 0.38 | 0.30 | 3.82 |
| 3 (Ops, 45) | 0.10 | 0.20 | 0.32 | 0.28 | 0.10 | 3.08 |
| 4 (Jr PM, 26) | 0.12 | 0.22 | 0.30 | 0.25 | 0.11 | 3.01 |
| 5 (PM, 34) | 0.05 | 0.10 | 0.22 | 0.38 | 0.25 | 3.68 |

**Overall Mean: 3.38** | Neutral territory. Two personas drop below 3.1 — significant purchase resistance.

## Price Sensitivity Summary

| Tier | Mean Score | Delta from $15 | Interpretation |
|------|-----------|-----------------|----------------|
| $15/mo | 4.09 | — | Strong intent. "Easy yes" for most segments. |
| $29/mo | 3.76 | -0.33 | Positive but requires justification. Budget personas hesitate. |
| $49/mo | 3.38 | -0.71 | Neutral. Budget and mid-level personas show resistance. |

## Segment-Level Price Sensitivity

**Most price-sensitive** (largest drop $15 → $49):
- Junior PM (26, $55K): 3.96 → 3.01 (delta: -0.95)
- Ops Manager (45, $90K): 3.80 → 3.08 (delta: -0.72)

**Least price-sensitive** (smallest drop):
- Engineering Manager (38, $130K): 4.32 → 3.82 (delta: -0.50)
- Product Manager (34, $110K): 4.24 → 3.68 (delta: -0.56)

## Recommendations

1. **$29/mo is the sweet spot** — maintains positive intent (3.76) while capturing 2x revenue vs $15. The drop is modest and concentrated in budget-constrained segments.

2. **Consider tiered pricing** — $15 for ICs/small teams, $29 for managers, $49 for enterprise with advanced features. This captures the full demand curve.

3. **$49 is viable only for high-value personas** — Engineering managers and PMs still show interest at $49, suggesting an enterprise tier is possible with additional features (SSO, admin controls, analytics).

4. **"Replaces 3 tools" is the key justification** — At $29, buyers need to see clear savings vs. Slack ($8) + Asana ($13) + Loom ($15) = $36. Position the bundle savings prominently.

5. **Free trial reduces price sensitivity** — Multiple personas across all tiers expressed "I'd want to try it first." A 14-day trial could shift the $29 and $49 distributions rightward.

## Limitations

- Synthetic pricing sensitivity follows broad patterns but may not capture:
  - Competitor-specific switching costs
  - Organizational procurement processes (budget approvals, security reviews)
  - Existing contract lock-ins
- Real Van Westendorp or Gabor-Granger study recommended before finalizing pricing
- Only U.S.-based personas — international pricing may differ significantly
