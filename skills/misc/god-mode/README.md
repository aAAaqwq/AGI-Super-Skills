# god-mode

> 🔭 Bird's-eye view of your coding projects. 🧠 AI agent coaching based on your actual work.

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-blue)](https://clawdhub.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What is this?

**god-mode** is an OpenClaw skill that gives you:

1. **Project Overview** - See all your repos at a glance (commits, PRs, issues)
2. **Agent Coaching** - Automatically improve your `agents.md` based on commit patterns

### The Problem

You're juggling multiple projects. You use AI coding assistants but your `agents.md` instructions are generic or outdated. You lose context when switching between repos.

### The Solution

```bash
# See everything at once
$ god status

🔭 god-mode

tandem-evaluator
  Last: 2h ago • fix: evaluation metrics
  PRs: 2 open (1 needs review) • Issues: 5

tada  
  Last: 1d ago • feat: API endpoints
  PRs: 0 • Issues: 3

This week: 23 commits • 3 PRs merged

# Make your AI assistant smarter
$ god agents analyze tandem-evaluator

🧠 Analyzing tandem-evaluator...

⚠️ GAPS FOUND

Testing (not mentioned)
  But 31% of your commits touch tests
  → Add: "Write tests for new code"

📝 SUGGESTED ADDITIONS

## Testing
- Unit tests for all new functions
- Run `npm test` before commits
```

## Installation

### Prerequisites

- `gh` - [GitHub CLI](https://cli.github.com/) (authenticated)
- `sqlite3` - Usually pre-installed
- `jq` - `brew install jq` or `apt install jq`

### Install

```bash
# Clone
git clone https://github.com/InfantLab/god-mode-skill
cd god-mode-skill

# Add to PATH
echo 'export PATH="$PATH:'$(pwd)'/scripts"' >> ~/.bashrc
source ~/.bashrc

# Setup
god setup
```

Or for OpenClaw:
```bash
openclaw skills add god-mode
```

## Quick Start

```bash
# 1. Add your first project
god projects add github:yourname/yourrepo

# 2. Sync data
god sync

# 3. See the overview
god status

# 4. Analyze your agents.md
god agents analyze yourrepo
```

## Commands

| Command | Description |
|---------|-------------|
| `god status` | Overview of all projects |
| `god status <project>` | Details for one project |
| `god sync` | Fetch latest data from repos |
| `god sync --force` | Full refresh (ignore cache) |
| `god projects` | List configured projects |
| `god projects add <uri>` | Add a project |
| `god agents analyze <project>` | Improve your agents.md |

## Configuration

`~/.config/god-mode/config.yaml`:

```yaml
projects:
  - id: github:myuser/myrepo
    name: My Project
    priority: high
    tags: [work, api]
    local: ~/code/myrepo

sync:
  initialDays: 90
  commitsCacheMinutes: 60
```

See [config.example.yaml](config.example.yaml) for all options.

## How Agent Analysis Works

1. **Reads your `agents.md`** (or similar file)
2. **Analyzes your commit history** (types, patterns, pain points)
3. **Finds gaps** between instructions and actual work
4. **Suggests improvements** based on your patterns

Example insights:
- "You write lots of tests but don't mention testing in agents.md"
- "40% of commits are error-handling fixes - add error handling guidance"
- "Your 'use TypeScript strict' instruction is working - 0 type errors"

## Data & Privacy

- **All data stored locally** in `~/.god-mode/`
- **No tokens stored** - uses your existing `gh` auth
- **No telemetry** - nothing phones home
- **Open source** - audit the code yourself

## Roadmap

### v0.1.0 (Current)
- [x] Project status overview
- [x] GitHub integration via `gh` CLI
- [x] Incremental sync with SQLite cache
- [x] Agent instruction analysis

### v0.2.0
- [ ] Context save/restore
- [ ] Activity summaries (`god today`, `god week`)
- [ ] `god agents generate` for new projects

### v0.3.0
- [ ] Azure DevOps support
- [ ] GitLab support
- [ ] Proactive alerts via OpenClaw heartbeat

### v1.0.0
- [ ] Cross-project intelligence
- [ ] Integration ecosystem (Obsidian, etc.)

## Contributing

Contributions welcome! Each command is a standalone script - easy to add features.

```bash
# Structure
scripts/
├── god                 # Entry point
├── commands/
│   ├── status.sh       # god status
│   ├── sync.sh         # god sync
│   ├── projects.sh     # god projects
│   └── agents.sh       # god agents
└── lib/
    ├── providers/      # GitHub, Azure, GitLab
    └── analysis/       # Commit patterns, agent analysis
```

See [HANDOVER.md](HANDOVER.md) for architecture details.

## License

MIT - see [LICENSE](LICENSE)

## Credits

Created by [InfantLab](https://github.com/InfantLab) for the [OpenClaw](https://openclaw.ai) community.

---

*"Know what's happening. Make your AI smarter."*
