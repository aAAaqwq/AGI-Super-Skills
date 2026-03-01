# Review - Claude latest vs prior OpenAI-style Unum

## Bottom line

The latest Claude draft is a **better architecture document** than the earlier versions.
It is **not yet the best top-level skill** without edits.

Best merge outcome:
- keep the OpenAI-style skeptical core and generality
- import Claude's architecture and degradation patterns
- avoid Claude's tendency to hardcode too much cost and deployment detail into the primary skill

## What Claude now does better

### 1. Council and routing mechanics
Claude's latest version is much better at:
- strategic vs tactical separation
- local vs cloud routing
- graceful degradation
- hold / abstain behavior

These should be preserved.

### 2. Operating-model realism
It understands that:
- execution should stay deterministic
- cloud reasoning should not sit on the hot path
- multi-agent systems need clear handoffs

These are strong ideas.

### 3. Better use of the custom brief
Claude incorporated:
- councils
- slow brain / fast hands split
- degradation logic
- no-trade validity

Those were the right things to abstract.

## Where Claude still overshoots

### 1. Hardcoded fee assumptions
It still presents generic venue and broker fee figures in a way that can sound authoritative.
This is risky because real viability depends on the user's exact displayed fees and actual fill behavior.

### 2. Council creep
It makes council architecture feel close to the default for sophisticated systems.
That is too aggressive.
Many users should stay with:
- single bot
- deterministic logic
- one review model at design time

### 3. Too much detail in the primary file
Large model-routing and regime blocks are useful, but they belong mostly in reference files.
The top-level skill should stay directive and portable.

### 4. Some pseudo-precision
Any exact latency or hidden-cost number can age badly or be misapplied.
The skill should speak in decision rules more than pseudo-benchmarks.

## What the OpenAI-style version still does better

### 1. Simplicity
The earlier OpenAI-style version better answers:
- can this survive costs?
- what strategy family fits?
- what should be rejected quickly?

### 2. Universal portability
It is less tied to one bot architecture and easier to invoke for any user.

### 3. Better default posture
It more strongly preserves:
- passive execution first
- spot first
- small-account skepticism
- AI as assistant, not edge

## Merge rule adopted in R3

Use this priority:

1. **Skeptical decision policy** from OpenAI-style version
2. **Architecture patterns** from Claude latest
3. **Portable process control** from the custom trading brief
4. **Generic source governance** and deployment intake added in this revision

## Practical recommendation

For the next external-model round, ask them to critique these exact questions:
1. Should hardware intake be conditional or always-on?
2. Should councils live in the top-level skill or only references?
3. How should the news source registry be structured?
4. What is the smallest complete version of the skill that still feels publishable?
5. Which parts are instructions versus knowledge versus templates?
