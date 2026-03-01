#!/usr/bin/env python3
"""Local registry index for factory runs and configs (SQLite).

This registry is a lightweight metadata store that lets you query:
- runs (by run_id/date)
- configs (by config_id)
- metrics per config per run

It is designed to be:
- append-only for runs (idempotent upserts are allowed)
- queryable without loading large artifact folders

The registry is stored under the artifacts root by default:
  artifacts/registry/registry.sqlite
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _write_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _stderr(msg: str) -> None:
    sys.stderr.write(str(msg).rstrip("\n") + "\n")


def default_registry_db_path(*, artifacts_root: Path) -> Path:
    return (artifacts_root / "registry" / "registry.sqlite").resolve()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=2.0)
    con.row_factory = sqlite3.Row
    with con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            generated_at_ms INTEGER NOT NULL,
            run_date_utc TEXT NOT NULL,
            run_dir TEXT NOT NULL,
            git_head TEXT,
            args_json TEXT,
            created_at_ms INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS configs (
            config_id TEXT PRIMARY KEY,
            yaml_text TEXT NOT NULL,
            first_seen_run_id TEXT,
            created_at_ms INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS run_configs (
            run_id TEXT NOT NULL,
            config_id TEXT NOT NULL,
            config_path TEXT NOT NULL,
            total_pnl REAL,
            max_drawdown_pct REAL,
            total_trades INTEGER,
            win_rate REAL,
            profit_factor REAL,
            total_fees REAL,
            verdict TEXT DEFAULT 'unknown',
            deployed INTEGER DEFAULT 0,
            retirement_reason TEXT,
            created_at_ms INTEGER NOT NULL,
            PRIMARY KEY (run_id, config_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (config_id) REFERENCES configs(config_id)
        )
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_date ON runs(run_date_utc)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_generated ON runs(generated_at_ms)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_run_configs_config_id ON run_configs(config_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_run_configs_verdict ON run_configs(verdict)")
    con.commit()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class IngestResult:
    run_id: str
    run_date_utc: str
    num_configs: int
    registry_db: str


def ingest_run_dir(*, registry_db: Path, run_dir: Path) -> IngestResult:
    """Ingest an existing factory run directory into the registry DB."""
    run_dir = Path(run_dir).expanduser().resolve()
    meta_path = run_dir / "run_metadata.json"
    report_path = run_dir / "reports" / "report.json"

    meta = _load_json(meta_path)
    report = _load_json(report_path)

    run_id = str(meta.get("run_id", "")).strip()
    if not run_id:
        raise ValueError(f"Missing run_id in {meta_path}")

    generated_at_ms = int(meta.get("generated_at_ms", 0))
    run_date_utc = str(meta.get("run_date_utc", "")).strip()
    git_head = str(meta.get("git_head", "")).strip() or None
    args_json = json.dumps(meta.get("args", {}), sort_keys=True)

    items = report.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"Expected list report.items in {report_path}")

    now_ms = int(time.time() * 1000)

    con = _connect(registry_db)
    try:
        _ensure_schema(con)
        cur = con.cursor()

        cur.execute(
            """
            INSERT INTO runs (run_id, generated_at_ms, run_date_utc, run_dir, git_head, args_json, created_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                generated_at_ms=excluded.generated_at_ms,
                run_date_utc=excluded.run_date_utc,
                run_dir=excluded.run_dir,
                git_head=excluded.git_head,
                args_json=excluded.args_json
            """,
            (run_id, generated_at_ms, run_date_utc, str(run_dir), git_head, args_json, now_ms),
        )

        seen_config_ids: set[str] = set()
        for it in items:
            if not isinstance(it, dict):
                continue
            config_id = str(it.get("config_id", "")).strip()
            config_path = str(it.get("config_path", "")).strip()
            if not config_id or not config_path:
                continue
            if config_id in seen_config_ids:
                continue
            seen_config_ids.add(config_id)

            yaml_text = Path(config_path).read_text(encoding="utf-8")
            cur.execute(
                """
                INSERT INTO configs (config_id, yaml_text, first_seen_run_id, created_at_ms)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(config_id) DO NOTHING
                """,
                (config_id, yaml_text, run_id, now_ms),
            )

        for it in items:
            if not isinstance(it, dict):
                continue
            config_id = str(it.get("config_id", "")).strip()
            config_path = str(it.get("config_path", "")).strip()
            if not config_id or not config_path:
                continue

            cur.execute(
                """
                INSERT INTO run_configs (
                    run_id, config_id, config_path,
                    total_pnl, max_drawdown_pct, total_trades, win_rate, profit_factor, total_fees,
                    verdict, deployed, retirement_reason, created_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', 0, NULL, ?)
                ON CONFLICT(run_id, config_id) DO UPDATE SET
                    config_path=excluded.config_path,
                    total_pnl=excluded.total_pnl,
                    max_drawdown_pct=excluded.max_drawdown_pct,
                    total_trades=excluded.total_trades,
                    win_rate=excluded.win_rate,
                    profit_factor=excluded.profit_factor,
                    total_fees=excluded.total_fees
                """,
                (
                    run_id,
                    config_id,
                    config_path,
                    float(it.get("total_pnl", 0.0)),
                    float(it.get("max_drawdown_pct", 0.0)),
                    int(it.get("total_trades", 0)),
                    float(it.get("win_rate", 0.0)),
                    float(it.get("profit_factor", 0.0)),
                    float(it.get("total_fees", 0.0)),
                    now_ms,
                ),
            )

        con.commit()
        return IngestResult(
            run_id=run_id,
            run_date_utc=run_date_utc,
            num_configs=len(seen_config_ids),
            registry_db=str(Path(registry_db).resolve()),
        )
    finally:
        con.close()


def query(
    *,
    registry_db: Path,
    run_id: str | None,
    config_id: str | None,
    date_utc: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    con = _connect(registry_db)
    try:
        _ensure_schema(con)
        where: list[str] = []
        params: list[Any] = []
        if run_id:
            where.append("r.run_id = ?")
            params.append(str(run_id))
        if config_id:
            where.append("rc.config_id = ?")
            params.append(str(config_id))
        if date_utc:
            where.append("r.run_date_utc = ?")
            params.append(str(date_utc))

        sql = """
        SELECT
            r.run_id,
            r.run_date_utc,
            r.generated_at_ms,
            r.run_dir,
            r.git_head,
            rc.config_id,
            rc.config_path,
            rc.total_pnl,
            rc.max_drawdown_pct,
            rc.total_trades,
            rc.win_rate,
            rc.profit_factor,
            rc.total_fees,
            rc.verdict,
            rc.deployed,
            rc.retirement_reason
        FROM run_configs rc
        JOIN runs r ON r.run_id = rc.run_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY r.generated_at_ms DESC LIMIT ?"
        params.append(int(limit))

        rows = list(con.execute(sql, params))
        return [dict(r) for r in rows]
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Local registry index (SQLite) for factory runs/configs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap.add_argument(
        "--registry-db",
        default="",
        help="Path to registry SQLite DB (default: artifacts/registry/registry.sqlite).",
    )
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root (default: artifacts).")

    ap_ingest = sub.add_parser("ingest-run-dir", help="Ingest a factory run directory into the registry.")
    ap_ingest.add_argument("--run-dir", required=True, help="Path to a run directory (artifacts/.../run_<id>/).")

    ap_query = sub.add_parser("query", help="Query registry by run_id/config_id/date.")
    ap_query.add_argument("--run-id", default="", help="Filter by run_id.")
    ap_query.add_argument("--config-id", default="", help="Filter by config_id.")
    ap_query.add_argument("--date-utc", default="", help="Filter by run_date_utc (YYYY-MM-DD).")
    ap_query.add_argument("--limit", type=int, default=50, help="Max rows to return (default: 50).")

    args = ap.parse_args(argv)

    artifacts_root = (AIQ_ROOT / str(args.artifacts_dir)).resolve()
    if args.registry_db:
        registry_db = Path(args.registry_db).expanduser().resolve()
    else:
        registry_db = default_registry_db_path(artifacts_root=artifacts_root)

    if args.cmd == "ingest-run-dir":
        res = ingest_run_dir(registry_db=registry_db, run_dir=Path(args.run_dir))
        _stderr(f"[registry] Ingested run_id={res.run_id} configs={res.num_configs} db={res.registry_db}")
        _write_json(res.__dict__)
        return 0

    if args.cmd == "query":
        out = query(
            registry_db=registry_db,
            run_id=(args.run_id or None),
            config_id=(args.config_id or None),
            date_utc=(args.date_utc or None),
            limit=int(args.limit),
        )
        _write_json({"registry_db": str(registry_db), "items": out})
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())

