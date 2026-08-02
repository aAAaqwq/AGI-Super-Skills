#!/usr/bin/env python3
"""Collect anonymous, hash-bound Smart Money to Square identity evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable
from urllib.request import HTTPHandler, HTTPSHandler, Request, build_opener


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.authors import (  # noqa: E402
    PUBLIC_PROFILE_ENDPOINT,
    PUBLIC_PROFILE_REQUEST_MANIFEST_SCHEMA,
    SMART_MONEY_SQUARE_MAPPING_SCHEMA,
    load_smart_money_square_identity_evidence,
)
from scanner.contracts import ContractViolation, format_utc  # noqa: E402


REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "binance-square-identity-evidence/1",
}


@dataclass(frozen=True, slots=True)
class IdentityMappingReceipt:
    raw_response_path: str
    raw_response_sha256: str
    manifest_path: str
    manifest_sha256: str
    mapping_path: str
    mapping_sha256: str
    captured_at_utc: str


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
    except FileExistsError as exc:
        raise ContractViolation(f"immutable evidence already exists: {path}") from exc


def _default_open(request: Request, timeout: float):
    # An explicit opener without HTTPCookieProcessor is isolated from browser
    # sessions and from any process-global urllib cookie jar.
    return build_opener(HTTPHandler(), HTTPSHandler()).open(request, timeout=timeout)


def collect_identity_mapping(
    *,
    username: str,
    tenant_id: str,
    output_dir: Path,
    timeout: float = 20.0,
    opener: Callable[[Request, float], Any] = _default_open,
    clock: Callable[[], datetime | str] = lambda: datetime.now(timezone.utc),
) -> IdentityMappingReceipt:
    """Capture one response without cookies, auth headers, or browser state.

    New captures are always ``PROPOSED``.  Approval is a separate reviewed
    artifact transition and is intentionally outside this network collector.
    """

    if not isinstance(username, str) or not username.strip():
        raise ContractViolation("username must be a non-empty string")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be a non-empty string")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ContractViolation("timeout must be positive")
    username = username.strip()
    tenant_id = tenant_id.strip()
    request_body = {
        "username": username,
        "getFollowCount": True,
        "queryFollowersInfo": True,
        "queryRelationTokens": True,
    }
    request_bytes = _canonical_bytes(request_body)
    request = Request(
        PUBLIC_PROFILE_ENDPOINT,
        data=request_bytes,
        headers=REQUEST_HEADERS,
        method="POST",
    )
    forbidden = {"cookie", "authorization", "proxy-authorization"}
    if forbidden.intersection(str(key).casefold() for key in request.headers):
        raise ContractViolation("identity collection request contains credentials")
    try:
        with opener(request, float(timeout)) as response:
            raw_response = response.read()
            http_status = int(response.status)
    except (OSError, ValueError, TypeError) as exc:
        raise ContractViolation("anonymous identity request failed") from exc
    captured_at = format_utc(clock())
    try:
        payload = json.loads(raw_response)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation("identity response was not JSON") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ContractViolation("identity response API status was not successful")
    if http_status != 200:
        raise ContractViolation(f"identity response HTTP status was {http_status}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ContractViolation("identity response has no data object")
    top_trader_id = data.get("topTraderId")
    square_uid = data.get("squareUid")
    if not isinstance(top_trader_id, str) or not top_trader_id.strip():
        raise ContractViolation("identity response has no topTraderId")
    if not isinstance(square_uid, str) or not square_uid.strip():
        raise ContractViolation("identity response has no squareUid")

    safe_username = re.sub(r"[^A-Za-z0-9_.-]+", "_", username).strip("._") or "profile"
    timestamp = captured_at.replace("-", "").replace(":", "").replace(".", "")
    stem = f"identity-{safe_username}-{timestamp}"
    output_root = Path(output_dir)
    raw_path = output_root / f"{stem}.response.bin"
    manifest_path = output_root / f"{stem}.request.json"
    mapping_path = output_root / f"{stem}.mapping.json"
    raw_digest = sha256(raw_response).hexdigest()
    _write_new(raw_path, raw_response)

    manifest = {
        "schema": PUBLIC_PROFILE_REQUEST_MANIFEST_SCHEMA,
        "captured_at_utc": captured_at,
        "tenant_id": tenant_id,
        "request": {
            "method": "POST",
            "url": PUBLIC_PROFILE_ENDPOINT,
            "body": request_body,
            "headers": REQUEST_HEADERS,
            "credential_metadata": {
                "mode": "ANONYMOUS",
                "cookie_jar_used": False,
                "authorization_used": False,
                "browser_session_used": False,
            },
        },
        "response": {
            "raw_path": raw_path.name,
            "raw_sha256": raw_digest,
            "http_status": http_status,
            "api_status": {
                "success": payload.get("success"),
                "code": payload.get("code"),
                "message": payload.get("message"),
            },
        },
    }
    manifest_bytes = _canonical_bytes(manifest)
    manifest_digest = sha256(manifest_bytes).hexdigest()
    _write_new(manifest_path, manifest_bytes)

    mapping = {
        "schema": SMART_MONEY_SQUARE_MAPPING_SCHEMA,
        "captured_at_utc": captured_at,
        "provenance": "LIVE_CAPTURE",
        "tenant_id": tenant_id,
        "verification_status": "DIRECT_VERIFIED",
        "promotion_status": "PROPOSED",
        "request_manifest": {
            "path": manifest_path.name,
            "sha256": manifest_digest,
        },
        "mappings": [
            {
                "username": username,
                "topTraderId": top_trader_id.strip(),
                "squareUid": square_uid.strip(),
                "verified_at_utc": captured_at,
                "raw_response": {
                    "path": raw_path.name,
                    "sha256": raw_digest,
                },
                "json_pointers": {
                    "topTraderId": "/data/topTraderId",
                    "squareUid": "/data/squareUid",
                },
            }
        ],
        "review": None,
    }
    mapping_bytes = _canonical_bytes(mapping)
    mapping_digest = sha256(mapping_bytes).hexdigest()
    _write_new(mapping_path, mapping_bytes)
    # Validate the bytes just written before returning their external receipt.
    load_smart_money_square_identity_evidence(
        mapping_path, expected_sha256=mapping_digest
    )
    return IdentityMappingReceipt(
        raw_response_path=str(raw_path),
        raw_response_sha256=raw_digest,
        manifest_path=str(manifest_path),
        manifest_sha256=manifest_digest,
        mapping_path=str(mapping_path),
        mapping_sha256=mapping_digest,
        captured_at_utc=captured_at,
    )


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "data" / "v4" / "identity-evidence",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        receipt = collect_identity_mapping(
            username=args.username,
            tenant_id=args.tenant_id,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
    except (ContractViolation, OSError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"status": "PROPOSED", "receipt": asdict(receipt)},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
