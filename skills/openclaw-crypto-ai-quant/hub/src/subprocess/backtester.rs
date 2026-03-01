use std::process::Stdio;
use std::sync::Arc;
use tokio::process::Command;

use crate::ws::broadcast::BroadcastHub;

use super::{run_subprocess, JobId, JobStore};

/// Arguments for spawning a backtest replay.
pub struct ReplayArgs {
    pub config_path: String,
    pub initial_balance: f64,
    pub symbol: Option<String>,
    pub output_file: Option<String>,
}

/// Arguments for spawning a parameter sweep.
pub struct SweepArgs {
    pub config_path: String,
    pub sweep_spec_path: String,
    pub initial_balance: f64,
    pub output_dir: Option<String>,
}

/// Spawn a backtest replay as a subprocess.
///
/// Runs `cargo run --release --manifest-path backtester/Cargo.toml -- replay ...`
/// in the project root directory. Stdout captures JSON report, stderr streams
/// progress lines.
pub async fn spawn_replay(
    job_id: JobId,
    args: ReplayArgs,
    aiq_root: String,
    store: Arc<JobStore>,
    broadcast: BroadcastHub,
) {
    let mut cmd = Command::new("cargo");
    cmd.arg("run")
        .arg("--release")
        .arg("--manifest-path")
        .arg("backtester/Cargo.toml")
        .arg("--")
        .arg("replay")
        .arg("--config")
        .arg(&args.config_path)
        .arg("--initial-balance")
        .arg(args.initial_balance.to_string());

    if let Some(ref sym) = args.symbol {
        cmd.arg("--symbol").arg(sym);
    }

    if let Some(ref out) = args.output_file {
        cmd.arg("--output").arg(out);
    }

    cmd.current_dir(&aiq_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let jid = job_id.clone();
    tokio::spawn(async move {
        run_subprocess(jid, "backtest", cmd, store, broadcast).await;
    });
}

/// Spawn a parameter sweep as a subprocess.
pub async fn spawn_sweep(
    job_id: JobId,
    args: SweepArgs,
    aiq_root: String,
    store: Arc<JobStore>,
    broadcast: BroadcastHub,
) {
    let mut cmd = Command::new("cargo");
    cmd.arg("run")
        .arg("--release")
        .arg("--manifest-path")
        .arg("backtester/Cargo.toml")
        .arg("--")
        .arg("sweep")
        .arg("--config")
        .arg(&args.config_path)
        .arg("--sweep-spec")
        .arg(&args.sweep_spec_path)
        .arg("--initial-balance")
        .arg(args.initial_balance.to_string());

    if let Some(ref out_dir) = args.output_dir {
        cmd.arg("--output-dir").arg(out_dir);
    }

    cmd.current_dir(&aiq_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let jid = job_id.clone();
    tokio::spawn(async move {
        run_subprocess(jid, "sweep", cmd, store, broadcast).await;
    });
}
