#!/usr/bin/env python3
"""
vectronode_image.py — VectorNode GPT Image 生成与编辑（智能路由）

Usage:
  vectronode_image.py generate --prompt "..." --output out.png [options]
  vectronode_image.py edit --image input.png --prompt "..." --output out.png [options]

Auto-routing:
  - Short prompt (≤200 chars) + simple (n=1, size<2K, default quality) → gpt-image-2 (Token)
  - Otherwise → gpt-image-2-all (per-call, 长/复杂任务友好)

Author: Daniel Li
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib import request, error


# ─── Constants ───────────────────────────────────────────────
DEFAULT_BASE_URL = "https://www.vectronode.com/"
ENV_FILE = Path.home() / ".openclaw" / ".env"

# Routing thresholds
LONG_PROMPT_THRESHOLD = 200  # chars
PROMPT_MAX_CHARS = 1000      # API hard limit
MAX_RETRIES = 2
RETRY_SLEEP = 2.0

VALID_SIZES = {
    "1024x1024", "1536x1024", "1024x1536",
    "2048x2048", "2048x1152",      # 2K
    "3840x2160", "2160x3840",      # 4K
    "auto",
}
SIZE_2K = {"2048x2048", "2048x1152"}
SIZE_4K = {"3840x2160", "2160x3840"}


# ─── Credentials ─────────────────────────────────────────────
def load_credentials():
    """Load VECTORNODE_API_KEY and VECTORNODE_BASE_URL from env, then ~/.openclaw/.env."""
    api_key = os.getenv("VECTORNODE_API_KEY", "").strip()
    base_url = os.getenv("VECTORNODE_BASE_URL", "").strip() or DEFAULT_BASE_URL

    # Fallback to ~/.openclaw/.env
    if not api_key and ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r'(?:export\s+)?VECTORNODE_API_KEY=(.+)', line)
                if m:
                    api_key = m.group(1).strip().strip('"').strip("'")
                m = re.match(r'(?:export\s+)?VECTORNODE_BASE_URL=(.+)', line)
                if m and not os.getenv("VECTORNODE_BASE_URL"):
                    val = m.group(1).strip().strip('"').strip("'")
                    if val:
                        base_url = val
        except Exception as e:
            print(f"⚠️  Failed to read {ENV_FILE}: {e}", file=sys.stderr)

    return api_key, base_url


# ─── Routing Logic ───────────────────────────────────────────
def decide_model(prompt, n, size, quality, force=None):
    """
    Decide which gpt-image-* model to use.

    Returns: (model_name, reason_string)
    """
    if force and force in ("gpt-image-2", "gpt-image-2-all"):
        return force, "user-specified"

    reasons = []

    # Heuristic 1: long prompt → per-call
    if len(prompt) > LONG_PROMPT_THRESHOLD:
        reasons.append(f"prompt {len(prompt)} > {LONG_PROMPT_THRESHOLD} chars")

    # Heuristic 2: multi-image → per-call
    if n > 1:
        reasons.append(f"n={n} > 1")

    # Heuristic 3: high resolution → per-call
    if size in SIZE_2K:
        reasons.append(f"size={size} (2K)")
    elif size in SIZE_4K:
        reasons.append(f"size={size} (4K)")

    # Heuristic 4: explicit high quality → per-call
    if quality == "high":
        reasons.append("quality=high")

    if reasons:
        return "gpt-image-2-all", "; ".join(reasons)

    return "gpt-image-2", f"short prompt ({len(prompt)} chars), simple config"


# ─── HTTP Layer ──────────────────────────────────────────────
def call_api(base_url, api_key, payload, files=None, timeout=120):
    """
    Call VectorNode API. Returns parsed JSON dict.

    If files is given, uses multipart/form-data (for edit endpoint).
    Otherwise uses application/json (for generate endpoint).
    """
    url = base_url.rstrip("/") + "/v1/images/generations"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "vectronode-image-skill/1.0",
    }

    if files is None:
        # JSON request
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    else:
        # Multipart request
        boundary = "----vectronode" + str(int(time.time() * 1000))
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        data = build_multipart(payload, files, boundary)

    req = request.Request(url, data=data, headers=headers, method="POST")

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            # Retry on 429 / 5xx
            if e.code == 429 or 500 <= e.code < 600:
                last_err = f"HTTP {e.code}: {err_body[:300]}"
                if attempt < MAX_RETRIES:
                    print(f"⚠️  {last_err} — retrying in {RETRY_SLEEP}s (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(RETRY_SLEEP)
                    continue
            raise RuntimeError(f"HTTP {e.code}: {err_body[:500]}")
        except Exception as e:
            last_err = str(e)
            if attempt < MAX_RETRIES:
                print(f"⚠️  {last_err} — retrying in {RETRY_SLEEP}s (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
                time.sleep(RETRY_SLEEP)
                continue
            raise

    raise RuntimeError(f"API call failed after {MAX_RETRIES} attempts: {last_err}")


def build_multipart(payload, files, boundary):
    """Build multipart/form-data body."""
    lines = []
    # JSON fields
    for key, value in payload.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(str(value).encode("utf-8"))
    # File fields
    for name, filepath in files.items():
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"'.encode("utf-8")
        )
        lines.append(b"Content-Type: application/octet-stream")
        lines.append(b"")
        lines.append(path.read_bytes())
    # End
    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    return b"\r\n".join(lines)


# ─── Output ──────────────────────────────────────────────────
def save_b64_image(b64_data, output_path, default_format="png"):
    """Decode base64 and save to file. Format determined by extension or default."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img_bytes = base64.b64decode(b64_data)
    out.write_bytes(img_bytes)
    return out


# ─── Commands ────────────────────────────────────────────────
def cmd_generate(args):
    api_key, base_url = load_credentials()
    if not api_key:
        print("❌ VECTORNODE_API_KEY not found in env or ~/.openclaw/.env", file=sys.stderr)
        sys.exit(1)

    prompt = args.prompt
    if len(prompt) > PROMPT_MAX_CHARS:
        print(f"❌ Prompt too long: {len(prompt)} chars (max {PROMPT_MAX_CHARS})", file=sys.stderr)
        sys.exit(1)

    n = args.n
    size = args.size
    quality = args.quality
    fmt = args.format

    model, reason = decide_model(prompt, n, size, quality, force=args.model)

    if args.dry_run:
        print("🔍 [DRY-RUN] Route decision:")
        print(f"   model:     {model}")
        print(f"   reason:    {reason}")
        print(f"   prompt:    {len(prompt)} chars")
        print(f"   n:         {n}")
        print(f"   size:      {size}")
        print(f"   quality:   {quality}")
        print(f"   format:    {fmt}")
        print(f"   output:    {args.output}")
        return

    print(f"🎨 Generating with {model} — {reason}")
    print(f"   prompt:    {len(prompt)} chars | n={n} | size={size} | quality={quality}")

    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
    }
    if size != "auto":
        payload["size"] = size
    if quality != "auto":
        payload["quality"] = quality
    if fmt != "png":
        payload["format"] = fmt

    result = call_api(base_url, api_key, payload)

    if not result.get("data"):
        print(f"❌ API returned no data: {json.dumps(result)[:500]}", file=sys.stderr)
        sys.exit(1)

    # Save all generated images
    data = result["data"]
    if isinstance(data, dict):
        # Single image response
        b64 = data.get("b64_json")
        if not b64:
            print(f"❌ No b64_json in response: {json.dumps(result)[:500]}", file=sys.stderr)
            sys.exit(1)
        out = save_b64_image(b64, args.output, fmt)
        print(f"✅ Saved: {out}")
    elif isinstance(data, list):
        # Multiple images
        out_path = Path(args.output)
        stem = out_path.stem
        suffix = out_path.suffix or f".{fmt}"
        parent = out_path.parent
        for i, item in enumerate(data):
            b64 = item.get("b64_json") if isinstance(item, dict) else None
            if not b64:
                continue
            out = parent / f"{stem}_{i+1}{suffix}"
            save_b64_image(b64, out, fmt)
            print(f"✅ Saved: {out}")
    else:
        print(f"❌ Unexpected data format: {type(data)}", file=sys.stderr)
        sys.exit(1)


def cmd_edit(args):
    api_key, base_url = load_credentials()
    if not api_key:
        print("❌ VECTORNODE_API_KEY not found in env or ~/.openclaw/.env", file=sys.stderr)
        sys.exit(1)

    if not Path(args.image).exists():
        print(f"❌ Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    prompt = args.prompt
    if len(prompt) > PROMPT_MAX_CHARS:
        print(f"❌ Prompt too long: {len(prompt)} chars (max {PROMPT_MAX_CHARS})", file=sys.stderr)
        sys.exit(1)

    n = args.n
    size = args.size
    quality = args.quality

    # Edit endpoint: model is hardcoded as gpt-image-2 (Token billing) per docs
    # But user can override
    model, reason = decide_model(prompt, n, size, quality, force=args.model)

    if args.dry_run:
        print("🔍 [DRY-RUN] Edit route decision:")
        print(f"   model:     {model}")
        print(f"   reason:    {reason}")
        print(f"   image:     {args.image}")
        print(f"   prompt:    {len(prompt)} chars")
        print(f"   n:         {n}")
        print(f"   output:    {args.output}")
        return

    print(f"🎨 Editing with {model} — {reason}")

    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
    }
    if size != "auto":
        payload["size"] = size
    if quality != "auto":
        payload["quality"] = quality

    files = {"image": args.image}
    if args.mask:
        if not Path(args.mask).exists():
            print(f"❌ Mask not found: {args.mask}", file=sys.stderr)
            sys.exit(1)
        files["mask"] = args.mask

    result = call_api(base_url, api_key, payload, files=files)

    if not result.get("data"):
        print(f"❌ API returned no data: {json.dumps(result)[:500]}", file=sys.stderr)
        sys.exit(1)

    data = result["data"]
    b64 = data.get("b64_json") if isinstance(data, dict) else None
    if not b64:
        print(f"❌ No b64_json in response: {json.dumps(result)[:500]}", file=sys.stderr)
        sys.exit(1)
    out = save_b64_image(b64, args.output, "png")
    print(f"✅ Saved: {out}")


# ─── Argparse ────────────────────────────────────────────────
def build_parser():
    parser = argparse.ArgumentParser(
        description="VectorNode GPT Image 生成与编辑（智能路由）"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", choices=["gpt-image-2", "gpt-image-2-all", "auto"], default="auto",
                        help="强制模型（默认 auto 自动路由）")
    common.add_argument("--n", type=int, default=1, help="生成张数 (1-10)")
    common.add_argument("--size", default="auto",
                        help="尺寸: 1024x1024 / 1536x1024 / 1024x1536 / 2048x2048 / 2048x1152 / 3840x2160 / 2160x3840 / auto")
    common.add_argument("--quality", default="auto", choices=["low", "medium", "high", "auto"])
    common.add_argument("--dry-run", action="store_true", help="仅打印路由决策")

    # generate
    p_gen = sub.add_parser("generate", parents=[common], help="生成图片")
    p_gen.add_argument("--prompt", required=True, help="提示词")
    p_gen.add_argument("--output", required=True, help="输出文件路径")
    p_gen.add_argument("--format", default="png", choices=["png", "jpeg", "webp"])
    p_gen.set_defaults(func=cmd_generate)

    # edit
    p_edit = sub.add_parser("edit", parents=[common], help="编辑图片")
    p_edit.add_argument("--image", required=True, help="输入图片路径")
    p_edit.add_argument("--mask", help="编辑遮罩 PNG")
    p_edit.add_argument("--prompt", required=True, help="编辑描述")
    p_edit.add_argument("--output", required=True, help="输出文件路径")
    p_edit.set_defaults(func=cmd_edit)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
