# Evaluation Framework

Use this framework for technology or framework selection in product R&D.

## Default Dimensions

| Dimension | What To Evaluate | Typical Questions |
|---|---|---|
| Business fit | Product stage and use case fit | Does it match MVP, scale-up, or platform stage needs? |
| Architecture fit | Fit with current system style | Modular monolith, microservices, event-driven, data-heavy? |
| Team capability fit | Learning curve and hiring reality | Can the team adopt and operate it reliably? |
| Delivery speed | Initial and ongoing productivity | Does it accelerate shipping and reduce cognitive load? |
| Runtime and scalability | Performance and resource profile | Are there known limits? What still needs benchmarking? |
| Operability and observability | Deploy, debug, trace, upgrade | Is day-2 operation mature? |
| Security and compliance | Security controls and deployment options | Are RBAC, audit, self-hosting, and compliance needs covered? |
| Ecosystem maturity | Community, docs, integrations, release discipline | Is it stable enough for the intended risk profile? |
| Migration cost | Adoption cost from current state | Data migration, pipeline migration, retraining, lock-in? |
| Long-term evolution | 2-3 year viability | Release notes, roadmap, standards alignment, ecosystem momentum |

## Candidate Universe First

Before building a weighted matrix, map the market by category. Weak evaluations often compare too few tools from one category and ignore adjacent but decision-relevant substitutes.

For each report, answer:

1. What is the full candidate universe worth mentioning?
2. Which 2-4 options are in the scored shortlist?
3. Why were the other important options excluded from scoring?

Typical categories:

- same-paradigm direct competitors
- adjacent-paradigm substitutes
- managed vs self-hosted variants
- incumbent option such as keeping the current stack

## Scoring Guidance

Use 1-5 unless the user specifies otherwise:

- `5`: strong fit with low concern
- `4`: good fit with manageable tradeoffs
- `3`: mixed fit, depends on context
- `2`: weak fit, serious tradeoffs
- `1`: poor fit for this decision

## Weighting Guidance

Default weights should reflect the scenario. Pre-built JSON weight files are available in `references/` and can be passed directly to `build_decision_matrix.py` as the `weights` field:

- **MVP or startup product** → `references/weights-mvp.json`
- **Core business system** → `references/weights-core-business.json`
- **Platform engineering or shared infrastructure** → `references/weights-platform.json`

All weight files sum to 100. If the user provides custom weights, use those instead.

## ATAM-Style Tradeoff Prompts

For each leading option, explicitly list:

- Risks: what may go wrong
- Non-risks: what is already well-supported
- Sensitivity points: assumptions that heavily affect outcome
- Tradeoff points: where one quality attribute is improved by weakening another

## Required Negative Space

Every final report should include:

- `Non-fit scenarios`: where this technology is a poor default choice
- `Important cautions`: what teams often underestimate before adoption

## Evidence Labels

Use these labels inside the report:

- `Verified`: supported by current source
- `Inference`: reasoned from sources
- `Needs PoC`: cannot be responsibly concluded from documents alone
