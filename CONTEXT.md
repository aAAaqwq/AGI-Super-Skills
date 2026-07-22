# Repository context and shared language

This repository packages versioned instructions, team compositions, safe installation, discovery indexes, and evidence. It is not an autonomous agent runtime and does not prove business outcomes by containing a large inventory.

## Architecture language

These terms are normative across documentation, configuration, reviews, and tests:

- **Module** — a cohesive capability with one stable purpose and an explicit boundary.
- **Interface** — the smallest public contract a consumer needs to use a Module.
- **Implementation** — replaceable files and logic hidden behind a Module Interface.
- **Depth** — useful complexity hidden behind a simpler Interface.
- **Seam** — a named boundary where two Modules exchange data, files, or control.
- **Adapter** — boundary-specific translation between a Module and an external harness.
- **Leverage** — how many important consumers improve through one boundary change.
- **Locality** — how closely a concept, its implementation, and its evidence live together.

The machine-readable definitions and path owners live in [`config/repository-architecture.json`](./config/repository-architecture.json).

## Product language

| Term | Meaning | Not evidence of |
|---|---|---|
| Canonical skill | A tracked, physical `skills/<id>/SKILL.md` entrypoint | Behavior, safety, license, or harness compatibility |
| Agent role pack | Versioned role instructions referencing required and optional skills | An autonomous employee or runtime |
| Starter kit | A manifest-selected group of Agent role packs | A completed business outcome |
| Generic workspace | Preview-first output assembled by `install.sh` | Harness-specific compatibility |
| Distribution Adapter | A harness manifest or curated package | Verification unless a matching receipt exists |
| Generated catalog | Rebuildable discovery output under `catalog/` | Source authority |
| Structural evidence | Deterministic checks for files, references, schemas, and safe copying | Semantic correctness or real-world outcomes |
| Verification receipt | Versioned evidence for a named commit, harness, fixture, checks, and limits | Future commits or other harnesses |

## Authority rules

1. `config/team-manifest.json` owns team and starter-kit membership.
2. Tracked physical `skills/*/SKILL.md` files own the canonical skill inventory.
3. `config/skill-taxonomy.json` owns deterministic discovery categories, not semantic truth.
4. Generated outputs never become authored authority.
5. Distribution presence is not runtime verification.
6. README numbers and badges are views, never authorities.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the repository map and [`docs/adr/`](./docs/adr/) for decisions.
