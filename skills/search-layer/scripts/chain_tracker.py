#!/usr/bin/env python3
"""
chain_tracker.py — Recursive content fetcher with LLM relevance gate.

Starting from a list of seed URLs, fetches content, extracts links with
anchor+context, scores them via LLM, and recursively follows high-scoring
links up to max_depth=3.

Usage:
  python3 chain_tracker.py \
    --query "Rust async runtime performance" \
    --urls "https://..." "https://..." \
    [--depth 3] [--threshold 0.5] [--max-per-level 3] [--output results.json]

Output JSON:
  {
    "query": "...",
    "knowledge_state": "...",
    "nodes": [
      {
        "url": "...", "depth": 0, "type": "...", "title": "...",
        "body": "...", "comments": [...], "score": 1.0, "reason": "seed"
      },
      ...
    ]
  }
"""

import json
import sys
import argparse
from pathlib import Path

# Add scripts dir to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))
import fetch_thread
import relevance_gate


# ---------------------------------------------------------------------------
# Knowledge state updater
# ---------------------------------------------------------------------------
def _update_knowledge(knowledge_state: str, node: dict, creds: dict) -> str:
    """Ask LLM to update knowledge_state after reading a new node."""
    title = node.get("title", "")
    body = (node.get("body", "") or "")[:500]
    comments_text = " ".join(c.get("body", "")[:100] for c in node.get("comments", [])[:5])

    prompt = f"""Current knowledge state: {knowledge_state or 'Nothing known yet.'}

Just read: "{title}"
Content summary: {body}
{f'Key comments: {comments_text}' if comments_text else ''}

Update the knowledge state in 1-2 sentences:
- What new facts were learned?
- What is still unclear or needs more investigation?

Respond with ONLY the updated knowledge state text, no preamble."""

    try:
        raw = relevance_gate._call_llm(prompt, creds)
        return raw.strip()
    except Exception:
        return f"{knowledge_state} Also read: {title}." if knowledge_state else f"Read: {title}."


# ---------------------------------------------------------------------------
# Candidate extractor: merge links + refs into scored candidates
# ---------------------------------------------------------------------------
def _get_candidates(node: dict) -> list:
    """Extract candidate links from a fetched node."""
    candidates = []
    seen = set()

    # Enriched links (anchor + context) from web pages
    for link in node.get("links", []):
        url = link.get("url", "")
        if url and url not in seen:
            seen.add(url)
            candidates.append({
                "url": url,
                "anchor": link.get("anchor", ""),
                "context": link.get("context", ""),
            })

    # Refs from GitHub/text (have context but no anchor)
    for ref in node.get("refs", []):
        url = ref.get("url", "")
        if url and url not in seen:
            seen.add(url)
            candidates.append({
                "url": url,
                "anchor": ref.get("type", "reference"),
                "context": ref.get("context", ""),
            })

    return candidates


# ---------------------------------------------------------------------------
# Main tracker
# ---------------------------------------------------------------------------
def track(
    query: str,
    seed_urls: list,
    max_depth: int = 3,
    threshold: float = 0.5,
    max_per_level: int = 3,
) -> dict:
    """Run recursive chain tracking from seed URLs.

    Returns dict with query, knowledge_state, and nodes list.
    """
    creds = relevance_gate._load_creds()
    visited = set()
    nodes = []
    knowledge_state = ""

    # Queue: list of (url, depth, score, reason)
    queue = [(url, 0, 1.0, "seed") for url in seed_urls]

    while queue:
        url, depth, score, reason = queue.pop(0)

        # Skip if already visited or too deep
        canon = url.rstrip("/")
        if canon in visited or depth > max_depth:
            continue
        visited.add(canon)

        # Fetch content
        sys.stderr.write(f"[chain_tracker] depth={depth} fetching: {url}\n")
        try:
            data = fetch_thread.fetch_thread_url(url)
        except Exception as e:
            sys.stderr.write(f"[chain_tracker] fetch failed: {e}\n")
            continue

        # Record node
        node = {
            "url": url,
            "depth": depth,
            "type": data.get("type", "unknown"),
            "title": data.get("title", ""),
            "body": (data.get("body", "") or "")[:2000],
            "comments": data.get("comments", [])[:10],
            "score": score,
            "reason": reason,
        }
        nodes.append(node)

        # Update knowledge state
        knowledge_state = _update_knowledge(knowledge_state, node, creds)
        sys.stderr.write(f"[chain_tracker] knowledge: {knowledge_state[:100]}\n")

        # Stop recursing at max depth
        if depth >= max_depth:
            continue

        # Extract + score candidates for next level
        candidates = _get_candidates(data)
        if not candidates:
            continue

        # Cap candidates to avoid token explosion (max 20 per level)
        candidates = candidates[:20]

        scored = relevance_gate.score_candidates(
            query=query,
            candidates=candidates,
            knowledge_state=knowledge_state,
            threshold=threshold,
            creds=creds,
        )

        # Take top-K per level
        for c in scored[:max_per_level]:
            queue.append((c["url"], depth + 1, c["score"], c.get("reason", "")))

    return {
        "query": query,
        "knowledge_state": knowledge_state,
        "nodes": nodes,
        "total_fetched": len(nodes),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Recursive chain tracker with LLM relevance gate")
    ap.add_argument("--query", required=True, help="Original search query")
    ap.add_argument("--urls", nargs="+", required=True, help="Seed URLs to start from")
    ap.add_argument("--depth", type=int, default=3, help="Max recursion depth (default 3)")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="Relevance score threshold (default 0.5)")
    ap.add_argument("--max-per-level", type=int, default=3,
                    help="Max links to follow per level (default 3)")
    ap.add_argument("--output", help="Write results to file instead of stdout")
    args = ap.parse_args()

    result = track(
        query=args.query,
        seed_urls=args.urls,
        max_depth=args.depth,
        threshold=args.threshold,
        max_per_level=args.max_per_level,
    )

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(out)
        sys.stderr.write(f"[chain_tracker] results written to {args.output}\n")
    else:
        print(out)


if __name__ == "__main__":
    main()
