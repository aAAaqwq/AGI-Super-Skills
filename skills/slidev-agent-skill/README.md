<div align="center">

```
  ███████╗██╗     ██╗██████╗ ███████╗██╗   ██╗
  ██╔════╝██║     ██║██╔══██╗██╔════╝██║   ██║
  ███████╗██║     ██║██║  ██║█████╗  ██║   ██║
  ╚════██║██║     ██║██║  ██║██╔══╝  ╚██╗ ██╔╝
  ███████║███████╗██║██████╔╝███████╗ ╚████╔╝
  ╚══════╝╚══════╝╚═╝╚═════╝ ╚══════╝  ╚═══╝
           A G E N T   S K I L L
```

**Give your AI agent the power to create stunning presentations.**

Create, edit, theme, build, and export [Slidev](https://sli.dev) decks — from any AI agent platform.

---

[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-6C5CE7?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiLz48L3N2Zz4=)](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview)
[![Codex](https://img.shields.io/badge/Codex-compatible-10A37F?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/docs/guides/codex)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-compatible-FF6B35?style=for-the-badge)](https://openclaw.dev)
[![Slidev](https://img.shields.io/badge/Slidev-powered-2DD4BF?style=for-the-badge)](https://sli.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

## Why?

AI agents are great at writing code — but when you ask them to make a Slidev presentation, they fumble through CLI docs, forget syntax, and produce broken builds.

This skill fixes that. It gives your agent **structured knowledge** and **battle-tested scripts** so it can go from blank file to deployed deck without hand-holding.

---

## What it does

| Capability | Script | Formats |
|:--|:--|:--|
| **Scaffold a new deck** | `slidev-init.sh` | — |
| **Live-preview edits** | `slidev-dev.sh` | — |
| **Build for production** | `slidev-build.sh` | Static SPA |
| **Export presentations** | `slidev-export.sh` | PDF, PPTX, PNG, Markdown |
| **Eject a theme** | `slidev-theme-eject.sh` | — |
| **Scaffold a custom theme** | `slidev-theme-scaffold.sh` | — |

All scripts handle edge cases, resolve the Slidev CLI automatically, and work around known CLI bugs — so the agent doesn't have to.

---

## Architecture

```
slidev-agent-skill/
│
├── SKILL.md                          # Orchestration — agent reads this first
│
├── references/
│   ├── index.md                      # Task-to-reference routing table
│   ├── slidev/                       # Official Slidev docs (auto-synced)
│   │   ├── core-syntax.md
│   │   ├── cli.md
│   │   ├── layout.md
│   │   ├── theme-addon.md
│   │   ├── write-theme.md
│   │   ├── directory-structure.md
│   │   ├── exporting.md
│   │   ├── hosting.md
│   │   └── work-with-ai.md
│   └── platforms/                    # Platform-specific skill guides
│       ├── claude-skills.md
│       ├── codex-skills.md
│       └── openclaw-skills.md
│
└── scripts/                          # Deterministic execution layer
    ├── _slidev_common.sh             # Shared CLI resolution
    ├── slidev-init.sh
    ├── slidev-dev.sh
    ├── slidev-build.sh
    ├── slidev-export.sh
    ├── slidev-theme-eject.sh
    ├── slidev-theme-scaffold.sh
    └── sync-references.mjs           # Auto-sync docs from sli.dev
```

The skill follows a strict **4-layer model**:

1. **Orchestration** (`SKILL.md`) — routing logic and workflow rules
2. **Documentation** (`references/`) — official docs, loaded on-demand per task
3. **Execution** (`scripts/`) — deterministic shell scripts wrapping the Slidev CLI
4. **Configuration** (`package.json`) — minimal, no heavy dependencies

---

## Install

### Claude Code

```bash
# Clone into your skills directory
git clone https://github.com/6missedcalls/slidev-agent-skill.git \
  ~/.claude/skills/slidev-agent-skill
```

### Codex / OpenAI Agents

```bash
git clone https://github.com/6missedcalls/slidev-agent-skill.git \
  ~/.agents/skills/slidev-agent-skill
```

### OpenClaw

```bash
git clone https://github.com/6missedcalls/slidev-agent-skill.git \
  skills/slidev-agent-skill
```

> No agent-specific packaging required. Works as-is across all platforms.

### Prerequisites

- `bash`
- `node` >= 18 and `npm`
- `playwright-chromium` — required for exports (auto-installable via scripts)

---

## Quick start

```bash
# Create a new deck
./scripts/slidev-init.sh my-talk

cd my-talk

# Start the dev server
../scripts/slidev-dev.sh slides.md --port 3030

# Build for production
../scripts/slidev-build.sh slides.md --out dist

# Export to PDF
../scripts/slidev-export.sh slides.md --format pdf --output my-talk.pdf
```

---

## Script reference

### `slidev-init.sh [dir] [--no-install]`

Scaffolds a new Slidev project with `slides.md`, `package.json`, and dependencies.

### `slidev-dev.sh [entry] [--port N] [--base /x/] [--theme name]`

Starts the live-reload dev server for iterative editing.

### `slidev-build.sh [entry] [--out dir] [--base /x/] [--without-notes]`

Builds a deployable static SPA.

### `slidev-export.sh [entry] [--format pdf|pptx|png|md] [--output file] [--with-clicks] [--range ...] [--dark] [--install-playwright]`

Exports the deck. Supports PDF, PowerPoint, PNG, and Markdown formats.

### `slidev-theme-eject.sh [entry] [--dir theme] [--theme name]`

Ejects the active theme into a local directory for full customization.

### `slidev-theme-scaffold.sh [theme-name]`

Scaffolds a brand-new theme package with layouts, styles, and setup files.

> All scripts support `--help`. Run any script without arguments for usage info.

---

## How agents use this

The agent workflow is intentionally **script-first and reference-routed**:

```
1. Agent reads SKILL.md
2. Agent checks references/index.md for task routing
3. Agent loads ONLY the reference files needed
4. Agent executes via scripts/* (not raw CLI)
5. Agent falls back to direct Slidev CLI only when needed
```

This keeps the agent's context window efficient — it never loads documentation it doesn't need.

### Reference routing

| Task | References loaded |
|:--|:--|
| Create a deck | `core-syntax.md`, `cli.md` |
| Edit content and layouts | `core-syntax.md`, `layout.md`, `directory-structure.md` |
| Theme customization | `theme-addon.md`, `write-theme.md`, `directory-structure.md` |
| Build and deploy | `hosting.md`, `cli.md` |
| Export | `exporting.md`, `cli.md` |

---

## Keeping references up to date

The bundled documentation auto-syncs from the official Slidev docs:

```bash
npm run sync:references
```

This fetches the latest content from [sli.dev](https://sli.dev) and updates local files with deterministic writes (only changes when content actually differs).

---

## Troubleshooting

**Export fails with Playwright error?**
```bash
# Auto-install Playwright with the export command
./scripts/slidev-export.sh slides.md --format pdf --install-playwright

# Or install manually
npm i -D playwright-chromium
```

**Markdown export path issues?**
The script automatically handles this — bare filenames are rewritten to `out/<name>.md` to work around a known Slidev CLI bug.

**Theme eject not working?**
Theme ejection uses `--entry` internally for compatibility with current Slidev CLI versions.

---

## Contributing

```bash
# Validate all shell scripts
npm run check:shell

# Refresh references from upstream docs
npm run sync:references
```

See [`README.quick.md`](README.quick.md) for a contributor cheat sheet.

---

## License

MIT

---

<div align="center">

Built for agents that present.

**[Slidev](https://sli.dev)** | **[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview)** | **[Codex](https://platform.openai.com/docs/guides/codex)** | **[OpenClaw](https://openclaw.dev)**

</div>
