# slidev-multi-agent Quick Reference

Short guide for contributors working on this skill.

## Purpose

Single shared Slidev skill for Codex, Claude Code, and OpenClaw:

- `SKILL.md` = orchestration
- `references/` = docs layer
- `scripts/` = execution layer

## Where to install

- Codex/OpenAI agents: `.agents/skills/slidev-multi-agent`
- Claude Code: `.claude/skills/slidev-multi-agent`
- OpenClaw: `<workspace>/skills/slidev-multi-agent`

## Fast setup

```bash
npm run check:shell
npm run sync:references
```

## Workflow rules

1. Read `references/index.md` first.
2. Load only needed reference files.
3. Run `scripts/*` before ad-hoc CLI.
4. Fall back to direct Slidev CLI only if script path does not cover the task.

## Command cheat sheet

```bash
# initialize deck
./scripts/slidev-init.sh [dir]

# run dev server
./scripts/slidev-dev.sh [entry] [--port N] [--base /x/] [--theme name]

# build SPA
./scripts/slidev-build.sh [entry] [--out dir] [--base /x/] [--without-notes]

# export deck
./scripts/slidev-export.sh [entry] [--format pdf|pptx|png|md] [--output file] [--with-clicks] [--range ...] [--dark] [--install-playwright]

# eject active theme
./scripts/slidev-theme-eject.sh [entry] [--dir theme] [--theme name]

# scaffold new theme
./scripts/slidev-theme-scaffold.sh [theme-name]
```

## Most common contributor tasks

### Update references

```bash
npm run sync:references
```

### Validate script syntax

```bash
npm run check:shell
```

### Smoke test in temp deck

```bash
./scripts/slidev-init.sh /tmp/slidev-skill-test
cd /tmp/slidev-skill-test
<skill-path>/scripts/slidev-build.sh slides.md --out dist
<skill-path>/scripts/slidev-export.sh slides.md --format md --output export.md --install-playwright
```

## Known behavior

- Export requires `playwright-chromium` (script can auto-install via `--install-playwright`).
- Markdown export with bare filename is rewritten to `out/<name>.md` to avoid Slidev path issues.
- Theme eject uses explicit `--entry` internally for current Slidev CLI compatibility.

## Edit policy

- Keep `SKILL.md` small and orchestration-only.
- Put detailed docs under `references/`.
- Put deterministic execution behavior under `scripts/`.
