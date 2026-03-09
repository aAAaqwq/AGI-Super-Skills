#!/usr/bin/env python3
"""
relevance_gate.py — LLM-based relevance scoring for chain tracking.

Given an original query, current knowledge_state, and a list of candidate
links (with anchor_text + context), calls an LLM to batch-score each candidate
and returns only those above the threshold.

Usage (standalone):
  python3 relevance_gate.py \
    --query "Rust async runtime performance" \
    --knowledge "Already know: Tokio vs async-std comparison. Still unclear: real-world benchmarks." \
    --candidates '[{"url":"...","anchor":"...","context":"..."}]' \
    --threshold 0.5

Output JSON:
  [{"url": "...", "anchor": "...", "context": "...", "score": 0.8, "reason": "..."}]
"""

import json
import os
import sys
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


# ---------------------------------------------------------------------------
# Credentials loader (reuse search-layer pattern)
# ---------------------------------------------------------------------------
def _load_creds() -> dict:
    keys = {}
    cred_path = Path.home() / ".openclaw" / "credentials" / "search.json"
    try:
        cred = json.loads(cred_path.read_text())
        if grok := cred.get("grok"):
            if isinstance(grok, dict):
                keys["grok_url"] = grok.get("apiUrl", "")
                keys["grok_key"] = grok.get("apiKey", "")
                keys["grok_model"] = grok.get("model", "grok-4.1-fast")
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    # Env var overrides
    for env, key in [("GROK_API_KEY", "grok_key"), ("GROK_API_URL", "grok_url"),
                     ("GROK_MODEL", "grok_model")]:
        if v := os.environ.get(env):
            keys[key] = v
    return keys


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def _call_llm(prompt: str, creds: dict) -> str:
    """Call Grok (or compatible OpenAI API) and return response text."""
    url = creds.get("grok_url", "").rstrip("/") + "/chat/completions"
    api_key = creds.get("grok_key", "")
    model = creds.get("grok_model", "grok-4.1-fast")

    if not api_key:
        raise ValueError("No LLM API key configured (grok_key missing)")

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024,
        "stream": False,
    }).encode()

    req = Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()

        # Handle SSE streaming response (server ignores stream:false)
        if raw.startswith("data:"):
            content_parts = []
            for line in raw.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                    delta = obj["choices"][0].get("delta", {})
                    if text := delta.get("content"):
                        content_parts.append(text)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
            return "".join(content_parts)

        # Standard non-streaming response
        data = json.loads(raw)
        return data["choices"][0]["message"]["content"]

    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"LLM API error {e.code}: {body[:200]}")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_prompt(query: str, knowledge_state: str, candidates: list) -> str:
    cand_lines = []
    for i, c in enumerate(candidates, 1):
        anchor = c.get("anchor") or c.get("context", "")[:60]
        context = c.get("context", "")[:150]
        url = c.get("url", "")
        cand_lines.append(f'{i}. anchor="{anchor}" url={url}\n   context="{context}"')

    candidates_text = "\n".join(cand_lines)

    return f"""You are a research assistant evaluating whether web links are worth following.

Original query: {query}

What we already know: {knowledge_state or "Nothing yet."}

Candidate links to evaluate:
{candidates_text}

For each candidate, score 0.0-1.0 how likely following this link will provide NEW, RELEVANT information to answer the original query.
- Score > 0.7: definitely follow (directly relevant, likely new info)
- Score 0.4-0.7: maybe follow (somewhat relevant or unclear)
- Score < 0.4: skip (irrelevant, duplicate, or noise)

Respond with ONLY a JSON array, no explanation outside JSON:
[
  {{"id": 1, "score": 0.9, "reason": "one sentence"}},
  {{"id": 2, "score": 0.2, "reason": "one sentence"}},
  ...
]"""


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------
def score_candidates(
    query: str,
    candidates: list,
    knowledge_state: str = "",
    threshold: float = 0.4,
    creds: dict | None = None,
) -> list:
    """Score candidates and return those above threshold.

    Args:
        query: Original search query.
        candidates: List of {"url", "anchor", "context"} dicts.
        knowledge_state: Summary of what we already know.
        threshold: Minimum score to include (default 0.4).
        creds: API credentials dict (loaded from file if None).

    Returns:
        Filtered + scored list: [{"url", "anchor", "context", "score", "reason"}]
    """
    if not candidates:
        return []

    if creds is None:
        creds = _load_creds()

    prompt = _build_prompt(query, knowledge_state, candidates)

    try:
        raw = _call_llm(prompt, creds)
    except Exception as e:
        # On LLM failure, return all candidates unscored (fail open)
        sys.stderr.write(f"[relevance_gate] LLM call failed: {e}, returning all candidates\n")
        return [dict(c, score=0.5, reason="LLM unavailable") for c in candidates]

    # Parse JSON response
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            text = text.rstrip("`").strip()
        scores = json.loads(text)
    except json.JSONDecodeError:
        sys.stderr.write(f"[relevance_gate] Failed to parse LLM response: {raw[:200]}\n")
        return [dict(c, score=0.5, reason="parse error") for c in candidates]

    # Merge scores back into candidates
    score_map = {item["id"]: item for item in scores if "id" in item}
    result = []
    for i, c in enumerate(candidates, 1):
        s = score_map.get(i, {})
        score = float(s.get("score", 0.5))
        if score >= threshold:
            result.append({
                **c,
                "score": score,
                "reason": s.get("reason", ""),
            })

    # Sort by score descending
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="LLM relevance gate for chain tracking")
    ap.add_argument("--query", required=True, help="Original search query")
    ap.add_argument("--knowledge", default="", help="Current knowledge state summary")
    ap.add_argument("--candidates", required=True,
                    help='JSON array of {"url","anchor","context"} objects')
    ap.add_argument("--threshold", type=float, default=0.4,
                    help="Minimum score threshold (default 0.4)")
    args = ap.parse_args()

    try:
        candidates = json.loads(args.candidates)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid candidates JSON: {e}"}))
        sys.exit(1)

    creds = _load_creds()
    results = score_candidates(
        query=args.query,
        candidates=candidates,
        knowledge_state=args.knowledge,
        threshold=args.threshold,
        creds=creds,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
