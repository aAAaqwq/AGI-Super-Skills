#!/usr/bin/env python3
"""Run one local no-send cycle: refresh Feed, then build the smart-money radar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable


PROJECT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class ProductionCycleConfig:
    project_dir: Path = PROJECT_DIR
    signals_json: Path = PROJECT_DIR / "data" / "signal_check_input.json"
    output_dir: Path = PROJECT_DIR / "data" / "v4" / "runs"
    database: Path = PROJECT_DIR / "data" / "v4" / "radar.sqlite"
    job_namespace: str = "production"
    production_job_id: str = "binance-square-shadow-v4"
    smart_money_square_mapping_evidence: Path | None = None
    limit: int = 200


def _subprocess_runner(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_DIR, check=True)


def run_production_cycle(
    config: ProductionCycleConfig,
    *,
    runner: Callable[[list[str]], None] = _subprocess_runner,
) -> None:
    """Execute exactly two ordered, foreground, no-send commands."""

    scraper = config.project_dir / "scripts" / "binance_scraper.py"
    radar = config.project_dir / "scripts" / "run_radar.py"
    runner([sys.executable, str(scraper)])
    latest_snapshot = config.project_dir / "data" / "binance_raw_posts.json"
    try:
        latest_content = latest_snapshot.read_bytes()
        latest_payload = json.loads(latest_content)
        immutable_snapshot = Path(latest_payload["snapshot_file"])
        immutable_content = immutable_snapshot.read_bytes()
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Feed refresh did not produce an immutable snapshot") from exc
    if latest_payload.get("status") != "ok" or not latest_payload.get("scanned_at"):
        raise RuntimeError("Feed refresh result is not a successful timestamped snapshot")
    if immutable_content != latest_content:
        raise RuntimeError("immutable Feed snapshot differs from the refreshed latest payload")
    radar_command = [
        sys.executable,
        str(radar),
        "--real",
        "--smart-money",
        "--official-news",
        "--input-snapshot",
        str(immutable_snapshot),
        "--signals-json",
        str(config.signals_json),
        "--output-dir",
        str(config.output_dir),
        "--database",
        str(config.database),
        "--job-namespace",
        config.job_namespace,
        "--production-job-id",
        config.production_job_id,
        "--limit",
        str(config.limit),
        "--no-send",
    ]
    if config.smart_money_square_mapping_evidence is not None:
        radar_command.extend(
            [
                "--smart-money-square-mapping-evidence",
                str(config.smart_money_square_mapping_evidence),
            ]
        )
    runner(radar_command)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals-json", type=Path, default=ProductionCycleConfig.signals_json)
    parser.add_argument("--output-dir", type=Path, default=ProductionCycleConfig.output_dir)
    parser.add_argument("--database", type=Path, default=ProductionCycleConfig.database)
    parser.add_argument("--job-namespace", default="production")
    parser.add_argument("--production-job-id", default="binance-square-shadow-v4")
    parser.add_argument("--smart-money-square-mapping-evidence", type=Path)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--no-send", action="store_true", default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    if args.limit < 1 or args.limit > 200:
        raise SystemExit("--limit must be between 1 and 200")
    run_production_cycle(
        ProductionCycleConfig(
            signals_json=args.signals_json,
            output_dir=args.output_dir,
            database=args.database,
            job_namespace=args.job_namespace,
            production_job_id=args.production_job_id,
            smart_money_square_mapping_evidence=(
                args.smart_money_square_mapping_evidence
            ),
            limit=args.limit,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
