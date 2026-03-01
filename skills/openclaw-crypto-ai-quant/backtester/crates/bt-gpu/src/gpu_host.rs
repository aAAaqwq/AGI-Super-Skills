//! CUDA device initialization, buffer management, and kernel dispatch.
//!
//! Uses cudarc (CUDA driver API). The earlier wgpu/WGSL path is deprecated
//! (AQC-1241); see `shaders/sweep_engine.wgsl` for the archived shader.
//! PTX is pre-compiled by build.rs via nvcc and embedded at compile time.
//!
//! Two kernel modules:
//! - "sweep" — sweep_engine_kernel (trade logic)
//! - "indicators" — indicator_kernel + breadth_kernel (indicator computation)

use std::{env, sync::Arc};

use cudarc::driver::{
    CudaDevice, CudaFunction, CudaSlice, DeviceRepr, LaunchAsync, LaunchConfig, ValidAsZeroBits,
};

use cudarc::nvrtc::Ptx;

use crate::buffers::{
    GpuComboConfig, GpuComboState, GpuFundingSpan, GpuIndicatorConfig, GpuParams, GpuRawCandle,
    GpuResult, GpuSnapshot, IndicatorParams, GPU_TRACE_SYMBOL_ALL,
};
use bytemuck::Zeroable;

// ═══════════════════════════════════════════════════════════════════════════
// DeviceRepr + ValidAsZeroBits impls for GPU buffer structs
// ═══════════════════════════════════════════════════════════════════════════

unsafe impl DeviceRepr for GpuSnapshot {}
unsafe impl DeviceRepr for GpuComboConfig {}
unsafe impl DeviceRepr for GpuComboState {}
unsafe impl DeviceRepr for GpuResult {}
unsafe impl DeviceRepr for GpuParams {}
unsafe impl DeviceRepr for GpuRawCandle {}
unsafe impl DeviceRepr for GpuIndicatorConfig {}
unsafe impl DeviceRepr for IndicatorParams {}
unsafe impl DeviceRepr for GpuFundingSpan {}

unsafe impl ValidAsZeroBits for GpuSnapshot {}
unsafe impl ValidAsZeroBits for GpuComboConfig {}
unsafe impl ValidAsZeroBits for GpuComboState {}
unsafe impl ValidAsZeroBits for GpuResult {}
unsafe impl ValidAsZeroBits for GpuParams {}
unsafe impl ValidAsZeroBits for GpuRawCandle {}
unsafe impl ValidAsZeroBits for GpuIndicatorConfig {}
unsafe impl ValidAsZeroBits for IndicatorParams {}
unsafe impl ValidAsZeroBits for GpuFundingSpan {}

fn env_truthy(name: &str) -> bool {
    env::var(name)
        .map(|v| {
            let s = v.trim().to_ascii_lowercase();
            s == "1" || s == "true" || s == "yes" || s == "on"
        })
        .unwrap_or(false)
}

fn trace_env_config(combo_base: usize, num_combos: usize) -> Option<(usize, u32)> {
    let trace_enabled = env_truthy("AQC_GPU_TRACE")
        || env::var("AQC_GPU_TRACE_COMBO").is_ok()
        || env::var("AQC_GPU_TRACE_SYMBOL").is_ok();
    if !trace_enabled || num_combos == 0 {
        return None;
    }

    let combo_idx_global = env::var("AQC_GPU_TRACE_COMBO")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(0);
    let combo_end = combo_base.saturating_add(num_combos);
    if combo_idx_global < combo_base || combo_idx_global >= combo_end {
        return None;
    }
    let combo_idx = combo_idx_global - combo_base;

    let sym_idx = env::var("AQC_GPU_TRACE_SYMBOL")
        .ok()
        .and_then(|v| v.parse::<u32>().ok())
        .unwrap_or(GPU_TRACE_SYMBOL_ALL);

    Some((combo_idx, sym_idx))
}

fn debug_t_sec_env() -> u32 {
    env::var("AQC_GPU_DEBUG_T_SEC")
        .ok()
        .and_then(|v| v.parse::<u32>().ok())
        .unwrap_or(0)
}

// ═══════════════════════════════════════════════════════════════════════════
// GpuDeviceState — persistent CUDA device (reused across batches)
// ═══════════════════════════════════════════════════════════════════════════

/// Persistent CUDA device state with both kernel modules loaded.
pub struct GpuDeviceState {
    pub dev: Arc<CudaDevice>,
}

impl GpuDeviceState {
    /// Initialize CUDA device and load PTX kernels.
    ///
    /// Returns `Err` on CUDA init failure or PTX load failure, allowing the
    /// caller to fall back to CPU mode instead of panicking (C6).
    pub fn new() -> Result<Self, String> {
        let dev = CudaDevice::new(0).map_err(|e| {
            format!(
                "CUDA init failed: {e}. \
                 Hint (WSL2): ensure /usr/lib/wsl/lib/libcuda.so.1 exists. \
                 Run `nvidia-smi` to verify the driver is loaded."
            )
        })?;

        // Load sweep engine PTX (trade logic)
        let ptx_sweep = include_str!(concat!(env!("OUT_DIR"), "/sweep_engine.ptx"));
        dev.load_ptx(Ptx::from_src(ptx_sweep), "sweep", &["sweep_engine_kernel"])
            .map_err(|e| format!("Failed to load sweep_engine PTX: {e}"))?;

        // Load indicator kernel PTX (indicator computation + breadth)
        let ptx_ind = include_str!(concat!(env!("OUT_DIR"), "/indicator_kernel.ptx"));
        dev.load_ptx(
            Ptx::from_src(ptx_ind),
            "indicators",
            &["indicator_kernel", "breadth_kernel"],
        )
        .map_err(|e| format!("Failed to load indicator_kernel PTX: {e}"))?;

        let name = dev.name().unwrap_or_else(|_| "unknown".to_string());
        eprintln!("[GPU] CUDA Device: {}", name);

        Ok(Self { dev })
    }

    /// Query (free, total) VRAM in bytes via cuMemGetInfo.
    pub fn vram_info(&self) -> (usize, usize) {
        match cudarc::driver::result::mem_get_info() {
            Ok((free, total)) => (free, total),
            Err(e) => {
                eprintln!("[GPU] WARNING: cuMemGetInfo failed ({e:?}), assuming 24 GiB VRAM");
                let total = 24 * 1024 * 1024 * 1024usize;
                (total * 90 / 100, total)
            }
        }
    }

    pub fn total_vram_bytes(&self) -> usize {
        self.vram_info().1
    }
    pub fn free_vram_bytes(&self) -> usize {
        self.vram_info().0
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// GPU-side indicator computation buffers
// ═══════════════════════════════════════════════════════════════════════════

/// Buffers for GPU-side indicator computation.
/// Raw candles uploaded once; snapshots/breadth/btc_bullish allocated in VRAM.
pub struct IndicatorBuffers {
    pub candles_gpu: CudaSlice<GpuRawCandle>,
    pub ind_configs_gpu: CudaSlice<GpuIndicatorConfig>,
    pub ind_params_gpu: CudaSlice<IndicatorParams>,
    pub snapshots_gpu: CudaSlice<GpuSnapshot>,
    pub breadth_gpu: CudaSlice<f32>,
    pub btc_bullish_gpu: CudaSlice<u32>,
    pub num_ind_combos: u32,
    pub num_symbols: u32,
    pub num_bars: u32,
    pub btc_sym_idx: u32,
    pub paxg_sym_idx: u32,
}

impl IndicatorBuffers {
    /// Create indicator buffers: upload raw candles + indicator configs,
    /// allocate snapshot/breadth/btc_bullish output in VRAM.
    ///
    /// Returns `Err` on GPU memory allocation failure (H11).
    pub fn new(
        ds: &GpuDeviceState,
        candles_gpu: &CudaSlice<GpuRawCandle>,
        ind_configs: &[GpuIndicatorConfig],
        num_bars: u32,
        num_symbols: u32,
        btc_sym_idx: u32,
        paxg_sym_idx: u32,
    ) -> Result<Self, String> {
        let k = ind_configs.len() as u32;

        let ind_configs_gpu = ds
            .dev
            .htod_sync_copy(ind_configs)
            .map_err(|e| format!("GPU: htod ind_configs failed: {e}"))?;

        let params = IndicatorParams {
            num_ind_combos: k,
            num_symbols,
            num_bars,
            btc_sym_idx,
            _pad: [0; 4],
        };
        let ind_params_gpu = ds
            .dev
            .htod_sync_copy(&[params])
            .map_err(|e| format!("GPU: htod ind_params failed: {e}"))?;

        // Allocate output buffers in VRAM (zeroed)
        let snap_count = (k as usize) * (num_bars as usize) * (num_symbols as usize);
        let breadth_count = (k as usize) * (num_bars as usize);

        let snapshots_gpu = ds
            .dev
            .alloc_zeros::<GpuSnapshot>(snap_count)
            .map_err(|e| format!("GPU: alloc snapshots ({snap_count} elems) failed: {e}"))?;
        let breadth_gpu = ds
            .dev
            .alloc_zeros::<f32>(breadth_count)
            .map_err(|e| format!("GPU: alloc breadth ({breadth_count} elems) failed: {e}"))?;
        let btc_bullish_gpu = ds
            .dev
            .alloc_zeros::<u32>(breadth_count)
            .map_err(|e| format!("GPU: alloc btc_bullish ({breadth_count} elems) failed: {e}"))?;

        Ok(Self {
            candles_gpu: candles_gpu.clone(),
            ind_configs_gpu,
            ind_params_gpu,
            snapshots_gpu,
            breadth_gpu,
            btc_bullish_gpu,
            num_ind_combos: k,
            num_symbols,
            num_bars,
            btc_sym_idx,
            paxg_sym_idx,
        })
    }
}

/// Dispatch indicator_kernel + breadth_kernel on GPU.
/// After this returns, snapshots/breadth/btc_bullish are ready in VRAM.
pub fn dispatch_indicator_kernels(
    ds: &GpuDeviceState,
    buffers: &mut IndicatorBuffers,
) -> Result<(), String> {
    let block_size = 64u32;

    // ── Indicator kernel: K × S threads ─────────────────────────────────
    let ind_threads = buffers.num_ind_combos * buffers.num_symbols;
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
                &buffers.ind_params_gpu,
                &buffers.ind_configs_gpu,
                &buffers.candles_gpu,
                &mut buffers.snapshots_gpu,
            ),
        )
    }
    .map_err(|e| format!("indicator_kernel launch failed: {e}"))?;

    // ── Breadth kernel: K × B threads ───────────────────────────────────
    let br_threads = buffers.num_ind_combos * buffers.num_bars;
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
                &buffers.ind_params_gpu,
                &buffers.snapshots_gpu,
                &mut buffers.breadth_gpu,
                &mut buffers.btc_bullish_gpu,
            ),
        )
    }
    .map_err(|e| format!("breadth_kernel launch failed: {e}"))?;

    Ok(())
}

// ═══════════════════════════════════════════════════════════════════════════
// Trade sweep BatchBuffers (uses VRAM-resident snapshots from indicator kernel)
// ═══════════════════════════════════════════════════════════════════════════

/// Buffers for one trade sweep dispatch batch.
/// Snapshots/breadth/btc_bullish come from IndicatorBuffers (already in VRAM).
pub struct BatchBuffers {
    pub candles: Option<CudaSlice<GpuRawCandle>>,
    pub snapshots: CudaSlice<GpuSnapshot>,
    pub breadth: CudaSlice<f32>,
    pub btc_bullish: CudaSlice<u32>,
    pub configs: CudaSlice<GpuComboConfig>,
    pub states: CudaSlice<GpuComboState>,
    pub results: CudaSlice<GpuResult>,
    pub params: CudaSlice<GpuParams>,
    pub num_combos: u32,
    pub num_symbols: u32,
    pub btc_sym_idx: u32,
    pub paxg_sym_idx: u32,
    pub initial_balance: f32,
    pub maker_fee_rate: f32,
    pub taker_fee_rate: f32,
    pub max_sub_per_bar: u32,
    pub entry_interval_sec: u32,
    pub signal_on_candle_close: u32,
    pub sub_candles: Option<Arc<CudaSlice<GpuRawCandle>>>,
    pub sub_counts: Option<Arc<CudaSlice<u32>>>,
    pub funding_spans: Option<Arc<CudaSlice<GpuFundingSpan>>>,
    pub funding_rates: Option<Arc<CudaSlice<f64>>>,
}

impl BatchBuffers {
    /// Create trade sweep buffers using VRAM-resident indicator data.
    /// Snapshots/breadth/btc_bullish are cloned references (VRAM pointers, no copy).
    pub fn from_indicator_buffers(
        ds: &GpuDeviceState,
        ind_bufs: &IndicatorBuffers,
        configs: &[GpuComboConfig],
        initial_balance: f32,
        combo_base: usize,
        maker_fee_rate: f32,
        taker_fee_rate: f32,
    ) -> Result<Self, String> {
        let num_combos = configs.len() as u32;
        let num_bars = ind_bufs.num_bars;
        let num_symbols = ind_bufs.num_symbols;

        let configs_gpu = ds
            .dev
            .htod_sync_copy(configs)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        let mut states_host = vec![GpuComboState::zeroed(); configs.len()];
        for s in &mut states_host {
            s.balance = initial_balance as f64;
            s.kernel_cash = initial_balance as f64;
            s.peak_equity = initial_balance as f64;
        }
        if let Some((combo_idx, sym_idx)) = trace_env_config(combo_base, states_host.len()) {
            states_host[combo_idx].trace_enabled = 1;
            states_host[combo_idx].trace_symbol = sym_idx;
        }
        let states = ds
            .dev
            .htod_sync_copy(&states_host)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;
        let results = ds
            .dev
            .alloc_zeros::<GpuResult>(configs.len())
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        let params_host = GpuParams {
            num_combos,
            num_symbols,
            num_bars,
            btc_sym_idx: ind_bufs.btc_sym_idx,
            paxg_sym_idx: ind_bufs.paxg_sym_idx,
            chunk_start: 0,
            chunk_end: num_bars,
            initial_balance_bits: initial_balance.to_bits(),
            maker_fee_rate_bits: maker_fee_rate.to_bits(),
            taker_fee_rate_bits: taker_fee_rate.to_bits(),
            max_sub_per_bar: 0,
            trade_end_bar: num_bars,
            debug_t_sec: debug_t_sec_env(),
            funding_enabled: 0,
            entry_interval_sec: 0,
            signal_on_candle_close: 0,
        };
        let params = ds
            .dev
            .htod_sync_copy(&[params_host])
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        Ok(Self {
            candles: Some(ind_bufs.candles_gpu.clone()),
            snapshots: ind_bufs.snapshots_gpu.clone(),
            breadth: ind_bufs.breadth_gpu.clone(),
            btc_bullish: ind_bufs.btc_bullish_gpu.clone(),
            configs: configs_gpu,
            states,
            results,
            params,
            num_combos,
            num_symbols,
            btc_sym_idx: ind_bufs.btc_sym_idx,
            paxg_sym_idx: ind_bufs.paxg_sym_idx,
            initial_balance,
            maker_fee_rate,
            taker_fee_rate,
            max_sub_per_bar: 0,
            entry_interval_sec: 0,
            signal_on_candle_close: 0,
            sub_candles: None,
            sub_counts: None,
            funding_spans: None,
            funding_rates: None,
        })
    }

    /// Create GPU buffers from pre-concatenated multi-indicator data (CPU-precomputed path).
    /// Kept for backwards compatibility.
    pub fn new_multi(
        ds: &GpuDeviceState,
        all_snapshots: &[GpuSnapshot],
        all_breadth: &[f32],
        all_btc_bullish: &[u32],
        configs: &[GpuComboConfig],
        initial_balance: f32,
        num_symbols: u32,
        btc_sym_idx: u32,
        paxg_sym_idx: u32,
        num_bars: u32,
        maker_fee_rate: f32,
        taker_fee_rate: f32,
    ) -> Result<Self, String> {
        let num_combos = configs.len() as u32;

        let snapshots = ds
            .dev
            .htod_sync_copy(all_snapshots)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;
        let breadth = ds
            .dev
            .htod_sync_copy(all_breadth)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;
        let btc_bullish = ds
            .dev
            .htod_sync_copy(all_btc_bullish)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;
        let configs_gpu = ds
            .dev
            .htod_sync_copy(configs)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        let mut states_host = vec![GpuComboState::zeroed(); configs.len()];
        for s in &mut states_host {
            s.balance = initial_balance as f64;
            s.kernel_cash = initial_balance as f64;
            s.peak_equity = initial_balance as f64;
        }
        if let Some((combo_idx, sym_idx)) = trace_env_config(0, states_host.len()) {
            states_host[combo_idx].trace_enabled = 1;
            states_host[combo_idx].trace_symbol = sym_idx;
        }
        let states = ds
            .dev
            .htod_sync_copy(&states_host)
            .map_err(|e| format!("GPU alloc failed: {e}"))?;
        let results = ds
            .dev
            .alloc_zeros::<GpuResult>(configs.len())
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        let params_host = GpuParams {
            num_combos,
            num_symbols,
            num_bars,
            btc_sym_idx,
            paxg_sym_idx,
            chunk_start: 0,
            chunk_end: num_bars,
            initial_balance_bits: initial_balance.to_bits(),
            maker_fee_rate_bits: maker_fee_rate.to_bits(),
            taker_fee_rate_bits: taker_fee_rate.to_bits(),
            max_sub_per_bar: 0,
            trade_end_bar: num_bars,
            debug_t_sec: debug_t_sec_env(),
            funding_enabled: 0,
            entry_interval_sec: 0,
            signal_on_candle_close: 0,
        };
        let params = ds
            .dev
            .htod_sync_copy(&[params_host])
            .map_err(|e| format!("GPU alloc failed: {e}"))?;

        Ok(Self {
            candles: None,
            snapshots,
            breadth,
            btc_bullish,
            configs: configs_gpu,
            states,
            results,
            params,
            num_combos,
            num_symbols,
            btc_sym_idx,
            paxg_sym_idx,
            initial_balance,
            maker_fee_rate,
            taker_fee_rate,
            max_sub_per_bar: 0,
            entry_interval_sec: 0,
            signal_on_candle_close: 0,
            sub_candles: None,
            sub_counts: None,
            funding_spans: None,
            funding_rates: None,
        })
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Trade sweep dispatch + readback
// ═══════════════════════════════════════════════════════════════════════════

/// Dispatch the trade sweep CUDA kernel and read back results.
///
/// `trade_start`/`trade_end` scope which bar indices the trade kernel processes.
/// Set to `(0, num_bars)` for full range (backwards compatible).
/// Indicator data must still cover all `num_bars` for snapshot indexing.
pub fn dispatch_and_readback(
    ds: &GpuDeviceState,
    buffers: &mut BatchBuffers,
    num_bars: u32,
    chunk_size: u32,
    trade_start: u32,
    trade_end: u32,
) -> Result<Vec<GpuResult>, String> {
    let block_size = 64u32;
    let grid_size = (buffers.num_combos + block_size - 1) / block_size;

    let trade_range = trade_end - trade_start;
    eprintln!(
        "[gpu] Trade bar range: {}..{} ({} of {} bars)",
        trade_start, trade_end, trade_range, num_bars,
    );

    // Dynamic chunk size: smaller when sub-bars active (TDR mitigation)
    let effective_chunk = if buffers.max_sub_per_bar > 0 {
        chunk_size.min(50)
    } else {
        chunk_size
    };
    let num_chunks = (trade_range + effective_chunk - 1) / effective_chunk;

    // Create sentinel buffers when candle pointers are absent (cudarc requires valid pointers).
    let sentinel_main_candle: CudaSlice<GpuRawCandle>;
    let main_candles_ref = match &buffers.candles {
        Some(c) => c,
        None => {
            sentinel_main_candle = ds
                .dev
                .alloc_zeros::<GpuRawCandle>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            &sentinel_main_candle
        }
    };

    let sentinel_sub_candle: CudaSlice<GpuRawCandle>;
    let sentinel_counts: CudaSlice<u32>;
    let (sub_candles_ref, sub_counts_ref) = match (&buffers.sub_candles, &buffers.sub_counts) {
        (Some(sc), Some(sn)) => (sc.as_ref(), sn.as_ref()),
        _ => {
            sentinel_sub_candle = ds
                .dev
                .alloc_zeros::<GpuRawCandle>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            sentinel_counts = ds
                .dev
                .alloc_zeros::<u32>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            (&sentinel_sub_candle, &sentinel_counts)
        }
    };
    let sentinel_funding_spans: CudaSlice<GpuFundingSpan>;
    let sentinel_funding_rates: CudaSlice<f64>;
    let funding_enabled = buffers.funding_spans.is_some() && buffers.funding_rates.is_some();
    let (funding_spans_ref, funding_rates_ref) = match (&buffers.funding_spans, &buffers.funding_rates) {
        (Some(spans), Some(rates)) => (spans.as_ref(), rates.as_ref()),
        _ => {
            sentinel_funding_spans = ds
                .dev
                .alloc_zeros::<GpuFundingSpan>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            sentinel_funding_rates = ds
                .dev
                .alloc_zeros::<f64>(1)
                .map_err(|e| format!("GPU alloc failed: {e}"))?;
            (&sentinel_funding_spans, &sentinel_funding_rates)
        }
    };

    for chunk_idx in 0..num_chunks {
        let chunk_start = trade_start + chunk_idx * effective_chunk;
        let chunk_end = (chunk_start + effective_chunk).min(trade_end);

        let params_host = GpuParams {
            num_combos: buffers.num_combos,
            num_symbols: buffers.num_symbols,
            num_bars,
            btc_sym_idx: buffers.btc_sym_idx,
            paxg_sym_idx: buffers.paxg_sym_idx,
            chunk_start,
            chunk_end,
            initial_balance_bits: buffers.initial_balance.to_bits(),
            maker_fee_rate_bits: buffers.maker_fee_rate.to_bits(),
            taker_fee_rate_bits: buffers.taker_fee_rate.to_bits(),
            max_sub_per_bar: buffers.max_sub_per_bar,
            trade_end_bar: trade_end,
            debug_t_sec: debug_t_sec_env(),
            funding_enabled: if funding_enabled { 1 } else { 0 },
            entry_interval_sec: buffers.entry_interval_sec,
            signal_on_candle_close: buffers.signal_on_candle_close,
        };
        ds.dev
            .htod_sync_copy_into(&[params_host], &mut buffers.params)
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
                    &buffers.params,
                    &buffers.snapshots,
                    &buffers.breadth,
                    &buffers.btc_bullish,
                    &buffers.configs,
                    &mut buffers.states,
                    &mut buffers.results,
                    main_candles_ref,
                    sub_candles_ref,
                    sub_counts_ref,
                    funding_spans_ref,
                    funding_rates_ref,
                ),
            )
        }
        .map_err(|e| format!("Kernel launch failed: {e}"))?;
    }

    ds.dev
        .dtoh_sync_copy(&buffers.results)
        .map_err(|e| format!("GPU readback failed: {e}"))
}

/// Read back mutable combo states from device.
pub fn readback_states(
    ds: &GpuDeviceState,
    buffers: &BatchBuffers,
) -> Result<Vec<GpuComboState>, String> {
    ds.dev
        .dtoh_sync_copy(&buffers.states)
        .map_err(|e| format!("GPU readback failed: {e}"))
}
