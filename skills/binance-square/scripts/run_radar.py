#!/usr/bin/env python3
"""Run the v4 Binance Square radar in local shadow mode only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.pipeline import PipelineConfig, run_shadow_radar


def _limit(value: str) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > 200:
        raise argparse.ArgumentTypeError("limit must be between 1 and 200")
    return parsed


def _post_id(value: str) -> str:
    parsed = value.strip()
    if not parsed.isdecimal():
        raise argparse.ArgumentTypeError("dedup baseline post IDs must be numeric")
    return parsed


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--real", action="store_true", help="refresh public post details and Futures evidence")
    mode.add_argument("--fixture", type=Path, help="offline Square fixture directory")
    parser.add_argument("--clock", help="UTC decision time; real mode defaults to Binance server time")
    parser.add_argument(
        "--input-snapshot",
        type=Path,
        default=PROJECT_DIR / "data" / "binance_raw_posts.json",
    )
    parser.add_argument(
        "--signals-json",
        type=Path,
        default=PROJECT_DIR / "data" / "signal_check_input.json",
    )
    parser.add_argument(
        "--leaderboard-seed-evidence",
        type=Path,
        help=(
            "fixed, timestamped profile-seed evidence; never treated as a "
            "complete TOP30 leaderboard"
        ),
    )
    parser.add_argument(
        "--smart-money",
        action="store_true",
        help=(
            "explicitly collect public read-only Binance Futures Smart Money "
            "PNL/ROI TOP30 evidence"
        ),
    )
    parser.add_argument(
        "--smart-money-fixture",
        type=Path,
        help=(
            "inject an integrity-verified Smart Money evidence JSON instead "
            "of making Smart Money network requests"
        ),
    )
    parser.add_argument(
        "--smart-money-square-mapping-evidence",
        type=Path,
        help=(
            "explicit SHA-verified topTraderId-to-squareUid evidence; names are "
            "never used for identity mapping"
        ),
    )
    parser.add_argument(
        "--official-news",
        action="store_true",
        help="collect Binance-hosted official announcements from the strict prior 24h",
    )
    parser.add_argument("--limit", type=_limit, default=200)
    parser.add_argument(
        "--job-namespace",
        default="production",
        help="explicit run identity namespace (for example production or canary-a)",
    )
    parser.add_argument(
        "--production-job-id",
        default="binance-square-shadow-v4",
        help="stable logical job identity; never inferred from the database path",
    )
    parser.add_argument(
        "--dedup-baseline-post-id",
        type=_post_id,
        action="append",
        default=None,
        help=(
            "explicit replay-only baseline ID; repeat for multiple posts. "
            "Without it, replay new/duplicate counts remain NOT_COMPUTED"
        ),
    )
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
    parser.add_argument(
        "--no-send",
        action="store_true",
        default=True,
        help="retained explicitly; shadow mode never sends Telegram",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    result = run_shadow_radar(
        PipelineConfig(
            mode="real" if args.real else "fixture",
            output_dir=args.output_dir,
            database=args.database,
            decision_at=args.clock,
            fixture_dir=args.fixture,
            input_snapshot=args.input_snapshot,
            signals_json=args.signals_json,
            leaderboard_seed_evidence=args.leaderboard_seed_evidence,
            smart_money_enabled=(
                args.smart_money or args.smart_money_fixture is not None
            ),
            smart_money_fixture=args.smart_money_fixture,
            smart_money_square_mapping_evidence=(
                args.smart_money_square_mapping_evidence
            ),
            official_news_enabled=args.official_news,
            limit=args.limit,
            job_namespace=args.job_namespace,
            production_job_id=args.production_job_id,
            no_send=True,
            dedup_baseline_post_ids=(
                frozenset(args.dedup_baseline_post_id)
                if args.dedup_baseline_post_id is not None
                else None
            ),
        )
    )
    print(
        json.dumps(
            {
                "logical_run_id": result.logical_run_id,
                "attempt_id": result.attempt_id,
                "raw_json": str(result.raw_json),
                "market_json": str(result.market_json),
                "report_json": str(result.report_json),
                "report_markdown": str(result.report_markdown),
                "latest_json": str(result.latest_json),
                "latest_markdown": str(result.latest_markdown),
                "latest_pointer": str(result.latest_pointer),
                "smart_money_json": (
                    str(result.smart_money_json)
                    if result.smart_money_json is not None
                    else None
                ),
                "market_catalog_json": (
                    str(result.market_catalog_json)
                    if result.market_catalog_json is not None
                    else None
                ),
                "official_news_json": (
                    str(result.official_news_json)
                    if result.official_news_json is not None
                    else None
                ),
                "no_send": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
