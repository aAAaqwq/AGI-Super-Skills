use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::config::{Confidence, MacdMode, StrategyConfig};
use bt_core::engine::{run_simulation, RunSimulationInput};
use rustc_hash::FxHashMap;

fn candle(t: i64, close: f64) -> OhlcvBar {
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

fn sub_bar(t: i64, close: f64) -> OhlcvBar {
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

fn permissive_cfg() -> StrategyConfig {
    let mut cfg = StrategyConfig::default();

    cfg.trade.entry_min_confidence = Confidence::Low;
    cfg.trade.enable_ssf_filter = false;
    cfg.trade.enable_reef_filter = false;

    cfg.filters.enable_ranging_filter = false;
    cfg.filters.enable_anomaly_filter = false;
    cfg.filters.enable_extension_filter = false;
    cfg.filters.require_volume_confirmation = false;
    cfg.filters.use_stoch_rsi_filter = false;
    cfg.filters.require_btc_alignment = false;
    cfg.filters.require_adx_rising = false;
    cfg.filters.require_macro_alignment = false;

    cfg.indicators.ema_fast_window = 2;
    cfg.indicators.ema_slow_window = 3;
    cfg.thresholds.entry.min_adx = -1.0;
    cfg.thresholds.entry.max_dist_ema_fast = 1.0;
    cfg.thresholds.entry.macd_hist_entry_mode = MacdMode::None;
    cfg.thresholds.tp_and_momentum.rsi_long_weak = 0.0;
    cfg.thresholds.tp_and_momentum.rsi_long_strong = 0.0;
    cfg.thresholds.tp_and_momentum.rsi_short_weak = 100.0;
    cfg.thresholds.tp_and_momentum.rsi_short_strong = 100.0;

    cfg
}

#[test]
fn bar_close_vs_partial_bar_exits_close_earlier() {
    let mut candles: CandleData = FxHashMap::default();
    candles.insert(
        "BTC".to_string(),
        vec![candle(0, 100.0), candle(3_600_000, 100.0)],
    );

    let mut exit_candles: CandleData = FxHashMap::default();
    // In (ts0, ts1] this sub-bar breaches the hard stop before main close.
    exit_candles.insert("BTC".to_string(), vec![sub_bar(1_800_000, 97.0)]);

    let mut cfg = permissive_cfg();
    // Keep focus on stop-loss semantics.
    cfg.trade.enable_rsi_overextension_exit = false;
    cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;
    cfg.filters.require_macro_alignment = false;

    let mut pos = FxHashMap::default();
    pos.insert(
        "BTC".to_string(),
        bt_core::position::Position {
            symbol: "BTC".to_string(),
            pos_type: bt_core::position::PositionType::Long,
            entry_price: 100.0,
            size: 1.0,
            confidence: Confidence::High,
            entry_atr: 1.0,
            entry_adx_threshold: 0.0,
            trailing_sl: None,
            leverage: 1.0,
            margin_used: 100.0,
            adds_count: 0,
            tp1_taken: false,
            open_time_ms: 0,
            last_add_time_ms: 0,
            mae_usd: 0.0,
            mfe_usd: 0.0,
        },
    );

    let with_exit = run_simulation(RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance: 1_000.0,
        lookback: 0,
        exit_candles: Some(&exit_candles),
        entry_candles: None,
        funding_rates: None,
        init_state: Some((1_000.0, pos.clone(), FxHashMap::default(), FxHashMap::default())),
        from_ts: None,
        to_ts: None,
    });

    let without_exit = run_simulation(RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance: 1_000.0,
        lookback: 0,
        exit_candles: None,
        entry_candles: None,
        funding_rates: None,
        init_state: Some((1_000.0, pos, FxHashMap::default(), FxHashMap::default())),
        from_ts: None,
        to_ts: None,
    });

    assert!(with_exit.final_balance < without_exit.final_balance);
    let exit_trade = with_exit
        .trades
        .iter()
        .find(|t| t.action == "CLOSE_LONG")
        .expect("sub-bar path should close position");
    assert_eq!(exit_trade.reason, "Stop Loss");
    assert_eq!(exit_trade.timestamp_ms, 1_800_000);

    let eob_trade = without_exit
        .trades
        .iter()
        .find(|t| t.action == "CLOSE_LONG")
        .expect("fallback path should close at bar close");
    assert_eq!(eob_trade.reason, "End of Backtest");
    assert_eq!(eob_trade.timestamp_ms, 3_600_000);
}

#[test]
fn warmup_bar_count_blocks_entry_until_lookback_boundary() {
    let mut candles: CandleData = FxHashMap::default();
    candles.insert(
        "BTC".to_string(),
        vec![
            candle(0, 100.0),
            candle(60_000, 101.0),
            candle(120_000, 102.0),
        ],
    );

    let cfg = permissive_cfg();
    let sim = run_simulation(RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance: 1_000.0,
        lookback: 2,
        exit_candles: None,
        entry_candles: None,
        funding_rates: None,
        init_state: None,
        from_ts: None,
        to_ts: None,
    });

    let opens: Vec<_> = sim
        .trades
        .iter()
        .filter(|t| t.action == "OPEN_LONG")
        .collect();

    assert_eq!(opens.len(), 1);
    assert_eq!(opens[0].timestamp_ms, 60_000);
    let expected_price = 101.0 * (1.0 + cfg.trade.slippage_bps / 10_000.0);
    assert!(
        (opens[0].price - expected_price).abs() < 1e-6,
        "price {:.10} should be close to {:.10}",
        opens[0].price,
        expected_price,
    );
}

#[test]
fn missing_candle_delays_symbol_eligibility_for_entry() {
    let mut candles: CandleData = FxHashMap::default();
    candles.insert(
        "BTC".to_string(),
        vec![
            candle(0, 100.0),
            candle(60_000, 101.0),
            candle(120_000, 102.0),
        ],
    );
    // ETH misses the middle bar and therefore warms later.
    candles.insert(
        "ETH".to_string(),
        vec![candle(0, 100.0), candle(120_000, 101.0)],
    );

    let cfg = permissive_cfg();
    let sim = run_simulation(RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance: 1_000.0,
        lookback: 2,
        exit_candles: None,
        entry_candles: None,
        funding_rates: None,
        init_state: None,
        from_ts: None,
        to_ts: None,
    });

    let btc_open = sim
        .trades
        .iter()
        .find(|t| t.symbol == "BTC" && t.action == "OPEN_LONG")
        .expect("BTC should open after 2 observed bars");
    let eth_open = sim
        .trades
        .iter()
        .find(|t| t.symbol == "ETH" && t.action == "OPEN_LONG")
        .expect("ETH should open after its 2nd observed bar");

    assert_eq!(btc_open.timestamp_ms, 60_000);
    assert_eq!(eth_open.timestamp_ms, 120_000);
}
