#!/usr/bin/env python3
"""Run CPU/GPU smoke parity for one replay bundle scope.

This helper reuses the same lane-A/lane-B parity semantics used by existing GPU
smoke parity tooling, but binds the run window to the replay bundle manifest
(`interval`, `from_ts`, `to_ts`) so parity evidence is scoped to the same
deterministic replay context.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

try:
    import yaml
except Exception:  # pragma: no cover - optional runtime dependency
    yaml = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bundle-scoped CPU/GPU smoke parity.")
    parser.add_argument("--bundle-dir", required=True, help="Replay bundle directory")
    parser.add_argument("--repo-root", help="Repo root path (default: inferred from script location)")
    parser.add_argument(
        "--bundle-manifest",
        default="replay_bundle_manifest.json",
        help="Replay bundle manifest filename/path",
    )
    parser.add_argument("--candles-db", help="Optional candles DB override path")
    parser.add_argument("--funding-db", help="Optional funding DB override path")
    parser.add_argument("--interval", help="Optional interval override (default: bundle manifest)")
    parser.add_argument("--from-ts", type=int, help="Optional start timestamp override (ms)")
    parser.add_argument("--to-ts", type=int, help="Optional end timestamp override (ms)")
    parser.add_argument("--output", help="Output parity report JSON path")
    return parser


def _resolve_under(base: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (base / p).resolve()


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    log_path.write_text(stdout + ("\n" if stdout and stderr else "") + stderr, encoding="utf-8")
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="")
    return int(proc.returncode)


def _load_config_sub_intervals(config_path: Path) -> tuple[str, str]:
    if yaml is None or not config_path.exists():
        return "", ""
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "", ""
    if not isinstance(raw, dict):
        return "", ""
    g = raw.get("global") or {}
    if not isinstance(g, dict):
        return "", ""
    eng = g.get("engine") or {}
    if not isinstance(eng, dict):
        return "", ""
    entry = str(eng.get("entry_interval") or "").strip()
    exit_ = str(eng.get("exit_interval") or "").strip()
    return entry, exit_


def _resolve_parity_config_path(repo_root: Path) -> Path:
    env_raw = str(os.environ.get("AQC_PARITY_CONFIG_PATH") or "").strip()
    if env_raw:
        p = Path(env_raw).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"AQC_PARITY_CONFIG_PATH does not exist: {p}")
        return p

    primary = (repo_root / "config" / "strategy_overrides.yaml").resolve()
    if primary.exists():
        return primary

    fallback = (repo_root / "config" / "strategy_overrides.yaml.example").resolve()
    if fallback.exists():
        print(
            f"[bundle-gpu-parity] config not found at {primary}; using fallback {fallback}",
        )
        return fallback

    return primary


def _derive_interval_db(base_candles_db: Path, interval: str) -> Path | None:
    iv = str(interval or "").strip()
    if not iv:
        return None
    name = base_candles_db.name
    if not (name.startswith("candles_") and name.endswith(".db")):
        return None
    candidate = (base_candles_db.parent / f"candles_{iv}.db").resolve()
    if candidate.exists():
        return candidate
    return None


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir).expanduser().resolve()
    if not bundle_dir.exists():
        parser.error(f"bundle directory not found: {bundle_dir}")

    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    if not repo_root.exists():
        parser.error(f"repo root not found: {repo_root}")

    manifest_path = _resolve_under(bundle_dir, args.bundle_manifest)
    if not manifest_path.exists():
        parser.error(f"bundle manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        parser.error("bundle manifest is not a JSON object")

    inputs = manifest.get("inputs") or {}
    interval = str(args.interval or inputs.get("interval") or "").strip()
    from_ts = int(args.from_ts if args.from_ts is not None else int(inputs.get("from_ts") or 0))
    to_ts = int(args.to_ts if args.to_ts is not None else int(inputs.get("to_ts") or 0))
    candles_db_raw = str(args.candles_db or os.environ.get("CANDLES_DB") or inputs.get("candles_db") or "").strip()
    funding_db_raw = str(args.funding_db or os.environ.get("FUNDING_DB") or inputs.get("funding_db") or "").strip()

    if not interval:
        parser.error("interval is missing (provide --interval or manifest inputs.interval)")
    if from_ts > to_ts:
        parser.error("from-ts must be <= to-ts")
    if not candles_db_raw:
        parser.error("candles DB path is missing (provide --candles-db or CANDLES_DB)")

    candles_db = Path(candles_db_raw).expanduser().resolve()
    if not candles_db.exists():
        parser.error(f"candles DB not found: {candles_db}")
    funding_db: Path | None = None
    if funding_db_raw:
        funding_db = Path(funding_db_raw).expanduser().resolve()
        if not funding_db.exists():
            parser.error(f"funding DB not found: {funding_db}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (bundle_dir / "gpu_smoke_parity_report.json").resolve()
    )
    lane_a_cpu_path = (bundle_dir / "gpu_parity_lane_a_cpu.jsonl").resolve()
    lane_a_gpu_path = (bundle_dir / "gpu_parity_lane_a_gpu.jsonl").resolve()
    lane_b_cpu_path = (bundle_dir / "gpu_parity_lane_b_cpu.jsonl").resolve()
    lane_b_gpu_path = (bundle_dir / "gpu_parity_lane_b_gpu.jsonl").resolve()
    logs_dir = (bundle_dir / "gpu_parity_logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    python_bin = str(os.environ.get("AQC_PARITY_PYTHON") or "python3")
    config_path_obj = _resolve_parity_config_path(repo_root)
    config_path = str(config_path_obj)
    sweep_spec = str(
        Path(os.environ.get("AQC_PARITY_SWEEP_SPEC") or (repo_root / "backtester" / "sweeps" / "smoke.yaml")).resolve()
    )
    cfg_entry_interval, cfg_exit_interval = _load_config_sub_intervals(config_path_obj)
    entry_interval = str(os.environ.get("AQC_PARITY_ENTRY_INTERVAL") or cfg_entry_interval or "").strip()
    exit_interval = str(os.environ.get("AQC_PARITY_EXIT_INTERVAL") or cfg_exit_interval or "").strip()
    entry_candles_db = str(os.environ.get("AQC_PARITY_ENTRY_CANDLES_DB") or "").strip()
    exit_candles_db = str(os.environ.get("AQC_PARITY_EXIT_CANDLES_DB") or "").strip()

    if not entry_candles_db and entry_interval:
        derived = _derive_interval_db(candles_db, entry_interval)
        if derived is not None:
            entry_candles_db = str(derived)
    if not exit_candles_db and exit_interval:
        derived = _derive_interval_db(candles_db, exit_interval)
        if derived is not None:
            exit_candles_db = str(derived)

    if entry_candles_db and not entry_interval:
        parser.error(
            "AQC_PARITY_ENTRY_CANDLES_DB is set but no entry interval is configured "
            "(set AQC_PARITY_ENTRY_INTERVAL or config global.engine.entry_interval)"
        )
    if entry_interval and not entry_candles_db and entry_interval != interval:
        parser.error(
            f"entry interval '{entry_interval}' requires entry candles DB "
            "(set AQC_PARITY_ENTRY_CANDLES_DB or provide candles_{entry_interval}.db beside {candles_db})"
        )
    if exit_candles_db and not exit_interval:
        parser.error(
            "AQC_PARITY_EXIT_CANDLES_DB is set but no exit interval is configured "
            "(set AQC_PARITY_EXIT_INTERVAL or config global.engine.exit_interval)"
        )
    if exit_interval and not exit_candles_db and exit_interval != interval:
        parser.error(
            f"exit interval '{exit_interval}' requires exit candles DB "
            "(set AQC_PARITY_EXIT_CANDLES_DB or provide candles_{exit_interval}.db beside {candles_db})"
        )

    bt_dir = (repo_root / "backtester").resolve()
    if not bt_dir.exists():
        parser.error(f"backtester directory not found: {bt_dir}")

    env = os.environ.copy()
    if Path("/usr/lib/wsl/lib").exists():
        env["LD_LIBRARY_PATH"] = f"/usr/lib/wsl/lib:{env.get('LD_LIBRARY_PATH', '')}".rstrip(":")

    def sweep_cmd(*, output: Path, parity_mode: str, gpu: bool) -> list[str]:
        cmd = [
            "cargo",
            "run",
            "-q",
            "--package",
            "bt-cli",
            "--features",
            "gpu",
            "--",
            "sweep",
            "--sweep-spec",
            sweep_spec,
            "--config",
            config_path,
            "--output",
            str(output),
            "--parity-mode",
            parity_mode,
            "--interval",
            interval,
            "--candles-db",
            str(candles_db),
            "--start-ts",
            str(from_ts),
            "--end-ts",
            str(to_ts),
        ]
        if funding_db is not None:
            cmd.extend(["--funding-db", str(funding_db)])
        if entry_interval:
            cmd.extend(["--entry-interval", entry_interval])
        if exit_interval:
            cmd.extend(["--exit-interval", exit_interval])
        if entry_interval:
            if entry_candles_db:
                cmd.extend(["--entry-candles-db", str(Path(entry_candles_db).expanduser().resolve())])
        if exit_interval:
            if exit_candles_db:
                cmd.extend(["--exit-candles-db", str(Path(exit_candles_db).expanduser().resolve())])
        if gpu:
            cmd.append("--gpu")
        return cmd

    sweep_jobs = [
        ("lane_a_cpu", sweep_cmd(output=lane_a_cpu_path, parity_mode="identical-symbol-universe", gpu=False)),
        ("lane_a_gpu", sweep_cmd(output=lane_a_gpu_path, parity_mode="identical-symbol-universe", gpu=True)),
        ("lane_b_cpu", sweep_cmd(output=lane_b_cpu_path, parity_mode="production", gpu=False)),
        ("lane_b_gpu", sweep_cmd(output=lane_b_gpu_path, parity_mode="production", gpu=True)),
    ]

    for name, cmd in sweep_jobs:
        print(f"[bundle-gpu-parity] running {name}: {' '.join(shlex.quote(x) for x in cmd)}")
        rc = _run(cmd, cwd=bt_dir, env=env, log_path=logs_dir / f"{name}.log")
        if rc != 0:
            print(f"[bundle-gpu-parity] FAIL: {name} exited with code {rc}")
            return rc

    cmp_cmd = [
        python_bin,
        str((repo_root / "tools" / "compare_sweep_outputs.py").resolve()),
        "--lane-a-cpu",
        str(lane_a_cpu_path),
        "--lane-a-gpu",
        str(lane_a_gpu_path),
        "--lane-b-cpu",
        str(lane_b_cpu_path),
        "--lane-b-gpu",
        str(lane_b_gpu_path),
        "--output",
        str(output_path),
        "--print-summary",
        "--fail-on-assert",
    ]

    baseline_map = {
        "AQC_PARITY_BASELINE_ANY_MISMATCH_COUNT": "--baseline-any-mismatch-count",
        "AQC_PARITY_BASELINE_MAX_ABS_PNL_DIFF": "--baseline-max-abs-total-pnl-diff",
        "AQC_PARITY_BASELINE_MEAN_ABS_PNL_DIFF": "--baseline-mean-abs-total-pnl-diff",
        "AQC_PARITY_BASELINE_TRADE_COUNT_MISMATCH_COUNT": "--baseline-trade-count-mismatch-count",
    }
    for env_name, arg_name in baseline_map.items():
        raw = str(env.get(env_name) or "").strip()
        if raw:
            cmp_cmd.extend([arg_name, raw])

    print(f"[bundle-gpu-parity] running compare: {' '.join(shlex.quote(x) for x in cmp_cmd)}")
    rc = _run(cmp_cmd, cwd=repo_root, env=env, log_path=logs_dir / "compare.log")
    if rc != 0:
        print(f"[bundle-gpu-parity] FAIL: compare exited with code {rc}")
        return rc

    print(f"[bundle-gpu-parity] PASS: report written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
