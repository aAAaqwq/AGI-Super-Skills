---
name: deploy-website
description: Website deployment via GitHub PR + Cloud Build
---
# Deploy Website

> Updating content on yourcompany.com and deploying via GitHub PR

## When to use

- "update the site", "add to the site"
- "deploy site changes"
- Any changes to yourcompany.com (landing pages, pages, styles)

## Paths

| What | Path |
|------|------|
| Repository | `$WEBSITE_REPO_PATH/` |
| GitHub | `https://github.com/your-github-org/your-website` |
| Styles | `$WEBSITE_REPO_PATH/styles.css` |

## Site structure

Bilingual site (EN + UK). **Always update both versions.**

| Page | EN | UK |
|------|----|----|
| Home | `index.html` | `uk/index.html` |
| Data Labeling | `data-labeling/index.html` | `uk/data-labeling/index.html` |
| AI Integration | `ai-integration/index.html` | `uk/ai-integration/index.html` |
| Agents | `agents/index.html` | `uk/agents/index.html` |
| Schedule Agent | `schedule-agent/index.html` | `uk/schedule-agent/index.html` |
| Agent Card | `schedule-agent/card/index.html` | `uk/schedule-agent/card/index.html` |
| Privacy | `privacy-policy/index.html` | `uk/privacy-policy/index.html` |
| Terms | `terms/index.html` | `uk/terms/index.html` |

## How to execute

### Step 1: Make changes

Edit HTML files. **Must update both EN + UK versions.**

### Step 2: PR + Merge

```bash
cd $WEBSITE_REPO_PATH
git checkout -b feature/change-description
git add <changed files>
git commit -m "Change description

Co-Authored-By: Claude <noreply@anthropic.com>"
git push -u origin feature/change-description
gh pr create --title "Change description" --body "..."
gh pr merge <PR_NUMBER> --squash --delete-branch
git checkout main && git pull --ff-only
```

### Step 3: Deploy (automatic)

Cloud Build (under `your@email.com`) triggers automatically on merge to main.
Changes appear on the site within 1-5 minutes.

### Step 4: Verification

```
WebFetch https://www.yourcompany.com/<page>?v=<timestamp>
```

**IMPORTANT:** CDN caches for up to 1 hour. To check the update immediately, add `?v=<number>` to the URL. Without this, WebFetch may show the old cached version.

## IMPORTANT: Do not touch GCP

- **DO NOT use** `gsutil`, `gcloud builds`, or other GCP commands
- GCP project is under `your@email.com`, local gcloud is under `your@email.com` -- no permissions
- Deployment happens **only through GitHub PR → merge to main** -- Cloud Build picks it up automatically

## Stack

- Static HTML + CSS + Vanilla JavaScript
- Google Fonts (Montserrat)
- Lucide Icons (unpkg CDN)
- Google Analytics (GA4)
- Hosting: GCS + Cloud Load Balancer + CDN

## Related skills

- `code-review` -- review changes before PR
