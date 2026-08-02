#!/usr/bin/env python3
"""Binance Square scraper using an already-running Chrome CDP session.

The scraper only extracts real Binance Square post URLs. It keeps a stable
latest-result file for downstream consumers and also writes immutable,
timestamped snapshots for audit and replay.
"""

import asyncio
import fcntl
import itertools
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import websockets


CDP_BASE = "http://127.0.0.1:9222"
BINANCE_SQUARE = "https://www.binance.com/en/square"
LOCAL_TIMEZONE = "America/Los_Angeles"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

from scanner.discovery import FEED_COVERAGE_CONTRACT_VERSION, FEED_COVERAGE_SCOPE

DATA_DIR = os.path.join(SKILL_DIR, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
OUTPUT_FILE = os.path.join(DATA_DIR, "binance_raw_posts.json")
DEDUP_FILE = os.path.join(DATA_DIR, "binance_square_last_scan.json")
ERROR_FILE = os.path.join(DATA_DIR, "binance_last_error.json")
# v3.1 uses a separate lock because pre-timeout processes may hang before
# releasing legacy locks; all current runs still serialize against each other.
LOCK_FILE = os.path.join(DATA_DIR, ".binance_scraper_v3_1.lock")


def env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def env_float(name, default, minimum, maximum):
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


# The default target is 100 posts and the hard safety ceiling is 200.
MAX_POSTS = env_int("BINANCE_SQUARE_MAX_POSTS", 200, 1, 200)
MIN_TARGET = env_int("BINANCE_SQUARE_MIN_TARGET", 100, 1, MAX_POSTS)
MAX_SCROLLS = env_int("BINANCE_SQUARE_MAX_SCROLLS", 80, 1, 200)
STAGNANT_ROUNDS = env_int("BINANCE_SQUARE_STAGNANT_ROUNDS", 10, 2, 30)
SCROLL_PIXELS = env_int("BINANCE_SQUARE_SCROLL_PIXELS", 1200, 200, 4000)
SCROLL_DELAY = env_float("BINANCE_SQUARE_SCROLL_DELAY", 1.0, 0.3, 5.0)
LOAD_TRIGGER_DELAY = env_float(
    "BINANCE_SQUARE_LOAD_TRIGGER_DELAY", 0.35, 0.1, 2.0
)
CDP_RESPONSE_TIMEOUT = env_float("BINANCE_SQUARE_CDP_TIMEOUT", 15.0, 3.0, 60.0)
SCRAPE_TIMEOUT = env_float("BINANCE_SQUARE_RUN_TIMEOUT", 240.0, 30.0, 300.0)
CDP_MESSAGE_IDS = itertools.count(1)


def timestamp_pair(now=None):
    now = now or datetime.now(timezone.utc)
    utc_text = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    local_text = now.astimezone(ZoneInfo(LOCAL_TIMEZONE)).isoformat(timespec="seconds")
    return utc_text, local_text


def atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp-{os.getpid()}"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def normalize_post_url(url):
    """Return a canonical Binance Square post URL or an empty string."""
    try:
        parsed = urlsplit((url or "").strip())
    except ValueError:
        return ""
    hostname = (parsed.hostname or "").lower()
    if hostname != "binance.com" and not hostname.endswith(".binance.com"):
        return ""
    path = parsed.path.rstrip("/")
    if not re.fullmatch(r"/(?:[^/]+/)?square/post/[^/?#]+", path):
        return ""
    return urlunsplit(("https", "www.binance.com", path, "", ""))


def load_dedup_state():
    try:
        with open(DEDUP_FILE, encoding="utf-8") as handle:
            state = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        state = {}
    return {
        "seen_urls": set(state.get("seen_urls") or []),
        "seen_texts": set(state.get("seen_texts") or []),
        "last_scan": state.get("last_scan"),
    }


def annotate_against_history(posts, state):
    annotated = []
    new_posts = []
    for post in posts:
        text_key = (post.get("text") or "")[:100]
        duplicate = post["url"] in state["seen_urls"] or (
            bool(text_key) and text_key in state["seen_texts"]
        )
        item = dict(post)
        item["is_new"] = not duplicate
        annotated.append(item)
        if not duplicate:
            new_posts.append(item)
    return annotated, new_posts


async def get_binance_tab():
    with urllib.request.urlopen(f"{CDP_BASE}/json", timeout=5) as response:
        tabs = json.loads(response.read())
    for tab in tabs:
        url = tab.get("url", "")
        if "binance.com/en/square" in url and not url.startswith("blob:"):
            return tab["webSocketDebuggerUrl"], tab["id"], False
    for tab in tabs:
        url = tab.get("url", "")
        if "binance.com" in url and not url.startswith("blob:"):
            return tab["webSocketDebuggerUrl"], tab["id"], False
    raise RuntimeError(
        "No Binance tab found. Open https://www.binance.com/en/square in Chrome."
    )


async def cdp(websocket, method, params=None):
    # CDP serializes IDs through JavaScript numbers. Keep them small and exact;
    # nanosecond timestamps can exceed Number.MAX_SAFE_INTEGER and never match.
    message_id = next(CDP_MESSAGE_IDS)
    await websocket.send(
        json.dumps({"id": message_id, "method": method, "params": params or {}})
    )
    while True:
        raw_response = await asyncio.wait_for(
            websocket.recv(), timeout=CDP_RESPONSE_TIMEOUT
        )
        response = json.loads(raw_response)
        if response.get("id") == message_id:
            if "error" in response:
                raise RuntimeError(f"CDP error [{method}]: {response['error']}")
            return response.get("result", {})


COLLECT_POSTS_JS = r"""
(() => {
    const anchors = Array.from(document.querySelectorAll('a[href*="/square/post/"]'));
    const posts = [];
    const invalidUrls = [];

    function canonicalUrl(anchor) {
        try {
            const parsed = new URL(anchor.href, location.href);
            if (!/(^|\.)binance\.com$/i.test(parsed.hostname)) return '';
            const path = parsed.pathname.replace(/\/$/, '');
            if (!/^\/(?:[^/]+\/)?square\/post\/[^/?#]+$/.test(path)) return '';
            return `https://www.binance.com${path}`;
        } catch (_) {
            return '';
        }
    }

    function uniquePostUrls(element) {
        const urls = new Set();
        element.querySelectorAll('a[href*="/square/post/"]').forEach(a => {
            const url = canonicalUrl(a);
            if (url) urls.add(url);
        });
        return urls;
    }

    function findCard(anchor) {
        const semantic = anchor.closest('article, [role="article"], li');
        if (semantic) {
            const text = (semantic.textContent || '').trim();
            if (text.length >= 30 && uniquePostUrls(semantic).size === 1) return semantic;
        }

        let node = anchor.parentElement;
        let best = null;
        for (let depth = 0; node && depth < 12; depth++, node = node.parentElement) {
            const text = (node.textContent || '').trim();
            const urlCount = uniquePostUrls(node).size;
            if (urlCount > 1) break;
            if (urlCount === 1 && text.length >= 30 && text.length <= 4000) best = node;
        }
        return best || anchor.parentElement;
    }

    function findTime(card) {
        const direct = card.querySelector(
            '[class*="create-time"], time, [class*="time"], [class*="Time"], [class*="date"], [class*="Date"]'
        );
        if (direct) return (direct.getAttribute('datetime') || direct.textContent || '').trim();
        // Check leaf elements in card
        for (const element of card.querySelectorAll('*')) {
            if (element.children.length) continue;
            const text = (element.textContent || '').trim();
            if (/^(\d+\s*(m|min|h|hour|d|day|w|week)s?\s*(ago)?)$/i.test(text)) return text;
            if (/^\d{4}-\d{2}-\d{2}|\d{2}-\d{2}\s+\d{2}:\d{2}/.test(text)) return text;
        }
        // Fallback: time may be a sibling in parent container (Binance pattern)
        let scope = card.parentElement;
        for (let up = 0; up < 4 && scope; up++, scope = scope.parentElement) {
            const timeEl = scope.querySelector(':scope > [class*="create-time"], :scope > [class*="time"]');
            if (timeEl) {
                const txt = (timeEl.textContent || '').trim();
                if (txt && /^\d+\s*(m|min|h|hour|d|day|w|week)s?\s*(ago)?$/i.test(txt)) return txt;
            }
            // Also check scope's children with time-like content
            for (const child of scope.children) {
                const cls = (child.className || '').toString();
                if (cls.includes('create-time') || cls.includes('CreateTime')) {
                    const t = (child.textContent || '').trim();
                    if (t) return t;
                }
            }
        }
        return '';
    }

    for (const anchor of anchors) {
        const url = canonicalUrl(anchor);
        if (!url) {
            invalidUrls.push(anchor.href || '');
            continue;
        }
        const card = findCard(anchor);
        const text = card ? (card.textContent || '').trim().replace(/\n{3,}/g, '\n\n') : '';
        const authorElement = card ? card.querySelector(
            'a[href*="/square/profile/"], [class*="author"], [class*="Author"], ' +
            '[class*="nickname"], [class*="user-name"], [class*="username"]'
        ) : null;
        posts.push({
            url,
            text: text.slice(0, 1200),
            time: card ? findTime(card) : '',
            author: authorElement ? (authorElement.textContent || '').trim() : ''
        });
    }

    const scrolling = document.scrollingElement || document.documentElement || document.body;
    const scrollTop = scrolling ? scrolling.scrollTop : window.scrollY;
    const viewportHeight = scrolling ? scrolling.clientHeight : window.innerHeight;
    const documentHeight = Math.max(
        document.body ? document.body.scrollHeight : 0,
        document.documentElement ? document.documentElement.scrollHeight : 0
    );
    return {
        candidateLinks: anchors.length,
        candidateBlocks: posts.length,
        invalidUrls: invalidUrls.length,
        posts,
        documentHeight,
        scrollTop,
        viewportHeight,
        reachedBottom: scrollTop + viewportHeight >= documentHeight - 2
    };
})()
"""


SCROLL_TO_TOP_JS = r"""
(() => {
    const candidates = [
        document.scrollingElement,
        document.documentElement,
        document.body,
        document.querySelector('main'),
        document.querySelector('[class*="feed-layout-main"]'),
        document.querySelector('[class*="Feed"]'),
        document.querySelector('[class*="feed"]')
    ].filter(Boolean);
    let target = candidates[0];
    let bestRange = -1;
    for (const element of candidates) {
        const range = Math.max(0, element.scrollHeight - element.clientHeight);
        if (range > bestRange) {
            bestRange = range;
            target = element;
        }
    }
    const isDocument = target === document.body || target === document.documentElement ||
        target === document.scrollingElement;
    const before = isDocument ? window.scrollY : target.scrollTop;
    if (isDocument) window.scrollTo(0, 0);
    else target.scrollTo(0, 0);
    const after = isDocument ? window.scrollY : target.scrollTop;
    const documentHeight = target.scrollHeight;
    const viewportHeight = target.clientHeight;
    return {
        before,
        after,
        documentHeight,
        viewportHeight,
        reachedBottom: after + viewportHeight >= documentHeight - 2
    };
})()
"""


SCROLL_JS = f"""
(() => {{
    const candidates = [
        document.scrollingElement,
        document.documentElement,
        document.body,
        document.querySelector('main'),
        document.querySelector('[class*="feed-layout-main"]'),
        document.querySelector('[class*="Feed"]'),
        document.querySelector('[class*="feed"]')
    ].filter(Boolean);
    let target = candidates[0];
    let bestRange = -1;
    for (const element of candidates) {{
        const range = Math.max(0, element.scrollHeight - element.clientHeight);
        if (range > bestRange) {{
            bestRange = range;
            target = element;
        }}
    }}
    const isDocument = target === document.body || target === document.documentElement ||
        target === document.scrollingElement;
    const before = isDocument ? window.scrollY : target.scrollTop;
    const viewportHeight = target.clientHeight;
    const documentHeight = target.scrollHeight;
    if (isDocument) window.scrollBy(0, {SCROLL_PIXELS});
    else target.scrollBy(0, {SCROLL_PIXELS});
    const after = isDocument ? window.scrollY : target.scrollTop;
    const afterHeight = target.scrollHeight;
    const afterViewport = target.clientHeight;
    return {{
        before,
        after,
        scrollRange: Math.max(0, afterHeight - afterViewport),
        documentHeight: afterHeight,
        viewportHeight: afterViewport,
        reachedBottom: after + afterViewport >= afterHeight - 2,
        backoffApplied: false
    }};
}})()
"""


LEAVE_BOTTOM_JS = r"""
(() => {
    const candidates = [
        document.scrollingElement,
        document.documentElement,
        document.body,
        document.querySelector('main'),
        document.querySelector('[class*="feed-layout-main"]'),
        document.querySelector('[class*="Feed"]'),
        document.querySelector('[class*="feed"]')
    ].filter(Boolean);
    let target = candidates[0];
    let bestRange = -1;
    for (const element of candidates) {
        const range = Math.max(0, element.scrollHeight - element.clientHeight);
        if (range > bestRange) {
            bestRange = range;
            target = element;
        }
    }
    const isDocument = target === document.body || target === document.documentElement ||
        target === document.scrollingElement;
    const before = isDocument ? window.scrollY : target.scrollTop;
    const viewportHeight = target.clientHeight;
    const retreat = Math.max(600, Math.min(1600, viewportHeight));
    if (isDocument) window.scrollTo(0, Math.max(0, before - retreat));
    else target.scrollTo(0, Math.max(0, before - retreat));
    const after = isDocument ? window.scrollY : target.scrollTop;
    const documentHeight = target.scrollHeight;
    const afterViewport = target.clientHeight;
    return {
        before,
        after,
        documentHeight,
        viewportHeight: afterViewport,
        reachedBottom: after + afterViewport >= documentHeight - 2
    };
})()
"""


RETURN_TO_BOTTOM_JS = r"""
(() => {
    const candidates = [
        document.scrollingElement,
        document.documentElement,
        document.body,
        document.querySelector('main'),
        document.querySelector('[class*="feed-layout-main"]'),
        document.querySelector('[class*="Feed"]'),
        document.querySelector('[class*="feed"]')
    ].filter(Boolean);
    let target = candidates[0];
    let bestRange = -1;
    for (const element of candidates) {
        const range = Math.max(0, element.scrollHeight - element.clientHeight);
        if (range > bestRange) {
            bestRange = range;
            target = element;
        }
    }
    const isDocument = target === document.body || target === document.documentElement ||
        target === document.scrollingElement;
    const before = isDocument ? window.scrollY : target.scrollTop;
    if (isDocument) window.scrollTo(0, target.scrollHeight);
    else target.scrollTo(0, target.scrollHeight);
    const after = isDocument ? window.scrollY : target.scrollTop;
    const documentHeight = target.scrollHeight;
    const viewportHeight = target.clientHeight;
    return {
        before,
        after,
        documentHeight,
        viewportHeight,
        reachedBottom: after + viewportHeight >= documentHeight - 2
    };
})()
"""


async def evaluate_value(websocket, expression):
    result = await cdp(
        websocket,
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
    )
    if result.get("exceptionDetails"):
        details = result["exceptionDetails"]
        description = (
            details.get("exception", {}).get("description")
            if isinstance(details, dict)
            else None
        )
        raise RuntimeError(
            f"Runtime.evaluate failed: {description or details}"
        )
    remote = result.get("result", {})
    if isinstance(remote, dict) and remote.get("subtype") == "error":
        raise RuntimeError(
            f"Runtime.evaluate failed: {remote.get('description') or 'JavaScript error'}"
        )
    return remote.get("value", {})


def merge_posts(collected, incoming):
    added = 0
    for raw_post in incoming:
        url = normalize_post_url(raw_post.get("url"))
        if not url:
            continue
        item = {
            "url": url,
            "text": (raw_post.get("text") or "").strip()[:1200],
            "time": (raw_post.get("time") or "").strip(),
            "author": (raw_post.get("author") or "").strip(),
        }
        previous = collected.get(url)
        if previous is None:
            collected[url] = item
            added += 1
        elif len(item["text"]) > len(previous.get("text", "")):
            # Keep the richest observed version of a virtualized feed card.
            collected[url] = item
        else:
            if not previous.get("author") and item["author"]:
                previous["author"] = item["author"]
            if not previous.get("time") and item["time"]:
                previous["time"] = item["time"]
    return added


@dataclass(frozen=True, slots=True)
class FeedDiscoveryCollection:
    posts: tuple[dict[str, str], ...]
    discovery_result: dict[str, Any]
    stats: dict[str, Any]


async def collect_feed_discovery(
    websocket: Any,
    *,
    evaluator: Callable[[Any, str], Awaitable[Any]] = evaluate_value,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    preferred_minimum: int = MIN_TARGET,
    hard_limit: int = MAX_POSTS,
    max_scrolls: int = MAX_SCROLLS,
    stagnant_rounds: int = STAGNANT_ROUNDS,
    scroll_delay: float = SCROLL_DELAY,
    load_trigger_delay: float = LOAD_TRIGGER_DELAY,
) -> FeedDiscoveryCollection:
    """Collect one bounded DOM surface and return its auditable stop contract."""

    top_reset = await evaluator(websocket, SCROLL_TO_TOP_JS)
    started_from_top = abs(float(top_reset.get("after") or 0)) <= 1
    collected: dict[str, dict[str, str]] = {}
    source_observations = 0
    valid_url_observations = 0
    invalid_url_observations = 0
    candidate_block_observations = 0
    scroll_observations: list[dict[str, Any]] = []
    load_trigger_observations: list[dict[str, Any]] = []
    load_trigger_attempts = 0
    consecutive_no_new = 0
    last_bottom_height: int | None = None
    reached_bottom = False
    bottom_geometry_stable = False
    scroll_rounds = 0
    termination_reason = "SCROLL_LIMIT"

    for round_number in range(max_scrolls + 1):
        batch = await evaluator(websocket, COLLECT_POSTS_JS)
        candidate_links = max(0, int(batch.get("candidateLinks") or 0))
        invalid_urls = max(0, int(batch.get("invalidUrls") or 0))
        source_observations += candidate_links
        invalid_url_observations += min(candidate_links, invalid_urls)
        valid_url_observations += max(0, candidate_links - invalid_urls)
        candidate_block_observations += max(
            0, int(batch.get("candidateBlocks") or 0)
        )
        added = merge_posts(collected, batch.get("posts") or [])

        at_bottom = bool(batch.get("reachedBottom"))
        height = max(0, int(batch.get("documentHeight") or 0))
        if at_bottom:
            reached_bottom = True
            if added:
                consecutive_no_new = 0
            elif last_bottom_height == height:
                consecutive_no_new += 1
            else:
                consecutive_no_new = 1
            last_bottom_height = height
        else:
            # Long virtualized feeds can expose no new anchors for many moving
            # rounds.  Only stable bottom observations count toward exhaustion.
            consecutive_no_new = 0
            last_bottom_height = None
        bottom_geometry_stable = bool(
            at_bottom and consecutive_no_new >= stagnant_rounds
        )

        if len(collected) >= hard_limit:
            termination_reason = "HARD_LIMIT"
            break
        if bottom_geometry_stable:
            termination_reason = (
                "EXHAUSTED"
                if started_from_top and len(collected) >= preferred_minimum
                else "STAGNANT"
            )
            break
        if round_number >= max_scrolls:
            termination_reason = "SCROLL_LIMIT"
            break

        if at_bottom:
            leave = await evaluator(websocket, LEAVE_BOTTOM_JS)
            load_trigger_attempts += 1
            leave_evidence = {
                "round": scroll_rounds + 1,
                "attempt": load_trigger_attempts,
                "phase": "LEAVE_BOTTOM",
                "before": leave.get("before"),
                "after": leave.get("after"),
                "document_height": leave.get("documentHeight"),
                "viewport_height": leave.get("viewportHeight"),
                "reached_bottom": bool(leave.get("reachedBottom")),
            }
            load_trigger_observations.append(leave_evidence)
            await sleeper(load_trigger_delay)
            scroll = await evaluator(websocket, RETURN_TO_BOTTOM_JS)
            return_evidence = {
                "round": scroll_rounds + 1,
                "attempt": load_trigger_attempts,
                "phase": "RETURN_TO_BOTTOM",
                "before": scroll.get("before"),
                "after": scroll.get("after"),
                "document_height": scroll.get("documentHeight"),
                "viewport_height": scroll.get("viewportHeight"),
                "reached_bottom": bool(scroll.get("reachedBottom")),
            }
            load_trigger_observations.append(return_evidence)
        else:
            leave_evidence = None
            return_evidence = None
            scroll = await evaluator(websocket, SCROLL_JS)
        scroll_rounds += 1
        evidence = {
            "round": scroll_rounds,
            "before": scroll.get("before"),
            "after": scroll.get("after"),
            "document_height": scroll.get("documentHeight"),
            "viewport_height": scroll.get("viewportHeight"),
            "scroll_range": scroll.get("scrollRange"),
            "reached_bottom": bool(scroll.get("reachedBottom")),
            "backoff_applied": at_bottom,
            "load_trigger_attempt": load_trigger_attempts if at_bottom else None,
            "load_trigger_phases": (
                [leave_evidence, return_evidence] if at_bottom else []
            ),
        }
        scroll_observations.append(evidence)
        reached_bottom = reached_bottom or evidence["reached_bottom"]
        await sleeper(scroll_delay)

    posts = tuple(list(collected.values())[:hard_limit])
    truncated = termination_reason == "HARD_LIMIT"
    if termination_reason == "EXHAUSTED":
        coverage_status = "BOUNDED_COMPLETE"
    elif termination_reason == "HARD_LIMIT":
        coverage_status = "CAPPED"
    else:
        coverage_status = "PARTIAL"
    discovery_result = {
        # This collector proves only the currently rendered Discover DOM
        # surface. It does not prove exhaustion of Binance's internal feed API
        # or a platform-wide denominator.
        "coverage_scope": FEED_COVERAGE_SCOPE,
        "global_denominator_known": False,
        "pagination_api_exhaustion_verified": False,
        "coverage_status": coverage_status,
        "termination_reason": termination_reason,
        "started_from_top": started_from_top,
        "reached_bottom": reached_bottom,
        "bottom_geometry_stable": bottom_geometry_stable,
        "source_observation_count": source_observations,
        "valid_url_observation_count": valid_url_observations,
        "invalid_url_observation_count": invalid_url_observations,
        "unique_candidate_post_count": len(posts),
        "same_run_duplicate_observation_count": max(
            0, valid_url_observations - len(posts)
        ),
        "preferred_minimum": preferred_minimum,
        "hard_limit": hard_limit,
        "minimum_target_met": len(posts) >= preferred_minimum,
        "truncated": truncated,
        "scroll_rounds": scroll_rounds,
        "consecutive_no_new": consecutive_no_new,
        "required_consecutive_no_new": stagnant_rounds,
        "top_reset": dict(top_reset),
        "scroll_observations": scroll_observations,
        "load_trigger_attempts": load_trigger_attempts,
        "load_trigger_observations": load_trigger_observations,
    }
    stats = {
        "candidate_link_observations": source_observations,
        "candidate_block_observations": candidate_block_observations,
        "invalid_url_observations": invalid_url_observations,
        "unique_valid_posts": len(posts),
        "scroll_rounds": scroll_rounds,
        "preferred_minimum": preferred_minimum,
        "hard_limit": hard_limit,
        "stopped_after_stagnant_rounds": consecutive_no_new,
        "scroll_observations": scroll_observations,
        "load_trigger_attempts": load_trigger_attempts,
        "load_trigger_observations": load_trigger_observations,
    }
    return FeedDiscoveryCollection(posts, discovery_result, stats)


async def scrape():
    websocket_url, tab_id, dedicated_tab = await get_binance_tab()
    print(
        f"[CDP] Tab: {tab_id} ({'dedicated' if dedicated_tab else 'reused'})",
        file=sys.stderr,
    )

    print("[*] Connecting to tab...", file=sys.stderr)
    await asyncio.sleep(0.5)
    async with websockets.connect(
        websocket_url,
        max_size=20 * 1024 * 1024,
        open_timeout=10,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
    ) as websocket:
        print("[*] Connected", file=sys.stderr)
        return await scrape_connected(websocket)


async def scrape_connected(websocket):
        await cdp(websocket, "Runtime.enable")
        await cdp(websocket, "Page.enable")

        print("[*] Loading page...", file=sys.stderr)
        current = await evaluate_value(websocket, "location.href")
        if "binance.com/en/square" in str(current or "") and "cloudflare" not in str(current or "").lower():
            await cdp(websocket, "Runtime.evaluate", {"expression": "location.reload()", "returnByValue": True})
        else:
            await cdp(websocket, "Page.navigate", {"url": BINANCE_SQUARE})
        await asyncio.sleep(8)

        print(
            f"[*] Dynamic collection: target={MIN_TARGET}, max={MAX_POSTS}, "
            f"scrolls<={MAX_SCROLLS}",
            file=sys.stderr,
        )

        collection = await collect_feed_discovery(websocket)
        posts = list(collection.posts)
        state = load_dedup_state()
        annotated_posts, new_posts = annotate_against_history(posts, state)

        now = datetime.now(timezone.utc)
        scanned_at_utc, scanned_at_local = timestamp_pair(now)
        snapshot_name = now.strftime("binance_raw_posts_%Y%m%dT%H%M%S.%fZ.json")
        snapshot_path = os.path.join(HISTORY_DIR, snapshot_name)

        stats = {
            **collection.stats,
            "duplicate_posts": len(annotated_posts) - len(new_posts),
            "new_posts": len(new_posts),
        }
        output = {
            "status": "ok",
            "coverage_contract_version": FEED_COVERAGE_CONTRACT_VERSION,
            "discovery_result": collection.discovery_result,
            "scanned_at": scanned_at_utc,
            "scanned_at_local": scanned_at_local,
            "timezone": LOCAL_TIMEZONE,
            "source_url": BINANCE_SQUARE,
            "snapshot_file": snapshot_path,
            "previous_successful_scan": state["last_scan"],
            "count": len(annotated_posts),
            "new_count": len(new_posts),
            "stats": stats,
            "new_posts": new_posts,
            "posts": annotated_posts,
        }

        atomic_write_json(snapshot_path, output)
        atomic_write_json(OUTPUT_FILE, output)

        print(
            f"[OK] latest={scanned_at_utc} local={scanned_at_local} | "
            f"valid={stats['unique_valid_posts']} new={stats['new_posts']} "
            f"duplicates={stats['duplicate_posts']} | snapshot={snapshot_path}",
            file=sys.stderr,
        )
        return output


def write_error(error):
    attempted_at_utc, attempted_at_local = timestamp_pair()
    payload = {
        "status": "error",
        "coverage_contract_version": FEED_COVERAGE_CONTRACT_VERSION,
        "discovery_result": {
            "coverage_status": "BLOCKED",
            "termination_reason": "ERROR",
            "started_from_top": False,
            "reached_bottom": False,
            "bottom_geometry_stable": False,
            "source_observation_count": 0,
            "valid_url_observation_count": 0,
            "invalid_url_observation_count": 0,
            "unique_candidate_post_count": 0,
            "same_run_duplicate_observation_count": 0,
            "preferred_minimum": MIN_TARGET,
            "hard_limit": MAX_POSTS,
            "minimum_target_met": False,
            "truncated": False,
            "scroll_rounds": 0,
            "consecutive_no_new": 0,
            "required_consecutive_no_new": STAGNANT_ROUNDS,
            "scroll_observations": [],
            "load_trigger_attempts": 0,
            "load_trigger_observations": [],
        },
        "attempted_at": attempted_at_utc,
        "attempted_at_local": attempted_at_local,
        "timezone": LOCAL_TIMEZONE,
        "error": str(error)[:500],
        "count": 0,
        "posts": [],
        "stats": {},
    }
    atomic_write_json(ERROR_FILE, payload)
    return payload


async def main():
    print("=" * 50, file=sys.stderr)
    print("[START] Binance Square Scraper v3.0", file=sys.stderr)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOCK_FILE, "a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[SKIP] Another Binance Square scan is already running.", file=sys.stderr)
            return True

        try:
            with urllib.request.urlopen(f"{CDP_BASE}/json/version", timeout=3):
                pass
            await asyncio.wait_for(scrape(), timeout=SCRAPE_TIMEOUT)
            return True
        except Exception as error:
            print(f"[FAIL] {error}", file=sys.stderr)
            write_error(error)
            return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
