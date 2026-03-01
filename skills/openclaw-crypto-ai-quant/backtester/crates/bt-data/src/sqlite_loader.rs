use bt_core::candle::{CandleData, FundingRateData, OhlcvBar};
use rusqlite::{Connection, OpenFlags};
use std::time::Instant;

const VALID_INTERVALS: &[&str] = &["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"];

fn validate_interval(interval: &str) -> Result<(), Box<dyn std::error::Error>> {
    if !VALID_INTERVALS.contains(&interval) {
        return Err(format!("invalid interval: {interval}").into());
    }
    Ok(())
}

/// Query the min/max timestamp for a given interval in the candle database.
/// Returns `(min_t, max_t)` in milliseconds, or `None` if the table is empty.
pub fn query_time_range(
    db_path: &str,
    interval: &str,
) -> Result<Option<(i64, i64)>, Box<dyn std::error::Error>> {
    validate_interval(interval)?;
    let conn = Connection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let mut stmt = conn.prepare("SELECT MIN(t), MAX(t) FROM candles WHERE interval = ?")?;
    let result = stmt.query_row([interval], |row| {
        let min_t: Option<i64> = row.get(0)?;
        let max_t: Option<i64> = row.get(1)?;
        Ok(min_t.zip(max_t))
    })?;
    Ok(result)
}

/// Query the min/max timestamp across multiple candle DBs for a given interval.
///
/// This is useful when candle history is partitioned into multiple SQLite files.
pub fn query_time_range_multi(
    db_paths: &[String],
    interval: &str,
) -> Result<Option<(i64, i64)>, Box<dyn std::error::Error>> {
    let mut min_t: Option<i64> = None;
    let mut max_t: Option<i64> = None;

    for p in db_paths {
        if let Some((mn, mx)) = query_time_range(p, interval)? {
            min_t = Some(min_t.map_or(mn, |v| v.min(mn)));
            max_t = Some(max_t.map_or(mx, |v| v.max(mx)));
        }
    }

    Ok(min_t.zip(max_t))
}

/// Load all candle rows for a given interval from the SQLite database,
/// returning them grouped by symbol with bars sorted by open-time ascending.
///
/// Optional `from_ts` / `to_ts` (milliseconds) restrict the loaded range.
pub fn load_candles(
    db_path: &str,
    interval: &str,
) -> Result<CandleData, Box<dyn std::error::Error>> {
    load_candles_filtered(db_path, interval, None, None)
}

/// Load candles across multiple SQLite databases for a given interval.
pub fn load_candles_multi(
    db_paths: &[String],
    interval: &str,
) -> Result<CandleData, Box<dyn std::error::Error>> {
    load_candles_filtered_multi(db_paths, interval, None, None)
}

/// Like [`load_candles`] but with optional timestamp filters.
pub fn load_candles_filtered(
    db_path: &str,
    interval: &str,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> Result<CandleData, Box<dyn std::error::Error>> {
    validate_interval(interval)?;

    let start = Instant::now();

    let conn = Connection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;

    // Tune for bulk read performance
    // Best-effort: archived partitions may be read-only or not in WAL mode.
    let _ = conn.execute_batch("PRAGMA journal_mode = WAL; PRAGMA synchronous = OFF;");

    // Build dynamic WHERE clause
    let mut where_parts = vec!["interval = ?1".to_string()];
    if from_ts.is_some() {
        where_parts.push("t >= ?2".to_string());
    }
    if to_ts.is_some() {
        where_parts.push(format!("t <= ?{}", if from_ts.is_some() { 3 } else { 2 }));
    }
    let query = format!(
        "SELECT symbol, t, t_close, o, h, l, c, v, COALESCE(n, 0) \
         FROM candles WHERE {} ORDER BY symbol, t ASC",
        where_parts.join(" AND "),
    );

    let mut stmt = conn.prepare(&query)?;

    let mut data: CandleData = CandleData::default();
    let mut total_bars: u64 = 0;
    let mut current_symbol = String::new();
    let mut current_vec: Vec<OhlcvBar> = Vec::new();

    // Bind parameters dynamically
    let mut params: Vec<Box<dyn rusqlite::types::ToSql>> = vec![Box::new(interval.to_string())];
    if let Some(ft) = from_ts {
        params.push(Box::new(ft));
    }
    if let Some(tt) = to_ts {
        params.push(Box::new(tt));
    }
    let param_refs: Vec<&dyn rusqlite::types::ToSql> = params.iter().map(|p| p.as_ref()).collect();

    let rows = stmt.query_map(param_refs.as_slice(), |row| {
        Ok((
            row.get::<_, String>(0)?,
            OhlcvBar {
                t: row.get(1)?,
                t_close: row.get(2)?,
                o: row.get(3)?,
                h: row.get(4)?,
                l: row.get(5)?,
                c: row.get(6)?,
                v: row.get(7)?,
                n: row.get(8)?,
            },
        ))
    })?;

    for row_result in rows {
        let (symbol, bar) = row_result?;
        total_bars += 1;

        if symbol != current_symbol {
            // Flush the previous symbol's bars
            if !current_symbol.is_empty() {
                data.insert(
                    std::mem::take(&mut current_symbol),
                    std::mem::take(&mut current_vec),
                );
            }
            current_symbol = symbol;
            current_vec = Vec::with_capacity(512);
        }
        current_vec.push(bar);
    }

    // Flush the last symbol
    if !current_symbol.is_empty() {
        data.insert(current_symbol, current_vec);
    }

    let elapsed = start.elapsed();
    let filter_info = match (from_ts, to_ts) {
        (Some(f), Some(t)) => format!(", range={f}..{t}"),
        (Some(f), None) => format!(", from={f}"),
        (None, Some(t)) => format!(", to={t}"),
        (None, None) => String::new(),
    };
    println!(
        "[bt-data] Loaded {} symbols, {} bars in {:.2}s from {:?} (interval={}{})",
        data.len(),
        total_bars,
        elapsed.as_secs_f64(),
        db_path,
        interval,
        filter_info,
    );

    Ok(data)
}

/// Like [`load_candles_filtered`], but merges results across multiple databases.
///
/// If partitions overlap, duplicate bars are deduped by `(symbol, t)` after merging.
pub fn load_candles_filtered_multi(
    db_paths: &[String],
    interval: &str,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> Result<CandleData, Box<dyn std::error::Error>> {
    let mut merged: CandleData = CandleData::default();
    for p in db_paths {
        let part = load_candles_filtered(p, interval, from_ts, to_ts)?;
        for (sym, bars) in part {
            merged.entry(sym).or_default().extend(bars);
        }
    }

    // Normalise ordering and dedupe within each symbol.
    for bars in merged.values_mut() {
        bars.sort_by_key(|b| b.t);
        bars.dedup_by_key(|b| b.t);
    }

    Ok(merged)
}

/// Load the distinct list of symbols available for a given interval.
pub fn load_symbols(
    db_path: &str,
    interval: &str,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    validate_interval(interval)?;

    let conn = Connection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;

    let mut stmt =
        conn.prepare("SELECT DISTINCT symbol FROM candles WHERE interval = ? ORDER BY symbol")?;

    let symbols: Vec<String> = stmt
        .query_map([interval], |row| row.get(0))?
        .collect::<Result<Vec<_>, _>>()?;

    println!(
        "[bt-data] Found {} symbols for interval={} in {:?}",
        symbols.len(),
        interval,
        db_path,
    );

    Ok(symbols)
}

/// Load symbols considered "active" during the given time range using a universe
/// history SQLite database (see `tools/sync_universe_history.py`).
///
/// A symbol is considered active when its observed listing interval overlaps with
/// the backtest window:
///   first_seen_ms <= to_ts AND last_seen_ms >= from_ts
pub fn load_universe_active_symbols(
    db_path: &str,
    from_ts: i64,
    to_ts: i64,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let conn = Connection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;

    let mut stmt = conn.prepare(
        "SELECT symbol FROM universe_listings \
         WHERE first_seen_ms <= ?2 AND last_seen_ms >= ?1 \
         ORDER BY symbol",
    )?;

    let symbols: Vec<String> = stmt
        .query_map([from_ts, to_ts], |row| row.get(0))?
        .collect::<Result<Vec<_>, _>>()?;

    Ok(symbols)
}

/// Load funding rates from a SQLite database, returning them grouped by
/// symbol as sorted Vec<(timestamp_ms, rate)>.
///
/// Expected table schema:
/// ```sql
/// CREATE TABLE funding_rates (
///     symbol TEXT NOT NULL,
///     time INTEGER NOT NULL,
///     funding_rate REAL NOT NULL,
///     PRIMARY KEY (symbol, time)
/// );
/// ```
pub fn load_funding_rates(db_path: &str) -> Result<FundingRateData, Box<dyn std::error::Error>> {
    load_funding_rates_filtered(db_path, None, None)
}

pub fn load_funding_rates_filtered(
    db_path: &str,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
) -> Result<FundingRateData, Box<dyn std::error::Error>> {
    let start = Instant::now();

    let conn = Connection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    // Best-effort: archived DBs may be read-only or not in WAL mode.
    let _ = conn.execute_batch("PRAGMA journal_mode = WAL; PRAGMA synchronous = OFF;");

    let mut where_parts: Vec<String> = Vec::new();
    let mut params: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();
    let mut idx = 1;
    if let Some(ft) = from_ts {
        where_parts.push(format!("time >= ?{idx}"));
        params.push(Box::new(ft));
        idx += 1;
    }
    if let Some(tt) = to_ts {
        where_parts.push(format!("time <= ?{idx}"));
        params.push(Box::new(tt));
    }
    let where_clause = if where_parts.is_empty() {
        String::new()
    } else {
        format!(" WHERE {}", where_parts.join(" AND "))
    };
    let query = format!(
        "SELECT symbol, time, funding_rate FROM funding_rates{} ORDER BY symbol, time ASC",
        where_clause,
    );

    let param_refs: Vec<&dyn rusqlite::types::ToSql> = params.iter().map(|p| p.as_ref()).collect();
    let mut stmt = conn.prepare(&query)?;

    let mut data: FundingRateData = FundingRateData::default();
    let mut total: u64 = 0;
    let mut current_symbol = String::new();
    let mut current_vec: Vec<(i64, f64)> = Vec::new();

    let rows = stmt.query_map(param_refs.as_slice(), |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, i64>(1)?,
            row.get::<_, f64>(2)?,
        ))
    })?;

    for row_result in rows {
        let (symbol, time_ms, rate) = row_result?;
        total += 1;

        if symbol != current_symbol {
            if !current_symbol.is_empty() {
                data.insert(
                    std::mem::take(&mut current_symbol),
                    std::mem::take(&mut current_vec),
                );
            }
            current_symbol = symbol;
            current_vec = Vec::with_capacity(256);
        }
        current_vec.push((time_ms, rate));
    }

    if !current_symbol.is_empty() {
        data.insert(current_symbol, current_vec);
    }

    let elapsed = start.elapsed();
    println!(
        "[bt-data] Loaded {} funding rate entries across {} symbols in {:.2}s from {:?}",
        total,
        data.len(),
        elapsed.as_secs_f64(),
        db_path,
    );

    Ok(data)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_db_path(tag: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("bt_data_{tag}_{nanos}.db"))
    }

    fn init_candles_db(path: &PathBuf) {
        let conn = Connection::open(path).unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                t INTEGER NOT NULL,
                t_close INTEGER,
                o REAL,
                h REAL,
                l REAL,
                c REAL,
                v REAL,
                n INTEGER,
                updated_at TEXT,
                PRIMARY KEY (symbol, interval, t)
            );
            CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_t
            ON candles(symbol, interval, t);
            "#,
        )
        .unwrap();
    }

    fn insert_bar(conn: &Connection, symbol: &str, interval: &str, t: i64) {
        conn.execute(
            "INSERT OR REPLACE INTO candles (symbol, interval, t, t_close, o, h, l, c, v, n, updated_at) \
             VALUES (?1, ?2, ?3, ?4, 1.0, 1.0, 1.0, 1.0, 0.0, 0, 'test')",
            (symbol, interval, t, t + 1),
        )
        .unwrap();
    }

    #[test]
    fn query_time_range_multi_unions_partitions() {
        let p1 = tmp_db_path("range1");
        let p2 = tmp_db_path("range2");

        init_candles_db(&p1);
        init_candles_db(&p2);

        {
            let c1 = Connection::open(&p1).unwrap();
            insert_bar(&c1, "BTC", "5m", 1000);
            insert_bar(&c1, "BTC", "5m", 2000);
        }
        {
            let c2 = Connection::open(&p2).unwrap();
            insert_bar(&c2, "BTC", "5m", 3000);
            insert_bar(&c2, "BTC", "5m", 4000);
        }

        let paths = vec![
            p1.to_string_lossy().to_string(),
            p2.to_string_lossy().to_string(),
        ];
        let got = query_time_range_multi(&paths, "5m").unwrap();
        assert_eq!(got, Some((1000, 4000)));

        let _ = std::fs::remove_file(&p1);
        let _ = std::fs::remove_file(&p2);
    }

    #[test]
    fn load_candles_filtered_multi_merges_and_dedupes() {
        let p1 = tmp_db_path("merge1");
        let p2 = tmp_db_path("merge2");

        init_candles_db(&p1);
        init_candles_db(&p2);

        {
            let c1 = Connection::open(&p1).unwrap();
            insert_bar(&c1, "BTC", "5m", 1000);
            insert_bar(&c1, "BTC", "5m", 2000);
        }
        {
            let c2 = Connection::open(&p2).unwrap();
            insert_bar(&c2, "BTC", "5m", 2000); // duplicate
            insert_bar(&c2, "BTC", "5m", 3000);
            insert_bar(&c2, "ETH", "5m", 1500);
        }

        let paths = vec![
            p1.to_string_lossy().to_string(),
            p2.to_string_lossy().to_string(),
        ];
        let data = load_candles_filtered_multi(&paths, "5m", None, None).unwrap();

        let btc = data.get("BTC").unwrap();
        let eth = data.get("ETH").unwrap();
        assert_eq!(
            btc.iter().map(|b| b.t).collect::<Vec<_>>(),
            vec![1000, 2000, 3000]
        );
        assert_eq!(eth.iter().map(|b| b.t).collect::<Vec<_>>(), vec![1500]);

        let _ = std::fs::remove_file(&p1);
        let _ = std::fs::remove_file(&p2);
    }
}
