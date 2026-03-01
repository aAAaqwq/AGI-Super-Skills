#!/usr/bin/env python3
"""Parameter sensitivity sanity check for a single strategy config.

This tool perturbs a small, pre-defined set of key parameters (one-at-a-time)
and replays each variant on CPU to estimate how fragile the edge is.

It is intentionally simple and deterministic:
- Perturbations are fixed unless overridden via CLI.
- Each variant is saved as a standalone YAML next to its replay report.
- A machine-readable JSON summary is emitted for factory pipeline consumption.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from tools.config_id import config_id_from_yaml_file
except ImportError:  # pragma: no cover
    from config_id import config_id_from_yaml_file  # type: ignore[no-redef]


AIQ_ROOT = Path(__file__).resolve().parent.parent


DEFAULT_PERTURBATIONS: list[tuple[str, float]] = [
    ("indicators.ema_fast_window", -1.0),
    ("indicators.ema_fast_window", +1.0),
    ("indicators.ema_slow_window", -1.0),
    ("indicators.ema_slow_window", +1.0),
    ("indicators.adx_window", -1.0),
    ("indicators.adx_window", +1.0),
    ("indicators.bb_window", -1.0),
    ("indicators.bb_window", +1.0),
    ("thresholds.entry.min_adx", -1.0),
    ("thresholds.entry.min_adx", +1.0),
    ("trade.sl_atr_mult", -0.1),
    ("trade.sl_atr_mult", +0.1),
    ("trade.tp_atr_mult", -0.1),
    ("trade.tp_atr_mult", +0.1),
]


@dataclass(frozen=True)
class CmdResult:
    argv: list[str]
    cwd: str
    exit_code: int
    elapsed_s: float
    timed_out: bool
    stdout_path: str | None
    stderr_path: str | None


def _run_cmd(
    argv: list[str],
    *,
    cwd: Path,
    stdout_path: Path | None,
    stderr_path: Path | None,
    timeout_s: float | None = 600.0,
) -> CmdResult:
    t0 = time.time()

    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_f = stdout_path.open("w", encoding="utf-8")
    else:
        stdout_f = subprocess.DEVNULL  # type: ignore[assignment]

    if stderr_path is not None:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_f = stderr_path.open("w", encoding="utf-8")
    else:
        stderr_f = subprocess.DEVNULL  # type: ignore[assignment]

    timed_out = False
    try:
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                stdout=stdout_f,
                stderr=stderr_f,
                check=False,
                text=True,
                timeout=timeout_s if timeout_s and timeout_s > 0 else None,
            )
            exit_code = int(proc.returncode)
        except subprocess.TimeoutExpired:
            exit_code = 124
            timed_out = True
    finally:
        if hasattr(stdout_f, "close"):
            stdout_f.close()  # type: ignore[call-arg]
        if hasattr(stderr_f, "close"):
            stderr_f.close()  # type: ignore[call-arg]

    return CmdResult(
        argv=list(argv),
        cwd=str(cwd),
        exit_code=exit_code,
        elapsed_s=float(time.time() - t0),
        timed_out=bool(timed_out),
        stdout_path=str(stdout_path) if stdout_path is not None else None,
        stderr_path=str(stderr_path) if stderr_path is not None else None,
    )


def _resolve_backtester_cmd() -> list[str]:
    env_bin = os.getenv("MEI_BACKTESTER_BIN", "").strip()
    if env_bin:
        return [env_bin]

    rel = AIQ_ROOT / "backtester" / "target" / "release" / "mei-backtester"
    if rel.exists():
        return [str(rel)]

    return ["cargo", "run", "-p", "bt-cli", "--bin", "mei-backtester", "--"]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML root mapping: {path}")
    return data


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _get_nested(data: dict[str, Any], dotpath: str, default: Any = None) -> Any:
    if not dotpath.startswith("global."):
        dotpath = "global." + dotpath
    keys = dotpath.split(".")
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _set_nested(data: dict[str, Any], dotpath: str, value: Any) -> None:
    if not dotpath.startswith("global."):
        dotpath = "global." + dotpath
    keys = dotpath.split(".")
    cur: Any = data
    for k in keys[:-1]:
        if k not in cur or cur[k] is None:
            cur[k] = {}
        cur = cur[k]
        if not isinstance(cur, dict):
            raise ValueError(f"Non-mapping node for {dotpath} at {k!r}")
    cur[keys[-1]] = value


def _coerce_perturbed_value(old: Any, new_raw: float) -> Any:
    if isinstance(old, bool):
        return bool(new_raw)
    if isinstance(old, int) and not isinstance(old, bool):
        return int(round(float(new_raw)))
    if isinstance(old, float):
        return float(new_raw)
    # Fallback: keep float.
    return float(new_raw)


def _validate_variant(config: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, reason_if_not_ok)."""
    def _parse_window_int(value: Any, *, name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
        if isinstance(value, int):
            return int(value)

        num = float(value)
        if not num.is_integer():
            raise ValueError(f"{name} must be an integer")
        return int(num)

    # Basic sanity: windows must be >0.
    fast = _get_nested(config, "indicators.ema_fast_window", None)
    slow = _get_nested(config, "indicators.ema_slow_window", None)
    parsed_fast: int | None = None
    parsed_slow: int | None = None
    for name, v in [("ema_fast_window", fast), ("ema_slow_window", slow)]:
        if v is None:
            continue
        try:
            parsed = _parse_window_int(v, name=name)
            if parsed <= 0:
                return False, f"{name} must be > 0"
        except Exception:
            return False, f"{name} must be an integer"
        if name == "ema_fast_window":
            parsed_fast = parsed
        else:
            parsed_slow = parsed
    if fast is not None and slow is not None:
        if parsed_fast is None or parsed_slow is None:
            return False, "ema windows must be integers"
        if parsed_fast >= parsed_slow:
            return False, "ema_fast_window must be < ema_slow_window"

    for dotpath in ["trade.sl_atr_mult", "trade.tp_atr_mult"]:
        v = _get_nested(config, dotpath, None)
        if v is None:
            continue
        try:
            if float(v) <= 0.0:
                return False, f"{dotpath} must be > 0"
        except Exception:
            return False, f"{dotpath} must be a number"

    return True, ""


def _compute_aggregate(base_total_pnl: float, variants: list[dict[str, Any]]) -> dict[str, Any]:
    ran = [v for v in variants if int(v.get("exit_code", 1)) == 0]
    pnls = [float(v.get("total_pnl", 0.0)) for v in ran]
    dds = [float(v.get("max_drawdown_pct", 0.0)) for v in ran]

    pnls_sorted = sorted(pnls)
    dds_sorted = sorted(dds)

    def _median(xs: list[float]) -> float:
        if not xs:
            return 0.0
        n = len(xs)
        mid = n // 2
        if n % 2 == 1:
            return float(xs[mid])
        return float(xs[mid - 1] + xs[mid]) / 2.0

    positive_rate = float(sum(1 for p in pnls if p > 0.0)) / float(len(pnls) or 1)
    metric_v1 = positive_rate

    baseline = float(base_total_pnl)
    median_pnl = _median(pnls_sorted)
    median_pnl_ratio = (median_pnl / abs(baseline)) if abs(baseline) > 1e-9 else 0.0

    return {
        "variants_total": int(len(variants)),
        "variants_ran": int(len(ran)),
        "variants_skipped": int(len(variants) - len(ran)),
        "positive_rate": float(positive_rate),
        "median_total_pnl": float(median_pnl),
        "min_total_pnl": float(min(pnls_sorted) if pnls_sorted else 0.0),
        "max_total_pnl": float(max(pnls_sorted) if pnls_sorted else 0.0),
        "median_drawdown_pct": float(_median(dds_sorted)),
        "baseline_total_pnl": float(baseline),
        "median_pnl_ratio_vs_baseline_abs": float(median_pnl_ratio),
        "sensitivity_metric_v1": float(metric_v1),
    }


def _parse_perturbations(csv: str | None) -> list[tuple[str, float]]:
    if not csv:
        return list(DEFAULT_PERTURBATIONS)
    out: list[tuple[str, float]] = []
    for item in str(csv).split(","):
        item = item.strip()
        if not item:
            continue
        # Format: dotpath:delta
        if ":" not in item:
            raise SystemExit(f"Invalid --perturb item (expected dotpath:delta): {item!r}")
        dotpath, delta_s = item.split(":", 1)
        try:
            delta = float(delta_s.strip())
        except ValueError as exc:
            raise SystemExit(f"Invalid --perturb delta (expected number): {item!r}") from exc
        out.append((dotpath.strip(), delta))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Perturb key parameters and replay variants to estimate sensitivity.")
    ap.add_argument("--config", required=True, help="Base YAML config to perturb.")
    ap.add_argument("--interval", default="1h", help="Main interval for replay (default: 1h).")
    ap.add_argument("--candles-db", default=None, help="Optional candle DB path override.")
    ap.add_argument("--funding-db", default=None, help="Optional funding DB path override.")
    ap.add_argument(
        "--baseline-replay-report",
        default=None,
        help="Optional baseline replay JSON to avoid rerunning the base config.",
    )
    ap.add_argument(
        "--perturb",
        default=None,
        help="Comma-separated perturbations in dotpath:delta format. Default is an internal fixed set.",
    )
    ap.add_argument("--out-dir", required=True, help="Output directory for configs/replays/logs.")
    ap.add_argument("--output", required=True, help="Write JSON summary to this path.")
    ap.add_argument(
        "--timeout-s",
        type=int,
        default=600,
        help="Per-replay timeout in seconds (default: 600, 0 = no timeout).",
    )
    args = ap.parse_args(argv)

    cfg_path = Path(args.config).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base_cfg = _load_yaml(cfg_path)
    base_cfg_id = config_id_from_yaml_file(cfg_path)

    baseline_obj: dict[str, Any] = {}
    if args.baseline_replay_report:
        baseline_obj = _load_json(Path(args.baseline_replay_report).expanduser().resolve())

    base_total_pnl = float(baseline_obj.get("total_pnl", 0.0)) if baseline_obj else 0.0
    base_max_dd = float(baseline_obj.get("max_drawdown_pct", 0.0)) if baseline_obj else 0.0
    base_trades = int(baseline_obj.get("total_trades", 0) or 0) if baseline_obj else 0

    bt_cmd = _resolve_backtester_cmd()

    perturbations = _parse_perturbations(args.perturb)
    variants: list[dict[str, Any]] = []

    cfgs_dir = out_dir / "configs"
    replays_dir = out_dir / "replays"
    logs_dir = out_dir / "logs"
    cfgs_dir.mkdir(parents=True, exist_ok=True)
    replays_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    for dotpath, delta in perturbations:
        old = _get_nested(base_cfg, dotpath, None)
        if old is None:
            variants.append(
                {
                    "dotpath": dotpath,
                    "delta": float(delta),
                    "skip": True,
                    "skip_reason": "missing parameter in config",
                }
            )
            continue

        new_val = _coerce_perturbed_value(old, float(old) + float(delta))

        v_cfg = copy.deepcopy(base_cfg)
        _set_nested(v_cfg, dotpath, new_val)
        ok, why = _validate_variant(v_cfg)
        if not ok:
            variants.append(
                {
                    "dotpath": dotpath,
                    "delta": float(delta),
                    "old": old,
                    "new": new_val,
                    "skip": True,
                    "skip_reason": why,
                }
            )
            continue

        delta_tag = str(delta).replace("-", "m").replace(".", "p")
        safe_path = dotpath.replace(".", "_")
        v_yaml = cfgs_dir / f"variant__{safe_path}__d{delta_tag}.yaml"
        _dump_yaml(v_yaml, v_cfg)
        v_cfg_id = config_id_from_yaml_file(v_yaml)

        v_json = replays_dir / f"{v_yaml.stem}.replay.json"
        v_stdout = logs_dir / f"{v_yaml.stem}.stdout.txt"
        v_stderr = logs_dir / f"{v_yaml.stem}.stderr.txt"

        replay_argv = bt_cmd + [
            "replay",
            "--config",
            str(v_yaml),
            "--interval",
            str(args.interval),
            "--output",
            str(v_json),
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

        timeout_s = float(args.timeout_s) if int(args.timeout_s or 0) > 0 else None
        res = _run_cmd(
            replay_argv,
            cwd=AIQ_ROOT / "backtester",
            stdout_path=v_stdout,
            stderr_path=v_stderr,
            timeout_s=timeout_s,
        )

        entry: dict[str, Any] = {
            "dotpath": dotpath,
            "delta": float(delta),
            "old": old,
            "new": new_val,
            "config_path": str(v_yaml),
            "config_id": str(v_cfg_id),
            "replay_report_path": str(v_json),
            "cmd": res.__dict__,
            "exit_code": int(res.exit_code),
            "elapsed_s": float(res.elapsed_s),
        }

        if res.exit_code == 0 and v_json.exists():
            try:
                rpt = _load_json(v_json)
                entry["total_pnl"] = float(rpt.get("total_pnl", 0.0))
                entry["max_drawdown_pct"] = float(rpt.get("max_drawdown_pct", 0.0))
                entry["total_trades"] = int(rpt.get("total_trades", 0) or 0)
            except Exception as e:
                entry["parse_error"] = f"{type(e).__name__}: {e}"

        variants.append(entry)

    out = {
        "version": "sensitivity_v1",
        "base": {
            "config_path": str(cfg_path),
            "config_id": str(base_cfg_id),
            "baseline_replay_report_path": str(args.baseline_replay_report or ""),
            "total_pnl": float(base_total_pnl),
            "max_drawdown_pct": float(base_max_dd),
            "total_trades": int(base_trades),
        },
        "perturbations": variants,
        "aggregate": _compute_aggregate(base_total_pnl, variants),
    }
    _write_json(out_path, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
