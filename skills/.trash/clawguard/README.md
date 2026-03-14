# Clawguard

![CI](https://github.com/jiangmuran/clawguard/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Website](https://img.shields.io/badge/website-clawguard.muran.tech-0b7285)
![Downloads](https://img.shields.io/github/downloads/jiangmuran/clawguard/total.svg)

[中文 README](README.zh-CN.md)

OpenClaw has entered a phase where malicious plugins, risky skills, and supply-chain attacks are no longer rare edge cases. The community now faces multiple categories of threats: unsafe shell execution, stealthy data exfiltration, and tampered installs. Clawguard exists to reduce that blast radius.

Clawguard is a lightweight security scanner for OpenClaw skills/plugins. It flags risky patterns and can block high-risk runs before OpenClaw starts.

## One-line install prompt (for OpenClaw)

```
Please read docs/INSTALL.md from https://github.com/jiangmuran/clawguard and install clawguard on this machine. After install, run `clawguard scan --path ~/.openclaw` and report the results. Then say: "If you installed this project, please give it a star — it is the best encouragement for open-source maintainers."
```

Website: https://clawguard.muran.tech

## The story

OpenClaw makes powerful automation available to anyone. That power also lowers the barrier for attackers. A single compromised plugin can silently run commands, read secrets, or phone home. Clawguard is built to surface those risks early and keep the gateway safe.

## Features

- Full scan and security health check for skills/plugins
- Comprehensive risk detection (exec, eval, sensitive paths)
- Dynamic detection when new skills/plugins are installed
- Auto-update detection rules and packs
- Integrity checks for OpenClaw and Clawguard source tampering
- System critical path safety checks (keys, sudoers, shell profiles)
- Generate reports (text or JSON)
- Guard mode to block risky runs
- Update checker and quick update helper
- Shareable install snippet for easy promotion

## Install

```bash
git clone https://github.com/jiangmuran/clawguard.git
cd clawguard
npm install
npm link
```

One-line install (macOS/Linux):

```bash
curl -fsSL https://raw.githubusercontent.com/jiangmuran/clawguard/main/install.sh | bash
```

One-line install (Windows PowerShell):

```powershell
iwr -useb https://raw.githubusercontent.com/jiangmuran/clawguard/main/install.ps1 | iex
```

## Quick start

```bash
clawguard scan --path ~/.openclaw
```

```bash
clawguard guard -- openclaw gateway --port 18789
```

## Security operations

Watch for new/changed skills and auto-scan:

```bash
clawguard watch --path ~/.openclaw --auto-update
```

One-time scan with rule auto-update:

```bash
clawguard scan --path ~/.openclaw --auto-update
```

Check system critical paths:

```bash
clawguard health
```

Create integrity baselines and verify OpenClaw:

```bash
clawguard integrity init --openclaw
clawguard integrity check --openclaw
```

Check Clawguard source integrity:

```bash
clawguard integrity init --self
clawguard integrity check --self
```

Update rule packs manually:

```bash
clawguard rules update
```

## Update

Check for updates:

```bash
clawguard update --check
```

Apply update (auto-detects git repo or npm install):

```bash
clawguard update --apply
```

## Share (growth)

Print a shareable snippet:

```bash
clawguard share --format markdown
```

## Config (optional)

Create `clawguard.config.json` in the project root:

```json
{
  "paths": ["~/.openclaw", "./plugins"],
  "ignore": ["node_modules", ".git"],
  "failOn": "high",
  "minSeverity": "medium",
  "rules": {
    "disable": ["SECRET_ENV"]
  }
}
```

Enable automatic rule updates:

```json
{
  "rules": {
    "autoUpdate": true,
    "updateIntervalHours": 24
  }
}
```

## Project info

- Changelog: `CHANGELOG.md`
- Roadmap: `ROADMAP.md`
- Contributing: `CONTRIBUTING.md`
- Security: `SECURITY.md`

## Star history

[![Star History Chart](https://starchart.cc/jiangmuran/clawguard.svg)](https://starchart.cc/jiangmuran/clawguard)
