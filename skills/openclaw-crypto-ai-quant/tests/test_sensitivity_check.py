import sys

import pytest

from tools.sensitivity_check import (
    DEFAULT_PERTURBATIONS,
    _compute_aggregate,
    _get_nested,
    _parse_perturbations,
    _run_cmd,
    _set_nested,
    _validate_variant,
)


def _base_config() -> dict:
    return {
        "global": {
            "indicators": {
                "ema_fast_window": 10,
                "ema_slow_window": 30,
                "adx_window": 14,
                "bb_window": 20,
            },
            "thresholds": {"entry": {"min_adx": 20.0}},
            "trade": {"sl_atr_mult": 1.5, "tp_atr_mult": 2.5},
        }
    }


def test_run_cmd_success_reports_no_timeout(tmp_path):
    stdout_path = tmp_path / "ok.stdout.txt"
    stderr_path = tmp_path / "ok.stderr.txt"
    res = _run_cmd(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_s=5.0,
    )
    assert res.exit_code == 0
    assert res.timed_out is False
    assert "ok" in stdout_path.read_text(encoding="utf-8")


def test_run_cmd_timeout_returns_124(tmp_path):
    stdout_path = tmp_path / "timeout.stdout.txt"
    stderr_path = tmp_path / "timeout.stderr.txt"
    res = _run_cmd(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        cwd=tmp_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_s=0.1,
    )
    assert res.exit_code == 124
    assert res.timed_out is True


def test_parse_perturbations_uses_defaults_copy():
    parsed = _parse_perturbations(None)
    assert parsed == DEFAULT_PERTURBATIONS
    assert parsed is not DEFAULT_PERTURBATIONS


def test_parse_perturbations_parses_custom_csv():
    parsed = _parse_perturbations("trade.sl_atr_mult:-0.2, thresholds.entry.min_adx:1")
    assert parsed == [("trade.sl_atr_mult", -0.2), ("thresholds.entry.min_adx", 1.0)]


def test_parse_perturbations_rejects_invalid_item_format():
    with pytest.raises(SystemExit, match="Invalid --perturb item"):
        _parse_perturbations("trade.sl_atr_mult")


def test_parse_perturbations_rejects_non_numeric_delta():
    with pytest.raises(SystemExit, match="Invalid --perturb delta"):
        _parse_perturbations("trade.sl_atr_mult:not-a-number")


def test_set_nested_creates_global_path_when_prefix_missing():
    cfg: dict = {}
    _set_nested(cfg, "trade.sl_atr_mult", 1.25)
    assert _get_nested(cfg, "trade.sl_atr_mult") == 1.25
    assert cfg["global"]["trade"]["sl_atr_mult"] == 1.25


def test_set_nested_rejects_non_mapping_parent():
    cfg = {"global": {"trade": 3.0}}
    with pytest.raises(ValueError, match="Non-mapping node"):
        _set_nested(cfg, "trade.sl_atr_mult", 1.0)


def test_validate_variant_accepts_well_formed_config():
    ok, reason = _validate_variant(_base_config())
    assert ok is True
    assert reason == ""


def test_validate_variant_rejects_fast_window_not_less_than_slow():
    cfg = _base_config()
    cfg["global"]["indicators"]["ema_fast_window"] = 30
    cfg["global"]["indicators"]["ema_slow_window"] = 30
    ok, reason = _validate_variant(cfg)
    assert ok is False
    assert reason == "ema_fast_window must be < ema_slow_window"


def test_validate_variant_rejects_non_positive_atr_multiplier():
    cfg = _base_config()
    cfg["global"]["trade"]["sl_atr_mult"] = 0.0
    ok, reason = _validate_variant(cfg)
    assert ok is False
    assert reason == "trade.sl_atr_mult must be > 0"


def test_validate_variant_rejects_non_integer_window_value():
    cfg = _base_config()
    cfg["global"]["indicators"]["ema_fast_window"] = 10.5
    ok, reason = _validate_variant(cfg)
    assert ok is False
    assert reason == "ema_fast_window must be an integer"


def test_compute_aggregate_uses_only_successful_variants_for_positive_rate():
    variants = [
        {"exit_code": 0, "total_pnl": 10.0, "max_drawdown_pct": 2.0},
        {"exit_code": 0, "total_pnl": -5.0, "max_drawdown_pct": 4.0},
        {"exit_code": 1, "total_pnl": 999.0, "max_drawdown_pct": 99.0},
    ]
    agg = _compute_aggregate(20.0, variants)
    assert agg["variants_total"] == 3
    assert agg["variants_ran"] == 2
    assert agg["variants_skipped"] == 1
    assert agg["positive_rate"] == pytest.approx(0.5)
    assert agg["median_total_pnl"] == pytest.approx(2.5)
    assert agg["median_drawdown_pct"] == pytest.approx(3.0)
    assert agg["median_pnl_ratio_vs_baseline_abs"] == pytest.approx(0.125)


def test_compute_aggregate_handles_zero_baseline_without_division_error():
    variants = [{"exit_code": 0, "total_pnl": 1.0, "max_drawdown_pct": 2.0}]
    agg = _compute_aggregate(0.0, variants)
    assert agg["median_pnl_ratio_vs_baseline_abs"] == 0.0
