#!/usr/bin/env python3
"""Audit action-level alignment between live and paper trading databases."""

from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

try:
    from reason_codes import classify_reason_code
except ModuleNotFoundError:  # pragma: no cover - module execution path
    from tools.reason_codes import classify_reason_code

SIDE_ACTIONS = {"OPEN", "ADD", "REDUCE", "CLOSE"}
FUNDING_ACTION = "FUNDING"
TRADE_ACTIONS = SIDE_ACTIONS | {FUNDING_ACTION}
DEFAULT_TOL = 1e-9


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit live-vs-paper action parity from SQLite trade logs.")
    parser.add_argument("--live-db", required=True, help="Path to live SQLite DB")
    parser.add_argument("--paper-db", required=True, help="Path to paper SQLite DB")
    parser.add_argument(
        "--paper-min-id-exclusive",
        type=int,
        help="Optional lower-bound filter: include only paper trades with id > this value.",
    )
    parser.add_argument(
        "--paper-seed-watermark",
        help=(
            "Optional JSON watermark file generated during seed step "
            "(expects key pre_seed_max_trade_id)."
        ),
    )
    parser.add_argument("--output", required=True, help="Path to output JSON report")
    parser.add_argument("--from-ts", type=int, help="Filter start timestamp (ms, inclusive)")
    parser.add_argument("--to-ts", type=int, help="Filter end timestamp (ms, inclusive)")
    parser.add_argument(
        "--timestamp-bucket-ms",
        type=int,
        default=1,
        help="Match timestamp bucket in milliseconds (1 = exact millisecond match)",
    )
    parser.add_argument("--price-tol", type=float, default=DEFAULT_TOL, help="Absolute tolerance for price comparison")
    parser.add_argument("--size-tol", type=float, default=DEFAULT_TOL, help="Absolute tolerance for size comparison")
    parser.add_argument("--pnl-tol", type=float, default=DEFAULT_TOL, help="Absolute tolerance for pnl comparison")
    parser.add_argument("--fee-tol", type=float, default=DEFAULT_TOL, help="Absolute tolerance for fee comparison")
    parser.add_argument("--balance-tol", type=float, default=DEFAULT_TOL, help="Absolute tolerance for balance comparison")
    parser.add_argument("--fail-on-mismatch", action="store_true", default=False, help="Return exit code 1 when strict parity fails")
    return parser


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _parse_timestamp_ms(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        iv = int(value)
        if iv > 10_000_000_000:
            return iv
        return max(0, iv * 1000)

    raw = str(value).strip()
    if not raw:
        return 0
    if raw.isdigit():
        iv = int(raw)
        if iv > 10_000_000_000:
            return iv
        return iv * 1000
    try:
        ts = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(ts.timestamp() * 1000)
    except Exception:
        return 0


def _normalise_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalise_side(value: Any) -> str:
    side = str(value or "").strip().upper()
    if side in {"LONG", "SHORT"}:
        return side
    return ""


def _normalise_confidence(value: Any) -> str:
    conf = str(value or "").strip().lower()
    if conf in {"low", "medium", "high"}:
        return conf
    return conf


def _almost_equal(left: float, right: float, tol: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tol)


def _bucket_timestamp_ms(ts_ms: int, bucket_ms: int) -> int:
    if bucket_ms <= 1:
        return int(ts_ms)
    if ts_ms >= 0:
        return int((ts_ms // bucket_ms) * bucket_ms)
    return int(-(((-ts_ms) // bucket_ms) * bucket_ms))


def _canonical_action(action: Any, side: Any) -> str:
    act = str(action or "").strip().upper()
    if act in SIDE_ACTIONS:
        s = _normalise_side(side)
        if not s:
            return ""
        return f"{act}_{s}"
    if act == FUNDING_ACTION:
        return FUNDING_ACTION
    return ""


def _resolve_paper_min_id_exclusive(
    *,
    raw_min_id: int | None,
    watermark_path_raw: str | None,
) -> int | None:
    resolved: int | None = int(raw_min_id) if raw_min_id is not None else None
    if not watermark_path_raw:
        return resolved

    watermark_path = Path(str(watermark_path_raw)).expanduser().resolve()
    if not watermark_path.exists():
        raise ValueError(f"paper seed watermark file not found: {watermark_path}")

    try:
        payload = json.loads(watermark_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid paper seed watermark JSON: {watermark_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid paper seed watermark payload: {watermark_path}")

    raw_watermark = payload.get("pre_seed_max_trade_id")
    if raw_watermark is None:
        raise ValueError(
            f"paper seed watermark missing pre_seed_max_trade_id: {watermark_path}"
        )
    try:
        watermark_value = int(raw_watermark)
    except Exception as exc:
        raise ValueError(
            f"invalid pre_seed_max_trade_id in paper seed watermark: {watermark_path}"
        ) from exc

    if resolved is None:
        return int(watermark_value)
    return max(int(resolved), int(watermark_value))


def _load_actions(
    db_path: Path,
    *,
    source_name: str,
    min_source_id_exclusive: int | None,
    from_ts: int | None,
    to_ts: int | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn = _connect_ro(db_path)
    try:
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
        has_reason_code = "reason_code" in cols
        if has_reason_code:
            rows = conn.execute(
                "SELECT id, timestamp, symbol, action, type, price, size, pnl, balance, reason, reason_code, confidence, fee_usd "
                "FROM trades ORDER BY id ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, timestamp, symbol, action, type, price, size, pnl, balance, reason, confidence, fee_usd "
                "FROM trades ORDER BY id ASC"
            ).fetchall()
    finally:
        conn.close()

    actions: list[dict[str, Any]] = []
    unknown_actions = 0
    filtered_by_id = 0

    for row in rows:
        source_id = int(row["id"] or 0)
        if min_source_id_exclusive is not None and source_id <= min_source_id_exclusive:
            filtered_by_id += 1
            continue
        action = str(row["action"] or "").strip().upper()
        if action not in TRADE_ACTIONS:
            continue

        ts_ms = _parse_timestamp_ms(row["timestamp"])
        if from_ts is not None and ts_ms < from_ts:
            continue
        if to_ts is not None and ts_ms > to_ts:
            continue

        action_code = _canonical_action(action, row["type"])
        if not action_code:
            unknown_actions += 1
            continue

        symbol = _normalise_symbol(row["symbol"])
        if not symbol or ts_ms <= 0:
            continue

        actions.append(
            {
                "source": source_name,
                "source_id": source_id,
                "symbol": symbol,
                "timestamp_ms": ts_ms,
                "action_code": action_code,
                "price": _parse_float(row["price"]),
                "size": _parse_float(row["size"]),
                "pnl_usd": _parse_float(row["pnl"]),
                "fee_usd": _parse_float(row["fee_usd"]),
                "balance": _parse_float(row["balance"]),
                "confidence": _normalise_confidence(row["confidence"]),
                "reason": str(row["reason"] or ""),
                "reason_code": (
                    str(row["reason_code"] or "").strip().lower()
                    if "reason_code" in row.keys()
                    else classify_reason_code(action_code, str(row["reason"] or ""))
                )
                or classify_reason_code(action_code, str(row["reason"] or "")),
            }
        )

    actions.sort(key=lambda r: (r["timestamp_ms"], r["symbol"], r["action_code"], r["source_id"]))
    counts = {
        f"{source_name}_canonical_actions": len(actions),
        f"{source_name}_unknown_actions": unknown_actions,
        f"{source_name}_filtered_by_id": filtered_by_id,
    }
    return actions, counts


def _group_events(
    rows: list[dict[str, Any]],
    *,
    timestamp_bucket_ms: int,
) -> dict[tuple[str, str, int], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["symbol"], row["action_code"], _bucket_timestamp_ms(int(row["timestamp_ms"]), timestamp_bucket_ms))
        grouped[key].append(row)
    for values in grouped.values():
        values.sort(
            key=lambda r: (
                float(r["size"]),
                float(r["pnl_usd"]),
                float(r["fee_usd"]),
                float(r["price"]),
                float(r["balance"]),
                int(r["source_id"]),
            )
        )
    return grouped


def _compare_actions(
    live_actions: list[dict[str, Any]],
    paper_actions: list[dict[str, Any]],
    *,
    timestamp_bucket_ms: int,
    price_tol: float,
    size_tol: float,
    pnl_tol: float,
    fee_tol: float,
    balance_tol: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    mismatches: list[dict[str, Any]] = []
    matched_pairs = 0
    numeric_mismatch = 0
    confidence_mismatch = 0
    reason_code_mismatch = 0
    unmatched_live = 0
    unmatched_paper = 0
    non_simulatable_residuals = 0

    per_symbol: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "symbol": "",
            "live_actions": 0,
            "paper_actions": 0,
            "matched_pairs": 0,
            "live_pnl_usd": 0.0,
            "paper_pnl_usd": 0.0,
            "live_fee_usd": 0.0,
            "paper_fee_usd": 0.0,
        }
    )

    for row in live_actions:
        stats = per_symbol[row["symbol"]]
        stats["symbol"] = row["symbol"]
        stats["live_actions"] += 1
        stats["live_pnl_usd"] += float(row["pnl_usd"])
        stats["live_fee_usd"] += float(row["fee_usd"])

    for row in paper_actions:
        stats = per_symbol[row["symbol"]]
        stats["symbol"] = row["symbol"]
        stats["paper_actions"] += 1
        stats["paper_pnl_usd"] += float(row["pnl_usd"])
        stats["paper_fee_usd"] += float(row["fee_usd"])

    live_groups = _group_events(live_actions, timestamp_bucket_ms=timestamp_bucket_ms)
    paper_groups = _group_events(paper_actions, timestamp_bucket_ms=timestamp_bucket_ms)
    all_keys = sorted(set(live_groups.keys()) | set(paper_groups.keys()))

    for key in all_keys:
        symbol, action_code, ts_ms = key
        live_rows = live_groups.get(key, [])
        paper_rows = paper_groups.get(key, [])
        pair_count = min(len(live_rows), len(paper_rows))

        for idx in range(pair_count):
            lrow = live_rows[idx]
            prow = paper_rows[idx]
            per_symbol[symbol]["matched_pairs"] += 1
            matched_pairs += 1

            numeric_checks = {
                "price": _almost_equal(lrow["price"], prow["price"], price_tol),
                "size": _almost_equal(lrow["size"], prow["size"], size_tol),
                "pnl_usd": _almost_equal(lrow["pnl_usd"], prow["pnl_usd"], pnl_tol),
                "fee_usd": _almost_equal(lrow["fee_usd"], prow["fee_usd"], fee_tol),
                "balance": _almost_equal(lrow["balance"], prow["balance"], balance_tol),
            }
            has_numeric_mismatch = not all(numeric_checks.values())

            live_conf = str(lrow["confidence"] or "")
            paper_conf = str(prow["confidence"] or "")
            has_confidence_mismatch = bool(live_conf and paper_conf and live_conf != paper_conf)
            live_reason_code = str(lrow["reason_code"] or "")
            paper_reason_code = str(prow["reason_code"] or "")
            has_reason_code_mismatch = bool(
                live_reason_code and paper_reason_code and live_reason_code != paper_reason_code
            )

            if not has_numeric_mismatch and not has_confidence_mismatch and not has_reason_code_mismatch:
                continue

            if has_numeric_mismatch:
                numeric_mismatch += 1
            if has_confidence_mismatch:
                confidence_mismatch += 1
            if has_reason_code_mismatch:
                reason_code_mismatch += 1

            classification = "numeric_policy_divergence" if has_numeric_mismatch else "deterministic_logic_divergence"
            if has_numeric_mismatch:
                kind = "action_numeric_mismatch"
            elif has_reason_code_mismatch:
                kind = "reason_code_mismatch"
            else:
                kind = "confidence_mismatch"
            mismatches.append(
                {
                    "classification": classification,
                    "kind": kind,
                    "symbol": symbol,
                    "action_code": action_code,
                    "match_key_timestamp_ms": ts_ms,
                    "live_timestamp_ms": lrow["timestamp_ms"],
                    "paper_timestamp_ms": prow["timestamp_ms"],
                    "live_ref": {"id": lrow["source_id"]},
                    "paper_ref": {"id": prow["source_id"]},
                    "live_reason_code": live_reason_code,
                    "paper_reason_code": paper_reason_code,
                    "delta": {
                        "price": lrow["price"] - prow["price"],
                        "size": lrow["size"] - prow["size"],
                        "pnl_usd": lrow["pnl_usd"] - prow["pnl_usd"],
                        "fee_usd": lrow["fee_usd"] - prow["fee_usd"],
                        "balance": lrow["balance"] - prow["balance"],
                    },
                    "flags": {
                        "numeric_mismatch": has_numeric_mismatch,
                        "confidence_mismatch": has_confidence_mismatch,
                        "reason_code_mismatch": has_reason_code_mismatch,
                    },
                }
            )

        if len(live_rows) > pair_count:
            for lrow in live_rows[pair_count:]:
                if action_code == FUNDING_ACTION:
                    non_simulatable_residuals += 1
                    mismatches.append(
                        {
                            "classification": "non-simulatable_exchange_oms_effect",
                            "kind": "missing_paper_funding_action",
                            "symbol": symbol,
                            "action_code": action_code,
                            "match_key_timestamp_ms": ts_ms,
                            "live_timestamp_ms": lrow["timestamp_ms"],
                            "live_ref": {"id": lrow["source_id"]},
                        }
                    )
                else:
                    unmatched_live += 1
                    mismatches.append(
                        {
                            "classification": "deterministic_logic_divergence",
                            "kind": "missing_paper_action",
                            "symbol": symbol,
                            "action_code": action_code,
                            "match_key_timestamp_ms": ts_ms,
                            "live_timestamp_ms": lrow["timestamp_ms"],
                            "live_ref": {"id": lrow["source_id"]},
                        }
                    )

        if len(paper_rows) > pair_count:
            for prow in paper_rows[pair_count:]:
                if action_code == FUNDING_ACTION:
                    non_simulatable_residuals += 1
                    mismatches.append(
                        {
                            "classification": "non-simulatable_exchange_oms_effect",
                            "kind": "missing_live_funding_action",
                            "symbol": symbol,
                            "action_code": action_code,
                            "match_key_timestamp_ms": ts_ms,
                            "paper_timestamp_ms": prow["timestamp_ms"],
                            "paper_ref": {"id": prow["source_id"]},
                        }
                    )
                else:
                    unmatched_paper += 1
                    mismatches.append(
                        {
                            "classification": "deterministic_logic_divergence",
                            "kind": "missing_live_action",
                            "symbol": symbol,
                            "action_code": action_code,
                            "match_key_timestamp_ms": ts_ms,
                            "paper_timestamp_ms": prow["timestamp_ms"],
                            "paper_ref": {"id": prow["source_id"]},
                        }
                    )

    per_symbol_rows = sorted(
        (
            {
                **values,
                "pnl_delta_usd": values["live_pnl_usd"] - values["paper_pnl_usd"],
                "fee_delta_usd": values["live_fee_usd"] - values["paper_fee_usd"],
            }
            for values in per_symbol.values()
        ),
        key=lambda row: row["symbol"],
    )

    summary = {
        "matched_pairs": matched_pairs,
        "numeric_mismatch": numeric_mismatch,
        "confidence_mismatch": confidence_mismatch,
        "reason_code_mismatch": reason_code_mismatch,
        "unmatched_live": unmatched_live,
        "unmatched_paper": unmatched_paper,
        "non_simulatable_residuals": non_simulatable_residuals,
    }
    return mismatches, summary, per_symbol_rows


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    live_db = Path(args.live_db).expanduser().resolve()
    paper_db = Path(args.paper_db).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    from_ts = int(args.from_ts) if args.from_ts is not None else None
    to_ts = int(args.to_ts) if args.to_ts is not None else None
    try:
        paper_min_id_exclusive = _resolve_paper_min_id_exclusive(
            raw_min_id=int(args.paper_min_id_exclusive)
            if args.paper_min_id_exclusive is not None
            else None,
            watermark_path_raw=str(args.paper_seed_watermark).strip()
            if args.paper_seed_watermark
            else None,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if not live_db.exists():
        parser.error(f"live DB not found: {live_db}")
    if not paper_db.exists():
        parser.error(f"paper DB not found: {paper_db}")
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        parser.error("from-ts must be <= to-ts")

    live_actions, live_counts = _load_actions(
        live_db,
        source_name="live",
        min_source_id_exclusive=None,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    paper_actions, paper_counts = _load_actions(
        paper_db,
        source_name="paper",
        min_source_id_exclusive=paper_min_id_exclusive,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    mismatches, compare_summary, per_symbol_rows = _compare_actions(
        live_actions,
        paper_actions,
        timestamp_bucket_ms=max(1, int(args.timestamp_bucket_ms)),
        price_tol=float(args.price_tol),
        size_tol=float(args.size_tol),
        pnl_tol=float(args.pnl_tol),
        fee_tol=float(args.fee_tol),
        balance_tol=float(args.balance_tol),
    )

    mismatch_counts: dict[str, int] = defaultdict(int)
    for item in mismatches:
        mismatch_counts[str(item.get("classification") or "unknown")] += 1

    accepted_residuals = [m for m in mismatches if m.get("classification") == "non-simulatable_exchange_oms_effect"]
    strict_alignment_pass = (
        compare_summary["numeric_mismatch"] == 0
        and compare_summary["confidence_mismatch"] == 0
        and compare_summary["reason_code_mismatch"] == 0
        and compare_summary["unmatched_live"] == 0
        and compare_summary["unmatched_paper"] == 0
    )
    live_simulatable_actions = sum(1 for row in live_actions if str(row.get("action_code") or "") != FUNDING_ACTION)
    paper_window_not_replayed = (
        len(paper_actions) == 0
        and live_simulatable_actions > 0
        and compare_summary["matched_pairs"] == 0
        and compare_summary["numeric_mismatch"] == 0
        and compare_summary["confidence_mismatch"] == 0
        and compare_summary["reason_code_mismatch"] == 0
        and compare_summary["unmatched_live"] == live_simulatable_actions
        and compare_summary["unmatched_paper"] == 0
    )
    if paper_window_not_replayed:
        accepted_residuals.append(
            {
                "classification": "state_initialisation_gap",
                "kind": "paper_window_not_replayed",
                "live_simulatable_actions": int(live_simulatable_actions),
                "paper_simulatable_actions": int(len(paper_actions)),
            }
        )
        strict_alignment_pass = True

    report = {
        "schema_version": 1,
        "generated_at_ms": int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000),
        "inputs": {
            "live_db": str(live_db),
            "paper_db": str(paper_db),
            "paper_min_id_exclusive": int(paper_min_id_exclusive)
            if paper_min_id_exclusive is not None
            else None,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "timestamp_bucket_ms": max(1, int(args.timestamp_bucket_ms)),
            "price_tol": float(args.price_tol),
            "size_tol": float(args.size_tol),
            "pnl_tol": float(args.pnl_tol),
            "fee_tol": float(args.fee_tol),
            "balance_tol": float(args.balance_tol),
        },
        "counts": {
            **live_counts,
            **paper_counts,
            **compare_summary,
            "mismatch_total": len(mismatches),
        },
        "status": {
            "strict_alignment_pass": strict_alignment_pass,
            "accepted_residuals_only": strict_alignment_pass and bool(accepted_residuals),
        },
        "mismatch_counts_by_classification": dict(sorted(mismatch_counts.items(), key=lambda x: x[0])),
        "accepted_residuals": accepted_residuals,
        "per_symbol": per_symbol_rows,
        "mismatches": mismatches,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.as_posix())

    if args.fail_on_mismatch and not strict_alignment_pass:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
