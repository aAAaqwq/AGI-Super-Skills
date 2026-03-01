use axum::extract::{Path, Query, State};
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;

use crate::db::decisions;
use crate::error::HubError;
use crate::state::AppState;

use super::monitor::normalize_mode;

#[derive(Debug, Deserialize)]
pub struct DecisionsQuery {
    #[serde(default = "default_mode")]
    mode: String,
    symbol: Option<String>,
    start: Option<i64>,
    end: Option<i64>,
    event_type: Option<String>,
    status: Option<String>,
    #[serde(default = "default_decisions_limit")]
    limit: u32,
    #[serde(default)]
    offset: u32,
}

fn default_mode() -> String {
    "paper".to_string()
}

fn default_decisions_limit() -> u32 {
    100
}

#[derive(Debug, Deserialize)]
pub struct ModeQuery {
    #[serde(default = "default_mode")]
    mode: String,
}

pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/v2/decisions", get(api_decisions_list))
        .route("/api/v2/decisions/{id}", get(api_decision_detail))
        .route("/api/v2/decisions/{id}/gates", get(api_decision_gates))
        .route(
            "/api/v2/trades/{id}/decision-trace",
            get(api_trade_decision_trace),
        )
}

async fn api_decisions_list(
    State(state): State<Arc<AppState>>,
    Query(q): Query<DecisionsQuery>,
) -> Result<Json<Value>, HubError> {
    let mode = normalize_mode(&q.mode);
    let pool = state
        .db_pool(&mode)
        .ok_or_else(|| HubError::Db("db not available".to_string()))?;
    let conn = pool.get()?;

    let limit = q.limit.clamp(1, 1000);
    let offset = q.offset;

    let (data, total) = decisions::list_decisions(
        &conn,
        q.symbol.as_deref(),
        q.start,
        q.end,
        q.event_type.as_deref(),
        q.status.as_deref(),
        limit,
        offset,
    )?;

    Ok(Json(json!({
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset,
    })))
}

async fn api_decision_detail(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Query(q): Query<ModeQuery>,
) -> Result<Json<Value>, HubError> {
    let mode = normalize_mode(&q.mode);
    let pool = state
        .db_pool(&mode)
        .ok_or_else(|| HubError::Db("db not available".to_string()))?;
    let conn = pool.get()?;

    match decisions::decision_detail(&conn, &id)? {
        Some(detail) => Ok(Json(detail)),
        None => Err(HubError::NotFound("decision not found".to_string())),
    }
}

async fn api_decision_gates(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Query(q): Query<ModeQuery>,
) -> Result<Json<Value>, HubError> {
    let mode = normalize_mode(&q.mode);
    let pool = state
        .db_pool(&mode)
        .ok_or_else(|| HubError::Db("db not available".to_string()))?;
    let conn = pool.get()?;

    match decisions::decision_gates(&conn, &id)? {
        Some(gates) => Ok(Json(json!({"gates": gates}))),
        None => Err(HubError::NotFound("decision not found".to_string())),
    }
}

async fn api_trade_decision_trace(
    State(state): State<Arc<AppState>>,
    Path(id): Path<i64>,
    Query(q): Query<ModeQuery>,
) -> Result<Json<Value>, HubError> {
    let mode = normalize_mode(&q.mode);
    let pool = state
        .db_pool(&mode)
        .ok_or_else(|| HubError::Db("db not available".to_string()))?;
    let conn = pool.get()?;

    let result = decisions::trade_decision_trace(&conn, id)?;
    Ok(Json(result))
}
