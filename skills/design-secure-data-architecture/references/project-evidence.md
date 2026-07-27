# Project evidence: data and security architecture

## Evidence baseline

- Main baseline reviewed: `origin/main` at `401ad9c`.

## Primary sources

- `docs/architecture/ADR-001-模块化单体与跨平台端口架构.md`: domain/application/port/adapter boundaries, unit of work, outbox, conflicts, and migration stages.
- `docs/architecture/验证报告-2026-07-23-跨平台端口与数据架构.md`: what is implemented versus still legacy, and evidence-quality labels.
- `docs/数据安全说明.md`: local data, cloud behavior, credentials, privacy, backups, and user-facing disclosures.
- `docs/cloud-sync-plan.md`: tenant model, RLS, sync direction, and risk assumptions.
- `app/domain`, `app/application`, `app/ports`, and `app/adapters`: enforced architecture boundaries.
- `tests/test_architecture_boundaries.py`, `tests/test_data_ports.py`, `tests/test_cloud_sync_resume_guard.py`, `tests/test_backup_restore.py`, and scoring/provenance race tests.

## Reusable lessons

1. Mark architecture state honestly. Passing boundary tests for new modules does not mean legacy scripts have completed migration.
2. Store business changes and outbox events in one explicit transaction; uncommitted work must leave neither.
3. Use leases, ownership checks, retries, acknowledgements, and dead letters for durable projection.
4. Resolve data conflicts by type: append messages, hash files, version scores and interviews, and compare source strength for profiles.
5. Sensitive artifacts need consumer-side revalidation. A path in the database is not proof of identity or file integrity.
6. Security documents can conflict on cloud region, default enablement, or PII scope as plans evolve. Reconcile deployed config/schema/code before making current claims.
7. A user disclaimer does not remove responsibility for candidate/data-subject information. Technical minimization and access control remain mandatory.
8. Separate user-scoped tokens from service-role/admin credentials and test tenant isolation with multiple identities.
