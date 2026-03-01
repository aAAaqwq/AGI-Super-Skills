//! tp_atr_mult directional parity: CPU f64 vs GPU f32.
//!
//! Uses a 200-bar 3-symbol sawtooth uptrend fixture with default indicator
//! windows.  Verifies that sweeping `tp_atr_mult` from low to high produces
//! the same PnL direction change on both CPU and GPU.
//!
//! The sawtooth price pattern creates clear TP-exit opportunities:
//!   - 15 bars up (+0.8%/bar) followed by 5 bars down (−0.4%/bar)
//!   - 10 full cycles over 200 bars
//!   - 3 symbols to dampen per-symbol f32 cascade divergence
//!
//! With SL disabled (99 ATR) and no trailing, TP is the only active exit
//! mechanism, making the directional relationship strong and robust.
//!
//! Replaces the original 8-bar single-symbol fixture which was too short
//! for GPU indicator warmup and suffered severe f32 cascade divergence.

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::config::{Confidence, MacdMode, StrategyConfig};
use bt_core::engine;
use bt_core::sweep::{SweepAxis, SweepSpec};
use cudarc::driver::CudaDevice;
use rustc_hash::FxHashMap;

const INITIAL_BALANCE: f64 = 10_000.0;
const TP_AXIS_VALUES: [f64; 4] = [1.5, 3.0, 5.0, 8.0];

fn bar_1h(t: i64, o: f64, h: f64, l: f64, c: f64) -> OhlcvBar {
    OhlcvBar {
        t,
        t_close: t + 3_600_000,
        o,
        h,
        l,
        c,
        v: 1_000.0,
        n: 1,
    }
}

/// 200-bar sawtooth uptrend for a single symbol.
///
/// Each cycle: 15 bars up (`+up_pct` per bar) then 5 bars down (`−down_pct`).
/// Net effect is a strong uptrend with clear pullback zones.
fn build_symbol_bars(base_price: f64, up_pct: f64, down_pct: f64) -> Vec<OhlcvBar> {
    let hour = 3_600_000i64;
    let mut bars = Vec::with_capacity(200);
    let mut price = base_price;
    for i in 0..200 {
        let open = price;
        if (i % 20) < 15 {
            price *= 1.0 + up_pct;
        } else {
            price *= 1.0 - down_pct;
        }
        let close = price;
        let high = open.max(close) * 1.003;
        let low = open.min(close) * 0.997;
        bars.push(bar_1h(i as i64 * hour, open, high, low, close));
    }
    bars
}

/// 3-symbol fixture: BTC, ETH, SOL with slightly different volatilities
/// to dampen f32 single-symbol cascade divergence.
fn build_fixture() -> CandleData {
    let mut candles: CandleData = FxHashMap::default();
    candles.insert("BTC".to_string(), build_symbol_bars(100.0, 0.008, 0.004));
    candles.insert("ETH".to_string(), build_symbol_bars(3.0, 0.009, 0.005));
    candles.insert("SOL".to_string(), build_symbol_bars(0.10, 0.007, 0.003));
    candles
}

/// Permissive entry, TP-only exit config with default indicator windows.
fn make_tp_isolation_config() -> StrategyConfig {
    let mut cfg = StrategyConfig::default();

    // ── Permissive entry (same pattern as cpu_gpu_parity_sweep_1h_3m) ──
    cfg.filters.enable_ranging_filter = false;
    cfg.filters.enable_anomaly_filter = false;
    cfg.filters.enable_extension_filter = false;
    cfg.filters.require_adx_rising = false;
    cfg.filters.require_btc_alignment = false;
    cfg.filters.use_stoch_rsi_filter = false;
    cfg.filters.require_macro_alignment = false;
    cfg.thresholds.entry.min_adx = -1.0;
    cfg.thresholds.entry.macd_hist_entry_mode = MacdMode::None;
    cfg.trade.entry_min_confidence = Confidence::Low;
    cfg.trade.enable_ssf_filter = false;
    cfg.trade.enable_reef_filter = false;

    // ── TP-only exit: disable SL, trailing, smart exits ──
    cfg.trade.sl_atr_mult = 99.0;
    cfg.trade.trailing_start_atr = 99.0;
    cfg.trade.trailing_distance_atr = 99.0;
    cfg.trade.enable_breakeven_stop = false;
    cfg.trade.enable_rsi_overextension_exit = false;
    cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;

    // ── Reduce f32 drift sources ──
    cfg.trade.enable_dynamic_sizing = false;
    cfg.trade.leverage = 1.0;
    cfg.trade.allocation_pct = 0.10;
    cfg.trade.slippage_bps = 0.0;
    cfg.trade.enable_pyramiding = false;
    cfg.trade.min_atr_pct = 0.0;

    // Default indicator windows from StrategyConfig::default():
    //   ema_fast=12, ema_slow=26, adx=14, atr=14, rsi=14, ...
    // 200-bar fixture provides ample warmup.

    cfg
}

fn sign(x: f64) -> i8 {
    if x > 1e-6 {
        1
    } else if x < -1e-6 {
        -1
    } else {
        0
    }
}

#[test]
fn tp_atr_mult_first_to_last_direction_matches_gpu_runtime() {
    if let Err(e) = CudaDevice::new(0) {
        eprintln!("Skipping: CUDA unavailable: {:?}", e);
        return;
    }

    let candles = build_fixture();
    let cfg = make_tp_isolation_config();

    // ── CPU: run each TP value individually ──
    let mut cpu_pnl: Vec<f64> = Vec::new();
    for &tp_mult in &TP_AXIS_VALUES {
        let mut c = cfg.clone();
        c.trade.tp_atr_mult = tp_mult;
        let sim = engine::run_simulation(engine::RunSimulationInput {
            candles: &candles,
            cfg: &c,
            initial_balance: INITIAL_BALANCE,
            lookback: 0,
            exit_candles: None,
            entry_candles: None,
            funding_rates: None,
            init_state: None,
            from_ts: None,
            to_ts: None,
        });
        cpu_pnl.push(sim.final_balance - INITIAL_BALANCE);
    }

    // ── GPU: sweep via SweepSpec ──
    let spec = SweepSpec {
        axes: vec![SweepAxis {
            path: "trade.tp_atr_mult".to_string(),
            values: TP_AXIS_VALUES.to_vec(),
            gate: None,
        }],
        initial_balance: INITIAL_BALANCE,
        lookback: 0,
    };

    let gpu_results = bt_gpu::run_gpu_sweep(&candles, &cfg, &spec, None, None, None, None);

    // Map GPU results back to axis order
    let mut gpu_pnl = vec![f64::NAN; TP_AXIS_VALUES.len()];
    for result in &gpu_results {
        let tp_mult = result
            .overrides
            .iter()
            .find_map(|(path, value)| (path == "trade.tp_atr_mult").then_some(*value))
            .unwrap_or(cfg.trade.tp_atr_mult);

        let idx = TP_AXIS_VALUES
            .iter()
            .position(|v| (tp_mult - v).abs() < 1e-9)
            .expect("unexpected tp_atr_mult override from GPU");

        gpu_pnl[idx] = result.final_balance - INITIAL_BALANCE;
    }

    assert!(
        gpu_pnl.iter().all(|v| !v.is_nan()),
        "Missing GPU results for some TP axis values"
    );

    // ── Diagnostics ──
    for (i, &tp) in TP_AXIS_VALUES.iter().enumerate() {
        eprintln!(
            "[diag] tp_atr_mult={:.1}: CPU PnL={:.2}, GPU PnL={:.2}",
            tp, cpu_pnl[i], gpu_pnl[i]
        );
    }

    let cpu_delta = cpu_pnl[cpu_pnl.len() - 1] - cpu_pnl[0];
    let gpu_delta = gpu_pnl[gpu_pnl.len() - 1] - gpu_pnl[0];
    eprintln!(
        "[diag] cpu_delta={:.6}, gpu_delta={:.6}",
        cpu_delta, gpu_delta
    );

    // Both must react (non-degenerate fixture)
    assert_ne!(
        sign(cpu_delta),
        0,
        "CPU fixture degenerate (delta ~0): {:?}",
        cpu_pnl
    );
    assert_ne!(
        sign(gpu_delta),
        0,
        "GPU fixture degenerate (delta ~0): {:?}",
        gpu_pnl
    );

    // Directional parity
    assert_eq!(
        sign(cpu_delta),
        sign(gpu_delta),
        "Directional parity: cpu_delta={:.6}, gpu_delta={:.6}\n  cpu={:?}\n  gpu={:?}",
        cpu_delta,
        gpu_delta,
        cpu_pnl,
        gpu_pnl,
    );
}
