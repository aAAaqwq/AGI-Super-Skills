---
name: design-secure-data-architecture
description: Design and review secure application data architecture across local databases, files, cloud projections, multi-tenant services, AI processing, backups, and synchronization. Use when defining data ownership, PII classification, local source-of-truth models, RLS isolation, credential boundaries, provenance chains, transactions, outbox delivery, idempotency, conflict resolution, retention, migration, or security acceptance tests.
---

# Design Secure Data Architecture

Start from data authority and threat boundaries, then choose storage and synchronization. Security statements must match deployed behavior, not planning documents.

## Workflow

1. **Inventory and classify data.** List fields, files, derived artifacts, logs, credentials, model inputs, backups, and identifiers. Classify sensitivity, data subject, purpose, source, retention, and allowed consumers.
2. **Draw trust boundaries.** Identify local user device, desktop service, browser session, model provider, cloud database, administrators, tenants, support tooling, CI, and backup locations.
3. **Choose authority.** Declare the system of record for every aggregate and which stores are caches, projections, replicas, or immutable artifacts. Define who may create, update, merge, delete, and restore.
4. **Model provenance.** Carry source, observed time, stable owner identity, content hash, validation status, and version for sensitive or derived data. Strong evidence may replace weak evidence; weak evidence must not overwrite strong evidence.
5. **Define transactions.** Put business writes and durable events in one unit of work. Use an outbox for remote projection. Make retries idempotent and conflicts explicit.
6. **Design tenant and credential isolation.** Use server-enforced tenant keys/RLS, least-privilege user tokens, separate administrative credentials, secure local storage, rotation, cache invalidation, and no secrets in frontend or logs.
7. **Minimize external disclosure.** Send only required fields to AI or cloud services. Redact exports, notifications, diagnostics, and support bundles. Treat disclaimers as communication, not a substitute for lawful basis or controls.
8. **Specify lifecycle.** Define backup, restore, retention, deletion, export, device loss, account revocation, schema migration, and sync conflict behavior.
9. **Validate adversarially.** Test cross-tenant access, stale writes, replay, duplicate events, partial failure, corrupted files, path traversal, SSRF, secret leakage, malicious markup, race conditions, and rollback.
10. **Document reality.** Reconcile code, schema, config defaults, region, encryption, and cloud fields before publishing a security statement.

## Architectural invariants

- Domain/application code must not depend directly on database or platform adapters.
- Local or cloud authority must be explicit; “both are truth” is not a merge policy.
- Sensitive file consumers must revalidate owner and hash, not trust a stored path.
- Failed remote sync must not destroy the local committed state.
- A retry must not duplicate messages, scores, interviews, files, or external actions.
- Conflicting updates must enter a visible conflict state instead of silently overwriting.
- Administrative credentials must never be distributed to normal clients.
- Backups require the same access, privacy, integrity, and deletion policy as primary data.

## References

- Read [architecture-checklist.md](references/architecture-checklist.md) for models, controls, migrations, and test gates.
- Read [project-evidence.md](references/project-evidence.md) for lessons from the repository's local-first, multi-tenant, provenance, and port architecture.
