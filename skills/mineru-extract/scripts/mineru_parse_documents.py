#!/usr/bin/env python3
"""MCP-aligned wrapper for MinerU official API.

Goal: expose a stable, workflow-friendly interface similar to MinerU MCP's `parse_documents`.

- Accept `file_sources` (comma/newline-separated URLs or local file paths).
- For URLs: use MinerU /api/v4/extract/task (single) with model_version auto/default.
- Download result zip + extract main Markdown.
- Return a JSON result contract on stdout.

Notes
- This is NOT an MCP server. It's a script meant to be called by OpenClaw skills via exec.
- Secrets loaded from .env (skill root) or environment.

Env
- MINERU_TOKEN (required): bearer token
- MINERU_API_BASE (optional): default https://mineru.net

"""

from __future__ import annotations

import argparse
import hashlib
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


def _default_workspace() -> pathlib.Path:
    """Return workspace root, preferring env override."""
    if v := os.environ.get("OPENCLAW_WORKSPACE"):
        return pathlib.Path(v)
    return pathlib.Path.home() / ".openclaw" / "workspace"


WORKSPACE = _default_workspace()
CACHE_ROOT = WORKSPACE / "mineru-cache"


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


def _http_json(method: str, url: str, *, headers: dict[str, str] | None = None, payload: dict | None = None, timeout: int = 60) -> dict:
    data = None
    hdrs = {"Accept": "application/json", "User-Agent": "openclaw-mineru"}
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
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:800]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e}") from e


def _http_bytes(url: str, *, headers: dict[str, str] | None = None, timeout: int = 180) -> bytes:
    hdrs = {"User-Agent": "openclaw-mineru"}
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
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:800]}") from e


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _split_sources(s: str) -> list[str]:
    parts = re.split(r"[\n,]+", s)
    out = []
    for p in parts:
        x = p.strip()
        if x:
            out.append(x)
    return out


def _sanitize(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s.strip())
    return s[:120] if len(s) > 120 else s


def _cache_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _pick_model_version(source: str, model_version: str | None) -> str:
    if model_version:
        return model_version
    lower = source.lower()
    if lower.endswith((".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg")):
        return "pipeline"
    return "MinerU-HTML"


def create_task(*, api_base: str, token: str, payload: dict) -> str:
    endpoint = api_base.rstrip("/") + "/api/v4/extract/task"
    res = _http_json("POST", endpoint, headers={"Authorization": f"Bearer {token}"}, payload=payload, timeout=90)
    if res.get("code") != 0:
        raise RuntimeError(f"MinerU create_task failed: {res}")
    task_id = (res.get("data") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"MinerU create_task missing task_id: {res}")
    return str(task_id)


def poll_task(*, api_base: str, token: str, task_id: str, timeout_sec: int, poll_interval: float) -> dict:
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
            raise RuntimeError(f"MinerU task failed: {data.get('err_msg') or '(no err_msg)'}")
        if time.time() - start > timeout_sec:
            raise RuntimeError(f"MinerU poll timeout after {timeout_sec}s (last state={state})")
        time.sleep(poll_interval)


def extract_main_markdown(zip_bytes: bytes, out_dir: pathlib.Path) -> pathlib.Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        z.extractall(out_dir)

    md_files = [p for p in out_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".md", ".markdown")]
    if not md_files:
        return None

    def score(p: pathlib.Path) -> tuple[int, int]:
        name = p.name.lower()
        penalty = 0
        if "readme" in name:
            penalty += 2
        if "layout" in name or "span" in name or "debug" in name:
            penalty += 3
        return (-penalty, p.stat().st_size)

    md_files_sorted = sorted(md_files, key=score, reverse=True)
    return md_files_sorted[0]


def parse_one_url(*, api_base: str, token: str, source_url: str, enable_ocr: bool, language: str, page_ranges: str | None, model_version: str | None, enable_table: bool | None, enable_formula: bool | None, extra_formats: list[str] | None, timeout_sec: int, poll_interval: float, cache: bool, force: bool) -> dict:
    mv = _pick_model_version(source_url, model_version)

    payload: dict = {
        "url": source_url,
        "model_version": mv,
        "language": language,
    }
    payload["is_ocr"] = bool(enable_ocr)
    if page_ranges:
        payload["page_ranges"] = page_ranges
    if enable_table is not None:
        payload["enable_table"] = bool(enable_table)
    if enable_formula is not None:
        payload["enable_formula"] = bool(enable_formula)
    if extra_formats:
        payload["extra_formats"] = extra_formats

    key = _cache_key(payload)
    out_dir = CACHE_ROOT / key
    meta_path = out_dir / "meta.json"

    if cache and (not force) and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            md_path = pathlib.Path(meta.get("markdown_path") or "")
            if md_path and md_path.exists():
                meta["cached"] = True
                return meta
        except Exception:
            pass

    out_dir.mkdir(parents=True, exist_ok=True)
    task_id = create_task(api_base=api_base, token=token, payload=payload)
    data = poll_task(api_base=api_base, token=token, task_id=task_id, timeout_sec=timeout_sec, poll_interval=poll_interval)

    full_zip_url = data.get("full_zip_url")
    if not full_zip_url:
        raise RuntimeError(f"No full_zip_url in done task: {data}")
    zip_bytes = _http_bytes(full_zip_url, timeout=180)
    zip_path = out_dir / f"{_sanitize(task_id)}.zip"
    zip_path.write_bytes(zip_bytes)

    md_path = extract_main_markdown(zip_bytes, out_dir)

    result = {
        "ok": True,
        "source": source_url,
        "task_id": task_id,
        "state": data.get("state"),
        "model_version": mv,
        "language": language,
        "enable_ocr": bool(enable_ocr),
        "page_ranges": page_ranges,
        "full_zip_url": full_zip_url,
        "out_dir": str(out_dir),
        "zip_path": str(zip_path),
        "markdown_path": str(md_path) if md_path else None,
        "cached": False,
        "cache_key": key,
        "fetched_at": int(time.time()),
    }
    meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    _bootstrap_env()

    ap = argparse.ArgumentParser()
    ap.add_argument("--file-sources", required=True, help="Comma/newline separated URLs or local paths (MCP-style).")
    ap.add_argument("--enable-ocr", action="store_true", help="Enable OCR (maps to MinerU is_ocr).")
    ap.add_argument("--language", default="ch")
    ap.add_argument("--page-ranges", default=None)
    ap.add_argument("--model-version", default=None, help="pipeline | vlm | MinerU-HTML")
    ap.add_argument("--enable-table", default=None, choices=["true", "false"])
    ap.add_argument("--enable-formula", default=None, choices=["true", "false"])
    ap.add_argument("--extra-formats", default=None, help="Comma-separated: docx,html,latex")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--poll-interval", type=float, default=3.0)
    ap.add_argument("--cache", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--emit-markdown", action="store_true", help="Include markdown text in JSON (can be large).")
    ap.add_argument("--max-chars", type=int, default=20000, help="When --emit-markdown, truncate markdown to this many chars.")

    args = ap.parse_args()

    token = os.environ.get("MINERU_TOKEN")
    if not token:
        print(json.dumps({
            "ok": False,
            "error": "Missing MINERU_TOKEN. Set env or put it in skill .env file.",
            "items": [],
        }, ensure_ascii=False))
        return 2

    api_base = os.environ.get("MINERU_API_BASE", "https://mineru.net")

    sources = _split_sources(args.file_sources)
    items: list[dict] = []
    errors: list[dict] = []

    enable_table = None
    if args.enable_table is not None:
        enable_table = args.enable_table == "true"

    enable_formula = None
    if args.enable_formula is not None:
        enable_formula = args.enable_formula == "true"

    extra_formats = None
    if args.extra_formats:
        extra_formats = [s.strip() for s in args.extra_formats.split(",") if s.strip()]

    for src in sources:
        if not _is_url(src):
            errors.append({
                "source": src,
                "error": "Local file paths not supported in this workflow yet.",
                "next_step": "Provide a public URL or ask to add MinerU batch upload support.",
            })
            continue

        try:
            meta = parse_one_url(
                api_base=api_base,
                token=token,
                source_url=src,
                enable_ocr=args.enable_ocr,
                language=args.language,
                page_ranges=args.page_ranges,
                model_version=args.model_version,
                enable_table=enable_table,
                enable_formula=enable_formula,
                extra_formats=extra_formats,
                timeout_sec=args.timeout,
                poll_interval=args.poll_interval,
                cache=args.cache,
                force=args.force,
            )
            if args.emit_markdown and meta.get("markdown_path"):
                p = pathlib.Path(meta["markdown_path"])
                if p.exists():
                    txt = p.read_text(encoding="utf-8", errors="replace")
                    if args.max_chars and len(txt) > args.max_chars:
                        txt = txt[: args.max_chars] + "\n\n[TRUNCATED]"
                    meta["markdown"] = txt
            items.append(meta)
        except Exception as e:
            errors.append({
                "source": src,
                "error": str(e),
                "next_step": "If this is a protected page, try another accessible mirror URL.",
            })

    ok = len(errors) == 0
    out = {"ok": ok, "items": items, "errors": errors}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
