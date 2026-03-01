pub mod axis_split;
pub mod buffers;
pub mod gpu_host;
pub mod layout;
pub mod precision;
pub mod raw_candles;
pub mod tpe_sweep;

#[cfg(feature = "codegen")]
#[path = "../codegen/mod.rs"]
pub mod codegen;

/// Check if a set of overrides produces a degenerate config that the GPU f32
/// kernel can evaluate but produces phantom signals not reproducible in f64.
///
/// Current checks:
/// - `ema_fast_window >= ema_slow_window` → alignment and close/ema gates
///   become anti-correlated, producing zero real signals.
pub fn is_degenerate_overrides(overrides: &[(String, f64)]) -> bool {
    let mut ema_fast: Option<f64> = None;
    let mut ema_slow: Option<f64> = None;
    for (path, val) in overrides {
        match path.as_str() {
            "indicators.ema_fast_window" => ema_fast = Some(*val),
            "indicators.ema_slow_window" => ema_slow = Some(*val),
            _ => {}
        }
    }
    if let (Some(fast), Some(slow)) = (ema_fast, ema_slow) {
        if fast.round() >= slow.round() {
            return true;
        }
    }
    false
}

use bt_core::candle::{CandleData, FundingRateData};
use bt_core::config::StrategyConfig;
use bt_core::sweep::SweepSpec;
use std::sync::Arc;

pub use buffers::GpuResult;
pub use layout::GpuSweepResult;

/// Bar chunk size for TDR mitigation in trade kernel.
const BAR_CHUNK_SIZE: u32 = 500;

/// Build deterministic symbol ordering and enforce GPU kernel symbol cap.
pub(crate) fn sorted_symbols_with_kernel_cap(
    candles: &CandleData,
    log_prefix: &str,
) -> Vec<String> {
    let mut symbols: Vec<String> = candles.keys().cloned().collect();
    symbols.sort();
    if symbols.len() > buffers::GPU_MAX_SYMBOLS {
        eprintln!(
            "{log_prefix} Warning: {} symbols loaded, truncating to {} (kernel state limit)",
            symbols.len(),
            buffers::GPU_MAX_SYMBOLS,
        );
        symbols.truncate(buffers::GPU_MAX_SYMBOLS);
    }
    symbols
}

fn usize_to_u32(label: &str, value: usize) -> Result<u32, String> {
    u32::try_from(value).map_err(|_| format!("{label} {value} exceeds u32::MAX"))
}

fn checked_offset_u32(label: &str, lhs: usize, rhs: usize) -> Result<u32, String> {
    let value = lhs
        .checked_mul(rhs)
        .ok_or_else(|| format!("{label} overflow: {lhs} * {rhs}"))?;
    usize_to_u32(label, value)
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

/// Run a GPU-accelerated parameter sweep.
///
/// **All-GPU pipeline**: Raw candles uploaded once → indicator kernel computes
/// indicators on GPU → breadth kernel → trade kernel. No CPU precompute,
/// no host RAM for snapshots, minimal host↔device transfers.
///
/// Pipeline:
/// 1. CPU: prepare raw candle flat buffer (~6 MB, layout only)
/// 2. Upload raw candles to GPU ONCE
/// 3. For each VRAM batch of K indicator combos:
///    a. Launch indicator_kernel (K × S threads) → snapshots in VRAM
///    b. Launch breadth_kernel (K × B threads) → breadth/btc_bullish in VRAM
///    c. Build K × T GpuComboConfigs with per-combo offsets
///    d. Launch sweep_engine_kernel (K × T threads) → trade results
///    e. Read back results (tiny: K × T × 48 bytes)
/// 4. Sort and return results
pub fn run_gpu_sweep(
    candles: &CandleData,
    base_cfg: &StrategyConfig,
    spec: &SweepSpec,
    funding: Option<&FundingRateData>,
    sub_candles: Option<&CandleData>,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> Vec<GpuSweepResult> {
    let (results, _states, _symbols) = run_gpu_sweep_internal(
        candles,
        base_cfg,
        spec,
        funding,
        sub_candles,
        from_ts,
        to_ts,
        false,
    );
    results
}

/// Run a GPU sweep and also return final GPU combo states plus the symbol
/// ordering used by the kernel.
///
/// Intended for diagnostic tooling (for example axis parity trace capture).
pub fn run_gpu_sweep_with_states(
    candles: &CandleData,
    base_cfg: &StrategyConfig,
    spec: &SweepSpec,
    funding: Option<&FundingRateData>,
    sub_candles: Option<&CandleData>,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> (
    Vec<GpuSweepResult>,
    Vec<buffers::GpuComboState>,
    Vec<String>,
) {
    let (results, states, symbols) = run_gpu_sweep_internal(
        candles,
        base_cfg,
        spec,
        funding,
        sub_candles,
        from_ts,
        to_ts,
        true,
    );
    (results, states.unwrap_or_default(), symbols)
}

fn run_gpu_sweep_internal(
    candles: &CandleData,
    base_cfg: &StrategyConfig,
    spec: &SweepSpec,
    funding: Option<&FundingRateData>,
    sub_candles: Option<&CandleData>,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
    capture_states: bool,
) -> (
    Vec<GpuSweepResult>,
    Option<Vec<buffers::GpuComboState>>,
    Vec<String>,
) {
    let (indicator_axes, trade_axes) = axis_split::split_axes(&spec.axes);

    let indicator_combos = axis_split::generate_combinations(&indicator_axes);
    let trade_combos = axis_split::generate_combinations(&trade_axes);

    let symbols = sorted_symbols_with_kernel_cap(candles, "[GPU]");
    let num_symbols = symbols.len();
    let num_symbols_u32 = match usize_to_u32("num_symbols", num_symbols) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("[GPU] {e} — skipping GPU sweep");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };

    // BTC symbol index for breadth kernel.
    // Use u32::MAX sentinel when unavailable, so kernels can treat alignment as unknown.
    // C7: validated u32 cast (symbols capped at GPU_MAX_SYMBOLS=52, always fits)
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

    // ── 1. Prepare raw candles (CPU, layout only, ~10ms) ─────────────────
    let raw = raw_candles::prepare_raw_candles(candles, &symbols);
    let num_bars = match u32::try_from(raw.num_bars) {
        Ok(n) => n,
        Err(_) => {
            eprintln!(
                "[GPU] num_bars {} exceeds u32::MAX — skipping GPU sweep",
                raw.num_bars
            );
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };

    // Compute trade bar range from time scope
    let (trade_start, trade_end) =
        raw_candles::find_trade_bar_range(&raw.timestamps, from_ts, to_ts);
    let funding_events_host = funding.map(|fr| {
        raw_candles::prepare_funding_event_buffers(fr, &raw.timestamps, &symbols)
    });

    eprintln!(
        "[GPU] {} ind × {} trade = {} total combos, {} bars × {} symbols",
        indicator_combos.len(),
        trade_combos.len(),
        indicator_combos.len() * trade_combos.len(),
        num_bars,
        num_symbols,
    );

    // Fee rates from bt_core accounting constants (H9: not hardcoded)
    let maker_fee_rate = bt_core::accounting::DEFAULT_MAKER_FEE_RATE as f32;
    let taker_fee_rate = bt_core::accounting::DEFAULT_TAKER_FEE_RATE as f32;
    let signal_on_candle_close = if base_cfg.engine.signal_on_candle_close {
        1
    } else {
        0
    };
    let entry_interval_sec = interval_to_seconds(&base_cfg.engine.entry_interval);

    // ── 2. Init CUDA device, upload raw candles ONCE ─────────────────────
    // C6: graceful fallback — return empty results if GPU init fails
    let device_state = match gpu_host::GpuDeviceState::new() {
        Ok(ds) => ds,
        Err(e) => {
            eprintln!("[GPU] {e} — GPU sweep unavailable, returning empty results");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };
    let candles_gpu = match device_state.dev.htod_sync_copy(&raw.candles) {
        Ok(buf) => buf,
        Err(e) => {
            eprintln!("[GPU] candle upload failed: {e} — skipping GPU sweep");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };

    let candle_upload_mb =
        (raw.candles.len() * std::mem::size_of::<buffers::GpuRawCandle>()) as f64 / 1e6;
    eprintln!(
        "[GPU] Raw candles uploaded: {:.1} MB (one-time)",
        candle_upload_mb
    );
    let (funding_spans_gpu, funding_rates_gpu): (
        Option<Arc<cudarc::driver::CudaSlice<buffers::GpuFundingSpan>>>,
        Option<Arc<cudarc::driver::CudaSlice<f64>>>,
    ) = if let Some(funding_events) = funding_events_host.as_ref() {
        let active_slots = funding_events.spans.iter().filter(|span| span.len > 0).count();
        if funding_events.rates.is_empty() || active_slots == 0 {
            eprintln!(
                "[GPU] Funding DB provided but no hourly settlements in scoped range; funding kernel path disabled"
            );
            (None, None)
        } else {
            let spans_gpu = match device_state.dev.htod_sync_copy(&funding_events.spans) {
                Ok(buf) => buf,
                Err(e) => {
                    eprintln!("[GPU] Funding span upload failed: {e} — skipping GPU sweep");
                    return (
                        Vec::new(),
                        if capture_states {
                            Some(Vec::new())
                        } else {
                            None
                        },
                        symbols,
                    );
                }
            };
            let rates_gpu = match device_state.dev.htod_sync_copy(&funding_events.rates) {
                Ok(buf) => buf,
                Err(e) => {
                    eprintln!("[GPU] Funding rate upload failed: {e} — skipping GPU sweep");
                    return (
                        Vec::new(),
                        if capture_states {
                            Some(Vec::new())
                        } else {
                            None
                        },
                        symbols,
                    );
                }
            };
            eprintln!(
                "[GPU] Funding settlements prepared: {} events across {} active bar-symbol slots",
                funding_events.rates.len(),
                active_slots
            );
            (Some(Arc::new(spans_gpu)), Some(Arc::new(rates_gpu)))
        }
    } else {
        (None, None)
    };

    // Prepare sub-bar candles for GPU (if provided)
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
                        eprintln!("[GPU] Sub-candle upload failed: {e}");
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
                        eprintln!("[GPU] Sub-counts upload failed: {e}");
                        None
                    }
                }
            }
        });
    let requested_max_sub_per_bar = sub_bar_result
        .as_ref()
        .map(|sbr| sbr.max_sub_per_bar)
        .unwrap_or(0);
    let sub_bar_buffers_ready = sub_candles_gpu.is_some() && sub_counts_gpu.is_some();
    let max_sub_per_bar = if sub_bar_buffers_ready {
        requested_max_sub_per_bar
    } else {
        0
    };

    if requested_max_sub_per_bar > 0 && !sub_bar_buffers_ready {
        eprintln!(
            "[GPU] Sub-bar buffers incomplete (candles={}, counts={}) — disabling sub-bar path for this sweep",
            sub_candles_gpu.is_some(),
            sub_counts_gpu.is_some(),
        );
    } else if max_sub_per_bar > 0 {
        eprintln!(
            "[GPU] Sub-bar candles: max_sub={}, GPU buffer uploaded",
            max_sub_per_bar
        );
    }

    // CPU scope guard skips bars with ts < from_ts before sub-bar processing.
    // Keep kernel start aligned to scoped trade_start; do not step back one bar.
    let trade_start_for_kernel = trade_start;

    // ── 3. Calculate VRAM budget ─────────────────────────────────────────
    let total_vram = device_state.total_vram_bytes();
    let free_vram = device_state.free_vram_bytes();

    // Per-indicator-combo VRAM cost (snapshots + breadth + btc_bullish)
    // C8: use checked arithmetic to prevent overflow on large inputs
    let snapshot_elements = match (num_bars as usize).checked_mul(num_symbols) {
        Some(v) => v,
        None => {
            eprintln!("[GPU] overflow: num_bars * num_symbols — skipping GPU sweep");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };
    let snapshot_bytes_per_ind: usize = match snapshot_elements
        .checked_mul(std::mem::size_of::<buffers::GpuSnapshot>())
        .and_then(|v| v.checked_add((num_bars as usize).checked_mul(std::mem::size_of::<f32>())?))
        .and_then(|v| v.checked_add((num_bars as usize).checked_mul(std::mem::size_of::<u32>())?))
    {
        Some(v) => v,
        None => {
            eprintln!("[GPU] overflow: snapshot_bytes_per_ind calculation — skipping GPU sweep");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };

    // Per-trade-combo VRAM cost (config + state + result)
    let combo_bytes: usize = std::mem::size_of::<buffers::GpuComboConfig>()
        + std::mem::size_of::<buffers::GpuComboState>()
        + std::mem::size_of::<buffers::GpuResult>()
        + 32; // params overhead

    let t = trade_combos.len();
    let t_combo_bytes = match t.checked_mul(combo_bytes) {
        Some(v) => v,
        None => {
            eprintln!("[GPU] overflow: t * combo_bytes — skipping GPU sweep");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };
    let per_ind_total_vram = match snapshot_bytes_per_ind.checked_add(t_combo_bytes) {
        Some(v) => v,
        None => {
            eprintln!("[GPU] overflow: per_ind_total_vram — skipping GPU sweep");
            return (
                Vec::new(),
                if capture_states {
                    Some(Vec::new())
                } else {
                    None
                },
                symbols,
            );
        }
    };

    // Hard cap: max 10 GB per snapshot allocation (large contiguous allocs
    // can fail even with plenty of total free VRAM due to fragmentation)
    let max_snapshot_alloc: usize = 10 * 1024 * 1024 * 1024; // 10 GB
    let max_ind_by_snapshot = if snapshot_bytes_per_ind > 0 {
        max_snapshot_alloc / snapshot_bytes_per_ind
    } else {
        indicator_combos.len()
    };

    // Also respect reported free VRAM (50% to leave room for configs/states/overhead)
    let usable_vram = (free_vram * 50) / 100;
    let max_ind_by_vram = if per_ind_total_vram > 0 {
        usable_vram / per_ind_total_vram
    } else {
        indicator_combos.len()
    };

    let max_ind_per_vram = max_ind_by_snapshot.min(max_ind_by_vram).max(1);
    let batch_size = max_ind_per_vram.min(indicator_combos.len());

    eprintln!(
        "[GPU] VRAM: {:.1} GB total, {:.1} GB free",
        total_vram as f64 / 1e9,
        free_vram as f64 / 1e9,
    );
    eprintln!(
        "[GPU] Per-ind snapshot: {:.1} MB, batch size: {} ind/batch (VRAM limit: {}, snap cap: {})",
        snapshot_bytes_per_ind as f64 / 1e6,
        batch_size,
        max_ind_by_vram,
        max_ind_by_snapshot,
    );
    eprintln!("[GPU] Pipeline: ALL-GPU (indicator + breadth + trade kernels)");

    // ── 4. Main sweep loop ───────────────────────────────────────────────
    let mut all_results: Vec<(GpuSweepResult, Option<buffers::GpuComboState>)> = Vec::new();
    let mut done = 0usize;
    let total_ind = indicator_combos.len();

    for chunk in indicator_combos.chunks(batch_size) {
        let k = chunk.len();

        // a. Build GpuIndicatorConfigs for this batch
        let ind_configs: Vec<buffers::GpuIndicatorConfig> = chunk
            .iter()
            .map(|ind_combo| {
                let mut cfg = base_cfg.clone();
                for (path, value) in ind_combo {
                    bt_core::sweep::apply_one_pub(&mut cfg, path, *value);
                }
                buffers::GpuIndicatorConfig::from_strategy_config(&cfg, spec.lookback)
            })
            .collect();

        // b. Create indicator buffers + dispatch indicator & breadth kernels
        // H11: handle GPU memory allocation failure gracefully
        let mut ind_bufs = match gpu_host::IndicatorBuffers::new(
            &device_state,
            &candles_gpu,
            &ind_configs,
            num_bars,
            num_symbols_u32,
            btc_sym_idx,
            paxg_sym_idx,
        ) {
            Ok(bufs) => bufs,
            Err(e) => {
                eprintln!("[GPU] Indicator buffer allocation failed: {e} — skipping batch");
                done += chunk.len();
                continue;
            }
        };
        if let Err(e) = gpu_host::dispatch_indicator_kernels(&device_state, &mut ind_bufs) {
            eprintln!("[GPU] Indicator kernel dispatch failed: {e} — skipping batch");
            done += chunk.len();
            continue;
        }

        // c. Build K×T GpuComboConfigs with per-combo offsets
        let snapshot_stride = snapshot_elements;
        let breadth_stride = num_bars as usize;

        // Also need per-indicator StrategyConfig for trade params
        let ind_cfgs: Vec<(Vec<(String, f64)>, StrategyConfig)> = chunk
            .iter()
            .map(|ind_combo| {
                let mut cfg = base_cfg.clone();
                for (path, value) in ind_combo {
                    bt_core::sweep::apply_one_pub(&mut cfg, path, *value);
                }
                (ind_combo.clone(), cfg)
            })
            .collect();

        let total_combos = k * t;
        let mut gpu_configs = Vec::with_capacity(total_combos);
        let mut combo_meta: Vec<(usize, usize)> = Vec::with_capacity(total_combos);
        let mut skip_batch = false;

        for (ind_idx, (_ind_combo, ind_cfg)) in ind_cfgs.iter().enumerate() {
            let snap_off = match checked_offset_u32("snapshot offset", ind_idx, snapshot_stride) {
                Ok(v) => v,
                Err(e) => {
                    eprintln!("[GPU] {e} — skipping batch");
                    skip_batch = true;
                    break;
                }
            };
            let br_off = match checked_offset_u32("breadth offset", ind_idx, breadth_stride) {
                Ok(v) => v,
                Err(e) => {
                    eprintln!("[GPU] {e} — skipping batch");
                    skip_batch = true;
                    break;
                }
            };

            for (trade_idx, trade_overrides) in trade_combos.iter().enumerate() {
                let mut cfg = ind_cfg.clone();
                for (path, value) in trade_overrides {
                    bt_core::sweep::apply_one_pub(&mut cfg, path, *value);
                }
                let mut gpu_cfg = match buffers::GpuComboConfig::from_strategy_config(&cfg) {
                    Ok(v) => v,
                    Err(e) => {
                        eprintln!("[GPU] invalid combo config conversion: {e} — skipping batch");
                        skip_batch = true;
                        break;
                    }
                };
                gpu_cfg.snapshot_offset = snap_off;
                gpu_cfg.breadth_offset = br_off;
                gpu_configs.push(gpu_cfg);
                combo_meta.push((ind_idx, trade_idx));
            }
            if skip_batch {
                break;
            }
        }
        if skip_batch {
            done += chunk.len();
            continue;
        }

        // d. Dispatch trade kernel using VRAM-resident indicator data
        let combo_base = done * t;
        let mut trade_bufs = match gpu_host::BatchBuffers::from_indicator_buffers(
            &device_state,
            &ind_bufs,
            &gpu_configs,
            spec.initial_balance as f32,
            combo_base,
            maker_fee_rate,
            taker_fee_rate,
        ) {
            Ok(bufs) => bufs,
            Err(e) => {
                eprintln!("[GPU] Trade buffer allocation failed: {e} — skipping batch");
                done += chunk.len();
                continue;
            }
        };
        trade_bufs.max_sub_per_bar = max_sub_per_bar;
        trade_bufs.entry_interval_sec = entry_interval_sec;
        trade_bufs.signal_on_candle_close = signal_on_candle_close;
        // Arc clone only bumps refcount; avoids cudarc CudaSlice device-to-device copy.
        trade_bufs.sub_candles = sub_candles_gpu.clone();
        trade_bufs.sub_counts = sub_counts_gpu.clone();
        trade_bufs.funding_spans = funding_spans_gpu.clone();
        trade_bufs.funding_rates = funding_rates_gpu.clone();

        let gpu_results = match gpu_host::dispatch_and_readback(
            &device_state,
            &mut trade_bufs,
            num_bars,
            BAR_CHUNK_SIZE,
            trade_start_for_kernel,
            trade_end,
        ) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("[GPU] Trade kernel dispatch/readback failed: {e} — skipping batch");
                done += chunk.len();
                continue;
            }
        };
        let gpu_states = if capture_states {
            match gpu_host::readback_states(&device_state, &trade_bufs) {
                Ok(s) => Some(s),
                Err(e) => {
                    eprintln!("[GPU] State readback failed: {e}");
                    None
                }
            }
        } else {
            None
        };

        // e. Map results back
        for (i, result) in gpu_results.iter().enumerate() {
            let (ind_idx, trade_idx) = combo_meta[i];
            let (ind_combo, _) = &ind_cfgs[ind_idx];
            let trade_overrides = &trade_combos[trade_idx];

            let mut all_overrides = ind_combo.clone();
            all_overrides.extend(trade_overrides.iter().cloned());

            // Skip degenerate combos (e.g. ema_fast >= ema_slow) that produce
            // phantom f32 signals not reproducible in f64 CPU replay.
            if is_degenerate_overrides(&all_overrides) {
                continue;
            }

            let config_id = all_overrides
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

            let mapped = GpuSweepResult {
                config_id,
                output_mode: "gpu".to_string(),
                total_pnl: result.total_pnl as f64,
                final_balance: result.final_balance as f64,
                total_trades: result.total_trades,
                total_wins: result.total_wins,
                win_rate: wr,
                profit_factor: pf,
                max_drawdown_pct: result.max_drawdown_pct as f64,
                overrides: all_overrides,
            };
            let state_opt = gpu_states.as_ref().map(|states| states[i]);
            all_results.push((mapped, state_opt));
        }

        done += chunk.len();
        if total_ind > 1 {
            eprintln!(
                "[GPU] Progress: {}/{} indicator configs done",
                done, total_ind
            );
        }
        // ind_bufs + trade_bufs dropped here → frees VRAM for next batch
    }

    all_results.sort_by(|a, b| {
        b.0.total_pnl
            .partial_cmp(&a.0.total_pnl)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    if capture_states {
        let mut results = Vec::with_capacity(all_results.len());
        let mut states = Vec::with_capacity(all_results.len());
        for (result, state) in all_results {
            match state {
                Some(s) => {
                    results.push(result);
                    states.push(s);
                }
                None => {
                    eprintln!(
                        "[GPU] WARNING: missing captured state for result index {} — skipping entry",
                        results.len()
                    );
                }
            }
        }
        (results, Some(states), symbols)
    } else {
        let results = all_results.into_iter().map(|(result, _)| result).collect();
        (results, None, symbols)
    }
}

#[cfg(test)]
mod tests {
    use bt_core::candle::{CandleData, OhlcvBar};

    fn extract_fn_block<'a>(source: &'a str, signature: &str) -> &'a str {
        let start = source
            .find(signature)
            .unwrap_or_else(|| panic!("Function signature not found: {signature}"));
        let brace_start = source[start..]
            .find('{')
            .map(|idx| start + idx)
            .expect("Function body start not found");

        let mut depth = 0usize;
        for (idx, ch) in source[brace_start..].char_indices() {
            match ch {
                '{' => depth += 1,
                '}' => {
                    depth -= 1;
                    if depth == 0 {
                        let end = brace_start + idx + 1;
                        return &source[start..end];
                    }
                }
                _ => {}
            }
        }
        panic!("Function body end not found: {signature}");
    }

    #[test]
    fn tp_mult_kernel_sources_are_fixed_to_trade_tp_atr_mult() {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));

        let cu_src = std::fs::read_to_string(root.join("kernels/sweep_engine.cu"))
            .expect("Failed to read CUDA sweep engine source");
        let cu_fn = extract_fn_block(&cu_src, "__device__ float get_tp_mult(");
        assert!(
            cu_fn.contains("return cfg->tp_atr_mult;"),
            "CUDA get_tp_mult must return cfg->tp_atr_mult"
        );
        assert!(
            !cu_fn.contains("return 7.0f;") && !cu_fn.contains("return 3.0f;"),
            "CUDA get_tp_mult must not hardcode ADX TP multipliers"
        );

        // DEPRECATED (AQC-1241): WGSL shader is no longer maintained.
        // This assertion is kept to prevent silent regressions in the
        // archived shader, but no new parity checks should be added here.
        let wgsl_src = std::fs::read_to_string(root.join("shaders/sweep_engine.wgsl"))
            .expect("Failed to read WGSL sweep engine source (deprecated, retained for reference)");
        let wgsl_fn = extract_fn_block(&wgsl_src, "fn get_tp_mult(");
        assert!(
            wgsl_fn.contains("return (*cfg).tp_atr_mult;"),
            "WGSL get_tp_mult must return (*cfg).tp_atr_mult"
        );
        assert!(
            !wgsl_fn.contains("return 7.0;") && !wgsl_fn.contains("return 3.0;"),
            "WGSL get_tp_mult must not hardcode ADX TP multipliers"
        );
    }

    #[test]
    fn sorted_symbols_with_kernel_cap_truncates_deterministically() {
        let mut candles: CandleData = CandleData::default();
        for idx in 0..(crate::buffers::GPU_MAX_SYMBOLS + 9) {
            candles.insert(
                format!("SYM{:03}", idx),
                vec![OhlcvBar {
                    t: 0,
                    t_close: 0,
                    o: 1.0,
                    h: 1.0,
                    l: 1.0,
                    c: 1.0,
                    v: 1.0,
                    n: 1,
                }],
            );
        }

        let out = crate::sorted_symbols_with_kernel_cap(&candles, "[test]");
        assert_eq!(out.len(), crate::buffers::GPU_MAX_SYMBOLS);
        assert_eq!(out.first().map(String::as_str), Some("SYM000"));
        assert_eq!(out.last().map(String::as_str), Some("SYM051"));
    }

    #[test]
    fn sorted_symbols_with_kernel_cap_keeps_all_when_within_limit() {
        let mut candles: CandleData = CandleData::default();
        candles.insert(
            "BTC".to_string(),
            vec![OhlcvBar {
                t: 0,
                t_close: 0,
                o: 1.0,
                h: 1.0,
                l: 1.0,
                c: 1.0,
                v: 1.0,
                n: 1,
            }],
        );
        candles.insert(
            "ETH".to_string(),
            vec![OhlcvBar {
                t: 0,
                t_close: 0,
                o: 1.0,
                h: 1.0,
                l: 1.0,
                c: 1.0,
                v: 1.0,
                n: 1,
            }],
        );

        let out = crate::sorted_symbols_with_kernel_cap(&candles, "[test]");
        assert_eq!(out, vec!["BTC".to_string(), "ETH".to_string()]);
    }

    #[test]
    fn usize_to_u32_rejects_overflow() {
        let err = crate::usize_to_u32("num_symbols", usize::MAX);
        assert!(err.is_err());
        assert!(
            err.unwrap_err().contains("exceeds u32::MAX"),
            "overflow error should mention u32 bound"
        );
    }

    #[test]
    fn checked_offset_u32_rejects_mul_overflow() {
        let err = crate::checked_offset_u32("snapshot offset", usize::MAX, 2);
        assert!(err.is_err());
        assert!(
            err.unwrap_err().contains("overflow"),
            "overflow error should mention multiplication overflow"
        );
    }

    #[test]
    fn checked_offset_u32_accepts_valid_values() {
        let off = crate::checked_offset_u32("snapshot offset", 7, 9).unwrap();
        assert_eq!(off, 63);
    }
}
