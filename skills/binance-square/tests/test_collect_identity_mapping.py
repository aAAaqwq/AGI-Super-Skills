from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scanner.authors import load_smart_money_square_identity_evidence
from scripts.collect_identity_mapping import collect_identity_mapping


class _Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class CollectIdentityMappingTests(unittest.TestCase):
    def test_collects_exact_raw_bytes_with_anonymous_request_and_external_receipt(self) -> None:
        response_bytes = json.dumps(
            {
                "success": True,
                "code": "000000",
                "data": {
                    "username": "fixture-user",
                    "topTraderId": "fixture-trader",
                    "squareUid": "fixture-square",
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")
        captured = []

        def opener(request, timeout):
            captured.append((request, timeout))
            return _Response(response_bytes)

        with tempfile.TemporaryDirectory() as directory:
            receipt = collect_identity_mapping(
                username="fixture-user",
                tenant_id="fixture-tenant",
                output_dir=Path(directory),
                opener=opener,
                clock=lambda: "2026-08-01T12:06:00Z",
            )
            raw_path = Path(receipt.raw_response_path)
            manifest = json.loads(Path(receipt.manifest_path).read_text(encoding="utf-8"))
            artifact = json.loads(Path(receipt.mapping_path).read_text(encoding="utf-8"))
            loaded = load_smart_money_square_identity_evidence(
                receipt.mapping_path, expected_sha256=receipt.mapping_sha256
            )
            stored_raw = raw_path.read_bytes()

        self.assertEqual(response_bytes, stored_raw)
        request, timeout = captured[0]
        self.assertEqual("POST", request.get_method())
        self.assertNotIn("Cookie", request.headers)
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(20.0, timeout)
        self.assertEqual("ANONYMOUS", manifest["request"]["credential_metadata"]["mode"])
        self.assertEqual("PROPOSED", artifact["promotion_status"])
        self.assertNotIn("mapping_sha256", artifact)
        self.assertEqual("DIRECT_VERIFIED", loaded.verification_status)


if __name__ == "__main__":
    unittest.main()
