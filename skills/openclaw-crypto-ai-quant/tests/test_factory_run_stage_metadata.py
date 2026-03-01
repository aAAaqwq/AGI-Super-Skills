from __future__ import annotations

import argparse

import factory_run


def test_sweep_output_mode_uses_candidate_for_gpu_and_tpe() -> None:
    args = argparse.Namespace(gpu=True, tpe=False)
    assert factory_run._sweep_output_mode_from_args(args) == "candidate"

    args_tpe = argparse.Namespace(gpu=False, tpe=True)
    assert factory_run._sweep_output_mode_from_args(args_tpe) == "candidate"


def test_sweep_output_mode_defaults_to_full_for_cpu() -> None:
    args = argparse.Namespace(gpu=False, tpe=False)
    assert factory_run._sweep_output_mode_from_args(args) == "full"


def test_replay_metadata_attachment_records_validation_stage() -> None:
    args = argparse.Namespace(gpu=True, tpe=False, walk_forward=True, slippage_stress=False)
    summary: dict[str, object] = {
        "replay_equivalence_status": "pass",
        "replay_equivalence_mode": "backtest",
        "replay_equivalence_failure_code": "",
        "replay_equivalence_count": 1,
        "replay_equivalence_error": "",
        "replay_equivalence_report_path": "/tmp/replay_equivalence.json",
        "replay_equivalence_diffs": [],
        "path": "/tmp/replay.json",
        "config_path": "/tmp/cfg.yaml",
    }
    entry: dict[str, object] = {}
    factory_run._attach_replay_metadata(summary=summary, entry=entry, args=args, replay_stage="cpu_replay")

    assert summary["pipeline_stage"] == "candidate_validation"
    assert summary["sweep_stage"] == "gpu"
    assert summary["replay_stage"] == "cpu_replay"
    assert summary["canonical_cpu_verified"] is True
    assert summary["replay_report_path"] == "/tmp/replay.json"
    assert summary["config_path"] == "/tmp/cfg.yaml"
    assert summary["replay_equivalence_report_path"] == "/tmp/replay_equivalence.json"
    assert summary["replay_equivalence_mode"] == "backtest"
    assert summary["replay_equivalence_count"] == 1
    assert summary["replay_equivalence_failure_code"] == ""
    assert entry["replay_equivalence_error"] == ""
    assert entry["replay_equivalence_diffs"] == []
    assert summary["schema_version"] == 1
    assert entry["schema_version"] == 1
    assert entry["pipeline_stage"] == "candidate_validation"
    assert entry["sweep_stage"] == "gpu"
    assert entry["replay_stage"] == "cpu_replay"
    assert entry["canonical_cpu_verified"] is True


def test_replay_metadata_attachment_marks_unverified_when_not_pass() -> None:
    args = argparse.Namespace(gpu=True, tpe=False, walk_forward=True, slippage_stress=False)
    summary: dict[str, object] = {
        "replay_equivalence_status": "fail",
        "replay_equivalence_mode": "live",
        "replay_equivalence_failure_code": "mismatch",
        "replay_equivalence_count": 2,
    }
    entry: dict[str, object] = {}
    factory_run._attach_replay_metadata(summary=summary, entry=entry, args=args, replay_stage="cpu_replay")

    assert summary["canonical_cpu_verified"] is False
    assert entry["canonical_cpu_verified"] is False
    assert entry["replay_equivalence_mode"] == "live"
    assert entry["replay_equivalence_failure_code"] == "mismatch"
    assert summary.get("schema_version", 1) == 1


def test_replay_metadata_attachment_preserves_candidate_mode() -> None:
    args = argparse.Namespace(gpu=True, tpe=False, walk_forward=False, slippage_stress=False)
    summary: dict[str, object] = {
        "replay_equivalence_status": "pass",
        "replay_equivalence_mode": "backtest",
    }
    entry: dict[str, object] = {"candidate_mode": True}

    factory_run._attach_replay_metadata(summary=summary, entry=entry, args=args, replay_stage="cpu_replay")

    assert summary["candidate_mode"] is True
    assert entry["candidate_mode"] is True
