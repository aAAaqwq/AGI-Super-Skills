#!/usr/bin/env python3
"""Validate deterministic repository contracts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repository_model import (
    AVAILABLE_CHECKS,
    render_json,
    render_text,
    validate_repository,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository or fixture root (default: current directory)",
    )
    parser.add_argument(
        "--checks",
        default=",".join(AVAILABLE_CHECKS),
        help=f"comma-separated checks: {', '.join(AVAILABLE_CHECKS)}",
    )
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="make documented drift warnings fail the command",
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=25,
        help="maximum error and warning details to print (default: 25 each)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if arguments.max_details < 1:
        raise SystemExit("--max-details must be at least 1")

    requested_checks = [
        check.strip() for check in arguments.checks.split(",") if check.strip()
    ]
    try:
        report = validate_repository(arguments.root, requested_checks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    output = (
        render_json(report, arguments.max_details)
        if arguments.format == "json"
        else render_text(report, arguments.max_details)
    )
    sys.stdout.write(output)
    return 1 if report.error_count or (
        arguments.warnings_as_errors and report.warning_count
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
