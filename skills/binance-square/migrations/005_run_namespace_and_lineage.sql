PRAGMA foreign_keys = ON;

-- A database path is a storage location, not a run identity.  Scope production
-- jobs explicitly so independent production/canary ledgers cannot emit the
-- same logical_run_id and attempt_id for different facts.  This side table is
-- additive and keeps migration replay safe for existing SQLite files.
CREATE TABLE IF NOT EXISTS run_identity_namespace (
    logical_run_id TEXT PRIMARY KEY,
    job_namespace TEXT NOT NULL CHECK (length(trim(job_namespace)) > 0),
    production_job_id TEXT,
    scheduled_for_utc TEXT,
    FOREIGN KEY (logical_run_id) REFERENCES logical_run(logical_run_id),
    UNIQUE (job_namespace, production_job_id, scheduled_for_utc)
);

INSERT OR IGNORE INTO run_identity_namespace (
    logical_run_id, job_namespace, production_job_id, scheduled_for_utc
)
SELECT logical_run_id, 'default', production_job_id, scheduled_for_utc
FROM logical_run;

DROP INDEX IF EXISTS logical_run_production_slot_uq;
