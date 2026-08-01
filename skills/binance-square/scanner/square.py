"""Parse Binance Square discovery and detail evidence into stable v4 records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any

from .contracts import (
    ContractViolation,
    canonical_post_id,
    canonical_profile_id,
    format_utc,
    load_v3_snapshot,
    parse_utc,
    strict_24h_window,
)
from .discovery import (
    CanonicalPostDiscovery,
    ChannelObservation,
    DeduplicatedDiscovery,
    deduplicate_post_observations,
    observations_from_feed_cards,
    parse_profile_content_response,
)


@dataclass(frozen=True, slots=True)
class FeedCard:
    """One discovery observation; feed text and time are never authoritative."""

    post_id: str
    post_url: str
    profile_url: str
    profile_slug: str
    author_name: str
    visible_labels: tuple[str, ...]
    published_text: str
    published_precision: str
    feed_text_excerpt: str
    published_at: None = None
    text_authority: str = "feed_card_summary"


@dataclass(frozen=True, slots=True)
class PostDetail:
    """An authoritative, versioned Square post observation."""

    post_id: str
    post_url: str
    author_id: str
    username: str
    display_name: str
    profile_url: str
    published_at: str
    published_precision: str
    content: str
    content_hash: str
    text_authority: str
    source_class: str
    observed_at: str
    edit_count: int | None


@dataclass(frozen=True, slots=True)
class StructuredPost:
    """Authoritative JSON-LD evidence before stable author-ID enrichment."""

    post_id: str
    post_url: str
    published_at: str
    content: str
    author_name: str
    profile_url: str
    profile_slug: str
    text_authority: str = "json_ld_text"


@dataclass(frozen=True, slots=True)
class QuarantinedPost:
    post_id: str | None
    post_url: str | None
    reason: str
    detail: str
    published_at: str | None = None
    observed_at: str | None = None
    author_id: str | None = None
    content_hash: str | None = None


@dataclass(frozen=True, slots=True)
class WindowSelection:
    accepted: tuple[PostDetail, ...]
    quarantined: tuple[QuarantinedPost, ...]


@dataclass(frozen=True, slots=True)
class PostParseResult:
    post: PostDetail | None
    quarantine: QuarantinedPost | None


class _StructuredDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_json_ld = False
        self._chunks: list[str] = []
        self.documents: list[Any] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "script":
            return
        attributes = {name.lower(): value for name, value in attrs}
        if (attributes.get("type") or "").lower() == "application/ld+json":
            self._inside_json_ld = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._inside_json_ld:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self._inside_json_ld:
            return
        self._inside_json_ld = False
        try:
            self.documents.append(json.loads("".join(self._chunks)))
        except json.JSONDecodeError:
            pass


def _json_ld_documents(html: str | None) -> list[Any]:
    if not html:
        return []
    parser = _StructuredDataParser()
    parser.feed(html)
    return parser.documents


def _typed_json_ld(html: str | None, schema_type: str) -> dict[str, Any] | None:
    pending = list(_json_ld_documents(html))
    while pending:
        value = pending.pop(0)
        if isinstance(value, list):
            pending.extend(value)
            continue
        if not isinstance(value, dict):
            continue
        if value.get("@type") == schema_type:
            return value
        graph = value.get("@graph")
        if isinstance(graph, list):
            pending.extend(graph)
    return None


def _friendly_data(payload: dict[str, Any]) -> dict[str, Any]:
    value: Any = payload
    if isinstance(value, dict) and isinstance(value.get("response"), dict):
        value = value["response"]
    if not isinstance(value, dict) or value.get("success") is not True:
        raise ContractViolation("friendly content response was not successful")
    data = value.get("data")
    if not isinstance(data, dict):
        raise ContractViolation("friendly content response has no data object")
    return data


def _milliseconds_utc(value: Any, field_name: str) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractViolation(f"{field_name} must be Unix milliseconds")
    seconds, milliseconds = divmod(value, 1000)
    observed = datetime.fromtimestamp(seconds, tz=timezone.utc) + timedelta(
        milliseconds=milliseconds
    )
    return format_utc(observed)


def classify_source(*aliases: str) -> str:
    """Classify only explicit Binance-owned aliases as official."""

    official = {
        "binance announcement",
        "binance news",
        "binance research",
        "binance_news",
        "square official",
    }
    normalized = {alias.strip().casefold() for alias in aliases if alias.strip()}
    return "BINANCE_OFFICIAL" if normalized & official else "SQUARE_UGC"


def parse_post_json_ld(html: str) -> StructuredPost:
    """Parse the authoritative public DiscussionForumPosting document."""

    structured = _typed_json_ld(html, "DiscussionForumPosting")
    if structured is None:
        raise ContractViolation("post page has no DiscussionForumPosting JSON-LD")
    post_url = structured.get("url") or structured.get("mainEntityOfPage")
    published_at = structured.get("datePublished")
    content = structured.get("text")
    author = structured.get("author")
    if not isinstance(post_url, str):
        raise ContractViolation("JSON-LD post has no canonical URL")
    if not isinstance(published_at, str):
        raise ContractViolation("JSON-LD post has no exact datePublished")
    if not isinstance(content, str) or not content.strip():
        raise ContractViolation("JSON-LD post has no text")
    if not isinstance(author, dict):
        raise ContractViolation("JSON-LD post has no author object")
    author_name = author.get("name")
    profile_url = author.get("url")
    if not isinstance(author_name, str) or not author_name.strip():
        raise ContractViolation("JSON-LD post has no author name")
    if author_name.strip().upper() == "LIVE":
        raise ContractViolation("LIVE is a label, not an author")
    if not isinstance(profile_url, str):
        raise ContractViolation("JSON-LD post has no author Profile URL")
    profile_slug = canonical_profile_id(profile_url)
    post_id = canonical_post_id(post_url)
    return StructuredPost(
        post_id=post_id,
        post_url=f"https://www.binance.com/en/square/post/{post_id}",
        published_at=format_utc(published_at),
        content=content.replace("\r\n", "\n").replace("\r", "\n"),
        author_name=author_name.strip(),
        profile_url=profile_url,
        profile_slug=profile_slug,
    )


def parse_post_detail(
    *,
    public_payload: dict[str, Any],
    html: str | None = None,
    observed_at: str | datetime,
) -> PostDetail:
    """Parse one public friendly response, cross-checking JSON-LD when present."""

    data = _friendly_data(public_payload)
    post_id = str(data.get("id") or "")
    post_url = data.get("webLink")
    if not post_id.isdecimal() or not isinstance(post_url, str):
        raise ContractViolation("post detail requires a numeric ID and canonical URL")
    if canonical_post_id(post_url) != post_id:
        raise ContractViolation("post detail ID conflicts with its canonical URL")

    author_id = data.get("squareUid")
    username = data.get("username")
    display_name = data.get("displayName")
    if not isinstance(author_id, str) or not author_id.strip():
        raise ContractViolation("post detail is missing stable squareUid")
    if not isinstance(username, str) or not username.strip():
        raise ContractViolation("post detail is missing username alias")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ContractViolation("post detail is missing display name alias")
    if "LIVE" in {username.strip().upper(), display_name.strip().upper()}:
        raise ContractViolation("LIVE is a label, not an author")

    body = data.get("bodyTextOnly")
    if not isinstance(body, str) or not body.strip():
        raise ContractViolation("post detail is missing authoritative bodyTextOnly")
    published_at = _milliseconds_utc(data.get("firstReleaseTime"), "firstReleaseTime")

    structured = _typed_json_ld(html, "DiscussionForumPosting")
    profile_url = f"https://www.binance.com/en/square/profile/{username.casefold()}"
    if structured is not None:
        structured_url = structured.get("url") or structured.get("mainEntityOfPage")
        if isinstance(structured_url, str) and canonical_post_id(structured_url) != post_id:
            raise ContractViolation("JSON-LD post ID conflicts with public response")
        structured_time = structured.get("datePublished")
        if isinstance(structured_time, str) and parse_utc(structured_time) != parse_utc(
            published_at
        ):
            raise ContractViolation("JSON-LD datePublished conflicts with public response")
        structured_author = structured.get("author")
        if isinstance(structured_author, dict) and isinstance(
            structured_author.get("url"), str
        ):
            canonical_profile_id(structured_author["url"])
            profile_url = structured_author["url"]

    edit_count = data.get("editCount")
    if not isinstance(edit_count, int) or isinstance(edit_count, bool):
        edit_count = None
    canonical_body = body.replace("\r\n", "\n").replace("\r", "\n")
    return PostDetail(
        post_id=post_id,
        post_url=f"https://www.binance.com/en/square/post/{post_id}",
        author_id=author_id.strip(),
        username=username.strip(),
        display_name=display_name.strip(),
        profile_url=profile_url,
        published_at=published_at,
        published_precision="exact_millisecond",
        content=canonical_body,
        content_hash=sha256(canonical_body.encode("utf-8")).hexdigest(),
        text_authority="friendly_body_text_only",
        source_class=classify_source(username, display_name),
        observed_at=format_utc(observed_at),
        edit_count=edit_count,
    )


def try_parse_post_detail(
    *,
    post_url: str,
    public_payload: dict[str, Any],
    observed_at: str | datetime,
    html: str | None = None,
) -> PostParseResult:
    """Turn an invalid source record into an auditable quarantine record."""

    try:
        post_id = canonical_post_id(post_url)
    except ContractViolation as exc:
        return PostParseResult(
            None, QuarantinedPost(None, post_url, "invalid_post_url", str(exc))
        )
    try:
        post = parse_post_detail(
            public_payload=public_payload, html=html, observed_at=observed_at
        )
        if post.post_id != post_id:
            raise ContractViolation("discovery URL conflicts with detail post ID")
        return PostParseResult(post, None)
    except ContractViolation as exc:
        message = str(exc)
        if "squareUid" in message:
            reason = "missing_stable_author_id"
        elif "firstReleaseTime" in message or "datePublished" in message:
            reason = "missing_or_conflicting_exact_published_at"
        elif "bodyTextOnly" in message:
            reason = "missing_authoritative_content"
        elif "LIVE" in message:
            reason = "live_label_as_author"
        elif "ID conflicts" in message or "post ID" in message:
            reason = "post_identity_conflict"
        else:
            reason = "invalid_detail_response"
        return PostParseResult(
            None,
            QuarantinedPost(
                post_id=post_id,
                post_url=f"https://www.binance.com/en/square/post/{post_id}",
                reason=reason,
                detail=message,
            ),
        )


def select_strict_24h(
    posts: tuple[PostDetail, ...] | list[PostDetail],
    *,
    decision_at: str | datetime,
) -> WindowSelection:
    """Accept only exact event times in ``[decision_at - 24h, decision_at)``."""

    window = strict_24h_window(decision_at)
    accepted: list[PostDetail] = []
    quarantined: list[QuarantinedPost] = []
    for post in posts:
        published = parse_utc(post.published_at)
        if window.contains(published):
            accepted.append(post)
            continue
        if published >= window.end:
            reason = "not_before_decision_at"
            detail = "published_at must be earlier than decision_at"
        else:
            reason = "outside_strict_24h"
            detail = "published_at is older than decision_at minus 24 hours"
        quarantined.append(
            QuarantinedPost(
                post_id=post.post_id,
                post_url=post.post_url,
                reason=reason,
                detail=detail,
                published_at=post.published_at,
                observed_at=post.observed_at,
                author_id=post.author_id,
                content_hash=post.content_hash,
            )
        )
    return WindowSelection(tuple(accepted), tuple(quarantined))


def parse_feed_cards(payload: dict[str, Any]) -> tuple[FeedCard, ...]:
    """Return validated feed candidates without inventing precise event time."""

    raw_cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(raw_cards, list):
        raise ContractViolation("feed payload must contain a cards list")

    cards: list[FeedCard] = []
    for raw in raw_cards:
        if not isinstance(raw, dict):
            raise ContractViolation("feed card must be an object")
        post_url = raw.get("post_url")
        profile_url = raw.get("profile_url")
        author_name = raw.get("author_name")
        if not isinstance(post_url, str) or not isinstance(profile_url, str):
            raise ContractViolation("feed card requires post and profile URLs")
        if not isinstance(author_name, str) or not author_name.strip():
            raise ContractViolation("feed card requires an author name")
        if author_name.strip().upper() == "LIVE":
            raise ContractViolation("LIVE is a label, not an author")

        post_id = canonical_post_id(post_url)
        profile_slug = canonical_profile_id(profile_url)
        declared_post_id = str(raw.get("post_id", ""))
        if declared_post_id and declared_post_id != post_id:
            raise ContractViolation("feed post ID conflicts with its canonical URL")

        labels = raw.get("visible_labels") or []
        if not isinstance(labels, list) or not all(
            isinstance(label, str) for label in labels
        ):
            raise ContractViolation("visible_labels must be a list of strings")
        cards.append(
            FeedCard(
                post_id=post_id,
                post_url=f"https://www.binance.com/en/square/post/{post_id}",
                profile_url=profile_url,
                profile_slug=profile_slug,
                author_name=author_name.strip(),
                visible_labels=tuple(label.strip() for label in labels if label.strip()),
                published_text=str(raw.get("published_text") or "").strip(),
                published_precision=str(raw.get("published_precision") or "").strip(),
                feed_text_excerpt=str(raw.get("feed_text_excerpt") or "").strip(),
            )
        )
    return tuple(cards)


def discover_snapshot_post_urls(
    path: str | Path, *, limit: int
) -> tuple[str, ...]:
    """Use canonical URLs in a read-only v3 snapshot as bounded discoveries."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ContractViolation("snapshot discovery limit must be positive")
    snapshot = load_v3_snapshot(path)
    discovered: list[str] = []
    seen: set[str] = set()
    for post in snapshot.posts:
        post_id = canonical_post_id(post.url)
        url = f"https://www.binance.com/en/square/post/{post_id}"
        if url in seen:
            continue
        seen.add(url)
        discovered.append(url)
        if len(discovered) >= limit:
            break
    return tuple(discovered)
