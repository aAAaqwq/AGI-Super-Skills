---
name: slidev-multi-agent
description: Create, edit, theme, build, and export Slidev presentations using a script-first workflow with detailed local references. Use when working on Slidev decks, themes, layouts, exports, or hosting. Always consult references/index.md first and execute via scripts when available.
---

# Slidev Multi-Agent Skill

Use this skill for Slidev presentation work across Codex, Claude Code, and OpenClaw.

## Required workflow

1. Read `references/index.md` first.
2. Load only the specific reference files needed for the current task.
3. Prefer `scripts/*` as the execution layer before ad-hoc CLI commands.
4. Fall back to direct Slidev CLI only when no script covers the workflow.

## Core workflows

### Create a deck

1. Run `scripts/slidev-init.sh [dir]`.
2. Confirm `slides.md` exists.
3. Start preview with `scripts/slidev-dev.sh [entry]`.

### Edit slides

1. Use `references/slidev/core-syntax.md` and `references/slidev/layout.md`.
2. Update slide structure, frontmatter, layouts, and content.
3. Preview changes with `scripts/slidev-dev.sh`.

### Customize themes

1. Use `references/slidev/theme-addon.md`, `references/slidev/write-theme.md`, and `references/slidev/directory-structure.md`.
2. For theme extraction from active deck, run `scripts/slidev-theme-eject.sh`.
3. For new theme scaffold, run `scripts/slidev-theme-scaffold.sh [theme-name]`.

### Build and export

1. Use `references/slidev/hosting.md` and `references/slidev/exporting.md`.
2. Build SPA with `scripts/slidev-build.sh`.
3. Export assets with `scripts/slidev-export.sh`.

## Reference loading rules

- For syntax and authoring: `references/slidev/core-syntax.md`
- For CLI behavior: `references/slidev/cli.md`
- For theming and addons: `references/slidev/theme-addon.md`, `references/slidev/write-theme.md`
- For deck structure and custom files: `references/slidev/directory-structure.md`
- For exports and hosting: `references/slidev/exporting.md`, `references/slidev/hosting.md`
- For platform-specific skill behavior:
  - Codex: `references/platforms/codex-skills.md`
  - Claude Code: `references/platforms/claude-skills.md`
  - OpenClaw: `references/platforms/openclaw-skills.md`

## Notes

- Keep operations deterministic and script-first.
- Do not assume platform-specific metadata files are required.
- This skill is intentionally a single shared source of truth.
