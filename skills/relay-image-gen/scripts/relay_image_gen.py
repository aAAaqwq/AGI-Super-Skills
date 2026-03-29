#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///
"""
Relay Image Generation — multi-provider with priority fallback.
Providers: Boluobao (primary) → Gemini direct → Xingjiabi (fallback). Extensible.

Usage:
    uv run relay_image_gen.py -p "description" -f "out.jpg" [-r 1k|2k|4k] [-a 16:9] [-m model] [-P provider]
"""

import argparse, base64, json, os, subprocess, sys, time
from pathlib import Path
from typing import Optional

import requests

# =================== RELAY CONFIG ===================
RELAY_PRIORITY = [
    {"name": "boluobao", "enabled": True},
    {"name": "gemini", "enabled": True},
    {"name": "xingjiabi", "enabled": True},
]

PROVIDER_CONFIG = {
    "boluobao": {
        "base_url": "https://apipark.boluobao.ai/v1",
        "default_model": "gemini-3-pro-image-preview",
        "fallback_models": [],
        "env_key": "BOLUOBAO_API_KEY",
        "pass_path": "api/boluobao",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.5-flash-image",
        "fallback_models": ["gemini-3-pro-image-preview"],
        "env_key": "GEMINI_API_KEY",
        "pass_path": "api/google-ai-studio",
    },
    "xingjiabi": {
        "base_url": "https://xingjiabiapi.com/v1",
        "default_model": "dall-e-3",
        "fallback_models": ["gpt-image-1", "google/imagen-4", "gemini-3-pro-image-preview"],
        "env_key": "XINGJIABIAPI_KEY",
        "pass_path": None,
    },
}

RESOLUTION_MAP = {
    "1k": {"boluobao": "1k", "xingjiabi": "1024x1024"},
    "2k": {"boluobao": "2k", "xingjiabi": "1792x1024"},
    "4k": {"boluobao": "4k", "xingjiabi": "2048x2048"},
}

# =================== HELPERS ===================

def get_api_key(provider: str) -> Optional[str]:
    cfg = PROVIDER_CONFIG[provider]
    key = os.environ.get(cfg["env_key"])
    if key:
        return key
    if cfg.get("pass_path"):
        try:
            r = subprocess.run(["pass", "show", cfg["pass_path"]], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
    return None


def _post(url, headers, payload, timeout=120):
    return requests.post(url, json=payload, headers=headers, timeout=timeout).json()


def _download(url, output, headers=None, timeout=60):
    resp = requests.get(url, headers=headers or {}, timeout=timeout)
    resp.raise_for_status()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(resp.content)
    return len(resp.content)

# =================== BOLUOBAO ===================

def gen_boluobao(prompt, output, resolution, aspect_ratio, model) -> bool:
    api_key = get_api_key("boluobao")
    if not api_key:
        print("[boluobao] ✗ No API key"); return False
    cfg = PROVIDER_CONFIG["boluobao"]
    model = model or cfg["default_model"]
    res = RESOLUTION_MAP.get(resolution, {}).get("boluobao", "1k")
    print(f"[boluobao] model={model} res={res} aspect={aspect_ratio}")
    try:
        data = _post(f"{cfg['base_url']}/images/generations",
                      {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                      {"model": model, "prompt": prompt, "aspect_ratio": aspect_ratio, "image_size": res})
    except Exception as e:
        print(f"[boluobao] ✗ {e}"); return False
    if "error" in data or (data.get("status") != 200 and "data" not in data):
        err = data.get("error", data)
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        print(f"[boluobao] ✗ {msg}"); return False
    results = data.get("data", [])
    if not results or not results[0].get("url"):
        print("[boluobao] ✗ No image URL"); return False
    try:
        sz = _download(results[0]["url"], output)
        print(f"[boluobao] ✓ {output} ({sz/1024:.0f} KB)"); return True
    except Exception as e:
        print(f"[boluobao] ✗ download: {e}"); return False

# =================== GOOGLE GEMINI ===================

def gen_gemini(prompt, output, resolution, aspect_ratio, model) -> bool:
    api_key = get_api_key("gemini")
    if not api_key:
        print("[gemini] ✗ No API key"); return False
    cfg = PROVIDER_CONFIG["gemini"]
    base = cfg["base_url"]

    models = [model or cfg["default_model"]] + cfg.get("fallback_models", [])
    seen = set()
    models = [m for m in models if m not in seen and not seen.add(m)]

    for mdl in models:
        print(f"[gemini] model={mdl} (generateContent with image)")
        url = f"{base}/models/{mdl}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        try:
            resp = requests.post(url, json=payload,
                                 headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                                 timeout=120)
            data = resp.json()
        except Exception as e:
            print(f"[gemini] ✗ {mdl}: {e}"); continue

        if "error" in data:
            print(f"[gemini] ✗ {mdl}: {data['error'].get('message', '')[:100]}"); continue

        candidates = data.get("candidates", [])
        for c in candidates:
            parts = c.get("content", {}).get("parts", [])
            for part in parts:
                ib = part.get("inlineData", {})
                if ib.get("mimeType", "").startswith("image/"):
                    img_bytes = base64.b64decode(ib["data"])
                    Path(output).parent.mkdir(parents=True, exist_ok=True)
                    Path(output).write_bytes(img_bytes)
                    print(f"[gemini] ✓ {output} ({len(img_bytes)/1024:.0f} KB)")
                    return True

        print(f"[gemini] ✗ {mdl}: no image in response")
    return False

# =================== XINGJIABI ===================

def gen_xingjiabi(prompt, output, resolution, model) -> bool:
    api_key = get_api_key("xingjiabi")
    if not api_key:
        print("[xingjiabi] ✗ No API key"); return False
    cfg = PROVIDER_CONFIG["xingjiabi"]
    models_to_try = [model or cfg["default_model"]] + cfg["fallback_models"]
    seen = set()
    models_to_try = [m for m in models_to_try if m not in seen and not seen.add(m)]
    res = RESOLUTION_MAP.get(resolution, {}).get("xingjiabi", "1024x1024")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for mdl in models_to_try:
        print(f"[xingjiabi] model={mdl} size={res}")
        try:
            data = _post(f"{cfg['base_url']}/images/generations", headers,
                          {"model": mdl, "prompt": prompt, "size": res, "n": 1}, timeout=180)
        except Exception as e:
            print(f"[xingjiabi] ✗ {mdl}: {e}"); continue
        if "error" in data:
            msg = data["error"].get("message", "") if isinstance(data["error"], dict) else str(data["error"])
            print(f"[xingjiabi] ✗ {mdl}: {msg}"); continue
        results = data.get("data", [])
        if not results:
            print(f"[xingjiabi] ✗ {mdl}: empty"); continue
        b64_data = results[0].get("b64_json", "")
        img_url = results[0].get("url", "")
        try:
            if b64_data:
                img = base64.b64decode(b64_data)
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                Path(output).write_bytes(img)
            elif img_url:
                _download(img_url, output)
                img = Path(output).read_bytes()
            else:
                print(f"[xingjiabi] ✗ {mdl}: no data"); continue
            print(f"[xingjiabi] ✓ {output} ({len(img)/1024:.0f} KB)"); return True
        except Exception as e:
            print(f"[xingjiabi] ✗ {mdl} save: {e}"); continue
    return False

# =================== MAIN ===================

def main():
    p = argparse.ArgumentParser(description="Relay Image Generation")
    p.add_argument("-p", "--prompt", required=True)
    p.add_argument("-f", "--filename", required=True)
    p.add_argument("-r", "--resolution", default="1k", choices=["1k", "2k", "4k"])
    p.add_argument("-a", "--aspect-ratio", default="1:1")
    p.add_argument("-m", "--model", help="Override model")
    p.add_argument("-P", "--provider", choices=list(PROVIDER_CONFIG.keys()))
    args = p.parse_args()

    tried = []
    for relay in RELAY_PRIORITY:
        if not relay["enabled"]: continue
        name = relay["name"]
        if args.provider and args.provider != name: continue
        tried.append(name)
        print(f"\n{'='*40}\n  Provider: {name}\n{'='*40}")
        ok = False
        if name == "boluobao":
            ok = gen_boluobao(args.prompt, args.filename, args.resolution, args.aspect_ratio, args.model)
        elif name == "gemini":
            ok = gen_gemini(args.prompt, args.filename, args.resolution, args.aspect_ratio, args.model)
        elif name == "xingjiabi":
            ok = gen_xingjiabi(args.prompt, args.filename, args.resolution, args.model)
        if ok: return

    print(f"\n✗ All providers failed: {tried}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
