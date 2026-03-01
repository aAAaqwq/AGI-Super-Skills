from __future__ import annotations

import os
import sys
from pathlib import Path

import factory_run


def test_run_cmd_reports_timeout_and_non_zero_exit(tmp_path: Path) -> None:
    out_path = tmp_path / "cmd.stdout.txt"
    err_path = tmp_path / "cmd.stderr.txt"

    res = factory_run._run_cmd(
        [sys.executable, "-c", "import time; time.sleep(1.0)"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=0.1,
    )

    assert res.timed_out is True
    assert res.exit_code == 124
    assert res.timeout_s is not None
    assert res.timeout_s == 0.1
    assert res.elapsed_s < 1.0
    assert "timed out" in err_path.read_text(encoding="utf-8").lower()


def test_run_cmd_non_timeout_path(tmp_path: Path) -> None:
    out_path = tmp_path / "ok.stdout.txt"
    err_path = tmp_path / "ok.stderr.txt"

    res = factory_run._run_cmd(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=2.0,
    )

    assert res.timed_out is False
    assert res.exit_code == 0
    assert res.timeout_s == 2.0
    assert out_path.read_text(encoding="utf-8").strip() == "ok"


def test_run_cmd_timeout_can_be_disabled(tmp_path: Path) -> None:
    out_path = tmp_path / "no_timeout.stdout.txt"
    err_path = tmp_path / "no_timeout.stderr.txt"

    res = factory_run._run_cmd(
        [sys.executable, "-c", "import time; time.sleep(0.2); print('done')"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=0,
    )

    assert res.timed_out is False
    assert res.exit_code == 0
    assert res.timeout_s is None
    assert out_path.read_text(encoding="utf-8").strip() == "done"


def test_run_cmd_respects_env_default_timeout_disable(
    tmp_path: Path, monkeypatch
) -> None:
    out_path = tmp_path / "env_disable.stdout.txt"
    err_path = tmp_path / "env_disable.stderr.txt"
    monkeypatch.setenv("AI_QUANT_FACTORY_CMD_TIMEOUT_S", "0")

    res = factory_run._run_cmd(
        [sys.executable, "-c", "import time; time.sleep(0.2); print('done')"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=None,
    )

    assert res.timed_out is False
    assert res.exit_code == 0
    assert res.timeout_s is None
    assert out_path.read_text(encoding="utf-8").strip() == "done"


def test_run_cmd_missing_executable_returns_non_zero(tmp_path: Path) -> None:
    out_path = tmp_path / "missing.stdout.txt"
    err_path = tmp_path / "missing.stderr.txt"

    res = factory_run._run_cmd(
        ["__definitely_missing_binary_for_factory_run_tests__"],
        cwd=tmp_path,
        stdout_path=out_path,
        stderr_path=err_path,
        timeout_s=1.0,
    )

    assert res.exit_code == 127
    assert res.timed_out is False
    assert "failed to start command" in err_path.read_text(encoding="utf-8").lower()


def test_ensure_cuda_env_returns_copy_without_global_mutation(monkeypatch) -> None:
    monkeypatch.setenv("LD_LIBRARY_PATH", "/base")
    monkeypatch.setattr(factory_run.Path, "is_dir", lambda p: p.as_posix() == "/usr/lib/wsl/lib")

    src_env = {"LD_LIBRARY_PATH": "/base"}
    out_env = factory_run._ensure_cuda_env(src_env)

    assert src_env["LD_LIBRARY_PATH"] == "/base"
    assert os.environ.get("LD_LIBRARY_PATH") == "/base"
    assert "/usr/lib/wsl/lib" in str(out_env.get("LD_LIBRARY_PATH", ""))


def test_resolve_subprocess_env_only_augments_backtester_cwd(monkeypatch) -> None:
    monkeypatch.setattr(factory_run.Path, "is_dir", lambda p: p.as_posix() == "/usr/lib/wsl/lib")

    env_in = {"LD_LIBRARY_PATH": "/base", "KEEP": "1"}
    bt_env = factory_run._resolve_subprocess_env(cwd=factory_run.AIQ_ROOT / "backtester", env=env_in)
    root_env = factory_run._resolve_subprocess_env(cwd=factory_run.AIQ_ROOT, env=env_in)
    inherited_env = factory_run._resolve_subprocess_env(cwd=factory_run.AIQ_ROOT, env=None)

    assert bt_env is not None
    assert "/usr/lib/wsl/lib" in str(bt_env.get("LD_LIBRARY_PATH", ""))
    assert root_env == env_in
    assert inherited_env is None
