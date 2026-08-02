#!/usr/bin/env python3
"""Collect stable Binance Square post/author evidence using read-only sources."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.request

import websockets


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.authors import parse_author_profile
from scanner.contracts import SCHEMA_VERSION, canonical_post_id, format_utc, parse_utc
from scanner.discovery import (
    ChannelObservation,
    DeduplicatedDiscovery,
    observations_from_feed_cards,
    parse_profile_content_response,
    profile_first_detail_queue,
)
from scanner.square import (
    FeedCard,
    PostDetail,
    QuarantinedPost,
    discover_snapshot_post_urls,
    parse_feed_cards,
    select_strict_24h,
    try_parse_post_detail,
)


CDP_BASE = "http://127.0.0.1:9222"
PUBLIC_DETAIL = "https://www.binance.com/bapi/composite/v4/friendly/pgc/content/{post_id}"


def _profile_detail_conflict(
    post: PostDetail,
    expectation: Any,
) -> QuarantinedPost | None:
    if expectation is None:
        return None
    expected_author = (
        expectation.get("author_id")
        if isinstance(expectation, dict)
        else getattr(expectation, "author_id", None)
    )
    expected_release = (
        expectation.get("first_release_time_ms")
        if isinstance(expectation, dict)
        else getattr(expectation, "first_release_time_ms", None)
    )
    reason = None
    detail = None
    if expected_author is not None and post.author_id != expected_author:
        reason = "profile_detail_author_conflict"
        detail = "detail squareUid conflicts with mapped Profile observation"
    elif expected_release is not None and int(
        parse_utc(post.published_at).timestamp() * 1000
    ) != expected_release:
        reason = "profile_detail_time_conflict"
        detail = "detail firstReleaseTime conflicts with Profile observation"
    if reason is None or detail is None:
        return None
    return QuarantinedPost(
        post_id=post.post_id,
        post_url=post.post_url,
        reason=reason,
        detail=detail,
        published_at=post.published_at,
        observed_at=post.observed_at,
        author_id=post.author_id,
        content_hash=post.content_hash,
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _fixture_public_posts(directory: Path) -> list[tuple[str, dict[str, Any], str | None, str]]:
    observations: list[tuple[str, dict[str, Any], str | None, str]] = []
    for path in sorted(directory.glob("*post*_public.json")):
        payload = _load_json(path)
        response = payload.get("response")
        data = response.get("data") if isinstance(response, dict) else None
        post_url = data.get("webLink") if isinstance(data, dict) else None
        if not isinstance(post_url, str):
            continue
        html_path = path.with_name(path.name.replace("_public.json", "_live.html"))
        html = html_path.read_text(encoding="utf-8") if html_path.exists() else None
        observed_at = str(payload.get("captured_at_utc") or "")
        observations.append((post_url, payload, html, observed_at))
    return observations


def _collect_fixture(
    directory: Path,
    *,
    limit: int,
    decision_at: str,
    profile_observations: tuple[ChannelObservation, ...] = (),
) -> dict[str, Any]:
    feed_path = directory / "feed_cards_live.json"
    feed_cards: tuple[FeedCard, ...] = ()
    if feed_path.exists():
        feed_cards = parse_feed_cards(_load_json(feed_path))

    collected_profile_observations = list(profile_observations)
    for path in sorted(directory.glob("*profile_contents*_public.json")):
        profile_contents = _load_json(path)
        author_id = profile_contents.get("planned_author_id")
        if not isinstance(author_id, str) or not author_id.strip():
            raise ValueError(f"profile contents fixture has no planned_author_id: {path}")
        collected_profile_observations.extend(
            parse_profile_content_response(profile_contents, author_id=author_id)
        )
    merged = profile_first_detail_queue(
        collected_profile_observations,
        observations_from_feed_cards(feed_cards),
        feed_limit=limit,
    )

    details = _fixture_public_posts(directory)
    detail_by_post_id = {
        canonical_post_id(post_url): (post_url, payload, html, observed_at)
        for post_url, payload, html, observed_at in details
    }
    selected_posts = list(merged.posts)
    selected_source_observations = [
        observation
        for post in selected_posts
        for observation in post.observations
    ]
    discovery = [post.post_url for post in selected_posts]
    discovered_source_records = sum(
        len(post.observations) for post in selected_posts
    )
    duplicate_source_records = discovered_source_records - len(discovery)
    discovered_ids = {canonical_post_id(url) for url in discovery}
    profile_expectations = {
        post.post_id: next(
            (
                observation
                for observation in post.observations
                if observation.channel == "PROFILE"
            ),
            None,
        )
        for post in selected_posts
    }
    for post_url, _, _, _ in details:
        if len(discovery) >= limit:
            break
        if canonical_post_id(post_url) in discovered_ids:
            continue
        discovery.append(post_url)
        discovered_ids.add(canonical_post_id(post_url))
        discovered_source_records += 1
        selected_source_observations.append(
            ChannelObservation(
                post_id=canonical_post_id(post_url),
                post_url=post_url,
                channel="FIXTURE_DETAIL",
            )
        )

    parsed: list[PostDetail] = []
    quarantined: list[QuarantinedPost] = []
    for post_url in discovery:
        post_id = canonical_post_id(post_url)
        evidence = detail_by_post_id.get(post_id)
        if evidence is None:
            quarantined.append(
                QuarantinedPost(
                    post_id=post_id,
                    post_url=post_url,
                    reason="detail_not_available_in_fixture",
                    detail=(
                        "feed discovery has only summary/approximate time; "
                        "authoritative detail is required"
                    ),
                )
            )
            continue
        _, public_payload, html, observed_at = evidence
        result = try_parse_post_detail(
            post_url=post_url,
            public_payload=public_payload,
            html=html,
            observed_at=observed_at or decision_at,
        )
        if result.post is not None:
            conflict = _profile_detail_conflict(
                result.post,
                profile_expectations.get(result.post.post_id),
            )
            if conflict is not None:
                quarantined.append(conflict)
            else:
                parsed.append(result.post)
        elif result.quarantine is not None:
            quarantined.append(result.quarantine)

    selected = select_strict_24h(parsed, decision_at=decision_at)
    quarantined.extend(selected.quarantined)

    authors: list[dict[str, Any]] = []
    profile_path = directory / "profile_public.json"
    if profile_path.exists():
        profile_payload = _load_json(profile_path)
        profile_html_path = directory / "profile_live.html"
        profile_html = (
            profile_html_path.read_text(encoding="utf-8")
            if profile_html_path.exists()
            else None
        )
        author = parse_author_profile(
            public_payload=profile_payload,
            html=profile_html,
            observed_at=str(profile_payload.get("captured_at_utc") or decision_at),
        )
        authors.append(asdict(author))

    return _output_payload(
        source_mode="fixture",
        decision_at=decision_at,
        discovered=discovered_source_records,
        unique_discovered=len(discovery),
        duplicate_source_records=duplicate_source_records,
        discovery_observations=[
            {
                "post_id": observation.post_id,
                "canonical_post_url": observation.post_url,
                "source_channel": observation.channel,
                "source_record_ordinal": ordinal,
                "expected_author_id": observation.author_id,
                "expected_first_release_time_ms": observation.first_release_time_ms,
                "source_profile_url": observation.profile_url,
            }
            for ordinal, observation in enumerate(selected_source_observations)
        ],
        accepted=list(selected.accepted),
        quarantined=quarantined,
        authors=authors,
    )


def _public_get_detail(post_url: str) -> dict[str, Any]:
    endpoint = PUBLIC_DETAIL.format(post_id=canonical_post_id(post_url))
    request = urllib.request.Request(
        endpoint,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "binance-square-v4-readonly/1"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("public detail response root is not an object")
    return payload


def _collect_live_urls(
    urls: tuple[str, ...] | list[str] | DeduplicatedDiscovery,
    *,
    decision_at: str,
    source_mode: str,
    fetch_detail: Any,
    profile_expectations: dict[str, Any] | None = None,
    direct_source_channel: str = "DIRECT",
) -> dict[str, Any]:
    collection_started_at = format_utc(datetime.now(timezone.utc))
    parsed: list[PostDetail] = []
    quarantined: list[QuarantinedPost] = []
    if isinstance(urls, DeduplicatedDiscovery):
        unique_urls = [post.post_url for post in urls.posts]
        discovered_source_records = urls.source_record_count
        duplicate_source_records = urls.duplicate_source_records
        discovery_observations = [
            {
                "post_id": observation.post_id,
                "canonical_post_url": post.post_url,
                "source_channel": observation.channel,
                "source_record_ordinal": ordinal,
                "expected_author_id": observation.author_id,
                "expected_first_release_time_ms": observation.first_release_time_ms,
                "source_profile_url": observation.profile_url,
            }
            for ordinal, (post, observation) in enumerate(
                (post, observation)
                for post in urls.posts
                for observation in post.observations
            )
        ]
        discovered_profile_expectations = {
            post.post_id: next(
                (
                    observation
                    for observation in post.observations
                    if observation.channel == "PROFILE"
                ),
                None,
            )
            for post in urls.posts
        }
    else:
        source_urls = list(urls)
        unique_urls = []
        seen_ids: set[str] = set()
        discovery_observations = []
        for ordinal, value in enumerate(source_urls):
            post_id = canonical_post_id(value)
            post_url = f"https://www.binance.com/en/square/post/{post_id}"
            discovery_observations.append(
                {
                    "post_id": post_id,
                    "canonical_post_url": post_url,
                    "source_channel": direct_source_channel,
                    "source_record_ordinal": ordinal,
                    "expected_author_id": None,
                    "expected_first_release_time_ms": None,
                    "source_profile_url": None,
                }
            )
            if post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_urls.append(post_url)
        discovered_source_records = len(source_urls)
        duplicate_source_records = len(source_urls) - len(unique_urls)
        discovered_profile_expectations = {}
    normalized_profile_expectations = {
        **discovered_profile_expectations,
        **{
            str(post_id): value
            for post_id, value in (profile_expectations or {}).items()
        },
    }
    for index, post_url in enumerate(unique_urls):
        try:
            public_payload = fetch_detail(post_url)
        except Exception as exc:
            quarantined.append(
                QuarantinedPost(
                    post_id=canonical_post_id(post_url),
                    post_url=post_url,
                    reason="detail_fetch_failed",
                    detail=str(exc)[:300],
                )
            )
            continue
        observed_at = format_utc(datetime.now(timezone.utc))
        result = try_parse_post_detail(
            post_url=post_url,
            public_payload=public_payload,
            observed_at=observed_at,
        )
        if result.post is not None:
            expectation = normalized_profile_expectations.get(result.post.post_id)
            conflict = _profile_detail_conflict(result.post, expectation)
            if conflict is not None:
                quarantined.append(conflict)
            else:
                parsed.append(result.post)
        elif result.quarantine is not None:
            quarantined.append(result.quarantine)
        if index + 1 < len(unique_urls):
            time.sleep(0.2)
    selected = select_strict_24h(parsed, decision_at=decision_at)
    quarantined.extend(selected.quarantined)
    collection_completed_at = format_utc(datetime.now(timezone.utc))
    return _output_payload(
        source_mode=source_mode,
        decision_at=decision_at,
        discovered=discovered_source_records,
        unique_discovered=len(unique_urls),
        duplicate_source_records=duplicate_source_records,
        discovery_observations=discovery_observations,
        accepted=list(selected.accepted),
        quarantined=quarantined,
        collection_started_at=collection_started_at,
        collection_completed_at=collection_completed_at,
    )


async def _cdp_command(websocket: Any, message_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    await websocket.send(json.dumps({"id": message_id, "method": method, "params": params}))
    while True:
        message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=20))
        if message.get("id") == message_id:
            if "error" in message:
                raise RuntimeError(f"CDP {method}: {message['error']}")
            return message.get("result", {})


async def _cdp_evaluate(websocket: Any, message_id: int, expression: str) -> Any:
    result = await _cdp_command(
        websocket,
        message_id,
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
    )
    remote = result.get("result", {})
    if "exceptionDetails" in result:
        raise RuntimeError(str(result["exceptionDetails"])[:300])
    return remote.get("value")


async def _collect_cdp(
    *, decision_at: str, limit: int, snapshot: Path | None
) -> dict[str, Any]:
    with urllib.request.urlopen(f"{CDP_BASE}/json", timeout=5) as response:
        targets = json.loads(response.read().decode("utf-8"))
    target = next(
        (
            item
            for item in targets
            if "binance.com" in str(item.get("url", ""))
            and item.get("webSocketDebuggerUrl")
        ),
        None,
    )
    if target is None:
        raise RuntimeError("no open Binance Chrome tab available for read-only CDP")
    async with websockets.connect(
        target["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024, open_timeout=10
    ) as websocket:
        message_id = 1
        if snapshot is not None:
            urls = list(discover_snapshot_post_urls(snapshot, limit=limit))
        else:
            expression = r"""
(() => Array.from(new Set(Array.from(document.querySelectorAll('a[href*="/square/post/"]'))
  .map(a => { try { const u = new URL(a.href, location.href); const m = u.pathname.match(/\/square\/post\/(\d+)\/?$/); return m ? `https://www.binance.com/en/square/post/${m[1]}` : ''; } catch (_) { return ''; } })
  .filter(Boolean))))()
"""
            urls = list(await _cdp_evaluate(websocket, message_id, expression) or [])[:limit]
            message_id += 1

        payloads: dict[str, dict[str, Any] | Exception] = {}
        for post_url in urls:
            endpoint = PUBLIC_DETAIL.format(post_id=canonical_post_id(post_url))
            expression = (
                "(async()=>{const r=await fetch("
                + json.dumps(endpoint)
                + ",{method:'GET',credentials:'omit',cache:'no-store'});"
                "if(!r.ok)throw new Error(`HTTP ${r.status}`);return await r.json();})()"
            )
            try:
                value = await _cdp_evaluate(websocket, message_id, expression)
                payloads[post_url] = value if isinstance(value, dict) else ValueError(
                    "CDP public detail response root is not an object"
                )
            except Exception as exc:
                payloads[post_url] = exc
            message_id += 1

    def fetch(post_url: str) -> dict[str, Any]:
        value = payloads[post_url]
        if isinstance(value, Exception):
            raise value
        return value

    return _collect_live_urls(
        urls,
        decision_at=decision_at,
        source_mode="live_cdp_snapshot" if snapshot else "live_cdp_feed",
        fetch_detail=fetch,
        direct_source_channel="FEED",
    )


def _output_payload(
    *,
    source_mode: str,
    decision_at: str,
    discovered: int,
    unique_discovered: int | None = None,
    duplicate_source_records: int = 0,
    discovery_observations: list[dict[str, Any]],
    accepted: list[PostDetail],
    quarantined: list[QuarantinedPost],
    authors: list[dict[str, Any]] | None = None,
    collection_started_at: str | None = None,
    collection_completed_at: str | None = None,
) -> dict[str, Any]:
    accepted_payload = [asdict(post) for post in accepted]
    quarantine_payload = [asdict(item) for item in quarantined]
    # Only authoritative old records are ordinary window exclusions. A post
    # at or after the frozen decision boundary is a data-quality violation,
    # because it cannot belong to the point-in-time evidence set.
    window_reasons = {"outside_strict_24h"}
    window_excluded = sum(
        item.reason in window_reasons for item in quarantined
    )
    dq_quarantined = len(quarantined) - window_excluded
    if authors is None:
        author_by_id: dict[str, dict[str, Any]] = {}
        for post in accepted:
            author_by_id.setdefault(
                post.author_id,
                {
                    "author_id": post.author_id,
                    "username": post.username,
                    "display_name": post.display_name,
                    "profile_url": post.profile_url,
                    "source_class": post.source_class,
                    "observed_at": post.observed_at,
                },
            )
        author_payload = [author_by_id[key] for key in sorted(author_by_id)]
    else:
        author_payload = authors
    deduplicated_candidates = (
        discovered if unique_discovered is None else unique_discovered
    )
    if discovered != deduplicated_candidates + duplicate_source_records:
        raise ValueError("source discovery records do not reconcile after deduplication")
    if len(discovery_observations) != discovered:
        raise ValueError(
            "discovery observations do not match discovered source records"
        )
    ordinals = [
        observation.get("source_record_ordinal")
        for observation in discovery_observations
    ]
    if ordinals != list(range(discovered)):
        raise ValueError("discovery observation ordinals must be contiguous")
    observed_post_ids = {
        observation.get("post_id") for observation in discovery_observations
    }
    if len(observed_post_ids) != deduplicated_candidates:
        raise ValueError(
            "discovery observations do not reconcile to canonical candidates"
        )
    if deduplicated_candidates != len(accepted_payload) + len(quarantine_payload):
        raise ValueError("deduplicated candidates do not reconcile to terminal outcomes")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_system": "binance_square_v4",
        "source_mode": source_mode,
        "decision_at_utc": format_utc(decision_at),
        "window_start_utc": format_utc(parse_utc(decision_at) - timedelta(hours=24)),
        "counts": {
            "discovered_source_records": discovered,
            "deduplicated_post_candidates": deduplicated_candidates,
            "duplicate_source_records": duplicate_source_records,
            "accepted_observations": len(accepted_payload),
            "quarantined_source_records": len(quarantine_payload),
            "dq_quarantined_source_records": dq_quarantined,
            "window_excluded_source_records": window_excluded,
        },
        "accepted": accepted_payload,
        "quarantine": quarantine_payload,
        "authors": author_payload,
        "discovery_observations": discovery_observations,
        "ranking_discovery_status": "BLOCKED_NO_VERIFIED_PUBLIC_ENTRY",
    }
    if collection_started_at is not None or collection_completed_at is not None:
        if collection_started_at is None or collection_completed_at is None:
            raise ValueError("collection start and completion must be recorded together")
        started = format_utc(collection_started_at)
        completed = format_utc(collection_completed_at)
        if parse_utc(completed) < parse_utc(started):
            raise ValueError("collection completion cannot precede its start")
        payload["collection_started_at_utc"] = started
        payload["collection_completed_at_utc"] = completed
    return payload


def _positive_limit(value: str) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > 200:
        raise argparse.ArgumentTypeError("limit must be between 1 and 200")
    return parsed


def _write_immutable(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--input-snapshot", type=Path)
    parser.add_argument("--live-cdp", action="store_true")
    parser.add_argument("--clock", required=True, help="strict 24h decision time")
    parser.add_argument("--limit", type=_positive_limit, default=200)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.fixture is not None and (args.input_snapshot is not None or args.live_cdp):
        parser.error("--fixture cannot be combined with live inputs")
    if args.fixture is None and args.input_snapshot is None and not args.live_cdp:
        parser.error("choose --fixture, --input-snapshot, or --live-cdp")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    decision_at = format_utc(args.clock)
    if args.fixture is not None:
        payload = _collect_fixture(args.fixture, limit=args.limit, decision_at=decision_at)
    elif args.live_cdp:
        payload = asyncio.run(
            _collect_cdp(
                decision_at=decision_at,
                limit=args.limit,
                snapshot=args.input_snapshot,
            )
        )
    else:
        urls = discover_snapshot_post_urls(args.input_snapshot, limit=args.limit)
        payload = _collect_live_urls(
            urls,
            decision_at=decision_at,
            source_mode="snapshot_public_get",
            fetch_detail=_public_get_detail,
            direct_source_channel="FEED",
        )
    _write_immutable(args.output, payload)
    counts = payload["counts"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "accepted": counts["accepted_observations"],
                "quarantine": counts["quarantined_source_records"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
