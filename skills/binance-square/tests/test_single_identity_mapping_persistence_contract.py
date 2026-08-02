from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from scanner.pipeline import PipelineConfig, run_shadow_radar
from scanner.smart_money import collect_smart_money
from scanner.storage import SQLiteRunLedger
from tests.test_authors import write_v2_identity_evidence
from tests.test_smart_money import FakeSmartMoneyApi


PROJECT = Path(__file__).parents[1]
MIGRATIONS = PROJECT / "migrations"
FIXTURE = PROJECT / "tests" / "fixtures" / "m1b"


class _CatalogOnlyMarketClient:
    def __init__(self, observed_at: datetime) -> None:
        self.observed_at = observed_at

    def fetch_futures_catalog(self) -> SimpleNamespace:
        return SimpleNamespace(
            server_time_ms=int(self.observed_at.timestamp() * 1000),
            captured_at=self.observed_at,
            contracts={},
        )


class SingleIdentityMappingPersistenceContractTests(unittest.TestCase):
    def _smart_money_evidence(self, *, provenance: str) -> dict[str, object]:
        api = FakeSmartMoneyApi()
        api.test_case = self
        return collect_smart_money(
            get_json=api,
            captured_at="2026-08-01T12:05:00Z",
            provenance=provenance,
        )

    @staticmethod
    def _empty_profile(square_uid: str, offset: int) -> dict[str, object]:
        del square_uid, offset
        return {
            "success": True,
            "data": {"contents": [], "nextTimeOffset": None},
        }

    def test_approved_v2_single_mapping_persists_in_fixture_and_real_modes(self) -> None:
        for mode in ("fixture", "real"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                mapping_dir = root / "mapping"
                mapping_dir.mkdir()
                provenance = (
                    "FIXTURE_REPLAY" if mode == "fixture" else "LIVE_CAPTURE"
                )
                evidence = self._smart_money_evidence(provenance=provenance)
                top_trader_id = evidence["rankings"][0]["rows"][0]["source_id"]
                square_uid = f"{mode}-single-square-uid"
                mapping_path, _, _ = write_v2_identity_evidence(
                    str(mapping_dir),
                    promotion_status="APPROVED",
                    top_trader_id=top_trader_id,
                    square_uid=square_uid,
                    provenance=provenance,
                )
                now = datetime(2026, 8, 1, 12, 8, tzinfo=timezone.utc)
                config = PipelineConfig(
                    mode=mode,
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at=now,
                    fixture_dir=FIXTURE if mode == "fixture" else None,
                    smart_money_enabled=True,
                    smart_money_square_mapping_evidence=mapping_path,
                    limit=5,
                )
                result = run_shadow_radar(
                    config,
                    clock=lambda: now,
                    market_client=(
                        _CatalogOnlyMarketClient(now) if mode == "real" else None
                    ),
                    smart_money_collector=lambda: evidence,
                    profile_content_fetcher=self._empty_profile,
                    profile_capture_time=now,
                )

                ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATIONS)
                self.addCleanup(ledger.close)
                author = ledger._connection.execute(  # noqa: SLF001 - receipt
                    "SELECT * FROM author_entity WHERE author_id = ?",
                    (square_uid,),
                ).fetchone()
                self.assertIsNotNone(author)
                self.assertEqual(
                    "BINANCE_SQUARE_UID_DIRECT_IDENTITY_EVIDENCE",
                    author["identity_source"],
                )
                artifact = ledger._connection.execute(  # noqa: SLF001 - receipt
                    "SELECT * FROM smart_money_identity_artifact"
                ).fetchone()
                self.assertEqual(str(mapping_path), artifact["artifact_path"])
                self.assertEqual("APPROVED", artifact["promotion_status"])
                self.assertEqual(
                    (1, 1, 1),
                    (
                        ledger._connection.execute(  # noqa: SLF001 - receipt
                            "SELECT COUNT(*) FROM smart_money_identity_artifact"
                        ).fetchone()[0],
                        ledger._connection.execute(  # noqa: SLF001 - receipt
                            "SELECT COUNT(*) FROM smart_money_identity_mapping_event "
                            "WHERE event_type = 'LINK'"
                        ).fetchone()[0],
                        len(ledger.list_smart_money_square_identity_mappings()),
                    ),
                )
                self.assertEqual("SUCCEEDED", ledger.get_attempt(result.attempt_id).status)

    def test_proposed_v2_single_mapping_never_creates_evidence_author_or_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mapping_dir = root / "mapping"
            mapping_dir.mkdir()
            evidence = self._smart_money_evidence(provenance="FIXTURE_REPLAY")
            top_trader_id = evidence["rankings"][0]["rows"][0]["source_id"]
            square_uid = "fixture-proposed-square-uid"
            mapping_path, _, _ = write_v2_identity_evidence(
                str(mapping_dir),
                top_trader_id=top_trader_id,
                square_uid=square_uid,
                provenance="FIXTURE_REPLAY",
            )
            requested: list[str] = []

            def fetch_profile(value: str, offset: int) -> dict[str, object]:
                requested.append(value)
                return self._empty_profile(value, offset)

            now = datetime(2026, 8, 1, 12, 8, tzinfo=timezone.utc)
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at=now,
                    fixture_dir=FIXTURE,
                    smart_money_enabled=True,
                    smart_money_square_mapping_evidence=mapping_path,
                    limit=5,
                ),
                clock=lambda: now,
                smart_money_collector=lambda: evidence,
                profile_content_fetcher=fetch_profile,
                profile_capture_time=now,
            )

            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            self.assertEqual([], requested)
            self.assertIsNone(
                ledger._connection.execute(  # noqa: SLF001 - receipt
                    "SELECT 1 FROM author_entity WHERE author_id = ?", (square_uid,)
                ).fetchone()
            )
            self.assertEqual(
                (0, 0, 0),
                (
                    ledger._connection.execute(  # noqa: SLF001 - receipt
                        "SELECT COUNT(*) FROM smart_money_identity_artifact"
                    ).fetchone()[0],
                    ledger._connection.execute(  # noqa: SLF001 - receipt
                        "SELECT COUNT(*) FROM smart_money_identity_mapping_event"
                    ).fetchone()[0],
                    len(ledger.list_smart_money_square_identity_mappings()),
                ),
            )
            self.assertEqual("SUCCEEDED", ledger.get_attempt(result.attempt_id).status)

    def test_legacy_v1_remains_fixture_fetch_compatible_but_is_not_activated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = self._smart_money_evidence(provenance="FIXTURE_REPLAY")
            top_trader_id = evidence["rankings"][0]["rows"][0]["source_id"]
            square_uid = "legacy-fixture-square-uid"
            mapping_path = root / "legacy-mapping.json"
            mapping_path.write_text(
                json.dumps(
                    {
                        "schema": "binance-smart-money-square-identity-mapping/v1",
                        "captured_at_utc": "2026-08-01T12:05:00Z",
                        "provenance": "FIXTURE_REPLAY",
                        "mappings": [
                            {
                                "topTraderId": top_trader_id,
                                "squareUid": square_uid,
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            requested: list[str] = []

            def fetch_profile(value: str, offset: int) -> dict[str, object]:
                requested.append(value)
                return self._empty_profile(value, offset)

            now = datetime(2026, 8, 1, 12, 8, tzinfo=timezone.utc)
            result = run_shadow_radar(
                PipelineConfig(
                    mode="fixture",
                    output_dir=root / "runs",
                    database=root / "radar.sqlite",
                    decision_at=now,
                    fixture_dir=FIXTURE,
                    smart_money_enabled=True,
                    smart_money_square_mapping_evidence=mapping_path,
                    limit=5,
                ),
                clock=lambda: now,
                smart_money_collector=lambda: evidence,
                profile_content_fetcher=fetch_profile,
                profile_capture_time=now,
            )

            ledger = SQLiteRunLedger(root / "radar.sqlite", MIGRATIONS)
            self.addCleanup(ledger.close)
            self.assertEqual([square_uid], requested)
            self.assertEqual(
                (0, 0, 0),
                (
                    ledger._connection.execute(  # noqa: SLF001 - receipt
                        "SELECT COUNT(*) FROM smart_money_identity_artifact"
                    ).fetchone()[0],
                    ledger._connection.execute(  # noqa: SLF001 - receipt
                        "SELECT COUNT(*) FROM smart_money_identity_mapping_event"
                    ).fetchone()[0],
                    len(ledger.list_smart_money_square_identity_mappings()),
                ),
            )
            self.assertEqual("SUCCEEDED", ledger.get_attempt(result.attempt_id).status)


if __name__ == "__main__":
    unittest.main()
