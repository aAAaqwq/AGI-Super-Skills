---
name: company-wiki
description: Company knowledge base — domains, services, infrastructure, accounts, credentials locations, architecture decisions
---
# Company Wiki

> Structured knowledge base about WeLabelData company: domains, hosting, services, accounts, infrastructure, architecture decisions. Single source of truth.

## When to use

- "запиши в базу знань" / "save to company wiki"
- "які домени в нас є?" / "what domains do we have?"
- "де хоститься сайт?" / "where is the site hosted?"
- "які сервіси ми використовуємо?" / "what services do we use?"
- Looking up infrastructure details (DNS, hosting, payments, etc.)
- Recording new company assets (domains, accounts, services)

## Paths

| What | Path |
|------|------|
| Wiki root | `~/company-wiki/` |
| Domains & DNS | `~/company-wiki/domains.md` |
| Services & accounts | `~/company-wiki/services.md` |
| Infrastructure | `~/company-wiki/infrastructure.md` |
| Products | `~/company-wiki/products.md` |
| Architecture decisions | `~/company-wiki/decisions.md` |

## How to execute

### Read information

```bash
# Find specific info
grep -ri "KEYWORD" ~/company-wiki/

# Read a specific section
cat ~/company-wiki/domains.md
```

### Write information

1. Identify the correct file based on the type of information
2. Read current file content
3. Add or update the relevant section
4. Keep format consistent: use markdown tables and headers

### File structure conventions

Each file follows this pattern:

```markdown
# [Topic]

## [Category]

| Field | Value |
|-------|-------|
| Name  | ...   |
| ...   | ...   |

### Notes
- Additional context
```

## Examples

### Example 1: Record a new domain

```bash
# Read current domains
cat ~/company-wiki/domains.md
# Edit to add new domain entry
```

### Example 2: Look up hosting details

```bash
grep -i "hosting\|cloudflare\|gcs" ~/company-wiki/infrastructure.md
```

### Example 3: Record architecture decision

Add to `~/company-wiki/decisions.md`:
```markdown
## YYYY-MM-DD: [Decision Title]
- **Context:** Why this came up
- **Decision:** What was decided
- **Alternatives considered:** What else was considered
- **Status:** Active / Superseded by [X]
```

## Maintenance

- Update wiki when infrastructure changes
- Review quarterly for outdated info
- Keep files concise — facts, not prose

## Related skills

- `memory` — session-level observations and summaries
- `query-leads` — CRM data (clients, leads)
- `deploy-website` — deployment procedures
