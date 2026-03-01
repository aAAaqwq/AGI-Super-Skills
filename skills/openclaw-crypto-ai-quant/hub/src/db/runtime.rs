use rusqlite::{params, Connection};

use crate::error::HubError;
use crate::heartbeat::{parse_heartbeat_line, Heartbeat};

/// Fetch and parse the latest heartbeat from the `runtime_logs` table.
pub fn fetch_heartbeat_from_db(conn: &Connection) -> Result<Option<Heartbeat>, HubError> {
    let mut stmt = conn.prepare(
        "SELECT ts_ms, message FROM runtime_logs
         WHERE message LIKE '%engine ok%'
         ORDER BY ts_ms DESC LIMIT 1",
    )?;

    let result = stmt.query_row([], |row| {
        let ts_ms: i64 = row.get(0)?;
        let message: String = row.get(1)?;
        Ok((ts_ms, message))
    });

    match result {
        Ok((ts_ms, message)) => {
            let hb = parse_heartbeat_line(&message, Some(ts_ms), "sqlite");
            Ok(Some(hb))
        }
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

/// Fetch recent runtime log entries.
pub fn fetch_recent_logs(
    conn: &Connection,
    limit: u32,
    level_filter: Option<&str>,
) -> Result<Vec<serde_json::Value>, HubError> {
    let sql = if let Some(level) = level_filter {
        format!(
            "SELECT ts_ms, level, source, message FROM runtime_logs WHERE level = ? ORDER BY ts_ms DESC LIMIT {limit}"
        )
    } else {
        format!("SELECT ts_ms, level, source, message FROM runtime_logs ORDER BY ts_ms DESC LIMIT {limit}")
    };

    let mut stmt = conn.prepare(&sql)?;
    let rows = if let Some(level) = level_filter {
        stmt.query_map(params![level], |row| {
            Ok(serde_json::json!({
                "ts_ms": row.get::<_, i64>(0)?,
                "level": row.get::<_, Option<String>>(1)?,
                "source": row.get::<_, Option<String>>(2)?,
                "message": row.get::<_, Option<String>>(3)?,
            }))
        })?
        .collect::<Result<Vec<_>, _>>()?
    } else {
        stmt.query_map([], |row| {
            Ok(serde_json::json!({
                "ts_ms": row.get::<_, i64>(0)?,
                "level": row.get::<_, Option<String>>(1)?,
                "source": row.get::<_, Option<String>>(2)?,
                "message": row.get::<_, Option<String>>(3)?,
            }))
        })?
        .collect::<Result<Vec<_>, _>>()?
    };
    Ok(rows)
}
