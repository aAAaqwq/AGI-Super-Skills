#!/usr/bin/env python3
"""Offline, explicit review and promotion for identity mapping/v2 evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.authors import (  # noqa: E402
    SMART_MONEY_SQUARE_MAPPING_SCHEMA,
    load_smart_money_square_identity_evidence,
)
from scanner.contracts import ContractViolation, format_utc  # noqa: E402


REVIEW_RECEIPT_SCHEMA = "binance-identity-mapping-review-receipt/v1"


@dataclass(frozen=True, slots=True)
class IdentityMappingReviewReceipt:
    proposed_mapping_path: str
    proposed_mapping_sha256: str
    approved_mapping_path: str
    approved_mapping_sha256: str
    receipt_path: str
    receipt_sha256: str
    reviewer: str
    reviewed_at: str


def _required(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{field_name} must be a non-empty string")
    return value.strip()


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
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractViolation(f"immutable review output already exists: {path}") from exc


def _default_output(source: Path, reviewed_at: str) -> Path:
    timestamp = reviewed_at.replace("-", "").replace(":", "").replace(".", "")
    return source.with_name(f"{source.stem}.approved-{timestamp}{source.suffix}")


def _validate_candidate(path: Path, content: bytes, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".identity-review-validation-",
            suffix=".json",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        load_smart_money_square_identity_evidence(
            temporary_path, expected_sha256=digest
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def promote_identity_mapping(
    *,
    proposed_mapping_path: Path,
    expected_sha256: str,
    reviewer: str,
    reason: str,
    reviewed_at: str,
    approve: bool,
    output_path: Path | None = None,
    receipt_path: Path | None = None,
) -> IdentityMappingReviewReceipt:
    """Write a separately reviewed APPROVED artifact; never mutate evidence.

    ``approve=True`` is deliberately mandatory even for direct Python callers,
    mirroring the CLI's required ``--approve`` flag.
    """

    if approve is not True:
        raise ContractViolation("explicit --approve is required for promotion")
    source_path = Path(proposed_mapping_path)
    expected_digest = _required(expected_sha256, "expected_sha256").casefold()
    reviewer_value = _required(reviewer, "reviewer")
    reason_value = _required(reason, "reason")
    reviewed = format_utc(reviewed_at)

    evidence = load_smart_money_square_identity_evidence(
        source_path, expected_sha256=expected_digest
    )
    if evidence.schema != SMART_MONEY_SQUARE_MAPPING_SCHEMA:
        raise ContractViolation("only identity mapping/v2 evidence can be promoted")
    if evidence.verification_status != "DIRECT_VERIFIED":
        raise ContractViolation("only DIRECT_VERIFIED evidence can be promoted")
    if evidence.promotion_status != "PROPOSED" or evidence.review is not None:
        raise ContractViolation("input mapping must be an unreviewed PROPOSED artifact")
    if reviewed < evidence.captured_at:
        raise ContractViolation("reviewed_at cannot precede capture time")

    try:
        proposed_bytes = source_path.read_bytes()
        payload = json.loads(proposed_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation("PROPOSED mapping is not readable JSON") from exc
    if not isinstance(payload, dict):
        raise ContractViolation("PROPOSED mapping must be a JSON object")

    approved_path = Path(output_path) if output_path is not None else _default_output(
        source_path, reviewed
    )
    external_receipt_path = (
        Path(receipt_path)
        if receipt_path is not None
        else approved_path.with_name(f"{approved_path.stem}.receipt.json")
    )
    resolved_source = source_path.resolve()
    resolved_approved = approved_path.resolve()
    resolved_receipt = external_receipt_path.resolve()
    if len({resolved_source, resolved_approved, resolved_receipt}) != 3:
        raise ContractViolation("source, approved artifact, and receipt paths must differ")
    if approved_path.exists() or external_receipt_path.exists():
        raise ContractViolation("immutable review output already exists")

    # Preserve the original files while making references location-independent
    # for an APPROVED artifact written to a separate review directory.
    payload["request_manifest"]["path"] = str(
        Path(evidence.request_manifest_path).resolve()
    )
    if len(payload.get("mappings", ())) != 1:
        raise ContractViolation("v2 promotion requires exactly one mapping")
    payload["mappings"][0]["raw_response"]["path"] = str(
        Path(evidence.mappings[0].raw_response_path).resolve()
    )
    payload["promotion_status"] = "APPROVED"
    payload["review"] = {
        "version": "review/v1",
        "reviewer": reviewer_value,
        "reviewed_at": reviewed,
        "decision": "APPROVE",
        "reason": reason_value,
    }
    approved_bytes = _canonical_bytes(payload)
    approved_digest = sha256(approved_bytes).hexdigest()
    _validate_candidate(approved_path, approved_bytes, approved_digest)

    receipt_document = {
        "schema": REVIEW_RECEIPT_SCHEMA,
        "proposed_mapping": {
            "path": str(source_path),
            "sha256": evidence.evidence_sha256,
        },
        "approved_mapping": {
            "path": str(approved_path),
            "sha256": approved_digest,
        },
        "review": payload["review"],
    }
    receipt_bytes = _canonical_bytes(receipt_document)
    receipt_digest = sha256(receipt_bytes).hexdigest()
    _write_new(approved_path, approved_bytes)
    _write_new(external_receipt_path, receipt_bytes)

    # Read back the final immutable path rather than relying on temp validation.
    load_smart_money_square_identity_evidence(
        approved_path, expected_sha256=approved_digest
    )
    return IdentityMappingReviewReceipt(
        proposed_mapping_path=str(source_path),
        proposed_mapping_sha256=evidence.evidence_sha256,
        approved_mapping_path=str(approved_path),
        approved_mapping_sha256=approved_digest,
        receipt_path=str(external_receipt_path),
        receipt_sha256=receipt_digest,
        reviewer=reviewer_value,
        reviewed_at=reviewed,
    )


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        receipt = promote_identity_mapping(
            proposed_mapping_path=args.mapping,
            expected_sha256=args.expected_sha256,
            reviewer=args.reviewer,
            reason=args.reason,
            reviewed_at=args.reviewed_at,
            approve=args.approve,
            output_path=args.output,
            receipt_path=args.receipt,
        )
    except (ContractViolation, OSError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"status": "APPROVED", "receipt": asdict(receipt)},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
