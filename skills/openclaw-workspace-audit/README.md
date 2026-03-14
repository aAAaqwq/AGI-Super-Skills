<![CDATA[<!-- SEO: openclaw-workspace-audit – OpenClaw skill for auditing, optimizing, and cleaning up AI agent workspace files. Reduce token waste, fix redundancy, detect conflicts in AGENTS.md, SOUL.md, USER.md, TOOLS.md, MEMORY.md. -->

<div align="center">

# openclaw-workspace-audit

**An OpenClaw skill that audits, optimizes, and cleans up your AI agent workspace — reduce token waste, remove redundancy, detect conflicts, enforce compliance.**

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-purple.svg)](https://github.com/openclaw)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)]()

English | [简体中文](./README.zh-CN.md)

</div>

---

## Why This Skill?

OpenClaw workspace files (`AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `MEMORY.md`, etc.) are injected into **every AI session as system prompt**. Over time, they accumulate problems:

| Problem | Impact | This Skill Fixes It |
|---------|--------|---------------------|
| **Bloated AGENTS.md** | Burns tokens every single session | Token diet — compress verbose instructions |
| **Duplicate rules across files** | Confuses the AI agent, wastes context | Cross-file redundancy detection |
| **Dead references** | Points to files/tools that no longer exist | Dead content scanner |
| **SOUL.md contains operating instructions** | Role bleeding — wrong file, wrong behavior | Role separation enforcement |
| **Stale memory entries** | Outdated facts pollute every session | Memory cleanup + archival |
| **No idea how many tokens your workspace costs** | Invisible overhead you pay every message | Per-file token audit with budget targets |

> **TL;DR** — Your OpenClaw workspace files are your AI agent's "brain." This skill is the doctor — it diagnoses bloat, finds conflicts, and prescribes targeted fixes, all without touching a single file until you approve.

## What It Does

### 7-Phase Audit Workflow

```
Phase 0: Pre-flight     → Scan all files, report sizes & token estimates
Phase 1: Compliance      → Check each file against official OpenClaw templates
Phase 2: Redundancy      → Find duplicate/dead content across files
Phase 3: Token Efficiency → Calculate savings, rank optimization opportunities
Phase 4: Conflict Detect  → Catch contradictory instructions between files
Phase 5: Report           → Structured report with numbered action items
Phase 6: Execute          → Apply approved changes with surgical edits
Phase 7: Memory Cleanup   → Archive stale memories, fix naming conventions
```

### Audit Scopes (User Chooses)

| Scope | Description |
|-------|-------------|
| **Full audit** | All files, all checks |
| **Token diet** | Focus on reducing always-injected file sizes |
| **Memory cleanup** | Focus on `MEMORY.md` + `memory/` hygiene |
| **Compliance check** | Format/spec issues only |
| **Single file** | Audit one specific file |

### Files It Audits

| File | Loaded When | Token Impact |
|------|-------------|-------------|
| `AGENTS.md` | Every session (system prompt) | **HIGH** — always injected |
| `SOUL.md` | Every session (system prompt) | **HIGH** — always injected |
| `USER.md` | Every session (system prompt) | **HIGH** — always injected |
| `TOOLS.md` | Every session (system prompt) | **HIGH** — always injected |
| `IDENTITY.md` | Every session (system prompt) | MEDIUM |
| `HEARTBEAT.md` | Each heartbeat poll | LOW |
| `BOOT.md` | Gateway restart | LOW |
| `MEMORY.md` | Main session only | **HIGH** |
| `memory/*.md` | On-demand via tools | LOW |

### Safety Guarantees

- **Read-only by default** — never modifies files without explicit approval
- **Propose, don't execute** — shows exact diffs before any change
- **Preserve semantics** — every removal must prove meaning is retained
- **Numbered choices** — reply with a digit at every decision point
- **No auto-scheduling** — cron scheduling only offered after audit completes

## Install

### One-liner

```bash
mkdir -p ~/.openclaw/skills && cd ~/.openclaw/skills && git clone https://github.com/gaoryan86/openclaw-workspace-audit.git
```

### Step by Step

```bash
# 1. Navigate to your OpenClaw skills directory
mkdir -p ~/.openclaw/skills
cd ~/.openclaw/skills

# 2. Clone this skill
git clone https://github.com/gaoryan86/openclaw-workspace-audit.git

# 3. Restart OpenClaw (or reload skills if supported)
```

### Trigger Phrases

Once installed, invoke by asking your AI agent any of these:

| English | 中文 |
|---------|------|
| "audit workspace" | "审计文档" |
| "clean up memory" | "清理记忆" |
| "optimize tokens" | "优化 token" |
| "check compliance" | "检查合规" |
| "reduce token waste" | "精简文档" |

## Example Output

After running a full audit, the skill produces a structured report:

```markdown
## Audit Report — 2026-03-03

### Summary
- Files audited: 8
- Total workspace tokens: ~4.2K
- Issues found: 11 (3 critical, 5 warnings, 3 info)

### Critical issues (must fix)
- ❌ AGENTS.md: 347 lines (recommended max: ~150)
- ❌ Duplicate safety rules in both AGENTS.md and SOUL.md
- ❌ TOOLS.md contains skill documentation (should be in SKILL.md)

### Optimization opportunities
| Change              | File       | Token savings | Risk |
|---------------------|------------|--------------|------|
| Compress verbose rules | AGENTS.md | ~280 tokens  | Low  |
| Remove dead tool refs  | TOOLS.md  | ~150 tokens  | Low  |
| Dedupe safety rules    | SOUL.md   | ~120 tokens  | Med  |

### Recommended actions (numbered)
1. Apply all safe changes
2. Apply critical only
3. Export plan for later
4. Do nothing
```

## Token Budget Reference

From official OpenClaw docs — recommended targets for workspace files:

| File | Recommended Max | Rationale |
|------|----------------|-----------|
| `AGENTS.md` | ~4,000 chars (~1K tokens) | Injected every session |
| `SOUL.md` | ~2,000 chars (~500 tokens) | Injected every session |
| `USER.md` | ~1,500 chars (~375 tokens) | Injected every session |
| `TOOLS.md` | ~3,000 chars (~750 tokens) | Injected every session |
| `IDENTITY.md` | ~500 chars (~125 tokens) | Small by design |
| `HEARTBEAT.md` | ~500 chars (~125 tokens) | Runs often |
| `MEMORY.md` | ~8,000 chars (~2K tokens) | Main session only |

These are soft targets for awareness, not hard limits.

## Anti-Patterns Detected

The skill flags these common issues:

- `AGENTS.md` over 300 lines (official template is ~150)
- `SOUL.md` containing operating instructions (belongs in AGENTS.md)
- `TOOLS.md` containing general skill docs (belongs in SKILL.md files)
- `MEMORY.md` containing raw daily logs (belongs in `memory/`)
- `HEARTBEAT.md` over 30 lines (token burn on every heartbeat)
- Secrets/API keys in any workspace file
- `memory/` files with non-date filenames
- Duplicate safety rules across files

## Files

```
openclaw-workspace-audit/
├── SKILL.md     # Skill definition & full audit workflow
├── README.md    # This file
└── LICENSE      # MIT
```

## Use Cases

- **New OpenClaw users** — validate your workspace setup against best practices
- **Power users with large workspaces** — find and fix accumulated bloat
- **Token-conscious developers** — know exactly how many tokens your workspace costs per session
- **Teams sharing workspace configs** — enforce consistency and catch conflicts
- **Periodic maintenance** — schedule monthly audits to keep your workspace lean

## FAQ

<details>
<summary><strong>Will this skill modify my files automatically?</strong></summary>

No. The skill is read-only by default. It proposes changes with exact diffs and waits for your explicit approval before making any edits.
</details>

<details>
<summary><strong>Does it work with any OpenClaw version?</strong></summary>

Yes. It references official templates and adapts to whatever files exist in your workspace. Missing files are noted but don't block the audit.
</details>

<details>
<summary><strong>How often should I run it?</strong></summary>

Monthly is recommended. The skill can optionally set up a cron reminder after your first audit.
</details>

<details>
<summary><strong>Can I audit just one file?</strong></summary>

Yes. Choose "Single file" scope during the pre-flight phase.
</details>

## Contributing

PRs welcome. Please keep the skill single-file (`SKILL.md`) for easy installation.

## License

MIT License. See [`LICENSE`](./LICENSE).

---

<div align="center">

**openclaw-workspace-audit** — Keep your AI agent's brain clean and efficient.

</div>
]]>
