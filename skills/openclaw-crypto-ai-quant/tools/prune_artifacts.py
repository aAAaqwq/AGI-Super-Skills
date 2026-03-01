#!/usr/bin/env python3
"""Prune factory artifacts with a retention policy.

Policy (v1):
- Keep summaries forever (run_metadata + reports + configs).
- Prune deep artifacts after N days (default: sweeps/ and replays/; optionally logs/).
- Never prune runs that have deployed configs recorded in the registry index.

This tool is designed to be run via cron/systemd on the *major-v8* worktree,
never on the production `master` worktree.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from tools.registry_index import default_registry_db_path
except ImportError:  # pragma: no cover
    from registry_index import default_registry_db_path  # type: ignore[no-redef]


AIQ_ROOT = Path(__file__).resolve().parents[1]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _write_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _stderr(msg: str) -> None:
    sys.stderr.write(str(msg).rstrip("\n") + "\n")


def _now_ms(override_now_ms: int | None) -> int:
    return int(override_now_ms) if override_now_ms is not None else int(time.time() * 1000)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=2.0)
    con.row_factory = sqlite3.Row
    return con


def _run_known(con: sqlite3.Connection, *, run_id: str) -> bool:
    row = con.execute("SELECT 1 FROM runs WHERE run_id = ? LIMIT 1", (run_id,)).fetchone()
    return row is not None


def _run_has_deployed(con: sqlite3.Connection, *, run_id: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM run_configs WHERE run_id = ? AND deployed != 0 LIMIT 1",
        (run_id,),
    ).fetchone()
    return row is not None


@dataclass(frozen=True)
class PruneAction:
    run_id: str
    run_dir: str
    age_days: int
    deleted: list[str]
    skipped_reason: str | None = None


def prune_artifacts(
    *,
    artifacts_root: Path,
    registry_db: Path,
    keep_deep_days: int,
    prune_logs: bool,
    dry_run: bool,
    override_now_ms: int | None,
) -> list[PruneAction]:
    artifacts_root = Path(artifacts_root).expanduser().resolve()
    registry_db = Path(registry_db).expanduser().resolve()
    if keep_deep_days < 0:
        raise ValueError("keep_deep_days must be >= 0")

    if not registry_db.exists():
        raise FileNotFoundError(f"Registry DB not found: {registry_db}")

    now_ms = _now_ms(override_now_ms)
    day_ms = 24 * 60 * 60 * 1000

    actions: list[PruneAction] = []

    con = _connect_ro(registry_db)
    try:
        for date_dir in sorted([p for p in artifacts_root.iterdir() if p.is_dir() and _DATE_RE.match(p.name)]):
            for run_dir in sorted([p for p in date_dir.iterdir() if p.is_dir() and p.name.startswith("run_")]):
                meta_path = run_dir / "run_metadata.json"
                if not meta_path.exists():
                    actions.append(
                        PruneAction(
                            run_id="",
                            run_dir=str(run_dir),
                            age_days=0,
                            deleted=[],
                            skipped_reason="missing_run_metadata",
                        )
                    )
                    continue

                meta = _load_json(meta_path)
                run_id = str(meta.get("run_id", "")).strip()
                generated_at_ms = int(meta.get("generated_at_ms", 0))
                if not run_id or generated_at_ms <= 0:
                    actions.append(
                        PruneAction(
                            run_id=run_id,
                            run_dir=str(run_dir),
                            age_days=0,
                            deleted=[],
                            skipped_reason="invalid_metadata",
                        )
                    )
                    continue

                age_days = int(max(0, (now_ms - generated_at_ms) // day_ms))
                if age_days <= int(keep_deep_days):
                    actions.append(
                        PruneAction(
                            run_id=run_id,
                            run_dir=str(run_dir),
                            age_days=age_days,
                            deleted=[],
                            skipped_reason="within_retention",
                        )
                    )
                    continue

                if not _run_known(con, run_id=run_id):
                    actions.append(
                        PruneAction(
                            run_id=run_id,
                            run_dir=str(run_dir),
                            age_days=age_days,
                            deleted=[],
                            skipped_reason="run_not_in_registry",
                        )
                    )
                    continue

                if _run_has_deployed(con, run_id=run_id):
                    actions.append(
                        PruneAction(
                            run_id=run_id,
                            run_dir=str(run_dir),
                            age_days=age_days,
                            deleted=[],
                            skipped_reason="has_deployed_configs",
                        )
                    )
                    continue

                deep_dirs = [run_dir / "sweeps", run_dir / "replays"]
                if prune_logs:
                    deep_dirs.append(run_dir / "logs")

                deleted: list[str] = []
                for d in deep_dirs:
                    if not d.exists():
                        continue
                    deleted.append(str(d))
                    if not dry_run:
                        shutil.rmtree(d)

                if not dry_run and deleted:
                    prune_marker = {
                        "pruned_at_ms": now_ms,
                        "keep_deep_days": int(keep_deep_days),
                        "deleted": deleted,
                    }
                    (run_dir / "prune.json").write_text(json.dumps(prune_marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")

                actions.append(
                    PruneAction(
                        run_id=run_id,
                        run_dir=str(run_dir),
                        age_days=age_days,
                        deleted=deleted,
                        skipped_reason=None,
                    )
                )
    finally:
        con.close()

    return actions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prune factory artifacts with a retention policy.")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root directory (default: artifacts).")
    ap.add_argument(
        "--registry-db",
        default="",
        help="Registry DB path (default: artifacts/registry/registry.sqlite).",
    )
    ap.add_argument("--keep-deep-days", type=int, default=14, help="Days to keep deep artifacts (default: 14).")
    ap.add_argument("--prune-logs", action="store_true", help="Also prune logs/ directories.")
    ap.add_argument("--dry-run", action="store_true", help="Do not delete anything; only report actions.")
    ap.add_argument("--now-ms", type=int, default=0, help="Override now timestamp (ms) for testing.")
    args = ap.parse_args(argv)

    artifacts_root = (AIQ_ROOT / str(args.artifacts_dir)).resolve()
    registry_db = Path(args.registry_db).expanduser().resolve() if args.registry_db else default_registry_db_path(artifacts_root=artifacts_root)
    now_ms = int(args.now_ms) if int(args.now_ms) > 0 else None

    actions = prune_artifacts(
        artifacts_root=artifacts_root,
        registry_db=registry_db,
        keep_deep_days=int(args.keep_deep_days),
        prune_logs=bool(args.prune_logs),
        dry_run=bool(args.dry_run),
        override_now_ms=now_ms,
    )

    pruned = [a for a in actions if a.deleted]
    skipped = [a for a in actions if a.skipped_reason]
    _stderr(
        f"[prune] scanned={len(actions)} pruned={len(pruned)} skipped={len(skipped)} dry_run={bool(args.dry_run)}"
    )
    _write_json({"actions": [a.__dict__ for a in actions]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
