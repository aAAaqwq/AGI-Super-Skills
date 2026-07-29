# Configuration authorities

| Contract | Owns | Consumer / check |
|---|---|---|
| [`team-manifest.json`](./team-manifest.json) | 14 Agents, starter kits, portable, harness-specific, and external Skill assignments | installer, catalog, validator |
| [`agent-hierarchy.json`](./agent-hierarchy.json) | CEO→CTO/CPO/CCO→direct-child edges, canonical PE reference, depth and wave limits | Codex generator, multi-CLI installer, hierarchy tests |
| [`cto-specialists.json`](./cto-specialists.json), [`cpo-specialists.json`](./cpo-specialists.json), [`cco-specialists.json`](./cco-specialists.json) | positive/negative triggers, inputs, outputs, acceptance and boundaries for 44 leaves | manager prompts and adapter renderers |
| [`agent-sources.lock.json`](./agent-sources.lock.json) | pinned agency-agents-zh source URL, vendored path and byte-level SHA-256 | provenance builder and drift tests |
| [`skill-taxonomy.json`](./skill-taxonomy.json) | deterministic primary discovery categories and risk flags | `npm run check:skills` |
| [`skill-provenance.json`](./skill-provenance.json) | reviewed Original, Adapted, Collected, or Unknown origin evidence for named Skills | catalog and Agent index builders |
| [`skill-curation.json`](./skill-curation.json) | digest-matched editorial selection, limitations, and Curation evidence scores | catalog and Agent index builders |
| [`skill-quality-baseline.json`](./skill-quality-baseline.json) | non-regression baseline for structural skill signals | `npm run check:skill-quality` |
| [`repository-architecture.json`](./repository-architecture.json) | Modules, path roles, authority, lineage, Adapters, quality ceilings | `npm run check:architecture` |
| [`external-skill-sources.json`](./external-skill-sources.json) | tombstones for removed non-portable links | repository validation |

Core executable contracts have neighboring JSON Schemas. Ledgers such as `external-skill-sources.json` are validated by repository invariants. Generated files and README copy never override these authorities.

Return to the [architecture map](../ARCHITECTURE.md) or [repository context](../CONTEXT.md).
