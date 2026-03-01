from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.slippage_stress as slippage_stress


def test_parse_bps_list_dedupes_and_preserves_order() -> None:
    parsed = slippage_stress._parse_bps_list("10,20,10,30")
    assert parsed == [10.0, 20.0, 30.0]


def test_parse_bps_list_rejects_invalid_value() -> None:
    with pytest.raises(SystemExit, match="Invalid slippage bps value"):
        slippage_stress._parse_bps_list("10,bad,30")


def test_parse_bps_list_rejects_empty_zero_and_negative() -> None:
    with pytest.raises(SystemExit, match="No slippage bps values provided"):
        slippage_stress._parse_bps_list("")
    with pytest.raises(SystemExit, match="Slippage bps must be > 0"):
        slippage_stress._parse_bps_list("0,10")
    with pytest.raises(SystemExit, match="Slippage bps must be > 0"):
        slippage_stress._parse_bps_list("-1,10")


def test_main_writes_summary_and_rejects_flip_sign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text("global: {}\n", encoding="utf-8")
    out_dir = tmp_path / "slippage_out"
    summary_path = tmp_path / "summary.json"

    pnl_by_bps = {10.0: 100.0, 20.0: -5.0, 30.0: -25.0}
    dd_by_bps = {10.0: 0.10, 20.0: 0.20, 30.0: 0.30}

    def _fake_run_cmd(argv: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> int:
        bps = float(argv[argv.index("--slippage-bps") + 1])
        replay_out = Path(argv[argv.index("--output") + 1])
        replay_out.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "config_id": "cfg",
            "initial_balance": 1000.0,
            "final_balance": 1000.0 + float(pnl_by_bps[bps]),
            "total_pnl": float(pnl_by_bps[bps]),
            "total_trades": 10,
            "win_rate": 0.5,
            "profit_factor": 1.1,
            "sharpe_ratio": 0.4,
            "max_drawdown_pct": float(dd_by_bps[bps]),
            "total_fees": 1.0,
            "slippage_bps": float(bps),
        }
        replay_out.write_text(json.dumps(report), encoding="utf-8")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(slippage_stress, "_resolve_backtester_cmd", lambda: ["mei-backtester"])
    monkeypatch.setattr(slippage_stress, "_run_cmd", _fake_run_cmd)

    rc = slippage_stress.main(
        [
            "--config",
            str(config_path),
            "--interval",
            "1h",
            "--slippage-bps",
            "10,20,30",
            "--reject-flip-bps",
            "20",
            "--out-dir",
            str(out_dir),
            "--output",
            str(summary_path),
        ]
    )
    assert rc == 0

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    agg = summary["aggregate"]
    assert agg["baseline_bps"] == 10.0
    assert agg["baseline_total_pnl"] == pytest.approx(100.0)
    assert agg["pnl_at_reject_bps"] == pytest.approx(-5.0)
    assert agg["pnl_drop_at_reject_bps"] == pytest.approx(105.0)
    assert agg["slippage_fragility"] == pytest.approx(0.105)
    assert agg["flip_sign_at_reject_bps"] is True
    assert agg["degraded"] is False
    assert agg["failed_levels"] == []
    assert agg["reject_reason"] == "flip_sign_at_reject_bps"
    assert agg["reject_reasons"] == ["flip_sign_at_reject_bps"]
    assert agg["reject"] is True


def test_main_records_failures_and_continues_levels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text("global: {}\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    summary_path = tmp_path / "summary.json"

    calls: list[float] = []

    def _fake_run_cmd(argv: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> int:  # noqa: ARG001
        bps = float(argv[argv.index("--slippage-bps") + 1])
        calls.append(bps)
        replay_out = Path(argv[argv.index("--output") + 1])
        replay_out.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if bps == 10.0:
            return 9
        replay_out.write_text(
            json.dumps(
                {
                    "config_id": "cfg",
                    "initial_balance": 1000.0,
                    "final_balance": 980.0,
                    "total_pnl": -20.0,
                    "total_trades": 5,
                    "win_rate": 0.3,
                    "profit_factor": 0.8,
                    "sharpe_ratio": -0.4,
                    "max_drawdown_pct": 0.2,
                    "total_fees": 1.0,
                    "slippage_bps": float(bps),
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(slippage_stress, "_resolve_backtester_cmd", lambda: ["mei-backtester"])
    monkeypatch.setattr(slippage_stress, "_run_cmd", _fake_run_cmd)

    rc = slippage_stress.main(
        [
            "--config",
            str(config_path),
            "--slippage-bps",
            "10,20",
            "--reject-flip-bps",
            "20",
            "--out-dir",
            str(out_dir),
            "--output",
            str(summary_path),
        ]
    )
    assert rc == 0
    assert calls == [10.0, 20.0]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    agg = summary["aggregate"]
    assert agg["degraded"] is True
    assert agg["failed_levels"] == [10.0]
    assert "missing_baseline_level" in agg["degraded_reasons"]
    assert "replay_failure" in agg["degraded_reasons"]
    assert agg["reject_reason"] == "degraded_run"
    assert agg["reject_reasons"] == ["degraded_run"]
    assert agg["reject"] is True

    failed = [r for r in summary["results"] if r.get("ok") is False]
    assert len(failed) == 1
    assert failed[0]["slippage_bps"] == 10.0
    assert failed[0]["metrics"] is None
    assert failed[0]["exit_code"] == 9


def test_main_reject_flip_bps_must_be_in_levels(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text("global: {}\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="must be included in --slippage-bps"):
        slippage_stress.main(
            [
                "--config",
                str(config_path),
                "--slippage-bps",
                "10,30",
                "--reject-flip-bps",
                "20",
                "--out-dir",
                str(tmp_path / "out"),
            ]
        )


def test_main_records_parse_error_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text("global: {}\n", encoding="utf-8")
    summary_path = tmp_path / "summary.json"
    out_dir = tmp_path / "out"

    def _fake_run_cmd(argv: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> int:  # noqa: ARG001
        bps = float(argv[argv.index("--slippage-bps") + 1])
        replay_out = Path(argv[argv.index("--output") + 1])
        replay_out.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if bps == 10.0:
            replay_out.write_text("{not-json", encoding="utf-8")
            return 0
        replay_out.write_text(
            json.dumps(
                {
                    "config_id": "cfg",
                    "initial_balance": 1000.0,
                    "final_balance": 990.0,
                    "total_pnl": -10.0,
                    "total_trades": 8,
                    "win_rate": 0.4,
                    "profit_factor": 0.9,
                    "sharpe_ratio": -0.2,
                    "max_drawdown_pct": 0.15,
                    "total_fees": 1.0,
                    "slippage_bps": float(bps),
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(slippage_stress, "_resolve_backtester_cmd", lambda: ["mei-backtester"])
    monkeypatch.setattr(slippage_stress, "_run_cmd", _fake_run_cmd)

    rc = slippage_stress.main(
        [
            "--config",
            str(config_path),
            "--slippage-bps",
            "10,20",
            "--reject-flip-bps",
            "20",
            "--out-dir",
            str(out_dir),
            "--output",
            str(summary_path),
        ]
    )
    assert rc == 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    failed = [r for r in summary["results"] if r.get("ok") is False]
    assert len(failed) == 1
    assert failed[0]["slippage_bps"] == 10.0
    assert "report_parse_error" in str(failed[0]["error"])
    agg = summary["aggregate"]
    assert agg["degraded"] is True
    assert "replay_failure" in agg["degraded_reasons"]


def test_main_marks_missing_reject_level_when_reject_run_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "strategy.yaml"
    config_path.write_text("global: {}\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    summary_path = tmp_path / "summary.json"

    def _fake_run_cmd(argv: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> int:  # noqa: ARG001
        bps = float(argv[argv.index("--slippage-bps") + 1])
        replay_out = Path(argv[argv.index("--output") + 1])
        replay_out.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if bps == 20.0:
            return 7
        replay_out.write_text(
            json.dumps(
                {
                    "config_id": "cfg",
                    "initial_balance": 1000.0,
                    "final_balance": 1020.0,
                    "total_pnl": 20.0,
                    "total_trades": 8,
                    "win_rate": 0.6,
                    "profit_factor": 1.2,
                    "sharpe_ratio": 0.3,
                    "max_drawdown_pct": 0.12,
                    "total_fees": 1.0,
                    "slippage_bps": float(bps),
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(slippage_stress, "_resolve_backtester_cmd", lambda: ["mei-backtester"])
    monkeypatch.setattr(slippage_stress, "_run_cmd", _fake_run_cmd)

    rc = slippage_stress.main(
        [
            "--config",
            str(config_path),
            "--slippage-bps",
            "10,20",
            "--reject-flip-bps",
            "20",
            "--out-dir",
            str(out_dir),
            "--output",
            str(summary_path),
        ]
    )
    assert rc == 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    agg = summary["aggregate"]
    assert agg["degraded"] is True
    assert "missing_reject_level" in agg["degraded_reasons"]
