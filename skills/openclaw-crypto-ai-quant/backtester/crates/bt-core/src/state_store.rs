//! SQLite-backed persistence for [`StrategyState`].
//!
//! Provides `save_state` / `load_state` so the kernel state can survive process
//! restarts — critical for live and paper trading.

use crate::decision_kernel::StrategyState;
use rusqlite::{params, Connection};
use sha2::{Digest, Sha256};
use std::path::Path;

/// Errors returned by state-store operations.
#[derive(Debug)]
pub enum StoreError {
    Sqlite(rusqlite::Error),
    Json(serde_json::Error),
    ChecksumMismatch { expected: String, actual: String },
}

impl std::fmt::Display for StoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StoreError::Sqlite(e) => write!(f, "sqlite: {e}"),
            StoreError::Json(e) => write!(f, "json: {e}"),
            StoreError::ChecksumMismatch { expected, actual } => {
                write!(f, "checksum mismatch: expected {expected}, got {actual}")
            }
        }
    }
}

impl std::error::Error for StoreError {}

impl From<rusqlite::Error> for StoreError {
    fn from(e: rusqlite::Error) -> Self {
        StoreError::Sqlite(e)
    }
}

impl From<serde_json::Error> for StoreError {
    fn from(e: serde_json::Error) -> Self {
        StoreError::Json(e)
    }
}

fn sha256_hex(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn ensure_table(conn: &Connection) -> Result<(), StoreError> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS kernel_state (
             id           INTEGER PRIMARY KEY,
             timestamp_ms INTEGER NOT NULL,
             state_json   TEXT    NOT NULL,
             checksum     TEXT    NOT NULL
         );",
    )?;
    Ok(())
}

/// Serialize `state` to JSON, compute SHA-256 checksum, and insert a row.
pub fn save_state(
    db_path: &Path,
    state: &StrategyState,
    timestamp_ms: i64,
) -> Result<(), StoreError> {
    let conn = Connection::open(db_path)?;
    ensure_table(&conn)?;

    let json = serde_json::to_string(state)?;
    let checksum = sha256_hex(&json);

    conn.execute(
        "INSERT INTO kernel_state (timestamp_ms, state_json, checksum) VALUES (?1, ?2, ?3)",
        params![timestamp_ms, json, checksum],
    )?;
    Ok(())
}

/// Load the most recent state row, validate its checksum, and deserialize.
///
/// Returns `Ok(None)` when the table is empty (or doesn't exist yet).
/// Returns `Err(ChecksumMismatch)` if the stored checksum doesn't match.
pub fn load_state(db_path: &Path) -> Result<Option<StrategyState>, StoreError> {
    let conn = Connection::open(db_path)?;
    ensure_table(&conn)?;

    let mut stmt =
        conn.prepare("SELECT state_json, checksum FROM kernel_state ORDER BY id DESC LIMIT 1")?;

    let row = stmt.query_row([], |row| {
        let json: String = row.get(0)?;
        let checksum: String = row.get(1)?;
        Ok((json, checksum))
    });

    match row {
        Ok((json, stored_checksum)) => {
            let actual_checksum = sha256_hex(&json);
            if actual_checksum != stored_checksum {
                return Err(StoreError::ChecksumMismatch {
                    expected: stored_checksum,
                    actual: actual_checksum,
                });
            }
            let state: StrategyState = serde_json::from_str(&json)?;
            Ok(Some(state))
        }
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(StoreError::Sqlite(e)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::decision_kernel::StrategyState;
    use std::collections::BTreeMap;

    fn sample_state() -> StrategyState {
        StrategyState {
            schema_version: 1,
            timestamp_ms: 1_000_000,
            step: 42,
            cash_usd: 98_765.4321,
            positions: BTreeMap::new(),
            last_entry_ms: BTreeMap::new(),
            last_exit_ms: BTreeMap::new(),
            last_close_info: BTreeMap::new(),
        }
    }

    #[test]
    fn save_and_load_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("test_state.db");
        let state = sample_state();

        save_state(&db_path, &state, state.timestamp_ms).unwrap();
        let loaded = load_state(&db_path).unwrap();

        assert_eq!(loaded, Some(state));
    }

    #[test]
    fn load_returns_latest_row() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("test_state.db");

        let mut s1 = sample_state();
        s1.step = 1;
        s1.cash_usd = 100_000.0;
        save_state(&db_path, &s1, 1_000).unwrap();

        let mut s2 = sample_state();
        s2.step = 2;
        s2.cash_usd = 99_000.0;
        save_state(&db_path, &s2, 2_000).unwrap();

        let loaded = load_state(&db_path).unwrap().unwrap();
        assert_eq!(loaded.step, 2);
        assert!((loaded.cash_usd - 99_000.0).abs() < 1e-12);
    }

    #[test]
    fn empty_db_returns_none() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("empty.db");

        let loaded = load_state(&db_path).unwrap();
        assert_eq!(loaded, None);
    }

    #[test]
    fn corrupt_checksum_returns_error() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("corrupt.db");
        let state = sample_state();

        save_state(&db_path, &state, state.timestamp_ms).unwrap();

        // Tamper with the stored checksum.
        let conn = Connection::open(&db_path).unwrap();
        conn.execute(
            "UPDATE kernel_state SET checksum = 'badc0ffee' WHERE id = (SELECT MAX(id) FROM kernel_state)",
            [],
        )
        .unwrap();

        let result = load_state(&db_path);
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(
            matches!(err, StoreError::ChecksumMismatch { .. }),
            "expected ChecksumMismatch, got: {err}",
        );
    }

    #[test]
    fn corrupt_json_returns_error() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("bad_json.db");
        let state = sample_state();

        save_state(&db_path, &state, state.timestamp_ms).unwrap();

        // Replace JSON with garbage that has a matching checksum.
        let garbage = "not valid json";
        let checksum = sha256_hex(garbage);
        let conn = Connection::open(&db_path).unwrap();
        conn.execute(
            "UPDATE kernel_state SET state_json = ?1, checksum = ?2 WHERE id = (SELECT MAX(id) FROM kernel_state)",
            params![garbage, checksum],
        )
        .unwrap();

        let result = load_state(&db_path);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), StoreError::Json(_)));
    }

    #[test]
    fn state_with_positions_round_trips() {
        use crate::decision_kernel::{Position, PositionSide};

        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("positions.db");

        let mut state = sample_state();
        state.positions.insert(
            "BTC".to_string(),
            Position {
                symbol: "BTC".to_string(),
                side: PositionSide::Long,
                quantity: 0.5,
                avg_entry_price: 60_000.0,
                opened_at_ms: 500_000,
                updated_at_ms: 900_000,
                notional_usd: 30_000.0,
                margin_usd: 10_000.0,
                confidence: Some(2),
                entry_atr: Some(1_500.0),
                entry_adx_threshold: None,
                adds_count: 1,
                tp1_taken: false,
                trailing_sl: Some(58_000.0),
                mae_usd: -500.0,
                mfe_usd: 2_000.0,
                last_funding_ms: None,
            },
        );

        save_state(&db_path, &state, state.timestamp_ms).unwrap();
        let loaded = load_state(&db_path).unwrap();
        assert_eq!(loaded, Some(state));
    }
}
