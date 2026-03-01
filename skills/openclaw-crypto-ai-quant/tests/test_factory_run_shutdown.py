from __future__ import annotations

import json
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

import factory_run


@pytest.fixture(autouse=True)
def _reset_shutdown_state_fixture() -> None:
    factory_run._reset_shutdown_state()
    yield
    factory_run._reset_shutdown_state()


def test_run_cmd_returns_interrupted_when_shutdown_already_requested(tmp_path: Path) -> None:
    out_path = tmp_path / "pre_interrupt.stdout.txt"
    err_path = tmp_path / "pre_interrupt.stderr.txt"

    factory_run._request_shutdown(signal.SIGTERM, None)

    res = factory_run._run_cmd(
        [sys.executable, "-c", "print('should_not_run')"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=5.0,
    )

    assert res.exit_code == 130
    assert res.interrupted is True
    assert res.timed_out is False


def test_run_cmd_interrupts_active_process_on_shutdown(tmp_path: Path) -> None:
    out_path = tmp_path / "interrupt.stdout.txt"
    err_path = tmp_path / "interrupt.stderr.txt"

    def _trigger_shutdown() -> None:
        time.sleep(0.2)
        factory_run._request_shutdown(signal.SIGINT, None)

    signal_thread = threading.Thread(target=_trigger_shutdown)
    signal_thread.start()
    res = factory_run._run_cmd(
        [sys.executable, "-c", "import time; time.sleep(30.0)"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=60.0,
    )
    signal_thread.join(timeout=2.0)

    assert signal_thread.is_alive() is False
    assert res.exit_code == 130
    assert res.interrupted is True
    assert res.timed_out is False
    assert "interrupted" in err_path.read_text(encoding="utf-8").lower()


def test_mark_run_interrupted_writes_metadata_and_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {"steps": []}
    factory_run._request_shutdown(signal.SIGTERM, None)

    factory_run._mark_run_interrupted(run_dir=run_dir, meta=meta, stage="cpu_replay_validation")

    meta_path = run_dir / "run_metadata.json"
    assert meta_path.exists()
    meta_json = json.loads(meta_path.read_text(encoding="utf-8"))

    assert meta_json["status"] == "interrupted"
    assert meta_json["shutdown_requested_stage"] == "cpu_replay_validation"
    assert int(meta_json["interrupt_signal"]) == signal.SIGTERM
    assert isinstance(meta_json.get("interrupted_at_ms"), int)
    assert any(str(step.get("name", "")) == "shutdown_interrupt" for step in meta_json.get("steps", []))

    report_path = run_dir / "reports" / "report.md"
    assert report_path.exists()
    assert "interrupted" in report_path.read_text(encoding="utf-8").lower()


def test_shutdown_stage_guard_records_stage_in_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {"steps": []}
    factory_run._request_shutdown(signal.SIGINT, None)

    interrupted = factory_run._shutdown_stage_guard(run_dir=run_dir, meta=meta, stage="sweep")

    assert interrupted is True
    assert meta["shutdown_requested_stage"] == "sweep"
    meta_json = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert meta_json["status"] == "interrupted"
    assert meta_json["shutdown_requested_stage"] == "sweep"
