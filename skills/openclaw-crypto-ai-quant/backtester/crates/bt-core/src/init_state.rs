//! Initial state injection for the backtester.
//!
//! Allows loading a pre-existing portfolio snapshot (exported from live or paper
//! trading) so that the backtester can continue from current positions instead
//! of starting from a blank slate.

use crate::config::Confidence;
use crate::position::{Position, PositionType};
use rustc_hash::FxHashMap;
use serde::Deserialize;

/// JSON schema versions supported by this loader.
const SUPPORTED_VERSIONS: [u32; 2] = [1, 2];

/// Runtime state that can affect deterministic continuation.
#[derive(Debug, Deserialize, Default)]
pub struct InitRuntimeState {
    #[serde(default)]
    pub entry_attempt_ms_by_symbol: FxHashMap<String, i64>,
    #[serde(default)]
    pub exit_attempt_ms_by_symbol: FxHashMap<String, i64>,
}

/// Top-level init-state file (matches `export_state.py` output and v2 snapshots).
#[derive(Debug, Deserialize)]
pub struct InitStateFile {
    pub version: u32,
    pub source: String,
    pub exported_at_ms: i64,
    pub balance: f64,
    #[serde(default)]
    pub positions: Vec<InitPosition>,
    #[serde(default)]
    pub runtime: Option<InitRuntimeState>,
}

/// A single position entry in the init-state file.
#[derive(Debug, Deserialize)]
pub struct InitPosition {
    pub symbol: String,
    pub side: String,
    pub size: f64,
    pub entry_price: f64,
    pub entry_atr: f64,
    #[serde(default)]
    pub trailing_sl: Option<f64>,
    pub confidence: String,
    pub leverage: f64,
    pub margin_used: f64,
    #[serde(default)]
    pub adds_count: u32,
    #[serde(default)]
    pub tp1_taken: bool,
    #[serde(default)]
    pub open_time_ms: i64,
    #[serde(default)]
    pub last_add_time_ms: i64,
    #[serde(default)]
    pub entry_adx_threshold: f64,
}

/// Seed tuple consumed by `engine::run_simulation`.
pub type SimInitState = (
    f64,
    FxHashMap<String, Position>,
    FxHashMap<String, i64>,
    FxHashMap<String, i64>,
);

/// Load and validate an init-state JSON file from disk.
pub fn load(path: &str) -> Result<InitStateFile, String> {
    let content = std::fs::read_to_string(path)
        .map_err(|e| format!("Failed to read init-state file {:?}: {}", path, e))?;
    let state: InitStateFile = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse init-state JSON: {}", e))?;

    if !SUPPORTED_VERSIONS.contains(&state.version) {
        return Err(format!(
            "Unsupported init-state version {} (expected one of {:?})",
            state.version, SUPPORTED_VERSIONS,
        ));
    }
    if state.balance < 0.0 {
        return Err(format!("Invalid init-state balance: {}", state.balance));
    }

    Ok(state)
}

fn symbol_allowed(symbol: &str, valid_symbols: Option<&[&str]>) -> bool {
    match valid_symbols {
        Some(syms) => syms.contains(&symbol),
        None => true,
    }
}

/// Convert the loaded init-state into simulator-compatible state including
/// runtime cooldown snapshots.
///
/// Returns `(balance, positions, last_entry_attempt_ms, last_exit_attempt_ms)`.
pub fn into_sim_state_with_runtime(
    state: InitStateFile,
    valid_symbols: Option<&[&str]>,
) -> SimInitState {
    let mut positions = FxHashMap::default();

    for ip in state.positions {
        if !symbol_allowed(&ip.symbol, valid_symbols) {
            eprintln!(
                "[init-state] WARNING: position for {:?} skipped - not in candle data",
                ip.symbol,
            );
            continue;
        }

        let pos_type = match ip.side.to_lowercase().as_str() {
            "long" => PositionType::Long,
            "short" => PositionType::Short,
            other => {
                eprintln!(
                    "[init-state] WARNING: position for {:?} skipped - unknown side {:?}",
                    ip.symbol, other,
                );
                continue;
            }
        };

        let confidence = match ip.confidence.to_lowercase().as_str() {
            "high" => Confidence::High,
            "medium" => Confidence::Medium,
            "low" => Confidence::Low,
            _ => Confidence::Medium,
        };

        let pos = Position {
            symbol: ip.symbol.clone(),
            pos_type,
            entry_price: ip.entry_price,
            size: ip.size,
            confidence,
            entry_atr: ip.entry_atr,
            entry_adx_threshold: ip.entry_adx_threshold,
            trailing_sl: ip.trailing_sl,
            leverage: ip.leverage,
            margin_used: ip.margin_used,
            adds_count: ip.adds_count,
            tp1_taken: ip.tp1_taken,
            open_time_ms: ip.open_time_ms,
            last_add_time_ms: ip.last_add_time_ms,
            mae_usd: 0.0,
            mfe_usd: 0.0,
        };
        positions.insert(ip.symbol, pos);
    }

    let mut last_entry_attempt_ms: FxHashMap<String, i64> = FxHashMap::default();
    let mut last_exit_attempt_ms: FxHashMap<String, i64> = FxHashMap::default();
    if let Some(runtime) = state.runtime {
        for (symbol, ts) in runtime.entry_attempt_ms_by_symbol {
            if symbol_allowed(symbol.as_str(), valid_symbols) {
                last_entry_attempt_ms.insert(symbol, ts);
            }
        }
        for (symbol, ts) in runtime.exit_attempt_ms_by_symbol {
            if symbol_allowed(symbol.as_str(), valid_symbols) {
                last_exit_attempt_ms.insert(symbol, ts);
            }
        }
    }

    eprintln!(
        "[init-state] Loaded balance=${:.2}, {} position(s), {} entry cooldown marker(s), {} exit cooldown marker(s) from {:?} (exported at {})",
        state.balance,
        positions.len(),
        last_entry_attempt_ms.len(),
        last_exit_attempt_ms.len(),
        state.source,
        state.exported_at_ms,
    );

    (
        state.balance,
        positions,
        last_entry_attempt_ms,
        last_exit_attempt_ms,
    )
}

/// Backward-compatible conversion that drops runtime cooldown maps.
pub fn into_sim_state(
    state: InitStateFile,
    valid_symbols: Option<&[&str]>,
) -> (f64, FxHashMap<String, Position>) {
    let (balance, positions, _, _) = into_sim_state_with_runtime(state, valid_symbols);
    (balance, positions)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_valid_v1_json() {
        let json = r#"{
            "version": 1,
            "source": "paper",
            "exported_at_ms": 1770562800000,
            "balance": 230.19,
            "positions": [
                {
                    "symbol": "BTC",
                    "side": "long",
                    "size": 0.003,
                    "entry_price": 71000.0,
                    "entry_atr": 1200.0,
                    "trailing_sl": 69500.0,
                    "confidence": "medium",
                    "leverage": 5.0,
                    "margin_used": 42.6,
                    "adds_count": 0,
                    "tp1_taken": false,
                    "open_time_ms": 1770500000000,
                    "last_add_time_ms": 0
                }
            ]
        }"#;

        let state: InitStateFile = serde_json::from_str(json).expect("v1 init-state should parse");
        assert_eq!(state.version, 1);
        assert_eq!(state.source, "paper");
        assert!((state.balance - 230.19).abs() < 0.01);
        assert_eq!(state.positions.len(), 1);
        assert_eq!(state.positions[0].symbol, "BTC");
    }

    #[test]
    fn test_parse_valid_v2_json_with_runtime() {
        let json = r#"{
            "version": 2,
            "source": "live_canonical",
            "exported_at_ms": 1770562800000,
            "balance": 1000.0,
            "positions": [],
            "runtime": {
                "entry_attempt_ms_by_symbol": {"BTC": 1770562700000},
                "exit_attempt_ms_by_symbol": {"ETH": 1770562750000}
            }
        }"#;

        let state: InitStateFile = serde_json::from_str(json).expect("v2 init-state should parse");
        assert_eq!(state.version, 2);
        let runtime = state.runtime.expect("runtime expected");
        assert_eq!(
            runtime.entry_attempt_ms_by_symbol.get("BTC").copied(),
            Some(1770562700000)
        );
        assert_eq!(
            runtime.exit_attempt_ms_by_symbol.get("ETH").copied(),
            Some(1770562750000)
        );
    }

    #[test]
    fn test_into_sim_state_with_runtime_filters_unknown_symbols() {
        let mut entry_map = FxHashMap::default();
        entry_map.insert("BTC".to_string(), 1_000);
        entry_map.insert("UNKNOWN".to_string(), 2_000);
        let mut exit_map = FxHashMap::default();
        exit_map.insert("ETH".to_string(), 3_000);

        let state = InitStateFile {
            version: 2,
            source: "live".to_string(),
            exported_at_ms: 0,
            balance: 500.0,
            positions: vec![InitPosition {
                symbol: "BTC".to_string(),
                side: "long".to_string(),
                size: 0.003,
                entry_price: 71000.0,
                entry_atr: 1200.0,
                trailing_sl: Some(69500.0),
                confidence: "high".to_string(),
                leverage: 5.0,
                margin_used: 42.6,
                adds_count: 1,
                tp1_taken: false,
                open_time_ms: 1770500000000,
                last_add_time_ms: 1770510000000,
                entry_adx_threshold: 22.0,
            }],
            runtime: Some(InitRuntimeState {
                entry_attempt_ms_by_symbol: entry_map,
                exit_attempt_ms_by_symbol: exit_map,
            }),
        };

        let valid_syms = vec!["BTC", "ETH"];
        let (balance, positions, entry_attempts, exit_attempts) =
            into_sim_state_with_runtime(state, Some(&valid_syms));
        assert!((balance - 500.0).abs() < 0.01);
        assert_eq!(positions.len(), 1);
        assert_eq!(entry_attempts.len(), 1);
        assert_eq!(entry_attempts.get("BTC").copied(), Some(1_000));
        assert_eq!(exit_attempts.len(), 1);
        assert_eq!(exit_attempts.get("ETH").copied(), Some(3_000));
    }

    #[test]
    fn test_unsupported_version() {
        let json = r#"{
            "version": 99,
            "source": "paper",
            "exported_at_ms": 0,
            "balance": 100.0,
            "positions": []
        }"#;

        let tmpdir = tempfile::tempdir().expect("tempdir should exist");
        let path = tmpdir.path().join("test_init_state_v99.json");
        std::fs::write(&path, json).expect("write should succeed");

        let result = load(path.to_str().expect("path should be utf-8"));
        assert!(result.is_err());
        assert!(result
            .expect_err("version 99 should fail")
            .contains("Unsupported init-state version"));
    }
}
