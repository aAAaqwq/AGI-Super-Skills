#!/usr/bin/env python3
"""Inspect and report the latest compatible replay-equivalence baseline.

This utility is intended for scheduled housekeeping jobs so operators can
detect stale pinned baselines before they block Step-5 promotion/deploy gates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import factory_run  # noqa: E402


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _infer_contract(*, right_report: Path, mode: str) -> dict[str, Any] | None:
    run_dir = factory_run._find_run_dir(right_report)
    if run_dir is None:
        return None
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        return None
    try:
        meta = _load_json(meta_path)
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    return factory_run._replay_equivalence_contract_from_meta(meta, mode=mode)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay-equivalence baseline lifecycle checker.")
    parser.add_argument("--right-report", required=True, help="Path to the current candidate replay JSON.")
    parser.add_argument("--mode", default="backtest", help="Replay equivalence mode (default: backtest).")
    parser.add_argument(
        "--contract-fingerprint",
        default="",
        help="Optional contract fingerprint override. If omitted, inferred from the run metadata.",
    )
    parser.add_argument(
        "--summary-json",
        default="",
        help="Optional output path for machine-readable summary JSON.",
    )
    return parser


def _run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    mode = factory_run._normalise_replay_equivalence_mode(str(args.mode or "backtest"))
    right_report = Path(str(args.right_report)).expanduser().resolve()
    summary: dict[str, Any] = {
        "config_id": "",
        "config_path": "",
        "sort_by": "",
        "rank": 0,
        "config_sha256": "",
    }

    contract_fp = str(args.contract_fingerprint or "").strip()
    inferred = _infer_contract(right_report=right_report, mode=mode)
    if not contract_fp and isinstance(inferred, dict):
        contract_fp = str(inferred.get("fingerprint", "") or "").strip()

    current_contract: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "fingerprint": contract_fp,
        "payload": {},
    }

    baseline, info = factory_run._auto_replay_equivalence_baseline_path(
        mode=mode,
        right_report=right_report,
        summary=summary,
        current_contract=current_contract,
    )

    payload = {
        "status": "ok" if baseline is not None else "not_found",
        "mode": mode,
        "right_report": str(right_report),
        "contract_fingerprint": contract_fp,
        "selected_baseline": str(baseline) if baseline is not None else "",
        "lookup": info,
    }

    if str(args.summary_json or "").strip():
        out = Path(str(args.summary_json)).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if baseline is not None else 1


if __name__ == "__main__":
    raise SystemExit(_run())
