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
    parser.add_argument(
        "--degraded",
        metavar="REASON",
        help="mark the rendered report as cached after a failed refresh",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        payload = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("committed report is not readable JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("committed report must be a JSON object")
    message = render_telegram(payload)
    if args.degraded:
        lines = message.splitlines()
        message = "\n".join(
            [
                lines[0],
                f"🔴 状态：本轮数据更新失败，{args.degraded}",
                "📌 以下为最近一次成功结果",
                *lines[1:],
            ]
        )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
