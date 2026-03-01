use axum::{
    extract::{Query, State},
    routing::{get, post, put},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use crate::error::HubError;
use crate::state::AppState;

/// Query parameter for config endpoints — selects which YAML file to operate on.
#[derive(Deserialize)]
pub struct ConfigQuery {
    /// Config file variant: "main", "live", "paper1", "paper2", "paper3",
    /// "promoted_primary", "promoted_fallback". Default: "main".
    pub file: Option<String>,
}

/// Body for PUT /api/config (raw YAML string).
#[derive(Deserialize)]
pub struct ConfigWriteBody {
    pub yaml: String,
}

/// Diff query parameters.
#[derive(Deserialize)]
pub struct DiffQuery {
    /// Backup timestamp A (filename stem).
    pub a: String,
    /// Backup timestamp B (or "current" for live version).
    pub b: String,
    /// Config file variant (default "main").
    pub file: Option<String>,
}

/// A single backup entry.
#[derive(Serialize)]
pub struct BackupEntry {
    pub filename: String,
    pub modified: String,
    pub size: u64,
}

/// Build the config sub-router.
pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/config", get(get_config))
        .route("/api/config/raw", get(get_config_raw))
        .route("/api/config", put(put_config))
        .route("/api/config/reload", post(post_config_reload))
        .route("/api/config/history", get(get_config_history))
        .route("/api/config/diff", get(get_config_diff))
        .route("/api/config/files", get(get_config_files))
}

// ── Helpers ─────────────────────────────────────────────────────────

/// Resolve the YAML file path for a given variant name.
/// Returns an error if the variant is not in the allow-list (path-traversal protection).
fn resolve_config_path(config_dir: &Path, file: &str) -> Result<PathBuf, HubError> {
    let filename = match file {
        "main" => "strategy_overrides.yaml",
        "live" => "strategy_overrides.live.yaml",
        "livepaper" => "strategy_overrides.livepaper.yaml",
        "paper1" => "strategy_overrides.paper1.yaml",
        "paper2" => "strategy_overrides.paper2.yaml",
        "paper3" => "strategy_overrides.paper3.yaml",
        "promoted_primary" => "strategy_overrides._promoted_primary.yaml",
        "promoted_fallback" => "strategy_overrides._promoted_fallback.yaml",
        _ => {
            return Err(HubError::BadRequest(format!(
                "unknown config variant: {file}"
            )))
        }
    };
    Ok(config_dir.join(filename))
}

/// Variant name from ConfigQuery, defaulting to "main".
fn variant(q: &ConfigQuery) -> &str {
    q.file.as_deref().unwrap_or("main")
}

/// Ensure the backups directory exists and return its path.
fn backups_dir(config_dir: &Path) -> Result<PathBuf, HubError> {
    let dir = config_dir.join("backups");
    if !dir.exists() {
        fs::create_dir_all(&dir)?;
    }
    Ok(dir)
}

// ── Handlers ────────────────────────────────────────────────────────

/// GET /api/config — Read YAML file, return as JSON.
async fn get_config(
    State(state): State<Arc<AppState>>,
    Query(q): Query<ConfigQuery>,
) -> Result<Json<Value>, HubError> {
    let path = resolve_config_path(&state.config.config_dir, variant(&q))?;
    if !path.exists() {
        return Err(HubError::NotFound(format!(
            "config file not found: {}",
            path.display()
        )));
    }
    let raw = fs::read_to_string(&path)?;
    let val: Value = serde_yaml::from_str(&raw)?;
    Ok(Json(val))
}

/// GET /api/config/raw — Read YAML file, return raw text.
async fn get_config_raw(
    State(state): State<Arc<AppState>>,
    Query(q): Query<ConfigQuery>,
) -> Result<String, HubError> {
    let path = resolve_config_path(&state.config.config_dir, variant(&q))?;
    if !path.exists() {
        return Err(HubError::NotFound(format!(
            "config file not found: {}",
            path.display()
        )));
    }
    let raw = fs::read_to_string(&path)?;
    Ok(raw)
}

/// PUT /api/config — Write YAML with atomic backup.
async fn put_config(
    State(state): State<Arc<AppState>>,
    Query(q): Query<ConfigQuery>,
    Json(body): Json<ConfigWriteBody>,
) -> Result<Json<Value>, HubError> {
    // Validate YAML parses.
    let _: Value = serde_yaml::from_str(&body.yaml)
        .map_err(|e| HubError::BadRequest(format!("invalid YAML: {e}")))?;

    let file_variant = variant(&q);
    let path = resolve_config_path(&state.config.config_dir, file_variant)?;

    // Backup current file (if it exists).
    let mut backup_path_str = String::new();
    if path.exists() {
        let bk_dir = backups_dir(&state.config.config_dir)?;
        let ts = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let stem = path
            .file_name()
            .unwrap_or_default()
            .to_str()
            .unwrap_or("config");
        let bk_name = format!("{stem}.{ts}.bak");
        let bk_path = bk_dir.join(&bk_name);
        fs::copy(&path, &bk_path)?;
        backup_path_str = bk_name;
    }

    // Atomic write: write to temp, then rename.
    let tmp_path = path.with_extension("yaml.tmp");
    fs::write(&tmp_path, &body.yaml)?;
    fs::rename(&tmp_path, &path)?;

    Ok(Json(serde_json::json!({
        "ok": true,
        "file": file_variant,
        "backup": backup_path_str,
    })))
}

/// POST /api/config/reload — Touch the config file mtime to trigger hot-reload.
async fn post_config_reload(
    State(state): State<Arc<AppState>>,
    Query(q): Query<ConfigQuery>,
) -> Result<Json<Value>, HubError> {
    let path = resolve_config_path(&state.config.config_dir, variant(&q))?;
    if !path.exists() {
        return Err(HubError::NotFound(format!(
            "config file not found: {}",
            path.display()
        )));
    }

    // Touch mtime by opening and syncing.
    let file = fs::OpenOptions::new().write(true).open(&path)?;
    file.sync_all()?;

    drop(file);

    // Set mtime via libc utimensat for reliability.
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        let c_path = std::ffi::CString::new(path.as_os_str().as_bytes())
            .map_err(|e| HubError::Internal(e.to_string()))?;
        unsafe {
            libc::utimensat(
                libc::AT_FDCWD,
                c_path.as_ptr(),
                std::ptr::null(), // null = set to current time
                0,
            );
        }
    }

    Ok(Json(
        serde_json::json!({ "ok": true, "reloaded": variant(&q) }),
    ))
}

/// GET /api/config/history — List backup files for a config variant.
async fn get_config_history(
    State(state): State<Arc<AppState>>,
    Query(q): Query<ConfigQuery>,
) -> Result<Json<Vec<BackupEntry>>, HubError> {
    let file_variant = variant(&q);
    let path = resolve_config_path(&state.config.config_dir, file_variant)?;
    let stem = path
        .file_name()
        .unwrap_or_default()
        .to_str()
        .unwrap_or("strategy_overrides.yaml");

    let bk_dir = backups_dir(&state.config.config_dir)?;
    let mut entries = Vec::new();

    if bk_dir.exists() {
        for entry in fs::read_dir(&bk_dir)? {
            let entry = entry?;
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with(stem) && name.ends_with(".bak") {
                let meta = entry.metadata()?;
                let modified = meta
                    .modified()
                    .ok()
                    .and_then(|t| {
                        let dt: chrono::DateTime<chrono::Utc> = t.into();
                        Some(dt.to_rfc3339())
                    })
                    .unwrap_or_default();
                entries.push(BackupEntry {
                    filename: name,
                    modified,
                    size: meta.len(),
                });
            }
        }
    }

    // Sort newest first.
    entries.sort_by(|a, b| b.filename.cmp(&a.filename));

    Ok(Json(entries))
}

/// GET /api/config/diff — Simple line-by-line diff between two versions.
async fn get_config_diff(
    State(state): State<Arc<AppState>>,
    Query(q): Query<DiffQuery>,
) -> Result<Json<Value>, HubError> {
    let file_variant = q.file.as_deref().unwrap_or("main");
    let config_path = resolve_config_path(&state.config.config_dir, file_variant)?;
    let bk_dir = backups_dir(&state.config.config_dir)?;

    let read_version = |version: &str| -> Result<String, HubError> {
        if version == "current" {
            if !config_path.exists() {
                return Err(HubError::NotFound("current config not found".into()));
            }
            Ok(fs::read_to_string(&config_path)?)
        } else {
            // version is a backup filename
            let bk_path = bk_dir.join(version);
            // Safety: ensure the resolved path is inside backups dir
            let canonical = bk_path
                .canonicalize()
                .map_err(|_| HubError::NotFound(format!("backup not found: {version}")))?;
            let bk_dir_canon = bk_dir.canonicalize().unwrap_or_else(|_| bk_dir.clone());
            if !canonical.starts_with(&bk_dir_canon) {
                return Err(HubError::BadRequest("invalid backup path".into()));
            }
            Ok(fs::read_to_string(&canonical)?)
        }
    };

    let text_a = read_version(&q.a)?;
    let text_b = read_version(&q.b)?;

    // Simple unified-style diff.
    let lines_a: Vec<&str> = text_a.lines().collect();
    let lines_b: Vec<&str> = text_b.lines().collect();

    let mut diff_lines = Vec::new();
    let max_len = lines_a.len().max(lines_b.len());
    for i in 0..max_len {
        let la = lines_a.get(i).copied().unwrap_or("");
        let lb = lines_b.get(i).copied().unwrap_or("");
        if la != lb {
            if !la.is_empty() {
                diff_lines.push(format!("-{la}"));
            }
            if !lb.is_empty() {
                diff_lines.push(format!("+{lb}"));
            }
        } else {
            diff_lines.push(format!(" {la}"));
        }
    }

    Ok(Json(serde_json::json!({
        "a": q.a,
        "b": q.b,
        "file": file_variant,
        "diff": diff_lines,
    })))
}

/// GET /api/config/files — List available config files with metadata.
async fn get_config_files(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<Value>>, HubError> {
    let variants = [
        "main",
        "live",
        "livepaper",
        "paper1",
        "paper2",
        "paper3",
        "promoted_primary",
        "promoted_fallback",
    ];

    let mut files = Vec::new();
    for v in &variants {
        if let Ok(path) = resolve_config_path(&state.config.config_dir, v) {
            let exists = path.exists();
            let (modified, size) = if exists {
                let meta = fs::metadata(&path).ok();
                let modified = meta
                    .as_ref()
                    .and_then(|m| m.modified().ok())
                    .map(|t| {
                        let dt: chrono::DateTime<chrono::Utc> = t.into();
                        dt.to_rfc3339()
                    })
                    .unwrap_or_default();
                let size = meta.map(|m| m.len()).unwrap_or(0);
                (modified, size)
            } else {
                (String::new(), 0)
            };
            files.push(serde_json::json!({
                "variant": v,
                "filename": path.file_name().unwrap_or_default().to_str().unwrap_or(""),
                "exists": exists,
                "modified": modified,
                "size": size,
            }));
        }
    }

    Ok(Json(files))
}
