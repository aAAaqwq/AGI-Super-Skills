from __future__ import annotations
import json

from pathlib import Path

import pytest

try:
    from jsonschema import validate
except Exception:  # pragma: no cover - defensive for minimal env
    validate = None  # type: ignore[assignment]


def test_gpu_candidate_rows_conform_to_schema() -> None:
    if validate is None:
        pytest.skip("jsonschema is not available in the test environment")

    schema = Path("schemas/gpu_candidate_schema.json")
    schema_json = json.loads(schema.read_text(encoding="utf-8"))
    candidate = {
        "schema_version": 1,
        "config_id": "cfg_001",
        "output_mode": "candidate",
        "overrides": {
            "trade.leverage": 3.0,
            "trade.enable_pyramiding": True,
        },
        "total_pnl": 120.5,
        "total_trades": 11,
        "profit_factor": 2.1,
        "max_drawdown_pct": 0.042,
        "candidate_mode": True,
    }

    validate(instance=candidate, schema=schema_json)


def test_gpu_candidate_schema_rejects_invalid_rows() -> None:
    if validate is None:
        pytest.skip("jsonschema is not available in the test environment")

    schema = Path("schemas/gpu_candidate_schema.json")
    schema_json = json.loads(schema.read_text(encoding="utf-8"))
    bad = {
        "schema_version": 1,
        "config_id": "cfg_001",
        "output_mode": "full",
        "overrides": {},
        "total_pnl": 0,
        "total_trades": 0,
        "profit_factor": 1.0,
        "max_drawdown_pct": 0,
        "candidate_mode": False,
    }

    with pytest.raises(Exception):
        validate(instance=bad, schema=schema_json)


def test_gpu_candidate_schema_requires_supported_version() -> None:
    if validate is None:
        pytest.skip("jsonschema is not available in the test environment")

    schema = Path("schemas/gpu_candidate_schema.json")
    schema_json = json.loads(schema.read_text(encoding="utf-8"))
    bad = {
        "schema_version": 2,
        "config_id": "cfg_001",
        "output_mode": "candidate",
        "overrides": {"trade.leverage": 3.0},
        "total_pnl": 120.5,
        "total_trades": 11,
        "profit_factor": 2.1,
        "max_drawdown_pct": 0.042,
        "candidate_mode": True,
    }
    with pytest.raises(Exception):
        validate(instance=bad, schema=schema_json)
