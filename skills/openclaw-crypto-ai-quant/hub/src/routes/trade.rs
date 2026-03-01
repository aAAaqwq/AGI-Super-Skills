use axum::{
    extract::{Path, State},
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::Arc;
use std::time::Instant;

use crate::error::HubError;
use crate::state::AppState;
use crate::subprocess::manual_trade::{self, ManualTradeAction, ManualTradeArgs};
use crate::subprocess::{JobInfo, JobStatus};

// ── Request bodies ──────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct TradeOpenBody {
    pub symbol: String,
    pub side: String,
    pub notional_usd: f64,
    pub leverage: u32,
    pub order_type: String,
    pub limit_price: Option<f64>,
    pub confirm_token: Option<String>,
}

#[derive(Deserialize)]
pub struct TradeCloseBody {
    pub symbol: String,
    pub close_pct: f64,
    pub order_type: String,
    pub limit_price: Option<f64>,
    pub confirm_token: Option<String>,
}

#[derive(Deserialize)]
pub struct TradeCancelBody {
    pub symbol: String,
    pub oid: Option<String>,
    pub intent_id: Option<String>,
}

// ── Param hash helpers ──────────────────────────────────────────────

fn open_param_hash(body: &TradeOpenBody) -> String {
    let mut hasher = DefaultHasher::new();
    body.symbol.hash(&mut hasher);
    body.side.hash(&mut hasher);
    body.notional_usd.to_bits().hash(&mut hasher);
    body.leverage.hash(&mut hasher);
    body.order_type.hash(&mut hasher);
    body.limit_price.map(|p| p.to_bits()).hash(&mut hasher);
    format!("{:x}", hasher.finish())
}

fn close_param_hash(body: &TradeCloseBody) -> String {
    let mut hasher = DefaultHasher::new();
    "close".hash(&mut hasher);
    body.symbol.hash(&mut hasher);
    body.close_pct.to_bits().hash(&mut hasher);
    body.order_type.hash(&mut hasher);
    body.limit_price.map(|p| p.to_bits()).hash(&mut hasher);
    format!("{:x}", hasher.finish())
}

// ── Routes ──────────────────────────────────────────────────────────

pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/trade/enabled", get(trade_enabled))
        .route("/api/trade/preview", post(trade_preview))
        .route("/api/trade/execute", post(trade_execute))
        .route("/api/trade/close", post(trade_close))
        .route("/api/trade/cancel", post(trade_cancel))
        .route("/api/trade/open-orders/{symbol}", get(trade_open_orders))
        .route("/api/trade/{id}/result", get(trade_result))
}

// ── Safety layer helpers ────────────────────────────────────────────

fn require_trade_enabled(state: &AppState) -> Result<(), HubError> {
    if !state.config.manual_trade_enabled {
        return Err(HubError::Forbidden("manual trading is disabled".into()));
    }
    Ok(())
}

/// Check per-symbol rate limit (5-second cooldown).
/// Lazily evicts stale entries older than 60 seconds.
async fn check_rate_limit(state: &AppState, symbol: &str) -> Result<(), HubError> {
    let mut limits = state.trade_rate_limits.lock().await;
    // Lazy GC: remove entries older than 60s
    limits.retain(|_, ts| ts.elapsed().as_secs() < 60);
    if let Some(last) = limits.get(symbol) {
        if last.elapsed().as_secs() < 5 {
            return Err(HubError::BadRequest(format!(
                "rate limited: wait before trading {symbol} again"
            )));
        }
    }
    limits.insert(symbol.to_string(), Instant::now());
    Ok(())
}

/// Atomically check that no other manual_trade job is running AND
/// pre-register this job as Running.  Prevents TOCTOU race.
///
/// Only used for write operations (execute, close) that submit real orders.
/// Read-only operations (preview, open-orders, cancel) skip this to avoid
/// contention with the 10s open-orders poll cycle.
async fn acquire_trade_slot(state: &AppState, job_id: &str) -> Result<(), HubError> {
    let mut jobs = state.jobs.jobs.lock().await;

    // Lazy GC: keep at most 100 completed manual_trade job entries.
    let mut mt_completed: Vec<(String, String)> = jobs
        .iter()
        .filter(|(_, j)| j.kind == "manual_trade" && j.status != JobStatus::Running)
        .map(|(id, j)| (id.clone(), j.created_at.clone()))
        .collect();
    if mt_completed.len() > 100 {
        mt_completed.sort_by(|a, b| a.1.cmp(&b.1));
        for (id, _) in mt_completed.iter().take(mt_completed.len() - 100) {
            jobs.remove(id);
        }
    }

    let running = jobs
        .values()
        .any(|j| j.kind == "manual_trade" && j.status == JobStatus::Running);
    if running {
        return Err(HubError::BadRequest(
            "another manual trade is already running".into(),
        ));
    }
    // Pre-register the job atomically to claim the slot.
    let now = chrono::Utc::now().to_rfc3339();
    jobs.insert(
        job_id.to_string(),
        JobInfo {
            id: job_id.to_string(),
            kind: "manual_trade".to_string(),
            status: JobStatus::Running,
            created_at: now,
            finished_at: None,
            stderr_tail: Vec::new(),
            result_json: None,
            error: None,
        },
    );
    Ok(())
}

// ── Confirm token helpers ───────────────────────────────────────────

/// Generate a confirm token bound to parameter hash and preview job.
/// Lazily evicts tokens older than 5 minutes.
async fn generate_confirm_token(
    state: &AppState,
    param_hash: String,
    preview_job_id: String,
) -> String {
    let token = uuid::Uuid::new_v4().to_string();
    let mut tokens = state.trade_confirm_tokens.lock().await;
    // Lazy GC: remove tokens older than 5 minutes
    tokens.retain(|_, (_, created, _)| created.elapsed().as_secs() < 300);
    tokens.insert(token.clone(), (param_hash, Instant::now(), preview_job_id));
    token
}

/// Validate confirm token: check TTL, param hash match, and that the
/// associated preview job actually succeeded.
async fn validate_confirm_token(
    state: &AppState,
    token: &str,
    expected_hash: &str,
) -> Result<(), HubError> {
    let preview_job_id;
    {
        let mut tokens = state.trade_confirm_tokens.lock().await;
        let (hash, created, jid) = tokens
            .remove(token)
            .ok_or_else(|| HubError::BadRequest("invalid or expired confirm token".into()))?;

        if created.elapsed().as_secs() > 60 {
            return Err(HubError::BadRequest("confirm token expired".into()));
        }
        if hash != expected_hash {
            return Err(HubError::BadRequest(
                "confirm token does not match parameters".into(),
            ));
        }
        preview_job_id = jid;
    }

    // Check the preview job actually succeeded (skip for close previews
    // which don't spawn a subprocess — their job_id won't exist in the store).
    let jobs = state.jobs.jobs.lock().await;
    if let Some(job) = jobs.get(&preview_job_id) {
        if job.status == JobStatus::Running {
            return Err(HubError::BadRequest("preview job still running".into()));
        }
        if let Some(result) = &job.result_json {
            if result.get("ok").and_then(|v| v.as_bool()) != Some(true) {
                return Err(HubError::BadRequest(
                    "preview failed — cannot execute".into(),
                ));
            }
        }
    }

    Ok(())
}

// ── DB path helper ──────────────────────────────────────────────────

fn trade_db_path(state: &AppState) -> Option<String> {
    Some(state.config.live_db.display().to_string())
}

// ── Handlers ────────────────────────────────────────────────────────

/// GET /api/trade/enabled — check if manual trading is active.
async fn trade_enabled(State(state): State<Arc<AppState>>) -> Json<Value> {
    let mode = if state.config.manual_trade_enabled {
        "live"
    } else {
        "disabled"
    };
    Json(json!({
        "enabled": state.config.manual_trade_enabled,
        "mode": mode,
    }))
}

/// POST /api/trade/preview — preview an order (read-only dry run).
///
/// Does NOT acquire a trade slot — previews are read-only and should
/// never block user write operations (execute/close).
async fn trade_preview(
    State(state): State<Arc<AppState>>,
    Json(body): Json<TradeOpenBody>,
) -> Result<Json<Value>, HubError> {
    require_trade_enabled(&state)?;

    let job_id = uuid::Uuid::new_v4().to_string();
    let hash = open_param_hash(&body);
    let confirm_token = generate_confirm_token(&state, hash, job_id.clone()).await;

    let args = ManualTradeArgs {
        action: ManualTradeAction::Preview,
        symbol: body.symbol,
        side: Some(body.side),
        notional_usd: Some(body.notional_usd),
        leverage: Some(body.leverage),
        order_type: Some(body.order_type),
        limit_price: body.limit_price,
        close_pct: None,
        oid: None,
        intent_id: None,
        db_path: trade_db_path(&state),
        secrets_path: state.config.secrets_path.clone(),
    };

    manual_trade::spawn_manual_trade(
        job_id.clone(),
        args,
        state.config.aiq_root.display().to_string(),
        Arc::clone(&state.jobs),
        state.broadcast.clone(),
    )
    .await;

    Ok(Json(json!({
        "job_id": job_id,
        "confirm_token": confirm_token,
        "status": "running",
    })))
}

/// POST /api/trade/execute — execute a confirmed order.
///
/// Acquires exclusive trade slot to prevent concurrent order submissions.
async fn trade_execute(
    State(state): State<Arc<AppState>>,
    Json(body): Json<TradeOpenBody>,
) -> Result<Json<Value>, HubError> {
    require_trade_enabled(&state)?;

    // Validate token + rate limit BEFORE acquiring trade slot to avoid
    // leaving an orphaned Running job entry on validation failure.
    let token = body
        .confirm_token
        .as_deref()
        .ok_or_else(|| HubError::BadRequest("confirm_token required".into()))?;
    let hash = open_param_hash(&body);
    validate_confirm_token(&state, token, &hash).await?;

    check_rate_limit(&state, &body.symbol).await?;

    let job_id = uuid::Uuid::new_v4().to_string();
    acquire_trade_slot(&state, &job_id).await?;

    let args = ManualTradeArgs {
        action: ManualTradeAction::Execute,
        symbol: body.symbol,
        side: Some(body.side),
        notional_usd: Some(body.notional_usd),
        leverage: Some(body.leverage),
        order_type: Some(body.order_type),
        limit_price: body.limit_price,
        close_pct: None,
        oid: None,
        intent_id: None,
        db_path: trade_db_path(&state),
        secrets_path: state.config.secrets_path.clone(),
    };

    manual_trade::spawn_manual_trade(
        job_id.clone(),
        args,
        state.config.aiq_root.display().to_string(),
        Arc::clone(&state.jobs),
        state.broadcast.clone(),
    )
    .await;

    Ok(Json(json!({
        "job_id": job_id,
        "status": "running",
    })))
}

/// POST /api/trade/close — close a position.
///
/// When `confirm_token` is `None`, returns a confirm token immediately
/// (no subprocess needed — position info is already visible in the dashboard).
/// When `Some`, validates the token and spawns the close subprocess.
///
/// Close operations are exempt from per-symbol rate limiting to allow
/// emergency closes immediately after an open.
async fn trade_close(
    State(state): State<Arc<AppState>>,
    Json(body): Json<TradeCloseBody>,
) -> Result<Json<Value>, HubError> {
    require_trade_enabled(&state)?;

    let hash = close_param_hash(&body);

    // No token → close preview: just generate a confirm token (no subprocess).
    if body.confirm_token.is_none() {
        let confirm_token =
            generate_confirm_token(&state, hash, "close_preview".to_string()).await;
        return Ok(Json(json!({
            "confirm_token": confirm_token,
            "status": "ready",
        })));
    }

    // Token present → validate and execute the close.
    let token = body.confirm_token.as_deref().unwrap();
    validate_confirm_token(&state, token, &hash).await?;

    // No rate limit for close — allow emergency close immediately.

    let job_id = uuid::Uuid::new_v4().to_string();
    acquire_trade_slot(&state, &job_id).await?;

    let args = ManualTradeArgs {
        action: ManualTradeAction::Close,
        symbol: body.symbol,
        side: None,
        notional_usd: None,
        leverage: None,
        order_type: Some(body.order_type),
        limit_price: body.limit_price,
        close_pct: Some(body.close_pct),
        oid: None,
        intent_id: None,
        db_path: trade_db_path(&state),
        secrets_path: state.config.secrets_path.clone(),
    };

    manual_trade::spawn_manual_trade(
        job_id.clone(),
        args,
        state.config.aiq_root.display().to_string(),
        Arc::clone(&state.jobs),
        state.broadcast.clone(),
    )
    .await;

    Ok(Json(json!({
        "job_id": job_id,
        "status": "running",
    })))
}

/// POST /api/trade/cancel — cancel a pending GTC order.
///
/// Does NOT acquire a trade slot — cancels should always be allowed,
/// even when another trade is in progress.
async fn trade_cancel(
    State(state): State<Arc<AppState>>,
    Json(body): Json<TradeCancelBody>,
) -> Result<Json<Value>, HubError> {
    require_trade_enabled(&state)?;

    // Must provide at least one of oid or intent_id.
    if body.oid.is_none() && body.intent_id.is_none() {
        return Err(HubError::BadRequest(
            "oid or intent_id required for cancel".into(),
        ));
    }

    let job_id = uuid::Uuid::new_v4().to_string();

    let args = ManualTradeArgs {
        action: ManualTradeAction::Cancel,
        symbol: body.symbol,
        side: None,
        notional_usd: None,
        leverage: None,
        order_type: None,
        limit_price: None,
        close_pct: None,
        oid: body.oid,
        intent_id: body.intent_id,
        db_path: trade_db_path(&state),
        secrets_path: state.config.secrets_path.clone(),
    };

    manual_trade::spawn_manual_trade(
        job_id.clone(),
        args,
        state.config.aiq_root.display().to_string(),
        Arc::clone(&state.jobs),
        state.broadcast.clone(),
    )
    .await;

    Ok(Json(json!({
        "job_id": job_id,
        "status": "running",
    })))
}

/// GET /api/trade/open-orders/{symbol} — list pending GTC orders.
///
/// Does NOT acquire a trade slot — this is a read-only query that runs
/// on a 10s poll timer and should never block user write operations.
async fn trade_open_orders(
    State(state): State<Arc<AppState>>,
    Path(symbol): Path<String>,
) -> Result<Json<Value>, HubError> {
    require_trade_enabled(&state)?;

    let job_id = uuid::Uuid::new_v4().to_string();

    let args = ManualTradeArgs {
        action: ManualTradeAction::OpenOrders,
        symbol,
        side: None,
        notional_usd: None,
        leverage: None,
        order_type: None,
        limit_price: None,
        close_pct: None,
        oid: None,
        intent_id: None,
        db_path: trade_db_path(&state),
        secrets_path: state.config.secrets_path.clone(),
    };

    manual_trade::spawn_manual_trade(
        job_id.clone(),
        args,
        state.config.aiq_root.display().to_string(),
        Arc::clone(&state.jobs),
        state.broadcast.clone(),
    )
    .await;

    Ok(Json(json!({
        "job_id": job_id,
        "status": "running",
    })))
}

/// GET /api/trade/{id}/result — get result JSON for a completed trade job.
async fn trade_result(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<Value>, HubError> {
    let jobs = state.jobs.jobs.lock().await;
    let job = jobs
        .get(&id)
        .ok_or_else(|| HubError::NotFound(format!("job {id} not found")))?;
    if job.status == JobStatus::Running {
        return Err(HubError::BadRequest("job still running".into()));
    }
    match &job.result_json {
        Some(result) => Ok(Json(result.clone())),
        None => Err(HubError::NotFound("no result available".into())),
    }
}
