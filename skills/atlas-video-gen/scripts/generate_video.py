#!/usr/bin/env python3
"""Generate one Atlas Cloud Veo video with a single, confirmed POST."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


API_BASE = "https://api.atlascloud.ai/api/v1"
MODEL = "google/veo3.1-lite/text-to-video"
TERMINAL_SUCCESS = {"completed", "succeeded", "success"}
TERMINAL_FAILURE = {"failed", "canceled", "cancelled", "timeout"}
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}


class AtlasVideoError(RuntimeError):
    """Raised when an Atlas Cloud request cannot be completed safely."""


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    *,
    attempts: int = 1,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agi-super-team-atlas-video-gen/1.0",
        },
    )

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                decoded = response.read().decode("utf-8")
                result = json.loads(decoded)
                if not isinstance(result, dict):
                    raise AtlasVideoError("Atlas Cloud returned a non-object response")
                return result
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in TRANSIENT_HTTP_CODES and attempt + 1 < attempts:
                sleep(2**attempt)
                continue
            raise AtlasVideoError(
                f"Atlas Cloud {method} failed with HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 < attempts:
                sleep(2**attempt)
                continue
            raise AtlasVideoError(f"Atlas Cloud {method} request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AtlasVideoError("Atlas Cloud returned invalid JSON") from exc

    raise AtlasVideoError(f"Atlas Cloud {method} request exhausted its attempts")


def submit_prediction(api_key: str, payload: dict[str, Any]) -> str:
    # Billable generation submissions are intentionally never retried.
    response = _request_json(
        "POST", f"{API_BASE}/model/generateVideo", api_key, payload, attempts=1
    )
    data = _unwrap(response)
    prediction_id = data.get("id") or data.get("request_id") or data.get("prediction_id")
    if not prediction_id:
        raise AtlasVideoError(
            "Atlas Cloud accepted no identifiable prediction; do not resubmit automatically"
        )
    return str(prediction_id)


def poll_prediction(
    api_key: str,
    prediction_id: str,
    *,
    poll_interval: float,
    timeout: float,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> list[str]:
    started = clock()
    url = f"{API_BASE}/model/prediction/{prediction_id}"

    while clock() - started < timeout:
        response = _request_json("GET", url, api_key, attempts=3, sleep=sleep)
        data = _unwrap(response)
        status = str(data.get("status", "")).lower()

        if status in TERMINAL_SUCCESS:
            outputs = data.get("outputs") or data.get("output") or []
            if isinstance(outputs, str):
                outputs = [outputs]
            urls = [item for item in outputs if isinstance(item, str) and item]
            if not urls:
                raise AtlasVideoError("Prediction completed without an output URL")
            return urls
        if status in TERMINAL_FAILURE:
            detail = data.get("error") or data.get("message") or "unknown error"
            raise AtlasVideoError(f"Prediction {status}: {detail}")

        sleep(poll_interval)

    raise AtlasVideoError(f"Timed out after {timeout:g}s waiting for prediction")


def download_video(
    url: str,
    output_path: Path,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "agi-super-team-atlas-video-gen/1.0"}
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                content = response.read()
            if not content:
                raise AtlasVideoError("Downloaded video is empty")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            return
        except urllib.error.HTTPError as exc:
            if exc.code in TRANSIENT_HTTP_CODES and attempt + 1 < attempts:
                sleep(2**attempt)
                continue
            raise AtlasVideoError(f"Video download failed with HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 < attempts:
                sleep(2**attempt)
                continue
            raise AtlasVideoError(f"Video download failed: {exc}") from exc
    raise AtlasVideoError("Video download exhausted its attempts")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.resolution == "1080p" and args.duration != 8:
        raise AtlasVideoError("1080p output requires --duration 8")
    return {
        "model": MODEL,
        "prompt": args.prompt,
        "aspect_ratio": args.ratio,
        "duration": args.duration,
        "resolution": args.resolution,
        "seed": args.seed,
    }


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate one Veo 3.1 Lite video through Atlas Cloud"
    )
    parser.add_argument("prompt", help="Text description of the video")
    parser.add_argument("-o", "--output", required=True, help="Output MP4 path")
    parser.add_argument("-r", "--ratio", choices=["16:9", "9:16"], default="16:9")
    parser.add_argument("-d", "--duration", choices=[4, 6, 8], type=int, default=8)
    parser.add_argument("--resolution", choices=["720p", "1080p"], default="720p")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--poll-interval", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--yes", action="store_true", help="Confirm one paid POST")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        if args.poll_interval <= 0 or args.timeout <= 0:
            raise AtlasVideoError("poll interval and timeout must be positive")
        payload = build_payload(args)
        plan = {
            "provider": "atlas-cloud",
            "endpoint": f"{API_BASE}/model/generateVideo",
            "payload": payload,
            "output": str(Path(args.output)),
            "billable_post_attempts": 1,
        }

        if not args.yes:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            print("Preview only. Re-run with --yes to send one paid request.", file=sys.stderr)
            return 2

        api_key = os.environ.get("ATLASCLOUD_API_KEY", "").strip()
        if not api_key:
            raise AtlasVideoError("ATLASCLOUD_API_KEY is required")

        prediction_id = submit_prediction(api_key, payload)
        output_urls = poll_prediction(
            api_key,
            prediction_id,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        output_path = Path(args.output).expanduser()
        download_video(output_urls[0], output_path)
        result = {
            "success": True,
            "prediction_id": prediction_id,
            "model": MODEL,
            "output": str(output_path),
        }
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(output_path)
        return 0
    except AtlasVideoError as exc:
        error = {"success": False, "error": str(exc)}
        if getattr(args, "json_output", False):
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
