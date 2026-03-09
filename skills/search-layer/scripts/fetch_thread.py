#!/usr/bin/env python3
"""
fetch-thread: Deep content fetcher for threaded discussions.

Fetches a URL's full discussion thread + extracts structured references.
GitHub-optimized (API for issues/PRs/discussions), with generic web fallback.

Usage:
  python3 fetch_thread.py <url> [--max-comments 100] [--extract-refs] [--format json|markdown]

Output (JSON):
  {
    "url": "...",
    "type": "github_issue|github_pr|github_discussion|web_page",
    "title": "...",
    "body": "...",
    "state": "open|closed|merged",
    "labels": [...],
    "comments": [{"author": "...", "date": "...", "body": "...", "reactions": {...}}],
    "refs": [{"type": "issue|pr|commit|url|duplicate", "url": "...", "context": "..."}],
    "metadata": {"created": "...", "updated": "...", "author": "...", "comment_count": N}
  }
"""

import json
import sys
import os
import re
import argparse
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only, no requests dependency)
# ---------------------------------------------------------------------------
def _http_get(url: str, headers: dict | None = None,
              params: dict | None = None, timeout: int = 20) -> dict:
    """Simple GET returning {"status": int, "json": ..., "text": ...}.
    Raises on network errors; does NOT raise on 4xx/5xx (check status)."""
    if params:
        from urllib.parse import urlencode
        sep = "&" if "?" in url else "?"
        url = url + sep + urlencode(params)
    req = Request(url, method="GET")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        status = e.code
    result = {"status": status, "text": body}
    try:
        result["json"] = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        result["json"] = None
    return result


# ---------------------------------------------------------------------------
# GitHub token discovery
# ---------------------------------------------------------------------------
def _find_github_token() -> str | None:
    """Find GitHub token from env or git-credentials."""
    if tok := os.environ.get("GITHUB_TOKEN"):
        return tok
    if tok := os.environ.get("GH_TOKEN"):
        return tok
    cred_path = os.path.expanduser("~/.git-credentials")
    if os.path.isfile(cred_path):
        try:
            with open(cred_path) as f:
                for line in f:
                    line = line.strip()
                    if "github.com" in line:
                        # Format: https://user:token@github.com
                        match = re.search(r'://[^:]+:([^@]+)@github\.com', line)
                        if match:
                            return match.group(1)
        except Exception:
            pass
    return None


def _gh_headers(token: str | None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ---------------------------------------------------------------------------
# Reference extraction from text
# ---------------------------------------------------------------------------
# Patterns for extracting references from markdown/text
_REF_PATTERNS = [
    # GitHub issue/PR references: #123, owner/repo#123, GH-123
    (r'(?:^|[\s(])(?:([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+))?#(\d+)(?=[\s).,;:!?\']|$)',
     'issue_ref'),
    (r'(?:^|[\s(])GH-(\d+)(?=[\s).,;:!?\']|$)', 'gh_ref'),
    # Full GitHub URLs
    (r'https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/(issues|pull|discussions)/(\d+)(?:#[^\s)]*)?',
     'github_url'),
    # Commit references: full SHA or short SHA in context
    (r'https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/commit/([0-9a-f]{7,40})',
     'commit_url'),
    (r'(?:^|[\s(])([0-9a-f]{40})(?=[\s).,;:!?\']|$)', 'full_sha'),
    # Duplicate markers
    (r'(?i)(?:duplicate\s+of|duplicates?|dup(?:licate)?(?:\s+of)?)\s+#(\d+)', 'duplicate'),
    (r'(?i)(?:duplicate\s+of|duplicates?)\s+https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/(issues|pull)/(\d+)',
     'duplicate_url'),
    # "See also", "Related", "Fixes", "Closes" references
    (r'(?i)(?:see\s+also|related(?:\s+to)?|fixes|closes|resolves|refs?)\s+#(\d+)', 'related_ref'),
    # Generic URLs (non-GitHub)
    (r'(?<!\S)(https?://(?!github\.com)[^\s<>\[\]()]+?)(?=[)\s.,;:!?\'\"]|$)', 'external_url'),
]


def extract_refs(text: str, repo_context: str = "") -> list:
    """Extract structured references from text.

    Args:
        text: The text to scan for references.
        repo_context: Default "owner/repo" for bare #123 references.

    Returns:
        List of {"type": ..., "url": ..., "context": ...} dicts.
    """
    if not text:
        return []

    refs = []
    seen_urls = set()

    def _add(ref_type: str, url: str, context: str = ""):
        canon = url.rstrip("/")
        if canon not in seen_urls:
            seen_urls.add(canon)
            refs.append({"type": ref_type, "url": url, "context": context})

    for pattern, kind in _REF_PATTERNS:
        for m in re.finditer(pattern, text, re.MULTILINE):
            # Get surrounding context (up to 80 chars around match)
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            ctx = text[start:end].replace("\n", " ").strip()

            if kind == 'issue_ref':
                repo = m.group(1) or repo_context
                num = m.group(2)
                if repo:
                    url = f"https://github.com/{repo}/issues/{num}"
                    _add("issue", url, ctx)

            elif kind == 'gh_ref':
                num = m.group(1)
                if repo_context:
                    url = f"https://github.com/{repo_context}/issues/{num}"
                    _add("issue", url, ctx)

            elif kind == 'github_url':
                repo = m.group(1)
                url_type = m.group(2)  # issues, pull, discussions
                num = m.group(3)
                full_url = f"https://github.com/{repo}/{url_type}/{num}"
                ref_type = {"issues": "issue", "pull": "pr",
                            "discussions": "discussion"}.get(url_type, "issue")
                _add(ref_type, full_url, ctx)

            elif kind == 'commit_url':
                repo = m.group(1)
                sha = m.group(2)
                url = f"https://github.com/{repo}/commit/{sha}"
                _add("commit", url, ctx)

            elif kind == 'full_sha':
                sha = m.group(1)
                if repo_context:
                    url = f"https://github.com/{repo_context}/commit/{sha}"
                    _add("commit", url, ctx)

            elif kind == 'duplicate':
                num = m.group(1)
                if repo_context:
                    url = f"https://github.com/{repo_context}/issues/{num}"
                    _add("duplicate", url, ctx)

            elif kind == 'duplicate_url':
                repo = m.group(1)
                url_type = m.group(2)
                num = m.group(3)
                url = f"https://github.com/{repo}/{url_type}/{num}"
                _add("duplicate", url, ctx)

            elif kind == 'related_ref':
                num = m.group(1)
                if repo_context:
                    url = f"https://github.com/{repo_context}/issues/{num}"
                    _add("related", url, ctx)

            elif kind == 'external_url':
                url = m.group(1)
                # Skip image URLs and common non-reference URLs
                if not re.search(r'\.(png|jpg|jpeg|gif|svg|ico|webp)(\?|$)', url, re.I):
                    _add("url", url, ctx)

    return refs


# ---------------------------------------------------------------------------
# GitHub API fetchers
# ---------------------------------------------------------------------------
def _parse_github_url(url: str) -> dict | None:
    """Parse a GitHub URL into components.
    Returns {"owner", "repo", "type", "number"} or None."""
    parsed = urlparse(url)
    if parsed.hostname not in ("github.com", "www.github.com"):
        return None
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 4:
        return None
    owner, repo = parts[0], parts[1]
    url_type = parts[2]  # issues, pull, discussions
    try:
        number = int(parts[3])
    except (ValueError, IndexError):
        return None
    type_map = {"issues": "issue", "pull": "pr", "discussions": "discussion"}
    gh_type = type_map.get(url_type)
    if not gh_type:
        return None
    return {"owner": owner, "repo": repo, "type": gh_type, "number": number}


def fetch_github_issue(owner: str, repo: str, number: int,
                       token: str | None, max_comments: int = 100) -> dict:
    """Fetch a GitHub issue with all comments via REST API."""
    base = f"https://api.github.com/repos/{owner}/{repo}"
    headers = _gh_headers(token)
    result = {
        "url": f"https://github.com/{owner}/{repo}/issues/{number}",
        "type": "github_issue",
        "title": "",
        "body": "",
        "state": "",
        "labels": [],
        "comments": [],
        "refs": [],
        "metadata": {},
    }
    repo_ctx = f"{owner}/{repo}"

    # Fetch issue
    try:
        r = _http_get(f"{base}/issues/{number}", headers=headers, timeout=20)
        if r["status"] >= 400:
            result["error"] = f"GitHub API {r['status']}: {r['text'][:200]}"
            return result
        issue = r["json"]
    except Exception as e:
        result["error"] = f"Failed to fetch issue: {e}"
        return result

    # Check if it's actually a PR (GitHub API returns PRs via /issues/ too)
    if issue.get("pull_request"):
        result["type"] = "github_pr"
        result["url"] = f"https://github.com/{owner}/{repo}/pull/{number}"

    result["title"] = issue.get("title", "")
    result["body"] = issue.get("body", "") or ""
    result["state"] = issue.get("state", "")
    if issue.get("pull_request", {}).get("merged_at"):
        result["state"] = "merged"
    result["labels"] = [l.get("name", "") for l in issue.get("labels", [])]
    result["metadata"] = {
        "author": issue.get("user", {}).get("login", ""),
        "created": issue.get("created_at", ""),
        "updated": issue.get("updated_at", ""),
        "comment_count": issue.get("comments", 0),
        "reactions": _extract_reactions(issue.get("reactions", {})),
    }

    # Extract refs from body
    all_text = result["body"]

    # Fetch comments (paginated)
    page = 1
    per_page = min(max_comments, 100)
    fetched = 0
    while fetched < max_comments:
        try:
            r = _http_get(
                f"{base}/issues/{number}/comments",
                headers=headers,
                params={"page": page, "per_page": per_page},
                timeout=20,
            )
            if r["status"] >= 400:
                print(f"[fetch-thread] comment page {page} error: HTTP {r['status']}", file=sys.stderr)
                break
            comments = r["json"]
        except Exception as e:
            print(f"[fetch-thread] comment page {page} error: {e}", file=sys.stderr)
            break

        if not comments:
            break

        for c in comments:
            body = c.get("body", "") or ""
            result["comments"].append({
                "author": c.get("user", {}).get("login", ""),
                "date": c.get("created_at", ""),
                "body": body,
                "reactions": _extract_reactions(c.get("reactions", {})),
            })
            all_text += "\n" + body
            fetched += 1
            if fetched >= max_comments:
                break

        if len(comments) < per_page:
            break
        page += 1

    # If it's a PR, also fetch review comments
    if result["type"] == "github_pr":
        try:
            r = _http_get(
                f"{base}/pulls/{number}/reviews",
                headers=headers,
                params={"per_page": 50},
                timeout=20,
            )
            if r["status"] < 400 and r["json"]:
                for review in r["json"]:
                    body = review.get("body", "") or ""
                    if body.strip():
                        result["comments"].append({
                            "author": review.get("user", {}).get("login", ""),
                            "date": review.get("submitted_at", ""),
                            "body": f"[Review: {review.get('state', 'COMMENTED')}] {body}",
                            "reactions": {},
                        })
                        all_text += "\n" + body
        except Exception:
            pass  # Non-critical

    # Extract all refs from combined text
    result["refs"] = extract_refs(all_text, repo_ctx)

    # Also check for timeline events (duplicate markers, cross-references)
    _enrich_with_timeline(owner, repo, number, token, result, repo_ctx)

    return result


def _extract_reactions(reactions: dict) -> dict:
    """Extract non-zero reaction counts."""
    keys = ["+1", "-1", "laugh", "hooray", "confused", "heart", "rocket", "eyes"]
    return {k: reactions.get(k, 0) for k in keys if reactions.get(k, 0) > 0}


def _enrich_with_timeline(owner: str, repo: str, number: int,
                          token: str | None, result: dict, repo_ctx: str):
    """Fetch issue timeline events for cross-references and duplicate markers."""
    headers = _gh_headers(token)
    headers["Accept"] = "application/vnd.github.mockingbird-preview+json"
    try:
        r = _http_get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/timeline",
            headers=headers,
            params={"per_page": 100},
            timeout=20,
        )
        if r["status"] != 200:
            return
        events = r["json"]
    except Exception:
        return

    for event in events:
        etype = event.get("event", "")

        if etype == "cross-referenced":
            source = event.get("source", {}).get("issue", {})
            if source:
                src_repo = source.get("repository", {}).get("full_name", repo_ctx)
                src_num = source.get("number")
                src_type = "pr" if source.get("pull_request") else "issue"
                if src_num:
                    url = f"https://github.com/{src_repo}/{'pull' if src_type == 'pr' else 'issues'}/{src_num}"
                    result["refs"].append({
                        "type": f"cross_ref_{src_type}",
                        "url": url,
                        "context": f"Referenced by {src_repo}#{src_num}: {source.get('title', '')}",
                    })

        elif etype == "marked_as_duplicate":
            # The canonical issue info isn't always in the event, but we already
            # catch "Duplicate of #X" in text extraction
            pass

        elif etype in ("referenced", "connected"):
            commit = event.get("commit_id")
            if commit:
                url = f"https://github.com/{repo_ctx}/commit/{commit}"
                result["refs"].append({
                    "type": "commit",
                    "url": url,
                    "context": f"Referenced in commit {commit[:7]}",
                })

    # Deduplicate refs
    seen = set()
    unique_refs = []
    for ref in result["refs"]:
        key = ref["url"].rstrip("/")
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    result["refs"] = unique_refs


# ---------------------------------------------------------------------------
# Generic web page fetcher (fallback)
# ---------------------------------------------------------------------------
def fetch_v2ex(url: str) -> dict:
    """Fetch a V2EX topic via API and extract structured content."""
    result = {
        "url": url,
        "type": "v2ex_topic",
        "title": "",
        "body": "",
        "state": None,
        "labels": [],
        "comments": [],
        "refs": [],
        "links": [],
        "metadata": {},
    }

    # Extract topic ID from URL: v2ex.com/t/123456
    m = re.search(r'v2ex\.com/t/(\d+)', url)
    if not m:
        result["error"] = "Cannot parse V2EX topic ID from URL"
        return result

    topic_id = m.group(1)

    try:
        # Try V2EX API v1 (no auth required)
        topic_data = _http_get(
            f"https://www.v2ex.com/api/topics/show.json?id={topic_id}",
            headers={"User-Agent": "fetch-thread/1.0"})

        if topic_data["status"] == 200 and topic_data["json"]:
            topics = topic_data["json"]
            topic = topics[0] if isinstance(topics, list) and topics else {}
            result["title"] = topic.get("title", "")
            result["body"] = topic.get("content", "")
            result["metadata"] = {
                "author": topic.get("member", {}).get("username", ""),
                "created": topic.get("created", ""),
                "reply_count": topic.get("replies", 0),
                "node": topic.get("node", {}).get("name", ""),
            }

            # Replies via v1 API
            replies_data = _http_get(
                f"https://www.v2ex.com/api/replies/show.json?topic_id={topic_id}",
                headers={"User-Agent": "fetch-thread/1.0"})
            if replies_data["status"] == 200 and replies_data["json"]:
                for r in (replies_data["json"] or []):
                    result["comments"].append({
                        "author": r.get("member", {}).get("username", ""),
                        "date": r.get("created", ""),
                        "body": r.get("content", ""),
                    })

            all_text = result["body"] + " " + " ".join(c["body"] for c in result["comments"])
            result["refs"] = extract_refs(all_text)
        else:
            raise Exception(f"V2EX API returned {topic_data['status']}")

    except Exception as e:
        result["error"] = f"V2EX API failed: {e}, falling back to web fetch"
        fallback = fetch_web_page(url)
        result["title"] = result["title"] or fallback.get("title", "")
        result["body"] = fallback.get("body", "")
        result["links"] = fallback.get("links", [])
        result["refs"] = fallback.get("refs", [])

    return result


def fetch_hn(url: str) -> dict:
    """Fetch a Hacker News item via Algolia API (no auth required)."""
    result = {
        "url": url,
        "type": "hn_item",
        "title": "",
        "body": "",
        "state": None,
        "labels": [],
        "comments": [],
        "refs": [],
        "links": [],
        "metadata": {},
    }

    # Extract item ID: news.ycombinator.com/item?id=12345
    m = re.search(r'[?&]id=(\d+)', url)
    if not m:
        result["error"] = "Cannot parse HN item ID from URL"
        return result

    item_id = m.group(1)

    try:
        data = _http_get(
            f"https://hn.algolia.com/api/v1/items/{item_id}",
            headers={"User-Agent": "fetch-thread/1.0"})

        if data["status"] != 200 or not data["json"]:
            raise Exception(f"HN API returned {data['status']}")

        item = data["json"]
        result["title"] = item.get("title", "") or item.get("story_title", "")
        result["body"] = item.get("text", "") or item.get("url", "")
        result["metadata"] = {
            "author": item.get("author", ""),
            "created": item.get("created_at", ""),
            "score": item.get("points", 0),
            "comment_count": item.get("num_comments", 0),
            "type": item.get("type", ""),
        }

        from html import unescape

        def _parse_hn_comment(node: dict, depth: int = 0) -> dict:
            body = unescape(re.sub(r'<[^>]+>', ' ', node.get("text", "") or ""))
            body = re.sub(r'\s+', ' ', body).strip()
            c = {
                "author": node.get("author", ""),
                "date": node.get("created_at", ""),
                "body": body,
                "depth": depth,
            }
            children = [
                _parse_hn_comment(ch, depth + 1)
                for ch in (node.get("children") or [])
                if ch.get("author")
            ]
            if children:
                c["replies"] = children
            return c

        def _flatten_comments(nodes: list, depth: int = 0, max_total: int = 200) -> list:
            flat = []
            for node in nodes:
                if len(flat) >= max_total:
                    break
                if node.get("author"):
                    flat.append(_parse_hn_comment(node, depth))
            return flat

        children = item.get("children") or []
        result["comments_tree"] = _flatten_comments(children, depth=0, max_total=200)
        # backward-compat flat list (top-level only, max 50)
        result["comments"] = [
            {"author": c["author"], "date": c["date"], "body": c["body"]}
            for c in result["comments_tree"][:50]
        ]

        all_text = result["body"] + " " + " ".join(c["body"] for c in result["comments"])
        result["refs"] = extract_refs(all_text)

    except Exception as e:
        result["error"] = f"HN API failed: {e}, falling back to web fetch"
        fallback = fetch_web_page(url)
        result["title"] = result["title"] or fallback.get("title", "")
        result["body"] = fallback.get("body", "")
        result["links"] = fallback.get("links", [])
        result["refs"] = fallback.get("refs", [])

    return result


def fetch_reddit(url: str, max_comments: int = 200) -> dict:
    """Fetch a Reddit post + comment tree via .json endpoint (no auth required)."""
    result = {
        "url": url,
        "type": "reddit_post",
        "title": "",
        "body": "",
        "state": None,
        "labels": [],
        "comments": [],
        "comments_tree": [],
        "refs": [],
        "links": [],
        "metadata": {},
    }

    # Build .json URL: strip query/fragment, append .json
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        json_url = f"https://www.reddit.com{path}.json?limit=500&depth=4"
    except Exception as e:
        result["error"] = f"Failed to build Reddit JSON URL: {e}"
        return result

    try:
        data = _http_get(json_url, headers={
            "User-Agent": "fetch-thread/1.0 (research bot)",
            "Accept": "application/json",
        })

        if data["status"] != 200 or not data["json"]:
            raise Exception(f"Reddit API returned {data['status']}")

        listing = data["json"]
        # Reddit returns [post_listing, comments_listing]
        if not isinstance(listing, list) or len(listing) < 1:
            raise Exception("Unexpected Reddit JSON structure")

        post_data = listing[0]["data"]["children"][0]["data"]
        result["title"] = post_data.get("title", "")
        result["body"] = post_data.get("selftext", "") or post_data.get("url", "")
        result["metadata"] = {
            "author": post_data.get("author", ""),
            "created": post_data.get("created_utc", ""),
            "score": post_data.get("score", 0),
            "upvote_ratio": post_data.get("upvote_ratio", 0),
            "comment_count": post_data.get("num_comments", 0),
            "subreddit": post_data.get("subreddit", ""),
            "flair": post_data.get("link_flair_text", ""),
        }

        from html import unescape

        def _parse_comment(node: dict, depth: int = 0) -> dict | None:
            if node.get("kind") != "t1":
                return None
            d = node["data"]
            body = unescape(d.get("body", "") or "")
            c = {
                "author": d.get("author", ""),
                "date": d.get("created_utc", ""),
                "score": d.get("score", 0),
                "body": body,
                "depth": depth,
            }
            replies_data = d.get("replies")
            if isinstance(replies_data, dict):
                children = replies_data.get("data", {}).get("children", [])
                sub = [_parse_comment(ch, depth + 1) for ch in children if depth < 4]
                sub = [x for x in sub if x]
                if sub:
                    c["replies"] = sub
            return c

        comments_raw = listing[1]["data"]["children"] if len(listing) > 1 else []
        tree = [_parse_comment(n) for n in comments_raw]
        tree = [c for c in tree if c]

        # cap total nodes
        def _flatten(nodes, acc):
            for n in nodes:
                if len(acc) >= max_comments:
                    return
                acc.append(n)
                _flatten(n.get("replies", []), acc)

        flat = []
        _flatten(tree, flat)

        result["comments_tree"] = tree
        result["comments"] = [
            {"author": c["author"], "date": c["date"], "body": c["body"]}
            for c in flat[:max_comments]
        ]

        all_text = result["body"] + " " + " ".join(c["body"] for c in result["comments"])
        result["refs"] = extract_refs(all_text)

    except Exception as e:
        result["error"] = f"Reddit API failed: {e}, falling back to web fetch"
        fallback = fetch_web_page(url)
        result["title"] = result["title"] or fallback.get("title", "")
        result["body"] = fallback.get("body", "")
        result["links"] = fallback.get("links", [])
        result["refs"] = fallback.get("refs", [])

    return result


def _detect_platform(url: str) -> str:
    """Detect platform from URL."""
    host = urlparse(url).netloc.lower()
    if "v2ex.com" in host:
        return "v2ex"
    if "news.ycombinator.com" in host:
        return "hn"
    if "github.com" in host:
        return "github"
    if "reddit.com" in host:
        return "reddit"
    return "web"


def _extract_links_from_html(html: str, base_url: str = "") -> list:
    """Extract links from HTML with anchor_text and surrounding_text.

    Returns list of {"url": ..., "anchor": ..., "context": ...}
    Must be called BEFORE stripping tags.
    """
    links = []
    seen = set()

    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except Exception:
        return links

    # Strip noisy sections first (nav, footer, ads)
    clean = re.sub(r'<(nav|footer|header|aside)[^>]*>.*?</\1>', '', html,
                   flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)

    soup = BeautifulSoup(clean, 'lxml')

    for tag in soup.find_all('a', href=True):
        href = (tag.get('href') or '').strip()
        anchor = tag.get_text(separator=' ', strip=True)
        anchor = re.sub(r'\s+', ' ', anchor)

        # Skip empty anchors, images-only, javascript links
        if not href or not anchor or len(anchor) < 2:
            continue
        if href.startswith('javascript:'):
            continue

        resolved = urljoin(base_url, href)

        # Skip non-http links (mailto:, tel:, etc.)
        if not resolved.startswith('http'):
            continue

        # Skip image/asset URLs
        if re.search(r'\.(png|jpg|jpeg|gif|svg|ico|webp|css|js)(\?|$)', resolved, re.I):
            continue

        canon = resolved.rstrip('/')
        if canon in seen:
            continue
        seen.add(canon)

        parent_text = ""
        if tag.parent:
            parent_text = tag.parent.get_text(separator=' ', strip=True)
        context = re.sub(r'\s+', ' ', parent_text).strip()[:200]

        links.append({"url": resolved, "anchor": anchor, "context": context})

    return links


def fetch_web_page(url: str) -> dict:
    """Fetch a generic web page and extract references with anchor context."""
    result = {
        "url": url,
        "type": "web_page",
        "title": "",
        "body": "",
        "state": None,
        "labels": [],
        "comments": [],
        "refs": [],
        "links": [],  # enriched links with anchor_text + context
        "metadata": {},
    }

    try:
        req = Request(url, method="GET", headers={
            "User-Agent": "Mozilla/5.0 (compatible; fetch-thread/1.0)"
        })
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        if title_match:
            result["title"] = title_match.group(1).strip()

        # Extract enriched links BEFORE stripping tags
        result["links"] = _extract_links_from_html(html, base_url=url)

        body_text = ""

        # Layer 1: trafilatura extraction (preferred)
        try:
            import trafilatura
            extracted = trafilatura.extract(
                html,
                include_links=True,
                include_comments=False,
            )
            if extracted:
                body_text = re.sub(r'\s+', ' ', extracted).strip()
        except Exception:
            pass

        # Layer 2: BeautifulSoup fallback when extraction is missing/too short
        if len(body_text) < 200:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'lxml')
                bs_text = soup.get_text(separator=' ')
                bs_text = re.sub(r'\s+', ' ', bs_text).strip()
                if bs_text:
                    body_text = bs_text
            except Exception:
                pass

        # Layer 3: legacy regex fallback
        if not body_text:
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            body_text = re.sub(r'\s+', ' ', text).strip()

        # Truncate to reasonable size
        result["body"] = body_text[:10000]

        # Extract refs only from cleaned body text (reduce HTML noise)
        result["refs"] = extract_refs(result["body"])

    except Exception as e:
        result["error"] = f"Failed to fetch: {e}"

    return result


# ---------------------------------------------------------------------------
# Markdown output formatter
# ---------------------------------------------------------------------------
def format_markdown(data: dict) -> str:
    """Format fetch result as readable markdown."""
    lines = []
    lines.append(f"# {data.get('title', 'Untitled')}")
    lines.append(f"URL: {data['url']}")

    meta = data.get("metadata", {})
    if meta:
        parts = []
        if meta.get("author"):
            parts.append(f"Author: @{meta['author']}")
        if data.get("state"):
            parts.append(f"State: {data['state']}")
        if meta.get("created"):
            parts.append(f"Created: {meta['created']}")
        if meta.get("comment_count"):
            parts.append(f"Comments: {meta['comment_count']}")
        if parts:
            lines.append(" | ".join(parts))

    if data.get("labels"):
        lines.append(f"Labels: {', '.join(data['labels'])}")

    lines.append("")

    if data.get("body"):
        lines.append("## Body")
        lines.append(data["body"][:5000])
        lines.append("")

    if data.get("comments"):
        lines.append(f"## Comments ({len(data['comments'])})")
        for i, c in enumerate(data["comments"], 1):
            lines.append(f"### Comment {i} — @{c.get('author', '?')} ({c.get('date', '?')})")
            body = c.get("body", "")
            # Truncate very long comments
            if len(body) > 2000:
                body = body[:2000] + "\n... (truncated)"
            lines.append(body)
            if c.get("reactions"):
                lines.append(f"Reactions: {c['reactions']}")
            lines.append("")

    if data.get("refs"):
        lines.append(f"## References ({len(data['refs'])})")
        for ref in data["refs"]:
            ctx = f" — {ref['context']}" if ref.get("context") else ""
            lines.append(f"- [{ref['type']}] {ref['url']}{ctx}")
        lines.append("")

    if data.get("error"):
        lines.append(f"## Error\n{data['error']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def fetch_thread_url(url: str, max_comments: int = 100) -> dict:
    """Public API: fetch any URL and return structured data.

    Automatically detects platform (github/v2ex/hn/web) and routes accordingly.
    """
    platform = _detect_platform(url)
    token = _find_github_token()

    if platform == "github":
        gh = _parse_github_url(url)
        if gh and gh["type"] in ("issue", "pr"):
            return fetch_github_issue(gh["owner"], gh["repo"], gh["number"],
                                      token, max_comments)
        elif gh and gh["type"] == "discussion":
            data = fetch_web_page(url)
            data["type"] = "github_discussion"
            return data
        else:
            return fetch_web_page(url)
    elif platform == "v2ex":
        return fetch_v2ex(url)
    elif platform == "hn":
        return fetch_hn(url)
    elif platform == "reddit":
        return fetch_reddit(url, max_comments)
    else:
        return fetch_web_page(url)


def main():
    ap = argparse.ArgumentParser(
        description="Fetch full discussion thread + extract references from a URL")
    ap.add_argument("url", help="URL to fetch (GitHub issue/PR/discussion or any web page)")
    ap.add_argument("--max-comments", type=int, default=100,
                    help="Max comments to fetch (default 100)")
    ap.add_argument("--extract-refs-only", action="store_true",
                    help="Only output the extracted references, not full thread")
    ap.add_argument("--format", choices=["json", "markdown"], default="json",
                    help="Output format (default: json)")
    args = ap.parse_args()

    platform = _detect_platform(args.url)
    token = _find_github_token()

    if platform == "github":
        gh = _parse_github_url(args.url)
        if gh and gh["type"] in ("issue", "pr"):
            data = fetch_github_issue(
                gh["owner"], gh["repo"], gh["number"],
                token, args.max_comments)
        elif gh and gh["type"] == "discussion":
            data = fetch_web_page(args.url)
            data["type"] = "github_discussion"
        else:
            data = fetch_web_page(args.url)
    elif platform == "v2ex":
        data = fetch_v2ex(args.url)
    elif platform == "hn":
        data = fetch_hn(args.url)
    elif platform == "reddit":
        data = fetch_reddit(args.url, args.max_comments)
    else:
        data = fetch_web_page(args.url)

    if args.extract_refs_only:
        output = {
            "url": data["url"],
            "type": data["type"],
            "refs": data.get("refs", []),
            "ref_count": len(data.get("refs", [])),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(data))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
