# awesome-claude-code Submission

> NOTE: This repo currently has a temporary ban on OpenClaw-related submissions.
> Our skill is primarily a Claude Code skill (GitHub-hosted, works without OpenClaw).
> Submit once the ban is lifted, or frame as a Claude Code skill, not an OpenClaw skill.

## Submission URL
https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml

## Fields to fill

**Resource Name:** Product Manager Skills

**Resource URL:** https://github.com/Digidai/product-manager-skills

**Author Name:** Gene Dai

**Author URL:** https://github.com/Digidai

**Category:** Agent Skills > General

**Description:**
A senior product manager agent skill for Claude Code. One install loads 6 knowledge domains (discovery, strategy, delivery, finance, career coaching, AI product craft), 30+ frameworks (JTBD, Geoffrey Moore, RICE/Kano, 8 story splitting patterns, 9 epic breakdown patterns), 10 templates (PRD, user stories, roadmaps, etc.), and 32 SaaS metrics with exact formulas and benchmarks. The skill routes user intent to the right framework via a 40+ entry routing table, applies quality gates, labels assumptions, and pushes back on bad PM practice (solution smuggling, metrics theater, feature factory). Three interaction modes: guided Q&A, context dump, or best guess. Pure Markdown, zero scripts, zero dependencies, no network calls.

**How to validate:**
1. Clone https://github.com/Digidai/product-manager-skills
2. Copy the SKILL.md, knowledge/, and templates/ directories into any Claude Code project
3. Ask Claude: "My SaaS has MRR $50k, monthly churn 8%, CAC $500. Diagnose my business health."
4. Observe: Claude loads the finance-metrics.md module, calculates annual churn (63%), flags it as critical, computes LTV:CAC ratio, and delivers a structured diagnostic with severity ratings and next steps
5. Ask: "Write a PRD for a notification preferences feature" -- observe framework-driven output with labeled assumptions and quality gates applied

**License:** CC BY-NC-SA 4.0
