#!/usr/bin/env python3
"""Evaluate replay bundle alignment reports and return a single pass/fail gate.

This tool reads:
- replay bundle manifest
- state alignment report
- trade reconciliation report
- action reconciliation report
- live/paper action reconciliation report (optional/required)
- live/paper decision trace reconciliation report (optional/required)
- event-order parity report (optional/required)
- GPU parity report (optional/required)

and emits one deterministic gate result for CI/manual workflows, including
market-data provenance checks for the replay candle window.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from candles_provenance import build_candles_window_provenance
except ModuleNotFoundError:  # pragma: no cover - module execution path
    from tools.candles_provenance import build_candles_window_provenance

try:
    import yaml
except Exception:  # pragma: no cover - optional runtime dependency
    yaml = None

_STRICT_ALLOWED_RESIDUAL_CLASSIFICATIONS = {
    "non-simulatable_exchange_oms_effect",
    "state_initialisation_gap",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assert replay bundle alignment reports with one strict gate.")
    parser.add_argument("--bundle-dir", required=True, help="Replay bundle directory")
    parser.add_argument(
        "--bundle-manifest",
        default="replay_bundle_manifest.json",
        help="Replay bundle manifest filename/path",
    )
    parser.add_argument(
        "--candles-db",
        help="Optional candles DB override path for provenance validation",
    )
    parser.add_argument("--state-report", default="state_alignment_report.json", help="State alignment report filename/path")
    parser.add_argument("--trade-report", default="trade_reconcile_report.json", help="Trade reconcile report filename/path")
    parser.add_argument("--action-report", default="action_reconcile_report.json", help="Action reconcile report filename/path")
    parser.add_argument(
        "--live-paper-report",
        default="live_paper_action_reconcile_report.json",
        help="Optional live/paper action reconcile report filename/path",
    )
    parser.add_argument(
        "--require-live-paper",
        action="store_true",
        default=False,
        help="Fail when live/paper action report is missing",
    )
    parser.add_argument(
        "--live-paper-decision-trace-report",
        default="live_paper_decision_trace_reconcile_report.json",
        help="Optional live/paper decision trace reconcile report filename/path",
    )
    parser.add_argument(
        "--paper-seed-apply-report",
        default="paper_seed_apply_report.json",
        help="Optional paper seed apply report filename/path (captures strict_replace actually used)",
    )
    parser.add_argument(
        "--require-live-paper-decision-trace",
        action="store_true",
        default=False,
        help="Fail when live/paper decision trace report is missing",
    )
    parser.add_argument(
        "--event-order-report",
        default="event_order_parity_report.json",
        help="Optional event-order parity report filename/path",
    )
    parser.add_argument(
        "--require-event-order",
        action="store_true",
        default=False,
        help="Fail when event-order parity report is missing",
    )
    parser.add_argument(
        "--gpu-parity-report",
        default="gpu_smoke_parity_report.json",
        help="Optional GPU smoke parity report filename/path",
    )
    parser.add_argument(
        "--require-gpu-parity",
        action="store_true",
        default=False,
        help="Fail when GPU parity report is missing",
    )
    parser.add_argument("--output", help="Optional output path for gate report JSON")
    parser.add_argument(
        "--strict-no-residuals",
        action="store_true",
        default=False,
        help="Fail if accepted residuals are present in trade/action reports",
    )
    parser.add_argument(
        "--skip-candles-provenance-check",
        action="store_true",
        default=False,
        help="Skip manifest candle-window provenance validation",
    )
    parser.add_argument(
        "--require-runtime-strategy-provenance",
        action="store_true",
        default=False,
        help="Fail when manifest runtime strategy provenance is missing",
    )
    parser.add_argument(
        "--max-strategy-sha1-distinct",
        type=int,
        default=None,
        help="Maximum allowed distinct runtime strategy_sha1 within the replay window",
    )
    parser.add_argument(
        "--require-oms-strategy-provenance",
        action="store_true",
        default=False,
        help="Fail when manifest OMS strategy provenance is missing",
    )
    parser.add_argument(
        "--max-oms-strategy-sha1-distinct",
        type=int,
        default=None,
        help="Maximum allowed distinct OMS strategy_sha1 within the replay window",
    )
    parser.add_argument(
        "--require-live-run-fingerprint-provenance",
        action="store_true",
        default=False,
        help="Fail when manifest live run fingerprint provenance is missing",
    )
    parser.add_argument(
        "--max-live-run-fingerprint-distinct",
        type=int,
        default=None,
        help="Maximum allowed distinct live run_fingerprint within the replay window",
    )
    parser.add_argument(
        "--require-locked-strategy-match",
        action="store_true",
        default=False,
        help="Fail when locked strategy hash cannot be matched against runtime/OMS provenance",
    )
    return parser


def _resolve_report_path(bundle_dir: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (bundle_dir / path).resolve()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _hash_json_canonical(obj: Any) -> str:
    try:
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = repr(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _compute_locked_strategy_hashes(bundle_dir: Path, manifest: dict[str, Any]) -> tuple[str, str, Path]:
    artefacts = manifest.get("artefacts") or {}
    snapshot_raw = str((artefacts.get("strategy_config_snapshot_file") or "strategy_overrides.locked.yaml")).strip()
    snapshot_path = Path(snapshot_raw).expanduser()
    if not snapshot_path.is_absolute():
        snapshot_path = (bundle_dir / snapshot_path).resolve()
    else:
        snapshot_path = snapshot_path.resolve()

    if yaml is None or not snapshot_path.exists():
        return "", "", snapshot_path
    try:
        raw = yaml.safe_load(snapshot_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "", "", snapshot_path
    obj = raw if isinstance(raw, dict) else {}
    sha256 = _hash_json_canonical(obj)
    try:
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = repr(obj).encode("utf-8")
    sha1_legacy = hashlib.sha1(payload).hexdigest()
    return sha256, sha1_legacy, snapshot_path


def _gpu_lane_pass_map(report: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    lanes = report.get("lanes")
    lane_map: dict[str, bool] = {}
    invalid_lanes: list[str] = []
    if isinstance(lanes, dict):
        for lane_name, lane_obj in lanes.items():
            if isinstance(lane_obj, dict):
                ranking = lane_obj.get("ranking") or {}
                raw_all_pass = (ranking or {}).get("all_pass")
                if isinstance(raw_all_pass, bool):
                    lane_map[str(lane_name)] = raw_all_pass
                else:
                    invalid_lanes.append(str(lane_name))
    elif isinstance(lanes, list):
        for idx, lane_obj in enumerate(lanes, start=1):
            if isinstance(lane_obj, dict):
                lane_name = str(lane_obj.get("lane") or f"lane_{idx}")
                ranking = lane_obj.get("ranking") or {}
                raw_all_pass = (ranking or {}).get("all_pass")
                if isinstance(raw_all_pass, bool):
                    lane_map[lane_name] = raw_all_pass
                else:
                    invalid_lanes.append(lane_name)
    return lane_map, invalid_lanes


def _blocking_residuals_for_strict_mode(
    residuals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocking: list[dict[str, Any]] = []
    for row in residuals:
        cls = str((row or {}).get("classification") or "").strip().lower()
        if cls and cls in _STRICT_ALLOWED_RESIDUAL_CLASSIFICATIONS:
            continue
        blocking.append(row)
    return blocking


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir).expanduser().resolve()
    if not bundle_dir.exists():
        parser.error(f"bundle directory not found: {bundle_dir}")

    manifest_path = _resolve_report_path(bundle_dir, args.bundle_manifest)
    state_path = _resolve_report_path(bundle_dir, args.state_report)
    trade_path = _resolve_report_path(bundle_dir, args.trade_report)
    action_path = _resolve_report_path(bundle_dir, args.action_report)
    live_paper_path = _resolve_report_path(bundle_dir, args.live_paper_report)
    live_paper_decision_trace_path = _resolve_report_path(bundle_dir, args.live_paper_decision_trace_report)
    paper_seed_apply_path = _resolve_report_path(bundle_dir, args.paper_seed_apply_report)
    event_order_path = _resolve_report_path(bundle_dir, args.event_order_report)
    gpu_parity_path = _resolve_report_path(bundle_dir, args.gpu_parity_report)

    failures: list[dict[str, Any]] = []
    candles_provenance_checked = not bool(args.skip_candles_provenance_check)
    candles_provenance_ok = not candles_provenance_checked
    manifest_candles_provenance: dict[str, Any] | None = None
    recomputed_candles_provenance: dict[str, Any] | None = None
    backtester_replay_report_path: Path | None = None
    backtester_replay_report: dict[str, Any] | None = None
    replay_config_fingerprint = ""
    snapshot_init_state_path: Path | None = None
    snapshot_position_state_provenance: dict[str, Any] | None = None
    snapshot_trades_only_positions = 0

    manifest: dict[str, Any] | None = None
    if not manifest_path.exists():
        failures.append(
            {
                "code": "missing_bundle_manifest",
                "classification": "market_data_alignment_gap",
                "detail": str(manifest_path),
            }
        )
    else:
        loaded = _load_json(manifest_path)
        if isinstance(loaded, dict):
            manifest = loaded
            raw_candles_provenance = manifest.get("candles_provenance")
            if isinstance(raw_candles_provenance, dict):
                manifest_candles_provenance = raw_candles_provenance
            snapshot_file = str(((manifest.get("artefacts") or {}).get("snapshot_file") or "").strip())
            if snapshot_file:
                snap_path = Path(snapshot_file).expanduser()
                if not snap_path.is_absolute():
                    snap_path = (bundle_dir / snap_path).resolve()
                else:
                    snap_path = snap_path.resolve()
                snapshot_init_state_path = snap_path
            artefacts = manifest.get("artefacts") or {}
            replay_report_raw = str((artefacts.get("backtester_replay_report_json") or "").strip())
            if replay_report_raw:
                replay_path = Path(replay_report_raw).expanduser()
                if not replay_path.is_absolute():
                    replay_path = (bundle_dir / replay_path).resolve()
                else:
                    replay_path = replay_path.resolve()
                backtester_replay_report_path = replay_path
            else:
                failures.append(
                    {
                        "code": "missing_backtester_replay_report_path_in_manifest",
                        "classification": "state_initialisation_gap",
                        "detail": "manifest.artefacts.backtester_replay_report_json is missing",
                    }
                )
        else:
            failures.append(
                {
                    "code": "invalid_bundle_manifest",
                    "classification": "market_data_alignment_gap",
                    "detail": "bundle manifest is not a JSON object",
                }
            )

    if snapshot_init_state_path is None:
        fallback_snapshot = (bundle_dir / "live_init_state_v2.json").resolve()
        if fallback_snapshot.exists():
            snapshot_init_state_path = fallback_snapshot
    if snapshot_init_state_path is not None and snapshot_init_state_path.exists():
        loaded_snapshot = _load_json(snapshot_init_state_path)
        if isinstance(loaded_snapshot, dict):
            raw_pos_prov = ((loaded_snapshot.get("canonical") or {}).get("position_state_provenance"))
            if isinstance(raw_pos_prov, dict):
                snapshot_position_state_provenance = raw_pos_prov
                snapshot_trades_only_positions = _as_int(
                    ((raw_pos_prov.get("counts") or {}).get("trades_only")),
                    0,
                )

    if backtester_replay_report_path is not None:
        if not backtester_replay_report_path.exists():
            failures.append(
                {
                    "code": "missing_backtester_replay_report",
                    "classification": "state_initialisation_gap",
                    "detail": str(backtester_replay_report_path),
                }
            )
        else:
            loaded_replay = _load_json(backtester_replay_report_path)
            if not isinstance(loaded_replay, dict):
                failures.append(
                    {
                        "code": "invalid_backtester_replay_report",
                        "classification": "state_initialisation_gap",
                        "detail": "backtester replay report is not a JSON object",
                    }
                )
            else:
                backtester_replay_report = loaded_replay
                replay_config_fingerprint = str(loaded_replay.get("config_fingerprint") or "").strip().lower()
                if not replay_config_fingerprint:
                    failures.append(
                        {
                            "code": "missing_backtester_replay_config_fingerprint",
                            "classification": "state_initialisation_gap",
                            "detail": "backtester replay report config_fingerprint is missing",
                        }
                    )
                elif not _is_sha256_hex(replay_config_fingerprint):
                    failures.append(
                        {
                            "code": "invalid_backtester_replay_config_fingerprint",
                            "classification": "state_initialisation_gap",
                            "detail": "backtester replay report config_fingerprint is not a valid sha256 hex",
                            "config_fingerprint_prefix8": replay_config_fingerprint[:8],
                        }
                    )

    strategy_runtime_stability_ok = True
    strategy_oms_stability_ok = True
    live_run_fingerprint_stability_ok = True
    locked_strategy_match_ok = True
    live_run_fingerprint_provenance: dict[str, Any] | None = None
    if manifest is not None:
        runtime_strategy = manifest.get("runtime_strategy_provenance")
        oms_strategy = manifest.get("oms_strategy_provenance")
        run_fingerprint_provenance = manifest.get("live_run_fingerprint_provenance")
        locked_strategy = manifest.get("locked_strategy_provenance")
        if not isinstance(runtime_strategy, dict):
            strategy_runtime_stability_ok = False
            if args.require_runtime_strategy_provenance:
                failures.append(
                    {
                        "code": "missing_runtime_strategy_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": "manifest.runtime_strategy_provenance is missing",
                    }
                )
        else:
            distinct_sha = _as_int(runtime_strategy.get("strategy_sha1_distinct"), 0)
            strategy_rows_sampled = _as_int(runtime_strategy.get("strategy_rows_sampled"), 0)
            timeline = runtime_strategy.get("strategy_sha1_timeline")
            timeline_count = len(timeline) if isinstance(timeline, list) else 0
            if args.require_runtime_strategy_provenance and (strategy_rows_sampled <= 0 or timeline_count <= 0):
                strategy_runtime_stability_ok = False
                failures.append(
                    {
                        "code": "empty_runtime_strategy_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": "runtime strategy provenance is present but contains no sampled strategy_sha1 rows",
                        "counts": {
                            "strategy_rows_sampled": strategy_rows_sampled,
                            "strategy_sha1_timeline_count": timeline_count,
                            "runtime_rows_in_window": _as_int(runtime_strategy.get("runtime_rows_in_window"), 0),
                        },
                    }
                )
            max_distinct = args.max_strategy_sha1_distinct
            if max_distinct is not None and distinct_sha > int(max_distinct):
                strategy_runtime_stability_ok = False
                failures.append(
                    {
                        "code": "strategy_config_drift_within_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"runtime strategy_sha1 drift exceeded limit: "
                            f"distinct={distinct_sha} > max={int(max_distinct)}"
                        ),
                        "counts": {
                            "strategy_sha1_distinct": distinct_sha,
                            "strategy_version_distinct": _as_int(runtime_strategy.get("strategy_version_distinct"), 0),
                            "strategy_rows_sampled": strategy_rows_sampled,
                            "runtime_rows_in_window": _as_int(runtime_strategy.get("runtime_rows_in_window"), 0),
                        },
                    }
                )

        if not isinstance(oms_strategy, dict):
            strategy_oms_stability_ok = False
            if args.require_oms_strategy_provenance or args.require_locked_strategy_match:
                failures.append(
                    {
                        "code": "missing_oms_strategy_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": "manifest.oms_strategy_provenance is missing",
                    }
                )
        else:
            oms_distinct_sha = _as_int(oms_strategy.get("strategy_sha1_distinct"), 0)
            has_oms_rows_in_window = "oms_rows_in_window" in oms_strategy
            oms_rows_in_window = _as_int(oms_strategy.get("oms_rows_in_window"), 0)
            oms_rows_sampled = _as_int(oms_strategy.get("oms_rows_sampled"), 0)
            oms_timeline = oms_strategy.get("strategy_sha1_timeline")
            oms_timeline_count = len(oms_timeline) if isinstance(oms_timeline, list) else 0
            enforce_non_empty_oms_provenance = (
                (oms_rows_in_window > 0) if has_oms_rows_in_window else True
            )
            if (
                args.require_oms_strategy_provenance
                and enforce_non_empty_oms_provenance
                and (oms_rows_sampled <= 0 or oms_timeline_count <= 0)
            ):
                strategy_oms_stability_ok = False
                failures.append(
                    {
                        "code": "empty_oms_strategy_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": "OMS strategy provenance is present but contains no sampled strategy_sha1 rows",
                        "counts": {
                            "has_oms_rows_in_window": bool(has_oms_rows_in_window),
                            "oms_rows_in_window": oms_rows_in_window,
                            "oms_rows_sampled": oms_rows_sampled,
                            "strategy_sha1_timeline_count": oms_timeline_count,
                        },
                    }
                )
            max_oms_distinct = args.max_oms_strategy_sha1_distinct
            if max_oms_distinct is not None and oms_distinct_sha > int(max_oms_distinct):
                strategy_oms_stability_ok = False
                failures.append(
                    {
                        "code": "strategy_config_drift_within_oms_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"OMS strategy_sha1 drift exceeded limit: "
                            f"distinct={oms_distinct_sha} > max={int(max_oms_distinct)}"
                        ),
                        "counts": {
                            "strategy_sha1_distinct": oms_distinct_sha,
                            "strategy_version_distinct": _as_int(oms_strategy.get("strategy_version_distinct"), 0),
                            "oms_rows_sampled": oms_rows_sampled,
                        },
                    }
                )

        if not isinstance(run_fingerprint_provenance, dict):
            live_run_fingerprint_stability_ok = False
            if args.require_live_run_fingerprint_provenance:
                failures.append(
                    {
                        "code": "missing_live_run_fingerprint_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": "manifest.live_run_fingerprint_provenance is missing",
                    }
                )
        else:
            live_run_fingerprint_provenance = run_fingerprint_provenance
            run_fp_distinct = _as_int(run_fingerprint_provenance.get("run_fingerprint_distinct"), 0)
            run_fp_rows_sampled = _as_int(run_fingerprint_provenance.get("rows_sampled"), 0)
            run_fp_timeline = run_fingerprint_provenance.get("run_fingerprint_timeline")
            run_fp_timeline_count = len(run_fp_timeline) if isinstance(run_fp_timeline, list) else 0
            if (
                args.require_live_run_fingerprint_provenance
                and run_fp_rows_sampled > 0
                and run_fp_timeline_count <= 0
            ):
                live_run_fingerprint_stability_ok = False
                failures.append(
                    {
                        "code": "empty_live_run_fingerprint_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            "live run fingerprint provenance is present but contains no sampled "
                            "run_fingerprint rows"
                        ),
                        "counts": {
                            "rows_sampled": run_fp_rows_sampled,
                            "run_fingerprint_timeline_count": run_fp_timeline_count,
                        },
                    }
                )
            max_live_run_fp_distinct = args.max_live_run_fingerprint_distinct
            if (
                max_live_run_fp_distinct is not None
                and run_fp_distinct > int(max_live_run_fp_distinct)
            ):
                live_run_fingerprint_stability_ok = False
                failures.append(
                    {
                        "code": "live_run_fingerprint_drift_within_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"live run_fingerprint drift exceeded limit: "
                            f"distinct={run_fp_distinct} > max={int(max_live_run_fp_distinct)}"
                        ),
                        "counts": {
                            "run_fingerprint_distinct": run_fp_distinct,
                            "rows_sampled": run_fp_rows_sampled,
                            "run_fingerprint_timeline_count": run_fp_timeline_count,
                        },
                    }
                )

        if args.require_locked_strategy_match:
            if not isinstance(locked_strategy, dict):
                locked_strategy_match_ok = False
                failures.append(
                    {
                        "code": "missing_locked_strategy_provenance",
                        "classification": "state_initialisation_gap",
                        "detail": "manifest.locked_strategy_provenance is missing",
                    }
                )
            else:
                locked_sha256 = str(locked_strategy.get("strategy_overrides_sha1") or "").strip().lower()
                locked_sha1_legacy = str(locked_strategy.get("strategy_overrides_sha1_legacy") or "").strip().lower()
                locked_snapshot_sha256 = str(locked_strategy.get("strategy_overrides_snapshot_sha1") or "").strip().lower()
                locked_snapshot_sha1_legacy = str(
                    locked_strategy.get("strategy_overrides_snapshot_sha1_legacy") or ""
                ).strip().lower()
                if len(locked_sha256) < 8 and len(locked_sha1_legacy) < 8:
                    locked_strategy_match_ok = False
                    failures.append(
                        {
                            "code": "invalid_locked_strategy_sha1",
                            "classification": "state_initialisation_gap",
                            "detail": "locked strategy hashes are missing or too short",
                        }
                    )
                else:
                    computed_locked_sha256, computed_locked_sha1_legacy, snapshot_path = _compute_locked_strategy_hashes(
                        bundle_dir, manifest
                    )
                    if len(computed_locked_sha256) < 8 and len(computed_locked_sha1_legacy) < 8:
                        locked_strategy_match_ok = False
                        failures.append(
                            {
                                "code": "locked_strategy_snapshot_hash_unavailable",
                                "classification": "state_initialisation_gap",
                                "detail": (
                                    f"unable to compute locked strategy hash from snapshot file: {snapshot_path}"
                                ),
                            }
                        )
                    expected_snapshot_sha256 = (
                        locked_snapshot_sha256 if len(locked_snapshot_sha256) >= 8 else locked_sha256
                    )
                    expected_snapshot_sha1_legacy = (
                        locked_snapshot_sha1_legacy
                        if len(locked_snapshot_sha1_legacy) >= 8
                        else locked_sha1_legacy
                    )

                    if len(expected_snapshot_sha256) >= 8 and computed_locked_sha256 != expected_snapshot_sha256:
                        locked_strategy_match_ok = False
                        failures.append(
                            {
                                "code": "locked_strategy_manifest_snapshot_hash_mismatch",
                                "classification": "state_initialisation_gap",
                                "detail": "manifest locked strategy hash does not match snapshot YAML canonical hash",
                                "manifest_locked_sha256_prefix8": expected_snapshot_sha256[:8],
                                "snapshot_locked_sha256_prefix8": computed_locked_sha256[:8],
                                "snapshot_path": str(snapshot_path),
                            }
                        )
                    elif (
                        len(expected_snapshot_sha1_legacy) >= 8
                        and computed_locked_sha1_legacy != expected_snapshot_sha1_legacy
                    ):
                        locked_strategy_match_ok = False
                        failures.append(
                            {
                                "code": "locked_strategy_manifest_snapshot_hash_mismatch_legacy",
                                "classification": "state_initialisation_gap",
                                "detail": (
                                    "manifest locked legacy strategy hash does not match snapshot YAML canonical hash"
                                ),
                                "manifest_locked_sha1_prefix8": expected_snapshot_sha1_legacy[:8],
                                "snapshot_locked_sha1_prefix8": computed_locked_sha1_legacy[:8],
                                "snapshot_path": str(snapshot_path),
                            }
                        )

                    effective_locked_hashes = {
                        str(locked_sha256 or computed_locked_sha256).strip().lower(),
                        str(locked_sha1_legacy or computed_locked_sha1_legacy).strip().lower(),
                    }
                    effective_locked_hashes.discard("")

                    runtime_timeline = (
                        runtime_strategy.get("strategy_sha1_timeline")
                        if isinstance(runtime_strategy, dict)
                        else []
                    )
                    runtime_rows = runtime_timeline if isinstance(runtime_timeline, list) else []
                    runtime_prefix_match = any(
                        any(
                            candidate.startswith(str(row.get("strategy_sha1") or "").strip().lower())
                            for candidate in effective_locked_hashes
                        )
                        for row in runtime_rows
                        if str(row.get("strategy_sha1") or "").strip()
                    )
                    if not runtime_prefix_match:
                        locked_strategy_match_ok = False
                        failures.append(
                            {
                                "code": "locked_strategy_runtime_prefix_mismatch",
                                "classification": "state_initialisation_gap",
                                "detail": "locked strategy hash does not match any runtime strategy_sha1 prefix",
                                "locked_strategy_sha256_prefix8": (locked_sha256 or computed_locked_sha256)[:8],
                                "locked_strategy_sha1_legacy_prefix8": (
                                    locked_sha1_legacy or computed_locked_sha1_legacy
                                )[:8],
                            }
                        )

                    oms_rows_sampled = _as_int(oms_strategy.get("oms_rows_sampled"), 0) if isinstance(oms_strategy, dict) else 0
                    oms_timeline = (
                        oms_strategy.get("strategy_sha1_timeline")
                        if isinstance(oms_strategy, dict)
                        else []
                    )
                    oms_rows = oms_timeline if isinstance(oms_timeline, list) else []
                    oms_rows_available = bool(oms_rows_sampled > 0 and len(oms_rows) > 0)
                    if oms_rows_available:
                        oms_exact_match = any(
                            str(row.get("strategy_sha1") or "").strip().lower() in effective_locked_hashes
                            for row in oms_rows
                        )
                        if not oms_exact_match:
                            locked_strategy_match_ok = False
                            failures.append(
                                {
                                    "code": "locked_strategy_oms_sha1_mismatch",
                                    "classification": "state_initialisation_gap",
                                    "detail": "locked strategy hash does not match any OMS strategy_sha1 in window",
                                    "locked_strategy_sha256_prefix8": (locked_sha256 or computed_locked_sha256)[:8],
                                    "locked_strategy_sha1_legacy_prefix8": (
                                        locked_sha1_legacy or computed_locked_sha1_legacy
                                    )[:8],
                                }
                            )

    if candles_provenance_checked and manifest is not None:
        manifest_inputs = manifest.get("inputs") or {}
        manifest_provenance = manifest.get("candles_provenance") or {}
        candles_db_raw = str(args.candles_db or manifest_inputs.get("candles_db") or "").strip()
        if not candles_db_raw:
            failures.append(
                {
                    "code": "missing_candles_db_for_provenance",
                    "classification": "market_data_alignment_gap",
                    "detail": "candles DB path is missing in manifest and no --candles-db override was provided",
                }
            )
        else:
            candles_db_path = Path(candles_db_raw).expanduser().resolve()
            if not candles_db_path.exists():
                failures.append(
                    {
                        "code": "candles_db_not_found_for_provenance",
                        "classification": "market_data_alignment_gap",
                        "detail": str(candles_db_path),
                    }
                )
            else:
                interval = str(manifest_provenance.get("interval") or manifest_inputs.get("interval") or "").strip()
                from_ts = _as_int(manifest_provenance.get("from_ts", manifest_inputs.get("from_ts")))
                to_ts = _as_int(manifest_provenance.get("to_ts", manifest_inputs.get("to_ts")))
                if not interval or from_ts > to_ts:
                    failures.append(
                        {
                            "code": "invalid_manifest_candles_provenance",
                            "classification": "market_data_alignment_gap",
                            "detail": "manifest candles provenance has invalid interval/from_ts/to_ts",
                        }
                    )
                else:
                    actual_provenance = build_candles_window_provenance(
                        candles_db_path,
                        interval=interval,
                        from_ts=from_ts,
                        to_ts=to_ts,
                    )
                    recomputed_candles_provenance = actual_provenance
                    expected_hash = str(manifest_provenance.get("window_hash_sha256") or "").strip().lower()
                    expected_universe_hash = str(manifest_provenance.get("universe_hash_sha256") or "").strip().lower()
                    raw_expected_symbols = manifest_provenance.get("symbols")
                    expected_symbols = (
                        [str(s or "").strip().upper() for s in raw_expected_symbols]
                        if isinstance(raw_expected_symbols, list)
                        else []
                    )
                    expected_row_count_raw = manifest_provenance.get("row_count")

                    missing_manifest_fields: list[str] = []
                    if not expected_hash:
                        missing_manifest_fields.append("candles_provenance.window_hash_sha256")
                    if not expected_universe_hash:
                        missing_manifest_fields.append("candles_provenance.universe_hash_sha256")
                    if not isinstance(raw_expected_symbols, list):
                        missing_manifest_fields.append("candles_provenance.symbols")
                    if expected_row_count_raw is None:
                        missing_manifest_fields.append("candles_provenance.row_count")

                    if missing_manifest_fields:
                        failures.append(
                            {
                                "code": "invalid_manifest_candles_provenance_fields",
                                "classification": "market_data_alignment_gap",
                                "detail": "manifest candles provenance is missing required lock fields",
                                "missing_fields": missing_manifest_fields,
                            }
                        )
                    else:
                        expected_row_count = _as_int(expected_row_count_raw, -1)
                        hash_mismatch = expected_hash != actual_provenance["window_hash_sha256"]
                        universe_hash_mismatch = expected_universe_hash != actual_provenance["universe_hash_sha256"]
                        symbol_mismatch = expected_symbols != actual_provenance["symbols"]
                        row_count_mismatch = expected_row_count != _as_int(actual_provenance["row_count"], -1)

                        if hash_mismatch or universe_hash_mismatch or symbol_mismatch or row_count_mismatch:
                            failures.append(
                                {
                                    "code": "candles_provenance_mismatch",
                                    "classification": "market_data_alignment_gap",
                                    "detail": "recomputed candle window provenance does not match manifest",
                                    "expected": {
                                        "window_hash_sha256": expected_hash,
                                        "universe_hash_sha256": expected_universe_hash,
                                        "symbol_count": len(expected_symbols),
                                        "symbols": expected_symbols,
                                        "row_count": expected_row_count,
                                    },
                                    "actual": {
                                        "window_hash_sha256": actual_provenance["window_hash_sha256"],
                                        "universe_hash_sha256": actual_provenance["universe_hash_sha256"],
                                        "symbol_count": _as_int(actual_provenance["symbol_count"]),
                                        "symbols": actual_provenance["symbols"],
                                        "row_count": _as_int(actual_provenance["row_count"]),
                                    },
                                }
                            )
                        else:
                            candles_provenance_ok = True

    state_report: dict[str, Any] | None = None
    if not state_path.exists():
        failures.append(
            {
                "code": "missing_state_report",
                "classification": "state_initialisation_gap",
                "detail": str(state_path),
            }
        )
    else:
        state_report = _load_json(state_path)
        if not bool(state_report.get("ok")):
            failures.append(
                {
                    "code": "state_alignment_failed",
                    "classification": "state_initialisation_gap",
                    "detail": "state alignment report is not ok",
                    "diff_count": int((state_report.get("summary") or {}).get("diff_count") or 0),
                }
            )

    trade_report: dict[str, Any] | None = None
    if not trade_path.exists():
        failures.append(
            {
                "code": "missing_trade_report",
                "classification": "deterministic_logic_divergence",
                "detail": str(trade_path),
            }
        )
    else:
        trade_report = _load_json(trade_path)
        trade_status = bool(((trade_report.get("status") or {}).get("strict_alignment_pass")))
        if not trade_status:
            failures.append(
                {
                    "code": "trade_alignment_failed",
                    "classification": "deterministic_logic_divergence",
                    "detail": "trade reconciliation strict alignment failed",
                    "counts": trade_report.get("counts") or {},
                }
            )
        if args.strict_no_residuals:
            trade_residuals = list(trade_report.get("accepted_residuals") or [])
            blocking_trade_residuals = _blocking_residuals_for_strict_mode(trade_residuals)
            if blocking_trade_residuals:
                failures.append(
                    {
                        "code": "trade_residuals_present",
                        "classification": "non-simulatable_exchange_oms_effect",
                        "detail": "trade reconciliation has strict-blocking accepted residuals",
                        "count": len(blocking_trade_residuals),
                        "total_accepted_residuals": len(trade_residuals),
                    }
                )

    action_report: dict[str, Any] | None = None
    if not action_path.exists():
        failures.append(
            {
                "code": "missing_action_report",
                "classification": "deterministic_logic_divergence",
                "detail": str(action_path),
            }
        )
    else:
        action_report = _load_json(action_path)
        action_status = bool(((action_report.get("status") or {}).get("strict_alignment_pass")))
        if not action_status:
            failures.append(
                {
                    "code": "action_alignment_failed",
                    "classification": "deterministic_logic_divergence",
                    "detail": "action reconciliation strict alignment failed",
                    "counts": action_report.get("counts") or {},
                }
            )
        if args.strict_no_residuals:
            action_residuals = list(action_report.get("accepted_residuals") or [])
            blocking_action_residuals = _blocking_residuals_for_strict_mode(action_residuals)
            if blocking_action_residuals:
                failures.append(
                    {
                        "code": "action_residuals_present",
                        "classification": "non-simulatable_exchange_oms_effect",
                        "detail": "action reconciliation has strict-blocking accepted residuals",
                        "count": len(blocking_action_residuals),
                        "total_accepted_residuals": len(action_residuals),
                    }
                )

    snapshot_position_state_count = _as_int(
        ((snapshot_position_state_provenance or {}).get("counts") or {}).get("position_state"),
        0,
    )
    snapshot_position_state_history_count = _as_int(
        ((snapshot_position_state_provenance or {}).get("counts") or {}).get("position_state_history"),
        0,
    )
    snapshot_trades_only_gate = (
        snapshot_trades_only_positions > 0
        and snapshot_position_state_count <= 0
        and snapshot_position_state_history_count <= 0
    )

    if (
        snapshot_trades_only_gate
        and (
            (trade_report is not None and not bool(((trade_report.get("status") or {}).get("strict_alignment_pass"))))
            or (
                action_report is not None
                and not bool(((action_report.get("status") or {}).get("strict_alignment_pass")))
            )
        )
    ):
        failures.append(
            {
                "code": "snapshot_position_state_provenance_gap",
                "classification": "state_initialisation_gap",
                "detail": (
                    "snapshot includes trades-only position-state fallbacks; "
                    "deterministic mismatches may be state-fidelity induced"
                ),
                "counts": {
                    "trades_only_positions": int(snapshot_trades_only_positions),
                    "position_state_positions": int(snapshot_position_state_count),
                    "position_state_history_positions": int(snapshot_position_state_history_count),
                },
            }
        )

    live_paper_report: dict[str, Any] | None = None
    if not live_paper_path.exists():
        if args.require_live_paper:
            failures.append(
                {
                    "code": "missing_live_paper_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": str(live_paper_path),
                }
            )
    else:
        live_paper_report = _load_json(live_paper_path)
        live_paper_status = bool(((live_paper_report.get("status") or {}).get("strict_alignment_pass")))
        if not live_paper_status:
            failures.append(
                {
                    "code": "live_paper_alignment_failed",
                    "classification": "deterministic_logic_divergence",
                    "detail": "live/paper reconciliation strict alignment failed",
                    "counts": live_paper_report.get("counts") or {},
                }
            )
        if args.strict_no_residuals:
            live_paper_residuals = list(live_paper_report.get("accepted_residuals") or [])
            blocking_live_paper_residuals = _blocking_residuals_for_strict_mode(live_paper_residuals)
            if blocking_live_paper_residuals:
                failures.append(
                    {
                        "code": "live_paper_residuals_present",
                        "classification": "non-simulatable_exchange_oms_effect",
                        "detail": "live/paper reconciliation has strict-blocking accepted residuals",
                        "count": len(blocking_live_paper_residuals),
                        "total_accepted_residuals": len(live_paper_residuals),
                    }
                )

    manifest_inputs = (manifest.get("inputs") or {}) if isinstance(manifest, dict) else {}
    manifest_snapshot_strict_replace = _as_bool(manifest_inputs.get("snapshot_strict_replace"), False)
    paper_seed_apply_report: dict[str, Any] | None = None
    if paper_seed_apply_path.exists():
        paper_seed_apply_report = _load_json(paper_seed_apply_path)
    seed_apply_strict_replace = _as_bool(
        (paper_seed_apply_report or {}).get("strict_replace"),
        False,
    )
    live_paper_decision_trace_report: dict[str, Any] | None = None
    live_paper_decision_trace_skipped_empty_paper = False
    if not live_paper_decision_trace_path.exists():
        if args.require_live_paper_decision_trace:
            failures.append(
                {
                    "code": "missing_live_paper_decision_trace_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": str(live_paper_decision_trace_path),
                }
            )
    else:
        live_paper_decision_trace_report = _load_json(live_paper_decision_trace_path)
        decision_trace_status = bool(
            ((live_paper_decision_trace_report.get("status") or {}).get("strict_alignment_pass"))
        )
        decision_counts = live_paper_decision_trace_report.get("counts") or {}
        live_decision_rows = _as_int(decision_counts.get("live_decision_rows"), -1)
        paper_decision_rows = _as_int(decision_counts.get("paper_decision_rows"), -1)
        if not decision_trace_status:
            if (
                manifest_snapshot_strict_replace
                and seed_apply_strict_replace
                and paper_decision_rows == 0
                and live_decision_rows > 0
            ):
                live_paper_decision_trace_skipped_empty_paper = True
            else:
                failures.append(
                    {
                        "code": "live_paper_decision_trace_alignment_failed",
                        "classification": "deterministic_logic_divergence",
                        "detail": "live/paper decision trace strict alignment failed",
                        "counts": live_paper_decision_trace_report.get("counts") or {},
                    }
                )

    event_order_report: dict[str, Any] | None = None
    if not event_order_path.exists():
        if args.require_event_order:
            failures.append(
                {
                    "code": "missing_event_order_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": str(event_order_path),
                }
            )
    else:
        event_order_report = _load_json(event_order_path)
        event_order_ok = bool((event_order_report.get("status") or {}).get("order_parity_pass"))
        if not event_order_ok:
            failures.append(
                {
                    "code": "event_order_parity_failed",
                    "classification": "deterministic_logic_divergence",
                    "detail": "event order parity check failed",
                    "counts": event_order_report.get("counts") or {},
                }
            )
        if args.strict_no_residuals:
            event_order_residuals = list(event_order_report.get("accepted_residuals") or [])
            blocking_event_order_residuals = _blocking_residuals_for_strict_mode(event_order_residuals)
            if blocking_event_order_residuals:
                failures.append(
                    {
                        "code": "event_order_residuals_present",
                        "classification": "state_initialisation_gap",
                        "detail": "event-order reconciliation has strict-blocking accepted residuals",
                        "count": len(blocking_event_order_residuals),
                        "total_accepted_residuals": len(event_order_residuals),
                    }
                )

    gpu_parity_report: dict[str, Any] | None = None
    gpu_lane_status: dict[str, bool] = {}
    if not gpu_parity_path.exists():
        if args.require_gpu_parity:
            failures.append(
                {
                    "code": "missing_gpu_parity_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": str(gpu_parity_path),
                }
            )
    else:
        loaded_gpu = _load_json(gpu_parity_path)
        if not isinstance(loaded_gpu, dict):
            failures.append(
                {
                    "code": "invalid_gpu_parity_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": "GPU parity report is not a JSON object",
                }
            )
        else:
            gpu_parity_report = loaded_gpu
            gpu_lane_status, invalid_gpu_lanes = _gpu_lane_pass_map(gpu_parity_report)
            if not gpu_lane_status:
                failures.append(
                    {
                        "code": "invalid_gpu_parity_report_lanes",
                        "classification": "deterministic_logic_divergence",
                        "detail": "GPU parity report does not contain lane ranking status",
                    }
                )
            elif invalid_gpu_lanes:
                failures.append(
                    {
                        "code": "invalid_gpu_parity_lane_values",
                        "classification": "deterministic_logic_divergence",
                        "detail": "GPU parity report has non-boolean ranking.all_pass values",
                        "lanes": invalid_gpu_lanes,
                    }
                )
            else:
                has_lane_a = any("lane_a" in name.lower() for name in gpu_lane_status)
                has_lane_b = any("lane_b" in name.lower() for name in gpu_lane_status)
                if not (has_lane_a and has_lane_b):
                    failures.append(
                        {
                            "code": "invalid_gpu_parity_lane_coverage",
                            "classification": "deterministic_logic_divergence",
                            "detail": "GPU parity report is missing required lane_a/lane_b coverage",
                            "lanes": gpu_lane_status,
                        }
                    )
                elif not all(gpu_lane_status.values()):
                    failures.append(
                        {
                            "code": "gpu_parity_failed",
                            "classification": "deterministic_logic_divergence",
                            "detail": "GPU parity lane ranking assertions failed",
                            "lanes": gpu_lane_status,
                        }
                    )

    ok = len(failures) == 0

    report = {
        "ok": ok,
        "generated_at_ms": int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000),
        "bundle_dir": str(bundle_dir),
        "inputs": {
            "bundle_manifest": str(manifest_path),
            "candles_db_override": str(Path(args.candles_db).expanduser().resolve()) if args.candles_db else None,
            "skip_candles_provenance_check": bool(args.skip_candles_provenance_check),
            "require_runtime_strategy_provenance": bool(args.require_runtime_strategy_provenance),
            "max_strategy_sha1_distinct": int(args.max_strategy_sha1_distinct)
            if args.max_strategy_sha1_distinct is not None
            else None,
            "require_oms_strategy_provenance": bool(args.require_oms_strategy_provenance),
            "max_oms_strategy_sha1_distinct": int(args.max_oms_strategy_sha1_distinct)
            if args.max_oms_strategy_sha1_distinct is not None
            else None,
            "require_live_run_fingerprint_provenance": bool(args.require_live_run_fingerprint_provenance),
            "max_live_run_fingerprint_distinct": int(args.max_live_run_fingerprint_distinct)
            if args.max_live_run_fingerprint_distinct is not None
            else None,
            "require_locked_strategy_match": bool(args.require_locked_strategy_match),
            "backtester_replay_report": str(backtester_replay_report_path) if backtester_replay_report_path else None,
            "state_report": str(state_path),
            "trade_report": str(trade_path),
            "action_report": str(action_path),
            "live_paper_report": str(live_paper_path),
            "require_live_paper": bool(args.require_live_paper),
            "live_paper_decision_trace_report": str(live_paper_decision_trace_path),
            "paper_seed_apply_report": str(paper_seed_apply_path),
            "require_live_paper_decision_trace": bool(args.require_live_paper_decision_trace),
            "event_order_report": str(event_order_path),
            "require_event_order": bool(args.require_event_order),
            "gpu_parity_report": str(gpu_parity_path),
            "require_gpu_parity": bool(args.require_gpu_parity),
            "strict_no_residuals": bool(args.strict_no_residuals),
        },
        "checks": {
            "manifest_present": manifest is not None,
            "strategy_runtime_stability_ok": strategy_runtime_stability_ok,
            "strategy_oms_stability_ok": strategy_oms_stability_ok,
            "live_run_fingerprint_stability_ok": live_run_fingerprint_stability_ok,
            "locked_strategy_match_ok": locked_strategy_match_ok,
            "backtester_replay_report_present": backtester_replay_report is not None,
            "backtester_replay_config_fingerprint_present": bool(replay_config_fingerprint),
            "backtester_replay_config_fingerprint_valid_sha256": _is_sha256_hex(replay_config_fingerprint),
            "backtester_replay_config_fingerprint_prefix8": replay_config_fingerprint[:8]
            if replay_config_fingerprint
            else None,
            "candles_provenance_checked": candles_provenance_checked,
            "candles_provenance_ok": candles_provenance_ok,
            "state_ok": bool(state_report.get("ok")) if state_report is not None else False,
            "trade_ok": bool((trade_report.get("status") or {}).get("strict_alignment_pass")) if trade_report else False,
            "action_ok": bool((action_report.get("status") or {}).get("strict_alignment_pass")) if action_report else False,
            "live_paper_ok": bool((live_paper_report.get("status") or {}).get("strict_alignment_pass"))
            if live_paper_report
            else (not bool(args.require_live_paper)),
            "live_paper_decision_trace_ok": (
                bool((live_paper_decision_trace_report.get("status") or {}).get("strict_alignment_pass"))
                or bool(live_paper_decision_trace_skipped_empty_paper)
            )
            if live_paper_decision_trace_report
            else (
                (not bool(args.require_live_paper_decision_trace))
                or bool(live_paper_decision_trace_skipped_empty_paper)
            ),
            "live_paper_decision_trace_skipped_empty_paper": bool(
                live_paper_decision_trace_skipped_empty_paper
            ),
            "manifest_snapshot_strict_replace": bool(manifest_snapshot_strict_replace),
            "seed_apply_strict_replace": bool(seed_apply_strict_replace),
            "event_order_ok": bool((event_order_report.get("status") or {}).get("order_parity_pass"))
            if event_order_report
            else (not bool(args.require_event_order)),
            "gpu_parity_ok": all(gpu_lane_status.values()) if gpu_lane_status else (not bool(args.require_gpu_parity)),
            "gpu_parity_lane_status": gpu_lane_status,
            "trade_residual_count": len((trade_report or {}).get("accepted_residuals") or []),
            "action_residual_count": len((action_report or {}).get("accepted_residuals") or []),
            "live_paper_residual_count": len((live_paper_report or {}).get("accepted_residuals") or []),
        },
        "market_data_provenance": {
            "candles_provenance_checked": candles_provenance_checked,
            "candles_provenance_ok": candles_provenance_ok,
            "manifest": manifest_candles_provenance,
            "recomputed": recomputed_candles_provenance,
        },
        "snapshot_position_state_provenance": {
            "snapshot_path": str(snapshot_init_state_path) if snapshot_init_state_path else None,
            "provenance": snapshot_position_state_provenance,
            "trades_only_positions": int(snapshot_trades_only_positions),
        },
        "live_run_fingerprint_provenance": live_run_fingerprint_provenance,
        "failure_count": len(failures),
        "failures": failures,
    }

    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    output_path = Path(args.output).expanduser().resolve() if args.output else (bundle_dir / "alignment_gate_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    print(output_path.as_posix())

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
