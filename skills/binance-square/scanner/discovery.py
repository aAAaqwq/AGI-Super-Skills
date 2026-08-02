"""Pure source-planning and cross-channel Binance Square discovery contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterable

from .contracts import (
    ContractViolation,
    canonical_post_id,
    canonical_profile_username,
    format_utc,
    parse_utc,
)


PROFILE_FETCH_STATUSES = frozenset(
    {"COMPLETE", "EMPTY", "PARTIAL", "FAILED", "NOT_ATTEMPTED"}
)


@dataclass(frozen=True, slots=True)
class ProfileFetchTarget:
    """One planned public Profile request, keyed only by stable ``squareUid``."""

    author_id: str
    username: str
    profile_url: str


@dataclass(frozen=True, slots=True)
class ProfileFetchPlan:
    """A deterministic Profile-channel plan with explicit availability."""

    targets: tuple[ProfileFetchTarget, ...]
    availability: str
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProfileFetchOutcome:
    """Observed outcome for one planned stable author identity."""

    author_id: str
    status: str
    post_count: int
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in PROFILE_FETCH_STATUSES:
            raise ContractViolation(f"unsupported profile fetch status: {self.status}")
        if (
            not isinstance(self.post_count, int)
            or isinstance(self.post_count, bool)
            or self.post_count < 0
        ):
            raise ContractViolation("profile fetch post_count must be non-negative")
        if self.status == "COMPLETE" and self.post_count == 0:
            raise ContractViolation("COMPLETE profile fetch must contain posts")
        if self.status in {"EMPTY", "FAILED", "NOT_ATTEMPTED"} and self.post_count:
            raise ContractViolation(f"{self.status} profile fetch cannot contain posts")


@dataclass(frozen=True, slots=True)
class ProfileFetchCoverage:
    """Strict reconciliation of a Profile plan and its per-author outcomes."""

    availability: str
    status: str
    reason: str
    planned_count: int
    complete_count: int
    empty_count: int
    partial_count: int
    failed_count: int
    not_attempted_count: int
    source_record_count: int
    outcomes: tuple[ProfileFetchOutcome, ...]


@dataclass(frozen=True, slots=True)
class ChannelObservation:
    """One source record before cross-channel post-ID deduplication."""

    post_id: str
    post_url: str
    channel: str
    author_id: str | None = None
    profile_url: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalPostDiscovery:
    """One canonical candidate retaining every source-channel observation."""

    post_id: str
    post_url: str
    channels: tuple[str, ...]
    observations: tuple[ChannelObservation, ...]


@dataclass(frozen=True, slots=True)
class DeduplicatedDiscovery:
    """Cross-channel discoveries with an auditable source-record equation."""

    posts: tuple[CanonicalPostDiscovery, ...]
    source_record_count: int
    unique_post_count: int
    duplicate_source_records: int


@dataclass(frozen=True, slots=True)
class FeedSnapshotCapture:
    """Validated point-in-time identity for one Feed discovery snapshot."""

    captured_at_utc: str
    record_count: int


def validate_feed_snapshot(
    payload: Any,
    *,
    consumed_at: Any,
    maximum_age: timedelta,
) -> FeedSnapshotCapture:
    """Fail closed when a report would consume stale or future Feed evidence."""

    if not isinstance(payload, dict):
        raise ContractViolation("Feed snapshot must be an object")
    if maximum_age <= timedelta(0):
        raise ContractViolation("Feed snapshot maximum_age must be positive")
    captured_value = payload.get("scanned_at", payload.get("captured_at"))
    if captured_value is None:
        raise ContractViolation("Feed snapshot is missing scanned_at")
    captured = parse_utc(captured_value)
    consumed = parse_utc(consumed_at)
    if captured > consumed:
        raise ContractViolation("Feed snapshot was captured after consumption")
    if consumed - captured > maximum_age:
        raise ContractViolation("Feed snapshot is stale")
    posts = payload.get("posts")
    if not isinstance(posts, list):
        raise ContractViolation("Feed snapshot posts must be a list")
    return FeedSnapshotCapture(
        captured_at_utc=format_utc(captured),
        record_count=len(posts),
    )


def feed_snapshot_post_urls(
    payload: Any,
    *,
    limit: int,
) -> tuple[str, ...]:
    """Return canonical URLs from the exact validated in-memory snapshot."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ContractViolation("Feed snapshot limit must be positive")
    if not isinstance(payload, dict) or not isinstance(payload.get("posts"), list):
        raise ContractViolation("Feed snapshot posts must be a list")
    urls: list[str] = []
    seen: set[str] = set()
    for row in payload["posts"]:
        if not isinstance(row, dict) or not isinstance(row.get("url"), str):
            continue
        try:
            post_id = canonical_post_id(row["url"])
        except ContractViolation:
            continue
        url = f"https://www.binance.com/en/square/post/{post_id}"
        if url not in seen:
            seen.add(url)
            urls.append(url)
        if len(urls) >= limit:
            break
    return tuple(urls)


def _author_field(author: Any, field: str) -> Any:
    if isinstance(author, dict):
        aliases = {
            "author_id": ("author_id", "square_uid", "squareUid"),
            "username": ("username",),
            "profile_url": ("profile_url", "profileUrl"),
        }.get(field, (field,))
        return next(
            (author.get(alias) for alias in aliases if alias in author), None
        )
    return getattr(author, field, None)


def plan_profile_fetches(
    authors: Iterable[Any] | None,
) -> ProfileFetchPlan:
    """Build a public Profile plan without treating route aliases as identities.

    ``None`` means no Profile plan exists.  An explicit empty registry is a
    valid, attempted planning input and is therefore reported as ``EMPTY``.
    """

    if authors is None:
        return ProfileFetchPlan(
            targets=(),
            availability="unavailable",
            status="NOT_ATTEMPTED",
            reason="no_profile_plan",
        )

    targets: list[ProfileFetchTarget] = []
    by_author_id: dict[str, ProfileFetchTarget] = {}
    for index, author in enumerate(authors):
        author_id = _author_field(author, "author_id")
        username = _author_field(author, "username")
        profile_url = _author_field(author, "profile_url")
        if not isinstance(author_id, str) or not author_id.strip():
            raise ContractViolation(
                f"profile plan author[{index}] is missing stable squareUid"
            )
        if not isinstance(username, str) or not username.strip():
            raise ContractViolation(f"profile plan author[{index}] has no username")
        if not isinstance(profile_url, str) or not profile_url.strip():
            raise ContractViolation(f"profile plan author[{index}] has no profile URL")
        stable_id = author_id.strip()
        alias = username.strip()
        route_alias = canonical_profile_username(profile_url)
        if route_alias.casefold() != alias.casefold():
            raise ContractViolation(
                f"profile plan alias conflicts with profile URL: {alias}"
            )
        target = ProfileFetchTarget(stable_id, alias, profile_url.strip())
        existing = by_author_id.get(stable_id)
        if existing is not None:
            if existing != target:
                raise ContractViolation(
                    f"profile plan has conflicting aliases for squareUid: {stable_id}"
                )
            continue
        by_author_id[stable_id] = target
        targets.append(target)

    if not targets:
        return ProfileFetchPlan((), "available", "EMPTY", "profile_registry_empty")
    return ProfileFetchPlan(
        tuple(targets), "available", "NOT_ATTEMPTED", "profile_fetch_not_attempted"
    )


def reconcile_profile_fetch_plan(
    plan: ProfileFetchPlan,
    outcomes: Iterable[ProfileFetchOutcome],
) -> ProfileFetchCoverage:
    """Reconcile exactly one result slot for every planned stable author."""

    supplied: dict[str, ProfileFetchOutcome] = {}
    planned_ids = {target.author_id for target in plan.targets}
    for outcome in outcomes:
        if not isinstance(outcome, ProfileFetchOutcome):
            raise ContractViolation("profile fetch outcomes must be ProfileFetchOutcome")
        if outcome.author_id not in planned_ids:
            raise ContractViolation(
                f"profile fetch outcome is not in the plan: {outcome.author_id}"
            )
        if outcome.author_id in supplied:
            raise ContractViolation(
                f"duplicate profile fetch outcome: {outcome.author_id}"
            )
        supplied[outcome.author_id] = outcome

    reconciled = tuple(
        supplied.get(
            target.author_id,
            ProfileFetchOutcome(target.author_id, "NOT_ATTEMPTED", 0),
        )
        for target in plan.targets
    )
    counts = {
        status: sum(outcome.status == status for outcome in reconciled)
        for status in PROFILE_FETCH_STATUSES
    }
    if plan.availability == "unavailable":
        status, reason = "NOT_ATTEMPTED", "no_profile_plan"
    elif not plan.targets:
        status, reason = "EMPTY", "profile_registry_empty"
    elif counts["NOT_ATTEMPTED"] == len(reconciled):
        status, reason = "NOT_ATTEMPTED", "profile_fetch_not_attempted"
    elif counts["COMPLETE"] == len(reconciled):
        status, reason = "COMPLETE", "all_planned_profiles_returned_posts"
    elif counts["EMPTY"] == len(reconciled):
        status, reason = "EMPTY", "all_planned_profiles_returned_no_posts"
    elif counts["FAILED"] == len(reconciled):
        status, reason = "FAILED", "all_planned_profile_fetches_failed"
    else:
        status, reason = "PARTIAL", "profile_plan_has_mixed_or_missing_outcomes"

    return ProfileFetchCoverage(
        availability=plan.availability,
        status=status,
        reason=reason,
        planned_count=len(plan.targets),
        complete_count=counts["COMPLETE"],
        empty_count=counts["EMPTY"],
        partial_count=counts["PARTIAL"],
        failed_count=counts["FAILED"],
        not_attempted_count=counts["NOT_ATTEMPTED"],
        source_record_count=sum(outcome.post_count for outcome in reconciled),
        outcomes=reconciled,
    )


_PROFILE_CONTENT_LIST_FIELDS = (
    "contents",
    "contentList",
    "items",
    "rows",
    "list",
    "vos",
    "data",
)
_NON_POST_CONTENT_TYPES = {
    "AUDIO",
    "AUDIO_REPLAY",
    "LIVE",
    "LIVE_REPLAY",
    "PODCAST",
    "SPACE",
}
_POST_CONTENT_TYPES = {"ARTICLE", "POST", "PGC", "TEXT", "VIDEO"}


def _profile_content_items(payload: dict[str, Any]) -> list[Any]:
    value: Any = payload
    if isinstance(value, dict) and isinstance(value.get("response"), dict):
        value = value["response"]
    if not isinstance(value, dict) or value.get("success") is not True:
        raise ContractViolation("friendly profile content response was not successful")
    data: Any = value.get("data")
    pending = [data]
    while pending:
        candidate = pending.pop(0)
        if isinstance(candidate, list):
            return candidate
        if not isinstance(candidate, dict):
            continue
        for field in _PROFILE_CONTENT_LIST_FIELDS:
            nested = candidate.get(field)
            if isinstance(nested, list):
                return nested
        pending.extend(
            candidate[field]
            for field in _PROFILE_CONTENT_LIST_FIELDS
            if isinstance(candidate.get(field), dict)
        )
    raise ContractViolation("friendly profile content response has no content list")


def parse_profile_content_response(
    payload: dict[str, Any],
    *,
    author_id: str,
    profile_url: str | None = None,
) -> tuple[ChannelObservation, ...]:
    """Parse public Profile contents into canonical post source records.

    Non-post items are ignored, and any embedded stable author ID must agree
    with the planned ``squareUid``.  No alias is ever substituted for it.
    """

    if not isinstance(author_id, str) or not author_id.strip():
        raise ContractViolation("profile content parsing requires stable squareUid")
    stable_id = author_id.strip()
    if profile_url is not None:
        canonical_profile_username(profile_url)

    observations: list[ChannelObservation] = []
    for index, raw_item in enumerate(_profile_content_items(payload)):
        if not isinstance(raw_item, dict):
            continue
        nested = raw_item.get("content")
        item = nested if isinstance(nested, dict) else raw_item
        content_type = item.get("contentType", item.get("type"))
        if (
            isinstance(content_type, str)
            and content_type.strip().upper() in _NON_POST_CONTENT_TYPES
        ):
            continue
        embedded_author = item.get(
            "squareUid", item.get("authorId", raw_item.get("squareUid"))
        )
        if embedded_author is not None and (
            not isinstance(embedded_author, str)
            or embedded_author.strip() != stable_id
        ):
            raise ContractViolation(
                f"profile content item[{index}] conflicts with planned squareUid"
            )

        raw_url = next(
            (
                item.get(field)
                for field in ("webLink", "postUrl", "url")
                if isinstance(item.get(field), str) and item.get(field).strip()
            ),
            None,
        )
        raw_id = next(
            (
                item.get(field)
                for field in ("id", "postId", "contentId")
                if item.get(field) is not None
            ),
            None,
        )
        declared_id = str(raw_id).strip() if raw_id is not None else ""
        url_id: str | None = None
        if raw_url is not None:
            try:
                url_id = canonical_post_id(raw_url)
            except ContractViolation:
                continue
        if url_id is not None and declared_id and declared_id != url_id:
            raise ContractViolation(
                f"profile content item[{index}] post ID conflicts with URL"
            )
        post_id = url_id or declared_id
        if raw_url is None and (
            not isinstance(content_type, str)
            or content_type.strip().upper() not in _POST_CONTENT_TYPES
        ):
            continue
        if not post_id.isdecimal():
            continue
        canonical_url = f"https://www.binance.com/en/square/post/{post_id}"
        observations.append(
            ChannelObservation(
                post_id=post_id,
                post_url=canonical_url,
                channel="PROFILE",
                author_id=stable_id,
                profile_url=profile_url,
            )
        )
    return tuple(observations)


def observations_from_feed_cards(cards: Iterable[Any]) -> tuple[ChannelObservation, ...]:
    """Convert validated feed cards into source observations."""

    observations: list[ChannelObservation] = []
    for card in cards:
        post_id = getattr(card, "post_id", None)
        post_url = getattr(card, "post_url", None)
        profile_url = getattr(card, "profile_url", None)
        if not isinstance(post_id, str) or not isinstance(post_url, str):
            raise ContractViolation("feed observation requires a post ID and URL")
        canonical_id = canonical_post_id(post_url)
        if canonical_id != post_id:
            raise ContractViolation("feed observation post ID conflicts with URL")
        observations.append(
            ChannelObservation(
                post_id=canonical_id,
                post_url=f"https://www.binance.com/en/square/post/{canonical_id}",
                channel="FEED",
                profile_url=profile_url if isinstance(profile_url, str) else None,
            )
        )
    return tuple(observations)


def deduplicate_post_observations(
    observations: Iterable[ChannelObservation],
) -> DeduplicatedDiscovery:
    """Deduplicate by stable post ID while preserving every source record."""

    grouped: dict[str, list[ChannelObservation]] = {}
    order: list[str] = []
    source_count = 0
    for observation in observations:
        if not isinstance(observation, ChannelObservation):
            raise ContractViolation("discovery records must be ChannelObservation")
        canonical_id = canonical_post_id(observation.post_url)
        if canonical_id != observation.post_id:
            raise ContractViolation("discovery post ID conflicts with canonical URL")
        if observation.channel not in {"FEED", "PROFILE"}:
            raise ContractViolation(
                f"unsupported Square discovery channel: {observation.channel}"
            )
        if canonical_id not in grouped:
            grouped[canonical_id] = []
            order.append(canonical_id)
        grouped[canonical_id].append(observation)
        source_count += 1

    posts: list[CanonicalPostDiscovery] = []
    for post_id in order:
        records = tuple(grouped[post_id])
        stable_authors = {
            record.author_id for record in records if record.author_id is not None
        }
        if len(stable_authors) > 1:
            raise ContractViolation(
                f"post {post_id} was observed with conflicting stable authors"
            )
        posts.append(
            CanonicalPostDiscovery(
                post_id=post_id,
                post_url=f"https://www.binance.com/en/square/post/{post_id}",
                channels=tuple(dict.fromkeys(record.channel for record in records)),
                observations=records,
            )
        )
    unique_count = len(posts)
    return DeduplicatedDiscovery(
        posts=tuple(posts),
        source_record_count=source_count,
        unique_post_count=unique_count,
        duplicate_source_records=source_count - unique_count,
    )


__all__ = [
    "PROFILE_FETCH_STATUSES",
    "CanonicalPostDiscovery",
    "ChannelObservation",
    "DeduplicatedDiscovery",
    "FeedSnapshotCapture",
    "ProfileFetchPlan",
    "ProfileFetchCoverage",
    "ProfileFetchOutcome",
    "ProfileFetchTarget",
    "deduplicate_post_observations",
    "feed_snapshot_post_urls",
    "observations_from_feed_cards",
    "parse_profile_content_response",
    "plan_profile_fetches",
    "reconcile_profile_fetch_plan",
    "validate_feed_snapshot",
]
