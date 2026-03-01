#!/usr/bin/env python3
"""Build a unified CPU/GPU smoke parity report for lane A and lane B.

Lane definitions:
- Lane A: identical symbol universe parity mode (CPU/GPU pre-aligned before scoring).
- Lane B: production behaviour (GPU kernel symbol-cap truncation may apply).

Inputs are sweep JSONL artefacts (one JSON object per combo) that include
`overrides`, `total_pnl`, and `total_trades` fields.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TOP_K = (1, 3, 5, 10)
REQUIRED_BASELINE_METRICS = (
    "max_abs_total_pnl_diff",
    "mean_abs_total_pnl_diff",
    "trade_count_mismatch_count",
)


@dataclass(frozen=True)
class RankingThresholds:
    min_spearman: float
    min_top3_overlap: int
    require_top1_match: bool


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"{path}:{lineno}: expected JSON object")
            rows.append(obj)
    return rows


def _normalise_overrides(raw_overrides: Any) -> list[tuple[str, Any]]:
    if isinstance(raw_overrides, dict):
        return [(str(k), v) for k, v in raw_overrides.items()]
    if isinstance(raw_overrides, list):
        out: list[tuple[str, Any]] = []
        for pair in raw_overrides:
            if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
                raise ValueError("Invalid overrides item (expected [key, value])")
            out.append((str(pair[0]), pair[1]))
        return out
    raise ValueError("Invalid overrides type (expected object or list-of-pairs)")


def _canon_value(value: Any, round_dp: int | None) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        fv = float(int(value))
    elif isinstance(value, (int, float)):
        fv = float(value)
    else:
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return str(value)

    if not math.isfinite(fv):
        return str(fv)
    if round_dp is not None:
        fv = round(fv, round_dp)
    if fv == 0.0:
        fv = 0.0
    return fv


def canon_overrides_key(raw_overrides: Any, round_dp: int | None = 12) -> tuple[tuple[str, Any], ...]:
    items = _normalise_overrides(raw_overrides)
    normalised = [(k, _canon_value(v, round_dp)) for (k, v) in items]
    normalised.sort(key=lambda item: item[0])
    return tuple(normalised)


def _format_overrides(key: tuple[tuple[str, Any], ...]) -> str:
    parts: list[str] = []
    for name, value in key:
        if isinstance(value, float):
            parts.append(f"{name}={value:.12g}")
        else:
            parts.append(f"{name}={value}")
    return ", ".join(parts)


def _as_float(row: dict[str, Any], metric: str, source: str, key: tuple[tuple[str, Any], ...]) -> float:
    if metric not in row:
        raise ValueError(f"{source}: missing metric '{metric}' for overrides: {_format_overrides(key)}")
    value = row[metric]
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{source}: metric '{metric}' is non-numeric ({value!r}) for overrides: {_format_overrides(key)}"
        ) from exc


def _index_rows(
    rows: list[dict[str, Any]], source: str, round_dp: int | None = 12
) -> dict[tuple[tuple[str, Any], ...], dict[str, Any]]:
    indexed: dict[tuple[tuple[str, Any], ...], dict[str, Any]] = {}
    for idx, row in enumerate(rows, start=1):
        if "overrides" not in row:
            raise ValueError(f"{source}: row {idx} is missing 'overrides'")
        key = canon_overrides_key(row["overrides"], round_dp=round_dp)
        if key in indexed:
            raise ValueError(f"{source}: duplicate overrides row: {_format_overrides(key)}")
        indexed[key] = row
    return indexed


def _rank_keys_by_total_pnl(
    indexed_rows: dict[tuple[tuple[str, Any], ...], dict[str, Any]],
    keys: set[tuple[tuple[str, Any], ...]],
    source: str,
) -> list[tuple[tuple[str, Any], ...]]:
    def _sort_key(k: tuple[tuple[str, Any], ...]) -> tuple[float, str]:
        pnl = _as_float(indexed_rows[k], "total_pnl", source, k)
        return (-pnl, _format_overrides(k))

    return sorted(keys, key=_sort_key)


def _spearman_rho(order_a: list[tuple[tuple[str, Any], ...]], order_b: list[tuple[tuple[str, Any], ...]]) -> float:
    if len(order_a) != len(order_b):
        raise ValueError("Spearman input lists must have equal length")
    n = len(order_a)
    if n <= 1:
        return 1.0
    pos_a = {key: i + 1 for i, key in enumerate(order_a)}
    pos_b = {key: i + 1 for i, key in enumerate(order_b)}
    d2_sum = 0
    for key, rank_a in pos_a.items():
        rank_b = pos_b[key]
        d = rank_a - rank_b
        d2_sum += d * d
    return 1.0 - (6.0 * d2_sum) / (n * (n * n - 1))


def _top_k_overlap(
    ranked_cpu: list[tuple[tuple[str, Any], ...]],
    ranked_gpu: list[tuple[tuple[str, Any], ...]],
    k: int,
) -> tuple[int, int]:
    k_eff = min(k, len(ranked_cpu), len(ranked_gpu))
    if k_eff <= 0:
        return 0, 0
    cpu_top = set(ranked_cpu[:k_eff])
    gpu_top = set(ranked_gpu[:k_eff])
    return len(cpu_top & gpu_top), k_eff


def build_lane_report(
    *,
    lane_name: str,
    cpu_path: Path,
    gpu_path: Path,
    pnl_abs_tol: float,
    trade_abs_tol: float,
    top_ks: tuple[int, ...],
    thresholds: RankingThresholds,
) -> dict[str, Any]:
    cpu_rows = _read_jsonl(cpu_path)
    gpu_rows = _read_jsonl(gpu_path)
    cpu_idx = _index_rows(cpu_rows, f"{lane_name}/CPU")
    gpu_idx = _index_rows(gpu_rows, f"{lane_name}/GPU")

    cpu_keys = set(cpu_idx)
    gpu_keys = set(gpu_idx)
    matched_keys = cpu_keys & gpu_keys
    missing_in_gpu = cpu_keys - gpu_keys
    missing_in_cpu = gpu_keys - cpu_keys

    pnl_abs_diffs: list[float] = []
    trades_abs_diffs: list[float] = []
    any_mismatch_count = 0
    trade_count_mismatch_count = 0

    for key in sorted(matched_keys, key=_format_overrides):
        cpu_pnl = _as_float(cpu_idx[key], "total_pnl", f"{lane_name}/CPU", key)
        gpu_pnl = _as_float(gpu_idx[key], "total_pnl", f"{lane_name}/GPU", key)
        pnl_diff = abs(cpu_pnl - gpu_pnl)
        pnl_abs_diffs.append(pnl_diff)
        if pnl_diff > pnl_abs_tol:
            any_mismatch_count += 1

        cpu_trades = _as_float(cpu_idx[key], "total_trades", f"{lane_name}/CPU", key)
        gpu_trades = _as_float(gpu_idx[key], "total_trades", f"{lane_name}/GPU", key)
        trades_diff = abs(cpu_trades - gpu_trades)
        trades_abs_diffs.append(trades_diff)
        if trades_diff > trade_abs_tol:
            trade_count_mismatch_count += 1

    max_abs_total_pnl_diff = max(pnl_abs_diffs) if pnl_abs_diffs else 0.0
    mean_abs_total_pnl_diff = statistics.fmean(pnl_abs_diffs) if pnl_abs_diffs else 0.0
    max_abs_total_trades_diff = max(trades_abs_diffs) if trades_abs_diffs else 0.0
    mean_abs_total_trades_diff = statistics.fmean(trades_abs_diffs) if trades_abs_diffs else 0.0

    ranked_cpu = _rank_keys_by_total_pnl(cpu_idx, matched_keys, f"{lane_name}/CPU")
    ranked_gpu = _rank_keys_by_total_pnl(gpu_idx, matched_keys, f"{lane_name}/GPU")

    overlaps: dict[str, dict[str, int]] = {}
    for k in top_ks:
        overlap, k_eff = _top_k_overlap(ranked_cpu, ranked_gpu, k)
        overlaps[f"top_{k}"] = {
            "overlap": overlap,
            "effective_k": k_eff,
        }

    top1_match = bool(ranked_cpu and ranked_gpu and ranked_cpu[0] == ranked_gpu[0])
    spearman_rho = _spearman_rho(ranked_cpu, ranked_gpu)

    top3_overlap = overlaps.get("top_3", {"overlap": 0, "effective_k": 0})
    top3_threshold = min(thresholds.min_top3_overlap, top3_overlap["effective_k"])

    ranking_assertions = {
        "top1_match": {
            "value": top1_match,
            "required": thresholds.require_top1_match,
            "pass": (not thresholds.require_top1_match) or top1_match,
        },
        "top3_overlap": {
            "value": top3_overlap["overlap"],
            "threshold": top3_threshold,
            "pass": top3_overlap["overlap"] >= top3_threshold,
        },
        "spearman_rho": {
            "value": spearman_rho,
            "threshold": thresholds.min_spearman,
            "pass": spearman_rho >= thresholds.min_spearman,
        },
    }

    ranking_all_pass = all(item["pass"] for item in ranking_assertions.values())

    return {
        "lane": lane_name,
        "inputs": {
            "cpu": str(cpu_path),
            "gpu": str(gpu_path),
        },
        "rows": {
            "cpu": len(cpu_rows),
            "gpu": len(gpu_rows),
            "matched": len(matched_keys),
            "missing_in_gpu": len(missing_in_gpu),
            "missing_in_cpu": len(missing_in_cpu),
        },
        "parity": {
            "any_mismatch_count": any_mismatch_count,
            "max_abs_total_pnl_diff": max_abs_total_pnl_diff,
            "mean_abs_total_pnl_diff": mean_abs_total_pnl_diff,
            "trade_count_mismatch_count": trade_count_mismatch_count,
            "max_abs_total_trades_diff": max_abs_total_trades_diff,
            "mean_abs_total_trades_diff": mean_abs_total_trades_diff,
            "pnl_abs_tol": pnl_abs_tol,
            "trade_abs_tol": trade_abs_tol,
        },
        "ranking": {
            "top_k_overlap": overlaps,
            "top1_cpu": _format_overrides(ranked_cpu[0]) if ranked_cpu else None,
            "top1_gpu": _format_overrides(ranked_gpu[0]) if ranked_gpu else None,
            "spearman_rho": spearman_rho,
            "assertions": ranking_assertions,
            "all_pass": ranking_all_pass,
        },
    }


def _load_optional_json(path: Path | None) -> Any:
    if path is None:
        return {"status": "not_provided"}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _baseline_comparison(lane_a: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    provided = {
        "any_mismatch_count": args.baseline_any_mismatch_count,
        "max_abs_total_pnl_diff": args.baseline_max_abs_total_pnl_diff,
        "mean_abs_total_pnl_diff": args.baseline_mean_abs_total_pnl_diff,
        "trade_count_mismatch_count": args.baseline_trade_count_mismatch_count,
    }
    provided_non_null = {k: v for (k, v) in provided.items() if v is not None}
    if not provided_non_null:
        return {"status": "not_provided"}

    lane_metrics = lane_a["parity"]
    checks: dict[str, dict[str, Any]] = {}
    for metric, baseline_value in provided_non_null.items():
        current_value = lane_metrics[metric]
        checks[metric] = {
            "baseline": baseline_value,
            "current": current_value,
            "improved_or_equal": current_value <= baseline_value,
        }

    missing_required_metrics = [metric for metric in REQUIRED_BASELINE_METRICS if metric not in provided_non_null]
    if missing_required_metrics:
        return {
            "status": "incomplete",
            "checks": checks,
            "required_metrics": list(REQUIRED_BASELINE_METRICS),
            "missing_required_metrics": missing_required_metrics,
            "all_improved_or_equal": False,
        }

    improved_all = all(c["improved_or_equal"] for c in checks.values())
    return {
        "status": "provided",
        "checks": checks,
        "required_metrics": list(REQUIRED_BASELINE_METRICS),
        "missing_required_metrics": [],
        "all_improved_or_equal": improved_all,
    }


def _parse_top_k(raw: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        value = int(chunk)
        if value <= 0:
            raise ValueError("top-k values must be positive integers")
        if value not in out:
            out.append(value)
    if not out:
        return DEFAULT_TOP_K
    return tuple(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane-a-cpu", required=True, type=Path)
    parser.add_argument("--lane-a-gpu", required=True, type=Path)
    parser.add_argument("--lane-b-cpu", required=True, type=Path)
    parser.add_argument("--lane-b-gpu", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Unified report JSON path")
    parser.add_argument("--pnl-abs-tol", type=float, default=0.0)
    parser.add_argument("--trade-abs-tol", type=float, default=0.0)
    parser.add_argument("--top-k", default=",".join(str(v) for v in DEFAULT_TOP_K))
    parser.add_argument("--min-spearman", type=float, default=0.90)
    parser.add_argument("--min-top3-overlap", type=int, default=2)
    parser.add_argument("--require-top1-match", action="store_true")
    parser.add_argument(
        "--synthetic-ranking-json",
        type=Path,
        default=None,
        help="Optional JSON payload for synthetic ranking assertions.",
    )
    parser.add_argument("--baseline-any-mismatch-count", type=float, default=None)
    parser.add_argument("--baseline-max-abs-total-pnl-diff", type=float, default=None)
    parser.add_argument("--baseline-mean-abs-total-pnl-diff", type=float, default=None)
    parser.add_argument("--baseline-trade-count-mismatch-count", type=float, default=None)
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--fail-on-assert", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    top_ks = _parse_top_k(args.top_k)
    thresholds = RankingThresholds(
        min_spearman=args.min_spearman,
        min_top3_overlap=args.min_top3_overlap,
        require_top1_match=bool(args.require_top1_match),
    )

    lane_a = build_lane_report(
        lane_name="lane_a_identical_symbol_universe",
        cpu_path=args.lane_a_cpu,
        gpu_path=args.lane_a_gpu,
        pnl_abs_tol=args.pnl_abs_tol,
        trade_abs_tol=args.trade_abs_tol,
        top_ks=top_ks,
        thresholds=thresholds,
    )
    lane_b = build_lane_report(
        lane_name="lane_b_production_truncation",
        cpu_path=args.lane_b_cpu,
        gpu_path=args.lane_b_gpu,
        pnl_abs_tol=args.pnl_abs_tol,
        trade_abs_tol=args.trade_abs_tol,
        top_ks=top_ks,
        thresholds=thresholds,
    )

    synthetic_assertions = _load_optional_json(args.synthetic_ranking_json)
    baseline = _baseline_comparison(lane_a, args)

    report = {
        "schema": "gpu_smoke_parity_lane_report_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lanes": {
            lane_a["lane"]: lane_a,
            lane_b["lane"]: lane_b,
        },
        "ranking_parity_assertions": {
            "synthetic": synthetic_assertions,
            "smoke": {
                lane_a["lane"]: lane_a["ranking"]["assertions"],
                lane_b["lane"]: lane_b["ranking"]["assertions"],
            },
        },
        "baseline_comparison": {
            "lane_a": baseline,
        },
    }

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.print_summary:
        for lane in (lane_a, lane_b):
            parity = lane["parity"]
            ranking = lane["ranking"]
            print(
                f"[{lane['lane']}] mismatches={parity['any_mismatch_count']} "
                f"max_abs_total_pnl_diff={parity['max_abs_total_pnl_diff']:.6f} "
                f"mean_abs_total_pnl_diff={parity['mean_abs_total_pnl_diff']:.6f} "
                f"trade_count_mismatch_count={parity['trade_count_mismatch_count']} "
                f"ranking_all_pass={ranking['all_pass']}"
            )
        if baseline.get("status") != "not_provided":
            missing_metrics = baseline.get("missing_required_metrics", [])
            missing_display = ",".join(str(item) for item in missing_metrics) if missing_metrics else "-"
            print(
                f"[baseline] lane_a_status={baseline.get('status')} "
                f"lane_a_all_improved_or_equal={baseline.get('all_improved_or_equal')} "
                f"missing_required_metrics={missing_display}"
            )
        print(f"[report] wrote {output_path}")

    all_assertions_pass = lane_a["ranking"]["all_pass"] and lane_b["ranking"]["all_pass"]
    baseline_status = baseline.get("status")
    if baseline_status == "not_provided":
        baseline_assertion_pass = True
    elif baseline_status == "provided":
        baseline_assertion_pass = bool(baseline.get("all_improved_or_equal"))
    else:
        baseline_assertion_pass = False

    if args.fail_on_assert and not (all_assertions_pass and baseline_assertion_pass):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
