# Configuration authorities

| Contract | Owns | Consumer / check |
|---|---|---|
| [`team-manifest.json`](./team-manifest.json) | 14 Agents, starter kits, portable, harness-specific, and external Skill assignments | installer, catalog, validator |
| [`skill-taxonomy.json`](./skill-taxonomy.json) | deterministic primary discovery categories and risk flags | `npm run check:skills` |
| [`skill-quality-baseline.json`](./skill-quality-baseline.json) | non-regression baseline for structural skill signals | `npm run check:skill-quality` |
| [`repository-architecture.json`](./repository-architecture.json) | Modules, path roles, authority, lineage, Adapters, quality ceilings | `npm run check:architecture` |
| [`external-skill-sources.json`](./external-skill-sources.json) | tombstones for removed non-portable links | repository validation |

Core executable contracts have neighboring JSON Schemas. Ledgers such as `external-skill-sources.json` are validated by repository invariants. Generated files and README copy never override these authorities.

Return to the [architecture map](../ARCHITECTURE.md) or [repository context](../CONTEXT.md).
