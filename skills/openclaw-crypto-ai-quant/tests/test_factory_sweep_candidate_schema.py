from __future__ import annotations

import json
from pathlib import Path

from factory_run import _validate_candidate_output_schema


def _write_lines(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_factory_validate_candidate_output_schema_accepts_valid_rows(tmp_path: Path) -> None:
    sweep_out = tmp_path / "sweep.jsonl"
    _write_lines(
        sweep_out,
        [
            {
                "schema_version": 1,
                "config_id": "cfg-001",
                "output_mode": "candidate",
                "overrides": {"trade.leverage": 5.0},
                "total_pnl": 12.5,
                "total_trades": 25,
                "profit_factor": 1.2,
                "max_drawdown_pct": 0.03,
                "candidate_mode": True,
            },
        ],
    )

    ok, errors = _validate_candidate_output_schema(sweep_out)
    assert ok
    assert errors == []


def test_factory_validate_candidate_output_schema_reports_invalid_rows(tmp_path: Path) -> None:
    sweep_out = tmp_path / "sweep.jsonl"
    _write_lines(
        sweep_out,
        [
            {
                "schema_version": 1,
                "config_id": "cfg-001",
                "output_mode": "full",
                "overrides": {"trade.leverage": 5.0},
                "total_pnl": 12.5,
                "total_trades": 25,
                "profit_factor": 1.2,
                "max_drawdown_pct": 0.03,
                "candidate_mode": False,
            },
        ],
    )

    ok, errors = _validate_candidate_output_schema(sweep_out)
    assert not ok
    assert any("output_mode is not candidate" in err for err in errors)
    assert any("candidate_mode is not true" in err for err in errors)


def test_factory_validate_candidate_output_schema_flags_invalid_schema_version(tmp_path: Path) -> None:
    sweep_out = tmp_path / "sweep.jsonl"
    _write_lines(
        sweep_out,
        [
            {
                "config_id": "cfg-001",
                "output_mode": "candidate",
                "overrides": {"trade.leverage": 5.0},
                "total_pnl": 12.5,
                "total_trades": 25,
                "profit_factor": 1.2,
                "max_drawdown_pct": 0.03,
                "candidate_mode": True,
                "schema_version": 2,
            },
        ],
    )

    ok, errors = _validate_candidate_output_schema(sweep_out)
    assert not ok
    assert any("schema_version must be 1" in err for err in errors)
