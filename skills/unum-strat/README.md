# ⚡ Unum (Strat)

**Universal fee-aware trading strategy design and audit skill for OpenClaw.**

Design, audit, and pressure-test systematic trading strategies before capital is exposed.

---

## What It Does

Unum (Strat) is a universal skill for:
- **Designing** trading strategies with realistic cost modeling
- **Auditing** existing strategies for fee survival and edge validation
- **Supporting** crypto, stocks, ETFs, forex, futures, and more
- **Defaulting** to conservative spot-style execution
- **Optional** multi-agent council architecture when justified

---

## Installation

```bash
clawhub install unum-strat
```

---

## Usage

Invoke in your OpenClaw session:

```
Design a mean-reversion strategy for BTC/USDC on Coinbase with $500 capital
```

```
Audit my grid trading bot - it's underperforming in chop
```

```
What fees do I need to overcome on Binance for a 2% target?
```

---

## Core Principles

| Setting | Default |
|---------|---------|
| Exposure style | Spot / cash / fully-paid only |
| Entry | Limit only |
| Exit | Limit only |
| Protective order | Stop-limit or controlled stop |
| Leverage | Off |
| Shorting | Off |
| Perps/futures/options | Off |
| Architecture | Single bot/agent first |

Only expands beyond defaults when explicitly justified by:
1. User request
2. Venue/cost structure makes it rational
3. Strategy cannot be expressed honestly in default mode

---

## Features

- **Venue intake templates** - Capture exact fees, constraints, order types
- **Fee hurdle calculations** - Know your break-even before trading
- **Capital-bucket routing** - Size appropriately for account level
- **Deployment profiles** - Local vs cloud model routing
- **News intelligence policy** - When news matters (and when it doesn't)
- **Decision tree frameworks** - Structured strategy logic

---

## Structure

```
unum-strat/
├── SKILL.md           # Full skill documentation
├── _meta.json         # ClawHub metadata
├── README.md          # This file
├── agents/            # Provider configs
│   └── openai.yaml
├── assets/            # Templates & snippets
│   ├── intake-template.md
│   ├── pseudologic-snippets.md
│   └── source-registry-template.md
└── references/        # Knowledge base
    ├── knowledge.md
    ├── decision-tree.md
    ├── deployment-profile.md
    ├── news-intelligence-policy.md
    └── review-claude-vs-openai.md
```

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 3.1.0 | 2026-02 | Initial ClawHub release |

---

## License

MIT License - see LICENSE file

---

## Author

**Antonis Corpu**  
GitHub: [@corpunum](https://github.com/corpunum)  
ClawHub: @corpunum
