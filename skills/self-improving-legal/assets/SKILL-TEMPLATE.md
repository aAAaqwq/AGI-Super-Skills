# Legal Skill Template

Template for creating legal skills extracted from learnings and legal issues. Copy and customize.

---

## SKILL.md Template

```markdown
---
name: skill-name-here
description: "Concise description of the legal skill and when to use it. Include trigger conditions."
---

# Skill Name

Brief introduction explaining the legal problem this skill addresses and its origin.

## Quick Reference

| Situation | Action |
|-----------|--------|
| [Legal trigger 1] | [Recommended response 1] |
| [Legal trigger 2] | [Recommended response 2] |

## Background

Why this legal knowledge matters. What risks, compliance gaps, or contract issues it prevents. Context from the original finding.

## Recommended Action

### Step-by-Step

1. First remediation or process step
2. Second step
3. Verification step (legal review, compliance audit, or counsel sign-off)

### Clause/Policy Example

\`\`\`markdown
Example showing the recommended clause language, policy text, or compliance checklist item
\`\`\`

## Common Variations

- **Variation A**: Different jurisdiction or regulatory framework specifics
- **Variation B**: Alternative clause language or compliance approach

## Gotchas

- Warning or common mistake during implementation #1
- Warning or common mistake during implementation #2
- **NEVER** log privileged attorney-client communications or confidential settlement terms

## Related Standards

- Regulation: GDPR | CCPA | SOX | HIPAA | EU AI Act
- Jurisdiction: US-Federal | US-CA | EU | UK
- Compliance: Reference to specific control or requirement

## Source

Extracted from legal learning or issue entry.
- **Entry ID**: LRN-YYYYMMDD-XXX or LEG-YYYYMMDD-XXX
- **Original Category**: clause_risk | compliance_gap | precedent_shift | contract_deviation | regulatory_change | litigation_exposure
- **Extraction Date**: YYYY-MM-DD
```

---

## Minimal Template

For simple legal skills:

```markdown
---
name: skill-name-here
description: "What this legal skill does and when to use it."
---

# Skill Name

[Legal problem statement in one sentence]

## Recommended Action

[Direct process improvement, clause revision, or compliance step]

## Source

- Entry ID: LRN-YYYYMMDD-XXX or LEG-YYYYMMDD-XXX
```

---

## Template with Scripts

For legal skills that include automation helpers:

```markdown
---
name: skill-name-here
description: "What this legal skill does and when to use it."
---

# Skill Name

[Introduction]

## Quick Reference

| Command | Purpose |
|---------|---------|
| \`./scripts/check-compliance.sh\` | [What it checks] |
| \`./scripts/extract-clauses.sh\` | [What it extracts] |
| \`./scripts/audit-deadlines.sh\` | [What it audits] |

## Usage

### Automated (Recommended)

\`\`\`bash
./skills/skill-name/scripts/check-compliance.sh [target]
\`\`\`

### Manual Steps

1. Step one
2. Step two

## Scripts

| Script | Description |
|--------|-------------|
| \`scripts/check-compliance.sh\` | Regulatory compliance checker |
| \`scripts/extract-clauses.sh\` | Clause extraction from contract templates |
| \`scripts/audit-deadlines.sh\` | Filing and compliance deadline auditor |

## Source

- Entry ID: LEG-YYYYMMDD-XXX
```

---

## Naming Conventions

- **Skill name**: lowercase, hyphens for spaces
  - Good: `liability-cap-playbook`, `ccpa-deletion-checklist`, `force-majeure-review`
  - Bad: `Liability_Cap_Playbook`, `CCPADeletion`

- **Description**: Start with action verb, mention legal trigger
  - Good: "Reviews liability cap clauses in vendor agreements. Use when negotiating SaaS contracts or renewals."
  - Bad: "Liability stuff"

- **Files**:
  - `SKILL.md` - Required, main documentation
  - `scripts/` - Optional, compliance checkers and automation
  - `references/` - Optional, regulatory mappings
  - `assets/` - Optional, templates

---

## Extraction Checklist

Before creating a skill from a legal finding:

- [ ] Finding is verified (status: resolved, process improvement confirmed)
- [ ] Solution is broadly applicable (not matter-specific one-off)
- [ ] **No privileged communications, case strategy, or confidential terms in any content**
- [ ] Content is complete (has all needed context for process improvement)
- [ ] Name follows conventions
- [ ] Description is concise but includes legal triggers
- [ ] Quick Reference table maps situations to actions
- [ ] Clause/policy examples are reviewed by counsel
- [ ] Regulatory references included where applicable
- [ ] Source entry ID is recorded

After creating:

- [ ] Update original entry with `promoted_to_skill` status
- [ ] Add `Skill-Path: skills/skill-name` to entry metadata
- [ ] Test skill by reading it in a fresh session
- [ ] Verify no privileged or confidential data leaked into the skill
