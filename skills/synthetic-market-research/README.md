# synthetic-market-research

AI agent skill for fast, cheap market research using synthetic survey responses and [Semantic Similarity Rating (SSR)](https://github.com/pymc-labs/semantic-similarity-rating).

Test product concepts, pricing, and purchase intent in minutes instead of weeks, at $0 per respondent. Based on [PyMC Labs' validated methodology](https://arxiv.org/html/2510.08338v1) — 90% correlation with real human responses across 57 consumer surveys.

## How It Works

1. Define your research question (purchase intent, pricing, concept appeal)
2. The skill generates demographic personas matching your target market
3. An LLM role-plays each persona and writes a natural-language reaction to your concept
4. SSR converts free-text responses into probability distributions over a Likert scale
5. You get segment-level breakdowns, overall scores, and qualitative themes

The key insight from the paper: asking an LLM for a number (1-5) gives poor results. Asking for free text and then mapping it to a scale via embedding similarity achieves 90% correlation with real humans.

## Installation

### Option 1: npx (recommended)

```bash
npx skills add BayramAnnakov/synthetic-market-research
```

Add `-g` to install globally (available in all your projects):

```bash
npx skills add BayramAnnakov/synthetic-market-research -g
```

### Option 2: Manual (no Node.js required)

Clone the repo into your AI tool's skills directory:

| Tool | Personal (global) | Project-level |
|------|-------------------|---------------|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` |
| **Cursor** | `~/.cursor/skills/` | `.cursor/skills/` |
| **Windsurf** | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` |
| **Codex** | `~/.codex/skills/` | `.agents/skills/` |

Example for Claude Code (personal):

```bash
git clone https://github.com/BayramAnnakov/synthetic-market-research.git \
  ~/.claude/skills/synthetic-market-research
```

Or download the [ZIP from GitHub](https://github.com/BayramAnnakov/synthetic-market-research/archive/refs/heads/master.zip) and unzip into the appropriate directory.

### Prerequisites

The skill uses `sentence-transformers` for local SSR (no API keys needed). Install once:

```bash
pip install sentence-transformers "numpy<2"
```

## Usage

### Interactive mode
```
/synthetic-market-research
```
Walks you through: concept → personas → responses → SSR analysis → report.

### Quick mode
```
/synthetic-market-research --quick "AI tool that writes personalized cold emails for SDRs, $49/mo"
```
Runs with default personas and purchase intent scale.

### Comparative mode
```
/synthetic-market-research
> Compare concepts
```
Test 2-4 product variants, pricing tiers, or positioning options side-by-side.

## Examples

- [Product Concept Test](examples/product_concept_test.md) — Testing a B2B SaaS concept with 6 personas
- [Pricing Research](examples/pricing_research.md) — Comparing $15/$29/$49 price tiers

## When to Use

- Directional concept testing before real panels
- Comparing product variants quickly
- Early-stage pricing research
- Iterating on positioning and messaging
- Pre-screening concepts before formal research

## When NOT to Use

- Final validation before launch (always confirm with real users)
- Niche products without online discourse
- Cultural/religious nuances
- Products requiring physical experience
- Regulatory decisions

## Methodology

Based on the paper: *"LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"* by PyMC Labs.

See [references/SSR_METHODOLOGY.md](references/SSR_METHODOLOGY.md) for the full methodology reference.

## License

MIT
