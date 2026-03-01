from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.config_id import config_id_from_yaml_text
from tools.prune_artifacts import prune_artifacts
from tools.registry_index import ingest_run_dir


def _make_run_dir(*, artifacts_root: Path, date: str, run_name: str, run_id: str, generated_at_ms: int) -> Path:
    run_dir = artifacts_root / date / run_name
    (run_dir / "configs").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)

    yaml_text = "global:\n  trade:\n    leverage: 3\n"
    cfg_path = run_dir / "configs" / "candidate.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")
    cfg_id = config_id_from_yaml_text(yaml_text)

    meta = {
        "run_id": run_id,
        "generated_at_ms": generated_at_ms,
        "run_date_utc": date,
        "run_dir": str(run_dir),
        "git_head": "deadbeef",
        "args": {"run_id": run_id},
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

    # Deep dirs we want to prune.
    (run_dir / "sweeps").mkdir(parents=True, exist_ok=True)
    (run_dir / "replays").mkdir(parents=True, exist_ok=True)
    (run_dir / "sweeps" / "dummy.jsonl").write_text("{}", encoding="utf-8")
    (run_dir / "replays" / "dummy.json").write_text("{}", encoding="utf-8")

    return run_dir


def test_prune_artifacts_respects_retention_and_deployed_guard(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    registry_db = artifacts_root / "registry" / "registry.sqlite"

    day_ms = 24 * 60 * 60 * 1000
    now_ms = 2_000_000_000_000
    keep_deep_days = 14

    run_old = _make_run_dir(
        artifacts_root=artifacts_root,
        date="2026-01-01",
        run_name="run_old",
        run_id="old",
        generated_at_ms=now_ms - (keep_deep_days + 2) * day_ms,
    )
    run_deployed = _make_run_dir(
        artifacts_root=artifacts_root,
        date="2026-01-02",
        run_name="run_deployed",
        run_id="deployed",
        generated_at_ms=now_ms - (keep_deep_days + 2) * day_ms,
    )
    run_new = _make_run_dir(
        artifacts_root=artifacts_root,
        date="2026-01-10",
        run_name="run_new",
        run_id="new",
        generated_at_ms=now_ms - (keep_deep_days - 1) * day_ms,
    )

    ingest_run_dir(registry_db=registry_db, run_dir=run_old)
    ingest_run_dir(registry_db=registry_db, run_dir=run_deployed)
    ingest_run_dir(registry_db=registry_db, run_dir=run_new)

    # Mark one run as deployed (must never be pruned).
    con = sqlite3.connect(str(registry_db))
    try:
        con.execute("UPDATE run_configs SET deployed = 1 WHERE run_id = ?", ("deployed",))
        con.commit()
    finally:
        con.close()

    dry = prune_artifacts(
        artifacts_root=artifacts_root,
        registry_db=registry_db,
        keep_deep_days=keep_deep_days,
        prune_logs=False,
        dry_run=True,
        override_now_ms=now_ms,
    )
    assert any(a.run_id == "old" and a.deleted for a in dry)
    assert (run_old / "sweeps").exists()
    assert (run_old / "replays").exists()

    real = prune_artifacts(
        artifacts_root=artifacts_root,
        registry_db=registry_db,
        keep_deep_days=keep_deep_days,
        prune_logs=False,
        dry_run=False,
        override_now_ms=now_ms,
    )
    assert any(a.run_id == "old" and a.deleted for a in real)
    assert not (run_old / "sweeps").exists()
    assert not (run_old / "replays").exists()
    assert (run_old / "prune.json").exists()

    # Deployed run should be untouched.
    assert (run_deployed / "sweeps").exists()
    assert (run_deployed / "replays").exists()

    # New run should be within retention.
    assert (run_new / "sweeps").exists()
    assert (run_new / "replays").exists()

