//! Deterministic tp_atr_mult fixture sanity regression.
//!
//! This CPU-only test keeps the synthetic fixture stable and ensures it still
//! reacts to low->high `trade.tp_atr_mult` changes. Runtime CPU/GPU directional
//! parity is validated in `bt-gpu/tests/tp_atr_mult_directional_parity.rs`.

use std::path::PathBuf;

use bt_core::candle::{CandleData, OhlcvBar};
use bt_core::{config, engine};

const INITIAL_BALANCE: f64 = 1000.0;
const TP_AXIS_VALUES: [f64; 4] = [3.0, 4.0, 5.0, 6.0];

fn build_tp_isolation_fixture() -> (CandleData, CandleData) {
    let closes = [100.0, 100.7, 101.3, 101.9, 102.5, 103.1, 103.7, 104.3];
    let rel_path = [
        0.05, 0.10, 0.20, 0.35, 0.55, 0.80, 1.10, 1.45, 1.75, 2.05, 2.20, 2.35, 2.45, 2.50, 2.35,
        2.10, 1.85, 1.60, 1.35, 1.20,
    ];

    let mut main: CandleData = CandleData::default();
    let mut sub: CandleData = CandleData::default();
    let mut main_bars: Vec<OhlcvBar> = Vec::new();
    let mut sub_bars: Vec<OhlcvBar> = Vec::new();

    for (i, close) in closes.iter().enumerate() {
        let t = (i as i64) * 3_600_000;
        let open: f64 = if i == 0 { *close } else { closes[i - 1] };
        let high = open.max(*close) + 0.12;
        let low = open.min(*close) - 0.12;

        main_bars.push(OhlcvBar {
            t,
            t_close: t + 3_600_000,
            o: open,
            h: high,
            l: low,
            c: *close,
            v: 1000.0,
            n: 1,
        });
    }

    for i in 1..closes.len() {
        let base = closes[i - 1];
        let start = ((i - 1) as i64) * 3_600_000;

        for (j, rel) in rel_path.iter().enumerate() {
            let px = base + rel;
            let t = start + ((j as i64) + 1) * 180_000;

            sub_bars.push(OhlcvBar {
                t,
                t_close: t + 180_000,
                o: px,
                h: px + 0.03,
                l: px - 0.03,
                c: px,
                v: 900.0,
                n: 1,
            });
        }
    }

    main.insert("BTC".to_string(), main_bars);
    sub.insert("BTC".to_string(), sub_bars);
    (main, sub)
}

fn sign(x: f64) -> i8 {
    let eps = 1e-9;
    if x > eps {
        1
    } else if x < -eps {
        -1
    } else {
        0
    }
}

#[test]
fn tp_atr_mult_fixture_reacts_to_low_to_high_changes() {
    let crate_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let cfg_path = crate_root.join("../../testdata/gpu_cpu_parity/tp_atr_mult_strategy.yaml");

    let base_cfg = config::load_config(&cfg_path.to_string_lossy(), None, false);
    let (main_candles, sub_candles) = build_tp_isolation_fixture();

    let mut cpu_pnl_by_axis_value: Vec<f64> = Vec::new();

    for tp_mult in TP_AXIS_VALUES {
        let mut cfg = base_cfg.clone();
        cfg.trade.tp_atr_mult = tp_mult;

        let sim = engine::run_simulation(engine::RunSimulationInput {
            candles: &main_candles,
            cfg: &cfg,
            initial_balance: INITIAL_BALANCE,
            lookback: 0,
            exit_candles: Some(&sub_candles),
            entry_candles: Some(&sub_candles),
            funding_rates: None,
            init_state: None,
            from_ts: None,
            to_ts: None,
        });

        cpu_pnl_by_axis_value.push(sim.final_balance - INITIAL_BALANCE);
    }

    let cpu_delta =
        cpu_pnl_by_axis_value[cpu_pnl_by_axis_value.len() - 1] - cpu_pnl_by_axis_value[0];
    assert_ne!(
        sign(cpu_delta),
        0,
        "CPU fixture did not react to tp_atr_mult (first->last delta is ~0)."
    );
}
