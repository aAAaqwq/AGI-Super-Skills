#!/usr/bin/env python3
"""Build privacy-preserving GitHub repository statistics for the static site."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable


API_VERSION = "2022-11-28"
DEFAULT_REPOSITORY = "aAAaqwq/AGI-Super-Team"
USER_AGENT = "agi-super-team-site-data/1.0"
HISTORY_UNAVAILABLE_STATUS_CODES = frozenset({401, 403, 429})


class GitHubRequestError(RuntimeError):
    """A transport or HTTP failure with enough context for scoped fallback."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.transient = transient


def isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _require_count(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def build_repository_stats(
    repository: str, payload: dict[str, Any], generated_at: datetime
) -> dict[str, Any]:
    if payload.get("full_name", "").casefold() != repository.casefold():
        raise ValueError("repository identity does not match requested repository")
    return {
        "schemaVersion": 1,
        "repository": repository,
        "stars": _require_count(payload.get("stargazers_count"), "stargazers_count"),
        "forks": _require_count(payload.get("forks_count"), "forks_count"),
        "fetchedAt": isoformat_utc(generated_at),
        "source": "github-rest-api",
    }


def _parse_starred_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("each stargazer entry must include starred_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"invalid starred_at timestamp: {value}") from error
    if parsed.tzinfo is None:
        raise ValueError("starred_at timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def aggregate_star_history(
    repository: str,
    stargazers: Iterable[dict[str, Any]],
    generated_at: datetime,
    current_stars: int | None = None,
) -> dict[str, Any]:
    daily = Counter(_parse_starred_at(item.get("starred_at")).date().isoformat() for item in stargazers)
    cumulative = 0
    points: list[dict[str, Any]] = []
    for date in sorted(daily):
        cumulative += daily[date]
        points.append({"date": date, "stars": cumulative})
    latest_stars = cumulative if current_stars is None else _require_count(
        current_stars, "current_stars"
    )
    return {
        "schemaVersion": 1,
        "repository": repository,
        "generatedAt": isoformat_utc(generated_at),
        "source": "github-current-stargazers",
        "semantics": (
            "Historical cumulative count reconstructed from users who currently star "
            "the repository; unstars can revise earlier points."
        ),
        "latestStars": latest_stars,
        "points": points,
    }


def render_star_history_svg(history: dict[str, Any]) -> str:
    width, height = 1200, 420
    left, top, right, bottom = 78, 58, 42, 72
    plot_width = width - left - right
    plot_height = height - top - bottom
    points = history.get("points") or []
    latest = _require_count(history.get("latestStars", 0), "latestStars")
    repository = escape(str(history.get("repository", "AGI Super Team")))

    if points:
        max_stars = max(1, max(_require_count(point["stars"], "stars") for point in points))
        denominator = max(1, len(points) - 1)
        coordinates = [
            (
                left + (index / denominator) * plot_width,
                top + plot_height - (point["stars"] / max_stars) * plot_height,
            )
            for index, point in enumerate(points)
        ]
        polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinates)
        area = (
            f"{left},{top + plot_height} {polyline} "
            f"{left + plot_width},{top + plot_height}"
        )
        first_date = escape(str(points[0]["date"]))
        last_date = escape(str(points[-1]["date"]))
        end_x, end_y = coordinates[-1]
    else:
        polyline = ""
        area = ""
        first_date = last_date = (
            "History refresh pending" if latest else "No stars yet"
        )
        end_x, end_y = left, top + plot_height

    chart = ""
    if polyline:
        chart = f"""
    <polygon points="{area}" fill="url(#area)" />
    <polyline points="{polyline}" fill="none" stroke="url(#line)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="7" fill="#f8fafc" stroke="#8b5cf6" stroke-width="5" />"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 {width} {height}">
  <title id="title">AGI Super Team star history</title>
  <desc id="desc">{repository}. Latest count: {latest} stars. Reconstructed from current GitHub stargazers.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#070b1d" />
      <stop offset="1" stop-color="#0b1422" />
    </linearGradient>
    <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#4cc9f0" />
      <stop offset="1" stop-color="#8b5cf6" />
    </linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#8b5cf6" stop-opacity="0.32" />
      <stop offset="1" stop-color="#8b5cf6" stop-opacity="0" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="28" fill="url(#bg)" />
  <text x="{left}" y="38" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="22" font-weight="700">GitHub star history</text>
  <text x="{width - right}" y="38" fill="#a5b4fc" text-anchor="end" font-family="ui-monospace, monospace" font-size="18">{latest} stars</text>
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#263449" />
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#263449" />
  <line x1="{left}" y1="{top + plot_height / 2}" x2="{left + plot_width}" y2="{top + plot_height / 2}" stroke="#263449" stroke-dasharray="6 10" />
  {chart}
  <text x="{left}" y="{height - 34}" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="16">{first_date}</text>
  <text x="{left + plot_width}" y="{height - 34}" fill="#94a3b8" text-anchor="end" font-family="system-ui, sans-serif" font-size="16">{last_date}</text>
</svg>
"""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_site_data(
    docs_directory: Path,
    repository: str,
    repository_payload: dict[str, Any],
    stargazers: Iterable[dict[str, Any]],
    generated_at: datetime,
) -> None:
    stats = build_repository_stats(repository, repository_payload, generated_at)
    history = aggregate_star_history(
        repository, stargazers, generated_at, current_stars=stats["stars"]
    )
    _write_json(docs_directory / "data/repo-stats.json", stats)
    _write_json(docs_directory / "data/star-history.json", history)
    chart_path = docs_directory / "assets/star-history.svg"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(render_star_history_svg(history), encoding="utf-8")


def _request_json(url: str, token: str | None, accept: str) -> tuple[Any, dict[str, str]]:
    headers = {
        "Accept": accept,
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    transient_errors = (urllib.error.URLError, http.client.HTTPException, TimeoutError)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, {
                    key.lower(): value for key, value in response.headers.items()
                }
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"GitHub API returned invalid JSON for {url}: {error}"
            ) from error
        except urllib.error.HTTPError as error:
            status_code = error.code
            reason = error.reason
            error.close()
            transient = status_code == 429 or 500 <= status_code < 600
            if transient and attempt < 2:
                time.sleep(0.5 * (2**attempt))
                continue
            raise GitHubRequestError(
                f"GitHub API request failed for {url}: HTTP {status_code} {reason}",
                status_code=status_code,
                transient=transient,
            ) from error
        except transient_errors as error:
            if attempt == 2:
                raise GitHubRequestError(
                    f"GitHub API request failed for {url}: {error}",
                    transient=True,
                ) from error
            time.sleep(0.5 * (2**attempt))

    raise AssertionError("unreachable")


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="([^"]+)"', part)
        if match and match.group(2) == "next":
            return match.group(1)
    return None


def fetch_github_data(repository: str, token: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    api_root = f"https://api.github.com/repos/{repository}"
    repository_payload, _ = _request_json(api_root, token, "application/vnd.github+json")
    stargazers: list[dict[str, Any]] = []
    next_url: str | None = f"{api_root}/stargazers?per_page=100"
    while next_url:
        try:
            page, headers = _request_json(
                next_url, token, "application/vnd.github.star+json"
            )
        except GitHubRequestError as error:
            if (
                error.status_code not in HISTORY_UNAVAILABLE_STATUS_CODES
                and not error.transient
            ):
                raise
            print(
                "GitHub star history is temporarily unavailable; writing a current-count "
                "placeholder so the site can still deploy.",
                file=sys.stderr,
            )
            return repository_payload, []
        if not isinstance(page, list):
            raise RuntimeError("GitHub stargazers response was not a list")
        stargazers.extend(page)
        next_url = _next_link(headers.get("link"))
    return repository_payload, stargazers


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    repository_payload, stargazers = fetch_github_data(
        arguments.repository, os.environ.get(arguments.token_env)
    )
    write_site_data(
        arguments.docs_dir,
        arguments.repository,
        repository_payload,
        stargazers,
        datetime.now(timezone.utc),
    )
    print(f"Built site data for {arguments.repository}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
