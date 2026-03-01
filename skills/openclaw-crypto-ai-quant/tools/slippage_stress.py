#!/usr/bin/env python3
"""Slippage stress runner for candidate configs.

For a given config, run CPU replay under multiple slippage levels and compute a
"slippage fragility" metric.

This is designed to be used by the strategy factory pipeline to reject configs
that only work under optimistic friction assumptions.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_backtester_cmd() -> list[str]:
    env_bin = os.getenv("MEI_BACKTESTER_BIN", "").strip()
    if env_bin:
        return [env_bin]

    rel = AIQ_ROOT / "backtester" / "target" / "release" / "mei-backtester"
    if rel.exists():
        return [str(rel)]

    return ["cargo", "run", "-p", "bt-cli", "--bin", "mei-backtester", "--"]


def _run_cmd(argv: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as out_f, stderr_path.open("w", encoding="utf-8") as err_f:
        proc = subprocess.run(argv, cwd=str(cwd), stdout=out_f, stderr=err_f, check=False, text=True)
    return int(proc.returncode)


def _summarise_replay_report(path: Path) -> dict[str, Any]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "config_id": str(d.get("config_id", "")),
        "initial_balance": float(d.get("initial_balance") or 0.0),
        "final_balance": float(d.get("final_balance") or 0.0),
        "total_pnl": float(d.get("total_pnl") or 0.0),
        "total_trades": int(d.get("total_trades") or 0),
        "win_rate": float(d.get("win_rate") or 0.0),
        "profit_factor": float(d.get("profit_factor") or 0.0),
        "sharpe_ratio": float(d.get("sharpe_ratio") or 0.0),
        "max_drawdown_pct": float(d.get("max_drawdown_pct") or 0.0),
        "total_fees": float(d.get("total_fees") or 0.0),
        "slippage_bps": float(d.get("slippage_bps") or 0.0),
    }


def _parse_bps_list(raw: str) -> list[float]:
    out: list[float] = []
    seen: set[float] = set()
    for part in str(raw or "").replace("\n", ",").split(","):
        s = part.strip()
        if not s:
            continue
        try:
            v = float(s)
        except Exception:
            raise SystemExit(f"Invalid slippage bps value: {s!r}")
        if v <= 0:
            raise SystemExit(f"Slippage bps must be > 0 (got {v})")
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    if not out:
        raise SystemExit("No slippage bps values provided")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run slippage stress replays and compute fragility metrics.")
    ap.add_argument("--config", required=True, help="Strategy YAML config path.")
    ap.add_argument("--interval", default="1h", help="Main interval for replay (default: 1h).")
    ap.add_argument("--candles-db", default=None, help="Optional candle DB path override.")
    ap.add_argument("--funding-db", default=None, help="Optional funding DB path for replay.")
    ap.add_argument("--slippage-bps", default="10,20,30", help="Comma-separated slippage bps levels (default: 10,20,30).")
    ap.add_argument(
        "--reject-flip-bps",
        type=float,
        default=20.0,
        help="Reject when PnL flips sign at this slippage level (default: 20).",
    )
    ap.add_argument("--out-dir", default="slippage_stress", help="Directory to write per-level replay outputs.")
    ap.add_argument("--output", default=None, help="Write summary JSON to this path (default: <out-dir>/summary.json).")
    args = ap.parse_args(argv)

    t0 = time.time()
    config_path = (AIQ_ROOT / str(args.config)).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    bps_levels = _parse_bps_list(str(args.slippage_bps))
    reject_bps = float(args.reject_flip_bps)
    if reject_bps <= 0:
        raise SystemExit("--reject-flip-bps must be > 0")
    if reject_bps not in {float(x) for x in bps_levels}:
        raise SystemExit("--reject-flip-bps must be included in --slippage-bps levels.")

    interval = str(args.interval).strip()
    if not interval:
        raise SystemExit("--interval cannot be empty")

    out_dir = (Path(args.out_dir).expanduser().resolve() if Path(args.out_dir).is_absolute() else (AIQ_ROOT / args.out_dir).resolve())
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.output).expanduser().resolve() if args.output else (out_dir / "summary.json")

    bt_cmd = _resolve_backtester_cmd()

    results: list[dict[str, Any]] = []
    pnl_by_bps: dict[float, float] = {}
    dd_by_bps: dict[float, float] = {}
    init_balance: float = 0.0
    failed_levels: list[dict[str, Any]] = []

    for bps in bps_levels:
        lvl_dir = out_dir / f"{bps:g}bps"
        lvl_dir.mkdir(parents=True, exist_ok=True)
        replay_out = lvl_dir / "replay.json"
        replay_stdout = lvl_dir / "replay.stdout.txt"
        replay_stderr = lvl_dir / "replay.stderr.txt"

        replay_argv = bt_cmd + [
            "replay",
            "--config",
            str(config_path),
            "--interval",
            str(interval),
            "--slippage-bps",
            str(bps),
            "--output",
            str(replay_out),
        ]
        if args.candles_db:
            replay_argv += [
                "--candles-db",
                str(args.candles_db),
                "--exit-candles-db",
                str(args.candles_db),
                "--entry-candles-db",
                str(args.candles_db),
            ]
        if args.funding_db:
            replay_argv += ["--funding-db", str(args.funding_db)]

        rc = _run_cmd(replay_argv, cwd=AIQ_ROOT / "backtester", stdout_path=replay_stdout, stderr_path=replay_stderr)
        if rc != 0:
            failure = {
                "slippage_bps": float(bps),
                "ok": False,
                "metrics": None,
                "exit_code": int(rc),
                "stderr_path": str(replay_stderr),
                "error": f"replay_failed_exit_{int(rc)}",
            }
            failed_levels.append(failure)
            results.append(failure)
            continue

        try:
            rpt = _summarise_replay_report(replay_out)
        except Exception as e:
            failure = {
                "slippage_bps": float(bps),
                "ok": False,
                "metrics": None,
                "exit_code": int(rc),
                "stderr_path": str(replay_stderr),
                "error": f"report_parse_error: {type(e).__name__}: {e}",
            }
            failed_levels.append(failure)
            results.append(failure)
            continue

        init_balance = float(rpt.get("initial_balance", 0.0) or 0.0)
        pnl = float(rpt.get("total_pnl", 0.0) or 0.0)
        dd = float(rpt.get("max_drawdown_pct", 0.0) or 0.0)
        pnl_by_bps[float(bps)] = pnl
        dd_by_bps[float(bps)] = dd
        results.append({"slippage_bps": float(bps), "ok": True, "metrics": rpt})

    baseline_bps = float(bps_levels[0])
    has_baseline = baseline_bps in pnl_by_bps
    has_reject = reject_bps in pnl_by_bps
    baseline_pnl = float(pnl_by_bps.get(baseline_bps, 0.0))
    reject_pnl = float(pnl_by_bps.get(reject_bps, 0.0))

    pnl_drop_reject = baseline_pnl - reject_pnl
    fragility_frac = pnl_drop_reject / init_balance if init_balance > 0 else 0.0

    degraded_reasons: list[str] = []
    if failed_levels:
        degraded_reasons.append("replay_failure")
    if not has_baseline:
        degraded_reasons.append("missing_baseline_level")
    if not has_reject:
        degraded_reasons.append("missing_reject_level")
    degraded = bool(degraded_reasons)

    flip_sign = bool(has_baseline and has_reject and baseline_pnl > 0 and reject_pnl < 0)
    reject = bool(flip_sign or degraded)
    reject_reasons: list[str] = []
    if flip_sign:
        reject_reasons.append("flip_sign_at_reject_bps")
    if degraded:
        reject_reasons.append("degraded_run")

    summary = {
        "config_path": str(config_path),
        "interval": str(interval),
        "levels_bps": [float(x) for x in bps_levels],
        "reject_flip_bps": float(reject_bps),
        "results": results,
        "aggregate": {
            "baseline_bps": float(baseline_bps),
            "baseline_total_pnl": float(baseline_pnl),
            "pnl_at_reject_bps": float(reject_pnl),
            "pnl_drop_at_reject_bps": float(pnl_drop_reject),
            "slippage_fragility": float(fragility_frac),
            "max_drawdown_pct_worst": float(max(dd_by_bps.values()) if dd_by_bps else 0.0),
            "flip_sign_at_reject_bps": bool(flip_sign),
            "degraded": bool(degraded),
            "degraded_reasons": [str(x) for x in degraded_reasons],
            "failed_levels": [float(x.get("slippage_bps", 0.0)) for x in failed_levels],
            "reject_reasons": [str(x) for x in reject_reasons],
            "reject_reason": str(reject_reasons[0]) if reject_reasons else "",
            "reject": bool(reject),
        },
        "elapsed_s": float(time.time() - t0),
    }

    _write_json(summary_path, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
