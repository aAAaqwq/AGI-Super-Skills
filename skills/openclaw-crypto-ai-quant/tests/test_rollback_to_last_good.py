import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import tools.rollback_to_last_good as rollback_tool
from tools.rollback_to_last_good import rollback_to_last_good


VALID_YAML = (
    "global:\n"
    "  trade:\n"
    "    allocation_pct: 0.20\n"
    "    leverage: 3.0\n"
    "    leverage_low: 2.0\n"
    "    leverage_medium: 3.0\n"
    "    leverage_high: 4.0\n"
    "    sl_atr_mult: 2.0\n"
    "    tp_atr_mult: 6.0\n"
    "    slippage_bps: 10.0\n"
    "    max_open_positions: 20\n"
    "    max_entry_orders_per_loop: 4\n"
    "    max_total_margin_pct: 0.60\n"
    "    min_notional_usd: 10.0\n"
    "    min_atr_pct: 0.003\n"
    "    bump_to_min_notional: true\n"
    "  indicators:\n"
    "    adx_window: 14\n"
    "    ema_fast_window: 20\n"
    "    ema_slow_window: 50\n"
    "    bb_window: 20\n"
    "    atr_window: 14\n"
    "  thresholds:\n"
    "    entry:\n"
    "      min_adx: 22.0\n"
    "  engine:\n"
    "    interval: 1h\n"
)


def _setup_paths(tmp_path):
    artifacts = tmp_path / "artifacts"
    deploy_root = artifacts / "deployments" / "paper"
    deploy_root.mkdir(parents=True, exist_ok=True)
    target_yaml = tmp_path / "strategy_overrides.yaml"
    target_yaml.write_text("global:\n  engine:\n    interval: 30m\n", encoding="utf-8")
    return artifacts, deploy_root, target_yaml


def test_rollback_to_last_good_uses_prev_config_yaml(tmp_path):
    artifacts, deploy_root, target_yaml = _setup_paths(tmp_path)

    latest = deploy_root / "20260210T100000Z_deadbeef"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "prev_config.yaml").write_text(VALID_YAML, encoding="utf-8")

    rb_dir = rollback_to_last_good(
        artifacts_dir=artifacts,
        yaml_path=target_yaml,
        steps=1,
        reason="unit test rollback",
        restart="never",
        service="does-not-matter",
        dry_run=False,
    )

    assert target_yaml.read_text(encoding="utf-8").strip() == VALID_YAML.strip()
    event = json.loads((rb_dir / "rollback_event.json").read_text(encoding="utf-8"))
    assert event["why"]["reason"] == "unit test rollback"


def test_rollback_to_last_good_falls_back_to_older_deployed_config(tmp_path):
    artifacts, deploy_root, target_yaml = _setup_paths(tmp_path)

    latest = deploy_root / "20260210T100000Z_deadbeef"
    older = deploy_root / "20260210T090000Z_cafebabe"
    latest.mkdir(parents=True, exist_ok=True)
    older.mkdir(parents=True, exist_ok=True)

    # Empty prev_config.yaml forces fallback.
    (latest / "prev_config.yaml").write_text("", encoding="utf-8")
    (older / "deployed_config.yaml").write_text(VALID_YAML, encoding="utf-8")

    rb_dir = rollback_to_last_good(
        artifacts_dir=artifacts,
        yaml_path=target_yaml,
        steps=1,
        reason="unit test fallback",
        restart="never",
        service="does-not-matter",
        dry_run=False,
    )

    assert target_yaml.read_text(encoding="utf-8").strip() == VALID_YAML.strip()
    assert (rb_dir / "restored_config.yaml").exists()


def test_rollback_to_last_good_raises_when_no_deployments_exist(tmp_path):
    artifacts, _, target_yaml = _setup_paths(tmp_path)

    with pytest.raises(FileNotFoundError, match="Not enough deployments"):
        rollback_to_last_good(
            artifacts_dir=artifacts,
            yaml_path=target_yaml,
            steps=1,
            reason="unit test missing deployment",
            restart="never",
            service="does-not-matter",
            dry_run=False,
        )


def test_rollback_to_last_good_raises_when_prev_and_fallback_are_missing(tmp_path):
    artifacts, deploy_root, target_yaml = _setup_paths(tmp_path)

    latest = deploy_root / "20260210T100000Z_deadbeef"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "prev_config.yaml").write_text("", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Could not locate a rollback config"):
        rollback_to_last_good(
            artifacts_dir=artifacts,
            yaml_path=target_yaml,
            steps=1,
            reason="unit test missing fallback",
            restart="never",
            service="does-not-matter",
            dry_run=False,
        )


def test_rollback_to_last_good_raises_on_invalid_backup_yaml(tmp_path):
    artifacts, deploy_root, target_yaml = _setup_paths(tmp_path)

    latest = deploy_root / "20260210T100000Z_deadbeef"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "prev_config.yaml").write_text("global:\n  trade: [\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Rollback config failed validation"):
        rollback_to_last_good(
            artifacts_dir=artifacts,
            yaml_path=target_yaml,
            steps=1,
            reason="unit test invalid yaml",
            restart="never",
            service="does-not-matter",
            dry_run=False,
        )


def test_rollback_to_last_good_propagates_permission_error_on_yaml_write(tmp_path, monkeypatch):
    artifacts, deploy_root, target_yaml = _setup_paths(tmp_path)

    latest = deploy_root / "20260210T100000Z_deadbeef"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "prev_config.yaml").write_text(VALID_YAML, encoding="utf-8")

    def _raise_permission_error(path, text):  # noqa: ARG001
        raise PermissionError("write denied")

    monkeypatch.setattr(rollback_tool, "_atomic_write_text", _raise_permission_error)

    with pytest.raises(PermissionError, match="write denied"):
        rollback_to_last_good(
            artifacts_dir=artifacts,
            yaml_path=target_yaml,
            steps=1,
            reason="unit test permission error",
            restart="never",
            service="does-not-matter",
            dry_run=False,
        )


def test_atomic_write_text_uses_named_temporary_file(tmp_path, monkeypatch):
    target = tmp_path / "atomic.yaml"
    calls: dict[str, object] = {}

    class _TempCtx:
        def __init__(self, fp: Path) -> None:
            self._path = fp
            self._handle = None

        def __enter__(self):
            self._handle = self._path.open("w", encoding="utf-8")
            return self._handle

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            assert self._handle is not None
            self._handle.close()

    def _fake_named_temporary_file(*, mode, encoding, dir, prefix, suffix, delete):  # noqa: A002
        calls["mode"] = mode
        calls["encoding"] = encoding
        calls["dir"] = str(dir)
        calls["prefix"] = prefix
        calls["suffix"] = suffix
        calls["delete"] = delete
        return _TempCtx(tmp_path / "tmp-write-file")

    monkeypatch.setattr(rollback_tool.tempfile, "NamedTemporaryFile", _fake_named_temporary_file)

    rollback_tool._atomic_write_text(target, "hello-world\n")

    assert target.read_text(encoding="utf-8") == "hello-world\n"
    assert calls["mode"] == "w"
    assert calls["encoding"] == "utf-8"
    assert calls["dir"] == str(tmp_path)
    assert calls["prefix"] == ".atomic.yaml.tmp."
    assert calls["suffix"] == ".tmp"
    assert calls["delete"] is False


def test_rollback_to_last_good_allows_concurrent_calls_for_same_timestamp(tmp_path, monkeypatch):
    artifacts, deploy_root, target_yaml = _setup_paths(tmp_path)

    latest = deploy_root / "20260210T100000Z_deadbeef"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "prev_config.yaml").write_text(VALID_YAML, encoding="utf-8")

    monkeypatch.setattr(rollback_tool, "_utc_compact", lambda: "20260217T120000Z")
    monkeypatch.setattr(rollback_tool, "_utc_now_iso", lambda: "2026-02-17T12:00:00Z")

    reasons = ["unit test concurrent rollback A", "unit test concurrent rollback B"]

    def _run_once(reason: str):
        return rollback_to_last_good(
            artifacts_dir=artifacts,
            yaml_path=target_yaml,
            steps=1,
            reason=reason,
            restart="never",
            service="does-not-matter",
            dry_run=False,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run_once, reasons[0])
        f2 = pool.submit(_run_once, reasons[1])
        rb1 = f1.result()
        rb2 = f2.result()

    assert rb1 != rb2
    assert rb1.name.startswith("20260217T120000Z")
    assert rb2.name.startswith("20260217T120000Z")
    assert target_yaml.read_text(encoding="utf-8").strip() == VALID_YAML.strip()
    event1 = json.loads((rb1 / "rollback_event.json").read_text(encoding="utf-8"))
    event2 = json.loads((rb2 / "rollback_event.json").read_text(encoding="utf-8"))
    assert event1["version"] == "rollback_event_v1"
    assert event2["version"] == "rollback_event_v1"
    assert {event1["why"]["reason"], event2["why"]["reason"]} == set(reasons)
