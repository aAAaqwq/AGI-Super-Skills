# Evaluation: Claude Code skills and MCP servers

**Query Type:** GENERAL
**Label Map (REVEAL AFTER SCORING):** {'A': 'hn', 'B': 'base', 'C': 'cross'}

## Evaluation Rubric

Score each version 1-5 on these dimensions:

### 1. GROUNDEDNESS (30%)
Does the narrative cite specific sources from the research data?
- 1: Generic statements, no citations, could be written without any research
- 3: Some citations but mixed with pre-existing knowledge filler
- 5: Every finding backed by a specific source ("per @handle", "per r/sub", "per [channel]")

### 2. SPECIFICITY (25%)
Are findings specific (named entities, exact numbers) or vague?
- 1: Vague generalities ("AI video tools are improving", "developers are debating frameworks")
- 3: Some specifics mixed with generic padding
- 5: Named products, exact numbers, version names ("Seedance 2.0 added lip sync", "698 likes")

### 3. COVERAGE (20%)
Does the synthesis represent findings from all available data sources?
- 1: Only mentions 1-2 sources, ignores others
- 3: Mentions most sources but unevenly weighted
- 5: Naturally weaves Reddit, X, YouTube (and HN if available) into the narrative

### 4. ACTIONABILITY (15%)
Does the invitation give specific, research-derived next steps?
- 1: Generic "let me know if you want more info"
- 3: Somewhat specific but not clearly grounded in research findings
- 5: Each suggestion references a specific thing from the research ("I can compare Seedance 2.0 vs Kling")

### 5. FORMAT COMPLIANCE (10%)
Does it follow the expected output format?
- 1: Missing stats block, no invitation, wrong structure
- 3: Partial stats block, generic invitation
- 5: Perfect stats block with real counts, source box-drawing chars, top voices identified


---
## VERSION A

What I learned:

Claude Code skills and MCP servers are at an inflection point - the community is building so fast that infrastructure tooling (sandboxes, marketplaces, directories) is appearing alongside the skills themselves. @ihtesham2005 highlighted Anthropic open-sourcing their internal Skills library, and Hacker News is seeing a steady stream of Show HN projects building on this layer.

**Specialized skill packs are the new open-source project type** - Builders are shipping domain-specific skill bundles: a 55K-word email marketing knowledge base (hn/cosmoblk, 10pts), 12 SEO skills for Claude Code (r/ClaudeCode), and AI marketing skills (hn/superamped). These aren't generic - they embed deep domain knowledge into SKILL.md files.

**Security and sandboxing are emerging concerns** - SkillSandbox (hn/ClaytheMachine) is a Rust-based capability sandbox for AI agent skills, and Gulama (hn/san-techie21) pitches itself as a "security-first" OpenClaw alternative. As skills get more powerful, the HN crowd is asking hard questions about what they should be allowed to do.

**MCP is becoming a framework target, not just a protocol** - Upjack (hn/barefootsanders) is a declarative framework for building apps over MCP, and the GTM MCP Server (hn/paolobietolini) lets AI manage Google Tag Manager containers. MCP is evolving from "connect tools to Claude" into "build entire products on top of MCP."

**Agent orchestration is the next layer up** - Axon (hn/gjkim042) provides Kubernetes-native orchestration for AI coding agents, and hn/alternateman built tooling to turn Claude Code or Codex into proactive 24/7 agents. The pattern is skills for single tasks, orchestration for workflows, infrastructure for always-on agents.

**Skill discovery is an unsolved problem** - Indx.sh (hn/micronink) is a directory of AI coding rules, MCP servers, and tools. ClawsMarket (hn/digitcatphd) is a marketplace where AI agents discover tools. @ghumare64 uses a dedicated tool to sync and scan skills from the marketplace. Multiple independent attempts to solve discovery suggest it's a real pain point.

KEY PATTERNS from the research:
1. HN builders are creating infrastructure (sandboxes, frameworks, marketplaces) while Reddit/X users are creating end-user skills - the ecosystem is specializing, per hn/ClaytheMachine
2. Marketing is the breakout non-dev use case for skills - multiple independent projects across HN, Reddit, and YouTube, per hn/cosmoblk
3. Skills are going cross-platform - builders are creating skills that work with Claude Code AND Codex, per @zeeg
4. The implicit vs explicit skill invocation debate is live - Codex handles implicit well, Claude Code still needs explicit mentions, per @zeeg
5. Solo devs and small teams are the core adoption wedge - team-level skill sharing is the growth vector, per r/ClaudeCode

---
All agents reported back!
├─ 🟠 Reddit: 3 threads │ 0 upvotes │ 0 comments
├─ 🔵 X: 12 posts │ 23 likes │ 1 reposts
├─ 🔴 YouTube: 10 videos │ 520,640 views │ 3 with transcripts
├─ 🟡 HN: 15 stories │ 35 points │ 16 comments
├─ 🌐 Web: supplementary
└─ 🗣️ Top voices: @ihtesham2005 (6 likes), @zeeg (4 likes, 1 RT) │ r/ClaudeCode, r/ClaudeAI │ hn/cosmoblk (10pts)
---

I'm now an expert on Claude Code skills and MCP servers. Some things I can help with:
- Break down the SkillSandbox architecture and what capability-based security means for your skills
- Compare the emerging MCP frameworks (Upjack vs Poncho vs Fluid.sh) for different use cases
- Help you build a domain-specific skill pack like the 55K-word email marketing knowledge base


---
## VERSION B

What I learned:

The Claude Code skills ecosystem is in a rapid expansion phase, with community-built skill libraries and frameworks emerging as the dominant trend across Reddit and X this month. @ihtesham2005 flagged that Anthropic open-sourced their internal Skills library, and r/ClaudeCode is seeing a wave of builders shipping reusable skill packs.

**Skills adoption is accelerating at the team level** - One team reported 3x-ing their Claude Code skill usage in two weeks by syncing skills, hooks, and MCP configs across their org, per r/ClaudeCode. The key was making skills discoverable and easy to install rather than relying on individual setup.

**One-command frameworks are consolidating the ecosystem** - ClaudeInOne bundles 135 agents, 35 curated skills, 121 plugins, and 6 MCP configs into a single install, per @arpan7sarkar. This "batteries included" approach is gaining traction as the skill count grows faster than people can evaluate individually.

**Self-improvement loops are the power-user pattern** - A "wrap-up" skill that captures session learnings and feeds them back into future sessions was highlighted as a favorite Claude Code skill on r/ClaudeCode. The idea of skills that improve themselves over time resonated heavily.

**Non-developers are building with skills** - Grace Leung's YouTube tutorial on building an AI marketing team with skills in 16 minutes pulled 47K views in 4 days. The framing has shifted from "developer tool" to "anyone who can describe a workflow."

**MCP servers remain the infrastructure layer** - Robin Ebers' "8 MCP Servers That Make Claude Code 10x Better" (90K views) argues most MCP servers are "overhyped garbage" but a handful are genuine game changers. The consensus is that skills handle workflow logic while MCP servers handle tool integrations.

KEY PATTERNS from the research:
1. Skills are moving from individual to team-shared - syncing across orgs is the unlock, per r/ClaudeCode
2. Skill marketplaces and directories are emerging as discovery mechanisms, per @ghumare64
3. Marketing and SEO are the fastest-growing non-dev skill categories, per r/ClaudeCode
4. Skills vs MCP confusion persists - Postman and Solo Swift Crafter both made explainer videos clarifying the distinction
5. Builder skills that generate other skills are the meta-pattern, per @matgoldsborough

---
All agents reported back!
├─ 🟠 Reddit: 4 threads │ 291 upvotes │ 0 comments
├─ 🔵 X: 11 posts │ 22 likes │ 1 reposts
├─ 🔴 YouTube: 10 videos │ 461,224 views │ 3 with transcripts
├─ 🟡 HN: 0 stories (no results this cycle)
├─ 🌐 Web: supplementary
└─ 🗣️ Top voices: @ihtesham2005 (6 likes), @zeeg (4 likes, 1 RT) │ r/ClaudeCode
---

I'm now an expert on Claude Code skills and MCP servers. Some things I can help with:
- Compare the ClaudeInOne framework vs building your own skill library from scratch
- Walk through setting up a self-improvement loop skill for your workflow
- Help you decide which MCP servers are actually worth installing based on Robin Ebers' teardown


---
## VERSION C

What I learned:

The Claude Code skills and MCP ecosystem is experiencing simultaneous growth at every layer - from individual skill authoring to team-level adoption to infrastructure tooling. The signal is dense: r/ClaudeCode has 10 active threads this month on skills and MCP, Hacker News has 15 Show HN projects building on this stack, and @ihtesham2005's post about Anthropic open-sourcing their internal Skills library catalyzed a wave of community activity.

**MCP server scaling is hitting real limits** - "Claude Code works great... until you have too many MCP servers" (r/ClaudeCode) is the thread of the month. Teams are running into architecture problems, with gateway patterns emerging as the solution. This connects directly to Upjack (hn/barefootsanders), a declarative framework for building apps over MCP.

**Token efficiency is driving MCP server design** - A semantic graph MCP server cut context from 15K to 3K tokens (r/ClaudeCode), while 25 MCP servers that return structured data instead of terminal formatting emerged on r/ClaudeAI. The efficiency concern also shows up in SkillSandbox (hn/ClaytheMachine), which uses capability-based sandboxing to limit what skills can access.

**Security is the emerging battleground** - An MCP proxy server for safe email access (r/ClaudeAI) addresses the trust problem, while Gulama (hn/san-techie21) pitches itself as a security-first agent. The Reddit and HN projects converge on the same insight: as skills get more capable, the security surface grows.

**Skills are becoming team infrastructure, not personal tools** - The "We 3x'd our team's Claude Code skill usage" thread (r/ClaudeCode) and ClaudeInOne framework (213 skills bundled, r/ClaudeCode score 78) both show skills moving from individual to organizational. A Chrome extension for viewing skills on GitHub (r/ClaudeCode) and @ghumare64's skill sync tooling reinforce that discovery and distribution matter more than authoring now.

**Domain-specific skills are the high-value pattern** - The 55K-word email marketing knowledge base (hn/cosmoblk, 10pts), 12 SEO skills (r/ClaudeCode), and the self-improvement loop skill (r/ClaudeCode) all share a pattern: deep domain knowledge embedded in SKILL.md files. Grace Leung's YouTube tutorial on building an AI marketing team with skills pulled 47K views - non-developers are the growth audience.

KEY PATTERNS from the research:
1. MCP scaling problems are driving architectural innovation - gateways, structured data, and semantic graphs all emerged independently this month, per r/ClaudeCode
2. Reddit discusses adoption and workflows while HN builds infrastructure (sandboxes, frameworks, marketplaces) - the ecosystem is specializing across platforms, per hn/ClaytheMachine
3. Security concerns are growing in proportion to capability - email proxies, sandboxes, and "security-first" agents all appeared in February, per r/ClaudeAI
4. Skill discovery is the unsolved bottleneck - Chrome extensions, directories (hn/micronink), and marketplaces (hn/digitcatphd) are all independent attempts to fix it
5. Cross-platform skill portability matters - @zeeg notes Codex handles implicit skill invocation better than Claude Code, suggesting the skill format may outlive any single runtime

---
All agents reported back!
├─ 🟠 Reddit: 10 threads │ 692 upvotes │ 0 comments
├─ 🔵 X: 12 posts │ 23 likes │ 1 reposts
├─ 🔴 YouTube: 10 videos │ 465,498 views │ 3 with transcripts
├─ 🟡 HN: 15 stories │ 35 points │ 16 comments
├─ 🌐 Web: supplementary
└─ 🗣️ Top voices: @ihtesham2005 (6 likes), @zeeg (5 likes, 1 RT) │ r/ClaudeCode, r/ClaudeAI │ hn/cosmoblk (10pts)
---

I'm now an expert on Claude Code skills and MCP servers. Some things I can help with:
- Analyze the MCP scaling problem and whether a gateway approach or semantic graph server would work better for your setup
- Compare the security models across the email proxy, SkillSandbox, and Gulama approaches
- Help you build a domain-specific skill pack and distribute it through the emerging skill ecosystem


---
## SCORES

### Version A
- Groundedness: 4/5
- Specificity: 5/5
- Coverage: 3/5
- Actionability: 4/5
- Format: 4/5
- **Weighted Total**: 4.05/5.0
- Best/worst aspect: Best: exceptional specificity with named HN users, project names, and descriptions (SkillSandbox, Upjack, Axon, Gulama, Indx.sh, ClawsMarket). Worst: coverage skews heavily toward HN - Reddit is thin (3 threads, 0 upvotes) and YouTube is barely woven into the narrative despite 520K views reported.

### Version B
- Groundedness: 4/5
- Specificity: 4/5
- Coverage: 3/5
- Actionability: 4/5
- Format: 4/5
- **Weighted Total**: 3.80/5.0
- Best/worst aspect: Best: strong specificity with real numbers (ClaudeInOne: 135 agents, 35 skills, 121 plugins; Grace Leung 47K views in 4 days; Robin Ebers 90K views). Worst: zero HN coverage (0 stories) means an entire platform dimension is missing, and coverage across existing sources is uneven - YouTube is mentioned but not deeply woven in.

### Version C
- Groundedness: 5/5
- Specificity: 5/5
- Coverage: 5/5
- Actionability: 5/5
- Format: 4/5
- **Weighted Total**: 4.90/5.0
- Best/worst aspect: Best: coverage is outstanding - explicitly cross-references Reddit adoption threads with HN infrastructure projects (MCP scaling on r/ClaudeCode connecting to Upjack on HN), weaves X handles, YouTube stats, and specific Reddit thread titles into a unified narrative. Cites 10 Reddit threads, 15 HN stories, and specific numbers throughout. Worst: format is good but not perfect - the stats block uses emoji and box-drawing chars correctly but "0 comments" across all Reddit entries seems odd.

## VERDICT

**Winner for Claude Code skills and MCP servers:** Version C
**Why:** Version C achieves what the other two cannot individually - it combines the HN depth of Version A with the Reddit/YouTube specificity of Version B, then adds cross-platform connections that neither version makes on its own. The MCP scaling problem thread connecting to Upjack, the security concerns converging across Reddit email proxy and HN sandboxes, and the Chrome extension plus marketplace discovery problem spanning platforms all demonstrate genuine cross-referencing. Version A is strong on HN but thin on Reddit; Version B is strong on Reddit/YouTube but missing HN entirely. Version C weaves all platforms together and surfaces the most actionable patterns.

**Reveal:** {'A': 'hn', 'B': 'base', 'C': 'cross'}