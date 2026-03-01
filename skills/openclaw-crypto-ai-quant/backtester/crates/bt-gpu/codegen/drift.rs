//! Source-hash drift detector for decision codegen.
//!
//! Computes SHA-256 hashes of the Rust source files that decision codegen
//! depends on.  These hashes are:
//!
//! 1. Written to `kernels/decision_source_hashes.json` (manifest).
//! 2. Compared against hashes embedded in the header comment of
//!    `kernels/generated_decision.cu` to detect stale codegen output.
//!
//! When drift is detected, a `cargo:warning` is emitted (or a panic if
//! `STRICT_CODEGEN_PARITY=1`).

use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::Path;

/// Source files that decision codegen depends on.
pub const DECISION_SOURCE_FILES: &[&str] = &[
    "../bt-signals/src/gates.rs",
    "../bt-signals/src/entry.rs",
    "../bt-core/src/exits/stop_loss.rs",
    "../bt-core/src/exits/trailing.rs",
    "../bt-core/src/exits/take_profit.rs",
    "../bt-core/src/exits/smart_exits.rs",
    "../bt-core/src/exits/mod.rs",
];

/// The prefix used to embed source hashes in generated CUDA files.
const HASH_LINE_PREFIX: &str = "// SOURCE_HASHES: ";

/// Compute SHA-256 hash of a file's contents, returning a lowercase hex string.
pub fn file_sha256(path: &Path) -> String {
    let bytes = std::fs::read(path)
        .unwrap_or_else(|e| panic!("drift: failed to read {}: {}", path.display(), e));
    let digest = Sha256::digest(&bytes);
    format!("{:x}", digest)
}

/// Compute hashes for all decision source files.
///
/// Keys are the relative paths as listed in [`DECISION_SOURCE_FILES`].
pub fn compute_source_hashes() -> BTreeMap<String, String> {
    DECISION_SOURCE_FILES
        .iter()
        .map(|&rel| {
            let hash = file_sha256(Path::new(rel));
            (rel.to_string(), hash)
        })
        .collect()
}

/// Format hashes as a pretty-printed JSON manifest string.
pub fn format_manifest(hashes: &BTreeMap<String, String>) -> String {
    let mut out = String::from("{\n");
    let len = hashes.len();
    for (i, (key, val)) in hashes.iter().enumerate() {
        out.push_str(&format!("  \"{}\": \"{}\"", key, val));
        if i + 1 < len {
            out.push(',');
        }
        out.push('\n');
    }
    out.push_str("}\n");
    out
}

/// Format hashes as a compact single-line JSON string (for embedding in CUDA
/// header comments).  Used by decision codegen (AQC-1201) to write the
/// `// SOURCE_HASHES: …` header line.
#[allow(dead_code)]
pub fn format_inline_json(hashes: &BTreeMap<String, String>) -> String {
    let entries: Vec<String> = hashes
        .iter()
        .map(|(k, v)| format!("\"{}\":\"{}\"", k, v))
        .collect();
    format!("{{{}}}", entries.join(","))
}

/// Extract hashes from the header comment of a generated CUDA file.
///
/// Looks for a line matching `// SOURCE_HASHES: {…}` and parses the JSON
/// payload.  Returns `None` if the file doesn't exist or has no hash header.
pub fn read_embedded_hashes(generated_path: &Path) -> Option<BTreeMap<String, String>> {
    let content = std::fs::read_to_string(generated_path).ok()?;

    for line in content.lines() {
        let trimmed = line.trim();
        if let Some(json_str) = trimmed.strip_prefix(HASH_LINE_PREFIX) {
            // Parse the compact JSON into a BTreeMap.
            let map: BTreeMap<String, String> = serde_json::from_str(json_str).ok()?;
            return Some(map);
        }
    }

    None
}

/// Check for drift between current source hashes and the hashes embedded in
/// the generated CUDA file.
///
/// Returns a list of file paths whose hashes differ (or are missing from the
/// embedded set).
pub fn check_drift(
    current: &BTreeMap<String, String>,
    embedded: &BTreeMap<String, String>,
) -> Vec<String> {
    let mut drifted = Vec::new();

    for (path, hash) in current {
        match embedded.get(path) {
            Some(embedded_hash) if embedded_hash == hash => {}
            _ => drifted.push(path.clone()),
        }
    }

    drifted
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn format_manifest_roundtrip() {
        let mut hashes = BTreeMap::new();
        hashes.insert("a.rs".to_string(), "abc123".to_string());
        hashes.insert("b.rs".to_string(), "def456".to_string());

        let manifest = format_manifest(&hashes);
        assert!(manifest.contains("\"a.rs\": \"abc123\""));
        assert!(manifest.contains("\"b.rs\": \"def456\""));
    }

    #[test]
    fn format_inline_json_sorted() {
        let mut hashes = BTreeMap::new();
        hashes.insert("z.rs".to_string(), "111".to_string());
        hashes.insert("a.rs".to_string(), "222".to_string());

        let inline = format_inline_json(&hashes);
        // BTreeMap iterates in sorted order
        assert_eq!(inline, r#"{"a.rs":"222","z.rs":"111"}"#);
    }

    #[test]
    fn read_embedded_hashes_parses_header() {
        use std::io::Write;
        let dir = std::env::temp_dir().join("drift_test");
        std::fs::create_dir_all(&dir).unwrap();
        let file_path = dir.join("test_generated.cu");

        let mut f = std::fs::File::create(&file_path).unwrap();
        writeln!(f, "// AUTO-GENERATED — do not edit").unwrap();
        writeln!(
            f,
            r#"// SOURCE_HASHES: {{"a.rs":"abc123","b.rs":"def456"}}"#
        )
        .unwrap();
        writeln!(f, "__device__ void foo() {{}}").unwrap();
        drop(f);

        let hashes = read_embedded_hashes(&file_path).unwrap();
        assert_eq!(hashes.get("a.rs").unwrap(), "abc123");
        assert_eq!(hashes.get("b.rs").unwrap(), "def456");

        std::fs::remove_file(&file_path).ok();
    }

    #[test]
    fn read_embedded_hashes_missing_file() {
        let result = read_embedded_hashes(Path::new("/nonexistent/file.cu"));
        assert!(result.is_none());
    }

    #[test]
    fn check_drift_detects_changes() {
        let mut current = BTreeMap::new();
        current.insert("a.rs".to_string(), "aaa".to_string());
        current.insert("b.rs".to_string(), "bbb_new".to_string());
        current.insert("c.rs".to_string(), "ccc".to_string());

        let mut embedded = BTreeMap::new();
        embedded.insert("a.rs".to_string(), "aaa".to_string());
        embedded.insert("b.rs".to_string(), "bbb_old".to_string());
        // c.rs missing from embedded

        let drifted = check_drift(&current, &embedded);
        assert_eq!(drifted, vec!["b.rs", "c.rs"]);
    }

    #[test]
    fn check_drift_no_changes() {
        let mut hashes = BTreeMap::new();
        hashes.insert("a.rs".to_string(), "same".to_string());

        let drifted = check_drift(&hashes, &hashes);
        assert!(drifted.is_empty());
    }
}
