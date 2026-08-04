#!/usr/bin/env python3
"""Render one committed radar report as the deterministic Telegram body."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.reports import render_telegram  # noqa: E402


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        payload = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("committed report is not readable JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("committed report must be a JSON object")
    print(render_telegram(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
