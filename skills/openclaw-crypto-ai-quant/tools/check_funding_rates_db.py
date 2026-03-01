#!/usr/bin/env python3
"""Verify funding rates DB freshness and detect anomalies (gaps/outliers/spikes).

This is designed for pipeline gating:
- Human-readable summary is printed to stderr.
- Machine-readable JSON is printed to stdout.

Exit codes:
  0: PASS (or WARN when --fail-on-warn is not set)
  1: WARN (only when --fail-on-warn is set)
  2: FAIL
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "candles_dbs" / "funding_rates.db"


class Status:
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


_STATUS_RANK = {Status.PASS: 0, Status.WARN: 1, Status.FAIL: 2}


def _utc_iso(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    # Use read-only mode to ensure this check never mutates the DB.
    uri = f"file:{db_path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=3.0)
    con.row_factory = sqlite3.Row
    return con


def _worst_status(a: str, b: str) -> str:
    return a if _STATUS_RANK[a] >= _STATUS_RANK[b] else b


def _parse_symbols(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    items = [s.strip().upper() for s in str(raw).split(",") if s.strip()]
    return items or None


@dataclass(frozen=True)
class Thresholds:
    lookback_hours: float
    expected_interval_hours: float
    interval_tolerance_seconds: float

    max_age_warn_hours: float
    max_age_fail_hours: float

    max_gap_warn_hours: float
    max_gap_fail_hours: float

    abs_rate_warn: float
    abs_rate_fail: float

    delta_rate_warn: float
    delta_rate_fail: float


def _get_db_symbols(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT DISTINCT symbol FROM funding_rates ORDER BY symbol ASC").fetchall()
    out: list[str] = []
    for r in rows:
        sym = str(r["symbol"] or "").strip().upper()
        if sym:
            out.append(sym)
    return out


def _iter_rows(con: sqlite3.Connection, *, symbol: str, start_ms: int, end_ms: int) -> Iterable[tuple[int, float]]:
    cur = con.execute(
        """
        SELECT time, funding_rate
        FROM funding_rates
        WHERE symbol = ?
          AND time >= ?
          AND time <= ?
        ORDER BY time ASC
        """,
        (symbol, int(start_ms), int(end_ms)),
    )
    for r in cur:
        try:
            ts_ms = int(r["time"])
            rate = float(r["funding_rate"])
        except Exception:
            continue
        yield ts_ms, rate


def _latest_time_ms(con: sqlite3.Connection, *, symbol: str) -> int | None:
    row = con.execute("SELECT MAX(time) AS t FROM funding_rates WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        return None
    try:
        val = row["t"]
        if val is None:
            return None
        return int(val)
    except Exception:
        return None


def _count_rows(con: sqlite3.Connection, *, symbol: str, start_ms: int, end_ms: int) -> int:
    row = con.execute(
        "SELECT COUNT(*) AS n FROM funding_rates WHERE symbol = ? AND time >= ? AND time <= ?",
        (symbol, int(start_ms), int(end_ms)),
    ).fetchone()
    try:
        return int(row["n"] if row else 0)
    except Exception:
        return 0


def _journal_mode(con: sqlite3.Connection) -> str:
    try:
        row = con.execute("PRAGMA journal_mode").fetchone()
    except Exception:
        return ""
    if row is None:
        return ""
    try:
        return str(row[0] or "").strip().lower()
    except Exception:
        return ""


def _hours(ms: int) -> float:
    return float(ms) / 3_600_000.0


def _finite(x: float) -> bool:
    return not (math.isnan(x) or math.isinf(x))


def check_funding_rates_db(
    db_path: Path,
    *,
    symbols: list[str] | None,
    now_ms: int,
    thresholds: Thresholds,
) -> dict[str, Any]:
    """Run funding DB checks and return a machine-readable result dict."""
    out: dict[str, Any] = {
        "status": Status.PASS,
        "db_path": str(db_path),
        "checked_at_ms": int(now_ms),
        "checked_at_iso": _utc_iso(int(now_ms)),
        "thresholds": {
            "lookback_hours": thresholds.lookback_hours,
            "expected_interval_hours": thresholds.expected_interval_hours,
            "interval_tolerance_seconds": thresholds.interval_tolerance_seconds,
            "max_age_warn_hours": thresholds.max_age_warn_hours,
            "max_age_fail_hours": thresholds.max_age_fail_hours,
            "max_gap_warn_hours": thresholds.max_gap_warn_hours,
            "max_gap_fail_hours": thresholds.max_gap_fail_hours,
            "abs_rate_warn": thresholds.abs_rate_warn,
            "abs_rate_fail": thresholds.abs_rate_fail,
            "delta_rate_warn": thresholds.delta_rate_warn,
            "delta_rate_fail": thresholds.delta_rate_fail,
        },
        "summary": {},
        "symbols": {},
        "issues": [],
        "errors": [],
    }

    if not db_path.exists():
        out["status"] = Status.FAIL
        out["errors"].append({"error": "db_missing", "message": "Database file does not exist."})
        return out

    try:
        con = _connect_readonly(db_path)
    except Exception as e:
        out["status"] = Status.FAIL
        out["errors"].append({"error": "db_open_failed", "message": str(e)})
        return out

    try:
        # Table existence check
        try:
            con.execute("SELECT 1 FROM funding_rates LIMIT 1").fetchone()
        except Exception as e:
            out["status"] = Status.FAIL
            out["errors"].append({"error": "table_missing", "message": f"funding_rates table not readable: {e}"})
            return out

        journal_mode = _journal_mode(con)
        if journal_mode and journal_mode != "wal":
            out["status"] = _worst_status(str(out["status"]), Status.WARN)
            out["issues"].append(
                {
                    "severity": Status.WARN,
                    "type": "journal_mode",
                    "message": f"SQLite journal_mode is '{journal_mode}', expected 'wal' for concurrent readers.",
                }
            )

        db_symbols = _get_db_symbols(con)
        target_symbols = symbols or db_symbols
        if not target_symbols:
            out["status"] = Status.FAIL
            out["errors"].append({"error": "no_symbols", "message": "No symbols found to check."})
            return out

        expected_ms = int(round(thresholds.expected_interval_hours * 3_600_000.0))
        tol_ms = int(round(float(thresholds.interval_tolerance_seconds) * 1000.0))
        lookback_ms = int(round(float(thresholds.lookback_hours) * 3_600_000.0))
        start_ms = int(now_ms) - lookback_ms
        end_ms = int(now_ms)

        # For gap detection at the window boundary, pull a small amount of extra history.
        start_query_ms = start_ms - expected_ms

        total_warn = 0
        total_fail = 0
        total_issues = 0

        for sym in target_symbols:
            sym_status = Status.PASS
            latest = _latest_time_ms(con, symbol=sym)
            sym_obj: dict[str, Any] = {
                "status": Status.PASS,
                "latest_time_ms": latest,
                "latest_time_iso": _utc_iso(latest) if latest is not None else "",
                "age_hours": None,
                "rows_lookback": 0,
                "gaps": [],
                "abs_rate_anomalies": [],
                "delta_rate_anomalies": [],
            }

            if latest is None:
                sym_status = Status.FAIL
                sym_obj["status"] = sym_status
                out["issues"].append(
                    {"severity": Status.FAIL, "symbol": sym, "type": "symbol_missing", "message": "No rows found."}
                )
                out["symbols"][sym] = sym_obj
                continue

            age_ms = int(now_ms) - int(latest)
            age_h = _hours(age_ms)
            sym_obj["age_hours"] = age_h

            if age_h > thresholds.max_age_fail_hours:
                sym_status = _worst_status(sym_status, Status.FAIL)
                out["issues"].append(
                    {
                        "severity": Status.FAIL,
                        "symbol": sym,
                        "type": "stale",
                        "message": f"Latest funding is too old: age={age_h:.2f}h > {thresholds.max_age_fail_hours:g}h.",
                        "latest_time_ms": int(latest),
                    }
                )
            elif age_h > thresholds.max_age_warn_hours:
                sym_status = _worst_status(sym_status, Status.WARN)
                out["issues"].append(
                    {
                        "severity": Status.WARN,
                        "symbol": sym,
                        "type": "stale",
                        "message": f"Latest funding is old: age={age_h:.2f}h > {thresholds.max_age_warn_hours:g}h.",
                        "latest_time_ms": int(latest),
                    }
                )

            sym_obj["rows_lookback"] = _count_rows(con, symbol=sym, start_ms=start_ms, end_ms=end_ms)

            times: list[int] = []
            rates: list[float] = []
            for ts_ms, rate in _iter_rows(con, symbol=sym, start_ms=start_query_ms, end_ms=end_ms):
                times.append(ts_ms)
                rates.append(rate)

            if not times:
                sym_status = _worst_status(sym_status, Status.FAIL)
                out["issues"].append(
                    {
                        "severity": Status.FAIL,
                        "symbol": sym,
                        "type": "no_data_in_window",
                        "message": "No funding rows found within the lookback window.",
                    }
                )
                sym_obj["status"] = sym_status
                out["symbols"][sym] = sym_obj
                continue

            # Gap checks
            max_gap_warn_ms = int(round(thresholds.max_gap_warn_hours * 3_600_000.0))
            max_gap_fail_ms = int(round(thresholds.max_gap_fail_hours * 3_600_000.0))

            # Consider the first row within [start_ms, end_ms]. If it begins too late, we have a leading gap.
            first_in_window_idx = 0
            for i, t in enumerate(times):
                if t >= start_ms:
                    first_in_window_idx = i
                    break
            first_in_window = times[first_in_window_idx]

            lead_gap_ms = int(first_in_window) - int(start_ms)
            if lead_gap_ms > max_gap_warn_ms:
                severity = Status.FAIL if lead_gap_ms > max_gap_fail_ms else Status.WARN
                sym_status = _worst_status(sym_status, severity)
                gap = {
                    "severity": severity,
                    "start_ms": int(start_ms),
                    "end_ms": int(first_in_window - expected_ms),
                    "start_iso": _utc_iso(int(start_ms)),
                    "end_iso": _utc_iso(int(first_in_window - expected_ms)),
                    "gap_hours": _hours(lead_gap_ms),
                }
                sym_obj["gaps"].append(gap)
                out["issues"].append(
                    {
                        "severity": severity,
                        "symbol": sym,
                        "type": "gap",
                        "message": f"Missing funding range at window start: gap={_hours(lead_gap_ms):.2f}h.",
                        "gap": gap,
                    }
                )

            for i in range(first_in_window_idx + 1, len(times)):
                t_prev = int(times[i - 1])
                t_cur = int(times[i])
                diff_ms = t_cur - t_prev
                if diff_ms <= expected_ms + tol_ms:
                    continue

                severity = (
                    Status.FAIL if diff_ms > max_gap_fail_ms else Status.WARN if diff_ms > max_gap_warn_ms else None
                )
                if severity is None:
                    continue

                sym_status = _worst_status(sym_status, severity)
                missing_points_est = max(0, int(round(float(diff_ms) / float(expected_ms))) - 1)
                gap = {
                    "severity": severity,
                    "start_ms": int(t_prev + expected_ms),
                    "end_ms": int(t_cur - expected_ms),
                    "start_iso": _utc_iso(int(t_prev + expected_ms)),
                    "end_iso": _utc_iso(int(t_cur - expected_ms)),
                    "diff_hours": _hours(diff_ms),
                    "missing_points_est": missing_points_est,
                }
                sym_obj["gaps"].append(gap)
                out["issues"].append(
                    {
                        "severity": severity,
                        "symbol": sym,
                        "type": "gap",
                        "message": f"Missing funding range: diff={_hours(diff_ms):.2f}h missing≈{missing_points_est}.",
                        "gap": gap,
                    }
                )

            # Outlier checks (absolute funding rate) and spikes (delta).
            prev_t: int | None = None
            prev_rate: float | None = None
            for ts_ms, rate in zip(times, rates, strict=True):
                if ts_ms < start_ms:
                    prev_t = ts_ms
                    prev_rate = rate
                    continue

                if _finite(rate):
                    abs_rate = abs(rate)
                    if abs_rate > thresholds.abs_rate_fail:
                        sym_status = _worst_status(sym_status, Status.FAIL)
                        sym_obj["abs_rate_anomalies"].append(
                            {"severity": Status.FAIL, "time_ms": ts_ms, "time_iso": _utc_iso(ts_ms), "rate": rate}
                        )
                        out["issues"].append(
                            {
                                "severity": Status.FAIL,
                                "symbol": sym,
                                "type": "abs_rate",
                                "message": f"Funding rate outlier: |rate|={abs_rate:g} > {thresholds.abs_rate_fail:g}.",
                                "time_ms": ts_ms,
                                "rate": rate,
                            }
                        )
                    elif abs_rate > thresholds.abs_rate_warn:
                        sym_status = _worst_status(sym_status, Status.WARN)
                        sym_obj["abs_rate_anomalies"].append(
                            {"severity": Status.WARN, "time_ms": ts_ms, "time_iso": _utc_iso(ts_ms), "rate": rate}
                        )
                        out["issues"].append(
                            {
                                "severity": Status.WARN,
                                "symbol": sym,
                                "type": "abs_rate",
                                "message": f"Funding rate outlier: |rate|={abs_rate:g} > {thresholds.abs_rate_warn:g}.",
                                "time_ms": ts_ms,
                                "rate": rate,
                            }
                        )

                # Delta checks only when adjacent points are close enough (avoid false 'spikes' across gaps).
                if prev_t is not None and prev_rate is not None:
                    if int(ts_ms) - int(prev_t) <= expected_ms + tol_ms and _finite(prev_rate) and _finite(rate):
                        delta = float(rate) - float(prev_rate)
                        abs_delta = abs(delta)
                        if abs_delta > thresholds.delta_rate_fail:
                            sym_status = _worst_status(sym_status, Status.FAIL)
                            sym_obj["delta_rate_anomalies"].append(
                                {
                                    "severity": Status.FAIL,
                                    "time_ms": ts_ms,
                                    "time_iso": _utc_iso(ts_ms),
                                    "rate": rate,
                                    "prev_rate": prev_rate,
                                    "delta": delta,
                                }
                            )
                            out["issues"].append(
                                {
                                    "severity": Status.FAIL,
                                    "symbol": sym,
                                    "type": "delta_rate",
                                    "message": (
                                        f"Funding spike: |delta|={abs_delta:g} > {thresholds.delta_rate_fail:g}."
                                    ),
                                    "time_ms": ts_ms,
                                    "rate": rate,
                                    "prev_rate": prev_rate,
                                    "delta": delta,
                                }
                            )
                        elif abs_delta > thresholds.delta_rate_warn:
                            sym_status = _worst_status(sym_status, Status.WARN)
                            sym_obj["delta_rate_anomalies"].append(
                                {
                                    "severity": Status.WARN,
                                    "time_ms": ts_ms,
                                    "time_iso": _utc_iso(ts_ms),
                                    "rate": rate,
                                    "prev_rate": prev_rate,
                                    "delta": delta,
                                }
                            )
                            out["issues"].append(
                                {
                                    "severity": Status.WARN,
                                    "symbol": sym,
                                    "type": "delta_rate",
                                    "message": (
                                        f"Funding spike: |delta|={abs_delta:g} > {thresholds.delta_rate_warn:g}."
                                    ),
                                    "time_ms": ts_ms,
                                    "rate": rate,
                                    "prev_rate": prev_rate,
                                    "delta": delta,
                                }
                            )

                prev_t = ts_ms
                prev_rate = rate

            sym_obj["status"] = sym_status
            out["symbols"][sym] = sym_obj
            out["status"] = _worst_status(str(out["status"]), sym_status)

        # Summarise issues by severity
        for iss in out["issues"]:
            sev = str(iss.get("severity") or "")
            total_issues += 1
            if sev == Status.FAIL:
                total_fail += 1
            elif sev == Status.WARN:
                total_warn += 1

        out["summary"] = {
            "symbols_checked": len(target_symbols),
            "issues_total": total_issues,
            "issues_warn": total_warn,
            "issues_fail": total_fail,
            "journal_mode": journal_mode or "unknown",
        }
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass


def _print_human_summary(result: dict[str, Any]) -> None:
    status = str(result.get("status") or Status.FAIL)
    db_path = str(result.get("db_path") or "")
    checked_at_iso = str(result.get("checked_at_iso") or "")
    summary = result.get("summary") or {}

    print(f"[funding-check] status={status} checked_at={checked_at_iso}", file=sys.stderr)
    print(f"[funding-check] db={db_path}", file=sys.stderr)
    if summary:
        print(
            "[funding-check] "
            f"symbols={summary.get('symbols_checked')} issues={summary.get('issues_total')} "
            f"warn={summary.get('issues_warn')} fail={summary.get('issues_fail')}",
            file=sys.stderr,
        )

    errors = result.get("errors") or []
    if errors:
        for e in errors[:20]:
            print(f"[funding-check] ERROR: {e}", file=sys.stderr)

    issues = result.get("issues") or []
    if issues:
        # Print the first N issues; JSON contains full detail.
        for iss in issues[:50]:
            sev = iss.get("severity")
            sym = iss.get("symbol", "")
            typ = iss.get("type", "")
            msg = iss.get("message", "")
            print(f"[funding-check] {sev} {sym} {typ}: {msg}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify funding_rates.db freshness and anomalies (gaps/outliers/spikes).")
    ap.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    ap.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbol list. Default: check all symbols present in the DB.",
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--lookback-hours", type=float, default=72.0, help="Lookback window in hours (default: 72).")
    group.add_argument("--lookback-days", type=float, default=None, help="Lookback window in days.")

    ap.add_argument(
        "--expected-interval-hours",
        type=float,
        default=1.0,
        help="Expected funding interval in hours (default: 1).",
    )
    ap.add_argument(
        "--interval-tolerance-seconds",
        type=float,
        default=60.0,
        help="Tolerance for timestamp jitter when detecting gaps/spikes (default: 60).",
    )

    ap.add_argument(
        "--max-age-warn-multiplier",
        type=float,
        default=8.0,
        help="Warn if latest age exceeds expected_interval_hours * multiplier (default: 8).",
    )
    ap.add_argument(
        "--max-age-fail-multiplier",
        type=float,
        default=12.0,
        help="Fail if latest age exceeds expected_interval_hours * multiplier (default: 12).",
    )
    ap.add_argument("--max-age-warn-hours", type=float, default=None, help="Override warn age threshold in hours.")
    ap.add_argument("--max-age-fail-hours", type=float, default=None, help="Override fail age threshold in hours.")

    ap.add_argument(
        "--warn-gap-hours",
        type=float,
        default=2.0,
        help="Warn if consecutive rows differ by more than this many hours (default: 2).",
    )
    ap.add_argument(
        "--max-gap-hours",
        type=float,
        default=4.0,
        help="Fail if consecutive rows differ by more than this many hours (default: 4).",
    )

    ap.add_argument(
        "--abs-rate-warn",
        type=float,
        default=0.01,
        help="Warn if abs(funding_rate) exceeds this value (default: 0.01).",
    )
    ap.add_argument(
        "--abs-rate-fail",
        type=float,
        default=0.02,
        help="Fail if abs(funding_rate) exceeds this value (default: 0.02).",
    )
    ap.add_argument(
        "--delta-rate-warn",
        type=float,
        default=0.01,
        help="Warn if abs(delta funding_rate) exceeds this value (default: 0.01).",
    )
    ap.add_argument(
        "--delta-rate-fail",
        type=float,
        default=0.02,
        help="Fail if abs(delta funding_rate) exceeds this value (default: 0.02).",
    )
    ap.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit non-zero when status is WARN (default: WARN exits 0).",
    )
    ap.add_argument(
        "--now-ms",
        type=int,
        default=None,
        help="Override current time (epoch milliseconds). Intended for tests.",
    )
    args = ap.parse_args()

    lookback_hours = float(args.lookback_hours)
    if args.lookback_days is not None:
        lookback_hours = float(args.lookback_days) * 24.0

    expected_interval_hours = float(args.expected_interval_hours)
    max_age_warn_hours = (
        float(args.max_age_warn_hours)
        if args.max_age_warn_hours is not None
        else expected_interval_hours * float(args.max_age_warn_multiplier)
    )
    max_age_fail_hours = (
        float(args.max_age_fail_hours)
        if args.max_age_fail_hours is not None
        else expected_interval_hours * float(args.max_age_fail_multiplier)
    )

    if max_age_warn_hours > max_age_fail_hours:
        raise SystemExit("--max-age-warn-hours must be <= --max-age-fail-hours (or their multiplier equivalents)")

    if float(args.warn_gap_hours) > float(args.max_gap_hours):
        raise SystemExit("--warn-gap-hours must be <= --max-gap-hours")

    thresholds = Thresholds(
        lookback_hours=lookback_hours,
        expected_interval_hours=expected_interval_hours,
        interval_tolerance_seconds=float(args.interval_tolerance_seconds),
        max_age_warn_hours=max_age_warn_hours,
        max_age_fail_hours=max_age_fail_hours,
        max_gap_warn_hours=float(args.warn_gap_hours),
        max_gap_fail_hours=float(args.max_gap_hours),
        abs_rate_warn=float(args.abs_rate_warn),
        abs_rate_fail=float(args.abs_rate_fail),
        delta_rate_warn=float(args.delta_rate_warn),
        delta_rate_fail=float(args.delta_rate_fail),
    )

    now_ms = int(args.now_ms) if args.now_ms is not None else int(time.time() * 1000)
    symbols = _parse_symbols(args.symbols)

    result = check_funding_rates_db(Path(args.db), symbols=symbols, now_ms=now_ms, thresholds=thresholds)
    _print_human_summary(result)

    # JSON output for pipeline consumption.
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))

    status = str(result.get("status") or Status.FAIL)
    if status == Status.FAIL:
        raise SystemExit(2)
    if status == Status.WARN and bool(args.fail_on_warn):
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
