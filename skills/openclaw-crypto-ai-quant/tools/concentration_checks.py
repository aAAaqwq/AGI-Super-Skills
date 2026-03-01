#!/usr/bin/env python3
"""Concentration / diversification checks for a replay report (AQC-503).

This tool consumes the JSON produced by `mei-backtester replay` and computes:
- %PnL from top 1 symbol
- %PnL from top 5 symbols
- Number of symbols traded
- Long/short contribution

It can optionally apply threshold-based rejection rules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _as_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute concentration metrics from a replay report JSON.")
    ap.add_argument("--replay-report", required=True, help="Path to mei-backtester replay JSON output.")
    ap.add_argument("--output", required=True, help="Write summary JSON to this path.")
    ap.add_argument(
        "--max-top1-pnl-pct",
        type=float,
        default=0.65,
        help="Reject if top-1 symbol contributes more than this fraction of positive PnL (default: 0.65).",
    )
    ap.add_argument(
        "--max-top5-pnl-pct",
        type=float,
        default=0.90,
        help="Reject if top-5 symbols contribute more than this fraction of positive PnL (default: 0.90).",
    )
    ap.add_argument(
        "--min-symbols-traded",
        type=int,
        default=5,
        help="Reject if fewer than this many symbols had at least one trade (default: 5).",
    )
    args = ap.parse_args(argv)

    rpt_path = Path(args.replay_report).expanduser().resolve()
    if not rpt_path.exists():
        raise SystemExit(f"Replay report not found: {rpt_path}")

    d = _load_json(rpt_path)
    per_symbol = d.get("per_symbol", {}) if isinstance(d, dict) else {}
    if not isinstance(per_symbol, dict):
        per_symbol = {}

    sym_rows: list[dict[str, Any]] = []
    for sym, stats in per_symbol.items():
        if not isinstance(stats, dict):
            continue
        trades = _as_int(stats.get("trades"))
        net_pnl = _as_float(stats.get("net_pnl_usd"))
        sym_rows.append({"symbol": str(sym), "trades": int(trades), "net_pnl_usd": float(net_pnl)})

    traded_syms = [r for r in sym_rows if int(r.get("trades", 0)) > 0]
    symbols_traded = int(len(traded_syms))

    pos_pnl_sum = float(sum(max(0.0, float(r.get("net_pnl_usd", 0.0))) for r in traded_syms))
    traded_sorted = sorted(traded_syms, key=lambda r: float(r.get("net_pnl_usd", 0.0)), reverse=True)

    top1_pnl = float(traded_sorted[0]["net_pnl_usd"]) if traded_sorted else 0.0
    top5_pnl = float(sum(max(0.0, float(r.get("net_pnl_usd", 0.0))) for r in traded_sorted[:5]))

    top1_pnl_pct = float(top1_pnl / pos_pnl_sum) if pos_pnl_sum > 0 else 0.0
    top5_pnl_pct = float(top5_pnl / pos_pnl_sum) if pos_pnl_sum > 0 else 0.0

    # Long/short contribution (best-effort): use report.by_side.
    long_pnl = 0.0
    short_pnl = 0.0
    by_side = d.get("by_side", []) if isinstance(d, dict) else []
    if isinstance(by_side, list):
        for it in by_side:
            if not isinstance(it, dict):
                continue
            side = str(it.get("side", "") or it.get("action", "")).upper()
            pnl = _as_float(it.get("pnl"))
            if side == "LONG":
                long_pnl += pnl
            elif side == "SHORT":
                short_pnl += pnl

    reasons: list[str] = []
    max_top1 = float(args.max_top1_pnl_pct)
    max_top5 = float(args.max_top5_pnl_pct)
    min_syms = int(args.min_symbols_traded)

    if min_syms > 0 and symbols_traded < min_syms:
        reasons.append(f"symbols_traded<{min_syms} ({symbols_traded})")
    if max_top1 > 0 and top1_pnl_pct > max_top1:
        reasons.append(f"top1_pnl_pct>{max_top1:.2f} ({top1_pnl_pct:.2f})")
    if max_top5 > 0 and top5_pnl_pct > max_top5:
        reasons.append(f"top5_pnl_pct>{max_top5:.2f} ({top5_pnl_pct:.2f})")

    out = {
        "replay_report_path": str(rpt_path),
        "metrics": {
            "symbols_traded": int(symbols_traded),
            "top1_pnl_usd": float(top1_pnl),
            "top5_pnl_usd": float(top5_pnl),
            "positive_pnl_sum_usd": float(pos_pnl_sum),
            "top1_pnl_pct": float(top1_pnl_pct),
            "top5_pnl_pct": float(top5_pnl_pct),
            "long_pnl_usd": float(long_pnl),
            "short_pnl_usd": float(short_pnl),
        },
        "thresholds": {
            "max_top1_pnl_pct": float(max_top1),
            "max_top5_pnl_pct": float(max_top5),
            "min_symbols_traded": int(min_syms),
        },
        "reject": bool(reasons),
        "reject_reasons": list(reasons),
    }

    out_path = Path(args.output).expanduser().resolve()
    _write_json(out_path, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

