//! Main vs V8 CPU replay parity test.
//!
//! Loads committed baseline results (from the main branch engine) and replays
//! the same candles through the V8 `engine::run_simulation()`.  Compares key
//! metrics within a configurable tolerance envelope.

use std::path::{Path, PathBuf};

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::{engine, report};
use serde::Deserialize;

// ---------------------------------------------------------------------------
// Fixture types
// ---------------------------------------------------------------------------

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
struct ExpectedBaseline {
    total_pnl: f64,
    total_trades: u32,
    win_rate: f64,
    max_drawdown_pct: f64,
    #[serde(default = "default_initial_balance")]
    initial_balance: f64,
}

fn default_initial_balance() -> f64 {
    10_000.0
}

// ---------------------------------------------------------------------------
// Configurable tolerances
// ---------------------------------------------------------------------------

fn tolerance(env_key: &str, default: f64) -> f64 {
    let multiplier: f64 = std::env::var("AQC_MAIN_V8_PARITY_TOLERANCE")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(1.0);
    let base: f64 = std::env::var(env_key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default);
    base * multiplier
}

// ---------------------------------------------------------------------------
// Diff report
// ---------------------------------------------------------------------------

struct ParityCheck {
    metric: &'static str,
    v8_value: f64,
    main_value: f64,
    delta: f64,
    tolerance: f64,
    passed: bool,
}

fn print_parity_table(checks: &[ParityCheck]) {
    eprintln!();
    eprintln!("┌───────────────────┬────────────┬────────────┬────────────┬────────────┬────────┐");
    eprintln!("│ Metric            │ V8         │ Main       │ Delta      │ Tolerance  │ Status │");
    eprintln!("├───────────────────┼────────────┼────────────┼────────────┼────────────┼────────┤");
    for c in checks {
        let status = if c.passed { "PASS" } else { "FAIL" };
        eprintln!(
            "│ {:<17} │ {:>10.4} │ {:>10.4} │ {:>10.4} │ {:>10.4} │ {:<6} │",
            c.metric, c.v8_value, c.main_value, c.delta, c.tolerance, status
        );
    }
    eprintln!("└───────────────────┴────────────┴────────────┴────────────┴────────────┴────────┘");
    eprintln!();
}

// ---------------------------------------------------------------------------
// Fixture loaders
// ---------------------------------------------------------------------------

fn load_candles_fixture(path: &Path) -> CandleData {
    let raw =
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("Failed to read {path:?}: {e}"));
    let parsed: std::collections::BTreeMap<String, Vec<FixtureBar>> =
        serde_json::from_str(&raw).unwrap_or_else(|e| panic!("Invalid JSON in {path:?}: {e}"));

    let mut out = CandleData::default();
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

fn load_expected(path: &Path) -> ExpectedBaseline {
    let raw =
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("Failed to read {path:?}: {e}"));
    serde_json::from_str(&raw).unwrap_or_else(|e| panic!("Invalid JSON in {path:?}: {e}"))
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

#[test]
fn main_v8_parity_is_within_tolerance() {
    let crate_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let fixture_dir = crate_root.join("../../testdata/main_v8_parity");

    // Graceful skip when fixture files are missing.
    if !fixture_dir.exists() {
        eprintln!("SKIP: main/V8 parity fixture not found at {fixture_dir:?}");
        return;
    }

    let candles_path = fixture_dir.join("candles_1h.json");
    let expected_path = fixture_dir.join("expected_baseline.json");
    let cfg_path = fixture_dir.join("strategy.yaml");

    if !candles_path.exists() || !expected_path.exists() || !cfg_path.exists() {
        eprintln!(
            "SKIP: incomplete fixture directory at {fixture_dir:?} \
             (need candles_1h.json, expected_baseline.json, strategy.yaml)"
        );
        return;
    }

    let candles = load_candles_fixture(&candles_path);
    let cfg = bt_core::config::load_config(&cfg_path.to_string_lossy(), None, false);
    let expected = load_expected(&expected_path);

    let initial_balance = expected.initial_balance;
    let lookback = 200;

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
        config_id: "v8_parity",
        include_trades: false,
        include_equity_curve: false,
    });

    assert!(
        rpt.total_trades > 0,
        "V8 simulation produced no trades; check strategy.yaml or candles fixture"
    );
    assert!(
        expected.total_trades > 0,
        "Expected baseline has no trades; regenerate expected_baseline.json"
    );

    // -------------------------------------------------------------------
    // Tolerances (per spec: trade count ±5%, PnL ±1%, drawdown ±2%, win rate ±5%)
    // -------------------------------------------------------------------

    let tol_pnl = tolerance("AQC_MV8_TOL_PNL", 0.01);
    let tol_dd = tolerance("AQC_MV8_TOL_DD", 0.02);
    let tol_wr = tolerance("AQC_MV8_TOL_WR", 0.05);
    let tol_tc = tolerance("AQC_MV8_TOL_TC", 0.05);

    // PnL relative error normalised by initial balance
    let v8_pnl = rpt.total_pnl;
    let main_pnl = expected.total_pnl;
    let pnl_rel_err = if main_pnl.abs() < 1e-9 {
        v8_pnl.abs() / initial_balance
    } else {
        (v8_pnl - main_pnl).abs() / initial_balance
    };

    let dd_delta = (rpt.max_drawdown_pct - expected.max_drawdown_pct).abs();
    let wr_delta = (rpt.win_rate - expected.win_rate).abs();

    let trade_ratio = rpt.total_trades as f64 / expected.total_trades as f64;
    let trade_ratio_delta = (trade_ratio - 1.0).abs();

    // -------------------------------------------------------------------
    // Build diff report
    // -------------------------------------------------------------------

    let checks = vec![
        ParityCheck {
            metric: "Total PnL (rel)",
            v8_value: v8_pnl,
            main_value: main_pnl,
            delta: pnl_rel_err,
            tolerance: tol_pnl,
            passed: pnl_rel_err <= tol_pnl,
        },
        ParityCheck {
            metric: "Max Drawdown %",
            v8_value: rpt.max_drawdown_pct,
            main_value: expected.max_drawdown_pct,
            delta: dd_delta,
            tolerance: tol_dd,
            passed: dd_delta <= tol_dd,
        },
        ParityCheck {
            metric: "Win Rate",
            v8_value: rpt.win_rate,
            main_value: expected.win_rate,
            delta: wr_delta,
            tolerance: tol_wr,
            passed: wr_delta <= tol_wr,
        },
        ParityCheck {
            metric: "Trade Count (±%)",
            v8_value: rpt.total_trades as f64,
            main_value: expected.total_trades as f64,
            delta: trade_ratio_delta,
            tolerance: tol_tc,
            passed: trade_ratio_delta <= tol_tc,
        },
    ];

    // Always print the table for CI visibility.
    print_parity_table(&checks);

    let failures: Vec<&ParityCheck> = checks.iter().filter(|c| !c.passed).collect();
    assert!(
        failures.is_empty(),
        "Main↔V8 parity failed for {} metric(s): [{}]",
        failures.len(),
        failures
            .iter()
            .map(|c| c.metric)
            .collect::<Vec<_>>()
            .join(", ")
    );
}
