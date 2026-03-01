#!/usr/bin/env python3
"""Monte Carlo / bootstrap analysis on trade outcomes (AQC-506).

This tool consumes a trade-level CSV export from `mei-backtester replay --export-trades`
and estimates confidence intervals for total return and max drawdown.

Notes and limitations:
- Funding events are not included in the trade export (exit events only), so funding PnL
  is excluded from this analysis.
- The export is grouped by symbol; this tool re-sorts by `exit_ts_ms` to approximate
  the realised PnL timeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DistSummary:
    n: int
    mean: float
    stdev: float
    p02_5: float
    p05: float
    p50: float
    p95: float
    p97_5: float


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _quantile(sorted_xs: list[float], q: float) -> float:
    if not sorted_xs:
        return 0.0
    if q <= 0.0:
        return float(sorted_xs[0])
    if q >= 1.0:
        return float(sorted_xs[-1])

    n = len(sorted_xs)
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if hi <= lo:
        return float(sorted_xs[lo])
    w = pos - lo
    return float(sorted_xs[lo] * (1.0 - w) + sorted_xs[hi] * w)


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / float(len(xs) or 1))


def _stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / float(len(xs) - 1)
    return float(math.sqrt(var))


def summarise_dist(xs: list[float]) -> DistSummary:
    xs_sorted = sorted([float(x) for x in xs])
    return DistSummary(
        n=int(len(xs_sorted)),
        mean=_mean(xs_sorted),
        stdev=_stdev(xs_sorted),
        p02_5=_quantile(xs_sorted, 0.025),
        p05=_quantile(xs_sorted, 0.05),
        p50=_quantile(xs_sorted, 0.50),
        p95=_quantile(xs_sorted, 0.95),
        p97_5=_quantile(xs_sorted, 0.975),
    )


def load_trade_deltas_csv(path: Path) -> list[tuple[int, float]]:
    """Return a list of (exit_ts_ms, net_pnl_usd) sorted by exit time."""
    rows: list[tuple[int, float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r:
                continue
            try:
                ts = int(float(r.get("exit_ts_ms", "0") or 0))
                pnl = float(r.get("pnl_usd", "0") or 0.0)
                fee = float(r.get("fee_usd", "0") or 0.0)
            except Exception:
                continue
            rows.append((ts, pnl - fee))

    rows.sort(key=lambda x: x[0])
    return rows


def compute_path_stats(deltas: list[float], *, initial_balance: float) -> dict[str, float]:
    equity = float(initial_balance)
    peak = float(equity)
    max_dd = 0.0

    for d in deltas:
        equity += float(d)
        if equity > peak:
            peak = equity
        if peak > 0.0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

    total_return_pct = (equity - float(initial_balance)) / float(initial_balance) if initial_balance != 0 else 0.0
    return {
        "final_balance": float(equity),
        "total_return_pct": float(total_return_pct),
        "max_drawdown_pct": float(max_dd),
    }


def _run_bootstrap(
    deltas: list[float],
    *,
    initial_balance: float,
    iters: int,
    rng: random.Random,
) -> tuple[list[float], list[float]]:
    n = len(deltas)
    if n == 0 or iters <= 0:
        return [], []

    returns: list[float] = []
    dds: list[float] = []

    for _ in range(int(iters)):
        sample = rng.choices(deltas, k=n)
        st = compute_path_stats(sample, initial_balance=float(initial_balance))
        returns.append(float(st["total_return_pct"]))
        dds.append(float(st["max_drawdown_pct"]))

    return returns, dds


def _run_shuffle(
    deltas: list[float],
    *,
    initial_balance: float,
    iters: int,
    rng: random.Random,
) -> tuple[list[float], list[float]]:
    n = len(deltas)
    if n == 0 or iters <= 0:
        return [], []

    returns: list[float] = []
    dds: list[float] = []

    base = list(deltas)
    for _ in range(int(iters)):
        xs = list(base)
        rng.shuffle(xs)
        st = compute_path_stats(xs, initial_balance=float(initial_balance))
        returns.append(float(st["total_return_pct"]))
        dds.append(float(st["max_drawdown_pct"]))

    return returns, dds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute Monte Carlo CIs for return and drawdown from trade CSV.")
    ap.add_argument("--trades-csv", required=True, help="Trade export CSV from mei-backtester replay --export-trades.")
    ap.add_argument("--initial-balance", type=float, required=True, help="Initial balance used for replay.")
    ap.add_argument("--iters", type=int, default=2000, help="Number of Monte Carlo iterations (default: 2000).")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42).")
    ap.add_argument(
        "--methods",
        default="bootstrap",
        help="Comma-separated methods: bootstrap,shuffle (default: bootstrap).",
    )
    ap.add_argument("--output", required=True, help="Write JSON summary to this path.")
    args = ap.parse_args(argv)

    trades_csv = Path(args.trades_csv).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    rows = load_trade_deltas_csv(trades_csv)
    deltas = [d for _ts, d in rows]

    baseline = compute_path_stats(deltas, initial_balance=float(args.initial_balance))

    methods = [m.strip() for m in str(args.methods).split(",") if m.strip()]
    iters = int(args.iters)
    if iters < 0:
        iters = 0

    rng = random.Random(int(args.seed))

    results: dict[str, Any] = {
        "version": "mc_bootstrap_v1",
        "trades_csv": str(trades_csv),
        "initial_balance": float(args.initial_balance),
        "n_trades": int(len(deltas)),
        "baseline": baseline,
        "iters": int(iters),
        "seed": int(args.seed),
        "methods": list(methods),
        "distributions": {},
    }

    for m in methods:
        if m == "bootstrap":
            rets, dds = _run_bootstrap(deltas, initial_balance=float(args.initial_balance), iters=iters, rng=rng)
        elif m == "shuffle":
            rets, dds = _run_shuffle(deltas, initial_balance=float(args.initial_balance), iters=iters, rng=rng)
        else:
            raise SystemExit(f"Unknown method: {m!r}")

        results["distributions"][m] = {
            "return_pct": summarise_dist(rets).__dict__ if rets else DistSummary(0, 0, 0, 0, 0, 0, 0, 0).__dict__,
            "max_drawdown_pct": summarise_dist(dds).__dict__ if dds else DistSummary(0, 0, 0, 0, 0, 0, 0, 0).__dict__,
        }

    _write_json(out_path, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

