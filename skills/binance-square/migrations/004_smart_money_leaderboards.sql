PRAGMA foreign_keys = ON;

-- Binance Futures Smart Money identities are not Binance Square identities.
-- ``top_trader_id`` remains source-specific unless an explicit evidence-backed
-- mapping is recorded in smart_money_square_identity_mapping.
CREATE TABLE IF NOT EXISTS smart_money_trader_entity (
    top_trader_id TEXT PRIMARY KEY CHECK (length(trim(top_trader_id)) > 0),
    identity_source TEXT NOT NULL CHECK (
        identity_source = 'BINANCE_SMART_MONEY_TOP_TRADER_ID'
    ),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS smart_money_leaderboard_capture (
    smart_money_capture_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    ranking_type TEXT NOT NULL CHECK (ranking_type IN ('PNL', 'ROI')),
    time_range TEXT NOT NULL CHECK (time_range = '30D'),
    capture_status TEXT NOT NULL CHECK (capture_status IN ('COMPLETE', 'FAILED')),
    captured_at_utc TEXT NOT NULL,
    snapshot_semantics TEXT NOT NULL CHECK (
        snapshot_semantics = 'OBSERVED_WINDOW'
    ),
    observed_start_utc TEXT NOT NULL,
    observed_end_utc TEXT NOT NULL,
    last_update_time_ms INTEGER CHECK (
        last_update_time_ms IS NULL OR last_update_time_ms >= 0
    ),
    evidence_path TEXT NOT NULL CHECK (length(trim(evidence_path)) > 0),
    evidence_file_sha256 TEXT NOT NULL CHECK (
        length(evidence_file_sha256) = 64
        AND evidence_file_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    payload_sha256 TEXT CHECK (
        payload_sha256 IS NULL
        OR (
            length(payload_sha256) = 64
            AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
        )
    ),
    expected_rows INTEGER NOT NULL CHECK (expected_rows = 30),
    rendered_rows INTEGER NOT NULL CHECK (rendered_rows BETWEEN 0 AND 30),
    failure_reason TEXT,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    UNIQUE (attempt_id, ranking_type, time_range),
    CHECK (
        julianday(observed_start_utc) IS NOT NULL
        AND julianday(observed_end_utc) IS NOT NULL
        AND julianday(captured_at_utc) IS NOT NULL
        AND julianday(observed_start_utc) <= julianday(observed_end_utc)
        AND julianday(observed_end_utc) <= julianday(captured_at_utc)
    ),
    CHECK (
        (capture_status = 'COMPLETE' AND rendered_rows = 30
            AND last_update_time_ms IS NOT NULL
            AND failure_reason IS NULL)
        OR
        (capture_status = 'FAILED' AND rendered_rows = 0
            AND length(trim(failure_reason)) > 0)
    )
);

CREATE TABLE IF NOT EXISTS smart_money_leaderboard_row (
    smart_money_row_id TEXT PRIMARY KEY,
    smart_money_capture_id TEXT NOT NULL,
    top_trader_id TEXT NOT NULL,
    rank_no INTEGER NOT NULL CHECK (rank_no BETWEEN 1 AND 30),
    pnl_decimal TEXT,
    roi_decimal TEXT,
    assets_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(assets_json)),
    subscribers INTEGER CHECK (subscribers IS NULL OR subscribers >= 0),
    position_status TEXT,
    signal_lead_on INTEGER CHECK (signal_lead_on IN (0, 1)),
    raw_row_json TEXT NOT NULL CHECK (
        json_valid(raw_row_json)
        AND json_type(raw_row_json, '$.topTraderId') = 'text'
        AND json_extract(raw_row_json, '$.topTraderId') = top_trader_id
    ),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (smart_money_capture_id)
        REFERENCES smart_money_leaderboard_capture(smart_money_capture_id)
        ON DELETE CASCADE,
    FOREIGN KEY (top_trader_id)
        REFERENCES smart_money_trader_entity(top_trader_id),
    UNIQUE (smart_money_capture_id, rank_no),
    UNIQUE (smart_money_capture_id, top_trader_id)
);

CREATE TRIGGER IF NOT EXISTS smart_money_pnl_row_requires_pnl_insert
BEFORE INSERT ON smart_money_leaderboard_row
WHEN (
    SELECT ranking_type
    FROM smart_money_leaderboard_capture
    WHERE smart_money_capture_id = NEW.smart_money_capture_id
) = 'PNL' AND NEW.pnl_decimal IS NULL
BEGIN
    SELECT RAISE(ABORT, 'PNL rows require pnl_decimal');
END;

CREATE TRIGGER IF NOT EXISTS smart_money_pnl_row_requires_pnl_update
BEFORE UPDATE OF smart_money_capture_id, pnl_decimal
ON smart_money_leaderboard_row
WHEN (
    SELECT ranking_type
    FROM smart_money_leaderboard_capture
    WHERE smart_money_capture_id = NEW.smart_money_capture_id
) = 'PNL' AND NEW.pnl_decimal IS NULL
BEGIN
    SELECT RAISE(ABORT, 'PNL rows require pnl_decimal');
END;

CREATE TRIGGER IF NOT EXISTS smart_money_roi_row_requires_roi_insert
BEFORE INSERT ON smart_money_leaderboard_row
WHEN (
    SELECT ranking_type
    FROM smart_money_leaderboard_capture
    WHERE smart_money_capture_id = NEW.smart_money_capture_id
) = 'ROI' AND NEW.roi_decimal IS NULL
BEGIN
    SELECT RAISE(ABORT, 'ROI rows require roi_decimal');
END;

CREATE TRIGGER IF NOT EXISTS smart_money_roi_row_requires_roi_update
BEFORE UPDATE OF smart_money_capture_id, roi_decimal
ON smart_money_leaderboard_row
WHEN (
    SELECT ranking_type
    FROM smart_money_leaderboard_capture
    WHERE smart_money_capture_id = NEW.smart_money_capture_id
) = 'ROI' AND NEW.roi_decimal IS NULL
BEGIN
    SELECT RAISE(ABORT, 'ROI rows require roi_decimal');
END;

CREATE TRIGGER IF NOT EXISTS smart_money_capture_metric_contract_update
BEFORE UPDATE OF ranking_type ON smart_money_leaderboard_capture
WHEN (
    (NEW.ranking_type = 'PNL' AND EXISTS (
        SELECT 1 FROM smart_money_leaderboard_row
        WHERE smart_money_capture_id = NEW.smart_money_capture_id
          AND pnl_decimal IS NULL
    ))
    OR
    (NEW.ranking_type = 'ROI' AND EXISTS (
        SELECT 1 FROM smart_money_leaderboard_row
        WHERE smart_money_capture_id = NEW.smart_money_capture_id
          AND roi_decimal IS NULL
    ))
)
BEGIN
    SELECT RAISE(ABORT, 'ranking_type conflicts with persisted row metrics');
END;

-- Profile values are point-in-time evidence.  They are never overwritten on
-- the stable trader entity.  FAILED observations permit partial profile
-- coverage to remain auditable without inventing values.
CREATE TABLE IF NOT EXISTS smart_money_profile_observation (
    smart_money_profile_observation_id TEXT PRIMARY KEY,
    logical_run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    top_trader_id TEXT NOT NULL,
    observation_status TEXT NOT NULL CHECK (
        observation_status IN ('COMPLETE', 'FAILED')
    ),
    captured_at_utc TEXT NOT NULL,
    days_active INTEGER CHECK (days_active IS NULL OR days_active >= 0),
    mdd_decimal TEXT,
    win_rate_decimal TEXT,
    um_margin_balance_decimal TEXT,
    cm_margin_balance_decimal TEXT,
    net_transfer_decimal TEXT,
    sharing_position_json TEXT CHECK (
        sharing_position_json IS NULL OR json_valid(sharing_position_json)
    ),
    sharing_history_json TEXT CHECK (
        sharing_history_json IS NULL OR json_valid(sharing_history_json)
    ),
    latest_record_json TEXT CHECK (
        latest_record_json IS NULL OR json_valid(latest_record_json)
    ),
    is_ai INTEGER CHECK (is_ai IN (0, 1)),
    is_pm_user INTEGER CHECK (is_pm_user IN (0, 1)),
    copy_trade_portfolio_ids_json TEXT CHECK (
        copy_trade_portfolio_ids_json IS NULL
        OR json_valid(copy_trade_portfolio_ids_json)
    ),
    evidence_path TEXT NOT NULL CHECK (length(trim(evidence_path)) > 0),
    evidence_file_sha256 TEXT NOT NULL CHECK (
        length(evidence_file_sha256) = 64
        AND evidence_file_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    payload_sha256 TEXT CHECK (
        payload_sha256 IS NULL
        OR (
            length(payload_sha256) = 64
            AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
        )
    ),
    failure_reason TEXT,
    raw_profile_json TEXT CHECK (
        raw_profile_json IS NULL OR json_valid(raw_profile_json)
    ),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id, attempt_id)
        REFERENCES run_attempt(logical_run_id, attempt_id),
    FOREIGN KEY (top_trader_id)
        REFERENCES smart_money_trader_entity(top_trader_id),
    UNIQUE (attempt_id, top_trader_id),
    CHECK (
        (observation_status = 'COMPLETE' AND failure_reason IS NULL
            AND raw_profile_json IS NOT NULL
            AND json_type(raw_profile_json, '$.topTraderId') = 'text'
            AND json_extract(raw_profile_json, '$.topTraderId') = top_trader_id)
        OR
        (observation_status = 'FAILED' AND length(trim(failure_reason)) > 0)
    )
);

CREATE TABLE IF NOT EXISTS smart_money_square_identity_mapping (
    top_trader_id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL UNIQUE,
    verification_method TEXT NOT NULL CHECK (
        verification_method = 'EXPLICIT_SOURCE_EVIDENCE'
    ),
    verified_at_utc TEXT NOT NULL,
    evidence_path TEXT NOT NULL CHECK (length(trim(evidence_path)) > 0),
    evidence_sha256 TEXT NOT NULL CHECK (
        length(evidence_sha256) = 64
        AND evidence_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (top_trader_id)
        REFERENCES smart_money_trader_entity(top_trader_id),
    FOREIGN KEY (author_id) REFERENCES author_entity(author_id)
);

CREATE INDEX IF NOT EXISTS smart_money_capture_run_idx
    ON smart_money_leaderboard_capture (
        logical_run_id, attempt_id, ranking_type, captured_at_utc
    );

CREATE INDEX IF NOT EXISTS smart_money_profile_run_idx
    ON smart_money_profile_observation (
        logical_run_id, attempt_id, captured_at_utc, top_trader_id
    );
