from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from scanner.market import MarketSource
from scanner.reports import (
    ReportValidationError,
    build_local_report,
    render_local_markdown,
    render_telegram,
)


def report_input(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "scanned_at": "2026-08-01T07:15:00Z",
        "post_counts": {
            "discovered": 9,
            "total": 7,
            "accepted": 7,
            "quarantine": 2,
            "new": 5,
            "duplicate": 2,
        },
        "author_coverage": {
            "tier_a": {
                "covered": 1,
                "expected": 2,
                "identity_sources": ["PROFILE_ID", "LEADERBOARD_30D"],
            },
            "tier_b": {
                "covered": 0,
                "expected": 1,
                "identity_sources": [],
            },
        },
        "leaderboard_coverage": {
            "covered": 0,
            "expected": 4,
            "status": "BLOCKED",
            "reason": "leaderboard DOM unavailable",
        },
        "top_opportunities": [],
        "observations": [],
        "filtered": {"RR below 2.0": 3},
        "snapshot_path": "/tmp/v4/reports/run-001.json",
        "limitations": ["Tier B profile coverage is incomplete"],
    }
    payload.update(overrides)
    return payload


def smart_money_input() -> dict[str, object]:
    return {
        "status": "COMPLETE",
        "observation_semantics": "OBSERVED_WINDOW",
        "captured_at_utc": "2026-08-01T12:05:00Z",
        "leaderboard_data_updated_at_utc": "2026-08-01T11:59:59Z",
        "leaderboard_data_updated_at_ms": 1785585599000,
        "leaderboard_observed_window": {
            "started_at_utc": "2026-08-01T12:00:01Z",
            "completed_at_utc": "2026-08-01T12:00:07Z",
            "duration_seconds": 6,
        },
        "ranking_coverage": {
            "covered": 2,
            "expected": 2,
            "ranking_types": ["PNL", "ROI"],
            "rendered_rank_rows": 60,
        },
        "profile_detail_coverage": {
            "covered": 60,
            "expected": 60,
            "failed": 0,
            "status": "COMPLETE",
        },
        "square_identity_mapping_coverage": {
            "covered": 0,
            "expected": 60,
            "verification_method": "EXPLICIT_SOURCE_EVIDENCE_ONLY",
        },
        "unique_top_trader_count": 60,
        "tier_a_eligible": 0,
        "tier_a_policy": "rank/profile evidence does not prove Square identity",
        "evidence_path": "/tmp/run/smart_money.json",
    }


class LocalReportContractTests(unittest.TestCase):
    def test_latest_report_cli_renders_the_existing_telegram_contract(self) -> None:
        report = build_local_report(report_input())
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(
                json.dumps(report, ensure_ascii=False), encoding="utf-8"
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).parents[1]
                        / "scripts"
                        / "render_latest_telegram.py"
                    ),
                    "--report",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(render_telegram(report), completed.stdout.rstrip("\n"))

    def test_latest_report_cli_marks_cached_report_when_capture_is_degraded(
        self,
    ) -> None:
        report = build_local_report(report_input())
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(
                json.dumps(report, ensure_ascii=False), encoding="utf-8"
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).parents[1]
                        / "scripts"
                        / "render_latest_telegram.py"
                    ),
                    "--report",
                    str(report_path),
                    "--degraded",
                    "自动重试 2 次仍未恢复",
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        message = completed.stdout.rstrip("\n")
        self.assertEqual("📡 币安合约雷达", message.splitlines()[0])
        self.assertEqual(
            "🔴 状态：本轮数据更新失败，自动重试 2 次仍未恢复",
            message.splitlines()[1],
        )
        self.assertEqual("📌 以下为最近一次成功结果", message.splitlines()[2])
        self.assertIn("🕒 数据时间：2026-08-01 00:15 PDT", message)
        self.assertNotIn("/tmp/", message)

    def test_profile_cohort_counts_must_reconcile_to_declared_denominator(self) -> None:
        profile_channel = {
            "status": "PARTIAL",
            "smart_money_profiles": {
                "status": "PARTIAL",
                "planned_authors": 60,
                "complete_authors": 1,
                "empty_authors": 2,
                "partial_authors": 3,
                "failed_authors": 4,
                "not_attempted_authors": 49,
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 9,
                "complete_authors": 0,
                "empty_authors": 9,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 60,
                "seed_profiles": 9,
            },
        }

        with self.assertRaisesRegex(
            ReportValidationError,
            "profile_channel.smart_money_profiles.*sum to denominator",
        ):
            build_local_report(report_input(profile_channel=profile_channel))

    def test_profile_cohort_outcome_rows_must_reconcile_to_denominator(self) -> None:
        profile_channel = {
            "status": "COMPLETE",
            "smart_money_profiles": {
                "status": "COMPLETE",
                "planned_authors": 2,
                "complete_authors": 1,
                "empty_authors": 1,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "trader-1", "status": "COMPLETE"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 2,
                "seed_profiles": 0,
            },
        }

        with self.assertRaisesRegex(
            ReportValidationError,
            "profile_channel.smart_money_profiles.outcomes must contain 2 rows",
        ):
            build_local_report(report_input(profile_channel=profile_channel))

    def test_profile_cohort_outcome_statuses_must_match_summary_counts(self) -> None:
        profile_channel = {
            "status": "COMPLETE",
            "smart_money_profiles": {
                "status": "COMPLETE",
                "planned_authors": 2,
                "complete_authors": 1,
                "empty_authors": 1,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "trader-1", "status": "COMPLETE"},
                    {"top_trader_id": "trader-2", "status": "PARTIAL"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 2,
                "seed_profiles": 0,
            },
        }

        with self.assertRaisesRegex(
            ReportValidationError,
            "profile_channel.smart_money_profiles outcomes do not match summary counts",
        ):
            build_local_report(report_input(profile_channel=profile_channel))

    def test_profile_cohort_coverage_counts_complete_and_empty_but_not_partial(
        self,
    ) -> None:
        profile_channel = {
            "status": "PARTIAL",
            "smart_money_profiles": {
                "status": "PARTIAL",
                "planned_authors": 4,
                "complete_authors": 1,
                "empty_authors": 1,
                "partial_authors": 2,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "trader-1", "status": "COMPLETE"},
                    {"top_trader_id": "trader-2", "status": "EMPTY"},
                    {"top_trader_id": "trader-3", "status": "PARTIAL"},
                    {"top_trader_id": "trader-4", "status": "PARTIAL"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 4,
                "seed_profiles": 0,
            },
        }

        report = build_local_report(report_input(profile_channel=profile_channel))
        smart_money_profiles = report["profile_channel"]["smart_money_profiles"]

        self.assertEqual("PARTIAL", smart_money_profiles["status"])
        self.assertEqual(
            {
                "covered": 2,
                "expected": 4,
                "label": "2/4 (50.0%)",
            },
            smart_money_profiles["coverage"],
        )
        self.assertEqual(
            {
                "covered": 2,
                "expected": 4,
                "label": "2/4 (50.0%)",
            },
            report["profile_channel"]["coverage"],
        )
        self.assertIn(
            "Smart Money Profiles：状态 PARTIAL｜coverage 2/4 (50.0%)",
            render_local_markdown(report),
        )

    def test_profile_aggregate_status_cannot_claim_complete_over_partial_cohort(
        self,
    ) -> None:
        profile_channel = {
            "status": "COMPLETE",
            "smart_money_profiles": {
                "status": "PARTIAL",
                "planned_authors": 2,
                "complete_authors": 1,
                "empty_authors": 0,
                "partial_authors": 1,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "trader-1", "status": "COMPLETE"},
                    {"top_trader_id": "trader-2", "status": "PARTIAL"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 2,
                "seed_profiles": 0,
            },
        }

        with self.assertRaisesRegex(
            ReportValidationError,
            "profile_channel.status.*aggregate terminal status counts",
        ):
            build_local_report(report_input(profile_channel=profile_channel))

    def test_explicit_profile_source_status_must_match_normalized_profile_status(
        self,
    ) -> None:
        profile_channel = {
            "status": "PARTIAL",
            "smart_money_profiles": {
                "status": "PARTIAL",
                "planned_authors": 2,
                "complete_authors": 1,
                "empty_authors": 0,
                "partial_authors": 1,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "trader-1", "status": "COMPLETE"},
                    {"top_trader_id": "trader-2", "status": "PARTIAL"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 2,
                "seed_profiles": 0,
            },
        }

        with self.assertRaisesRegex(
            ReportValidationError,
            "source_coverage.PROFILE.status must match normalized profile status",
        ):
            build_local_report(
                report_input(
                    profile_channel=profile_channel,
                    source_coverage={
                        "PROFILE": {
                            "status": "COMPLETE",
                            "provenance": "UNKNOWN",
                            "source_capture_time_utc": None,
                        }
                    },
                )
            )

    def test_all_empty_profile_aggregate_maps_to_complete_source_status(self) -> None:
        captured_at = "2026-08-01T07:14:00Z"
        profile_channel = {
            "status": "EMPTY",
            "provenance": "LIVE_CAPTURE",
            "source_capture_time_utc": captured_at,
            "smart_money_profiles": {
                "status": "EMPTY",
                "planned_authors": 2,
                "complete_authors": 0,
                "empty_authors": 2,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "trader-1", "status": "EMPTY"},
                    {"top_trader_id": "trader-2", "status": "EMPTY"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 2,
                "seed_profiles": 0,
            },
        }

        report = build_local_report(
            report_input(
                profile_channel=profile_channel,
                source_coverage={
                    "PROFILE": {
                        "status": "EMPTY",
                        "provenance": "LIVE_CAPTURE",
                        "source_capture_time_utc": captured_at,
                    }
                },
            )
        )

        self.assertEqual("COMPLETE", report["profile_channel"]["status"])
        self.assertEqual("COMPLETE", report["source_coverage"]["PROFILE"]["status"])
        self.assertEqual(
            "2/2 (100.0%)",
            report["profile_channel"]["coverage"]["label"],
        )

    def test_zero_denominator_profile_aggregate_stays_not_attempted(self) -> None:
        profile_channel = {
            "status": "NOT_ATTEMPTED",
            "smart_money_profiles": {
                "status": "NOT_ATTEMPTED",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 0,
                "seed_profiles": 0,
            },
        }

        report = build_local_report(report_input(profile_channel=profile_channel))

        self.assertEqual("NOT_ATTEMPTED", report["profile_channel"]["status"])
        self.assertEqual(
            "NOT_ATTEMPTED",
            report["source_coverage"]["PROFILE"]["status"],
        )
        self.assertEqual(
            "0/0 (coverage unavailable)",
            report["profile_channel"]["coverage"]["label"],
        )

    def test_profile_structure_without_denominators_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ReportValidationError,
            "profile_channel.cohort_denominators is required",
        ):
            build_local_report(
                report_input(
                    profile_channel={
                        "status": "COMPLETE",
                        "planned_authors": 20,
                        "complete_authors": 19,
                        "partial_authors": 1,
                    }
                )
            )

    def test_profile_outcome_identities_must_be_unique(self) -> None:
        profile_channel = {
            "status": "COMPLETE",
            "planned_authors": 2,
            "complete_authors": 2,
            "empty_authors": 0,
            "partial_authors": 0,
            "failed_authors": 0,
            "not_attempted_authors": 0,
            "smart_money_profiles": {
                "status": "COMPLETE",
                "planned_authors": 2,
                "complete_authors": 2,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "outcomes": [
                    {"top_trader_id": "duplicate", "status": "COMPLETE"},
                    {"top_trader_id": "duplicate", "status": "COMPLETE"},
                ],
            },
            "seed_profiles": {
                "status": "EMPTY",
                "planned_authors": 0,
                "complete_authors": 0,
                "empty_authors": 0,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
            },
            "cohort_denominators": {
                "smart_money_profiles": 2,
                "seed_profiles": 0,
            },
        }

        with self.assertRaisesRegex(
            ReportValidationError,
            "outcome identities must be unique",
        ):
            build_local_report(report_input(profile_channel=profile_channel))

    def test_profile_cohorts_render_separate_complete_count_lines(self) -> None:
        profile_channel = {
            "status": "PARTIAL",
            "planned_authors": 69,
            "complete_authors": 8,
            "empty_authors": 4,
            "partial_authors": 3,
            "failed_authors": 4,
            "not_attempted_authors": 50,
            "source_records": 24,
            "smart_money_profiles": {
                "status": "PARTIAL",
                "planned_authors": 60,
                "complete_authors": 1,
                "empty_authors": 2,
                "partial_authors": 3,
                "failed_authors": 4,
                "not_attempted_authors": 50,
                "source_records": 13,
                "square_identity_mapping_coverage": {
                    "covered": 1,
                    "expected": 60,
                    "label": "1/60 (1.7%)",
                },
                "outcomes": [
                    *(
                        {"top_trader_id": f"complete-{index}", "status": "COMPLETE"}
                        for index in range(1)
                    ),
                    *(
                        {"top_trader_id": f"empty-{index}", "status": "EMPTY"}
                        for index in range(2)
                    ),
                    *(
                        {"top_trader_id": f"partial-{index}", "status": "PARTIAL"}
                        for index in range(3)
                    ),
                    *(
                        {"top_trader_id": f"failed-{index}", "status": "FAILED"}
                        for index in range(4)
                    ),
                    *(
                        {
                            "top_trader_id": f"pending-{index}",
                            "status": "NOT_ATTEMPTED",
                        }
                        for index in range(50)
                    ),
                ],
            },
            "seed_profiles": {
                "status": "COMPLETE",
                "planned_authors": 9,
                "complete_authors": 7,
                "empty_authors": 2,
                "partial_authors": 0,
                "failed_authors": 0,
                "not_attempted_authors": 0,
                "source_records": 11,
                "outcomes": [
                    *(
                        {"author_id": f"seed-complete-{index}", "status": "COMPLETE"}
                        for index in range(7)
                    ),
                    *(
                        {"author_id": f"seed-empty-{index}", "status": "EMPTY"}
                        for index in range(2)
                    ),
                ],
            },
            "cohort_denominators": {
                "smart_money_profiles": 60,
                "seed_profiles": 9,
            },
        }

        markdown = render_local_markdown(
            build_local_report(report_input(profile_channel=profile_channel))
        )

        self.assertIn(
            "Profile主通道：PARTIAL｜计划作者 69｜完成 8｜未尝试 50",
            markdown,
        )
        self.assertIn(
            "Smart Money Profiles：状态 PARTIAL｜coverage 3/60 (5.0%)｜"
            "计划 60｜完成 1｜空 2｜部分 3｜失败 4｜"
            "未尝试 50｜来源记录 13｜mapping 1/60 (1.7%)",
            markdown,
        )
        self.assertIn(
            "Seed Profiles：状态 COMPLETE｜coverage 9/9 (100.0%)｜"
            "计划 9｜完成 7｜空 2｜部分 0｜失败 0｜"
            "未尝试 0｜来源记录 11",
            markdown,
        )

    def test_feed_coverage_contract_is_visible_in_json_and_markdown(self) -> None:
        report = build_local_report(
            report_input(
                report_generated_at="2026-08-01T08:02:00Z",
                source_coverage={
                    "FEED": {
                        "status": "PARTIAL",
                        "provenance": "LIVE_CAPTURE",
                        "source_capture_time_utc": "2026-08-01T08:01:00Z",
                        "coverage_contract_version": "square-feed-coverage/v1",
                        "coverage_status": "PARTIAL",
                        "termination_reason": "SCROLL_LIMIT",
                        "reason": "scroll budget reached",
                    }
                },
            )
        )

        feed = report["source_coverage"]["FEED"]
        self.assertEqual("PARTIAL", feed["coverage_status"])
        self.assertEqual("SCROLL_LIMIT", feed["termination_reason"])
        self.assertIn(
            "coverage PARTIAL｜termination SCROLL_LIMIT",
            render_local_markdown(report),
        )

    def test_source_coverage_keeps_capture_time_separate_from_report_time(self) -> None:
        report = build_local_report(
            report_input(
                report_generated_at="2026-08-01T13:00:00Z",
                source_coverage={
                    "FEED": {
                        "status": "COMPLETE",
                        "provenance": "FIXTURE_REPLAY",
                        "source_capture_time_utc": "2026-07-30T05:48:36Z",
                        "evidence_path": "/fixtures/feed.json",
                        "reason": "immutable fixture",
                    },
                    "SMART_MONEY": {
                        "status": "FAILED",
                        "provenance": "LIVE_CAPTURE",
                        "source_capture_time_utc": "2026-08-01T12:00:07Z",
                        "reason": "public endpoint timeout",
                    },
                },
            )
        )

        coverage = report["source_coverage"]
        self.assertEqual(
            (
                "FEED",
                "BINANCE_OFFICIAL_NEWS",
                "SMART_MONEY",
                "PROFILE",
                "MARKET_CATALOG",
            ),
            tuple(coverage),
        )
        self.assertEqual("FIXTURE_REPLAY", coverage["FEED"]["provenance"])
        self.assertEqual(
            "2026-07-30T05:48:36Z",
            coverage["FEED"]["source_capture_time_utc"],
        )
        self.assertEqual("/fixtures/feed.json", coverage["FEED"]["evidence_path"])
        self.assertEqual("NOT_ATTEMPTED", coverage["BINANCE_OFFICIAL_NEWS"]["status"])
        self.assertIsNone(coverage["BINANCE_OFFICIAL_NEWS"]["source_capture_time_utc"])
        markdown = render_local_markdown(report)
        self.assertIn("报告生成时间 UTC：2026-08-01T13:00:00Z", markdown)
        self.assertIn(
            "FEED：COMPLETE｜FIXTURE_REPLAY｜source capture 2026-07-30T05:48:36Z",
            markdown,
        )
        self.assertNotIn(
            "BINANCE_OFFICIAL_NEWS：NOT_ATTEMPTED｜UNKNOWN｜source capture 2026-08-01T13:00:00Z",
            markdown,
        )

    def test_cdo_capture_timing_aliases_are_consumed_without_clock_fallback(
        self,
    ) -> None:
        report = build_local_report(
            report_input(
                feed_provenance="LIVE_CAPTURE",
                market_provenance="LIVE_CAPTURE",
                capture_timing={
                    "discovery_snapshot_at": "2026-08-01T12:00:00Z",
                    "detail_fetch_started": "2026-08-01T12:00:01Z",
                    "detail_fetch_completed": "2026-08-01T12:00:03Z",
                    "market_catalog": "2026-08-01T12:00:04Z",
                    "report": "2026-08-01T12:00:10Z",
                },
            )
        )

        self.assertEqual("2026-08-01T12:00:10Z", report["report_generated_at"])
        self.assertEqual("COMPLETE", report["source_coverage"]["FEED"]["status"])
        self.assertEqual(
            "COMPLETE", report["source_coverage"]["MARKET_CATALOG"]["status"]
        )
        self.assertEqual(
            "2026-08-01T12:00:04Z",
            report["source_coverage"]["MARKET_CATALOG"]["source_capture_time_utc"],
        )

        with self.assertRaisesRegex(ReportValidationError, "report_generated_at"):
            build_local_report(
                report_input(
                    report_generated_at="2026-08-01T11:59:59Z",
                    source_coverage={
                        "FEED": {
                            "status": "COMPLETE",
                            "provenance": "LIVE_CAPTURE",
                            "source_capture_time_utc": "2026-08-01T12:00:00Z",
                        }
                    },
                )
            )

    def test_smart_money_rank_profile_and_identity_coverage_are_separate(self) -> None:
        report = build_local_report(
            report_input(
                leaderboard_coverage={
                    "covered": 2,
                    "expected": 2,
                    "status": "COMPLETE",
                    "complete_top30": True,
                    "ranking_types": ["PNL", "ROI"],
                    "rendered_rank_rows": 60,
                },
                smart_money=smart_money_input(),
            )
        )
        markdown = render_local_markdown(report)
        telegram = render_telegram(report)

        self.assertEqual("2/2 (100.0%)", report["leaderboard_coverage"]["label"])
        self.assertEqual(
            "60/60 (100.0%)",
            report["smart_money"]["profile_detail_coverage"]["label"],
        )
        self.assertEqual(
            "0/60 (0.0%)",
            report["smart_money"]["square_identity_mapping_coverage"]["label"],
        )
        self.assertEqual("PARTIAL", report["source_coverage"]["SMART_MONEY"]["status"])
        self.assertEqual(
            "UNKNOWN", report["source_coverage"]["SMART_MONEY"]["provenance"]
        )
        self.assertIn("OBSERVED_WINDOW", markdown)
        self.assertIn("60行", markdown)
        self.assertIn("Tier A eligible=0", markdown)
        self.assertIn("交易员身份映射不完整", telegram)
        self.assertIn("Square身份未解析", report["risk_banner"]["labels"])

    def test_smart_money_rank_coverage_cannot_claim_identity_coverage(self) -> None:
        invalid = smart_money_input()
        invalid["square_identity_mapping_coverage"] = {
            "covered": 1,
            "expected": 59,
            "verification_method": "EXPLICIT_SOURCE_EVIDENCE_ONLY",
        }
        with self.assertRaisesRegex(
            ReportValidationError, "unique trader/detail/identity"
        ):
            build_local_report(
                report_input(
                    leaderboard_coverage={
                        "covered": 2,
                        "expected": 2,
                        "status": "COMPLETE",
                        "complete_top30": True,
                        "rendered_rank_rows": 60,
                    },
                    smart_money=invalid,
                )
            )

    def test_uses_real_scan_time_in_utc_and_los_angeles(self) -> None:
        report = build_local_report(report_input())

        self.assertEqual("2026-08-01T07:15:00Z", report["scanned_at"]["utc"])
        self.assertEqual(
            "2026-08-01T00:15:00-07:00",
            report["scanned_at"]["america_los_angeles"],
        )
        json.dumps(report)

        with self.assertRaises(ReportValidationError):
            build_local_report(report_input(scanned_at=None))

    def test_zero_opportunity_report_is_waiting_with_truthful_coverage(self) -> None:
        report = build_local_report(report_input())

        self.assertEqual("WAIT", report["status"])
        self.assertIsNone(report["report_generated_at"])
        self.assertEqual(24, report["window_hours"])
        self.assertEqual(
            {
                "discovered": 9,
                "total": 7,
                "accepted": 7,
                "quarantine": 2,
                "dq_quarantine": 2,
                "window_excluded": 0,
                "unique_accepted": 7,
                "new": 5,
                "duplicate": 2,
                "dedup_status": "COMPUTED",
                "source_observations": 9,
                "deduplicated_candidates": 9,
                "same_run_duplicates": 0,
            },
            report["post_counts"],
        )
        self.assertEqual("1/2 (50.0%)", report["author_coverage"]["tier_a"]["label"])
        self.assertEqual(
            ["PROFILE_ID", "LEADERBOARD_30D"],
            report["author_coverage"]["tier_a"]["identity_sources"],
        )
        self.assertEqual("0/4 (0.0%)", report["leaderboard_coverage"]["label"])
        self.assertEqual("BLOCKED", report["leaderboard_coverage"]["status"])
        self.assertEqual([], report["top_opportunities"])
        self.assertEqual("/tmp/v4/reports/run-001.json", report["snapshot_path"])

    def test_partial_seed_discovery_never_claims_top30_coverage(self) -> None:
        report = build_local_report(
            report_input(
                leaderboard_coverage={
                    "covered": 0,
                    "expected": 4,
                    "status": "PARTIAL_SEED_DISCOVERY",
                    "reason": "official mini-program entry verified; rows not rendered",
                    "verified_seed_profiles": 9,
                    "rendered_rank_rows": 0,
                    "complete_top30": False,
                    "seed_scope": "PROFILE_BACKED",
                    "evidence_captured_at_utc": "2026-08-01T08:50:34Z",
                }
            )
        )

        markdown = render_local_markdown(report)
        telegram = render_telegram(report)
        self.assertEqual("0/4 (0.0%)", report["leaderboard_coverage"]["label"])
        self.assertIn("排行榜部分覆盖", report["risk_banner"]["labels"])
        self.assertIn("Profile种子 9｜已渲染榜单行 0｜非TOP30", markdown)
        self.assertIn("排行榜仅部分覆盖", telegram)

        invalid_partial_claims = (
            {
                "covered": 1,
                "expected": 4,
                "status": "PARTIAL_SEED_DISCOVERY",
                "verified_seed_profiles": 9,
                "rendered_rank_rows": 0,
                "complete_top30": False,
                "seed_scope": "PROFILE_BACKED",
            },
            {
                "covered": 0,
                "expected": 4,
                "status": "PARTIAL_SEED_DISCOVERY",
                "verified_seed_profiles": 9,
                "rendered_rank_rows": 0,
                "seed_scope": "PROFILE_BACKED",
            },
            {
                "covered": 0,
                "expected": 4,
                "status": "PARTIAL_SEED_DISCOVERY",
                "verified_seed_profiles": 9,
                "rendered_rank_rows": 1,
                "complete_top30": False,
                "seed_scope": "PROFILE_BACKED",
            },
            {
                "covered": 0,
                "expected": 4,
                "status": "PARTIAL_SEED_DISCOVERY",
                "verified_seed_profiles": 9,
                "rendered_rank_rows": 0,
                "complete_top30": False,
                "seed_scope": "LEADERBOARD_ROWS",
            },
        )
        for claim in invalid_partial_claims:
            with (
                self.subTest(claim=claim),
                self.assertRaisesRegex(ReportValidationError, "partial seed discovery"),
            ):
                build_local_report(report_input(leaderboard_coverage=claim))

    def test_uncomputed_dedup_is_not_rendered_as_zero_or_as_24h_discovery(self) -> None:
        report = build_local_report(
            report_input(
                post_counts={
                    "discovered": 25,
                    "total": 11,
                    "accepted": 11,
                    "quarantine": 14,
                    "dq_quarantine": 0,
                    "window_excluded": 14,
                    "new": None,
                    "duplicate": None,
                    "dedup_status": "NOT_COMPUTED",
                }
            )
        )

        markdown = render_local_markdown(report)
        telegram = render_telegram(report)

        self.assertEqual(25, report["post_counts"]["discovered"])
        self.assertIsNone(report["post_counts"]["new"])
        self.assertIn(
            "发现25 / 窗口内11 / accepted 11 / 窗口排除14 / DQ隔离0 / 新增未计算 / 重复未计算",
            markdown,
        )
        self.assertIn(
            "📊 扫描 25｜有效 11｜新增 未计算",
            telegram,
        )
        self.assertNotIn("24h帖子：总数25", markdown)

    def test_quarantine_split_must_reconcile(self) -> None:
        with self.assertRaisesRegex(ReportValidationError, "quarantine must equal"):
            build_local_report(
                report_input(
                    post_counts={
                        "discovered": 25,
                        "total": 11,
                        "accepted": 11,
                        "quarantine": 14,
                        "dq_quarantine": 1,
                        "window_excluded": 14,
                        "new": None,
                        "duplicate": None,
                        "dedup_status": "NOT_COMPUTED",
                    }
                )
            )

    def test_all_report_count_invariants_are_enforced(self) -> None:
        invalid = (
            {
                "discovered": 8,
                "total": 7,
                "accepted": 7,
                "quarantine": 2,
                "new": 5,
                "duplicate": 2,
            },
            {
                "discovered": 9,
                "total": 8,
                "accepted": 7,
                "quarantine": 2,
                "new": 5,
                "duplicate": 2,
            },
            {
                "discovered": 9,
                "total": 7,
                "accepted": 7,
                "quarantine": 2,
                "unique_accepted": 6,
                "new": 5,
                "duplicate": 2,
            },
        )
        for counts in invalid:
            with self.subTest(counts=counts), self.assertRaises(ReportValidationError):
                build_local_report(report_input(post_counts=counts))

    def test_normalizes_dto_like_opportunities_and_applies_three_five_caps(
        self,
    ) -> None:
        def opportunity(index: int) -> SimpleNamespace:
            return SimpleNamespace(
                symbol=f"COIN{index}USDT",
                direction="LONG",
                entry=(Decimal("100.0"), Decimal("101.5")),
                stop_loss=Decimal("97"),
                tp1=Decimal("108"),
                tp2=Decimal("115"),
                current_price=Decimal("102.25"),
                invalidation="4h closes below 97",
                total_score=80 - index,
                evidence=("4h uptrend", "volume confirms"),
                source_post_url=f"https://www.binance.com/en/square/post/{1000 + index}",
                market_captured_at=datetime(2026, 8, 1, 7, 10, tzinfo=timezone.utc),
                evidence_captured_at=datetime(2026, 8, 1, 7, 5, tzinfo=timezone.utc),
                market_source=MarketSource.SPOT_PROXY
                if index == 0
                else MarketSource.FUTURES,
                missing_market_fields=("mark_price",) if index == 0 else (),
                parameter_source="AUTHOR",
                nominal_rr=Decimal("5"),
                cost_model_status="APPLIED",
            )

        observations = [
            {
                "symbol": f"WATCH{index}USDT",
                "direction": "SHORT",
                "score": 70,
                "waiting_condition": "wait for 1h close",
                "source_post_url": f"https://www.binance.com/en/square/post/{2000 + index}",
                "market_captured_at": "2026-08-01T07:11:00Z",
                "market_source": "FUTURES",
            }
            for index in range(6)
        ]

        report = build_local_report(
            report_input(
                top_opportunities=[opportunity(index) for index in range(4)],
                observations=observations,
            )
        )

        self.assertEqual("OPPORTUNITIES", report["status"])
        self.assertEqual(3, len(report["top_opportunities"]))
        self.assertEqual(5, len(report["observations"]))
        first = report["top_opportunities"][0]
        self.assertEqual(["100.0", "101.5"], first["entry"])
        self.assertEqual("97", first["stop_loss"])
        self.assertEqual("SPOT_PROXY", first["market_source"])
        self.assertEqual("2026-08-01T07:10:00Z", first["market_captured_at"])
        self.assertEqual(["mark_price"], first["missing_market_fields"])
        json.dumps(report)

    def test_top_opportunity_requires_source_url_and_market_capture_time(self) -> None:
        complete = {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry": ["62000", "62500"],
            "stop_loss": "61000",
            "tp1": "64500",
            "tp2": "67000",
            "current_price": "63000",
            "invalidation": "4h close below 61000",
            "score": 81,
            "evidence": ["4h structure aligned"],
            "source_post_url": "https://www.binance.com/en/square/post/3001",
            "market_captured_at": "2026-08-01T07:12:00Z",
            "evidence_captured_at": "2026-08-01T07:05:00Z",
            "market_source": "FUTURES",
            "parameter_source": "AUTHOR",
            "nominal_rr": "5",
            "cost_model_status": "APPLIED",
        }

        for missing_field in (
            "entry",
            "stop_loss",
            "tp1",
            "tp2",
            "current_price",
            "invalidation",
            "parameter_source",
            "nominal_rr",
            "cost_model_status",
            "evidence",
            "source_post_url",
            "market_captured_at",
            "evidence_captured_at",
        ):
            with self.subTest(missing_field=missing_field):
                incomplete = dict(complete)
                incomplete.pop(missing_field)
                with self.assertRaisesRegex(ReportValidationError, missing_field):
                    build_local_report(report_input(top_opportunities=[incomplete]))

        for unsafe_status in ("NOT_APPLIED", "NOT_CONFIGURED", "UNKNOWN"):
            with (
                self.subTest(unsafe_status=unsafe_status),
                self.assertRaisesRegex(ReportValidationError, "cost_model_status"),
            ):
                unsafe = dict(complete, cost_model_status=unsafe_status)
                build_local_report(report_input(top_opportunities=[unsafe]))

    def test_full_markdown_puts_proxy_and_concentration_risks_first(self) -> None:
        top = {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry": ["62000", "62500"],
            "stop_loss": "61000",
            "tp1": "64500",
            "tp2": "67000",
            "current_price": "63000",
            "invalidation": "4h close below 61000",
            "score": 81,
            "evidence": ["4h structure aligned", "volume confirms"],
            "source_post_url": "https://www.binance.com/en/square/post/3001",
            "market_captured_at": "2026-08-01T07:12:00Z",
            "evidence_captured_at": "2026-08-01T07:05:00Z",
            "market_source": "SPOT_PROXY",
            "missing_market_fields": ["mark_price", "funding_rate"],
            "parameter_source": "AUTHOR",
            "nominal_rr": "5",
            "cost_model_status": "APPLIED",
        }
        report = build_local_report(
            report_input(
                top_opportunities=[top],
                concentration_risk="TOP opportunities share BTC beta",
            )
        )

        markdown = render_local_markdown(report)
        first_line = markdown.splitlines()[0]

        self.assertIn("SPOT PROXY", first_line)
        self.assertIn("集中风险", first_line)
        self.assertIn("排行榜阻塞", first_line)
        self.assertIn("抓取时间 UTC：2026-08-01T07:15:00Z", markdown)
        self.assertIn(
            "帖子口径：发现9 / 窗口内7 / accepted 7 / 窗口排除0 / DQ隔离2 / 新增5 / 重复2",
            markdown,
        )
        self.assertIn("Tier A：1/2 (50.0%)", markdown)
        self.assertIn("身份来源：PROFILE_ID, LEADERBOARD_30D", markdown)
        self.assertIn("排行榜：0/4 (0.0%)｜BLOCKED", markdown)
        self.assertIn("## TOP 1｜BTCUSDT LONG｜SPOT PROXY", markdown)
        self.assertIn("Entry：62000–62500", markdown)
        self.assertIn("SL：61000｜TP1：64500｜TP2：67000｜现价：63000", markdown)
        self.assertIn("名义RR：5｜成本模型：APPLIED", markdown)
        self.assertIn("行情抓取：2026-08-01T07:12:00Z", markdown)
        self.assertIn("来源：https://www.binance.com/en/square/post/3001", markdown)
        self.assertIn("过滤原因：RR below 2.0 × 3", markdown)
        self.assertIn("完整快照：/tmp/v4/reports/run-001.json", markdown)

        telegram = render_telegram(report)
        self.assertEqual("📡 币安合约雷达", telegram.splitlines()[0])
        self.assertEqual("🟢 结论：发现 1 个可执行信号", telegram.splitlines()[1])
        self.assertIn("📊 扫描 9｜有效 7｜新增 5", telegram)
        self.assertIn("🟢 1. BTCUSDT 做多｜评分 81", telegram)
        self.assertIn("入场 62000–62500｜止损 61000｜目标 64500 / 67000", telegram)
        self.assertIn("现价 63000｜RR 5", telegram)
        self.assertIn(
            "来源 https://www.binance.com/en/square/post/3001",
            telegram,
        )
        self.assertIn("部分行情使用现货代理", telegram)
        self.assertIn("候选信号存在集中风险", telegram)
        self.assertNotIn("/tmp/", telegram)
        self.assertNotIn("LONG", telegram)
        self.assertNotIn("SPOT_PROXY", telegram)
        self.assertNotIn("APPLIED", telegram)
        self.assertLessEqual(len(telegram), 1200)

    def test_telegram_zero_opportunity_message_is_decision_first_and_private(self) -> None:
        message = render_telegram(build_local_report(report_input()))

        self.assertEqual("📡 币安合约雷达", message.splitlines()[0])
        self.assertEqual(
            "🟡 结论：本轮无可执行信号，继续等待",
            message.splitlines()[1],
        )
        self.assertIn("📊 扫描 9｜有效 7｜新增 5", message)
        self.assertIn("🧹 主要过滤：风险收益不足 × 3", message)
        self.assertIn("⚠️ 数据提示：排行榜数据不完整", message)
        self.assertIn("🕒 数据时间：2026-08-01 00:15 PDT", message)
        self.assertNotIn("/tmp/", message)
        self.assertNotIn("BLOCKED", message)
        self.assertLessEqual(len(message), 700)


if __name__ == "__main__":
    unittest.main()
