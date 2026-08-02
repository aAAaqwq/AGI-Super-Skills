#!/usr/bin/env python3
"""Repair local latest pointers from one verified SUCCEEDED shadow attempt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.pipeline import (
    PipelineConfig,
    repair_latest_from_succeeded_attempt,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logical-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args(argv)
    result = repair_latest_from_succeeded_attempt(
        PipelineConfig(
            mode="real",
            output_dir=args.output_dir,
            database=args.database,
            no_send=True,
        ),
        logical_run_id=args.logical_run_id,
    )
    print(
        json.dumps(
            {
                "logical_run_id": result.logical_run_id,
                "attempt_id": result.attempt_id,
                "latest_pointer": str(result.latest_pointer),
                "latest_json": str(result.latest_json),
                "latest_markdown": str(result.latest_markdown),
                "repair_only": True,
                "no_send": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
