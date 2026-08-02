PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS logical_run (
    logical_run_id TEXT PRIMARY KEY,
    run_namespace TEXT NOT NULL CHECK (run_namespace IN ('PRODUCTION', 'REPLAY')),
    production_job_id TEXT,
    scheduled_for_utc TEXT,
    pipeline_version TEXT NOT NULL,
    replay_namespace TEXT,
    source_logical_run_id TEXT,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CHECK (
        (run_namespace = 'PRODUCTION'
            AND production_job_id IS NOT NULL
            AND scheduled_for_utc IS NOT NULL
            AND replay_namespace IS NULL
            AND source_logical_run_id IS NULL)
        OR
        (run_namespace = 'REPLAY'
            AND production_job_id IS NULL
            AND scheduled_for_utc IS NULL
            AND replay_namespace IS NOT NULL
            AND source_logical_run_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS logical_run_production_slot_uq
    ON logical_run (production_job_id, scheduled_for_utc)
    WHERE run_namespace = 'PRODUCTION';

CREATE UNIQUE INDEX IF NOT EXISTS logical_run_replay_identity_uq
    ON logical_run (replay_namespace, source_logical_run_id, pipeline_version)
    WHERE run_namespace = 'REPLAY';

CREATE TABLE IF NOT EXISTS run_attempt (
    attempt_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL CHECK (attempt_no IN (1, 2)),
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    started_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    failed_stage TEXT,
    recovered_silently INTEGER NOT NULL DEFAULT 0
        CHECK (recovered_silently IN (0, 1)),
    alert_sent_at_utc TEXT,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id) REFERENCES logical_run(logical_run_id),
    UNIQUE (logical_run_id, attempt_no),
    UNIQUE (logical_run_id, attempt_id)
);

CREATE TABLE IF NOT EXISTS bronze_manifest (
    manifest_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    sha256_hex TEXT NOT NULL
        CHECK (length(sha256_hex) = 64 AND sha256_hex NOT GLOB '*[^0-9a-f]*'),
    payload_schema_version TEXT NOT NULL,
    event_start_utc TEXT,
    event_end_utc TEXT,
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CHECK (
        (event_start_utc IS NULL AND event_end_utc IS NULL)
        OR (event_start_utc IS NOT NULL AND event_end_utc IS NOT NULL)
    ),
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (logical_run_id, attempt_id, artifact_path, sha256_hex)
);

CREATE TABLE IF NOT EXISTS delivery_outbox (
    outbox_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL UNIQUE,
    report_sha256 TEXT NOT NULL
        CHECK (length(report_sha256) = 64 AND report_sha256 NOT GLOB '*[^0-9a-f]*'),
    payload_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'SENDING', 'SENT', 'FAILED')),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id) REFERENCES logical_run(logical_run_id)
);

CREATE TRIGGER IF NOT EXISTS delivery_outbox_production_only
BEFORE INSERT ON delivery_outbox
WHEN (SELECT run_namespace FROM logical_run
      WHERE logical_run_id = NEW.logical_run_id) != 'PRODUCTION'
BEGIN
    SELECT RAISE(ABORT, 'replay runs cannot write delivery_outbox');
END;
