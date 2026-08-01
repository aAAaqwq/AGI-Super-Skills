"""Strict read-only contracts for Binance Futures Smart Money leaderboards.

The public leaderboard exposes ten rows per page and does not return a rank
field.  This module therefore derives ranks only after three complete pages
have passed reconciliation.  ``topTraderId`` is a Smart Money source identity;
it must never be treated as a Binance Square ``squareUid``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import ContractViolation, format_utc, parse_utc


LEADERBOARD_ENDPOINT = (
    "https://www.binance.com/bapi/futures/v1/friendly/future/"
    "smart-money/top-trader/list"
)
PROFILE_ENDPOINT = (
    "https://www.binance.com/bapi/asset/v1/friendly/future/"
    "smart-money/profile"
)
EVIDENCE_SCHEMA_VERSION = "binance-smart-money-top30-evidence/v1"
RANKING_TYPES = ("PNL", "ROI")
TIME_RANGE = "30D"
ORDER = "DESC"
ROWS_PER_PAGE = 10
PAGES = (1, 2, 3)
RANK_SOURCE = "DERIVED_FROM_PAGE_AND_POSITION"
SOURCE_ID_TYPE = "topTraderId"


JsonGet = Callable[[str, float], dict[str, Any]]
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class SmartMoneyRequest:
    ranking_type: str
    time_range: str = TIME_RANGE
    order: str = ORDER
    rows: int = ROWS_PER_PAGE

    def __post_init__(self) -> None:
        if self.ranking_type not in RANKING_TYPES:
            raise ContractViolation(
                "Smart Money rankingType must be one of PNL or ROI"
            )
        if self.time_range != TIME_RANGE:
            raise ContractViolation("Smart Money timeRange must be 30D")
        if self.order != ORDER:
            raise ContractViolation("Smart Money order must be DESC")
        if self.rows != ROWS_PER_PAGE:
            raise ContractViolation(
                "Smart Money TOP30 must use rows=10 and pages=1..3; "
                "rows=30 is not an accepted API contract"
            )

    def query(self, page: int) -> dict[str, str | int]:
        if page not in PAGES:
            raise ContractViolation("Smart Money page must be 1, 2, or 3")
        return {
            "rankingType": self.ranking_type,
            "timeRange": self.time_range,
            "order": self.order,
            "page": page,
            "rows": self.rows,
            "onlyShowSharingPosition": "false",
            "onlyShowSignalEnabled": "false",
        }

    def url(self, page: int) -> str:
        return f"{LEADERBOARD_ENDPOINT}?{urlencode(self.query(page))}"


@dataclass(frozen=True, slots=True)
class EvidenceWriteReceipt:
    path: str
    file_sha256: str
    payload_sha256: str
    byte_count: int


def public_json_get(url: str, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch one public JSON document without browser or credential state."""

    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "binance-smart-money-readonly/1",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolation("Smart Money endpoint returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ContractViolation("Smart Money response root must be an object")
    return payload


def _clock_utc(clock: Clock) -> datetime:
    observed = clock()
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise ContractViolation("Smart Money clock must return a timezone-aware datetime")
    return observed.astimezone(timezone.utc)


def _observed_window(started_at: datetime, completed_at: datetime) -> dict[str, Any]:
    if completed_at < started_at:
        raise ContractViolation("Smart Money observed window cannot move backwards")
    return {
        "snapshot_semantics": "OBSERVED_WINDOW",
        "started_at_utc": format_utc(started_at),
        "completed_at_utc": format_utc(completed_at),
        "duration_seconds": (completed_at - started_at).total_seconds(),
    }


def _successful_data(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    if payload.get("code") != "000000" or payload.get("success") is not True:
        code = payload.get("code")
        raise ContractViolation(f"{source} API failed with code={code!r}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ContractViolation(f"{source} response has no data object")
    return data


def _positive_total(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 30:
        raise ContractViolation("Smart Money total must be an integer >= 30")
    return value


def _last_update_time(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractViolation("Smart Money lastUpdateTime must be Unix milliseconds")
    return value


def _stable_top_trader_id(row: dict[str, Any], *, page: int, position: int) -> str:
    value = row.get("topTraderId")
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(
            f"Smart Money page {page} row {position} has no stable topTraderId"
        )
    return value.strip()


def _collect_ranking(
    request: SmartMoneyRequest,
    *,
    get_json: JsonGet,
    timeout: float,
    clock: Clock,
) -> dict[str, Any]:
    parsed_rows: list[dict[str, Any]] = []
    page_metadata: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    expected_update: int | None = None
    expected_total: int | None = None
    observed_start: datetime | None = None
    observed_end: datetime | None = None

    for page in PAGES:
        request_started_at = _clock_utc(clock)
        if observed_start is None:
            observed_start = request_started_at
        payload = get_json(request.url(page), timeout)
        response_received_at = _clock_utc(clock)
        _observed_window(request_started_at, response_received_at)
        observed_end = response_received_at
        if not isinstance(payload, dict):
            raise ContractViolation("Smart Money response root must be an object")
        data = _successful_data(payload, source="Smart Money leaderboard")
        total = _positive_total(data.get("total"))
        update_time = _last_update_time(data.get("lastUpdateTime"))
        rows = data.get("rows")
        if not isinstance(rows, list):
            raise ContractViolation(f"Smart Money page {page} rows must be a list")
        if len(rows) != ROWS_PER_PAGE:
            raise ContractViolation(
                f"Smart Money page {page} must contain exactly 10 rows; got {len(rows)}"
            )
        if expected_update is None:
            expected_update = update_time
            expected_total = total
        elif update_time != expected_update:
            raise ContractViolation(
                "Smart Money lastUpdateTime changed between leaderboard pages"
            )
        elif total != expected_total:
            raise ContractViolation("Smart Money total changed between leaderboard pages")

        page_metadata.append(
            {
                "page": page,
                "request": request.query(page),
                "request_started_at_utc": format_utc(request_started_at),
                "response_received_at_utc": format_utc(response_received_at),
                "response": {
                    "code": payload.get("code"),
                    "success": payload.get("success"),
                    "total": total,
                    "row_count": len(rows),
                    "lastUpdateTime": update_time,
                    "promptOpenSignal": data.get("promptOpenSignal"),
                },
            }
        )
        for position, source_row in enumerate(rows, start=1):
            if not isinstance(source_row, dict):
                raise ContractViolation(
                    f"Smart Money page {page} row {position} must be an object"
                )
            source_id = _stable_top_trader_id(
                source_row, page=page, position=position
            )
            if source_id in seen_ids:
                raise ContractViolation(
                    f"Smart Money duplicate topTraderId across pages: {source_id}"
                )
            seen_ids.add(source_id)
            parsed_rows.append(
                {
                    "rank": (page - 1) * ROWS_PER_PAGE + position,
                    "rank_source": RANK_SOURCE,
                    "page": page,
                    "position_on_page": position,
                    "source_id": source_id,
                    "source_id_type": SOURCE_ID_TYPE,
                    "source_row": source_row,
                }
            )

    if len(parsed_rows) != 30 or len(seen_ids) != 30:
        raise ContractViolation("Smart Money TOP30 reconciliation failed")
    if [row["rank"] for row in parsed_rows] != list(range(1, 31)):
        raise ContractViolation("Smart Money derived ranks are not exactly 1..30")
    if observed_start is None or observed_end is None:
        raise AssertionError("Smart Money ranking has no observed window")
    return {
        "ranking_type": request.ranking_type,
        "time_range": request.time_range,
        "order": request.order,
        "status": "COMPLETE",
        "total": expected_total,
        "lastUpdateTime": expected_update,
        "rank_source": RANK_SOURCE,
        "source_id_type": SOURCE_ID_TYPE,
        "snapshot_semantics": "OBSERVED_WINDOW",
        "observed_window": _observed_window(observed_start, observed_end),
        "pages": page_metadata,
        "rows": parsed_rows,
    }


def _collect_profiles(
    source_ids: Iterable[str],
    *,
    get_json: JsonGet,
    timeout: float,
    clock: Clock,
) -> dict[str, Any]:
    requested = tuple(dict.fromkeys(source_ids))
    profiles: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    observed_start: datetime | None = None
    observed_end: datetime | None = None
    for source_id in requested:
        url = f"{PROFILE_ENDPOINT}?{urlencode({'topTraderId': source_id})}"
        request_started_at = _clock_utc(clock)
        if observed_start is None:
            observed_start = request_started_at
        try:
            payload = get_json(url, timeout)
            if not isinstance(payload, dict):
                raise ContractViolation("Smart Money profile root must be an object")
            data = _successful_data(payload, source="Smart Money profile")
            observed_id = data.get("topTraderId")
            if observed_id != source_id:
                raise ContractViolation(
                    "Smart Money profile topTraderId does not match requested identity"
                )
        except Exception as exc:
            response_received_at = _clock_utc(clock)
            _observed_window(request_started_at, response_received_at)
            observed_end = response_received_at
            failures.append(
                {
                    "source_id": source_id,
                    "status": "FAILED",
                    "request_started_at_utc": format_utc(request_started_at),
                    "response_received_at_utc": format_utc(response_received_at),
                    "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
        else:
            response_received_at = _clock_utc(clock)
            _observed_window(request_started_at, response_received_at)
            observed_end = response_received_at
            profiles.append(
                {
                    "source_id": source_id,
                    "source_id_type": SOURCE_ID_TYPE,
                    "status": "COMPLETE",
                    "request_started_at_utc": format_utc(request_started_at),
                    "response_received_at_utc": format_utc(response_received_at),
                    "profile": data,
                }
            )
    completed = len(profiles)
    expected = len(requested)
    result = {
        "enabled": True,
        "status": "COMPLETE" if completed == expected else "PARTIAL",
        "expected": expected,
        "completed": completed,
        "failed": len(failures),
        "coverage_ratio": completed / expected if expected else 1.0,
        "profiles": profiles,
        "failures": failures,
    }
    if observed_start is not None and observed_end is not None:
        result["observed_window"] = _observed_window(observed_start, observed_end)
    return result


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _attach_integrity(document: dict[str, Any]) -> dict[str, Any]:
    if "integrity" in document:
        raise ContractViolation("integrity must be generated, not supplied")
    digest = sha256(_canonical_bytes(document)).hexdigest()
    return {
        **document,
        "integrity": {
            "algorithm": "SHA256",
            "scope": "canonical top-level JSON excluding integrity",
            "payload_sha256": digest,
        },
    }


def verify_evidence_integrity(document: dict[str, Any]) -> bool:
    integrity = document.get("integrity")
    if not isinstance(integrity, dict):
        return False
    expected = integrity.get("payload_sha256")
    if not isinstance(expected, str):
        return False
    unsigned = {key: value for key, value in document.items() if key != "integrity"}
    return sha256(_canonical_bytes(unsigned)).hexdigest() == expected


def collect_smart_money(
    *,
    ranking_types: Iterable[str] = RANKING_TYPES,
    rows_per_page: int = ROWS_PER_PAGE,
    include_profiles: bool = True,
    get_json: JsonGet = public_json_get,
    timeout: float = 20.0,
    captured_at: str | datetime | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Collect strict TOP30 rankings and optional unique-profile enrichment."""

    selected = tuple(ranking_types)
    if not selected or len(set(selected)) != len(selected):
        raise ContractViolation("ranking_types must be a non-empty unique sequence")
    if timeout <= 0:
        raise ContractViolation("timeout must be positive")
    if clock is not None:
        actual_clock = clock
    elif captured_at is not None:
        fixed_observed_at = parse_utc(captured_at)
        actual_clock = lambda: fixed_observed_at
    else:
        actual_clock = lambda: datetime.now(timezone.utc)
    rankings = tuple(
        _collect_ranking(
            SmartMoneyRequest(ranking_type, rows=rows_per_page),
            get_json=get_json,
            timeout=timeout,
            clock=actual_clock,
        )
        for ranking_type in selected
    )
    update_times = {ranking["lastUpdateTime"] for ranking in rankings}
    if len(update_times) != 1:
        raise ContractViolation(
            "Smart Money lastUpdateTime changed between requested rankings"
        )
    unique_ids = tuple(
        dict.fromkeys(
            row["source_id"]
            for ranking in rankings
            for row in ranking["rows"]
        )
    )
    if include_profiles:
        profile_enrichment = _collect_profiles(
            unique_ids, get_json=get_json, timeout=timeout, clock=actual_clock
        )
    else:
        profile_enrichment = {
            "enabled": False,
            "status": "NOT_REQUESTED",
            "expected": len(unique_ids),
            "completed": 0,
            "failed": 0,
            "coverage_ratio": 0.0,
            "profiles": [],
            "failures": [],
        }
    leaderboard_starts = [
        parse_utc(ranking["observed_window"]["started_at_utc"])
        for ranking in rankings
    ]
    leaderboard_ends = [
        parse_utc(ranking["observed_window"]["completed_at_utc"])
        for ranking in rankings
    ]
    leaderboard_window = _observed_window(
        min(leaderboard_starts), max(leaderboard_ends)
    )
    observed_at = parse_utc(captured_at) if captured_at is not None else _clock_utc(actual_clock)
    latest_observed_end = leaderboard_window["completed_at_utc"]
    profile_window = profile_enrichment.get("observed_window")
    if isinstance(profile_window, dict):
        latest_observed_end = max(
            parse_utc(latest_observed_end),
            parse_utc(profile_window["completed_at_utc"]),
        )
    else:
        latest_observed_end = parse_utc(latest_observed_end)
    if observed_at < latest_observed_end:
        raise ContractViolation(
            "Smart Money captured_at cannot precede the observed request window"
        )
    document = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_system": "binance_futures_smart_money_public_api",
        "source_endpoints": {
            "leaderboard": LEADERBOARD_ENDPOINT,
            "profile": PROFILE_ENDPOINT,
        },
        "access": {
            "network": "PUBLIC_READ_ONLY_HTTP_GET",
            "browser_state": False,
            "credential_access": False,
        },
        "captured_at": format_utc(observed_at),
        "snapshot_semantics": "OBSERVED_WINDOW",
        "leaderboard_observed_window": leaderboard_window,
        "contract": {
            "ranking_types": list(selected),
            "time_range": TIME_RANGE,
            "order": ORDER,
            "rows_per_page": ROWS_PER_PAGE,
            "pages": list(PAGES),
            "expected_rows_per_ranking": 30,
            "rank_source": RANK_SOURCE,
            "source_id_type": SOURCE_ID_TYPE,
            "fixed_filters": {
                "onlyShowSharingPosition": "false",
                "onlyShowSignalEnabled": "false",
            },
        },
        "status": (
            "COMPLETE"
            if profile_enrichment["status"] in {"COMPLETE", "NOT_REQUESTED"}
            else "PARTIAL_PROFILE_ENRICHMENT"
        ),
        "rankings": list(rankings),
        "unique_top_trader_count": len(unique_ids),
        "profile_enrichment": profile_enrichment,
    }
    return _attach_integrity(document)


def default_evidence_filename(document: dict[str, Any]) -> str:
    captured = str(document.get("captured_at", ""))
    stamp = captured.replace("-", "").replace(":", "").replace(".", "")
    ranking_types = document.get("contract", {}).get("ranking_types", [])
    slug = "-".join(str(value).lower() for value in ranking_types)
    return f"smart_money_top30_{slug}_{stamp}.json"


def write_evidence_atomic(
    document: dict[str, Any], output_path: Path
) -> EvidenceWriteReceipt:
    """Write one immutable evidence file via same-directory atomic link."""

    if not verify_evidence_integrity(document):
        raise ContractViolation("Smart Money evidence integrity is invalid")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    file_digest = sha256(rendered).hexdigest()
    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
        )
        temp_path = Path(temp_name)
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, output_path)
        except FileExistsError as exc:
            raise ContractViolation(
                f"Smart Money evidence already exists: {output_path}"
            ) from exc
        directory_fd = os.open(output_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return EvidenceWriteReceipt(
        path=str(output_path),
        file_sha256=file_digest,
        payload_sha256=document["integrity"]["payload_sha256"],
        byte_count=len(rendered),
    )
