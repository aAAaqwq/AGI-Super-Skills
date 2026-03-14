---
name: openclaw-workspace-audit
description: Audit and optimize OpenClaw workspace documents (AGENTS.md, SOUL.md, USER.md, TOOLS.md, IDENTITY.md, HEARTBEAT.md, BOOT.md, MEMORY.md, memory/) for redundancy, dead content, format compliance, cross-file conflicts, and token efficiency. Use when user asks to audit workspace files, check document health, reduce token usage, clean up memory, or optimize agent configuration. Triggers on "audit workspace", "check my docs", "optimize tokens", "clean up memory", "workspace health", "文档审计", "精简文档", "token优化".
---

# Workspace Audit

Audit OpenClaw workspace documents for redundancy, compliance, conflicts, and token efficiency. Propose targeted fixes without losing meaning or breaking agent behavior.

## Scope

Auditable files (all workspace-relative):

| File | Role | Loaded | Token impact |
|------|------|--------|-------------|
| `AGENTS.md` | Operating instructions | Every session (system prompt) | HIGH — always injected |
| `SOUL.md` | Persona/tone | Every session (system prompt) | HIGH — always injected |
| `USER.md` | User profile | Every session (system prompt) | HIGH — always injected |
| `TOOLS.md` | Local tool notes | Every session (system prompt) | HIGH — always injected |
| `IDENTITY.md` | Agent identity | Every session (system prompt) | MEDIUM — small file |
| `HEARTBEAT.md` | Heartbeat tasks | Each heartbeat poll | LOW — only on heartbeat |
| `BOOT.md` | Startup checklist | Gateway restart (hooks) | LOW — only on boot |
| `MEMORY.md` | Long-term memory | Main session only | HIGH — main session |
| `memory/*.md` | Daily logs | On-demand via memory tools | LOW — not auto-injected |

**Not in scope:** `~/.openclaw/openclaw.json`, `~/.openclaw/skills/`, session transcripts, OS/host security (use `healthcheck` skill for those).

## Core rules

- **Read-only by default.** Never modify files without explicit approval.
- **Propose, don't execute.** Show exact diffs/rewrites and wait for go-ahead.
- **Preserve semantics.** Every removal must prove the meaning is retained or the content is genuinely dead.
- **Numbered choices** for every decision point so user can reply with a digit.
- **No auto-scheduling.** Only offer cron scheduling after audit completes.

## Workflow

### Phase 0: Pre-flight

1. Confirm the workspace path (default: repo root from runtime metadata).
2. Read each file and record: exists / missing / line count / estimated char count.
3. Present a **summary table** with file sizes and token estimates (~4 chars/token).
4. Ask which audit scope to run (numbered):
   1. **Full audit** — all files, all checks
   2. **Token diet** — focus on reducing token consumption of always-injected files
   3. **Memory cleanup** — focus on `MEMORY.md` + `memory/` hygiene
   4. **Compliance check** — format/spec issues only
   5. **Single file** — user picks one file to audit

### Phase 1: Format compliance

For each file, compare against the official template at:
`/opt/homebrew/lib/node_modules/openclaw/docs/reference/templates/<FILE>.md`

Check:

- **AGENTS.md**: Has required sections (First Run, Every Session, Memory, Safety)? Uses correct memory file paths (`memory/YYYY-MM-DD.md`)? References `SOUL.md`, `USER.md`, `MEMORY.md` correctly?
- **SOUL.md**: Defines persona boundaries? Includes continuity guidance? Avoids duplicating AGENTS.md operating instructions?
- **USER.md**: Has Name, Timezone, Notes? Avoids embedding secrets or API keys?
- **TOOLS.md**: Contains only environment-specific notes (not general skill instructions)? Avoids duplicating skill SKILL.md content?
- **IDENTITY.md**: Has Name, Creature, Vibe, Emoji fields? Avatar path valid?
- **HEARTBEAT.md**: Short enough to avoid token burn? Tasks are actionable, not stale?
- **BOOT.md**: Short, explicit startup instructions? Uses message tool for outbound?
- **MEMORY.md**: Only loaded in main session? Contains curated long-term info, not raw daily logs?
- **memory/*.md**: Follows `YYYY-MM-DD.md` naming? No timestamp filenames? No stale files older than configured retention?

Report each finding as: ✅ Pass / ⚠️ Warning / ❌ Fail with one-line explanation.

### Phase 2: Redundancy & dead content

Scan for:

1. **Cross-file duplication** — Same rule/instruction appearing in multiple files (e.g., safety rules in both AGENTS.md and SOUL.md).
2. **Internal duplication** — Repeated content within a single file.
3. **Dead references** — Mentions of tools, paths, files, or projects that no longer exist. Verify by checking filesystem.
4. **Obsolete rules** — Instructions tied to old OpenClaw versions or deprecated features. Cross-check against current docs at `/opt/homebrew/lib/node_modules/openclaw/docs/`.
5. **Stale memory entries** — `MEMORY.md` items superseded by newer entries, or daily memory files with content already distilled into `MEMORY.md`.

For each finding, report:
- **What**: the duplicated/dead content (quote it)
- **Where**: file + line range
- **Why it's removable**: brief justification
- **Risk if removed**: what breaks (if anything)

### Phase 3: Token efficiency

Calculate and report:

1. **Per-file char/token estimate** for always-injected files.
2. **Total system prompt overhead** from workspace files (sum of AGENTS + SOUL + USER + TOOLS + IDENTITY + HEARTBEAT if present + MEMORY if main session).
3. **Reduction opportunities** ranked by token savings:
   - Verbose explanations that can be compressed
   - Examples/templates that can move to reference files
   - Comments/notes that are self-documenting and add no instruction value
   - Markdown formatting overhead (excessive headers, tables where bullets suffice)

Present a **before/after** comparison: current tokens vs projected tokens after proposed changes.

### Phase 4: Cross-file conflict detection

Check for:

1. **Contradictory instructions** — e.g., AGENTS.md says "always ask before external actions" but SOUL.md says "be bold with internal ones" (not a conflict) vs actual contradictions.
2. **Role bleeding** — Operating instructions in SOUL.md (should be in AGENTS.md), persona rules in AGENTS.md (should be in SOUL.md), tool-specific notes in AGENTS.md (should be in TOOLS.md).
3. **Memory policy conflicts** — Different memory rules in AGENTS.md vs actual MEMORY.md structure.
4. **Group chat rules** — Conflicting engagement rules across files.

### Phase 5: Report & remediation

Produce a structured report:

```
## Audit Report — [date]

### Summary
- Files audited: N
- Total workspace tokens: ~XXXK
- Issues found: N (X critical, Y warnings, Z info)

### Critical issues (must fix)
...

### Warnings (should fix)
...

### Optimization opportunities
| Change | File | Token savings | Risk |
|--------|------|--------------|------|
| ... | ... | ~NNN tokens | Low/Med/High |

### Recommended actions (numbered)
1. ...
2. ...
3. Skip / do nothing
```

After presenting the report, offer (numbered):
1. **Apply all safe changes** — execute low-risk fixes with user approval per file
2. **Apply critical only** — fix only ❌ items
3. **Export plan** — write remediation plan to a file for later
4. **Do nothing** — report only

### Phase 6: Execute (if approved)

For each approved change:
1. Show the exact edit (old → new) before applying.
2. Apply via `edit` tool (surgical edits, not full rewrites).
3. After all edits, re-calculate token counts and show the delta.

### Phase 7: Memory cleanup (if scope includes memory)

For `memory/` directory:
1. List all files with dates and sizes.
2. Identify files older than 30 days that have NOT been distilled into `MEMORY.md`.
3. Identify files with naming violations (timestamps, slugs instead of `YYYY-MM-DD.md`).
4. Propose archival or deletion (never auto-delete — always ask).

For `MEMORY.md`:
1. Check for entries superseded by newer facts.
2. Check for entries that are purely narrative (no actionable conclusion).
3. Propose condensation where possible.

## Anti-patterns to flag

- `AGENTS.md` over 300 lines (official template is ~150 lines; bloat hurts every session)
- `SOUL.md` containing operating instructions (belongs in AGENTS.md)
- `TOOLS.md` containing general skill documentation (belongs in skill SKILL.md files)
- `MEMORY.md` containing raw daily logs (belongs in `memory/YYYY-MM-DD.md`)
- `HEARTBEAT.md` over 30 lines (token burn on every heartbeat)
- Secrets/API keys in any workspace file (should be in `~/.openclaw/` or env vars)
- `memory/` files with non-date filenames (violates convention)
- Duplicate safety rules across AGENTS.md and SOUL.md

## Token budget reference

From official docs (`bootstrapMaxChars` default: 20,000 per file; `bootstrapTotalMaxChars` default: 150,000 total):

| File | Recommended max | Rationale |
|------|----------------|-----------|
| AGENTS.md | ~4,000 chars (~1K tokens) | Injected every session |
| SOUL.md | ~2,000 chars (~500 tokens) | Injected every session |
| USER.md | ~1,500 chars (~375 tokens) | Injected every session |
| TOOLS.md | ~3,000 chars (~750 tokens) | Injected every session |
| IDENTITY.md | ~500 chars (~125 tokens) | Small by design |
| HEARTBEAT.md | ~500 chars (~125 tokens) | Runs often |
| MEMORY.md | ~8,000 chars (~2K tokens) | Main session only |

These are soft targets, not hard limits. The goal is awareness, not enforcement.

## Memory writes

After a completed audit, if the user opts in, append a dated summary to `memory/YYYY-MM-DD.md`:
- Files audited and their sizes
- Key findings (issues found, tokens saved)
- Actions taken
- Any deferred items

Append-only. Never overwrite existing entries. Redact sensitive details.

## Scheduling

After a completed audit, offer to schedule periodic re-audits via cron (numbered):
1. Monthly audit reminder (recommended)
2. Weekly audit reminder
3. No scheduling

Use stable cron name: `workspace-audit:periodic`. Check for existing job before creating.
