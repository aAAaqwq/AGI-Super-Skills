#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///
"""
Relay Video Generation — multi-provider with priority fallback + async polling.
Providers: Google Gemini (primary) → Xingjiabi (fallback). Extensible.

Usage:
    uv run relay_video_gen.py -p "description" -f "out.mp4" [-d 5] [-a 16:9] [-m model] [-P provider]
"""

import argparse, json, os, subprocess, sys, time
from pathlib import Path
from typing import Optional

import requests

# =================== RELAY CONFIG ===================
RELAY_PRIORITY = [
    {"name": "gemini", "enabled": True},       # Google direct API — most reliable
    {"name": "xingjiabi", "enabled": True},     # Relay fallback
]

PROVIDER_CONFIG = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "veo-3.1-generate-preview",
        "fallback_models": [],
        "env_key": "GEMINI_API_KEY",
        "pass_path": "api/google-ai-studio",
    },
    "xingjiabi": {
        "base_url": "https://xingjiabiapi.com/v1",
        "default_model": "kling-video",
        "fallback_models": [
            "veo-3.1-fast", "veo-3.1",
            "minimax/video-01", "grok-video-3",
        ],
        "env_key": "XINGJIABIAPI_KEY",
        "pass_path": None,
    },
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


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def download_video(url: str, output: str, headers: dict = None) -> bool:
    try:
        resp = requests.get(url, headers=headers or {}, stream=True, timeout=300)
        resp.raise_for_status()
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(resp.content)
        mb = len(resp.content) / (1024 * 1024)
        print(f"  ✓ saved {output} ({mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"  ✗ download: {e}")
        return False

# =================== GOOGLE GEMINI ===================

def gen_gemini(prompt: str, output: str, model: str, duration: int, aspect_ratio: str) -> bool:
    api_key = get_api_key("gemini")
    if not api_key:
        print("[gemini] ✗ No API key"); return False

    cfg = PROVIDER_CONFIG["gemini"]
    model = model if model and model.startswith("veo") else cfg["default_model"]
    base = cfg["base_url"]

    # Clamp duration to Gemini's range (4-8)
    gem_duration = max(4, min(8, duration))
    if gem_duration != duration:
        print(f"[gemini] Duration clamped {duration}→{gem_duration}s (Gemini range: 4-8)")

    print(f"[gemini] model={model} duration={gem_duration}s aspect={aspect_ratio}")

    # Submit
    url = f"{base}/models/{model}:predictLongRunning"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "durationSeconds": gem_duration,
            "sampleCount": 1,
        },
    }
    try:
        resp = requests.post(url, json=payload,
                             headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                             timeout=60)
        data = resp.json()
    except Exception as e:
        print(f"[gemini] ✗ submit: {e}"); return False

    if "error" in data:
        print(f"[gemini] ✗ {data['error'].get('message', data['error'])}"); return False

    op_name = data.get("name", "")
    if not op_name:
        print(f"[gemini] ✗ no operation name: {data}"); return False

    print(f"[gemini] Operation: {op_name}")

    # Poll
    poll_url = f"{base}/{op_name}"
    poll_headers = {"x-goog-api-key": api_key}
    max_wait, interval, elapsed = 600, 5, 0

    while elapsed < max_wait:
        try:
            pdata = requests.get(poll_url, headers=poll_headers, timeout=30).json()
        except Exception as e:
            print(f"  poll error: {e}")
            time.sleep(interval); elapsed += interval; continue

        done = pdata.get("done", False)
        mins, secs = elapsed // 60, elapsed % 60

        if done:
            # Check error
            if "error" in pdata:
                print(f"  ✗ {pdata['error'].get('message', pdata['error'])}"); return False

            # Extract video URI
            resp_data = pdata.get("response", {})
            samples = resp_data.get("generateVideoResponse", {}).get("generatedSamples", [])
            if not samples:
                samples = resp_data.get("predictions", [])

            for sample in samples:
                video = sample.get("video", {})
                uri = video.get("uri", "")
                b64 = video.get("bytesBase64Encoded", "")

                if uri:
                    print(f"  Video URI: {uri[:80]}...")
                    return download_video(uri, output, poll_headers)
                elif b64:
                    import base64
                    raw = base64.b64decode(b64)
                    Path(output).parent.mkdir(parents=True, exist_ok=True)
                    Path(output).write_bytes(raw)
                    print(f"  ✓ saved {output} ({len(raw)/1024/1024:.1f} MB)")
                    return True

            print(f"  ✗ done but no video: {json.dumps(resp_data, ensure_ascii=False)[:300]}")
            return False

        print(f"  [{mins:02d}:{secs:02d}] polling...")
        time.sleep(interval); elapsed += interval

    print(f"  ✗ timeout after {max_wait}s"); return False

# =================== XINGJIABI VIDEO ===================

def submit_xj_video(base_url, headers, model, prompt, duration, aspect_ratio):
    payload = {"model": model, "prompt": prompt, "duration": str(duration), "aspect_ratio": aspect_ratio}
    try:
        resp = requests.post(f"{base_url}/video/generations", json=payload, headers=headers, timeout=60)
        return resp.json()
    except Exception as e:
        print(f"  ✗ request failed: {e}"); return None


def poll_xj_task(base_url, api_key, task_id, output, max_wait=600, interval=5):
    url = f"{base_url}/video/generations/{task_id}"
    hdrs = {"Authorization": f"Bearer {api_key}"}
    elapsed = 0
    print(f"  Polling task {task_id} (max {max_wait}s)...")
    while elapsed < max_wait:
        try:
            data = requests.get(url, headers=hdrs, timeout=30).json()
        except Exception as e:
            print(f"  poll error: {e}"); time.sleep(interval); elapsed += interval; continue
        status = data.get("data", {}).get("task_status", "unknown")
        video_url = data.get("data", {}).get("video_url", "")
        if status in ("completed", "succeed", "success"):
            if video_url:
                return download_video(video_url, output, hdrs)
            for key in ("output", "result", "video"):
                nested = data.get("data", {}).get(key, {})
                if isinstance(nested, dict):
                    u = nested.get("url") or nested.get("video_url")
                    if u: return download_video(u, output, hdrs)
                elif isinstance(nested, str) and nested.startswith("http"):
                    return download_video(nested, output, hdrs)
            return False
        if status in ("failed", "error", "cancelled"):
            print(f"  ✗ task {status}"); return False
        mins, secs = elapsed // 60, elapsed % 60
        print(f"  [{mins:02d}:{secs:02d}] status={status}")
        time.sleep(interval); elapsed += interval
    return False


def gen_xingjiabi(prompt, output, model, duration, aspect_ratio):
    api_key = get_api_key("xingjiabi")
    if not api_key:
        print("[xingjiabi] ✗ No API key"); return False
    cfg = PROVIDER_CONFIG["xingjiabi"]
    base, hdrs = cfg["base_url"], _headers(api_key)
    models = [model or cfg["default_model"]] + cfg["fallback_models"]
    seen = set()
    models = [m for m in models if m not in seen and not seen.add(m)]
    for mdl in models:
        print(f"\n[xingjiabi] model={mdl} duration={duration}s aspect={aspect_ratio}")
        data = submit_xj_video(base, hdrs, mdl, prompt, duration, aspect_ratio)
        if data is None: continue
        code = data.get("code", 0)
        task_id = data.get("data", {}).get("task_id", "")
        if code == 200 and task_id:
            print(f"  Task: {task_id}")
            if poll_xj_task(base, api_key, task_id, output): return True
            continue
        msg = data.get("message", data.get("error", ""))
        if isinstance(msg, dict): msg = msg.get("message", str(msg))
        if "不支持" in msg or "not supported" in msg.lower():
            print(f"  ✗ {mdl}: not supported"); continue
        if "负载已饱和" in msg or "saturated" in msg.lower():
            print(f"  ✗ {mdl}: saturated"); continue
        if "无可用渠道" in msg or "no available channel" in msg.lower():
            print(f"  ✗ {mdl}: no channels"); continue
        print(f"  ✗ {mdl}: {msg}"); continue
    return False

# =================== MAIN ===================

def main():
    p = argparse.ArgumentParser(description="Relay Video Generation")
    p.add_argument("-p", "--prompt", required=True)
    p.add_argument("-f", "--filename", required=True)
    p.add_argument("-d", "--duration", type=int, default=5, help="Seconds (Gemini: 4-8)")
    p.add_argument("-a", "--aspect-ratio", default="16:9")
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
        if name == "gemini":
            ok = gen_gemini(args.prompt, args.filename, args.model, args.duration, args.aspect_ratio)
        elif name == "xingjiabi":
            ok = gen_xingjiabi(args.prompt, args.filename, args.model, args.duration, args.aspect_ratio)
        if ok: return

    print(f"\n✗ All providers failed: {tried}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
