---
name: openclaw-shield
description: Security audit engine for OpenClaw configurations. Detects vulnerabilities, misconfigurations, secret leaks, and over-privileged agents. Use when the user asks about security, hardening, config review, or audit of their OpenClaw setup.
metadata: {"openclaw":{"emoji":"🛡️","homepage":"https://github.com/autonomous-intelligence/openclaw-shield"}}
---

# OpenClaw Shield — Security Audit

Audit any OpenClaw config for security vulnerabilities, misconfigurations, and best-practice violations. Produces a structured JSON report with risk scores, findings, and remediation steps.

## When to Use

- User asks to check/audit/review their OpenClaw security
- User wants to harden their config before deploying
- User is setting up a new OpenClaw instance
- User asks about secret leakage or API key exposure in their config
- Before publishing or sharing any config file

## Quick Audit (live config)

```bash
node scripts/shield-audit.sh
```

Or directly:

```bash
node SKILL_DIR/bin/shield.js audit ~/.openclaw/openclaw.json --summary
```

## What It Checks (11 categories)

1. **Gateway Auth** — missing/weak auth, insecure UI settings
2. **Network Exposure** — bind address, Tailscale funnel, wildcard proxies
3. **Channel Security** — wildcard allowFrom, missing allowlists
4. **DM Policy** — open DM policy without pairing
5. **Subagent Permissions** — wildcard allowAgents, circular delegation chains, self-delegation
6. **Tool Permissions** — over-privileged agents with tools.profile: "full"
7. **Secret Leakage** — API keys, tokens, private keys in plaintext config
8. **Sandbox/Execution** — missing workspace isolation, no execution policies
9. **Plugin Config** — enabled plugins without channel config
10. **Heartbeat Exposure** — sensitive data in heartbeat prompts
11. **Remote Config** — unencrypted WebSocket, exposed remote URLs/tokens

## Usage

### Audit a config file
```bash
node SKILL_DIR/bin/shield.js audit <config.json>
node SKILL_DIR/bin/shield.js audit <config.json> --summary   # human-readable
```

### Audit from stdin
```bash
cat config.json | node SKILL_DIR/bin/shield.js audit --stdin
```

### Sanitize a config (strip secrets)
```bash
node SKILL_DIR/bin/shield.js sanitize <config.json>
```

### Programmatic use
```javascript
const { auditConfig } = require('SKILL_DIR/src/audit');
const config = require('./openclaw.json');
const report = auditConfig(config);
console.log(report.risk_level);      // "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
console.log(report.overall_score);   // 0-100
console.log(report.vulnerabilities); // detailed findings
```

## Output

Returns JSON with: `risk_level`, `overall_score` (0-100), `vulnerabilities[]`, `vulnerability_count`, `best_practices_compliance`, `action_recommended`, `safe_to_deploy`, `audit_timestamp`.

## Workflow for Agent

1. Load the user's config: `cat ~/.openclaw/openclaw.json`
2. Run: `node SKILL_DIR/bin/shield.js audit ~/.openclaw/openclaw.json --summary`
3. Present findings to user with prioritized recommendations
4. Offer to sanitize before sharing: `node SKILL_DIR/bin/shield.js sanitize <file>`
