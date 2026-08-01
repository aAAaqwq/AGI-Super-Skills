from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from scanner.contracts import (
    AcceptedPostObservation,
    ContractMetadata,
    ContractViolation,
    DedupStatus,
    PostCountContract,
    SCHEMA_VERSION,
    canonical_post_id,
    canonical_profile_id,
    canonical_profile_username,
    parse_utc,
    deserialize_decimal,
    load_v3_snapshot,
    serialize_decimal,
    strict_24h_window,
)


class VersionedContractTests(unittest.TestCase):
    def test_contract_metadata_carries_v4_schema_and_source(self) -> None:
        observed_at = datetime(2026, 8, 1, 4, tzinfo=timezone.utc)

        metadata = ContractMetadata(
            source_system="offline_fixture",
            created_at=observed_at,
            updated_at=observed_at,
        )

        self.assertEqual("4.1.0", SCHEMA_VERSION)
        self.assertEqual("4.1.0", metadata.schema_version)
        self.assertEqual("offline_fixture", metadata.source_system)

    def test_canonical_ids_ignore_locale_query_and_display_aliases(self) -> None:
        self.assertEqual(
            "28268999497593",
            canonical_post_id(
                "https://www.binance.com/en/square/post/28268999497593?ref=feed"
            ),
        )
        self.assertEqual(
            "stable-profile_42",
            canonical_profile_id(
                "https://www.binance.com/zh-CN/square/profile/stable-profile_42/"
            ),
        )
        self.assertEqual(
            "stable-profile_42",
            canonical_profile_username(
                "https://www.binance.com/zh-CN/square/profile/stable-profile_42/"
            ),
        )

        with self.assertRaises(ContractViolation):
            canonical_profile_id("LIVE")

    def test_utc_parsing_and_strict_24h_window_are_left_closed(self) -> None:
        decision_at = parse_utc("2026-08-01T04:00:00Z")
        window = strict_24h_window(decision_at)

        self.assertEqual(
            datetime(2026, 7, 31, 4, tzinfo=timezone.utc), window.start
        )
        self.assertTrue(window.contains("2026-07-31T04:00:00+00:00"))
        self.assertTrue(window.contains("2026-08-01T05:59:59+02:00"))
        self.assertFalse(window.contains("2026-08-01T04:00:00Z"))
        self.assertFalse(window.contains("2026-07-31T03:59:59Z"))

        with self.assertRaises(ContractViolation):
            parse_utc("2026-08-01T04:00:00")

    def test_decimal_serialization_never_uses_binary_float(self) -> None:
        stored = serialize_decimal(Decimal("0.0100"))

        self.assertEqual("0.0100", stored)
        self.assertEqual(Decimal("0.0100"), deserialize_decimal(stored))
        with self.assertRaises(ContractViolation):
            serialize_decimal(0.01)  # type: ignore[arg-type]
        with self.assertRaises(ContractViolation):
            deserialize_decimal("NaN")

    def test_post_count_contract_freezes_report_reconciliation(self) -> None:
        counts = PostCountContract(
            discovered=10,
            total=7,
            accepted=7,
            quarantine=3,
            dq_quarantine=1,
            window_excluded=2,
            unique_accepted=6,
            new=4,
            duplicate=2,
            dedup_status=DedupStatus.COMPUTED,
        )

        self.assertEqual(6, counts.as_dict()["unique_accepted"])
        for override in (
            {"discovered": 9},
            {"total": 6},
            {"quarantine": 4},
            {"new": 3},
        ):
            values = {
                "discovered": 10,
                "total": 7,
                "accepted": 7,
                "quarantine": 3,
                "dq_quarantine": 1,
                "window_excluded": 2,
                "unique_accepted": 6,
                "new": 4,
                "duplicate": 2,
                "dedup_status": DedupStatus.COMPUTED,
            }
            values.update(override)
            with self.subTest(override=override), self.assertRaises(ContractViolation):
                PostCountContract(**values)

        with self.assertRaisesRegex(ContractViolation, "must both be null"):
            PostCountContract(
                discovered=1,
                total=1,
                accepted=1,
                quarantine=0,
                dq_quarantine=0,
                window_excluded=0,
                unique_accepted=1,
                new=1,
                duplicate=0,
                dedup_status=DedupStatus.NOT_COMPUTED,
            )

    def test_accepted_observation_requires_stable_identity_and_exact_hash(self) -> None:
        observation = AcceptedPostObservation(
            post_id="28268999497593",
            canonical_post_url="https://www.binance.com/en/square/post/28268999497593",
            author_id="opaque-square-uid",
            published_at=datetime(2026, 8, 1, 3, tzinfo=timezone.utc),
            observed_at=datetime(2026, 8, 1, 3, 1, tzinfo=timezone.utc),
            content_hash="a" * 64,
            source_channel="PROFILE",
            source_record_ordinal=0,
        )

        self.assertEqual("28268999497593", observation.post_id)
        with self.assertRaisesRegex(ContractViolation, "non-LIVE"):
            AcceptedPostObservation(
                post_id=observation.post_id,
                canonical_post_url=observation.canonical_post_url,
                author_id="LIVE",
                published_at=observation.published_at,
                observed_at=observation.observed_at,
                content_hash=observation.content_hash,
                source_channel=observation.source_channel,
                source_record_ordinal=0,
            )

    def test_all_existing_v3_history_snapshots_are_read_compatibly(self) -> None:
        history = Path(__file__).parent / "fixtures" / "history"
        paths = sorted(history.glob("v3_snapshot_*.json"))

        snapshots = [load_v3_snapshot(path) for path in paths]

        self.assertEqual(3, len(snapshots))
        self.assertTrue(all(snapshot.schema_version == "3.1-compat" for snapshot in snapshots))
        self.assertEqual([2, 3, 4], [snapshot.count for snapshot in snapshots])
        self.assertTrue(
            all(canonical_post_id(post.url) for snapshot in snapshots for post in snapshot.posts)
        )


if __name__ == "__main__":
    unittest.main()
