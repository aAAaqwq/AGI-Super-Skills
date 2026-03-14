---
title: "Building an AI Product Manager: Architecture of a 130KB Knowledge System"
published: false
description: "How 18 Markdown files, 40+ intent mappings, and zero scripts turn Claude into a senior PM agent that pushes back on sloppy thinking."
tags: ai, productmanagement, claudecode, architecture
cover_image:
canonical_url:
---

## The Problem

Ask ChatGPT to write a PRD and you get this:

> **Goal:** Improve the user experience for notifications.
> **Success Metrics:** Increased user satisfaction and engagement.
> **Target Users:** Users who receive notifications.

That is a PRD-shaped void. No persona specificity, no measurable outcome, no tradeoffs named. "Users who receive notifications" is not a persona. "Increased satisfaction" is not a metric.

Now ask an agent loaded with domain-specific PM knowledge:

> **Goal:** Reduce notification fatigue so mid-market ops managers running 3+ product lines can surface critical alerts without disabling the channel entirely.
> **Success Metric:** Reduce notification-disabled rate from 34% to 15% within Q3. `[assumption: 34% baseline from Oct analytics]`
> **Tradeoff:** Prioritizing quiet-by-default over engagement metrics — expect 20% drop in notification-driven DAU.

The difference is not better prompting. It is structured knowledge: what a good PRD requires, what quality gates to enforce, what anti-patterns to flag. Generic LLMs have broad knowledge but no depth. They do not know that "improve UX" fails the measurable-outcome gate, or that embedding "we need a dashboard" in a problem statement is Solution Smuggling. A domain-specific agent does.

The question is: how do you encode PM expertise into something an LLM can actually use?

## The Architecture

The system is 18 Markdown files totaling ~130KB. No scripts, no dependencies, no API calls. The architecture has four layers.

### Routing Table: 40+ Intent-to-Framework Mappings

When a user says something, the agent matches intent to a specific framework and knowledge module. The routing table is a simple lookup:

```markdown
| User Intent                        | Framework              | Load                          |
|------------------------------------|------------------------|-------------------------------|
| "Validate a problem"               | Problem Framing + PoL  | knowledge/discovery-research.md |
| "Write a PRD"                      | PRD Development        | knowledge/artifacts-delivery.md |
| "SaaS metrics" / "MRR" / "ARR"    | SaaS Revenue Metrics   | knowledge/finance-metrics.md    |
| "Position my product"              | Geoffrey Moore          | knowledge/strategy-positioning.md |
| "PM to Director"                   | Altitude-Horizon        | knowledge/career-leadership.md  |
| "Context engineering"              | Context Engineering     | knowledge/ai-product-craft.md   |
```

Six knowledge domains. Each domain file is 12-17KB of compressed frameworks, decision logic, formulas, and quality gates. The routing table lives in `SKILL.md` — the orchestration brain.

### On-Demand Loading: Token Economics

Why not dump all 130KB into context? Because tokens are money and attention. A question about churn does not need the 15KB career-leadership module. On-demand loading means the agent reads only the relevant module when routed, keeping context focused and costs down. In pre-loaded environments (Claude Projects), the content is already available — the agent searches by section name instead of loading files.

### Quality Gates: Two-Tier Checking

Every output passes through two layers:

1. **Universal gates** (in SKILL.md) — apply to all outputs: assumptions must be labeled, outcomes must be measurable, roles must be specific, tradeoffs must be named.
2. **Domain-specific gates** (in each knowledge module) — apply when that module is active. The finance module flags vanity metric traps and blended metric dangers. The discovery module catches leading questions and prototype theater.

### Interaction Protocol: Three Modes

The agent adapts to how much context the user provides:

- **Guided mode** — asks one question at a time with progress labels (`Q1/6`, `Q2/6`). Best for discovery and diagnostics.
- **Context dump** — user pastes everything; agent fills gaps and delivers.
- **Best guess** — agent infers missing details, marks every inference with `[assumption]`, delivers immediately.

The user chooses. If they say "just do it," the agent defaults to best guess with labeled assumptions.

## The Finance Module Deep Dive

The finance module (`knowledge/finance-metrics.md`) encodes 32 SaaS metrics across four categories: Revenue & Growth, Unit Economics, Retention & Expansion, and Capital Efficiency. Each metric has three components: the exact formula, stage-specific benchmarks, and red flag severity.

Take churn. Most people multiply monthly churn by 12. That is wrong. Churn compounds:

```
Annual Churn = 1 - (1 - Monthly)^12
```

At 3% monthly, that is ~31% annual — not 36%. At 5% monthly, it is ~46% annual. At 8% monthly (a number I have seen teams shrug at), it is **63% annual**. The module encodes this formula and flags the multiply-by-12 error explicitly under "Common Calculation Errors."

Benchmarks are stage-specific, not one-size-fits-all:

| Metric | Early (<$10M ARR) | Growth ($10-50M) | Scale ($50M+) |
|--------|-------------------|-------------------|---------------|
| Growth YoY | >50% | >40% | >25% |
| NRR | — | >100% | >110% |
| Gross Margin | >70% | — | — |
| Rule of 40 | — | >40 | >40 |
| Runway | >12 months | — | positive cash flow |

Red flags are tiered by severity. **Critical (fix immediately):** runway <6 months, LTV:CAC <1.5:1, churn accelerating cohort-over-cohort, NRR <90%. **High priority (fix within quarter):** Rule of 40 <25, payback >24 months, Quick Ratio <2. The agent does not just report metrics — it diagnoses them against these thresholds and recommends action: scale aggressively, fix before scaling, urgent intervention, or survival mode.

A critical insight the module encodes: `4:1 LTV:CAC with 36-month payback is a cash trap. 3:1 LTV:CAC with 8-month payback is better for growth.` Ratios without payback context are vanity metrics.

## Anti-Pattern Detection

The agent does not just answer questions — it pushes back. Seven universal anti-patterns are baked into the quality gates:

1. **Solution Smuggling** — problem statements that embed a solution ("We need a dashboard" instead of "Managers can't see team velocity")
2. **Metrics Theater** — tracking metrics that look good but drive no decisions
3. **Feature Factory** — shipping features without validating the problem first
4. **Stakeholder-Driven Roadmap** — roadmap shaped by the loudest voice, not evidence
5. **Confirmation Bias in Discovery** — interview questions designed to confirm existing beliefs
6. **Premature Scaling** — optimizing growth before unit economics work
7. **Horizontal Slicing** — splitting work by architecture layer instead of user value

Here is what this looks like in practice:

> **User:** "The problem is we don't have a real-time analytics dashboard."
>
> **Agent:** That is Solution Smuggling — your problem statement embeds a specific solution. Let me reframe: what outcome are your users unable to achieve? If managers cannot see team velocity, the problem statement becomes: "Engineering managers running 3+ squads need a way to assess cross-team velocity weekly because current reporting requires manual aggregation from 4 tools, which takes 3 hours and is often stale by the time it is compiled." Now we can evaluate dashboards, automated reports, Slack digests, or other solutions on their merits.

Each knowledge domain adds 10-40 more domain-specific anti-patterns on top of the universal set.

## Lessons Learned

**Compression beats verbosity for context windows.** The finance module packs 32 metrics with formulas, benchmarks, and decision logic into 14KB. That is roughly 4,000 tokens. A textbook covering the same material would be 50-100 pages. The trick: tables over prose, formulas over explanations, decision thresholds over general advice. Every sentence must earn its tokens.

**Persist the routing table, retrieve the knowledge.** The routing table and interaction protocol live in SKILL.md — always loaded, always available. The six knowledge modules are retrieved on demand. This is the persist-vs-retrieve decision: routing logic is cheap and needed on every request; domain knowledge is expensive and needed selectively.

**Templates are scaffolding, not boilerplate.** The 10 templates are not fill-in-the-blank forms. They are structural scaffolding that the agent fills with the user's specific context, applying quality gates as it goes. A PRD template without quality gates produces the same platitudes as generic AI. The template plus the framework plus the gates — that combination is what produces useful output.

**Markdown is the right format.** No YAML configs, no JSON schemas, no custom DSLs. LLMs parse Markdown natively. Tables, headers, and code blocks give structure without overhead.

## Try It

Install in one command:

```bash
clawhub install product-manager-skills
```

Or upload `SKILL.md` plus `knowledge/` and `templates/` folders to a Claude Project.

Three prompts to test drive:

1. `"Help me write a PRD for a notification preferences feature"` — watch it ask the right questions, not fill a template
2. `"My SaaS has MRR $50k, monthly churn 8%, CAC $500. Diagnose my business health."` — get a full diagnostic with severity ratings
3. `"I'm preparing a problem statement. The problem is we don't have a mobile app."` — watch it catch Solution Smuggling in real time

18 files. 130KB. Zero dependencies. A PM agent that thinks, not just templates.

If it saves you time, [star it on GitHub](https://github.com/Digidai/product-manager-skills).
