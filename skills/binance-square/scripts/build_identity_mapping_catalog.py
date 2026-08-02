#!/usr/bin/env python3
"""Build an immutable catalog from independently APPROVED mapping/v2 files."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Iterable


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.authors import (  # noqa: E402
    SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA,
    SMART_MONEY_SQUARE_MAPPING_SCHEMA,
    load_smart_money_square_identity_catalog,
    load_smart_money_square_identity_evidence,
)
from scanner.contracts import ContractViolation  # noqa: E402


CATALOG_RECEIPT_SCHEMA = "binance-identity-mapping-catalog-receipt/v1"


@dataclass(frozen=True, slots=True)
class IdentityMappingCatalogReceipt:
    catalog_path: str
    catalog_sha256: str
    receipt_path: str
    receipt_sha256: str
    tenant_id: str
    provenance: str
    mapping_count: int


def _canonical_bytes(value: object) -> bytes:
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
        raise ContractViolation(f"immutable catalog output already exists: {path}") from exc


def _validate_candidate(path: Path, content: bytes, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".identity-catalog-validation-",
            suffix=".json",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        load_smart_money_square_identity_catalog(
            temporary_path, expected_sha256=digest
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def build_identity_mapping_catalog(
    *,
    artifacts: Iterable[tuple[Path, str]],
    output_path: Path,
    receipt_path: Path | None = None,
) -> IdentityMappingCatalogReceipt:
    """Validate, normalize, and reference APPROVED artifacts without copying raw."""

    output = Path(output_path)
    external_receipt = (
        Path(receipt_path)
        if receipt_path is not None
        else output.with_name(f"{output.stem}.receipt.json")
    )
    if output.resolve() == external_receipt.resolve():
        raise ContractViolation("catalog and receipt paths must differ")
    if output.exists() or external_receipt.exists():
        raise ContractViolation("immutable catalog output already exists")

    loaded = []
    for artifact_path, expected_sha256 in artifacts:
        path = Path(artifact_path).resolve()
        evidence = load_smart_money_square_identity_evidence(
            path, expected_sha256=expected_sha256
        )
        if (
            evidence.schema != SMART_MONEY_SQUARE_MAPPING_SCHEMA
            or evidence.verification_status != "DIRECT_VERIFIED"
            or evidence.promotion_status != "APPROVED"
            or len(evidence.mappings) != 1
        ):
            raise ContractViolation(
                "catalog builder accepts only DIRECT_VERIFIED APPROVED mapping/v2 artifacts"
            )
        loaded.append((evidence.mappings[0], evidence, path))
    if not loaded:
        raise ContractViolation("catalog builder requires at least one artifact")
    loaded.sort(
        key=lambda item: (item[0].top_trader_id, item[0].square_uid, str(item[2]))
    )
    document = {
        "schema": SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA,
        "tenant_id": loaded[0][1].tenant_id,
        "provenance": loaded[0][1].provenance,
        "artifacts": [
            {"path": str(path), "sha256": evidence.evidence_sha256}
            for _, evidence, path in loaded
        ],
    }
    catalog_bytes = _canonical_bytes(document)
    catalog_digest = sha256(catalog_bytes).hexdigest()
    _validate_candidate(output, catalog_bytes, catalog_digest)
    receipt_document = {
        "schema": CATALOG_RECEIPT_SCHEMA,
        "catalog": {"path": str(output), "sha256": catalog_digest},
        "tenant_id": document["tenant_id"],
        "provenance": document["provenance"],
        "mapping_count": len(loaded),
    }
    receipt_bytes = _canonical_bytes(receipt_document)
    receipt_digest = sha256(receipt_bytes).hexdigest()
    _write_new(output, catalog_bytes)
    _write_new(external_receipt, receipt_bytes)
    load_smart_money_square_identity_catalog(
        output, expected_sha256=catalog_digest
    )
    return IdentityMappingCatalogReceipt(
        catalog_path=str(output),
        catalog_sha256=catalog_digest,
        receipt_path=str(external_receipt),
        receipt_sha256=receipt_digest,
        tenant_id=str(document["tenant_id"]),
        provenance=str(document["provenance"]),
        mapping_count=len(loaded),
    )


def _artifact(value: str) -> tuple[Path, str]:
    path, separator, digest = value.rpartition("=")
    if not separator or not path or not digest:
        raise argparse.ArgumentTypeError("artifact must be PATH=SHA256")
    return Path(path), digest


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", type=_artifact, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        receipt = build_identity_mapping_catalog(
            artifacts=args.artifact,
            output_path=args.output,
            receipt_path=args.receipt,
        )
    except (ContractViolation, OSError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"status": "COMPLETE", "receipt": asdict(receipt)},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
