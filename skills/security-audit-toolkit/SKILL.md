---
name: security-audit
description: Audit codebases and infrastructure for security issues. Use when scanning dependencies for vulnerabilities, detecting hardcoded secrets, checking OWASP top 10 issues, verifying SSL/TLS, auditing file permissions, or reviewing code for injection and auth flaws.
metadata: {"clawdbot":{"emoji":"🔒","requires":{"anyBins":["npm","pip","git","openssl","curl"]},"os":["linux","darwin","win32"]}}
---

# Security Audit

Scan, detect, and fix security issues in codebases and infrastructure. Covers dependency vulnerabilities, secret detection, OWASP top 10, SSL/TLS verification, file permissions, and secure coding patterns.

## When to Use

- Scanning project dependencies for known vulnerabilities
- Detecting hardcoded secrets, API keys, or credentials in source code
- Reviewing code for OWASP top 10 vulnerabilities (injection, XSS, CSRF, etc.)
- Verifying SSL/TLS configuration for endpoints
- Auditing file and directory permissions
- Checking authentication and authorization patterns
- Preparing for a security review or compliance audit

## Dependency Vulnerability Scanning

### Node.js

```bash
# Built-in npm audit
npm audit
npm audit --json | jq '.vulnerabilities | to_entries[] | {name: .key, severity: .value.severity, via: .value.via[0]}'

# Fix automatically where possible
npm audit fix

# Show only high and critical
npm audit --audit-level=high

# Check a specific package
npm audit --package-lock-only

# Alternative: use npx to scan without installing
npx audit-ci --high
```

### Python

```bash
# pip-audit (recommended)
pip install pip-audit
pip-audit
pip-audit -r requirements.txt
pip-audit --format=json

# safety (alternative)
pip install safety
safety check
safety check -r requirements.txt --json

# Check a specific package
pip-audit --requirement=- <<< "requests==2.25.0"
```

### Go

```bash
# Built-in vuln checker
go install golang.org/x/vuln/cmd/govulncheck@latest
govulncheck ./...

# Check specific binary
govulncheck -mode=binary ./myapp
```

### Rust

```bash
# cargo-audit
cargo install cargo-audit
cargo audit

# With fix suggestions
cargo audit fix
```

### Universal: Trivy (scans any project)

```bash
# Install: https://aquasecurity.github.io/trivy
# Scan filesystem
trivy fs .

# Scan specific language
trivy fs --scanners vuln --severity HIGH,CRITICAL .

# Scan Docker image
trivy image myapp:latest

# JSON output
trivy fs --format json -o results.json .
```

## Secret Detection

### Manual grep patterns

```bash
# AWS keys
grep -rn 'AKIA[0-9A-Z]\{16\}' --include='*.{js,ts,py,go,java,rb,env,yml,yaml,json,xml,cfg,conf,ini}' .

# Generic API keys and tokens
grep -rn -i 'api[_-]\?key\|api[_-]\?secret\|access[_-]\?token\|auth[_-]\?token\|bearer ' \
  --include='*.{js,ts,py,go,java,rb,env,yml,yaml,json}' .

# Private keys
grep -rn 'BEGIN.*PRIVATE KEY' .

# Passwords in config
grep -rn -i 'password\s*[:=]' --include='*.{env,yml,yaml,json,xml,cfg,conf,ini,toml}' .

# Connection strings with credentials
grep -rn -i 'mongodb://\|mysql://\|postgres://\|redis://' --include='*.{js,ts,py,go,env,yml,yaml,json}' . | grep -v 'localhost\|127.0.0.1\|example'

# JWT tokens (three base64 segments separated by dots)
grep -rn 'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.' --include='*.{js,ts,py,go,log,json}' .
```

### Automated scanning with git

```bash
# Scan git history for secrets (not just current files)
# Using git log + grep
git log -p --all | grep -n -i 'api.key\|password\|secret\|token' | head -50

# Check staged files before commit
git diff --cached --name-only | xargs grep -l -i 'api.key\|password\|secret\|token' 2>/dev/null
```

### Pre-commit hook for secrets

```bash
#!/bin/bash
# .git/hooks/pre-commit - Block commits containing potential secrets

PATTERNS=(
    'AKIA[0-9A-Z]{16}'
    'BEGIN.*PRIVATE KEY'
    'password\s*[:=]\s*["\x27][^"\x27]+'
    'api[_-]?key\s*[:=]\s*["\x27][^"\x27]+'
    'sk-[A-Za-z0-9]{20,}'
    'ghp_[A-Za-z0-9]{36}'
    'xox[bpoas]-[A-Za-z0-9-]+'
)

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)
[ -z "$STAGED_FILES" ] && exit 0

EXIT_CODE=0
for pattern in "${PATTERNS[@]}"; do
    matches=$(echo "$STAGED_FILES" | xargs grep -Pn "$pattern" 2>/dev/null)
    if [ -n "$matches" ]; then
        echo "BLOCKED: Potential secret detected matching pattern: $pattern"
        echo "$matches"
        EXIT_CODE=1
    fi
done

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "To proceed anyway: git commit --no-verify"
    echo "To remove secrets: replace with environment variables"
fi
exit $EXIT_CODE
```

### .gitignore audit

```bash
# Check if sensitive files are tracked
echo "--- Files that should probably be gitignored ---"
for pattern in '.env' '.env.*' '*.pem' '*.key' '*.p12' '*.pfx' 'credentials.json' \
               'service-account*.json' '*.keystore' 'id_rsa' 'id_ed25519'; do
    found=$(git ls-files "$pattern" 2>/dev/null)
    [ -n "$found" ] && echo "  TRACKED: $found"
done

# Check if .gitignore exists and has common patterns
if [ ! -f .gitignore ]; then
    echo "WARNING: No .gitignore file found"
else
    for entry in '.env' 'node_modules' '*.key' '*.pem'; do
        grep -q "$entry" .gitignore || echo "  MISSING from .gitignore: $entry"
    done
fi
```

## OWASP Top 10 Code Patterns

### 1. Injection (SQL, Command, LDAP)

```bash
# SQL injection: string concatenation in queries
grep -rn "query\|execute\|cursor" --include='*.{py,js,ts,go,java,rb}' . | \
  grep -i "f\"\|format(\|%s\|\${\|+ \"\|concat\|sprintf" | \
  grep -iv "parameterized\|placeholder\|prepared"

# Command injection: user input in shell commands
grep -rn "exec(\|spawn(\|system(\|popen(\|subprocess\|os\.system\|child_process" \
  --include='*.{py,js,ts,go,java,rb}' .

# Check for parameterized queries (good)
grep -rn "\\$[0-9]\|\\?\|%s\|:param\|@param\|prepared" --include='*.{py,js,ts,go,java,rb}' .
```

### 2. Broken Authentication

```bash
# Weak password hashing (MD5, SHA1 used for passwords)
grep -rn "md5\|sha1\|sha256" --include='*.{py,js,ts,go,java,rb}' . | grep -i "password\|passwd"

# Hardcoded credentials
grep -rn -i "admin.*password\|password.*admin\|default.*password" \
  --include='*.{py,js,ts,go,java,rb,yml,yaml,json}' .

# Session tokens in URLs
grep -rn "session\|token\|jwt" --include='*.{py,js,ts,go,java,rb}' . | grep -i "url\|query\|param\|GET"

# Check for rate limiting on auth endpoints
grep -rn -i "rate.limit\|throttle\|brute" --include='*.{py,js,ts,go,java,rb}' .
```

### 3. Cross-Site Scripting (XSS)

```bash
# Unescaped output in templates
grep -rn "innerHTML\|dangerouslySetInnerHTML\|v-html\|\|html(" \
  --include='*.{js,ts,jsx,tsx,vue,html}' .

# Template injection
grep -rn "{{{.*}}}\|<%=\|<%-\|\$\!{" --include='*.{html,ejs,hbs,pug,erb}' .

# Document.write
grep -rn "document\.write\|document\.writeln" --include='*.{js,ts,html}' .

# eval with user input
grep -rn "eval(\|new Function(\|setTimeout.*string\|setInterval.*string" \
  --include='*.{js,ts}' .
```

### 4. Insecure Direct Object References

```bash
# Direct ID usage in routes without authz check
grep -rn "params\.id\|params\[.id.\]\|req\.params\.\|request\.args\.\|request\.GET\." \
  --include='*.{py,js,ts,go,java,rb}' . | \
  grep -i "user\|account\|profile\|order\|document"
```

### 5. Security Misconfiguration

```bash
# CORS wildcard
grep -rn "Access-Control-Allow-Origin.*\*\|cors({.*origin.*true\|cors()" \
  --include='*.{py,js,ts,go,java,rb}' .

# Debug mode in production configs
grep -rn "DEBUG\s*=\s*True\|debug:\s*true\|NODE_ENV.*development" \
  --include='*.{py,js,ts,yml,yaml,json,env}' .

# Verbose error messages exposed to clients
grep -rn "stack\|traceback\|stackTrace" --include='*.{py,js,ts,go,java,rb}' . | \
  grep -i "response\|send\|return\|res\."
```

## SSL/TLS Verification

### Check endpoint SSL

```bash
# Full SSL check
openssl s_client -connect example.com:443 -servername example.com < /dev/null 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates -fingerprint

# Check certificate expiry
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | \
  openssl x509 -noout -enddate

# Check supported TLS versions
for v in tls1 tls1_1 tls1_2 tls1_3; do
  result=$(openssl s_client -connect example.com:443 -$v < /dev/null 2>&1)
  if echo "$result" | grep -q "Cipher is"; then
    echo "$v: SUPPORTED"
  else
    echo "$v: NOT SUPPORTED"
  fi
done

# Check cipher suites
openssl s_client -connect example.com:443 -cipher 'ALL' < /dev/null 2>&1 | \
  grep "Cipher    :"

# Check for weak ciphers
openssl s_client -connect example.com:443 -cipher 'NULL:EXPORT:DES:RC4:MD5' < /dev/null 2>&1 | \
  grep "Cipher    :"
```

### Verify certificate chain

```bash
# Download and verify full chain
openssl s_client -connect example.com:443 -showcerts < /dev/null 2>/dev/null | \
  awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/{print}' > chain.pem

# Verify chain
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt chain.pem

# Check certificate details
openssl x509 -in chain.pem -noout -text | grep -A2 "Subject:\|Issuer:\|Not Before\|Not After\|DNS:"
```

### Check SSL from code

```bash
# Verify SSL isn't disabled in code
grep -rn "verify\s*=\s*False\|rejectUnauthorized.*false\|InsecureSkipVerify.*true\|CURLOPT_SSL_VERIFYPEER.*false\|NODE_TLS_REJECT_UNAUTHORIZED.*0" \
  --include='*.{py,js,ts,go,java,rb,yml,yaml}' .
```

## File Permission Audit

```bash
# Find world-writable files
find . -type f -perm -o=w -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null

# Find executable files that shouldn't be
find . -type f -perm -u=x -not -name '*.sh' -not -name '*.py' -not -path '*/node_modules/*' \
  -not -path '*/.git/*' -not -path '*/bin/*' 2>/dev/null

# Check sensitive file permissions
for f in .env .env.* *.pem *.key *.p12 id_rsa id_ed25519; do
    [ -f "$f" ] && ls -la "$f"
done

# Find files with SUID/SGID bits (Linux)
find / -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | head -20

# Check SSH key permissions
if [ -d ~/.ssh ]; then
    echo "--- SSH directory permissions ---"
    ls -la ~/.ssh/
    echo ""
    # Should be: dir=700, private keys=600, public keys=644, config=600
    [ "$(stat -c %a ~/.ssh 2>/dev/null || stat -f %Lp ~/.ssh)" != "700" ] && echo "WARNING: ~/.ssh should be 700"
fi
```

## Full Project Security Audit Script

```bash
#!/bin/bash
# security-audit.sh - Run a comprehensive security check on a project
set -euo pipefail

PROJECT_DIR="${1:-.}"
cd "$PROJECT_DIR"

echo "========================================="
echo "Security Audit: $(basename "$(pwd)")"
echo "Date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "========================================="
echo ""

ISSUES=0
warn() { echo "  [!] $1"; ((ISSUES++)); }
ok() { echo "  [OK] $1"; }
section() { echo ""; echo "--- $1 ---"; }

# 1. Secrets detection
section "Secret Detection"
for pattern in 'AKIA[0-9A-Z]\{16\}' 'BEGIN.*PRIVATE KEY' 'sk-[A-Za-z0-9]\{20,\}' \
               'ghp_[A-Za-z0-9]\{36\}' 'xox[bpoas]-'; do
    count=$(grep -rn "$pattern" --include='*.{js,ts,py,go,java,rb,env,yml,yaml,json,xml}' . 2>/dev/null | \
            grep -v 'node_modules\|\.git\|vendor\|__pycache__' | wc -l)
    if [ "$count" -gt 0 ]; then
        warn "Found $count matches for pattern: $pattern"
    fi
done
grep -rn -i 'password\s*[:=]\s*["'"'"'][^"'"'"']*["'"'"']' \
  --include='*.{js,ts,py,go,yml,yaml,json,env}' . 2>/dev/null | \
  grep -v 'node_modules\|\.git\|example\|test\|mock\|placeholder\|changeme\|xxxx' | \
  while read -r line; do warn "Hardcoded password: $line"; done

# 2. Dependency audit
section "Dependency Vulnerabilities"
if [ -f package-lock.json ] || [ -f package.json ]; then
    npm audit --audit-level=high 2>/dev/null && ok "npm: no high/critical vulns" || warn "npm audit found issues"
fi
if [ -f requirements.txt ]; then
    pip-audit -r requirements.txt 2>/dev/null && ok "pip: no known vulns" || warn "pip-audit found issues"
fi
if [ -f go.sum ]; then
    govulncheck ./... 2>/dev/null && ok "Go: no known vulns" || warn "govulncheck found issues"
fi

# 3. Gitignore check
section ".gitignore Coverage"
if [ ! -f .gitignore ]; then
    warn "No .gitignore file"
else
    for entry in '.env' 'node_modules' '*.key' '*.pem' '.DS_Store'; do
        grep -q "$entry" .gitignore 2>/dev/null && ok ".gitignore has $entry" || warn ".gitignore missing: $entry"
    done
fi

# 4. SSL verification disabled
section "SSL Verification"
disabled=$(grep -rn "verify\s*=\s*False\|rejectUnauthorized.*false\|InsecureSkipVerify.*true" \
  --include='*.{py,js,ts,go,java,rb}' . 2>/dev/null | \
  grep -v 'node_modules\|\.git\|test\|spec\|mock' | wc -l)
[ "$disabled" -gt 0 ] && warn "SSL verification disabled in $disabled location(s)" || ok "No SSL bypasses found"

# 5. CORS wildcard
section "CORS Configuration"
cors=$(grep -rn "Access-Control-Allow-Origin.*\*\|cors({.*origin.*true" \
  --include='*.{py,js,ts,go,java,rb}' . 2>/dev/null | \
  grep -v 'node_modules\|\.git' | wc -l)
[ "$cors" -gt 0 ] && warn "CORS wildcard found in $cors location(s)" || ok "No CORS wildcard"

# 6. Debug mode
section "Debug/Development Settings"
debug=$(grep -rn "DEBUG\s*=\s*True\|debug:\s*true" \
  --include='*.{py,yml,yaml,json}' . 2>/dev/null | \
  grep -v 'node_modules\|\.git\|test\|jest\|vitest' | wc -l)
[ "$debug" -gt 0 ] && warn "Debug mode enabled in $debug location(s)" || ok "No debug flags found"

echo ""
echo "========================================="
echo "Audit complete. Issues found: $ISSUES"
echo "========================================="
[ "$ISSUES" -eq 0 ] && exit 0 || exit 1
```

## Secure Coding Quick Reference

### Environment variables instead of hardcoded secrets

```bash
# Bad: hardcoded in source
API_KEY="sk-abc123..."

# Good: from environment
API_KEY="${API_KEY:?Error: API_KEY not set}"

# Good: from .env file (loaded at startup, never committed)
# .env
API_KEY=sk-abc123...
# .gitignore
.env
```

### Input validation checklist

```
- [ ] All user input validated (type, length, format)
- [ ] SQL queries use parameterized statements (never string concat)
- [ ] Shell commands never include user input directly
- [ ] File paths validated (no path traversal: ../)
- [ ] URLs validated (no SSRF: restrict to expected domains)
- [ ] HTML output escaped (no XSS: use framework auto-escaping)
- [ ] JSON parsing has error handling (no crash on malformed input)
- [ ] File uploads checked (type, size, no executable content)
```

### HTTP security headers

```bash
# Check security headers on a URL
curl -sI https://example.com | grep -i 'strict-transport\|content-security\|x-frame\|x-content-type\|referrer-policy\|permissions-policy'

# Expected headers:
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# Content-Security-Policy: default-src 'self'
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Referrer-Policy: strict-origin-when-cross-origin
# Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## Tips

- Run `npm audit` / `pip-audit` / `govulncheck` in CI on every pull request, not just occasionally.
- Secret detection in git history matters: even if a secret is removed from HEAD, it exists in git history. Use `git filter-branch` or `git-filter-repo` to purge, then rotate the credential.
- The most dangerous vulnerabilities are often the simplest: SQL injection via string concatenation, command injection via unsanitized input, XSS via `innerHTML`.
- CORS `Access-Control-Allow-Origin: *` is safe for truly public, read-only APIs. It's dangerous for anything that uses cookies or auth tokens.
- Always verify SSL in production. `verify=False` or `rejectUnauthorized: false` should only appear in test code, never in production paths.
- Defense in depth: validate input, escape output, use parameterized queries, enforce least privilege, and assume every layer might be bypassed.
