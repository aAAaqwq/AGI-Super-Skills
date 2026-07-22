# ADR-0002: Generic workspace and curated distributions

- Status: Accepted
- Date: 2026-07-21

## Context

The repository serves a preview-first generic installer and several harness-facing package manifests. Treating every manifest as the same product surface obscures ownership and overstates compatibility.

## Decision

`install.sh` is the generic workspace Interface. Harness manifests and `plugins/` are Distribution Adapters. The root full-library manifests remain legacy or manifest-only surfaces; a curated package may be recommended independently. Adapter presence never proves runtime compatibility.

## Consequences

- Removing one Adapter must not break generic installation.
- Adapter support labels remain `manifest`, `pending`, or `legacy` until a matching runtime receipt exists.
- Canonical source content is not duplicated merely to satisfy a harness layout.
- Future Adapter consolidation requires a separate decision and migration evidence.
