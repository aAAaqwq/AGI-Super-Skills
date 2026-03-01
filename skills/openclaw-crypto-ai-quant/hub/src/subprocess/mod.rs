pub mod backtester;
pub mod manual_trade;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

use crate::ws::broadcast::BroadcastHub;

/// Unique job identifier.
pub type JobId = String;

/// Job status enum.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Running,
    Done,
    Failed,
    Cancelled,
}

/// Metadata for a running or completed job.
#[derive(Debug, Clone, Serialize)]
pub struct JobInfo {
    pub id: JobId,
    pub kind: String, // "backtest", "sweep", or "manual_trade"
    pub status: JobStatus,
    pub created_at: String,
    pub finished_at: Option<String>,
    pub stderr_tail: Vec<String>,
    pub result_json: Option<serde_json::Value>,
    pub error: Option<String>,
}

/// Thread-safe job store.
pub struct JobStore {
    pub jobs: Mutex<HashMap<JobId, JobInfo>>,
    pub handles: Mutex<HashMap<JobId, Child>>,
}

impl JobStore {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            jobs: Mutex::new(HashMap::new()),
            handles: Mutex::new(HashMap::new()),
        })
    }
}

/// Generic subprocess runner: captures stdout + stderr, updates job store.
pub(crate) async fn run_subprocess(
    job_id: JobId,
    kind: &str,
    mut cmd: Command,
    store: Arc<JobStore>,
    broadcast: BroadcastHub,
) {
    let now = chrono::Utc::now().to_rfc3339();
    let info = JobInfo {
        id: job_id.clone(),
        kind: kind.to_string(),
        status: JobStatus::Running,
        created_at: now,
        finished_at: None,
        stderr_tail: Vec::new(),
        result_json: None,
        error: None,
    };

    {
        let mut jobs = store.jobs.lock().await;
        jobs.insert(job_id.clone(), info);
    }

    let child = cmd.spawn();
    let mut child = match child {
        Ok(c) => c,
        Err(e) => {
            let mut jobs = store.jobs.lock().await;
            if let Some(j) = jobs.get_mut(&job_id) {
                j.status = JobStatus::Failed;
                j.error = Some(format!("spawn failed: {e}"));
                j.finished_at = Some(chrono::Utc::now().to_rfc3339());
            }
            return;
        }
    };

    // Store child handle for cancellation.
    let child_id = child.id();
    {
        // We can't store Child directly since we need to take stdout/stderr.
        // Instead, we'll handle cancellation via the PID.
        let _ = child_id;
    }

    let stdout = child.stdout.take();
    let stderr = child.stderr.take();

    // Collect stdout (JSON result).
    let stdout_handle = tokio::spawn(async move {
        let mut output = String::new();
        if let Some(stdout) = stdout {
            let mut reader = BufReader::new(stdout).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                output.push_str(&line);
                output.push('\n');
            }
        }
        output
    });

    // Stream stderr (progress lines) and broadcast via WebSocket.
    let store_clone = Arc::clone(&store);
    let jid_clone = job_id.clone();
    let bc = broadcast.clone();
    let stderr_handle = tokio::spawn(async move {
        let mut tail: Vec<String> = Vec::new();
        if let Some(stderr) = stderr {
            let mut reader = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                // Broadcast progress line.
                if let Ok(msg) = serde_json::to_string(&serde_json::json!({
                    "type": "job_progress",
                    "job_id": jid_clone,
                    "line": line,
                })) {
                    bc.publish(&format!("job:{jid_clone}"), msg);
                }

                // Keep last 100 lines.
                tail.push(line);
                if tail.len() > 100 {
                    tail.remove(0);
                }
            }
        }

        // Update stderr tail.
        let mut jobs = store_clone.jobs.lock().await;
        if let Some(j) = jobs.get_mut(&jid_clone) {
            j.stderr_tail = tail;
        }
    });

    // Wait for process to exit.
    let exit_status = child.wait().await;

    let _ = stderr_handle.await;
    let stdout_output = stdout_handle.await.unwrap_or_default();

    // Update job status.
    let mut jobs = store.jobs.lock().await;
    if let Some(j) = jobs.get_mut(&job_id) {
        j.finished_at = Some(chrono::Utc::now().to_rfc3339());

        match exit_status {
            Ok(status) if status.success() => {
                j.status = JobStatus::Done;
                // Parse stdout as JSON.
                match serde_json::from_str::<serde_json::Value>(&stdout_output) {
                    Ok(val) => j.result_json = Some(val),
                    Err(e) => {
                        j.error = Some(format!("failed to parse result JSON: {e}"));
                        // Still mark as done — the output file may have been used.
                    }
                }
            }
            Ok(status) => {
                j.status = JobStatus::Failed;
                j.error = Some(format!("exited with code {}", status.code().unwrap_or(-1)));
                // Still try to parse stdout — Python may have emitted a structured error.
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&stdout_output) {
                    j.result_json = Some(val);
                }
            }
            Err(e) => {
                j.status = JobStatus::Failed;
                j.error = Some(format!("wait error: {e}"));
            }
        }

        // Broadcast completion.
        if let Ok(msg) = serde_json::to_string(&serde_json::json!({
            "type": "job_done",
            "job_id": job_id,
            "status": j.status,
        })) {
            broadcast.publish(&format!("job:{job_id}"), msg);
        }
    }
}
