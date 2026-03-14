#!/usr/bin/env python3
"""MinerU official API extractor (single URL, low-level).

Primary use: submit a URL (including HTML pages) to MinerU, poll until done,
download the result zip, and extract Markdown.

Designed to be called from OpenClaw skills via `exec`.

Env (load order):
- process env
- .env next to this script
- ../.env (skill root)

Required:
- MINERU_TOKEN: Bearer token from mineru.net

Optional:
- MINERU_API_BASE (default: https://mineru.net)
- OPENCLAW_WORKSPACE: workspace root for output (default: ~/.openclaw/workspace)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile


def _load_dotenv(path: pathlib.Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _bootstrap_env() -> None:
    here = pathlib.Path(__file__).resolve()
    _load_dotenv(here.parent / ".env")
    _load_dotenv(here.parent.parent / ".env")


def _default_workspace() -> pathlib.Path:
    if v := os.environ.get("OPENCLAW_WORKSPACE"):
        return pathlib.Path(v)
    return pathlib.Path.home() / ".openclaw" / "workspace"


def _http_json(method: str, url: str, *, headers: dict[str, str] | None = None, payload: dict | None = None, timeout: int = 60) -> dict:
    data = None
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url=url, data=data, method=method.upper(), headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:500]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e}") from e


def _http_bytes(url: str, *, headers: dict[str, str] | None = None, timeout: int = 120) -> bytes:
    hdrs = {}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url=url, method="GET", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:500]}") from e


def create_task(*, api_base: str, token: str, source_url: str, model_version: str, is_ocr: bool | None, enable_formula: bool | None, enable_table: bool | None, language: str | None, page_ranges: str | None, extra_formats: list[str] | None) -> str:
    endpoint = api_base.rstrip("/") + "/api/v4/extract/task"
    payload: dict = {"url": source_url, "model_version": model_version}
    if is_ocr is not None:
        payload["is_ocr"] = bool(is_ocr)
    if enable_formula is not None:
        payload["enable_formula"] = bool(enable_formula)
    if enable_table is not None:
        payload["enable_table"] = bool(enable_table)
    if language:
        payload["language"] = language
    if page_ranges:
        payload["page_ranges"] = page_ranges
    if extra_formats:
        payload["extra_formats"] = extra_formats

    res = _http_json(
        "POST",
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
        timeout=90,
    )
    if res.get("code") != 0:
        raise RuntimeError(f"MinerU create_task failed: {res}")
    data = res.get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"MinerU create_task missing task_id: {res}")
    return str(task_id)


def poll_task(*, api_base: str, token: str, task_id: str, timeout_sec: int = 600, poll_interval: float = 2.0) -> dict:
    endpoint = api_base.rstrip("/") + f"/api/v4/extract/task/{task_id}"
    start = time.time()
    last_state = None
    while True:
        res = _http_json("GET", endpoint, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if res.get("code") != 0:
            raise RuntimeError(f"MinerU poll failed: {res}")
        data = res.get("data") or {}
        state = data.get("state")
        if state and state != last_state:
            print(f"state={state}", file=sys.stderr)
            last_state = state

        if state == "done":
            return data
        if state == "failed":
            err = data.get("err_msg") or "(no err_msg)"
            raise RuntimeError(f"MinerU task failed: {err}")

        if time.time() - start > timeout_sec:
            raise RuntimeError(f"MinerU poll timeout after {timeout_sec}s (last state={state})")
        time.sleep(poll_interval)


def extract_markdown_from_zip(zip_bytes: bytes, out_dir: pathlib.Path) -> tuple[pathlib.Path | None, list[pathlib.Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[pathlib.Path] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        z.extractall(out_dir)

    for p in out_dir.rglob("*"):
        if p.is_file():
            extracted.append(p)

    md_files = [p for p in extracted if p.suffix.lower() in [".md", ".markdown"]]
    if not md_files:
        return None, extracted

    def score(p: pathlib.Path) -> tuple[int, int]:
        name = p.name.lower()
        penalty = 0
        if "readme" in name:
            penalty += 2
        if "layout" in name or "span" in name or "debug" in name:
            penalty += 3
        size = p.stat().st_size
        return (-penalty, size)

    md_files_sorted = sorted(md_files, key=score, reverse=True)
    return md_files_sorted[0], extracted


def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s.strip())
    return s[:120] if len(s) > 120 else s


def main() -> int:
    _bootstrap_env()

    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="URL to parse (supports HTML/PDF/Office/images).")
    ap.add_argument("--model", dest="model_version", default=None, help="pipeline | vlm | MinerU-HTML (required for HTML).")
    ap.add_argument("--api-base", default=os.environ.get("MINERU_API_BASE", "https://mineru.net"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--poll-interval", type=float, default=2.0)

    ap.add_argument("--ocr", dest="is_ocr", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--formula", dest="enable_formula", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--table", dest="enable_table", action=argparse.BooleanOptionalAction, default=None)
    ap.add_argument("--language", default=None)
    ap.add_argument("--page-ranges", default=None)
    ap.add_argument("--extra-formats", default=None, help='Comma-separated: docx,html,latex (md+json are default).')

    ap.add_argument("--out", default=None, help="Output directory (default: workspace/mineru/<task_id>).")
    ap.add_argument("--print", dest="do_print", action="store_true", help="Print extracted markdown to stdout.")
    ap.add_argument("--max-chars", type=int, default=12000, help="When --print, max chars to print.")

    args = ap.parse_args()

    token = os.environ.get("MINERU_TOKEN")
    if not token:
        print("Missing MINERU_TOKEN (set env or skill .env)", file=sys.stderr)
        return 2

    model_version = args.model_version
    if not model_version:
        lower = args.source.lower()
        if lower.endswith((".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg")):
            model_version = "pipeline"
        else:
            model_version = "MinerU-HTML"

    extra_formats = None
    if args.extra_formats:
        extra_formats = [s.strip() for s in args.extra_formats.split(",") if s.strip()]

    task_id = create_task(
        api_base=args.api_base,
        token=token,
        source_url=args.source,
        model_version=model_version,
        is_ocr=args.is_ocr,
        enable_formula=args.enable_formula,
        enable_table=args.enable_table,
        language=args.language,
        page_ranges=args.page_ranges,
        extra_formats=extra_formats,
    )

    data = poll_task(api_base=args.api_base, token=token, task_id=task_id, timeout_sec=args.timeout, poll_interval=args.poll_interval)
    full_zip_url = data.get("full_zip_url")
    if not full_zip_url:
        raise RuntimeError(f"No full_zip_url in done task: {data}")

    zip_bytes = _http_bytes(full_zip_url, timeout=180)

    workspace = _default_workspace()
    base_out = pathlib.Path(args.out) if args.out else (workspace / "mineru" / sanitize_filename(task_id))
    base_out.mkdir(parents=True, exist_ok=True)
    zip_path = base_out / "result.zip"
    zip_path.write_bytes(zip_bytes)

    md_path, extracted = extract_markdown_from_zip(zip_bytes, base_out)

    summary = {
        "task_id": task_id,
        "state": data.get("state"),
        "model_version": model_version,
        "full_zip_url": full_zip_url,
        "out_dir": str(base_out),
        "zip_path": str(zip_path),
        "markdown_path": str(md_path) if md_path else None,
        "extracted_files": len(extracted),
    }
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    if args.do_print:
        if not md_path or not md_path.exists():
            print("(no markdown file found)")
            return 0
        text = md_path.read_text(encoding="utf-8", errors="replace")
        if args.max_chars and len(text) > args.max_chars:
            text = text[: args.max_chars] + "\n\n[TRUNCATED]"
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
