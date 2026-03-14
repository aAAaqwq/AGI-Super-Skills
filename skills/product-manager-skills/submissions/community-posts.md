# Community Posts -- Ready to Post

---

## 1. Hacker News "Show HN" Post

**Title:** Show HN: A 130KB Markdown file that turns Claude Code into an opinionated senior PM

**Body:**

I got tired of AI giving me "it depends" answers when I asked it product management questions. So I built a SKILL.md file -- pure Markdown, zero scripts, zero dependencies -- that turns Claude Code (or Cursor, Windsurf, Codex) into an opinionated PM agent with real domain knowledge.

The architecture is intentionally boring. A single SKILL.md file acts as a router: it maps 40+ user intents to 6 knowledge modules loaded on demand from a `knowledge/` directory. Each module contains frameworks, decision trees, quality gates, and anti-pattern detectors. There are 12 templates in a `templates/` directory. Total system: ~130KB across 20 Markdown files. No build step, no runtime, no API calls. You can read every line before installing.

What makes it different from just prompting "act like a PM": the knowledge modules encode actual domain logic. The finance module has 32 SaaS metrics with exact formulas and stage-specific benchmarks. Ask it about 8% monthly churn and it doesn't say "that's high" -- it computes `1 - (1 - 0.08)^12 = 63%` annual churn, flags it as a red severity indicator, and tells you the benchmark for your stage. The discovery module enforces Mom Test principles and catches "Solution Smuggling" (sneaking a solution into a problem statement). The artifacts module has 8 story splitting patterns and 9 epic breakdown patterns, not just a template to fill in.

The quality gate system is the part I'm most interested in feedback on. Every output passes through universal gates (assumptions must be labeled, outcomes must be measurable, no "Feature Factory" outputs) plus domain-specific gates loaded from the active knowledge module. The agent is designed to push back -- if you ask for a PRD without a clear problem statement, it will challenge you rather than generate filler.

Tradeoffs worth noting: it's CC BY-NC-SA 4.0, not MIT, since the knowledge modules represent significant curation work. It's also opinionated by design, which means it won't work well if you want a yes-machine. And it's optimized for Claude Code's SKILL.md convention -- it works in other editors that support Markdown skills but the routing system is tuned for Claude's context window management.

GitHub: https://github.com/Digidai/product-manager-skills

Install: `clawhub install product-manager-skills`

---

## 2. Indie Hackers Post

**Title:** I built a Markdown file that turns AI coding assistants into a senior PM -- here's what I learned

**Body:**

Six months ago I noticed a pattern: every time I asked Claude or GPT to help with PM work, I spent more time fixing the output than I would have spent writing it myself. PRDs full of platitudes. "Reduce churn by improving user experience." Strategy advice that was a Wikipedia summary of Porter's Five Forces.

The problem isn't that LLMs are bad at PM work. It's that they lack the domain-specific knowledge to be good at it. They don't know that 8% monthly churn compounds to 63% annual. They don't know the difference between a user story and a task. They can't tell you your LTV:CAC ratio is unhealthy for your stage.

So I built product-manager-skills: a pure Markdown knowledge system that loads into Claude Code (or Cursor, Windsurf, Codex) as a SKILL.md file. No scripts, no dependencies, no API calls. Just structured PM knowledge that an AI agent can actually use.

**What's in it:**
- 6 knowledge domains: discovery, strategy, artifacts, finance/metrics, career coaching, AI product craft
- 30+ frameworks applied to your specific context (not just recited)
- 32 SaaS metrics with exact formulas and stage-specific benchmarks
- 12 templates for PRDs, user stories, positioning statements, press releases, etc.
- Anti-pattern detection: Solution Smuggling, Metrics Theater, Feature Factory
- 3 interaction modes: guided (one question at a time), context dump, best guess

**The architecture decision that made it work:** Instead of one massive prompt, SKILL.md acts as a router. It maps 40+ user intents to knowledge modules loaded on demand. This means the AI only loads the finance module when you ask about metrics, keeping the context window focused.

**What I learned building it:**
1. Structured knowledge beats clever prompting. A well-organized Markdown file with decision trees outperforms a 2000-word system prompt every time.
2. Quality gates matter more than templates. The agent pushing back on sloppy thinking is more valuable than generating perfect-looking documents.
3. Pure Markdown is a feature, not a limitation. Zero dependencies means zero trust issues. Users can read every line before installing.

The whole thing is ~130KB across 20 files. Free and open source (CC BY-NC-SA 4.0).

**Try it:**
```
clawhub install product-manager-skills
```

Then ask: "My SaaS has MRR $50k, monthly churn 8%, CAC $500. Diagnose my business health."

GitHub: https://github.com/Digidai/product-manager-skills

Would love feedback from other PMs or indie hackers who use AI in their workflow. What PM tasks do you wish AI was better at?

---

## 3. Claude Discord Post (#share-your-projects)

**Body:**

Hey everyone -- I built a SKILL.md that turns Claude Code into an opinionated senior PM agent. It covers the full PM lifecycle: discovery interviews, strategy, PRDs, user stories, 32 SaaS metrics with exact formulas, career coaching (PM to CPO), and AI product craft. Pure Markdown, zero dependencies, ~130KB.

The thing I'm most proud of: it pushes back on bad thinking instead of just generating filler. It catches anti-patterns like Solution Smuggling (hiding a solution in a problem statement) and Metrics Theater (tracking vanity metrics). Every assumption gets labeled. Every output gets quality-gated.

Install and try it:
```
clawhub install product-manager-skills
```

Some prompts to start with:
- "Help me write a PRD for [your feature idea]"
- "My SaaS has MRR $50k, monthly churn 8%, CAC $500. Diagnose my business health."
- "I'm a senior PM preparing for Director interviews. Coach me."

Free and open source -- https://github.com/Digidai/product-manager-skills. Feedback welcome!

---

## 4. Product Coalition (Medium) Article Pitch

**Subject:** Guest post pitch: Why your AI PM assistant is giving you bad advice (and what to do about it)

**Body:**

Hi Product Coalition team,

I'd like to pitch a guest post: "Why Your AI PM Assistant Is Giving You Bad Advice -- And a 130KB Fix."

The angle: most PMs using ChatGPT/Claude for PM work get generic outputs because LLMs lack structured domain knowledge. I built an open-source Markdown skill file that encodes 30+ PM frameworks, 32 SaaS metrics with exact formulas, and anti-pattern detection into a system that runs inside Claude Code. The article would walk through three concrete before/after examples (churn diagnosis, PRD quality, career coaching) and explain the architecture pattern of "knowledge-augmented AI agents" that other PMs could apply to their own domains.

Target: 1,500 words. I can deliver within a week of approval.

Gene Dai
https://github.com/Digidai/product-manager-skills

---

## 5. AI Tool Directory Submission Template

Use this template to submit to AIxploria, Toolify, OpenTools, TheAISurf, FutureTools, There's An AI For That, AI Tool Guru, TopAI.tools, AiToolHunt, and similar directories.

---

**Tool Name:** Product Manager Skills

**One-Line Description:** Open-source SKILL.md that turns Claude Code into an opinionated senior PM agent with 30+ frameworks and 32 SaaS metrics.

**Full Description (150-300 words):**
Product Manager Skills is a pure Markdown knowledge system that transforms AI coding assistants (Claude Code, Cursor, Windsurf, Codex) into senior product management agents. Unlike generic AI prompts, it encodes deep domain knowledge: 6 knowledge domains, 30+ frameworks, 12 templates, and 32 SaaS metrics with exact formulas and stage-specific benchmarks.

The system covers the full PM lifecycle: discovery interviews (JTBD, Mom Test, opportunity mapping), strategy (Geoffrey Moore positioning, PESTEL, TAM/SAM/SOM), artifacts (PRDs, user stories, epics, press releases), finance (MRR/ARR/NRR/CAC/LTV/Rule of 40), career coaching (PM to Director to VP to CPO transitions), and AI product craft (context engineering, agent orchestration).

It is opinionated by design. It pushes back on sloppy thinking, flags anti-patterns (Solution Smuggling, Metrics Theater, Feature Factory), labels every assumption, and enforces quality gates on every output. Ask about 8% monthly churn and it computes 63% annual churn, flags it red, and gives stage-specific recommendations.

Architecture: ~130KB across 20 Markdown files. Zero scripts, zero dependencies, zero network calls. A SKILL.md router maps 40+ intents to knowledge modules loaded on demand.

**URL:** https://github.com/Digidai/product-manager-skills

**Category:** Productivity / Product Management / AI Agent Tools

**Subcategory (if applicable):** Product Management, Business Strategy, SaaS Analytics

**Pricing:** Free (open source)

**License:** CC BY-NC-SA 4.0

**Platform/Requirements:** Claude Code, Cursor, Windsurf, or Codex (any editor supporting Markdown skill files)

**Install Command:** `clawhub install product-manager-skills`

**Key Features:**
- 6 knowledge domains covering the full PM lifecycle
- 30+ frameworks applied contextually, not just recited
- 32 SaaS metrics with exact formulas and benchmarks
- 12 ready-to-use templates (PRD, user story, positioning, press release, etc.)
- Anti-pattern detection: Solution Smuggling, Metrics Theater, Feature Factory
- 3 interaction modes: guided, context dump, best guess
- Quality gates on every output (universal + domain-specific)
- Intent router mapping 40+ PM intents to knowledge modules
- Career coaching from PM to CPO with transition-specific frameworks
- AI product craft module for building AI-native products
- Pure Markdown -- zero scripts, zero dependencies, fully auditable
- Works with Claude Code, Cursor, Windsurf, and Codex

**Screenshots Description (for preparing actual screenshots):**
1. Terminal showing `clawhub install product-manager-skills` command completing successfully
2. Claude Code session: user asks "Diagnose my business health" with SaaS metrics, agent returns a formatted scorecard with severity ratings, computed annual churn, and red flags
3. Claude Code session: user asks for a PRD, agent pushes back asking for a problem statement first instead of generating filler
4. The SKILL.md routing table showing the 40+ intent mappings across 6 domains
5. A finance diagnostic output showing the 32 metrics with formulas, benchmarks, and color-coded health indicators

**Tags/Keywords:** product management, PM tools, SaaS metrics, PRD, user stories, Claude Code, AI agent, SKILL.md, frameworks, strategy, discovery, career coaching, open source

**Author:** Gene Dai

**Social Links:** https://github.com/Digidai
