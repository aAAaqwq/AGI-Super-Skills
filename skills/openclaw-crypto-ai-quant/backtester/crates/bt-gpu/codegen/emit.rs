//! File emitter: writes generated CUDA source to the target directory.

use std::fs;
use std::path::Path;

/// Write `content` to `dir/filename`, creating the directory if needed.
pub fn write_generated(dir: &Path, filename: &str, content: &str) {
    fs::create_dir_all(dir).unwrap_or_else(|e| {
        panic!(
            "codegen: failed to create directory {}: {}",
            dir.display(),
            e
        );
    });

    let path = dir.join(filename);
    fs::write(&path, content).unwrap_or_else(|e| {
        panic!("codegen: failed to write {}: {}", path.display(), e);
    });
}
