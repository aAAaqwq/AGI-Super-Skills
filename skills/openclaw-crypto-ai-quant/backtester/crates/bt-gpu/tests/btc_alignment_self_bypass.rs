use bt_core::config::StrategyConfig;
use bt_core::indicators::IndicatorSnapshot;
use bt_core::signals::gates::check_gates;

fn bullish_snap() -> IndicatorSnapshot {
    IndicatorSnapshot {
        close: 105.0,
        high: 106.0,
        low: 104.0,
        open: 104.5,
        volume: 1200.0,
        t: 0,
        ema_slow: 100.0,
        ema_fast: 102.0,
        ema_macro: 98.0,
        adx: 32.0,
        adx_pos: 22.0,
        adx_neg: 10.0,
        adx_slope: 1.2,
        bb_upper: 108.0,
        bb_lower: 96.0,
        bb_width: 12.0,
        bb_width_avg: 10.0,
        bb_width_ratio: 1.2,
        atr: 1.8,
        atr_slope: 0.1,
        avg_atr: 1.6,
        rsi: 58.0,
        stoch_rsi_k: 0.5,
        stoch_rsi_d: 0.5,
        macd_hist: 0.3,
        prev_macd_hist: 0.2,
        prev2_macd_hist: 0.1,
        prev3_macd_hist: 0.0,
        vol_sma: 800.0,
        vol_trend: true,
        prev_close: 104.0,
        prev_ema_fast: 101.5,
        prev_ema_slow: 99.8,
        bar_count: 200,
        funding_rate: 0.0,
    }
}

fn bearish_snap() -> IndicatorSnapshot {
    IndicatorSnapshot {
        close: 95.0,
        high: 96.0,
        low: 94.0,
        open: 95.5,
        volume: 1200.0,
        t: 0,
        ema_slow: 100.0,
        ema_fast: 98.0,
        ema_macro: 102.0,
        adx: 32.0,
        adx_pos: 10.0,
        adx_neg: 22.0,
        adx_slope: 1.2,
        bb_upper: 104.0,
        bb_lower: 92.0,
        bb_width: 12.0,
        bb_width_avg: 10.0,
        bb_width_ratio: 1.2,
        atr: 1.8,
        atr_slope: 0.1,
        avg_atr: 1.6,
        rsi: 42.0,
        stoch_rsi_k: 0.5,
        stoch_rsi_d: 0.5,
        macd_hist: -0.3,
        prev_macd_hist: -0.2,
        prev2_macd_hist: -0.1,
        prev3_macd_hist: 0.0,
        vol_sma: 800.0,
        vol_trend: true,
        prev_close: 96.0,
        prev_ema_fast: 98.5,
        prev_ema_slow: 100.2,
        bar_count: 200,
        funding_rate: 0.0,
    }
}

#[test]
fn btc_symbol_bypasses_alignment_when_btc_is_bearish() {
    let mut cfg = StrategyConfig::default();
    cfg.filters.require_btc_alignment = true;

    let snap = bullish_snap();

    let btc_gate = check_gates(&snap, &cfg, "BTC", Some(false), 0.001);
    assert!(
        btc_gate.btc_ok_long,
        "BTC symbol must bypass long alignment blocking"
    );
    assert!(
        btc_gate.btc_ok_short,
        "BTC symbol must bypass short alignment blocking"
    );

    let eth_gate = check_gates(&snap, &cfg, "ETH", Some(false), 0.001);
    assert!(
        !eth_gate.btc_ok_long,
        "Non-BTC long should be blocked when BTC is bearish"
    );
    assert!(
        eth_gate.btc_ok_short,
        "Non-BTC short should remain allowed when BTC is bearish"
    );
}

#[test]
fn btc_symbol_bypasses_alignment_when_btc_is_bullish() {
    let mut cfg = StrategyConfig::default();
    cfg.filters.require_btc_alignment = true;

    let snap = bearish_snap();

    let btc_gate = check_gates(&snap, &cfg, "BTC", Some(true), -0.001);
    assert!(
        btc_gate.btc_ok_long,
        "BTC symbol must bypass long alignment blocking"
    );
    assert!(
        btc_gate.btc_ok_short,
        "BTC symbol must bypass short alignment blocking"
    );

    let eth_gate = check_gates(&snap, &cfg, "ETH", Some(true), -0.001);
    assert!(
        eth_gate.btc_ok_long,
        "Non-BTC long should remain allowed when BTC is bullish"
    );
    assert!(
        !eth_gate.btc_ok_short,
        "Non-BTC short should be blocked when BTC is bullish"
    );
}
