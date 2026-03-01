//! TPE (Tree-structured Parzen Estimator) Bayesian optimization for GPU sweep.
//!
//! Uses the `tpe` crate for intelligent parameter sampling instead of grid search.
//! Each TPE trial batch is evaluated on GPU using the same all-GPU pipeline.
//!
//! **Hybrid approach**: TPE samples N configs -> GPU batch evaluate -> tell results -> repeat.
//! First batch is essentially random; subsequent batches are increasingly informed.
//!
//! **Optimization layers**:
//! - Layer 1: Fixed VRAM budget from total_vram (not fluctuating free_vram) + arena buffers
//! - Layer 2: Indicator config dedup (many TPE trials share identical rounded int params)
//! - Layer 3: TPE observation pruning (caps ask/tell complexity at O(4000))
//! - Layer 4: Double-buffer pipeline — TPE ask() overlaps with GPU evaluation

use std::collections::{BinaryHeap, HashMap};
use std::sync::Arc;
use std::time::Instant;

use bt_core::candle::{CandleData, FundingRateData};
use bt_core::config::StrategyConfig;
use bt_core::sweep::SweepSpec;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rayon::prelude::*;

use cudarc::driver::{CudaFunction, CudaSlice, LaunchAsync, LaunchConfig};

use bytemuck::Zeroable;

use crate::axis_split::INDICATOR_PATHS;
use crate::buffers;
use crate::gpu_host;
use crate::layout::{GpuSweepResult, MinPnlHeapEntry};
use crate::raw_candles;
use crate::BAR_CHUNK_SIZE;

/// Maximum TPE observations before pruning kicks in.
/// Lower = faster ask() calls (each ask is O(observations) per axis).
/// 1000 balances Bayesian quality vs ask() speed for 34-axis spaces.
const MAX_TPE_OBSERVATIONS: usize = 1000;
/// After pruning, keep only this many best observations.
const PRUNED_OBSERVATIONS: usize = 500;
const FAILED_TRIAL_TOTAL_PNL: f64 = -1.0e12;

fn checked_num_bars_u32(num_bars: usize) -> Result<u32, String> {
    u32::try_from(num_bars).map_err(|_| format!("num_bars {num_bars} exceeds u32::MAX"))
}

fn interval_to_seconds(interval: &str) -> u32 {
    let iv = interval.trim();
    if iv.is_empty() {
        return 0;
    }
    if let Some(m) = iv.strip_suffix('m').and_then(|s| s.parse::<u32>().ok()) {
        return m.saturating_mul(60);
    }
    if let Some(h) = iv.strip_suffix('h').and_then(|s| s.parse::<u32>().ok()) {
        return h.saturating_mul(3_600);
    }
    if let Some(d) = iv.strip_suffix('d').and_then(|s| s.parse::<u32>().ok()) {
        return d.saturating_mul(86_400);
    }
    0
}

fn failed_batch_results(n: usize, reason: &str) -> Vec<buffers::GpuResult> {
    eprintln!("[TPE] {reason} — marking {n} trial(s) as failed");
    let mut out = vec![buffers::GpuResult::zeroed(); n];
    for r in &mut out {
        r.total_pnl = FAILED_TRIAL_TOTAL_PNL;
    }
    out
}

/// Configuration for TPE-based sweep.
pub struct TpeConfig {
    /// Total number of trials to evaluate.
    pub trials: usize,
    /// Number of trials per GPU batch (higher = more GPU throughput, less TPE efficiency).
    pub batch_size: usize,
    /// RNG seed for reproducibility.
    pub seed: u64,
}

impl Default for TpeConfig {
    fn default() -> Self {
        Self {
            trials: 5000,
            batch_size: 256,
            seed: 42,
        }
    }
}

// =============================================================================
// Double-buffer pipeline messages
// =============================================================================

/// TPE thread → GPU thread: sampled params for one batch.
struct TpeBatchRequest {
    batch_idx: usize,
    batch_n: usize,
    trial_overrides: Vec<Vec<(String, f64)>>,
    trial_raw_values: Vec<Vec<f64>>,
}

/// GPU thread → TPE thread: evaluation results for one batch.
struct GpuBatchResult {
    #[allow(dead_code)]
    batch_idx: usize,
    results: Vec<buffers::GpuResult>,
    trial_overrides: Vec<Vec<(String, f64)>>,
    trial_raw_values: Vec<Vec<f64>>,
}

// =============================================================================
// Per-axis optimizer state
// =============================================================================

/// Type-aware axis classification for TPE sampling.
///
/// Binary/Categorical use `histogram_estimator` + `categorical_range` for clean
/// discrete sampling. Integer/Float use `parzen_estimator` + continuous `range`.
#[derive(Debug, Clone)]
enum AxisType {
    /// {0.0, 1.0} — histogram_estimator + categorical_range(2)
    Binary,
    /// N unordered choices — histogram_estimator + categorical_range(n)
    Categorical { values: Vec<f64> },
    /// Discrete integer — parzen_estimator + range, round() post-sample
    Integer,
    /// Continuous float quantized to step — parzen_estimator + range
    Float { step: f64 },
}

/// Per-axis optimizer state.
struct AxisOptimizer {
    path: String,
    min_val: f64,
    max_val: f64,
    optimizer: tpe::TpeOptimizer,
    is_indicator: bool,
    axis_type: AxisType,
    freeze_val: f64,
    gate: Option<AxisGateBinding>,
}

#[derive(Clone, Copy)]
struct AxisGateBinding {
    parent_idx: usize,
    eq: f64,
}

fn gate_is_active(axis: &AxisOptimizer, resolved_vals: &[f64]) -> bool {
    if let Some(g) = axis.gate {
        resolved_vals
            .get(g.parent_idx)
            .map_or(true, |v| (*v - g.eq).abs() < 1e-9)
    } else {
        true
    }
}

// =============================================================================
// TPE worker (runs on dedicated thread)
// =============================================================================

/// TPE worker: runs on a dedicated thread. Owns all TpeOptimizer state.
///
/// **Pre-fetch pipeline** — always stays one batch ahead of GPU:
///   1. Sample batch 0 (priming) → send to GPU
///   2. Immediately sample batch 1 (speculative, pre-fetch) → send to GPU
///   3. Wait for GPU results of batch 0
///   4. tell() batch 0 results
///   5. Sample batch 2 (now informed by batch 0) → send to GPU
///   6. Wait for GPU results of batch 1 → tell() → sample batch 3 → send ...
///   7. Repeat until all trials exhausted
///
/// GPU never starves because there's always a pre-fetched batch in the channel.
/// Quality loss: batch 1 is sampled before batch 0 results (same as random for
/// the first batch; subsequent pre-fetches lag by one tell cycle, not two).
fn tpe_worker(
    mut axis_opts: Vec<AxisOptimizer>,
    mut rng: StdRng,
    tpe_cfg_trials: usize,
    tpe_cfg_batch_size: usize,
    result_rx: crossbeam_channel::Receiver<GpuBatchResult>,
    request_tx: crossbeam_channel::Sender<Option<TpeBatchRequest>>,
) {
    let mut observation_cache: Vec<(Vec<f64>, Vec<f64>, f64)> = Vec::new();
    let mut obs_count: usize = 0;
    let mut trials_sampled: usize = 0;
    let mut batch_idx: usize = 0;
    let mut pending_results: usize = 0;

    // --- Helper: sample and send one batch if trials remain ---
    let send_batch = |axis_opts: &mut Vec<AxisOptimizer>,
                      rng: &mut StdRng,
                      trials_sampled: &mut usize,
                      batch_idx: &mut usize,
                      pending: &mut usize,
                      tx: &crossbeam_channel::Sender<Option<TpeBatchRequest>>|
     -> bool {
        if *trials_sampled >= tpe_cfg_trials {
            return false;
        }
        let batch_n = tpe_cfg_batch_size.min(tpe_cfg_trials - *trials_sampled);
        let (overrides, raw_values) = sample_batch(axis_opts, rng, batch_n);
        *trials_sampled += batch_n;

        let ok = tx
            .send(Some(TpeBatchRequest {
                batch_idx: *batch_idx,
                batch_n,
                trial_overrides: overrides,
                trial_raw_values: raw_values,
            }))
            .is_ok();
        if ok {
            *batch_idx += 1;
            *pending += 1;
        }
        ok
    };

    // --- Priming: send batch 0 ---
    send_batch(
        &mut axis_opts,
        &mut rng,
        &mut trials_sampled,
        &mut batch_idx,
        &mut pending_results,
        &request_tx,
    );

    // --- Pre-fetch: send batch 1 immediately (speculative, before any results) ---
    send_batch(
        &mut axis_opts,
        &mut rng,
        &mut trials_sampled,
        &mut batch_idx,
        &mut pending_results,
        &request_tx,
    );

    // --- Main loop: receive results, tell, pre-fetch next ---
    while pending_results > 0 {
        let gpu_result = match result_rx.recv() {
            Ok(r) => r,
            Err(_) => break,
        };
        pending_results -= 1;

        // tell() the results from the completed batch
        tell_results(
            &mut axis_opts,
            &gpu_result,
            &mut observation_cache,
            &mut obs_count,
        );

        // Pre-fetch: sample and send next batch (overlaps with GPU processing
        // the batch that's already in the channel)
        if trials_sampled < tpe_cfg_trials {
            send_batch(
                &mut axis_opts,
                &mut rng,
                &mut trials_sampled,
                &mut batch_idx,
                &mut pending_results,
                &request_tx,
            );
        }
    }

    // Signal GPU thread: no more batches
    let _ = request_tx.send(None);
}

/// Resolve a raw TPE sample to a concrete axis value.
fn resolve_raw(axis: &AxisOptimizer, raw_val: f64) -> f64 {
    match &axis.axis_type {
        AxisType::Binary => {
            let idx = raw_val.floor() as usize;
            if idx == 0 { 0.0 } else { 1.0 }
        }
        AxisType::Categorical { values } => {
            let idx = (raw_val.floor() as usize).min(values.len() - 1);
            values[idx]
        }
        AxisType::Integer => raw_val.round().clamp(axis.min_val, axis.max_val),
        AxisType::Float { step } => {
            if *step > 1e-9 {
                // Anchor quantization grid at min_val so offset value lists
                // (e.g. [28, 40, 52] with step=12) snap to their intended values
                // instead of zero-origin multiples (36, 48).
                let origin = axis.min_val;
                (((raw_val - origin) / step).round() * step + origin)
                    .clamp(axis.min_val, axis.max_val)
            } else {
                raw_val.clamp(axis.min_val, axis.max_val)
            }
        }
    }
}

/// Sample one batch of trial parameters from TPE.
///
/// **Gate-aware two-phase sampling**: ungated axes are sampled in parallel
/// (via rayon), then gated sub-axes are only sampled when their parent toggle
/// is active. This eliminates wasted TPE ask() calls on frozen sub-axes and
/// improves Bayesian convergence by not polluting the surrogate with no-op
/// samples.
fn sample_batch(
    axis_opts: &mut [AxisOptimizer],
    rng: &mut StdRng,
    batch_n: usize,
) -> (Vec<Vec<(String, f64)>>, Vec<Vec<f64>>) {
    let has_gated = axis_opts.iter().any(|a| a.gate.is_some());

    if !has_gated {
        // Fast path: no gates → parallel sample all axes (original behaviour)
        return sample_batch_ungated(axis_opts, rng, batch_n);
    }

    // Two-phase gate-aware sampling
    let n_axes = axis_opts.len();

    // Phase 1: parallel sample all axes — ungated get real ask(), gated get
    // freeze_val placeholder (will be overwritten in Phase 2 when gate is active).
    let axis_seeds: Vec<u64> = (0..n_axes).map(|_| rng.gen()).collect();

    let axis_samples: Vec<Vec<f64>> = axis_opts
        .par_iter_mut()
        .zip(axis_seeds.par_iter())
        .map(|(axis, &seed)| {
            if axis.gate.is_some() {
                // Gated axis — produce freeze_val placeholder; Phase 2 will
                // conditionally ask() only when the parent toggle is active.
                vec![axis.freeze_val; batch_n]
            } else {
                let mut local_rng = StdRng::seed_from_u64(seed);
                (0..batch_n)
                    .map(|_| {
                        if (axis.max_val - axis.min_val).abs() < 1e-12 {
                            axis.min_val
                        } else {
                            axis.optimizer.ask(&mut local_rng).unwrap()
                        }
                    })
                    .collect()
            }
        })
        .collect();

    // Resolve ungated samples into per-trial layout
    let mut raw_vals_all: Vec<Vec<f64>> = vec![vec![0.0; n_axes]; batch_n];
    let mut resolved_all: Vec<Vec<f64>> = vec![vec![0.0; n_axes]; batch_n];

    for a in 0..n_axes {
        for t in 0..batch_n {
            let raw = axis_samples[a][t];
            raw_vals_all[t][a] = raw;
            resolved_all[t][a] = resolve_raw(&axis_opts[a], raw);
        }
    }

    // Phase 2: sequentially sample gated axes — only ask() when gate is active.
    // This avoids wasting TPE ask() calls on sub-axes whose parent toggle is OFF.
    for a in 0..n_axes {
        let gate = match axis_opts[a].gate {
            Some(g) => g,
            None => continue,
        };
        debug_assert!(
            gate.parent_idx < a || axis_opts[gate.parent_idx].gate.is_none(),
            "gate parent axis [{}] '{}' must be ungated or precede child axis [{}] '{}' \
             — check YAML axis ordering",
            gate.parent_idx,
            axis_opts[gate.parent_idx].path,
            a,
            axis_opts[a].path,
        );
        for t in 0..batch_n {
            let parent_val = resolved_all[t][gate.parent_idx];
            let gate_active = (parent_val - gate.eq).abs() < 1e-9;

            if gate_active && (axis_opts[a].max_val - axis_opts[a].min_val).abs() >= 1e-12 {
                // Gate is active — ask TPE for an informed sample
                let raw = axis_opts[a].optimizer.ask(rng).unwrap();
                raw_vals_all[t][a] = raw;
                resolved_all[t][a] = resolve_raw(&axis_opts[a], raw);
            } else {
                // Gate is inactive — keep freeze_val from Phase 1
                let freeze = axis_opts[a].freeze_val;
                raw_vals_all[t][a] = freeze;
                resolved_all[t][a] = freeze;
            }
        }
    }

    // Build output
    let mut trial_overrides: Vec<Vec<(String, f64)>> = Vec::with_capacity(batch_n);
    let mut trial_raw_values: Vec<Vec<f64>> = Vec::with_capacity(batch_n);

    for t in 0..batch_n {
        let mut overrides = Vec::with_capacity(n_axes);
        for (a, axis) in axis_opts.iter().enumerate() {
            overrides.push((axis.path.clone(), resolved_all[t][a]));
        }
        trial_overrides.push(overrides);
        trial_raw_values.push(raw_vals_all[t].clone());
    }

    (trial_overrides, trial_raw_values)
}

/// Fast path: sample all axes in parallel (no gate dependencies).
fn sample_batch_ungated(
    axis_opts: &mut [AxisOptimizer],
    rng: &mut StdRng,
    batch_n: usize,
) -> (Vec<Vec<(String, f64)>>, Vec<Vec<f64>>) {
    let axis_seeds: Vec<u64> = (0..axis_opts.len()).map(|_| rng.gen()).collect();

    let axis_samples: Vec<Vec<f64>> = axis_opts
        .par_iter_mut()
        .zip(axis_seeds.par_iter())
        .map(|(axis, &seed)| {
            let mut local_rng = StdRng::seed_from_u64(seed);
            (0..batch_n)
                .map(|_| {
                    if (axis.max_val - axis.min_val).abs() < 1e-12 {
                        axis.min_val
                    } else {
                        axis.optimizer.ask(&mut local_rng).unwrap()
                    }
                })
                .collect()
        })
        .collect();

    let mut trial_overrides: Vec<Vec<(String, f64)>> = Vec::with_capacity(batch_n);
    let mut trial_raw_values: Vec<Vec<f64>> = Vec::with_capacity(batch_n);

    for t in 0..batch_n {
        let mut raw_vals = Vec::with_capacity(axis_opts.len());
        let mut resolved_vals = Vec::with_capacity(axis_opts.len());

        for (a, axis) in axis_opts.iter().enumerate() {
            let raw_val = axis_samples[a][t];
            raw_vals.push(raw_val);
            resolved_vals.push(resolve_raw(axis, raw_val));
        }

        let mut overrides = Vec::with_capacity(axis_opts.len());
        for (axis, value) in axis_opts.iter().zip(resolved_vals.iter()) {
            overrides.push((axis.path.clone(), *value));
        }

        trial_overrides.push(overrides);
        trial_raw_values.push(raw_vals);
    }

    (trial_overrides, trial_raw_values)
}

/// Process GPU results: tell TPE + prune observations.
fn tell_results(
    axis_opts: &mut [AxisOptimizer],
    gpu_result: &GpuBatchResult,
    observation_cache: &mut Vec<(Vec<f64>, Vec<f64>, f64)>,
    obs_count: &mut usize,
) {
    for (i, result) in gpu_result.results.iter().enumerate() {
        let pnl = result.total_pnl as f64;
        let objective = if crate::is_degenerate_overrides(&gpu_result.trial_overrides[i]) {
            1e18
        } else {
            let trade_penalty = if result.total_trades < 20 { 0.5 } else { 1.0 };
            -(pnl * trade_penalty)
        };
        let resolved_vals: Vec<f64> = gpu_result.trial_overrides[i]
            .iter()
            .map(|(_, v)| *v)
            .collect();

        for (j, axis) in axis_opts.iter_mut().enumerate() {
            if (axis.max_val - axis.min_val).abs() < 1e-12 {
                continue;
            }
            if !gate_is_active(axis, &resolved_vals) {
                continue;
            }
            let _ = axis
                .optimizer
                .tell(gpu_result.trial_raw_values[i][j], objective);
        }

        observation_cache.push((
            gpu_result.trial_raw_values[i].clone(),
            resolved_vals,
            objective,
        ));
        *obs_count += 1;
    }

    // Layer 3: TPE observation pruning
    if *obs_count > MAX_TPE_OBSERVATIONS {
        let t_prune = Instant::now();

        observation_cache
            .sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
        observation_cache.truncate(PRUNED_OBSERVATIONS);
        *obs_count = observation_cache.len();

        for axis in axis_opts.iter_mut() {
            if (axis.max_val - axis.min_val).abs() < 1e-12 {
                continue;
            }
            axis.optimizer = make_optimizer(&axis.axis_type, axis.min_val, axis.max_val);
        }

        for (raw_vals, resolved_vals, objective) in observation_cache.iter() {
            for (j, axis) in axis_opts.iter_mut().enumerate() {
                if (axis.max_val - axis.min_val).abs() < 1e-12 {
                    continue;
                }
                if !gate_is_active(axis, resolved_vals) {
                    continue;
                }
                let _ = axis.optimizer.tell(raw_vals[j], *objective);
            }
        }

        let prune_ms = t_prune.elapsed().as_millis();
        eprintln!(
            "[TPE] Pruned observations: {} -> {} ({}ms)",
            MAX_TPE_OBSERVATIONS, PRUNED_OBSERVATIONS, prune_ms,
        );
    }
}

// =============================================================================
// GPU-side result builder
// =============================================================================

/// Build GpuSweepResult entries from raw GPU results + trial overrides.
fn build_sweep_results(
    gpu_results: &[buffers::GpuResult],
    trial_overrides: &[Vec<(String, f64)>],
    best_pnl: &mut f64,
    best_trial: &mut usize,
    trials_done: usize,
) -> Vec<GpuSweepResult> {
    let mut out = Vec::with_capacity(gpu_results.len());

    for (i, result) in gpu_results.iter().enumerate() {
        let pnl = result.total_pnl as f64;
        let overrides = &trial_overrides[i];

        let config_id = overrides
            .iter()
            .map(|(k, v)| format!("{}={}", k, v))
            .collect::<Vec<_>>()
            .join(",");

        let pf = if result.gross_loss.abs() > 0.001 {
            result.gross_profit as f64 / result.gross_loss.abs() as f64
        } else if result.gross_profit > 0.0 {
            999.0
        } else {
            0.0
        };

        let wr = if result.total_trades > 0 {
            result.total_wins as f64 / result.total_trades as f64
        } else {
            0.0
        };

        if pnl > *best_pnl {
            *best_pnl = pnl;
            *best_trial = trials_done + i;
        }

        out.push(GpuSweepResult {
            config_id,
            output_mode: "gpu_tpe".to_string(),
            total_pnl: pnl,
            final_balance: result.final_balance as f64,
            total_trades: result.total_trades,
            total_wins: result.total_wins,
            win_rate: wr,
            profit_factor: pf,
            max_drawdown_pct: result.max_drawdown_pct as f64,
            overrides: overrides.clone(),
        });
    }

    out
}

// =============================================================================
// Main entry point
// =============================================================================

/// Run a TPE-guided GPU sweep with double-buffer pipeline.
///
/// TPE sampling (CPU) overlaps with GPU evaluation using a dedicated TPE thread
/// and crossbeam channels. Protocol:
///   1. TPE thread samples batch 0 (priming)
///   2. GPU evaluates batch 0 while TPE thread idles
///   3. GPU sends results → TPE thread tells batch 0, samples batch 1
///   4. GPU evaluates batch 1 while TPE samples batch 2 (full overlap)
///   5. Repeat until all trials done
pub fn run_tpe_sweep(
    candles: &CandleData,
    base_cfg: &StrategyConfig,
    spec: &SweepSpec,
    funding: Option<&FundingRateData>,
    tpe_cfg: &TpeConfig,
    sub_candles: Option<&CandleData>,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
    top_k: usize,
) -> Vec<GpuSweepResult> {
    let rng = StdRng::seed_from_u64(tpe_cfg.seed);
    let axis_idx_by_path: HashMap<&str, usize> = spec
        .axes
        .iter()
        .enumerate()
        .map(|(i, axis)| (axis.path.as_str(), i))
        .collect();

    // -- 1. Create per-axis TPE optimizers ----------------------------------------
    let mut axis_opts: Vec<AxisOptimizer> = Vec::new();
    for axis in &spec.axes {
        let min_val = axis.values.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_val = axis
            .values
            .iter()
            .cloned()
            .fold(f64::NEG_INFINITY, f64::max);
        let freeze_val = axis.values.first().copied().unwrap_or(min_val);
        let gate = axis.gate.as_ref().and_then(|g| {
            axis_idx_by_path
                .get(g.path.as_str())
                .copied()
                .map(|parent_idx| AxisGateBinding { parent_idx, eq: g.eq })
        });

        let axis_type = classify_axis(&axis.path, &axis.values);

        if (max_val - min_val).abs() < 1e-12 {
            // Single-value axis: dummy optimizer (never sampled meaningfully)
            axis_opts.push(AxisOptimizer {
                path: axis.path.clone(),
                min_val,
                max_val,
                optimizer: tpe::TpeOptimizer::new(
                    tpe::parzen_estimator(),
                    tpe::range(min_val - 0.5, max_val + 0.5).unwrap(),
                ),
                is_indicator: is_indicator_path(&axis.path),
                axis_type,
                freeze_val,
                gate,
            });
            continue;
        }

        let optimizer = make_optimizer(&axis_type, min_val, max_val);

        axis_opts.push(AxisOptimizer {
            path: axis.path.clone(),
            min_val,
            max_val,
            optimizer,
            is_indicator: is_indicator_path(&axis.path),
            axis_type,
            freeze_val,
            gate,
        });
    }

    let has_indicator_axes = axis_opts.iter().any(|a| a.is_indicator);
    let gated_axes = axis_opts.iter().filter(|a| a.gate.is_some()).count();

    let n_binary = axis_opts
        .iter()
        .filter(|a| matches!(a.axis_type, AxisType::Binary))
        .count();
    let n_cat = axis_opts
        .iter()
        .filter(|a| matches!(a.axis_type, AxisType::Categorical { .. }))
        .count();
    let n_int = axis_opts
        .iter()
        .filter(|a| matches!(a.axis_type, AxisType::Integer))
        .count();
    let n_float = axis_opts
        .iter()
        .filter(|a| matches!(a.axis_type, AxisType::Float { .. }))
        .count();

    eprintln!(
        "[TPE] {} axes ({} indicator, {} trade, {} gated), {} trials, batch={}",
        axis_opts.len(),
        axis_opts.iter().filter(|a| a.is_indicator).count(),
        axis_opts.iter().filter(|a| !a.is_indicator).count(),
        gated_axes,
        tpe_cfg.trials,
        tpe_cfg.batch_size,
    );
    eprintln!(
        "[TPE] Axis types: {} binary, {} categorical, {} integer, {} float",
        n_binary, n_cat, n_int, n_float,
    );
    for a in &axis_opts {
        let type_tag = match &a.axis_type {
            AxisType::Binary => "(binary)".to_string(),
            AxisType::Categorical { values } => format!("(cat/{})", values.len()),
            AxisType::Integer => "(int)".to_string(),
            AxisType::Float { step } => format!("(float step={:.6})", step),
        };
        eprintln!(
            "  - {} [{:.4}..{:.4}] {}{}",
            a.path,
            a.min_val,
            a.max_val,
            if a.is_indicator { "(indicator) " } else { "" },
            type_tag,
        );
    }

    // -- 2. Init GPU, upload raw candles ------------------------------------------
    let symbols = crate::sorted_symbols_with_kernel_cap(candles, "[TPE]");
    let num_symbols = symbols.len();
    let btc_sym_idx = symbols
        .iter()
        .position(|s| s == "BTC")
        .or_else(|| symbols.iter().position(|s| s == "BTCUSDT"))
        .and_then(|idx| u32::try_from(idx).ok())
        .unwrap_or(u32::MAX);
    let paxg_sym_idx = symbols
        .iter()
        .position(|s| s == "PAXG")
        .or_else(|| symbols.iter().position(|s| s == "PAXGUSDT"))
        .and_then(|idx| u32::try_from(idx).ok())
        .unwrap_or(u32::MAX);

    let raw = raw_candles::prepare_raw_candles(candles, &symbols);
    let num_bars = match checked_num_bars_u32(raw.num_bars) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("[TPE] {e} — returning empty results");
            return Vec::new();
        }
    };

    let (trade_start, trade_end) =
        raw_candles::find_trade_bar_range(&raw.timestamps, from_ts, to_ts);
    let funding_events_host = funding.map(|fr| {
        raw_candles::prepare_funding_event_buffers(fr, &raw.timestamps, &symbols)
    });
    eprintln!(
        "[TPE] Trade bar range: {}..{} ({} of {} bars)",
        trade_start,
        trade_end,
        trade_end - trade_start,
        num_bars,
    );

    // C6: graceful fallback — return empty results if GPU init fails
    let device_state = match gpu_host::GpuDeviceState::new() {
        Ok(ds) => ds,
        Err(e) => {
            eprintln!("[TPE] {e} — GPU sweep unavailable, returning empty results");
            return Vec::new();
        }
    };
    let candles_gpu = match device_state.dev.htod_sync_copy(&raw.candles) {
        Ok(buf) => buf,
        Err(e) => {
            eprintln!("[TPE] GPU candle upload failed: {e} — returning empty results");
            return Vec::new();
        }
    };
    let (funding_spans_gpu, funding_rates_gpu): (
        Option<Arc<cudarc::driver::CudaSlice<buffers::GpuFundingSpan>>>,
        Option<Arc<cudarc::driver::CudaSlice<f64>>>,
    ) = if let Some(funding_events) = funding_events_host.as_ref() {
        let active_slots = funding_events.spans.iter().filter(|span| span.len > 0).count();
        if funding_events.rates.is_empty() || active_slots == 0 {
            eprintln!(
                "[TPE] Funding DB provided but no hourly settlements in scoped range; funding kernel path disabled"
            );
            (None, None)
        } else {
            let spans_gpu = match device_state.dev.htod_sync_copy(&funding_events.spans) {
                Ok(buf) => buf,
                Err(e) => {
                    eprintln!("[TPE] Funding span upload failed: {e} — returning empty results");
                    return Vec::new();
                }
            };
            let rates_gpu = match device_state.dev.htod_sync_copy(&funding_events.rates) {
                Ok(buf) => buf,
                Err(e) => {
                    eprintln!("[TPE] Funding rate upload failed: {e} — returning empty results");
                    return Vec::new();
                }
            };
            eprintln!(
                "[TPE] Funding settlements prepared: {} events across {} active bar-symbol slots",
                funding_events.rates.len(),
                active_slots
            );
            (Some(Arc::new(spans_gpu)), Some(Arc::new(rates_gpu)))
        }
    } else {
        (None, None)
    };

    let sub_bar_result =
        sub_candles.map(|sc| raw_candles::prepare_sub_bar_candles(&raw.timestamps, sc, &symbols));
    let sub_candles_gpu: Option<Arc<cudarc::driver::CudaSlice<buffers::GpuRawCandle>>> =
        sub_bar_result.as_ref().and_then(|sbr| {
            if sbr.max_sub_per_bar == 0 || sbr.candles.is_empty() {
                None
            } else {
                match device_state.dev.htod_sync_copy(&sbr.candles) {
                    Ok(buf) => Some(Arc::new(buf)),
                    Err(e) => {
                        eprintln!("[TPE] GPU sub-candle upload failed: {e}");
                        None
                    }
                }
            }
        });
    let sub_counts_gpu: Option<Arc<cudarc::driver::CudaSlice<u32>>> =
        sub_bar_result.as_ref().and_then(|sbr| {
            if sbr.max_sub_per_bar == 0 || sbr.sub_counts.is_empty() {
                None
            } else {
                match device_state.dev.htod_sync_copy(&sbr.sub_counts) {
                    Ok(buf) => Some(Arc::new(buf)),
                    Err(e) => {
                        eprintln!("[TPE] GPU sub-counts upload failed: {e}");
                        None
                    }
                }
            }
        });
    let max_sub_per_bar = sub_bar_result
        .as_ref()
        .map(|sbr| sbr.max_sub_per_bar)
        .unwrap_or(0);

    if max_sub_per_bar > 0 {
        eprintln!(
            "[TPE] Sub-bar candles: max_sub={}, GPU buffer uploaded",
            max_sub_per_bar,
        );
    }

    // CPU scope guard skips bars with ts < from_ts before sub-bar processing.
    // Keep kernel start aligned to scoped trade_start; do not step back one bar.
    let trade_start_for_kernel = trade_start;

    eprintln!(
        "[TPE] {} bars x {} symbols, CUDA device ready",
        num_bars, num_symbols,
    );

    // Fee rates from bt_core accounting constants (H9: not hardcoded)
    let maker_fee_rate = bt_core::accounting::DEFAULT_MAKER_FEE_RATE as f32;
    let taker_fee_rate = bt_core::accounting::DEFAULT_TAKER_FEE_RATE as f32;

    // -- Layer 1: Fixed VRAM budget from total_vram (40%) -------------------------
    let num_symbols_u32 = match u32::try_from(num_symbols) {
        Ok(v) => v,
        Err(_) => {
            eprintln!("[TPE] num_symbols {num_symbols} exceeds u32::MAX — returning empty results");
            return Vec::new();
        }
    };
    let total_vram = device_state.total_vram_bytes();
    let snapshot_stride = (num_bars as usize) * (num_symbols as usize);
    let breadth_stride = num_bars as usize;

    let snap_bytes_per_ind = snapshot_stride * std::mem::size_of::<buffers::GpuSnapshot>();
    let breadth_bytes_per_ind = breadth_stride * std::mem::size_of::<f32>();
    let btc_bytes_per_ind = breadth_stride * std::mem::size_of::<u32>();
    let ind_bytes_per_slot = snap_bytes_per_ind + breadth_bytes_per_ind + btc_bytes_per_ind;

    let vram_budget = 22usize * 1024 * 1024 * 1024;
    let arena_cap = if ind_bytes_per_slot > 0 {
        (vram_budget / ind_bytes_per_slot).max(1)
    } else {
        tpe_cfg.batch_size
    };

    let arena_cap = if snap_bytes_per_ind > 0 {
        let max_by_alloc = (20usize * 1024 * 1024 * 1024) / snap_bytes_per_ind;
        arena_cap.min(max_by_alloc).max(1)
    } else {
        arena_cap
    };

    eprintln!(
        "[TPE] VRAM budget: {:.1} GB (of {:.1} GB total), arena_cap={} ind slots ({:.1} MB/slot)",
        vram_budget as f64 / 1e9,
        total_vram as f64 / 1e9,
        arena_cap,
        ind_bytes_per_slot as f64 / 1e6,
    );

    // Pre-allocate arena buffers
    let mut snap_arena: CudaSlice<buffers::GpuSnapshot> = match device_state
        .dev
        .alloc_zeros::<buffers::GpuSnapshot>(arena_cap * snapshot_stride)
    {
        Ok(buf) => buf,
        Err(e) => {
            eprintln!("[TPE] GPU arena alloc (snapshots) failed: {e} — returning empty results");
            return Vec::new();
        }
    };
    let mut breadth_arena: CudaSlice<f32> = match device_state
        .dev
        .alloc_zeros::<f32>(arena_cap * breadth_stride)
    {
        Ok(buf) => buf,
        Err(e) => {
            eprintln!("[TPE] GPU arena alloc (breadth) failed: {e} — returning empty results");
            return Vec::new();
        }
    };
    let mut btc_arena: CudaSlice<u32> = match device_state
        .dev
        .alloc_zeros::<u32>(arena_cap * breadth_stride)
    {
        Ok(buf) => buf,
        Err(e) => {
            eprintln!("[TPE] GPU arena alloc (btc) failed: {e} — returning empty results");
            return Vec::new();
        }
    };

    // -- 3. Double-buffer pipeline ------------------------------------------------
    // Request channel: bounded(2) so TPE can always have one pre-fetched batch
    // queued while GPU processes the current one. This is the core of the
    // double-buffer: GPU finishes → immediately grabs pre-fetched batch → zero stall.
    let (request_tx, request_rx) = crossbeam_channel::bounded::<Option<TpeBatchRequest>>(2);
    let (result_tx, result_rx) = crossbeam_channel::bounded::<GpuBatchResult>(1);

    let tpe_trials = tpe_cfg.trials;
    let tpe_batch_size = tpe_cfg.batch_size;

    // Spawn TPE thread — takes ownership of axis_opts + rng
    let tpe_handle = match std::thread::Builder::new()
        .name("tpe-sampler".into())
        .spawn(move || {
            tpe_worker(
                axis_opts,
                rng,
                tpe_trials,
                tpe_batch_size,
                result_rx,
                request_tx,
            );
        }) {
        Ok(handle) => handle,
        Err(e) => {
            eprintln!("[TPE] Failed to spawn TPE thread: {e} — returning empty results");
            return Vec::new();
        }
    };

    // GPU thread: receive batches, evaluate, send results
    // Bounded top-K heap: keeps only the best results by PnL to prevent OOM
    let effective_top_k = if top_k == 0 { usize::MAX } else { top_k };
    let mut top_heap: BinaryHeap<MinPnlHeapEntry> =
        BinaryHeap::with_capacity(effective_top_k.min(tpe_cfg.trials).min(100_000) + 1);
    let mut best_pnl = f64::NEG_INFINITY;
    let mut best_trial = 0usize;
    let mut trials_done = 0usize;

    eprintln!("[TPE] Pipeline mode: double-buffer (TPE thread + GPU thread)");

    while let Ok(Some(request)) = request_rx.recv() {
        let t_gpu = Instant::now();

        // Evaluate batch on GPU
        let gpu_results = if has_indicator_axes {
            evaluate_mixed_batch_arena(
                &device_state,
                &candles_gpu,
                base_cfg,
                &request.trial_overrides,
                num_bars,
                num_symbols_u32,
                btc_sym_idx,
                paxg_sym_idx,
                spec.lookback,
                spec.initial_balance as f32,
                maker_fee_rate,
                taker_fee_rate,
                arena_cap,
                snapshot_stride,
                breadth_stride,
                &mut snap_arena,
                &mut breadth_arena,
                &mut btc_arena,
                max_sub_per_bar,
                sub_candles_gpu.as_deref(),
                sub_counts_gpu.as_deref(),
                funding_spans_gpu.as_deref(),
                funding_rates_gpu.as_deref(),
                trade_start_for_kernel,
                trade_end,
            )
        } else {
            evaluate_trade_only_batch(
                &device_state,
                &candles_gpu,
                base_cfg,
                &request.trial_overrides,
                num_bars,
                num_symbols_u32,
                btc_sym_idx,
                paxg_sym_idx,
                spec.lookback,
                spec.initial_balance as f32,
                maker_fee_rate,
                taker_fee_rate,
                max_sub_per_bar,
                sub_candles_gpu.as_ref(),
                sub_counts_gpu.as_ref(),
                funding_spans_gpu.as_ref(),
                funding_rates_gpu.as_ref(),
                trade_start_for_kernel,
                trade_end,
            )
        };

        let gpu_ms = t_gpu.elapsed().as_millis();

        // Build GpuSweepResult on GPU thread (no need to send back through channel)
        let batch_results = build_sweep_results(
            &gpu_results,
            &request.trial_overrides,
            &mut best_pnl,
            &mut best_trial,
            trials_done,
        );

        trials_done += request.batch_n;

        eprintln!(
            "[TPE] {}/{} trials done, best PnL: ${:.2} (trial #{}) | gpu={}ms batch={}",
            trials_done, tpe_trials, best_pnl, best_trial, gpu_ms, request.batch_idx,
        );

        for r in batch_results {
            if top_heap.len() < effective_top_k {
                top_heap.push(MinPnlHeapEntry(r));
            } else if let Some(worst) = top_heap.peek() {
                if r.total_pnl > worst.0.total_pnl || worst.0.total_pnl.is_nan() {
                    top_heap.pop();
                    top_heap.push(MinPnlHeapEntry(r));
                }
            }
        }

        // Send results to TPE thread (tell + ask next batch)
        // This returns immediately — TPE thread will process while we wait for next request
        if result_tx
            .send(GpuBatchResult {
                batch_idx: request.batch_idx,
                results: gpu_results,
                trial_overrides: request.trial_overrides,
                trial_raw_values: request.trial_raw_values,
            })
            .is_err()
        {
            break; // TPE thread exited
        }
    }

    // Wait for TPE thread to finish; if it panics, keep and return collected GPU results.
    if let Err(panic_payload) = tpe_handle.join() {
        let panic_msg = if let Some(msg) = panic_payload.downcast_ref::<&str>() {
            *msg
        } else if let Some(msg) = panic_payload.downcast_ref::<String>() {
            msg.as_str()
        } else {
            "<non-string panic payload>"
        };
        eprintln!(
            "[TPE] sampler thread panicked: {panic_msg}; returning {} collected results",
            top_heap.len()
        );
    }

    // Drain heap and sort by PnL descending
    let mut results: Vec<GpuSweepResult> = top_heap.into_iter().map(|e| e.0).collect();
    results.sort_by(|a, b| {
        b.total_pnl
            .partial_cmp(&a.total_pnl)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

// =============================================================================
// GPU batch evaluation helpers
// =============================================================================

/// Evaluate a batch of trials where all share the same indicator config
/// (no indicator axes in the sweep). Single indicator dispatch, N trade combos.
fn evaluate_trade_only_batch(
    ds: &gpu_host::GpuDeviceState,
    candles_gpu: &CudaSlice<buffers::GpuRawCandle>,
    base_cfg: &StrategyConfig,
    trial_overrides: &[Vec<(String, f64)>],
    num_bars: u32,
    num_symbols: u32,
    btc_sym_idx: u32,
    paxg_sym_idx: u32,
    lookback: usize,
    initial_balance: f32,
    maker_fee_rate: f32,
    taker_fee_rate: f32,
    max_sub_per_bar: u32,
    sub_candles_gpu: Option<&Arc<CudaSlice<buffers::GpuRawCandle>>>,
    sub_counts_gpu: Option<&Arc<CudaSlice<u32>>>,
    funding_spans_gpu: Option<&Arc<CudaSlice<buffers::GpuFundingSpan>>>,
    funding_rates_gpu: Option<&Arc<CudaSlice<f64>>>,
    trade_start: u32,
    trade_end: u32,
) -> Vec<buffers::GpuResult> {
    let trial_n = trial_overrides.len();
    let entry_interval_sec = interval_to_seconds(&base_cfg.engine.entry_interval);
    let signal_on_candle_close = if base_cfg.engine.signal_on_candle_close {
        1
    } else {
        0
    };
    let ind_config = buffers::GpuIndicatorConfig::from_strategy_config(base_cfg, lookback);

    // H11: handle GPU memory allocation failure gracefully
    let mut ind_bufs = match gpu_host::IndicatorBuffers::new(
        ds,
        candles_gpu,
        &[ind_config],
        num_bars,
        num_symbols,
        btc_sym_idx,
        paxg_sym_idx,
    ) {
        Ok(bufs) => bufs,
        Err(e) => {
            return failed_batch_results(
                trial_n,
                &format!("Indicator buffer allocation failed: {e}"),
            );
        }
    };
    if let Err(e) = gpu_host::dispatch_indicator_kernels(ds, &mut ind_bufs) {
        return failed_batch_results(trial_n, &format!("Indicator kernel dispatch failed: {e}"));
    }

    let mut gpu_configs: Vec<buffers::GpuComboConfig> = Vec::with_capacity(trial_overrides.len());
    for overrides in trial_overrides {
        let mut cfg = base_cfg.clone();
        for (path, value) in overrides {
            bt_core::sweep::apply_one_pub(&mut cfg, path, *value);
        }
        let mut gpu_cfg = match buffers::GpuComboConfig::from_strategy_config(&cfg) {
            Ok(v) => v,
            Err(e) => {
                return failed_batch_results(
                    trial_n,
                    &format!("GpuComboConfig conversion failed: {e}"),
                );
            }
        };
        gpu_cfg.snapshot_offset = 0;
        gpu_cfg.breadth_offset = 0;
        gpu_configs.push(gpu_cfg);
    }

    let mut trade_bufs = match gpu_host::BatchBuffers::from_indicator_buffers(
        ds,
        &ind_bufs,
        &gpu_configs,
        initial_balance,
        0,
        maker_fee_rate,
        taker_fee_rate,
    ) {
        Ok(bufs) => bufs,
        Err(e) => {
            return failed_batch_results(trial_n, &format!("Trade buffer allocation failed: {e}"));
        }
    };
    trade_bufs.max_sub_per_bar = max_sub_per_bar;
    trade_bufs.entry_interval_sec = entry_interval_sec;
    trade_bufs.signal_on_candle_close = signal_on_candle_close;
    // Arc clone only bumps refcount; avoids cudarc CudaSlice device-to-device copy.
    trade_bufs.sub_candles = sub_candles_gpu.cloned();
    trade_bufs.sub_counts = sub_counts_gpu.cloned();
    trade_bufs.funding_spans = funding_spans_gpu.cloned();
    trade_bufs.funding_rates = funding_rates_gpu.cloned();

    match gpu_host::dispatch_and_readback(
        ds,
        &mut trade_bufs,
        num_bars,
        BAR_CHUNK_SIZE,
        trade_start,
        trade_end,
    ) {
        Ok(r) => r,
        Err(e) => failed_batch_results(
            trial_n,
            &format!("Trade kernel dispatch/readback failed: {e}"),
        ),
    }
}

/// Evaluate a batch of trials where indicator params may vary per trial.
/// Uses Layer 1 (arena buffers) + Layer 2 (indicator config dedup).
fn evaluate_mixed_batch_arena(
    ds: &gpu_host::GpuDeviceState,
    candles_gpu: &CudaSlice<buffers::GpuRawCandle>,
    base_cfg: &StrategyConfig,
    trial_overrides: &[Vec<(String, f64)>],
    num_bars: u32,
    num_symbols: u32,
    btc_sym_idx: u32,
    paxg_sym_idx: u32,
    lookback: usize,
    initial_balance: f32,
    maker_fee_rate: f32,
    taker_fee_rate: f32,
    arena_cap: usize,
    snapshot_stride: usize,
    breadth_stride: usize,
    snap_arena: &mut CudaSlice<buffers::GpuSnapshot>,
    breadth_arena: &mut CudaSlice<f32>,
    btc_arena: &mut CudaSlice<u32>,
    max_sub_per_bar: u32,
    sub_candles_gpu: Option<&CudaSlice<buffers::GpuRawCandle>>,
    sub_counts_gpu: Option<&CudaSlice<u32>>,
    funding_spans_gpu: Option<&CudaSlice<buffers::GpuFundingSpan>>,
    funding_rates_gpu: Option<&CudaSlice<f64>>,
    trade_start: u32,
    trade_end: u32,
) -> Vec<buffers::GpuResult> {
    let n = trial_overrides.len();

    let trial_cfgs: Vec<StrategyConfig> = trial_overrides
        .iter()
        .map(|overrides| {
            let mut cfg = base_cfg.clone();
            for (path, value) in overrides {
                bt_core::sweep::apply_one_pub(&mut cfg, path, *value);
            }
            cfg
        })
        .collect();

    let trial_ind_cfgs: Vec<buffers::GpuIndicatorConfig> = trial_cfgs
        .iter()
        .map(|cfg| buffers::GpuIndicatorConfig::from_strategy_config(cfg, lookback))
        .collect();

    // Layer 2: Indicator config dedup
    let mut dedup_map: HashMap<[u8; 80], usize> = HashMap::new();
    let mut unique_ind_cfgs: Vec<buffers::GpuIndicatorConfig> = Vec::new();
    let mut trial_to_unique: Vec<usize> = Vec::with_capacity(n);

    for ind_cfg in &trial_ind_cfgs {
        let bytes: &[u8] = bytemuck::bytes_of(ind_cfg);
        let mut key = [0u8; 80];
        key.copy_from_slice(bytes);

        let unique_idx = if let Some(&idx) = dedup_map.get(&key) {
            idx
        } else {
            let idx = unique_ind_cfgs.len();
            dedup_map.insert(key, idx);
            unique_ind_cfgs.push(*ind_cfg);
            idx
        };
        trial_to_unique.push(unique_idx);
    }

    let num_unique = unique_ind_cfgs.len();
    if num_unique < n {
        eprintln!(
            "[TPE-dedup] {} trials -> {} unique indicator configs ({:.0}% dedup)",
            n,
            num_unique,
            (1.0 - num_unique as f64 / n as f64) * 100.0,
        );
    }

    let mut all_results: Vec<buffers::GpuResult> = vec![buffers::GpuResult::zeroed(); n];

    let num_groups = (num_unique + arena_cap - 1) / arena_cap;
    for group_idx in 0..num_groups {
        let group_start = group_idx * arena_cap;
        let group_end = (group_start + arena_cap).min(num_unique);
        let group_ind_cfgs = &unique_ind_cfgs[group_start..group_end];

        if let Err(e) = dispatch_indicator_arena(
            ds,
            candles_gpu,
            group_ind_cfgs,
            num_bars,
            num_symbols,
            btc_sym_idx,
            snap_arena,
            breadth_arena,
            btc_arena,
        ) {
            eprintln!("[TPE] Indicator arena dispatch failed: {e} — skipping group");
            continue;
        }

        let mut group_trial_indices: Vec<usize> = Vec::new();
        let mut gpu_configs: Vec<buffers::GpuComboConfig> = Vec::new();

        for (trial_idx, &unique_slot) in trial_to_unique.iter().enumerate() {
            if unique_slot >= group_start && unique_slot < group_end {
                let local_slot = unique_slot - group_start;
                let mut gpu_cfg =
                    match buffers::GpuComboConfig::from_strategy_config(&trial_cfgs[trial_idx]) {
                        Ok(v) => v,
                        Err(e) => {
                            return failed_batch_results(
                                n,
                                &format!("GpuComboConfig conversion failed: {e}"),
                            );
                        }
                    };
                gpu_cfg.snapshot_offset = match u32::try_from(local_slot * snapshot_stride) {
                    Ok(v) => v,
                    Err(_) => {
                        return failed_batch_results(
                            n,
                            &format!(
                                "snapshot_offset {} exceeds u32::MAX",
                                local_slot * snapshot_stride
                            ),
                        );
                    }
                };
                gpu_cfg.breadth_offset = match u32::try_from(local_slot * breadth_stride) {
                    Ok(v) => v,
                    Err(_) => {
                        return failed_batch_results(
                            n,
                            &format!(
                                "breadth_offset {} exceeds u32::MAX",
                                local_slot * breadth_stride
                            ),
                        );
                    }
                };
                gpu_configs.push(gpu_cfg);
                group_trial_indices.push(trial_idx);
            }
        }

        if gpu_configs.is_empty() {
            continue;
        }

        let first_trial_cfg = &trial_cfgs[group_trial_indices[0]];
        let entry_interval_sec = interval_to_seconds(&first_trial_cfg.engine.entry_interval);
        let signal_on_candle_close = if first_trial_cfg.engine.signal_on_candle_close {
            1
        } else {
            0
        };

        let trade_results = match dispatch_trade_arena(
            ds,
            candles_gpu,
            snap_arena,
            breadth_arena,
            btc_arena,
            &gpu_configs,
            initial_balance,
            num_symbols,
            btc_sym_idx,
            paxg_sym_idx,
            num_bars,
            maker_fee_rate,
            taker_fee_rate,
            max_sub_per_bar,
            sub_candles_gpu,
            sub_counts_gpu,
            funding_spans_gpu,
            funding_rates_gpu,
            trade_start,
            trade_end,
            entry_interval_sec,
            signal_on_candle_close,
        ) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("[TPE] Trade arena dispatch failed: {e} — skipping group");
                continue;
            }
        };

        for (local_idx, &trial_idx) in group_trial_indices.iter().enumerate() {
            all_results[trial_idx] = trade_results[local_idx];
        }
    }

    all_results
}

/// Dispatch indicator_kernel + breadth_kernel into pre-allocated arena buffers.
fn dispatch_indicator_arena(
    ds: &gpu_host::GpuDeviceState,
    candles_gpu: &CudaSlice<buffers::GpuRawCandle>,
    ind_configs: &[buffers::GpuIndicatorConfig],
    num_bars: u32,
    num_symbols: u32,
    btc_sym_idx: u32,
    snap_arena: &mut CudaSlice<buffers::GpuSnapshot>,
    breadth_arena: &mut CudaSlice<f32>,
    btc_arena: &mut CudaSlice<u32>,
) -> Result<(), String> {
    let k = u32::try_from(ind_configs.len())
        .map_err(|_| format!("ind_configs.len() {} exceeds u32::MAX", ind_configs.len()))?;
    let block_size = 64u32;

    let ind_configs_gpu = ds
        .dev
        .htod_sync_copy(ind_configs)
        .map_err(|e| format!("GPU alloc failed: {e}"))?;

    let params = buffers::IndicatorParams {
        num_ind_combos: k,
        num_symbols,
        num_bars,
        btc_sym_idx,
        _pad: [0; 4],
    };
    let ind_params_gpu = ds
        .dev
        .htod_sync_copy(&[params])
        .map_err(|e| format!("GPU alloc failed: {e}"))?;

    let ind_threads = k * num_symbols;
    let ind_grid = (ind_threads + block_size - 1) / block_size;

    let ind_func: CudaFunction = ds
        .dev
        .get_func("indicators", "indicator_kernel")
        .ok_or_else(|| "indicator_kernel not found in PTX".to_string())?;

    let ind_cfg = LaunchConfig {
        grid_dim: (ind_grid, 1, 1),
        block_dim: (block_size, 1, 1),
        shared_mem_bytes: 0,
    };

    unsafe {
        ind_func.launch(
            ind_cfg,
            (
                &ind_params_gpu,
                &ind_configs_gpu,
                candles_gpu,
                &mut *snap_arena,
            ),
        )
    }
    .map_err(|e| format!("indicator kernel launch: {e}"))?;

    let br_threads = k * num_bars;
    let br_grid = (br_threads + block_size - 1) / block_size;

    let br_func: CudaFunction = ds
        .dev
        .get_func("indicators", "breadth_kernel")
        .ok_or_else(|| "breadth_kernel not found in PTX".to_string())?;

    let br_cfg = LaunchConfig {
        grid_dim: (br_grid, 1, 1),
        block_dim: (block_size, 1, 1),
        shared_mem_bytes: 0,
    };

    unsafe {
        br_func.launch(
            br_cfg,
            (
                &ind_params_gpu,
                &*snap_arena,
                &mut *breadth_arena,
                &mut *btc_arena,
            ),
        )
    }
    .map_err(|e| format!("breadth kernel launch: {e}"))?;

    Ok(())
}

/// Dispatch trade sweep kernel using pre-allocated arena snapshot/breadth/btc buffers.
fn dispatch_trade_arena(
    ds: &gpu_host::GpuDeviceState,
    candles_gpu: &CudaSlice<buffers::GpuRawCandle>,
    snap_arena: &mut CudaSlice<buffers::GpuSnapshot>,
    breadth_arena: &mut CudaSlice<f32>,
    btc_arena: &mut CudaSlice<u32>,
    gpu_configs: &[buffers::GpuComboConfig],
    initial_balance: f32,
    num_symbols: u32,
    btc_sym_idx: u32,
    paxg_sym_idx: u32,
    num_bars: u32,
    maker_fee_rate: f32,
    taker_fee_rate: f32,
    max_sub_per_bar: u32,
    sub_candles_gpu: Option<&CudaSlice<buffers::GpuRawCandle>>,
    sub_counts_gpu: Option<&CudaSlice<u32>>,
    funding_spans_gpu: Option<&CudaSlice<buffers::GpuFundingSpan>>,
    funding_rates_gpu: Option<&CudaSlice<f64>>,
    trade_start: u32,
    trade_end: u32,
    entry_interval_sec: u32,
    signal_on_candle_close: u32,
) -> Result<Vec<buffers::GpuResult>, String> {
    let num_combos = u32::try_from(gpu_configs.len())
        .map_err(|_| format!("gpu_configs.len() {} exceeds u32::MAX", gpu_configs.len()))?;
    let block_size = 64u32;
    let grid_size = (num_combos + block_size - 1) / block_size;

    let configs_gpu = ds
        .dev
        .htod_sync_copy(gpu_configs)
        .map_err(|e| format!("GPU alloc failed: {e}"))?;

    let mut states_host = vec![buffers::GpuComboState::zeroed(); gpu_configs.len()];
    for s in &mut states_host {
        s.balance = initial_balance as f64;
        s.kernel_cash = initial_balance as f64;
        s.peak_equity = initial_balance as f64;
    }
    let mut states_gpu = ds
        .dev
        .htod_sync_copy(&states_host)
        .map_err(|e| format!("GPU alloc failed: {e}"))?;
    let mut results_gpu = ds
        .dev
        .alloc_zeros::<buffers::GpuResult>(gpu_configs.len())
        .map_err(|e| format!("GPU alloc failed: {e}"))?;

    let sentinel_candle: CudaSlice<buffers::GpuRawCandle>;
    let sentinel_counts: CudaSlice<u32>;
    let (sc_ref, sn_ref) = match (sub_candles_gpu, sub_counts_gpu) {
        (Some(sc), Some(sn)) => (sc, sn),
        _ => {
            sentinel_candle = ds
                .dev
                .alloc_zeros::<buffers::GpuRawCandle>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            sentinel_counts = ds
                .dev
                .alloc_zeros::<u32>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            (&sentinel_candle, &sentinel_counts)
        }
    };
    let sentinel_funding_spans: CudaSlice<buffers::GpuFundingSpan>;
    let sentinel_funding_rates: CudaSlice<f64>;
    let funding_enabled = funding_spans_gpu.is_some() && funding_rates_gpu.is_some();
    let (fr_spans_ref, fr_rates_ref) = match (funding_spans_gpu, funding_rates_gpu) {
        (Some(spans), Some(rates)) => (spans, rates),
        _ => {
            sentinel_funding_spans = ds
                .dev
                .alloc_zeros::<buffers::GpuFundingSpan>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            sentinel_funding_rates = ds
                .dev
                .alloc_zeros::<f64>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            (&sentinel_funding_spans, &sentinel_funding_rates)
        }
    };

    let effective_chunk = if max_sub_per_bar > 0 {
        BAR_CHUNK_SIZE.min(50)
    } else {
        BAR_CHUNK_SIZE
    };
    let debug_t_sec = std::env::var("AQC_GPU_DEBUG_T_SEC")
        .ok()
        .and_then(|v| v.parse::<u32>().ok())
        .unwrap_or(0);
    let trade_range = trade_end - trade_start;
    let num_chunks = (trade_range + effective_chunk - 1) / effective_chunk;

    for chunk_idx in 0..num_chunks {
        let chunk_start = trade_start + chunk_idx * effective_chunk;
        let chunk_end = (chunk_start + effective_chunk).min(trade_end);

        let params_host = buffers::GpuParams {
            num_combos,
            num_symbols,
            num_bars,
            btc_sym_idx,
            paxg_sym_idx,
            chunk_start,
            chunk_end,
            initial_balance_bits: initial_balance.to_bits(),
            maker_fee_rate_bits: maker_fee_rate.to_bits(),
            taker_fee_rate_bits: taker_fee_rate.to_bits(),
            max_sub_per_bar,
            trade_end_bar: trade_end,
            debug_t_sec,
            funding_enabled: if funding_enabled { 1 } else { 0 },
            entry_interval_sec,
            signal_on_candle_close,
        };
        let params_gpu = ds
            .dev
            .htod_sync_copy(&[params_host])
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        let cfg = LaunchConfig {
            grid_dim: (grid_size, 1, 1),
            block_dim: (block_size, 1, 1),
            shared_mem_bytes: 0,
        };

        let func: CudaFunction = ds
            .dev
            .get_func("sweep", "sweep_engine_kernel")
            .ok_or_else(|| "sweep_engine_kernel not found in PTX".to_string())?;

        unsafe {
            func.launch(
                cfg,
                (
                    &params_gpu,
                    &*snap_arena,
                    &*breadth_arena,
                    &*btc_arena,
                    &configs_gpu,
                    &mut states_gpu,
                    &mut results_gpu,
                    candles_gpu,
                    sc_ref,
                    sn_ref,
                    fr_spans_ref,
                    fr_rates_ref,
                ),
            )
        }
        .map_err(|e| format!("sweep_engine_kernel launch: {e}"))?;
    }

    ds.dev
        .dtoh_sync_copy(&results_gpu)
        .map_err(|e| format!("GPU readback failed: {e}"))
}

// =============================================================================
// Helpers
// =============================================================================

fn is_indicator_path(path: &str) -> bool {
    INDICATOR_PATHS.contains(&path)
}

/// Categorical axis paths (enum-typed params in `apply_one`).
const CATEGORICAL_PATHS: &[&str] = &[
    "trade.entry_min_confidence",
    "trade.add_min_confidence",
    "thresholds.entry.pullback_confidence",
    "thresholds.entry.macd_hist_entry_mode",
];

/// Integer axis paths (usize-typed params in `apply_one`).
fn is_integer_path(path: &str) -> bool {
    path.starts_with("indicators.")
        || path.contains("_window")
        || path == "trade.max_open_positions"
        || path == "trade.max_entry_orders_per_loop"
        || path == "trade.pyramid_max_adds"
        || path == "trade.leverage"
        || path == "trade.leverage_low"
        || path == "trade.leverage_medium"
        || path == "trade.leverage_high"
        || path == "trade.max_adds_per_symbol"
        || path == "trade.add_cooldown_minutes"
        || path == "trade.reentry_cooldown_minutes"
        || path == "trade.reentry_cooldown_min_mins"
        || path == "trade.reentry_cooldown_max_mins"
        || path == "trade.entry_cooldown_s"
        || path == "trade.exit_cooldown_s"
        || path == "thresholds.ranging.min_signals"
}

/// Compute approximate GCD of a sorted list of differences to derive step size.
fn approx_step_from_values(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let mut diffs: Vec<f64> = values.windows(2).map(|w| w[1] - w[0]).collect();
    diffs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    // Remove near-zero diffs (duplicate values)
    diffs.retain(|d| *d > 1e-9);
    if diffs.is_empty() {
        return 0.0;
    }
    // Approximate GCD via Euclidean algorithm on first diff, checking all others
    let mut gcd = diffs[0];
    for &d in &diffs[1..] {
        gcd = approx_gcd(gcd, d);
        if gcd < 1e-6 {
            return 1e-6;
        }
    }
    gcd.max(1e-6)
}

fn approx_gcd(mut a: f64, mut b: f64) -> f64 {
    for _ in 0..50 {
        if b < 1e-9 {
            break;
        }
        let rem = a % b;
        a = b;
        b = rem;
    }
    a
}

/// Create a TpeOptimizer with the correct estimator/range for the axis type.
fn make_optimizer(axis_type: &AxisType, min_val: f64, max_val: f64) -> tpe::TpeOptimizer {
    match axis_type {
        AxisType::Binary => tpe::TpeOptimizer::new(
            tpe::histogram_estimator(),
            tpe::categorical_range(2).unwrap(),
        ),
        AxisType::Categorical { values } => tpe::TpeOptimizer::new(
            tpe::histogram_estimator(),
            tpe::categorical_range(values.len()).unwrap(),
        ),
        AxisType::Integer | AxisType::Float { .. } => tpe::TpeOptimizer::new(
            tpe::parzen_estimator(),
            tpe::range(min_val, max_val).unwrap(),
        ),
    }
}

/// Classify a sweep axis into the appropriate AxisType based on path and values.
fn classify_axis(path: &str, values: &[f64]) -> AxisType {
    // Categorical first: known enum paths always use categorical, even if
    // narrowed to two values like [0.0, 1.0] (which would match Binary).
    if CATEGORICAL_PATHS.contains(&path) {
        return AxisType::Categorical {
            values: values.to_vec(),
        };
    }

    // Binary: exactly two values that are {0.0, 1.0} (sorted)
    if values.len() == 2 {
        let mut sorted = [values[0], values[1]];
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        if (sorted[0] - 0.0).abs() < 1e-9 && (sorted[1] - 1.0).abs() < 1e-9 {
            return AxisType::Binary;
        }
    }

    // Integer: indicator windows and other usize-typed params
    if is_integer_path(path) {
        return AxisType::Integer;
    }

    // Float with step quantization
    let step = approx_step_from_values(values);
    AxisType::Float { step }
}

#[cfg(test)]
mod tests {
    use super::{
        approx_step_from_values, checked_num_bars_u32, classify_axis, is_integer_path,
        resolve_raw, AxisOptimizer, AxisType,
    };

    #[test]
    fn binary_axes_detected_from_values() {
        assert!(matches!(
            classify_axis("trade.enable_breakeven_stop", &[0.0, 1.0]),
            AxisType::Binary
        ));
        assert!(matches!(
            classify_axis("filters.enable_ranging_filter", &[0.0, 1.0]),
            AxisType::Binary
        ));
        // Order doesn't matter
        assert!(matches!(
            classify_axis("trade.enable_pyramiding", &[1.0, 0.0]),
            AxisType::Binary
        ));
    }

    #[test]
    fn two_non_binary_values_not_binary() {
        // Two values that aren't {0, 1} should NOT be binary
        assert!(!matches!(
            classify_axis("trade.allocation_pct", &[0.1, 0.2]),
            AxisType::Binary
        ));
        assert!(!matches!(
            classify_axis("trade.leverage", &[2.0, 3.0]),
            AxisType::Binary
        ));
    }

    #[test]
    fn categorical_axes_detected() {
        assert!(matches!(
            classify_axis("trade.entry_min_confidence", &[0.0, 1.0, 2.0]),
            AxisType::Categorical { .. }
        ));
        assert!(matches!(
            classify_axis("trade.add_min_confidence", &[0.0, 1.0, 2.0]),
            AxisType::Categorical { .. }
        ));
        assert!(matches!(
            classify_axis(
                "thresholds.entry.macd_hist_entry_mode",
                &[0.0, 1.0, 2.0]
            ),
            AxisType::Categorical { .. }
        ));
        if let AxisType::Categorical { values } =
            classify_axis("trade.entry_min_confidence", &[0.0, 1.0, 2.0])
        {
            assert_eq!(values, vec![0.0, 1.0, 2.0]);
        }
    }

    #[test]
    fn leverage_axes_are_integer() {
        assert!(matches!(
            classify_axis("trade.leverage", &[2.0, 3.0, 4.0, 5.0]),
            AxisType::Integer
        ));
        assert!(matches!(
            classify_axis("trade.leverage_low", &[1.0, 2.0, 3.0]),
            AxisType::Integer
        ));
        assert!(matches!(
            classify_axis("trade.leverage_medium", &[2.0, 3.0, 4.0, 5.0]),
            AxisType::Integer
        ));
        assert!(matches!(
            classify_axis("trade.leverage_high", &[3.0, 4.0, 5.0]),
            AxisType::Integer
        ));
    }

    #[test]
    fn indicator_axes_are_integer() {
        assert!(matches!(
            classify_axis("indicators.adx_window", &[8.0, 10.0, 12.0, 14.0]),
            AxisType::Integer
        ));
        assert!(matches!(
            classify_axis("indicators.ema_fast_window", &[5.0, 10.0, 15.0]),
            AxisType::Integer
        ));
        assert!(matches!(
            classify_axis("trade.max_open_positions", &[1.0, 2.0, 3.0]),
            AxisType::Integer
        ));
        assert!(matches!(
            classify_axis("trade.max_entry_orders_per_loop", &[1.0, 2.0]),
            AxisType::Integer
        ));
    }

    #[test]
    fn added_integer_paths() {
        assert!(is_integer_path("trade.max_adds_per_symbol"));
        assert!(is_integer_path("trade.add_cooldown_minutes"));
        assert!(is_integer_path("trade.reentry_cooldown_minutes"));
        assert!(is_integer_path("trade.reentry_cooldown_min_mins"));
        assert!(is_integer_path("trade.reentry_cooldown_max_mins"));
        assert!(is_integer_path("trade.entry_cooldown_s"));
        assert!(is_integer_path("trade.exit_cooldown_s"));
        assert!(is_integer_path("thresholds.ranging.min_signals"));
    }

    #[test]
    fn continuous_axes_are_float() {
        assert!(matches!(
            classify_axis("trade.allocation_pct", &[0.05, 0.10, 0.15, 0.20]),
            AxisType::Float { .. }
        ));
        assert!(matches!(
            classify_axis("trade.sl_atr_mult", &[1.0, 1.25, 1.5, 1.75, 2.0]),
            AxisType::Float { .. }
        ));
        assert!(matches!(
            classify_axis("thresholds.entry.min_adx", &[10.0, 15.0, 20.0, 25.0]),
            AxisType::Float { .. }
        ));
    }

    #[test]
    fn float_step_detection() {
        let step = approx_step_from_values(&[0.05, 0.10, 0.15, 0.20]);
        assert!((step - 0.05).abs() < 1e-6, "step={step}, expected 0.05");

        let step = approx_step_from_values(&[1.0, 1.25, 1.5, 1.75, 2.0]);
        assert!((step - 0.25).abs() < 1e-6, "step={step}, expected 0.25");

        let step = approx_step_from_values(&[10.0, 15.0, 20.0, 25.0]);
        assert!((step - 5.0).abs() < 1e-4, "step={step}, expected 5.0");
    }

    /// Build a minimal AxisOptimizer for `resolve_raw` tests (only axis_type,
    /// min_val, max_val matter; optimizer is a dummy).
    fn dummy_axis(min_val: f64, max_val: f64, axis_type: AxisType) -> AxisOptimizer {
        AxisOptimizer {
            path: String::new(),
            min_val,
            max_val,
            optimizer: tpe::TpeOptimizer::new(
                tpe::parzen_estimator(),
                tpe::range(min_val, max_val + 1.0).unwrap(),
            ),
            is_indicator: false,
            axis_type,
            freeze_val: min_val,
            gate: None,
        }
    }

    #[test]
    fn float_step_min_origin_quantization() {
        // Offset grid: [28, 40, 52] step=12, min=28
        // Zero-origin would produce 36, 48 — wrong.
        // Min-origin should produce 28, 40, 52.
        let axis = dummy_axis(28.0, 52.0, AxisType::Float { step: 12.0 });
        assert_eq!(resolve_raw(&axis, 28.0), 28.0);
        assert_eq!(resolve_raw(&axis, 33.0), 28.0); // closer to 28 than 40
        assert_eq!(resolve_raw(&axis, 34.0), 40.0); // 34-28=6, 6/12=0.5, rounds to 1 → 40
        assert_eq!(resolve_raw(&axis, 40.0), 40.0);
        assert_eq!(resolve_raw(&axis, 46.0), 52.0); // 46-28=18, 18/12=1.5, rounds to 2 → 52
        assert_eq!(resolve_raw(&axis, 52.0), 52.0);

        // Offset grid: [0.35, 0.50, 0.65] step=0.15, min=0.35
        let axis = dummy_axis(0.35, 0.65, AxisType::Float { step: 0.15 });
        assert!((resolve_raw(&axis, 0.35) - 0.35).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.50) - 0.50).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.65) - 0.65).abs() < 1e-9);

        // Zero-aligned grid: [0.05, 0.10, 0.15, 0.20] step=0.05
        // Should still work correctly with min-origin.
        let axis = dummy_axis(0.05, 0.20, AxisType::Float { step: 0.05 });
        assert!((resolve_raw(&axis, 0.05) - 0.05).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.10) - 0.10).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.15) - 0.15).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.20) - 0.20).abs() < 1e-9);

        // Clamping at boundaries still works
        assert_eq!(resolve_raw(&axis, 0.01), 0.05);
        assert_eq!(resolve_raw(&axis, 0.99), 0.20);
    }

    #[test]
    fn float_step_offset_grid_vol_baseline() {
        // [0.007, 0.010, 0.013] step=0.003, min=0.007
        let axis = dummy_axis(0.007, 0.013, AxisType::Float { step: 0.003 });
        assert!((resolve_raw(&axis, 0.007) - 0.007).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.010) - 0.010).abs() < 1e-9);
        assert!((resolve_raw(&axis, 0.013) - 0.013).abs() < 1e-9);
    }

    #[test]
    fn confidence_is_categorical_not_binary() {
        // Even though [0.0, 1.0] subset exists, 3 values + categorical path → Categorical
        assert!(matches!(
            classify_axis("trade.entry_min_confidence", &[0.0, 1.0, 2.0]),
            AxisType::Categorical { .. }
        ));
    }

    #[test]
    fn categorical_path_with_two_values_stays_categorical() {
        // Narrowed categorical sweep with only [0.0, 1.0] should NOT be classified as Binary
        assert!(matches!(
            classify_axis("trade.entry_min_confidence", &[0.0, 1.0]),
            AxisType::Categorical { .. }
        ));
        assert!(matches!(
            classify_axis("thresholds.entry.macd_hist_entry_mode", &[0.0, 1.0]),
            AxisType::Categorical { .. }
        ));
    }

    #[test]
    fn checked_num_bars_u32_accepts_small_values() {
        assert_eq!(checked_num_bars_u32(123).unwrap(), 123);
    }

    #[test]
    fn checked_num_bars_u32_rejects_overflow() {
        let err = checked_num_bars_u32(usize::MAX);
        assert!(err.is_err());
        assert!(
            err.unwrap_err().contains("exceeds u32::MAX"),
            "overflow error should mention u32 bound"
        );
    }
}
