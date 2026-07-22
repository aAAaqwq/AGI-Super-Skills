# 🧰 Skills library

Find reusable instructions by the outcome you need. Each catalog entry is a tracked, physical directory with a `SKILL.md`; symlinks are forbidden.

Start with a small team pack when possible. A large inventory improves coverage, but it is not evidence that every item has equal quality, portability, or support.

## 🚀 Start here

| Goal | Maintained entry point | Evidence boundary |
|---|---|---|
| Plan, build, and communicate | [Solo Founder](../starter-kits/solo-founder/) | Three active Agent workspaces; generic installer tested |
| Research, draft, and measure | [Content Creator](../starter-kits/content-creator/) | Drafting workflow; publishing remains human-controlled |
| Backtest with risk review | [Quant Trader](../starter-kits/quant-trader/) | Research only; no live-trading claim |
| Use native Codex workflows | [Codex package](../.codex/INDEX.md) | Separate curated distribution and sync policy |

## 🧭 Browse skills by outcome

The [generated skill catalog](../catalog/) classifies every canonical entry once. Its [machine-readable index](../catalog/skill-index.json) supports search and future filtering without turning README into a database.

| Category | Category | Category |
|---|---|---|
| [🤖 AI Agents & Orchestration](../catalog/#ai-agents-orchestration) | [💻 Software Engineering](../catalog/#software-engineering) | [☁️ Cloud, DevOps & Reliability](../catalog/#cloud-devops-reliability) |
| [📊 Data, Analytics & Research](../catalog/#data-analytics-research) | [🛡️ Security, Privacy & Legal](../catalog/#security-privacy-legal) | [🎨 Product, Design & UX](../catalog/#product-design-ux) |
| [📈 Marketing, SEO & Growth](../catalog/#marketing-seo-growth) | [✍️ Content, Media & Publishing](../catalog/#content-media-publishing) | [🤝 Sales, CRM & Customer Success](../catalog/#sales-crm-customer-success) |
| [💹 Finance, Trading & Markets](../catalog/#finance-trading-markets) | [🧭 Business Operations & Strategy](../catalog/#business-operations-strategy) | [⚙️ Apps & Workflow Automation](../catalog/#apps-workflow-automation) |
| [🇨🇳 Chinese Platform Workflows](../catalog/#chinese-platform-workflows) | [🧰 Specialized Domains & Utilities](../catalog/#general-utilities) | |

Search locally when you already know a name or phrase:

```bash
rg -n '^description:' skills -g SKILL.md
npm run check:skills
```

## 🏷️ Support and portability

- **Curated:** reviewed and versioned in a named distribution with its own sync policy.
- **Pack-required:** referenced by an active Agent and covered by repository structure checks.
- **Catalog:** tracked with a physical `SKILL.md`; behavior, dependencies, license, and harness support may still require review.
- **External:** recommended by the manifest but not bundled here.

Portability is a separate axis:

- **Portable required / optional:** copied by the generic installer and scanned for known host paths and runtime-only commands.
- **Harness-specific:** assigned to an Agent but skipped by the generic installer because it assumes a named runtime or tool.
- **Catalog-only:** discoverable source with no active Agent assignment.

Neither axis is a quality ranking or runtime guarantee. Inspect each skill's permissions, dependencies, provenance, and license before use.

## 🔬 Structural quality evidence

[`catalog/skill-quality.json`](../catalog/skill-quality.json) publishes deterministic structural findings for every canonical entrypoint. It separates hard structure failures, progressive-disclosure warnings, and script evidence requiring review.

```bash
npm run build:skill-quality
npm run check:skill-quality
```

The checked [debt baseline](../config/skill-quality-baseline.json) allows findings to improve but fails CI when known issue counts regress. This evidence does not score semantic usefulness, safety, or harness behavior.

## 📦 Inventory contract

The canonical rules and active requirements live in [`config/team-manifest.json`](../config/team-manifest.json). Taxonomy rules live in [`config/skill-taxonomy.json`](../config/skill-taxonomy.json); generated counts are not maintained by hand.

The validator counts only skills that are tracked by Git, physical rather than symlinked, present in the working tree, and backed by a top-level `SKILL.md`.

```bash
npm run build:skills
npm test
npm run validate -- --warnings-as-errors
```

The older [Agent matrix](../docs/skills-matrix.md) is retained as a legacy research view. It is not the inventory or active Agent-assignment authority.

## 🧹 Removed links and provenance

Machine-local links removed during the portability refactor are recorded in [`config/external-skill-sources.json`](../config/external-skill-sources.json).

A removed entry should return only after its source, license, pinned revision, physical contents, and validation are clear.

## 🤝 Contributing

New or restored skills need understandable instructions, provenance, license compatibility, declared dependencies, and no secrets or host-specific paths.

Placeholders, duplicated bulk content, unsupported compatibility claims, and skills without a maintainable purpose should not enter the promoted catalog. See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full review contract.
