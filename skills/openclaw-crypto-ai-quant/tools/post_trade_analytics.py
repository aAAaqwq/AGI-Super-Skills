#!/usr/bin/env python3
"""Post-trade analytics helpers (AQC-905).

This tool is intended for offline review of backtest or live trading behaviour.

Inputs
  1) A trade-level CSV (required).
     Recommended source: `mei-backtester replay --export-trades trades.csv`
  2) A structured events JSONL (optional).
     Recommended source: `artifacts/events/events.jsonl` (aiq_event_v1).

Outputs
  - A small pack of CSV/JSON files under an output directory:
    - trade_summary.json
    - pnl_by_symbol.csv
    - reason_code_stats.csv
    - mae_mfe_summary.json
    - entry_event_counts.csv
    - entry_event_counts_by_symbol.csv

The goal is to provide fast, repeatable diagnostics for:
- MAE/MFE distributions
- symbol contribution
- entry/exit reason breakdowns
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _write_json(path: Path, payload: Any) -> None:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def _require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing required column(s): {missing}")


def _trade_quantiles(df: pd.DataFrame, col: str) -> dict[str, float]:
    if col not in df.columns:
        return {}
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return {}
    qs = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).to_dict()
    return {f"q{int(k * 100):02d}": float(v) for k, v in qs.items()}


@dataclass(frozen=True)
class AnalyticsPaths:
    out_dir: Path
    trade_summary_json: Path
    pnl_by_symbol_csv: Path
    reason_code_stats_csv: Path
    mae_mfe_summary_json: Path
    entry_event_counts_csv: Path
    entry_event_counts_by_symbol_csv: Path


def _default_out_dir() -> Path:
    ts = _utc_now_iso().replace(":", "").replace("-", "")
    return (AIQ_ROOT / "artifacts" / "analytics" / f"post_trade_{ts}").resolve()


def _analyse_trades(trades: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    req = [
        "trade_id",
        "position_id",
        "entry_ts_ms",
        "exit_ts_ms",
        "symbol",
        "side",
        "entry_price",
        "exit_price",
        "exit_size",
        "pnl_usd",
        "fee_usd",
        "mae_pct",
        "mfe_pct",
        "reason_code",
        "reason",
    ]
    _require_columns(trades, req)

    df = trades.copy()
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["reason_code"] = df["reason_code"].astype(str).str.strip()

    for c in ["pnl_usd", "fee_usd", "mae_pct", "mfe_pct", "entry_price", "exit_price", "exit_size"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["pnl_net_usd"] = df["pnl_usd"].fillna(0.0) - df["fee_usd"].fillna(0.0)

    n = int(len(df))
    total_pnl = float(df["pnl_usd"].fillna(0.0).sum())
    total_fees = float(df["fee_usd"].fillna(0.0).sum())
    total_net = float(df["pnl_net_usd"].fillna(0.0).sum())

    win_rate = 0.0
    if n > 0:
        win_rate = float((df["pnl_net_usd"] > 0).mean())

    pnl_by_symbol = (
        df.groupby("symbol", dropna=False)
        .agg(
            trades=("trade_id", "count"),
            pnl_usd=("pnl_usd", "sum"),
            fee_usd=("fee_usd", "sum"),
            pnl_net_usd=("pnl_net_usd", "sum"),
            win_rate=("pnl_net_usd", lambda s: float((s > 0).mean()) if len(s) else 0.0),
            mae_pct_median=("mae_pct", "median"),
            mfe_pct_median=("mfe_pct", "median"),
        )
        .reset_index()
        .sort_values(["pnl_net_usd", "trades"], ascending=[False, False])
    )

    reason_code_stats = (
        df.groupby("reason_code", dropna=False)
        .agg(
            trades=("trade_id", "count"),
            pnl_net_usd=("pnl_net_usd", "sum"),
            win_rate=("pnl_net_usd", lambda s: float((s > 0).mean()) if len(s) else 0.0),
            mae_pct_median=("mae_pct", "median"),
            mfe_pct_median=("mfe_pct", "median"),
        )
        .reset_index()
        .sort_values(["trades", "pnl_net_usd"], ascending=[False, False])
    )

    mae_mfe_summary = {
        "mae_pct": _trade_quantiles(df, "mae_pct"),
        "mfe_pct": _trade_quantiles(df, "mfe_pct"),
    }

    summary = {
        "trades": n,
        "total_pnl_usd": total_pnl,
        "total_fees_usd": total_fees,
        "total_net_pnl_usd": total_net,
        "win_rate_net": win_rate,
    }
    return summary, pnl_by_symbol, reason_code_stats, mae_mfe_summary


def _analyse_entry_events(events: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    # We only use structured aiq_event_v1 audit events here.
    rows: list[dict[str, Any]] = []
    for e in events:
        if str(e.get("schema") or "").strip() != "aiq_event_v1":
            continue
        if str(e.get("kind") or "").strip().lower() != "audit":
            continue
        data = e.get("data") if isinstance(e.get("data"), dict) else {}
        ev = str(data.get("event") or "").strip()
        if not ev.startswith("ENTRY_"):
            continue

        rows.append(
            {
                "ts_ms": int(e.get("ts_ms") or 0),
                "ts": str(e.get("ts") or ""),
                "mode": str(e.get("mode") or ""),
                "symbol": str(e.get("symbol") or "").strip().upper(),
                "event": ev,
                "level": str(data.get("level") or ""),
            }
        )

    if not rows:
        empty = pd.DataFrame(columns=["event", "count"])
        empty2 = pd.DataFrame(columns=["symbol", "event", "count"])
        return empty, empty2

    df = pd.DataFrame(rows)
    counts = df.groupby("event").size().reset_index(name="count").sort_values("count", ascending=False)
    counts_by_symbol = (
        df.groupby(["symbol", "event"]).size().reset_index(name="count").sort_values(["count"], ascending=[False])
    )
    return counts, counts_by_symbol


def run(
    *,
    trades_csv: Path,
    events_jsonl: Path | None,
    out_dir: Path,
) -> AnalyticsPaths:
    t_path = Path(trades_csv).expanduser().resolve()
    if not t_path.exists():
        raise FileNotFoundError(f"trades CSV not found: {t_path}")

    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(t_path)
    trade_summary, pnl_by_symbol, reason_code_stats, mae_mfe_summary = _analyse_trades(trades)

    events: list[dict[str, Any]] = []
    if events_jsonl is not None:
        events = _read_jsonl(Path(events_jsonl))

    entry_counts, entry_counts_by_symbol = _analyse_entry_events(events)

    paths = AnalyticsPaths(
        out_dir=out,
        trade_summary_json=(out / "trade_summary.json").resolve(),
        pnl_by_symbol_csv=(out / "pnl_by_symbol.csv").resolve(),
        reason_code_stats_csv=(out / "reason_code_stats.csv").resolve(),
        mae_mfe_summary_json=(out / "mae_mfe_summary.json").resolve(),
        entry_event_counts_csv=(out / "entry_event_counts.csv").resolve(),
        entry_event_counts_by_symbol_csv=(out / "entry_event_counts_by_symbol.csv").resolve(),
    )

    _write_json(
        paths.trade_summary_json,
        {
            "generated_at": _utc_now_iso(),
            "trades_csv": str(t_path),
            "events_jsonl": None if events_jsonl is None else str(Path(events_jsonl).expanduser().resolve()),
            "summary": trade_summary,
        },
    )
    _write_json(paths.mae_mfe_summary_json, mae_mfe_summary)
    _write_csv(paths.pnl_by_symbol_csv, pnl_by_symbol)
    _write_csv(paths.reason_code_stats_csv, reason_code_stats)
    _write_csv(paths.entry_event_counts_csv, entry_counts)
    _write_csv(paths.entry_event_counts_by_symbol_csv, entry_counts_by_symbol)

    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Post-trade analytics pack (AQC-905).")
    ap.add_argument("--trades-csv", required=True, help="Trade export CSV path (mei-backtester replay --export-trades).")
    ap.add_argument(
        "--events-jsonl",
        default=str((AIQ_ROOT / "artifacts" / "events" / "events.jsonl").resolve()),
        help="Structured events JSONL path (default: artifacts/events/events.jsonl).",
    )
    ap.add_argument(
        "--no-events",
        action="store_true",
        help="Do not load events JSONL (trade-only report).",
    )
    ap.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: artifacts/analytics/post_trade_<timestamp>).",
    )
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir).expanduser().resolve() if str(args.out_dir).strip() else _default_out_dir()
    events_jsonl = None if bool(args.no_events) else Path(args.events_jsonl).expanduser().resolve()

    try:
        paths = run(
            trades_csv=Path(args.trades_csv),
            events_jsonl=events_jsonl,
            out_dir=out_dir,
        )
    except Exception as e:
        print(f"[post_trade_analytics] FAILED: {e}", file=sys.stderr)
        return 1

    print(f"[post_trade_analytics] Wrote analytics pack to: {paths.out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

