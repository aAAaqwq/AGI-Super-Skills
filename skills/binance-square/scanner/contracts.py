"""Versioned, dependency-free contracts shared by scanner components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = "4.1.0"
_PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class ContractViolation(ValueError):
    """Raised when external data cannot satisfy a stable v4 contract."""


class RunNamespace(str, Enum):
    """Production slots and offline replays never share an identity space."""

    PRODUCTION = "PRODUCTION"
    REPLAY = "REPLAY"


class DedupStatus(str, Enum):
    """Whether cross-run new/duplicate counts have an explicit baseline."""

    COMPUTED = "COMPUTED"
    NOT_COMPUTED = "NOT_COMPUTED"


class AttemptStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def parse_utc(value: datetime | str) -> datetime:
    """Parse an aware ISO-8601 value and normalize it to UTC."""

    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ContractViolation(f"invalid ISO-8601 timestamp: {value!r}") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ContractViolation("timestamp must be an ISO-8601 string or datetime")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractViolation("timestamp must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def format_utc(value: datetime | str) -> str:
    """Return one canonical ISO-8601 representation for persisted identities."""

    parsed = parse_utc(value)
    timespec = "microseconds" if parsed.microsecond else "seconds"
    return parsed.isoformat(timespec=timespec).replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A left-closed, right-open UTC event-time window."""

    start: datetime
    end: datetime

    def contains(self, published_at: datetime | str) -> bool:
        observed = parse_utc(published_at)
        return self.start <= observed < self.end


def strict_24h_window(decision_at: datetime | str) -> TimeWindow:
    """Return ``[decision_at - 24h, decision_at)`` in UTC."""

    end = parse_utc(decision_at)
    return TimeWindow(start=end - timedelta(hours=24), end=end)


def serialize_decimal(value: Decimal) -> str:
    """Serialize an audit amount without passing through binary float."""

    if not isinstance(value, Decimal) or not value.is_finite():
        raise ContractViolation("audit amounts must be finite Decimal values")
    return format(value, "f")


def deserialize_decimal(value: str) -> Decimal:
    """Restore an audit amount from its exact string representation."""

    if not isinstance(value, str):
        raise ContractViolation("stored audit amounts must be strings")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ContractViolation(f"invalid stored Decimal: {value!r}") from exc
    if not amount.is_finite():
        raise ContractViolation("stored audit amounts must be finite")
    return amount


def _binance_path_parts(url: str) -> list[str]:
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        host == "binance.com" or host.endswith(".binance.com")
    ):
        raise ContractViolation("identity must come from a Binance URL")
    return [part for part in parsed.path.split("/") if part]


def canonical_post_id(url: str) -> str:
    """Extract the stable numeric ID from a canonical Square post URL."""

    parts = _binance_path_parts(url)
    for index in range(len(parts) - 2):
        if parts[index : index + 2] == ["square", "post"]:
            post_id = parts[index + 2]
            if post_id.isdecimal():
                return post_id
    raise ContractViolation("URL does not contain a stable Square post ID")


def canonical_profile_username(url: str) -> str:
    """Extract the profile-route username alias from a Binance URL.

    The route segment is not the stable Square author identity.  Stable
    author identity must come from the profile payload's opaque ``squareUid``.
    """

    parts = _binance_path_parts(url)
    for index in range(len(parts) - 2):
        if parts[index : index + 2] == ["square", "profile"]:
            profile_id = parts[index + 2]
            if _PROFILE_ID.fullmatch(profile_id) and profile_id.upper() != "LIVE":
                return profile_id
    raise ContractViolation("URL does not contain a stable Square profile ID")


def canonical_profile_id(url: str) -> str:
    """Backward-compatible alias for :func:`canonical_profile_username`.

    Older callers used the misleading ``profile_id`` name.  Keep the API
    stable while making the route-alias semantics explicit for new code.
    """

    return canonical_profile_username(url)


@dataclass(frozen=True, slots=True)
class ContractMetadata:
    """Audit metadata required on persisted v4 contracts."""

    source_system: str
    created_at: datetime
    updated_at: datetime
    schema_version: str = field(default=SCHEMA_VERSION, init=False)


def _non_negative_integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractViolation(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class PostCountContract:
    """Reconciled report counts with an explicit cross-run dedup state."""

    discovered: int
    total: int
    accepted: int
    quarantine: int
    dq_quarantine: int
    window_excluded: int
    unique_accepted: int
    new: int | None
    duplicate: int | None
    dedup_status: DedupStatus

    def __post_init__(self) -> None:
        if not isinstance(self.dedup_status, DedupStatus):
            raise ContractViolation("dedup_status must use DedupStatus")
        for field_name in (
            "discovered",
            "total",
            "accepted",
            "quarantine",
            "dq_quarantine",
            "window_excluded",
            "unique_accepted",
        ):
            _non_negative_integer(getattr(self, field_name), field_name)
        if self.discovered != self.accepted + self.quarantine:
            raise ContractViolation("discovered must equal accepted + quarantine")
        if self.total != self.accepted:
            raise ContractViolation("total must equal accepted")
        if self.quarantine != self.dq_quarantine + self.window_excluded:
            raise ContractViolation(
                "quarantine must equal dq_quarantine + window_excluded"
            )
        if self.unique_accepted > self.accepted:
            raise ContractViolation("unique_accepted cannot exceed accepted")
        if self.dedup_status is DedupStatus.NOT_COMPUTED:
            if self.new is not None or self.duplicate is not None:
                raise ContractViolation(
                    "NOT_COMPUTED dedup counts must both be null"
                )
            return
        if self.new is None or self.duplicate is None:
            raise ContractViolation("COMPUTED dedup counts must both be present")
        _non_negative_integer(self.new, "new")
        _non_negative_integer(self.duplicate, "duplicate")
        if self.new + self.duplicate != self.unique_accepted:
            raise ContractViolation(
                "new + duplicate must equal unique_accepted"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "discovered": self.discovered,
            "total": self.total,
            "accepted": self.accepted,
            "quarantine": self.quarantine,
            "dq_quarantine": self.dq_quarantine,
            "window_excluded": self.window_excluded,
            "unique_accepted": self.unique_accepted,
            "new": self.new,
            "duplicate": self.duplicate,
            "dedup_status": self.dedup_status.value,
        }


@dataclass(frozen=True, slots=True)
class AcceptedPostObservation:
    """One accepted source observation pending its attempt's commit outcome."""

    post_id: str
    canonical_post_url: str
    author_id: str
    published_at: datetime
    observed_at: datetime
    content_hash: str
    source_channel: str
    source_record_ordinal: int

    def __post_init__(self) -> None:
        if not isinstance(self.post_id, str) or not self.post_id.isdecimal():
            raise ContractViolation("post_id must be a numeric stable ID")
        if canonical_post_id(self.canonical_post_url) != self.post_id:
            raise ContractViolation("canonical_post_url does not match post_id")
        if (
            not isinstance(self.author_id, str)
            or not self.author_id.strip()
            or self.author_id.strip().upper() == "LIVE"
        ):
            raise ContractViolation("author_id must be a stable non-LIVE ID")
        parse_utc(self.published_at)
        parse_utc(self.observed_at)
        digest = self.content_hash
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ContractViolation("content_hash must be lowercase SHA-256")
        if not isinstance(self.source_channel, str) or not self.source_channel.strip():
            raise ContractViolation("source_channel must be non-empty")
        _non_negative_integer(self.source_record_ordinal, "source_record_ordinal")


@dataclass(frozen=True, slots=True)
class V3Post:
    """Read-only compatibility view of one v3 feed post."""

    url: str
    text: str
    time_text: str
    author: str
    is_new: bool


@dataclass(frozen=True, slots=True)
class V3Snapshot:
    """Validated compatibility view that never rewrites a v3 snapshot."""

    scanned_at: datetime
    posts: tuple[V3Post, ...]
    new_posts: tuple[V3Post, ...]
    source_system: str = "binance_square_v3"
    schema_version: str = "3.1-compat"

    @property
    def count(self) -> int:
        return len(self.posts)


def _v3_post(value: Any) -> V3Post:
    if not isinstance(value, dict) or not isinstance(value.get("url"), str):
        raise ContractViolation("v3 post must be an object with a URL")
    return V3Post(
        url=value["url"],
        text=value.get("text") if isinstance(value.get("text"), str) else "",
        time_text=value.get("time") if isinstance(value.get("time"), str) else "",
        author=value.get("author") if isinstance(value.get("author"), str) else "",
        is_new=value.get("is_new") is True,
    )


def load_v3_snapshot(path: str | Path) -> V3Snapshot:
    """Read and validate a v3 JSON snapshot without modifying the source file."""

    snapshot_path = Path(path)
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"cannot read v3 snapshot: {snapshot_path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("posts"), list):
        raise ContractViolation("v3 snapshot must contain a posts list")
    posts = tuple(_v3_post(item) for item in payload["posts"])
    declared_count = payload.get("count")
    if not isinstance(declared_count, int) or declared_count != len(posts):
        raise ContractViolation("v3 snapshot count does not match posts")
    raw_new_posts = payload.get("new_posts", [])
    if not isinstance(raw_new_posts, list):
        raise ContractViolation("v3 snapshot new_posts must be a list")
    return V3Snapshot(
        scanned_at=parse_utc(payload.get("scanned_at")),
        posts=posts,
        new_posts=tuple(_v3_post(item) for item in raw_new_posts),
    )
