# Claude Skills Repository

**Owner:** Your Name (your@email.com)

## How It Works

Skills are auto-discovered by Claude Code from `~/.claude/skills/` (per-skill symlinks to this repo's `skills/` directories).

Each skill has `SKILL.md` with YAML frontmatter:
- `name` -- skill identifier (used for `/slash-commands`)
- `description` -- Claude uses this to decide when to load the skill automatically

## Structure

```
~/.claude/skills/              (flat, per-skill symlinks)
├── telegram-send → repo/skills/channels/telegram-send/
├── daily-briefing → repo/skills/pm/daily-briefing/
└── ...

~/claude-skills/skills/        (git repo, categories for organization)
├── channels/telegram-send/SKILL.md
├── pm/daily-briefing/SKILL.md
└── ...
```

## Adding a New Skill

1. Create directory: `skills/{category}/{skill-name}/`
2. Create `SKILL.md` with frontmatter (see `skills/TEMPLATE.md`)
3. Add symlink: `ln -s ~/claude-skills/skills/{category}/{skill-name} ~/.claude/skills/{skill-name}`
4. Commit via `git-workflow` skill

## Git Workflow

**Always branch -> PR -> squash merge -> delete branch. Never push to main.**
