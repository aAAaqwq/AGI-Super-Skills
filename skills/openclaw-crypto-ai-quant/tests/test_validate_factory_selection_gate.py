from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_factory_selection_gate import _run, validate_selection_path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _base_payload(tmp_path: Path, *, stage: str = "smoke", config_id: str = "cfg-001") -> dict[str, object]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    evidence_bundle = {
        "run_dir": str(run_dir),
        "run_metadata_json": str(run_dir / "run_metadata.json"),
        "selection_json": str(run_dir / "selection.json"),
        "report_json": str(run_dir / "report.json"),
        "report_md": str(run_dir / "report.md"),
        "selection_md": str(run_dir / "selection.md"),
    }
    for key, path in evidence_bundle.items():
        if key == "run_dir":
            continue
        Path(path).write_text("{}", encoding="utf-8")

    run_metadata = {"candidate_configs": [{"config_id": config_id, "canonical_cpu_verified": True}]}
    _write_json(run_dir / "run_metadata.json", run_metadata)

    selected = {
        "config_id": config_id,
        "pipeline_stage": "candidate_validation",
        "sweep_stage": "gpu",
        "replay_stage": "cpu_replay",
        "validation_gate": "replay_only",
        "candidate_mode": True,
        "schema_version": 1,
        "canonical_cpu_verified": True,
        "replay_report_path": str(run_dir / "replay.json"),
        "replay_equivalence_report_path": str(run_dir / "replay_equivalence.json"),
        "replay_equivalence_status": "pass",
        "replay_equivalence_count": 0,
    }
    _write_json(run_dir / "replay.json", {"decision_diagnostics": []})
    _write_json(run_dir / "replay_equivalence.json", {"ok": True})

    deploy_stage = "pending" if stage == "real" else "no_deploy"
    promotion_stage = "pending" if stage == "real" else "skipped"

    return {
        "selection_stage": "selected",
        "deploy_stage": deploy_stage,
        "promotion_stage": promotion_stage,
        "evidence_bundle_paths": evidence_bundle,
        "selected": selected,
    }


def test_validate_selection_path_accepts_valid_payload_for_smoke_stage(tmp_path: Path) -> None:
    selection_path = tmp_path / "selection.json"
    _write_json(selection_path, _base_payload(tmp_path, stage="smoke"))
    assert validate_selection_path(selection_path, stage="smoke") == []


@pytest.mark.parametrize("stage, deploy_stage, promotion_stage", [("dry", "pending", "pending"), ("smoke", "pending", "pending")])
def test_validate_selection_path_flags_stage_mismatch_for_non_live_stages(
    tmp_path: Path, stage: str, deploy_stage: str, promotion_stage: str
) -> None:
    selection = _base_payload(tmp_path, stage=stage)
    selection["deploy_stage"] = deploy_stage
    selection["promotion_stage"] = promotion_stage
    selection_path = tmp_path / "selection.json"
    _write_json(selection_path, selection)

    errors = validate_selection_path(selection_path, stage=stage)
    assert any("dry/smoke stage must be no_deploy or skipped" in err for err in errors)
    assert any("dry/smoke stage must be skipped by default" in err for err in errors)


def test_validate_selection_path_rejects_non_verified_candidate(tmp_path: Path) -> None:
    payload = _base_payload(tmp_path, stage="real")
    payload["selected"]["canonical_cpu_verified"] = False
    payload["deploy_stage"] = "pending"
    payload["promotion_stage"] = "pending"
    payload["selected"]["replay_equivalence_status"] = "fail"
    payload["selected"]["replay_equivalence_count"] = 2
    payload["selected"]["replay_equivalence_diffs"] = ["a", "b"]
    _write_json(tmp_path / "selection.json", payload)

    errors = validate_selection_path(tmp_path / "selection.json", stage="real")
    assert any("not canonical_cpu_verified" in err for err in errors)
    assert any("replay_equivalence_status is not pass" in err for err in errors)


def test_validate_selection_path_rejects_legacy_candidate_mode(tmp_path: Path) -> None:
    payload = _base_payload(tmp_path, stage="real")
    payload["selected"]["candidate_mode"] = False
    payload["deploy_stage"] = "pending"
    payload["promotion_stage"] = "pending"
    _write_json(tmp_path / "selection.json", payload)

    errors = validate_selection_path(tmp_path / "selection.json", stage="real")
    assert any("selected candidate is not candidate_mode=true" in err for err in errors)


def test_validate_selection_path_rejects_missing_replay_proof_fields(tmp_path: Path) -> None:
    payload = _base_payload(tmp_path, stage="smoke")
    del payload["selected"]["replay_equivalence_report_path"]
    _write_json(tmp_path / "selection.json", payload)

    errors = validate_selection_path(tmp_path / "selection.json", stage="smoke")
    assert any("selected candidate missing required key: replay_equivalence_report_path" in err for err in errors)


def test_validate_selection_path_rejects_report_path_mismatch_with_run_metadata(tmp_path: Path) -> None:
    payload = _base_payload(tmp_path, stage="smoke")
    run_dir = Path(payload["evidence_bundle_paths"]["run_dir"])  # type: ignore[assignment]
    run_metadata = {
        "candidate_configs": [
            {
                "config_id": payload["selected"]["config_id"],
                "canonical_cpu_verified": True,
                "replay_report_path": str(run_dir / "replay_candidate_a.json"),
                "replay_equivalence_report_path": str(run_dir / "replay_equivalence_candidate_a.json"),
            }
        ]
    }
    _write_json(run_dir / "run_metadata.json", run_metadata)
    _write_json(run_dir / "replay_candidate_a.json", {"decision_diagnostics": []})
    _write_json(run_dir / "replay_equivalence_candidate_a.json", {"ok": True})

    _write_json(tmp_path / "selection.json", payload)
    errors = validate_selection_path(tmp_path / "selection.json", stage="smoke")
    assert any("selected replay_report_path does not match run_metadata candidate metadata" in err for err in errors)
    assert any("selected replay_equivalence_report_path does not match run_metadata candidate metadata" in err for err in errors)


def test_validate_selection_path_allows_legacy_mode(tmp_path: Path) -> None:
    payload = _base_payload(tmp_path, stage="real")
    payload = {
        "selection_stage": "selected",
        "deploy_stage": "pending",
        "promotion_stage": "pending",
        "selected": payload["selected"],
        "evidence_bundle_paths": payload["evidence_bundle_paths"],
    }
    path = tmp_path / "selection.json"
    _write_json(path, payload)

    assert validate_selection_path(path, stage="real", allow_legacy=True) == []


def test_run_writes_summary_json_on_success(tmp_path: Path) -> None:
    path = tmp_path / "selection.json"
    _write_json(path, _base_payload(tmp_path, stage="smoke"))
    summary = tmp_path / "selection_summary.json"

    rc = _run(
        [
            "--selection-json",
            str(path),
            "--stage",
            "smoke",
            "--summary-json",
            str(summary),
        ]
    )

    assert rc == 0
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["status"] == "pass"
    assert data["selection_stage"] == "selected"
    assert data["selected"]["canonical_cpu_verified"] is True


def test_run_writes_summary_json_on_failure(tmp_path: Path) -> None:
    path = tmp_path / "selection.json"
    payload = _base_payload(tmp_path, stage="real")
    payload["selected"]["canonical_cpu_verified"] = False
    payload["selected"]["replay_equivalence_status"] = "fail"
    _write_json(path, payload)
    summary = tmp_path / "selection_summary_fail.json"

    rc = _run(
        [
            "--selection-json",
            str(path),
            "--stage",
            "real",
            "--summary-json",
            str(summary),
        ]
    )

    assert rc != 0
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["status"] == "fail"
    assert data["errors"]
    assert any("canonical_cpu_verified" in item for item in data["errors"])
