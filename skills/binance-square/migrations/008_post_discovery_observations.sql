PRAGMA foreign_keys = ON;

-- Selected source observations that formed the canonical detail-fetch queue.
-- This table is intentionally separate from post_observation: discovery can
-- terminate in quarantine, while post_observation remains accepted detail
-- evidence only.
CREATE TABLE IF NOT EXISTS post_discovery_observation (
    post_discovery_observation_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    post_id TEXT NOT NULL CHECK (
        length(post_id) > 0 AND post_id NOT GLOB '*[^0-9]*'
    ),
    canonical_post_url TEXT NOT NULL CHECK (
        length(trim(canonical_post_url)) > 0
    ),
    source_channel TEXT NOT NULL CHECK (
        source_channel IN (
            'PROFILE', 'FEED', 'CURATED_SIGNAL', 'DIRECT', 'FIXTURE_DETAIL'
        )
    ),
    source_record_ordinal INTEGER NOT NULL CHECK (source_record_ordinal >= 0),
    expected_author_id TEXT CHECK (
        expected_author_id IS NULL OR length(trim(expected_author_id)) > 0
    ),
    expected_first_release_time_ms INTEGER CHECK (
        expected_first_release_time_ms IS NULL
        OR expected_first_release_time_ms >= 0
    ),
    source_profile_url TEXT CHECK (
        source_profile_url IS NULL OR length(trim(source_profile_url)) > 0
    ),
    observed_at_utc TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (attempt_id, source_record_ordinal)
);

CREATE INDEX IF NOT EXISTS post_discovery_observation_attempt_post_idx
    ON post_discovery_observation (attempt_id, post_id, source_record_ordinal);
