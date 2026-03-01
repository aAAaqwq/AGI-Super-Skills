import subprocess
from types import SimpleNamespace

import tools.interval_orchestrator as interval_orchestrator


def test_orchestrate_restart_clears_pause_file_on_success(tmp_path, monkeypatch):
    pause_file = tmp_path / "kill.txt"

    calls = []

    def fake_run(argv, capture_output, text, check, timeout):  # noqa: ARG001
        assert timeout == interval_orchestrator.SYSTEMCTL_TIMEOUT_S
        calls.append(list(argv))
        if argv[:3] == ["systemctl", "--user", "restart"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:4] == ["systemctl", "--user", "is-active", "--quiet"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr("subprocess.run", fake_run)

    res = interval_orchestrator.orchestrate_interval_restart(
        ws_service="ws",
        trader_service="trader",
        pause_file=pause_file,
        pause_mode="close_only",
        resume_on_success=True,
        verify_sleep_s=0.0,
    )

    assert all(r.ok for r in res)
    assert not pause_file.exists()
    assert any(c[:3] == ["systemctl", "--user", "restart"] for c in calls)


def test_orchestrate_restart_leaves_pause_file_on_restart_failure(tmp_path, monkeypatch):
    pause_file = tmp_path / "kill.txt"

    def fake_run(argv, capture_output, text, check, timeout):  # noqa: ARG001
        assert timeout == interval_orchestrator.SYSTEMCTL_TIMEOUT_S
        if argv[:3] == ["systemctl", "--user", "restart"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="boom")
        if argv[:4] == ["systemctl", "--user", "is-active", "--quiet"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr("subprocess.run", fake_run)

    res = interval_orchestrator.orchestrate_interval_restart(
        ws_service="ws",
        trader_service="trader",
        pause_file=pause_file,
        pause_mode="close_only",
        resume_on_success=True,
        verify_sleep_s=0.0,
    )

    assert any(not r.ok for r in res)
    assert pause_file.exists()


def test_orchestrate_restart_leaves_pause_file_on_is_active_failure(tmp_path, monkeypatch):
    pause_file = tmp_path / "kill.txt"

    def fake_run(argv, capture_output, text, check, timeout):  # noqa: ARG001
        assert timeout == interval_orchestrator.SYSTEMCTL_TIMEOUT_S
        if argv[:3] == ["systemctl", "--user", "restart"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:4] == ["systemctl", "--user", "is-active", "--quiet"]:
            # Fail for trader
            svc = argv[4]
            return SimpleNamespace(returncode=0 if svc == "ws" else 3, stdout="", stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr("subprocess.run", fake_run)

    res = interval_orchestrator.orchestrate_interval_restart(
        ws_service="ws",
        trader_service="trader",
        pause_file=pause_file,
        pause_mode="close_only",
        resume_on_success=True,
        verify_sleep_s=0.0,
    )

    assert any(not r.ok for r in res)
    assert pause_file.exists()


def test_systemctl_restart_timeout_maps_to_failure(monkeypatch):
    def fake_run(argv, capture_output, text, check, timeout):  # noqa: ARG001
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr("subprocess.run", fake_run)
    res = interval_orchestrator._systemctl_restart("ws")
    assert res.ok is False
    assert res.exit_code == 124
    assert "timed out" in res.stderr


def test_systemctl_is_active_timeout_returns_false(monkeypatch):
    def fake_run(argv, capture_output, text, check, timeout):  # noqa: ARG001
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr("subprocess.run", fake_run)
    assert interval_orchestrator._systemctl_is_active("ws") is False
