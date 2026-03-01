use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::config::{Confidence, MacdMode, StrategyConfig};
use bt_core::sweep::SweepSpec;
use bt_gpu::run_gpu_sweep;
use cudarc::driver::CudaDevice;
use rustc_hash::FxHashMap;

fn bar_1h(t: i64, close: f64) -> OhlcvBar {
    OhlcvBar {
        t,
        t_close: t + 3_600_000,
        o: close,
        h: close + 1.0,
        l: close - 1.0,
        c: close,
        v: 1_000.0,
        n: 1,
    }
}

fn bar_3m(t: i64, close: f64) -> OhlcvBar {
    OhlcvBar {
        t,
        t_close: t + 180_000,
        o: close,
        h: close,
        l: close,
        c: close,
        v: 1_000.0,
        n: 1,
    }
}

#[test]
fn cpu_gpu_parity_sweep_1h_3m_tiny_fixture() {
    if let Err(e) = CudaDevice::new(0) {
        eprintln!("Skipping: CUDA unavailable: {:?}", e);
        return;
    }

    // Build a 200-bar fixture with a clear uptrend so default-window
    // indicators warm up (ADX=14, EMA_slow=26 need ~30 bars).
    let hour = 3_600_000i64;
    let mut bars_1h = Vec::new();
    for i in 0..200 {
        // Steady uptrend with some noise: ~100 → ~300 over 200 bars
        let close = 100.0 + i as f64 + (i as f64 * 0.1).sin() * 2.0;
        bars_1h.push(bar_1h(i as i64 * hour, close));
    }
    let mut candles: CandleData = FxHashMap::default();
    candles.insert("BTC".to_string(), bars_1h);

    // No sub-bar exit candles — let trades close via SL/trailing on main bars.
    let exit_candles: CandleData = FxHashMap::default();

    let mut cfg = StrategyConfig::default();

    // Make entry permissive and deterministic (avoid depending on ADX/MACD/StochRSI).
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

    // Disable entry-time trade filters that can suppress trades on short fixtures.
    cfg.trade.enable_ssf_filter = false;
    cfg.trade.enable_reef_filter = false;

    // Reduce sources of CPU f64 vs GPU f32 drift.
    cfg.trade.enable_dynamic_sizing = false;
    cfg.trade.leverage = 1.0;
    cfg.trade.allocation_pct = 0.10;
    cfg.trade.slippage_bps = 0.0;
    cfg.trade.enable_pyramiding = false;
    cfg.trade.enable_rsi_overextension_exit = false;
    cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;
    cfg.trade.min_atr_pct = 0.0;

    // Use default indicator windows — they need ~30 bars to warm up
    // which the 200-bar fixture provides with margin.

    let spec = SweepSpec {
        axes: vec![],
        initial_balance: 1_000.0,
        lookback: 0,
    };

    let cpu = bt_core::sweep::run_sweep(
        &cfg, &spec, &candles, None, // no sub-bar candles
        None, None, None, None,
    );
    assert_eq!(cpu.len(), 1);
    let cpu_rpt = &cpu[0].report;
    eprintln!(
        "[diag] CPU: trades={} wins={} bal={:.2} pnl={:.2}",
        cpu_rpt.total_trades, cpu_rpt.total_wins, cpu_rpt.final_balance, cpu_rpt.total_pnl
    );
    assert!(
        cpu_rpt.total_trades > 0,
        "Fixture should produce at least one trade on CPU (got 0)"
    );

    let gpu = run_gpu_sweep(&candles, &cfg, &spec, None, None, None, None);
    assert_eq!(gpu.len(), 1);
    let gpu_rpt = &gpu[0];
    eprintln!(
        "[diag] GPU: trades={} wins={} bal={:.2} pnl={:.2}",
        gpu_rpt.total_trades, gpu_rpt.total_wins, gpu_rpt.final_balance, gpu_rpt.total_pnl
    );
    assert!(
        gpu_rpt.total_trades > 0,
        "Fixture should produce at least one trade on GPU (got 0)"
    );

    // Parity: trade counts should match exactly or be very close.
    let trade_ratio = gpu_rpt.total_trades as f64 / cpu_rpt.total_trades.max(1) as f64;
    assert!(
        (0.5..=2.0).contains(&trade_ratio),
        "Trade count mismatch (cpu={}, gpu={}, ratio={:.2})",
        cpu_rpt.total_trades,
        gpu_rpt.total_trades,
        trade_ratio
    );

    // Parity: allow differences due to f32 vs f64 math.
    let balance_rel_err =
        (cpu_rpt.final_balance - gpu_rpt.final_balance).abs() / spec.initial_balance;
    assert!(
        balance_rel_err <= 0.05,
        "final_balance drift too large (cpu={:.2}, gpu={:.2}, rel_err={:.4})",
        cpu_rpt.final_balance,
        gpu_rpt.final_balance,
        balance_rel_err
    );

    let pnl_rel_err = (cpu_rpt.total_pnl - gpu_rpt.total_pnl).abs() / spec.initial_balance;
    assert!(
        pnl_rel_err <= 0.05,
        "total_pnl drift too large (cpu={:.2}, gpu={:.2}, rel_err={:.4})",
        cpu_rpt.total_pnl,
        gpu_rpt.total_pnl,
        pnl_rel_err
    );

    eprintln!(
        "[cpu-gpu-parity] cpu: trades={} bal={:.2} pnl={:.2} | gpu: trades={} bal={:.2} pnl={:.2} | balance_err={:.6}",
        cpu_rpt.total_trades, cpu_rpt.final_balance, cpu_rpt.total_pnl,
        gpu_rpt.total_trades, gpu_rpt.final_balance, gpu_rpt.total_pnl,
        balance_rel_err
    );
}
