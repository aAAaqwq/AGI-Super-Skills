from __future__ import annotations

import json
from pathlib import Path

from tools.config_id import config_id_from_yaml_text
from tools.registry_index import ingest_run_dir, query


def test_registry_ingest_and_query(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_dir = artifacts_root / "2026-02-10" / "run_test123"
    (run_dir / "configs").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)

    yaml_text = "global:\n  trade:\n    leverage: 3\n"
    cfg_path = run_dir / "configs" / "candidate.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")
    cfg_id = config_id_from_yaml_text(yaml_text)

    meta = {
        "run_id": "test123",
        "generated_at_ms": 1234567890,
        "run_date_utc": "2026-02-10",
        "run_dir": str(run_dir),
        "git_head": "deadbeef",
        "args": {"run_id": "test123"},
        "candidate_configs": [{"path": str(cfg_path), "config_id": cfg_id}],
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

    report = {
        "items": [
            {
                "path": str(run_dir / "replays" / "candidate.replay.json"),
                "config_path": str(cfg_path),
                "config_id": cfg_id,
                "final_balance": 101.0,
                "total_pnl": 1.0,
                "total_trades": 2,
                "win_rate": 0.5,
                "profit_factor": 1.2,
                "max_drawdown_pct": 0.1,
                "total_fees": 0.01,
            }
        ]
    }
    (run_dir / "reports" / "report.json").write_text(json.dumps(report), encoding="utf-8")

    registry_db = tmp_path / "registry.sqlite"
    res = ingest_run_dir(registry_db=registry_db, run_dir=run_dir)
    assert res.run_id == "test123"
    assert res.num_configs == 1

    by_run = query(registry_db=registry_db, run_id="test123", config_id=None, date_utc=None, limit=10)
    assert len(by_run) == 1
    assert by_run[0]["config_id"] == cfg_id
    assert by_run[0]["run_date_utc"] == "2026-02-10"

    by_date = query(registry_db=registry_db, run_id=None, config_id=None, date_utc="2026-02-10", limit=10)
    assert len(by_date) == 1

