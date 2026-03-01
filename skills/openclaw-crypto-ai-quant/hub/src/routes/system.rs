use axum::{
    extract::{Query, State},
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::process::Command;

use crate::error::HubError;
use crate::state::AppState;

/// Build system sub-router.
pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/system/services", get(list_services))
        .route("/api/system/services/{name}/{action}", post(service_action))
        .route("/api/system/db-stats", get(db_stats))
        .route("/api/system/disk", get(disk_usage))
        .route("/api/system/logs", get(service_logs))
}

/// Known service names (allow-list for safety).
const ALLOWED_SERVICES: &[&str] = &[
    "openclaw-ai-quant-live-v8",
    "openclaw-ai-quant-trader-v8-paper1",
    "openclaw-ai-quant-trader-v8-paper2",
    "openclaw-ai-quant-trader-v8-paper3",
    "openclaw-ai-quant-monitor-v8",
    "openclaw-ai-quant-factory-v8",
    "openclaw-ai-quant-factory-v8-deep",
    "openclaw-ai-quant-funding",
    "openclaw-ai-quant-ws-sidecar",
    "openclaw-ai-quant-prune-runtime-logs-v8",
    "openclaw-gateway",
];

/// Validate service name is in allow-list.
fn validate_service(name: &str) -> Result<(), HubError> {
    if ALLOWED_SERVICES.contains(&name) {
        Ok(())
    } else {
        Err(HubError::BadRequest(format!("unknown service: {name}")))
    }
}

/// GET /api/system/services — List systemd user services with status.
async fn list_services(State(_state): State<Arc<AppState>>) -> Result<Json<Vec<Value>>, HubError> {
    let mut services = Vec::new();

    for svc_name in ALLOWED_SERVICES {
        let unit = format!("{svc_name}.service");
        let output = Command::new("systemctl")
            .arg("--user")
            .arg("show")
            .arg(&unit)
            .arg("--property=ActiveState,SubState,MainPID,LoadState")
            .output()
            .await;

        let (active, sub, pid, load) = match output {
            Ok(out) => {
                let text = String::from_utf8_lossy(&out.stdout);
                let mut active = String::new();
                let mut sub = String::new();
                let mut pid = String::new();
                let mut load = String::new();
                for line in text.lines() {
                    if let Some(v) = line.strip_prefix("ActiveState=") {
                        active = v.to_string();
                    } else if let Some(v) = line.strip_prefix("SubState=") {
                        sub = v.to_string();
                    } else if let Some(v) = line.strip_prefix("MainPID=") {
                        pid = v.to_string();
                    } else if let Some(v) = line.strip_prefix("LoadState=") {
                        load = v.to_string();
                    }
                }
                (active, sub, pid, load)
            }
            Err(_) => (
                "unknown".to_string(),
                "unknown".to_string(),
                "0".to_string(),
                "unknown".to_string(),
            ),
        };

        let status = if active == "active" {
            "ok"
        } else if load == "not-found" {
            "unknown"
        } else {
            "bad"
        };

        services.push(json!({
            "name": svc_name,
            "active": active,
            "sub": sub,
            "pid": pid,
            "load": load,
            "status": status,
        }));
    }

    Ok(Json(services))
}

/// POST /api/system/services/{name}/{action} — Restart/start/stop a service.
async fn service_action(
    axum::extract::Path((name, action)): axum::extract::Path<(String, String)>,
) -> Result<Json<Value>, HubError> {
    validate_service(&name)?;

    match action.as_str() {
        "restart" | "start" | "stop" => {}
        _ => return Err(HubError::BadRequest(format!("invalid action: {action}"))),
    }

    let unit = format!("{name}.service");
    let output = Command::new("systemctl")
        .arg("--user")
        .arg(&action)
        .arg(&unit)
        .output()
        .await
        .map_err(|e| HubError::Internal(format!("systemctl failed: {e}")))?;

    let success = output.status.success();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    Ok(Json(json!({
        "ok": success,
        "service": name,
        "action": action,
        "stderr": stderr,
    })))
}

/// GET /api/system/db-stats — Database file sizes and row counts.
async fn db_stats(State(state): State<Arc<AppState>>) -> Result<Json<Vec<Value>>, HubError> {
    let dbs = vec![
        ("live", &state.config.live_db),
        ("paper1", &state.config.paper1_db),
        ("paper2", &state.config.paper2_db),
        ("paper3", &state.config.paper3_db),
    ];

    let mut stats = Vec::new();
    for (label, path) in &dbs {
        let exists = path.exists();
        let size = if exists {
            std::fs::metadata(path).ok().map(|m| m.len()).unwrap_or(0)
        } else {
            0
        };
        let modified = if exists {
            std::fs::metadata(path)
                .ok()
                .and_then(|m| m.modified().ok())
                .map(|t| {
                    let dt: chrono::DateTime<chrono::Utc> = t.into();
                    dt.to_rfc3339()
                })
                .unwrap_or_default()
        } else {
            String::new()
        };

        stats.push(json!({
            "label": label,
            "path": path.display().to_string(),
            "exists": exists,
            "size_bytes": size,
            "size_mb": format!("{:.1}", size as f64 / 1_048_576.0),
            "modified": modified,
        }));
    }

    // Candle DBs
    if state.config.candles_db_dir.exists() {
        if let Ok(entries) = std::fs::read_dir(&state.config.candles_db_dir) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.ends_with(".db") {
                    let meta = entry.metadata().ok();
                    stats.push(json!({
                        "label": format!("candle/{name}"),
                        "path": entry.path().display().to_string(),
                        "exists": true,
                        "size_bytes": meta.as_ref().map(|m| m.len()).unwrap_or(0),
                        "size_mb": format!("{:.1}", meta.as_ref().map(|m| m.len()).unwrap_or(0) as f64 / 1_048_576.0),
                        "modified": meta.and_then(|m| m.modified().ok()).map(|t| {
                            let dt: chrono::DateTime<chrono::Utc> = t.into();
                            dt.to_rfc3339()
                        }).unwrap_or_default(),
                    }));
                }
            }
        }
    }

    Ok(Json(stats))
}

/// Query for logs endpoint.
#[derive(Deserialize)]
pub struct LogsQuery {
    pub service: String,
    pub lines: Option<u32>,
}

/// GET /api/system/logs — Recent journalctl logs for a service.
async fn service_logs(Query(q): Query<LogsQuery>) -> Result<Json<Value>, HubError> {
    validate_service(&q.service)?;

    let lines = q.lines.unwrap_or(50).min(500);
    let unit = format!("{}.service", q.service);

    let output = Command::new("journalctl")
        .arg("--user")
        .arg("-u")
        .arg(&unit)
        .arg("-n")
        .arg(lines.to_string())
        .arg("--no-pager")
        .output()
        .await
        .map_err(|e| HubError::Internal(format!("journalctl failed: {e}")))?;

    let text = String::from_utf8_lossy(&output.stdout).to_string();

    Ok(Json(json!({
        "service": q.service,
        "lines": text.lines().count(),
        "log": text,
    })))
}

/// GET /api/system/disk — Disk usage of key directories.
async fn disk_usage(State(state): State<Arc<AppState>>) -> Result<Json<Vec<Value>>, HubError> {
    let dirs = vec![
        ("project_root", state.config.aiq_root.display().to_string()),
        (
            "candle_dbs",
            state.config.candles_db_dir.display().to_string(),
        ),
        (
            "artifacts",
            state
                .config
                .aiq_root
                .join("artifacts")
                .display()
                .to_string(),
        ),
    ];

    let mut result = Vec::new();
    for (label, path) in dirs {
        let output = Command::new("du").arg("-sh").arg(&path).output().await;
        let size = output
            .ok()
            .map(|o| {
                String::from_utf8_lossy(&o.stdout)
                    .split_whitespace()
                    .next()
                    .unwrap_or("?")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_string());

        result.push(json!({
            "label": label,
            "path": path,
            "size": size,
        }));
    }

    Ok(Json(result))
}
