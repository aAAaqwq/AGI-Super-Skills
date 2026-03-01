# Unum (Strat) - Knowledge Base

## Purpose

This file is the main policy reference for `unum-strat`.

It combines:
- the conservative, fee-first posture from the earlier OpenAI draft
- the richer architecture patterns from the newer Claude draft
- the practical deployment and council ideas abstracted from the custom trading brief

The result is meant to be:
- venue-agnostic
- asset-agnostic
- capital-scalable
- usable by a human, a single agent, or an OpenClaw-style multi-agent setup

## What the latest Claude draft improved

The latest Claude version materially improved four things:

1. **Architecture clarity**
   - better separation between strategic, tactical, and execution layers
   - clearer graceful-degradation logic
   - more explicit local vs cloud routing

2. **Operational shape**
   - stronger handoff ideas
   - better explanation of why deterministic execution should stay simple
   - more concrete signal-policy thinking

3. **Regime-awareness**
   - more explicit "hold in chop" behavior
   - stronger emphasis on no-trade as a correct output

4. **Capital scaling**
   - clearer route by account size
   - more practical parameter scaling

## What should NOT be copied blindly from the latest Claude draft

1. **Hardcoded fee tables**
   Generic tables are fine as rough intuition, but they should not override the user's actual displayed fees.

2. **Council-first bias**
   Councils are useful when the user already has a complex stack, needs slower strategic synthesis, or wants critique diversity.
   They are not required for most profitable or sensible trading systems.

3. **Too much primary-skill detail**
   Some of the large architecture blocks are better in references than in the top-level skill instructions.

4. **Too much implied precision**
   If a skill sounds too certain about fee thresholds, latency cutoffs, or broker hidden costs, it can become brittle.

## Architecture patterns worth keeping

### 1. Strategic / tactical / execution split

Portable pattern:
- strategic layer: regime, allocation, allowed playbook
- tactical layer: timing, ranking, candidate entries
- execution layer: deterministic order placement and risk controls

Why it generalizes:
- works for crypto, stocks, and other assets
- works for simple single-agent systems or multi-agent systems
- prevents expensive reasoning from sitting on the execution hot path

### 2. Graceful degradation

Good pattern:
- if strategic intelligence is stale or unavailable -> no new entries
- if tactical is degraded -> manage risk only
- if execution is degraded -> stop new orders and alert
- if market state is undefined -> abstain

This should be a default architectural principle in the skill.

### 3. Learning as constraint promotion

Good pattern:
- log repeated failures
- convert repeated failures into hard rules, filters, or warnings
- do not claim magical autonomous learning

This is the right way to borrow from "self-improving" skill ideas.

### 4. Deterministic execution

Strong general rule:
- keep the order layer as simple and testable as possible
- use AI for design, critique, classification, or slower synthesis
- avoid AI deciding every live order in real time

## Hardware and OS intake policy

### When to ask for hardware / OS
Ask only when the user wants:
- local models
- council or multi-agent deployment
- on-device inference
- sub-agent distribution across machines
- node / gateway / VPS planning
- latency-sensitive local processing
- privacy-sensitive processing

Do not ask for hardware details when the user only wants:
- a strategy idea
- a backtest review
- a code review
- a fee-aware viability check

### Minimum deployment fields to capture
- host role: laptop / desktop / home server / VPS / mixed
- OS
- CPU
- RAM
- GPU
- VRAM
- storage
- network quality
- always-on availability
- local vs remote execution preference
- whether OpenClaw browser, web tools, cron, or node host are available

### Why this matters
These fields influence:
- whether local models are realistic
- whether councils should be local, cloud, or mixed
- whether scheduled scans are safe
- whether browser-heavy collection is practical
- whether the user should keep reasoning central and execution remote

## Strategy family ranking

### A. Trend / breakout
Best default for most users.

Why:
- lower turnover
- more likely to survive fees
- portable across venues and assets
- easier to reason about and validate

Failure modes:
- whipsaw in chop
- late entries after large expansions
- poor universes with low liquidity

### B. Swing mean reversion
Conditional.

Why:
- can work on liquid instruments with moderate costs
- can be expressed simply

Failure modes:
- cheap-looking backtests that vanish under spread and slippage
- repeated small losses in trend regimes

### C. Portfolio rotation / ranking
Strong for bigger accounts.

Why:
- low turnover
- good fit for diversified universes
- easier to operate at portfolio level

Failure modes:
- weak universe design
- overfitting ranking formulas
- hidden frictions in rebalances

### D. Grid / range systems
Conditional and often overrated.

Why users like them:
- intuitive
- active
- easy to simulate

Why they fail:
- ranges break
- fees accumulate
- users assume fills without adverse selection

### E. Pair trade / stat-arb
Advanced and conditional.

Why it can work:
- relationship-based logic can be real

Why it fails:
- unstable relationships
- high execution requirements
- overlooked borrow, spread, or rebalance costs

### F. Market making
Rarely a beginner default.

Why it can work:
- spread capture is real in the right environment

Why it fails:
- inventory risk
- adverse selection
- queue-position illusions
- fee drag
- retail venue limitations

### G. Perp carry / basis
Real, but opt-in only.

Why it can work:
- not purely directional
- can have structurally identifiable drivers

Why it fails:
- funding instability
- legging risk
- liquidation mechanics
- venue risk

### H. LLM-only prediction systems
Reject by default.

Why:
- fragile
- overfit-prone
- rarely cost-aware by construction

Use AI instead for:
- hypothesis generation
- code review
- backtest critique
- regime labeling
- research summarization
- error analysis

## News and context intelligence policy

### Principle
News should usually act as:
- a filter
- a veto
- a prioritization signal
- a post-trade explanation aid

It should rarely be a direct trigger by itself.

### Source classes

#### Tier 1 - primary sources
Use first:
- exchange notices
- broker notices
- issuer filings and official IR pages
- central bank, regulator, and macro releases
- official project, protocol, or fund communications

#### Tier 2 - high-quality secondary sources
Use for broad context:
- established financial press
- well-regarded sector publications
- specialist crypto outlets with a clear editorial process

#### Tier 3 - curated social
Use only as supplemental context:
- selected X lists
- selected analysts / desks / researchers
- selected Reddit communities when used as sentiment or idea discovery only

#### Tier 4 - trend signals
Use as tertiary context:
- Google Trends or similar interest indicators
- topic-frequency shifts
- search-intent changes
- social tag frequency

### Generic source-registry design
For each asset class or venue, maintain a registry with:
- source name
- source class
- purpose
- trust level
- method: web_search / web_fetch / browser
- query template
- update cadence
- if the source is a trigger, filter, veto, or research-only input

### Collection method policy
- Use `web_search` for discovery.
- Use `web_fetch` for readable text extraction where possible.
- Use browser automation only for JS-heavy or login-gated sites.
- Prefer whitelists, query templates, and time windows.
- Avoid open-ended crawling without a source policy.
- Cache summaries and deduplicate repeated stories.

### Example generic query buckets
- official venue incident, maintenance, delisting, listing, fee, margin, custody
- issuer guidance, earnings, filing, buyback, dividend, ETF flow
- macro release, rate decision, CPI, payrolls, geopolitical escalation
- asset-specific exploit, validator outage, protocol proposal, stablecoin depeg, ETF rumor
- social momentum check with strict whitelists and keywords

### How to use social correctly
Good use:
- detect that something unusual is being discussed
- escalate to primary-source verification
- use as a risk veto or caution flag

Bad use:
- trade because a hashtag is trending
- assume repost volume equals edge
- let anonymous claims bypass verification

## Helper tools and related skill patterns

### Prefer first-class OpenClaw tools over fragile helper skills
If the runtime is OpenClaw, default to:
- web tools for search and fetch
- browser for JS-heavy or interactive sources
- cron for recurring scans
- sub-agents for parallel or heavier research
- nodes for cross-device execution
- agent routing for specialized roles

### Helper-skill ideas worth referencing, not depending on
Patterns to borrow:
- self-improving / lessons-learned capture
- research-report generation
- browser verification / screenshot confirmation

But do not make the skill dependent on third-party skills being installed.

## Missing pieces that improve completeness

### 1. Compliance and policy awareness
The skill should ask:
- is this personal use, fund use, or client use?
- are there reporting, mandate, or jurisdiction constraints?
- are there wash-sale, PDT, leverage, or restricted-instrument constraints?

### 2. Data provenance
Capture:
- where market data comes from
- how fresh it is
- whether it includes delistings, splits, or corporate actions
- how missing candles or bad ticks are handled

### 3. Audit trail
For live systems, require:
- decision logs
- order logs
- fill logs
- strategy-version IDs
- parameter snapshots

### 4. Rollback
Every live path needs:
- a kill switch
- a fallback mode
- a revert plan
- a "no new entries" mode

### 5. Session and cost budgets
For LLM-heavy architectures, capture:
- token budget
- inference budget
- maximum decision latency
- caching policy

## Decision posture

When uncertain:
- prefer fewer trades
- prefer slower systems
- prefer better instruments
- prefer deterministic execution
- prefer abstaining over forcing a signal
