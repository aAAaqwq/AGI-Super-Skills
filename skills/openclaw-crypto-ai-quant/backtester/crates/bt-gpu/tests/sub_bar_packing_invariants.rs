use bt_core::candle::{CandleData, OhlcvBar};
use bt_gpu::raw_candles::prepare_sub_bar_candles;
use rustc_hash::FxHashMap;

fn sub_bar(t: i64, close: f64) -> OhlcvBar {
    OhlcvBar {
        t,
        t_close: t + 180_000,
        o: close,
        h: close,
        l: close,
        c: close,
        v: 1.0,
        n: 1,
    }
}

#[test]
fn union_tick_packing_and_sub_counts_are_consistent() {
    let main_ts: Vec<i64> = vec![1_000, 2_000, 3_000];
    let symbols: Vec<String> = vec!["BTC".to_string(), "ETH".to_string()];

    let mut sub: CandleData = FxHashMap::default();
    sub.insert(
        "BTC".to_string(),
        vec![
            sub_bar(1_000, 99.0), // t <= main_ts[0] => dropped
            sub_bar(1_500, 10.0),
            sub_bar(2_001, 11.0),
            sub_bar(3_500, 12.0), // t > main_ts[last] => last bar
        ],
    );
    sub.insert(
        "ETH".to_string(),
        vec![
            sub_bar(2_000, 20.0), // t == main_ts[1] => previous bar (bar 0)
            sub_bar(3_500, 21.0),
        ],
    );

    let res = prepare_sub_bar_candles(&main_ts, &sub, &symbols);

    assert_eq!(res.num_bars, main_ts.len());
    assert_eq!(res.num_symbols, symbols.len());
    assert_eq!(res.max_sub_per_bar, 2);

    // sub_counts replicates the per-bar union tick count across all symbols.
    assert_eq!(res.sub_counts.len(), res.num_bars * res.num_symbols);
    assert_eq!(res.sub_counts, vec![2, 2, 1, 1, 1, 1]);

    let max_sub = res.max_sub_per_bar as usize;
    let num_symbols = res.num_symbols;
    let at = |bar_idx: usize, sub_idx: usize, sym_idx: usize| {
        let flat_idx = (bar_idx * max_sub + sub_idx) * num_symbols + sym_idx;
        res.candles[flat_idx]
    };

    // Bar 0 union ticks: [1500, 2000]
    assert_eq!(at(0, 0, 0).close, 10.0);
    assert_eq!(at(0, 0, 1).close, 0.0);
    assert_eq!(at(0, 1, 0).close, 0.0);
    assert_eq!(at(0, 1, 1).close, 20.0);

    // Bar 1 union ticks: [2001]
    assert_eq!(at(1, 0, 0).close, 11.0);
    assert_eq!(at(1, 0, 1).close, 0.0);

    // Bar 2 union ticks: [3500]
    assert_eq!(at(2, 0, 0).close, 12.0);
    assert_eq!(at(2, 0, 1).close, 21.0);
}
