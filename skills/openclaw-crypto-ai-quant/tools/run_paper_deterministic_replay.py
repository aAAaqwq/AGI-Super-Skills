#!/usr/bin/env python3
"""Run the full paper deterministic replay harness for a prepared replay bundle."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute full paper deterministic replay flow for a replay bundle.")
    parser.add_argument("--bundle-dir", required=True, help="Path to replay bundle directory")
    parser.add_argument("--repo-root", help="Repo root path (default: inferred from script location)")
    parser.add_argument("--live-db", help="Optional LIVE_DB override")
    parser.add_argument("--paper-db", help="Optional PAPER_DB override")
    parser.add_argument("--candles-db", help="Optional CANDLES_DB override")
    parser.add_argument("--funding-db", help="Optional FUNDING_DB override")
    parser.add_argument(
        "--strict-no-residuals",
        action="store_true",
        default=False,
        help="Run final alignment gate with --strict-no-residuals",
    )
    parser.add_argument(
        "--output",
        help="Optional output report path (default: <bundle-dir>/paper_deterministic_replay_run.json)",
    )
    return parser


def _now_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _run_step(
    *,
    step_name: str,
    command: list[str],
    env: dict[str, str],
    cwd: Path,
    logs_dir: Path,
) -> dict[str, Any]:
    start_ms = _now_ms()
    proc = subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True)
    end_ms = _now_ms()

    stdout_log = logs_dir / f"{step_name}.stdout.log"
    stderr_log = logs_dir / f"{step_name}.stderr.log"
    stdout_log.write_text(proc.stdout or "", encoding="utf-8")
    stderr_log.write_text(proc.stderr or "", encoding="utf-8")

    return {
        "step": step_name,
        "command": " ".join(shlex.quote(x) for x in command),
        "exit_code": int(proc.returncode),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "duration_ms": int(end_ms - start_ms),
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir).expanduser().resolve()
    if not bundle_dir.exists():
        parser.error(f"bundle directory not found: {bundle_dir}")

    if args.repo_root:
        repo_root = Path(args.repo_root).expanduser().resolve()
    else:
        repo_root = Path(__file__).resolve().parents[1]

    if not repo_root.exists():
        parser.error(f"repo root not found: {repo_root}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (bundle_dir / "paper_deterministic_replay_run.json").resolve()
    )
    logs_dir = (bundle_dir / "harness_logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["REPO_ROOT"] = str(repo_root)
    if args.live_db:
        env["LIVE_DB"] = str(Path(args.live_db).expanduser().resolve())
    if args.paper_db:
        env["PAPER_DB"] = str(Path(args.paper_db).expanduser().resolve())
    if args.candles_db:
        env["CANDLES_DB"] = str(Path(args.candles_db).expanduser().resolve())
    if args.funding_db:
        env["FUNDING_DB"] = str(Path(args.funding_db).expanduser().resolve())

    script_steps = [
        ("export_and_seed", bundle_dir / "run_01_export_and_seed.sh"),
        ("replay", bundle_dir / "run_02_replay.sh"),
        ("state_audit", bundle_dir / "run_03_audit.sh"),
        ("trade_reconcile", bundle_dir / "run_04_trade_reconcile.sh"),
        ("action_reconcile", bundle_dir / "run_05_action_reconcile.sh"),
        ("live_paper_action_reconcile", bundle_dir / "run_06_live_paper_action_reconcile.sh"),
        ("live_paper_decision_trace_reconcile", bundle_dir / "run_07_live_paper_decision_trace_reconcile.sh"),
        ("gpu_parity", bundle_dir / "run_07c_gpu_parity.sh"),
        ("event_order_parity", bundle_dir / "run_07b_event_order_parity.sh"),
    ]

    steps: list[dict[str, Any]] = []
    overall_ok = True
    failed_step: str | None = None

    for step_name, script_path in script_steps:
        if not script_path.exists():
            steps.append(
                {
                    "step": step_name,
                    "command": str(script_path),
                    "exit_code": 127,
                    "start_ms": _now_ms(),
                    "end_ms": _now_ms(),
                    "duration_ms": 0,
                    "stdout_log": "",
                    "stderr_log": "",
                    "error": f"missing script: {script_path}",
                }
            )
            overall_ok = False
            failed_step = step_name
            break

        result = _run_step(
            step_name=step_name,
            command=["bash", str(script_path)],
            env=env,
            cwd=repo_root,
            logs_dir=logs_dir,
        )
        steps.append(result)
        if int(result["exit_code"]) != 0:
            overall_ok = False
            failed_step = step_name
            break

    if overall_ok:
        gate_report = bundle_dir / "alignment_gate_report.json"
        max_strategy_sha1_distinct_raw = str(env.get("AQC_MAX_STRATEGY_SHA1_DISTINCT") or "1").strip()
        try:
            max_strategy_sha1_distinct = max(1, int(max_strategy_sha1_distinct_raw))
        except Exception:
            max_strategy_sha1_distinct = 1
        max_oms_strategy_sha1_distinct_raw = str(
            env.get("AQC_MAX_OMS_STRATEGY_SHA1_DISTINCT") or str(max_strategy_sha1_distinct)
        ).strip()
        try:
            max_oms_strategy_sha1_distinct = max(1, int(max_oms_strategy_sha1_distinct_raw))
        except Exception:
            max_oms_strategy_sha1_distinct = max_strategy_sha1_distinct
        require_oms_strategy_provenance = _env_bool("AQC_REQUIRE_OMS_STRATEGY_PROVENANCE", True)
        gate_cmd = [
            "python3",
            str((repo_root / "tools" / "assert_replay_bundle_alignment.py").resolve()),
            "--bundle-dir",
            str(bundle_dir),
            "--live-paper-report",
            str((bundle_dir / "live_paper_action_reconcile_report.json").resolve()),
            "--require-live-paper",
            "--live-paper-decision-trace-report",
            str((bundle_dir / "live_paper_decision_trace_reconcile_report.json").resolve()),
            "--require-live-paper-decision-trace",
            "--event-order-report",
            str((bundle_dir / "event_order_parity_report.json").resolve()),
            "--require-event-order",
            "--gpu-parity-report",
            str((bundle_dir / "gpu_smoke_parity_report.json").resolve()),
            "--require-gpu-parity",
            "--require-runtime-strategy-provenance",
            "--max-strategy-sha1-distinct",
            str(max_strategy_sha1_distinct),
            "--require-locked-strategy-match",
            "--output",
            str(gate_report),
        ]
        if require_oms_strategy_provenance:
            gate_cmd.extend(
                [
                    "--require-oms-strategy-provenance",
                    "--max-oms-strategy-sha1-distinct",
                    str(max_oms_strategy_sha1_distinct),
                ]
            )
        if args.strict_no_residuals:
            gate_cmd.append("--strict-no-residuals")
        candles_db_for_gate = str(env.get("CANDLES_DB") or "").strip()
        if candles_db_for_gate:
            gate_cmd.extend(["--candles-db", candles_db_for_gate])

        gate_result = _run_step(
            step_name="alignment_gate",
            command=gate_cmd,
            env=env,
            cwd=repo_root,
            logs_dir=logs_dir,
        )
        steps.append(gate_result)
        if int(gate_result["exit_code"]) != 0:
            overall_ok = False
            failed_step = "alignment_gate"

    report = {
        "schema_version": 1,
        "generated_at_ms": _now_ms(),
        "bundle_dir": str(bundle_dir),
        "repo_root": str(repo_root),
        "strict_no_residuals": bool(args.strict_no_residuals),
        "ok": bool(overall_ok),
        "failed_step": failed_step,
        "step_count": len(steps),
        "steps": steps,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_path.as_posix())

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
