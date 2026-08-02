from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from scanner.authors import load_smart_money_square_identity_evidence
from scanner.contracts import ContractViolation
from scripts.collect_identity_mapping import collect_identity_mapping
from scripts.review_identity_mapping import promote_identity_mapping


class _Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def proposed_capture(root: Path):
    response = json.dumps(
        {
            "success": True,
            "code": "000000",
            "data": {
                "topTraderId": "fixture-trader",
                "squareUid": "fixture-square",
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return collect_identity_mapping(
        username="fixture-user",
        tenant_id="fixture-tenant",
        output_dir=root,
        opener=lambda request, timeout: _Response(response),
        clock=lambda: "2026-08-01T12:06:00Z",
    )


class ReviewIdentityMappingTests(unittest.TestCase):
    def test_approval_is_explicit_hash_bound_immutable_and_keeps_sources_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposed = proposed_capture(root)
            proposed_bytes = Path(proposed.mapping_path).read_bytes()
            raw_bytes = Path(proposed.raw_response_path).read_bytes()
            manifest_bytes = Path(proposed.manifest_path).read_bytes()
            output = root / "reviewed.approved.json"
            receipt_path = root / "reviewed.approved.receipt.json"

            receipt = promote_identity_mapping(
                proposed_mapping_path=Path(proposed.mapping_path),
                expected_sha256=proposed.mapping_sha256,
                reviewer="governor-fixture",
                reason="The raw response and manifest bind both stable IDs.",
                reviewed_at="2026-08-01T12:07:00Z",
                approve=True,
                output_path=output,
                receipt_path=receipt_path,
            )
            approved_bytes = output.read_bytes()
            approved = load_smart_money_square_identity_evidence(
                output, expected_sha256=receipt.approved_mapping_sha256
            )
            external_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

            self.assertEqual(proposed_bytes, Path(proposed.mapping_path).read_bytes())
            self.assertEqual(raw_bytes, Path(proposed.raw_response_path).read_bytes())
            self.assertEqual(manifest_bytes, Path(proposed.manifest_path).read_bytes())
            self.assertNotEqual(proposed_bytes, approved_bytes)
            self.assertEqual("APPROVED", approved.promotion_status)
            self.assertEqual("governor-fixture", approved.review.reviewer)
            self.assertEqual("fixture-square", approved.square_uid_for("fixture-trader"))
            self.assertEqual(sha256(approved_bytes).hexdigest(), receipt.approved_mapping_sha256)
            self.assertEqual(
                receipt.approved_mapping_sha256,
                external_receipt["approved_mapping"]["sha256"],
            )
            self.assertNotIn("mapping_sha256", json.loads(approved_bytes))

            with self.assertRaises(ContractViolation):
                promote_identity_mapping(
                    proposed_mapping_path=Path(proposed.mapping_path),
                    expected_sha256=proposed.mapping_sha256,
                    reviewer="governor-fixture",
                    reason="A second write must not overwrite the first.",
                    reviewed_at="2026-08-01T12:08:00Z",
                    approve=True,
                    output_path=output,
                    receipt_path=receipt_path,
                )
            self.assertEqual(approved_bytes, output.read_bytes())

    def test_missing_approve_wrong_hash_and_tampered_sources_fail_before_output(self) -> None:
        cases = ("missing_approve", "wrong_hash", "tampered_raw")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                proposed = proposed_capture(root)
                if case == "tampered_raw":
                    raw_path = Path(proposed.raw_response_path)
                    raw_path.write_bytes(raw_path.read_bytes() + b" ")
                output = root / "must-not-exist.approved.json"
                receipt_path = root / "must-not-exist.receipt.json"
                with self.assertRaises(ContractViolation):
                    promote_identity_mapping(
                        proposed_mapping_path=Path(proposed.mapping_path),
                        expected_sha256=(
                            "0" * 64 if case == "wrong_hash" else proposed.mapping_sha256
                        ),
                        reviewer="governor-fixture",
                        reason="Fixture review.",
                        reviewed_at="2026-08-01T12:07:00Z",
                        approve=case != "missing_approve",
                        output_path=output,
                        receipt_path=receipt_path,
                    )
                self.assertFalse(output.exists())
                self.assertFalse(receipt_path.exists())


if __name__ == "__main__":
    unittest.main()
