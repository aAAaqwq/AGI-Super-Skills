PRAGMA foreign_keys = ON;

-- Per-author Profile fetch evidence.  This is intentionally separate from
-- author_fetch_coverage, whose A/B rows remain the aggregate compatibility
-- contract.
CREATE TABLE IF NOT EXISTS profile_fetch_outcome (
    profile_fetch_outcome_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    profile_cohort TEXT NOT NULL CHECK (
        profile_cohort IN ('SMART_MONEY_PROFILE', 'SEED_PROFILE')
    ),
    planned_author_id TEXT NOT NULL CHECK (
        length(trim(planned_author_id)) > 0
    ),
    planned_id_type TEXT NOT NULL CHECK (
        planned_id_type IN ('TOP_TRADER_ID', 'SQUARE_UID')
    ),
    resolved_author_id TEXT CHECK (
        resolved_author_id IS NULL OR length(trim(resolved_author_id)) > 0
    ),
    fetch_status TEXT NOT NULL CHECK (
        fetch_status IN (
            'COMPLETE', 'EMPTY', 'PARTIAL', 'FAILED', 'NOT_ATTEMPTED'
        )
    ),
    post_count INTEGER NOT NULL CHECK (post_count >= 0),
    pages_fetched INTEGER NOT NULL CHECK (pages_fetched >= 0),
    termination_reason TEXT CHECK (
        termination_reason IS NULL OR length(trim(termination_reason)) > 0
    ),
    error_detail TEXT CHECK (
        error_detail IS NULL OR length(trim(error_detail)) > 0
    ),
    observed_at_utc TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (attempt_id, profile_cohort, planned_author_id),
    CHECK (
        (profile_cohort = 'SMART_MONEY_PROFILE' AND planned_id_type = 'TOP_TRADER_ID')
        OR
        (profile_cohort = 'SEED_PROFILE' AND planned_id_type = 'SQUARE_UID')
    ),
    CHECK (fetch_status != 'COMPLETE' OR post_count > 0),
    CHECK (
        fetch_status NOT IN ('EMPTY', 'FAILED', 'NOT_ATTEMPTED')
        OR post_count = 0
    ),
    CHECK (fetch_status != 'NOT_ATTEMPTED' OR pages_fetched = 0),
    CHECK (fetch_status NOT IN ('COMPLETE', 'EMPTY') OR pages_fetched > 0)
);

CREATE INDEX IF NOT EXISTS profile_fetch_outcome_attempt_idx
    ON profile_fetch_outcome (attempt_id, profile_cohort, fetch_status);

CREATE INDEX IF NOT EXISTS profile_fetch_outcome_planned_author_idx
    ON profile_fetch_outcome (planned_id_type, planned_author_id);
