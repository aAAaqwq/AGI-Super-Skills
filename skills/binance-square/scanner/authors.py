"""Stable Binance Square author identities and evidence-based tier gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any

from .contracts import (
    ContractViolation,
    canonical_profile_username,
    format_utc,
)


SMART_MONEY_SQUARE_MAPPING_SCHEMA_V1 = (
    "binance-smart-money-square-identity-mapping/v1"
)
SMART_MONEY_SQUARE_MAPPING_SCHEMA = (
    "binance-smart-money-square-identity-mapping/v2"
)
SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA = (
    "binance-smart-money-square-identity-catalog/v1"
)
PUBLIC_PROFILE_REQUEST_MANIFEST_SCHEMA = (
    "binance-public-profile-request-manifest/v1"
)
PUBLIC_PROFILE_ENDPOINT = (
    "https://www.binance.com/bapi/composite/v3/friendly/pgc/user/client"
)
IDENTITY_EVIDENCE_PROVENANCE = frozenset({"LIVE_CAPTURE", "FIXTURE_REPLAY"})


@dataclass(frozen=True, slots=True)
class AuthorProfile:
    author_id: str
    username: str
    display_name: str
    profile_url: str
    visible_labels: tuple[str, ...]
    trading_days: int | None
    duration_tier: str
    public_live: bool
    leaderboard_tags: tuple[str, ...]
    tier_status: str
    follower_count: int | None
    following_count: int | None
    like_count: int | None
    observed_at: str


@dataclass(frozen=True, slots=True)
class SeedAuthorIdentity:
    """Profile-backed identity seed that is deliberately score-ineligible."""

    author_id: str
    username: str
    display_name: str
    profile_url: str
    top_trader_id: str | None
    leaderboard_tags: tuple[str, ...]
    visible_labels: tuple[str, ...]
    observed_at: str
    identity_status: str = "PROFILE_BACKED_SEED"
    tier_status: str = "UNASSESSED_PROFILE_SEED"
    score_eligible: bool = False
    author_score: int = 0


@dataclass(frozen=True, slots=True)
class SeedProfileEvidence:
    """Immutable evidence bundle for partial leaderboard seed discovery."""

    evidence_path: str
    sha256_hex: str
    captured_at: str
    source_system: str
    profiles: tuple[SeedAuthorIdentity, ...]
    leaderboard_coverage: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SmartMoneySquareIdentityMapping:
    """One explicitly evidenced, one-to-one source identity binding."""

    top_trader_id: str
    square_uid: str
    verified_at: str
    username: str | None = None
    raw_response_path: str | None = None
    raw_response_sha256: str | None = None
    top_trader_id_pointer: str | None = None
    square_uid_pointer: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityMappingReview:
    version: str
    reviewer: str
    reviewed_at: str
    decision: str
    reason: str


@dataclass(frozen=True, slots=True)
class SmartMoneySquareIdentityEvidence:
    """Auditable file evidence; aliases and display names are intentionally absent."""

    schema: str
    captured_at: str
    provenance: str
    evidence_path: str
    evidence_sha256: str
    mappings: tuple[SmartMoneySquareIdentityMapping, ...]
    tenant_id: str = "legacy-global"
    verification_status: str = "LEGACY_SELF_REPORTED"
    promotion_status: str = "PROPOSED"
    request_manifest_path: str | None = None
    request_manifest_sha256: str | None = None
    review: IdentityMappingReview | None = None
    catalog_members: tuple[tuple[str, str], ...] = ()

    def square_uid_for(self, top_trader_id: str) -> str | None:
        if not isinstance(top_trader_id, str) or not top_trader_id.strip():
            return None
        requested = top_trader_id.strip()
        is_active = self.promotion_status == "APPROVED" or (
            self.schema == SMART_MONEY_SQUARE_MAPPING_SCHEMA_V1
            and self.provenance == "FIXTURE_REPLAY"
        )
        if not is_active:
            return None
        return next(
            (
                mapping.square_uid
                for mapping in self.mappings
                if mapping.top_trader_id == requested
            ),
            None,
        )


LEADERBOARD_METRICS = ("PNL", "ROI", "VOLUME", "WIN_RATE")


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    """One accepted TOP30 row keyed by stable ``squareUid``."""

    metric: str
    period: str
    rank: int
    author_id: str
    username: str | None
    display_name: str | None
    profile_url: str | None
    value: str | int | float | None


@dataclass(frozen=True, slots=True)
class RejectedLeaderboardRow:
    """One source row rejected by the strict TOP30 contract."""

    source_index: int
    reason: str
    rank: int | None
    author_id: str | None


@dataclass(frozen=True, slots=True)
class LeaderboardParseResult:
    """A named 30D leaderboard with source-record reconciliation."""

    metric: str
    period: str
    status: str
    reason: str
    rows: tuple[LeaderboardRow, ...]
    rejected: tuple[RejectedLeaderboardRow, ...]
    source_record_count: int

    @property
    def complete_top30(self) -> bool:
        return self.status == "COMPLETE"


@dataclass(frozen=True, slots=True)
class LeaderboardCoverage:
    """Coverage across the four required named 30D TOP30 leaderboards."""

    covered: int
    expected: int
    status: str
    reason: str
    full_leaderboards_covered: int
    rendered_rank_rows: int
    expected_rows_per_leaderboard: int
    verified_seed_profiles: int
    seed_scope: str | None
    complete_top30: bool
    metric_statuses: tuple[tuple[str, str], ...]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.text.append(value)


def _public_data(payload: dict[str, Any]) -> dict[str, Any]:
    value: Any = payload
    if isinstance(value, dict) and isinstance(value.get("response"), dict):
        value = value["response"]
    if not isinstance(value, dict) or value.get("success") is not True:
        raise ContractViolation("friendly profile response was not successful")
    data = value.get("data")
    if not isinstance(data, dict):
        raise ContractViolation("friendly profile response has no data object")
    return data


_DURATION = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(years?|yrs?|months?|mos?|days?)\s*$", re.I
)


def parse_trading_days(label: str) -> int | None:
    match = _DURATION.fullmatch(label)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    unit = match.group(2).casefold()
    multiplier = Decimal(365 if unit.startswith(("year", "yr")) else 30)
    if unit.startswith("day"):
        multiplier = Decimal(1)
    return int(amount * multiplier)


def duration_tier(trading_days: int | None) -> str:
    if trading_days is None:
        return "UNKNOWN"
    if trading_days >= 365:
        return "A"
    if trading_days >= 90:
        return "B"
    return "C"


def _profile_tier_status(
    *,
    duration: str,
    public_live: bool,
    leaderboard_tags: tuple[str, ...],
    analysis_qualified: bool,
) -> str:
    has_hard_evidence = public_live or bool(leaderboard_tags)
    if not has_hard_evidence:
        return "UNQUALIFIED_MISSING_LIVE_OR_LEADERBOARD"
    if not analysis_qualified:
        return "UNQUALIFIED_PENDING_CONTENT_QUALITY"
    if duration == "A":
        return "A_EXTERNAL_VERIFIED_PROBATION"
    if duration == "B":
        return "B"
    if duration == "C":
        return "C"
    return "UNQUALIFIED_UNKNOWN_TRADING_DURATION"


def _optional_count(data: dict[str, Any], field_name: str) -> int | None:
    value = data.get(field_name)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_author_profile(
    *,
    public_payload: dict[str, Any],
    html: str | None,
    observed_at: str | datetime,
    leaderboard_tags: tuple[str, ...] = (),
    analysis_qualified: bool = False,
) -> AuthorProfile:
    """Parse aliases and tags while keeping ``squareUid`` as the only identity."""

    data = _public_data(public_payload)
    author_id = data.get("squareUid")
    username = data.get("username")
    display_name = data.get("displayName")
    if not isinstance(author_id, str) or not author_id.strip():
        raise ContractViolation("profile is missing stable squareUid")
    if not isinstance(username, str) or not username.strip():
        raise ContractViolation("profile is missing username alias")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ContractViolation("profile is missing display name alias")
    if "LIVE" in {username.strip().upper(), display_name.strip().upper()}:
        raise ContractViolation("LIVE is a label, not an author")

    raw_tags = data.get("userTags") or []
    if not isinstance(raw_tags, list):
        raise ContractViolation("profile userTags must be a list")
    typed_tags: list[tuple[str, int | None]] = []
    for tag in raw_tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("name"), str):
            continue
        tag_type = tag.get("type")
        typed_tags.append(
            (tag["name"].strip(), tag_type if isinstance(tag_type, int) else None)
        )

    labels: list[str] = []
    if data.get("verificationType") == 1:
        labels.append("Square Verified+")
    labels.extend(name for name, _ in typed_tags if name)
    if html:
        visible = _VisibleTextParser()
        visible.feed(html)
        for expected in ("Square Verified+",):
            if expected in visible.text and expected not in labels:
                labels.append(expected)

    trading_days = next(
        (
            parsed
            for name, tag_type in typed_tags
            if tag_type == 4
            for parsed in [parse_trading_days(name)]
            if parsed is not None
        ),
        None,
    )
    duration = duration_tier(trading_days)
    public_live = any(
        "live" in name.casefold()
        and ("trad" in name.casefold() or "futures" in name.casefold())
        for name, _ in typed_tags
    )
    normalized_leaderboard = tuple(
        value.strip() for value in leaderboard_tags if value.strip()
    )
    return AuthorProfile(
        author_id=author_id.strip(),
        username=username.strip(),
        display_name=display_name.strip(),
        profile_url=(
            "https://www.binance.com/en/square/profile/"
            f"{username.strip().casefold()}"
        ),
        visible_labels=tuple(dict.fromkeys(labels)),
        trading_days=trading_days,
        duration_tier=duration,
        public_live=public_live,
        leaderboard_tags=normalized_leaderboard,
        tier_status=_profile_tier_status(
            duration=duration,
            public_live=public_live,
            leaderboard_tags=normalized_leaderboard,
            analysis_qualified=analysis_qualified,
        ),
        follower_count=_optional_count(data, "totalFollowerCount"),
        following_count=_optional_count(data, "totalFollowCount"),
        like_count=_optional_count(data, "totalLikeCount"),
        observed_at=format_utc(observed_at),
    )


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractViolation(f"{field_name} must be a list of strings")
    return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))


def _leaderboard_objects(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    objects: list[dict[str, Any]] = []
    pending: list[Any] = [payload]
    while pending:
        value = pending.pop(0)
        if not isinstance(value, dict) or any(value is item for item in objects):
            continue
        objects.append(value)
        for field in ("response", "data", "result"):
            nested = value.get(field)
            if isinstance(nested, dict):
                pending.append(nested)
    return tuple(objects)


def _leaderboard_value(
    objects: tuple[dict[str, Any], ...], fields: tuple[str, ...]
) -> Any:
    for value in objects:
        for field in fields:
            if field in value:
                return value[field]
    return None


def _normalize_metric(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation("leaderboard must explicitly name rankingType")
    normalized = re.sub(r"[\s-]+", "_", value.strip().upper())
    if normalized == "WINRATE":
        normalized = "WIN_RATE"
    if normalized not in LEADERBOARD_METRICS:
        raise ContractViolation(f"unsupported 30D leaderboard metric: {value}")
    return normalized


def _optional_alias(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_30d_leaderboard(payload: dict[str, Any]) -> LeaderboardParseResult:
    """Parse a strictly named PNL/ROI/VOLUME/WIN_RATE 30D TOP30.

    ``COMPLETE`` is possible only for exactly 30 source rows with ranks 1..30,
    30 unique non-empty ``squareUid`` values, and no rejected row.  Partial
    evidence remains auditable but never masquerades as a complete ranking.
    """

    if not isinstance(payload, dict):
        raise ContractViolation("leaderboard payload must be an object")
    objects = _leaderboard_objects(payload)
    if any("success" in value and value.get("success") is not True for value in objects):
        raise ContractViolation("leaderboard response was not successful")
    metric = _normalize_metric(
        _leaderboard_value(objects, ("rankingType", "ranking_type", "metric"))
    )
    raw_period = _leaderboard_value(
        objects, ("timeRange", "time_range", "period")
    )
    if not isinstance(raw_period, str) or raw_period.strip().upper() != "30D":
        raise ContractViolation("leaderboard must explicitly name the 30D period")
    period = "30D"
    raw_rows = _leaderboard_value(
        objects, ("rows", "rankings", "leaderboard", "list", "items")
    )
    if not isinstance(raw_rows, list):
        raise ContractViolation("leaderboard payload must contain a rows list")

    accepted: list[LeaderboardRow] = []
    rejected: list[RejectedLeaderboardRow] = []
    ranks: set[int] = set()
    author_ids: set[str] = set()
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict):
            rejected.append(RejectedLeaderboardRow(index, "row_not_object", None, None))
            continue
        raw_rank = next(
            (raw.get(field) for field in ("rank", "ranking", "position") if field in raw),
            None,
        )
        if isinstance(raw_rank, int) and not isinstance(raw_rank, bool):
            rank = raw_rank
        elif isinstance(raw_rank, str) and raw_rank.strip().isdecimal():
            rank = int(raw_rank.strip())
        else:
            rank = None
        raw_author_object = raw.get("author", raw.get("user"))
        author_object = (
            raw_author_object if isinstance(raw_author_object, dict) else {}
        )
        raw_author = next(
            (
                raw.get(field)
                for field in ("squareUid", "author_id", "authorId")
                if field in raw
            ),
            next(
                (
                    author_object.get(field)
                    for field in ("squareUid", "author_id", "authorId")
                    if field in author_object
                ),
                None,
            ),
        )
        author_id = _optional_alias(raw_author)
        reason: str | None = None
        if rank is None or rank not in range(1, 31):
            reason = "rank_must_be_integer_1_to_30"
        elif author_id is None:
            reason = "missing_stable_author_id"
        elif rank in ranks:
            reason = "duplicate_rank"
        elif author_id in author_ids:
            reason = "duplicate_author_id"
        if reason is not None:
            rejected.append(RejectedLeaderboardRow(index, reason, rank, author_id))
            continue

        username = _optional_alias(raw.get("username", author_object.get("username")))
        display_name = _optional_alias(
            raw.get(
                "displayName",
                raw.get(
                    "display_name",
                    author_object.get(
                        "displayName", author_object.get("display_name")
                    ),
                ),
            )
        )
        raw_profile_url = raw.get(
            "profileUrl",
            raw.get(
                "profile_url",
                author_object.get("profileUrl", author_object.get("profile_url")),
            ),
        )
        profile_url = _optional_alias(raw_profile_url)
        if profile_url is not None:
            try:
                route_alias = canonical_profile_username(profile_url)
            except ContractViolation:
                rejected.append(
                    RejectedLeaderboardRow(index, "invalid_profile_url", rank, author_id)
                )
                continue
            if username is not None and route_alias.casefold() != username.casefold():
                rejected.append(
                    RejectedLeaderboardRow(
                        index, "profile_alias_conflict", rank, author_id
                    )
                )
                continue
        elif username is not None:
            profile_url = (
                "https://www.binance.com/en/square/profile/" + username.casefold()
            )
        metric_fields = {
            "PNL": ("pnl", "value", "metricValue"),
            "ROI": ("roi", "value", "metricValue"),
            "VOLUME": ("volume", "value", "metricValue"),
            "WIN_RATE": ("winRate", "win_rate", "value", "metricValue"),
        }[metric]
        metric_value = next(
            (raw.get(field) for field in metric_fields if field in raw), None
        )
        if not isinstance(metric_value, (str, int, float)) or isinstance(
            metric_value, bool
        ):
            metric_value = None
        ranks.add(rank)
        author_ids.add(author_id)
        accepted.append(
            LeaderboardRow(
                metric=metric,
                period=period,
                rank=rank,
                author_id=author_id,
                username=username,
                display_name=display_name,
                profile_url=profile_url,
                value=metric_value,
            )
        )

    accepted.sort(key=lambda row: row.rank)
    complete = (
        len(raw_rows) == 30
        and len(accepted) == 30
        and not rejected
        and ranks == set(range(1, 31))
        and len(author_ids) == 30
    )
    if complete:
        status, reason = "COMPLETE", "strict_top30_contract_satisfied"
    elif not raw_rows:
        status, reason = "EMPTY", "leaderboard_rows_empty"
    elif accepted:
        status, reason = "PARTIAL", "strict_top30_contract_not_satisfied"
    else:
        status, reason = "FAILED", "no_valid_leaderboard_rows"
    if len(accepted) + len(rejected) != len(raw_rows):
        raise AssertionError("leaderboard source records did not reconcile")
    return LeaderboardParseResult(
        metric=metric,
        period=period,
        status=status,
        reason=reason,
        rows=tuple(accepted),
        rejected=tuple(rejected),
        source_record_count=len(raw_rows),
    )


def parse_30d_leaderboards(payload: dict[str, Any]) -> tuple[LeaderboardParseResult, ...]:
    """Parse an offline fixture containing explicitly named leaderboard objects."""

    if not isinstance(payload, dict):
        raise ContractViolation("leaderboard fixture must be an object")
    raw = payload.get("leaderboards")
    if raw is None and any(
        field in payload for field in ("rankingType", "ranking_type", "metric")
    ):
        raw = [payload]
    if not isinstance(raw, list):
        raise ContractViolation("leaderboard fixture must contain leaderboards list")
    results = tuple(parse_30d_leaderboard(item) for item in raw)
    metrics = [result.metric for result in results]
    if len(metrics) != len(set(metrics)):
        raise ContractViolation("leaderboard fixture contains duplicate named metrics")
    return results


def assess_leaderboard_coverage(
    leaderboards: tuple[LeaderboardParseResult, ...] | list[LeaderboardParseResult],
    *,
    seed_count: int = 0,
) -> LeaderboardCoverage:
    """Assess four-board coverage without promoting Profile seeds to rank rows."""

    if not isinstance(seed_count, int) or isinstance(seed_count, bool) or seed_count < 0:
        raise ContractViolation("leaderboard seed_count must be non-negative")
    by_metric: dict[str, LeaderboardParseResult] = {}
    for result in leaderboards:
        if not isinstance(result, LeaderboardParseResult):
            raise ContractViolation(
                "leaderboard coverage requires LeaderboardParseResult records"
            )
        if result.metric in by_metric:
            raise ContractViolation(
                f"duplicate leaderboard metric in coverage: {result.metric}"
            )
        by_metric[result.metric] = result
    covered = sum(
        by_metric.get(metric) is not None
        and by_metric[metric].status == "COMPLETE"
        for metric in LEADERBOARD_METRICS
    )
    rendered = sum(result.source_record_count for result in by_metric.values())
    complete = covered == len(LEADERBOARD_METRICS) and set(by_metric) == set(
        LEADERBOARD_METRICS
    )
    if complete:
        status = "COMPLETE"
        reason = "all_four_named_30d_top30_leaderboards_complete"
    elif not by_metric and seed_count:
        status = "PARTIAL_SEED_DISCOVERY"
        reason = "profile_seeds_are_not_leaderboard_rows"
    elif not by_metric:
        status = "NOT_ATTEMPTED"
        reason = "no_leaderboard_evidence"
    elif all(result.status == "FAILED" for result in by_metric.values()):
        status = "FAILED"
        reason = "all_supplied_leaderboards_failed_strict_parsing"
    else:
        status = "PARTIAL"
        reason = "fewer_than_four_complete_named_30d_top30_leaderboards"
    return LeaderboardCoverage(
        covered=covered,
        expected=len(LEADERBOARD_METRICS),
        status=status,
        reason=reason,
        full_leaderboards_covered=covered,
        rendered_rank_rows=rendered,
        expected_rows_per_leaderboard=30,
        verified_seed_profiles=seed_count,
        seed_scope="PROFILE_BACKED" if seed_count else None,
        complete_top30=complete,
        metric_statuses=tuple(
            (metric, by_metric[metric].status if metric in by_metric else "NOT_ATTEMPTED")
            for metric in LEADERBOARD_METRICS
        ),
    )


def load_smart_money_square_identity_evidence(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> SmartMoneySquareIdentityEvidence:
    """Load an explicit ``topTraderId`` → ``squareUid`` evidence document.

    The file hash, capture time, provenance, schema, and one-to-one mapping are
    all part of the public contract.  Names and aliases are never considered.
    """

    evidence_path = Path(path)
    try:
        content = evidence_path.read_bytes()
        payload = json.loads(content)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(
            f"cannot read Smart Money identity mapping evidence: {evidence_path}"
        ) from exc
    digest = sha256(content).hexdigest()
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str)
        or expected_sha256.casefold() != digest
    ):
        raise ContractViolation("Smart Money identity mapping evidence SHA256 mismatch")
    if not isinstance(payload, dict):
        raise ContractViolation("Smart Money identity mapping evidence must be an object")
    schema = payload.get("schema")
    if schema not in {
        SMART_MONEY_SQUARE_MAPPING_SCHEMA_V1,
        SMART_MONEY_SQUARE_MAPPING_SCHEMA,
    }:
        raise ContractViolation(
            "Smart Money identity mapping schema must be "
            f"{SMART_MONEY_SQUARE_MAPPING_SCHEMA_V1} or "
            f"{SMART_MONEY_SQUARE_MAPPING_SCHEMA}"
        )
    captured_raw = payload.get("captured_at_utc", payload.get("verified_at_utc"))
    try:
        captured_at = format_utc(captured_raw)
    except ContractViolation as exc:
        raise ContractViolation(
            "Smart Money identity mapping evidence requires captured_at_utc"
        ) from exc
    provenance = str(payload.get("provenance") or "").upper()
    if provenance not in IDENTITY_EVIDENCE_PROVENANCE:
        raise ContractViolation(
            "Smart Money identity mapping provenance must be LIVE_CAPTURE or FIXTURE_REPLAY"
        )
    if schema == SMART_MONEY_SQUARE_MAPPING_SCHEMA:
        return _load_v2_identity_evidence(
            evidence_path=evidence_path,
            content=content,
            digest=digest,
            payload=payload,
            captured_at=captured_at,
            provenance=provenance,
        )

    raw_mappings = payload.get("mappings")
    if raw_mappings is None and (
        "topTraderId" in payload or "squareUid" in payload
    ):
        raw_mappings = [payload]
    if not isinstance(raw_mappings, list) or not raw_mappings:
        raise ContractViolation(
            "Smart Money identity mapping evidence requires non-empty mappings"
        )

    mappings: list[SmartMoneySquareIdentityMapping] = []
    seen_traders: set[str] = set()
    seen_square_uids: set[str] = set()
    for index, raw in enumerate(raw_mappings):
        if not isinstance(raw, dict):
            raise ContractViolation(f"identity mappings[{index}] must be an object")
        top_trader_id = _required_text(
            raw.get("topTraderId"), f"identity mappings[{index}].topTraderId"
        )
        square_uid = _required_text(
            raw.get("squareUid"), f"identity mappings[{index}].squareUid"
        )
        if top_trader_id in seen_traders:
            raise ContractViolation(
                f"duplicate identity mapping topTraderId: {top_trader_id}"
            )
        if square_uid in seen_square_uids:
            raise ContractViolation(
                f"identity mapping squareUid is not one-to-one: {square_uid}"
            )
        seen_traders.add(top_trader_id)
        seen_square_uids.add(square_uid)
        verified_raw = raw.get(
            "verified_at_utc", raw.get("captured_at_utc", captured_at)
        )
        try:
            verified_at = format_utc(verified_raw)
        except ContractViolation as exc:
            raise ContractViolation(
                f"identity mappings[{index}].verified_at_utc is invalid"
            ) from exc
        mappings.append(
            SmartMoneySquareIdentityMapping(
                top_trader_id=top_trader_id,
                square_uid=square_uid,
                verified_at=verified_at,
            )
        )
    return SmartMoneySquareIdentityEvidence(
        schema=SMART_MONEY_SQUARE_MAPPING_SCHEMA_V1,
        captured_at=captured_at,
        provenance=provenance,
        evidence_path=str(evidence_path),
        evidence_sha256=digest,
        mappings=tuple(mappings),
        verification_status="LEGACY_SELF_REPORTED",
        promotion_status="PROPOSED",
    )


def load_smart_money_square_identity_catalog(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> SmartMoneySquareIdentityEvidence:
    """Load and aggregate an immutable catalog of APPROVED mapping/v2 files."""

    catalog_path = Path(path)
    try:
        content = catalog_path.read_bytes()
        payload = json.loads(content)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(
            f"cannot read Smart Money identity catalog: {catalog_path}"
        ) from exc
    digest = sha256(content).hexdigest()
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str)
        or expected_sha256.casefold() != digest
    ):
        raise ContractViolation("Smart Money identity catalog SHA256 mismatch")
    if not isinstance(payload, dict) or payload.get("schema") != (
        SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA
    ):
        raise ContractViolation(
            "Smart Money identity catalog schema must be "
            f"{SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA}"
        )
    if {"catalog_sha256", "receipt"}.intersection(payload):
        raise ContractViolation("catalog hash belongs in an external receipt")
    tenant_id = _required_text(payload.get("tenant_id"), "catalog.tenant_id")
    provenance = _required_text(
        payload.get("provenance"), "catalog.provenance"
    ).upper()
    if provenance not in IDENTITY_EVIDENCE_PROVENANCE:
        raise ContractViolation("identity catalog provenance is invalid")
    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ContractViolation("identity catalog requires non-empty artifacts")

    combined: list[
        tuple[SmartMoneySquareIdentityMapping, SmartMoneySquareIdentityEvidence]
    ] = []
    seen_paths: set[Path] = set()
    seen_traders: set[str] = set()
    seen_square_uids: set[str] = set()
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256"}:
            raise ContractViolation(
                f"catalog artifacts[{index}] must contain only path and sha256"
            )
        member_path = _resolved_evidence_path(
            catalog_path, raw.get("path"), f"catalog artifacts[{index}].path"
        )
        member_path = member_path.resolve()
        if member_path in seen_paths:
            raise ContractViolation("identity catalog contains duplicate artifact path")
        seen_paths.add(member_path)
        member_digest = _sha256_reference(
            raw.get("sha256"), f"catalog artifacts[{index}].sha256"
        )
        evidence = load_smart_money_square_identity_evidence(
            member_path, expected_sha256=member_digest
        )
        if evidence.schema != SMART_MONEY_SQUARE_MAPPING_SCHEMA:
            raise ContractViolation("identity catalog accepts only mapping/v2 artifacts")
        if (
            evidence.verification_status != "DIRECT_VERIFIED"
            or evidence.promotion_status != "APPROVED"
        ):
            raise ContractViolation(
                "identity catalog accepts only DIRECT_VERIFIED APPROVED artifacts"
            )
        if evidence.tenant_id != tenant_id:
            raise ContractViolation("identity catalog members must share one tenant")
        if evidence.provenance != provenance:
            raise ContractViolation("identity catalog members must share one provenance")
        if len(evidence.mappings) != 1:
            raise ContractViolation("identity catalog members must bind exactly one pair")
        mapping = evidence.mappings[0]
        if mapping.top_trader_id in seen_traders:
            raise ContractViolation("identity catalog topTraderId is not one-to-one")
        if mapping.square_uid in seen_square_uids:
            raise ContractViolation("identity catalog squareUid is not one-to-one")
        seen_traders.add(mapping.top_trader_id)
        seen_square_uids.add(mapping.square_uid)
        combined.append((mapping, evidence))

    combined.sort(
        key=lambda item: (
            item[0].top_trader_id,
            item[0].square_uid,
            str(Path(item[1].evidence_path).resolve()),
        )
    )
    return SmartMoneySquareIdentityEvidence(
        schema=SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA,
        captured_at=max(evidence.captured_at for _, evidence in combined),
        provenance=provenance,
        evidence_path=str(catalog_path),
        evidence_sha256=digest,
        mappings=tuple(mapping for mapping, _ in combined),
        tenant_id=tenant_id,
        verification_status="DIRECT_VERIFIED",
        promotion_status="APPROVED",
        catalog_members=tuple(
            (
                str(Path(evidence.evidence_path).resolve()),
                evidence.evidence_sha256,
            )
            for _, evidence in combined
        ),
    )


def _resolved_evidence_path(base: Path, value: Any, field_name: str) -> Path:
    raw = _required_text(value, field_name)
    path = Path(raw)
    return path if path.is_absolute() else base.parent / path


def _sha256_reference(value: Any, field_name: str) -> str:
    digest = _required_text(value, field_name).casefold()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractViolation(f"{field_name} must be a lowercase SHA256")
    return digest


def _read_hash_bound_file(path: Path, digest: str, field_name: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ContractViolation(f"{field_name} must reference a readable file") from exc
    if sha256(content).hexdigest() != digest:
        raise ContractViolation(f"{field_name} SHA256 mismatch")
    return content


def _json_pointer(document: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ContractViolation("identity evidence JSON Pointer is invalid")
    value = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise ContractViolation(f"identity evidence JSON Pointer not found: {pointer}")
    return value


def _load_v2_identity_evidence(
    *,
    evidence_path: Path,
    content: bytes,
    digest: str,
    payload: dict[str, Any],
    captured_at: str,
    provenance: str,
) -> SmartMoneySquareIdentityEvidence:
    forbidden_self_hashes = {"artifact_sha256", "mapping_sha256", "receipt"}
    if forbidden_self_hashes.intersection(payload):
        raise ContractViolation("mapping artifact hash belongs in an external receipt")
    tenant_id = _required_text(payload.get("tenant_id"), "tenant_id")
    verification_status = str(payload.get("verification_status") or "").upper()
    if verification_status != "DIRECT_VERIFIED":
        raise ContractViolation("verification_status must be DIRECT_VERIFIED")
    promotion_status = str(payload.get("promotion_status") or "").upper()
    if promotion_status not in {"PROPOSED", "APPROVED"}:
        raise ContractViolation("promotion_status must be PROPOSED or APPROVED")

    manifest_ref = payload.get("request_manifest")
    if not isinstance(manifest_ref, dict):
        raise ContractViolation("v2 identity evidence requires request_manifest")
    manifest_path = _resolved_evidence_path(
        evidence_path, manifest_ref.get("path"), "request_manifest.path"
    )
    manifest_digest = _sha256_reference(
        manifest_ref.get("sha256"), "request_manifest.sha256"
    )
    manifest_content = _read_hash_bound_file(
        manifest_path, manifest_digest, "request_manifest"
    )
    try:
        manifest = json.loads(manifest_content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation("request manifest must be readable JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != (
        PUBLIC_PROFILE_REQUEST_MANIFEST_SCHEMA
    ):
        raise ContractViolation("request manifest schema is invalid")
    if format_utc(manifest.get("captured_at_utc")) != captured_at:
        raise ContractViolation("mapping and request manifest capture times differ")
    if manifest.get("tenant_id") != tenant_id:
        raise ContractViolation("mapping and request manifest tenants differ")

    request = manifest.get("request")
    if not isinstance(request, dict):
        raise ContractViolation("request manifest requires request metadata")
    if request.get("method") != "POST" or request.get("url") != PUBLIC_PROFILE_ENDPOINT:
        raise ContractViolation("request manifest endpoint contract is invalid")
    body = request.get("body")
    required_body = {
        "getFollowCount": True,
        "queryFollowersInfo": True,
        "queryRelationTokens": True,
    }
    if not isinstance(body, dict) or any(body.get(key) is not value for key, value in required_body.items()):
        raise ContractViolation("request manifest body contract is invalid")
    username = _required_text(body.get("username"), "request.body.username")
    if set(body) != {"username", *required_body}:
        raise ContractViolation("request manifest body contains unsupported fields")
    headers = request.get("headers")
    allowed_headers = {"accept", "content-type", "user-agent"}
    if not isinstance(headers, dict) or {
        str(key).casefold() for key in headers
    } != allowed_headers:
        raise ContractViolation("request manifest headers violate the anonymous allowlist")
    normalized_headers = {str(key).casefold(): value for key, value in headers.items()}
    if normalized_headers.get("content-type") != "application/json":
        raise ContractViolation("request manifest Content-Type must be application/json")
    credential_metadata = request.get("credential_metadata")
    if credential_metadata != {
        "mode": "ANONYMOUS",
        "cookie_jar_used": False,
        "authorization_used": False,
        "browser_session_used": False,
    }:
        raise ContractViolation("credential metadata must prove an anonymous independent client")

    response = manifest.get("response")
    if not isinstance(response, dict):
        raise ContractViolation("request manifest requires response metadata")
    if response.get("http_status") != 200:
        raise ContractViolation("identity response HTTP status must be 200")
    api_status = response.get("api_status")
    if not isinstance(api_status, dict) or api_status.get("success") is not True:
        raise ContractViolation("identity response API status was not successful")
    raw_path_from_manifest = _resolved_evidence_path(
        manifest_path, response.get("raw_path"), "response.raw_path"
    )
    raw_digest_from_manifest = _sha256_reference(
        response.get("raw_sha256"), "response.raw_sha256"
    )
    raw_content = _read_hash_bound_file(
        raw_path_from_manifest, raw_digest_from_manifest, "raw_response"
    )
    try:
        raw_payload = json.loads(raw_content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation("raw identity response must be readable JSON") from exc
    if not isinstance(raw_payload, dict) or raw_payload.get("success") is not True:
        raise ContractViolation("raw identity response was not successful")
    if api_status.get("code") != raw_payload.get("code") or api_status.get("message") != raw_payload.get("message"):
        raise ContractViolation("manifest API status does not match raw response")

    raw_mappings = payload.get("mappings")
    if not isinstance(raw_mappings, list) or len(raw_mappings) != 1:
        raise ContractViolation("each v2 artifact must bind exactly one anonymous response")
    raw_mapping = raw_mappings[0]
    if not isinstance(raw_mapping, dict):
        raise ContractViolation("identity mapping must be an object")
    mapping_username = _required_text(raw_mapping.get("username"), "mappings[0].username")
    if mapping_username != username:
        raise ContractViolation("mapping username does not match request body")
    top_trader_id = _required_text(raw_mapping.get("topTraderId"), "mappings[0].topTraderId")
    square_uid = _required_text(raw_mapping.get("squareUid"), "mappings[0].squareUid")
    verified_at = format_utc(raw_mapping.get("verified_at_utc"))
    if verified_at != captured_at:
        raise ContractViolation("mapping verified_at must equal capture time")
    raw_ref = raw_mapping.get("raw_response")
    if not isinstance(raw_ref, dict):
        raise ContractViolation("mapping requires raw_response reference")
    raw_path_from_mapping = _resolved_evidence_path(
        evidence_path, raw_ref.get("path"), "mappings[0].raw_response.path"
    )
    raw_digest_from_mapping = _sha256_reference(
        raw_ref.get("sha256"), "mappings[0].raw_response.sha256"
    )
    if (
        raw_path_from_mapping.resolve() != raw_path_from_manifest.resolve()
        or raw_digest_from_mapping != raw_digest_from_manifest
    ):
        raise ContractViolation("mapping and manifest raw response references differ")
    pointers = raw_mapping.get("json_pointers")
    expected_pointers = {
        "topTraderId": "/data/topTraderId",
        "squareUid": "/data/squareUid",
    }
    if pointers != expected_pointers:
        raise ContractViolation("identity mapping JSON Pointers are not authoritative")
    if _json_pointer(raw_payload, pointers["topTraderId"]) != top_trader_id:
        raise ContractViolation("raw topTraderId does not match mapping")
    if _json_pointer(raw_payload, pointers["squareUid"]) != square_uid:
        raise ContractViolation("raw squareUid does not match mapping")

    raw_review = payload.get("review")
    review: IdentityMappingReview | None = None
    if promotion_status == "PROPOSED":
        if raw_review is not None:
            raise ContractViolation("PROPOSED mapping must not carry an approval review")
    else:
        if not isinstance(raw_review, dict):
            raise ContractViolation("APPROVED mapping requires review metadata")
        reviewed_at = format_utc(raw_review.get("reviewed_at"))
        if reviewed_at < captured_at:
            raise ContractViolation("identity review cannot precede capture")
        review = IdentityMappingReview(
            version=_required_text(raw_review.get("version"), "review.version"),
            reviewer=_required_text(raw_review.get("reviewer"), "review.reviewer"),
            reviewed_at=reviewed_at,
            decision=_required_text(raw_review.get("decision"), "review.decision").upper(),
            reason=_required_text(raw_review.get("reason"), "review.reason"),
        )
        if review.decision != "APPROVE":
            raise ContractViolation("APPROVED mapping review decision must be APPROVE")

    mapping = SmartMoneySquareIdentityMapping(
        top_trader_id=top_trader_id,
        square_uid=square_uid,
        verified_at=verified_at,
        username=mapping_username,
        raw_response_path=str(raw_path_from_manifest),
        raw_response_sha256=raw_digest_from_manifest,
        top_trader_id_pointer=expected_pointers["topTraderId"],
        square_uid_pointer=expected_pointers["squareUid"],
    )
    return SmartMoneySquareIdentityEvidence(
        schema=SMART_MONEY_SQUARE_MAPPING_SCHEMA,
        captured_at=captured_at,
        provenance=provenance,
        evidence_path=str(evidence_path),
        evidence_sha256=digest,
        mappings=(mapping,),
        tenant_id=tenant_id,
        verification_status=verification_status,
        promotion_status=promotion_status,
        request_manifest_path=str(manifest_path),
        request_manifest_sha256=manifest_digest,
        review=review,
    )


def load_seed_profile_evidence(path: str | Path) -> SeedProfileEvidence:
    """Load a fixed profile-seed artifact without promoting authors or ranks.

    The evidence proves stable profile identities and a Binance-provided
    leaderboard deep link.  It does not prove that any complete TOP30 list was
    rendered and never makes an author eligible for credibility points.
    """

    evidence_path = Path(path)
    try:
        content = evidence_path.read_bytes()
        payload = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolation(
            f"cannot read leaderboard seed evidence: {evidence_path}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        "binance-square-leaderboard-evidence-v1"
    ):
        raise ContractViolation("unsupported leaderboard seed evidence schema")
    captured_at = format_utc(payload.get("captured_at_utc"))
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ContractViolation("leaderboard seed evidence requires profiles")

    author_ids: set[str] = set()
    alias_owners: dict[str, str] = {}
    profiles: list[SeedAuthorIdentity] = []
    for index, raw in enumerate(raw_profiles):
        if not isinstance(raw, dict):
            raise ContractViolation(f"profiles[{index}] must be an object")
        author_id = _required_text(raw.get("square_uid"), f"profiles[{index}].square_uid")
        username = _required_text(raw.get("username"), f"profiles[{index}].username")
        display_name = _required_text(
            raw.get("display_name"), f"profiles[{index}].display_name"
        )
        profile_url = _required_text(
            raw.get("profile_url"), f"profiles[{index}].profile_url"
        )
        if author_id in author_ids:
            raise ContractViolation(f"duplicate square_uid: {author_id}")
        route_alias = canonical_profile_username(profile_url)
        if route_alias.casefold() != username.casefold():
            raise ContractViolation(
                f"profile route alias conflicts with username: {username}"
            )
        alias_key = username.casefold()
        owner = alias_owners.get(alias_key)
        if owner is not None and owner != author_id:
            raise ContractViolation(f"ALIAS_COLLISION: {username}")
        alias_owners[alias_key] = author_id
        author_ids.add(author_id)

        top_trader_id = raw.get("top_trader_id")
        if top_trader_id is not None and (
            not isinstance(top_trader_id, str) or not top_trader_id.strip()
        ):
            raise ContractViolation(
                f"profiles[{index}].top_trader_id must be a string or null"
            )
        badges = _string_tuple(raw.get("badges"), f"profiles[{index}].badges")
        labels = _string_tuple(
            raw.get("leaderboard_labels"),
            f"profiles[{index}].leaderboard_labels",
        )
        tags = _string_tuple(raw.get("user_tags"), f"profiles[{index}].user_tags")
        profiles.append(
            SeedAuthorIdentity(
                author_id=author_id,
                username=username,
                display_name=display_name,
                profile_url=profile_url,
                top_trader_id=top_trader_id.strip() if isinstance(top_trader_id, str) else None,
                leaderboard_tags=tuple(dict.fromkeys((*badges, *labels))),
                visible_labels=tuple(dict.fromkeys((*tags, *badges, *labels))),
                observed_at=captured_at,
            )
        )

    entry = payload.get("leaderboard_entry")
    if not isinstance(entry, dict) or entry.get("coverage_status") != (
        "PARTIAL_SEED_DISCOVERY"
    ):
        raise ContractViolation("leaderboard entry must be partial seed discovery")
    digest = sha256(content).hexdigest()
    coverage = {
        "covered": 0,
        "expected": 4,
        "status": "PARTIAL_SEED_DISCOVERY",
        "reason": "Profile种子只验证身份合同；未提供完整TOP30榜单",
        "full_leaderboards_covered": 0,
        "rendered_rank_rows": 0,
        "expected_rows_per_leaderboard": 30,
        "verified_seed_profiles": len(profiles),
        "seed_scope": "PROFILE_BACKED",
        "complete_top30": False,
        "evidence_captured_at_utc": captured_at,
        "evidence_sha256": digest,
        "evidence_path": str(evidence_path),
    }
    return SeedProfileEvidence(
        evidence_path=str(evidence_path),
        sha256_hex=digest,
        captured_at=captured_at,
        source_system="binance_square_profile_seed_cdp_v1",
        profiles=tuple(profiles),
        leaderboard_coverage=coverage,
    )


__all__ = [
    "AuthorProfile",
    "IdentityMappingReview",
    "LEADERBOARD_METRICS",
    "LeaderboardCoverage",
    "LeaderboardParseResult",
    "LeaderboardRow",
    "PUBLIC_PROFILE_ENDPOINT",
    "PUBLIC_PROFILE_REQUEST_MANIFEST_SCHEMA",
    "RejectedLeaderboardRow",
    "SeedAuthorIdentity",
    "SeedProfileEvidence",
    "SmartMoneySquareIdentityEvidence",
    "SmartMoneySquareIdentityMapping",
    "SMART_MONEY_SQUARE_IDENTITY_CATALOG_SCHEMA",
    "SMART_MONEY_SQUARE_MAPPING_SCHEMA",
    "SMART_MONEY_SQUARE_MAPPING_SCHEMA_V1",
    "duration_tier",
    "assess_leaderboard_coverage",
    "load_seed_profile_evidence",
    "load_smart_money_square_identity_catalog",
    "load_smart_money_square_identity_evidence",
    "parse_30d_leaderboard",
    "parse_30d_leaderboards",
    "parse_author_profile",
    "parse_trading_days",
]
