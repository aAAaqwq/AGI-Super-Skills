# ADR-0001: Canonical inventory and generated outputs

- Status: Accepted
- Date: 2026-07-21

## Context

Inventory counts previously came from README copy, directory scans, symlinks, and generated files. Those sources disagreed and could include non-portable entries.

## Decision

The canonical skill inventory is the set of tracked, physical, top-level `skills/<id>/SKILL.md` entrypoints. Team and kit membership comes from `config/team-manifest.json`. Taxonomy is an authored discovery rule set. `catalog/` and `docs/data/` are generated outputs and must declare a generator and verification command.

## Consequences

- Generated output can be deleted and rebuilt without changing source truth.
- README counts cannot override repository authorities.
- Symlinks and ignored directories are excluded from the canonical inventory.
- CI fails when generated catalog output drifts from its authored inputs.
