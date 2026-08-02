from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from scanner.authors import load_smart_money_square_identity_catalog
from scanner.contracts import ContractViolation
from scripts.build_identity_mapping_catalog import build_identity_mapping_catalog
from tests.test_authors import write_v2_identity_evidence


class BuildIdentityMappingCatalogTests(unittest.TestCase):
    def test_builder_normalizes_members_and_keeps_hash_in_external_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            members = []
            for name, trader, square in (
                ("two", "fixture-trader-02", "fixture-square-02"),
                ("one", "fixture-trader-01", "fixture-square-01"),
            ):
                member = root / name
                member.mkdir()
                path, _, _ = write_v2_identity_evidence(
                    str(member),
                    promotion_status="APPROVED",
                    top_trader_id=trader,
                    square_uid=square,
                )
                members.append((path, sha256(path.read_bytes()).hexdigest()))
            output = root / "catalog.json"
            receipt_path = root / "catalog.receipt.json"

            receipt = build_identity_mapping_catalog(
                artifacts=reversed(members),
                output_path=output,
                receipt_path=receipt_path,
            )
            document = json.loads(output.read_text(encoding="utf-8"))
            loaded = load_smart_money_square_identity_catalog(
                output, expected_sha256=receipt.catalog_sha256
            )

            self.assertEqual(
                ["fixture-trader-01", "fixture-trader-02"],
                [mapping.top_trader_id for mapping in loaded.mappings],
            )
            self.assertEqual(
                [str(members[1][0].resolve()), str(members[0][0].resolve())],
                [entry["path"] for entry in document["artifacts"]],
            )
            self.assertNotIn("catalog_sha256", document)
            self.assertNotIn("raw_response", document)
            self.assertEqual(
                receipt.catalog_sha256,
                json.loads(receipt_path.read_text(encoding="utf-8"))["catalog"]["sha256"],
            )
            with self.assertRaises(ContractViolation):
                build_identity_mapping_catalog(
                    artifacts=members,
                    output_path=output,
                    receipt_path=receipt_path,
                )


if __name__ == "__main__":
    unittest.main()
