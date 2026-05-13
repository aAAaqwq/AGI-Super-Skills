# OpenClaw Legal Integration

Complete setup and usage guide for integrating the legal self-improvement skill with OpenClaw.

## Overview

OpenClaw uses workspace-based prompt injection combined with event-driven hooks. Legal context is injected from workspace files at session start, and hooks trigger on lifecycle events to remind the agent about legal finding capture.

## Workspace Structure

```
~/.openclaw/
├── workspace/                   # Working directory
│   ├── AGENTS.md               # Legal workflows, contract review delegation
│   ├── SOUL.md                 # Legal principles, privilege protection
│   ├── TOOLS.md                # Legal tool configs, CLM integration
│   ├── CLAUSE_LIBRARY.md       # Standard clauses with positions and fallbacks
│   ├── COMPLIANCE.md           # Regulatory requirements and audit checklists
│   ├── PLAYBOOKS.md            # Contract negotiation and compliance playbooks
│   ├── RISK_REGISTER.md        # Recurring risk categories and mitigation plans
│   ├── MEMORY.md               # Long-term memory (main session only)
│   └── .learnings/             # Legal finding logs
│       ├── LEARNINGS.md
│       ├── LEGAL_ISSUES.md
│       └── FEATURE_REQUESTS.md
├── skills/                      # Installed skills
│   └── self-improving-legal/
│       └── SKILL.md
└── hooks/                       # Custom hooks
    └── self-improving-legal/
        ├── HOOK.md
        └── handler.ts
```

## Quick Setup

### 1. Install the Skill

```bash
clawdhub install self-improving-legal
```

Or copy manually:

```bash
cp -r self-improving-legal ~/.openclaw/skills/
```

### 2. Install the Hook (Optional)

Copy the hook to OpenClaw's hooks directory:

```bash
cp -r hooks/openclaw ~/.openclaw/hooks/self-improving-legal
```

Enable the hook:

```bash
openclaw hooks enable self-improving-legal
```

### 3. Create Learning Files

```bash
mkdir -p ~/.openclaw/workspace/.learnings
```

Or copy from `assets/`:

```bash
cp assets/LEARNINGS.md ~/.openclaw/workspace/.learnings/
cp assets/ERRORS.md ~/.openclaw/workspace/.learnings/LEGAL_ISSUES.md
cp assets/FEATURE_REQUESTS.md ~/.openclaw/workspace/.learnings/
```

## Injected Prompt Files

### AGENTS.md (Legal Workflows)

Purpose: Legal operations workflows and matter routing patterns.

```markdown
# Legal Agent Coordination

## Contract Review Workflow
1. Receive: Contract or amendment for review
2. Classify: Standard vs non-standard terms
3. Compare: Diff against original MSA or template
4. Flag: Deviations from clause library positions
5. Escalate: Red-line items to senior counsel
6. Document: Log clause risks to .learnings/

## Delegation Rules
- Use explore agent for clause pattern searches across contracts
- Spawn sub-agents for parallel regulatory research
- Use sessions_send to share urgent compliance findings across sessions
```

### SOUL.md (Legal Principles)

Purpose: Legal operations mindset and privilege protection.

```markdown
# Legal Principles

## Core Mindset
- Protect privilege: never document attorney-client communications
- Abstract to process: capture lessons, not confidential details
- Track deadlines: regulatory filings and statutes of limitations
- Standardize positions: use clause library for consistent negotiation

## Handling Privileged Information
- NEVER log attorney-client communications or work product
- NEVER record specific case strategy or litigation tactics
- NEVER document confidential settlement terms or amounts
- Always abstract to process-level lessons
- When in doubt, omit the detail entirely
```

### TOOLS.md (Legal Tools)

Purpose: Legal technology capabilities, CLM configurations, and integration notes.

```markdown
# Legal Tools

## Contract Lifecycle Management
- CLM platform for contract drafting, review, and execution
- Clause library integration for standard positions
- Signature tracking and deadline alerts

## Compliance Management
- Regulatory change monitoring feeds
- Compliance checklist automation
- Audit evidence collection and retention

## E-Discovery & Litigation
- Document hold and preservation tools
- Search and review platforms
- Matter management system
```

## Legal-Specific Promotion Decision Tree

```
Is the finding a one-off matter or broadly applicable?
├── One-off → Keep in .learnings/
└── Broadly applicable →
    ├── Clause pattern or fallback position? → CLAUSE_LIBRARY.md
    ├── Compliance requirement or control? → COMPLIANCE.md
    ├── Contract negotiation procedure? → PLAYBOOKS.md
    ├── Recurring risk category? → RISK_REGISTER.md
    ├── Tool configuration or gotcha? → TOOLS.md
    └── Workflow or matter routing? → AGENTS.md
```

## Inter-Agent Communication

OpenClaw provides tools for cross-session sharing of legal findings.

Use these only when cross-session sharing is explicitly needed and the environment is trusted. **Never forward privileged communications, case strategy, or confidential terms.**

### sessions_send (Legal Alerts)

Send urgent legal findings to other sessions:
```
sessions_send(sessionKey="session-id", message="LEGAL: Vendor changed payment terms in renewal without flagging. See LEG-20260412-001.")
```

Prefer sending a concise finding summary plus entry ID rather than raw details.

### sessions_spawn (Legal Research)

Spawn background agents for legal tasks:
```
sessions_spawn(task="Research EU AI Act Annex III classification for recommendation engines", label="legal-research")
```

## OpenClaw-Specific Detection Triggers

| Trigger | Action |
|---------|--------|
| Contract review identifies clause risk | Log to LEARNINGS.md with clause_risk category |
| Compliance audit reveals gap | Log to LEARNINGS.md with compliance_gap category |
| Regulatory change published | Log to LEARNINGS.md with regulatory_change category |
| Contract deviation found | Log to LEGAL_ISSUES.md with contract_deviation category |
| Cross-session legal alert | Evaluate and log locally if applicable |

## Available Hook Events

| Event | When It Fires |
|-------|---------------|
| `agent:bootstrap` | Before workspace files inject |
| `command:new` | When `/new` command issued |
| `command:reset` | When `/reset` command issued |
| `command:stop` | When `/stop` command issued |
| `gateway:startup` | When gateway starts |

## Verification

Check hook is registered:

```bash
openclaw hooks list
```

Check skill is loaded:

```bash
openclaw status
```

## Troubleshooting

### Hook not firing

1. Ensure hooks enabled in config
2. Restart gateway after config changes
3. Check gateway logs for errors

### Learnings not persisting

1. Verify `.learnings/` directory exists
2. Check file permissions
3. Ensure workspace path is configured correctly

### Skill not loading

1. Check skill is in skills directory
2. Verify SKILL.md has correct frontmatter
3. Run `openclaw status` to see loaded skills
