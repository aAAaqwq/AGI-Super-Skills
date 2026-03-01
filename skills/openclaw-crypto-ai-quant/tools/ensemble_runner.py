#!/usr/bin/env python3
"""Ensemble runner (AQC-1003).

This tool runs 2-3 strategy daemons concurrently as separate processes.

Rationale
  - The current strategy engine is single-config per process.
  - Running multiple independent configs concurrently is therefore best done as a small
    orchestration layer that launches multiple daemons with different environment variables
    and/or derived YAML configs.

Risk budgeting model (v1)
  - Each strategy process should set its own sizing budget via config overrides
    (e.g. `global.trade.size_multiplier` or `global.trade.allocation_pct`).
  - Global heat/exposure caps remain enforced by the existing RiskManager logic, because each
    live daemon observes the same account positions.

This is an operator tool. It is intentionally conservative:
  - It defaults to dry-run (print plan only).
  - It requires --yes to actually launch.
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    obj = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(obj, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return obj


def _dump_yaml(path: Path, obj: dict[str, Any]) -> None:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base (overlay wins)."""
    out: dict[str, Any] = dict(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_nested(data: dict[str, Any], dotpath: str, value: Any) -> None:
    """Set nested dict value using dot notation.

    Convenience:
      - If dotpath does not start with global/symbols/live/modes/engine, assume global.<dotpath>.
    """
    raw = str(dotpath or "").strip()
    if not raw:
        return
    if not any(raw.startswith(p) for p in ("global.", "symbols.", "live.", "modes.", "engine.")):
        raw = "global." + raw

    keys = raw.split(".")
    cur: Any = data
    for k in keys[:-1]:
        if not isinstance(cur, dict):
            return
        if k not in cur or cur[k] is None:
            cur[k] = {}
        cur = cur[k]
    if isinstance(cur, dict):
        cur[keys[-1]] = value


def _apply_dot_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for k, v in (overrides or {}).items():
        _set_nested(out, str(k), v)
    return out


@dataclass(frozen=True)
class StrategySpec:
    name: str
    strategy_yaml: Path
    overrides: dict[str, Any]
    env: dict[str, str]


@dataclass(frozen=True)
class LaunchPlan:
    name: str
    daemon_argv: list[str]
    env: dict[str, str]
    derived_yaml_path: Path


def _parse_strategy_specs(obj: dict[str, Any], *, root: Path) -> list[StrategySpec]:
    raw = obj.get("strategies")
    if not isinstance(raw, list) or not raw:
        raise ValueError("spec must contain a non-empty 'strategies' list")

    out: list[StrategySpec] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each strategies[] entry must be a mapping")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError("each strategies[] entry must have a non-empty 'name'")

        yaml_path = item.get("strategy_yaml") or item.get("config") or ""
        yaml_path = str(yaml_path).strip()
        if not yaml_path:
            raise ValueError(f"strategies[{name}] missing strategy_yaml")
        p = Path(yaml_path)
        if not p.is_absolute():
            p = (root / p).resolve()

        overrides = item.get("overrides") or {}
        if overrides is None:
            overrides = {}
        if not isinstance(overrides, dict):
            raise ValueError(f"strategies[{name}].overrides must be a mapping of dotpath->value")

        env = item.get("env") or {}
        if env is None:
            env = {}
        if not isinstance(env, dict):
            raise ValueError(f"strategies[{name}].env must be a mapping")
        env2: dict[str, str] = {}
        for k, v in env.items():
            ks = str(k).strip()
            if not ks:
                continue
            env2[ks] = str(v)

        out.append(StrategySpec(name=name, strategy_yaml=p, overrides=dict(overrides), env=env2))

    return out


def build_launch_plan(
    *,
    spec_path: Path,
    out_dir: Path,
    mode: str,
    daemon_argv: list[str],
) -> list[LaunchPlan]:
    root = AIQ_ROOT
    spec_obj = _load_yaml(spec_path)
    strategies = _parse_strategy_specs(spec_obj, root=root)

    if len(strategies) > 3:
        raise ValueError("v1 supports up to 3 strategies (keep it small and auditable)")

    plans: list[LaunchPlan] = []
    for s in strategies:
        base_cfg = _load_yaml(s.strategy_yaml)
        derived = _apply_dot_overrides(base_cfg, s.overrides)

        derived_path = (Path(out_dir) / f"strategy.{s.name}.yaml").resolve()
        _dump_yaml(derived_path, derived)

        env = dict(os.environ)
        env["AI_QUANT_MODE"] = str(mode)
        env["AI_QUANT_STRATEGY_YAML"] = str(derived_path)
        env["AI_QUANT_RUN_ID"] = env.get("AI_QUANT_RUN_ID") or f"ensemble:{s.name}"

        # Split event logs per strategy (defaults to artifacts/events/events.jsonl otherwise).
        env.setdefault("AI_QUANT_EVENT_LOG_DIR", str((AIQ_ROOT / "artifacts" / "events" / f"ensemble_{s.name}").resolve()))

        # Apply per-strategy env overrides last.
        env.update({k: str(v) for k, v in s.env.items()})

        plans.append(
            LaunchPlan(
                name=s.name,
                daemon_argv=list(daemon_argv),
                env=env,
                derived_yaml_path=derived_path,
            )
        )
    return plans


def _terminate_all(procs: list[subprocess.Popen], *, timeout_s: float) -> None:
    if not procs:
        return
    for p in procs:
        try:
            p.send_signal(signal.SIGTERM)
        except Exception:
            pass

    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        if all(p.poll() is not None for p in procs):
            return
        time.sleep(0.1)

    for p in procs:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a small strategy ensemble (AQC-1003).")
    ap.add_argument("--spec", required=True, help="Path to an ensemble YAML spec (see config/ensemble.example.yaml).")
    ap.add_argument(
        "--mode",
        default="dry_live",
        choices=["paper", "dry_live", "live"],
        help="Daemon mode for all strategies (default: dry_live).",
    )
    ap.add_argument(
        "--out-dir",
        default=str((AIQ_ROOT / "artifacts" / "ensemble").resolve()),
        help="Directory for derived YAML configs (default: artifacts/ensemble).",
    )
    ap.add_argument(
        "--daemon-cmd",
        default="python3 -m engine.daemon",
        help="Daemon command to launch (default: python3 -m engine.daemon).",
    )
    ap.add_argument("--yes", action="store_true", help="Actually launch processes (otherwise dry-run).")
    ap.add_argument("--terminate-timeout-s", type=float, default=10.0, help="Graceful shutdown timeout (default: 10s).")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    daemon_argv = shlex.split(str(args.daemon_cmd).strip())

    try:
        plans = build_launch_plan(
            spec_path=spec_path,
            out_dir=out_dir,
            mode=str(args.mode),
            daemon_argv=daemon_argv,
        )
    except Exception as e:
        print(f"[ensemble_runner] FAILED to build plan: {e}", file=sys.stderr)
        return 1

    print("[ensemble_runner] Plan:")
    for p in plans:
        print(f"  - {p.name}: {p.daemon_argv} (AI_QUANT_STRATEGY_YAML={p.derived_yaml_path})")

    if not bool(args.yes):
        print("[ensemble_runner] Dry-run only. Re-run with --yes to launch.", file=sys.stderr)
        return 0

    if str(args.mode) == "live":
        # Extra friction for live launches.
        print("[ensemble_runner] LIVE mode selected. Ensure kill-switch + risk caps are configured.", file=sys.stderr)

    procs: list[subprocess.Popen] = []
    try:
        for p in plans:
            print(f"[ensemble_runner] Launching {p.name}...", file=sys.stderr)
            procs.append(
                subprocess.Popen(
                    p.daemon_argv,
                    cwd=str(AIQ_ROOT),
                    env=p.env,
                )
            )

        # Wait for any child to exit; if one exits, terminate the rest.
        while True:
            for pr in procs:
                rc = pr.poll()
                if rc is not None:
                    print(f"[ensemble_runner] Process exited (rc={rc}); terminating ensemble.", file=sys.stderr)
                    _terminate_all(procs, timeout_s=float(args.terminate_timeout_s))
                    return int(rc)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[ensemble_runner] Interrupted; terminating.", file=sys.stderr)
        _terminate_all(procs, timeout_s=float(args.terminate_timeout_s))
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
