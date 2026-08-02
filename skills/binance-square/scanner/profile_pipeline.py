"""Fail-closed Smart Money identity mapping to public Square Profile outcomes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import inspect
import json
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
import urllib.request

from .authors import (
    SmartMoneySquareIdentityEvidence,
    SmartMoneySquareIdentityMapping,
)
from .contracts import ContractViolation, format_utc, parse_utc
from .discovery import ChannelObservation, parse_profile_content_response


PROFILE_PROVENANCE = frozenset({"LIVE_CAPTURE", "FIXTURE_REPLAY"})
PROFILE_CONTENTS_ENDPOINT = (
    "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/"
    "queryUserProfilePageContentsWithFilter"
)
DEFAULT_PROFILE_MAX_PAGES = 20


@dataclass(frozen=True, slots=True)
class ProfilePipelineOutcome:
    top_trader_id: str
    square_uid: str | None
    status: str
    post_count: int
    error: str | None = None
    pages_fetched: int = 0
    termination_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProfilePageCollection:
    status: str
    reason: str
    observations: tuple[ChannelObservation, ...]
    pages_fetched: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ProfilePipelineResult:
    status: str
    reason: str
    provenance: str
    source_capture_time_utc: str | None
    mapping_covered: int
    mapping_expected: int
    tier_a_eligible: int
    mapping_evidence_path: str | None
    mapping_evidence_sha256: str | None
    identity_mappings: tuple[SmartMoneySquareIdentityMapping, ...]
    outcomes: tuple[ProfilePipelineOutcome, ...]
    observations: tuple[ChannelObservation, ...]

    def identity_mapping_records(self) -> tuple[dict[str, str], ...]:
        """Return the exact keyword contract expected by ledger persistence."""

        if self.mapping_evidence_path is None or self.mapping_evidence_sha256 is None:
            return ()
        return tuple(
            {
                "top_trader_id": mapping.top_trader_id,
                "author_id": mapping.square_uid,
                "verified_at": mapping.verified_at,
                "evidence_path": self.mapping_evidence_path,
                "evidence_sha256": self.mapping_evidence_sha256,
            }
            for mapping in self.identity_mappings
        )

    def as_report_contract(self) -> dict[str, Any]:
        counts = {
            status: sum(outcome.status == status for outcome in self.outcomes)
            for status in ("COMPLETE", "EMPTY", "PARTIAL", "FAILED", "NOT_ATTEMPTED")
        }
        return {
            "status": self.status,
            "reason": self.reason,
            "provenance": self.provenance,
            "source_capture_time_utc": self.source_capture_time_utc,
            "evidence_path": self.mapping_evidence_path,
            "square_identity_mapping_coverage": {
                "covered": self.mapping_covered,
                "expected": self.mapping_expected,
                "label": f"{self.mapping_covered}/{self.mapping_expected}",
                "status": (
                    "COMPLETE"
                    if self.mapping_expected and self.mapping_covered == self.mapping_expected
                    else "PARTIAL"
                    if self.mapping_covered
                    else "NOT_ATTEMPTED"
                ),
                "verification_method": "EXPLICIT_SOURCE_EVIDENCE_ONLY",
                "evidence_path": self.mapping_evidence_path,
                "evidence_sha256": self.mapping_evidence_sha256,
            },
            "planned_authors": self.mapping_expected,
            "complete_authors": counts["COMPLETE"],
            "empty_authors": counts["EMPTY"],
            "partial_authors": counts["PARTIAL"],
            "failed_authors": counts["FAILED"],
            "not_attempted_authors": counts["NOT_ATTEMPTED"],
            "source_records": sum(item.post_count for item in self.outcomes),
            "tier_a_eligible": self.tier_a_eligible,
            "outcomes": [asdict(item) for item in self.outcomes],
            "observations": [asdict(item) for item in self.observations],
        }


def _top_trader_ids(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ContractViolation(f"top_trader_ids[{index}] must be non-empty")
        source_id = value.strip()
        if source_id in seen:
            raise ContractViolation(f"duplicate topTraderId: {source_id}")
        seen.add(source_id)
        result.append(source_id)
    return tuple(result)


def public_get_profile_contents(square_uid: str, time_offset: int) -> dict[str, Any]:
    """Fetch one anonymous public Profile page without ambient credentials."""

    if not isinstance(square_uid, str) or not square_uid.strip():
        raise ContractViolation("Profile request requires a stable squareUid")
    if not isinstance(time_offset, int) or isinstance(time_offset, bool):
        raise ContractViolation("Profile timeOffset must be an integer")
    query = urlencode(
        (
            ("targetSquareUid", square_uid.strip()),
            ("timeOffset", str(time_offset)),
            ("filterType", "ALL"),
        )
    )
    request = urllib.request.Request(
        f"{PROFILE_CONTENTS_ENDPOINT}?{query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "binance-square-v4-readonly/1",
        },
    )
    # A fresh default opener has no cookie jar or authentication handler and
    # cannot inherit browser/session credentials from the process.
    opener = urllib.request.build_opener()
    with opener.open(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ContractViolation("Profile response root must be an object")
    return payload


def _supports_offset(fetcher: Callable[..., Any]) -> bool:
    """Keep legacy one-page fixture callbacks compatible during migration."""

    try:
        parameters = tuple(inspect.signature(fetcher).parameters.values())
    except (TypeError, ValueError):
        return True
    return any(parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters) or sum(
        parameter.kind
        in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        for parameter in parameters
    ) >= 2


def _strict_page_data(payload: Any) -> tuple[list[Any], int | None]:
    if not isinstance(payload, dict):
        raise ContractViolation("Profile response root must be an object")
    value: Any = payload.get("response", payload)
    if not isinstance(value, dict) or value.get("success") is not True:
        raise ContractViolation("friendly profile content response was not successful")
    data = value.get("data")
    if not isinstance(data, dict):
        raise ContractViolation("friendly profile content response data is not an object")
    items = next(
        (
            data.get(field)
            for field in ("contents", "contentList", "items", "rows", "list", "vos")
            if isinstance(data.get(field), list)
        ),
        None,
    )
    if items is None:
        raise ContractViolation("friendly profile content response has no content list")
    raw_next = next(
        (
            data[field]
            for field in ("nextTimeOffset", "nextOffset", "timeOffset")
            if field in data
        ),
        None,
    )
    if raw_next is not None and (
        not isinstance(raw_next, int) or isinstance(raw_next, bool)
    ):
        raise ContractViolation("Profile next offset must be an integer or null")
    return items, raw_next


def _tail_first_release_time(items: list[Any]) -> int | None:
    if not items or not isinstance(items[-1], dict):
        return None
    raw_item = items[-1]
    nested = raw_item.get("content")
    item = nested if isinstance(nested, dict) else raw_item
    value = item.get("firstReleaseTime", raw_item.get("firstReleaseTime"))
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    return value


def _paginated_profile(
    *,
    square_uid: str,
    fetcher: Callable[..., dict[str, Any]],
    decision_at: datetime | str,
    max_pages: int,
) -> tuple[tuple[ChannelObservation, ...], str, str | None, int]:
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise ContractViolation("Profile max_pages must be positive")
    end = parse_utc(decision_at)
    start = end - timedelta(hours=24)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    offset = -1
    seen_offsets = {-1}
    by_post_id: dict[str, ChannelObservation] = {}

    for page_number in range(1, max_pages + 1):
        try:
            payload = fetcher(square_uid, offset)
        except Exception as exc:
            return (
                tuple(by_post_id.values()),
                "REQUEST_FAILED",
                f"{type(exc).__name__}: {exc}"[:300],
                page_number - 1,
            )
        try:
            items, next_offset = _strict_page_data(payload)
            if next_offset is not None:
                tail_release_ms = _tail_first_release_time(items)
                if tail_release_ms is None:
                    return (
                        tuple(by_post_id.values()),
                        "CURSOR_WATERMARK_MISSING",
                        None,
                        page_number,
                    )
                if next_offset != tail_release_ms - 1:
                    return (
                        tuple(by_post_id.values()),
                        "CURSOR_ANCHOR_MISMATCH",
                        None,
                        page_number,
                    )
                if next_offset in seen_offsets or next_offset == offset:
                    return tuple(by_post_id.values()), "OFFSET_STAGNANT", None, page_number
                if offset != -1 and next_offset > offset:
                    return tuple(by_post_id.values()), "OFFSET_RISING", None, page_number
            page_observations = parse_profile_content_response(
                payload,
                author_id=square_uid,
            )
            for observation in page_observations:
                released = observation.first_release_time_ms
                if released is None:
                    raise ContractViolation(
                        "Profile post is missing firstReleaseTime"
                    )
                if start_ms <= released < end_ms:
                    existing = by_post_id.get(observation.post_id)
                    if existing is not None and existing != observation:
                        raise ContractViolation(
                            "Profile duplicate post observations conflict"
                        )
                    by_post_id.setdefault(observation.post_id, observation)
        except ContractViolation as exc:
            return tuple(by_post_id.values()), "SCHEMA_DRIFT", str(exc)[:300], page_number

        if not items and next_offset is None:
            return tuple(by_post_id.values()), "EMPTY_PAGE", None, page_number
        if next_offset is None:
            return tuple(by_post_id.values()), "NO_NEXT_OFFSET", None, page_number
        if next_offset < start_ms:
            return tuple(by_post_id.values()), "WINDOW_START_CROSSED", None, page_number
        seen_offsets.add(next_offset)
        offset = next_offset

    return tuple(by_post_id.values()), "MAX_PAGES", None, max_pages


def collect_profile_pages(
    square_uid: str,
    *,
    fetch_profile_contents: Callable[..., dict[str, Any]],
    decision_at: datetime | str,
    max_pages: int = DEFAULT_PROFILE_MAX_PAGES,
) -> ProfilePageCollection:
    """Collect one mapped or seeded public Profile with bounded pagination."""

    observations, reason, error, pages = _paginated_profile(
        square_uid=square_uid,
        fetcher=fetch_profile_contents,
        decision_at=decision_at,
        max_pages=max_pages,
    )
    partial_reasons = {
        "REQUEST_FAILED",
        "SCHEMA_DRIFT",
        "OFFSET_STAGNANT",
        "OFFSET_RISING",
        "CURSOR_ANCHOR_MISMATCH",
        "CURSOR_WATERMARK_MISSING",
        "MAX_PAGES",
    }
    return ProfilePageCollection(
        status=(
            "PARTIAL"
            if reason in partial_reasons
            else "COMPLETE"
            if observations
            else "EMPTY"
        ),
        reason=reason,
        observations=observations,
        pages_fetched=pages,
        error=error,
    )


def run_profile_pipeline(
    top_trader_ids: Iterable[str],
    *,
    mapping_evidence: SmartMoneySquareIdentityEvidence | None,
    fetch_profile_contents: Callable[..., dict[str, Any]] | None,
    source_capture_time_utc: str | None,
    provenance: str,
    decision_at: datetime | str | None = None,
    max_pages: int = DEFAULT_PROFILE_MAX_PAGES,
) -> ProfilePipelineResult:
    """Return a reconciled result slot for every Smart Money identity.

    The fetch callback receives only an explicitly mapped ``squareUid``.  When
    mapping evidence is absent, the callback is never invoked.
    """

    source_ids = _top_trader_ids(top_trader_ids)
    normalized_provenance = str(provenance).upper()
    if normalized_provenance not in PROFILE_PROVENANCE:
        raise ContractViolation(
            "Profile provenance must be LIVE_CAPTURE or FIXTURE_REPLAY"
        )
    if mapping_evidence is None:
        return ProfilePipelineResult(
            status="NOT_ATTEMPTED",
            reason="BLOCKED_IDENTITY_MAPPING",
            provenance=normalized_provenance,
            source_capture_time_utc=None,
            mapping_covered=0,
            mapping_expected=len(source_ids),
            tier_a_eligible=0,
            mapping_evidence_path=None,
            mapping_evidence_sha256=None,
            identity_mappings=(),
            outcomes=tuple(
                ProfilePipelineOutcome(source_id, None, "NOT_ATTEMPTED", 0)
                for source_id in source_ids
            ),
            observations=(),
        )

    mapping_by_trader = {
        top_trader_id: square_uid
        for top_trader_id in source_ids
        if (square_uid := mapping_evidence.square_uid_for(top_trader_id)) is not None
    }
    accepted_mappings = tuple(
        mapping
        for mapping in mapping_evidence.mappings
        if mapping_by_trader.get(mapping.top_trader_id) == mapping.square_uid
    )
    mapping_covered = len(mapping_by_trader)
    if fetch_profile_contents is not None and mapping_covered:
        if source_capture_time_utc is None:
            raise ContractViolation(
                "Profile collection requires an explicit source_capture_time_utc"
            )
        try:
            captured_at = format_utc(source_capture_time_utc)
        except ContractViolation as exc:
            raise ContractViolation(
                "Profile source_capture_time_utc must be timezone-aware"
            ) from exc
    else:
        captured_at = None

    outcomes: list[ProfilePipelineOutcome] = []
    observations: list[ChannelObservation] = []
    for top_trader_id in source_ids:
        square_uid = mapping_by_trader.get(top_trader_id)
        if square_uid is None:
            outcomes.append(
                ProfilePipelineOutcome(
                    top_trader_id,
                    None,
                    "NOT_ATTEMPTED",
                    0,
                    "no_explicit_identity_mapping",
                )
            )
            continue
        if fetch_profile_contents is None:
            outcomes.append(
                ProfilePipelineOutcome(
                    top_trader_id,
                    square_uid,
                    "NOT_ATTEMPTED",
                    0,
                    "profile_fetcher_not_supplied",
                )
            )
            continue
        try:
            if decision_at is not None and _supports_offset(fetch_profile_contents):
                collection = collect_profile_pages(
                    square_uid,
                    fetch_profile_contents=fetch_profile_contents,
                    decision_at=decision_at,
                    max_pages=max_pages,
                )
                observations.extend(collection.observations)
                outcomes.append(
                    ProfilePipelineOutcome(
                        top_trader_id,
                        square_uid,
                        collection.status,
                        len(collection.observations),
                        collection.error,
                        collection.pages_fetched,
                        collection.reason,
                    )
                )
                continue
            payload = fetch_profile_contents(square_uid)
            if not isinstance(payload, dict):
                raise ContractViolation("Profile response root must be an object")
            profile_observations = parse_profile_content_response(payload, author_id=square_uid)
        except Exception as exc:
            outcomes.append(
                ProfilePipelineOutcome(
                    top_trader_id,
                    square_uid,
                    "FAILED",
                    0,
                    f"{type(exc).__name__}: {exc}"[:300],
                    0,
                    "REQUEST_FAILED",
                )
            )
            continue
        observations.extend(profile_observations)
        outcomes.append(
            ProfilePipelineOutcome(
                top_trader_id,
                square_uid,
                "COMPLETE" if profile_observations else "EMPTY",
                len(profile_observations),
                None,
                1,
                "LEGACY_SINGLE_PAGE",
            )
        )

    successful = {"COMPLETE", "EMPTY"}
    if not mapping_covered or fetch_profile_contents is None:
        status = "NOT_ATTEMPTED"
        reason = (
            "BLOCKED_IDENTITY_MAPPING"
            if not mapping_covered
            else "profile_fetcher_not_supplied"
        )
    elif mapping_covered == len(source_ids) and all(
        outcome.status in successful for outcome in outcomes
    ):
        status = "COMPLETE"
        reason = "all_explicitly_mapped_profiles_reconciled"
    elif mapping_covered == len(source_ids) and all(
        outcome.status == "FAILED" for outcome in outcomes
    ):
        status = "FAILED"
        reason = "all_explicitly_mapped_profile_fetches_failed"
    else:
        status = "PARTIAL"
        reason = "identity_mapping_or_profile_outcomes_are_partial"
    return ProfilePipelineResult(
        status=status,
        reason=reason,
        provenance=normalized_provenance,
        source_capture_time_utc=captured_at,
        mapping_covered=mapping_covered,
        mapping_expected=len(source_ids),
        tier_a_eligible=0,
        mapping_evidence_path=mapping_evidence.evidence_path,
        mapping_evidence_sha256=mapping_evidence.evidence_sha256,
        identity_mappings=accepted_mappings,
        outcomes=tuple(outcomes),
        observations=tuple(observations),
    )


__all__ = [
    "DEFAULT_PROFILE_MAX_PAGES",
    "PROFILE_CONTENTS_ENDPOINT",
    "PROFILE_PROVENANCE",
    "ProfilePipelineOutcome",
    "ProfilePageCollection",
    "ProfilePipelineResult",
    "collect_profile_pages",
    "public_get_profile_contents",
    "run_profile_pipeline",
]
