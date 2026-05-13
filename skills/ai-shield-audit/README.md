# 🛡️ OpenClaw Shield

**Security audit engine for OpenClaw configurations.** Find vulnerabilities, misconfigurations, and secret leaks before they become breaches.

Built by [Autonomous Intelligence](https://autonomousintelligence.ai) — we run 9 agents in production. We know what breaks.

## Features

- **11 security check categories** covering auth, networking, channels, agents, secrets, and more
- **Structured JSON reports** with risk scores, severity levels, and remediation steps
- **Config sanitizer** to strip secrets before sharing
- **CLI tool** for quick audits
- **Zero dependencies** — pure Node.js, no npm install needed

## Quick Start

```bash
# Audit your live config
node bin/shield.js audit ~/.openclaw/openclaw.json --summary

# Get JSON report
node bin/shield.js audit ~/.openclaw/openclaw.json

# Strip secrets before sharing
node bin/shield.js sanitize ~/.openclaw/openclaw.json > safe-config.json
```

## Sample Output

```
╔══════════════════════════════════════════════════╗
║         🛡️  OpenClaw Shield Audit Report         ║
╚══════════════════════════════════════════════════╝

  Risk Level:    HIGH
  Score:         42/100
  Safe to Deploy: ❌ No
  Action:        REVIEW_AND_REMEDIATE

  Vulnerabilities: 12
    🔴 Critical: 2
    🟠 High:     3
    🟡 Medium:   4
    🔵 Low:      3
```

## Security Checks

| # | Category | What It Catches |
|---|----------|----------------|
| 1 | Gateway Auth | Missing auth token, insecure UI, weak tokens |
| 2 | Network Exposure | Non-loopback bind, Tailscale funnel, wildcard proxies |
| 3 | Channel Security | Wildcard allowFrom, missing allowlists |
| 4 | DM Policy | Open DM policy without pairing |
| 5 | Subagent Permissions | Wildcard allowAgents, circular chains, self-spawn |
| 6 | Tool Permissions | Over-privileged agents (full tool access) |
| 7 | Secret Leakage | API keys, tokens, private keys in plaintext |
| 8 | Sandbox/Execution | Missing workspace isolation, no exec policies |
| 9 | Plugin Config | Orphaned plugins, missing channel configs |
| 10 | Heartbeat Exposure | Sensitive data in heartbeat prompts |
| 11 | Remote Config | Unencrypted WebSocket, exposed remote tokens |

## JSON Report Schema

```json
{
  "risk_level": "CRITICAL|HIGH|MEDIUM|LOW",
  "overall_score": 0-100,
  "vulnerabilities": [{
    "category": "string",
    "severity": "critical|high|medium|low",
    "issue": "Description of the problem",
    "recommendation": "How to fix it",
    "auto_fix": { "path": "config.path", "value": "suggested_value" }
  }],
  "vulnerability_count": { "critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0 },
  "best_practices_compliance": 0.0-1.0,
  "action_recommended": "BLOCK|REVIEW_AND_REMEDIATE|APPROVE",
  "safe_to_deploy": true|false,
  "audit_timestamp": "ISO8601",
  "engine_version": "1.0.0"
}
```

## Programmatic Usage

```javascript
const { auditConfig } = require('./src/audit');
const { sanitizeConfig } = require('./src/sanitize');

// Audit
const config = require('./my-openclaw.json');
const report = auditConfig(config);

if (!report.safe_to_deploy) {
  console.log(`${report.vulnerability_count.critical} critical issues found!`);
}

// Sanitize before sharing
const clean = sanitizeConfig(config);
```

## Pricing

- **Local audit:** Free (install the skill, run locally)
- **Premium remote audit:** $0.10/audit via ACP (deeper analysis + auto-fix patches)

## License

MIT — Autonomous Intelligence 2026
