#!/usr/bin/env python3
"""
VectorNode Image Generation — GPT Image via VectorNode relay API.
Auto-routes token billing (gpt-image-2) vs per-request billing (gpt-image-2-all)
based on prompt length.

Usage:
  # Generate (auto-route)
  python3 vectornode_gen.py -p "a cat on a windowsill" -o out.png

  # Generate with explicit billing
  python3 vectornode_gen.py -p "..." -o out.png --billing per-request

  # Edit existing image
  python3 vectornode_gen.py -p "add sunset" -i input.png -o out.png
"""

import argparse
import base64
import os
import sys
import time
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# ── Config ──────────────────────────────────────────────

DEFAULT_BASE_URL = "https://www.vectronode.com"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "auto"
DEFAULT_COUNT = 1
ROUTE_THRESHOLD = int(os.environ.get("VECTORNODE_ROUTE_THRESHOLD", "300"))
TIMEOUT = 120  # seconds
MAX_RETRIES = 1


def load_env_file():
    """Load .env from workspace if exists."""
    env_paths = [
        Path.home() / ".openclaw" / "workspace" / ".env",
        Path.cwd() / ".env",
    ]
    for p in env_paths:
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        key, val = key.strip(), val.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = val


def get_config():
    """Get API key and base URL from env."""
    load_env_file()
    api_key = os.environ.get("VECTORNODE_API_KEY")
    base_url = os.environ.get("VECTORNODE_BASE_URL", DEFAULT_BASE_URL)
    if not api_key:
        die("VECTORNODE_API_KEY not set. Add to ~/.openclaw/workspace/.env or export it.")
    return api_key, base_url.rstrip("/")


def choose_model(prompt, billing_mode):
    """Select model based on billing mode and prompt length."""
    if billing_mode == "token":
        return "gpt-image-2"
    elif billing_mode == "per-request":
        return "gpt-image-2-all"
    else:  # auto
        if len(prompt) < ROUTE_THRESHOLD:
            return "gpt-image-2"
        else:
            return "gpt-image-2-all"


def generate_image(api_key, base_url, prompt, model, size, quality, count, output_format, output_path):
    """Call /v1/images/generations (token or per-request billing)."""
    url = f"{base_url}/v1/images/generations"
    
    body = {
        "model": model,
        "prompt": prompt,
        "n": count,
        "size": size,
        "quality": quality,
    }
    if output_format:
        body["format"] = output_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")

    resp_data = api_call(req, "image generation")
    return extract_images_from_response(resp_data, output_path, count)


def edit_image(api_key, base_url, prompt, image_path, mask_path, model, size, quality, count, background, moderation, output_path):
    """Call /v1/images/edits (multipart/form-data)."""
    url = f"{base_url}/v1/images/edits"

    # Build multipart form
    boundary = f"----VectorNodeFormBoundary{int(time.time() * 1000)}"
    
    body_parts = []
    
    # Image file(s)
    for img_path in [image_path] + ([mask_path] if mask_path else []):
        if not os.path.exists(img_path):
            die(f"Image not found: {img_path}")
        with open(img_path, "rb") as f:
            img_data = f.read()
        filename = os.path.basename(img_path)
        
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8")
        body_parts.append(part + img_data + b"\r\n")

    # Prompt
    body_parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="prompt"\r\n\r\n{prompt}\r\n'
        .encode("utf-8")
    )

    # Model
    body_parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'
        .encode("utf-8")
    )

    # Optional fields
    for name, value in [
        ("n", str(count)),
        ("size", size),
        ("quality", quality),
        ("background", background),
        ("moderation", moderation),
    ]:
        if value:
            body_parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
                .encode("utf-8")
            )

    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(body_parts)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }

    req = Request(url, data=body, headers=headers, method="POST")
    resp_data = api_call(req, "image edit")
    return extract_images_from_response(resp_data, output_path, count)


def api_call(req, label):
    """Make API call with retry logic."""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
                return json.loads(raw)
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            last_error = f"HTTP {e.code}: {body[:500]}"
            if e.code < 500:
                break  # Don't retry 4xx
        except URLError as e:
            last_error = f"Network error: {e.reason}"
        except Exception as e:
            last_error = str(e)
        
        if attempt < MAX_RETRIES:
            wait = (attempt + 1) * 2
            print(f"⚠ Retry {attempt + 1}/{MAX_RETRIES} in {wait}s...", file=sys.stderr)
            time.sleep(wait)
    
    die(f"{label} failed: {last_error}")


def extract_images_from_response(resp_data, output_path, count):
    """Extract base64 images from API response and save to disk."""
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_path.stem
    ext = output_path.suffix or ".png"

    # Try standard OpenAI format: data[].b64_json
    images = []
    if "data" in resp_data:
        for item in resp_data["data"]:
            if isinstance(item, dict):
                if "b64_json" in item:
                    images.append(item["b64_json"])
                elif "url" in item:
                    images.append(item["url"])

    # Try chat-completion format: choices[].message.content
    if not images and "choices" in resp_data:
        for choice in resp_data["choices"]:
            content = choice.get("message", {}).get("content", "")
            if content:
                # Content might be base64 or a markdown image link
                if content.startswith("data:image"):
                    # data URI
                    _, b64 = content.split(",", 1)
                    images.append(b64)
                elif content.startswith("http"):
                    images.append(content)
                else:
                    # Try as raw base64
                    images.append(content)

    if not images:
        die(f"No image data in response. Keys: {list(resp_data.keys())}")

    saved = []
    for i, img in enumerate(images):
        if i == 0 and count == 1:
            out = str(output_path)
        else:
            out = str(output_dir / f"{stem}_{i+1}{ext}")

        if isinstance(img, str) and (img.startswith("http://") or img.startswith("https://")):
            # Download from URL
            req = Request(img)
            with urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
            with open(out, "wb") as f:
                f.write(raw)
        else:
            # Base64 decode
            try:
                raw = base64.b64decode(img)
            except Exception:
                # Maybe it's already raw bytes? Save as-is
                raw = img.encode("utf-8") if isinstance(img, str) else img
            with open(out, "wb") as f:
                f.write(raw)
        
        saved.append(out)

    return saved


def die(msg):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def detect_format(output_path):
    """Detect output format from extension."""
    ext = Path(output_path).suffix.lower()
    mapping = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}
    return mapping.get(ext)


def main():
    parser = argparse.ArgumentParser(description="VectorNode GPT Image Generation")
    parser.add_argument("-p", "--prompt", required=True, help="Image prompt")
    parser.add_argument("-o", "--output", required=True, help="Output file path")
    parser.add_argument("-i", "--image", help="Input image for edit mode")
    parser.add_argument("-m", "--mask", help="Mask image for edit (transparent areas = edit zone)")
    parser.add_argument("-s", "--size", default=DEFAULT_SIZE, help="Image size (default: 1024x1024)")
    parser.add_argument("-n", "--count", type=int, default=DEFAULT_COUNT, help="Number of images (1-10)")
    parser.add_argument("-q", "--quality", default=DEFAULT_QUALITY,
                        choices=["low", "medium", "high", "auto"], help="Image quality")
    parser.add_argument("--billing", default="auto", choices=["auto", "token", "per-request"],
                        help="Billing mode (default: auto-route)")
    parser.add_argument("--background", default="auto", choices=["opaque", "transparent", "auto"],
                        help="Background mode (edit only)")
    parser.add_argument("--moderation", default="auto", choices=["low", "auto"],
                        help="Content moderation level")

    args = parser.parse_args()

    if args.count < 1 or args.count > 10:
        die("Count must be between 1 and 10")

    # Config
    api_key, base_url = get_config()
    fmt = detect_format(args.output)

    # Route
    model = choose_model(args.prompt, args.billing)
    mode_str = "🪙 token" if model == "gpt-image-2" else "📦 per-request"
    print(f"🎨 Model: {model} ({mode_str} billing)", file=sys.stderr)
    print(f"📝 Prompt ({len(args.prompt)} chars)", file=sys.stderr)

    # Execute
    if args.image:
        # Edit mode
        print(f"✏️  Edit mode — source: {args.image}", file=sys.stderr)
        saved = edit_image(
            api_key, base_url,
            prompt=args.prompt,
            image_path=args.image,
            mask_path=args.mask,
            model=model,
            size=args.size,
            quality=args.quality,
            count=args.count,
            background=args.background,
            moderation=args.moderation,
            output_path=args.output,
        )
    else:
        # Generate mode
        saved = generate_image(
            api_key, base_url,
            prompt=args.prompt,
            model=model,
            size=args.size,
            quality=args.quality,
            count=args.count,
            output_format=fmt,
            output_path=args.output,
        )

    for s in saved:
        size_kb = os.path.getsize(s) / 1024
        print(f"✅ {s} ({size_kb:.1f} KB)", file=sys.stderr)
    
    # Print output path for downstream consumption
    if len(saved) == 1:
        print(saved[0])
    else:
        print("\n".join(saved))


if __name__ == "__main__":
    main()
