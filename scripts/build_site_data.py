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
CHART_THEMES = {
    "dark": {
        "background": "#080d1a",
        "panel": "#111827",
        "text": "#f8fafc",
        "muted": "#94a3b8",
        "grid": "#263449",
        "line_start": "#22d3ee",
        "line_end": "#8b5cf6",
        "area": "#8b5cf6",
        "marker": "#f8fafc",
    },
    "light": {
        "background": "#ffffff",
        "panel": "#f8fafc",
        "text": "#0f172a",
        "muted": "#64748b",
        "grid": "#dbe3ef",
        "line_start": "#0891b2",
        "line_end": "#7c3aed",
        "area": "#8b5cf6",
        "marker": "#ffffff",
    },
}


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
        "status": "live" if points else "pending",
    }


def _validated_cached_points(history: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not history or not isinstance(history.get("points"), list):
        return []

    validated: list[dict[str, Any]] = []
    previous_stars = -1
    previous_date = ""
    for point in history["points"]:
        if not isinstance(point, dict):
            return []
        date = point.get("date")
        stars = point.get("stars")
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return []
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return []
        if (
            isinstance(stars, bool)
            or not isinstance(stars, int)
            or stars < previous_stars
            or date <= previous_date
        ):
            return []
        validated.append({"date": date, "stars": stars})
        previous_stars = stars
        previous_date = date
    return validated


def resolve_star_history(
    repository: str,
    stargazers: Iterable[dict[str, Any]],
    generated_at: datetime,
    current_stars: int,
    cached_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stargazer_list = list(stargazers)
    if stargazer_list:
        return aggregate_star_history(
            repository,
            stargazer_list,
            generated_at,
            current_stars=current_stars,
        )

    cached_points: list[dict[str, Any]] = []
    if (
        cached_history
        and str(cached_history.get("repository", "")).casefold()
        == repository.casefold()
    ):
        cached_points = _validated_cached_points(cached_history)
    if cached_points:
        return {
            "schemaVersion": 1,
            "repository": repository,
            "generatedAt": isoformat_utc(generated_at),
            "source": "repository-cache+github-current-count",
            "semantics": (
                "Last successful historical reconstruction retained from the "
                "repository cache; latestStars is refreshed from GitHub."
            ),
            "latestStars": _require_count(current_stars, "current_stars"),
            "points": cached_points,
            "status": "cached",
        }

    return aggregate_star_history(
        repository,
        [],
        generated_at,
        current_stars=current_stars,
    )


def render_star_history_svg(
    history: dict[str, Any], theme: str = "dark"
) -> str:
    if theme not in CHART_THEMES:
        raise ValueError(f"unsupported chart theme: {theme}")
    colors = CHART_THEMES[theme]
    width, height = 1200, 420
    left, top, right, bottom = 82, 92, 46, 70
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
        y_axis_max = max_stars
    else:
        polyline = ""
        area = ""
        first_date = last_date = (
            "History refresh pending" if latest else "No stars yet"
        )
        end_x, end_y = left, top + plot_height
        y_axis_max = latest

    chart = ""
    if polyline:
        chart = f"""    <polygon points="{area}" fill="url(#area)" />
    <polyline points="{polyline}" fill="none" stroke="url(#line)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="7" fill="{colors['marker']}" stroke="{colors['line_end']}" stroke-width="5" />"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" data-theme="{theme}" viewBox="0 0 {width} {height}">
  <title id="title">AGI Super Team star history</title>
  <desc id="desc">{repository}. Latest count: {latest} stars. Reconstructed from current GitHub stargazers.</desc>
  <defs>
    <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{colors['line_start']}" />
      <stop offset="1" stop-color="{colors['line_end']}" />
    </linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{colors['area']}" stop-opacity="0.28" />
      <stop offset="1" stop-color="{colors['area']}" stop-opacity="0" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="28" fill="{colors['background']}" />
  <rect x="22" y="22" width="{width - 44}" height="{height - 44}" rx="20" fill="none" stroke="{colors['grid']}" />
  <text x="{left}" y="52" fill="{colors['text']}" font-family="system-ui, sans-serif" font-size="24" font-weight="700">GitHub star history</text>
  <text x="{left}" y="77" fill="{colors['muted']}" font-family="system-ui, sans-serif" font-size="14">aAAaqwq / AGI-Super-Team</text>
  <rect x="{width - right - 132}" y="39" width="132" height="38" rx="19" fill="{colors['panel']}" stroke="{colors['grid']}" />
  <text x="{width - right - 66}" y="64" fill="{colors['text']}" text-anchor="middle" font-family="ui-monospace, monospace" font-size="17" font-weight="700">★ {latest}</text>
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="{colors['grid']}" />
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="{colors['grid']}" />
  <line x1="{left}" y1="{top + plot_height / 2}" x2="{left + plot_width}" y2="{top + plot_height / 2}" stroke="{colors['grid']}" stroke-dasharray="6 10" />
{chart}
  <text x="{left - 14}" y="{top + 5}" fill="{colors['muted']}" text-anchor="end" font-family="ui-monospace, monospace" font-size="13">{y_axis_max}</text>
  <text x="{left - 14}" y="{top + plot_height + 5}" fill="{colors['muted']}" text-anchor="end" font-family="ui-monospace, monospace" font-size="13">0</text>
  <text x="{left}" y="{height - 38}" fill="{colors['muted']}" font-family="system-ui, sans-serif" font-size="15">{first_date}</text>
  <text x="{left + plot_width}" y="{height - 38}" fill="{colors['muted']}" text-anchor="end" font-family="system-ui, sans-serif" font-size="15">{last_date}</text>
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
    cached_history: dict[str, Any] | None = None,
) -> None:
    stats = build_repository_stats(repository, repository_payload, generated_at)
    history = resolve_star_history(
        repository,
        stargazers,
        generated_at,
        current_stars=stats["stars"],
        cached_history=cached_history,
    )
    _write_json(docs_directory / "data/repo-stats.json", stats)
    _write_json(docs_directory / "data/star-history.json", history)
    assets_directory = docs_directory / "assets"
    assets_directory.mkdir(parents=True, exist_ok=True)
    dark_chart = render_star_history_svg(history, theme="dark")
    light_chart = render_star_history_svg(history, theme="light")
    (assets_directory / "star-history.svg").write_text(dark_chart, encoding="utf-8")
    (assets_directory / "star-history-dark.svg").write_text(
        dark_chart, encoding="utf-8"
    )
    (assets_directory / "star-history-light.svg").write_text(
        light_chart, encoding="utf-8"
    )


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
    history_path = arguments.docs_dir / "data/star-history.json"
    cached_history: dict[str, Any] | None = None
    if history_path.is_file():
        try:
            cached_payload = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(cached_payload, dict):
                cached_history = cached_payload
        except (OSError, json.JSONDecodeError) as error:
            print(f"Ignoring invalid cached star history: {error}", file=sys.stderr)
    repository_payload, stargazers = fetch_github_data(
        arguments.repository, os.environ.get(arguments.token_env)
    )
    write_site_data(
        arguments.docs_dir,
        arguments.repository,
        repository_payload,
        stargazers,
        datetime.now(timezone.utc),
        cached_history=cached_history,
    )
    print(f"Built site data for {arguments.repository}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
