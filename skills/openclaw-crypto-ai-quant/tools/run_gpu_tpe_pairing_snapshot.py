#!/usr/bin/env python3
"""Run reproducible GPU TPE sweep -> CPU pairing with immutable input snapshots.

This harness snapshots config and DB inputs into an artefact directory, then runs:
1) GPU TPE sweep for each trial count
2) CPU single-combo recheck on deterministic random samples

All rechecks are executed against the snapped files to avoid drift from live DB updates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

@dataclass(frozen=True)
class SnapshotFile:
    source: Path
    snapped: Path
    sha256: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _snapshot(src: Path, dst: Path) -> SnapshotFile:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return SnapshotFile(source=src, snapped=dst, sha256=_sha256(dst))


def _run(cmd: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> None:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open(
        "w", encoding="utf-8"
    ) as err:
        proc = subprocess.run(cmd, cwd=str(cwd), stdout=out, stderr=err)
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout={stdout_path}\n"
            f"stderr={stderr_path}"
        )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalise_overrides(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out[str(item[0])] = item[1]
        return out
    return {}


def _build_single_spec(
    *,
    full_spec: Path,
    sample_row: dict[str, Any],
    output_spec: Path,
    allow_missing_axes: bool,
) -> None:
    src = yaml.safe_load(full_spec.read_text(encoding="utf-8"))
    if not isinstance(src, dict):
        raise RuntimeError(f"invalid sweep spec root: {full_spec}")
    axes = src.get("axes")
    if not isinstance(axes, list):
        raise RuntimeError(f"invalid sweep spec axes: {full_spec}")

    overrides = _normalise_overrides(sample_row.get("overrides"))
    if not overrides:
        raise RuntimeError("sample row has no overrides")

    axis_paths: list[str] = []
    for axis in axes:
        if not isinstance(axis, dict) or "path" not in axis:
            raise RuntimeError("invalid axis entry in sweep spec")
        axis_paths.append(str(axis["path"]))

    axis_paths_set = set(axis_paths)
    missing_paths = sorted(path for path in axis_paths if path not in overrides)
    extra_paths = sorted(path for path in overrides if path not in axis_paths_set)
    if (missing_paths or extra_paths) and not allow_missing_axes:
        missing_preview = missing_paths[:5]
        extra_preview = extra_paths[:5]
        raise RuntimeError(
            "sample row override coverage mismatch: "
            f"missing={len(missing_paths)} {missing_preview}, "
            f"extra={len(extra_paths)} {extra_preview}"
        )

    out = dict(src)
    out_axes: list[dict[str, Any]] = []
    for axis in axes:
        path = str(axis["path"])
        axis_out = dict(axis)
        if path in overrides:
            axis_out["values"] = [overrides[path]]
        elif allow_missing_axes:
            old_values = axis_out.get("values")
            if isinstance(old_values, list) and old_values:
                axis_out["values"] = [old_values[0]]
            else:
                axis_out["values"] = [0.0]
        else:
            raise RuntimeError(f"missing axis override for path={path}")
        out_axes.append(axis_out)
    out["axes"] = out_axes

    output_spec.parent.mkdir(parents=True, exist_ok=True)
    output_spec.write_text(yaml.safe_dump(out, sort_keys=False), encoding="utf-8")


def _snapshot_meta(sf: SnapshotFile | None) -> dict[str, str] | None:
    if sf is None:
        return None
    return {
        "source": str(sf.source),
        "snapped": str(sf.snapped),
        "sha256": sf.sha256,
    }


def _pair_trial(
    *,
    backtester_dir: Path,
    mei_backtester: Path,
    config_snapshot: Path,
    sweep_spec_full: Path,
    sweep_rows_path: Path,
    pairing_dir: Path,
    sample_n: int,
    seed: int,
    candles_db: Path,
    interval: str,
    entry_candles_db: Path | None,
    entry_interval: str | None,
    exit_candles_db: Path | None,
    exit_interval: str | None,
    funding_db: Path | None,
    balance_from: Path | None,
    start_ts: int | None,
    end_ts: int | None,
    allow_missing_axes: bool,
    pairing_pnl_abs_tol: float,
    pairing_pnl_rel_tol: float,
) -> dict[str, Any]:
    rows = _read_jsonl(sweep_rows_path)
    if len(rows) < sample_n:
        raise RuntimeError(
            f"not enough rows to sample: requested={sample_n}, available={len(rows)} ({sweep_rows_path})"
        )

    rng = random.Random(seed)
    sample_indices = rng.sample(range(len(rows)), sample_n)

    (pairing_dir / "samples").mkdir(parents=True, exist_ok=True)
    (pairing_dir / "specs").mkdir(parents=True, exist_ok=True)
    (pairing_dir / "cpu_rows").mkdir(parents=True, exist_ok=True)

    base_cmd = [
        str(mei_backtester),
        "sweep",
        "--config",
        str(config_snapshot),
        "--candles-db",
        str(candles_db),
        "--interval",
        interval,
        "--output-mode",
        "candidate",
    ]
    if entry_candles_db and entry_interval:
        base_cmd.extend(
            [
                "--entry-candles-db",
                str(entry_candles_db),
                "--entry-interval",
                entry_interval,
            ]
        )
    if exit_candles_db and exit_interval:
        base_cmd.extend(
            [
                "--exit-candles-db",
                str(exit_candles_db),
                "--exit-interval",
                exit_interval,
            ]
        )
    if funding_db:
        base_cmd.extend(["--funding-db", str(funding_db)])
    if balance_from:
        base_cmd.extend(["--balance-from", str(balance_from)])
    if start_ts is not None:
        base_cmd.extend(["--start-ts", str(start_ts)])
    if end_ts is not None:
        base_cmd.extend(["--end-ts", str(end_ts)])

    report_rows: list[dict[str, Any]] = []
    for i, row_idx in enumerate(sample_indices, start=1):
        name = f"sample_{i:02d}"
        sample_row = rows[row_idx]
        sample_path = pairing_dir / "samples" / f"{name}.json"
        _write_json(sample_path, sample_row)

        spec_path = pairing_dir / "specs" / f"{name}.yaml"
        _build_single_spec(
            full_spec=sweep_spec_full,
            sample_row=sample_row,
            output_spec=spec_path,
            allow_missing_axes=allow_missing_axes,
        )

        cpu_row_path = pairing_dir / "cpu_rows" / f"{name}.jsonl"
        cmd = base_cmd + ["--sweep-spec", str(spec_path), "--output", str(cpu_row_path)]
        proc = subprocess.run(
            cmd,
            cwd=str(backtester_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"CPU pairing run failed for {name}")

        cpu_rows = _read_jsonl(cpu_row_path)
        if not cpu_rows:
            raise RuntimeError(f"CPU pairing row is empty for {name}")
        cpu_row = cpu_rows[0]

        sweep_pnl = float(sample_row.get("total_pnl", 0.0))
        cpu_pnl = float(cpu_row.get("total_pnl", 0.0))
        sweep_trades = int(sample_row.get("total_trades", 0))
        cpu_trades = int(cpu_row.get("total_trades", 0))
        pnl_diff = cpu_pnl - sweep_pnl
        trades_diff = cpu_trades - sweep_trades
        abs_pnl_diff = abs(pnl_diff)
        pnl_scale = max(abs(cpu_pnl), abs(sweep_pnl), 1.0)
        pnl_tol = max(float(pairing_pnl_abs_tol), float(pairing_pnl_rel_tol) * pnl_scale)

        report_rows.append(
            {
                "sample": name,
                "sample_index": row_idx,
                "sweep_total_pnl": sweep_pnl,
                "cpu_total_pnl": cpu_pnl,
                "pnl_diff": pnl_diff,
                "abs_pnl_diff": abs_pnl_diff,
                "pnl_tol": pnl_tol,
                "sweep_total_trades": sweep_trades,
                "cpu_total_trades": cpu_trades,
                "trades_diff": trades_diff,
                "pass": (trades_diff == 0 and abs_pnl_diff <= pnl_tol),
            }
        )

    summary = {
        "total": len(report_rows),
        "pass": sum(1 for r in report_rows if r["pass"]),
        "fail": sum(1 for r in report_rows if not r["pass"]),
        "trade_diff_zero": sum(1 for r in report_rows if r["trades_diff"] == 0),
        "max_abs_pnl_diff": max((abs(r["pnl_diff"]) for r in report_rows), default=0.0),
        "max_pnl_tol": max((float(r.get("pnl_tol") or 0.0) for r in report_rows), default=0.0),
        "max_abs_trades_diff": max((abs(r["trades_diff"]) for r in report_rows), default=0),
        "seed": seed,
        "pairing_pnl_abs_tol": float(pairing_pnl_abs_tol),
        "pairing_pnl_rel_tol": float(pairing_pnl_rel_tol),
    }
    _write_json(pairing_dir / "pairing_report.json", {"rows": report_rows, "summary": summary})
    return summary


def _parse_trials(value: str) -> list[int]:
    out: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise argparse.ArgumentTypeError("trial list must not be empty")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run immutable-input GPU TPE sweep and CPU pairing checks.",
    )
    p.add_argument("--repo-root", default=".", help="Repository root path")
    p.add_argument("--out-dir", required=True, help="Output artefact directory")
    p.add_argument("--config", required=True, help="Base strategy YAML path")
    p.add_argument("--sweep-spec", required=True, help="Full sweep spec YAML path")
    p.add_argument("--candles-db", required=True, help="Main interval candles DB path")
    p.add_argument("--interval", required=True, help="Main interval (for example 30m)")
    p.add_argument("--entry-candles-db", help="Entry interval candles DB path")
    p.add_argument("--entry-interval", help="Entry interval (for example 3m)")
    p.add_argument("--exit-candles-db", help="Exit interval candles DB path")
    p.add_argument("--exit-interval", help="Exit interval (for example 3m)")
    p.add_argument("--funding-db", help="Funding rates DB path")
    p.add_argument("--balance-from", help="Path to initial balance JSON file")
    p.add_argument("--start-ts", type=int, help="Fixed start timestamp (ms)")
    p.add_argument("--end-ts", type=int, help="Fixed end timestamp (ms)")
    p.add_argument(
        "--trials",
        type=_parse_trials,
        default=[5000, 10000, 20000],
        help="Comma-separated TPE trial counts, for example 5000,10000,20000",
    )
    p.add_argument("--sample-count", type=int, default=10, help="Pairing samples per trial")
    p.add_argument("--tpe-batch", type=int, default=256, help="GPU TPE batch size")
    p.add_argument("--sweep-top-k", type=int, default=50000, help="GPU sweep top-k retention")
    p.add_argument(
        "--pairing-pnl-abs-tol",
        type=float,
        default=1e-5,
        help="Absolute total_pnl tolerance for GPU->CPU pairing pass/fail",
    )
    p.add_argument(
        "--pairing-pnl-rel-tol",
        type=float,
        default=1e-8,
        help="Relative total_pnl tolerance for GPU->CPU pairing pass/fail",
    )
    p.add_argument(
        "--allow-missing-axes",
        action="store_true",
        help=(
            "Allow sample rows with incomplete axis coverage; missing axes fall back "
            "to the first configured axis value."
        ),
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    backtester_dir = repo_root / "backtester"
    mei_backtester = backtester_dir / "target" / "release" / "mei-backtester"
    if not mei_backtester.exists():
        raise SystemExit(f"missing binary: {mei_backtester}")

    out_dir = Path(args.out_dir).resolve()
    state_dir = out_dir / "state"
    logs_dir = out_dir / "logs"
    sweeps_dir = out_dir / "sweeps"
    pairing_root = out_dir / "pairing"
    out_dir.mkdir(parents=True, exist_ok=True)
    sweeps_dir.mkdir(parents=True, exist_ok=True)
    pairing_root.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()

    snapped_cfg = _snapshot(Path(args.config).resolve(), state_dir / "config_snapshot.yaml")
    snapped_candles = _snapshot(Path(args.candles_db).resolve(), state_dir / "candles_main.db")
    snapped_entry: SnapshotFile | None = None
    snapped_exit: SnapshotFile | None = None
    snapped_funding: SnapshotFile | None = None
    snapped_balance: SnapshotFile | None = None
    if args.entry_candles_db:
        snapped_entry = _snapshot(
            Path(args.entry_candles_db).resolve(), state_dir / "candles_entry.db"
        )
    if args.exit_candles_db:
        snapped_exit = _snapshot(
            Path(args.exit_candles_db).resolve(), state_dir / "candles_exit.db"
        )
    if args.funding_db:
        snapped_funding = _snapshot(
            Path(args.funding_db).resolve(), state_dir / "funding_rates.db"
        )
    if args.balance_from:
        snapped_balance = _snapshot(
            Path(args.balance_from).resolve(), state_dir / "initial_balance.json"
        )

    final_summary: dict[str, Any] = {
        "out_dir": str(out_dir),
        "generated_at_utc": ts,
        "inputs": {
            "config": _snapshot_meta(snapped_cfg),
            "candles_main": _snapshot_meta(snapped_candles),
            "candles_entry": _snapshot_meta(snapped_entry),
            "candles_exit": _snapshot_meta(snapped_exit),
            "funding_db": _snapshot_meta(snapped_funding),
            "balance_from": _snapshot_meta(snapped_balance),
            "interval": args.interval,
            "entry_interval": args.entry_interval,
            "exit_interval": args.exit_interval,
            "start_ts": args.start_ts,
            "end_ts": args.end_ts,
            "trials": args.trials,
            "sample_count": args.sample_count,
            "tpe_batch": args.tpe_batch,
            "sweep_top_k": args.sweep_top_k,
            "pairing_pnl_abs_tol": args.pairing_pnl_abs_tol,
            "pairing_pnl_rel_tol": args.pairing_pnl_rel_tol,
            "allow_missing_axes": args.allow_missing_axes,
        },
        "trials": [],
    }

    for trial_count in args.trials:
        sweep_out = sweeps_dir / f"gpu_tpe_{trial_count}.jsonl"
        sweep_stdout = logs_dir / f"gpu_tpe_{trial_count}.stdout.txt"
        sweep_stderr = logs_dir / f"gpu_tpe_{trial_count}.stderr.txt"

        cmd = [
            str(mei_backtester),
            "sweep",
            "--config",
            str(snapped_cfg.snapped),
            "--sweep-spec",
            str(Path(args.sweep_spec).resolve()),
            "--candles-db",
            str(snapped_candles.snapped),
            "--interval",
            args.interval,
            "--output",
            str(sweep_out),
            "--output-mode",
            "candidate",
            "--gpu",
            "--tpe",
            "--tpe-trials",
            str(trial_count),
            "--tpe-batch",
            str(args.tpe_batch),
            "--tpe-seed",
            str(trial_count),
            "--sweep-top-k",
            str(args.sweep_top_k),
        ]
        if snapped_entry and args.entry_interval:
            cmd.extend(
                [
                    "--entry-candles-db",
                    str(snapped_entry.snapped),
                    "--entry-interval",
                    args.entry_interval,
                ]
            )
        if snapped_exit and args.exit_interval:
            cmd.extend(
                [
                    "--exit-candles-db",
                    str(snapped_exit.snapped),
                    "--exit-interval",
                    args.exit_interval,
                ]
            )
        if snapped_funding:
            cmd.extend(["--funding-db", str(snapped_funding.snapped)])
        if snapped_balance:
            cmd.extend(["--balance-from", str(snapped_balance.snapped)])
        if args.start_ts is not None:
            cmd.extend(["--start-ts", str(args.start_ts)])
        if args.end_ts is not None:
            cmd.extend(["--end-ts", str(args.end_ts)])

        _run(cmd, cwd=backtester_dir, stdout_path=sweep_stdout, stderr_path=sweep_stderr)

        pairing_dir = pairing_root / f"trials_{trial_count}"
        pairing_summary = _pair_trial(
            backtester_dir=backtester_dir,
            mei_backtester=mei_backtester,
            config_snapshot=snapped_cfg.snapped,
            sweep_spec_full=Path(args.sweep_spec).resolve(),
            sweep_rows_path=sweep_out,
            pairing_dir=pairing_dir,
            sample_n=args.sample_count,
            seed=trial_count,
            candles_db=snapped_candles.snapped,
            interval=args.interval,
            entry_candles_db=snapped_entry.snapped if snapped_entry else None,
            entry_interval=args.entry_interval,
            exit_candles_db=snapped_exit.snapped if snapped_exit else None,
            exit_interval=args.exit_interval,
            funding_db=snapped_funding.snapped if snapped_funding else None,
            balance_from=snapped_balance.snapped if snapped_balance else None,
            start_ts=args.start_ts,
            end_ts=args.end_ts,
            allow_missing_axes=args.allow_missing_axes,
            pairing_pnl_abs_tol=args.pairing_pnl_abs_tol,
            pairing_pnl_rel_tol=args.pairing_pnl_rel_tol,
        )
        final_summary["trials"].append(
            {
                "trial_count": trial_count,
                "pair_total": pairing_summary["total"],
                "pair_pass": pairing_summary["pass"],
                "pair_fail": pairing_summary["fail"],
                "trade_diff_zero": pairing_summary["trade_diff_zero"],
                "max_abs_trades_diff": pairing_summary["max_abs_trades_diff"],
                "max_abs_pnl_diff": pairing_summary["max_abs_pnl_diff"],
                "max_pnl_tol": pairing_summary["max_pnl_tol"],
            }
        )

    _write_json(out_dir / "final_summary_snapshot_inputs.json", final_summary)
    print(json.dumps(final_summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
