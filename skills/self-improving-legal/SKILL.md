---
name: self-improving-legal
description: "Captures clause risks, compliance gaps, precedent shifts, contract deviations, regulatory changes, and litigation exposure to enable continuous legal operations improvement. Use when: (1) An unfavorable clause is accepted or slips through review, (2) A compliance deadline is missed or approaching, (3) A new regulation impacts the organization, (4) A contract remains unsigned past SLA, (5) An IP infringement notice is received, (6) New case law changes interpretation in a relevant jurisdiction, (7) A data subject access request reveals process gaps."
---

# Self-Improving Legal Skill

Log legal learnings, compliance findings, contract issues, and regulatory changes to markdown files for continuous improvement. Captures clause risks, compliance gaps, precedent shifts, contract deviations, regulatory changes, and litigation exposure. Important learnings get promoted to clause libraries, compliance checklists, regulatory trackers, contract playbooks, or risk registers.

## CRITICAL: Privilege & Confidentiality Protection

**NEVER log privileged attorney-client communications, specific case strategy, confidential settlement terms, or litigation work product in any learning or issue entry.** Always abstract findings to process-level lessons. Use generalized descriptions:

| Protected Information | Acceptable Abstraction |
|----------------------|----------------------|
| Attorney-client advice on specific matter | "Outside counsel recommended clause revision for indemnity cap" |
| Settlement amount or terms | "Settlement reached; update playbook to flag similar exposure earlier" |
| Litigation strategy details | "Discovery phase revealed need for better document retention process" |
| Privileged legal memoranda | "Internal review identified gap in force majeure clause coverage" |
| Specific opposing party positions | "Counterparty negotiation pattern: late-stage payment term changes" |
| Confidential deal terms | "Deal structure required non-standard IP assignment clause" |

When in doubt, omit the specific detail and log only the process improvement lesson. Privilege waiver through careless documentation is irreversible.

## First-Use Initialisation

Before logging anything, ensure the `.learnings/` directory and files exist in the project or workspace root. If any are missing, create them:

```bash
mkdir -p .learnings
[ -f .learnings/LEARNINGS.md ] || printf "# Legal Learnings\n\nClause risks, compliance gaps, precedent shifts, regulatory changes, and legal operations insights.\n\n**Categories**: clause_risk | compliance_gap | precedent_shift | contract_deviation | regulatory_change | litigation_exposure\n**Areas**: contracts | compliance | litigation | intellectual_property | privacy | regulatory | corporate_governance\n\n---\n" > .learnings/LEARNINGS.md
[ -f .learnings/LEGAL_ISSUES.md ] || printf "# Legal Issues Log\n\nContract disputes, compliance failures, regulatory impacts, and litigation matters.\n\n---\n" > .learnings/LEGAL_ISSUES.md
[ -f .learnings/FEATURE_REQUESTS.md ] || printf "# Legal Operations Feature Requests\n\nLegal technology, automation, and process improvement requests.\n\n---\n" > .learnings/FEATURE_REQUESTS.md
```

Never overwrite existing files. This is a no-op if `.learnings/` is already initialised.

Do not log privileged communications, specific case strategy, or confidential settlement terms. Abstract all entries to process-level lessons.

If you want automatic reminders, use the opt-in hook workflow described in [Hook Integration](#hook-integration).

## Quick Reference

| Situation | Action |
|-----------|--------|
| Unfavorable clause accepted in contract | Log to `.learnings/LEARNINGS.md` with category `clause_risk` |
| Compliance deadline missed or approaching | Log to `.learnings/LEGAL_ISSUES.md` with category `compliance_gap` |
| New regulation impacts the organization | Log to `.learnings/LEARNINGS.md` with category `regulatory_change` |
| Contract unsigned past SLA | Log to `.learnings/LEGAL_ISSUES.md` with category `contract_deviation` |
| IP infringement notice received | Log to `.learnings/LEGAL_ISSUES.md` with category `litigation_exposure` |
| New case law in relevant jurisdiction | Log to `.learnings/LEARNINGS.md` with category `precedent_shift` |
| Data subject access request reveals gaps | Log to `.learnings/LEARNINGS.md` with category `compliance_gap` |
| Vendor changed terms without flagging | Log to `.learnings/LEGAL_ISSUES.md` with category `contract_deviation` |
| Regulatory filing deadline within 30 days | Log to `.learnings/LEGAL_ISSUES.md` with priority `high` |
| Contract redline rejected 3+ times | Log to `.learnings/LEARNINGS.md` with category `clause_risk` |
| Similar to existing entry | Link with `**See Also**`, consider priority bump |
| Broadly applicable legal pattern | Promote to clause library, compliance checklist, or playbook |
| Proven compliance workflow | Promote to `AGENTS.md` (OpenClaw workspace) |
| Legal tool configuration | Promote to `TOOLS.md` (OpenClaw workspace) |
| Legal operations principles | Promote to `SOUL.md` (OpenClaw workspace) |

## OpenClaw Setup (Recommended)

OpenClaw is the primary platform for this skill. It uses workspace-based prompt injection with automatic skill loading.

### Installation

**Via ClawdHub (recommended):**
```bash
clawdhub install self-improving-legal
```

**Manual:**
```bash
git clone https://github.com/jose-compu/self-improving-legal.git ~/.openclaw/skills/self-improving-legal
```

### Workspace Structure

OpenClaw injects these files into every session:

```
~/.openclaw/workspace/
├── AGENTS.md          # Legal workflows, contract review delegation
├── SOUL.md            # Legal principles, privilege protection, confidentiality
├── TOOLS.md           # Legal tool capabilities, CLM configs, e-discovery
├── MEMORY.md          # Long-term memory (main session only)
├── memory/            # Daily memory files
│   └── YYYY-MM-DD.md
└── .learnings/        # This skill's log files
    ├── LEARNINGS.md
    ├── LEGAL_ISSUES.md
    └── FEATURE_REQUESTS.md
```

### Create Learning Files

```bash
mkdir -p ~/.openclaw/workspace/.learnings
```

Then create the log files (or copy from `assets/`):
- `LEARNINGS.md` — clause risks, compliance gaps, regulatory changes, precedent shifts
- `LEGAL_ISSUES.md` — contract disputes, compliance failures, litigation matters
- `FEATURE_REQUESTS.md` — legal technology and automation requests

### Promotion Targets

When legal learnings prove broadly applicable, promote them:

| Learning Type | Promote To | Example |
|---------------|------------|---------|
| Clause patterns | Clause library | "Always cap indemnity at 2x annual contract value" |
| Compliance requirements | Compliance checklist | "CCPA deletion must cover backup systems within 90 days" |
| Regulatory tracking | Regulatory tracker | "EU AI Act model documentation deadline Q1 2026" |
| Contract negotiation patterns | Contract playbook | "Vendor payment term changes require VP approval" |
| Risk patterns | Risk register | "Unlimited liability clauses in SaaS agreements" |
| Legal operations workflows | `AGENTS.md` | "Route IP matters to patent counsel within 48 hours" |

### Optional: Enable Hook

For automatic reminders at session start:

```bash
cp -r hooks/openclaw ~/.openclaw/hooks/self-improving-legal
openclaw hooks enable self-improving-legal
```

See `references/openclaw-integration.md` for complete details.

---

## Generic Setup (Other Agents)

For Claude Code, Codex, Copilot, or other agents, create `.learnings/` in the project or workspace root:

```bash
mkdir -p .learnings
```

Create the files inline using the headers shown above. Avoid reading templates from the current repo or workspace unless you explicitly trust that path.

### Add reference to agent files

Add to AGENTS.md, CLAUDE.md, or `.github/copilot-instructions.md`:

#### Legal Self-Improvement Workflow

When legal issues or findings occur:
1. Log to `.learnings/LEGAL_ISSUES.md`, `LEARNINGS.md`, or `FEATURE_REQUESTS.md`
2. **NEVER log privileged communications, case strategy, or settlement terms**
3. Review and promote broadly applicable findings to:
   - Clause libraries — reusable clause language and fallback positions
   - Compliance checklists — regulatory requirement tracking
   - Contract playbooks — negotiation patterns and escalation guides
   - Risk registers — recurring risk categories and mitigation plans

## Logging Format

### Learning Entry [LRN-YYYYMMDD-XXX]

Append to `.learnings/LEARNINGS.md`:

```markdown
## [LRN-YYYYMMDD-XXX] category

**Logged**: ISO-8601 timestamp
**Priority**: low | medium | high | critical
**Status**: pending
**Area**: contracts | compliance | litigation | intellectual_property | privacy | regulatory | corporate_governance

### Summary
One-line description of the legal insight or finding

### Details
Full context: what clause, regulation, or precedent was involved, why it matters,
what the correct approach or fallback position is. NEVER include privileged
attorney-client communications or confidential settlement terms.

### Recommended Action
Specific clause revision, compliance step, filing, or process change

### Metadata
- Source: contract_review | regulatory_update | case_law | audit | negotiation | litigation
- Jurisdiction: US-Federal | US-CA | EU | UK | other
- Related Files: path/to/contract.docx, path/to/policy.md
- Tags: tag1, tag2
- Regulation: GDPR | CCPA | SOX | HIPAA | EU-AI-Act (if applicable)
- See Also: LRN-20260110-001 (if related to existing entry)
- Pattern-Key: clause.indemnity_cap | comply.ccpa_deletion (optional)
- Recurrence-Count: 1 (optional)
- First-Seen: 2026-01-15 (optional)
- Last-Seen: 2026-01-15 (optional)

---
```

**Categories for learnings:**

| Category | Use When |
|----------|----------|
| `clause_risk` | Unfavorable or missing clause identified in contract review |
| `compliance_gap` | Regulatory requirement not met or process gap discovered |
| `precedent_shift` | New case law changes interpretation of existing obligations |
| `contract_deviation` | Contract terms deviate from standard playbook without approval |
| `regulatory_change` | New regulation or amendment requires operational adjustment |
| `litigation_exposure` | Pattern or practice that increases litigation risk |

### Legal Issue Entry [LEG-YYYYMMDD-XXX]

Append to `.learnings/LEGAL_ISSUES.md`:

```markdown
## [LEG-YYYYMMDD-XXX] issue_type

**Logged**: ISO-8601 timestamp
**Priority**: critical | high | medium | low
**Status**: pending
**Area**: contracts | compliance | litigation | intellectual_property | privacy | regulatory | corporate_governance
**Severity**: critical | high | medium | low

### Summary
Brief description of the legal issue

### Issue Details
Context of the legal issue: what happened, what contract or regulation is involved,
what the exposure or risk is. Abstract to process-level lessons — do NOT include
privileged communications, specific case strategy, or confidential terms.

### Impact Assessment
- Affected contracts/matters
- Financial exposure estimate (range, not exact if confidential)
- Regulatory risk (enforcement action, fine range, reputational)
- Deadline or statute of limitations implications

### Recommended Action
- Immediate steps to mitigate
- Escalation path (in-house counsel, outside counsel, board)
- Long-term process improvement

### Timeline
- **Identified**: ISO-8601
- **Escalated**: ISO-8601 (if applicable)
- **Resolved**: ISO-8601 (if applicable)

### Metadata
- Trigger: contract_redline | regulatory_filing | case_law | audit_finding | infringement_notice | dsar
- Jurisdiction: US-Federal | US-CA | EU | UK | other
- Counterparty: [generalized role, e.g., "SaaS vendor", "enterprise customer"]
- Related Files: path/to/document
- See Also: LEG-20260110-001 (if related)

---
```

### Feature Request Entry [FEAT-YYYYMMDD-XXX]

Append to `.learnings/FEATURE_REQUESTS.md`:

```markdown
## [FEAT-YYYYMMDD-XXX] capability_name

**Logged**: ISO-8601 timestamp
**Priority**: medium
**Status**: pending
**Area**: contracts | compliance | litigation | intellectual_property | privacy | regulatory | corporate_governance

### Requested Capability
What legal operations tool, automation, or capability is needed

### Business Justification
Why it's needed — what risk it mitigates, what workflow it improves, what compliance
requirement it satisfies

### Complexity Estimate
simple | medium | complex

### Suggested Implementation
How this could be built: CLM integration, regulatory API, compliance dashboard, clause library

### Metadata
- Frequency: first_time | recurring
- Related Features: existing_tool_or_feature
- Compliance: GDPR | CCPA | SOX | HIPAA (if applicable)

---
```

## ID Generation

Format: `TYPE-YYYYMMDD-XXX`
- TYPE: `LRN` (learning), `LEG` (legal issue), `FEAT` (feature request)
- YYYYMMDD: Current date
- XXX: Sequential number or random 3 chars (e.g., `001`, `A7B`)

Examples: `LRN-20260412-001`, `LEG-20260412-A3F`, `FEAT-20260412-002`

## Resolving Entries

When an issue is resolved, update the entry:

1. Change `**Status**: pending` → `**Status**: resolved`
2. Add resolution block after Metadata:

```markdown
### Resolution
- **Resolved**: 2026-01-16T09:00:00Z
- **Action Taken**: Brief description of resolution (abstracted, no privileged details)
- **Clause/Policy Updated**: Reference to updated clause library or compliance checklist
- **Verified By**: legal review | compliance audit | outside counsel
```

Other status values:
- `in_progress` — Actively being negotiated, reviewed, or remediated
- `wont_fix` — Risk accepted with documented justification and approver
- `promoted` — Elevated to clause library, compliance checklist, or contract playbook
- `promoted_to_skill` — Extracted as a reusable skill

## Detection Triggers

Automatically log when you encounter:

**Contract Review Signals** (→ learning or legal issue):
- Contract redline rejected 3+ times on the same clause
- Unlimited liability or uncapped indemnity accepted
- Non-standard payment terms without VP approval
- Auto-renewal clause without termination notice window
- Assignment clause missing change-of-control protections
- Most-favored-nation clause absent from strategic vendor agreement

**Regulatory Signals** (→ learning or legal issue):
- New regulation published affecting the organization's industry
- Regulatory filing deadline within 30 days
- Amendment to existing regulation (GDPR, CCPA, SOX, HIPAA)
- Enforcement action against peer company in same sector
- Cross-border data transfer mechanism invalidated

**Litigation Signals** (→ legal issue):
- IP infringement notice or cease-and-desist received
- Data subject access request (DSAR) received
- Subpoena or litigation hold notice
- Non-compete or non-solicitation dispute
- Breach of contract claim or demand letter

**Compliance Signals** (→ learning):
- GDPR/CCPA audit finding
- SOX control deficiency
- Internal audit exception
- Third-party vendor compliance gap
- Data retention policy violation
- Missing consent mechanism for data processing

**Precedent Signals** (→ learning):
- Court ruling changes interpretation of standard clause
- Regulatory guidance document issued
- Industry association publishes new model terms
- Arbitration award sets new benchmark in relevant area

## Priority Guidelines

| Priority | When to Use | Legal Examples |
|----------|-------------|----------------|
| `critical` | Active litigation, regulatory enforcement, material breach | Injunction filed, regulatory investigation opened, data breach notification deadline |
| `high` | Compliance deadline approaching, material contract risk, IP claim | Filing due in 30 days, unlimited liability accepted, patent infringement notice |
| `medium` | Process improvement, clause optimization, template update | Clause library gap, negotiation playbook outdated, compliance checklist incomplete |
| `low` | Documentation, minor template revision, informational | Precedent noted for future reference, template formatting, policy language cleanup |

## Area Tags

Use to filter learnings by legal domain:

| Area | Scope |
|------|-------|
| `contracts` | Contract drafting, review, negotiation, CLM, clause libraries |
| `compliance` | Regulatory compliance, audits, certifications, internal controls |
| `litigation` | Disputes, claims, discovery, settlement, litigation holds |
| `intellectual_property` | Patents, trademarks, copyrights, trade secrets, licensing |
| `privacy` | Data protection, GDPR, CCPA, DSAR, consent management |
| `regulatory` | Regulatory filings, government relations, enforcement actions |
| `corporate_governance` | Board matters, corporate records, entity management, fiduciary duties |

## Promoting to Permanent Legal Standards

When a learning is broadly applicable (not a one-off matter), promote it to permanent legal operations standards.

### When to Promote

- Clause risk recurs across multiple contract negotiations
- Compliance gap applies to the entire regulatory program
- Precedent shift affects standard contract positions
- Contract negotiation pattern should be institutionalized
- Regulatory change requires ongoing monitoring

### Promotion Targets

| Target | What Belongs There |
|--------|-------------------|
| Clause library | Standard clauses, fallback positions, red/yellow/green markups |
| Compliance checklist | Regulatory requirements, audit preparation, filing deadlines |
| Regulatory tracker | New regulations, amendments, enforcement trends |
| Contract playbook | Negotiation positions, escalation triggers, approval thresholds |
| Risk register | Recurring risk categories, exposure estimates, mitigation plans |
| `CLAUDE.md` | Legal operations conventions for AI agents |
| `AGENTS.md` | Legal workflows, matter routing, delegation patterns |

### How to Promote

1. **Distill** the learning into a concise clause, checklist item, or playbook entry
2. **Add** to appropriate target (clause library, compliance checklist, playbook)
3. **Update** original entry:
   - Change `**Status**: pending` → `**Status**: promoted`
   - Add `**Promoted**: clause_library` (or `compliance_checklist`, `contract_playbook`, `risk_register`)

### Promotion Examples

**Learning → Clause library entry:**
> Unlimited liability in SaaS renewal (3 instances in quarter) → Standard clause: "Cap at 12 months fees, fallback 2x annual value, VP Legal approval for exceptions."

**Learning → Compliance checklist item:**
> CCPA deletion not covering backups → Checklist: "Primary DB 30 days, backups 90 days, confirmation within 45-day window, quarterly audit."

## Recurring Pattern Detection

If logging something similar to an existing entry:

1. **Search first**: `grep -r "keyword" .learnings/`
2. **Link entries**: Add `**See Also**: LEG-20260110-001` in Metadata
3. **Bump priority** if issue keeps recurring
4. **Consider systemic fix**: Recurring legal issues often indicate:
   - Missing clause library entry (→ add standard clause with fallback)
   - Missing compliance control (→ add to compliance checklist)
   - Outdated contract playbook (→ update negotiation positions)
   - Training gap (→ schedule legal operations training)

## Periodic Review

Review `.learnings/` at natural breakpoints:

### When to Review
- Before major contract negotiations
- Before compliance audit deadlines
- After regulatory changes affecting the organization
- After litigation matters are resolved
- Quarterly during active legal operations
- Before board meetings or governance reviews

### Quick Status Check
```bash
grep -h "Status\*\*: pending" .learnings/*.md | wc -l
grep -B5 "Priority\*\*: critical\|Priority\*\*: high" .learnings/*.md | grep "^## \["
grep -l "Area\*\*: contracts" .learnings/*.md
grep -h "Regulation:" .learnings/*.md | sort -u
```

### Review Actions
- Resolve closed legal matters and promote recurring clause risks
- Update compliance checklists for new regulations
- Link related entries and archive resolved litigation matters

## Hook Integration

Enable automatic reminders through agent hooks. This is **opt-in**.

### Quick Setup (Claude Code / Codex)

Create `.claude/settings.json` in your project:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "./skills/self-improving-legal/scripts/activator.sh"
      }]
    }]
  }
}
```

This injects a legal-focused learning evaluation reminder after each prompt (~80-120 tokens overhead).

### Advanced Setup (With Legal Issue Detection)

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "./skills/self-improving-legal/scripts/activator.sh"
      }]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "./skills/self-improving-legal/scripts/error-detector.sh"
      }]
    }]
  }
}
```

Enable `PostToolUse` only if you want the hook to inspect command output for legal-relevant patterns such as breach, violation, non-compliance, litigation, and regulatory keywords.

### Available Hook Scripts

| Script | Hook Type | Purpose |
|--------|-----------|---------|
| `scripts/activator.sh` | UserPromptSubmit | Reminds to evaluate legal findings after tasks |
| `scripts/error-detector.sh` | PostToolUse (Bash) | Triggers on legal-relevant patterns in output |

See `references/hooks-setup.md` for detailed configuration and troubleshooting.

## Automatic Skill Extraction

When a legal learning is valuable enough to become a reusable skill, extract it.

### Skill Extraction Criteria

| Criterion | Description |
|-----------|-------------|
| **Recurring** | Same clause risk or compliance gap in 2+ contract types or regulatory areas |
| **Verified** | Status is `resolved` with confirmed process improvement |
| **Non-obvious** | Required legal analysis or cross-jurisdictional research |
| **Broadly applicable** | Not matter-specific; useful across contract types or regulatory programs |
| **User-flagged** | User says "save this as a legal skill" or similar |

### Extraction Workflow

1. **Identify candidate**: Learning meets extraction criteria
2. **Run helper** (or create manually):
   ```bash
   ./skills/self-improving-legal/scripts/extract-skill.sh skill-name --dry-run
   ./skills/self-improving-legal/scripts/extract-skill.sh skill-name
   ```
3. **Customize SKILL.md**: Fill in template with legal-specific content
4. **Update learning**: Set status to `promoted_to_skill`, add `Skill-Path`
5. **Verify**: Ensure NO privileged communications, case strategy, or confidential terms leaked into the skill

### Extraction Detection Triggers

**In conversation:**
- "This clause keeps causing problems"
- "Save this compliance process as a skill"
- "We see this regulatory issue every quarter"
- "Add this to our contract playbook"

**In entries:**
- Multiple `See Also` links (recurring clause risk pattern)
- High priority + resolved status
- Category: `compliance_gap` with reusable remediation process
- Regulatory change with broad organizational impact

## Multi-Agent Support

| Agent | Activation | Detection |
|-------|-----------|-----------|
| Claude Code | Hooks (UserPromptSubmit, PostToolUse) | Automatic via hook scripts |
| Codex CLI | Hooks (same pattern) | Automatic via hook scripts |
| GitHub Copilot | Manual (`.github/copilot-instructions.md`) | Manual review |
| OpenClaw | Workspace injection + inter-agent messaging | Via session tools |

Regardless of agent, apply legal self-improvement when you:

1. **Review a contract** — identify clause risks, deviations, missing protections
2. **Encounter a compliance gap** — regulatory requirement not met, audit finding
3. **Track a regulatory change** — new law, amendment, or enforcement action
4. **Handle litigation matters** — claims, disputes, discovery, holds
5. **Process IP issues** — infringement notices, licensing gaps, trade secret exposure
6. **Manage privacy requests** — DSARs, consent gaps, cross-border transfer issues

## Legal-Specific Best Practices

1. **Protect privilege** — never log attorney-client communications or work product
2. **Abstract to process** — capture the lesson, not the confidential details
3. **Track deadlines** — regulatory filings, statutes of limitations, response windows
4. **Version clause libraries** — track which clause version was used in which agreement
5. **Audit compliance quarterly** — systematic review of regulatory obligations
6. **Maintain jurisdiction tags** — legal obligations vary by jurisdiction
7. **Link related matters** — contract issues may relate to compliance or litigation
8. **Escalate promptly** — critical items require immediate counsel notification
9. **Document approval chains** — record who approved exceptions to standard terms
10. **Review before negotiations** — check `.learnings/` for past issues with similar clauses or counterparties

## Gitignore Options

**Keep learnings local** (recommended for legal):
```gitignore
.learnings/
```

Legal findings may contain sensitive context even when abstracted. Default to local-only.
Track in repo only if all entries are confirmed free of privileged information and confidential terms.

**Hybrid** (track templates, ignore entries): add `.learnings/*.md` and `!.learnings/.gitkeep` to `.gitignore`.

## Stackability Contract (Standalone + Multi-Skill)

This skill is standalone-compatible and stackable with other self-improving skills.

### Namespaced Logging (recommended for 2+ skills)
- Namespace for this skill: `.learnings/legal/`
- Keep current standalone behavior if you prefer flat files.
- Optional shared index for all skills: `.learnings/INDEX.md`

### Required Metadata
Every new entry must include:

```markdown
**Skill**: legal
```

### Hook Arbitration (when 2+ skills are enabled)
- Use one dispatcher hook as the single entrypoint.
- Dispatcher responsibilities: route by matcher, dedupe repeated events, and rate-limit reminders.
- Suggested defaults: dedupe key = `event + matcher + file + 5m_window`; max 1 reminder per skill every 5 minutes.

### Narrow Matcher Scope (legal)
Only trigger this skill automatically for legal signals such as:
- `contract clause|liability|indemnity|compliance obligation`
- `jurisdiction|regulatory update|legal risk|counsel escalation`
- explicit legal intent in user prompt

### Cross-Skill Precedence
When guidance conflicts, apply:
1. `security`
2. `engineering`
3. `coding`
4. `ai`
5. user-explicit domain skill
6. `meta` as tie-breaker

### Ownership Rules
- This skill writes only to `.learnings/legal/` in stackable mode.
- It may read other skill folders for cross-linking, but should not rewrite their entries.
