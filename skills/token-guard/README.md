# Token Guard 💰

[🇨🇳 中文文档](./README_CN.md)

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-blue)](https://clawdhub.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](./SKILL.md)

## Stop burning money while you sleep.

> Your agent runs 24/7. Opus costs $75/M tokens. Do the math.

One user spent $55 on a single task (registering an email + X account). Another burned $100 in a week just exploring. Token Guard watches your spend so you don't have to.

## Quick Start

```bash
# Current usage + costs
bash scripts/token-guard.sh status

# Set $10/day budget
bash scripts/token-guard.sh set-budget 10

# Hard limit: auto-downgrade to Haiku when exceeded
bash scripts/token-guard.sh set-budget 10 80 true claude-haiku-3-5

# Estimate before running
bash scripts/token-guard.sh estimate claude-opus-4 50000 10000

# Usage history
bash scripts/token-guard.sh history
```

## Features

- **Budget alerts** — warning at 80%, critical at 100%
- **Auto-downgrade** — hit budget → auto-switch to cheaper model
- **Cost estimation** — estimate before running expensive tasks
- **Usage history** — daily breakdown by model
- **Model comparison** — see real cost differences at a glance

## The Real Savings

| What you change | Monthly savings |
|---|---|
| Route subagents to Haiku | ~70% |
| Route heartbeat to Flash | ~95% |
| Set daily budget + downgrade | prevents blowouts |
| Cache-aware heartbeat (55min) | ~30% |

## Requirements

- `bash` 4+, `python3`, `curl`

## 🛡️ Part of the AI Agent Security Suite

| Tool | What It Prevents |
|------|-----------------|
| **[agent-guardrails](https://github.com/jzOcb/agent-guardrails)** | AI rewrites validated code, leaks secrets, bypasses standards |
| **[config-guard](https://github.com/jzOcb/config-guard)** | AI writes malformed config, crashes gateway |
| **[upgrade-guard](https://github.com/jzOcb/upgrade-guard)** | Version upgrades break dependencies, no rollback |
| **[token-guard](https://github.com/jzOcb/token-guard)** | Runaway token costs, budget overruns |
| **[process-guardian](https://github.com/jzOcb/process-guardian)** | Background processes die silently, no auto-recovery |

📖 **Read the full story:** [I audited my own AI agent system and found it full of holes](https://x.com/xxx111god/status/2019455237048709336)

## License

MIT

## 🛡️ Part of the OpenClaw Security Suite

| Guard | Purpose | Protects Against |
|-------|---------|------------------|
| **[agent-guardrails](https://github.com/jzOcb/agent-guardrails)** | Pre-commit hooks + secret detection | Code leaks, unsafe commits |
| **[config-guard](https://github.com/jzOcb/config-guard)** | Config validation + auto-rollback | Gateway crashes from bad config |
| **[upgrade-guard](https://github.com/jzOcb/upgrade-guard)** | Safe upgrades + watchdog | Update failures, cascading breaks |
| **[token-guard](https://github.com/jzOcb/token-guard)** | Usage monitoring + cost alerts | Budget overruns, runaway costs |

📚 **Full writeup:** [4-Layer Defense System for AI Agents](https://x.com/xxx111god/status/2019096285853139083)
