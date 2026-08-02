"""Public Binance official announcement evidence with strict 24h semantics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .contracts import ContractViolation, format_utc, parse_utc


OFFICIAL_NEWS_ENDPOINT = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/"
    "catalog/list/query?catalogId=48&pageNo={page_no}&pageSize=20"
)
OFFICIAL_NEWS_DETAIL_ENDPOINT = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/"
    "detail/query?articleCode={article_code}"
)


def _public_get_json(page_no: int) -> Any:
    request = Request(
        OFFICIAL_NEWS_ENDPOINT.format(page_no=page_no),
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "binance-square-scanner-v4"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _public_get_detail_json(article_code: str) -> Any:
    request = Request(
        OFFICIAL_NEWS_DETAIL_ENDPOINT.format(article_code=article_code),
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "binance-square-scanner-v4"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _article_rows(value: Any) -> list[Mapping[str, Any]]:
    if (
        not isinstance(value, Mapping)
        or value.get("success") is not True
        or value.get("code") != "000000"
        or not isinstance(value.get("data"), Mapping)
    ):
        raise ContractViolation("official news response is missing Binance envelope")
    articles = value["data"].get("articles")
    if not isinstance(articles, list):
        raise ContractViolation("official news response is missing article list")
    if not all(isinstance(row, Mapping) for row in articles):
        raise ContractViolation("official news article list contains non-objects")
    return list(articles)


def _article_detail(value: Any, *, article_code: str) -> Mapping[str, Any]:
    if (
        not isinstance(value, Mapping)
        or value.get("success") is not True
        or value.get("code") != "000000"
        or not isinstance(value.get("data"), Mapping)
    ):
        raise ContractViolation("official news detail is missing Binance envelope")
    data = value["data"]
    if data.get("code") != article_code:
        raise ContractViolation("official news detail code conflicts with list row")
    return data


def _published_at(value: Any) -> datetime:
    if isinstance(value, int) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return parse_utc(value)


def collect_binance_official_news(
    *,
    decision_at: datetime | str,
    get_json: Callable[[int], Any] | None = None,
    get_detail_json: Callable[[str], Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Collect only Binance-hosted official announcements in ``[cutoff-24h, cutoff)``."""

    cutoff = parse_utc(decision_at)
    window_start = cutoff - timedelta(hours=24)
    captured = parse_utc((clock or (lambda: datetime.now(timezone.utc)))())
    fetch_page = get_json or _public_get_json
    fetch_detail = get_detail_json or _public_get_detail_json
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    returned_rows = 0
    total_available: int | None = None
    pages_fetched = 0
    detail_requests = 0
    crossed_window_start = False
    all_rows: list[tuple[Mapping[str, Any], datetime]] = []
    for page_no in range(1, 51):
        payload = fetch_page(page_no)
        rows = _article_rows(payload)
        total = payload["data"].get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ContractViolation("official news response total is invalid")
        total_available = total
        pages_fetched += 1
        returned_rows += len(rows)
        parsed_dates: list[datetime] = []
        for row in rows:
            article_id = str(row.get("code", row.get("id", ""))).strip()
            title = row.get("title")
            if not article_id or not isinstance(title, str) or not title.strip():
                raise ContractViolation("official news list row is missing identity")
            raw_date = row.get("publishDate", row.get("releaseDate"))
            try:
                published = _published_at(raw_date)
                resolved = row
            except (ContractViolation, ValueError, TypeError, OSError):
                detail_requests += 1
                resolved = _article_detail(
                    fetch_detail(article_id), article_code=article_id
                )
                published = _published_at(
                    resolved.get("publishDate", resolved.get("releaseDate"))
                )
            parsed_dates.append(published)
            all_rows.append((resolved, published))
        if any(
            earlier < later
            for earlier, later in zip(parsed_dates, parsed_dates[1:])
        ):
            raise ContractViolation("official news list is not newest-first")
        crossed_window_start = any(value < window_start for value in parsed_dates)
        if crossed_window_start or not rows or returned_rows >= total:
            break
    for row, published in all_rows:
        article_id = str(row.get("code", row.get("id", ""))).strip()
        if not article_id or article_id in seen:
            continue
        if not (window_start <= published < cutoff):
            continue
        seen.add(article_id)
        records.append(
            {
                "article_id": article_id,
                "title": row["title"].strip(),
                "published_at_utc": format_utc(published),
                "captured_at_utc": format_utc(captured),
                "source_url": (
                    "https://www.binance.com/en/support/announcement/detail/"
                    f"{article_id}"
                ),
            }
        )
    records.sort(key=lambda item: (item["published_at_utc"], item["article_id"]))
    return {
        "schema_version": "binance-official-news/v1",
        "source_system": "binance_official_announcement_cms",
        "source_endpoint": OFFICIAL_NEWS_ENDPOINT.format(page_no=1),
        "status": (
            "COMPLETE"
            if crossed_window_start or returned_rows >= (total_available or 0)
            else "PARTIAL"
        ),
        "decision_at_utc": format_utc(cutoff),
        "window_start_utc": format_utc(window_start),
        "captured_at_utc": format_utc(captured),
        "record_count": len(records),
        "coverage": {
            "pages_fetched": pages_fetched,
            "detail_requests": detail_requests,
            "returned_rows": returned_rows,
            "total_available": total_available,
            "page_size_requested": 20,
            "exhaustive_until_window_start": (
                crossed_window_start or returned_rows >= (total_available or 0)
            ),
        },
        "records": records,
    }


__all__ = [
    "OFFICIAL_NEWS_DETAIL_ENDPOINT",
    "OFFICIAL_NEWS_ENDPOINT",
    "collect_binance_official_news",
]
