use super::trading::has_table;
use crate::error::HubError;
use rusqlite::{params, Connection};
use serde::Serialize;
use serde_json::Value;

// ── Types ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize)]
pub struct DecisionEvent {
    pub id: String,
    pub timestamp_ms: Option<i64>,
    pub symbol: Option<String>,
    pub event_type: Option<String>,
    pub status: Option<String>,
    pub decision_phase: Option<String>,
    pub parent_decision_id: Option<String>,
    pub trade_id: Option<i64>,
    pub triggered_by: Option<String>,
    pub action_taken: Option<String>,
    pub rejection_reason: Option<String>,
    pub config_fingerprint: Option<String>,
    pub context_json: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GateEvaluation {
    pub id: i64,
    pub decision_id: String,
    pub gate_name: Option<String>,
    pub gate_passed: Option<bool>,
    pub metric_value: Option<f64>,
    pub threshold_value: Option<f64>,
    pub operator: Option<String>,
    pub explanation: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DecisionLineage {
    pub id: i64,
    pub signal_decision_id: Option<String>,
    pub entry_trade_id: Option<i64>,
    pub exit_decision_id: Option<String>,
    pub exit_trade_id: Option<i64>,
    pub exit_reason: Option<String>,
    pub duration_ms: Option<i64>,
}

// ── Queries ──────────────────────────────────────────────────────────────

fn has_column(conn: &Connection, table: &str, column: &str) -> Result<bool, HubError> {
    let mut stmt = conn.prepare(&format!("PRAGMA table_info({table})"))?;
    let mut rows = stmt.query([])?;
    while let Some(row) = rows.next()? {
        let name: String = row.get(1)?;
        if name == column {
            return Ok(true);
        }
    }
    Ok(false)
}

/// List decision events with optional filters and pagination.
pub fn list_decisions(
    conn: &Connection,
    symbol: Option<&str>,
    start_ms: Option<i64>,
    end_ms: Option<i64>,
    event_type: Option<&str>,
    status: Option<&str>,
    limit: u32,
    offset: u32,
) -> Result<(Vec<DecisionEvent>, i64), HubError> {
    if !has_table(conn, "decision_events") {
        return Ok((Vec::new(), 0));
    }
    let cfg_col = if has_column(conn, "decision_events", "config_fingerprint")? {
        "config_fingerprint"
    } else {
        "NULL AS config_fingerprint"
    };

    let mut where_clauses: Vec<String> = Vec::new();
    let mut params_vec: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();

    if let Some(sym) = symbol {
        where_clauses.push("symbol = ?".into());
        params_vec.push(Box::new(sym.trim().to_uppercase()));
    }
    if let Some(s) = start_ms {
        where_clauses.push("timestamp_ms >= ?".into());
        params_vec.push(Box::new(s));
    }
    if let Some(e) = end_ms {
        where_clauses.push("timestamp_ms <= ?".into());
        params_vec.push(Box::new(e));
    }
    if let Some(et) = event_type {
        where_clauses.push("event_type = ?".into());
        params_vec.push(Box::new(et.trim().to_string()));
    }
    if let Some(st) = status {
        where_clauses.push("status = ?".into());
        params_vec.push(Box::new(st.trim().to_string()));
    }

    let where_sql = if where_clauses.is_empty() {
        String::new()
    } else {
        format!(" WHERE {}", where_clauses.join(" AND "))
    };

    // Count total
    let count_sql = format!("SELECT COUNT(*) FROM decision_events{where_sql}");
    let params_refs: Vec<&dyn rusqlite::types::ToSql> =
        params_vec.iter().map(|p| p.as_ref()).collect();
    let total: i64 = conn.query_row(&count_sql, params_refs.as_slice(), |row| row.get(0))?;

    // Fetch rows
    let data_sql = format!(
        "SELECT id, timestamp_ms, symbol, event_type, status, decision_phase,
                parent_decision_id, trade_id, triggered_by, action_taken,
                rejection_reason, {cfg_col}, context_json
         FROM decision_events{where_sql}
         ORDER BY timestamp_ms DESC, id DESC
         LIMIT ? OFFSET ?"
    );
    // Rebuild params for data query
    let mut data_params: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();
    if let Some(sym) = symbol {
        data_params.push(Box::new(sym.trim().to_uppercase()));
    }
    if let Some(s) = start_ms {
        data_params.push(Box::new(s));
    }
    if let Some(e) = end_ms {
        data_params.push(Box::new(e));
    }
    if let Some(et) = event_type {
        data_params.push(Box::new(et.trim().to_string()));
    }
    if let Some(st) = status {
        data_params.push(Box::new(st.trim().to_string()));
    }
    data_params.push(Box::new(limit));
    data_params.push(Box::new(offset));

    let data_refs: Vec<&dyn rusqlite::types::ToSql> =
        data_params.iter().map(|p| p.as_ref()).collect();
    let mut stmt = conn.prepare(&data_sql)?;
    let rows = stmt
        .query_map(data_refs.as_slice(), |row| {
            Ok(DecisionEvent {
                id: row.get::<_, String>(0)?,
                timestamp_ms: row.get(1)?,
                symbol: row.get(2)?,
                event_type: row.get(3)?,
                status: row.get(4)?,
                decision_phase: row.get(5)?,
                parent_decision_id: row.get(6)?,
                trade_id: row.get(7)?,
                triggered_by: row.get(8)?,
                action_taken: row.get(9)?,
                rejection_reason: row.get(10)?,
                config_fingerprint: row.get(11)?,
                context_json: row.get(12)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;

    Ok((rows, total))
}

/// Fetch a single decision event with context and gates.
pub fn decision_detail(conn: &Connection, decision_id: &str) -> Result<Option<Value>, HubError> {
    if !has_table(conn, "decision_events") {
        return Ok(None);
    }
    let cfg_col = if has_column(conn, "decision_events", "config_fingerprint")? {
        "config_fingerprint"
    } else {
        "NULL AS config_fingerprint"
    };

    let decision = conn
        .prepare(
            &format!(
                "SELECT id, timestamp_ms, symbol, event_type, status, decision_phase,
                parent_decision_id, trade_id, triggered_by, action_taken,
                rejection_reason, {cfg_col}, context_json
         FROM decision_events WHERE id = ?"
            ),
        )?
        .query_row(params![decision_id], |row| {
            Ok(DecisionEvent {
                id: row.get(0)?,
                timestamp_ms: row.get(1)?,
                symbol: row.get(2)?,
                event_type: row.get(3)?,
                status: row.get(4)?,
                decision_phase: row.get(5)?,
                parent_decision_id: row.get(6)?,
                trade_id: row.get(7)?,
                triggered_by: row.get(8)?,
                action_taken: row.get(9)?,
                rejection_reason: row.get(10)?,
                config_fingerprint: row.get(11)?,
                context_json: row.get(12)?,
            })
        });

    let decision = match decision {
        Ok(d) => d,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(e) => return Err(e.into()),
    };

    // Context
    let context: Vec<Value> = if has_table(conn, "decision_context") {
        let mut stmt = conn.prepare("SELECT * FROM decision_context WHERE decision_id = ?")?;
        let col_count = stmt.column_count();
        let col_names: Vec<String> = (0..col_count)
            .map(|i| stmt.column_name(i).unwrap_or("").to_string())
            .collect();
        let result: Vec<Value> = stmt
            .query_map(params![decision_id], |row| {
                let mut map = serde_json::Map::new();
                for (i, name) in col_names.iter().enumerate() {
                    let val: rusqlite::types::Value = row.get(i)?;
                    map.insert(name.clone(), rusqlite_value_to_json(val));
                }
                Ok(Value::Object(map))
            })?
            .filter_map(|r| r.ok())
            .collect();
        result
    } else {
        Vec::new()
    };

    // Gates
    let gates: Vec<GateEvaluation> = if has_table(conn, "gate_evaluations") {
        let mut stmt = conn.prepare(
            "SELECT id, decision_id, gate_name, gate_passed, metric_value,
                    threshold_value, operator, explanation
             FROM gate_evaluations WHERE decision_id = ?
             ORDER BY id ASC",
        )?;
        let result = stmt
            .query_map(params![decision_id], |row| {
                Ok(GateEvaluation {
                    id: row.get(0)?,
                    decision_id: row.get(1)?,
                    gate_name: row.get(2)?,
                    gate_passed: row.get(3)?,
                    metric_value: row.get(4)?,
                    threshold_value: row.get(5)?,
                    operator: row.get(6)?,
                    explanation: row.get(7)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        result
    } else {
        Vec::new()
    };

    Ok(Some(serde_json::json!({
        "decision": decision,
        "context": context,
        "gates": gates,
    })))
}

/// Fetch gate evaluations for a single decision.
pub fn decision_gates(
    conn: &Connection,
    decision_id: &str,
) -> Result<Option<Vec<GateEvaluation>>, HubError> {
    if !has_table(conn, "decision_events") {
        return Ok(None);
    }

    // Verify decision exists
    let exists = conn
        .prepare("SELECT id FROM decision_events WHERE id = ?")?
        .query_row(params![decision_id], |_| Ok(()));
    if exists.is_err() {
        return Ok(None);
    }

    let gates = if has_table(conn, "gate_evaluations") {
        let mut stmt = conn.prepare(
            "SELECT id, decision_id, gate_name, gate_passed, metric_value,
                    threshold_value, operator, explanation
             FROM gate_evaluations WHERE decision_id = ?
             ORDER BY id ASC",
        )?;
        let result = stmt
            .query_map(params![decision_id], |row| {
                Ok(GateEvaluation {
                    id: row.get(0)?,
                    decision_id: row.get(1)?,
                    gate_name: row.get(2)?,
                    gate_passed: row.get(3)?,
                    metric_value: row.get(4)?,
                    threshold_value: row.get(5)?,
                    operator: row.get(6)?,
                    explanation: row.get(7)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        result
    } else {
        Vec::new()
    };

    Ok(Some(gates))
}

/// Build decision chain for a trade.
pub fn trade_decision_trace(conn: &Connection, trade_id: i64) -> Result<Value, HubError> {
    if !has_table(conn, "decision_lineage") || !has_table(conn, "decision_events") {
        return Ok(serde_json::json!({"chain": [], "lineage": null}));
    }
    let cfg_col = if has_column(conn, "decision_events", "config_fingerprint")? {
        "config_fingerprint"
    } else {
        "NULL AS config_fingerprint"
    };

    // Find lineage rows
    let mut stmt = conn.prepare(
        "SELECT id, signal_decision_id, entry_trade_id, exit_decision_id,
                exit_trade_id, exit_reason, duration_ms
         FROM decision_lineage
         WHERE entry_trade_id = ? OR exit_trade_id = ?",
    )?;
    let lineage_rows: Vec<DecisionLineage> = stmt
        .query_map(params![trade_id, trade_id], |row| {
            Ok(DecisionLineage {
                id: row.get(0)?,
                signal_decision_id: row.get(1)?,
                entry_trade_id: row.get(2)?,
                exit_decision_id: row.get(3)?,
                exit_trade_id: row.get(4)?,
                exit_reason: row.get(5)?,
                duration_ms: row.get(6)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;

    let lineage = lineage_rows.first().cloned();

    // Collect decision IDs and trade IDs
    let mut decision_ids: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut trade_ids: std::collections::HashSet<i64> = std::collections::HashSet::new();

    for row in &lineage_rows {
        if let Some(ref id) = row.signal_decision_id {
            decision_ids.insert(id.clone());
        }
        if let Some(ref id) = row.exit_decision_id {
            decision_ids.insert(id.clone());
        }
        if let Some(id) = row.entry_trade_id {
            trade_ids.insert(id);
        }
        if let Some(id) = row.exit_trade_id {
            trade_ids.insert(id);
        }
    }

    // Find decision_events linked to trade_ids
    if !trade_ids.is_empty() {
        let placeholders = trade_ids.iter().map(|_| "?").collect::<Vec<_>>().join(",");
        let sql = format!("SELECT id FROM decision_events WHERE trade_id IN ({placeholders})");
        let mut stmt = conn.prepare(&sql)?;
        let params: Vec<&dyn rusqlite::types::ToSql> = trade_ids
            .iter()
            .map(|id| id as &dyn rusqlite::types::ToSql)
            .collect();
        let rows = stmt.query_map(params.as_slice(), |row| row.get::<_, String>(0))?;
        for row in rows.flatten() {
            decision_ids.insert(row);
        }
    }

    if decision_ids.is_empty() {
        return Ok(serde_json::json!({"chain": [], "lineage": lineage}));
    }

    // Fetch all matching decision events
    let placeholders = decision_ids
        .iter()
        .map(|_| "?")
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "SELECT id, timestamp_ms, symbol, event_type, status,
                decision_phase, parent_decision_id, trade_id,
                triggered_by, action_taken, rejection_reason, {cfg_col}, context_json
         FROM decision_events
         WHERE id IN ({placeholders})
         ORDER BY timestamp_ms ASC, id ASC"
    );
    let mut stmt = conn.prepare(&sql)?;
    let ids_vec: Vec<String> = decision_ids.into_iter().collect();
    let params: Vec<&dyn rusqlite::types::ToSql> = ids_vec
        .iter()
        .map(|id| id as &dyn rusqlite::types::ToSql)
        .collect();
    let chain: Vec<DecisionEvent> = stmt
        .query_map(params.as_slice(), |row| {
            Ok(DecisionEvent {
                id: row.get(0)?,
                timestamp_ms: row.get(1)?,
                symbol: row.get(2)?,
                event_type: row.get(3)?,
                status: row.get(4)?,
                decision_phase: row.get(5)?,
                parent_decision_id: row.get(6)?,
                trade_id: row.get(7)?,
                triggered_by: row.get(8)?,
                action_taken: row.get(9)?,
                rejection_reason: row.get(10)?,
                config_fingerprint: row.get(11)?,
                context_json: row.get(12)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;

    Ok(serde_json::json!({"chain": chain, "lineage": lineage}))
}

fn rusqlite_value_to_json(val: rusqlite::types::Value) -> Value {
    match val {
        rusqlite::types::Value::Null => Value::Null,
        rusqlite::types::Value::Integer(i) => Value::Number(i.into()),
        rusqlite::types::Value::Real(f) => serde_json::Number::from_f64(f)
            .map(Value::Number)
            .unwrap_or(Value::Null),
        rusqlite::types::Value::Text(s) => Value::String(s),
        rusqlite::types::Value::Blob(b) => Value::String(format!("<blob {} bytes>", b.len())),
    }
}
