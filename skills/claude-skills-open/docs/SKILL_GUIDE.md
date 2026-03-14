# Skill Guide

## What is a Skill?

A skill is a markdown file (`SKILL.md`) that teaches Claude Code how to perform a specific task. Skills contain:

1. **Frontmatter** -- name and description (YAML)
2. **Triggers** -- when Claude should load this skill
3. **Paths** -- files and tools the skill needs
4. **Instructions** -- step-by-step execution guide
5. **Code snippets** -- ready-to-run Python/Bash/JS

## Skill Lifecycle

```
User says something
  → Claude checks skill descriptions
  → Matches trigger? Load SKILL.md
  → Follow instructions
  → Execute code
  → Return result
```

Skills are **lazy-loaded** -- Claude only reads the full SKILL.md when it matches a trigger. The description in frontmatter is always visible.

## Creating a New Skill

### 1. Choose a category

| Category | For |
|----------|-----|
| core | Framework utilities (routing, memory, timezone) |
| crm | CRM data operations |
| pm | Project/task management |
| channels | Communication (email, Telegram, WhatsApp, LinkedIn) |
| agents | Autonomous multi-step workflows |
| dev | Development tools (code review, git) |
| finance | Invoicing, payments |
| infra | Auth, deployment, infrastructure |
| sales | Sales preparation, outreach |

### 2. Create the files

```bash
mkdir -p skills/{category}/{skill-name}
cp skills/TEMPLATE.md skills/{category}/{skill-name}/SKILL.md
```

### 3. Edit SKILL.md

The frontmatter is critical:

```yaml
---
name: my-skill
description: One sentence describing what this skill does
---
```

- `name` -- used for `/slash-command` invocation
- `description` -- Claude reads this to decide when to load the skill

### 4. Write the body

Follow this structure:

```markdown
# Skill Name

> One-line description

## When to use

- "user says X"
- "user asks about Y"
- Trigger condition Z

## Paths

| What | Path |
|------|------|
| Script | `$CRM_PATH/script.py` |
| Data | `$PM_PATH/data.csv` |

## How to execute

### Step 1: Do something

```python
code here
```

### Step 2: Do something else

```bash
command here
```

## Parameters

| Param | Description | Default |
|-------|-------------|---------|
| `--count` | Number of items | 5 |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Error X | Fix X |

## Related skills

- `other-skill` -- how they connect
```

### 5. Install symlink

```bash
ln -s ~/claude-skills/skills/{category}/{skill-name} ~/.claude/skills/{skill-name}
```

Or run `bash setup/install.sh` to install all at once.

### 6. Commit

```bash
git checkout -b feat/{skill-name}
git add skills/{category}/{skill-name}/
git commit -m "Add {skill-name} skill"
git push -u origin feat/{skill-name}
# Create PR on GitHub
```

## Best Practices

1. **One skill, one task** -- don't combine unrelated operations
2. **Concrete triggers** -- list exact phrases users might say
3. **Include code** -- Claude can run it immediately, no guessing
4. **Use config paths** -- `$CRM_PATH` not `/Users/you/...`
5. **Add troubleshooting** -- common errors and fixes
6. **Link related skills** -- help Claude chain workflows

## Path Variables

Skills use these config-driven path variables:

| Variable | Description |
|----------|-------------|
| `$CRM_PATH` | Path to CRM data directory |
| `$PM_PATH` | Path to PM data directory |
| `$GOOGLE_TOOLS_PATH` | Path to Google API tools |
| `$TG_TOOLS_PATH` | Path to Telegram tools |
| `$AGENTS_PATH` | Path to agent scripts |
| `$PROJECT_ROOT` | Path to project root |
| `$SKILLS_PATH` | Path to this skills repo |

Replace these with actual paths from `setup/config.yaml` when using.
