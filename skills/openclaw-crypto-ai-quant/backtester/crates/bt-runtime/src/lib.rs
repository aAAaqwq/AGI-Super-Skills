//! Python binding entrypoint for the Rust decision kernel.
//!
//! The module exposes a small JSON envelope API so Python callers can execute the
//! canonical `decision_kernel::step` transition without mirroring Rust structs.
//! The response is always JSON, which keeps the interface language-agnostic and
//! easy to persist in test artefacts.

use std::collections::HashMap;

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::{self, json, Value};

use bt_core::candle::OhlcvBar;
use bt_core::config::IndicatorsConfig;
use bt_core::decision_kernel;
use bt_core::indicators::IndicatorBank;

const ERROR_OK_PREFIX: &str = "bt-runtime:";

#[derive(Serialize)]
struct ErrorObject {
    code: String,
    message: String,
    details: Vec<String>,
}

#[derive(Serialize)]
struct ErrorEnvelope {
    ok: bool,
    error: ErrorObject,
}

#[derive(Serialize)]
struct StepEnvelope {
    ok: bool,
    decision: decision_kernel::DecisionResult,
}

fn validation_error(code: &str, message: &str, details: Vec<String>) -> String {
    let envelope = ErrorEnvelope {
        ok: false,
        error: ErrorObject {
            code: code.to_string(),
            message: message.to_string(),
            details,
        },
    };
    serde_json::to_string(&envelope).unwrap_or_else(|_| {
        json!({
            "ok": false,
            "error": {
                "code": code,
                "message": message,
                "details": envelope.error.details,
            }
        })
        .to_string()
    })
}

fn as_u32(payload: &str, label: &str) -> PyResult<u32> {
    let payload: Value = serde_json::from_str(payload).map_err(|err| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "{ERROR_OK_PREFIX} cannot parse {label} JSON payload: {err}"
        ))
    })?;
    payload
        .as_object()
        .and_then(|obj| obj.get("schema_version"))
        .and_then(|value| value.as_u64())
        .map(|v| v as u32)
        .ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "{ERROR_OK_PREFIX} missing schema_version in {label}"
            ))
        })
}

fn ensure_matching_schema_version(
    state_version: u32,
    event_version: u32,
    params_version: u32,
    expected_version: u32,
) -> Option<Vec<String>> {
    if state_version == expected_version
        && event_version == expected_version
        && params_version == expected_version
    {
        return None;
    }

    let mut errors = Vec::with_capacity(3);
    if state_version != expected_version {
        errors.push(format!(
            "state schema_version={state_version}, expected={expected_version}"
        ));
    }
    if event_version != expected_version {
        errors.push(format!(
            "event schema_version={event_version}, expected={expected_version}"
        ));
    }
    if params_version != expected_version {
        errors.push(format!(
            "params schema_version={params_version}, expected={expected_version}"
        ));
    }
    Some(errors)
}

fn default_schema_version() -> u32 {
    decision_kernel::StrategyState::new(0.0, 0).schema_version
}

fn step_envelope(decision: decision_kernel::DecisionResult) -> String {
    serde_json::to_string(&StepEnvelope { ok: true, decision }).unwrap_or_else(|err| {
        validation_error(
            "SERIALIZATION_FAILED",
            "Failed to serialise kernel decision envelope",
            vec![err.to_string()],
        )
    })
}

#[pyfunction]
fn step_decision(state_json: &str, event_json: &str, params_json: &str) -> PyResult<String> {
    let state_version = match as_u32(state_json, "state") {
        Ok(v) => v,
        Err(err) => {
            return Ok(validation_error(
                "INVALID_JSON",
                "Failed to parse state payload",
                vec![err.to_string()],
            ));
        }
    };

    let event_version = match as_u32(event_json, "event") {
        Ok(v) => v,
        Err(err) => {
            return Ok(validation_error(
                "INVALID_JSON",
                "Failed to parse event payload",
                vec![err.to_string()],
            ));
        }
    };

    let params_version = match as_u32(params_json, "params") {
        Ok(v) => v,
        Err(err) => {
            return Ok(validation_error(
                "INVALID_JSON",
                "Failed to parse params payload",
                vec![err.to_string()],
            ));
        }
    };

    let expected = default_schema_version();
    if let Some(details) =
        ensure_matching_schema_version(state_version, event_version, params_version, expected)
    {
        return Ok(validation_error(
            "SCHEMA_VERSION_MISMATCH",
            "Schema version mismatch",
            details,
        ));
    }

    let state_result = serde_json::from_str::<decision_kernel::StrategyState>(state_json);
    let state = match state_result {
        Ok(value) => value,
        Err(err) => {
            return Ok(validation_error(
                "INVALID_JSON",
                "Failed to parse StrategyState",
                vec![err.to_string()],
            ));
        }
    };

    let event_result = serde_json::from_str::<decision_kernel::MarketEvent>(event_json);
    let event = match event_result {
        Ok(value) => value,
        Err(err) => {
            return Ok(validation_error(
                "INVALID_JSON",
                "Failed to parse MarketEvent",
                vec![err.to_string()],
            ));
        }
    };

    let params_result = serde_json::from_str::<decision_kernel::KernelParams>(params_json);
    let params = match params_result {
        Ok(value) => value,
        Err(err) => {
            return Ok(validation_error(
                "INVALID_JSON",
                "Failed to parse KernelParams",
                vec![err.to_string()],
            ));
        }
    };

    let decision = decision_kernel::step(&state, &event, &params);
    if !decision.diagnostics.errors.is_empty() {
        return Ok(validation_error(
            "KERNEL_DECISION_REJECTED",
            "Kernel diagnostics reported errors",
            decision.diagnostics.errors.clone(),
        ));
    }

    Ok(step_envelope(decision))
}

#[pyfunction]
fn default_kernel_state_json(initial_cash_usd: f64, timestamp_ms: i64) -> PyResult<String> {
    let state = decision_kernel::StrategyState::new(initial_cash_usd, timestamp_ms);
    serde_json::to_string(&state).map_err(|err| {
        pyo3::exceptions::PyRuntimeError::new_err(format!(
            "failed to serialise default state: {err}"
        ))
    })
}

#[pyfunction]
fn default_kernel_params_json() -> PyResult<String> {
    let params = decision_kernel::KernelParams::default();
    serde_json::to_string(&params).map_err(|err| {
        pyo3::exceptions::PyRuntimeError::new_err(format!(
            "failed to serialise default params: {err}"
        ))
    })
}

#[pyfunction]
fn schema_version(payload_json: &str) -> PyResult<u32> {
    as_u32(payload_json, "payload")
}

/// Convenience wrapper that merges `exit_params_json` into `params_json`
/// (setting the `exit_params` field) before calling the regular step logic.
#[pyfunction]
fn step_full(
    state_json: &str,
    event_json: &str,
    params_json: &str,
    exit_params_json: &str,
) -> PyResult<String> {
    let mut params_val: Value = serde_json::from_str(params_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid params JSON: {e}"))
    })?;
    let exit_params_val: Value = serde_json::from_str(exit_params_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid exit_params JSON: {e}"))
    })?;

    params_val
        .as_object_mut()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("params must be a JSON object"))?
        .insert("exit_params".to_string(), exit_params_val);

    let merged_params = serde_json::to_string(&params_val).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to serialise merged params: {e}"))
    })?;

    step_decision(state_json, event_json, &merged_params)
}

/// Construct a Funding `MarketEvent` and run one kernel step, returning the
/// new state JSON.
#[pyfunction]
fn apply_funding(
    state_json: &str,
    symbol: &str,
    rate: f64,
    price: f64,
    params_json: &str,
) -> PyResult<String> {
    let state: decision_kernel::StrategyState = serde_json::from_str(state_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid state JSON: {e}")))?;
    let params: decision_kernel::KernelParams = serde_json::from_str(params_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid params JSON: {e}"))
    })?;

    let event = decision_kernel::MarketEvent {
        schema_version: default_schema_version(),
        event_id: 0,
        timestamp_ms: state.timestamp_ms,
        symbol: symbol.to_string(),
        signal: decision_kernel::MarketSignal::Funding,
        price,
        notional_hint_usd: None,
        close_fraction: None,
        fee_role: None,
        funding_rate: Some(rate),
        indicators: None,
        gate_result: None,
        ema_slow_slope_pct: None,
    };

    let result = decision_kernel::step(&state, &event, &params);
    serde_json::to_string(&result.state).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to serialise state: {e}"))
    })
}

/// Mark-to-market equity: `cash_usd + sum(unrealized PnL)`.
#[pyfunction]
fn get_equity(state_json: &str, prices_json: &str) -> PyResult<f64> {
    let state: decision_kernel::StrategyState = serde_json::from_str(state_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid state JSON: {e}")))?;
    let prices: HashMap<String, f64> = serde_json::from_str(prices_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid prices JSON: {e}"))
    })?;

    let mut equity = state.cash_usd;
    for (symbol, pos) in &state.positions {
        let current_price = prices.get(symbol).copied().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("Missing price for symbol: {symbol}"))
        })?;
        let unrealized_pnl = match pos.side {
            decision_kernel::PositionSide::Long => {
                (current_price - pos.avg_entry_price) * pos.quantity
            }
            decision_kernel::PositionSide::Short => {
                (pos.avg_entry_price - current_price) * pos.quantity
            }
        };
        equity += unrealized_pnl;
    }
    Ok(equity)
}

/// Extract positions map from kernel state as JSON.
///
/// Returns the `positions` field of `StrategyState` as a JSON string
/// (a map of symbol -> Position).  This is the SSOT for position state
/// (AQC-814).
#[pyfunction]
fn get_positions(state_json: &str) -> PyResult<String> {
    let state: decision_kernel::StrategyState = serde_json::from_str(state_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid state JSON: {e}")))?;
    serde_json::to_string(&state.positions).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to serialise positions: {e}"))
    })
}

/// Validate and persist state JSON to a file.
#[pyfunction]
fn save_state(state_json: &str, path: &str) -> PyResult<()> {
    let _: decision_kernel::StrategyState = serde_json::from_str(state_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid state JSON: {e}")))?;
    std::fs::write(path, state_json).map_err(|e| {
        pyo3::exceptions::PyIOError::new_err(format!("Failed to write {path}: {e}"))
    })?;
    Ok(())
}

/// Load and validate state JSON from a file.
#[pyfunction]
fn load_state(path: &str) -> PyResult<String> {
    let json = std::fs::read_to_string(path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Failed to read {path}: {e}")))?;
    let _: decision_kernel::StrategyState = serde_json::from_str(&json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid state JSON at {path}: {e}"))
    })?;
    Ok(json)
}

// ---------------------------------------------------------------------------
// IndicatorSnapshot bridge — compute_indicators
// ---------------------------------------------------------------------------

/// Input candle for JSON deserialization. Field names match the Python
/// convention (`open`, `high`, …) rather than the compact `OhlcvBar` names.
#[derive(Deserialize)]
struct CandleInput {
    t: i64,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    volume: f64,
}

impl CandleInput {
    fn to_bar(&self) -> OhlcvBar {
        OhlcvBar {
            t: self.t,
            t_close: self.t, // not meaningful for indicator computation
            o: self.open,
            h: self.high,
            l: self.low,
            c: self.close,
            v: self.volume,
            n: 0,
        }
    }
}

/// Compute indicators from a JSON array of candles and an optional config,
/// returning the final `IndicatorSnapshot` as a JSON string.
///
/// `candles_json`: `[{"t": <ms>, "open": f64, "high": f64, "low": f64, "close": f64, "volume": f64}, ...]`
/// `config_json`:  JSON matching `IndicatorsConfig` fields, or `"null"`/`"{}"` for defaults.
#[pyfunction]
fn compute_indicators(candles_json: &str, config_json: &str) -> PyResult<String> {
    let candles: Vec<CandleInput> = serde_json::from_str(candles_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid candles JSON: {e}"))
    })?;

    if candles.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "candles array must not be empty",
        ));
    }

    let cfg: IndicatorsConfig = if config_json.trim().is_empty()
        || config_json.trim() == "null"
        || config_json.trim() == "{}"
    {
        IndicatorsConfig::default()
    } else {
        serde_json::from_str(config_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Invalid config JSON: {e}"))
        })?
    };

    let mut bank = IndicatorBank::new(&cfg, true);

    for candle in &candles {
        bank.update(&candle.to_bar());
    }

    let snap = bank.latest_snap();
    serde_json::to_string(&snap).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!(
            "Failed to serialise IndicatorSnapshot: {e}"
        ))
    })
}

#[pymodule]
fn bt_runtime(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(step_decision, m)?)?;
    m.add_function(wrap_pyfunction!(step_full, m)?)?;
    m.add_function(wrap_pyfunction!(apply_funding, m)?)?;
    m.add_function(wrap_pyfunction!(get_equity, m)?)?;
    m.add_function(wrap_pyfunction!(get_positions, m)?)?;
    m.add_function(wrap_pyfunction!(default_kernel_state_json, m)?)?;
    m.add_function(wrap_pyfunction!(default_kernel_params_json, m)?)?;
    m.add_function(wrap_pyfunction!(schema_version, m)?)?;
    m.add_function(wrap_pyfunction!(save_state, m)?)?;
    m.add_function(wrap_pyfunction!(load_state, m)?)?;
    m.add_function(wrap_pyfunction!(compute_indicators, m)?)?;
    Ok(())
}
