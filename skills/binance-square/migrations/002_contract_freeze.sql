PRAGMA foreign_keys = ON;

-- v4.1 is an additive contract freeze.  The v4.0 run ledger remains intact;
-- these tables attach point-in-time state to a concrete run attempt.

CREATE TABLE IF NOT EXISTS author_entity (
    author_id TEXT PRIMARY KEY
        CHECK (length(trim(author_id)) > 0 AND upper(trim(author_id)) != 'LIVE'),
    identity_source TEXT NOT NULL CHECK (length(trim(identity_source)) > 0),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS author_profile_observation (
    profile_observation_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    profile_url TEXT,
    username TEXT,
    display_name TEXT,
    public_live INTEGER CHECK (public_live IN (0, 1)),
    trading_days INTEGER CHECK (trading_days IS NULL OR trading_days >= 0),
    analysis_completeness TEXT,
    tier_status TEXT,
    labels_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(labels_json)),
    content_hash TEXT NOT NULL
        CHECK (length(content_hash) = 64 AND content_hash NOT GLOB '*[^0-9a-f]*'),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    FOREIGN KEY (author_id) REFERENCES author_entity(author_id),
    UNIQUE (attempt_id, author_id, observed_at_utc, content_hash)
);

CREATE TABLE IF NOT EXISTS leaderboard_capture (
    leaderboard_capture_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    ranking_type TEXT NOT NULL CHECK (
        ranking_type IN ('PNL', 'ROI', 'VOLUME', 'WIN_RATE')
    ),
    time_range TEXT NOT NULL CHECK (time_range = '30D'),
    capture_status TEXT NOT NULL CHECK (
        capture_status IN ('COMPLETE', 'PARTIAL_SEED_DISCOVERY', 'BLOCKED', 'FAILED')
    ),
    captured_at_utc TEXT NOT NULL,
    expected_rows INTEGER NOT NULL DEFAULT 30 CHECK (expected_rows >= 0),
    rendered_rows INTEGER NOT NULL DEFAULT 0 CHECK (
        rendered_rows >= 0 AND rendered_rows <= expected_rows
    ),
    evidence_path TEXT,
    evidence_sha256 TEXT CHECK (
        evidence_sha256 IS NULL OR
        (length(evidence_sha256) = 64 AND evidence_sha256 NOT GLOB '*[^0-9a-f]*')
    ),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (attempt_id, ranking_type, time_range, captured_at_utc),
    CHECK (capture_status != 'COMPLETE' OR rendered_rows = expected_rows),
    CHECK (capture_status != 'PARTIAL_SEED_DISCOVERY' OR rendered_rows = 0)
);

CREATE TABLE IF NOT EXISTS leaderboard_row (
    leaderboard_row_id TEXT PRIMARY KEY,
    leaderboard_capture_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    rank_no INTEGER NOT NULL CHECK (rank_no BETWEEN 1 AND 30),
    metric_value_decimal TEXT,
    metric_unit TEXT,
    public_live INTEGER CHECK (public_live IN (0, 1)),
    raw_row_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(raw_row_json)),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (leaderboard_capture_id)
        REFERENCES leaderboard_capture(leaderboard_capture_id),
    FOREIGN KEY (author_id) REFERENCES author_entity(author_id),
    UNIQUE (leaderboard_capture_id, rank_no),
    UNIQUE (leaderboard_capture_id, author_id)
);

CREATE TABLE IF NOT EXISTS post_observation (
    post_observation_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    post_id TEXT NOT NULL CHECK (
        length(trim(post_id)) > 0 AND post_id NOT GLOB '*[^0-9]*'
    ),
    canonical_post_url TEXT NOT NULL,
    author_id TEXT NOT NULL,
    published_at_utc TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    content_hash TEXT NOT NULL CHECK (
        length(content_hash) = 64 AND content_hash NOT GLOB '*[^0-9a-f]*'
    ),
    source_channel TEXT NOT NULL CHECK (length(trim(source_channel)) > 0),
    source_record_ordinal INTEGER NOT NULL CHECK (source_record_ordinal >= 0),
    observation_status TEXT NOT NULL DEFAULT 'ACCEPTED'
        CHECK (observation_status = 'ACCEPTED'),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    FOREIGN KEY (author_id) REFERENCES author_entity(author_id),
    UNIQUE (attempt_id, source_channel, source_record_ordinal),
    UNIQUE (attempt_id, source_channel, post_id, observed_at_utc, content_hash)
);

CREATE INDEX IF NOT EXISTS post_observation_post_idx
    ON post_observation (post_id, logical_run_id, attempt_id);

CREATE TABLE IF NOT EXISTS author_fetch_coverage (
    author_fetch_coverage_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    source_channel TEXT NOT NULL,
    author_tier TEXT NOT NULL CHECK (author_tier IN ('A', 'B')),
    expected_authors INTEGER NOT NULL CHECK (expected_authors >= 0),
    covered_authors INTEGER NOT NULL CHECK (
        covered_authors >= 0 AND covered_authors <= expected_authors
    ),
    coverage_status TEXT NOT NULL CHECK (
        coverage_status IN ('COMPLETE', 'PARTIAL', 'BLOCKED', 'NOT_APPLICABLE')
    ),
    observed_at_utc TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (attempt_id, source_channel, author_tier),
    CHECK (coverage_status != 'COMPLETE' OR covered_authors = expected_authors)
);

CREATE TABLE IF NOT EXISTS signal_family (
    signal_family_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL CHECK (
        length(trim(post_id)) > 0 AND post_id NOT GLOB '*[^0-9]*'
    ),
    symbol TEXT NOT NULL CHECK (length(trim(symbol)) > 0),
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    first_logical_run_id TEXT NOT NULL,
    first_attempt_id TEXT NOT NULL,
    family_status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (family_status IN ('OPEN', 'INVALIDATED', 'CLOSED')),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (first_logical_run_id, first_attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (post_id, symbol, direction)
);

CREATE TABLE IF NOT EXISTS signal_revision (
    signal_revision_id TEXT PRIMARY KEY,
    signal_family_id TEXT NOT NULL,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    revision_no INTEGER NOT NULL CHECK (revision_no >= 1),
    decision_at_utc TEXT NOT NULL,
    parameter_source TEXT NOT NULL CHECK (
        parameter_source IN ('AUTHOR', 'SYSTEM_REDERIVED')
    ),
    entry_low_decimal TEXT NOT NULL,
    entry_high_decimal TEXT NOT NULL,
    stop_loss_decimal TEXT NOT NULL,
    tp1_decimal TEXT NOT NULL,
    tp2_decimal TEXT,
    original_signal_status TEXT NOT NULL,
    invalidation_reason TEXT,
    dq_score INTEGER NOT NULL CHECK (dq_score BETWEEN 0 AND 100),
    quality_flags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(quality_flags_json)),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (signal_family_id) REFERENCES signal_family(signal_family_id),
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (signal_family_id, revision_no),
    UNIQUE (signal_family_id, logical_run_id, attempt_id)
);

CREATE TABLE IF NOT EXISTS tracking_evaluation (
    tracking_evaluation_id TEXT PRIMARY KEY,
    signal_revision_id TEXT NOT NULL,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    evaluated_at_utc TEXT NOT NULL,
    evaluation_status TEXT NOT NULL CHECK (
        evaluation_status IN (
            'PENDING', 'UNTRIGGERED', 'TRIGGERED', 'STOPPED',
            'TP1_HIT', 'TP2_HIT', 'EXPIRED'
        )
    ),
    nominal_r_decimal TEXT,
    mfe_r_decimal TEXT,
    mae_r_decimal TEXT,
    net_r_decimal TEXT,
    cost_model_version TEXT,
    dq_score INTEGER NOT NULL CHECK (dq_score BETWEEN 0 AND 100),
    quality_flags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(quality_flags_json)),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (signal_revision_id) REFERENCES signal_revision(signal_revision_id),
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (signal_revision_id, evaluated_at_utc),
    CHECK (net_r_decimal IS NULL OR cost_model_version IS NOT NULL)
);
