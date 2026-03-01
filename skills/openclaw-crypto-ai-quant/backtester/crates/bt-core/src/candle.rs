/// OHLCV bar representation — cache-friendly contiguous layout.
#[derive(Debug, Clone, Copy)]
#[repr(C)]
pub struct OhlcvBar {
    pub t: i64,       // open time (ms since epoch)
    pub t_close: i64, // close time (ms)
    pub o: f64,       // open
    pub h: f64,       // high
    pub l: f64,       // low
    pub c: f64,       // close
    pub v: f64,       // volume
    pub n: i32,       // number of trades
}

/// All candle data loaded from the database, keyed by symbol.
pub type CandleData = rustc_hash::FxHashMap<String, Vec<OhlcvBar>>;

/// Funding rate data: symbol → sorted Vec<(timestamp_ms, hourly_rate)>.
pub type FundingRateData = rustc_hash::FxHashMap<String, Vec<(i64, f64)>>;
