#!/usr/bin/env python3
"""Generate a daily markdown report from logs + registry (AQC-901).

This report is intended for fast operational review of both paper and live modes:
- config_id in use
- today's PnL + drawdown (UTC day)
- kill/alert events (from structured JSONL event log)
- recent factory runs (from registry.sqlite)

Outputs are stored under the artifacts directory for auditability.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _utc_day_from_ts_ms(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc).date().isoformat()
    except Exception:
        return ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=2.0)
    con.row_factory = sqlite3.Row
    return con


def _fetchone(con: sqlite3.Connection, q: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    cur = con.cursor()
    cur.execute(q, params)
    row = cur.fetchone()
    return dict(row) if row else None


def _fetchall(con: sqlite3.Connection, q: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cur = con.cursor()
    cur.execute(q, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


@dataclass(frozen=True)
class TradingDailyMetrics:
    utc_day: str
    trades: int
    start_balance: float | None
    end_balance: float | None
    peak_balance: float | None
    pnl_usd: float
    drawdown_pct: float


def _daily_trading_metrics(db_path: Path, *, utc_day: str) -> TradingDailyMetrics | None:
    if not db_path.exists():
        return None

    like = f"{utc_day}%"
    con = _connect_ro(db_path)
    try:
        row_cnt = _fetchone(con, "SELECT COUNT(*) AS n FROM trades WHERE timestamp LIKE ?", (like,))
        row0 = _fetchone(
            con,
            "SELECT balance FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL ORDER BY id ASC LIMIT 1",
            (like,),
        )
        row1 = _fetchone(
            con,
            "SELECT balance FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL ORDER BY id DESC LIMIT 1",
            (like,),
        )
        row_peak = _fetchone(
            con,
            "SELECT MAX(balance) AS peak FROM trades WHERE timestamp LIKE ? AND balance IS NOT NULL",
            (like,),
        )

        try:
            n = int(row_cnt["n"]) if row_cnt and row_cnt.get("n") is not None else 0
        except Exception:
            n = 0

        start = float(row0["balance"]) if row0 and row0.get("balance") is not None else None
        end = float(row1["balance"]) if row1 and row1.get("balance") is not None else None
        peak = float(row_peak["peak"]) if row_peak and row_peak.get("peak") is not None else None

        pnl = float(end - start) if (start is not None and end is not None) else 0.0

        dd = 0.0
        if peak is not None and peak > 0 and end is not None:
            dd = max(0.0, (peak - end) / peak) * 100.0

        return TradingDailyMetrics(
            utc_day=str(utc_day),
            trades=int(n),
            start_balance=start,
            end_balance=end,
            peak_balance=peak,
            pnl_usd=float(pnl),
            drawdown_pct=float(dd),
        )
    finally:
        con.close()


def _events_for_day(events: Iterable[dict[str, Any]], *, utc_day: str, mode: str) -> list[dict[str, Any]]:
    mode2 = str(mode or "").strip().lower()
    out: list[dict[str, Any]] = []
    for e in events:
        if not isinstance(e, dict):
            continue
        if str(e.get("schema", "")).strip() != "aiq_event_v1":
            continue
        if str(e.get("mode", "")).strip().lower() != mode2:
            continue
        try:
            ts_ms = int(e.get("ts_ms") or 0)
        except Exception:
            ts_ms = 0
        if not ts_ms:
            continue
        if _utc_day_from_ts_ms(ts_ms) != str(utc_day):
            continue
        out.append(e)
    out.sort(key=lambda x: int(x.get("ts_ms") or 0))
    return out


def _latest_config_id(events: list[dict[str, Any]]) -> str:
    for e in reversed(events):
        cid = str(e.get("config_id") or "").strip().lower()
        if cid:
            return cid
    return ""


def _kill_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in events:
        if str(e.get("kind", "")).strip().lower() != "audit":
            continue
        data = e.get("data") if isinstance(e.get("data"), dict) else {}
        ev = str(data.get("event", "")).strip()
        if not ev.startswith("RISK_KILL"):
            continue
        out.append(e)
    return out


def _slippage_kill_summary(kills: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Extract a small summary from the latest RISK_KILL_SLIPPAGE event."""
    last = None
    for e in reversed(kills):
        data = e.get("data") if isinstance(e.get("data"), dict) else {}
        if str(data.get("event", "")).strip() != "RISK_KILL_SLIPPAGE":
            continue
        last = e
        break
    if last is None:
        return None
    payload = last.get("data") if isinstance(last.get("data"), dict) else {}
    inner = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return {
        "ts": str(last.get("ts") or ""),
        "symbol": str(last.get("symbol") or ""),
        "slippage_median_bps": inner.get("slippage_median_bps"),
        "threshold_median_bps": inner.get("threshold_median_bps"),
        "window_fills": inner.get("slippage_window_fills"),
    }


def _registry_runs_for_day(registry_db: Path, *, utc_day: str, limit: int = 20) -> list[dict[str, Any]]:
    if not registry_db.exists():
        return []
    con = _connect_ro(registry_db)
    try:
        return _fetchall(
            con,
            "SELECT run_id, run_date_utc, generated_at_ms, git_head, run_dir FROM runs WHERE run_date_utc = ? ORDER BY generated_at_ms DESC LIMIT ?",
            (str(utc_day), int(limit)),
        )
    finally:
        con.close()


def _registry_top_configs_for_run(registry_db: Path, *, run_id: str, limit: int = 5) -> list[dict[str, Any]]:
    if not registry_db.exists():
        return []
    con = _connect_ro(registry_db)
    try:
        return _fetchall(
            con,
            """
            SELECT config_id, total_pnl, max_drawdown_pct, total_trades, win_rate, profit_factor, total_fees
            FROM run_configs
            WHERE run_id = ?
            ORDER BY total_pnl DESC
            LIMIT ?
            """,
            (str(run_id), int(limit)),
        )
    finally:
        con.close()


def _fmt_money(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"${float(x):,.2f}"


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{float(x):.2f}%"


def _render_report_md(
    *,
    utc_day: str,
    generated_at_utc: str,
    paper: dict[str, Any],
    live: dict[str, Any],
    registry: dict[str, Any],
    warnings: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"# Daily Summary Report ({utc_day} UTC)")
    lines.append("")
    lines.append(f"- Generated at: {generated_at_utc}")
    if warnings:
        lines.append(f"- Warnings: {', '.join(warnings)}")
    lines.append("")

    def _section(name: str, payload: dict[str, Any]) -> None:
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- config_id: `{payload.get('config_id') or 'n/a'}`")
        m = payload.get("metrics")
        if isinstance(m, TradingDailyMetrics):
            lines.append(f"- trades (today): {m.trades}")
            lines.append(f"- start_balance: {_fmt_money(m.start_balance)}")
            lines.append(f"- end_balance: {_fmt_money(m.end_balance)}")
            lines.append(f"- pnl (today): {_fmt_money(m.pnl_usd)}")
            lines.append(f"- drawdown (today): {_fmt_pct(m.drawdown_pct)}")
        else:
            lines.append("- trades (today): n/a")
            lines.append("- pnl (today): n/a")
            lines.append("- drawdown (today): n/a")

        kills = payload.get("kills", [])
        if isinstance(kills, list) and kills:
            lines.append(f"- kill events: {len(kills)}")
            # Print a short list of the most recent kill events.
            for e in list(reversed(kills))[:5]:
                ts = str(e.get("ts") or "")
                data = e.get("data") if isinstance(e.get("data"), dict) else {}
                ev = str(data.get("event", "")).strip()
                lines.append(f"  - {ts} {ev}")
        else:
            lines.append("- kill events: 0")

        slip = payload.get("slippage_kill")
        if isinstance(slip, dict) and slip:
            lines.append(
                "- slippage: kill at {med} bps (threshold {thr} bps, window {win})".format(
                    med=slip.get("slippage_median_bps", "n/a"),
                    thr=slip.get("threshold_median_bps", "n/a"),
                    win=slip.get("window_fills", "n/a"),
                )
            )
        else:
            lines.append("- slippage: n/a")

        lines.append("")

    _section("Paper", paper)
    _section("Live", live)

    lines.append("## Registry")
    lines.append("")
    runs = registry.get("runs", [])
    if isinstance(runs, list) and runs:
        lines.append(f"- factory runs: {len(runs)}")
        for r in runs[:10]:
            rid = str(r.get("run_id", "")).strip()
            gen = int(r.get("generated_at_ms") or 0)
            ts = datetime.fromtimestamp(gen / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z") if gen else ""
            lines.append(f"  - run_id: `{rid}` at {ts}")
            tops = registry.get("top_configs", {}).get(rid, [])
            if isinstance(tops, list) and tops:
                for c in tops:
                    lines.append(
                        "    - config_id `{cid}` pnl={pnl:.2f} dd={dd:.4f} trades={tr}".format(
                            cid=str(c.get("config_id", ""))[:12],
                            pnl=float(c.get("total_pnl", 0.0) or 0.0),
                            dd=float(c.get("max_drawdown_pct", 0.0) or 0.0),
                            tr=int(c.get("total_trades", 0) or 0),
                        )
                    )
    else:
        lines.append("- factory runs: n/a (registry missing or no runs for this day)")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a daily summary report (paper + live).")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root directory (default: artifacts).")
    ap.add_argument("--date", default=None, help="UTC date in YYYY-MM-DD format (default: today UTC).")
    ap.add_argument("--event-log", default=None, help="Path to events.jsonl (default: artifacts/events/events.jsonl).")
    ap.add_argument("--registry-db", default=None, help="Path to registry.sqlite (default: artifacts/registry/registry.sqlite).")
    ap.add_argument("--paper-db", default=str(AIQ_ROOT / "trading_engine.db"), help="Paper trading DB path.")
    ap.add_argument("--live-db", default=str(AIQ_ROOT / "trading_engine_live.db"), help="Live trading DB path.")
    ap.add_argument("--output", default=None, help="Write markdown report to this path (default under artifacts).")
    args = ap.parse_args(argv)

    now_ms = int(time.time() * 1000)
    utc_day = str(args.date or _utc_day_from_ts_ms(now_ms)).strip()
    if not utc_day:
        raise SystemExit("--date is empty and could not infer today's UTC day")

    artifacts_root = Path(args.artifacts_dir).expanduser().resolve()
    event_log = Path(args.event_log).expanduser().resolve() if args.event_log else (artifacts_root / "events" / "events.jsonl")
    registry_db = (
        Path(args.registry_db).expanduser().resolve() if args.registry_db else (artifacts_root / "registry" / "registry.sqlite")
    )

    paper_db = Path(args.paper_db).expanduser().resolve()
    live_db = Path(args.live_db).expanduser().resolve()

    warnings: list[str] = []
    if not event_log.exists():
        warnings.append("event_log_missing")
    if not registry_db.exists():
        warnings.append("registry_missing")

    all_events = list(_load_jsonl(event_log))
    paper_events = _events_for_day(all_events, utc_day=utc_day, mode="paper")
    live_events = _events_for_day(all_events, utc_day=utc_day, mode="live")

    paper_kills = _kill_events(paper_events)
    live_kills = _kill_events(live_events)

    paper_payload: dict[str, Any] = {
        "config_id": _latest_config_id(paper_events),
        "metrics": _daily_trading_metrics(paper_db, utc_day=utc_day),
        "kills": paper_kills,
        "slippage_kill": _slippage_kill_summary(paper_kills),
    }
    live_payload: dict[str, Any] = {
        "config_id": _latest_config_id(live_events),
        "metrics": _daily_trading_metrics(live_db, utc_day=utc_day),
        "kills": live_kills,
        "slippage_kill": _slippage_kill_summary(live_kills),
    }

    runs = _registry_runs_for_day(registry_db, utc_day=utc_day)
    top_configs: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        rid = str(r.get("run_id", "")).strip()
        if not rid:
            continue
        top_configs[rid] = _registry_top_configs_for_run(registry_db, run_id=rid)

    registry_payload = {"runs": runs, "top_configs": top_configs}

    report_md = _render_report_md(
        utc_day=utc_day,
        generated_at_utc=_utc_now_iso(),
        paper=paper_payload,
        live=live_payload,
        registry=registry_payload,
        warnings=warnings,
    )

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        out_path = (artifacts_root / "reports" / "daily" / f"{utc_day}.md").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")
    sys.stderr.write(f"[report] wrote {out_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

