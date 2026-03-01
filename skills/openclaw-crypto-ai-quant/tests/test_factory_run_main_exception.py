from __future__ import annotations

import json
import signal
from pathlib import Path

import pytest

import factory_run


@pytest.fixture(autouse=True)
def _reset_shutdown_state_fixture() -> None:
    factory_run._reset_shutdown_state()
    yield
    factory_run._reset_shutdown_state()


def test_main_persists_fatal_error_and_reraises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "fatal-main-ut"
    artifacts_dir = tmp_path / "artifacts"

    def _boom() -> list[str]:
        raise RuntimeError("boom in resolve backtester")

    monkeypatch.setattr(factory_run, "_resolve_backtester_cmd", _boom)

    with pytest.raises(RuntimeError, match="boom in resolve backtester"):
        factory_run.main(["--run-id", run_id, "--artifacts-dir", str(artifacts_dir)])

    metadata_paths = list(artifacts_dir.rglob("run_metadata.json"))
    assert len(metadata_paths) == 1

    meta = json.loads(metadata_paths[0].read_text(encoding="utf-8"))
    assert meta["status"] == "failed"
    assert "RuntimeError: boom in resolve backtester" in str(meta.get("fatal_error", ""))
    assert meta["fatal_error_stage"] == "initialisation"
    assert isinstance(meta.get("fatal_error_at_ms"), int)


def test_main_preserves_fatal_metadata_when_shutdown_also_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "fatal-main-shutdown-ut"
    artifacts_dir = tmp_path / "artifacts"

    def _boom_with_shutdown() -> list[str]:
        factory_run._request_shutdown(signal.SIGTERM, None)
        raise RuntimeError("boom after shutdown request")

    monkeypatch.setattr(factory_run, "_resolve_backtester_cmd", _boom_with_shutdown)

    with pytest.raises(RuntimeError, match="boom after shutdown request"):
        factory_run.main(["--run-id", run_id, "--artifacts-dir", str(artifacts_dir)])

    metadata_paths = list(artifacts_dir.rglob("run_metadata.json"))
    assert len(metadata_paths) == 1

    meta = json.loads(metadata_paths[0].read_text(encoding="utf-8"))
    assert meta["status"] == "failed"
    assert "RuntimeError: boom after shutdown request" in str(meta.get("fatal_error", ""))
    assert meta["fatal_error_stage"] == "initialisation"
