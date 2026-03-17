# Security Policy

## ⚠️ This Repository is De-sensitized

All provider-specific API keys, tokens, secrets, and vendor names have been replaced with generic placeholders.

### Placeholder Conventions
| Pattern | Meaning |
|---------|---------|
| `<provider>/<model>` | Replace with your provider/model ID |
| `your-provider.example.com` | Replace with your API endpoint |
| `YOUR_API_KEY` | Replace with your actual API key |
| `pass show api/<service>` | Reference to local password store |
| `Provider-A`, `Provider-B` | Generic provider names |

### What is NOT in This Repo
- ❌ Real API keys or tokens
- ❌ `auth-profiles.json` (provider credentials)
- ❌ `models.json` (model routing config)
- ❌ `openclaw.json` (runtime config)
- ❌ `.env` files
- ❌ Private keys (`.key`, `.pem`)
- ❌ Browser session data

### Pre-Push Security Protocol
Before every push, run the three-layer scan:

```bash
# Layer 1: Critical key patterns
grep -rE 'AIza[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xoxb-|AKIA[A-Z0-9]{16}' \
  --include='*.py' --include='*.js' --include='*.json' --include='*.md' --include='*.sh' -l .

# Layer 2: Broader secret patterns
grep -rE 'Bearer [A-Za-z0-9]{20,}|api[_-]?key.*=.*[A-Za-z0-9]{20,}' \
  --include='*.py' --include='*.js' --include='*.json' --include='*.md' --include='*.sh' -l .

# Layer 3: Git history check
git log --all --diff-filter=A --name-only --pretty=format: | sort -u | grep -iE 'secret|token|key|auth|env'
```

All three layers must pass with zero real credentials before pushing.

### Reporting
If you discover a leaked credential in this repo, please open an issue immediately.
