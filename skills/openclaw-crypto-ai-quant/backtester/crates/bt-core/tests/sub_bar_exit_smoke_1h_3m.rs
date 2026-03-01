use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::config::{Confidence, StrategyConfig};
use bt_core::engine::{run_simulation, RunSimulationInput};
use bt_core::position::{Position, PositionType};
use rustc_hash::FxHashMap;

fn bar(t: i64, close: f64) -> OhlcvBar {
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

#[test]
fn exit_sub_bars_change_outcomes() {
    let mut candles: CandleData = FxHashMap::default();
    candles.insert(
        "BTC".to_string(),
        vec![bar(0, 100.0), bar(3_600_000, 100.0)],
    );

    let mut exit_candles: CandleData = FxHashMap::default();
    // In (ts0, ts1] => should be scanned for the first main bar.
    exit_candles.insert("BTC".to_string(), vec![sub_bar(180_000, 97.0)]);

    let mut cfg = StrategyConfig::default();
    // Keep the test focused on sub-bar exits rather than ancillary exit rules.
    cfg.trade.enable_rsi_overextension_exit = false;
    cfg.trade.smart_exit_adx_exhaustion_lt = 0.0;
    cfg.filters.require_macro_alignment = false;

    let pos = Position {
        symbol: "BTC".to_string(),
        pos_type: PositionType::Long,
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
    };

    let mut positions = FxHashMap::default();
    positions.insert("BTC".to_string(), pos);

    let with_exit = run_simulation(RunSimulationInput {
        candles: &candles,
        cfg: &cfg,
        initial_balance: 1_000.0,
        lookback: 0,
        exit_candles: Some(&exit_candles),
        entry_candles: None,
        funding_rates: None,
        init_state: Some((
            1_000.0,
            positions.clone(),
            FxHashMap::default(),
            FxHashMap::default(),
        )),
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
        init_state: Some((1_000.0, positions, FxHashMap::default(), FxHashMap::default())),
        from_ts: None,
        to_ts: None,
    });

    assert!(with_exit.final_balance < without_exit.final_balance);

    assert_eq!(with_exit.trades.len(), 1);
    assert_eq!(with_exit.trades[0].reason, "Stop Loss");
    assert_eq!(without_exit.trades.len(), 1);
    assert_eq!(without_exit.trades[0].reason, "End of Backtest");
}
