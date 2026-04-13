#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///
"""
Generate images using Boluobao API (菠萝包 image generation).
Fallback provider for nano-banana-pro when xingjiabiapi is unavailable.

API: POST https://apipark.boluobao.ai/v1/images/generations
Models: gemini-3-pro-image-preview (and others)

Usage:
    uv run generate_image_boluobao.py --prompt "description" --filename "out.jpg" [--resolution 1k|2k|4k] [--aspect-ratio 16:9] [--input-image URL]
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path


def get_api_key(provided_key: str | None) -> str | None:
    if provided_key:
        return provided_key
    key = os.environ.get("BOLUOBAO_API_KEY")
    if key:
        return key
    # Try pass
    try:
        result = subprocess.run(["pass", "show", "api/boluobao"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Generate images via Boluobao API")
    parser.add_argument("--prompt", "-p", required=True, help="Image prompt")
    parser.add_argument("--filename", "-f", required=True, help="Output filename")
    parser.add_argument("--model", "-m", default="gemini-3-pro-image-preview", help="Model name")
    parser.add_argument("--resolution", "-r", choices=["1k", "2k", "4k"], default="1k", help="Image size")
    parser.add_argument("--aspect-ratio", "-a", default="1:1",
                        choices=["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
                        help="Aspect ratio")
    parser.add_argument("--input-image", "-i", nargs="*", default=[], help="Input image URLs (up to 14)")
    parser.add_argument("--api-key", "-k", help="API key (overrides env/pass)")

    args = parser.parse_args()

    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: No API key. Set BOLUOBAO_API_KEY, pass --api-key, or store in `pass api/boluobao`", file=sys.stderr)
        sys.exit(1)

    import requests

    url = "https://apipark.boluobao.ai/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
        "image": args.input_image,
        "image_size": args.resolution,
    }

    print(f"Generating image: model={args.model}, resolution={args.resolution}, aspect={args.aspect_ratio}")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        data = resp.json()
    except Exception as e:
        print(f"Error calling API: {e}", file=sys.stderr)
        sys.exit(1)

    if data.get("status") != 200 and "data" not in data:
        print(f"API error: {data}", file=sys.stderr)
        sys.exit(1)

    results = data.get("data", [])
    if not results:
        print("Error: No image in response", file=sys.stderr)
        sys.exit(1)

    image_url = results[0].get("url", "")
    revised_prompt = results[0].get("revised_prompt", "")
    if revised_prompt:
        print(f"Revised prompt: {revised_prompt}")

    if not image_url:
        print("Error: No image URL in response", file=sys.stderr)
        sys.exit(1)

    print(f"Image URL: {image_url}")

    # Download image
    output_path = Path(args.filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        output_path.write_bytes(img_resp.content)
        print(f"\nImage saved: {output_path.resolve()} ({len(img_resp.content) / 1024:.0f} KB)")
    except Exception as e:
        print(f"Error downloading image: {e}", file=sys.stderr)
        print(f"Image URL (manual download): {image_url}")
        sys.exit(1)


if __name__ == "__main__":
    main()
