# Secure data architecture checklist

## Data inventory fields

For each datum record:

- canonical name and schema type;
- data subject and sensitivity class;
- purpose and lawful/contractual basis to verify;
- source and confidence/provenance;
- system of record and replicas;
- readers, writers, exports, and model/cloud recipients;
- encryption and key owner;
- retention, deletion, backup, and restore behavior;
- audit event and incident impact.

## Local-first pattern

Use a local source of truth when offline continuity, privacy, or device-owned artifacts matter. Treat cloud as an explicit projection:

```text
local transaction
  -> domain change + outbox event commit
  -> worker lease
  -> tenant-scoped remote upsert
  -> acknowledgement
  -> retry/dead-letter on failure
```

Never mark local data synchronized before the remote acknowledgement. Preserve retry ownership, attempt count, lease expiry, and dead-letter reason.

## Provenance pattern

For identity-sensitive artifacts store:

- stable owner ID and normalized display name;
- source event/message ID;
- source/preview URL fingerprint where appropriate;
- content SHA-256 and format validation;
- observed and verified timestamps;
- validation version and reason;
- current trust state.

Consumers must verify the artifact still matches the record before display, scoring, export, or cloud projection.

## Multi-tenant controls

- Put `tenant_id` in every tenant-owned primary/unique key.
- Enforce tenant filtering in the database with RLS or equivalent, not only in application queries.
- Test two real identities against read, insert, update, delete, storage, RPC, and realtime paths.
- Separate anonymous/public configuration from privileged service credentials.
- Scope user tokens minimally and support expiry, refresh, revocation, and device loss.
- Log administrative access without leaking record contents.

## Conflict policies

Define per data class:

- append-only messages by stable message ID;
- immutable files by content hash;
- derived scores by input hash and scoring version;
- state-machine aggregates by optimistic version;
- profile fields by source strength and observation time;
- unresolved conflicts in a dedicated queue/table.

## Migration gates

1. Back up and integrity-check the current store.
2. Make schema changes forward-compatible where possible.
3. Backfill provenance without claiming historical certainty.
4. Dual-read or shadow-compare before switching authority.
5. Keep a rollback path that does not discard newly written data.
6. Verify old clients and partial upgrades.
7. Re-run privacy, tenant, restore, and sync tests.

## Security acceptance

- Loopback services reject non-local exposure and unauthorized calls.
- Paths remain within approved roots and reject links/traversal.
- Downloads restrict scheme/host and validate body/size/type.
- Queries are parameterized and exports are escaped/redacted.
- Secrets never appear in source, frontend payloads, logs, screenshots, or generated documents.
- Backups restore transactionally and failures roll back.
- Cross-tenant and privileged-key misuse tests fail closed.
- Sync retries are idempotent and observable.
- AI requests contain only necessary, policy-approved content.
