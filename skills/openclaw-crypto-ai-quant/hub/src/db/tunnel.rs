use crate::error::HubError;
use rusqlite::Connection;
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct TunnelPoint {
    pub ts_ms: i64,
    pub upper_full: f64,
    pub upper_partial: Option<f64>,
    pub lower_full: f64,
    pub entry_price: f64,
    pub pos_type: String,
}

/// Fetch exit tunnel data for a symbol within a time range.
///
/// Returns an empty Vec if the `exit_tunnel` table doesn't exist (older DBs).
pub fn fetch_tunnel(
    conn: &Connection,
    symbol: &str,
    from_ts: Option<i64>,
    to_ts: Option<i64>,
    limit: u32,
) -> Result<Vec<TunnelPoint>, HubError> {
    // Gracefully handle missing table (older DBs that predate exit_tunnel).
    let table_exists: bool = conn
        .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='exit_tunnel' LIMIT 1")?
        .exists([])?;
    if !table_exists {
        return Ok(Vec::new());
    }

    let mut sql = String::from(
        "SELECT ts_ms, upper_full, upper_partial, lower_full, entry_price, pos_type \
         FROM exit_tunnel WHERE symbol = ?",
    );
    let mut param_values: Vec<Box<dyn rusqlite::types::ToSql>> = vec![Box::new(symbol.to_string())];

    if let Some(from) = from_ts {
        sql.push_str(" AND ts_ms >= ?");
        param_values.push(Box::new(from));
    }
    if let Some(to) = to_ts {
        sql.push_str(" AND ts_ms <= ?");
        param_values.push(Box::new(to));
    }
    sql.push_str(" ORDER BY ts_ms ASC LIMIT ?");
    param_values.push(Box::new(limit));

    let params_ref: Vec<&dyn rusqlite::types::ToSql> = param_values.iter().map(|b| b.as_ref()).collect();
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt
        .query_map(params_ref.as_slice(), |row| {
            Ok(TunnelPoint {
                ts_ms: row.get(0)?,
                upper_full: row.get(1)?,
                upper_partial: row.get(2)?,
                lower_full: row.get(3)?,
                entry_price: row.get(4)?,
                pos_type: row.get(5)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}
