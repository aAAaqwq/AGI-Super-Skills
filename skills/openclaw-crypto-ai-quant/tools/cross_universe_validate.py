#!/usr/bin/env python3
"""Cross-universe validation using per-symbol replay breakdown (AQC-508).

This tool compares strategy performance on a configured subset of symbols versus the full universe,
based on the `per_symbol` breakdown in a `mei-backtester replay` JSON report.

It answers: "Is the edge coming from a long tail of symbols outside the liquid/core set?"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_symbol_set(path: Path) -> list[str]:
    """Load symbols from a .json array file or a newline-delimited text file."""
    p = Path(path).expanduser().resolve()
    if p.suffix.lower() == ".json":
        obj = _load_json(p)
        if not isinstance(obj, list):
            raise ValueError(f"Expected a JSON array of symbols: {p}")
        out = [str(x).strip() for x in obj if str(x).strip()]
        return sorted(dict.fromkeys(out))

    symbols: list[str] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        symbols.append(s)
    return sorted(dict.fromkeys(symbols))


def _sum_stats(per_symbol: dict[str, dict[str, Any]], symbols: set[str]) -> dict[str, float]:
    keys = [
        "trades",
        "wins",
        "losses",
        "realised_pnl_usd",
        "funding_pnl_usd",
        "fees_usd",
        "net_pnl_usd",
        "estimated_slippage_usd",
        "fills",
        "funding_events",
    ]
    out: dict[str, float] = {k: 0.0 for k in keys}
    for sym in symbols:
        st = per_symbol.get(sym)
        if not isinstance(st, dict):
            continue
        for k in keys:
            try:
                out[k] += float(st.get(k, 0.0) or 0.0)
            except Exception:
                continue
    return out


def _safe_div(n: float, d: float) -> float:
    if abs(float(d)) < 1e-12:
        return 0.0
    return float(n) / float(d)


def compute_cross_universe_summary(
    replay_obj: dict[str, Any],
    *,
    sets: list[tuple[str, list[str]]],
) -> dict[str, Any]:
    per_symbol = replay_obj.get("per_symbol", {})
    if not isinstance(per_symbol, dict):
        raise ValueError("Replay report is missing per_symbol stats (requires AQC-302).")

    # Normalise per_symbol -> dict[str, dict]
    per_symbol_norm: dict[str, dict[str, Any]] = {}
    for k, v in per_symbol.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            continue
        per_symbol_norm[k] = v

    universe_syms = set(per_symbol_norm.keys())
    total = _sum_stats(per_symbol_norm, universe_syms)

    out_sets: list[dict[str, Any]] = []
    for name, symbols in sets:
        wanted = [str(s).strip() for s in symbols if str(s).strip()]
        wanted_set = set(wanted)
        present = sorted([s for s in wanted_set if s in universe_syms])
        missing = sorted([s for s in wanted_set if s not in universe_syms])

        subset_stats = _sum_stats(per_symbol_norm, set(present))
        outside_syms = universe_syms - set(present)
        outside_stats = _sum_stats(per_symbol_norm, outside_syms)

        out_sets.append(
            {
                "name": str(name),
                "provided_symbols": sorted(dict.fromkeys(wanted)),
                "present_symbols": present,
                "missing_symbols": missing,
                "subset": subset_stats,
                "outside": outside_stats,
                "shares": {
                    "net_pnl_usd": _safe_div(float(subset_stats["net_pnl_usd"]), float(total["net_pnl_usd"])),
                    "trades": _safe_div(float(subset_stats["trades"]), float(total["trades"])),
                    "fees_usd": _safe_div(float(subset_stats["fees_usd"]), float(total["fees_usd"])),
                },
            }
        )

    return {
        "version": "cross_universe_v1",
        "total": total,
        "sets": out_sets,
    }


def _parse_symbol_sets(items: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        if "=" not in s:
            raise SystemExit(f"Invalid --symbol-set (expected NAME=PATH): {s!r}")
        name, path = s.split("=", 1)
        out.append((name.strip(), Path(path.strip())))
    if not out:
        raise SystemExit("At least one --symbol-set NAME=PATH is required.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cross-universe validation using per_symbol replay breakdown.")
    ap.add_argument("--replay-report", required=True, help="Replay JSON report path (must include per_symbol).")
    ap.add_argument(
        "--symbol-set",
        action="append",
        default=[],
        help="Symbol set in NAME=PATH format (repeatable). PATH can be .json array or newline-delimited text.",
    )
    ap.add_argument("--output", required=True, help="Write JSON summary to this path.")
    args = ap.parse_args(argv)

    replay_path = Path(args.replay_report).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    replay_obj = _load_json(replay_path)
    if not isinstance(replay_obj, dict):
        raise SystemExit("Replay report must be a JSON object.")

    set_specs = _parse_symbol_sets(list(args.symbol_set or []))
    sets: list[tuple[str, list[str]]] = []
    for name, p in set_specs:
        sets.append((name, load_symbol_set(p)))

    summary = compute_cross_universe_summary(replay_obj, sets=sets)
    summary["replay_report_path"] = str(replay_path)
    summary["symbol_sets"] = [{"name": n, "path": str(p)} for n, p in set_specs]

    _write_json(out_path, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

