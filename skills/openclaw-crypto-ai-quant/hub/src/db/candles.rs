use rusqlite::{params, Connection};
use serde::Serialize;

use crate::error::HubError;

#[derive(Debug, Clone, Serialize)]
pub struct Candle {
    pub t: i64,
    pub t_close: i64,
    pub o: f64,
    pub h: f64,
    pub l: f64,
    pub c: f64,
    pub v: f64,
    pub n: i64,
}

/// Fetch OHLCV candles for a symbol/interval from a candle DB connection.
pub fn fetch_candles(
    conn: &Connection,
    symbol: &str,
    interval: &str,
    limit: u32,
) -> Result<Vec<Candle>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT t, t_close, o, h, l, c, v, n
         FROM candles
         WHERE symbol = ? AND interval = ?
         ORDER BY COALESCE(t_close, t) DESC
         LIMIT ?",
    )?;

    let rows: Vec<Candle> = stmt
        .query_map(params![symbol, interval, limit], |row| {
            Ok(Candle {
                t: row.get(0)?,
                t_close: row.get::<_, i64>(1).unwrap_or(0),
                o: row.get(2)?,
                h: row.get(3)?,
                l: row.get(4)?,
                c: row.get(5)?,
                v: row.get(6)?,
                n: row.get::<_, i64>(7).unwrap_or(0),
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;

    // Reverse to chronological order.
    let mut candles = rows;
    candles.reverse();
    Ok(candles)
}

/// Fetch OHLCV candles for a symbol/interval within an optional time range.
pub fn fetch_candles_range(
    conn: &Connection,
    symbol: &str,
    interval: &str,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
    limit: u32,
) -> Result<Vec<Candle>, HubError> {
    let (sql, params_vec): (String, Vec<Box<dyn rusqlite::types::ToSql>>) = match (from_ts, to_ts) {
        (Some(from), Some(to)) => (
            "SELECT t, t_close, o, h, l, c, v, n
             FROM candles
             WHERE symbol = ? AND interval = ? AND COALESCE(t_close, t) >= ? AND t <= ?
             ORDER BY COALESCE(t_close, t) ASC
             LIMIT ?"
                .to_string(),
            vec![
                Box::new(symbol.to_string()),
                Box::new(interval.to_string()),
                Box::new(from),
                Box::new(to),
                Box::new(limit),
            ],
        ),
        (Some(from), None) => (
            "SELECT t, t_close, o, h, l, c, v, n
             FROM candles
             WHERE symbol = ? AND interval = ? AND COALESCE(t_close, t) >= ?
             ORDER BY COALESCE(t_close, t) ASC
             LIMIT ?"
                .to_string(),
            vec![
                Box::new(symbol.to_string()),
                Box::new(interval.to_string()),
                Box::new(from),
                Box::new(limit),
            ],
        ),
        (None, Some(to)) => (
            "SELECT t, t_close, o, h, l, c, v, n
             FROM candles
             WHERE symbol = ? AND interval = ? AND t <= ?
             ORDER BY COALESCE(t_close, t) DESC
             LIMIT ?"
                .to_string(),
            vec![
                Box::new(symbol.to_string()),
                Box::new(interval.to_string()),
                Box::new(to),
                Box::new(limit),
            ],
        ),
        (None, None) => {
            return fetch_candles(conn, symbol, interval, limit);
        }
    };

    let mut stmt = conn.prepare(&sql)?;
    let params_refs: Vec<&dyn rusqlite::types::ToSql> = params_vec.iter().map(|b| b.as_ref()).collect();

    let mut candles: Vec<Candle> = stmt
        .query_map(params_refs.as_slice(), |row| {
            Ok(Candle {
                t: row.get(0)?,
                t_close: row.get::<_, i64>(1).unwrap_or(0),
                o: row.get(2)?,
                h: row.get(3)?,
                l: row.get(4)?,
                c: row.get(5)?,
                v: row.get(6)?,
                n: row.get::<_, i64>(7).unwrap_or(0),
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;

    // Ensure chronological order (some queries use DESC)
    candles.sort_by_key(|c| c.t);
    Ok(candles)
}

/// Fetch last N close prices for multiple symbols in one go.
pub fn fetch_recent_closes_batch(
    conn: &Connection,
    symbols: &[String],
    interval: &str,
    limit: u32,
) -> Result<std::collections::HashMap<String, Vec<f64>>, HubError> {
    let mut out = std::collections::HashMap::new();
    for sym in symbols {
        let candles = fetch_candles(conn, sym, interval, limit)?;
        let closes: Vec<f64> = candles.iter().map(|c| c.c).collect();
        if !closes.is_empty() {
            out.insert(sym.clone(), closes);
        }
    }
    Ok(out)
}

/// Fetch last N candles for multiple symbols in one go.
pub fn fetch_recent_candles_batch(
    conn: &Connection,
    symbols: &[String],
    interval: &str,
    limit: u32,
) -> Result<std::collections::HashMap<String, Vec<Candle>>, HubError> {
    let mut out = std::collections::HashMap::new();
    for sym in symbols {
        let candles = fetch_candles(conn, sym, interval, limit)?;
        if !candles.is_empty() {
            out.insert(sym.clone(), candles);
        }
    }
    Ok(out)
}

/// Fetch 24h rolling USD volume per symbol: SUM(v * c) for candles in the last 24 h.
pub fn fetch_24h_volumes(
    conn: &Connection,
    interval: &str,
    cutoff_ms: i64,
) -> Result<std::collections::HashMap<String, f64>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT symbol, SUM(v * c) AS vol_usd
         FROM candles
         WHERE interval = ? AND COALESCE(t_close, t) >= ?
         GROUP BY symbol",
    )?;
    let rows = stmt.query_map(params![interval, cutoff_ms], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, f64>(1)?))
    })?;
    let mut out = std::collections::HashMap::new();
    for r in rows.flatten() {
        out.insert(r.0, r.1);
    }
    Ok(out)
}

/// List available candle intervals by scanning DB files in the candles directory.
pub fn list_available_intervals(candles_dir: &std::path::Path) -> Vec<String> {
    let mut intervals: Vec<String> = Vec::new();
    if let Ok(entries) = std::fs::read_dir(candles_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if let Some(iv) = name
                .strip_prefix("candles_")
                .and_then(|s| s.strip_suffix(".db"))
            {
                if !iv.is_empty() {
                    intervals.push(iv.to_string());
                }
            }
        }
    }
    intervals.sort_by(|a, b| interval_sort_key(a).cmp(&interval_sort_key(b)));
    intervals
}

fn interval_sort_key(iv: &str) -> (u64, String) {
    let s = iv.trim().to_lowercase();
    let (num_str, unit) = s.split_at(s.len().saturating_sub(1));
    let n: u64 = num_str.parse().unwrap_or(u64::MAX);
    let mult: u64 = match unit {
        "m" => 1,
        "h" => 60,
        "d" => 60 * 24,
        _ => 1_000_000,
    };
    (n * mult, s)
}
