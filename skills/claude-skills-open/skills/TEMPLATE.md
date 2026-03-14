---
name: skill-name
description: Short description of what this skill does (1 sentence)
---
# [Skill Name]

> Short description of what this skill does

## When to use

- Trigger 1
- Trigger 2

## Dependencies

- Other skills: `skill-id-1`, `skill-id-2`
- External: Python 3, Node.js, etc.

## Paths

| What | Path |
|------|------|
| Script | `/path/to/script.py` |
| Credentials | `/path/to/creds.json` |
| Data | `/path/to/data/` |

## How to execute

### Step 1: [Name]

```bash
command here
```

### Step 2: [Name]

```python
code here
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--count` | Quantity | 5 |
| `--dry-run` | Test mode | false |

## Examples

### Example 1: [Description]

```bash
python3 script.py --count 10
```

### Example 2: [Description]

```bash
python3 script.py --dry-run
```

## Limitations

- Limitation 1
- Limitation 2

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Error X | Fix X |
| Error Y | Fix Y |

## Related skills

- `related-skill-1` — relationship description
- `related-skill-2` — relationship description

## Checklist (when creating)

- [ ] SKILL.md has frontmatter with `name` and `description`
- [ ] Symlink created: `ln -s ~/claude-skills/skills/{category}/{skill-name} ~/.claude/skills/{skill-name}`
- [ ] Commit via `git-workflow`
