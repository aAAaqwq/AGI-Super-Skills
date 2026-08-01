#!/usr/bin/env python3
"""Idempotently commit a successfully delivered scan to the dedup state."""

import argparse
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
DEFAULT_SCAN = os.path.join(DATA_DIR, "binance_raw_posts.json")
STATE_FILE = os.path.join(DATA_DIR, "binance_square_last_scan.json")
MAX_SEEN = 500


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def append_unique(items, values):
    result = list(items or [])
    known = set(result)
    for value in values:
        if value and value not in known:
            result.append(value)
            known.add(value)
    return result[-MAX_SEEN:]


def build_state(scan, existing):
    if scan.get("status") != "ok":
        raise ValueError("Refusing to commit a scan whose status is not 'ok'.")
    scanned_at = scan.get("scanned_at")
    if not scanned_at:
        raise ValueError("Refusing to commit a scan without scanned_at.")

    posts = scan.get("posts") or []
    urls = [post.get("url", "") for post in posts]
    texts = [(post.get("text") or "")[:100] for post in posts]
    previous_scan = existing.get("last_scan") or ""

    return {
        "seen_urls": append_unique(existing.get("seen_urls"), urls),
        "seen_texts": append_unique(existing.get("seen_texts"), texts),
        "last_scan": max(previous_scan, scanned_at),
    }


def atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp-{os.getpid()}"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scan", nargs="?", default=DEFAULT_SCAN)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the resulting counts without changing state",
    )
    args = parser.parse_args()

    scan = load_json(args.scan)
    existing = load_json(
        STATE_FILE,
        default={"seen_urls": [], "seen_texts": [], "last_scan": None},
    )
    state = build_state(scan, existing)

    if not args.dry_run:
        atomic_write_json(STATE_FILE, state)

    result = {
        "status": "dry-run" if args.dry_run else "committed",
        "scan": args.scan,
        "last_scan": state["last_scan"],
        "seen_urls": len(state["seen_urls"]),
        "seen_texts": len(state["seen_texts"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        sys.exit(1)
