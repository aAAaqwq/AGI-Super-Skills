# CLAUDE.md — AGI Super Team

> This file is auto-loaded by Claude Code when working in this repository.

## Repository Overview

AGI Super Team is a plug-and-play AI team template for [OpenClaw](https://github.com/openclaw/openclaw). It contains:
- **12 C-Suite agent personas** in `agents/` (CEO, CTO, PE, CCO, etc.)
- **727+ skills** in `skills/` (each with SKILL.md)
- **Starter kits** in `starter-kits/` for one-click deployment
- **Cookbooks** in `cookbook/` for deep learning

## When User Says "Install AGI Super Team"

Follow the steps in [`setup.md`](./setup.md):

1. `git clone --depth 1 https://github.com/aAAaqwq/AGI-Super-Team.git ~/.agi-super-team`
2. `bash ~/.agi-super-team/install.sh <kit-name>`
3. Verify workspace files exist
4. Guide user through `openclaw config` and `openclaw gateway restart`

Kit options: `solo-founder` | `content-creator` | `quant-trader` | `full-team` | or any agent ID (ceo, pe, cco, cto...)

## File Conventions

- `agents/{id}/SOUL.md` — Agent personality (mandatory)
- `agents/{id}/AGENTS.md` — Role definition and operations
- `agents/{id}/IDENTITY.md` — Detailed identity profile
- `agents/{id}/BOOTSTRAP.md` — Startup sequence
- `skills/{name}/SKILL.md` — Skill definition with YAML frontmatter
- `starter-kits/{name}/README.md` — Kit description and usage

## Agent IDs

`ceo`(CEO), `cto`, `pe`, `cpo`, `cqo`, `cmo`, `cfo`, `cdo`, `cco`, `clo`, `cro`, `cso`, `coo`
