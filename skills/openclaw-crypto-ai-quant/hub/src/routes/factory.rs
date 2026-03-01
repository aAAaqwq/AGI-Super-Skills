use axum::{
    extract::{Path, State},
    routing::get,
    Json, Router,
};
use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;

use crate::error::HubError;
use crate::state::AppState;

/// Build factory sub-router.
pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/factory/runs", get(list_runs))
        .route("/api/factory/runs/{date}/{run_id}", get(run_detail))
        .route("/api/factory/runs/{date}/{run_id}/report", get(run_report))
        .route(
            "/api/factory/runs/{date}/{run_id}/candidates",
            get(run_candidates),
        )
}

/// Resolve the artifacts directory.
fn artifacts_dir(state: &AppState) -> PathBuf {
    state.config.aiq_root.join("artifacts")
}

/// Validate a date string is YYYY-MM-DD (path-traversal protection).
fn validate_date(date: &str) -> Result<(), HubError> {
    if date.len() == 10
        && date.chars().all(|c| c.is_ascii_digit() || c == '-')
        && date.chars().filter(|c| *c == '-').count() == 2
    {
        Ok(())
    } else {
        Err(HubError::BadRequest(format!("invalid date: {date}")))
    }
}

/// Validate a run_id (alphanumeric + underscores + dashes + T/Z).
fn validate_run_id(id: &str) -> Result<(), HubError> {
    if !id.is_empty()
        && id
            .chars()
            .all(|c| c.is_alphanumeric() || c == '_' || c == '-' || c == 'T' || c == 'Z')
    {
        Ok(())
    } else {
        Err(HubError::BadRequest(format!("invalid run_id: {id}")))
    }
}

/// GET /api/factory/runs — List all factory runs across all dates.
async fn list_runs(State(state): State<Arc<AppState>>) -> Result<Json<Vec<Value>>, HubError> {
    let base = artifacts_dir(&state);
    let mut runs = Vec::new();

    if !base.exists() {
        return Ok(Json(runs));
    }

    // Iterate date directories.
    let mut dates: Vec<String> = Vec::new();
    for entry in fs::read_dir(&base)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if entry.file_type()?.is_dir() && validate_date(&name).is_ok() {
            dates.push(name);
        }
    }
    dates.sort();
    dates.reverse(); // newest first

    for date in &dates {
        let date_dir = base.join(date);
        if !date_dir.is_dir() {
            continue;
        }
        for entry in fs::read_dir(&date_dir)? {
            let entry = entry?;
            let run_id = entry.file_name().to_string_lossy().to_string();
            if !entry.file_type()?.is_dir() {
                continue;
            }

            // Read metadata if available.
            let meta_path = entry.path().join("run_metadata.json");
            let metadata = if meta_path.exists() {
                fs::read_to_string(&meta_path)
                    .ok()
                    .and_then(|s| serde_json::from_str::<Value>(&s).ok())
            } else {
                None
            };

            let has_report = entry.path().join("reports/report.json").exists();

            runs.push(json!({
                "date": date,
                "run_id": run_id,
                "has_report": has_report,
                "profile": metadata.as_ref()
                    .and_then(|m| m["args"]["profile"].as_str())
                    .unwrap_or("unknown"),
                "num_candidates": metadata.as_ref()
                    .and_then(|m| m["args"]["num_candidates"].as_i64()),
            }));
        }
    }

    Ok(Json(runs))
}

/// GET /api/factory/runs/{date}/{run_id} — Run metadata.
async fn run_detail(
    State(state): State<Arc<AppState>>,
    Path((date, run_id)): Path<(String, String)>,
) -> Result<Json<Value>, HubError> {
    validate_date(&date)?;
    validate_run_id(&run_id)?;

    let run_dir = artifacts_dir(&state).join(&date).join(&run_id);
    if !run_dir.is_dir() {
        return Err(HubError::NotFound(format!(
            "run not found: {date}/{run_id}"
        )));
    }

    let meta_path = run_dir.join("run_metadata.json");
    let metadata = if meta_path.exists() {
        let raw = fs::read_to_string(&meta_path)?;
        serde_json::from_str::<Value>(&raw)?
    } else {
        json!({})
    };

    // List subdirectories to show available data.
    let subdirs: Vec<String> = fs::read_dir(&run_dir)?
        .filter_map(|e| {
            let e = e.ok()?;
            if e.file_type().ok()?.is_dir() {
                Some(e.file_name().to_string_lossy().to_string())
            } else {
                None
            }
        })
        .collect();

    Ok(Json(json!({
        "date": date,
        "run_id": run_id,
        "metadata": metadata,
        "subdirs": subdirs,
    })))
}

/// GET /api/factory/runs/{date}/{run_id}/report — Factory report.json content.
async fn run_report(
    State(state): State<Arc<AppState>>,
    Path((date, run_id)): Path<(String, String)>,
) -> Result<Json<Value>, HubError> {
    validate_date(&date)?;
    validate_run_id(&run_id)?;

    let report_path = artifacts_dir(&state)
        .join(&date)
        .join(&run_id)
        .join("reports/report.json");

    if !report_path.exists() {
        return Err(HubError::NotFound("report.json not found".into()));
    }

    let raw = fs::read_to_string(&report_path)?;
    let val: Value = serde_json::from_str(&raw)?;
    Ok(Json(val))
}

/// GET /api/factory/runs/{date}/{run_id}/candidates — List candidate configs.
async fn run_candidates(
    State(state): State<Arc<AppState>>,
    Path((date, run_id)): Path<(String, String)>,
) -> Result<Json<Vec<Value>>, HubError> {
    validate_date(&date)?;
    validate_run_id(&run_id)?;

    let configs_dir = artifacts_dir(&state)
        .join(&date)
        .join(&run_id)
        .join("configs");

    if !configs_dir.exists() {
        return Ok(Json(Vec::new()));
    }

    let mut candidates = Vec::new();
    for entry in fs::read_dir(&configs_dir)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if name.ends_with(".yaml") || name.ends_with(".yml") {
            let size = entry.metadata()?.len();
            candidates.push(json!({
                "filename": name,
                "size": size,
            }));
        }
    }
    candidates.sort_by(|a, b| {
        a["filename"]
            .as_str()
            .unwrap_or("")
            .cmp(b["filename"].as_str().unwrap_or(""))
    });

    Ok(Json(candidates))
}
