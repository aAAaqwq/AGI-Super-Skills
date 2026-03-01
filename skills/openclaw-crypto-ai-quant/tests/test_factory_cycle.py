from __future__ import annotations

import datetime
import json

import pytest

import tools.factory_cycle as factory_cycle
from tools.factory_cycle import (
    _apply_strategy_mode_overlay,
    _build_step5_gate_report,
    _parse_candidate,
    _select_deployable_candidates,
    _stable_promotion_since_s,
)


def _iso(ts: datetime.datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError("tz-aware required")
    return ts.isoformat().replace("+00:00", "Z")


def _write_deploy_event(*, root, stamp: str, service: str, config_id: str, ts_utc: str) -> None:
    ev_dir = root / "deployments" / "paper" / stamp
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev = {
        "ts_utc": ts_utc,
        "what": {"config_id": config_id},
        "restart": {"service": service},
    }
    (ev_dir / "deploy_event.json").write_text(json.dumps(ev), encoding="utf-8")


def test_apply_strategy_mode_overlay_materialises_modes_into_global() -> None:
    base = {
        "global": {"engine": {"interval": "1h", "entry_interval": "3m", "exit_interval": "3m"}},
        "modes": {
            "primary": {
                "global": {"engine": {"interval": "30m", "entry_interval": "5m", "exit_interval": "5m"}},
            }
        },
    }

    eff = _apply_strategy_mode_overlay(base=base, strategy_mode="primary")
    assert eff["global"]["engine"]["interval"] == "30m"
    assert eff["global"]["engine"]["entry_interval"] == "5m"
    assert eff["global"]["engine"]["exit_interval"] == "5m"
    # Preserve the original modes section (useful for operators).
    assert "modes" in eff


def test_apply_strategy_mode_overlay_raises_on_unknown_mode() -> None:
    base = {"global": {"engine": {"interval": "1h"}}, "modes": {"primary": {"global": {"engine": {"interval": "30m"}}}}}
    with pytest.raises(KeyError):
        _apply_strategy_mode_overlay(base=base, strategy_mode="does_not_exist")


def test_stable_promotion_since_tracks_oldest_timestamp_for_contiguous_config_segment(tmp_path) -> None:
    start = datetime.datetime(2026, 2, 10, 0, 0, tzinfo=datetime.timezone.utc)
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T000000Z_cfg",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start),
    )
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T010000Z_cfg",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start + datetime.timedelta(hours=1)),
    )
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T020000Z_cfg",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start + datetime.timedelta(hours=2)),
    )

    since_s = _stable_promotion_since_s(artifacts_dir=tmp_path, service="svc-a", config_id="cfgA")
    assert since_s is not None
    assert since_s == pytest.approx(start.timestamp())


def test_stable_promotion_since_uses_latest_contiguous_segment_after_config_switch(tmp_path) -> None:
    start = datetime.datetime(2026, 2, 10, 0, 0, tzinfo=datetime.timezone.utc)
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T000000Z_cfgA",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start),
    )
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T010000Z_cfgA",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start + datetime.timedelta(hours=1)),
    )
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T020000Z_cfgB",
        service="svc-a",
        config_id="cfgB",
        ts_utc=_iso(start + datetime.timedelta(hours=2)),
    )
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T030000Z_cfgA",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start + datetime.timedelta(hours=3)),
    )
    _write_deploy_event(
        root=tmp_path,
        stamp="20260210T040000Z_cfgA",
        service="svc-a",
        config_id="cfgA",
        ts_utc=_iso(start + datetime.timedelta(hours=4)),
    )

    since_a = _stable_promotion_since_s(artifacts_dir=tmp_path, service="svc-a", config_id="cfgA")
    since_b = _stable_promotion_since_s(artifacts_dir=tmp_path, service="svc-a", config_id="cfgB")
    assert since_a is not None
    assert since_b is not None
    assert since_a == pytest.approx((start + datetime.timedelta(hours=3)).timestamp())
    assert since_b == pytest.approx((start + datetime.timedelta(hours=2)).timestamp())


def test_parse_candidate_legacy_fields_are_backward_compatible() -> None:
    legacy = {
        "config_id": "abc",
        "config_path": "/tmp/candidate.yaml",
        "total_pnl": 1.5,
        "profit_factor": 1.2,
        "total_trades": 2,
    }
    cand = _parse_candidate(legacy)
    assert cand is not None
    assert cand.pipeline_stage == "legacy"
    assert cand.sweep_stage == "legacy"
    assert cand.replay_stage == ""
    assert cand.validation_gate == "replay_only"
    assert cand.canonical_cpu_verified is True
    assert cand.candidate_mode is False
    assert cand.has_stage_metadata is False


def test_select_deployable_candidates_prefers_stage_and_cpu_verified_candidates() -> None:
    candidates = [
        {
            "config_id": "cand_1",
            "config_path": "/tmp/a.yaml",
            "total_pnl": 1.0,
            "total_trades": 1,
            "profit_factor": 1.0,
            "max_drawdown_pct": 0.1,
            "pipeline_stage": "candidate_generation",
            "sweep_stage": "cpu",
            "replay_stage": "",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": False,
            "candidate_mode": True,
        },
        {
            "config_id": "cand_2",
            "config_path": "/tmp/b.yaml",
            "total_pnl": 0.5,
            "total_trades": 1,
            "profit_factor": 1.0,
            "max_drawdown_pct": 0.1,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": True,
            "replay_report_path": "/tmp/replay.json",
            "replay_equivalence_report_path": "/tmp/replay_eq.json",
            "replay_equivalence_status": "pass",
            "replay_equivalence_count": 0,
            "schema_version": 1,
            "candidate_mode": True,
        },
        {
            "config_id": "cand_3",
            "config_path": "/tmp/c.yaml",
            "total_pnl": 2.0,
            "total_trades": 1,
            "profit_factor": 1.0,
            "max_drawdown_pct": 0.1,
            "candidate_mode": False,
        },
    ]
    parsed = [_parse_candidate(c) for c in candidates]
    assert all(p is not None for p in parsed)
    selected = _select_deployable_candidates([p for p in parsed if p is not None], limit=1)
    assert len(selected) == 1
    assert selected[0].config_id == "cand_2"


def test_unverified_staged_candidates_are_not_deployable() -> None:
    candidates = [
        {
            "config_id": "cand_legacy",
            "config_path": "/tmp/a.yaml",
            "total_pnl": 1.0,
            "total_trades": 1,
            "profit_factor": 1.0,
            "max_drawdown_pct": 0.1,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": True,
            "replay_report_path": "/tmp/legacy_replay.json",
            "replay_equivalence_report_path": "/tmp/legacy_replay_eq.json",
            "replay_equivalence_status": "pass",
            "replay_equivalence_count": 0,
            "schema_version": 1,
            "candidate_mode": True,
        },
        {
            "config_id": "cand_unverified",
            "config_path": "/tmp/b.yaml",
            "total_pnl": 10.0,
            "total_trades": 1,
            "profit_factor": 3.0,
            "max_drawdown_pct": 0.1,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": False,
            "replay_report_path": "/tmp/replay.json",
            "replay_equivalence_report_path": "/tmp/replay_eq.json",
            "replay_equivalence_status": "pass",
            "replay_equivalence_count": 0,
            "candidate_mode": True,
        },
    ]
    parsed = [_parse_candidate(c) for c in candidates]
    assert all(p is not None for p in parsed)
    selected = _select_deployable_candidates([p for p in parsed if p is not None], limit=2)
    assert len(selected) == 1
    assert selected[0].config_id == "cand_legacy"


def test_candidate_mode_requires_complete_stage_metadata() -> None:
    candidates = [
        {
            "config_id": "incomplete",
            "config_path": "/tmp/incomplete.yaml",
            "total_pnl": 10.0,
            "total_trades": 2,
            "profit_factor": 1.8,
            "max_drawdown_pct": 0.2,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": True,
            "schema_version": 1,
            "candidate_mode": True,
        },
        {
            "config_id": "complete",
            "config_path": "/tmp/complete.yaml",
            "total_pnl": 9.0,
            "total_trades": 3,
            "profit_factor": 1.7,
            "max_drawdown_pct": 0.2,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": True,
            "replay_report_path": "/tmp/complete_replay.json",
            "replay_equivalence_report_path": "/tmp/complete_replay_equiv.json",
            "replay_equivalence_status": "pass",
            "replay_equivalence_count": 0,
            "schema_version": 1,
            "candidate_mode": True,
        },
    ]
    parsed = [_parse_candidate(c) for c in candidates]
    assert all(p is not None for p in parsed)
    selected = _select_deployable_candidates([p for p in parsed if p is not None], limit=2)
    assert len(selected) == 1
    assert selected[0].config_id == "complete"


def test_require_ssot_evidence_can_be_disabled_for_selection() -> None:
    candidate = {
        "config_id": "legacy_proofless",
        "config_path": "/tmp/legacy_proofless.yaml",
        "total_pnl": 10.0,
        "total_trades": 3,
        "profit_factor": 1.7,
        "max_drawdown_pct": 0.2,
        "pipeline_stage": "candidate_validation",
        "sweep_stage": "gpu",
        "replay_stage": "cpu_replay",
        "validation_gate": "replay_only",
        "canonical_cpu_verified": True,
        "schema_version": 1,
        "candidate_mode": True,
    }
    parsed = _parse_candidate(candidate)
    assert parsed is not None
    selected = _select_deployable_candidates([parsed], limit=1, require_ssot_evidence=False)
    assert len(selected) == 1
    assert selected[0].config_id == "legacy_proofless"


def test_build_step5_gate_report_tracks_block_reasons() -> None:
    blocked = _parse_candidate(
        {
            "config_id": "blocked_cfg",
            "config_path": "/tmp/blocked.yaml",
            "total_pnl": 1.0,
            "total_trades": 1,
            "profit_factor": 1.1,
            "max_drawdown_pct": 0.2,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": True,
            "candidate_mode": True,
            "schema_version": 1,
            "replay_report_path": "/tmp/blocked.replay.json",
            "replay_equivalence_report_path": "/tmp/blocked.replay_eq.json",
            "replay_equivalence_status": "baseline_stale",
            "replay_equivalence_count": 0,
        }
    )
    deployable = _parse_candidate(
        {
            "config_id": "ok_cfg",
            "config_path": "/tmp/ok.yaml",
            "total_pnl": 2.0,
            "total_trades": 2,
            "profit_factor": 1.4,
            "max_drawdown_pct": 0.1,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": True,
            "candidate_mode": True,
            "schema_version": 1,
            "replay_report_path": "/tmp/ok.replay.json",
            "replay_equivalence_report_path": "/tmp/ok.replay_eq.json",
            "replay_equivalence_status": "pass",
            "replay_equivalence_count": 0,
        }
    )
    assert blocked is not None
    assert deployable is not None

    report = _build_step5_gate_report(
        run_id="run_test",
        parsed=[blocked, deployable],
        require_ssot_evidence=True,
        selection_policy="deployable_rank_v1",
        deployable_selected=[deployable],
        deployable_by_slot={1: deployable},
        deploy_targets=[factory_cycle.DeployTarget(slot=1, service="svc", yaml_path=factory_cycle.Path("/tmp/a.yaml"))],
        selection_warnings=[],
        blocked_reason="",
    )

    assert report["blocked"] is False
    assert report["deployable_count"] == 1
    assert report["blocked_reasons_count"]["replay_equivalence_baseline_stale"] == 1


def test_pid_environ_filters_secret_like_keys(monkeypatch) -> None:
    proc_env_path = "/proc/4242/environ"
    raw_env = (
        b"AI_QUANT_DISCORD_CHANNEL=12345\x00"
        b"AI_QUANT_DISCORD_LABEL=paper\x00"
        b"SAFE_FLAG=1\x00"
        b"API_KEY=super-secret\x00"
        b"DB_SECRET=hidden\x00"
        b"MONITOR_TOKEN=hidden\x00"
        b"ADMIN_PASSWORD=hidden\x00"
    )

    real_exists = factory_cycle.Path.exists
    real_read_bytes = factory_cycle.Path.read_bytes

    def _fake_exists(self) -> bool:  # noqa: ANN001
        if self.as_posix() == proc_env_path:
            return True
        return bool(real_exists(self))

    def _fake_read_bytes(self) -> bytes:  # noqa: ANN001
        if self.as_posix() == proc_env_path:
            return raw_env
        return bytes(real_read_bytes(self))

    monkeypatch.setattr(factory_cycle.Path, "exists", _fake_exists)
    monkeypatch.setattr(factory_cycle.Path, "read_bytes", _fake_read_bytes)

    env = factory_cycle._pid_environ(4242)

    assert env["AI_QUANT_DISCORD_CHANNEL"] == "12345"
    assert env["AI_QUANT_DISCORD_LABEL"] == "paper"
    assert env["SAFE_FLAG"] == "1"
    assert "API_KEY" not in env
    assert "DB_SECRET" not in env
    assert "MONITOR_TOKEN" not in env
    assert "ADMIN_PASSWORD" not in env


def test_service_environment_filters_secret_like_keys(monkeypatch) -> None:
    monkeypatch.setattr(
        factory_cycle,
        "_systemctl_show_value",
        lambda *, service, prop: (  # noqa: ARG005
            "SAFE_ENV=ok AI_QUANT_DISCORD_CHANNEL=12345 API_KEY=secret "
            "DB_SECRET=secret MONITOR_TOKEN=secret ADMIN_PASSWORD=secret"
        ),
    )

    env = factory_cycle._service_environment("openclaw-ai-quant-trader")

    assert env["SAFE_ENV"] == "ok"
    assert env["AI_QUANT_DISCORD_CHANNEL"] == "12345"
    assert "API_KEY" not in env
    assert "DB_SECRET" not in env
    assert "MONITOR_TOKEN" not in env
    assert "ADMIN_PASSWORD" not in env


def test_factory_cycle_writes_step5_reports_when_blocked(monkeypatch, tmp_path) -> None:
    run_id = "run_blocked_case"
    run_dir = tmp_path / "2026-02-24" / f"run_{run_id}"
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "configs").mkdir(parents=True, exist_ok=True)
    (run_dir / "replays").mkdir(parents=True, exist_ok=True)
    (run_dir / "run_metadata.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

    items = [
        {
            "config_id": "blocked_cfg",
            "config_path": str(run_dir / "configs" / "blocked.yaml"),
            "total_pnl": 1.0,
            "total_trades": 1,
            "profit_factor": 1.0,
            "max_drawdown_pct": 0.2,
            "pipeline_stage": "candidate_validation",
            "sweep_stage": "gpu",
            "replay_stage": "cpu_replay",
            "validation_gate": "replay_only",
            "canonical_cpu_verified": False,
            "candidate_mode": True,
            "schema_version": 1,
            "replay_report_path": str(run_dir / "replays" / "blocked.replay.json"),
            "replay_equivalence_report_path": str(run_dir / "replays" / "blocked.replay_eq.json"),
            "replay_equivalence_status": "baseline_stale",
            "replay_equivalence_count": 0,
            "rejected": False,
        }
    ]
    (reports_dir / "report.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    (reports_dir / "report.md").write_text("# report\n", encoding="utf-8")

    base_cfg = tmp_path / "base.yaml"
    base_cfg.write_text("global:\n  engine:\n    interval: 30m\n", encoding="utf-8")
    target_yaml = tmp_path / "target.yaml"
    target_yaml.write_text("global:\n  engine:\n    interval: 30m\n", encoding="utf-8")

    monkeypatch.setattr(factory_cycle.factory_run, "main", lambda argv=None: 0)
    monkeypatch.setattr(factory_cycle, "_query_run_dir", lambda *, registry_db, run_id: run_dir)
    monkeypatch.setattr(factory_cycle, "_send_discord", lambda **kwargs: None)
    monkeypatch.setattr(factory_cycle, "_send_discord_chunks", lambda **kwargs: None)

    rc = factory_cycle.main(
        [
            "--run-id",
            run_id,
            "--artifacts-dir",
            str(tmp_path),
            "--config",
            str(base_cfg),
            "--service",
            "svc-test",
            "--yaml-path",
            str(target_yaml),
            "--candidate-services",
            "svc-test",
            "--candidate-yaml-paths",
            str(target_yaml),
            "--candidate-count",
            "1",
            "--discord-target",
            "",
        ]
    )

    assert rc == 0
    selection_path = reports_dir / "selection.json"
    step5_json = reports_dir / "step5_gate_report.json"
    step5_md = reports_dir / "step5_gate_report.md"
    assert selection_path.is_file()
    assert step5_json.is_file()
    assert step5_md.is_file()

    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    assert selection["selection_stage"] == "blocked"
    assert selection["deploy_stage"] == "blocked"
    assert selection["promotion_stage"] == "skipped"
    assert selection["step5_gate_status"] == "blocked"
