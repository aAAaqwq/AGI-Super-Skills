//! Tiny GPU runtime parity fixture.
//!
//! This test runs a single GPU sweep on a fixed fixture and compares the
//! result against committed expected output.
//!
//! Behaviour:
//! - On CUDA-capable machines: the test must pass.
//! - On machines without CUDA runtime/device: the test prints a skip message
//!   and returns without failing.
//! - On CUDA misconfiguration: the test fails loudly.

use std::any::Any;
use std::collections::BTreeMap;
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::sweep::SweepSpec;
use cudarc::driver::sys::CUresult;
use cudarc::driver::{CudaDevice, DriverError};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct FixtureBar {
    t: i64,
    t_close: Option<i64>,
    o: f64,
    h: f64,
    l: f64,
    c: f64,
    v: f64,
    n: i32,
}

#[derive(Debug, Deserialize)]
struct ExpectedGpuSweepResult {
    config_id: String,
    total_pnl: f64,
    final_balance: f64,
    total_trades: u32,
    total_wins: u32,
    win_rate: f64,
    profit_factor: f64,
    max_drawdown_pct: f64,
}

enum CudaProbe {
    Available,
    Unavailable(String),
    Misconfigured(String),
}

fn panic_payload_to_string(payload: Box<dyn Any + Send>) -> String {
    let payload_ref = payload.as_ref();
    if let Some(msg) = payload_ref.downcast_ref::<&str>() {
        return (*msg).to_string();
    }
    if let Some(msg) = payload_ref.downcast_ref::<String>() {
        return msg.clone();
    }
    "unknown panic payload".to_string()
}

fn is_cuda_unavailable_error(err: &DriverError) -> bool {
    matches!(
        err.0,
        CUresult::CUDA_ERROR_NO_DEVICE | CUresult::CUDA_ERROR_INVALID_DEVICE
    )
}

fn probe_cuda_runtime() -> CudaProbe {
    match panic::catch_unwind(AssertUnwindSafe(|| CudaDevice::new(0))) {
        Ok(Ok(_)) => CudaProbe::Available,
        Ok(Err(err)) => {
            if is_cuda_unavailable_error(&err) {
                CudaProbe::Unavailable(format!("{err:?}"))
            } else {
                CudaProbe::Misconfigured(format!("{err:?}"))
            }
        }
        Err(payload) => {
            let msg = panic_payload_to_string(payload);
            if msg.contains("Unable to dynamically load the \"cuda\" shared library") {
                CudaProbe::Unavailable(msg)
            } else {
                CudaProbe::Misconfigured(msg)
            }
        }
    }
}

fn load_candles_fixture(path: &Path) -> CandleData {
    let raw =
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("Failed to read {path:?}: {e}"));
    let parsed: BTreeMap<String, Vec<FixtureBar>> =
        serde_json::from_str(&raw).unwrap_or_else(|e| panic!("Invalid JSON in {path:?}: {e}"));

    let mut out: CandleData = CandleData::default();
    for (sym, bars) in parsed {
        let mut v: Vec<OhlcvBar> = Vec::with_capacity(bars.len());
        for b in bars {
            v.push(OhlcvBar {
                t: b.t,
                t_close: b.t_close.unwrap_or(b.t),
                o: b.o,
                h: b.h,
                l: b.l,
                c: b.c,
                v: b.v,
                n: b.n,
            });
        }
        out.insert(sym, v);
    }
    out
}

fn load_expected(path: &Path) -> ExpectedGpuSweepResult {
    let raw =
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("Failed to read {path:?}: {e}"));
    serde_json::from_str(&raw).unwrap_or_else(|e| panic!("Invalid JSON in {path:?}: {e}"))
}

#[test]
fn gpu_runtime_parity_tiny_fixture_matches_expected() {
    match probe_cuda_runtime() {
        CudaProbe::Available => {}
        CudaProbe::Unavailable(reason) => {
            eprintln!("[gpu-parity] SKIP: CUDA unavailable ({reason})");
            return;
        }
        CudaProbe::Misconfigured(reason) => {
            panic!("CUDA probe failed unexpectedly: {reason}");
        }
    }

    let crate_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let fixture_dir = crate_root.join("../../testdata/gpu_cpu_parity");

    let candles_path = fixture_dir.join("candles_1h.json");
    let expected_path = fixture_dir.join("expected_gpu_sweep.json");
    let cfg_path = fixture_dir.join("strategy.yaml");

    let candles = load_candles_fixture(&candles_path);
    let cfg = bt_core::config::load_config(&cfg_path.to_string_lossy(), None, false);
    let expected = load_expected(&expected_path);

    let initial_balance = 10_000.0;
    let lookback = 200;
    let spec = SweepSpec {
        axes: Vec::new(),
        initial_balance,
        lookback,
    };

    let results = bt_gpu::run_gpu_sweep(&candles, &cfg, &spec, None, None, None, None);
    assert_eq!(
        results.len(),
        1,
        "Tiny parity fixture should produce exactly one GPU sweep result"
    );

    let got = &results[0];

    assert!(
        got.total_trades > 0,
        "Tiny parity fixture produced no GPU trades; check testdata/strategy fixture"
    );
    assert!(
        expected.total_trades > 0,
        "Expected GPU fixture contains no trades; regenerate expected_gpu_sweep.json"
    );
    assert!(
        got.config_id.is_empty() && expected.config_id.is_empty(),
        "Expected empty config_id for empty sweep axis set"
    );

    let got_net_pnl = got.final_balance - initial_balance;
    let expected_net_pnl = expected.final_balance - initial_balance;
    assert!(
        got_net_pnl.signum() == expected_net_pnl.signum(),
        "Net PnL sign mismatch (got={:.2}, expected={:.2})",
        got_net_pnl,
        expected_net_pnl
    );

    let final_balance_rel_err =
        (got.final_balance - expected.final_balance).abs() / initial_balance;
    assert!(
        final_balance_rel_err <= 0.03,
        "Final balance drift too large (got={:.2}, expected={:.2}, rel_err={:.3})",
        got.final_balance,
        expected.final_balance,
        final_balance_rel_err
    );

    let net_pnl_rel_err = (got.total_pnl - expected.total_pnl).abs() / initial_balance;
    assert!(
        net_pnl_rel_err <= 0.03,
        "Total PnL drift too large (got={:.2}, expected={:.2}, rel_err={:.3})",
        got.total_pnl,
        expected.total_pnl,
        net_pnl_rel_err
    );

    let drawdown_delta = (got.max_drawdown_pct - expected.max_drawdown_pct).abs();
    assert!(
        drawdown_delta <= 0.03,
        "Max drawdown drift too large (got={:.3}, expected={:.3}, delta={:.3})",
        got.max_drawdown_pct,
        expected.max_drawdown_pct,
        drawdown_delta
    );

    let win_rate_delta = (got.win_rate - expected.win_rate).abs();
    assert!(
        win_rate_delta <= 0.20,
        "Win-rate drift too large (got={:.4}, expected={:.4}, delta={:.4})",
        got.win_rate,
        expected.win_rate,
        win_rate_delta
    );

    let profit_factor_delta = (got.profit_factor - expected.profit_factor).abs();
    assert!(
        profit_factor_delta <= 3.0,
        "Profit-factor drift too large (got={:.3}, expected={:.3}, delta={:.3})",
        got.profit_factor,
        expected.profit_factor,
        profit_factor_delta
    );

    let trade_ratio = got.total_trades as f64 / expected.total_trades.max(1) as f64;
    assert!(
        (0.25..=4.0).contains(&trade_ratio),
        "Trade count ratio out of bounds (got={}, expected={}, ratio={:.3})",
        got.total_trades,
        expected.total_trades,
        trade_ratio
    );

    let win_ratio = got.total_wins as f64 / expected.total_wins.max(1) as f64;
    assert!(
        (0.25..=4.0).contains(&win_ratio),
        "Win count ratio out of bounds (got={}, expected={}, ratio={:.3})",
        got.total_wins,
        expected.total_wins,
        win_ratio
    );
}
