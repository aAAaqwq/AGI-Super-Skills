//! Generate `expected_gpu_sweep.json` for the GPU/CPU parity harness.
//!
//! This binary is a maintainer utility and requires a working CUDA environment.

use std::path::{Path, PathBuf};

use clap::Parser;
use serde::{Deserialize, Serialize};

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::config::StrategyConfig;
use bt_core::sweep::SweepSpec;

#[derive(Parser, Debug)]
struct Args {
    /// Strategy YAML to load.
    #[arg(
        long,
        default_value = "backtester/testdata/gpu_cpu_parity/strategy.yaml"
    )]
    config: String,

    /// Path to the candle fixture JSON.
    #[arg(
        long,
        default_value = "backtester/testdata/gpu_cpu_parity/candles_1h.json"
    )]
    candles_json: PathBuf,

    /// Output path for the expected GPU result JSON.
    #[arg(
        long,
        default_value = "backtester/testdata/gpu_cpu_parity/expected_gpu_sweep.json"
    )]
    out: PathBuf,

    /// Initial balance used for the sweep.
    #[arg(long, default_value_t = 10_000.0)]
    initial_balance: f64,

    /// Lookback bars before trading begins.
    #[arg(long, default_value_t = 200)]
    lookback: usize,
}

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

#[derive(Debug, Serialize)]
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

fn load_cfg(path: &Path) -> StrategyConfig {
    // This is a maintainer utility: load config as-is (no symbol override, no live overlay).
    bt_core::config::load_config(&path.to_string_lossy(), None, false)
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
    let args = Args::parse();

    let root = repo_root();
    let cfg_path = resolve_from_root(&root, Path::new(&args.config));
    let candles_path = resolve_from_root(&root, &args.candles_json);
    let out_path = resolve_from_root(&root, &args.out);

    let cfg = load_cfg(&cfg_path);
    let candles = load_candles_fixture(&candles_path);
    let spec = SweepSpec {
        axes: Vec::new(),
        initial_balance: args.initial_balance,
        lookback: args.lookback,
    };

    let results = bt_gpu::run_gpu_sweep(&candles, &cfg, &spec, None, None, None, None);
    if results.is_empty() {
        eprintln!("[error] GPU sweep returned no results");
        std::process::exit(1);
    }

    // With an empty sweep spec, this should be exactly one combo.
    let r = &results[0];
    let expected = ExpectedGpuSweepResult {
        config_id: r.config_id.clone(),
        total_pnl: r.total_pnl,
        final_balance: r.final_balance,
        total_trades: r.total_trades,
        total_wins: r.total_wins,
        win_rate: r.win_rate,
        profit_factor: r.profit_factor,
        max_drawdown_pct: r.max_drawdown_pct,
    };

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent).unwrap();
    }
    let json = serde_json::to_string_pretty(&expected).unwrap();
    std::fs::write(&out_path, format!("{json}\n")).unwrap();

    eprintln!("[ok] Wrote {}", out_path.display());
}
