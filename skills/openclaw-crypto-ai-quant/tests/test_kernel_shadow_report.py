from __future__ import annotations

import json

from engine.kernel_shadow_report import DEFAULT_SHADOW_MAX_COMPARISONS, ShadowReport
from engine.kernel_shadow_report import MAX_SHADOW_MAX_COMPARISONS, MIN_SHADOW_MAX_COMPARISONS


def test_shadow_report_comparisons_are_bounded_by_env_limit(monkeypatch):
    monkeypatch.setenv("AI_QUANT_SHADOW_MAX_COMPARISONS", "3")
    report = ShadowReport()

    for i in range(5):
        report.add_comparison(
            metric=f"m{i}",
            old_val=1.0,
            kernel_val=1.0,
            tolerance=0.01,
            timestamp=float(i),
        )

    assert report.comparisons.maxlen == 3
    assert len(report.comparisons) == 3
    assert [c.metric for c in report.comparisons] == ["m2", "m3", "m4"]


def test_shadow_report_invalid_env_uses_default_limit(monkeypatch):
    monkeypatch.setenv("AI_QUANT_SHADOW_MAX_COMPARISONS", "not-a-number")
    report = ShadowReport()
    assert report.comparisons.maxlen == DEFAULT_SHADOW_MAX_COMPARISONS


def test_shadow_report_env_limit_is_clamped(monkeypatch):
    monkeypatch.setenv("AI_QUANT_SHADOW_MAX_COMPARISONS", "0")
    report_min = ShadowReport()
    assert report_min.comparisons.maxlen == MIN_SHADOW_MAX_COMPARISONS

    monkeypatch.setenv("AI_QUANT_SHADOW_MAX_COMPARISONS", str(MAX_SHADOW_MAX_COMPARISONS + 123))
    report_max = ShadowReport()
    assert report_max.comparisons.maxlen == MAX_SHADOW_MAX_COMPARISONS


def test_shadow_report_from_json_keeps_latest_with_bounded_deque(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_QUANT_SHADOW_MAX_COMPARISONS", "2")
    src = tmp_path / "shadow_report.json"
    src.write_text(
        json.dumps(
            [
                {
                    "timestamp": float(i),
                    "metric": f"m{i}",
                    "old_value": 1.0,
                    "kernel_value": 1.0,
                    "delta": 0.0,
                    "tolerance": 0.01,
                    "passed": True,
                }
                for i in range(5)
            ]
        ),
        encoding="utf-8",
    )

    report = ShadowReport.from_json(str(src))
    assert report.comparisons.maxlen == 2
    assert len(report.comparisons) == 2
    assert [c.metric for c in report.comparisons] == ["m3", "m4"]
