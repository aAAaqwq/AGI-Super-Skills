# Orchestration Workflow

> One-command AI coding pipeline: worktree → worker → gate → merge → deploy → cleanup

Turn Claude Code / Codex into an engineering team with quality guardrails, TDD debugging, and automatic verification — all from a single shell command.

## Quick Start

```bash
# Install
curl -sL https://raw.githubusercontent.com/Arslan-Z/orchestration-workflow/main/install.sh | bash

# Run a task
orchestrate.sh /path/to/repo my-feature prompt.md codex --yolo --deploy --skills="core frontend"
```

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐     ┌───────────┐     ┌──────────┐
│  1. Setup   │────▶│  2. Worker   │────▶│  3. Gate   │────▶│  4. Merge  │────▶│ 5. Deploy │
│  worktree   │     │  codex/claude │     │  verify    │     │  to main   │     │  + verify  │
│  npm install│     │  + CLAUDE.md  │     │  build+test│     │  fast-fwd  │     │  browser   │
│  inject skills│   │  writes code  │     │  file count│     │            │     │            │
└─────────────┘     └──────────────┘     └───────────┘     └───────────┘     └──────────┘
```

1. **Setup**: Creates git worktree, installs deps, injects CLAUDE.md with selected skill fragments
2. **Worker**: Launches Codex/Claude Code with your prompt in YOLO mode, polls git for completion
3. **Gate**: Verifies build passes, checks file count, validates `.task-result.json`, rejects bad code
4. **Merge**: Fast-forward merge to main with clean oneline + diff stat
5. **Deploy**: Vercel deploy + optional headless browser verification via Actionbook CLI

## Worker Skills (Skill Pack)

Skills are injected into the Worker's `CLAUDE.md` before it starts coding. Pick what you need:

| Tag | What It Does | Lines | Source |
|-----|-------------|-------|--------|
| `core` | 8 engineering rules (approach first, surgical changes, test-before-fix) | 89 | Karpathy + custom |
| `frontend` | UI/UX quality, anti-AI-slop, design engineering | 226 | [taste-skill](https://github.com/Leonxlnx/taste-skill) |
| `tdd` | Test-driven development protocol | 371 | [superpowers](https://github.com/obra/superpowers) |
| `debug` | Systematic debugging (root cause before fix) | 296 | [superpowers](https://github.com/obra/superpowers) |
| `debug-tdd` | TDD-first autonomous bug fix (6-step loop) | 139 | Custom |
| `verify` | Pre-completion verification checklist | 139 | [superpowers](https://github.com/obra/superpowers) |

```bash
# UI feature
orchestrate.sh /repo task prompt.md codex --skills="core frontend"

# Bug fix with TDD
orchestrate.sh /repo fix-bug prompt.md codex --skills="core debug-tdd"

# New feature with tests
orchestrate.sh /repo feature prompt.md codex --skills="core tdd verify"
```

Default (no `--skills`): `core` only.

## Gate Safety

The gate is **deny-by-default**. A task passes only when ALL conditions are met:

- ✅ Worker committed code (`git log` shows new commit)
- ✅ Build passes (`npm run build` — gate runs it if Worker didn't report)
- ✅ `needs_split` is not flagged
- ✅ File count ≤ `MAX_FILES` (default: 5)
- ✅ `build_pass` is not `false`

Failed tasks automatically clean up worktree + branch (zero residual).

## Structured Output

Workers produce `.task-result.json` with:

```json
{
  "status": "success",
  "commit": "a1e3ab5",
  "build_pass": true,
  "test_pass": true,
  "needs_split": false,
  "approach": "3-sentence summary of what I did",
  "edge_cases": ["reduced-motion fallback", "touch devices", "empty state"],
  "assumptions": ["only modify listed files", "Tailwind is available"],
  "root_cause": "(debug tasks only) why the bug existed",
  "errors": []
}
```

## Task Templates

| Template | Use For |
|----------|---------|
| `templates/task-prompt.md` | General features, refactors |
| `templates/debug-task-prompt.md` | Bug fixes with TDD protocol |

## Options

```bash
orchestrate.sh <repo> <task-id> <prompt-file> [agent] [flags]

Agents: codex (default), claude, gemini
Flags:
  --yolo           Run agent in full-auto mode
  --deploy         Deploy + verify after merge (mode auto-detected)
  --no-cleanup     Keep worktree and branch after completion
  --skills="..."   Space-separated skill tags to inject

Environment:
  MAX_FILES=5           Max files changed before gate rejects
  WORKER_HOST=user@host Run worker on remote machine via SSH
  VERIFY_MODE=browser   Verify strategy: browser|api|test|none (auto-detect if unset)
  VERIFY_BROWSER=1      Enable actionbook browser verification (browser mode)
  VERIFY_MANIFEST=file  Per-page verification manifest (browser mode)
  VERIFY_SHOTS_DIR=dir  Screenshot output dir (default: /tmp/deploy-shots)
  API_HEALTH_URL=url    Health check endpoint (api mode)
  WORKER_MUX=zellij     Use zellij instead of tmux
```

## Project Types

The workflow auto-detects your project type and adjusts verification:

| Mode | Auto-detect | Verification |
|------|-------------|-------------|
| `browser` | `.vercel/` exists | Vercel deploy → HTTP check → DOM snapshot → console errors |
| `api` | `Dockerfile` exists | `npm test` → health check (`API_HEALTH_URL`) |
| `test` | fallback | `npm test` only |
| `none` | — | Skip |

```bash
# Web app (auto-detected from .vercel/)
orchestrate.sh /repo task prompt.md codex --yolo --deploy

# Express API
VERIFY_MODE=api API_HEALTH_URL=http://localhost:3000/health \
  orchestrate.sh /repo task prompt.md codex --yolo --deploy

# npm library
VERIFY_MODE=test orchestrate.sh /repo task prompt.md codex --yolo --deploy
```

### Env Var Detection

Gate automatically scans for new `process.env.*` references and warns if found.
This catches the common mistake of adding code that needs env vars without configuring them.

### Console Error Check

Browser verification now checks console errors after visiting all pages. Known benign
errors (Cesium skybox, favicon) are filtered. Critical runtime errors are surfaced.

## Remote Execution

```bash
# Run worker on a remote VPS via SSH + tmux
WORKER_HOST=root@100.125.204.29 \
  orchestrate.sh /tmp/my-project task prompt.md codex --yolo
```

Requires: SSH key auth + tmux on remote host.

## needs_split: Auto Task Decomposition

When a task touches too many files, the Worker stops and suggests a split plan:

```
Worker: "8 files needed. Suggested split:
  Chunk 1: lib/theme.ts + app/page.tsx + app/search/page.tsx
  Chunk 2: app/explore/page.tsx + app/about/page.tsx
  Chunk 3: components/Navbar.tsx + Footer.tsx + FlightResults.tsx"

Gate: REJECTED (needs_split)
```

The Orchestrator then creates 3 focused sub-tasks and runs them sequentially.

## Project Structure

```
├── SKILL.md              ← OpenClaw skill entry point
├── install.sh            ← curl | bash installer
├── scripts/
│   ├── orchestrate.sh    ← Main orchestrator (one command)
│   ├── inject-worker-skills.sh  ← CLAUDE.md assembler
│   ├── deploy-verify.sh  ← Deploy + browser verification
│   ├── worker-session.sh ← tmux/zellij terminal management
│   ├── watchdog.sh       ← Process monitor + salvage
│   └── parse-worker-output.sh
├── worker-skills/        ← Skill Pack fragments
│   ├── karpathy.md       ← core (8 rules)
│   ├── taste-frontend.md ← frontend UI/UX
│   ├── tdd.md            ← test-driven dev
│   ├── debug.md          ← systematic debugging
│   ├── debug-tdd.md      ← TDD auto-debug
│   └── verify.md         ← completion verification
└── templates/            ← Task prompt templates
    ├── task-prompt.md
    └── debug-task-prompt.md
```

## Tested Results

| Task Type | Example | Polls | Result |
|-----------|---------|-------|--------|
| Feature | Flight filter (slider+checkbox+sort) | 13 | ✅ |
| Debug-TDD | Inverted filter logic | 13 | ✅ one-shot |
| Refactor | Extract data layer (5 files) | 19 | ✅ |
| Multi-chunk | Theme refactor (3 chunks, 8 files) | 31 total | ✅ all pass |
| Small fix | Footer update | 4 | ✅ |
| Gate reject | Intentional bad import | 8 | ✅ blocked |
| needs_split | 8-file refactor | 2 | ✅ stopped |

18 friction points found and fixed across v2.6→v3.4.1.

## Requirements

- Node.js 18+
- Git
- `codex` CLI ([OpenAI Codex](https://github.com/openai/codex)) or `claude` CLI ([Claude Code](https://docs.anthropic.com/en/docs/claude-code))
- Optional: [Actionbook CLI](https://github.com/nicholasgriffintn/actionbook) for browser verification
- Optional: Vercel CLI for deploy

## For OpenClaw Users

This is an [OpenClaw](https://github.com/openclaw/openclaw) skill. After installing, Minerva (or your agent) can orchestrate coding tasks automatically:

```
"Hey Minerva, add a dark mode toggle to the settings page"
→ Minerva writes prompt → orchestrate.sh → Codex codes → gate verifies → deployed
```

## License

MIT

## Credits

Worker skills adapted from:
- [Karpathy's coding principles](https://github.com/forrestchang/andrej-karpathy-skills)
- [taste-skill](https://github.com/Leonxlnx/taste-skill) by Leonxlnx
- [superpowers](https://github.com/obra/superpowers) by obra
