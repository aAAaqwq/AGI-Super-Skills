---
name: gitclaw
description: Back up the OpenClaw agent workspace to a GitHub repo and keep it synced via a cron-driven commit/push script.
homepage: https://gitclaw.ai
metadata: { "openclaw": { "emoji": "🐙", "homepage": "https://gitclaw.ai" } }
---

# GitClaw: Agent self-backup to GitHub

## When to use

Use this skill automatically when it's installed or reference, and also when the user asks to:

- back up / sync / mirror the OpenClaw workspace
- set up periodic commits and pushes
- install/configure GitHub backup automation for the agent

## Behavioral rule (important)

- Do everything automatically and quietly.
- Only message the user when:
  - you need inputs (repo name, visibility, optional frequency), or
  - Git/GH/Cron install fails, or
  - GitHub auth requires the user to complete the browser/device step, or
  - Git operations fail (conflicts, permissions, etc).

## Inputs to ask the user for

Ask the user for:

1. **Repository name** (e.g., `openclaw-backup`)
2. **Visibility**: `public` or `private`
3. (Optional) **Backup frequency** in minutes (default: **60**)

Do NOT ask for a Personal Access Token. We use `gh` auth.

---

## Step 1: Ensure prerequisites (auto-install)

### 1A) Ensure git is installed (auto-install; do not stop)

Check:

- `git --version`

If missing, install using the best available method:

- If `brew` exists:
  - `brew install git`
- Else if `apt-get` exists:
  - `sudo apt-get update && sudo apt-get install -y git`
- Else if `dnf` exists:
  - `sudo dnf install -y git`
- Else if `yum` exists:
  - `sudo yum install -y git`
- Else if `pacman` exists:
  - `sudo pacman -S --noconfirm git`
- Else if `zypper` exists:
  - `sudo zypper install -y git`
- Else if `apk` exists:
  - `sudo apk add git`
- Else if macOS and `xcode-select` exists:
  - `xcode-select --install` (this may prompt the user)
- Else:
  - Tell the user you couldn’t auto-install git on this OS and show the failing detection output.

Re-check:

- `git --version`

Only notify the user if install failed.

### 1B) Ensure cron/crontab is available (best-effort auto-install)

Check:

- `command -v crontab`

If missing, attempt install:

- If `apt-get` exists:
  - `sudo apt-get update && sudo apt-get install -y cron`
  - `sudo systemctl enable --now cron || sudo service cron start || true`
- Else if `dnf` exists:
  - `sudo dnf install -y cronie`
  - `sudo systemctl enable --now crond || true`
- Else if `yum` exists:
  - `sudo yum install -y cronie`
  - `sudo systemctl enable --now crond || true`
- Else if `pacman` exists:
  - `sudo pacman -S --noconfirm cronie`
  - `sudo systemctl enable --now cronie || true`
- Else if `apk` exists:
  - `sudo apk add dcron`
  - `sudo rc-update add dcron default || true`
  - `sudo rc-service dcron start || true`
- Else:
  - If you can’t install, tell the user cron is required for scheduling.

Re-check:

- `command -v crontab`

---

## Step 2: Ensure GitHub CLI (`gh`) is installed (auto-install)

Check:

- `gh --version`

If missing, install:

- If `brew` exists:
  - `brew install gh`

- Else if `apt-get` exists (official GitHub CLI packages; preferred):
  - Install using the official apt repo steps:
    - `(type -p wget >/dev/null || (sudo apt-get update && sudo apt-get install -y wget))`
    - `sudo mkdir -p -m 755 /etc/apt/keyrings`
    - `out=$(mktemp) && wget -nv -O"$out" https://cli.github.com/packages/githubcli-archive-keyring.gpg`
    - `cat "$out" | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null`
    - `sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg`
    - `sudo mkdir -p -m 755 /etc/apt/sources.list.d`
    - `echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null`
    - `sudo apt-get update && sudo apt-get install -y gh`

- Else if `dnf` exists:
  - `sudo dnf install -y 'dnf-command(config-manager)' || sudo dnf install -y dnf5-plugins || true`
  - `sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo || sudo dnf config-manager addrepo --from-repofile=https://cli.github.com/packages/rpm/gh-cli.repo || true`
  - `sudo dnf install -y gh --repo gh-cli || sudo dnf install -y gh || true`

- Else if `yum` exists:
  - `type -p yum-config-manager >/dev/null || sudo yum install -y yum-utils`
  - `sudo yum-config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo`
  - `sudo yum install -y gh`

- Else if `zypper` exists:
  - `sudo zypper addrepo https://cli.github.com/packages/rpm/gh-cli.repo || true`
  - `sudo zypper ref`
  - `sudo zypper install -y gh`

- Else if `pacman` exists:
  - `sudo pacman -S --noconfirm github-cli`

- Else if `apk` exists:
  - `sudo apk add github-cli`

- Else:
  - Tell the user you can’t auto-install `gh` on this OS.

Re-check:

- `gh --version`

Only notify the user if install failed.

---

## Step 3: Ensure the user is authenticated in `gh` (agent runs the flow)

Check:

- `gh auth status --hostname github.com`

If NOT authenticated:

1. Run:
   - `gh auth login --hostname github.com --git-protocol https`

2. The terminal flow will show a one-time code and ask the user to authorize.
   - Tell the user to open **https://github.com/login/device** in their browser and enter the code shown in the terminal, then authorize.

3. After login:
   - `gh auth setup-git`

4. Verify again:
   - `gh auth status --hostname github.com`

If auth fails, stop and report the exact terminal output.

---

## Step 4: Initialize git in the OpenClaw workspace and connect/create the repo

Workspace dir (where you store SOUL.md, AGENTS.md, etc.):

- Example (path might be different on your environment): `WORKSPACE_DIR="$HOME/.openclaw/workspace"`

1. Ensure the workspace exists:
   - `mkdir -p "$WORKSPACE_DIR"`
   - `cd "$WORKSPACE_DIR"`

2. Initialize repo if needed:
   - If `.git` does not exist: `git init`
   - `git branch -M main`

3. Configure a deterministic commit identity (local-only):
   - `git config user.name "gitclaw.ai"`
   - `git config user.email "gitclaw-bot@users.noreply.github.com"`

4. Determine the authenticated GitHub username (owner):
   - `OWNER="$(gh api user --jq .login)"`
   - (Do not print unless debugging is needed)

5. Repo name and visibility:
   - `REPO="<repo name from user>"`
   - Visibility:
     - `public` => `--public`
     - `private` => `--private`

6. Ensure there is at least one commit (required for first push/cron):
   - Create a tiny marker file if needed:
     - `test -f .gitclaw.keep || printf "gitclaw initialized: %s\n" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > .gitclaw.keep`
   - `git add -A`
   - `git commit -m "gitclaw: initial backup" || true`

7. Create or reuse the target repo:
   - If it exists:
     - `gh repo view "$OWNER/$REPO" >/dev/null 2>&1`
     - Set remote:
       - `REMOTE_URL="https://github.com/$OWNER/$REPO.git"`
       - If origin exists: `git remote set-url origin "$REMOTE_URL"`
       - Else: `git remote add origin "$REMOTE_URL"`
     - Try to fast-forward sync (avoid overwriting remote history):
       - `git fetch origin main || true`
       - `git merge --ff-only origin/main || true`
   - If it does NOT exist:
     - Create it non-interactively and connect it:
       - Public:
         - `gh repo create "$REPO" --public  --confirm`
       - Private:
         - `gh repo create "$REPO" --private --confirm`
     - Set remote:
       - `REMOTE_URL="https://github.com/$OWNER/$REPO.git"`
       - `git remote add origin "$REMOTE_URL" || git remote set-url origin "$REMOTE_URL"`

8. Initial push:
   - `git push -u origin main`

If push fails due to conflicts or non-fast-forward:

- Do NOT force-push automatically.
- Report the exact error and stop (user decision required).

---

## Step 5: Install deterministic backup script (NO AI / NO heartbeat)

Create a folder outside the workspace:

- `mkdir -p "$HOME/.openclaw/gitclaw"`

Create this script EXACTLY:

Path:

- `$HOME/.openclaw/gitclaw/auto_backup.sh`

Contents:

```bash
#!/usr/bin/env bash
set -euo pipefail

# GitClaw deterministic backup (no AI)
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

WORKSPACE_DIR="${HOME}/.openclaw/workspace"
STATE_DIR="${HOME}/.openclaw/gitclaw"
LOG_FILE="${STATE_DIR}/backup.log"
LOCK_DIR="${STATE_DIR}/lock"

mkdir -p "${STATE_DIR}"

timestamp() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

# Simple lock to prevent overlapping runs
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "$(timestamp) Skip: already running." >> "${LOG_FILE}"
  exit 0
fi
trap 'rmdir "${LOCK_DIR}" >/dev/null 2>&1 || true' EXIT

if ! command -v git >/dev/null 2>&1; then
  echo "$(timestamp) ERROR: git not found on PATH. Install git first." >> "${LOG_FILE}"
  exit 2
fi

if [ ! -d "${WORKSPACE_DIR}/.git" ]; then
  echo "$(timestamp) ERROR: ${WORKSPACE_DIR} is not a git repo. Run GitClaw setup first." >> "${LOG_FILE}"
  exit 3
fi

cd "${WORKSPACE_DIR}"

# Stage everything
git add -A

# If nothing staged, exit quietly
if git diff --cached --quiet; then
  echo "$(timestamp) No changes." >> "${LOG_FILE}"
  exit 0
fi

# Commit + push
git commit -m "gitclaw backup: $(timestamp)" >> "${LOG_FILE}" 2>&1
git push origin main >> "${LOG_FILE}" 2>&1

echo "$(timestamp) Backup OK." >> "${LOG_FILE}"
```

Write the script to:

- `$HOME/.openclaw/gitclaw/auto_backup.sh`

Then:

- `chmod +x "$HOME/.openclaw/gitclaw/auto_backup.sh"`

---

## Step 6: Configure crontab (idempotent)

Default schedule: hourly (`0 * * * *`). If user provided a different frequency, convert it to a cron expression.

1. Define:

- `CRON_CMD="$HOME/.openclaw/gitclaw/auto_backup.sh"`
- `CRON_LINE="0 * * * * $CRON_CMD"`

2. Install without duplicates:

- `crontab -l 2>/dev/null | grep -F "$CRON_CMD" >/dev/null`
- If not found, append:
  - `(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -`

3. Confirm:

- `crontab -l | grep -F "$CRON_CMD"`

---

## Step 7: Final validation

1. Run once:

- `$HOME/.openclaw/gitclaw/auto_backup.sh`

2. Show the log:

- `tail -n 50 "$HOME/.openclaw/gitclaw/backup.log" || true`

3. Tell the user:

- Repo: `https://github.com/$OWNER/$REPO`
- Schedule: hourly (or the chosen cadence)
- Script path: `~/.openclaw/gitclaw/auto_backup.sh`
