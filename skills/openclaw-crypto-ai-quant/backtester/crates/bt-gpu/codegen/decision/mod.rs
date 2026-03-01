//! Decision codegen orchestrator: renders all decision templates into generated_decision.cu.

mod decision_templates;

use std::path::Path;

/// Run the decision codegen pipeline.
pub fn run(out_dir: &Path, inspect_dir: &Path, source_hashes_json: Option<&str>) {
    let source = render_all_decision(source_hashes_json);

    super::emit::write_generated(out_dir, "generated_decision.cu", &source);
    super::emit::write_generated(inspect_dir, "generated_decision.cu", &source);

    eprintln!(
        "cargo:warning=codegen: wrote generated_decision.cu ({} bytes)",
        source.len()
    );
}

/// Render all decision templates into a single CUDA source string.
pub fn render_all_decision(source_hashes_json: Option<&str>) -> String {
    let mut out = String::with_capacity(16384);

    out.push_str(decision_templates::DECISION_HEADER);
    out.push('\n');

    // Embed source hashes for drift detection (AQC-1200)
    if let Some(hashes) = source_hashes_json {
        out.push_str(&format!("// SOURCE_HASHES: {}\n\n", hashes));
    }

    // Gates & Signals (Phase 1)
    out.push_str(&decision_templates::check_gates_codegen());
    out.push_str(&decision_templates::generate_signal_codegen());

    // Exits (Phase 2)
    out.push_str(&decision_templates::compute_sl_price_codegen());
    out.push_str(&decision_templates::compute_trailing_codegen());
    out.push_str(&decision_templates::check_tp_codegen());
    out.push_str(&decision_templates::check_smart_exits_codegen());
    out.push_str(&decision_templates::check_all_exits_codegen());

    // Sizing & Cooldowns (Phase 3)
    out.push_str(&decision_templates::compute_entry_size_codegen());
    out.push_str(&decision_templates::is_pesc_blocked_codegen());

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_all_decision_contains_header() {
        let source = render_all_decision(None);
        assert!(source.contains("AUTO-GENERATED"));
        assert!(source.contains("#pragma once"));
    }

    #[test]
    fn render_all_decision_embeds_hashes_when_provided() {
        let hashes = r#"{"gates.rs":"abc123"}"#;
        let source = render_all_decision(Some(hashes));
        assert!(source.contains("SOURCE_HASHES:"));
        assert!(source.contains("abc123"));
    }

    #[test]
    fn render_all_decision_no_hashes_when_none() {
        let source = render_all_decision(None);
        assert!(!source.contains("SOURCE_HASHES:"));
    }
}
