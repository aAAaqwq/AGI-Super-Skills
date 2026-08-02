#!/usr/bin/env python3
"""Collect public Binance Smart Money PNL/ROI TOP30 evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.contracts import ContractViolation
from scanner.smart_money import (
    RANKING_TYPES,
    collect_smart_money,
    default_evidence_filename,
    write_evidence_atomic,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ranking-type",
        action="append",
        choices=RANKING_TYPES,
        dest="ranking_types",
        help="ranking to collect; repeat to override the default PNL+ROI",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=10,
        help="contract parameter; only 10 is valid (TOP30 is three pages)",
    )
    parser.add_argument(
        "--without-profiles",
        action="store_true",
        help="skip public topTraderId profile enrichment",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "data" / "v4" / "evidence",
    )
    parser.add_argument("--output", type=Path, help="explicit immutable JSON path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    ranking_types = tuple(args.ranking_types or RANKING_TYPES)
    try:
        document = collect_smart_money(
            ranking_types=ranking_types,
            rows_per_page=args.rows,
            include_profiles=not args.without_profiles,
            timeout=args.timeout,
        )
        output_path = args.output or (
            args.output_dir / default_evidence_filename(document)
        )
        receipt = write_evidence_atomic(document, output_path)
    except (ContractViolation, OSError) as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": str(exc)}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": document["status"],
                "ranking_types": ranking_types,
                "unique_top_trader_count": document["unique_top_trader_count"],
                "profile_coverage": {
                    key: document["profile_enrichment"][key]
                    for key in (
                        "enabled",
                        "status",
                        "expected",
                        "completed",
                        "failed",
                        "coverage_ratio",
                    )
                },
                "receipt": asdict(receipt),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
