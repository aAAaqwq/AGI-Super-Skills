use axum::{
    extract::{Path, State},
    routing::{delete, get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;

use crate::error::HubError;
use crate::state::AppState;
use crate::subprocess::backtester;
use crate::subprocess::JobStatus;

/// Body for POST /api/backtest/run.
#[derive(Deserialize)]
pub struct RunBacktestBody {
    /// Config file variant (default "main").
    pub config: Option<String>,
    /// Initial balance for the replay.
    pub initial_balance: Option<f64>,
    /// Optional single-symbol filter.
    pub symbol: Option<String>,
}

/// Build backtest sub-router.
pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/backtest/run", post(run_backtest))
        .route("/api/backtest/jobs", get(list_jobs))
        .route("/api/backtest/{id}/status", get(job_status))
        .route("/api/backtest/{id}/result", get(job_result))
        .route("/api/backtest/{id}", delete(cancel_job))
}

/// POST /api/backtest/run — launch a new backtest.
async fn run_backtest(
    State(state): State<Arc<AppState>>,
    Json(body): Json<RunBacktestBody>,
) -> Result<Json<Value>, HubError> {
    let job_id = uuid::Uuid::new_v4().to_string();

    let config_variant = body.config.as_deref().unwrap_or("main");
    let config_path = format!(
        "{}/config/{}",
        state.config.aiq_root.display(),
        match config_variant {
            "main" => "strategy_overrides.yaml",
            "live" => "strategy_overrides.live.yaml",
            "paper1" => "strategy_overrides.paper1.yaml",
            "paper2" => "strategy_overrides.paper2.yaml",
            "paper3" => "strategy_overrides.paper3.yaml",
            _ =>
                return Err(HubError::BadRequest(format!(
                    "unknown config: {config_variant}"
                ))),
        }
    );

    let balance = body.initial_balance.unwrap_or(10000.0);

    let args = backtester::ReplayArgs {
        config_path,
        initial_balance: balance,
        symbol: body.symbol,
        output_file: None,
    };

    backtester::spawn_replay(
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

/// GET /api/backtest/jobs — list all backtest jobs.
async fn list_jobs(State(state): State<Arc<AppState>>) -> Result<Json<Vec<Value>>, HubError> {
    let jobs = state.jobs.jobs.lock().await;
    let mut result: Vec<Value> = jobs
        .values()
        .filter(|j| j.kind == "backtest")
        .map(|j| {
            json!({
                "id": j.id,
                "status": j.status,
                "created_at": j.created_at,
                "finished_at": j.finished_at,
                "error": j.error,
            })
        })
        .collect();
    // Sort newest first.
    result.sort_by(|a, b| {
        let ta = a["created_at"].as_str().unwrap_or("");
        let tb = b["created_at"].as_str().unwrap_or("");
        tb.cmp(ta)
    });
    Ok(Json(result))
}

/// GET /api/backtest/{id}/status — job status + stderr tail.
async fn job_status(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<Value>, HubError> {
    let jobs = state.jobs.jobs.lock().await;
    let job = jobs
        .get(&id)
        .ok_or_else(|| HubError::NotFound(format!("job {id} not found")))?;
    Ok(Json(json!({
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "stderr_tail": job.stderr_tail,
        "error": job.error,
    })))
}

/// GET /api/backtest/{id}/result — full result JSON.
async fn job_result(
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

/// DELETE /api/backtest/{id} — cancel a running job.
async fn cancel_job(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<Value>, HubError> {
    let mut jobs = state.jobs.jobs.lock().await;
    let job = jobs
        .get_mut(&id)
        .ok_or_else(|| HubError::NotFound(format!("job {id} not found")))?;
    if job.status != JobStatus::Running {
        return Err(HubError::BadRequest("job is not running".into()));
    }
    job.status = JobStatus::Cancelled;
    job.finished_at = Some(chrono::Utc::now().to_rfc3339());

    // Kill the subprocess via handles.
    let mut handles = state.jobs.handles.lock().await;
    if let Some(mut child) = handles.remove(&id) {
        let _ = child.kill().await;
    }

    Ok(Json(json!({ "ok": true, "cancelled": id })))
}
