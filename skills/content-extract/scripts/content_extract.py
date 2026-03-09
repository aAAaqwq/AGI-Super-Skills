#!/usr/bin/env python3
"""content-extract: deterministic MinerU-only extractor for OpenClaw.

Why this exists:
- OpenClaw's `web_fetch` is a tool, not available inside scripts.
- This script provides a stable "fallback engine" that the agent can call
  after probing with `web_fetch`.

It wraps mineru-extract's MCP-aligned script and returns a compact JSON contract.

Usage:
  python3 scripts/content_extract.py --url <URL> [--model MinerU-HTML]

Output (stdout):
  { ok, source_url, engine, markdown, artifacts, sources, notes }

"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys


def _find_mineru_wrapper() -> str:
    """Locate mineru_parse_documents.py relative to this script or via env."""
    # 1. Env override
    if v := os.environ.get("MINERU_WRAPPER_PATH"):
        return v

    here = pathlib.Path(__file__).resolve().parent
    # 2. Monorepo sibling: ../mineru-extract/scripts/mineru_parse_documents.py
    candidate = here.parent.parent / "mineru-extract" / "scripts" / "mineru_parse_documents.py"
    if candidate.exists():
        return str(candidate)

    # 3. OpenClaw workspace default
    default = pathlib.Path.home() / ".openclaw" / "workspace" / "skills" / "mineru-extract" / "scripts" / "mineru_parse_documents.py"
    if default.exists():
        return str(default)

    raise FileNotFoundError(
        "Cannot find mineru_parse_documents.py. "
        "Set MINERU_WRAPPER_PATH env or install mineru-extract skill as a sibling directory."
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", default="MinerU-HTML")
    ap.add_argument("--language", default="ch")
    ap.add_argument("--emit-markdown", action="store_true", default=True)
    ap.add_argument("--max-chars", type=int, default=20000)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    try:
        wrapper = _find_mineru_wrapper()
    except FileNotFoundError as e:
        out = {
            "ok": False,
            "source_url": args.url,
            "engine": "mineru",
            "markdown": None,
            "artifacts": {},
            "sources": [args.url],
            "notes": [str(e)],
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 2

    cmd = [
        sys.executable,
        wrapper,
        "--file-sources",
        args.url,
        "--model-version",
        args.model,
        "--language",
        args.language,
        "--emit-markdown",
        "--max-chars",
        str(args.max_chars),
    ]
    if args.force:
        cmd.append("--force")

    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode not in (0, 1):
        out = {
            "ok": False,
            "source_url": args.url,
            "engine": "mineru",
            "markdown": None,
            "artifacts": {},
            "sources": [args.url],
            "notes": [
                "mineru wrapper crashed",
                (p.stderr or "").strip()[:500],
            ],
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 2

    try:
        j = json.loads(p.stdout)
    except Exception:
        out = {
            "ok": False,
            "source_url": args.url,
            "engine": "mineru",
            "markdown": None,
            "artifacts": {},
            "sources": [args.url],
            "notes": ["mineru wrapper returned non-json", (p.stdout or "")[:300]],
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 2

    if not j.get("items"):
        out = {
            "ok": False,
            "source_url": args.url,
            "engine": "mineru",
            "markdown": None,
            "artifacts": {},
            "sources": [args.url],
            "notes": ["no items", json.dumps(j.get("errors") or [], ensure_ascii=False)[:800]],
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 1

    item = j["items"][0]
    sources = [args.url]
    if item.get("full_zip_url"):
        sources.append(item["full_zip_url"])
    if item.get("markdown_path"):
        sources.append(item["markdown_path"])

    out = {
        "ok": True,
        "source_url": args.url,
        "engine": "mineru",
        "markdown": item.get("markdown"),
        "artifacts": {
            "out_dir": item.get("out_dir"),
            "markdown_path": item.get("markdown_path"),
            "zip_path": item.get("zip_path"),
            "task_id": item.get("task_id"),
            "cache_key": item.get("cache_key"),
        },
        "sources": sources,
        "notes": ["mcp-aligned: mineru_parse_documents"],
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
