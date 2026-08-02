PRAGMA foreign_keys = ON;

-- Immutable evidence metadata.  The mapping artifact digest is external to the
-- artifact itself (receipt semantics), so there is no self-referential hash.
CREATE TABLE IF NOT EXISTS smart_money_identity_artifact (
    artifact_sha256 TEXT PRIMARY KEY CHECK (
        length(artifact_sha256) = 64
        AND artifact_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    artifact_schema TEXT NOT NULL CHECK (
        artifact_schema IN (
            'binance-smart-money-square-identity-mapping/v1',
            'binance-smart-money-square-identity-mapping/v2'
        )
    ),
    tenant_id TEXT NOT NULL CHECK (length(trim(tenant_id)) > 0),
    verification_status TEXT NOT NULL CHECK (
        verification_status IN ('DIRECT_VERIFIED', 'LEGACY_SELF_REPORTED')
    ),
    promotion_status TEXT NOT NULL CHECK (
        promotion_status IN ('PROPOSED', 'APPROVED')
    ),
    captured_at_utc TEXT NOT NULL CHECK (julianday(captured_at_utc) IS NOT NULL),
    artifact_path TEXT NOT NULL CHECK (length(trim(artifact_path)) > 0),
    request_manifest_path TEXT,
    request_manifest_sha256 TEXT CHECK (
        request_manifest_sha256 IS NULL OR (
            length(request_manifest_sha256) = 64
            AND request_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
        )
    ),
    raw_response_path TEXT,
    raw_response_sha256 TEXT CHECK (
        raw_response_sha256 IS NULL OR (
            length(raw_response_sha256) = 64
            AND raw_response_sha256 NOT GLOB '*[^0-9a-f]*'
        )
    ),
    top_trader_id_pointer TEXT,
    square_uid_pointer TEXT,
    review_json TEXT CHECK (review_json IS NULL OR json_valid(review_json)),
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CHECK (
        artifact_schema = 'binance-smart-money-square-identity-mapping/v1'
        OR (
            verification_status = 'DIRECT_VERIFIED'
            AND request_manifest_path IS NOT NULL
            AND request_manifest_sha256 IS NOT NULL
            AND raw_response_path IS NOT NULL
            AND raw_response_sha256 IS NOT NULL
            AND top_trader_id_pointer = '/data/topTraderId'
            AND square_uid_pointer = '/data/squareUid'
            AND (
                (promotion_status = 'PROPOSED' AND review_json IS NULL)
                OR (promotion_status = 'APPROVED' AND review_json IS NOT NULL)
            )
        )
    )
);

CREATE TABLE IF NOT EXISTS smart_money_identity_mapping_event (
    mapping_event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL CHECK (length(trim(tenant_id)) > 0),
    top_trader_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('LINK', 'REVOKE')),
    artifact_sha256 TEXT,
    effective_at_utc TEXT NOT NULL CHECK (julianday(effective_at_utc) IS NOT NULL),
    reason TEXT,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (artifact_sha256)
        REFERENCES smart_money_identity_artifact(artifact_sha256),
    FOREIGN KEY (top_trader_id)
        REFERENCES smart_money_trader_entity(top_trader_id),
    FOREIGN KEY (author_id) REFERENCES author_entity(author_id),
    CHECK (
        (event_type = 'LINK' AND artifact_sha256 IS NOT NULL AND reason IS NULL)
        OR
        (event_type = 'REVOKE' AND artifact_sha256 IS NULL
            AND length(trim(reason)) > 0)
    )
);

CREATE INDEX IF NOT EXISTS smart_money_identity_event_order_idx
    ON smart_money_identity_mapping_event (
        tenant_id, effective_at_utc, mapping_event_id
    );
