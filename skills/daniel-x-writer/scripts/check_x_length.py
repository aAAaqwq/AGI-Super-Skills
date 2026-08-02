#!/usr/bin/env python3
"""Conservatively estimate the weighted length of an X post."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def weighted_length(text: str) -> int:
    """Count ASCII as 1, non-ASCII as 2, and each URL as 23.

    This intentionally favors false over-limit warnings for Chinese posts. The
    live X composer remains authoritative because platform rules can change.
    """

    total = 0
    cursor = 0

    for match in URL_RE.finditer(text):
        total += sum(1 if ord(char) <= 0x7F else 2 for char in text[cursor : match.start()])
        total += 23
        cursor = match.end()

    total += sum(1 if ord(char) <= 0x7F else 2 for char in text[cursor:])
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Conservatively check an X post's weighted character length."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="UTF-8 draft file. Reads standard input when omitted.",
    )
    parser.add_argument("--limit", type=int, default=280, help="Hard ceiling (default: 280).")
    parser.add_argument(
        "--target",
        type=int,
        default=260,
        help="Preferred ceiling with editing room (default: 260).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit <= 0 or args.target <= 0 or args.target > args.limit:
        raise SystemExit("target and limit must be positive, with target <= limit")

    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    length = weighted_length(text.rstrip("\n"))
    status = "safe" if length <= args.target else "fits" if length <= args.limit else "over"

    print(
        json.dumps(
            {
                "weighted_length": length,
                "target": args.target,
                "limit": args.limit,
                "remaining": args.limit - length,
                "status": status,
            },
            ensure_ascii=False,
        )
    )
    return 2 if status == "over" else 0


if __name__ == "__main__":
    raise SystemExit(main())
