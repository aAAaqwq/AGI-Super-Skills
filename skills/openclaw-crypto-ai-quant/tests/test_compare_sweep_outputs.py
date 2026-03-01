from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from tools.compare_sweep_outputs import RankingThresholds, _baseline_comparison, build_lane_report, main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_lane_report_metrics_and_ranking_pass(tmp_path: Path) -> None:
    cpu_path = tmp_path / "cpu.jsonl"
    gpu_path = tmp_path / "gpu.jsonl"

    cpu_rows = [
        {"overrides": {"axis": 1.0}, "total_pnl": 12.0, "total_trades": 5},
        {"overrides": {"axis": 2.0}, "total_pnl": 10.0, "total_trades": 4},
        {"overrides": {"axis": 3.0}, "total_pnl": 8.0, "total_trades": 3},
    ]
    gpu_rows = [
        {"overrides": [["axis", 1.0]], "total_pnl": 11.0, "total_trades": 5},
        {"overrides": [["axis", 2.0]], "total_pnl": 10.0, "total_trades": 2},
        {"overrides": [["axis", 3.0]], "total_pnl": 7.0, "total_trades": 3},
    ]

    _write_jsonl(cpu_path, cpu_rows)
    _write_jsonl(gpu_path, gpu_rows)

    lane = build_lane_report(
        lane_name="lane_a_identical_symbol_universe",
        cpu_path=cpu_path,
        gpu_path=gpu_path,
        pnl_abs_tol=0.0,
        trade_abs_tol=0.0,
        top_ks=(1, 3),
        thresholds=RankingThresholds(min_spearman=0.90, min_top3_overlap=2, require_top1_match=True),
    )

    assert lane["rows"]["matched"] == 3
    assert lane["parity"]["any_mismatch_count"] == 2
    assert lane["parity"]["trade_count_mismatch_count"] == 1
    assert lane["parity"]["max_abs_total_pnl_diff"] == 1.0
    assert lane["parity"]["mean_abs_total_pnl_diff"] == 2 / 3

    assert lane["ranking"]["top1_cpu"] == "axis=1"
    assert lane["ranking"]["top1_gpu"] == "axis=1"
    assert lane["ranking"]["spearman_rho"] == 1.0
    assert lane["ranking"]["all_pass"] is True


def test_build_lane_report_ranking_assertion_failure(tmp_path: Path) -> None:
    cpu_path = tmp_path / "cpu.jsonl"
    gpu_path = tmp_path / "gpu.jsonl"

    cpu_rows = [
        {"overrides": {"axis": 1.0}, "total_pnl": 12.0, "total_trades": 5},
        {"overrides": {"axis": 2.0}, "total_pnl": 10.0, "total_trades": 4},
        {"overrides": {"axis": 3.0}, "total_pnl": 8.0, "total_trades": 3},
    ]
    gpu_rows = [
        {"overrides": [["axis", 1.0]], "total_pnl": 5.0, "total_trades": 5},
        {"overrides": [["axis", 2.0]], "total_pnl": 10.0, "total_trades": 4},
        {"overrides": [["axis", 3.0]], "total_pnl": 13.0, "total_trades": 3},
    ]

    _write_jsonl(cpu_path, cpu_rows)
    _write_jsonl(gpu_path, gpu_rows)

    lane = build_lane_report(
        lane_name="lane_b_production_truncation",
        cpu_path=cpu_path,
        gpu_path=gpu_path,
        pnl_abs_tol=0.0,
        trade_abs_tol=0.0,
        top_ks=(1, 3),
        thresholds=RankingThresholds(min_spearman=0.8, min_top3_overlap=3, require_top1_match=True),
    )

    assert lane["ranking"]["top1_cpu"] == "axis=1"
    assert lane["ranking"]["top1_gpu"] == "axis=3"
    assert lane["ranking"]["spearman_rho"] == -1.0
    assert lane["ranking"]["all_pass"] is False


def test_baseline_comparison_marks_improvement() -> None:
    lane_a = {
        "parity": {
            "any_mismatch_count": 10,
            "max_abs_total_pnl_diff": 2.5,
            "mean_abs_total_pnl_diff": 1.0,
            "trade_count_mismatch_count": 4,
        }
    }

    args = SimpleNamespace(
        baseline_any_mismatch_count=12.0,
        baseline_max_abs_total_pnl_diff=3.0,
        baseline_mean_abs_total_pnl_diff=2.0,
        baseline_trade_count_mismatch_count=6.0,
    )

    out = _baseline_comparison(lane_a, args)
    assert out["status"] == "provided"
    assert out["missing_required_metrics"] == []
    assert out["all_improved_or_equal"] is True


def test_baseline_comparison_missing_trade_baseline_is_incomplete() -> None:
    lane_a = {
        "parity": {
            "any_mismatch_count": 10,
            "max_abs_total_pnl_diff": 2.5,
            "mean_abs_total_pnl_diff": 1.0,
            "trade_count_mismatch_count": 4,
        }
    }

    args = SimpleNamespace(
        baseline_any_mismatch_count=12.0,
        baseline_max_abs_total_pnl_diff=3.0,
        baseline_mean_abs_total_pnl_diff=2.0,
        baseline_trade_count_mismatch_count=None,
    )

    out = _baseline_comparison(lane_a, args)
    assert out["status"] == "incomplete"
    assert out["missing_required_metrics"] == ["trade_count_mismatch_count"]
    assert out["all_improved_or_equal"] is False


def test_main_fail_on_assert_fails_on_incomplete_baseline(tmp_path: Path, monkeypatch) -> None:
    lane_a_cpu = tmp_path / "lane_a_cpu.jsonl"
    lane_a_gpu = tmp_path / "lane_a_gpu.jsonl"
    lane_b_cpu = tmp_path / "lane_b_cpu.jsonl"
    lane_b_gpu = tmp_path / "lane_b_gpu.jsonl"
    output = tmp_path / "report.json"

    lane_rows = [
        {"overrides": {"axis": 1.0}, "total_pnl": 10.0, "total_trades": 5},
        {"overrides": {"axis": 2.0}, "total_pnl": 9.0, "total_trades": 4},
    ]
    _write_jsonl(lane_a_cpu, lane_rows)
    _write_jsonl(lane_a_gpu, lane_rows)
    _write_jsonl(lane_b_cpu, lane_rows)
    _write_jsonl(lane_b_gpu, lane_rows)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_sweep_outputs.py",
            "--lane-a-cpu",
            str(lane_a_cpu),
            "--lane-a-gpu",
            str(lane_a_gpu),
            "--lane-b-cpu",
            str(lane_b_cpu),
            "--lane-b-gpu",
            str(lane_b_gpu),
            "--output",
            str(output),
            "--baseline-max-abs-total-pnl-diff",
            "1.0",
            "--baseline-mean-abs-total-pnl-diff",
            "1.0",
            "--fail-on-assert",
        ],
    )

    exit_code = main()
    report = json.loads(output.read_text(encoding="utf-8"))
    baseline = report["baseline_comparison"]["lane_a"]

    assert baseline["status"] == "incomplete"
    assert baseline["missing_required_metrics"] == ["trade_count_mismatch_count"]
    assert exit_code == 1


def test_main_fail_on_assert_fails_on_baseline_regression(tmp_path: Path, monkeypatch) -> None:
    lane_a_cpu = tmp_path / "lane_a_cpu.jsonl"
    lane_a_gpu = tmp_path / "lane_a_gpu.jsonl"
    lane_b_cpu = tmp_path / "lane_b_cpu.jsonl"
    lane_b_gpu = tmp_path / "lane_b_gpu.jsonl"
    output = tmp_path / "report.json"

    lane_a_cpu_rows = [
        {"overrides": {"axis": 1.0}, "total_pnl": 10.0, "total_trades": 5},
        {"overrides": {"axis": 2.0}, "total_pnl": 9.0, "total_trades": 4},
    ]
    lane_a_gpu_rows = [
        {"overrides": [["axis", 1.0]], "total_pnl": 9.0, "total_trades": 5},
        {"overrides": [["axis", 2.0]], "total_pnl": 8.5, "total_trades": 4},
    ]
    lane_b_rows = [
        {"overrides": {"axis": 1.0}, "total_pnl": 7.0, "total_trades": 3},
        {"overrides": {"axis": 2.0}, "total_pnl": 6.0, "total_trades": 2},
    ]

    _write_jsonl(lane_a_cpu, lane_a_cpu_rows)
    _write_jsonl(lane_a_gpu, lane_a_gpu_rows)
    _write_jsonl(lane_b_cpu, lane_b_rows)
    _write_jsonl(lane_b_gpu, lane_b_rows)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_sweep_outputs.py",
            "--lane-a-cpu",
            str(lane_a_cpu),
            "--lane-a-gpu",
            str(lane_a_gpu),
            "--lane-b-cpu",
            str(lane_b_cpu),
            "--lane-b-gpu",
            str(lane_b_gpu),
            "--output",
            str(output),
            "--baseline-max-abs-total-pnl-diff",
            "0.5",
            "--baseline-mean-abs-total-pnl-diff",
            "0.5",
            "--baseline-trade-count-mismatch-count",
            "0",
            "--fail-on-assert",
        ],
    )

    exit_code = main()
    report = json.loads(output.read_text(encoding="utf-8"))
    baseline = report["baseline_comparison"]["lane_a"]

    assert baseline["status"] == "provided"
    assert baseline["all_improved_or_equal"] is False
    assert exit_code == 1
