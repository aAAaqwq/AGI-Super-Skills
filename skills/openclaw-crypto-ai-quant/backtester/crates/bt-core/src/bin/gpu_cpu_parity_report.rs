//! GPU/CPU parity drift report (maintainer utility).
//!
//! This binary is intended for local developer use when updating the GPU sweep kernel
//! or when regenerating `expected_gpu_sweep.json`.
//!
//! It re-runs the CPU simulation on the fixed fixture candles and prints the drift against
//! the committed expected GPU sweep output (CPU-only, so it can run anywhere).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::{engine, report};
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
    #[allow(dead_code)]
    total_pnl: f64,
    final_balance: f64,
    total_trades: u32,
    total_wins: u32,
    win_rate: f64,
    profit_factor: f64,
    max_drawdown_pct: f64,
}

fn load_candles_fixture(path: &Path) -> CandleData {
    let raw =
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("Failed to read {path:?}: {e}"));
    let parsed: std::collections::BTreeMap<String, Vec<FixtureBar>> =
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

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."))
}

fn resolve_from_root(root: &Path, p: &Path) -> PathBuf {
    if p.is_absolute() {
        p.to_path_buf()
    } else {
        root.join(p)
    }
}

fn main() {
    let root = repo_root();

    let candles_path = resolve_from_root(
        &root,
        &PathBuf::from("backtester/testdata/gpu_cpu_parity/candles_1h.json"),
    );
    let expected_path = resolve_from_root(
        &root,
        &PathBuf::from("backtester/testdata/gpu_cpu_parity/expected_gpu_sweep.json"),
    );
    let cfg_path = resolve_from_root(
        &root,
        &PathBuf::from("backtester/testdata/gpu_cpu_parity/strategy.yaml"),
    );

    let initial_balance = 10_000.0;
    let lookback = 200;

    let candles = load_candles_fixture(&candles_path);
    let cfg = bt_core::config::load_config(&cfg_path.to_string_lossy(), None, false);
    let expected = load_expected(&expected_path);

    let sim = engine::run_simulation(engine::RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance,
        lookback,
        exit_candles: None,
        entry_candles: None,
        funding_rates: None,
        init_state: None,
        from_ts: None,
        to_ts: None,
    });

    let rpt = report::build_report(report::BuildReportInput {
        trades: &sim.trades,
        signals: &sim.signals,
        equity_curve: &sim.equity_curve,
        gate_stats: &sim.gate_stats,
        initial_balance,
        final_balance: sim.final_balance,
        config_id: "cpu_parity_report",
        include_trades: false,
        include_equity_curve: false,
    });

    let cpu_net_pnl = rpt.final_balance - initial_balance;
    let gpu_net_pnl = expected.final_balance - initial_balance;
    let net_pnl_rel_err = (cpu_net_pnl - gpu_net_pnl).abs() / initial_balance;

    let dd_delta = (rpt.max_drawdown_pct - expected.max_drawdown_pct).abs();
    let wr_delta = (rpt.win_rate - expected.win_rate).abs();
    let pf_delta = (rpt.profit_factor - expected.profit_factor).abs();

    let trade_ratio = rpt.total_trades as f64 / expected.total_trades.max(1) as f64;
    let win_ratio = rpt.total_wins as f64 / expected.total_wins.max(1) as f64;

    let cpu_signal_flip_closes = sim
        .trades
        .iter()
        .filter(|t| t.is_close() && t.reason == "Signal Flip")
        .count();

    let mut close_reason_counts: BTreeMap<String, usize> = BTreeMap::new();
    for t in &sim.trades {
        if t.is_close() {
            *close_reason_counts.entry(t.reason.clone()).or_insert(0) += 1;
        }
    }
    let mut close_reason_vec: Vec<(String, usize)> = close_reason_counts.into_iter().collect();
    close_reason_vec.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    println!("gpu_cpu_parity_report");
    println!("  cpu_final_balance={:.2}", rpt.final_balance);
    println!("  gpu_final_balance={:.2}", expected.final_balance);
    println!("  cpu_net_pnl={:.2}", cpu_net_pnl);
    println!("  gpu_net_pnl={:.2}", gpu_net_pnl);
    println!("  net_pnl_rel_err={:.6}", net_pnl_rel_err);
    println!("  cpu_max_dd_pct={:.6}", rpt.max_drawdown_pct);
    println!("  gpu_max_dd_pct={:.6}", expected.max_drawdown_pct);
    println!("  dd_delta={:.6}", dd_delta);
    println!("  wr_delta={:.6}", wr_delta);
    println!("  pf_delta={:.6}", pf_delta);
    println!("  trade_ratio={:.6}", trade_ratio);
    println!("  win_ratio={:.6}", win_ratio);
    println!("  cpu_signal_flip_closes={}", cpu_signal_flip_closes);
    println!("  cpu_close_reasons_top:");
    for (reason, count) in close_reason_vec.into_iter().take(10) {
        println!("    {}: {}", reason, count);
    }
}
