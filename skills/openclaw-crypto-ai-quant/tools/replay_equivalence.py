from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

DecisionTrace = list[dict[str, Any]]
OPTIONAL_TRACE_FIELDS = frozenset({"config_fingerprint"})


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_decision_trace(payload: Any) -> DecisionTrace:
    if isinstance(payload, list):
        traces = payload
    elif isinstance(payload, dict):
        traces = payload.get("decision_diagnostics") or payload.get("decision_trace")
        if traces is None:
            raise ValueError("payload missing decision trace (decision_diagnostics or decision_trace)")
    else:
        raise ValueError("payload must be a list or an object containing decision diagnostics")

    if not isinstance(traces, list):
        raise ValueError("decision trace must be an array")
    return traces


def _normalise_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("value is not numeric")


def _record(diff_bucket: list[dict[str, Any]], path: list[str], left: Any, right: Any, *, max_diffs: int) -> None:
    if len(diff_bucket) >= max_diffs:
        return
    diff_bucket.append(
        {
            "path": "/".join(path),
            "left": left,
            "right": right,
        }
    )


def _compare_payload(
    left: Any,
    right: Any,
    path: list[str],
    diffs: list[dict[str, Any]],
    *,
    tolerance: float,
    max_diffs: int,
) -> None:
    if len(diffs) >= max_diffs:
        return

    if isinstance(left, dict) and isinstance(right, dict):
        left_keys = set(left.keys())
        right_keys = set(right.keys())
        for key in sorted(left_keys | right_keys):
            if len(diffs) >= max_diffs:
                return
            if key in OPTIONAL_TRACE_FIELDS and (key not in left or key not in right):
                continue
            if key not in left:
                _record(diffs, path + [str(key)], None, right[key], max_diffs=max_diffs)
                continue
            if key not in right:
                _record(diffs, path + [str(key)], left[key], None, max_diffs=max_diffs)
                continue
            _compare_payload(
                left[key],
                right[key],
                path + [str(key)],
                diffs,
                tolerance=tolerance,
                max_diffs=max_diffs,
            )
        return

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            _record(diffs, path, len(left), len(right), max_diffs=max_diffs)
        count = min(len(left), len(right))
        for idx in range(count):
            if len(diffs) >= max_diffs:
                return
            _compare_payload(
                left[idx],
                right[idx],
                path + [f"[{idx}]"],
                diffs,
                tolerance=tolerance,
                max_diffs=max_diffs,
            )
        return

    if isinstance(left, bool) and isinstance(right, bool):
        if left != right:
            _record(diffs, path, left, right, max_diffs=max_diffs)
        return

    if isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool) and not isinstance(right, bool):
        lf = _normalise_number(left)
        rf = _normalise_number(right)
        if not math.isclose(lf, rf, rel_tol=0.0, abs_tol=tolerance):
            _record(diffs, path, lf, rf, max_diffs=max_diffs)
        return

    if left != right:
        _record(diffs, path, left, right, max_diffs=max_diffs)


def compare_traces(
    left: DecisionTrace,
    right: DecisionTrace,
    *,
    tolerance: float = 1e-12,
    max_diffs: int = 25,
) -> tuple[bool, list[dict[str, Any]], dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    max_diffs = max(1, int(max_diffs or 25))
    _compare_payload(left, right, [], diffs, tolerance=tolerance, max_diffs=max_diffs)
    status = len(diffs) == 0
    left_dump = json.dumps(left, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    right_dump = json.dumps(right, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    summary: dict[str, Any] = {
        "status": "match" if status else "mismatch",
        "max_diffs": int(max_diffs),
        "reported_diffs": len(diffs[:max_diffs]),
        "left_len": len(left),
        "right_len": len(right),
        "left_checksum": hashlib.sha256(left_dump.encode()).hexdigest(),
        "right_checksum": hashlib.sha256(right_dump.encode()).hexdigest(),
    }
    return status, diffs[:max_diffs], summary


def compare_files(
    left_path: str | Path,
    right_path: str | Path,
    *,
    tolerance: float = 1e-12,
    max_diffs: int = 25,
) -> tuple[bool, list[dict[str, Any]], dict[str, Any]]:
    left_data = _load_json(Path(left_path))
    right_data = _load_json(Path(right_path))
    left_trace = extract_decision_trace(left_data)
    right_trace = extract_decision_trace(right_data)
    return compare_traces(left_trace, right_trace, tolerance=tolerance, max_diffs=max_diffs)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two kernel decision traces for deterministic equivalence.")
    parser.add_argument("left", help="Left trace JSON file")
    parser.add_argument("right", help="Right trace JSON file")
    parser.add_argument("--tolerance", type=float, default=1e-12, help="Absolute float tolerance")
    parser.add_argument("--max-diffs", type=int, default=25, help="Limit printed/returned diffs")
    parser.add_argument(
        "--json-report",
        help="Optional JSON report path. If omitted, the report is printed to stdout.",
    )
    return parser


def _run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    left = Path(args.left)
    right = Path(args.right)
    if not left.exists():
        print(f"left path not found: {left}")
        return 2
    if not right.exists():
        print(f"right path not found: {right}")
        return 2

    ok, diffs, summary = compare_files(left, right, tolerance=args.tolerance, max_diffs=args.max_diffs)
    report = {
        "ok": ok,
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "diffs": diffs,
        "summary": summary,
    }

    if ok:
        report["summary"]["status"] = "ok"
    else:
        report["summary"]["status"] = "mismatch"

    if args.json_report:
        out_path = Path(args.json_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not args.json_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(out_path.as_posix())

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_run())
