//! CUDA code generator: derives GPU accounting and decision functions from Rust kernel source.
//!
//! This module reads `decision_kernel.rs` and `accounting.rs` signatures and
//! emits CUDA-compatible `.cu` device functions that mirror the Rust logic.
//!
//! The approach is string-template based (not full AST parsing) — pragmatic and
//! sufficient to guarantee accounting parity by construction.

pub mod decision;
mod emit;
mod templates;

use std::path::Path;

/// Run the full codegen pipeline: accounting + decision.
pub fn run(out_dir: &Path, inspect_dir: &Path, source_hashes_json: &str) {
    // Accounting codegen (existing)
    let accounting_source = render_all();
    emit::write_generated(out_dir, "generated_accounting.cu", &accounting_source);
    emit::write_generated(inspect_dir, "generated_accounting.cu", &accounting_source);
    eprintln!(
        "cargo:warning=codegen: wrote generated_accounting.cu ({} bytes)",
        accounting_source.len()
    );

    // Decision codegen (new — AQC-1201) with embedded source hashes (AQC-1200)
    decision::run(out_dir, inspect_dir, Some(source_hashes_json));
}

/// Render all accounting templates into a single CUDA source string.
fn render_all() -> String {
    let mut out = String::with_capacity(8192);

    out.push_str(templates::HEADER);
    out.push('\n');
    out.push_str(&templates::quantize_codegen());
    out.push('\n');
    out.push_str(&templates::apply_open_codegen());
    out.push('\n');
    out.push_str(&templates::apply_close_codegen());
    out.push('\n');
    out.push_str(&templates::apply_partial_close_codegen());
    out.push('\n');
    out.push_str(&templates::funding_delta_codegen());
    out.push('\n');
    out.push_str(&templates::mark_to_market_pnl_codegen());
    out.push('\n');

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_all_contains_all_functions() {
        let source = render_all();
        assert!(source.contains("__device__ double quantize_codegen("));
        assert!(source.contains("__device__ void apply_open_codegen("));
        assert!(source.contains("__device__ void apply_close_codegen("));
        assert!(source.contains("__device__ void apply_partial_close_codegen("));
        assert!(source.contains("__device__ double funding_delta_codegen("));
        assert!(source.contains("__device__ double mark_to_market_pnl_codegen("));
        assert!(source.contains("AUTO-GENERATED"));
    }

    #[test]
    fn render_uses_double_accumulators() {
        let source = render_all();
        // All monetary calculations must use double, not float
        assert!(source.contains("double notional"));
        assert!(source.contains("double fee"));
        assert!(source.contains("double pnl"));
    }
}
