#!/usr/bin/env python3
"""Walk-forward validation runner.

Given a config and a date range, run multiple train/test splits by replaying the
test segment for each split (out-of-sample) and aggregating the results.

This is designed for short 12-19 day windows where full "train -> select -> test"
is impractical in a nightly pipeline, but we still want OOS pressure via multiple
held-out segments.

Output:
- Per-split test metrics
- Aggregated OOS metrics (including median OOS daily return)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


AIQ_ROOT = Path(__file__).resolve().parents[1]
DAY_MS = 86_400_000


@dataclass(frozen=True)
class SplitSpec:
    name: str
    offset_days: int
    train_days: int
    test_days: int


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_ts_to_ms(raw: str) -> int:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("empty timestamp")

    neg = s.startswith("-")
    digits = s[1:] if neg else s
    if digits.isdigit():
        v = int(s)
        # Heuristic: 13+ digits => epoch milliseconds; otherwise seconds.
        if len(digits) >= 13:
            return v
        return v * 1000

    # Normalise Zulu suffix for fromisoformat.
    s2 = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s2)
    except Exception as e:
        raise ValueError(f"invalid ISO8601 timestamp: {s}") from e

    if dt.tzinfo is None:
        # Assume UTC when timezone is omitted.
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _fmt_iso_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_db_paths(raw: str) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()

    for part in str(raw or "").split(","):
        s = part.strip()
        if not s:
            continue
        s = os.path.expandvars(os.path.expanduser(s))
        p = Path(s)

        candidates: list[str] = []
        if p.is_dir():
            candidates = sorted(glob.glob(str(p / "*.db")))
        else:
            expanded = glob.glob(s)
            candidates = sorted(expanded) if expanded else [s]

        for c in candidates:
            cp = Path(c)
            key = str(cp.resolve()) if cp.exists() else str(cp)
            if key in seen:
                continue
            seen.add(key)
            out.append(cp)

    return out


def _query_time_range_multi(*, db_paths: list[Path], interval: str) -> tuple[int, int]:
    min_t: int | None = None
    max_t: int | None = None

    for p in db_paths:
        uri = f"file:{p}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            cur = con.cursor()
            cur.execute("SELECT MIN(t), MAX(t) FROM candles WHERE interval = ?", (str(interval),))
            row = cur.fetchone()
        finally:
            con.close()

        if not row:
            continue
        mn, mx = row[0], row[1]
        if mn is None or mx is None:
            continue
        mn_i = int(mn)
        mx_i = int(mx)
        min_t = mn_i if min_t is None else min(min_t, mn_i)
        max_t = mx_i if max_t is None else max(max_t, mx_i)

    if min_t is None or max_t is None:
        raise RuntimeError(f"no candles found for interval={interval!r} in: {[str(p) for p in db_paths]}")
    return int(min_t), int(max_t)


def _load_engine_intervals_from_config(config_path: Path) -> dict[str, str]:
    d = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(d, dict):
        return {"interval": "1h", "entry_interval": "", "exit_interval": ""}
    g = d.get("global", {})
    if not isinstance(g, dict):
        g = {}
    eng = g.get("engine", {})
    if not isinstance(eng, dict):
        eng = {}
    return {
        "interval": str(eng.get("interval", "1h") or "1h"),
        "entry_interval": str(eng.get("entry_interval", "") or ""),
        "exit_interval": str(eng.get("exit_interval", "") or ""),
    }


def _compute_overlap_range_ms(
    *, config_path: Path, interval: str, candles_db_raw: str | None, scope_entry_exit: bool
) -> tuple[int, int, dict[str, Any]]:
    eng = _load_engine_intervals_from_config(config_path)
    entry_iv = eng.get("entry_interval", "").strip()
    exit_iv = eng.get("exit_interval", "").strip()

    # Mirror backtester scoping rule: scope entry/exit DBs when enabled; otherwise scope the main DB.
    scope_sets: list[tuple[str, str]] = []
    if scope_entry_exit and exit_iv:
        scope_sets.append((f"candles_dbs/candles_{exit_iv}.db", exit_iv))
    if scope_entry_exit and entry_iv:
        scope_sets.append((f"candles_dbs/candles_{entry_iv}.db", entry_iv))
    if not scope_sets:
        raw = candles_db_raw or f"candles_dbs/candles_{interval}.db"
        scope_sets.append((raw, interval))

    ranges: list[dict[str, Any]] = []
    overlap_from: int | None = None
    overlap_to: int | None = None

    for raw, iv in scope_sets:
        paths = _resolve_db_paths(raw)
        mn, mx = _query_time_range_multi(db_paths=paths, interval=iv)
        ranges.append({"raw": raw, "interval": iv, "min_t_ms": mn, "max_t_ms": mx, "paths": [str(p) for p in paths]})
        overlap_from = mn if overlap_from is None else max(overlap_from, mn)
        overlap_to = mx if overlap_to is None else min(overlap_to, mx)

    if overlap_from is None or overlap_to is None or overlap_from > overlap_to:
        raise RuntimeError("no overlapping time range across scoped candle DBs")

    meta = {"scoped_dbs": ranges, "overlap_from_ms": overlap_from, "overlap_to_ms": overlap_to}
    return int(overlap_from), int(overlap_to), meta


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


def _default_splits() -> list[SplitSpec]:
    # Matches the 19-day example in AQC-501.
    return [
        SplitSpec(name="split1", offset_days=0, train_days=12, test_days=7),
        SplitSpec(name="split2", offset_days=3, train_days=12, test_days=4),
        SplitSpec(name="split3", offset_days=0, train_days=9, test_days=10),
    ]


def _parse_splits_from_args(args: argparse.Namespace) -> list[SplitSpec]:
    if args.splits_json:
        p = Path(args.splits_json).expanduser()
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, list):
            raise SystemExit("--splits-json must be a JSON list")
        out: list[SplitSpec] = []
        for i, it in enumerate(d):
            if not isinstance(it, dict):
                continue
            name = str(it.get("name", f"split{i+1}"))
            out.append(
                SplitSpec(
                    name=name,
                    offset_days=int(it.get("offset_days", 0)),
                    train_days=int(it.get("train_days", 0)),
                    test_days=int(it.get("test_days", 0)),
                )
            )
        return out

    if args.split:
        out: list[SplitSpec] = []
        for i, raw in enumerate(args.split):
            s = str(raw or "").strip()
            if not s:
                continue
            name = f"split{i+1}"
            if ":" in s:
                name, s = s.split(":", 1)
                name = name.strip() or f"split{i+1}"
            parts = [p.strip() for p in s.split(",") if p.strip()]
            if len(parts) != 3:
                raise SystemExit(f"Invalid --split '{raw}'. Expected 'train_days,test_days,offset_days' or 'name:train,test,offset'.")
            train_d, test_d, off_d = (int(parts[0]), int(parts[1]), int(parts[2]))
            out.append(SplitSpec(name=name, offset_days=off_d, train_days=train_d, test_days=test_d))
        return out

    return _default_splits()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run walk-forward validation via multiple OOS splits.")
    ap.add_argument("--config", required=True, help="Strategy YAML config path.")
    ap.add_argument("--interval", default="1h", help="Main interval for replay (default: 1h).")
    ap.add_argument("--candles-db", default=None, help="Optional candle DB path override.")
    ap.add_argument("--funding-db", default=None, help="Optional funding DB path for replay.")

    ap.add_argument("--start-ts", default=None, help="Overall start timestamp (ISO8601 or epoch s/ms).")
    ap.add_argument("--end-ts", default=None, help="Overall end timestamp (ISO8601 or epoch s/ms).")
    ap.add_argument(
        "--no-scope-entry-exit",
        action="store_false",
        dest="scope_entry_exit",
        default=True,
        help="Do not scope to entry/exit candle DBs (scope using main candle DB only).",
    )

    ap.add_argument("--splits-json", default=None, help="Optional JSON file defining split specs.")
    ap.add_argument(
        "--split",
        action="append",
        default=[],
        help="Override splits: 'train_days,test_days,offset_days' or 'name:train,test,offset'. May be repeated.",
    )
    ap.add_argument("--min-test-days", type=int, default=1, help="Skip splits with shorter OOS than this (default: 1).")

    ap.add_argument("--out-dir", default="walk_forward", help="Directory to write per-split replay outputs.")
    ap.add_argument("--output", default=None, help="Write summary JSON to this path (default: <out-dir>/summary.json).")
    args = ap.parse_args(argv)

    t0 = time.time()
    config_path = (AIQ_ROOT / str(args.config)).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    interval = str(args.interval).strip()
    if not interval:
        raise SystemExit("--interval cannot be empty")

    overlap_from, overlap_to, overlap_meta = _compute_overlap_range_ms(
        config_path=config_path,
        interval=interval,
        candles_db_raw=str(args.candles_db) if args.candles_db else None,
        scope_entry_exit=bool(args.scope_entry_exit),
    )

    start_ms = _parse_ts_to_ms(args.start_ts) if args.start_ts else overlap_from
    end_ms = _parse_ts_to_ms(args.end_ts) if args.end_ts else overlap_to
    if start_ms < overlap_from or end_ms > overlap_to:
        raise SystemExit(
            "Requested range is outside DB coverage overlap: "
            f"requested={_fmt_iso_utc(start_ms)}..{_fmt_iso_utc(end_ms)} "
            f"overlap={_fmt_iso_utc(overlap_from)}..{_fmt_iso_utc(overlap_to)}"
        )
    if start_ms > end_ms:
        raise SystemExit("--start-ts must be <= --end-ts")

    splits = _parse_splits_from_args(args)
    if not splits:
        raise SystemExit("No splits configured")

    out_dir = (Path(args.out_dir).expanduser().resolve() if Path(args.out_dir).is_absolute() else (AIQ_ROOT / args.out_dir).resolve())
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.output).expanduser().resolve() if args.output else (out_dir / "summary.json")

    bt_cmd = _resolve_backtester_cmd()

    split_results: list[dict[str, Any]] = []
    oos_daily_returns: list[float] = []
    oos_dd: list[float] = []

    for spec in splits:
        if spec.train_days <= 0 or spec.test_days <= 0:
            continue
        if spec.offset_days < 0:
            continue

        split_start = start_ms + int(spec.offset_days) * DAY_MS
        train_end = split_start + int(spec.train_days) * DAY_MS - 1
        test_start = train_end + 1
        test_end = test_start + int(spec.test_days) * DAY_MS - 1

        if split_start < start_ms or train_end >= end_ms or test_start > end_ms:
            continue
        if test_end > end_ms:
            test_end = end_ms
        test_days_actual = (test_end - test_start + 1) / DAY_MS
        if test_days_actual < float(int(args.min_test_days)):
            continue

        split_dir = out_dir / spec.name
        split_dir.mkdir(parents=True, exist_ok=True)
        replay_out = split_dir / "replay.json"
        replay_stdout = split_dir / "replay.stdout.txt"
        replay_stderr = split_dir / "replay.stderr.txt"

        replay_argv = bt_cmd + [
            "replay",
            "--config",
            str(config_path),
            "--interval",
            str(interval),
            "--start-ts",
            str(int(test_start)),
            "--end-ts",
            str(int(test_end)),
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
            raise SystemExit(f"Replay failed for {spec.name} (exit {rc}). See {replay_stderr}.")

        rpt = _summarise_replay_report(replay_out)
        days = max(1e-9, float(test_days_actual))
        init_bal = float(rpt.get("initial_balance", 0.0) or 0.0)
        daily_ret = float(rpt.get("total_pnl", 0.0) or 0.0) / init_bal / days if init_bal > 0 else 0.0
        oos_daily_returns.append(float(daily_ret))
        oos_dd.append(float(rpt.get("max_drawdown_pct", 0.0) or 0.0))

        split_results.append(
            {
                "name": spec.name,
                "offset_days": int(spec.offset_days),
                "train_days": int(spec.train_days),
                "test_days": int(spec.test_days),
                "test_range": {
                    "start_ms": int(test_start),
                    "end_ms": int(test_end),
                    "start_iso": _fmt_iso_utc(int(test_start)),
                    "end_iso": _fmt_iso_utc(int(test_end)),
                    "days": float(test_days_actual),
                },
                "metrics": rpt,
                "oos_daily_return": float(daily_ret),
            }
        )

    if not split_results:
        raise SystemExit("No valid splits produced any results (check date range and split specs).")

    median_oos_daily_return = float(statistics.median(oos_daily_returns)) if oos_daily_returns else 0.0
    max_oos_drawdown_pct = float(max(oos_dd)) if oos_dd else 0.0

    summary = {
        "config_path": str(config_path),
        "interval": str(interval),
        "requested_range": {
            "start_ms": int(start_ms),
            "end_ms": int(end_ms),
            "start_iso": _fmt_iso_utc(int(start_ms)),
            "end_iso": _fmt_iso_utc(int(end_ms)),
            "days": float((end_ms - start_ms + 1) / DAY_MS),
        },
        "auto_scope": overlap_meta,
        "splits": split_results,
        "aggregate": {
            "oos_daily_returns": [float(x) for x in oos_daily_returns],
            "median_oos_daily_return": float(median_oos_daily_return),
            "max_oos_drawdown_pct": float(max_oos_drawdown_pct),
            # A minimal scalar for ranking until the full stability score (AQC-504) is wired in.
            "walk_forward_score_v1": float(median_oos_daily_return),
        },
        "elapsed_s": float(time.time() - t0),
    }

    _write_json(summary_path, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
