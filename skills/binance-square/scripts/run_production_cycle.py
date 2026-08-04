#!/usr/bin/env python3
"""Run one local no-send cycle: refresh Feed, then build the smart-money radar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.contracts import ContractViolation  # noqa: E402
from scanner.discovery import validate_feed_discovery_result  # noqa: E402


@dataclass(frozen=True, slots=True)
class ProductionCycleConfig:
    project_dir: Path = PROJECT_DIR
    signals_json: Path | None = None
    leaderboard_seed_evidence: Path | None = None
    output_dir: Path = PROJECT_DIR / "data" / "v4" / "runs"
    database: Path = PROJECT_DIR / "data" / "v4" / "radar.sqlite"
    job_namespace: str = "production"
    production_job_id: str = "binance-square-shadow-v4"
    smart_money_square_mapping_evidence: Path | None = None
    smart_money_square_mapping_catalog: Path | None = None
    limit: int = 200


def _subprocess_runner(
    command: list[str],
    *,
    heartbeat_interval_seconds: float = 30.0,
) -> None:
    """Run a foreground child while proving liveness to command schedulers."""

    if heartbeat_interval_seconds <= 0:
        raise ValueError("heartbeat interval must be positive")
    process = subprocess.Popen(command, cwd=PROJECT_DIR)
    started = time.monotonic()
    child_name = Path(command[1] if len(command) > 1 else command[0]).name
    try:
        while True:
            try:
                return_code = process.wait(timeout=heartbeat_interval_seconds)
                break
            except subprocess.TimeoutExpired:
                elapsed = int(time.monotonic() - started)
                print(
                    f"[HEARTBEAT] child={child_name} elapsed_seconds={elapsed}",
                    file=sys.stderr,
                    flush=True,
                )
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)


def run_production_cycle(
    config: ProductionCycleConfig,
    *,
    runner: Callable[[list[str]], None] = _subprocess_runner,
) -> None:
    """Execute exactly two ordered, foreground, no-send commands."""

    scraper = config.project_dir / "scripts" / "binance_scraper.py"
    radar = config.project_dir / "scripts" / "run_radar.py"
    latest_snapshot = config.project_dir / "data" / "binance_raw_posts.json"
    try:
        previous_latest_content = latest_snapshot.read_bytes()
    except OSError:
        previous_latest_content = None
    runner([sys.executable, str(scraper)])
    try:
        latest_content = latest_snapshot.read_bytes()
        latest_payload = json.loads(latest_content)
        immutable_snapshot = Path(latest_payload["snapshot_file"])
        immutable_content = immutable_snapshot.read_bytes()
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Feed refresh did not produce an immutable snapshot"
        ) from exc
    if (
        previous_latest_content is not None
        and latest_content == previous_latest_content
    ):
        raise RuntimeError("Feed scraper did not refresh the observed latest snapshot")
    if latest_payload.get("status") != "ok" or not latest_payload.get("scanned_at"):
        raise RuntimeError(
            "Feed refresh result is not a successful timestamped snapshot"
        )
    try:
        _, coverage_status, termination_reason, discovery_result = (
            validate_feed_discovery_result(latest_payload, allow_legacy=False)
        )
    except ContractViolation as exc:
        raise RuntimeError(
            "Feed refresh result has no valid coverage contract"
        ) from exc
    if not (
        latest_payload.get("eligible_for_coverage_promotion") is True
        and coverage_status == "BOUNDED_COMPLETE"
        and termination_reason == "EXHAUSTED"
        and discovery_result is not None
        and discovery_result.get("minimum_target_met") is True
        and latest_payload.get("eligible_snapshot_file")
        == latest_payload.get("snapshot_file")
    ):
        raise RuntimeError("Feed refresh result is not eligible for coverage promotion")
    if immutable_content != latest_content:
        raise RuntimeError(
            "immutable Feed snapshot differs from the refreshed latest payload"
        )
    eligible_pointer = config.project_dir / "data" / "binance_raw_posts_eligible.json"
    try:
        eligible_content = eligible_pointer.read_bytes()
    except OSError as exc:
        raise RuntimeError(
            "Feed refresh did not produce an eligible Feed pointer"
        ) from exc
    if eligible_content != latest_content:
        raise RuntimeError(
            "eligible Feed pointer differs from the refreshed latest payload"
        )
    radar_command = [
        sys.executable,
        str(radar),
        "--real",
        "--smart-money",
        "--official-news",
        "--input-snapshot",
        str(immutable_snapshot),
    ]
    if config.signals_json is not None:
        radar_command.extend(["--signals-json", str(config.signals_json)])
    if config.leaderboard_seed_evidence is not None:
        radar_command.extend(
            [
                "--leaderboard-seed-evidence",
                str(config.leaderboard_seed_evidence),
            ]
        )
    radar_command.extend(
        [
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
    )
    if (
        config.smart_money_square_mapping_evidence is not None
        and config.smart_money_square_mapping_catalog is not None
    ):
        raise ValueError("use either one Smart Money mapping artifact or one catalog")
    if config.smart_money_square_mapping_catalog is not None:
        radar_command.extend(
            [
                "--smart-money-square-mapping-catalog",
                str(config.smart_money_square_mapping_catalog),
            ]
        )
    elif config.smart_money_square_mapping_evidence is not None:
        radar_command.extend(
            [
                "--smart-money-square-mapping-evidence",
                str(config.smart_money_square_mapping_evidence),
            ]
        )
    runner(radar_command)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals-json", type=Path)
    parser.add_argument("--leaderboard-seed-evidence", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "data" / "v4" / "runs",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_DIR / "data" / "v4" / "radar.sqlite",
    )
    parser.add_argument("--job-namespace", default="production")
    parser.add_argument("--production-job-id", default="binance-square-shadow-v4")
    identity_mapping = parser.add_mutually_exclusive_group()
    identity_mapping.add_argument("--smart-money-square-mapping-evidence", type=Path)
    identity_mapping.add_argument("--smart-money-square-mapping-catalog", type=Path)
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
            leaderboard_seed_evidence=args.leaderboard_seed_evidence,
            output_dir=args.output_dir,
            database=args.database,
            job_namespace=args.job_namespace,
            production_job_id=args.production_job_id,
            smart_money_square_mapping_evidence=(
                args.smart_money_square_mapping_evidence
            ),
            smart_money_square_mapping_catalog=(
                args.smart_money_square_mapping_catalog
            ),
            limit=args.limit,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
