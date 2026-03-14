# Product Manager Skills - Growth & Promotion Plan

> Generated 2026-03-05. Based on deep research across ClawHub ecosystem, competitor analysis, and channel strategy.

---

## Executive Summary

**Current state:** 2 installs, 1 star, "Suspicious" security rating (now fixed in v0.1.1).

**Core insight:** ClawHub has 3,286 skills but only 151 in the Business category (smallest). Post-ClawHavoc (341 malicious skills purged), trust is the #1 concern. Your skill is pure Markdown with no scripts -- this is a structural advantage. The PM skill market on ClawHub has only 3 competitors, none with significant traction.

**Strategy:** Fix foundation issues (Week 1) -> Multi-channel distribution launch (Weeks 2-4) -> Community & partnerships (Weeks 5-8).

**90-day targets:** 500 installs, 50 stars, #1 search rank for "product manager."

---

## Current Status

| Metric | Value |
|--------|-------|
| ClawHub Slugs | `product-manager-skills` + `pm-agent` (duplicate, must consolidate) |
| Installs | 2 (total across both slugs) |
| Stars | 1 |
| Version | 0.1.1 |
| Security Scan | Pending re-scan (v0.1.1 fixes "Suspicious" flag) |
| package.json name | `pm-agent-skill` (mismatch with slug and repo name) |

### Competitive Landscape

| Competitor | Platform | Scale | Weakness |
|-----------|----------|-------|----------|
| deanpeters/Product-Manager-Skills | GitHub | 1.1k stars, 46 frameworks | 46 separate installs; no ClawHub presence |
| ivangdavila/product-manager | ClawHub | v1.0.0 | Generic description; no tags |
| 1kalin/afrexai-product-manager | ClawHub | v1.0.0, 9 tags | New; unproven |

### Your Unique Advantages

1. **"One skill, six domains"** -- single install vs. 46 separate skills
2. **AI Product Craft domain** -- no competitor covers context engineering, agent orchestration
3. **32 SaaS metrics with exact formulas** -- not summaries, actual calculation logic
4. **Career coaching (PM to CPO)** -- unique in the market
5. **Opinionated agent** -- pushes back, labels assumptions, detects 50+ anti-patterns
6. **Pure Markdown, zero scripts** -- maximum trust signal in post-ClawHavoc era
7. **3 interaction modes** -- guided, context dump, best guess

### Content Inventory

| Category | Count |
|----------|-------|
| Knowledge domains | 6 |
| Templates | 10 |
| Routing table entries | 40+ |
| Named frameworks | 25+ |
| SaaS metrics with formulas | 32 |
| Anti-patterns catalogued | 50+ |
| Story/epic splitting patterns | 17 (8 + 9) |
| Career transition frameworks | 4 |
| Prioritization frameworks | 6+ |

---

## Part 1: Foundation Fixes (Week 1)

### 1.1 Consolidate Duplicate Slugs

You have THREE different names for the same product:
- `product-manager-skills` (ClawHub slug #1, repo name)
- `pm-agent` (ClawHub slug #2, v1.1.0 with 16 tags)
- `pm-agent-skill` (package.json name)

**Actions:**
1. Keep `product-manager-skills` as the canonical slug (more descriptive for vector search)
2. Fix `package.json` name to match: `product-manager-skills`
3. Re-publish with consolidated tags from `pm-agent`

```bash
# Fix package.json name, then publish
clawhub publish . --slug product-manager-skills --version 0.2.0 \
  --tags "latest,pm,prd,user-story,roadmap,saas-metrics,positioning,discovery,jtbd,epic,finance,career-coaching,ai-product,context-engineering,prioritization,product-manager" \
  --changelog "Consolidate slugs; add full tag set; include all knowledge and template files"
```

### 1.2 Optimize Description for Vector Search

ClawHub uses **OpenAI text-embedding-3-small** for search. Write natural, intent-rich descriptions -- not keyword stuffing.

**Optimized SKILL.md description:**
```
Senior product manager agent with 6 knowledge domains, 10 templates, and 30+ frameworks. Covers the full PM lifecycle: discovery interviews (JTBD, Mom Test, opportunity mapping), strategy (Geoffrey Moore positioning, PESTEL, TAM/SAM/SOM), artifacts (PRD, user stories, epics, press release/PRFAQ), 32 SaaS metrics with formulas (MRR/ARR/NRR/CAC/LTV/Rule of 40), career coaching (PM to Director to VP to CPO), and AI product craft (context engineering, agent orchestration). Opinionated -- pushes back on bad framing, labels assumptions, detects anti-patterns. Three interaction modes: guided, context dump, best guess.
```

### 1.3 Verify Security Scan

After v0.1.1 re-scan completes, expected results:
- Purpose & Capability: PASS (files now bundled)
- Instruction Scope: PASS (references match bundled files)
- Install Mechanism: PASS (instruction-only)
- Credentials: PASS (none requested)
- Persistence & Privilege: PASS (no escalation)

**Positioning opportunity:** Post-ClawHavoc, explicitly call out your trust profile:
> "Zero scripts. Zero dependencies. Zero network calls. Pure Markdown knowledge -- inspect every line before you install."

### 1.4 Fix package.json Name Mismatch

```json
{
  "name": "product-manager-skills",
  "version": "0.2.0"
}
```

### 1.5 Add GitHub Topics

Add these topics to the GitHub repo settings (up to 20):
```
claude-code, openclaw-skill, product-management, product-manager, prd,
user-story, roadmap, saas-metrics, ai-agent, jtbd, positioning,
discovery, prioritization, career-coaching, ai-product, skill-md,
claude-skills, pm-tools, frameworks
```

---

## Part 2: README Rewrite (Week 1)

The README is the #1 conversion surface on both GitHub and ClawHub. Current README is minimal.

### Target Structure

```
1. Hero: One-liner + install command + badges (version, license, installs)
2. "What It Does": 6 domains as a table with concrete examples
3. Quick Start: 3 copy-paste prompts that demonstrate immediate value
4. Framework Inventory: Full list of 30+ frameworks (your biggest differentiator)
5. Template Gallery: All 10 templates listed
6. Demo: GIF or screenshot of real output
7. Why This Skill: Comparison vs. generic ChatGPT / vs. separate skill files
8. Trust & Security: "Zero scripts, zero dependencies" statement
9. Contributing / Feedback
```

### Key Messaging to Include

**Hook (first line):** "Not a template pack -- a PM brain. One install gives you 6 knowledge domains, 30+ frameworks, and an agent that pushes back when your thinking is sloppy."

**Three demo prompts for Quick Start:**
1. "Help me write a PRD for a notification preferences feature"
2. "My SaaS has MRR $50k, monthly churn 8%, CAC $500. Diagnose."
3. "I'm a senior PM preparing for Director interviews. Coach me."

---

## Part 3: Multi-Platform Distribution (Weeks 2-3)

### 3.1 Skill Marketplaces (Publish to ALL)

| Platform | URL | Status | Action |
|----------|-----|--------|--------|
| ClawHub | clawhub.ai | Published v0.1.1 | Upgrade to v0.2.0 with tags |
| SkillHub | skillhub.club | Not listed | Submit (7,000+ skills, AI-rated) |
| SkillsMP | skillsmp.com | Not listed | Submit (350,000+ aggregated skills) |
| LobeHub | lobehub.com/skills | Auto-indexed | Verify listing after ClawHub publish |
| Anthropic Skills | github.com/anthropics/skills | Not listed | Submit PR if accepting community skills |

### 3.2 Curated Lists (Submit PRs)

| List | Stars | Category for Your Skill | Priority |
|------|-------|------------------------|----------|
| VoltAgent/awesome-openclaw-skills | High | Productivity & Tasks | P0 |
| sundial-org/awesome-openclaw-skills | Medium | Productivity | P0 |
| hesreallyhim/awesome-claude-code | High | Agent Skills | P0 |
| travisvn/awesome-claude-skills | Medium | Skills | P1 |
| ComposioHQ/awesome-claude-skills | Medium | Skills | P1 |
| ComposioHQ/awesome-claude-plugins | Medium | Plugins | P2 |

**PR description template:**
```markdown
- [product-manager-skills](https://clawhub.ai/Digidai/product-manager-skills) - Senior PM agent with 6 knowledge domains (discovery, strategy, delivery, finance, career, AI product craft), 30+ frameworks, 10 templates, and 32 SaaS metrics with formulas. Single install, zero scripts.
```

### 3.3 PM-Specific Directories

| Directory | URL | Action |
|-----------|-----|--------|
| prodmgmt.world/claude-code | prodmgmt.world | Email to get listed in their 180+ curated PM skills |
| ccforpms.com | ccforpms.com | Contact -- they teach Claude Code specifically to PMs |
| awesome-skills.com | awesome-skills.com | Submit to web directory |
| awesomeclaude.ai | awesomeclaude.ai | Submit to Claude resources directory |

---

## Part 4: Content Marketing (Weeks 2-6)

### 4.1 Channel Strategy

#### Tier 1 -- Launch Week (Week 2)

| Channel | Content | Format | Goal |
|---------|---------|--------|------|
| **X/Twitter** | Builder story thread | 8-10 tweets + demo GIF | 50+ retweets |
| **LinkedIn** | "I gave Claude Code a PM brain" | Personal narrative + screenshots | 5,000+ impressions |
| **r/ClaudeAI** | Tool showcase | Post with demo | 50+ upvotes |
| **r/ProductManagement** | "Open-sourced a PM agent -- feedback welcome" | Community ask | 30+ comments |

#### Tier 2 -- Amplification (Weeks 3-4)

| Channel | Content | Format | Goal |
|---------|---------|--------|------|
| **Dev.to** | "Architecture of a 130KB PM Knowledge System" | Technical deep-dive | SEO + 200 reactions |
| **Medium** | "Why Generic AI Fails at Product Management" | Thought leadership | 1,000+ reads |
| **r/SaaS** | "Free tool: AI that calculates 32 SaaS metrics" | Value-first post | Cross-audience |
| **X/Twitter** | SaaS metrics thread | Thread + calculator demo | Finance PM audience |

#### Tier 3 -- Scaling (Weeks 5-8)

| Channel | Content | Format | Goal |
|---------|---------|--------|------|
| **Hacker News** | "Show HN: Open-source PM agent skill" | Show HN post | Front page attempt |
| **YouTube/Loom** | Full walkthrough video | 5-min demo | Evergreen traffic |
| **Product Hunt** | Launch | Full PH campaign | Top 5 of day |
| **Newsletters** | Pitch to Lenny, TLDR, SVPG | Outbound email | Feature/mention |

### 4.2 Content Pieces (Detailed)

#### X/Twitter Thread #1: Builder Story (Week 2)
```
1/ I built an AI product manager. Not a chatbot that recites PM advice
   -- an agent that thinks like a senior PM.

   6 knowledge domains. 30+ frameworks. 32 SaaS metrics with exact
   formulas. One install.

   Here's what I learned building it: [thread]

2/ The core insight: generic AI is terrible at PM work.

   Ask ChatGPT to write a PRD and you get a template filled with
   platitudes. Ask it about churn and it says "reduce churn by
   improving the user experience."

   That's not PM thinking. That's word completion.

3/ So I built a routing system. When you say "write a PRD," it
   doesn't just generate text -- it loads the PRD framework, applies
   quality gates, labels assumptions, and pushes back if your
   problem statement embeds a solution.

   [screenshot of pushback example]

4/ The finance module alone took a week. 32 SaaS metrics, each with:
   - Exact formula (not "multiply by 12" for annual churn)
   - Stage-specific benchmarks (early/growth/scale)
   - Red flag severity tiers
   - Decision logic

   [screenshot of metric output]

5/ Most surprising module: Career coaching.

   PM -> Director -> VP -> CPO. Each transition has a framework,
   failure modes, and diagnostic questions.

   "Hero Syndrome" is when a new Director keeps doing IC work
   instead of building systems. The agent catches this.

6/ It's also the only PM skill I know of with an AI Product Craft
   domain. Context engineering, agent orchestration, AI validation
   -- the stuff 2026 PMs actually need.

7/ Zero scripts. Zero dependencies. Pure Markdown knowledge.

   Post-ClawHavoc, I wanted something you can inspect in 5 minutes.
   Every line is readable. No hidden behavior.

8/ Try it:
   clawhub install product-manager-skills

   Then ask: "My SaaS has MRR $50k, churn 8%, CAC $500. Diagnose."

   [link to ClawHub listing]
```

#### LinkedIn Post #1: Narrative + Demo (Week 2)
```
I gave Claude Code a PM brain. Here's what happened.

As a PM, I got tired of explaining my process to AI every time.
"Use the RICE framework." "Apply Geoffrey Moore positioning."
"Don't forget to label assumptions."

So I built a skill that already knows all of this.

6 knowledge domains:
- Discovery & Research (JTBD, interviews, opportunity mapping)
- Strategy & Positioning (Moore, PESTEL, TAM/SAM/SOM)
- Artifacts & Delivery (PRD, user stories, epics)
- Finance & Metrics (32 SaaS metrics with formulas)
- Career & Leadership (PM to Director to CPO)
- AI Product Craft (context engineering, agent patterns)

The part that surprised me most: it pushes back.

Ask it to write a PRD for "a dashboard" and it'll flag that as
Solution Smuggling -- embedding a solution in the problem statement.

Ask it about a "better user experience" and it'll demand a
measurable outcome with a number, direction, and timeframe.

That's not a template filler. That's a PM.

It's open source, free, and takes 10 seconds to install:
clawhub install product-manager-skills

What would you want an AI PM co-pilot to do?

#ProductManagement #AI #ClaudeCode #SaaS
```

#### Reddit r/ClaudeAI Post (Week 2)
```
Title: Built an OpenClaw skill that turns Claude into a senior PM
       with 30+ frameworks -- zero scripts, pure knowledge

I've been using Claude Code for PM work and got frustrated with
re-explaining frameworks every session. So I built a skill that
pre-loads PM knowledge.

What it includes:
- 6 domains: discovery, strategy, delivery, finance, career,
  AI product craft
- 30+ frameworks (JTBD, Geoffrey Moore, RICE, Kano, etc.)
- 10 templates (PRD, user stories, positioning, roadmaps, etc.)
- 32 SaaS metrics with exact formulas and benchmarks
- 3 interaction modes: guided Q&A, context dump, or best guess

What makes it different from just prompting:
- Routing table: it matches your intent to the right framework
  automatically
- Quality gates: every output gets checked for unlabeled
  assumptions, unmeasurable outcomes, vague personas
- It pushes back on bad PM practice (solution smuggling, metrics
  theater, feature factory, etc.)

Security: zero scripts, zero dependencies, pure Markdown. You can
read every line in 10 minutes.

Install: clawhub install product-manager-skills
Repo: github.com/Digidai/product-manager-skills

Happy to hear feedback -- especially on what frameworks or
templates are missing.
```

---

## Part 5: Community & Partnerships (Weeks 3-8)

### 5.1 Strategic Outreach

| Partner | Contact Method | Value Exchange |
|---------|---------------|----------------|
| prodmgmt.world | Email/contact form | Free inclusion in their 180+ curated PM skills list |
| ccforpms.com | Email | Feature in their Claude Code for PMs course material |
| Product School | LinkedIn/email | Free resource for their AI PM certification students |
| Lenny's Newsletter | Submission form | Pitch as tool review: "AI PM co-pilot with 32 SaaS metrics" |
| SVPG (Silicon Valley Product Group) | Blog pitch | Guest post on AI-native PM workflows |
| Mind the Product | Community submission | Share in community tools section |
| OpenClaw Discord | discord.gg/clawd | Engage, share skill, gather feedback |
| X OpenClaw Community | x.com/i/communities/2013441068562325602 | Post announcements |

### 5.2 Cross-Skill Integration Guides

Create short guides showing your PM skill + popular skills working together:

| Combo | Use Case | Content |
|-------|----------|---------|
| PM + `github` skill (10.6k installs) | "Write user stories -> auto-create GitHub issues" | Blog post + demo |
| PM + `summarize` skill (11k installs) | "Summarize research -> feed into discovery framework" | Tutorial |
| PM + Linear MCP | "PRD -> Linear tickets with acceptance criteria" | Integration guide |
| PM + Notion MCP | "Roadmap -> Notion database" | Integration guide |

### 5.3 GitHub Community

- Enable GitHub Discussions on the repo
- Seed threads: "What PM framework is missing?", "Show your best output", "Feature requests"
- Label issues with `good-first-issue` for contributors
- Add CONTRIBUTING.md with clear guidelines

---

## Part 6: Product Improvements for Growth

### 6.1 Content Gaps to Fill (from deep analysis)

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Add worked examples (end-to-end: problem -> PRD) | High (onboarding) | Medium | P0 |
| Add competitive analysis template | Medium (missing deliverable) | Low | P1 |
| Add Lean UX Canvas template | Medium (referenced but missing) | Low | P1 |
| Add stakeholder update template | Medium (career module references it) | Low | P1 |
| Add A/B testing / experimentation depth | Medium (thin coverage) | Medium | P2 |
| Consider MIT license for commercial adoption | High (CC-BY-NC-SA blocks enterprise) | Decision | P2 |

### 6.2 Feature Roadmap for Growth Metrics

| Feature | Growth Lever | Effort |
|---------|-------------|--------|
| Sample outputs in README | Conversion rate | Low |
| "PM Daily Standup" mode | Retention (daily use) | Medium |
| OKR / goal-setting module | Quarterly cadence | Medium |
| Multi-language (zh-CN, ja) | New markets | Medium |
| Integration guides (Linear, Notion, Jira) | Ecosystem play | Medium |
| Streamlit demo app | Try-before-install | High |

### 6.3 License Decision

Current: **CC BY-NC-SA 4.0** -- blocks commercial use.

Impact: Any PM using this at work (i.e., for their employer) is technically in violation. This limits:
- Enterprise adoption
- Word-of-mouth from professional PMs
- Inclusion in commercial toolkits

**Recommendation:** Consider switching to MIT or Apache 2.0 for maximum adoption, or CC BY-SA 4.0 (removes non-commercial restriction while keeping attribution).

---

## Part 7: Metrics & Tracking

### Growth Targets

| Metric | Now | 30 days | 60 days | 90 days |
|--------|-----|---------|---------|---------|
| ClawHub installs | 2 | 50 | 200 | 500 |
| ClawHub stars | 1 | 10 | 25 | 50 |
| GitHub stars | 0 | 30 | 100 | 200 |
| Security scan | Suspicious | Clean | Clean | Clean |
| Search rank ("product manager") | #2 | #1 | #1 | #1 |
| Curated list inclusions | 0 | 3 | 5 | 6+ |
| Content pieces published | 0 | 4 | 8 | 12 |

### Tracking Method

```bash
# Check installs (after ClawHub supports it)
clawhub inspect product-manager-skills

# Monitor search rank
clawhub search "product manager"
```

---

## Part 8: Execution Timeline

### Week 1: Foundation
- [ ] Fix package.json name to `product-manager-skills`
- [ ] Consolidate to single slug; publish v0.2.0 with full tags
- [ ] Update SKILL.md description (vector search optimized)
- [ ] Verify security scan passes on v0.2.0
- [ ] Add GitHub topics (20 keywords)
- [ ] Rewrite README (hero, quick start, framework inventory, trust statement)
- [ ] Create 2 demo GIFs (PRD generation + SaaS diagnostic)
- [ ] Add worked example to README

### Week 2: Distribution Launch
- [ ] Submit PRs to 4+ curated lists (awesome-openclaw-skills, awesome-claude-code, etc.)
- [ ] Publish to SkillHub and SkillsMP
- [ ] Contact prodmgmt.world and ccforpms.com
- [ ] Post X/Twitter thread #1 (builder story)
- [ ] Post LinkedIn article #1 (narrative + demo)
- [ ] Post in r/ClaudeAI and r/ProductManagement

### Week 3: Amplification
- [ ] Publish Dev.to article (technical architecture)
- [ ] Post X/Twitter thread #2 (SaaS metrics angle)
- [ ] Post r/SaaS (metrics calculator angle)
- [ ] Record and post 5-min demo video
- [ ] Engage with every comment/feedback

### Week 4: Partnerships + Content
- [ ] Reach out to PM education partners (Product School, etc.)
- [ ] Create integration guide (PM skill + Linear MCP)
- [ ] Post X/Twitter thread #3 (career ladder angle)
- [ ] LinkedIn article #2 (workflow demo)
- [ ] Join and engage in OpenClaw Discord

### Weeks 5-6: Scale
- [ ] Analyze which channels drove most installs; 2x invest in top 2
- [ ] Attempt Show HN post
- [ ] Medium thought leadership piece
- [ ] Fill template gaps (competitive analysis, Lean UX Canvas)
- [ ] Pitch to newsletters (Lenny, TLDR)

### Weeks 7-8: Sustain
- [ ] Consider Product Hunt launch
- [ ] Publish cross-skill integration guides
- [ ] Add features based on community feedback
- [ ] Enable GitHub Discussions; seed community
- [ ] Review and update growth targets

---

## Appendix: All Key URLs

### Your Assets
| Resource | URL |
|----------|-----|
| ClawHub listing | https://clawhub.ai/Digidai/product-manager-skills |
| ClawHub listing (duplicate) | https://clawhub.ai/Digidai/pm-agent |
| GitHub repo | https://github.com/Digidai/product-manager-skills |

### Marketplaces to Publish To
| Platform | URL |
|----------|-----|
| ClawHub | https://clawhub.ai |
| SkillHub | https://skillhub.club |
| SkillsMP | https://skillsmp.com |
| LobeHub | https://lobehub.com/skills |
| Anthropic Skills | https://github.com/anthropics/skills |

### Curated Lists to Submit To
| List | URL |
|------|-----|
| VoltAgent/awesome-openclaw-skills | https://github.com/VoltAgent/awesome-openclaw-skills |
| sundial-org/awesome-openclaw-skills | https://github.com/sundial-org/awesome-openclaw-skills |
| hesreallyhim/awesome-claude-code | https://github.com/hesreallyhim/awesome-claude-code |
| travisvn/awesome-claude-skills | https://github.com/travisvn/awesome-claude-skills |
| ComposioHQ/awesome-claude-skills | https://github.com/ComposioHQ/awesome-claude-skills |

### PM Education Partners
| Partner | URL |
|---------|-----|
| prodmgmt.world | https://www.prodmgmt.world/claude-code |
| ccforpms.com | https://ccforpms.com |
| Product School | https://productschool.com |
| awesomeclaude.ai | https://awesomeclaude.ai |

### Competitors
| Competitor | URL |
|-----------|-----|
| deanpeters/Product-Manager-Skills | https://github.com/deanpeters/Product-Manager-Skills |
| ivangdavila/product-manager | https://clawhub.ai/ivangdavila/product-manager |
| 1kalin/afrexai-product-manager | https://clawhub.ai/1kalin/afrexai-product-manager |

### Community Channels
| Channel | URL |
|---------|-----|
| OpenClaw Discord | https://discord.gg/clawd |
| X OpenClaw Community | https://x.com/i/communities/2013441068562325602 |
| ClawHub Docs | https://docs.openclaw.ai/tools/clawhub |
