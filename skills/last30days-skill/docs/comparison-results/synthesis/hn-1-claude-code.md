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
