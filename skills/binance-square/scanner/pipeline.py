"""Shadow-only orchestration from post evidence to local audit reports."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from scripts.collect_square_v4 import (
    _collect_fixture,
    _collect_live_urls,
    _public_get_detail,
)

from .authors import (
    SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA,
    SMART_MONEY_SQUARE_MAPPING_SCHEMA,
    SeedProfileEvidence,
    SmartMoneySquareIdentityEvidence,
    load_seed_profile_evidence,
    load_smart_money_square_identity_catalog,
    load_smart_money_square_identity_evidence,
)
from .binance_news import collect_binance_official_news
from .contracts import (
    AcceptedPostObservation,
    ContractViolation,
    DedupStatus,
    SCHEMA_VERSION,
    canonical_post_id,
    format_utc,
    parse_utc,
)
from .derivation import DerivationDisposition, DerivationResult, apply_derivation_policy
from .discovery import (
    CanonicalPostDiscovery,
    ChannelObservation,
    DeduplicatedDiscovery,
    ProfileFetchOutcome,
    feed_snapshot_post_urls,
    profile_first_detail_queue,
    plan_profile_fetches,
    reconcile_profile_fetch_plan,
    validate_feed_snapshot,
)
from .market import BinanceMarketClient, MarketApiError, MarketSnapshot
from .opportunities import (
    ConsensusObservation,
    SignalCandidate,
    build_consensus_index,
    extract_signal,
)
from .profile_pipeline import (
    ProfilePipelineResult,
    collect_profile_pages,
    public_get_profile_contents,
    run_profile_pipeline,
)
from .reports import build_local_report, render_local_markdown
from .scoring import build_opportunity_board, score_opportunity
from .smart_money import (
    EVIDENCE_SCHEMA_VERSION as SMART_MONEY_SCHEMA_VERSION,
    ORDER as SMART_MONEY_ORDER,
    PAGES as SMART_MONEY_PAGES,
    RANK_SOURCE as SMART_MONEY_RANK_SOURCE,
    RANKING_TYPES as SMART_MONEY_RANKING_TYPES,
    ROWS_PER_PAGE as SMART_MONEY_ROWS_PER_PAGE,
    SOURCE_ID_TYPE as SMART_MONEY_SOURCE_ID_TYPE,
    TIME_RANGE as SMART_MONEY_TIME_RANGE,
    collect_smart_money,
    verify_evidence_integrity,
)
from .square import PostDetail, discover_snapshot_post_urls
from .storage import (
    PostDiscoveryObservationInput,
    ProfileFetchOutcomeInput,
    SQLiteRunLedger,
    SmartMoneyLeaderboardRowInput,
)
from .tracking import tracking_signals_from_scored


PROJECT_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS = PROJECT_DIR / "migrations"
MAX_PRODUCTION_SLOT_LATENESS = timedelta(minutes=10)
MAX_DECISION_CLOCK_SKEW = timedelta(seconds=30)
# Backward-compatible internal name; it now denotes the ordered migration set.
MIGRATION = MIGRATIONS


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    mode: str
    output_dir: Path
    database: Path
    decision_at: str | datetime | None = None
    fixture_dir: Path | None = None
    input_snapshot: Path | None = None
    signals_json: Path | None = None
    leaderboard_seed_evidence: Path | None = None
    limit: int = 200
    job_namespace: str = "production"
    production_job_id: str = "binance-square-shadow-v4"
    no_send: bool = True
    scheduled_retry: bool = False
    dedup_baseline_post_ids: frozenset[str] | tuple[str, ...] | None = None
    smart_money_enabled: bool = False
    smart_money_fixture: Path | None = None
    smart_money_square_mapping_evidence: Path | None = None
    smart_money_square_mapping_catalog: Path | None = None
    official_news_enabled: bool = False


@dataclass(frozen=True, slots=True)
class PipelineResult:
    logical_run_id: str
    attempt_id: str
    raw_json: Path
    market_json: Path
    report_json: Path
    report_markdown: Path
    latest_json: Path
    latest_markdown: Path
    latest_pointer: Path
    smart_money_json: Path | None = None
    market_catalog_json: Path | None = None
    official_news_json: Path | None = None


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return format_utc(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            _json_value(payload), ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    ).encode("utf-8")


def _market_catalog_artifact(
    catalog: Any,
    *,
    logical_run_id: str,
    attempt_id: str,
    decision_at: str,
) -> dict[str, Any]:
    """Freeze the complete Futures catalog used by this attempt."""

    contracts = getattr(catalog, "contracts", {})
    if not isinstance(contracts, Mapping):
        contracts = {}
    records = []
    for symbol, contract in sorted(contracts.items()):
        records.append(
            {
                "symbol": str(getattr(contract, "symbol", symbol)),
                "status": str(getattr(contract, "status", "")),
                "contractType": str(getattr(contract, "contract_type", "")),
                "baseAsset": str(getattr(contract, "base_asset", "")),
                "quoteAsset": str(getattr(contract, "quote_asset", "")),
                "marginAsset": str(getattr(contract, "margin_asset", "")),
            }
        )
    records_bytes = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    captured_at = getattr(catalog, "captured_at", None)
    return {
        "schema_version": "binance-futures-catalog/v1",
        "source_system": "binance_public_futures_exchange_info",
        "logical_run_id": logical_run_id,
        "attempt_id": attempt_id,
        "decision_at_utc": format_utc(parse_utc(decision_at)),
        "captured_at_utc": format_utc(captured_at) if captured_at is not None else None,
        "server_time_ms": getattr(catalog, "server_time_ms", None),
        "record_count": len(records),
        "records_sha256": sha256(records_bytes).hexdigest(),
        "records": records,
    }


def _validate_official_news_document(
    document: Any,
    *,
    decision_at: str,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ContractViolation("official news evidence must be an object")
    status = str(document.get("status", "")).upper()
    if status not in {"COMPLETE", "PARTIAL", "FAILED"}:
        raise ContractViolation("official news evidence status is invalid")
    captured_at = format_utc(parse_utc(document.get("captured_at_utc")))
    records = document.get("records")
    if not isinstance(records, list):
        raise ContractViolation("official news records must be a list")
    cutoff = parse_utc(decision_at)
    window_start = cutoff - timedelta(hours=24)
    for record in records:
        if not isinstance(record, Mapping):
            raise ContractViolation("official news record must be an object")
        source_url = record.get("source_url")
        published = parse_utc(record.get("published_at_utc"))
        if (
            not isinstance(source_url, str)
            or not source_url.startswith(
                "https://www.binance.com/en/support/announcement/detail/"
            )
        ):
            raise ContractViolation("official news source URL is not Binance official")
        if not (window_start <= published < cutoff):
            raise ContractViolation("official news record is outside strict 24h")
    normalized = dict(document)
    normalized["status"] = status
    normalized["captured_at_utc"] = captured_at
    normalized["record_count"] = len(records)
    return normalized


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _replace_symlink(path: Path, target: str, attempt_id: str) -> None:
    temporary = path.with_name(f".{path.name}.{attempt_id}.tmp")
    if os.path.lexists(temporary):
        temporary.unlink()
    os.symlink(target, temporary)
    try:
        os.replace(temporary, path)
    except Exception:
        if os.path.lexists(temporary):
            temporary.unlink()
        raise


def _publish_latest(output_dir: Path, run_dir: Path, attempt_id: str) -> tuple[Path, Path, Path]:
    """Atomically switch one directory pointer for the JSON/Markdown pair."""

    output_dir.mkdir(parents=True, exist_ok=True)
    compatibility = (
        (output_dir / "latest.json", "latest/report.json"),
        (output_dir / "latest.md", "latest/report.md"),
    )
    for path, target in compatibility:
        if path.is_symlink() and os.readlink(path) == target:
            continue
        _replace_symlink(path, target, attempt_id)
    pointer = output_dir / "latest"
    relative_run = os.path.relpath(run_dir, output_dir)
    _replace_symlink(pointer, relative_run, attempt_id)
    return compatibility[0][0], compatibility[1][0], pointer


def repair_latest_from_succeeded_attempt(
    config: PipelineConfig,
    *,
    logical_run_id: str,
) -> PipelineResult:
    """Idempotently publish verified artifacts from an already-successful attempt.

    SQLite and filesystem pointers cannot share one transaction.  If the
    attempt commit succeeds but the symlink switch fails, this recovery path
    verifies every manifested artifact before repairing ``latest`` without
    creating a new attempt or re-running collection.
    """

    if not config.no_send:
        raise ValueError("latest repair is local-only and requires no_send")
    ledger = SQLiteRunLedger(config.database, MIGRATIONS)
    try:
        logical_run = next(
            (
                item
                for item in ledger.list_logical_runs()
                if item.logical_run_id == logical_run_id
            ),
            None,
        )
        if logical_run is None:
            raise ContractViolation("latest repair logical run does not exist")
        succeeded = [
            item
            for item in ledger.list_attempts(logical_run_id)
            if item.status == "SUCCEEDED"
        ]
        if len(succeeded) != 1:
            raise ContractViolation(
                "latest repair requires exactly one SUCCEEDED attempt"
            )
        attempt = succeeded[0]
        run_dir = (
            config.output_dir
            / logical_run_id
            / f"attempt-{attempt.attempt_no}"
        )
        raw_path = run_dir / "raw.json"
        market_path = run_dir / "market.json"
        market_catalog_path = run_dir / "market_catalog.json"
        official_news_path = run_dir / "official_news.json"
        smart_money_path = run_dir / "smart_money.json"
        report_path = run_dir / "report.json"
        markdown_path = run_dir / "report.md"
        manifests = {
            item.artifact_path: item
            for item in ledger.list_manifests(logical_run_id)
            if item.attempt_id == attempt.attempt_id
        }
        required_paths = [raw_path, market_path, report_path, markdown_path]
        if market_catalog_path.is_file() or str(market_catalog_path) in manifests:
            required_paths.append(market_catalog_path)
        if official_news_path.is_file() or str(official_news_path) in manifests:
            required_paths.append(official_news_path)
        if smart_money_path.is_file() or str(smart_money_path) in manifests:
            required_paths.append(smart_money_path)
        for path in required_paths:
            if not path.is_file():
                raise ContractViolation(f"latest repair artifact is missing: {path}")
            manifest = manifests.get(str(path))
            if manifest is None:
                raise ContractViolation(
                    f"latest repair manifest is missing: {path}"
                )
            if sha256(path.read_bytes()).hexdigest() != manifest.sha256_hex:
                raise ContractViolation(
                    f"latest repair artifact hash mismatch: {path}"
                )
        latest_json, latest_markdown, latest_pointer = _publish_latest(
            config.output_dir,
            run_dir,
            attempt.attempt_id,
        )
        return PipelineResult(
            logical_run_id=logical_run_id,
            attempt_id=attempt.attempt_id,
            raw_json=raw_path,
            market_json=market_path,
            report_json=report_path,
            report_markdown=markdown_path,
            latest_json=latest_json,
            latest_markdown=latest_markdown,
            latest_pointer=latest_pointer,
            smart_money_json=(smart_money_path if smart_money_path.is_file() else None),
            market_catalog_json=(
                market_catalog_path if market_catalog_path.is_file() else None
            ),
            official_news_json=(
                official_news_path if official_news_path.is_file() else None
            ),
        )
    finally:
        ledger.close()


def _scanned_at(raw: Mapping[str, Any], fallback: datetime) -> str:
    completed = raw.get("collection_completed_at_utc")
    if completed is not None:
        return format_utc(parse_utc(completed))
    observed = [
        item.get("observed_at")
        for item in raw.get("accepted", [])
        if isinstance(item, Mapping) and item.get("observed_at")
    ]
    if not observed:
        return format_utc(fallback)
    return format_utc(max(parse_utc(value) for value in observed))


def _latest_fetch_at(
    raw: Mapping[str, Any],
    market_cache: Mapping[str, Any | None],
    fallback: datetime,
) -> str:
    """Return the latest completed Square or market capture timestamp."""

    values = [parse_utc(_scanned_at(raw, fallback))]
    for snapshot in market_cache.values():
        captured_at = getattr(snapshot, "captured_at", None)
        if captured_at is not None:
            values.append(parse_utc(captured_at))
    return format_utc(max(values))


def _load_smart_money_fixture(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolation("Smart Money fixture is not readable JSON") from exc
    if not isinstance(payload, dict) or not verify_evidence_integrity(payload):
        raise ContractViolation("Smart Money evidence integrity is invalid")
    return payload


def _optional_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ContractViolation(f"Smart Money {field_name} must be numeric")
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ContractViolation(
            f"Smart Money {field_name} must be numeric"
        ) from exc
    if not parsed.is_finite():
        raise ContractViolation(f"Smart Money {field_name} must be finite")
    return parsed


def _smart_money_summary(
    document: Mapping[str, Any],
    ledger: SQLiteRunLedger,
) -> dict[str, Any]:
    """Validate and summarize ranking, profile, and identity evidence separately."""

    if not isinstance(document, dict) or not verify_evidence_integrity(document):
        raise ContractViolation("Smart Money evidence integrity is invalid")
    if document.get("evidence_schema_version") != SMART_MONEY_SCHEMA_VERSION:
        raise ContractViolation("Smart Money evidence schema version is unsupported")
    if document.get("snapshot_semantics") != "OBSERVED_WINDOW":
        raise ContractViolation("Smart Money snapshot semantics must be OBSERVED_WINDOW")
    captured_at = format_utc(parse_utc(document.get("captured_at")))
    observed_window = document.get("leaderboard_observed_window")
    if (
        not isinstance(observed_window, Mapping)
        or observed_window.get("snapshot_semantics") != "OBSERVED_WINDOW"
    ):
        raise ContractViolation("Smart Money leaderboard observed window is missing")
    observed_start = parse_utc(observed_window.get("started_at_utc"))
    observed_end = parse_utc(observed_window.get("completed_at_utc"))
    duration = observed_window.get("duration_seconds")
    if (
        observed_end < observed_start
        or parse_utc(captured_at) < observed_end
        or not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or duration < 0
        or abs(duration - (observed_end - observed_start).total_seconds()) > 0.001
    ):
        raise ContractViolation("Smart Money leaderboard observed window is invalid")
    contract = document.get("contract")
    rankings = document.get("rankings")
    if not isinstance(contract, Mapping) or not isinstance(rankings, list):
        raise ContractViolation("Smart Money evidence contract/rankings are missing")
    selected = contract.get("ranking_types")
    expected_filters = {
        "onlyShowSharingPosition": "false",
        "onlyShowSignalEnabled": "false",
    }
    if selected != list(SMART_MONEY_RANKING_TYPES):
        raise ContractViolation(
            "Smart Money standard integration requires complete PNL+ROI rankings"
        )
    if (
        contract.get("time_range") != SMART_MONEY_TIME_RANGE
        or contract.get("order") != SMART_MONEY_ORDER
        or contract.get("rows_per_page") != SMART_MONEY_ROWS_PER_PAGE
        or contract.get("pages") != list(SMART_MONEY_PAGES)
        or contract.get("expected_rows_per_ranking")
        != SMART_MONEY_ROWS_PER_PAGE * len(SMART_MONEY_PAGES)
        or contract.get("rank_source") != SMART_MONEY_RANK_SOURCE
        or contract.get("source_id_type") != SMART_MONEY_SOURCE_ID_TYPE
        or contract.get("fixed_filters") != expected_filters
    ):
        raise ContractViolation("Smart Money evidence contract is invalid")
    if len(rankings) != len(selected):
        raise ContractViolation("Smart Money ranking coverage does not match contract")

    ranking_types: list[str] = []
    update_times: set[int] = set()
    source_ids: list[str] = []
    row_count = 0
    for ranking in rankings:
        if not isinstance(ranking, Mapping):
            raise ContractViolation("Smart Money ranking must be an object")
        ranking_type = ranking.get("ranking_type")
        rows = ranking.get("rows")
        update_time = ranking.get("lastUpdateTime")
        ranking_total = ranking.get("total")
        if (
            ranking_type not in selected
            or ranking_type in ranking_types
            or ranking.get("status") != "COMPLETE"
            or ranking.get("time_range") != SMART_MONEY_TIME_RANGE
            or ranking.get("order") != SMART_MONEY_ORDER
            or ranking.get("rank_source") != SMART_MONEY_RANK_SOURCE
            or ranking.get("source_id_type") != SMART_MONEY_SOURCE_ID_TYPE
            or ranking.get("snapshot_semantics") != "OBSERVED_WINDOW"
            or not isinstance(rows, list)
            or len(rows) != 30
            or not isinstance(ranking_total, int)
            or isinstance(ranking_total, bool)
            or ranking_total < 30
        ):
            raise ContractViolation("Smart Money ranking is not a complete TOP30")
        if (
            not isinstance(update_time, int)
            or isinstance(update_time, bool)
            or update_time < 0
        ):
            raise ContractViolation("Smart Money lastUpdateTime is invalid")
        expected_ranks = list(range(1, 31))
        actual_ranks = [row.get("rank") for row in rows if isinstance(row, Mapping)]
        ranking_ids = [
            row.get("source_id") for row in rows if isinstance(row, Mapping)
        ]
        if (
            actual_ranks != expected_ranks
            or len(ranking_ids) != 30
            or len(set(ranking_ids)) != 30
            or not all(isinstance(value, str) and value for value in ranking_ids)
        ):
            raise ContractViolation("Smart Money TOP30 rank/source IDs are invalid")
        for row_index, row in enumerate(rows, start=1):
            if not isinstance(row, Mapping):
                raise ContractViolation("Smart Money TOP30 row is invalid")
            expected_page = ((row_index - 1) // SMART_MONEY_ROWS_PER_PAGE) + 1
            expected_position = ((row_index - 1) % SMART_MONEY_ROWS_PER_PAGE) + 1
            source_row = row.get("source_row")
            if (
                row.get("rank") != row_index
                or row.get("rank_source") != SMART_MONEY_RANK_SOURCE
                or row.get("page") != expected_page
                or row.get("position_on_page") != expected_position
                or row.get("source_id_type") != SMART_MONEY_SOURCE_ID_TYPE
                or not isinstance(source_row, Mapping)
                or source_row.get("topTraderId") != row.get("source_id")
            ):
                raise ContractViolation(
                    "Smart Money derived rank/page/position does not match source row"
                )
        ranking_window = ranking.get("observed_window")
        pages = ranking.get("pages")
        if (
            not isinstance(ranking_window, Mapping)
            or ranking_window.get("snapshot_semantics") != "OBSERVED_WINDOW"
            or not isinstance(pages, list)
            or len(pages) != 3
        ):
            raise ContractViolation("Smart Money ranking observed window is invalid")
        ranking_start = parse_utc(ranking_window.get("started_at_utc"))
        ranking_end = parse_utc(ranking_window.get("completed_at_utc"))
        if not (observed_start <= ranking_start <= ranking_end <= observed_end):
            raise ContractViolation(
                "Smart Money ranking window is outside leaderboard observed window"
            )
        if [page.get("page") for page in pages if isinstance(page, Mapping)] != list(
            SMART_MONEY_PAGES
        ):
            raise ContractViolation("Smart Money pages must be exactly 1, 2, and 3")
        for expected_page, page in zip(SMART_MONEY_PAGES, pages):
            if not isinstance(page, Mapping):
                raise ContractViolation("Smart Money page timing is invalid")
            request = page.get("request")
            response = page.get("response")
            expected_request = {
                "rankingType": ranking_type,
                "timeRange": SMART_MONEY_TIME_RANGE,
                "order": SMART_MONEY_ORDER,
                "page": expected_page,
                "rows": SMART_MONEY_ROWS_PER_PAGE,
                **expected_filters,
            }
            if (
                request != expected_request
                or not isinstance(response, Mapping)
                or response.get("code") != "000000"
                or response.get("success") is not True
                or response.get("total") != ranking_total
                or response.get("row_count") != SMART_MONEY_ROWS_PER_PAGE
                or response.get("lastUpdateTime") != update_time
            ):
                raise ContractViolation("Smart Money page request/response is invalid")
            request_started = parse_utc(page.get("request_started_at_utc"))
            response_received = parse_utc(page.get("response_received_at_utc"))
            if not (
                ranking_start
                <= request_started
                <= response_received
                <= ranking_end
            ):
                raise ContractViolation("Smart Money page timing is invalid")
        ranking_types.append(str(ranking_type))
        update_times.add(update_time)
        source_ids.extend(str(value) for value in ranking_ids)
        row_count += len(rows)
    if ranking_types != selected or len(update_times) != 1:
        raise ContractViolation("Smart Money rankings are inconsistent")

    unique_ids = tuple(dict.fromkeys(source_ids))
    declared_unique = document.get("unique_top_trader_count")
    if declared_unique != len(unique_ids):
        raise ContractViolation("Smart Money unique trader count is inconsistent")
    profiles = document.get("profile_enrichment")
    if not isinstance(profiles, Mapping):
        raise ContractViolation("Smart Money profile enrichment is missing")
    profile_expected = profiles.get("expected")
    profile_completed = profiles.get("completed")
    profile_failed = profiles.get("failed")
    if (
        profile_expected != len(unique_ids)
        or not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in (profile_completed, profile_failed)
        )
        or profile_completed + profile_failed > profile_expected
    ):
        raise ContractViolation("Smart Money profile coverage is inconsistent")
    completed_profiles = profiles.get("profiles")
    failed_profiles = profiles.get("failures")
    if not isinstance(completed_profiles, list) or not isinstance(failed_profiles, list):
        raise ContractViolation("Smart Money profile observations are invalid")
    if len(completed_profiles) != profile_completed or len(failed_profiles) != profile_failed:
        raise ContractViolation("Smart Money profile observation counts do not reconcile")
    profile_ids = [
        item.get("source_id")
        for item in (*completed_profiles, *failed_profiles)
        if isinstance(item, Mapping)
    ]
    profiles_enabled = profiles.get("enabled")
    if (
        not isinstance(profiles_enabled, bool)
        or len(profile_ids) != profile_completed + profile_failed
        or len(set(profile_ids)) != len(profile_ids)
        or any(value not in unique_ids for value in profile_ids)
        or (
            profiles_enabled is True
            and profile_completed + profile_failed != profile_expected
        )
        or (
            profiles_enabled is False
            and (profile_completed != 0 or profile_failed != 0)
        )
    ):
        raise ContractViolation("Smart Money profile identities do not reconcile")

    mapped_ids = {
        item.top_trader_id
        for item in ledger.list_smart_money_square_identity_mappings()
        if item.top_trader_id in unique_ids
    }
    last_update_ms = next(iter(update_times))
    last_update_at = format_utc(
        datetime.fromtimestamp(last_update_ms / 1000, tz=timezone.utc)
    )
    provenance = str(document.get("provenance") or "").upper()
    if provenance not in {"LIVE_CAPTURE", "FIXTURE_REPLAY"}:
        raise ContractViolation("Smart Money evidence provenance is invalid")
    return {
        "status": "COMPLETE" if len(ranking_types) == 2 else "PARTIAL",
        "provenance": provenance,
        "observation_semantics": "OBSERVED_WINDOW",
        "captured_at_utc": captured_at,
        "leaderboard_observed_window": {
            "started_at_utc": format_utc(observed_start),
            "completed_at_utc": format_utc(observed_end),
            "duration_seconds": duration,
        },
        "leaderboard_data_updated_at_utc": last_update_at,
        "leaderboard_data_updated_at_ms": last_update_ms,
        "ranking_coverage": {
            "covered": len(ranking_types),
            "expected": 2,
            "ranking_types": ranking_types,
            "rendered_rank_rows": row_count,
        },
        "profile_detail_coverage": {
            "covered": profile_completed,
            "expected": profile_expected,
            "failed": profile_failed,
            "status": profiles.get("status"),
        },
        "square_identity_mapping_coverage": {
            "covered": len(mapped_ids),
            "expected": len(unique_ids),
            "verification_method": "EXPLICIT_SOURCE_EVIDENCE_ONLY",
        },
        "unique_top_trader_count": len(unique_ids),
        "tier_a_eligible": 0,
        "tier_a_policy": (
            "Smart Money rank/profile alone never authorizes Square identity, "
            "content retrieval, or author-score credit"
        ),
    }


def _smart_money_top_trader_ids(
    document: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return the stable source IDs from an already-validated Smart Money document."""

    rankings = document.get("rankings")
    if not isinstance(rankings, list):
        raise ContractViolation("Smart Money rankings are missing")
    source_ids: list[str] = []
    for ranking in rankings:
        if not isinstance(ranking, Mapping) or not isinstance(ranking.get("rows"), list):
            raise ContractViolation("Smart Money ranking rows are missing")
        for row in ranking["rows"]:
            if not isinstance(row, Mapping):
                raise ContractViolation("Smart Money ranking row is invalid")
            source_id = row.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise ContractViolation("Smart Money ranking source ID is invalid")
            source_ids.append(source_id)
    return tuple(dict.fromkeys(source_ids))


def _persist_smart_money(
    *,
    ledger: SQLiteRunLedger,
    logical_run_id: str,
    attempt_id: str,
    document: Mapping[str, Any],
    evidence_path: Path,
    evidence_file_sha256: str,
    now: datetime,
) -> None:
    captured_at = format_utc(parse_utc(document.get("captured_at")))
    rankings = document.get("rankings")
    profiles = document.get("profile_enrichment")
    assert isinstance(rankings, list)
    assert isinstance(profiles, Mapping)
    for ranking in rankings:
        assert isinstance(ranking, Mapping)
        observed_window = ranking.get("observed_window")
        if not isinstance(observed_window, Mapping):
            raise ContractViolation("Smart Money ranking observed window is missing")
        inputs: list[SmartMoneyLeaderboardRowInput] = []
        for row in ranking["rows"]:
            source = row["source_row"]
            if not isinstance(source, Mapping):
                raise ContractViolation("Smart Money source row is invalid")
            subscribers = source.get("subscribers")
            if not (
                subscribers is None
                or (isinstance(subscribers, int) and not isinstance(subscribers, bool))
            ):
                subscribers = None
            position_status = source.get("positionStatus")
            if not isinstance(position_status, str):
                position_status = None
            signal_lead_on = source.get("signalLeadOn")
            if not isinstance(signal_lead_on, bool):
                signal_lead_on = None
            inputs.append(
                SmartMoneyLeaderboardRowInput(
                    rank_no=row["rank"],
                    top_trader_id=row["source_id"],
                    pnl=_optional_decimal(source.get("pnl"), "pnl"),
                    roi=_optional_decimal(source.get("roi"), "roi"),
                    assets=source.get("assets", []),
                    subscribers=subscribers,
                    position_status=position_status,
                    signal_lead_on=signal_lead_on,
                    raw=dict(source),
                )
            )
        ledger.record_smart_money_leaderboard_capture(
            logical_run_id=logical_run_id,
            attempt_id=attempt_id,
            ranking_type=ranking["ranking_type"],
            captured_at=captured_at,
            snapshot_semantics=ranking.get("snapshot_semantics"),
            observed_start=observed_window.get("started_at_utc"),
            observed_end=observed_window.get("completed_at_utc"),
            last_update_time_ms=ranking["lastUpdateTime"],
            capture_status="COMPLETE",
            evidence_path=str(evidence_path),
            evidence_file_sha256=evidence_file_sha256,
            payload_sha256=document["integrity"]["payload_sha256"],
            rows=inputs,
            now=now,
        )

    for observation in profiles["profiles"]:
        if not isinstance(observation, Mapping):
            raise ContractViolation("Smart Money completed profile is invalid")
        profile = observation.get("profile")
        if not isinstance(profile, Mapping):
            raise ContractViolation("Smart Money completed profile is invalid")
        ledger.record_smart_money_profile_observation(
            logical_run_id=logical_run_id,
            attempt_id=attempt_id,
            top_trader_id=observation["source_id"],
            observation_status="COMPLETE",
            captured_at=captured_at,
            evidence_path=str(evidence_path),
            evidence_file_sha256=evidence_file_sha256,
            payload_sha256=document["integrity"]["payload_sha256"],
            days_active=profile.get("daysActive"),
            mdd=_optional_decimal(profile.get("mdd"), "mdd"),
            win_rate=_optional_decimal(profile.get("winRate"), "winRate"),
            um_margin_balance=_optional_decimal(
                profile.get("umMarginBalance"), "umMarginBalance"
            ),
            cm_margin_balance=_optional_decimal(
                profile.get("cmMarginBalance"), "cmMarginBalance"
            ),
            net_transfer=_optional_decimal(
                profile.get("netTransfer"), "netTransfer"
            ),
            sharing_position=profile.get("sharingPosition"),
            sharing_history=profile.get("sharingPositionHistory"),
            latest_record=profile.get("sharingLatestRecord"),
            is_ai=profile.get("isAi") if isinstance(profile.get("isAi"), bool) else None,
            is_pm_user=(
                profile.get("isPmUser")
                if isinstance(profile.get("isPmUser"), bool)
                else None
            ),
            copy_trade_portfolio_ids=profile.get("copyTradePortfolioIds"),
            raw_profile=dict(profile),
            now=now,
        )
    for failure in profiles["failures"]:
        if not isinstance(failure, Mapping):
            raise ContractViolation("Smart Money failed profile is invalid")
        ledger.record_smart_money_profile_observation(
            logical_run_id=logical_run_id,
            attempt_id=attempt_id,
            top_trader_id=failure["source_id"],
            observation_status="FAILED",
            captured_at=captured_at,
            evidence_path=str(evidence_path),
            evidence_file_sha256=evidence_file_sha256,
            payload_sha256=document["integrity"]["payload_sha256"],
            failure_reason=str(failure.get("reason") or "profile collection failed"),
            now=now,
        )


def _persist_identity_mapping_evidence(
    *,
    ledger: SQLiteRunLedger,
    evidence: SmartMoneySquareIdentityEvidence,
    now: datetime,
) -> None:
    """Persist only active v2 evidence, revalidating each artifact in storage."""

    if evidence.schema == SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA:
        if (
            evidence.verification_status != "DIRECT_VERIFIED"
            or evidence.promotion_status != "APPROVED"
            or len(evidence.catalog_members) != len(evidence.mappings)
        ):
            raise ContractViolation(
                "identity mapping catalog member evidence is incomplete"
            )
        records = tuple(
            (mapping, artifact_path, artifact_sha256)
            for mapping, (artifact_path, artifact_sha256) in zip(
                evidence.mappings, evidence.catalog_members, strict=True
            )
        )
    elif evidence.schema == SMART_MONEY_SQUARE_MAPPING_SCHEMA:
        # A proposal may drive no Profile requests and must never create an
        # active database projection. The legacy v1 fixture path is handled by
        # the final branch below for backwards-compatible replay only.
        if evidence.promotion_status == "PROPOSED":
            return
        if (
            evidence.verification_status != "DIRECT_VERIFIED"
            or evidence.promotion_status != "APPROVED"
            or len(evidence.mappings) != 1
        ):
            raise ContractViolation(
                "single identity mapping persistence requires one APPROVED v2 binding"
            )
        records = (
            (
                evidence.mappings[0],
                evidence.evidence_path,
                evidence.evidence_sha256,
            ),
        )
    else:
        # Legacy v1 evidence remains fixture-replay input only and cannot enter
        # the v2 artifact/event projection.
        return

    for mapping, artifact_path, artifact_sha256 in records:
        ledger.record_smart_money_square_identity_mapping(
            top_trader_id=mapping.top_trader_id,
            author_id=mapping.square_uid,
            verified_at=mapping.verified_at,
            evidence_path=artifact_path,
            evidence_sha256=artifact_sha256,
            now=now,
        )


def _extraction_failure_reason(error: ContractViolation) -> str:
    message = str(error).casefold()
    if "direction" in message:
        return "AMBIGUOUS_OR_MISSING_DIRECTION"
    if "symbol" in message:
        return "AMBIGUOUS_OR_MISSING_SYMBOL"
    if "price" in message or "entry" in message or "target" in message:
        return "INVALID_AUTHOR_PARAMETERS"
    return "EXTRACTION_CONTRACT_VIOLATION"


def _four_hour_slot(value: str | datetime) -> str:
    decision = parse_utc(value)
    return format_utc(decision.replace(
        hour=(decision.hour // 4) * 4,
        minute=0,
        second=0,
        microsecond=0,
    ))


def _validate_real_attempt_timing(
    decision_at: str | datetime,
    observed_at: str | datetime,
    *,
    scheduled_retry: bool,
) -> str:
    """Freeze one production cutoff without permitting ad-hoc historical runs."""

    decision = parse_utc(decision_at)
    scheduled_for = parse_utc(_four_hour_slot(decision))
    lateness = decision - scheduled_for
    if lateness > MAX_PRODUCTION_SLOT_LATENESS:
        raise ContractViolation(
            "real decision_at must fall within +10 minutes of its UTC slot"
        )
    observed = parse_utc(observed_at)
    if observed + MAX_DECISION_CLOCK_SKEW < decision:
        raise ContractViolation("real radar cannot run before decision_at")
    maximum_age = MAX_DECISION_CLOCK_SKEW
    if scheduled_retry:
        maximum_age += timedelta(minutes=10)
    if observed - decision > maximum_age:
        raise ContractViolation(
            "real decision_at must be captured at this attempt start"
        )
    return format_utc(decision)


def _accepted_observation_contracts(
    raw: Mapping[str, Any],
) -> tuple[AcceptedPostObservation, ...]:
    source_channel = str(raw.get("source_mode") or "UNKNOWN")
    result: list[AcceptedPostObservation] = []
    for ordinal, value in enumerate(raw.get("accepted", [])):
        if not isinstance(value, Mapping):
            raise ContractViolation("accepted observations must be mappings")
        post_url = value.get("post_url")
        post_id = value.get("post_id")
        author_id = value.get("author_id")
        published_at = value.get("published_at")
        observed_at = value.get("observed_at")
        content_hash = value.get("content_hash")
        if not all(
            isinstance(item, str)
            for item in (
                post_url,
                post_id,
                author_id,
                published_at,
                observed_at,
                content_hash,
            )
        ):
            raise ContractViolation(
                "accepted observation is missing stable identity or event time"
            )
        result.append(
            AcceptedPostObservation(
                post_id=post_id,
                canonical_post_url=post_url,
                author_id=author_id,
                published_at=parse_utc(published_at),
                observed_at=parse_utc(observed_at),
                content_hash=content_hash,
                source_channel=str(value.get("source_channel") or source_channel),
                source_record_ordinal=ordinal,
            )
        )
    return tuple(result)


def _event_range(
    values: list[str | datetime],
) -> tuple[str | None, str | None]:
    if not values:
        return None, None
    parsed = [parse_utc(value) for value in values]
    return format_utc(min(parsed)), format_utc(max(parsed))


def _raw_event_range(raw: Mapping[str, Any]) -> tuple[str | None, str | None]:
    values: list[str | datetime] = []
    for collection in (raw.get("accepted", []), raw.get("quarantine", [])):
        for item in collection:
            if isinstance(item, Mapping) and item.get("published_at") is not None:
                values.append(item["published_at"])
    return _event_range(values)


def _market_event_range(
    market_payload: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    values: list[str | datetime] = []
    snapshots = market_payload.get("snapshots", {})
    if isinstance(snapshots, Mapping):
        for snapshot in snapshots.values():
            if isinstance(snapshot, Mapping) and snapshot.get("captured_at") is not None:
                values.append(snapshot["captured_at"])
    return _event_range(values)


def _candidate_audit(
    scored: Any,
    *,
    parameter_mapping: str,
    content_hash: str,
    derivation: DerivationResult | None = None,
    consensus_author_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "signal_id": scored.signal_id,
        "symbol": scored.symbol,
        "direction": scored.direction.value,
        "rank_bucket": scored.rank_bucket.value,
        "score": scored.total_score,
        "hard_gate_reasons": list(scored.hard_gate_reasons),
        "parameter_mapping": parameter_mapping,
        "parameter_source": scored.candidate.parameter_source.value,
        "derivation_policy": (
            derivation.policy_version if derivation is not None else None
        ),
        "derivation_disposition": (
            derivation.disposition.value if derivation is not None else "NOT_APPLIED"
        ),
        "derivation_reasons": (
            list(derivation.reasons) if derivation is not None else []
        ),
        "content_hash": content_hash,
        "consensus_author_ids": list(consensus_author_ids),
        "consensus_distinct_other_authors": len(consensus_author_ids),
        "author_score_assumption": 0,
        "source_post_url": scored.post_url,
        "market_source": (
            scored.market_source.value if scored.market_source is not None else None
        ),
        "market_captured_at": (
            format_utc(scored.market_captured_at)
            if scored.market_captured_at is not None
            else None
        ),
        "evidence": list(scored.evidence),
    }


def _derivation_rejection_audit(
    *,
    post: PostDetail,
    candidate: SignalCandidate,
    derivation: DerivationResult,
    market: MarketSnapshot,
) -> dict[str, Any]:
    """Keep rejected shadow re-entry evidence visible instead of dropping it."""

    return {
        "signal_id": candidate.signal_id,
        "symbol": candidate.symbol,
        "direction": candidate.direction.value,
        "rank_bucket": "FILTER",
        "score": None,
        "hard_gate_reasons": list(derivation.reasons),
        "parameter_mapping": "REJECTED_BY_DERIVATION_POLICY",
        "parameter_source": candidate.parameter_source.value,
        "derivation_policy": derivation.policy_version,
        "derivation_disposition": derivation.disposition.value,
        "derivation_reasons": list(derivation.reasons),
        "content_hash": post.content_hash,
        "consensus_author_ids": [],
        "consensus_distinct_other_authors": 0,
        "author_score_assumption": 0,
        "source_post_url": candidate.post_url,
        "market_source": market.source.value,
        "market_captured_at": format_utc(market.captured_at),
        "evidence": list(derivation.evidence),
    }


def _market_snapshot_audit(snapshot: Any) -> dict[str, Any]:
    contract = getattr(snapshot, "contract", None)
    candles: dict[str, list[dict[str, Any]]] = {}
    for interval, rows in getattr(snapshot, "candles", {}).items():
        candles[str(interval)] = [
            {
                "open_time": getattr(row, "open_time", None),
                "open": getattr(row, "open", None),
                "high": getattr(row, "high", None),
                "low": getattr(row, "low", None),
                "close": getattr(row, "close", None),
                "volume": getattr(row, "volume", None),
                "close_time": getattr(row, "close_time", None),
                "quote_volume": getattr(row, "quote_volume", None),
                "number_of_trades": getattr(row, "number_of_trades", None),
                "source": getattr(getattr(row, "source", None), "value", getattr(row, "source", None)),
                "volume_unit": getattr(row, "volume_unit", None),
            }
            for row in rows
        ]
    source = getattr(snapshot, "source", None)
    failures = getattr(snapshot, "failures", ())
    return {
        "symbol": getattr(snapshot, "symbol", None),
        "contract": {
            field: getattr(contract, field, None)
            for field in (
                "symbol", "status", "contract_type", "base_asset",
                "quote_asset", "margin_asset",
            )
        },
        "source": getattr(source, "value", source),
        "decision_time_ms": getattr(snapshot, "decision_time_ms", None),
        "captured_at": getattr(snapshot, "captured_at", None),
        "last_price": getattr(snapshot, "last_price", None),
        "mark_price": getattr(snapshot, "mark_price", None),
        "index_price": getattr(snapshot, "index_price", None),
        "funding_rate": getattr(snapshot, "funding_rate", None),
        "open_interest": getattr(snapshot, "open_interest", None),
        "base_volume_24h": getattr(snapshot, "base_volume_24h", None),
        "quote_volume_24h": getattr(snapshot, "quote_volume_24h", None),
        "missing_fields": list(getattr(snapshot, "missing_fields", ())),
        "failures": [getattr(value, "value", value) for value in failures],
        "candles": candles,
    }


def _audit_markdown(audits: list[dict[str, Any]]) -> str:
    lines = ["", "## 候选证据审计"]
    if not audits:
        lines.append("- 无可解析候选")
    for item in audits:
        lines.append(
            "- "
            f"{item['symbol']} {item['direction']}｜参数 {item['parameter_mapping']}｜"
            f"行情抓取 {item['market_captured_at'] or 'UNKNOWN'}｜"
            f"来源 {item['source_post_url']}"
        )
    return "\n".join(lines)


def _load_legacy_signals(path: Path | None) -> dict[str, Mapping[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("signals JSON must contain a list")
    result: dict[str, Mapping[str, Any]] = {}
    for item in payload:
        if isinstance(item, Mapping):
            source_url = item.get("source_url", item.get("url"))
        else:
            source_url = None
        if isinstance(source_url, str):
            try:
                post_id = canonical_post_id(source_url)
            except ContractViolation:
                continue
            result[f"https://www.binance.com/en/square/post/{post_id}"] = item
    return result


def _real_discovery(
    config: PipelineConfig,
    legacy: Mapping[str, Any],
    *,
    snapshot_payload: Mapping[str, Any] | None = None,
    profile_observations: tuple[ChannelObservation, ...] = (),
) -> DeduplicatedDiscovery:
    # Mapped/seeded Profile observations are authoritative candidates and are
    # never truncated by the broad Feed budget. Curated signal URLs remain the
    # first Feed supplement, ahead of snapshot noise.
    curated_observations = tuple(
        ChannelObservation(
            post_id=canonical_post_id(value),
            post_url=(
                "https://www.binance.com/en/square/post/"
                f"{canonical_post_id(value)}"
            ),
            channel="CURATED_SIGNAL",
        )
        for value in legacy
    )
    feed_urls: list[str] = []
    if snapshot_payload is not None:
        feed_urls.extend(feed_snapshot_post_urls(snapshot_payload, limit=200))
    elif config.input_snapshot is not None:
        feed_urls.extend(discover_snapshot_post_urls(config.input_snapshot, limit=200))
    feed_observations: list[ChannelObservation] = []
    for value in feed_urls:
        post_id = canonical_post_id(value)
        canonical = f"https://www.binance.com/en/square/post/{post_id}"
        feed_observations.append(
            ChannelObservation(post_id=post_id, post_url=canonical, channel="FEED")
        )
    # The existing Profile-first selector owns the Feed budget. Curated signal
    # candidates participate in that budget ahead of Feed noise, but their
    # original source channel is restored below for lineage.
    selection_feed = tuple(
        ChannelObservation(
            post_id=observation.post_id,
            post_url=observation.post_url,
            channel="FEED",
        )
        for observation in curated_observations
    ) + tuple(feed_observations)
    queued = profile_first_detail_queue(
        profile_observations,
        selection_feed,
        feed_limit=config.limit,
    )
    selected_ids = {post.post_id for post in queued.posts}
    source_observations = tuple(profile_observations) + tuple(
        observation
        for observation in (*curated_observations, *feed_observations)
        if observation.post_id in selected_ids
    )
    by_post_id: dict[str, list[ChannelObservation]] = {
        post.post_id: [] for post in queued.posts
    }
    for observation in source_observations:
        by_post_id[observation.post_id].append(observation)
    posts = tuple(
        CanonicalPostDiscovery(
            post_id=post.post_id,
            post_url=post.post_url,
            channels=tuple(
                dict.fromkeys(
                    observation.channel
                    for observation in by_post_id[post.post_id]
                )
            ),
            observations=tuple(by_post_id[post.post_id]),
        )
        for post in queued.posts
    )
    source_count = sum(len(post.observations) for post in posts)
    return DeduplicatedDiscovery(
        posts=posts,
        source_record_count=source_count,
        unique_post_count=len(posts),
        duplicate_source_records=source_count - len(posts),
    )


def run_shadow_radar(
    config: PipelineConfig,
    *,
    clock: Callable[[], datetime] | None = None,
    detail_fetcher: Callable[[str], dict[str, Any]] | None = None,
    market_client: BinanceMarketClient | None = None,
    smart_money_collector: Callable[[], dict[str, Any]] | None = None,
    official_news_collector: Callable[[], dict[str, Any]] | None = None,
    profile_content_fetcher: Callable[[str], dict[str, Any]] | None = None,
    profile_capture_time: str | datetime | None = None,
) -> PipelineResult:
    """Run one fixture or real shadow pass and publish only local artifacts."""

    if config.mode not in {"fixture", "real"}:
        raise ValueError("mode must be fixture or real")
    if config.mode == "fixture" and config.fixture_dir is None:
        raise ValueError("fixture mode requires fixture_dir")
    if config.mode == "real" and config.dedup_baseline_post_ids is not None:
        raise ValueError("production dedup baseline is ledger-controlled")
    if config.mode == "real" and config.scheduled_retry and config.decision_at is None:
        raise ValueError("scheduled retry requires the frozen first-attempt decision_at")
    if not config.no_send:
        raise ValueError("shadow pipeline does not support external sending")
    if config.limit < 1 or config.limit > 200:
        raise ValueError("limit must be between 1 and 200")
    smart_money_requested = (
        config.smart_money_enabled or config.smart_money_fixture is not None
    )
    if (
        config.smart_money_square_mapping_evidence is not None
        and config.smart_money_square_mapping_catalog is not None
    ):
        raise ValueError("use either one Smart Money mapping artifact or one catalog")
    identity_mapping_path = (
        config.smart_money_square_mapping_catalog
        or config.smart_money_square_mapping_evidence
    )
    if identity_mapping_path is not None and not smart_money_requested:
        raise ValueError("Smart Money identity mapping requires Smart Money collection")
    if (
        smart_money_requested
        and config.mode == "fixture"
        and config.smart_money_fixture is None
        and smart_money_collector is None
    ):
        raise ValueError(
            "fixture mode Smart Money requires an explicit fixture or collector"
        )
    runtime_clock = clock or (lambda: datetime.now(timezone.utc))
    now = parse_utc(runtime_clock())
    client = market_client or (BinanceMarketClient() if config.mode == "real" else None)
    if config.mode == "real":
        decision_at = _validate_real_attempt_timing(
            config.decision_at or now,
            now,
            scheduled_retry=config.scheduled_retry,
        )
    else:
        decision_at = format_utc(config.decision_at or now)

    ledger = SQLiteRunLedger(config.database, MIGRATIONS)
    attempt = None
    current_stage = "initialization"
    discovery_snapshot_payload: Mapping[str, Any] | None = None
    discovery_snapshot_content: bytes | None = None
    discovery_snapshot_path: Path | None = None
    discovery_snapshot_capture = None
    signal_input_content: bytes | None = None
    signal_input_count = 0
    identity_mapping_content: bytes | None = None
    identity_mapping_evidence = None
    try:
        if config.mode == "fixture":
            assert config.fixture_dir is not None
            logical_run = ledger.create_or_open_replay_run(
                replay_namespace="fixture-shadow",
                source_logical_run_id=f"fixture:{config.fixture_dir.name}:{decision_at}",
                pipeline_version=SCHEMA_VERSION,
                now=now,
            )
        else:
            logical_run = ledger.create_or_open_production_run(
                job_namespace=config.job_namespace,
                production_job_id=config.production_job_id,
                scheduled_for_utc=_four_hour_slot(decision_at),
                pipeline_version=SCHEMA_VERSION,
                now=now,
            )
            frozen_cutoff = ledger.freeze_production_decision(
                logical_run.logical_run_id,
                decision_at=decision_at,
                now=now,
            )
            decision_at = frozen_cutoff.decision_at_utc
        existing_attempts = ledger.list_attempts(logical_run.logical_run_id)
        if config.scheduled_retry:
            if (
                len(existing_attempts) != 1
                or existing_attempts[0].attempt_no != 1
                or existing_attempts[0].status != "FAILED"
            ):
                raise ContractViolation(
                    "scheduled retry requires exactly one FAILED first attempt"
                )
        elif existing_attempts:
            raise ContractViolation(
                "an existing logical run requires the explicit scheduled_retry path"
            )
        attempt = ledger.start_next_attempt(
            logical_run.logical_run_id,
            started_at=now,
        )
        if config.scheduled_retry != (attempt.attempt_no == 2):
            raise ContractViolation("scheduled_retry flag does not match attempt number")
        run_dir = (
            config.output_dir
            / logical_run.logical_run_id
            / f"attempt-{attempt.attempt_no}"
        )
        raw_path = run_dir / "raw.json"
        market_path = run_dir / "market.json"
        market_catalog_path = run_dir / "market_catalog.json"
        official_news_path = run_dir / "official_news.json"
        report_path = run_dir / "report.json"
        markdown_path = run_dir / "report.md"
        smart_money_path = run_dir / "smart_money.json"
        latest_json = config.output_dir / "latest.json"
        latest_markdown = config.output_dir / "latest.md"
        latest_pointer = config.output_dir / "latest"

        catalog = None
        market_failures: Counter[str] = Counter()
        if config.mode == "real":
            current_stage = "market_catalog"
            if client is None:
                raise ContractViolation("real radar requires a market client")
            catalog = client.fetch_futures_catalog()
            server_time = datetime.fromtimestamp(
                catalog.server_time_ms / 1000,
                tz=timezone.utc,
            )
            if not config.scheduled_retry:
                if abs(server_time - parse_utc(decision_at)) > MAX_DECISION_CLOCK_SKEW:
                    raise ContractViolation(
                        "attempt-start decision_at is not validated by Binance server time"
                    )
                if _four_hour_slot(server_time) != logical_run.scheduled_for_utc:
                    raise ContractViolation(
                        "Binance server time crossed into a different UTC slot"
                    )
            elif server_time < parse_utc(decision_at):
                raise ContractViolation(
                    "retry Binance server time precedes the frozen decision_at"
                )

        current_stage = "input"
        if config.mode == "real" and config.input_snapshot is not None:
            try:
                discovery_snapshot_content = config.input_snapshot.read_bytes()
                parsed_snapshot = json.loads(discovery_snapshot_content)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ContractViolation("Feed snapshot is not readable JSON") from exc
            declared_snapshot = parsed_snapshot.get("snapshot_file")
            if not isinstance(declared_snapshot, str) or not declared_snapshot.strip():
                raise ContractViolation("Feed snapshot is missing immutable snapshot_file")
            discovery_snapshot_path = Path(declared_snapshot)
            if not discovery_snapshot_path.is_absolute():
                discovery_snapshot_path = config.input_snapshot.parent / discovery_snapshot_path
            try:
                immutable_content = discovery_snapshot_path.read_bytes()
            except OSError as exc:
                raise ContractViolation("Feed immutable snapshot_file is unreadable") from exc
            if immutable_content != discovery_snapshot_content:
                raise ContractViolation("Feed latest payload differs from immutable snapshot_file")
            discovery_snapshot_content = immutable_content
            discovery_snapshot_capture = validate_feed_snapshot(
                parsed_snapshot,
                consumed_at=now,
                maximum_age=MAX_PRODUCTION_SLOT_LATENESS,
            )
            discovery_snapshot_payload = parsed_snapshot
        if config.mode == "real" and config.signals_json is not None:
            try:
                signal_input_content = config.signals_json.read_bytes()
                signal_payload = json.loads(signal_input_content)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ContractViolation("signal input is not readable JSON") from exc
            if not isinstance(signal_payload, list):
                raise ContractViolation("signal input must contain a list")
            signal_input_count = len(signal_payload)
        legacy_signals = _load_legacy_signals(config.signals_json)
        seed_evidence: SeedProfileEvidence | None = None
        if config.leaderboard_seed_evidence is not None:
            seed_evidence = load_seed_profile_evidence(
                config.leaderboard_seed_evidence
            )
        if identity_mapping_path is not None:
            try:
                identity_mapping_content = identity_mapping_path.read_bytes()
            except OSError as exc:
                raise ContractViolation(
                    "Smart Money identity mapping evidence is unreadable"
                ) from exc
            identity_mapping_digest = sha256(identity_mapping_content).hexdigest()
            if config.smart_money_square_mapping_catalog is not None:
                identity_mapping_evidence = load_smart_money_square_identity_catalog(
                    identity_mapping_path,
                    expected_sha256=identity_mapping_digest,
                )
            else:
                identity_mapping_evidence = load_smart_money_square_identity_evidence(
                    identity_mapping_path,
                    expected_sha256=identity_mapping_digest,
                )
            expected_provenance = (
                "LIVE_CAPTURE" if config.mode == "real" else "FIXTURE_REPLAY"
            )
            if identity_mapping_evidence.provenance != expected_provenance:
                raise ContractViolation(
                    "Smart Money identity mapping provenance does not match run mode"
                )
        profile_plan = plan_profile_fetches(
            seed_evidence.profiles if seed_evidence is not None else None
        )
        profile_coverage = reconcile_profile_fetch_plan(profile_plan, ())
        seed_coverage = profile_coverage
        seed_page_results: list[dict[str, Any]] = []
        profile_channel_contract: dict[str, Any] = {
            "availability": profile_coverage.availability,
            "status": profile_coverage.status,
            "reason": profile_coverage.reason,
            "provenance": (
                "FIXTURE_REPLAY" if seed_evidence is not None else "UNKNOWN"
            ),
            "source_capture_time_utc": (
                seed_evidence.captured_at if seed_evidence is not None else None
            ),
            "evidence_path": (
                seed_evidence.evidence_path if seed_evidence is not None else None
            ),
            "planned_authors": profile_coverage.planned_count,
            "complete_authors": profile_coverage.complete_count,
            "empty_authors": profile_coverage.empty_count,
            "partial_authors": profile_coverage.partial_count,
            "failed_authors": profile_coverage.failed_count,
            "not_attempted_authors": profile_coverage.not_attempted_count,
            "source_records": profile_coverage.source_record_count,
            "tier_a_eligible": 0,
        }
        seed_profile_contract = dict(profile_channel_contract)
        seed_profile_observations: tuple[ChannelObservation, ...] = ()
        profile_fetch_adapter = profile_content_fetcher or (
            public_get_profile_contents if config.mode == "real" else None
        )
        if profile_plan.targets and profile_fetch_adapter is not None:
            seed_capture = profile_capture_time
            if seed_capture is None:
                if config.mode == "fixture":
                    raise ContractViolation(
                        "fixture Profile collection requires profile_capture_time"
                    )
                seed_capture = runtime_clock()
            seed_outcomes: list[ProfileFetchOutcome] = []
            seed_observations: list[ChannelObservation] = []
            for target in profile_plan.targets:
                collection = collect_profile_pages(
                    target.author_id,
                    fetch_profile_contents=profile_fetch_adapter,
                    decision_at=decision_at,
                )
                seed_observations.extend(collection.observations)
                seed_page_results.append(
                    {
                        "author_id": target.author_id,
                        "status": collection.status,
                        "termination_reason": collection.reason,
                        "pages_fetched": collection.pages_fetched,
                        "post_count": len(collection.observations),
                        "error": collection.error,
                    }
                )
                seed_outcomes.append(
                    ProfileFetchOutcome(
                        target.author_id,
                        collection.status,
                        len(collection.observations),
                        collection.error or (
                            collection.reason
                            if collection.status == "PARTIAL"
                            else None
                        ),
                    )
                )
            seed_profile_observations = tuple(seed_observations)
            seed_coverage = reconcile_profile_fetch_plan(
                profile_plan,
                seed_outcomes,
            )
            seed_profile_contract = {
                "availability": seed_coverage.availability,
                "status": seed_coverage.status,
                "reason": seed_coverage.reason,
                "provenance": (
                    "LIVE_CAPTURE" if config.mode == "real" else "FIXTURE_REPLAY"
                ),
                "source_capture_time_utc": format_utc(seed_capture),
                "evidence_path": seed_evidence.evidence_path if seed_evidence else None,
                "planned_authors": seed_coverage.planned_count,
                "complete_authors": seed_coverage.complete_count,
                "empty_authors": seed_coverage.empty_count,
                "partial_authors": seed_coverage.partial_count,
                "failed_authors": seed_coverage.failed_count,
                "not_attempted_authors": seed_coverage.not_attempted_count,
                "source_records": seed_coverage.source_record_count,
                "tier_a_eligible": 0,
                "outcomes": seed_page_results,
            }

        smart_money_document: dict[str, Any] | None = None
        smart_money_summary: dict[str, Any] | None = None
        profile_pipeline_result: ProfilePipelineResult | None = None
        smart_money_profile_contract: dict[str, Any] = {
            "status": "NOT_ATTEMPTED",
            "reason": "smart_money_not_requested",
            "provenance": "UNKNOWN",
            "source_capture_time_utc": None,
            "planned_authors": 0,
            "complete_authors": 0,
            "empty_authors": 0,
            "partial_authors": 0,
            "failed_authors": 0,
            "not_attempted_authors": 0,
            "source_records": 0,
            "tier_a_eligible": 0,
        }
        if smart_money_requested:
            current_stage = "smart_money"
            if config.smart_money_fixture is not None:
                smart_money_document = _load_smart_money_fixture(
                    config.smart_money_fixture
                )
            elif smart_money_collector is not None:
                smart_money_document = smart_money_collector()
            else:
                smart_money_document = collect_smart_money()
            smart_money_summary = _smart_money_summary(
                smart_money_document,
                ledger,
            )
            smart_money_summary["evidence_path"] = str(smart_money_path)
            profile_source_capture = profile_capture_time
            if (
                profile_fetch_adapter is not None
                and identity_mapping_evidence is not None
                and profile_source_capture is None
            ):
                if config.mode == "fixture":
                    raise ContractViolation(
                        "fixture Profile collection requires profile_capture_time"
                    )
                profile_source_capture = runtime_clock()
            profile_pipeline_result = run_profile_pipeline(
                _smart_money_top_trader_ids(smart_money_document),
                mapping_evidence=identity_mapping_evidence,
                fetch_profile_contents=profile_fetch_adapter,
                source_capture_time_utc=(
                    format_utc(profile_source_capture)
                    if profile_source_capture is not None
                    else None
                ),
                provenance=(
                    "LIVE_CAPTURE" if config.mode == "real" else "FIXTURE_REPLAY"
                ),
                decision_at=decision_at,
            )
            smart_money_profile_contract = profile_pipeline_result.as_report_contract()
            smart_money_summary["square_identity_mapping_coverage"] = dict(
                smart_money_profile_contract["square_identity_mapping_coverage"]
            )
            smart_money_summary["tier_a_eligible"] = (
                smart_money_profile_contract["tier_a_eligible"]
            )

        combined_profile_observations = tuple(
            (*seed_profile_observations, *(
                profile_pipeline_result.observations
                if profile_pipeline_result is not None
                else ()
            ))
        )
        # Preserve cohort-specific denominators. The top level remains a
        # compatibility summary and never represents seed coverage as Smart
        # Money mapping coverage.
        cohort_contracts = (smart_money_profile_contract, seed_profile_contract)
        active_cohorts = tuple(
            cohort
            for cohort in cohort_contracts
            if int(cohort.get("planned_authors", 0)) > 0
        )
        profile_channel_contract = dict(
            active_cohorts[0]
            if len(active_cohorts) == 1
            else smart_money_profile_contract
            if smart_money_requested
            else seed_profile_contract
        )
        if len(active_cohorts) > 1:
            statuses = {str(cohort["status"]) for cohort in active_cohorts}
            if statuses <= {"COMPLETE", "EMPTY"}:
                aggregate_status = "COMPLETE"
            elif statuses == {"NOT_ATTEMPTED"}:
                aggregate_status = "NOT_ATTEMPTED"
            else:
                aggregate_status = "PARTIAL"
            profile_channel_contract.update(
                {
                    "status": aggregate_status,
                    "reason": "PROFILE_COHORTS_REPORTED_SEPARATELY",
                    **{
                        field: sum(int(cohort.get(field, 0)) for cohort in active_cohorts)
                        for field in (
                            "planned_authors",
                            "complete_authors",
                            "empty_authors",
                            "partial_authors",
                            "failed_authors",
                            "not_attempted_authors",
                            "source_records",
                        )
                    },
                }
            )
        profile_channel_contract["smart_money_profiles"] = smart_money_profile_contract
        profile_channel_contract["seed_profiles"] = seed_profile_contract
        profile_channel_contract["cohort_denominators"] = {
            "smart_money_profiles": int(
                smart_money_profile_contract.get("planned_authors", 0)
            ),
            "seed_profiles": int(seed_profile_contract.get("planned_authors", 0)),
        }

        seed_page_results_by_author = {
            str(result["author_id"]): result for result in seed_page_results
        }
        persisted_profile_outcomes: list[ProfileFetchOutcomeInput] = []
        for outcome in seed_coverage.outcomes:
            page_result = seed_page_results_by_author.get(outcome.author_id, {})
            persisted_profile_outcomes.append(
                ProfileFetchOutcomeInput(
                    profile_cohort="SEED_PROFILE",
                    planned_author_id=outcome.author_id,
                    planned_id_type="SQUARE_UID",
                    resolved_author_id=outcome.author_id,
                    fetch_status=outcome.status,
                    post_count=outcome.post_count,
                    pages_fetched=int(page_result.get("pages_fetched", 0)),
                    termination_reason=page_result.get("termination_reason"),
                    error_detail=page_result.get("error") or outcome.error,
                )
            )
        if profile_pipeline_result is not None:
            persisted_profile_outcomes.extend(
                ProfileFetchOutcomeInput(
                    profile_cohort="SMART_MONEY_PROFILE",
                    planned_author_id=outcome.top_trader_id,
                    planned_id_type="TOP_TRADER_ID",
                    resolved_author_id=outcome.square_uid,
                    fetch_status=outcome.status,
                    post_count=outcome.post_count,
                    pages_fetched=outcome.pages_fetched,
                    termination_reason=outcome.termination_reason,
                    error_detail=outcome.error,
                )
                for outcome in profile_pipeline_result.outcomes
            )
        profile_capture_candidates = [now]
        for cohort in (seed_profile_contract, smart_money_profile_contract):
            captured_at = cohort.get("source_capture_time_utc")
            if captured_at is not None:
                profile_capture_candidates.append(parse_utc(captured_at))
        profile_outcome_observed_at = max(profile_capture_candidates)
        current_stage = "profile_fetch_coverage"
        ledger.record_profile_fetch_outcomes(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            outcomes=persisted_profile_outcomes,
            observed_at=profile_outcome_observed_at,
        )

        current_stage = "fetch"
        if config.mode == "fixture":
            assert config.fixture_dir is not None
            raw = _collect_fixture(
                config.fixture_dir,
                limit=config.limit,
                decision_at=decision_at,
                profile_observations=combined_profile_observations,
            )
        else:
            discovery = _real_discovery(
                config,
                legacy_signals,
                snapshot_payload=discovery_snapshot_payload,
                profile_observations=combined_profile_observations,
            )
            profile_expectations = {
                observation.post_id: observation
                for observation in combined_profile_observations
            }
            raw = _collect_live_urls(
                discovery,
                decision_at=decision_at,
                source_mode="shadow_real_public_detail",
                fetch_detail=detail_fetcher or _public_get_detail,
                profile_expectations=profile_expectations,
            )

        raw_discovery_observations = raw.get("discovery_observations")
        if not isinstance(raw_discovery_observations, list) or not all(
            isinstance(observation, Mapping)
            for observation in raw_discovery_observations
        ):
            raise ContractViolation(
                "raw discovery_observations must be an array of objects"
            )
        discovery_counts = raw.get("counts")
        if not isinstance(discovery_counts, Mapping):
            raise ContractViolation("raw discovery counts must be an object")
        discovery_observed_at = max(
            now,
            parse_utc(raw.get("collection_completed_at_utc", now)),
        )
        current_stage = "discovery_lineage"
        ledger.record_post_discovery_observations(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            observations=(
                PostDiscoveryObservationInput(
                    post_id=str(observation.get("post_id", "")),
                    canonical_post_url=str(
                        observation.get("canonical_post_url", "")
                    ),
                    source_channel=str(
                        observation.get("source_channel", "")
                    ),
                    source_record_ordinal=observation.get(
                        "source_record_ordinal"
                    ),
                    expected_author_id=observation.get("expected_author_id"),
                    expected_first_release_time_ms=observation.get(
                        "expected_first_release_time_ms"
                    ),
                    source_profile_url=observation.get("source_profile_url"),
                )
                for observation in raw_discovery_observations
            ),
            canonical_candidate_count=discovery_counts.get(
                "deduplicated_post_candidates", 0
            ),
            same_run_duplicate_count=discovery_counts.get(
                "duplicate_source_records", 0
            ),
            observed_at=discovery_observed_at,
        )

        official_news_document: dict[str, Any] | None = None
        if config.official_news_enabled:
            current_stage = "official_news"
            try:
                collected_news = (
                    official_news_collector()
                    if official_news_collector is not None
                    else collect_binance_official_news(decision_at=decision_at)
                )
                official_news_document = _validate_official_news_document(
                    collected_news,
                    decision_at=decision_at,
                )
            except Exception as exc:
                official_news_document = {
                    "schema_version": "binance-official-news/v1",
                    "source_system": "binance_official_announcement_cms",
                    "status": "FAILED",
                    "decision_at_utc": decision_at,
                    "window_start_utc": format_utc(
                        parse_utc(decision_at) - timedelta(hours=24)
                    ),
                    "captured_at_utc": format_utc(parse_utc(runtime_clock())),
                    "record_count": 0,
                    "records": [],
                    "failure_reason": type(exc).__name__,
                }

        current_stage = "analysis"
        accepted_observations = _accepted_observation_contracts(raw)
        ledger.record_accepted_post_observations(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            observations=accepted_observations,
            now=now,
        )
        current_post_ids = frozenset(
            observation.post_id for observation in accepted_observations
        )
        if config.mode == "real":
            assert logical_run.scheduled_for_utc is not None
            baseline_post_ids = ledger.prior_succeeded_production_post_ids(
                job_namespace=config.job_namespace,
                production_job_id=config.production_job_id,
                scheduled_for_utc=logical_run.scheduled_for_utc,
            )
            dedup_status = DedupStatus.COMPUTED
        elif config.dedup_baseline_post_ids is not None:
            baseline_post_ids = frozenset(config.dedup_baseline_post_ids)
            if not all(
                isinstance(post_id, str) and post_id.isdecimal()
                for post_id in baseline_post_ids
            ):
                raise ContractViolation(
                    "dedup_baseline_post_ids must contain stable numeric post IDs"
                )
            dedup_status = DedupStatus.COMPUTED
        else:
            baseline_post_ids = frozenset()
            dedup_status = DedupStatus.NOT_COMPUTED
        new_count = (
            len(current_post_ids - baseline_post_ids)
            if dedup_status is DedupStatus.COMPUTED
            else None
        )
        duplicate_count = (
            len(current_post_ids & baseline_post_ids)
            if dedup_status is DedupStatus.COMPUTED
            else None
        )

        scored = []
        audits: list[dict[str, Any]] = []
        extraction_failures: Counter[str] = Counter()
        derivation_failures: Counter[str] = Counter()
        market_cache: dict[str, Any | None] = {}
        resolved_candidates: list[
            tuple[
                SignalCandidate,
                Any | None,
                PostDetail,
                Mapping[str, Any] | None,
                DerivationResult | None,
            ]
        ] = []
        for item in raw.get("accepted", []):
            if not isinstance(item, Mapping):
                continue
            post = PostDetail(**item)
            legacy = legacy_signals.get(post.post_url)
            try:
                candidate = extract_signal(post, None, legacy_signal=legacy)
                market = None
                if client is not None:
                    if candidate.symbol in market_cache:
                        market = market_cache[candidate.symbol]
                    else:
                        try:
                            if catalog is None:
                                catalog = client.fetch_futures_catalog()
                            market = client.fetch_snapshot(
                                candidate.symbol,
                                catalog=catalog,
                                decision_time_ms=int(
                                    parse_utc(decision_at).timestamp() * 1000
                                ),
                            )
                            market_cache[candidate.symbol] = market
                        except (MarketApiError, ContractViolation) as exc:
                            reason = exc.kind.value if isinstance(exc, MarketApiError) else type(exc).__name__
                            market_failures[reason] += 1
                            market_cache[candidate.symbol] = None
            except ContractViolation as exc:
                extraction_failures[_extraction_failure_reason(exc)] += 1
                continue

            derivation: DerivationResult | None = None
            if isinstance(market, MarketSnapshot):
                derivation = apply_derivation_policy(
                    candidate,
                    market,
                    decision_at=decision_at,
                )
                if derivation.disposition is DerivationDisposition.REJECTED:
                    derivation_failures.update(derivation.reasons)
                    audits.append(
                        _derivation_rejection_audit(
                            post=post,
                            candidate=candidate,
                            derivation=derivation,
                            market=market,
                        )
                    )
                    continue
                assert derivation.candidate is not None
                candidate = derivation.candidate
            resolved_candidates.append((candidate, market, post, legacy, derivation))

        consensus_index = build_consensus_index(
            ConsensusObservation(
                signal_id=candidate.signal_id,
                symbol=candidate.symbol,
                direction=candidate.direction,
                author_id=candidate.author_id,
                content_hash=post.content_hash,
            )
            for candidate, _, post, _, _ in resolved_candidates
        )
        for candidate, market, post, legacy, derivation in resolved_candidates:
            value = score_opportunity(
                candidate,
                None,
                market,
                decision_at=decision_at,
                consensus_index=consensus_index,
                source_detail_captured_at=post.observed_at,
                content_hash=post.content_hash,
            )
            if derivation is not None:
                value = replace(
                    value,
                    evidence=tuple(derivation.evidence) + value.evidence,
                )
            scored.append(value)
            consensus_author_ids = consensus_index.other_author_ids(
                symbol=candidate.symbol,
                direction=candidate.direction,
                author_id=candidate.author_id,
                content_hash=post.content_hash,
            )
            mapping = (
                "SYSTEM_REDERIVED_V1"
                if candidate.parameter_source.value == "SYSTEM_REDERIVED"
                else "AUTHOR_LEGACY_EXTRACTED"
                if legacy is not None
                else "AUTHOR_STRUCTURED"
            )
            audits.append(
                _candidate_audit(
                    value,
                    parameter_mapping=mapping,
                    content_hash=post.content_hash,
                    derivation=derivation,
                    consensus_author_ids=consensus_author_ids,
                )
            )

        board = build_opportunity_board(scored)
        tracking_signals = tracking_signals_from_scored(
            (*board.top, *board.watch)
        )
        scored_by_signal_id = {
            item.signal_id: item for item in (*board.top, *board.watch)
        }
        tracking_records: list[dict[str, Any]] = []
        for signal in tracking_signals:
            scored_value = scored_by_signal_id[signal.signal_id]
            candidate = scored_value.candidate
            revision = ledger.record_signal_revision(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                post_id=candidate.post_id,
                symbol=candidate.symbol,
                direction=candidate.direction,
                decision_at=decision_at,
                parameter_source=candidate.parameter_source,
                entry_low=candidate.entry_low or signal.entry_low,
                entry_high=candidate.entry_high or signal.entry_high,
                stop_loss=signal.stop_loss,
                tp1=signal.tp1,
                tp2=candidate.tp2,
                original_signal_status=(
                    "SYSTEM_REDERIVED_SHADOW"
                    if candidate.parameter_source.value == "SYSTEM_REDERIVED"
                    else "AUTHOR_PARAMETERS_VALID"
                ),
                invalidation_reason=candidate.invalidation,
                quality_flags=("SHADOW_ONLY", "NO_LIVE_TRADE"),
                signal_family_id=candidate.signal_family_id,
                now=now,
            )
            evaluation = ledger.record_tracking_evaluation(
                signal_revision_id=revision.signal_revision_id,
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                evaluated_at=decision_at,
                evaluation_status="PENDING",
                quality_flags=("AWAITING_FORWARD_CANDLES", "SHADOW_ONLY"),
                now=now,
            )
            tracking_records.append(
                {
                    "signal_id": signal.signal_id,
                    "signal_family_id": signal.signal_family_id,
                    "signal_revision_id": revision.signal_revision_id,
                    "tracking_evaluation_id": evaluation.tracking_evaluation_id,
                    "evaluation_status": evaluation.evaluation_status,
                }
            )
        filtered = Counter(extraction_failures)
        filtered.update(derivation_failures)
        filtered.update({f"MARKET_{key}": count for key, count in market_failures.items()})
        for item in board.filtered:
            reasons = item.hard_gate_reasons or (
                item.waiting_condition or "SCORE_BELOW_THRESHOLD",
            )
            filtered.update(reasons)
        current_stage = "report"
        counts = raw["counts"]
        latest_fetch_at = _latest_fetch_at(raw, market_cache, now)
        if smart_money_summary is not None:
            latest_fetch_at = format_utc(
                max(
                    parse_utc(latest_fetch_at),
                    parse_utc(smart_money_summary["captured_at_utc"]),
                )
            )
        generated_at = max(
            parse_utc(runtime_clock()),
            parse_utc(latest_fetch_at),
        )
        report = build_local_report(
            {
                "schema_version": SCHEMA_VERSION,
                "source_system": "binance_square_shadow_v4",
                "logical_run_id": logical_run.logical_run_id,
                "attempt_id": attempt.attempt_id,
                "run_identity": {
                    "job_namespace": logical_run.job_namespace,
                    "production_job_id": logical_run.production_job_id,
                    "run_namespace": logical_run.run_namespace.value,
                },
                "input_lineage": {
                    "discovery_snapshot": (
                        {
                            "path": str(discovery_snapshot_path),
                            "sha256": sha256(discovery_snapshot_content).hexdigest(),
                            "captured_at_utc": discovery_snapshot_capture.captured_at_utc,
                            "record_count": discovery_snapshot_capture.record_count,
                            "coverage_contract_version": (
                                "square-feed-coverage/v1"
                                if discovery_snapshot_capture.discovery_result is not None
                                else None
                            ),
                            "coverage_status": discovery_snapshot_capture.coverage_status,
                            "termination_reason": discovery_snapshot_capture.termination_reason,
                        }
                        if discovery_snapshot_path is not None
                        and discovery_snapshot_content is not None
                        and discovery_snapshot_capture is not None
                        else None
                    ),
                    "signal_input": (
                        {
                            "path": str(config.signals_json),
                            "sha256": sha256(signal_input_content).hexdigest(),
                            "record_count": signal_input_count,
                        }
                        if config.signals_json is not None
                        and signal_input_content is not None
                        else None
                    ),
                    "smart_money_square_identity_mapping": (
                        {
                            "path": str(
                                identity_mapping_path
                            ),
                            "sha256": sha256(identity_mapping_content).hexdigest(),
                            "captured_at_utc": identity_mapping_evidence.captured_at,
                            "record_count": len(identity_mapping_evidence.mappings),
                        }
                        if identity_mapping_path is not None
                        and identity_mapping_content is not None
                        and identity_mapping_evidence is not None
                        else None
                    ),
                    "market_catalog": (
                        {
                            "path": str(market_catalog_path),
                            "captured_at_utc": (
                                format_utc(catalog.captured_at)
                                if getattr(catalog, "captured_at", None) is not None
                                else None
                            ),
                            "record_count": len(getattr(catalog, "contracts", {})),
                        }
                        if catalog is not None
                        else None
                    ),
                    "official_news": (
                        {
                            "path": str(official_news_path),
                            "captured_at_utc": official_news_document["captured_at_utc"],
                            "record_count": official_news_document["record_count"],
                        }
                        if official_news_document is not None
                        else None
                    ),
                },
                "source_coverage": {
                    "FEED": {
                        "status": (
                            discovery_snapshot_capture.source_status
                            if discovery_snapshot_capture is not None
                            else "NOT_ATTEMPTED"
                        ),
                        "provenance": (
                            "LIVE_CAPTURE" if config.mode == "real" else "FIXTURE_REPLAY"
                        ),
                        "source_capture_time_utc": (
                            discovery_snapshot_capture.captured_at_utc
                            if discovery_snapshot_capture is not None
                            else None
                        ),
                        "capture_started_at_utc": raw.get("collection_started_at_utc"),
                        "capture_completed_at_utc": raw.get("collection_completed_at_utc"),
                        "coverage_contract_version": (
                            "square-feed-coverage/v1"
                            if discovery_snapshot_capture is not None
                            and discovery_snapshot_capture.discovery_result is not None
                            else None
                        ),
                        "coverage_status": (
                            discovery_snapshot_capture.coverage_status
                            if discovery_snapshot_capture is not None
                            else None
                        ),
                        "termination_reason": (
                            discovery_snapshot_capture.termination_reason
                            if discovery_snapshot_capture is not None
                            else None
                        ),
                        "evidence_path": (
                            str(discovery_snapshot_path)
                            if discovery_snapshot_path is not None
                            else None
                        ),
                        "reason": (
                            discovery_snapshot_capture.termination_reason
                            if discovery_snapshot_capture is not None
                            else "no_feed_snapshot_input"
                        ),
                    },
                    "BINANCE_OFFICIAL_NEWS": {
                        "status": (
                            official_news_document["status"]
                            if official_news_document is not None
                            else "NOT_ATTEMPTED"
                        ),
                        "provenance": (
                            "LIVE_CAPTURE"
                            if official_news_document is not None
                            else "UNKNOWN"
                        ),
                        "source_capture_time_utc": (
                            official_news_document["captured_at_utc"]
                            if official_news_document is not None
                            else None
                        ),
                        "reason": (
                            official_news_document.get("failure_reason")
                            if official_news_document is not None
                            else "official_news_not_requested"
                        ),
                    },
                    "SMART_MONEY": {
                        "status": (
                            smart_money_summary["status"]
                            if smart_money_summary is not None
                            else "NOT_ATTEMPTED"
                        ),
                        "provenance": (
                            "LIVE_CAPTURE"
                            if smart_money_summary is not None
                            and config.smart_money_fixture is None
                            and config.mode == "real"
                            else "FIXTURE_REPLAY"
                            if smart_money_summary is not None
                            else "UNKNOWN"
                        ),
                        "source_capture_time_utc": (
                            smart_money_summary["captured_at_utc"]
                            if smart_money_summary is not None
                            else None
                        ),
                        "reason": (
                            None
                            if smart_money_summary is not None
                            else "smart_money_not_requested"
                        ),
                    },
                    "PROFILE": {
                        "status": profile_channel_contract["status"],
                        "provenance": profile_channel_contract.get(
                            "provenance", "UNKNOWN"
                        ),
                        "source_capture_time_utc": profile_channel_contract.get(
                            "source_capture_time_utc"
                        ),
                        "evidence_path": profile_channel_contract.get(
                            "evidence_path"
                        ),
                        "reason": profile_channel_contract["reason"],
                    },
                    "MARKET_CATALOG": {
                        "status": "COMPLETE" if catalog is not None else "NOT_ATTEMPTED",
                        "provenance": "LIVE_CAPTURE" if catalog is not None else "UNKNOWN",
                        "source_capture_time_utc": (
                            format_utc(catalog.captured_at)
                            if catalog is not None
                            and getattr(catalog, "captured_at", None) is not None
                            else None
                        ),
                        "reason": None if catalog is not None else "fixture_without_market_catalog",
                    },
                },
                "scanned_at": latest_fetch_at,
                "report_generated_at": format_utc(generated_at),
                "run_timing": {
                    "scheduled_for_utc": logical_run.scheduled_for_utc,
                    "decision_at_utc": decision_at,
                    "decision_lag_seconds": (
                        int(
                            (
                                parse_utc(decision_at)
                                - parse_utc(logical_run.scheduled_for_utc)
                            ).total_seconds()
                        )
                        if logical_run.scheduled_for_utc is not None
                        else None
                    ),
                    "maximum_production_lag_seconds": int(
                        MAX_PRODUCTION_SLOT_LATENESS.total_seconds()
                    ),
                },
                "capture_timing": {
                    "discovery_snapshot_at_utc": (
                        discovery_snapshot_capture.captured_at_utc
                        if discovery_snapshot_capture is not None
                        else None
                    ),
                    "detail_fetch_started_at_utc": raw.get("collection_started_at_utc"),
                    "detail_fetch_completed_at_utc": raw.get("collection_completed_at_utc"),
                    "square_started_at_utc": raw.get("collection_started_at_utc"),
                    "square_completed_at_utc": raw.get("collection_completed_at_utc"),
                    "market_catalog_at_utc": (
                        format_utc(catalog.captured_at)
                        if catalog is not None
                        and getattr(catalog, "captured_at", None) is not None
                        else None
                    ),
                    "market_latest_at_utc": (
                        max(
                            (
                                format_utc(snapshot.captured_at)
                                for snapshot in market_cache.values()
                                if snapshot is not None
                                and getattr(snapshot, "captured_at", None) is not None
                            ),
                            key=parse_utc,
                            default=None,
                        )
                    ),
                    "latest_fetch_at_utc": latest_fetch_at,
                    "report_generated_at_utc": format_utc(generated_at),
                },
                "post_counts": {
                    "source_observations": counts[
                        "discovered_source_records"
                    ],
                    "deduplicated_candidates": counts.get(
                        "deduplicated_post_candidates",
                        counts["discovered_source_records"],
                    ),
                    "same_run_duplicates": counts.get(
                        "duplicate_source_records", 0
                    ),
                    "discovered": counts.get(
                        "deduplicated_post_candidates",
                        counts["discovered_source_records"],
                    ),
                    "total": counts["accepted_observations"],
                    "accepted": counts["accepted_observations"],
                    "quarantine": counts["quarantined_source_records"],
                    "dq_quarantine": counts.get(
                        "dq_quarantined_source_records",
                        counts["quarantined_source_records"],
                    ),
                    "window_excluded": counts.get(
                        "window_excluded_source_records", 0
                    ),
                    "unique_accepted": len(current_post_ids),
                    "new": new_count,
                    "duplicate": duplicate_count,
                    "dedup_status": dedup_status.value,
                },
                "author_coverage": {
                    "tier_a": {"covered": 0, "expected": 0, "identity_sources": []},
                    "tier_b": {"covered": 0, "expected": 0, "identity_sources": []},
                },
                "leaderboard_coverage": (
                    {
                        "covered": smart_money_summary["ranking_coverage"]["covered"],
                        "expected": 2,
                        "status": smart_money_summary["status"],
                        "complete_top30": (
                            smart_money_summary["ranking_coverage"]["covered"] > 0
                        ),
                        "ranking_types": smart_money_summary["ranking_coverage"][
                            "ranking_types"
                        ],
                        "rendered_rank_rows": smart_money_summary[
                            "ranking_coverage"
                        ]["rendered_rank_rows"],
                        "evidence_captured_at_utc": smart_money_summary[
                            "captured_at_utc"
                        ],
                        "leaderboard_data_updated_at_utc": smart_money_summary[
                            "leaderboard_data_updated_at_utc"
                        ],
                        "observation_semantics": smart_money_summary[
                            "observation_semantics"
                        ],
                    }
                    if smart_money_summary is not None
                    else seed_evidence.leaderboard_coverage
                    if seed_evidence is not None
                    else {
                        "covered": 0,
                        "expected": 4 if config.mode == "fixture" else 2,
                        "status": "BLOCKED",
                        "reason": (
                            raw.get("ranking_discovery_status")
                            if config.mode == "fixture"
                            else "Smart Money collection was not enabled"
                        ),
                    }
                ),
                "smart_money": smart_money_summary,
                "profile_channel": profile_channel_contract,
                "top_opportunities": board.top,
                "observations": board.watch,
                "tracking": {
                    "status": "SHADOW_ONLY",
                    "signal_count": len(tracking_signals),
                    "signals": tracking_signals,
                    "persisted_revision_count": len(tracking_records),
                    "pending_evaluation_count": len(tracking_records),
                    "records": tracking_records,
                    "evaluation_status": "PENDING_MARKET_REPLAY",
                },
                "filtered": dict(filtered),
                "snapshot_path": str(report_path),
                "market_snapshot_path": str(market_path),
                "limitations": [
                    (
                        "Smart Money PNL/ROI榜单已按三页各10行观察窗口采集；"
                        "COMPLETE仅表示排行覆盖，不表示原子快照"
                        if smart_money_summary is not None
                        else "排行榜入口已验证为官方小程序；完整TOP30仍未渲染，完整榜单coverage=0/4"
                        if seed_evidence is not None
                        else "历史fixture沿用原排行榜缺失口径，coverage=0/4"
                        if config.mode == "fixture"
                        else "Smart Money未启用，官方PNL/ROI coverage=0/2"
                    ),
                    (
                        "topTraderId与Square author_id保持分离；未验证映射不抓取内容、"
                        "不增加作者分，Tier A eligible=0"
                        if smart_money_summary is not None
                        else f"{len(seed_evidence.profiles)}个Profile种子只作身份/实盘上下文证据；"
                        "本轮Profile通道状态为"
                        f"{profile_coverage.status}，内容质量门未通过，不参与作者加分"
                        if seed_evidence is not None
                        else "未验证作者Profile或榜单证据，作者可信度计0分"
                    ),
                    (
                        "fixture模式未请求公共行情，候选不能进入TOP"
                        if config.mode == "fixture"
                        else (
                            "旧signal文件仅提供AUTHOR参数；时间与作者均由详情回源重验；"
                            "完整Futures证据下启用DERIVATION_POLICY_V1影子再推导"
                        )
                    ),
                    (
                        "回放未提供显式跨轮基线，新增/重复显示未计算"
                        if dedup_status is DedupStatus.NOT_COMPUTED
                        else "跨轮去重仅使用更早且成功提交的生产时槽"
                    ),
                    "追踪计划仅落本地shadow合同；尚未取得后续K线时显示PENDING",
                    "不发送Telegram、不启用常驻调度、不交易",
                ],
                "candidate_audit": audits,
            }
        )
        market_payload = {
            "schema_version": SCHEMA_VERSION,
            "source_system": "binance_public_futures_v4",
            "logical_run_id": logical_run.logical_run_id,
            "attempt_id": attempt.attempt_id,
            "decision_at_utc": decision_at,
            "generated_at_utc": format_utc(generated_at),
            "catalog": {
                "server_time_ms": getattr(catalog, "server_time_ms", None),
                "captured_at": getattr(catalog, "captured_at", None),
            },
            "snapshots": {
                symbol: _market_snapshot_audit(snapshot)
                for symbol, snapshot in sorted(market_cache.items())
                if snapshot is not None
            },
            "failures": dict(market_failures),
        }
        market_catalog_payload = (
            _market_catalog_artifact(
                catalog,
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                decision_at=decision_at,
            )
            if catalog is not None
            else None
        )
        raw_content = _json_bytes(raw)
        market_content = _json_bytes(market_payload)
        market_catalog_content = (
            _json_bytes(market_catalog_payload)
            if market_catalog_payload is not None
            else None
        )
        report_content = _json_bytes(report)
        smart_money_content = (
            _json_bytes(smart_money_document)
            if smart_money_document is not None
            else None
        )
        official_news_content = (
            _json_bytes(official_news_document)
            if official_news_document is not None
            else None
        )
        markdown_content = (
            render_local_markdown(report) + _audit_markdown(audits) + "\n"
        ).encode("utf-8")
        _write_new(raw_path, raw_content)
        _write_new(market_path, market_content)
        if market_catalog_content is not None:
            _write_new(market_catalog_path, market_catalog_content)
        if smart_money_content is not None:
            _write_new(smart_money_path, smart_money_content)
        if official_news_content is not None:
            _write_new(official_news_path, official_news_content)
        _write_new(report_path, report_content)
        _write_new(markdown_path, markdown_content)
        artifacts_written_at = max(
            parse_utc(runtime_clock()),
            generated_at,
            parse_utc(latest_fetch_at),
        )

        raw_event_start, raw_event_end = _raw_event_range(raw)
        market_event_start, market_event_end = _market_event_range(market_payload)
        if smart_money_document is not None and smart_money_content is not None:
            _persist_smart_money(
                ledger=ledger,
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                document=smart_money_document,
                evidence_path=smart_money_path,
                evidence_file_sha256=sha256(smart_money_content).hexdigest(),
                now=artifacts_written_at,
            )
        if identity_mapping_evidence is not None:
            current_stage = "identity_mapping"
            _persist_identity_mapping_evidence(
                ledger=ledger,
                evidence=identity_mapping_evidence,
                now=artifacts_written_at,
            )
            current_stage = "artifacts"
        if official_news_document is not None and official_news_content is not None:
            published_times = [
                record["published_at_utc"]
                for record in official_news_document["records"]
            ]
            news_event_start = min(published_times, key=parse_utc) if published_times else official_news_document["captured_at_utc"]
            news_event_end = max(published_times, key=parse_utc) if published_times else official_news_document["captured_at_utc"]
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=str(official_news_path),
                sha256_hex=sha256(official_news_content).hexdigest(),
                source_system="binance_official_announcement_cms",
                payload_schema_version="binance-official-news/v1",
                event_start=news_event_start,
                event_end=news_event_end,
                record_count=official_news_document["record_count"],
                now=artifacts_written_at,
            )
        if (
            discovery_snapshot_path is not None
            and discovery_snapshot_content is not None
            and discovery_snapshot_capture is not None
        ):
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=str(discovery_snapshot_path),
                sha256_hex=sha256(discovery_snapshot_content).hexdigest(),
                source_system="binance_square_feed_snapshot",
                payload_schema_version=(
                    "square-feed-coverage/v1"
                    if discovery_snapshot_capture.discovery_result is not None
                    else "binance-square-feed-snapshot/legacy-unverified"
                ),
                event_start=discovery_snapshot_capture.captured_at_utc,
                event_end=discovery_snapshot_capture.captured_at_utc,
                record_count=discovery_snapshot_capture.record_count,
                now=artifacts_written_at,
            )
        if config.signals_json is not None and signal_input_content is not None:
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=str(config.signals_json),
                sha256_hex=sha256(signal_input_content).hexdigest(),
                source_system="curated_signal_input",
                payload_schema_version="binance-square-signal-input/v1",
                event_start=None,
                event_end=None,
                record_count=signal_input_count,
                now=artifacts_written_at,
            )
        if (
            identity_mapping_path is not None
            and identity_mapping_content is not None
            and identity_mapping_evidence is not None
        ):
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=str(identity_mapping_path),
                sha256_hex=sha256(identity_mapping_content).hexdigest(),
                source_system="binance_smart_money_square_identity_mapping",
                payload_schema_version=identity_mapping_evidence.schema,
                event_start=identity_mapping_evidence.captured_at,
                event_end=identity_mapping_evidence.captured_at,
                record_count=len(identity_mapping_evidence.mappings),
                now=artifacts_written_at,
            )
        ledger.record_manifest(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            artifact_path=str(raw_path),
            sha256_hex=sha256(raw_content).hexdigest(),
            source_system="binance_square_v4",
            payload_schema_version=SCHEMA_VERSION,
            event_start=raw_event_start,
            event_end=raw_event_end,
            record_count=counts["discovered_source_records"],
            now=artifacts_written_at,
        )
        if market_catalog_payload is not None and market_catalog_content is not None:
            catalog_event_at = market_catalog_payload.get("captured_at_utc")
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=str(market_catalog_path),
                sha256_hex=sha256(market_catalog_content).hexdigest(),
                source_system="binance_public_futures_exchange_info",
                payload_schema_version="binance-futures-catalog/v1",
                event_start=catalog_event_at,
                event_end=catalog_event_at,
                record_count=market_catalog_payload["record_count"],
                now=artifacts_written_at,
            )
        if smart_money_document is not None and smart_money_content is not None:
            smart_window = smart_money_document["leaderboard_observed_window"]
            smart_event_start = format_utc(
                parse_utc(smart_window["started_at_utc"])
            )
            smart_event_end = format_utc(
                parse_utc(smart_window["completed_at_utc"])
            )
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=str(smart_money_path),
                sha256_hex=sha256(smart_money_content).hexdigest(),
                source_system="binance_futures_smart_money_public_api",
                payload_schema_version=SMART_MONEY_SCHEMA_VERSION,
                event_start=smart_event_start,
                event_end=smart_event_end,
                record_count=sum(
                    len(ranking["rows"])
                    for ranking in smart_money_document["rankings"]
                ),
                now=artifacts_written_at,
            )
        ledger.record_manifest(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            artifact_path=str(market_path),
            sha256_hex=sha256(market_content).hexdigest(),
            source_system="binance_public_futures_v4",
            payload_schema_version=SCHEMA_VERSION,
            event_start=market_event_start,
            event_end=market_event_end,
            record_count=len(market_payload["snapshots"]),
            now=artifacts_written_at,
        )
        ledger.record_manifest(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            artifact_path=str(report_path),
            sha256_hex=sha256(report_content).hexdigest(),
            source_system="binance_square_shadow_v4",
            payload_schema_version=SCHEMA_VERSION,
            event_start=format_utc(generated_at),
            event_end=format_utc(generated_at),
            record_count=1,
            now=artifacts_written_at,
        )
        ledger.record_manifest(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            artifact_path=str(markdown_path),
            sha256_hex=sha256(markdown_content).hexdigest(),
            source_system="binance_square_shadow_markdown_v4",
            payload_schema_version=SCHEMA_VERSION,
            event_start=format_utc(generated_at),
            event_end=format_utc(generated_at),
            record_count=1,
            now=artifacts_written_at,
        )
        if seed_evidence is not None:
            ledger.record_manifest(
                logical_run_id=logical_run.logical_run_id,
                attempt_id=attempt.attempt_id,
                artifact_path=seed_evidence.evidence_path,
                sha256_hex=seed_evidence.sha256_hex,
                source_system=seed_evidence.source_system,
                payload_schema_version=(
                    "binance-square-leaderboard-evidence-v1"
                ),
                event_start=seed_evidence.captured_at,
                event_end=seed_evidence.captured_at,
                record_count=len(seed_evidence.profiles),
                now=artifacts_written_at,
            )
        finished_at = max(
            parse_utc(runtime_clock()),
            artifacts_written_at,
        )
        ledger.finish_attempt(
            attempt.attempt_id,
            status="SUCCEEDED",
            finished_at=finished_at,
        )
        latest_json, latest_markdown, latest_pointer = _publish_latest(
            config.output_dir, run_dir, attempt.attempt_id
        )
        return PipelineResult(
            logical_run_id=logical_run.logical_run_id,
            attempt_id=attempt.attempt_id,
            raw_json=raw_path,
            market_json=market_path,
            report_json=report_path,
            report_markdown=markdown_path,
            latest_json=latest_json,
            latest_markdown=latest_markdown,
            latest_pointer=latest_pointer,
            smart_money_json=(
                smart_money_path if smart_money_document is not None else None
            ),
            market_catalog_json=(
                market_catalog_path if market_catalog_payload is not None else None
            ),
            official_news_json=(
                official_news_path if official_news_document is not None else None
            ),
        )
    except Exception:
        if attempt is not None:
            current_attempt = ledger.get_attempt(attempt.attempt_id)
            if current_attempt.status == "RUNNING":
                ledger.finish_attempt(
                    attempt.attempt_id,
                    status="FAILED",
                    failed_stage=current_stage,
                    finished_at=max(now, parse_utc(runtime_clock())),
                )
        raise
    finally:
        ledger.close()


__all__ = [
    "PipelineConfig",
    "PipelineResult",
    "repair_latest_from_succeeded_attempt",
    "run_shadow_radar",
]
