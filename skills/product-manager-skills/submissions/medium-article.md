# Why Generic AI Fails at Product Management (and How Domain-Specific Agents Fix It)

Ask ChatGPT to write a PRD and you'll get something that looks like a PRD. It has sections. It has bullet points. It mentions stakeholders and success metrics. If you squint, it passes.

Then a senior PM reads it and starts circling problems.

## The Illusion of Competence

I've reviewed dozens of AI-generated product artifacts over the past year. The pattern is consistent: surface-level professionalism masking hollow thinking. Here's what I keep seeing.

**Vague success metrics.** "Improve user experience" or "increase engagement." No baseline, no target, no timeframe. A real metric looks like "Reduce time-to-first-value from 14 days to 3 days within Q2." The AI-generated version looks like a mission statement, not a measurable outcome.

**Unnamed personas.** "Users will benefit from this feature." Which users? A mid-market ops manager running three product lines with no dedicated analytics support has fundamentally different needs than a startup founder wearing every hat. Generic AI writes for "users" because it doesn't know how to ask who you're actually building for.

**Missing tradeoffs.** Every recommendation comes without a cost. "We should build a real-time dashboard" — but what are you not building? What's the maintenance burden? What's the opportunity cost? AI-generated PRDs present options as if they exist in a vacuum, because tradeoff analysis requires understanding constraints that weren't in the prompt.

**Unlabeled assumptions.** The output states "customers want self-service onboarding" as fact, when it's actually a hypothesis that needs validation. There's no distinction between what's known from data and what's inferred from pattern matching on training text.

**Solution smuggling.** "We need a dashboard" appears in the problem statement. That's not a problem — that's a solution wearing a problem's clothes. The actual problem might be "Managers can't see team velocity," which could be solved five different ways. Generic AI can't catch this because it doesn't know the difference.

Any of these individually is minor. Together, they produce an artifact that creates the illusion of rigor while actively misleading the team that builds from it.

## Why This Happens

Large language models are optimized for plausible text. They're trained on millions of blog posts about product management, not on the practice of product management itself. The distinction matters enormously.

A blog post says "define your success metrics." A practicing PM knows that "3% monthly churn" sounds manageable until you calculate that it compounds to 31% annual churn, not 36% — and that the difference between those two numbers reveals whether someone actually did the math or just multiplied by twelve. Generic AI will confidently multiply by twelve, because that's what most text on the internet does.

LLMs have no concept of quality gates — the checkpoints where a senior PM catches bad reasoning before it propagates. They don't verify that every "As a user" story names a specific persona instead of a generic placeholder. They don't flag when a "so that" clause merely restates the action instead of articulating the underlying motivation. They don't notice when acceptance criteria say "better experience" instead of something a QA engineer could actually test.

The deeper issue is structural. AI generates text left-to-right, optimizing for coherence with what came before. PM work is fundamentally different: you hold multiple competing constraints in your head simultaneously — technical feasibility, business viability, user desirability, timeline pressure, team capacity — and the artifact reflects the resolution of those tensions. A PRD that doesn't show tension isn't a PRD. It's a brochure.

This is why "just prompt it better" hits a ceiling fast. You can improve individual outputs with better instructions, but you can't prompt your way into systematic rigor across an entire domain. The knowledge has to live somewhere other than the prompt.

## What Domain-Specific Means

When I say domain-specific, I don't mean a long system prompt that says "You are a senior PM, be rigorous." I mean encoding the actual knowledge structures that PMs use to think.

**Routing tables that match intent to frameworks.** When someone says "validate a problem," a domain-aware agent doesn't freestyle — it loads the Problem Framing Canvas or a Proof-of-Life Probe framework. When someone says "write a user story," it applies the Mike Cohn format with Gherkin acceptance criteria and checks against eight splitting patterns from Richard Lawrence. The mapping between intent and framework is explicit, not emergent.

**Quality gates that check every output.** Not one gate — two tiers. Universal gates apply to everything: assumptions must be labeled, outcomes must be measurable, roles must be specific, tradeoffs must be named. Then domain-specific gates layer on top. For user stories: "As a" must use a specific persona, not generic "user." One When, one Then per story — multiple means you need to split. Acceptance criteria must be testable by QA, not aspirational. For PRDs: metrics must have a current baseline, a target, and a measurement timeline. These gates aren't suggestions — they're enforced on every output.

**Anti-pattern libraries that catch bad practice.** Solution smuggling. Metrics theater — tracking numbers that look good but drive no decisions. Feature factory — shipping without validating the problem. Horizontal slicing — splitting work by architecture layer instead of user value. Confirmation bias in discovery — asking questions designed to confirm what you already believe. A domain-aware agent recognizes these patterns in the user's input and names them explicitly. "That problem statement embeds a solution. The actual problem might be..."

**Interaction protocols that adapt to complexity.** Simple request? Deliver directly. Complex, multi-dimensional request? Offer guided mode (one question at a time with progress labels), context dump mode (user provides everything, agent fills gaps), or best-guess mode (agent infers, labels every assumption, user validates). This isn't UX polish — it's the difference between an agent that helps you think and one that just produces text.

The knowledge modules themselves follow a persist-versus-retrieve architecture. Core constraints and quality gates are always active. Specialized frameworks — like the nine epic breakdown patterns or the six-frame storyboard arc — load on demand when the routing table activates them. This prevents context stuffing, which degrades accuracy as the context window grows.

## The Architecture Pattern

The pattern underlying this is transferable to any domain:

**1. Route.** Match intent to the right knowledge structure. Don't dump everything into context. A routing table with clear mappings outperforms a giant system prompt every time.

**2. Load on demand.** Retrieve the specific framework, template, or decision logic needed for this request. Context engineering — treating the AI's attention as a scarce resource — beats context stuffing. Research shows that retrieval with 25% of available tokens preserves 95% of accuracy while cutting latency and cost.

**3. Apply framework-specific logic.** Don't just surface the framework — execute it. Apply the splitting patterns. Run the quality checks. Validate the metrics format. The AI should reason with the knowledge, not just recite it.

**4. Enforce quality gates and close with next steps.** Every output gets checked against both universal and domain-specific gates. Every interaction ends with decisions made, assumptions to validate, and a recommended next action. Bias to action, not summary.

This is the Research-Plan-Reset-Implement cycle applied to agent design: gather the relevant knowledge, synthesize it into a focused context, clear the noise, execute with precision.

## What Changes

When AI has genuine domain knowledge, the interaction shifts from generation to collaboration.

**Before:** You ask for a PRD. The AI writes twelve polished sections. You spend an hour finding the gaps.
**After:** The AI writes the PRD, flags three assumptions it couldn't validate, notes that your success metric has no baseline, and asks whether "enterprise customers" means 500-seat companies or 10,000-seat companies — because the answer changes the solution.

**Before:** You say "We need a recommendation engine." The AI outlines a recommendation engine.
**After:** The AI asks what problem the recommendation engine solves, notes that the request looks like solution smuggling, and suggests reframing around the user outcome: "Customers can't find relevant content in catalogs with 10,000+ items."

**Before:** You ask it to split a large epic. The AI gives you five chunks that look reasonable. Three of them are horizontal slices.
**After:** The AI applies vertical splitting patterns — each slice delivers end-to-end user value — and flags that two of the resulting stories might not be independently testable, suggesting you combine them.

The difference isn't intelligence. It's knowledge structure. The model is the same. The domain architecture changes what it can do with it.

---

I built a PM agent to test this thesis. It encodes six knowledge domains, ten templates, and over thirty frameworks into a structured skill that any Claude-based agent can load. It's open source: [github.com/dai-shi/product-manager-skills](https://github.com/dai-shi/product-manager-skills). But the bigger point is that every domain needs this — not better prompts, but structured knowledge that the AI can reason with. Legal review, sales engineering, clinical research, financial analysis — any field where "looks right" and "is right" diverge needs domain-specific agents, not generic ones with clever instructions.

The era of prompting harder is ending. The era of encoding expertise is starting.
