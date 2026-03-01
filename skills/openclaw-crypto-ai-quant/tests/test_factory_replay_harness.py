from __future__ import annotations

import json
import factory_run

from pathlib import Path

import pytest

from factory_run import _run_replay_equivalence_check


TRACE = {
    "decision_diagnostics": [
        {
            "event_id": 1,
            "source": "fixture",
            "timestamp_ms": 1700000000000,
            "symbol": "ETH",
            "signal": "BUY",
            "requested_notional_usd": 1000.0,
            "schema_version": 1,
            "intents": [],
            "fills": [],
            "warnings": [],
            "errors": [],
            "applied_to_kernel_state": True,
        }
    ]
}


def _write_trace(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _force_mode(monkeypatch, mode: str) -> None:
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_MODE", mode)


def test_factory_run_replay_equivalence_happy_path(monkeypatch, tmp_path) -> None:
    baseline = tmp_path / "baseline.json"
    replay = tmp_path / "replay.json"
    _write_trace(baseline, TRACE)
    _write_trace(replay, TRACE)

    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", str(baseline))
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", "1")
    _force_mode(monkeypatch, "backtest")

    summary: dict = {}
    ok = _run_replay_equivalence_check(right_report=replay, summary=summary)

    assert ok
    assert summary["replay_equivalence_status"] == "pass"
    assert summary["replay_equivalence_mode"] == "backtest"
    assert summary["replay_equivalence_failure_code"] == ""
    assert summary["replay_equivalence_report_path"] != ""

    report_path = Path(summary["replay_equivalence_report_path"])
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["mode"] == "backtest"


def test_factory_run_replay_equivalence_detects_mismatch_when_strict(monkeypatch, tmp_path) -> None:
    baseline = tmp_path / "baseline.json"
    replay = tmp_path / "replay.json"
    changed = json.loads(json.dumps(TRACE))
    changed["decision_diagnostics"][0]["event_id"] = 2

    _write_trace(baseline, TRACE)
    _write_trace(replay, changed)

    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", str(baseline))
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", "1")
    _force_mode(monkeypatch, "backtest")

    summary: dict = {}
    ok = _run_replay_equivalence_check(right_report=replay, summary=summary)

    assert not ok
    assert summary["replay_equivalence_status"] == "fail"
    assert summary["replay_equivalence_mode"] == "backtest"
    assert summary["replay_equivalence_count"] >= 1
    assert summary["replay_equivalence_failure_code"] == "mismatch"


def test_factory_run_replay_equivalence_runs_as_warning_when_not_strict(monkeypatch, tmp_path) -> None:
    baseline = tmp_path / "baseline.json"
    replay = tmp_path / "replay.json"
    changed = json.loads(json.dumps(TRACE))
    changed["decision_diagnostics"][0]["event_id"] = 3

    _write_trace(baseline, TRACE)
    _write_trace(replay, changed)

    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", str(baseline))
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", "0")
    _force_mode(monkeypatch, "backtest")

    summary: dict = {}
    ok = _run_replay_equivalence_check(right_report=replay, summary=summary)

    assert ok
    assert summary["replay_equivalence_status"] == "fail"
    assert summary["replay_equivalence_mode"] == "backtest"
    assert summary["replay_equivalence_failure_code"] == "mismatch"


def test_factory_run_replay_equivalence_not_run_without_baseline(monkeypatch, tmp_path) -> None:
    replay = tmp_path / "replay.json"
    _write_trace(replay, TRACE)

    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", raising=False)
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", "0")
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_LIVE_BASELINE", raising=False)
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_PAPER_BASELINE", raising=False)
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_BACKTEST_BASELINE", raising=False)
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_BACKTEST_STRICT", raising=False)
    _force_mode(monkeypatch, "backtest")

    summary: dict = {}
    ok = _run_replay_equivalence_check(right_report=replay, summary=summary)

    assert ok
    assert summary["replay_equivalence_status"] == "not_run"
    assert summary["replay_equivalence_count"] == 0
    assert summary["replay_equivalence_mode"] == "backtest"
    assert summary["replay_equivalence_diffs"] == []
    assert summary["replay_equivalence_failure_code"] == "not_run"


def test_factory_run_replay_equivalence_missing_baseline_fails_in_strict_mode(monkeypatch, tmp_path) -> None:
    baseline = tmp_path / "missing.json"
    replay = tmp_path / "replay.json"
    _write_trace(replay, TRACE)

    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", str(baseline))
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", "1")
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_AUTO_SEED", "0")
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_LIVE_BASELINE", raising=False)
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_PAPER_BASELINE", raising=False)
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_BACKTEST_BASELINE", raising=False)
    monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_BACKTEST_STRICT", raising=False)
    _force_mode(monkeypatch, "backtest")

    summary: dict = {}
    ok = _run_replay_equivalence_check(right_report=replay, summary=summary)

    assert not ok
    assert summary["replay_equivalence_status"] == "missing_baseline"
    assert summary["replay_equivalence_count"] == 0
    assert summary["replay_equivalence_mode"] == "backtest"
    assert summary["replay_equivalence_failure_code"] == "missing_baseline"


@pytest.mark.parametrize(
    ("mode", "mode_baseline", "mode_strict", "global_strict", "strict_result"),
    [
        ("live", True, "1", "0", False),
        ("paper", True, "0", "1", True),
        ("backtest", False, None, "1", False),
        ("backtest", False, None, "0", True),
    ],
)
def test_factory_run_replay_equivalence_mode_specific_strictness_matrix(
    monkeypatch,
    tmp_path,
    mode: str,
    mode_baseline: bool,
    mode_strict: str | None,
    global_strict: str,
    strict_result: bool,
) -> None:
    baseline = tmp_path / "baseline.json"
    replay = tmp_path / "replay.json"
    changed = json.loads(json.dumps(TRACE))
    changed["decision_diagnostics"][0]["event_id"] = 4

    _write_trace(baseline, TRACE)
    _write_trace(replay, changed)

    if mode_baseline:
        monkeypatch.setenv(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_BASELINE", str(baseline))
        monkeypatch.delenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", raising=False)
    else:
        monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE", str(baseline))
        monkeypatch.delenv(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_BASELINE", raising=False)

    if mode_strict is None:
        monkeypatch.delenv(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_STRICT", raising=False)
    else:
        monkeypatch.setenv(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_STRICT", mode_strict)

    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", global_strict)

    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_MODE", mode)

    summary: dict = {}
    ok = _run_replay_equivalence_check(right_report=replay, summary=summary)

    assert ok is strict_result
    assert summary["replay_equivalence_mode"] == mode
    assert summary["replay_equivalence_status"] == "fail"
    assert summary["replay_equivalence_failure_code"] == "mismatch"


def _write_run_metadata(
    *,
    run_dir: Path,
    candidate_id: str,
    config_path: str,
    replay_report: str,
    run_id: str = "baseline-run",
    generated_at_ms: int = 0,
    contract_fingerprint: str = "",
    candidate_extra: dict | None = None,
    artifacts_root: str = "",
) -> None:
    (run_dir / "replays").mkdir(parents=True, exist_ok=True)
    (run_dir / "replays" / replay_report).write_text("{}\n", encoding="utf-8")
    candidate = {
        "config_id": candidate_id,
        "path": str(config_path),
        "replay_report_path": str(run_dir / "replays" / replay_report),
        "pipeline_stage": "candidate_validation",
        "sweep_stage": "gpu",
        "replay_stage": "cpu_replay",
        "validation_gate": "replay_only",
        "canonical_cpu_verified": True,
        "candidate_mode": True,
    }
    if isinstance(candidate_extra, dict):
        candidate.update(candidate_extra)
    run_meta = {
        "run_id": str(run_id),
        "candidate_configs": [candidate],
    }
    if generated_at_ms > 0:
        run_meta["generated_at_ms"] = int(generated_at_ms)
    if contract_fingerprint:
        run_meta["replay_equivalence_contract"] = {
            "schema_version": 1,
            "mode": "backtest",
            "fingerprint": str(contract_fingerprint),
            "payload": {},
        }
    if artifacts_root:
        run_meta["repro"] = {"artifacts_root": str(artifacts_root)}
    (run_dir / "run_metadata.json").write_text(json.dumps(run_meta), encoding="utf-8")


def test_factory_run_resolve_baseline_aligns_to_candidate_run_metadata(tmp_path: Path) -> None:
    baseline_run = tmp_path / "baseline_run"
    right_run = tmp_path / "right_run"
    baseline_run.mkdir()
    right_run.mkdir()

    _write_run_metadata(
        run_dir=baseline_run,
        candidate_id="cfg-alpha",
        config_path=str(tmp_path / "candidate_alpha.yaml"),
        replay_report="candidate_alpha.replay.json",
    )
    (tmp_path / "candidate_alpha.yaml").write_text("candidate: alpha\n", encoding="utf-8")

    right_report = right_run / "candidate_alpha.replay.json"
    right_report.write_text("{}", encoding="utf-8")

    baseline = factory_run._resolve_replay_equivalence_baseline_path(
        "backtest",
        baseline_path=baseline_run / "replays" / "candidate_alpha.replay.json",
        right_report=right_report,
        summary={"config_id": "cfg-alpha", "config_path": str(tmp_path / "candidate_alpha.yaml")},
    )
    assert baseline == (baseline_run / "replays" / "candidate_alpha.replay.json")


def test_factory_run_resolve_baseline_aligns_by_filename_fallback(tmp_path: Path) -> None:
    raw_dir = tmp_path / "baseline_dir"
    raw_dir.mkdir()
    baseline_dir = raw_dir / "replays"
    baseline_dir.mkdir()

    (baseline_dir / "candidate_alpha.replay.json").write_text("{}", encoding="utf-8")
    (baseline_dir / "candidate_beta.replay.json").write_text("{}", encoding="utf-8")

    right_report = tmp_path / "candidate_beta.replay.json"
    right_report.write_text("{}", encoding="utf-8")

    resolved = factory_run._resolve_replay_equivalence_baseline_path(
        "backtest",
        baseline_path=baseline_dir / "candidate_alpha.replay.json",
        right_report=right_report,
        summary={"config_id": "unknown", "config_path": "/tmp/missing.yaml"},
    )
    assert resolved == baseline_dir / "candidate_beta.replay.json"


def test_factory_run_resolve_baseline_run_dir_uses_metadata_match(tmp_path: Path) -> None:
    baseline_run = tmp_path / "baseline_run"
    right_dir = tmp_path / "right"
    baseline_run.mkdir()
    right_dir.mkdir()

    _write_run_metadata(
        run_dir=baseline_run,
        candidate_id="cfg-beta",
        config_path=str(tmp_path / "candidate_beta.yaml"),
        replay_report="candidate_beta.replay.json",
    )
    (baseline_run / "replays" / "candidate_beta.replay.json").write_text("{}", encoding="utf-8")
    right_report = right_dir / "candidate_beta.replay.json"
    right_report.write_text("{}", encoding="utf-8")

    (tmp_path / "candidate_beta.yaml").write_text("candidate: beta\n", encoding="utf-8")

    resolved = factory_run._resolve_replay_equivalence_baseline_path(
        "backtest",
        baseline_path=baseline_run,
        right_report=right_report,
        summary={"config_id": "cfg-beta", "config_path": str(tmp_path / "candidate_beta.yaml")},
    )
    assert resolved == baseline_run / "replays" / "candidate_beta.replay.json"


def test_factory_run_resolve_baseline_prefers_mode_rank_identity(tmp_path: Path) -> None:
    baseline_run = tmp_path / "baseline_run"
    right_dir = tmp_path / "right"
    baseline_run.mkdir()
    right_dir.mkdir()
    (baseline_run / "replays").mkdir(parents=True, exist_ok=True)

    rows = [
        {
            "config_id": "cfg-growth-r1",
            "path": str(tmp_path / "candidate_growth_rank1.yaml"),
            "replay_report_path": str(baseline_run / "replays" / "candidate_growth_rank1.replay.json"),
            "sort_by": "growth",
            "rank": 1,
            "candidate_mode": True,
        },
        {
            "config_id": "cfg-growth-r2",
            "path": str(tmp_path / "candidate_growth_rank2.yaml"),
            "replay_report_path": str(baseline_run / "replays" / "candidate_growth_rank2.replay.json"),
            "sort_by": "growth",
            "rank": 2,
            "candidate_mode": True,
        },
    ]
    (baseline_run / "replays" / "candidate_growth_rank1.replay.json").write_text("{}", encoding="utf-8")
    (baseline_run / "replays" / "candidate_growth_rank2.replay.json").write_text("{}", encoding="utf-8")
    (baseline_run / "run_metadata.json").write_text(
        json.dumps({"run_id": "baseline", "candidate_configs": rows}), encoding="utf-8"
    )

    right_report = right_dir / "candidate_growth_rank2.replay.json"
    right_report.write_text("{}", encoding="utf-8")

    resolved = factory_run._resolve_replay_equivalence_baseline_path(
        "backtest",
        baseline_path=baseline_run,
        right_report=right_report,
        summary={"config_id": "", "config_path": "", "sort_by": "growth", "rank": 2},
    )
    assert resolved == baseline_run / "replays" / "candidate_growth_rank2.replay.json"


def test_factory_run_replay_equivalence_auto_fallback_recovers_stale_pinned_baseline(
    monkeypatch, tmp_path: Path
) -> None:
    artifacts_root = tmp_path / "artifacts"
    stale_run = artifacts_root / "2026-02-20" / "run_stale"
    good_run = artifacts_root / "2026-02-23" / "run_good"
    current_run = artifacts_root / "2026-02-24" / "run_current"
    stale_run.mkdir(parents=True, exist_ok=True)
    good_run.mkdir(parents=True, exist_ok=True)
    current_run.mkdir(parents=True, exist_ok=True)

    cfg_path = tmp_path / "candidate_alpha.yaml"
    cfg_path.write_text("candidate: alpha\n", encoding="utf-8")
    cfg_sha = factory_run._sha256_file_optional(cfg_path)

    _write_run_metadata(
        run_dir=stale_run,
        candidate_id="cfg-alpha",
        config_path=str(cfg_path),
        replay_report="candidate_alpha.replay.json",
        run_id="stale",
        generated_at_ms=1700000000000,
        contract_fingerprint="stale-contract-fp",
        candidate_extra={"sort_by": "growth", "rank": 1, "config_sha256": cfg_sha},
    )
    _write_trace(stale_run / "replays" / "candidate_alpha.replay.json", TRACE)
    (stale_run / "replay_equivalence_baseline_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at_ms": 1700000000000,
                "run_id": "stale",
                "run_dir": str(stale_run),
                "contract": {
                    "schema_version": 1,
                    "mode": "backtest",
                    "fingerprint": "stale-contract-fp",
                    "payload": {},
                },
                "candidate_count": 1,
                "seed_mode_count": 0,
                "candidates": [
                    {
                        "config_id": "cfg-alpha",
                        "replay_report_path": str(stale_run / "replays" / "candidate_alpha.replay.json"),
                        "config_sha256": cfg_sha,
                        "sort_by": "growth",
                        "rank": 1,
                        "seed_mode": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _write_run_metadata(
        run_dir=good_run,
        candidate_id="cfg-alpha",
        config_path=str(cfg_path),
        replay_report="candidate_alpha.replay.json",
        run_id="good",
        generated_at_ms=1700100000000,
        contract_fingerprint="current-contract-fp",
        candidate_extra={"sort_by": "growth", "rank": 1, "config_sha256": cfg_sha},
    )
    _write_trace(good_run / "replays" / "candidate_alpha.replay.json", TRACE)
    (good_run / "replay_equivalence_baseline_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at_ms": 1700100000000,
                "run_id": "good",
                "run_dir": str(good_run),
                "contract": {
                    "schema_version": 1,
                    "mode": "backtest",
                    "fingerprint": "current-contract-fp",
                    "payload": {},
                },
                "candidate_count": 1,
                "seed_mode_count": 0,
                "candidates": [
                    {
                        "config_id": "cfg-alpha",
                        "replay_report_path": str(good_run / "replays" / "candidate_alpha.replay.json"),
                        "config_sha256": cfg_sha,
                        "sort_by": "growth",
                        "rank": 1,
                        "seed_mode": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _write_run_metadata(
        run_dir=current_run,
        candidate_id="cfg-alpha",
        config_path=str(cfg_path),
        replay_report="candidate_alpha.replay.json",
        run_id="current",
        generated_at_ms=1700200000000,
        contract_fingerprint="current-contract-fp",
        candidate_extra={"sort_by": "growth", "rank": 1, "config_sha256": cfg_sha},
        artifacts_root=str(artifacts_root),
    )
    right_report = current_run / "replays" / "candidate_alpha.replay.json"
    _write_trace(right_report, TRACE)

    monkeypatch.setenv(
        "AI_QUANT_REPLAY_EQUIVALENCE_BASELINE",
        str(stale_run / "replays" / "candidate_alpha.replay.json"),
    )
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", "1")
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_BASELINE_POLICY", "pinned_or_auto")
    monkeypatch.setenv("AI_QUANT_REPLAY_EQUIVALENCE_AUTO_FALLBACK", "1")
    _force_mode(monkeypatch, "backtest")

    summary: dict = {
        "config_id": "cfg-alpha",
        "config_path": str(cfg_path),
        "config_sha256": cfg_sha,
        "sort_by": "growth",
        "rank": 1,
    }
    ok = _run_replay_equivalence_check(
        right_report=right_report,
        summary=summary,
        current_contract={"schema_version": 1, "mode": "backtest", "fingerprint": "current-contract-fp", "payload": {}},
    )

    assert ok
    assert summary["replay_equivalence_status"] == "pass"
    assert summary["replay_equivalence_baseline_source"] == "auto_fallback"
    assert summary["replay_equivalence_baseline_path"] == str(good_run / "replays" / "candidate_alpha.replay.json")
