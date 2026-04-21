---
name: git-workflow
description: Git workflow: branches, PR, merge, cleanup
---
# Git Workflow

> Standard Git workflow: branches, commits, PR, merge

## When to use

- Any change to data or code going to GitHub
- "commit" / "push" / "create PR" / "merge"
- After running any skill that modifies files

## Rules

### 1. Never push to main directly

Always through PR:

```bash
git checkout -b <prefix>/<name>
# changes
git add <files>
git commit -m "Description"
git push -u origin <prefix>/<name>
gh pr create --title "..." --body "..."
gh pr merge --squash --delete-branch
git checkout main && git pull
```

### 2. Branch naming

| Change type | Prefix | Example |
|-------------|--------|---------|
| New feature | `feature/` | `feature/clientk-lookalikes` |
| Data update | `update/` | `update/stream-cohort-2026-02-08` |
| Fix | `fix/` | `fix/crm-product-fk` |
| New lead/contact | `feat/` | `feat/kyrylo-mazur-lead` |

### 3. Merge strategy

**Always squash merge + delete branch:**

```bash
gh pr merge --squash --delete-branch
```

- `--squash` -- one clean commit in main
- `--delete-branch` -- automatically deletes the branch after merge

### 4. After merge

```bash
git checkout main
git pull origin main
```

### 5. Commit message format

```
<Action>: <what exactly was done>

Details if needed.

Co-Authored-By: Claude <noreply@anthropic.com>
```

Examples:
- `Add 24 stream participants (p-fb-018..041)`
- `Update task-042: expand stream outreach to 39 people`
- `Fix CRM product FK consistency`

### 6. Cleanup

If old branches have accumulated:

```bash
# View all remote branches
gh api repos/your-org/<repo>/branches --jq '.[].name'

# Delete a specific one
gh api repos/your-org/<repo>/git/refs/heads/<branch> -X DELETE
```

## Repositories

| Repo | What's there | Prefix |
|------|-------------|--------|
| `your-org/$PROJECT_ROOT` | CRM + PM data | `update/`, `feat/`, `fix/` |
| `your-org/claude-skills` | Claude skills | `update/`, `feature/` |
| `your-org/google-tools` | Google API scripts | `feature/`, `fix/` |

## Restrictions

- DO NOT commit secrets (.env, token.json, credentials.json)
- DO NOT force push
- DO NOT rebase main
- DO NOT leave dead branches after merge

## Related skills

- `change-review` -- CRM/PM data validation before PR
- `code-review` -- code review for code PRs
