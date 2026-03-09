# inference-optimizer

**An OpenClaw skill that audits token usage, purges stale sessions, and optimizes inference speed.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

![banner](banner.png)

Ask your bot to run a baseline audit, purge old session files, or get optimization recommendations. Instead of guessing where tokens go, you get workspace sizes, session counts, and actionable next steps.

```
> /optimize
> purge stale sessions
> audit workspace tokens
```

## Why

Every OpenClaw instance loads workspace files, session history, and tool schemas on every request. Stale sessions pile up. Daily memory stubs accumulate. The model gets slower and more expensive without obvious cause.

This skill fixes that. Run `/optimize` to get a token audit. Approve a purge to clear stale sessions and stub files. No manual SSH, no guessing.

## Install

**ClawHub (recommended):**
```bash
clawhub install https://github.com/vitalyis/inference-optimizer
```

**Manual:**
```bash
git clone https://github.com/vitalyis/inference-optimizer.git ~/clawd/skills/public/inference-optimizer
bash ~/clawd/skills/public/inference-optimizer/scripts/setup.sh
```

## Setup

After install, run the setup script to wire `/optimize` and purge into your workspace:

```bash
bash ~/clawd/skills/public/inference-optimizer/scripts/setup.sh
```

This copies instructions into `AGENTS.md` and `TOOLS.md`, ensures scripts are executable, and prints allowlist snippets if needed.

## Commands

| Command | What it does |
|---------|--------------|
| `/optimize` | Run token audit (workspace files, sessions, config) and return raw output |
| `/audit` | Same as `/optimize` |
| purge sessions | After audit, if user approves, run purge script to remove stale sessions and stub memory |

## Verify

Confirm installation and script enablement:

```bash
bash ~/clawd/skills/public/inference-optimizer/scripts/verify.sh
```

Expected output:
- `optimization-agent.md` found
- `openclaw-audit.sh` executable
- `purge-stale-sessions.sh` executable
- Workspace paths resolvable
- AGENTS.md has `/optimize` (or manual step required)

## How It Works

```
SKILL.md (triggers + workflow)
    ↓
optimization-agent.md  ← agent reads for full Task 1–5 flow
scripts/
├── openclaw-audit.sh      ← baseline token audit
├── purge-stale-sessions.sh ← removes stale sessions + stub memory
├── setup.sh               ← wires commands into workspace
└── verify.sh              ← confirms install
    ↓
/optimize in chat → exec audit script → return output
purge approved    → exec purge script → return output
```

## Paths

Scripts auto-detect session and workspace paths:

- **Sessions:** `~/.openclaw/agents/main/sessions` or `~/.clawdbot/agents.main/sessions`
- **Workspace:** `~/clawd` or `~/.openclaw/workspace-whatsapp`
- **Memory:** `~/clawd/memory` or `~/.openclaw/workspace-whatsapp/memory`

## Limitations

- Run on the same host as OpenClaw (VPS or local)
- Exec allowlist must include `find`, `find *`, `find **`, `rm`, `rm *`, `rm **`, `bash`, `bash *`, `bash **` for purge
- Workspace layout must match OpenClaw defaults

## License

MIT
