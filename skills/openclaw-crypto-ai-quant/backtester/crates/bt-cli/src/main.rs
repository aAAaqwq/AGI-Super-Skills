//! CLI entry point for the mei-backtester Rust backtesting simulator.
//!
//! Subcommands:
//!   - `replay`          — Run a single backtest against historical candles
//!   - `sweep`           — Parallel parameter sweep (Cartesian product of axes)
//!   - `dump-indicators` — Dump raw indicator values as CSV for debugging

use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Instant;

use chrono::{DateTime, NaiveDate, SecondsFormat, Utc};
use clap::{Parser, Subcommand, ValueEnum};

const VERSION: &str = concat!(
    env!("CARGO_PKG_VERSION"),
    " git:",
    env!("AIQ_GIT_SHA"),
    " build:",
    env!("AIQ_BUILD_UNIX"),
    " gpu:",
    env!("AIQ_GPU")
);
const DEFAULT_LOOKBACK: usize = 200;

#[derive(Clone, Copy, Debug)]
struct TimestampMs(i64);

impl std::str::FromStr for TimestampMs {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        parse_timestamp_ms(s).map(Self)
    }
}

fn format_ts_ms(ms: i64) -> String {
    match DateTime::<Utc>::from_timestamp_millis(ms) {
        Some(dt) => format!("{ms} ({})", dt.to_rfc3339_opts(SecondsFormat::Millis, true)),
        None => ms.to_string(),
    }
}

fn format_ts_opt(ms: Option<i64>) -> String {
    match ms {
        Some(x) => format_ts_ms(x),
        None => "unbounded".to_string(),
    }
}

fn parse_timestamp_ms(input: &str) -> Result<i64, String> {
    let s = input.trim();
    if s.is_empty() {
        return Err("timestamp is empty".to_string());
    }

    // Epoch parsing: accept seconds (10 digits), milliseconds (13 digits),
    // and also tolerate micros/nanos by magnitude.
    let s_no_underscores: String = s.chars().filter(|c| *c != '_').collect();
    let is_epoch = {
        let signless = s_no_underscores
            .strip_prefix('+')
            .or_else(|| s_no_underscores.strip_prefix('-'))
            .unwrap_or(&s_no_underscores);
        !signless.is_empty() && signless.chars().all(|c| c.is_ascii_digit())
    };
    if is_epoch {
        let n: i64 = s_no_underscores
            .parse()
            .map_err(|e| format!("invalid epoch timestamp {input:?}: {e}"))?;

        let abs: i128 = (n as i128).abs();
        if abs < 10_000_000_000_i128 {
            return n.checked_mul(1000).ok_or_else(|| {
                "epoch seconds overflow when converting to milliseconds".to_string()
            });
        }
        if abs < 10_000_000_000_000_i128 {
            return Ok(n);
        }
        if abs < 10_000_000_000_000_000_i128 {
            return Ok(n / 1000);
        }
        return Ok(n / 1_000_000);
    }

    // ISO8601 parsing: prefer RFC3339 with timezone, but also accept date-only (UTC midnight).
    if let Ok(dt) = DateTime::parse_from_rfc3339(s) {
        return Ok(dt.with_timezone(&Utc).timestamp_millis());
    }
    if let Ok(date) = NaiveDate::parse_from_str(s, "%Y-%m-%d") {
        let naive = date
            .and_hms_opt(0, 0, 0)
            .ok_or_else(|| format!("invalid date {input:?}"))?;
        let dt = DateTime::<Utc>::from_naive_utc_and_offset(naive, Utc);
        return Ok(dt.timestamp_millis());
    }

    Err(format!(
        "invalid timestamp {input:?}. Expected ISO8601/RFC3339 (e.g. 2024-01-01T00:00:00Z) or epoch seconds/milliseconds"
    ))
}

/// Read only the `balance` field from an export_state.py JSON file.
fn read_balance_from_json(path: &str) -> Result<f64, Box<dyn std::error::Error>> {
    let data = std::fs::read_to_string(path).map_err(|e| format!("Cannot read {:?}: {}", path, e))?;
    let json: serde_json::Value =
        serde_json::from_str(&data).map_err(|e| format!("Invalid JSON in {:?}: {}", path, e))?;
    let balance = json
        .get("balance")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| format!("{:?} has no numeric \"balance\" field", path))?;
    eprintln!(
        "[balance-from] Read balance=${:.2} from {:?}",
        balance, path
    );
    Ok(balance)
}

// ---------------------------------------------------------------------------
// CLI argument structs
// ---------------------------------------------------------------------------

#[derive(Parser)]
#[command(
    name = "mei-backtester",
    version = VERSION,
    about = "High-performance backtesting simulator for the Mei Alpha strategy",
    propagate_version = true,
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run a single backtest
    Replay(ReplayArgs),
    /// Run a parallel parameter sweep
    Sweep(SweepArgs),
    /// Dump indicator values for debugging/validation
    DumpIndicators(DumpArgs),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum SweepParityMode {
    /// Default production behaviour. GPU may truncate symbols to the kernel limit.
    Production,
    /// Enforce an identical pre-scored symbol universe for CPU and GPU lane comparisons.
    IdenticalSymbolUniverse,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum SweepOutputMode {
    /// Full row format (legacy): report style fields and all diagnostics.
    Full,
    /// Candidate-oriented compact format with stable fields for downstream tooling.
    Candidate,
}

impl SweepOutputMode {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Full => "full",
            Self::Candidate => "candidate",
        }
    }

    fn is_candidate(&self) -> bool {
        matches!(self, Self::Candidate)
    }
}

#[derive(Parser)]
struct ReplayArgs {
    /// Path to the strategy YAML config
    #[arg(long, default_value = "config/strategy_overrides.yaml")]
    config: String,

    /// Path to the SQLite candle database.
    /// If omitted, auto-resolved from --interval: candles_dbs/candles_{interval}.db
    #[arg(long)]
    candles_db: Option<String>,

    /// Candle interval for indicator computation and entry signals (e.g. "1h", "15m", "5m").
    /// If omitted, reads from YAML engine.interval (default "1h").
    /// The DB path is auto-resolved to candles_dbs/candles_{interval}.db unless --candles-db is set.
    #[arg(long)]
    interval: Option<String>,

    /// Starting account balance in USD
    #[arg(long, default_value_t = 10_000.0)]
    initial_balance: f64,

    /// Indicator warmup bars before trading begins
    #[arg(long, default_value_t = DEFAULT_LOOKBACK)]
    lookback: usize,

    /// Write JSON report to this file instead of stdout
    #[arg(long)]
    output: Option<PathBuf>,

    /// Export trade rows as CSV for analysis (deterministic ordering, includes trade_id).
    ///
    /// The export is one row per exit event (CLOSE_* / REDUCE_*), with entry fields repeated.
    #[arg(long)]
    export_trades: Option<PathBuf>,

    /// Only backtest this single symbol (otherwise all symbols in DB)
    #[arg(long)]
    symbol: Option<String>,

    /// Include the full trade log in the JSON output
    #[arg(long, default_value_t = false)]
    trades: bool,

    /// Include the equity curve in the JSON output
    #[arg(long, default_value_t = false)]
    equity_curve: bool,

    /// Apply the `live` config overlay on top of global + per-symbol
    #[arg(long, default_value_t = false)]
    live: bool,

    /// Path to a secondary SQLite candle database for higher-resolution exit checks.
    /// If omitted but --exit-interval is set, auto-resolved to candles_dbs/candles_{exit_interval}.db.
    /// When active, exit conditions are evaluated on these sub-bars within each indicator bar,
    /// aligning backtest exits with live behavior.
    #[arg(long)]
    exit_candles_db: Option<String>,

    /// Candle interval for exit checks (e.g. "1m", "3m", "5m").
    /// If omitted, reads from YAML engine.exit_interval. Empty string = disabled.
    /// Must be a shorter interval than --interval for meaningful sub-bar precision.
    #[arg(long)]
    exit_interval: Option<String>,

    /// Path to a funding rate SQLite database. When provided, funding payments
    /// are applied at hourly boundaries for open positions.
    #[arg(long)]
    funding_db: Option<String>,

    /// Path to a secondary SQLite candle database for higher-resolution entry checks.
    /// If omitted but --entry-interval is set, auto-resolved to candles_dbs/candles_{entry_interval}.db.
    #[arg(long)]
    entry_candles_db: Option<String>,

    /// Candle interval for entry checks (e.g. "15m", "5m").
    /// If omitted, reads from YAML engine.entry_interval. Empty string = disabled.
    /// Entry signals are evaluated at this resolution using indicator-bar indicators + sub-bar price.
    #[arg(long)]
    entry_interval: Option<String>,

    /// Start timestamp (inclusive). Accepts ISO8601/RFC3339 or epoch seconds/milliseconds.
    /// Alias: --from-ts
    #[arg(long = "start-ts", alias = "from-ts")]
    start_ts: Option<TimestampMs>,

    /// End timestamp (inclusive). Accepts ISO8601/RFC3339 or epoch seconds/milliseconds.
    /// Alias: --to-ts
    #[arg(long = "end-ts", alias = "to-ts")]
    end_ts: Option<TimestampMs>,

    /// Filter the candle universe to symbols active during the backtest window using
    /// `universe_listings` from a universe history DB (see tools/sync_universe_history.py).
    ///
    /// A symbol is considered active when its observed listing interval overlaps with
    /// the backtest window:
    ///   first_seen_ms <= to_ts AND last_seen_ms >= from_ts
    #[arg(long, default_value_t = false)]
    universe_filter: bool,

    /// Path to the universe history SQLite DB.
    /// If omitted, auto-resolved as: <candles_db_dir>/universe_history.db
    #[arg(long)]
    universe_db: Option<String>,

    /// Override slippage in basis points for this replay run.
    ///
    /// This avoids editing YAML when running slippage stress tests.
    #[arg(long)]
    slippage_bps: Option<f64>,

    /// Disable auto-scoping. By default, replay auto-scopes all candle DBs to the
    /// shortest overlapping time range for apple-to-apple comparison.
    /// Use --no-auto-scope to disable this and rely on explicit --start-ts / --end-ts.
    #[arg(long, default_value_t = false)]
    no_auto_scope: bool,

    /// Path to a JSON file exported by export_state.py. When provided, the simulation
    /// starts with the exported balance and open positions instead of a blank slate.
    /// Overrides --initial-balance.
    #[arg(long)]
    init_state: Option<String>,

    /// Read initial balance from an export_state.py JSON file (ignores positions).
    /// Overrides --initial-balance.
    #[arg(long)]
    balance_from: Option<String>,
}

#[derive(Parser)]
struct SweepArgs {
    /// Path to the strategy YAML config (base config for sweep)
    #[arg(long, default_value = "config/strategy_overrides.yaml")]
    config: String,

    /// Path to the SQLite candle database.
    /// If omitted, auto-resolved from --interval: candles_dbs/candles_{interval}.db
    #[arg(long)]
    candles_db: Option<String>,

    /// Candle interval (e.g. "1h", "15m"). If omitted, reads from YAML engine.interval.
    #[arg(long)]
    interval: Option<String>,

    /// Path to the YAML file defining sweep axes
    #[arg(long)]
    sweep_spec: String,

    /// Output file for JSONL results (one JSON object per line per combo)
    #[arg(long, default_value = "sweep_results.jsonl")]
    output: PathBuf,

    /// Sweep output format.
    ///
    /// `full` writes compatibility rows used by existing replay/reporting pipelines.
    /// `candidate` writes a compact candidate row for sweep-gate handoffs.
    #[arg(long, default_value_t = SweepOutputMode::Full, value_enum)]
    output_mode: SweepOutputMode,

    /// Starting account balance in USD
    #[arg(long, default_value_t = 10_000.0)]
    initial_balance: f64,

    /// Override rayon's thread count (defaults to num CPUs)
    #[arg(long)]
    threads: Option<usize>,

    /// Only print the top N results sorted by total PnL
    #[arg(long)]
    top_n: Option<usize>,

    /// Apply the `live` config overlay on top of global
    #[arg(long, default_value_t = false)]
    live: bool,

    /// Path to exit candle DB. Auto-resolved from --exit-interval if omitted.
    #[arg(long)]
    exit_candles_db: Option<String>,

    /// Exit check interval (e.g. "1m", "5m"). If omitted, reads from YAML engine.exit_interval.
    #[arg(long)]
    exit_interval: Option<String>,

    /// Path to entry candle DB. Auto-resolved from --entry-interval if omitted.
    #[arg(long)]
    entry_candles_db: Option<String>,

    /// Entry check interval (e.g. "15m", "5m"). If omitted, reads from YAML engine.entry_interval.
    #[arg(long)]
    entry_interval: Option<String>,

    /// Path to funding rate SQLite database.
    #[arg(long)]
    funding_db: Option<String>,

    /// Start timestamp (inclusive). Accepts ISO8601/RFC3339 or epoch seconds/milliseconds.
    /// Alias: --from-ts
    #[arg(long = "start-ts", alias = "from-ts")]
    start_ts: Option<TimestampMs>,

    /// End timestamp (inclusive). Accepts ISO8601/RFC3339 or epoch seconds/milliseconds.
    /// Alias: --to-ts
    #[arg(long = "end-ts", alias = "to-ts")]
    end_ts: Option<TimestampMs>,

    /// Filter the candle universe to symbols active during the sweep window using
    /// `universe_listings` from a universe history DB (see tools/sync_universe_history.py).
    ///
    /// A symbol is considered active when its observed listing interval overlaps with
    /// the sweep window:
    ///   first_seen_ms <= to_ts AND last_seen_ms >= from_ts
    #[arg(long, default_value_t = false)]
    universe_filter: bool,

    /// Path to the universe history SQLite DB.
    /// If omitted, auto-resolved as: <candles_db_dir>/universe_history.db
    #[arg(long)]
    universe_db: Option<String>,

    /// Disable auto-scoping. By default, sweep auto-scopes all candle DBs to the
    /// shortest overlapping time range for apple-to-apple comparison.
    /// Use --no-auto-scope to disable this and rely on explicit --start-ts / --end-ts.
    #[arg(long, default_value_t = false)]
    no_auto_scope: bool,

    /// Read initial balance from an export_state.py JSON file (ignores positions).
    /// Overrides --initial-balance.
    #[arg(long)]
    balance_from: Option<String>,

    /// Symbol-universe parity mode for smoke comparisons.
    ///
    /// - `production`: default runtime behaviour (GPU may truncate to kernel symbol cap).
    /// - `identical-symbol-universe`: pre-truncate symbols before sweep scoring so CPU/GPU
    ///   evaluate the exact same universe (lane A parity mode).
    #[arg(long, value_enum, default_value_t = SweepParityMode::Production)]
    parity_mode: SweepParityMode,

    /// Use GPU-accelerated sweep (requires building with `--features gpu`)
    #[arg(long, default_value_t = false)]
    gpu: bool,

    /// Use TPE (Bayesian optimization) instead of grid search.
    /// Requires --gpu. Samples intelligently from the parameter ranges.
    #[arg(long, default_value_t = false)]
    tpe: bool,

    /// Number of TPE trials to evaluate (default: 5000)
    #[arg(long, default_value_t = 5000)]
    tpe_trials: usize,

    /// Number of trials per GPU batch for TPE (default: 256)
    #[arg(long, default_value_t = 256)]
    tpe_batch: usize,

    /// RNG seed for TPE reproducibility (default: 42)
    #[arg(long, default_value_t = 42)]
    tpe_seed: u64,

    /// Max results kept in memory during TPE sweep (0 = unlimited). Default 50000.
    #[arg(long, default_value_t = 50_000)]
    sweep_top_k: usize,

    /// Override GPU sweep guardrails (unsafe).
    ///
    /// By default, GPU sweeps are restricted to "safe" interval combos
    /// (30m/5m, 1h/5m, 30m/3m, 1h/3m).
    #[arg(long, default_value_t = false)]
    allow_unsafe_gpu_sweep: bool,

    /// Verify that each sweep override path actually takes effect on the config.
    /// Logs warnings for any failed overrides.
    #[arg(long, default_value_t = false)]
    verify_overrides: bool,

    /// Abort the sweep if any override path is not found or fails to apply.
    /// Implies --verify-overrides.
    #[arg(long, default_value_t = false)]
    strict_overrides: bool,
}

#[derive(Parser)]
struct DumpArgs {
    /// Path to the strategy YAML config
    #[arg(long, default_value = "config/strategy_overrides.yaml")]
    config: String,

    /// Path to the SQLite candle database.
    /// If omitted, auto-resolved from --interval: candles_dbs/candles_{interval}.db
    #[arg(long)]
    candles_db: Option<String>,

    /// Candle interval (e.g. "1h", "15m"). If omitted, reads from YAML engine.interval.
    #[arg(long)]
    interval: Option<String>,

    /// Symbol to dump indicators for
    #[arg(long)]
    symbol: String,

    /// Write CSV to this file instead of stdout
    #[arg(long)]
    output: Option<PathBuf>,
}

// ---------------------------------------------------------------------------
// Candle DB sets: support partitions via comma-separated paths and/or directories
// ---------------------------------------------------------------------------

fn expand_db_path(raw: &str) -> Vec<String> {
    let p = Path::new(raw);
    if !p.is_dir() {
        return vec![raw.to_string()];
    }

    let mut out: Vec<String> = Vec::new();
    let entries = match fs::read_dir(p) {
        Ok(v) => v,
        Err(_) => return Vec::new(),
    };
    for ent in entries.flatten() {
        let path = ent.path();
        if path
            .extension()
            .and_then(|s| s.to_str())
            .map(|s| s.eq_ignore_ascii_case("db"))
            != Some(true)
        {
            continue;
        }
        // Only include files named candles_*.db — skip funding_rates.db,
        // bbo_snapshots.db, and other non-candle DBs that happen to live
        // in the same directory.
        let fname = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
        if !fname.starts_with("candles_") {
            continue;
        }
        out.push(path.to_string_lossy().to_string());
    }
    out.sort();
    out
}

fn resolve_db_paths(raw: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();

    for part in raw.split(',') {
        let s = part.trim();
        if s.is_empty() {
            continue;
        }
        let expanded = expand_db_path(s);
        if expanded.is_empty() {
            // If the user passed an empty directory, keep the original value so we fail loudly later.
            if seen.insert(s.to_string()) {
                out.push(s.to_string());
            }
            continue;
        }
        for p in expanded {
            if seen.insert(p.clone()) {
                out.push(p);
            }
        }
    }

    out
}

fn format_db_set(paths: &[String]) -> String {
    if paths.len() <= 1 {
        return paths
            .first()
            .cloned()
            .unwrap_or_else(|| "<empty>".to_string());
    }
    format!("{} (+{} partitions)", paths[0], paths.len() - 1)
}

// ---------------------------------------------------------------------------
// Auto-scope: detect the shortest overlapping time range across all candle DBs
// ---------------------------------------------------------------------------

/// Given a list of (db_paths, interval) pairs, query each for its time range
/// and return the narrowest overlap: (max of all min_t, min of all max_t).
fn query_candle_db_range_multi_or_exit(db_paths: &[String], interval: &str) -> (i64, i64) {
    match bt_data::sqlite_loader::query_time_range_multi(db_paths, interval) {
        Ok(Some((min_t, max_t))) => (min_t, max_t),
        Ok(None) => {
            eprintln!(
                "[error] Candle DB set {:?} has no candles for interval={:?}",
                format_db_set(db_paths),
                interval,
            );
            std::process::exit(1);
        }
        Err(e) => {
            eprintln!(
                "[error] Failed to query candle DB range for {:?} (interval={:?}): {}",
                format_db_set(db_paths),
                interval,
                e
            );
            std::process::exit(1);
        }
    }
}

fn compute_auto_scope_overlap(dbs: &[(&[String], &str)]) -> (i64, i64) {
    if dbs.is_empty() {
        eprintln!("[error] Internal error: auto-scope DB list is empty");
        std::process::exit(1);
    }

    let mut overlap_from: i64 = i64::MIN;
    let mut overlap_to: i64 = i64::MAX;

    for (db_paths, interval) in dbs {
        let (min_t, max_t) = query_candle_db_range_multi_or_exit(db_paths, interval);
        eprintln!(
            "[auto-scope] {} ({}): {}..{} ({:.1} days)",
            format_db_set(db_paths),
            interval,
            min_t,
            max_t,
            (max_t - min_t) as f64 / 86_400_000.0,
        );
        overlap_from = overlap_from.max(min_t);
        overlap_to = overlap_to.min(max_t);
    }

    if overlap_from > overlap_to {
        eprintln!(
            "[error] No overlapping time range across the selected candle DBs (overlap would be {}..{})",
            overlap_from, overlap_to
        );
        std::process::exit(1);
    }

    eprintln!(
        "[auto-scope] Common range: {}..{} ({:.1} days)",
        overlap_from,
        overlap_to,
        (overlap_to - overlap_from) as f64 / 86_400_000.0,
    );

    (overlap_from, overlap_to)
}

fn resolve_time_range_or_exit(
    label: &str,
    dbs: &[(&[String], &str)],
    auto_scope: bool,
    requested_start: Option<i64>,
    requested_end: Option<i64>,
) -> (Option<i64>, Option<i64>) {
    if let (Some(s), Some(e)) = (requested_start, requested_end) {
        if s > e {
            eprintln!(
                "[error] Invalid time range: --start-ts is after --end-ts (start={}, end={})",
                format_ts_ms(s),
                format_ts_ms(e),
            );
            std::process::exit(1);
        }
    }

    if auto_scope {
        let (scope_from, scope_to) = compute_auto_scope_overlap(dbs);

        if let Some(s) = requested_start {
            if s < scope_from {
                eprintln!(
                    "[error] Requested --start-ts {} is earlier than DB coverage (common start is {})",
                    format_ts_ms(s),
                    format_ts_ms(scope_from),
                );
                std::process::exit(1);
            }
            if s > scope_to {
                eprintln!(
                    "[error] Requested --start-ts {} is later than DB coverage (common end is {})",
                    format_ts_ms(s),
                    format_ts_ms(scope_to),
                );
                std::process::exit(1);
            }
        }
        if let Some(e) = requested_end {
            if e < scope_from {
                eprintln!(
                    "[error] Requested --end-ts {} is earlier than DB coverage (common start is {})",
                    format_ts_ms(e),
                    format_ts_ms(scope_from),
                );
                std::process::exit(1);
            }
            if e > scope_to {
                eprintln!(
                    "[error] Requested --end-ts {} is later than DB coverage (common end is {})",
                    format_ts_ms(e),
                    format_ts_ms(scope_to),
                );
                std::process::exit(1);
            }
        }

        let effective_from = requested_start.unwrap_or(scope_from);
        let effective_to = requested_end.unwrap_or(scope_to);
        if effective_from > effective_to {
            eprintln!(
                "[error] Invalid effective time range: start={} end={}",
                format_ts_ms(effective_from),
                format_ts_ms(effective_to),
            );
            std::process::exit(1);
        }
        eprintln!(
            "[{label}] Effective time range: {}..{}",
            format_ts_ms(effective_from),
            format_ts_ms(effective_to),
        );
        return (Some(effective_from), Some(effective_to));
    }

    // No auto-scope: validate requested bounds against each DB's min/max if a bound was provided.
    if requested_start.is_some() || requested_end.is_some() {
        for (db_paths, interval) in dbs {
            let (min_t, max_t) = query_candle_db_range_multi_or_exit(db_paths, interval);
            if let Some(s) = requested_start {
                if s < min_t {
                    eprintln!(
                        "[error] Requested --start-ts {} is earlier than DB coverage start {} for {} ({})",
                        format_ts_ms(s),
                        format_ts_ms(min_t),
                        format_db_set(db_paths),
                        interval,
                    );
                    std::process::exit(1);
                }
                if s > max_t {
                    eprintln!(
                        "[error] Requested --start-ts {} is later than DB coverage end {} for {} ({})",
                        format_ts_ms(s),
                        format_ts_ms(max_t),
                        format_db_set(db_paths),
                        interval,
                    );
                    std::process::exit(1);
                }
            }
            if let Some(e) = requested_end {
                if e < min_t {
                    eprintln!(
                        "[error] Requested --end-ts {} is earlier than DB coverage start {} for {} ({})",
                        format_ts_ms(e),
                        format_ts_ms(min_t),
                        format_db_set(db_paths),
                        interval,
                    );
                    std::process::exit(1);
                }
                if e > max_t {
                    eprintln!(
                        "[error] Requested --end-ts {} is later than DB coverage end {} for {} ({})",
                        format_ts_ms(e),
                        format_ts_ms(max_t),
                        format_db_set(db_paths),
                        interval,
                    );
                    std::process::exit(1);
                }
            }
        }
    }

    eprintln!(
        "[{label}] Effective time range: start={}, end={}",
        format_ts_opt(requested_start),
        format_ts_opt(requested_end),
    );
    (requested_start, requested_end)
}

// ---------------------------------------------------------------------------
// Universe filtering helpers (survivorship bias mitigation)
// ---------------------------------------------------------------------------

fn default_universe_db_path(candles_db: &str) -> String {
    let p = Path::new(candles_db);
    let dir = p.parent().unwrap_or_else(|| Path::new("."));
    dir.join("universe_history.db")
        .to_string_lossy()
        .to_string()
}

fn infer_candle_range_ms(candles: &bt_core::candle::CandleData) -> Option<(i64, i64)> {
    let mut min_t: Option<i64> = None;
    let mut max_t: Option<i64> = None;
    for bars in candles.values() {
        if let Some(first) = bars.first() {
            min_t = Some(min_t.map_or(first.t, |m| m.min(first.t)));
        }
        if let Some(last) = bars.last() {
            max_t = Some(max_t.map_or(last.t, |m| m.max(last.t)));
        }
    }
    min_t.zip(max_t)
}

const GPU_KERNEL_SYMBOL_CAP: usize = 52;

fn apply_alphabetical_symbol_cap(
    candles: &mut bt_core::candle::CandleData,
    cap: usize,
) -> Option<(usize, usize)> {
    if cap == 0 {
        let before = candles.len();
        candles.clear();
        return Some((before, 0));
    }

    let before = candles.len();
    if before <= cap {
        return None;
    }

    let mut symbols: Vec<String> = candles.keys().cloned().collect();
    symbols.sort();
    let keep: HashSet<String> = symbols.into_iter().take(cap).collect();
    candles.retain(|sym, _| keep.contains(sym));
    Some((before, candles.len()))
}

// ---------------------------------------------------------------------------
// Replay JSON extensions
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, serde::Serialize)]
struct PerSymbolStats {
    /// Number of close/reduce events (same definition as report.total_trades, but per symbol).
    trades: u32,
    wins: u32,
    losses: u32,
    win_rate: f64,

    /// Sum of realised PnL from close/reduce events (fees excluded; matches report.by_symbol pnl logic).
    realised_pnl_usd: f64,

    /// Sum of funding PnL events for this symbol (from TradeRecord action=FUNDING).
    funding_pnl_usd: f64,

    /// Sum of all fees charged for this symbol (opens/adds/closes).
    fees_usd: f64,

    /// Net PnL estimate: realised_pnl_usd + funding_pnl_usd - fees_usd.
    ///
    /// Note: realised PnL already reflects the simulator's fill price slippage; do not subtract
    /// estimated_slippage_usd from this again.
    net_pnl_usd: f64,

    /// Max drawdown of cumulative net PnL contributions for this symbol (pnl - fee) over time.
    max_drawdown_usd: f64,

    /// Estimated execution slippage paid in USD (diagnostic; approximate).
    estimated_slippage_usd: f64,

    /// Total number of trade log records for this symbol (including opens/adds/funding).
    fills: u32,
    funding_events: u32,
}

#[derive(Default)]
struct PerSymbolAcc {
    trades: u32,
    wins: u32,
    losses: u32,
    realised_pnl_usd: f64,
    funding_pnl_usd: f64,
    fees_usd: f64,
    estimated_slippage_usd: f64,
    fills: u32,
    funding_events: u32,
    deltas: Vec<(i64, f64)>,
}

fn compute_max_drawdown_from_deltas(deltas: &[(i64, f64)]) -> f64 {
    let mut cumulative = 0.0_f64;
    let mut peak = 0.0_f64;
    let mut max_dd = 0.0_f64;

    for &(_ts, delta) in deltas {
        cumulative += delta;
        if cumulative > peak {
            peak = cumulative;
        }
        let dd = peak - cumulative;
        if dd > max_dd {
            max_dd = dd;
        }
    }

    max_dd
}

fn estimate_slippage_usd(tr: &bt_core::position::TradeRecord, entry_slippage_bps: f64) -> f64 {
    if tr.action == "FUNDING" {
        return 0.0;
    }

    // The engine currently applies configured slippage to entries/adds, and a fixed half-bps
    // to exits (see bt-core engine apply_exit). Keep this estimate consistent with that behaviour.
    let bps = if tr.is_close() {
        0.5
    } else {
        entry_slippage_bps
    };
    if bps <= 0.0 {
        return 0.0;
    }

    tr.notional * (bps / 10_000.0)
}

fn build_per_symbol_stats(
    trades: &[bt_core::position::TradeRecord],
    slippage_bps: f64,
) -> BTreeMap<String, PerSymbolStats> {
    let slippage_bps = slippage_bps.max(0.0);

    let mut acc: BTreeMap<String, PerSymbolAcc> = BTreeMap::new();

    for tr in trades {
        let a = acc.entry(tr.symbol.clone()).or_default();
        a.fills += 1;
        a.fees_usd += tr.fee_usd;
        a.estimated_slippage_usd += estimate_slippage_usd(tr, slippage_bps);
        a.deltas.push((tr.timestamp_ms, tr.pnl - tr.fee_usd));

        if tr.action == "FUNDING" {
            a.funding_events += 1;
            a.funding_pnl_usd += tr.pnl;
            continue;
        }

        if tr.is_close() {
            a.trades += 1;
            a.realised_pnl_usd += tr.pnl;
            if tr.pnl > 0.0 {
                a.wins += 1;
            } else if tr.pnl < 0.0 {
                a.losses += 1;
            }
        }
    }

    acc.into_iter()
        .map(|(symbol, a)| {
            let win_rate = if a.trades > 0 {
                a.wins as f64 / a.trades as f64
            } else {
                0.0
            };

            let net_pnl_usd = a.realised_pnl_usd + a.funding_pnl_usd - a.fees_usd;
            let max_drawdown_usd = compute_max_drawdown_from_deltas(&a.deltas);

            (
                symbol,
                PerSymbolStats {
                    trades: a.trades,
                    wins: a.wins,
                    losses: a.losses,
                    win_rate,
                    realised_pnl_usd: a.realised_pnl_usd,
                    funding_pnl_usd: a.funding_pnl_usd,
                    fees_usd: a.fees_usd,
                    net_pnl_usd,
                    max_drawdown_usd,
                    estimated_slippage_usd: a.estimated_slippage_usd,
                    fills: a.fills,
                    funding_events: a.funding_events,
                },
            )
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Trade export (CSV)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
struct TradeExportRow {
    trade_id: String,
    position_id: u64,
    entry_ts_ms: i64,
    exit_ts_ms: i64,
    symbol: String,
    side: String,
    entry_price: f64,
    exit_price: f64,
    exit_size: f64,
    pnl_usd: f64,
    fee_usd: f64,
    mae_pct: f64,
    mfe_pct: f64,
    reason_code: String,
    reason: String,
}

#[derive(Debug, Clone, Copy)]
enum Side {
    Long,
    Short,
}

#[derive(Debug, Clone)]
struct ActiveTrade {
    position_id: u64,
    entry_ts_ms: i64,
    entry_price: f64,
    side: Side,
    max_high: f64,
    min_low: f64,
    exit_seq: u32,
    open_count_for_symbol: u32,
}

fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') || s.contains('\r') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

fn reason_code_string(code: bt_core::reason_codes::ReasonCode) -> String {
    // ReasonCode serialises to a snake_case string; reuse that canonical representation.
    serde_json::to_string(&code)
        .unwrap_or_else(|_| "\"unknown\"".to_string())
        .trim_matches('"')
        .to_string()
}

fn update_extremes(active: &mut ActiveTrade, bar: &bt_core::candle::OhlcvBar) {
    if bar.h > active.max_high {
        active.max_high = bar.h;
    }
    if bar.l < active.min_low {
        active.min_low = bar.l;
    }
}

fn build_trade_export_rows(
    candles: &bt_core::candle::CandleData,
    trades: &[bt_core::position::TradeRecord],
    init_positions: Option<&[bt_core::position::Position]>,
) -> Vec<TradeExportRow> {
    // Assign a stable position_id per synthetic-init OPEN and per OPEN event in trade-log order.
    let mut next_position_id: u64 = 1;
    let mut open_counts: BTreeMap<String, u32> = BTreeMap::new();
    let mut position_ids: BTreeMap<(String, u32), u64> = BTreeMap::new();
    let mut init_position_by_symbol: BTreeMap<String, bt_core::position::Position> =
        BTreeMap::new();

    if let Some(init_positions) = init_positions {
        let mut sorted_init: Vec<&bt_core::position::Position> = init_positions.iter().collect();
        sorted_init.sort_by(|a, b| a.symbol.cmp(&b.symbol));
        for pos in sorted_init {
            if pos.size <= 0.0 {
                continue;
            }
            let c = open_counts.entry(pos.symbol.clone()).or_insert(0);
            *c += 1;
            position_ids.insert((pos.symbol.clone(), *c), next_position_id);
            init_position_by_symbol.insert(pos.symbol.clone(), pos.clone());
            next_position_id += 1;
        }
    }

    let mut open_seq_by_trade_index: Vec<Option<u32>> = vec![None; trades.len()];
    for (idx, tr) in trades.iter().enumerate() {
        if tr.action.starts_with("OPEN_") {
            let c = open_counts.entry(tr.symbol.clone()).or_insert(0);
            *c += 1;
            open_seq_by_trade_index[idx] = Some(*c);
            position_ids.insert((tr.symbol.clone(), *c), next_position_id);
            next_position_id += 1;
        }
    }

    // Collect relevant events per symbol with stable ordering.
    let mut per_symbol: BTreeMap<String, Vec<(i64, usize)>> = BTreeMap::new();
    for (idx, tr) in trades.iter().enumerate() {
        let action = tr.action.as_str();
        if action.starts_with("OPEN_")
            || action.starts_with("ADD_")
            || action.starts_with("CLOSE_")
            || action.starts_with("REDUCE_")
        {
            per_symbol
                .entry(tr.symbol.clone())
                .or_default()
                .push((tr.timestamp_ms, idx));
        }
    }
    for events in per_symbol.values_mut() {
        events.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    }

    let mut rows: Vec<TradeExportRow> = Vec::new();

    for (symbol, events) in per_symbol {
        let bars = match candles.get(&symbol) {
            Some(b) => b,
            None => continue,
        };

        let mut candle_i: usize = 0;
        let mut active: Option<ActiveTrade> = init_position_by_symbol.get(&symbol).map(|pos| {
            let position_id = position_ids.get(&(symbol.clone(), 1)).copied().unwrap_or(0);
            let side = match pos.pos_type {
                bt_core::position::PositionType::Long => Side::Long,
                bt_core::position::PositionType::Short => Side::Short,
            };
            ActiveTrade {
                position_id,
                entry_ts_ms: pos.open_time_ms,
                entry_price: pos.entry_price,
                side,
                max_high: pos.entry_price,
                min_low: pos.entry_price,
                exit_seq: 0,
                open_count_for_symbol: 1,
            }
        });

        for (ts, idx) in events {
            let tr = &trades[idx];

            // Advance candles strictly before this trade timestamp.
            while candle_i < bars.len() && bars[candle_i].t < ts {
                if let Some(ref mut a) = active {
                    update_extremes(a, &bars[candle_i]);
                }
                candle_i += 1;
            }

            // OPEN must start the trade before we include the candle at ts.
            if tr.action.starts_with("OPEN_") {
                let open_count_for_symbol = open_seq_by_trade_index[idx].unwrap_or(1);

                let position_id = position_ids
                    .get(&(symbol.clone(), open_count_for_symbol))
                    .copied()
                    .unwrap_or(0);

                let side = if tr.action.ends_with("_LONG") {
                    Side::Long
                } else {
                    Side::Short
                };

                let mut a = ActiveTrade {
                    position_id,
                    entry_ts_ms: tr.timestamp_ms,
                    entry_price: tr.price,
                    side,
                    max_high: tr.price,
                    min_low: tr.price,
                    exit_seq: 0,
                    open_count_for_symbol,
                };

                // Include the entry candle bar at this timestamp.
                while candle_i < bars.len() && bars[candle_i].t == ts {
                    update_extremes(&mut a, &bars[candle_i]);
                    candle_i += 1;
                }

                active = Some(a);
                continue;
            }

            // For non-OPEN events, include the candle bar at ts before processing the event.
            while candle_i < bars.len() && bars[candle_i].t == ts {
                if let Some(ref mut a) = active {
                    update_extremes(a, &bars[candle_i]);
                }
                candle_i += 1;
            }

            // ADD events update the position but do not emit a trade row.
            if tr.action.starts_with("ADD_") {
                continue;
            }

            // Exit events emit a row.
            if tr.action.starts_with("CLOSE_") || tr.action.starts_with("REDUCE_") {
                let Some(ref mut a) = active else {
                    continue;
                };

                a.exit_seq += 1;

                let (mae_pct, mfe_pct) = if a.entry_price.abs() > 1e-12 {
                    match a.side {
                        Side::Long => (
                            (a.min_low - a.entry_price) / a.entry_price,
                            (a.max_high - a.entry_price) / a.entry_price,
                        ),
                        Side::Short => (
                            (a.entry_price - a.max_high) / a.entry_price,
                            (a.entry_price - a.min_low) / a.entry_price,
                        ),
                    }
                } else {
                    (0.0, 0.0)
                };

                let rc = bt_core::reason_codes::classify_reason_code(&tr.action, &tr.reason);

                rows.push(TradeExportRow {
                    trade_id: format!("{}:{}", a.position_id, a.exit_seq),
                    position_id: a.position_id,
                    entry_ts_ms: a.entry_ts_ms,
                    exit_ts_ms: tr.timestamp_ms,
                    symbol: symbol.clone(),
                    side: match a.side {
                        Side::Long => "LONG".to_string(),
                        Side::Short => "SHORT".to_string(),
                    },
                    entry_price: a.entry_price,
                    exit_price: tr.price,
                    exit_size: tr.size,
                    pnl_usd: tr.pnl,
                    fee_usd: tr.fee_usd,
                    mae_pct,
                    mfe_pct,
                    reason_code: reason_code_string(rc),
                    reason: tr.reason.clone(),
                });

                if tr.action.starts_with("CLOSE_") {
                    active = None;
                }
            }
        }
    }

    // Deterministic output order.
    rows.sort_by(|a, b| {
        a.exit_ts_ms
            .cmp(&b.exit_ts_ms)
            .then_with(|| a.symbol.cmp(&b.symbol))
            .then_with(|| a.trade_id.cmp(&b.trade_id))
    });

    rows
}

fn write_trade_export_csv(
    path: &PathBuf,
    rows: &[TradeExportRow],
) -> Result<(), Box<dyn std::error::Error>> {
    let mut f = std::fs::File::create(path)?;

    writeln!(
        f,
        "trade_id,position_id,entry_ts_ms,exit_ts_ms,symbol,side,entry_price,exit_price,exit_size,pnl_usd,fee_usd,mae_pct,mfe_pct,reason_code,reason"
    )?;

    for r in rows {
        writeln!(
            f,
            "{},{},{},{},{},{},{:.8},{:.8},{:.8},{:.8},{:.8},{:.8},{:.8},{},{}",
            csv_escape(&r.trade_id),
            r.position_id,
            r.entry_ts_ms,
            r.exit_ts_ms,
            csv_escape(&r.symbol),
            csv_escape(&r.side),
            r.entry_price,
            r.exit_price,
            r.exit_size,
            r.pnl_usd,
            r.fee_usd,
            r.mae_pct,
            r.mfe_pct,
            csv_escape(&r.reason_code),
            csv_escape(&r.reason),
        )?;
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// GPU sweep guardrails
// ---------------------------------------------------------------------------

fn parse_interval_minutes(iv: &str) -> Option<u32> {
    let s = iv.trim();
    if s.len() < 2 {
        return None;
    }
    let (num, unit) = s.split_at(s.len() - 1);
    let n: u32 = num.parse().ok()?;
    match unit {
        "m" | "M" => Some(n),
        "h" | "H" => Some(n.saturating_mul(60)),
        _ => None,
    }
}

fn compute_scope_days(from_ts: Option<i64>, to_ts: Option<i64>) -> Option<f64> {
    let f = from_ts?;
    let t = to_ts?;
    Some((t - f) as f64 / 86_400_000.0)
}

fn check_gpu_sweep_guardrails(
    main_interval: &str,
    exit_interval: Option<&str>,
    entry_interval: Option<&str>,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> Result<(), String> {
    let main_min = parse_interval_minutes(main_interval)
        .ok_or_else(|| format!("Unsupported main interval format: {:?}", main_interval))?;

    let mut sub_ivs: Vec<&str> = Vec::new();
    if let Some(iv) = exit_interval {
        sub_ivs.push(iv);
    }
    if let Some(iv) = entry_interval {
        sub_ivs.push(iv);
    }
    sub_ivs.sort_unstable();
    sub_ivs.dedup();

    if sub_ivs.is_empty() {
        return Err(format!(
            "GPU sweep requires sub-bar entry/exit intervals. Got interval={:?}, exit_interval=None, entry_interval=None.",
            main_interval,
        ));
    }
    if sub_ivs.len() > 1 {
        return Err(format!(
            "GPU sweep sub-bar intervals must match. Got interval={:?}, exit_interval={:?}, entry_interval={:?}.",
            main_interval,
            exit_interval,
            entry_interval,
        ));
    }

    let sub_iv = sub_ivs[0];
    let sub_min = parse_interval_minutes(sub_iv)
        .ok_or_else(|| format!("Unsupported sub-bar interval format: {:?}", sub_iv))?;

    let is_safe_combo = matches!((main_min, sub_min), (30, 5) | (60, 5) | (30, 3) | (60, 3));
    if !is_safe_combo {
        return Err(format!(
            "GPU sweep interval combo {:?}/{:?} is outside the default safe set (30m/5m, 1h/5m, 30m/3m, 1h/3m).",
            main_interval, sub_iv,
        ));
    }

    if compute_scope_days(from_ts, to_ts).is_none() {
        return Err(
            "GPU sweep requires a bounded scoped window (auto-scope or explicit --from-ts/--to-ts)."
                .to_string(),
        );
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Subcommand implementations
// ---------------------------------------------------------------------------

fn cmd_replay(args: ReplayArgs) -> Result<(), Box<dyn std::error::Error>> {
    let symbol_norm = args.symbol.as_ref().map(|s| s.trim().to_uppercase());
    let mut cfg = bt_core::config::load_config_checked(
        &args.config,
        symbol_norm.as_deref(),
        args.live,
    )
    .map_err(|e| {
        std::io::Error::new(std::io::ErrorKind::InvalidData, format!("[replay] {e}"))
    })?;

    if let Some(bps) = args.slippage_bps {
        cfg.trade.slippage_bps = bps.max(0.0);
    }

    // Resolve intervals: CLI arg > YAML engine section > default "1h"
    let interval = args.interval.unwrap_or_else(|| {
        let yaml_iv = &cfg.engine.interval;
        if yaml_iv.is_empty() {
            "1h".to_string()
        } else {
            yaml_iv.clone()
        }
    });

    // Auto-resolve candle DB path from interval if not explicitly provided
    let candles_db = args
        .candles_db
        .unwrap_or_else(|| format!("candles_dbs/candles_{}.db", interval));
    let candles_db_paths = resolve_db_paths(&candles_db);

    // Resolve exit_interval: CLI arg > YAML engine.exit_interval > None
    let exit_interval = args.exit_interval.or_else(|| {
        let yaml_eiv = &cfg.engine.exit_interval;
        if yaml_eiv.is_empty() {
            None
        } else {
            Some(yaml_eiv.clone())
        }
    });

    // Auto-resolve exit candle DB path from exit_interval if not explicitly provided
    let (exit_candles_db, exit_interval) = match (args.exit_candles_db, exit_interval) {
        (Some(db), iv) => (Some(db), iv),
        (None, Some(iv)) => (Some(format!("candles_dbs/candles_{}.db", iv)), Some(iv)),
        (None, None) => (None, None),
    };

    // Resolve entry_interval: CLI arg > YAML engine.entry_interval > None
    let entry_interval = args.entry_interval.or_else(|| {
        let yaml_niv = &cfg.engine.entry_interval;
        if yaml_niv.is_empty() {
            None
        } else {
            Some(yaml_niv.clone())
        }
    });

    // Auto-resolve entry candle DB path from entry_interval if not explicitly provided
    let (entry_candles_db, entry_interval) = match (args.entry_candles_db, entry_interval) {
        (Some(db), iv) => (Some(db), iv),
        (None, Some(iv)) => (Some(format!("candles_dbs/candles_{}.db", iv)), Some(iv)),
        (None, None) => (None, None),
    };
    let exit_db_paths = exit_candles_db.as_ref().map(|p| resolve_db_paths(p));
    let entry_db_paths = entry_candles_db.as_ref().map(|p| resolve_db_paths(p));

    eprintln!(
        "[replay] Config loaded from {:?} (live={}, symbol={:?})",
        args.config, args.live, symbol_norm,
    );
    eprintln!(
        "[replay] Indicator interval: {} (db: {})",
        interval, candles_db,
    );
    if let (Some(ref edb), Some(ref eiv)) = (&exit_candles_db, &exit_interval) {
        eprintln!("[replay] Exit interval: {} (db: {})", eiv, edb);
    }
    if let (Some(ref ndb), Some(ref niv)) = (&entry_candles_db, &entry_interval) {
        eprintln!("[replay] Entry interval: {} (db: {})", niv, ndb);
    }
    eprintln!(
        "[replay] SL={:.1}x ATR, TP={:.1}x ATR, leverage={:.1}, alloc={:.1}%",
        cfg.trade.sl_atr_mult,
        cfg.trade.tp_atr_mult,
        cfg.trade.leverage,
        cfg.trade.allocation_pct * 100.0,
    );
    eprintln!("[replay] slippage_bps={:.2}", cfg.trade.slippage_bps);

    // Compute time range: explicit --start-ts / --end-ts, with optional auto-scope.
    let mut scope_dbs: Vec<(&[String], &str)> = Vec::new();
    // Don't scope the indicator DB — it needs full history for warmup.
    // Only scope the entry/exit DBs that determine the trading window.
    if let (Some(ref paths), Some(ref eiv)) = (&exit_db_paths, &exit_interval) {
        scope_dbs.push((paths.as_slice(), eiv.as_str()));
    }
    if let (Some(ref paths), Some(ref niv)) = (&entry_db_paths, &entry_interval) {
        scope_dbs.push((paths.as_slice(), niv.as_str()));
    }
    if scope_dbs.is_empty() {
        // No sub-bar DBs — scope the main indicator DB
        scope_dbs.push((candles_db_paths.as_slice(), interval.as_str()));
    }
    let (from_ts, to_ts) = resolve_time_range_or_exit(
        "replay",
        &scope_dbs,
        !args.no_auto_scope,
        args.start_ts.map(|t| t.0),
        args.end_ts.map(|t| t.0),
    );

    // Load indicator candles (full history for warmup — no time filter)
    let mut candles = bt_data::sqlite_loader::load_candles_multi(&candles_db_paths, &interval)?;

    if candles.is_empty() {
        eprintln!("[replay] No candles found. Check --candles-db and --interval.");
        std::process::exit(1);
    }

    // If --symbol specified, verify it exists in the candle data (normalised to uppercase)
    if let Some(ref sym) = symbol_norm {
        if !candles.contains_key(sym) {
            let mut available: Vec<&String> = candles.keys().collect();
            available.sort();
            eprintln!(
                "[replay] Symbol {:?} not found in candle DB. Available: {:?}",
                sym, available,
            );
            std::process::exit(1);
        }
    }

    // Optional: filter candle universe to active symbols from universe_history.db
    let mut keep_symbols: Option<HashSet<String>> = None;
    if args.universe_filter {
        let (min_t, max_t) = infer_candle_range_ms(&candles).unwrap_or_else(|| {
            eprintln!("[replay] No candle timestamps found.");
            std::process::exit(1);
        });
        let filter_from = from_ts.unwrap_or(min_t);
        let filter_to = to_ts.unwrap_or(max_t);
        if filter_from > filter_to {
            eprintln!(
                "[replay] Invalid time range: from_ts > to_ts ({} > {})",
                filter_from, filter_to
            );
            std::process::exit(1);
        }

        let default_universe_seed = candles_db_paths
            .first()
            .map(|s| s.as_str())
            .unwrap_or(candles_db.as_str());
        let universe_db = args
            .universe_db
            .clone()
            .unwrap_or_else(|| default_universe_db_path(default_universe_seed));

        eprintln!(
            "[replay] Universe filter enabled: range={}..{}, db={}",
            filter_from, filter_to, universe_db,
        );
        let active = bt_data::sqlite_loader::load_universe_active_symbols(
            &universe_db,
            filter_from,
            filter_to,
        )
        .unwrap_or_else(|e| {
            eprintln!("[replay] Universe filter failed: {e}");
            std::process::exit(1);
        });
        if active.is_empty() {
            eprintln!(
                "[replay] Universe filter returned 0 active symbols (range={}..{})",
                filter_from, filter_to
            );
            std::process::exit(1);
        }
        keep_symbols = Some(active.into_iter().collect());
    }

    // If --symbol specified, restrict to a single symbol (and validate against universe filter if enabled).
    if let Some(ref sym) = symbol_norm {
        if let Some(ref keep) = keep_symbols {
            if !keep.contains(sym) {
                eprintln!(
                    "[replay] Symbol {:?} is not active in the universe history DB for the selected window.",
                    sym,
                );
                std::process::exit(1);
            }
        }
        let mut single = HashSet::new();
        single.insert(sym.clone());
        keep_symbols = Some(single);
    }

    // Apply final symbol filter to indicator candles
    if let Some(ref keep) = keep_symbols {
        let before = candles.len();
        candles.retain(|sym, _| keep.contains(sym));
        eprintln!(
            "[replay] Symbol universe: {before} -> {} symbols",
            candles.len()
        );
        if candles.is_empty() {
            eprintln!("[replay] No candles left after symbol filtering.");
            std::process::exit(1);
        }
    }

    let num_symbols = candles.len();
    let total_bars: usize = candles.values().map(|v| v.len()).sum();
    eprintln!("[replay] Loaded {total_bars} bars across {num_symbols} symbols");

    // Optional: load exit candles for two-level simulation (filtered)
    let exit_candles = if let Some(ref exit_db) = exit_candles_db {
        let exit_paths = exit_db_paths.as_ref().unwrap_or(&candles_db_paths);
        let exit_iv = exit_interval.as_deref().unwrap_or(&interval);
        eprintln!(
            "[replay] Loading exit candles from {:?} (interval={})",
            exit_db, exit_iv
        );
        let mut ec = bt_data::sqlite_loader::load_candles_filtered_multi(
            exit_paths, exit_iv, from_ts, to_ts,
        )?;
        if let Some(ref keep) = keep_symbols {
            ec.retain(|sym, _| keep.contains(sym));
        }
        let ec_bars: usize = ec.values().map(|v| v.len()).sum();
        eprintln!(
            "[replay] Exit candles: {} bars across {} symbols",
            ec_bars,
            ec.len()
        );
        Some(ec)
    } else {
        None
    };

    // Optional: load entry candles for sub-bar entry evaluation (filtered)
    let entry_candles = if let Some(ref entry_db) = entry_candles_db {
        let entry_paths = entry_db_paths.as_ref().unwrap_or(&candles_db_paths);
        let entry_iv = entry_interval.as_deref().unwrap_or(&interval);
        eprintln!(
            "[replay] Loading entry candles from {:?} (interval={})",
            entry_db, entry_iv
        );
        let mut nc = bt_data::sqlite_loader::load_candles_filtered_multi(
            entry_paths,
            entry_iv,
            from_ts,
            to_ts,
        )?;
        if let Some(ref keep) = keep_symbols {
            nc.retain(|sym, _| keep.contains(sym));
        }
        let nc_bars: usize = nc.values().map(|v| v.len()).sum();
        eprintln!(
            "[replay] Entry candles: {} bars across {} symbols",
            nc_bars,
            nc.len()
        );
        Some(nc)
    } else {
        None
    };

    // Optional: load funding rates (filtered)
    let funding_rates = if let Some(ref fdb) = args.funding_db {
        eprintln!("[replay] Loading funding rates from {:?}", fdb);
        let mut fr = bt_data::sqlite_loader::load_funding_rates_filtered(fdb, from_ts, to_ts)?;
        if let Some(ref keep) = keep_symbols {
            fr.retain(|sym, _| keep.contains(sym));
        }
        let fr_count: usize = fr.values().map(|v| v.len()).sum();
        eprintln!(
            "[replay] Funding rates: {} entries across {} symbols",
            fr_count,
            fr.len()
        );
        Some(fr)
    } else {
        None
    };

    // Resolve effective initial balance: --balance-from overrides --initial-balance
    let base_balance = if let Some(ref path) = args.balance_from {
        read_balance_from_json(path)?
    } else {
        args.initial_balance
    };

    // L9: validate initial_balance > 0
    if base_balance <= 0.0 {
        eprintln!("[error] initial_balance must be > 0.0, got {base_balance}");
        std::process::exit(1);
    }

    // Load init-state if provided (overrides both --initial-balance and --balance-from)
    let (effective_balance, init_state, init_positions_for_export) = if let Some(ref path) = args.init_state {
        eprintln!("[replay] Loading init-state from {:?}", path);
        let state_file = bt_core::init_state::load(path).unwrap_or_else(|e| {
            eprintln!("[error] {e}");
            std::process::exit(1);
        });

        // Collect valid symbols from candle data for filtering
        let sym_strs: Vec<&str> = candles.keys().map(|s| s.as_str()).collect();
        let (balance, positions, entry_attempt_ms, exit_attempt_ms) =
            bt_core::init_state::into_sim_state_with_runtime(state_file, Some(&sym_strs));
        let init_positions_for_export: Vec<bt_core::position::Position> =
            positions.values().cloned().collect();
        eprintln!(
            "[replay] Init-state: balance=${:.2}, {} position(s), {} entry cooldown marker(s), {} exit cooldown marker(s)",
            balance,
            positions.len(),
            entry_attempt_ms.len(),
            exit_attempt_ms.len(),
        );
        (
            balance,
            Some((balance, positions, entry_attempt_ms, exit_attempt_ms)),
            Some(init_positions_for_export),
        )
    } else {
        (base_balance, None, None)
    };

    let start = Instant::now();
    let sim = bt_core::engine::run_simulation(bt_core::engine::RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance: effective_balance,
        lookback: args.lookback,
        exit_candles: exit_candles.as_ref(),
        entry_candles: entry_candles.as_ref(),
        funding_rates: funding_rates.as_ref(),
        init_state,
        from_ts,
        to_ts,
    });
    let elapsed = start.elapsed();
    let config_fingerprint = bt_core::config::strategy_config_fingerprint_sha256(&cfg);

    let mut report = bt_core::report::build_report(bt_core::report::BuildReportInput {
        trades: &sim.trades,
        signals: &sim.signals,
        equity_curve: &sim.equity_curve,
        gate_stats: &sim.gate_stats,
        initial_balance: effective_balance,
        final_balance: sim.final_balance,
        config_id: "replay",
        include_trades: args.trades,
        include_equity_curve: args.equity_curve,
    });
    report.config_fingerprint = Some(config_fingerprint.clone());

    let mut decision_diagnostics = sim.decision_diagnostics;
    for trace in &mut decision_diagnostics {
        trace.set_config_fingerprint(config_fingerprint.clone());
    }
    report.decision_diagnostics = Some(decision_diagnostics);

    // Print summary to stderr
    print_summary(&report, effective_balance);
    eprintln!("\nCompleted in {:.3}s", elapsed.as_secs_f64());

    // Optional trade-level CSV export (one row per exit event).
    if let Some(ref path) = args.export_trades {
        let rows = build_trade_export_rows(
            &candles,
            &sim.trades,
            init_positions_for_export.as_deref(),
        );
        write_trade_export_csv(path, &rows)?;
        eprintln!("[replay] Trade CSV written to {}", path.display());
    }

    // JSON output
    let per_symbol = build_per_symbol_stats(&sim.trades, cfg.trade.slippage_bps);
    let mut json_obj = serde_json::to_value(&report)?;
    if let serde_json::Value::Object(ref mut map) = json_obj {
        map.insert("per_symbol".to_string(), serde_json::to_value(&per_symbol)?);
        // Record the effective slippage used for this run, even when overridden via CLI.
        map.insert(
            "slippage_bps".to_string(),
            serde_json::json!(cfg.trade.slippage_bps),
        );
    }
    let json = serde_json::to_string_pretty(&json_obj)?;
    if let Some(ref path) = args.output {
        let mut f = std::fs::File::create(path)?;
        f.write_all(json.as_bytes())?;
        f.write_all(b"\n")?;
        eprintln!("[replay] Report written to {}", path.display());
    } else {
        println!("{json}");
    }

    Ok(())
}

fn cmd_sweep(args: SweepArgs) -> Result<(), Box<dyn std::error::Error>> {
    // Load base config
    let base_cfg = bt_core::config::load_config_checked(&args.config, None, args.live).map_err(
        |e| std::io::Error::new(std::io::ErrorKind::InvalidData, format!("[sweep] {e}")),
    )?;

    // Resolve intervals: CLI arg > YAML engine section > default "1h"
    let interval = args.interval.unwrap_or_else(|| {
        let yaml_iv = &base_cfg.engine.interval;
        if yaml_iv.is_empty() {
            "1h".to_string()
        } else {
            yaml_iv.clone()
        }
    });

    // Auto-resolve candle DB path from interval
    let candles_db = args
        .candles_db
        .unwrap_or_else(|| format!("candles_dbs/candles_{}.db", interval));
    let candles_db_paths = resolve_db_paths(&candles_db);

    // Resolve exit_interval: CLI arg > YAML engine.exit_interval > None
    let exit_interval = args.exit_interval.or_else(|| {
        let yaml_eiv = &base_cfg.engine.exit_interval;
        if yaml_eiv.is_empty() {
            None
        } else {
            Some(yaml_eiv.clone())
        }
    });

    // Auto-resolve exit candle DB paths
    let (exit_candles_db, exit_interval) = match (args.exit_candles_db, exit_interval) {
        (Some(db), iv) => (Some(db), iv),
        (None, Some(iv)) => (Some(format!("candles_dbs/candles_{}.db", iv)), Some(iv)),
        (None, None) => (None, None),
    };

    // Resolve entry_interval: CLI arg > YAML engine.entry_interval > None
    let entry_interval = args.entry_interval.or_else(|| {
        let yaml_niv = &base_cfg.engine.entry_interval;
        if yaml_niv.is_empty() {
            None
        } else {
            Some(yaml_niv.clone())
        }
    });

    let (entry_candles_db, entry_interval) = match (args.entry_candles_db, entry_interval) {
        (Some(db), iv) => (Some(db), iv),
        (None, Some(iv)) => (Some(format!("candles_dbs/candles_{}.db", iv)), Some(iv)),
        (None, None) => (None, None),
    };
    let exit_db_paths = exit_candles_db.as_ref().map(|p| resolve_db_paths(p));
    let entry_db_paths = entry_candles_db.as_ref().map(|p| resolve_db_paths(p));

    // Resolve effective initial balance: --balance-from overrides --initial-balance
    let initial_balance = if let Some(ref path) = args.balance_from {
        read_balance_from_json(path)?
    } else {
        args.initial_balance
    };

    // L9: validate initial_balance > 0
    if initial_balance <= 0.0 {
        eprintln!("[error] initial_balance must be > 0.0, got {initial_balance}");
        std::process::exit(1);
    }

    // Load sweep spec
    let mut spec = bt_core::sweep::load_sweep_spec(&args.sweep_spec)?;
    // Override spec balance with CLI-resolved value (--balance-from > --initial-balance > default)
    spec.initial_balance = initial_balance;

    eprintln!(
        "[sweep] {} axes, initial_balance={}, lookback={}, interval={} (db: {})",
        spec.axes.len(),
        initial_balance,
        spec.lookback,
        interval,
        candles_db,
    );
    if let (Some(ref edb), Some(ref eiv)) = (&exit_candles_db, &exit_interval) {
        eprintln!("[sweep] Exit interval: {} (db: {})", eiv, edb);
    }
    if let (Some(ref ndb), Some(ref niv)) = (&entry_candles_db, &entry_interval) {
        eprintln!("[sweep] Entry interval: {} (db: {})", niv, ndb);
    }
    for axis in &spec.axes {
        eprintln!(
            "  - {} ({} values: {:?})",
            axis.path,
            axis.values.len(),
            axis.values
        );
    }

    // Override verification (before any heavy I/O)
    let do_verify = args.verify_overrides || args.strict_overrides;
    let override_verifications = if do_verify {
        // Collect unique (path, sample_value) pairs from the sweep spec
        let test_overrides: Vec<(String, f64)> = spec
            .axes
            .iter()
            .map(|axis| {
                let sample_value = axis.values.first().copied().unwrap_or(0.0);
                (axis.path.clone(), sample_value)
            })
            .collect();

        let verifications = bt_core::sweep::verify_overrides(&base_cfg, &test_overrides);

        let mut has_failures = false;
        for v in &verifications {
            match v.status {
                bt_core::sweep::OverrideStatus::Applied => {
                    eprintln!(
                        "[verify] OK: {} (before={:.6}, after={:.6}, requested={:.6})",
                        v.path,
                        v.before.unwrap_or(f64::NAN),
                        v.after.unwrap_or(f64::NAN),
                        v.requested,
                    );
                }
                bt_core::sweep::OverrideStatus::FailedNotFound => {
                    eprintln!("[verify] FAIL: {} — path not found in config", v.path);
                    has_failures = true;
                }
                bt_core::sweep::OverrideStatus::FailedUnchanged => {
                    eprintln!(
                        "[verify] FAIL: {} — override did not change value (before={:.6}, requested={:.6})",
                        v.path,
                        v.before.unwrap_or(f64::NAN),
                        v.requested,
                    );
                    has_failures = true;
                }
            }
        }

        if has_failures && args.strict_overrides {
            return Err("Aborting: --strict-overrides is set and one or more override paths failed verification.".into());
        }

        Some(verifications)
    } else {
        None
    };

    // Compute time range: explicit --start-ts / --end-ts, with optional auto-scope.
    let mut scope_dbs: Vec<(&[String], &str)> =
        vec![(candles_db_paths.as_slice(), interval.as_str())];
    if let (Some(ref paths), Some(ref eiv)) = (&exit_db_paths, &exit_interval) {
        scope_dbs.push((paths.as_slice(), eiv.as_str()));
    }
    if let (Some(ref paths), Some(ref niv)) = (&entry_db_paths, &entry_interval) {
        scope_dbs.push((paths.as_slice(), niv.as_str()));
    }
    let (from_ts, to_ts) = resolve_time_range_or_exit(
        "sweep",
        &scope_dbs,
        !args.no_auto_scope,
        args.start_ts.map(|t| t.0),
        args.end_ts.map(|t| t.0),
    );

    if !args.no_auto_scope {
        if let Some(days) = compute_scope_days(from_ts, to_ts) {
            eprintln!("[auto-scope] Scoped period length: {:.1} days", days);
        } else {
            eprintln!("[auto-scope] Scoped period length: unknown (missing bounds)");
        }
    }

    if args.gpu && !args.allow_unsafe_gpu_sweep {
        if let Err(msg) = check_gpu_sweep_guardrails(
            &interval,
            exit_interval.as_deref(),
            entry_interval.as_deref(),
            from_ts,
            to_ts,
        ) {
            eprintln!("[guardrail] {msg}");
            eprintln!("[guardrail] Override with --allow-unsafe-gpu-sweep.");
            std::process::exit(1);
        }
    }

    // Load indicator candles (full history for warmup — no time filter)
    let mut candles = bt_data::sqlite_loader::load_candles_multi(&candles_db_paths, &interval)?;
    if candles.is_empty() {
        eprintln!("[sweep] No candles found. Check --candles-db.");
        std::process::exit(1);
    }

    // Optional: filter candle universe to active symbols from universe_history.db
    let mut keep_symbols: Option<HashSet<String>> = None;
    if args.universe_filter {
        let (min_t, max_t) = infer_candle_range_ms(&candles).unwrap_or_else(|| {
            eprintln!("[sweep] No candle timestamps found.");
            std::process::exit(1);
        });
        let filter_from = from_ts.unwrap_or(min_t);
        let filter_to = to_ts.unwrap_or(max_t);
        if filter_from > filter_to {
            eprintln!(
                "[sweep] Invalid time range: from_ts > to_ts ({} > {})",
                filter_from, filter_to
            );
            std::process::exit(1);
        }

        let default_universe_seed = candles_db_paths
            .first()
            .map(|s| s.as_str())
            .unwrap_or(candles_db.as_str());
        let universe_db = args
            .universe_db
            .clone()
            .unwrap_or_else(|| default_universe_db_path(default_universe_seed));

        eprintln!(
            "[sweep] Universe filter enabled: range={}..{}, db={}",
            filter_from, filter_to, universe_db,
        );
        let active = bt_data::sqlite_loader::load_universe_active_symbols(
            &universe_db,
            filter_from,
            filter_to,
        )
        .unwrap_or_else(|e| {
            eprintln!("[sweep] Universe filter failed: {e}");
            std::process::exit(1);
        });
        if active.is_empty() {
            eprintln!(
                "[sweep] Universe filter returned 0 active symbols (range={}..{})",
                filter_from, filter_to
            );
            std::process::exit(1);
        }
        keep_symbols = Some(active.into_iter().collect());
    }

    // Apply final symbol filter to indicator candles
    if let Some(ref keep) = keep_symbols {
        let before = candles.len();
        candles.retain(|sym, _| keep.contains(sym));
        eprintln!(
            "[sweep] Symbol universe: {before} -> {} symbols",
            candles.len()
        );
        if candles.is_empty() {
            eprintln!("[sweep] No candles left after symbol filtering.");
            std::process::exit(1);
        }
    }

    match args.parity_mode {
        SweepParityMode::Production => {
            eprintln!(
                "[sweep] Parity mode: production (lane B). GPU runtime may truncate symbols to the kernel cap ({}).",
                GPU_KERNEL_SYMBOL_CAP,
            );
        }
        SweepParityMode::IdenticalSymbolUniverse => {
            match apply_alphabetical_symbol_cap(&mut candles, GPU_KERNEL_SYMBOL_CAP) {
                Some((before, after)) => {
                    eprintln!(
                        "[sweep] Parity mode: identical-symbol-universe (lane A). Symbol universe: {before} -> {after} (alphabetical cap={}).",
                        GPU_KERNEL_SYMBOL_CAP,
                    );
                }
                None => {
                    eprintln!(
                        "[sweep] Parity mode: identical-symbol-universe (lane A). No cap needed ({} symbols <= {}).",
                        candles.len(),
                        GPU_KERNEL_SYMBOL_CAP,
                    );
                }
            }
            if candles.is_empty() {
                eprintln!("[sweep] No candles left after lane A parity symbol-cap.");
                std::process::exit(1);
            }
        }
    }

    let aux_symbol_filter: Option<HashSet<String>> =
        if keep_symbols.is_some() || args.parity_mode == SweepParityMode::IdenticalSymbolUniverse {
            Some(candles.keys().cloned().collect())
        } else {
            None
        };

    let num_symbols = candles.len();
    let total_bars: usize = candles.values().map(|v| v.len()).sum();
    eprintln!("[sweep] Loaded {total_bars} bars across {num_symbols} symbols");

    // Load exit candles (filtered)
    let exit_candles = if let Some(ref exit_db) = exit_candles_db {
        let exit_paths = exit_db_paths.as_ref().unwrap_or(&candles_db_paths);
        let exit_iv = exit_interval.as_deref().unwrap_or(&interval);
        eprintln!(
            "[sweep] Loading exit candles from {:?} (interval={})",
            exit_db, exit_iv
        );
        let mut ec = bt_data::sqlite_loader::load_candles_filtered_multi(
            exit_paths, exit_iv, from_ts, to_ts,
        )?;
        if let Some(ref keep) = aux_symbol_filter {
            ec.retain(|sym, _| keep.contains(sym));
        }
        let ec_bars: usize = ec.values().map(|v| v.len()).sum();
        eprintln!(
            "[sweep] Exit candles: {} bars across {} symbols",
            ec_bars,
            ec.len()
        );
        Some(ec)
    } else {
        None
    };

    // Load entry candles (filtered)
    let entry_candles = if let Some(ref entry_db) = entry_candles_db {
        let entry_paths = entry_db_paths.as_ref().unwrap_or(&candles_db_paths);
        let entry_iv = entry_interval.as_deref().unwrap_or(&interval);
        eprintln!(
            "[sweep] Loading entry candles from {:?} (interval={})",
            entry_db, entry_iv
        );
        let mut nc = bt_data::sqlite_loader::load_candles_filtered_multi(
            entry_paths,
            entry_iv,
            from_ts,
            to_ts,
        )?;
        if let Some(ref keep) = aux_symbol_filter {
            nc.retain(|sym, _| keep.contains(sym));
        }
        let nc_bars: usize = nc.values().map(|v| v.len()).sum();
        eprintln!(
            "[sweep] Entry candles: {} bars across {} symbols",
            nc_bars,
            nc.len()
        );
        Some(nc)
    } else {
        None
    };

    // Load funding rates (filtered)
    let funding_rates = if let Some(ref fdb) = args.funding_db {
        let mut fr = bt_data::sqlite_loader::load_funding_rates_filtered(fdb, from_ts, to_ts)?;
        if let Some(ref keep) = aux_symbol_filter {
            fr.retain(|sym, _| keep.contains(sym));
        }
        let fr_count: usize = fr.values().map(|v| v.len()).sum();
        eprintln!(
            "[sweep] Funding rates: {} entries across {} symbols",
            fr_count,
            fr.len()
        );
        Some(fr)
    } else {
        None
    };

    #[cfg(feature = "gpu")]
    {
        let gpu_path_requested = args.gpu || args.tpe;
        if gpu_path_requested && funding_rates.is_some() {
            eprintln!("[sweep] Funding DB enabled; GPU funding settlements active");
        }
    }

    // Configure rayon thread pool
    if let Some(n) = args.threads {
        rayon::ThreadPoolBuilder::new()
            .num_threads(n)
            .build_global()
            .ok();
        eprintln!("[sweep] Rayon thread pool: {n} threads");
    } else {
        eprintln!(
            "[sweep] Rayon thread pool: {} threads (auto)",
            rayon::current_num_threads(),
        );
    }

    // ------------------------------------------------------------------
    // GPU-accelerated sweep path (feature-gated)
    // ------------------------------------------------------------------
    #[cfg(not(feature = "gpu"))]
    if args.gpu {
        eprintln!("Error: --gpu requires building with `--features gpu`");
        std::process::exit(1);
    }

    #[cfg(not(feature = "gpu"))]
    if args.tpe {
        eprintln!("Error: --tpe requires building with `--features gpu`");
        std::process::exit(1);
    }

    // GPU sub-bar candles: prefer exit_candles, fallback to entry_candles
    #[cfg(feature = "gpu")]
    let gpu_sub_candles: Option<&bt_core::candle::CandleData> =
        exit_candles.as_ref().or(entry_candles.as_ref());

    #[cfg(feature = "gpu")]
    if args.tpe {
        if !args.gpu {
            eprintln!("Error: --tpe requires --gpu");
            std::process::exit(1);
        }
        eprintln!("[sweep] Using TPE Bayesian optimization (GPU)");
        let gpu_start = Instant::now();
        let tpe_cfg = bt_gpu::tpe_sweep::TpeConfig {
            trials: args.tpe_trials,
            batch_size: args.tpe_batch,
            seed: args.tpe_seed,
        };
        let results = bt_gpu::tpe_sweep::run_tpe_sweep(
            &candles,
            &base_cfg,
            &spec,
            funding_rates.as_ref(),
            &tpe_cfg,
            gpu_sub_candles,
            from_ts,
            to_ts,
            args.sweep_top_k,
        );
        let gpu_elapsed = gpu_start.elapsed();

        // Write JSONL output
        {
            let mut f = std::fs::File::create(&args.output)?;
            let top_n = args.top_n.unwrap_or(results.len());
            for r in results.iter().take(top_n) {
                let mut overrides = serde_json::Map::new();
                for (k, v) in &r.overrides {
                    overrides.insert(k.clone(), serde_json::Value::from(*v));
                }
                let overrides = serde_json::Value::Object(overrides);
                let json = if args.output_mode.is_candidate() {
                    serde_json::json!({
                        "schema_version": 1,
                        "config_id": r.config_id,
                        "output_mode": args.output_mode.as_str(),
                        "overrides": overrides,
                        "total_pnl": r.total_pnl,
                        "total_trades": r.total_trades,
                        "profit_factor": r.profit_factor,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "candidate_mode": true,
                    })
                } else {
                    serde_json::json!({
                        "config_id": r.config_id,
                        "output_mode": args.output_mode.as_str(),
                        "total_pnl": r.total_pnl,
                        "final_balance": r.final_balance,
                        "total_trades": r.total_trades,
                        "total_wins": r.total_wins,
                        "win_rate": r.win_rate,
                        "profit_factor": r.profit_factor,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "overrides": overrides,
                    })
                };
                writeln!(f, "{}", json)?;
            }
            eprintln!(
                "\n[sweep] TPE results written to {} ({} rows)",
                args.output.display(),
                top_n.min(results.len()),
            );
        }

        eprintln!(
            "\n[sweep] {} TPE trials completed via GPU in {:.2}s ({:.1} trials/s)",
            results.len(),
            gpu_elapsed.as_secs_f64(),
            results.len() as f64 / gpu_elapsed.as_secs_f64(),
        );

        // Print top 5 summary
        eprintln!("\n[TPE] Top 5 results:");
        for (i, r) in results.iter().take(5).enumerate() {
            eprintln!(
                "  #{}: PnL=${:.2}, Trades={}, WR={:.1}%, PF={:.2}, DD={:.1}%",
                i + 1,
                r.total_pnl,
                r.total_trades,
                r.win_rate * 100.0,
                r.profit_factor,
                r.max_drawdown_pct * 100.0,
            );
        }

        return Ok(());
    }

    #[cfg(feature = "gpu")]
    if args.gpu {
        eprintln!("[sweep] Using GPU-accelerated sweep");
        let gpu_start = Instant::now();
        let results = bt_gpu::run_gpu_sweep(
            &candles,
            &base_cfg,
            &spec,
            funding_rates.as_ref(),
            gpu_sub_candles,
            from_ts,
            to_ts,
        );
        let gpu_elapsed = gpu_start.elapsed();

        // Write JSONL output (same format as CPU sweep)
        {
            let mut f = std::fs::File::create(&args.output)?;
            for r in &results {
                let mut overrides = serde_json::Map::new();
                for (k, v) in &r.overrides {
                    overrides.insert(k.clone(), serde_json::Value::from(*v));
                }
                let overrides = serde_json::Value::Object(overrides);
                let json = if args.output_mode.is_candidate() {
                    serde_json::json!({
                        "schema_version": 1,
                        "config_id": r.config_id,
                        "output_mode": args.output_mode.as_str(),
                        "overrides": overrides,
                        "total_pnl": r.total_pnl,
                        "total_trades": r.total_trades,
                        "profit_factor": r.profit_factor,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "candidate_mode": true,
                    })
                } else {
                    serde_json::json!({
                        "config_id": r.config_id,
                        "output_mode": args.output_mode.as_str(),
                        "total_pnl": r.total_pnl,
                        "final_balance": r.final_balance,
                        "total_trades": r.total_trades,
                        "win_rate": r.win_rate,
                        "profit_factor": r.profit_factor,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "overrides": overrides,
                    })
                };
                writeln!(f, "{}", json)?;
            }
            eprintln!(
                "\n[sweep] GPU results written to {} ({} rows)",
                args.output.display(),
                results.len(),
            );
        }

        eprintln!(
            "\n[sweep] {} combos completed via GPU in {:.2}s ({:.1} combos/s)",
            results.len(),
            gpu_elapsed.as_secs_f64(),
            results.len() as f64 / gpu_elapsed.as_secs_f64(),
        );
        return Ok(());
    }

    // ------------------------------------------------------------------
    // CPU sweep path (default)
    // ------------------------------------------------------------------
    let sweep_start = Instant::now();
    let results = bt_core::sweep::run_sweep(
        &base_cfg,
        &spec,
        &candles,
        exit_candles.as_ref(),
        entry_candles.as_ref(),
        funding_rates.as_ref(),
        from_ts,
        to_ts,
    );
    let sweep_elapsed = sweep_start.elapsed();

    let total_combos = results.len();

    // Write JSONL output (report + overrides flattened)
    {
        let mut f = std::fs::File::create(&args.output)?;
        for r in &results {
            let mut obj = serde_json::to_value(&r.report)?;
            if let serde_json::Value::Object(ref mut map) = obj {
                let mut ov = serde_json::Map::new();
                for (k, v) in &r.overrides {
                    ov.insert(k.clone(), serde_json::Value::from(*v));
                }
                map.insert("overrides".to_string(), serde_json::Value::Object(ov));
                map.insert(
                    "output_mode".to_string(),
                    serde_json::Value::String(args.output_mode.as_str().to_string()),
                );
                if args.output_mode.is_candidate() {
                    map.insert("candidate_mode".to_string(), serde_json::Value::Bool(true));
                }
                if let Some(ref verifications) = override_verifications {
                    map.insert(
                        "override_verification".to_string(),
                        serde_json::to_value(verifications).unwrap_or(serde_json::Value::Null),
                    );
                }
            }
            let line = if args.output_mode.is_candidate() {
                serde_json::json!({
                        "schema_version": 1,
                        "config_id": r.config_id,
                        "output_mode": args.output_mode.as_str(),
                        "overrides": obj.get("overrides").cloned().unwrap_or_else(|| serde_json::Value::Object(serde_json::Map::new())),
                        "total_pnl": r.report.total_pnl,
                    "total_trades": r.report.total_trades,
                    "profit_factor": r.report.profit_factor,
                    "max_drawdown_pct": r.report.max_drawdown_pct,
                    "candidate_mode": true,
                })
            } else {
                obj
            };
            let line = serde_json::to_string(&line)?;
            writeln!(f, "{line}")?;
        }
        eprintln!(
            "\n[sweep] Results written to {} ({} rows)",
            args.output.display(),
            results.len(),
        );
    }

    // Print top N summary
    let display_n = args.top_n.unwrap_or(10).min(results.len());
    eprintln!("\n--- Top {display_n} results (by total PnL) ---\n");
    eprintln!(
        "{:>5}  {:>10}  {:>12}  {:>8}  {:>8}  {:>8}  {:>10}  {}",
        "Rank", "Config", "PnL", "WR%", "Trades", "Sharpe", "MaxDD%", "Overrides",
    );
    eprintln!("{}", "-".repeat(100));

    for (rank, r) in results.iter().take(display_n).enumerate() {
        let overrides_str: Vec<String> = r
            .overrides
            .iter()
            .map(|(k, v)| format!("{k}={v:.3}"))
            .collect();

        eprintln!(
            "{:>5}  {:>10}  {:>12.2}  {:>7.1}%  {:>8}  {:>8.3}  {:>9.2}%  {}",
            rank + 1,
            r.config_id,
            r.report.total_pnl,
            r.report.win_rate * 100.0,
            r.report.total_trades,
            r.report.sharpe_ratio,
            r.report.max_drawdown_pct * 100.0,
            overrides_str.join(", "),
        );
    }

    eprintln!(
        "\n[sweep] {total_combos} combos completed in {:.2}s ({:.1} combos/s)",
        sweep_elapsed.as_secs_f64(),
        total_combos as f64 / sweep_elapsed.as_secs_f64(),
    );

    Ok(())
}

fn cmd_dump_indicators(args: DumpArgs) -> Result<(), Box<dyn std::error::Error>> {
    let cfg = bt_core::config::load_config_checked(&args.config, Some(&args.symbol), false)
        .map_err(|e| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("[dump-indicators] {e}"),
            )
        })?;

    // Resolve interval: CLI arg > YAML engine section > default "1h"
    let interval = args.interval.unwrap_or_else(|| {
        let yaml_iv = &cfg.engine.interval;
        if yaml_iv.is_empty() {
            "1h".to_string()
        } else {
            yaml_iv.clone()
        }
    });

    // Auto-resolve candle DB path from interval
    let candles_db = args
        .candles_db
        .unwrap_or_else(|| format!("candles_dbs/candles_{}.db", interval));

    let candles_db_paths = resolve_db_paths(&candles_db);
    let candles = bt_data::sqlite_loader::load_candles_multi(&candles_db_paths, &interval)?;

    let bars = candles.get(&args.symbol).ok_or_else(|| {
        let mut available: Vec<&String> = candles.keys().collect();
        available.sort();
        format!(
            "Symbol {:?} not found in candle DB. Available: {:?}",
            args.symbol, available,
        )
    })?;

    eprintln!(
        "[dump-indicators] {} bars for {} (config: {:?})",
        bars.len(),
        args.symbol,
        args.config,
    );

    let mut bank = make_indicator_bank(&cfg);

    let mut writer: Box<dyn Write> = if let Some(ref path) = args.output {
        Box::new(std::io::BufWriter::new(std::fs::File::create(path)?))
    } else {
        Box::new(std::io::BufWriter::new(std::io::stdout().lock()))
    };

    // CSV header
    writeln!(
        writer,
        "t,close,ema_slow,ema_fast,ema_macro,adx,adx_slope,adx_pos,adx_neg,\
         bb_upper,bb_lower,bb_width,atr,rsi,macd_hist,\
         stoch_rsi_k,stoch_rsi_d,vol_sma,vol_trend"
    )?;

    let start = Instant::now();

    for bar in bars {
        let snap = bank.update(bar);

        writeln!(
            writer,
            "{},{:.8},{:.8},{:.8},{:.8},{:.4},{:.4},{:.4},{:.4},\
             {:.8},{:.8},{:.6},{:.8},{:.4},{:.8},\
             {:.4},{:.4},{:.4},{}",
            snap.t,
            snap.close,
            snap.ema_slow,
            snap.ema_fast,
            snap.ema_macro,
            snap.adx,
            snap.adx_slope,
            snap.adx_pos,
            snap.adx_neg,
            snap.bb_upper,
            snap.bb_lower,
            snap.bb_width,
            snap.atr,
            snap.rsi,
            snap.macd_hist,
            snap.stoch_rsi_k,
            snap.stoch_rsi_d,
            snap.vol_sma,
            snap.vol_trend as u8,
        )?;
    }

    writer.flush()?;

    let elapsed = start.elapsed();

    if let Some(ref path) = args.output {
        eprintln!(
            "[dump-indicators] Wrote {} rows to {} in {:.2}s",
            bars.len(),
            path.display(),
            elapsed.as_secs_f64(),
        );
    } else {
        eprintln!(
            "[dump-indicators] Dumped {} rows in {:.2}s",
            bars.len(),
            elapsed.as_secs_f64(),
        );
    }

    Ok(())
}

fn make_indicator_bank(
    cfg: &bt_core::config::StrategyConfig,
) -> bt_core::indicators::IndicatorBank {
    bt_core::indicators::IndicatorBank::new_with_ave_window(
        &cfg.indicators,
        cfg.filters.use_stoch_rsi_filter,
        cfg.effective_ave_avg_atr_window(),
    )
}

// ---------------------------------------------------------------------------
// Summary printer
// ---------------------------------------------------------------------------

fn print_summary(r: &bt_core::report::SimReport, initial_balance: f64) {
    eprintln!("\n=== Backtest Summary ===\n");
    eprintln!("Initial Balance:   ${:.2}", initial_balance);
    eprintln!("Final Balance:     ${:.2}", r.final_balance);
    eprintln!(
        "Total PnL:         ${:.2} ({:+.2}%)",
        r.total_pnl,
        r.total_pnl / initial_balance * 100.0
    );
    eprintln!("Total Trades:      {}", r.total_trades);
    eprintln!(
        "Win Rate:          {:.1}% ({}/{})",
        r.win_rate * 100.0,
        r.total_wins,
        r.total_trades
    );
    eprintln!("Profit Factor:     {:.2}", r.profit_factor);
    eprintln!("Sharpe Ratio:      {:.3}", r.sharpe_ratio);
    eprintln!(
        "Max Drawdown:      ${:.2} ({:.2}%)",
        r.max_drawdown_usd,
        r.max_drawdown_pct * 100.0
    );
    eprintln!("Avg Win:           ${:.2}", r.avg_win);
    eprintln!("Avg Loss:          ${:.2}", r.avg_loss);
    eprintln!("Total Fees:        ${:.2}", r.total_fees);
    eprintln!("Signals Generated: {}", r.total_signals);

    if !r.by_confidence.is_empty() {
        eprintln!("\n--- By Confidence ---");
        for b in &r.by_confidence {
            eprintln!(
                "  {:>8}: {:>4} trades, PnL ${:>8.2}, WR {:.1}%, Avg ${:.2}",
                b.confidence,
                b.trades,
                b.pnl,
                b.win_rate * 100.0,
                b.avg_pnl
            );
        }
    }

    if !r.by_exit_reason.is_empty() {
        eprintln!("\n--- By Exit Reason ---");
        for b in &r.by_exit_reason {
            eprintln!(
                "  {:>20}: {:>4} trades, PnL ${:>8.2}, WR {:.1}%",
                b.reason,
                b.trades,
                b.pnl,
                b.win_rate * 100.0
            );
        }
    }

    // Gate stats
    let gs = &r.gate_stats;
    eprintln!("\n--- Gate Stats ---");
    eprintln!("  Total checks:         {}", gs.total_checks);
    eprintln!(
        "  Signals generated:    {} ({:.1}%)",
        gs.signals_generated,
        gs.signal_pct * 100.0
    );
    if gs.blocked_by_ranging > 0 {
        eprintln!("  Blocked by ranging:   {}", gs.blocked_by_ranging);
    }
    if gs.blocked_by_anomaly > 0 {
        eprintln!("  Blocked by anomaly:   {}", gs.blocked_by_anomaly);
    }
    if gs.blocked_by_adx_low > 0 {
        eprintln!("  Blocked by ADX low:   {}", gs.blocked_by_adx_low);
    }
    if gs.blocked_by_confidence > 0 {
        eprintln!("  Blocked by confidence:{}", gs.blocked_by_confidence);
    }
    if gs.blocked_by_max_positions > 0 {
        eprintln!("  Blocked by max pos:   {}", gs.blocked_by_max_positions);
    }
    if gs.blocked_by_pesc > 0 {
        eprintln!("  Blocked by PESC:      {}", gs.blocked_by_pesc);
    }
    if gs.blocked_by_ssf > 0 {
        eprintln!("  Blocked by SSF:       {}", gs.blocked_by_ssf);
    }
    if gs.blocked_by_reef > 0 {
        eprintln!("  Blocked by REEF:      {}", gs.blocked_by_reef);
    }
    if gs.blocked_by_margin > 0 {
        eprintln!("  Blocked by margin:    {}", gs.blocked_by_margin);
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod guardrails_tests {
    use super::*;

    #[test]
    fn test_parse_interval_minutes() {
        assert_eq!(parse_interval_minutes("3m"), Some(3));
        assert_eq!(parse_interval_minutes("30m"), Some(30));
        assert_eq!(parse_interval_minutes("1h"), Some(60));
        assert_eq!(parse_interval_minutes("2h"), Some(120));
        assert_eq!(parse_interval_minutes(""), None);
        assert_eq!(parse_interval_minutes("abc"), None);
        assert_eq!(parse_interval_minutes("5"), None);
    }

    #[test]
    fn test_gpu_guardrails_safe_combo() {
        let from_ts = Some(0);
        let to_ts = Some((10.0 * 86_400_000.0) as i64);
        assert!(check_gpu_sweep_guardrails("1h", Some("3m"), Some("3m"), from_ts, to_ts).is_ok());
        assert!(check_gpu_sweep_guardrails("30m", Some("5m"), None, from_ts, to_ts).is_ok());
    }

    #[test]
    fn test_gpu_guardrails_allows_long_window() {
        let from_ts = Some(0);
        let to_ts = Some((365.0 * 86_400_000.0) as i64);
        assert!(check_gpu_sweep_guardrails("1h", Some("3m"), Some("3m"), from_ts, to_ts).is_ok());
    }

    #[test]
    fn test_gpu_guardrails_rejects_unbounded_window() {
        let err = check_gpu_sweep_guardrails("1h", Some("3m"), Some("3m"), None, None).unwrap_err();
        assert!(err.contains("bounded scoped window"));
    }

    #[test]
    fn test_gpu_guardrails_rejects_unsafe_combo() {
        let from_ts = Some(0);
        let to_ts = Some((10.0 * 86_400_000.0) as i64);
        let err = check_gpu_sweep_guardrails("15m", Some("5m"), None, from_ts, to_ts).unwrap_err();
        assert!(err.contains("outside the default safe set"));
    }

    #[test]
    fn test_gpu_guardrails_rejects_mismatched_sub_intervals() {
        let from_ts = Some(0);
        let to_ts = Some((10.0 * 86_400_000.0) as i64);
        let err =
            check_gpu_sweep_guardrails("1h", Some("3m"), Some("5m"), from_ts, to_ts).unwrap_err();
        assert!(err.contains("must match"));
    }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

// ─── WSL2 CUDA driver fix ────────────────────────────────────────────
//
// On WSL2, the real CUDA driver lives in /usr/lib/wsl/lib/ but a stale
// native-Linux libcuda.so from a CUDA toolkit install may shadow it in
// ld.so.cache.  cudarc loads "libcuda.so" via dlopen which picks the
// cached (wrong) version → CUDA_ERROR_NO_DEVICE.
//
// Fix: detect WSL2, prepend /usr/lib/wsl/lib to LD_LIBRARY_PATH, and
// re-exec so the dynamic linker sees the correct library first.
#[cfg(all(target_os = "linux", feature = "gpu"))]
fn ensure_wsl_cuda_path() {
    const WSL_LIB: &str = "/usr/lib/wsl/lib";
    const MARKER: &str = "__MEI_WSL_CUDA_REEXEC";

    // Already re-executed, or not on WSL2.
    if std::env::var_os(MARKER).is_some() {
        return;
    }
    if !std::path::Path::new(&format!("{WSL_LIB}/libcuda.so.1")).exists() {
        return;
    }

    let current = std::env::var("LD_LIBRARY_PATH").unwrap_or_default();
    if current.contains(WSL_LIB) {
        return;
    }

    let new_val = if current.is_empty() {
        WSL_LIB.to_string()
    } else {
        format!("{WSL_LIB}:{current}")
    };

    // SAFETY: single-threaded at this point (before rayon/tokio init).
    unsafe {
        std::env::set_var("LD_LIBRARY_PATH", &new_val);
        std::env::set_var(MARKER, "1");
    }

    let exe = match std::env::current_exe() {
        Ok(p) => p,
        Err(_) => return,
    };
    let args: Vec<std::ffi::CString> = std::env::args()
        .map(|a| std::ffi::CString::new(a).unwrap_or_default())
        .collect();
    let mut ptrs: Vec<*const libc::c_char> = args.iter().map(|a| a.as_ptr()).collect();
    ptrs.push(std::ptr::null());

    let exe_c = match std::ffi::CString::new(exe.to_string_lossy().into_owned()) {
        Ok(c) => c,
        Err(_) => return,
    };

    eprintln!("[GPU] WSL2 detected — re-exec with LD_LIBRARY_PATH={new_val}");
    unsafe {
        libc::execv(exe_c.as_ptr(), ptrs.as_ptr());
    }
    // execv only returns on error — fall through and try without the fix.
    eprintln!("[GPU] WSL2 re-exec failed, CUDA may not work");
}

fn main() {
    #[cfg(all(target_os = "linux", feature = "gpu"))]
    ensure_wsl_cuda_path();

    let cli = Cli::parse();

    eprintln!("mei-backtester v{VERSION}");
    eprintln!();

    let result = match cli.command {
        Commands::Replay(args) => cmd_replay(args),
        Commands::Sweep(args) => cmd_sweep(args),
        Commands::DumpIndicators(args) => cmd_dump_indicators(args),
    };

    if let Err(e) = result {
        eprintln!("\n[error] {e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use bt_core::candle::{CandleData, OhlcvBar};
    use bt_core::config::{Confidence, StrategyConfig};
    use bt_core::position::TradeRecord;
    use std::collections::HashSet;

    fn one_bar() -> Vec<OhlcvBar> {
        vec![OhlcvBar {
            t: 0,
            t_close: 0,
            o: 1.0,
            h: 1.0,
            l: 1.0,
            c: 1.0,
            v: 1.0,
            n: 1,
        }]
    }

    fn temp_json_path(prefix: &str) -> std::path::PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock before unix epoch")
            .as_nanos();
        std::env::temp_dir().join(format!("{prefix}_{}_{}.json", std::process::id(), nanos))
    }

    #[test]
    fn read_balance_from_json_ok() {
        let path = temp_json_path("bt_cli_balance_ok");
        std::fs::write(&path, r#"{"balance": 1234.5}"#).expect("write json");
        let got = read_balance_from_json(path.to_str().expect("utf8 path")).expect("balance parse");
        assert!((got - 1234.5).abs() < f64::EPSILON);
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn read_balance_from_json_missing_field_returns_error() {
        let path = temp_json_path("bt_cli_balance_missing");
        std::fs::write(&path, r#"{"foo": 1}"#).expect("write json");
        let err = read_balance_from_json(path.to_str().expect("utf8 path")).unwrap_err();
        assert!(err.to_string().contains("no numeric \"balance\" field"));
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn apply_alphabetical_symbol_cap_truncates_in_sort_order() {
        let mut candles: CandleData = CandleData::default();
        candles.insert("SOL".to_string(), one_bar());
        candles.insert("BTC".to_string(), one_bar());
        candles.insert("ETH".to_string(), one_bar());
        candles.insert("ADA".to_string(), one_bar());

        let changed = apply_alphabetical_symbol_cap(&mut candles, 2);
        assert_eq!(changed, Some((4, 2)));
        let mut symbols: Vec<String> = candles.keys().cloned().collect();
        symbols.sort();
        assert_eq!(symbols, vec!["ADA".to_string(), "BTC".to_string()]);
    }

    #[test]
    fn apply_alphabetical_symbol_cap_noop_when_within_cap() {
        let mut candles: CandleData = CandleData::default();
        candles.insert("BTC".to_string(), one_bar());
        candles.insert("ETH".to_string(), one_bar());
        let changed = apply_alphabetical_symbol_cap(&mut candles, 2);
        assert_eq!(changed, None);
        assert_eq!(candles.len(), 2);
    }

    fn tr(
        ts: i64,
        symbol: &str,
        action: &str,
        notional: f64,
        pnl: f64,
        fee_usd: f64,
    ) -> TradeRecord {
        TradeRecord {
            timestamp_ms: ts,
            symbol: symbol.to_string(),
            action: action.to_string(),
            price: 0.0,
            size: 0.0,
            notional,
            reason: String::new(),
            confidence: Confidence::Low,
            pnl,
            fee_usd,
            balance: 0.0,
            entry_atr: 0.0,
            leverage: 1.0,
            margin_used: 0.0,
            mae_usd: 0.0,
            mfe_usd: 0.0,
            exit_context: None,
        }
    }

    #[test]
    fn test_dump_indicators_bank_uses_threshold_ave_window() {
        let mut cfg = StrategyConfig::default();
        cfg.indicators.ave_avg_atr_window = 2;
        cfg.thresholds.entry.ave_avg_atr_window = 4;

        let mut bank = make_indicator_bank(&cfg);
        for i in 0..3 {
            bank.update(&OhlcvBar {
                t: i * 60_000,
                t_close: i * 60_000 + 59_999,
                o: 100.0 + i as f64,
                h: 101.0 + i as f64,
                l: 99.0 + i as f64,
                c: 100.5 + i as f64,
                v: 10_000.0,
                n: 100,
            });
        }
        assert!(!bank.avg_atr.full());

        bank.update(&OhlcvBar {
            t: 3 * 60_000,
            t_close: 3 * 60_000 + 59_999,
            o: 103.0,
            h: 104.0,
            l: 102.0,
            c: 103.5,
            v: 10_000.0,
            n: 100,
        });
        assert!(bank.avg_atr.full());
    }

    #[test]
    fn per_symbol_stats_include_fees_funding_and_drawdown() {
        let trades = vec![
            tr(1, "BTC", "OPEN_LONG", 100.0, 0.0, 1.0),
            tr(2, "BTC", "FUNDING", 100.0, -0.5, 0.0),
            tr(3, "BTC", "CLOSE_LONG", 100.0, 10.0, 1.0),
            tr(1, "ETH", "OPEN_SHORT", 200.0, 0.0, 0.5),
            tr(2, "ETH", "CLOSE_SHORT", 200.0, -5.0, 0.5),
        ];

        let out = build_per_symbol_stats(&trades, 10.0);
        let btc = out.get("BTC").unwrap();
        assert_eq!(btc.fills, 3);
        assert_eq!(btc.funding_events, 1);
        assert_eq!(btc.trades, 1);
        assert_eq!(btc.wins, 1);
        assert_eq!(btc.losses, 0);
        assert!((btc.realised_pnl_usd - 10.0).abs() < 1e-9);
        assert!((btc.funding_pnl_usd - (-0.5)).abs() < 1e-9);
        assert!((btc.fees_usd - 2.0).abs() < 1e-9);
        assert!((btc.net_pnl_usd - 7.5).abs() < 1e-9);
        assert!((btc.max_drawdown_usd - 1.5).abs() < 1e-9);

        let eth = out.get("ETH").unwrap();
        assert_eq!(eth.fills, 2);
        assert_eq!(eth.funding_events, 0);
        assert_eq!(eth.trades, 1);
        assert_eq!(eth.wins, 0);
        assert_eq!(eth.losses, 1);
        assert!((eth.net_pnl_usd - (-6.0)).abs() < 1e-9);
        assert!((eth.max_drawdown_usd - 6.0).abs() < 1e-9);
    }

    fn tr_full(
        ts: i64,
        symbol: &str,
        action: &str,
        price: f64,
        size: f64,
        notional: f64,
        pnl: f64,
        fee_usd: f64,
        reason: &str,
    ) -> TradeRecord {
        TradeRecord {
            timestamp_ms: ts,
            symbol: symbol.to_string(),
            action: action.to_string(),
            price,
            size,
            notional,
            reason: reason.to_string(),
            confidence: Confidence::Low,
            pnl,
            fee_usd,
            balance: 0.0,
            entry_atr: 0.0,
            leverage: 1.0,
            margin_used: 0.0,
            mae_usd: 0.0,
            mfe_usd: 0.0,
            exit_context: None,
        }
    }

    fn bar(t: i64, h: f64, l: f64) -> OhlcvBar {
        OhlcvBar {
            t,
            t_close: t,
            o: 0.0,
            h,
            l,
            c: 0.0,
            v: 0.0,
            n: 0,
        }
    }

    #[test]
    fn trade_export_is_deterministic_and_has_unique_trade_ids() {
        let mut candles: CandleData = CandleData::default();
        candles.insert(
            "BTC".to_string(),
            vec![bar(0, 110.0, 90.0), bar(3_600_000, 120.0, 80.0)],
        );

        let trades = vec![
            tr_full(
                0,
                "BTC",
                "OPEN_LONG",
                100.0,
                1.0,
                100.0,
                0.0,
                1.0,
                "High entry",
            ),
            tr_full(
                3_600_000,
                "BTC",
                "CLOSE_LONG",
                105.0,
                1.0,
                105.0,
                5.0,
                1.0,
                "Take Profit",
            ),
        ];

        let rows1 = build_trade_export_rows(&candles, &trades, None);
        let rows2 = build_trade_export_rows(&candles, &trades, None);
        assert_eq!(rows1, rows2);

        assert_eq!(rows1.len(), 1);
        let r = &rows1[0];
        assert_eq!(r.trade_id, "1:1");
        assert_eq!(r.position_id, 1);
        assert_eq!(r.symbol, "BTC");
        assert_eq!(r.side, "LONG");
        assert!((r.mae_pct - (-0.2)).abs() < 1e-9);
        assert!((r.mfe_pct - 0.2).abs() < 1e-9);
        assert_eq!(r.reason_code, "exit_take_profit");

        let mut ids = HashSet::new();
        for row in &rows1 {
            assert!(ids.insert(row.trade_id.clone()), "duplicate trade_id");
        }
    }
}
