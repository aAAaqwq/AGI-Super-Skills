import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from scanner.authors import (
    LEADERBOARD_METRICS,
    assess_leaderboard_coverage,
    load_seed_profile_evidence,
    load_smart_money_square_identity_evidence,
    load_smart_money_square_identity_catalog,
    parse_30d_leaderboard,
    parse_author_profile,
)
from scanner.contracts import ContractViolation


FIXTURES = Path(__file__).parent / "fixtures" / "m1b"
PROJECT = Path(__file__).parents[1]
SEED_EVIDENCE = (
    Path(__file__).parent / "fixtures" / "discovery" / "leaderboard_seed_profiles.json"
)


def write_v2_identity_evidence(
    directory: str,
    *,
    promotion_status: str = "PROPOSED",
    top_trader_id: str = "fixture-trader-01",
    square_uid: str = "fixture-square-01",
    tenant_id: str = "fixture-tenant",
    provenance: str = "LIVE_CAPTURE",
) -> tuple[Path, Path, Path]:
    root = Path(directory)
    raw_path = root / "response.bin"
    raw = json.dumps(
        {
            "success": True,
            "code": "000000",
            "data": {
                "username": "fixture-user",
                "topTraderId": top_trader_id,
                "squareUid": square_uid,
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    raw_path.write_bytes(raw)
    manifest_path = root / "request-manifest.json"
    manifest = {
        "schema": "binance-public-profile-request-manifest/v1",
        "captured_at_utc": "2026-08-01T12:06:00Z",
        "tenant_id": tenant_id,
        "request": {
            "method": "POST",
            "url": "https://www.binance.com/bapi/composite/v3/friendly/pgc/user/client",
            "body": {
                "username": "fixture-user",
                "getFollowCount": True,
                "queryFollowersInfo": True,
                "queryRelationTokens": True,
            },
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "binance-square-identity-evidence/1",
            },
            "credential_metadata": {
                "mode": "ANONYMOUS",
                "cookie_jar_used": False,
                "authorization_used": False,
                "browser_session_used": False,
            },
        },
        "response": {
            "raw_path": raw_path.name,
            "raw_sha256": sha256(raw).hexdigest(),
            "http_status": 200,
            "api_status": {"success": True, "code": "000000", "message": None},
        },
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    mapping_path = root / "mapping.json"
    mapping = {
        "schema": "binance-smart-money-square-identity-mapping/v2",
        "captured_at_utc": "2026-08-01T12:06:00Z",
        "provenance": provenance,
        "tenant_id": tenant_id,
        "verification_status": "DIRECT_VERIFIED",
        "promotion_status": promotion_status,
        "request_manifest": {
            "path": manifest_path.name,
            "sha256": sha256(manifest_bytes).hexdigest(),
        },
        "mappings": [
            {
                "username": "fixture-user",
                "topTraderId": top_trader_id,
                "squareUid": square_uid,
                "verified_at_utc": "2026-08-01T12:06:00Z",
                "raw_response": {
                    "path": raw_path.name,
                    "sha256": sha256(raw).hexdigest(),
                },
                "json_pointers": {
                    "topTraderId": "/data/topTraderId",
                    "squareUid": "/data/squareUid",
                },
            }
        ],
        "review": (
            {
                "version": "review/v1",
                "reviewer": "fixture-reviewer",
                "reviewed_at": "2026-08-01T12:07:00Z",
                "decision": "APPROVE",
                "reason": "Both IDs are bound by the same anonymous response.",
            }
            if promotion_status == "APPROVED"
            else None
        ),
    }
    mapping_path.write_text(json.dumps(mapping, sort_keys=True), encoding="utf-8")
    return mapping_path, manifest_path, raw_path


class AuthorProfileTests(unittest.TestCase):
    def test_catalog_aggregates_two_approved_v2_artifacts_in_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for name, trader, square in (
                ("z", "fixture-trader-02", "fixture-square-02"),
                ("a", "fixture-trader-01", "fixture-square-01"),
            ):
                member = root / name
                member.mkdir()
                path, _, _ = write_v2_identity_evidence(
                    str(member),
                    promotion_status="APPROVED",
                    top_trader_id=trader,
                    square_uid=square,
                )
                paths.append(path)
            catalog_path = root / "catalog.json"
            catalog = {
                "schema": "binance-smart-money-square-identity-catalog/v1",
                "tenant_id": "fixture-tenant",
                "provenance": "LIVE_CAPTURE",
                "artifacts": [
                    {"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()}
                    for path in paths
                ],
            }
            catalog_bytes = json.dumps(catalog, sort_keys=True).encode("utf-8")
            catalog_path.write_bytes(catalog_bytes)

            evidence = load_smart_money_square_identity_catalog(
                catalog_path, expected_sha256=sha256(catalog_bytes).hexdigest()
            )

        self.assertEqual(
            ("fixture-trader-01", "fixture-trader-02"),
            tuple(mapping.top_trader_id for mapping in evidence.mappings),
        )
        self.assertEqual("fixture-square-01", evidence.square_uid_for("fixture-trader-01"))
        self.assertEqual("fixture-square-02", evidence.square_uid_for("fixture-trader-02"))
        self.assertEqual(str(catalog_path), evidence.evidence_path)
        self.assertEqual(2, len(evidence.catalog_members))

    def test_catalog_rejects_unapproved_cross_tenant_provenance_conflict_and_hash_tamper(self) -> None:
        cases = ("proposed", "tenant", "provenance", "conflict", "hash")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                members = []
                definitions = [
                    ("one", "fixture-trader-01", "fixture-square-01", "fixture-tenant", "LIVE_CAPTURE", "APPROVED"),
                    (
                        "two",
                        "fixture-trader-02",
                        "fixture-square-01" if case == "conflict" else "fixture-square-02",
                        "other-tenant" if case == "tenant" else "fixture-tenant",
                        "FIXTURE_REPLAY" if case == "provenance" else "LIVE_CAPTURE",
                        "PROPOSED" if case == "proposed" else "APPROVED",
                    ),
                ]
                for name, trader, square, tenant, provenance, status in definitions:
                    member = root / name
                    member.mkdir()
                    path, _, _ = write_v2_identity_evidence(
                        str(member),
                        promotion_status=status,
                        top_trader_id=trader,
                        square_uid=square,
                        tenant_id=tenant,
                        provenance=provenance,
                    )
                    members.append(path)
                catalog_path = root / "catalog.json"
                catalog = {
                    "schema": "binance-smart-money-square-identity-catalog/v1",
                    "tenant_id": "fixture-tenant",
                    "provenance": "LIVE_CAPTURE",
                    "artifacts": [
                        {
                            "path": str(path),
                            "sha256": (
                                "0" * 64
                                if case == "hash" and index == 1
                                else sha256(path.read_bytes()).hexdigest()
                            ),
                        }
                        for index, path in enumerate(members)
                    ],
                }
                catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
                with self.assertRaises(ContractViolation):
                    load_smart_money_square_identity_catalog(catalog_path)

    def test_v2_proposed_is_directly_verified_but_not_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, _, _ = write_v2_identity_evidence(directory)
            evidence = load_smart_money_square_identity_evidence(mapping_path)

        self.assertEqual("DIRECT_VERIFIED", evidence.verification_status)
        self.assertEqual("PROPOSED", evidence.promotion_status)
        self.assertIsNone(evidence.square_uid_for("fixture-trader-01"))
        self.assertEqual("fixture-square-01", evidence.mappings[0].square_uid)

    def test_v2_approved_review_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, _, _ = write_v2_identity_evidence(
                directory, promotion_status="APPROVED"
            )
            evidence = load_smart_money_square_identity_evidence(mapping_path)

        self.assertEqual("APPROVED", evidence.promotion_status)
        self.assertEqual("fixture-reviewer", evidence.review.reviewer)
        self.assertEqual(
            "fixture-square-01", evidence.square_uid_for("fixture-trader-01")
        )

    def test_v2_rejects_any_evidence_tampering(self) -> None:
        mutations = (
            "raw_bytes",
            "raw_hash",
            "pointer",
            "value",
            "capture_time",
            "tenant",
            "credential_metadata",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                mapping_path, manifest_path, raw_path = write_v2_identity_evidence(
                    directory, promotion_status="APPROVED"
                )
                mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if mutation == "raw_bytes":
                    raw_path.write_bytes(raw_path.read_bytes() + b" ")
                elif mutation == "raw_hash":
                    mapping["mappings"][0]["raw_response"]["sha256"] = "0" * 64
                elif mutation == "pointer":
                    mapping["mappings"][0]["json_pointers"]["squareUid"] = "/data/username"
                elif mutation == "value":
                    mapping["mappings"][0]["squareUid"] = "tampered-square"
                elif mutation == "capture_time":
                    mapping["captured_at_utc"] = "2026-08-01T12:06:01Z"
                elif mutation == "tenant":
                    mapping["tenant_id"] = "another-tenant"
                elif mutation == "credential_metadata":
                    manifest["request"]["credential_metadata"]["cookie_jar_used"] = True
                if mutation == "credential_metadata":
                    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
                    manifest_path.write_bytes(manifest_bytes)
                    mapping["request_manifest"]["sha256"] = sha256(manifest_bytes).hexdigest()
                mapping_path.write_text(json.dumps(mapping, sort_keys=True), encoding="utf-8")

                with self.assertRaises(ContractViolation):
                    load_smart_money_square_identity_evidence(mapping_path)

    def test_v2_rejects_same_tenant_one_to_many_and_name_badge_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, _, _ = write_v2_identity_evidence(directory)
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            duplicate = dict(mapping["mappings"][0])
            duplicate["squareUid"] = "fixture-square-02"
            mapping["mappings"].append(duplicate)
            mapping_path.write_text(json.dumps(mapping, sort_keys=True), encoding="utf-8")
            with self.assertRaises(ContractViolation):
                load_smart_money_square_identity_evidence(mapping_path)

            mapping["mappings"] = [
                {"username": "same", "badges": ["Top Trader", "Verified"]}
            ]
            mapping_path.write_text(json.dumps(mapping, sort_keys=True), encoding="utf-8")
            with self.assertRaises(ContractViolation):
                load_smart_money_square_identity_evidence(mapping_path)

    def test_v1_live_self_report_never_auto_promotes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "captured_at_utc": "2026-08-01T12:06:00Z",
                        "provenance": "LIVE_CAPTURE",
                        "mappings": [
                            {
                                "topTraderId": "fixture-trader-01",
                                "squareUid": "fixture-square-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            evidence = load_smart_money_square_identity_evidence(path)

        self.assertEqual("PROPOSED", evidence.promotion_status)
        self.assertIsNone(evidence.square_uid_for("fixture-trader-01"))

    def test_explicit_smart_money_to_square_mapping_is_file_verified(self) -> None:
        payload = {
            "schema": "binance-smart-money-square-identity-mapping/v1",
            "captured_at_utc": "2026-08-01T12:06:00Z",
            "provenance": "FIXTURE_REPLAY",
            "mappings": [
                {
                    "topTraderId": "fixture-trader-01",
                    "squareUid": "fixture-square-01",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            content = json.dumps(payload, sort_keys=True).encode("utf-8")
            path.write_bytes(content)

            evidence = load_smart_money_square_identity_evidence(
                path,
                expected_sha256=__import__("hashlib").sha256(content).hexdigest(),
            )

        self.assertEqual("FIXTURE_REPLAY", evidence.provenance)
        self.assertEqual("2026-08-01T12:06:00Z", evidence.captured_at)
        self.assertEqual("fixture-square-01", evidence.square_uid_for("fixture-trader-01"))
        self.assertIsNone(evidence.square_uid_for("unmapped-trader"))

    def test_identity_mapping_rejects_name_only_and_non_bijective_claims(self) -> None:
        base = {
            "schema": "binance-smart-money-square-identity-mapping/v1",
            "captured_at_utc": "2026-08-01T12:06:00Z",
            "provenance": "LIVE_CAPTURE",
        }
        invalid_mappings = (
            [{"traderName": "same name", "squareDisplayName": "same name"}],
            [
                {"topTraderId": "fixture-trader-01", "squareUid": "fixture-square-01"},
                {"topTraderId": "fixture-trader-02", "squareUid": "fixture-square-01"},
            ],
        )
        for index, mappings in enumerate(invalid_mappings):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.json"
                path.write_text(
                    json.dumps({**base, "mappings": mappings}), encoding="utf-8"
                )
                with self.assertRaises(ContractViolation):
                    load_smart_money_square_identity_evidence(path)

    def test_profile_keeps_stable_id_labels_duration_and_hard_tier_gate(self) -> None:
        public_payload = json.loads(
            (FIXTURES / "profile_public.json").read_text(encoding="utf-8")
        )
        html = (FIXTURES / "profile_live.html").read_text(encoding="utf-8")

        author = parse_author_profile(
            public_payload=public_payload,
            html=html,
            observed_at="2026-08-01T07:03:00Z",
        )

        self.assertEqual("synthetic-square-uid-profile", author.author_id)
        self.assertEqual("FixtureTrader", author.username)
        self.assertEqual("Fixture Analyst", author.display_name)
        self.assertEqual(1314, author.trading_days)
        self.assertEqual("A", author.duration_tier)
        self.assertFalse(author.public_live)
        self.assertEqual(
            "UNQUALIFIED_MISSING_LIVE_OR_LEADERBOARD", author.tier_status
        )
        self.assertIn("High-Frequency Trader", author.visible_labels)
        self.assertIn("Square Verified+", author.visible_labels)
        self.assertEqual(12000, author.follower_count)

    def test_content_quality_is_required_before_external_probation(self) -> None:
        public_payload = json.loads(
            (FIXTURES / "profile_public.json").read_text(encoding="utf-8")
        )
        pending = parse_author_profile(
            public_payload=public_payload,
            html=None,
            observed_at="2026-08-01T07:03:00Z",
            leaderboard_tags=("Top traders by profit in 30D",),
        )
        qualified = parse_author_profile(
            public_payload=public_payload,
            html=None,
            observed_at="2026-08-01T07:03:00Z",
            leaderboard_tags=("Top traders by profit in 30D",),
            analysis_qualified=True,
        )

        self.assertEqual("UNQUALIFIED_PENDING_CONTENT_QUALITY", pending.tier_status)
        self.assertEqual("A_EXTERNAL_VERIFIED_PROBATION", qualified.tier_status)

    def test_seed_evidence_keeps_nine_stable_ids_score_ineligible(self) -> None:
        evidence = load_seed_profile_evidence(SEED_EVIDENCE)

        self.assertEqual(9, len(evidence.profiles))
        self.assertEqual(
            "2f07802a6b32b05746dcadc8f55cf77d8a04109ac3f7bfc547353ebdb90dfaed",
            evidence.sha256_hex,
        )
        self.assertEqual(9, evidence.leaderboard_coverage["verified_seed_profiles"])
        self.assertEqual(0, evidence.leaderboard_coverage["covered"])
        self.assertFalse(evidence.leaderboard_coverage["complete_top30"])
        self.assertEqual(
            9, len({profile.author_id for profile in evidence.profiles})
        )
        self.assertTrue(all(not profile.score_eligible for profile in evidence.profiles))
        self.assertTrue(all(profile.author_score == 0 for profile in evidence.profiles))

    def test_seed_evidence_quarantines_cross_identity_alias_collision(self) -> None:
        payload = json.loads(SEED_EVIDENCE.read_text(encoding="utf-8"))
        payload["profiles"][1]["username"] = payload["profiles"][0]["username"]
        payload["profiles"][1]["profile_url"] = payload["profiles"][0]["profile_url"]
        with tempfile.TemporaryDirectory() as directory:
            collision = Path(directory) / "collision.json"
            collision.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ContractViolation, "ALIAS_COLLISION"):
                load_seed_profile_evidence(collision)


def _leaderboard_payload(metric: str, count: int = 30) -> dict[str, object]:
    return {
        "rankingType": metric,
        "timeRange": "30D",
        "rows": [
            {
                "rank": rank,
                "squareUid": f"stable-author-{rank:02d}",
                "username": f"trader-{rank:02d}",
                "displayName": f"Trader {rank:02d}",
                "value": str(1000 - rank),
            }
            for rank in range(1, count + 1)
        ],
    }


class LeaderboardContractTests(unittest.TestCase):
    def test_named_30d_top30_with_unique_stable_ids_is_complete(self) -> None:
        result = parse_30d_leaderboard(_leaderboard_payload("PNL"))

        self.assertEqual("PNL", result.metric)
        self.assertEqual("30D", result.period)
        self.assertEqual("COMPLETE", result.status)
        self.assertEqual(tuple(range(1, 31)), tuple(row.rank for row in result.rows))
        self.assertEqual(30, result.source_record_count)
        self.assertEqual(30, len(result.rows))
        self.assertEqual(0, len(result.rejected))

    def test_all_four_named_metrics_use_the_same_strict_contract(self) -> None:
        results = tuple(
            parse_30d_leaderboard(_leaderboard_payload(metric))
            for metric in LEADERBOARD_METRICS
        )

        self.assertEqual(
            ("PNL", "ROI", "VOLUME", "WIN_RATE"),
            tuple(result.metric for result in results),
        )
        self.assertTrue(all(result.complete_top30 for result in results))
        coverage = assess_leaderboard_coverage(results)
        self.assertEqual("COMPLETE", coverage.status)
        self.assertEqual(4, coverage.covered)
        self.assertEqual(120, coverage.rendered_rank_rows)

    def test_short_duplicate_or_missing_identity_never_becomes_complete(self) -> None:
        short = parse_30d_leaderboard(_leaderboard_payload("ROI", 29))
        duplicate_rank_payload = _leaderboard_payload("VOLUME")
        duplicate_rank_payload["rows"][-1]["rank"] = 1
        duplicate_rank = parse_30d_leaderboard(duplicate_rank_payload)
        duplicate_author_payload = _leaderboard_payload("WIN_RATE")
        duplicate_author_payload["rows"][-1]["squareUid"] = (
            duplicate_author_payload["rows"][0]["squareUid"]
        )
        duplicate_author = parse_30d_leaderboard(duplicate_author_payload)
        missing_id_payload = _leaderboard_payload("PNL")
        del missing_id_payload["rows"][-1]["squareUid"]
        missing_id = parse_30d_leaderboard(missing_id_payload)

        for result in (short, duplicate_rank, duplicate_author, missing_id):
            with self.subTest(reason=result.reason):
                self.assertFalse(result.complete_top30)
                self.assertNotEqual("COMPLETE", result.status)
                self.assertEqual(
                    result.source_record_count,
                    len(result.rows) + len(result.rejected),
                )

    def test_profile_seeds_remain_zero_of_four_partial_discovery(self) -> None:
        seeds = load_seed_profile_evidence(SEED_EVIDENCE)

        coverage = assess_leaderboard_coverage((), seed_count=len(seeds.profiles))

        self.assertEqual("PARTIAL_SEED_DISCOVERY", coverage.status)
        self.assertEqual(0, coverage.covered)
        self.assertEqual(4, coverage.expected)
        self.assertEqual(0, coverage.rendered_rank_rows)
        self.assertEqual(9, coverage.verified_seed_profiles)
        self.assertFalse(coverage.complete_top30)


if __name__ == "__main__":
    unittest.main()
