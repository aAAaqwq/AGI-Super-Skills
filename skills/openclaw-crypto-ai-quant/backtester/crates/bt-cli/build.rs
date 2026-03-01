use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn _git_sha() -> String {
    if let Ok(sha) = std::env::var("GITHUB_SHA") {
        let s = sha.trim();
        if !s.is_empty() {
            return s.chars().take(12).collect();
        }
    }

    // Best-effort local build: derive from git.
    let out = Command::new("git")
        .args(["rev-parse", "--short=12", "HEAD"])
        .output();
    if let Ok(out) = out {
        if out.status.success() {
            let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !s.is_empty() {
                return s;
            }
        }
    }
    "unknown".to_string()
}

fn _build_unix_s() -> u64 {
    if let Ok(v) = std::env::var("SOURCE_DATE_EPOCH") {
        if let Ok(x) = v.trim().parse::<u64>() {
            return x;
        }
    }
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn main() {
    let sha = _git_sha();
    println!("cargo:rustc-env=AIQ_GIT_SHA={sha}");

    let build_unix = _build_unix_s();
    println!("cargo:rustc-env=AIQ_BUILD_UNIX={build_unix}");

    let gpu = if std::env::var_os("CARGO_FEATURE_GPU").is_some() {
        "1"
    } else {
        "0"
    };
    println!("cargo:rustc-env=AIQ_GPU={gpu}");

    println!("cargo:rerun-if-env-changed=GITHUB_SHA");
    println!("cargo:rerun-if-env-changed=SOURCE_DATE_EPOCH");
    println!("cargo:rerun-if-env-changed=CARGO_FEATURE_GPU");
}
