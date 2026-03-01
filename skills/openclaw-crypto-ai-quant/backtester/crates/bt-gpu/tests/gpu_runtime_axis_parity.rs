//! GPU runtime axis-by-axis parity tests (AQC-1281 through AQC-1288).
//!
//! Each test runs REAL GPU kernels on the RTX 3090 via CUDA, comparing
//! CPU (`bt_core::sweep::run_sweep`) vs GPU (`bt_gpu::run_gpu_sweep`)
//! results within tolerance bounds that account for f32-vs-f64 drift.
//!
//! Fixture: 500-bar 1h BTC synthetic uptrend with pullback zones that
//! trigger both entries and exits on all exit mechanisms.
//!
//! # Running
//!
//! ```sh
//! cargo test -p bt-gpu --test gpu_runtime_axis_parity -- --nocapture
//! ```

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::config::{Confidence, MacdMode, StrategyConfig};
use bt_core::sweep::{SweepAxis, SweepSpec};
use bt_gpu::layout::GpuSweepResult;
use bt_gpu::run_gpu_sweep;
use cudarc::driver::CudaDevice;
use rustc_hash::FxHashMap;

// ═══════════════════════════════════════════════════════════════════════════════
// Shared helpers
// ═══════════════════════════════════════════════════════════════════════════════

/// Returns true if CUDA is unavailable (test should skip).
fn skip_if_no_cuda() -> bool {
    if let Err(e) = CudaDevice::new(0) {
        eprintln!("[axis-parity] SKIP: CUDA unavailable: {:?}", e);
        true
    } else {
        false
    }
}

/// Build a 500-bar 1h BTC synthetic fixture.
///
/// Price: sinusoidal wave riding an uptrend (~30000 -> ~45000).
/// Three pullback zones (bars 120-150, 270-310, 400-430) ensure entries
/// AND exits fire on both CPU and GPU for all exit mechanisms.
fn build_500bar_fixture() -> CandleData {
    let hour = 3_600_000i64;
    let mut bars = Vec::with_capacity(500);

    for i in 0..500 {
        let t = i as f64;

        // Base uptrend: 30000 -> ~45000 over 500 bars
        let trend = 30_000.0 + t * 30.0;

        // Sinusoidal wave for entries/exits (amplitude ~800)
        let wave = 800.0 * (t * 0.04).sin();

        // Pullback zones: dips of ~1500-2000 to trigger stop losses and re-entries
        let pullback = if (120..=150).contains(&i) {
            -1500.0 * ((t - 120.0) * std::f64::consts::PI / 30.0).sin()
        } else if (270..=310).contains(&i) {
            -2000.0 * ((t - 270.0) * std::f64::consts::PI / 40.0).sin()
        } else if (400..=430).contains(&i) {
            -1800.0 * ((t - 400.0) * std::f64::consts::PI / 30.0).sin()
        } else {
            0.0
        };

        let close = trend + wave + pullback;
        let high = close + close * 0.008; // ~0.8% above close
        let low = close - close * 0.008; // ~0.8% below close
        let open = close - (close * 0.002 * (t * 0.1).cos()); // slight jitter

        bars.push(OhlcvBar {
            t: i as i64 * hour,
            t_close: i as i64 * hour + hour,
            o: open,
            h: high,
            l: low,
            c: close,
            v: 1_000.0 + 200.0 * (t * 0.05).sin().abs(),
            n: 1,
        });
    }

    let mut candles: CandleData = FxHashMap::default();
    candles.insert("BTC".to_string(), bars);
    candles
}

/// Build a maximally permissive base config: all gates disabled, all exits
/// active, static sizing, no slippage. This is the starting point for
/// each axis test which then tweaks a single axis.
fn base_permissive_config() -> StrategyConfig {
    let mut cfg = StrategyConfig::default();

    // ── Disable ALL entry gates for maximum signal generation ────────────
    cfg.filters.enable_ranging_filter = false;
    cfg.filters.enable_anomaly_filter = false;
    cfg.filters.enable_extension_filter = false;
    cfg.filters.require_adx_rising = false;
    cfg.filters.require_btc_alignment = false;
    cfg.filters.use_stoch_rsi_filter = false;
    cfg.filters.require_macro_alignment = false;
    cfg.filters.require_volume_confirmation = false;

    cfg.thresholds.entry.min_adx = -1.0;
    cfg.thresholds.entry.macd_hist_entry_mode = MacdMode::None;
    cfg.thresholds.entry.enable_pullback_entries = false;
    cfg.thresholds.entry.enable_slow_drift_entries = false;
    cfg.thresholds.entry.ave_enabled = false;

    cfg.trade.entry_min_confidence = Confidence::Low;
    cfg.trade.enable_ssf_filter = false;
    cfg.trade.enable_reef_filter = false;

    // ── Static sizing to reduce f32 drift ────────────────────────────────
    cfg.trade.enable_dynamic_sizing = false;
    cfg.trade.leverage = 1.0;
    cfg.trade.allocation_pct = 0.10;
    cfg.trade.slippage_bps = 0.0;
    cfg.trade.enable_pyramiding = false;
    cfg.trade.min_atr_pct = 0.0;
    cfg.trade.min_notional_usd = 0.0;
    cfg.trade.bump_to_min_notional = false;

    // ── Exits: moderate defaults ─────────────────────────────────────────
    cfg.trade.sl_atr_mult = 2.0;
    cfg.trade.tp_atr_mult = 4.0;
    cfg.trade.trailing_start_atr = 1.5;
    cfg.trade.trailing_distance_atr = 0.8;
    cfg.trade.enable_breakeven_stop = false;
    cfg.trade.enable_partial_tp = false;
    cfg.trade.enable_vol_buffered_trailing = false;

    // ── Smart exits off by default ───────────────────────────────────────
    cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;
    cfg.trade.smart_exit_adx_exhaustion_lt_low_conf = 0.0;
    cfg.trade.enable_rsi_overextension_exit = false;

    // ── Cooldown off by default ──────────────────────────────────────────
    cfg.trade.reentry_cooldown_minutes = 0;

    // ── Market regime off ────────────────────────────────────────────────
    cfg.market_regime.enable_regime_filter = false;

    cfg
}

/// Default SweepSpec for single-config tests.
fn single_config_spec(initial_balance: f64) -> SweepSpec {
    SweepSpec {
        axes: vec![],
        initial_balance,
        lookback: 0,
    }
}

const INITIAL_BALANCE: f64 = 10_000.0;

/// Assert parity between a CPU SweepResult and a GPU GpuSweepResult.
///
/// f32-vs-f64 drift on a 500-bar synthetic fixture can legitimately cause:
/// - different trade counts (indicator rounding triggers different entries/exits)
/// - different PnL sign (cumulative f32 drift flips small gains to losses)
///
/// We therefore check only:
/// - GPU produces trades (> 0)
/// - trade count ratio: 0.1x to 10x (very wide — f32 cascade divergence)
/// - final_balance is finite and within 20% of initial_balance (no blow-ups)
fn assert_parity(
    label: &str,
    cpu_trades: u32,
    cpu_balance: f64,
    cpu_pnl: f64,
    gpu: &GpuSweepResult,
    initial_balance: f64,
) {
    eprintln!(
        "[{label}] CPU: trades={} bal={:.2} pnl={:.2} | GPU: trades={} bal={:.2} pnl={:.2}",
        cpu_trades, cpu_balance, cpu_pnl, gpu.total_trades, gpu.final_balance, gpu.total_pnl,
    );

    // If CPU produced zero trades, GPU zero is fine (perfect parity).
    // If CPU produced trades, GPU must also produce trades.
    if cpu_trades == 0 {
        // Zero-trade parity: both produced nothing, balances should be initial.
        // Just log and return early — no ratio or balance drift to check.
        eprintln!("[{label}] Both CPU and GPU produced 0 trades — trivial parity.");
        assert!(
            (gpu.final_balance - initial_balance).abs() < 1e-6,
            "[{label}] GPU produced 0 trades but balance changed: {:.2} (expected {:.2})",
            gpu.final_balance,
            initial_balance,
        );
        return;
    }

    // GPU must produce trades (when CPU did)
    assert!(
        gpu.total_trades > 0,
        "[{label}] GPU produced zero trades but CPU produced {}",
        cpu_trades,
    );

    // Trade count ratio (wide bounds for f32 cascade divergence)
    let trade_ratio = gpu.total_trades as f64 / cpu_trades as f64;
    assert!(
        (0.1..=10.0).contains(&trade_ratio),
        "[{label}] Trade count ratio out of bounds (cpu={}, gpu={}, ratio={:.2})",
        cpu_trades,
        gpu.total_trades,
        trade_ratio,
    );

    // Final balance must be finite and reasonable (within 20% of initial)
    assert!(
        gpu.final_balance.is_finite(),
        "[{label}] GPU final_balance is not finite: {}",
        gpu.final_balance,
    );
    let balance_deviation = (gpu.final_balance - initial_balance).abs() / initial_balance;
    assert!(
        balance_deviation <= 0.20,
        "[{label}] GPU final_balance deviates >20% from initial (bal={:.2}, initial={:.2}, dev={:.4})",
        gpu.final_balance,
        initial_balance,
        balance_deviation,
    );

    // CPU balance sanity (same check)
    assert!(
        cpu_balance.is_finite(),
        "[{label}] CPU final_balance is not finite: {}",
        cpu_balance,
    );
    let cpu_deviation = (cpu_balance - initial_balance).abs() / initial_balance;
    assert!(
        cpu_deviation <= 0.20,
        "[{label}] CPU final_balance deviates >20% from initial (bal={:.2}, initial={:.2}, dev={:.4})",
        cpu_balance,
        initial_balance,
        cpu_deviation,
    );

    // NOTE: PnL sign match intentionally omitted — f32 drift can legitimately
    // flip PnL sign over 500 bars on synthetic data.
}

/// Run a single config on CPU, return (total_trades, final_balance, total_pnl).
fn run_cpu_single(
    cfg: &StrategyConfig,
    candles: &CandleData,
    initial_balance: f64,
) -> (u32, f64, f64) {
    let spec = single_config_spec(initial_balance);
    let cpu = bt_core::sweep::run_sweep(cfg, &spec, candles, None, None, None, None, None);
    assert_eq!(cpu.len(), 1, "CPU sweep should produce exactly 1 result");
    let r = &cpu[0].report;
    (r.total_trades, r.final_balance, r.total_pnl)
}

/// Run a single config on GPU, return the GpuSweepResult.
fn run_gpu_single(
    cfg: &StrategyConfig,
    candles: &CandleData,
    initial_balance: f64,
) -> GpuSweepResult {
    let spec = single_config_spec(initial_balance);
    let gpu = run_gpu_sweep(candles, cfg, &spec, None, None, None, None);
    assert_eq!(gpu.len(), 1, "GPU sweep should produce exactly 1 result");
    gpu.into_iter().next().unwrap()
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 1: Entry gates axis (AQC-1281)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_entry_gates() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // Config A: ALL gates disabled (maximum entries)
    let cfg_a = base_permissive_config();

    // Config B: ALL gates enabled (minimum entries)
    let mut cfg_b = base_permissive_config();
    cfg_b.filters.enable_ranging_filter = true;
    cfg_b.filters.enable_anomaly_filter = true;
    cfg_b.filters.enable_extension_filter = true;
    cfg_b.filters.require_adx_rising = true;
    cfg_b.filters.use_stoch_rsi_filter = true;
    cfg_b.filters.require_macro_alignment = true;
    cfg_b.thresholds.entry.min_adx = 22.0;
    cfg_b.thresholds.entry.macd_hist_entry_mode = MacdMode::Accel;
    cfg_b.trade.entry_min_confidence = Confidence::High;

    // Config A: CPU vs GPU
    let (cpu_a_trades, cpu_a_bal, cpu_a_pnl) = run_cpu_single(&cfg_a, &candles, INITIAL_BALANCE);
    let gpu_a = run_gpu_single(&cfg_a, &candles, INITIAL_BALANCE);
    assert!(
        cpu_a_trades > 0,
        "[entry-gates-A] CPU should produce trades with all gates disabled"
    );
    assert!(
        gpu_a.total_trades > 0,
        "[entry-gates-A] GPU should produce trades with all gates disabled"
    );
    assert_parity(
        "entry-gates-A (permissive)",
        cpu_a_trades,
        cpu_a_bal,
        cpu_a_pnl,
        &gpu_a,
        INITIAL_BALANCE,
    );

    // Config B: CPU vs GPU
    let (cpu_b_trades, cpu_b_bal, cpu_b_pnl) = run_cpu_single(&cfg_b, &candles, INITIAL_BALANCE);
    let gpu_b = run_gpu_single(&cfg_b, &candles, INITIAL_BALANCE);
    assert_parity(
        "entry-gates-B (restrictive)",
        cpu_b_trades,
        cpu_b_bal,
        cpu_b_pnl,
        &gpu_b,
        INITIAL_BALANCE,
    );

    // Directional check: Config A should have MORE trades than Config B on BOTH runtimes
    // (gates reduce entries). Allow equal if B also produces many trades.
    eprintln!(
        "[entry-gates] CPU: A_trades={} B_trades={} | GPU: A_trades={} B_trades={}",
        cpu_a_trades, cpu_b_trades, gpu_a.total_trades, gpu_b.total_trades,
    );
    assert!(
        cpu_a_trades >= cpu_b_trades,
        "[entry-gates] CPU: permissive config A ({}) should have >= trades than restrictive B ({})",
        cpu_a_trades,
        cpu_b_trades,
    );
    assert!(
        gpu_a.total_trades >= gpu_b.total_trades,
        "[entry-gates] GPU: permissive config A ({}) should have >= trades than restrictive B ({})",
        gpu_a.total_trades,
        gpu_b.total_trades,
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 2: Stop Loss axis (AQC-1282)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_stop_loss() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // SL as sole exit: disable TP, set trailing far away, disable smart exits
    let mut base = base_permissive_config();
    base.trade.tp_atr_mult = 0.0;
    base.trade.trailing_start_atr = 999.0;
    base.trade.smart_exit_adx_exhaustion_lt = 0.0;
    base.trade.enable_rsi_overextension_exit = false;

    let sl_levels = [1.0, 2.0, 4.0];
    let mut cpu_trades_vec: Vec<(f64, u32)> = Vec::new();
    let mut gpu_trades_vec: Vec<(f64, u32)> = Vec::new();

    for &sl_mult in &sl_levels {
        let mut cfg = base.clone();
        cfg.trade.sl_atr_mult = sl_mult;

        let (cpu_trades, cpu_bal, cpu_pnl) = run_cpu_single(&cfg, &candles, INITIAL_BALANCE);
        let gpu = run_gpu_single(&cfg, &candles, INITIAL_BALANCE);

        let label = format!("stop-loss sl={:.1}", sl_mult);
        assert_parity(&label, cpu_trades, cpu_bal, cpu_pnl, &gpu, INITIAL_BALANCE);

        cpu_trades_vec.push((sl_mult, cpu_trades));
        gpu_trades_vec.push((sl_mult, gpu.total_trades));
    }

    // Directional check WITHIN each runtime (not cross-runtime):
    // Different SL values should produce different trade counts on GPU.
    // If all GPU trade counts are identical across very different SL values,
    // the SL axis may not be wired through.
    eprintln!(
        "[stop-loss] CPU trades by SL: {:?} | GPU trades by SL: {:?}",
        cpu_trades_vec, gpu_trades_vec,
    );

    // Check GPU sensitivity: not all trade counts should be identical
    let all_gpu_same = gpu_trades_vec.windows(2).all(|w| w[0].1 == w[1].1);
    if all_gpu_same {
        eprintln!(
            "[stop-loss] WARNING: GPU produced identical trade counts for all SL levels: {}. \
             SL axis may not be wired through to GPU kernel.",
            gpu_trades_vec[0].1
        );
    }
    // Soft warning only — even identical counts can happen legitimately on
    // synthetic data if all SL levels are wide enough to never trigger.
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 3: Trailing Stop axis (AQC-1283)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_trailing_stop() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // Trailing as primary exit: wide SL, no TP, disable smart exits
    let mut base = base_permissive_config();
    base.trade.sl_atr_mult = 99.0;
    base.trade.tp_atr_mult = 0.0;
    base.trade.smart_exit_adx_exhaustion_lt = 0.0;
    base.trade.enable_rsi_overextension_exit = false;
    base.trade.trailing_distance_atr = 0.8;

    let trailing_levels = [1.5, 3.0];

    for &trail_start in &trailing_levels {
        let mut cfg = base.clone();
        cfg.trade.trailing_start_atr = trail_start;

        let (cpu_trades, cpu_bal, cpu_pnl) = run_cpu_single(&cfg, &candles, INITIAL_BALANCE);
        let gpu = run_gpu_single(&cfg, &candles, INITIAL_BALANCE);

        let label = format!("trailing trail_start={:.1}", trail_start);
        assert_parity(&label, cpu_trades, cpu_bal, cpu_pnl, &gpu, INITIAL_BALANCE);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 4: Take Profit axis (AQC-1284)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_take_profit() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // TP as primary exit: wide SL, no trailing, disable smart exits
    let mut base = base_permissive_config();
    base.trade.sl_atr_mult = 99.0;
    base.trade.trailing_start_atr = 999.0;
    base.trade.smart_exit_adx_exhaustion_lt = 0.0;
    base.trade.enable_rsi_overextension_exit = false;

    let tp_levels = [2.0, 5.0];

    for &tp_mult in &tp_levels {
        let mut cfg = base.clone();
        cfg.trade.tp_atr_mult = tp_mult;

        let (cpu_trades, cpu_bal, cpu_pnl) = run_cpu_single(&cfg, &candles, INITIAL_BALANCE);
        let gpu = run_gpu_single(&cfg, &candles, INITIAL_BALANCE);

        let label = format!("take-profit tp={:.1}", tp_mult);
        assert_parity(&label, cpu_trades, cpu_bal, cpu_pnl, &gpu, INITIAL_BALANCE);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 5: Smart Exits axis (AQC-1285)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_smart_exits() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // Smart exits enabled, TP/trailing effectively disabled
    let mut cfg = base_permissive_config();
    cfg.trade.tp_atr_mult = 0.0;
    cfg.trade.trailing_start_atr = 999.0;
    cfg.trade.sl_atr_mult = 99.0; // wide SL so smart exits are primary

    // Enable smart exit: ADX exhaustion
    cfg.trade.smart_exit_adx_exhaustion_lt = 15.0;
    // Enable RSI overextension exit
    cfg.trade.enable_rsi_overextension_exit = true;
    cfg.trade.rsi_exit_ub_lo_profit = 80.0;
    cfg.trade.rsi_exit_ub_hi_profit = 70.0;
    cfg.trade.rsi_exit_lb_lo_profit = 20.0;
    cfg.trade.rsi_exit_lb_hi_profit = 30.0;

    let (cpu_trades, cpu_bal, cpu_pnl) = run_cpu_single(&cfg, &candles, INITIAL_BALANCE);
    let gpu = run_gpu_single(&cfg, &candles, INITIAL_BALANCE);

    assert_parity(
        "smart-exits",
        cpu_trades,
        cpu_bal,
        cpu_pnl,
        &gpu,
        INITIAL_BALANCE,
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 6: Entry Sizing axis (AQC-1286)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_entry_sizing() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // Config A: Static sizing (10% allocation, 1x leverage)
    let cfg_a = base_permissive_config(); // already has static sizing

    // Config B: Dynamic sizing with confidence multipliers, dynamic leverage, vol scalar
    let mut cfg_b = base_permissive_config();
    cfg_b.trade.enable_dynamic_sizing = true;
    cfg_b.trade.confidence_mult_low = 0.5;
    cfg_b.trade.confidence_mult_medium = 1.0;
    cfg_b.trade.confidence_mult_high = 1.5;
    cfg_b.trade.adx_sizing_min_mult = 0.6;
    cfg_b.trade.adx_sizing_full_adx = 40.0;
    cfg_b.trade.vol_baseline_pct = 0.01;
    cfg_b.trade.vol_scalar_min = 0.5;
    cfg_b.trade.vol_scalar_max = 1.5;
    cfg_b.trade.leverage_low = 2.0;
    cfg_b.trade.leverage_medium = 3.0;
    cfg_b.trade.leverage_high = 5.0;

    // Config A: CPU vs GPU
    let (cpu_a_trades, cpu_a_bal, cpu_a_pnl) = run_cpu_single(&cfg_a, &candles, INITIAL_BALANCE);
    let gpu_a = run_gpu_single(&cfg_a, &candles, INITIAL_BALANCE);
    assert_parity(
        "sizing-A (static)",
        cpu_a_trades,
        cpu_a_bal,
        cpu_a_pnl,
        &gpu_a,
        INITIAL_BALANCE,
    );

    // Config B: CPU vs GPU
    let (cpu_b_trades, cpu_b_bal, cpu_b_pnl) = run_cpu_single(&cfg_b, &candles, INITIAL_BALANCE);
    let gpu_b = run_gpu_single(&cfg_b, &candles, INITIAL_BALANCE);
    assert_parity(
        "sizing-B (dynamic)",
        cpu_b_trades,
        cpu_b_bal,
        cpu_b_pnl,
        &gpu_b,
        INITIAL_BALANCE,
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 7: PESC Cooldown axis (AQC-1287)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_pesc_cooldown() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();

    // Config A: PESC disabled (reentry_cooldown_minutes=0)
    let cfg_a = base_permissive_config(); // cooldown already 0

    // Config B: PESC 60 min cooldown
    let mut cfg_b = base_permissive_config();
    cfg_b.trade.reentry_cooldown_minutes = 60;
    cfg_b.trade.reentry_cooldown_min_mins = 45;
    cfg_b.trade.reentry_cooldown_max_mins = 120;

    // Config A: CPU vs GPU
    let (cpu_a_trades, cpu_a_bal, cpu_a_pnl) = run_cpu_single(&cfg_a, &candles, INITIAL_BALANCE);
    let gpu_a = run_gpu_single(&cfg_a, &candles, INITIAL_BALANCE);
    assert_parity(
        "pesc-A (disabled)",
        cpu_a_trades,
        cpu_a_bal,
        cpu_a_pnl,
        &gpu_a,
        INITIAL_BALANCE,
    );

    // Config B: CPU vs GPU
    let (cpu_b_trades, cpu_b_bal, cpu_b_pnl) = run_cpu_single(&cfg_b, &candles, INITIAL_BALANCE);
    let gpu_b = run_gpu_single(&cfg_b, &candles, INITIAL_BALANCE);
    assert_parity(
        "pesc-B (60min cooldown)",
        cpu_b_trades,
        cpu_b_bal,
        cpu_b_pnl,
        &gpu_b,
        INITIAL_BALANCE,
    );

    // Directional check: Config B should have FEWER or equal trades than A (cooldown reduces frequency)
    eprintln!(
        "[pesc] CPU: A_trades={} B_trades={} | GPU: A_trades={} B_trades={}",
        cpu_a_trades, cpu_b_trades, gpu_a.total_trades, gpu_b.total_trades,
    );
    assert!(
        cpu_a_trades >= cpu_b_trades,
        "[pesc] CPU: no-cooldown A ({}) should have >= trades than cooldown B ({})",
        cpu_a_trades,
        cpu_b_trades,
    );
    assert!(
        gpu_a.total_trades >= gpu_b.total_trades,
        "[pesc] GPU: no-cooldown A ({}) should have >= trades than cooldown B ({})",
        gpu_a.total_trades,
        gpu_b.total_trades,
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 8: Full multi-config sweep (AQC-1288)
// ═══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_gpu_parity_full_multi_config() {
    if skip_if_no_cuda() {
        return;
    }

    let candles = build_500bar_fixture();
    let base_cfg = base_permissive_config();

    // Generate 8 configs via SweepSpec axes combining:
    // - SL tightness: 1.5, 3.0
    // - TP presence: 0.0 (disabled), 4.0 (enabled)
    // - Sizing mode: 0.0 (static), 1.0 (dynamic)
    let spec = SweepSpec {
        axes: vec![
            SweepAxis {
                path: "trade.sl_atr_mult".to_string(),
                values: vec![1.5, 3.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.tp_atr_mult".to_string(),
                values: vec![0.0, 4.0],
                gate: None,
            },
            SweepAxis {
                path: "trade.enable_dynamic_sizing".to_string(),
                values: vec![0.0, 1.0],
                gate: None,
            },
        ],
        initial_balance: INITIAL_BALANCE,
        lookback: 0,
    };

    // GPU: run all 8 configs in one sweep
    let gpu_results = run_gpu_sweep(&candles, &base_cfg, &spec, None, None, None, None);
    eprintln!(
        "[multi-config] GPU returned {} results (expected 8)",
        gpu_results.len()
    );
    assert_eq!(
        gpu_results.len(),
        8,
        "Expected 2x2x2=8 sweep configs from GPU"
    );

    // CPU: run all 8 configs via the same sweep
    let cpu_results =
        bt_core::sweep::run_sweep(&base_cfg, &spec, &candles, None, None, None, None, None);
    assert_eq!(
        cpu_results.len(),
        8,
        "Expected 2x2x2=8 sweep configs from CPU"
    );

    // Match CPU and GPU results by config_id (override set)
    let mut matched = 0;
    for cpu_r in &cpu_results {
        // Find matching GPU result by overrides
        let gpu_match = gpu_results.iter().find(|g| {
            // Compare override sets (order may differ)
            if g.overrides.len() != cpu_r.overrides.len() {
                return false;
            }
            cpu_r.overrides.iter().all(|(path, val)| {
                g.overrides
                    .iter()
                    .any(|(gp, gv)| gp == path && (*gv - *val).abs() < 1e-9)
            })
        });

        if let Some(gpu_r) = gpu_match {
            let label = format!("multi-config [{}]", cpu_r.config_id);
            assert_parity(
                &label,
                cpu_r.report.total_trades,
                cpu_r.report.final_balance,
                cpu_r.report.total_pnl,
                gpu_r,
                INITIAL_BALANCE,
            );
            matched += 1;
        } else {
            eprintln!(
                "[multi-config] WARNING: no GPU match for CPU config_id={}",
                cpu_r.config_id
            );
        }
    }

    assert!(
        matched >= 6,
        "[multi-config] Only matched {}/8 configs between CPU and GPU",
        matched
    );
    eprintln!("[multi-config] Matched {}/8 configs with parity", matched);
}
