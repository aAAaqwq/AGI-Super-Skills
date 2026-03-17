# 🔒 Security Policy

## Overview

This repository is a **sanitized, public-facing** version of our team configuration. All secrets have been removed and replaced with `pass show api/xxx` references.

## 🚫 Absolute Rules

1. **NEVER hardcode** API keys, tokens, secrets, or passwords
2. **ALWAYS use** `pass show api/<service>` or environment variables
3. **ALWAYS scan** before committing (three-layer scan below)
4. **IMMEDIATELY rotate** any key that enters git history

## 🔑 Historical Incidents (All Resolved)

| Date | Incident | Resolution |
|------|----------|------------|
| 2026-02-05 | Feishu app_id/secret hardcoded | Removed + keys rotated |
| 2026-02-21 | Feishu Secret re-introduced | Removed + filter-repo cleanup |
| 2026-03-14 | Google API Key in coding-agent-backup | Removed + key rotated |
| 2026-03-17 | Full history cleanup | git-filter-repo replaced all leaked values |

⚠️ **All previously leaked keys have been rotated.** The values in git history are replaced with `REDACTED_*` markers.

## 🛡️ Three-Layer Pre-Push Security Scan

Run ALL three before any `git push`:

```bash
# Layer 1: Critical key patterns
grep -rE 'AIza[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xoxb-|AKIA[A-Z0-9]{16}' \
  --include='*.py' --include='*.js' --include='*.json' --include='*.md' --include='*.sh' -l .

# Layer 2: Broader secret patterns  
grep -rE 'Bearer [A-Za-z0-9]{20,}|api[_-]?key.*=.*[A-Za-z0-9]{20,}|secret.*=.*[A-Za-z0-9]{10,}' \
  --include='*.py' --include='*.js' --include='*.json' --include='*.md' --include='*.sh' -l .

# Layer 3: Git history audit
git log --all -p | grep -E 'AIzaSy[A-Za-z0-9]{33}|sk-[a-zA-Z0-9]{20,}|app_secret.*[A-Za-z0-9]{20}' | head -20
```

## 📋 Files That Must NEVER Be Committed

Added to `.gitignore`:
- `auth-profiles.json` — API auth credentials
- `models.json` — model provider keys
- `openclaw.json` — runtime config with tokens
- `.env` / `.env.*` — environment secrets
- `*.key` / `*.pem` / `*.p12` — certificates

## 🔧 Recommended Secret Management

```bash
# Store secrets
pass insert api/feishu-hanxing-app-secret

# Use in code
import os
secret = os.popen("pass show api/feishu-hanxing-app-secret").read().strip()

# Use in shell
APP_SECRET=$(pass show api/feishu-hanxing-app-secret)
```

## Reporting

If you find a leaked secret, immediately:
1. Open an issue with `[SECURITY]` prefix
2. Rotate the affected key at the provider
3. Use `git-filter-repo --replace-text` to clean history
4. Force push the cleaned history
