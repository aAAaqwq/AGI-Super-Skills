#!/usr/bin/env python3
"""Deployment-time YAML validation (AQC-706).

This validator is designed to fail fast before writing a config to a running engine.

It checks:
- YAML parses and has the expected `global` mapping shape.
- A minimal set of required fields exist with sane types/ranges.

It does not attempt to validate strategy performance, only configuration structure.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import yaml

MAX_SAFE_LEVERAGE = 20.0
MAX_ENTRY_ORDERS_PER_LOOP = 20
MAX_ADDS_PER_SYMBOL = 10
VALID_CONFIDENCE_LEVELS = {"low", "medium", "high"}
VALID_ENGINE_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"}
VALID_MACD_HIST_ENTRY_MODES = {"accel", "sign", "none"}


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _get_path(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


_MISSING = object()


def _get_path_or_missing(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def validate_config_obj(obj: Any) -> list[str]:
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["YAML root must be a mapping"]

    glob = obj.get("global")
    if not isinstance(glob, dict):
        return ["Missing required mapping: global"]

    def req_map(path: str) -> dict[str, Any] | None:
        v = _get_path(obj, path)
        if not isinstance(v, dict):
            errs.append(f"Missing required mapping: {path}")
            return None
        return v

    def req_number(path: str, *, min_v: float | None = None, max_v: float | None = None) -> None:
        v = _get_path(obj, path)
        if not _is_number(v):
            errs.append(f"Missing/invalid number: {path}")
            return
        fv = float(v)
        if not math.isfinite(fv):
            errs.append(f"Missing/invalid number: {path}")
            return
        if min_v is not None and fv < float(min_v):
            errs.append(f"Out of range (min {min_v}): {path}={fv}")
        if max_v is not None and fv > float(max_v):
            errs.append(f"Out of range (max {max_v}): {path}={fv}")

    def req_int(path: str, *, min_v: int | None = None, max_v: int | None = None) -> None:
        v = _get_path(obj, path)
        if isinstance(v, bool) or not isinstance(v, int):
            # Do not accept floats here: keep windows/limits unambiguous.
            errs.append(f"Missing/invalid int: {path}")
            return
        iv = int(v)
        if min_v is not None and iv < int(min_v):
            errs.append(f"Out of range (min {min_v}): {path}={iv}")
        if max_v is not None and iv > int(max_v):
            errs.append(f"Out of range (max {max_v}): {path}={iv}")

    def req_bool(path: str) -> None:
        v = _get_path(obj, path)
        if not isinstance(v, bool):
            errs.append(f"Missing/invalid bool: {path}")

    def req_enum(path: str, *, allowed: set[str]) -> None:
        v = _get_path(obj, path)
        if not isinstance(v, str):
            errs.append(f"Missing/invalid enum: {path}")
            return
        s = str(v).strip().lower()
        if s not in allowed:
            vals = ", ".join(sorted(allowed))
            errs.append(f"Out of range (allowed: {vals}): {path}={v!r}")

    def opt_number(path: str, *, min_v: float | None = None, max_v: float | None = None) -> None:
        if _get_path_or_missing(obj, path) is _MISSING:
            return
        req_number(path, min_v=min_v, max_v=max_v)

    def opt_int(path: str, *, min_v: int | None = None, max_v: int | None = None) -> None:
        if _get_path_or_missing(obj, path) is _MISSING:
            return
        req_int(path, min_v=min_v, max_v=max_v)

    def opt_enum(path: str, *, allowed: set[str]) -> None:
        if _get_path_or_missing(obj, path) is _MISSING:
            return
        req_enum(path, allowed=allowed)

    # Required mappings
    req_map("global.trade")
    req_map("global.indicators")
    req_map("global.thresholds.entry")

    # Core trade sizing/execution fields
    req_number("global.trade.allocation_pct", min_v=0.0, max_v=1.0)
    req_number("global.trade.leverage", min_v=0.0, max_v=MAX_SAFE_LEVERAGE)
    req_number("global.trade.leverage_low", min_v=0.0, max_v=MAX_SAFE_LEVERAGE)
    req_number("global.trade.leverage_medium", min_v=0.0, max_v=MAX_SAFE_LEVERAGE)
    req_number("global.trade.leverage_high", min_v=0.0, max_v=MAX_SAFE_LEVERAGE)
    req_number("global.trade.sl_atr_mult", min_v=0.0)
    req_number("global.trade.tp_atr_mult", min_v=0.0)
    req_number("global.trade.slippage_bps", min_v=0.0)
    req_int("global.trade.max_open_positions", min_v=1)
    req_int(
        "global.trade.max_entry_orders_per_loop",
        min_v=1,
        max_v=MAX_ENTRY_ORDERS_PER_LOOP,
    )
    req_number("global.trade.max_total_margin_pct", min_v=0.0, max_v=1.0)
    req_number("global.trade.min_notional_usd", min_v=0.0)
    req_number("global.trade.min_atr_pct", min_v=0.0, max_v=1.0)
    opt_number("global.trade.tp_partial_pct", min_v=0.0, max_v=1.0)
    opt_int("global.trade.max_adds_per_symbol", min_v=0, max_v=MAX_ADDS_PER_SYMBOL)
    opt_number("global.trade.trailing_start_atr", min_v=0.000001)
    opt_number("global.trade.trailing_distance_atr", min_v=0.000001)
    opt_enum("global.trade.entry_min_confidence", allowed=VALID_CONFIDENCE_LEVELS)
    req_bool("global.trade.bump_to_min_notional")

    # Key indicator windows
    req_int("global.indicators.adx_window", min_v=1)
    req_int("global.indicators.ema_fast_window", min_v=1)
    req_int("global.indicators.ema_slow_window", min_v=1)
    req_int("global.indicators.bb_window", min_v=1)
    req_int("global.indicators.atr_window", min_v=1)

    # Entry threshold sanity
    req_number("global.thresholds.entry.min_adx", min_v=0.0)
    opt_enum("global.thresholds.entry.macd_hist_entry_mode", allowed=VALID_MACD_HIST_ENTRY_MODES)
    opt_enum("global.engine.interval", allowed=VALID_ENGINE_INTERVALS)
    opt_enum("global.engine.entry_interval", allowed=VALID_ENGINE_INTERVALS)
    opt_enum("global.engine.exit_interval", allowed=VALID_ENGINE_INTERVALS)

    # Invariants
    fast = _get_path(obj, "global.indicators.ema_fast_window")
    slow = _get_path(obj, "global.indicators.ema_slow_window")
    if isinstance(fast, int) and isinstance(slow, int) and fast >= slow:
        errs.append("Invalid invariant: global.indicators.ema_fast_window must be < ema_slow_window")

    return errs


def validate_yaml_text(text: str) -> list[str]:
    try:
        obj = yaml.safe_load(text) or {}
    except Exception as e:
        return [f"YAML parse error: {type(e).__name__}: {e}"]
    return validate_config_obj(obj)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a strategy overrides YAML before deploying.")
    ap.add_argument("--config", required=True, help="Path to a YAML config file to validate.")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config).expanduser().resolve()
    text = cfg_path.read_text(encoding="utf-8")
    errs = validate_yaml_text(text)
    if errs:
        for e in errs:
            print(f"[invalid] {e}")
        return 1
    print("[ok] config validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
