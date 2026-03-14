# Social Media Content Pack

## X/Twitter Thread #1: Builder Story

Thread (copy each as a separate tweet):

---

**Tweet 1:**
I built an AI product manager. Not a chatbot that recites PM advice -- an agent that thinks like a senior PM.

6 knowledge domains. 30+ frameworks. 32 SaaS metrics with exact formulas. One install.

Here's what I learned building it:

---

**Tweet 2:**
The core insight: generic AI is terrible at PM work.

Ask ChatGPT to write a PRD and you get a template filled with platitudes. Ask it about churn and it says "reduce churn by improving the user experience."

That's not PM thinking. That's word completion.

---

**Tweet 3:**
So I built a routing system. When you say "write a PRD," it doesn't just generate text -- it loads the PRD framework, applies quality gates, labels assumptions, and pushes back if your problem statement embeds a solution.

That's called Solution Smuggling. The agent catches it.

---

**Tweet 4:**
The finance module alone took a week. 32 SaaS metrics, each with:

- Exact formula (not "multiply by 12" for annual churn)
- Stage-specific benchmarks (early/growth/scale)
- Red flag severity tiers
- Decision logic

"Your 8% monthly churn = 63% annual. That's critical."

---

**Tweet 5:**
Most surprising module: Career coaching.

PM -> Director -> VP -> CPO. Each transition has a framework, failure modes, and diagnostic questions.

"Hero Syndrome" is when a new Director keeps doing IC work instead of building systems. The agent catches this.

---

**Tweet 6:**
It's also the only PM skill I know of with an AI Product Craft domain.

Context engineering, agent orchestration, AI validation -- the stuff 2026 PMs actually need.

---

**Tweet 7:**
Zero scripts. Zero dependencies. Pure Markdown knowledge.

Post-ClawHavoc, I wanted something you can inspect in 5 minutes. Every line is readable. No hidden behavior.

---

**Tweet 8:**
Try it:

clawhub install product-manager-skills

Then ask: "My SaaS has MRR $50k, churn 8%, CAC $500. Diagnose."

GitHub: github.com/Digidai/product-manager-skills
ClawHub: clawhub.ai/Digidai/product-manager-skills

---

## LinkedIn Post #1: Narrative + Demo

---

I gave Claude Code a PM brain. Here's what happened.

As a PM, I got tired of explaining my process to AI every time. "Use the RICE framework." "Apply Geoffrey Moore positioning." "Don't forget to label assumptions."

So I built a skill that already knows all of this.

6 knowledge domains:
- Discovery & Research (JTBD, interviews, opportunity mapping)
- Strategy & Positioning (Moore, PESTEL, TAM/SAM/SOM)
- Artifacts & Delivery (PRD, user stories, epics)
- Finance & Metrics (32 SaaS metrics with formulas)
- Career & Leadership (PM to Director to CPO)
- AI Product Craft (context engineering, agent patterns)

The part that surprised me most: it pushes back.

Ask it to write a PRD for "a dashboard" and it'll flag that as Solution Smuggling -- embedding a solution in the problem statement.

Ask it about a "better user experience" and it'll demand a measurable outcome with a number, direction, and timeframe.

That's not a template filler. That's a PM.

It's open source, free, and takes 10 seconds to install:

clawhub install product-manager-skills

Or copy the files from GitHub:
github.com/Digidai/product-manager-skills

What would you want an AI PM co-pilot to do?

#ProductManagement #AI #ClaudeCode #SaaS #ProductManager

---

## Reddit r/ClaudeAI Post

---

**Title:** Built a Claude Code skill that turns Claude into a senior PM with 30+ frameworks -- zero scripts, pure knowledge

**Body:**

I've been using Claude Code for PM work and got frustrated with re-explaining frameworks every session. So I built a skill that pre-loads PM knowledge.

**What it includes:**
- 6 domains: discovery, strategy, delivery, finance, career, AI product craft
- 30+ frameworks (JTBD, Geoffrey Moore, RICE, Kano, etc.)
- 10 templates (PRD, user stories, positioning, roadmaps, etc.)
- 32 SaaS metrics with exact formulas and benchmarks
- 3 interaction modes: guided Q&A, context dump, or best guess

**What makes it different from just prompting:**
- Routing table: it matches your intent to the right framework automatically
- Quality gates: every output gets checked for unlabeled assumptions, unmeasurable outcomes, vague personas
- It pushes back on bad PM practice (solution smuggling, metrics theater, feature factory, etc.)

**Security:** Zero scripts, zero dependencies, pure Markdown. You can read every line in 10 minutes.

**Install:**

    clawhub install product-manager-skills

**Repo:** github.com/Digidai/product-manager-skills

Happy to hear feedback -- especially on what frameworks or templates are missing.

---

## Reddit r/ProductManagement Post

---

**Title:** I open-sourced a PM agent skill for Claude Code -- turns AI into a senior PM co-pilot with 32 SaaS metrics, JTBD, positioning frameworks, and career coaching

**Body:**

I've spent the last few weeks building something I've wanted for a while: a PM knowledge system that plugs into Claude Code and actually thinks like a PM instead of just filling templates.

**The problem I was solving:** Every time I used AI for PM work, I had to re-explain my frameworks, remind it to label assumptions, and push it to be specific. I wanted an agent that already knows these things.

**What it covers (6 domains):**

1. **Discovery & Research** -- JTBD framework, customer interview prep (Mom Test-inspired), opportunity solution trees, PoL probes for validation
2. **Strategy & Positioning** -- Geoffrey Moore positioning, PESTEL analysis, TAM/SAM/SOM, 6 prioritization frameworks (RICE, ICE, Kano, etc.), roadmap planning
3. **Artifacts & Delivery** -- PRD development, user stories with Gherkin criteria, 8 story splitting patterns, 9 epic breakdown patterns, PRFAQ
4. **Finance & Metrics** -- 32 SaaS metrics with EXACT formulas (not "multiply monthly churn by 12"), stage-specific benchmarks, red flag severity tiers
5. **Career & Leadership** -- PM to Director transition (Altitude-Horizon Framework), Director to VP/CPO (Three Ps), 30-60-90 executive onboarding
6. **AI Product Craft** -- AI-Shaped readiness assessment, context engineering, agent orchestration

**The thing I'm most proud of:** It pushes back. Ask it to write a PRD for "a dashboard" and it flags Solution Smuggling. Ask about "better user experience" and it demands a measurable outcome with a number, direction, and timeframe. It detects 50+ anti-patterns including Metrics Theater, Feature Factory, and HiPPO Prioritization.

**Try it:**

    clawhub install product-manager-skills

Or just grab the files: github.com/Digidai/product-manager-skills

It's pure Markdown -- no scripts, no dependencies. You can read the entire thing in 10 minutes.

Would love feedback from this community: what's missing? What frameworks do you wish an AI PM co-pilot knew?

---

## Reddit r/SaaS Post

---

**Title:** Free tool: AI agent that calculates 32 SaaS metrics with exact formulas (MRR, ARR, NRR, CAC, LTV, Rule of 40, and more)

**Body:**

Built an open-source Claude Code skill that includes a finance module with 32 SaaS metrics. Each metric has:

- **Exact formula** (e.g., Annual Churn = 1 - (1 - Monthly)^12, not the common mistake of Monthly x 12)
- **Stage-specific benchmarks** (early-stage / growth / scale)
- **Red flag severity** (watch / warning / critical)
- **Decision logic** for what to do when metrics are off

You can just paste your numbers and ask: "My SaaS has MRR $50k, monthly churn 8%, CAC $500, LTV $3,000. Diagnose."

It'll calculate your annual churn (63% -- critical), LTV:CAC ratio (6:1 -- looks good but payback period matters), Rule of 40 score, and give you a prioritized action plan.

The metrics covered:

**Revenue:** MRR, ARR, MoM Growth, Net New MRR, Quick Ratio
**Unit Economics:** CAC, LTV, LTV:CAC, Payback Period, Gross Margin
**Retention:** Logo Churn, Revenue Churn, NRR, Gross Revenue Retention
**Efficiency:** Rule of 40, Burn Multiple, Magic Number, Sales Efficiency
**Engagement:** DAU/MAU, Activation Rate, Time-to-Value, NPS

Install: `clawhub install product-manager-skills`
Repo: github.com/Digidai/product-manager-skills

Free, open source, pure Markdown. Also includes 30+ other PM frameworks if you need PRDs, user stories, positioning, etc.

---

## Dev.to Article Outline

---

**Title:** Building an AI Product Manager: Architecture of a 130KB Knowledge System

**Tags:** ai, productmanagement, claudecode, architecture

**Outline:**

1. **The Problem** -- Why generic AI fails at PM work (with before/after examples)
2. **The Architecture** -- How 18 Markdown files turn into a senior PM agent
   - Routing table: intent matching to frameworks
   - On-demand loading: why not dump everything into context
   - Quality gates: two-tier checking system
   - Interaction protocol: three modes
3. **The Finance Module Deep Dive** -- How to encode 32 metrics with formulas, benchmarks, and decision logic
4. **Anti-Pattern Detection** -- Teaching AI to push back on bad PM practice
5. **What I Learned** -- Compression for context windows, the "persist vs. retrieve" decision, why templates should be scaffolding
6. **Try It** -- Install instructions + 3 demo prompts
