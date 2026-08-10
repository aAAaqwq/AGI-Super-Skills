#!/usr/bin/env python3
"""Render radar report as clean user-facing Telegram format."""

from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

PDT = timezone(timedelta(hours=-7))


def fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(PDT).strftime("%Y-%m-%d %H:%M PDT")
    except Exception:
        return ts


def render(report: dict[str, Any]) -> str:
    scanned = report.get("scanned_at", {}) or {}
    ts = scanned.get("america_los_angeles", report.get("report_generated_at", ""))
    date_str = fmt_time(ts)

    candidates = report.get("candidate_audit", []) or []
    filtered = report.get("filtered", {}) or {}
    opportunities = report.get("top_opportunities", []) or []
    observations = report.get("observations", []) or []
    snapshot = report.get("snapshot_path", "") or ""

    lines: list[str] = []
    lines.append(f"📡 币安雷达 | {date_str}")

    # ── Signals ──────────────────────────────────────
    longs: list[tuple[str, str, str]] = []   # (symbol, price, reason)
    shorts: list[tuple[str, str, str]] = []
    squeeze: list[tuple[str, str]] = []

    for c in candidates:
        disp = c.get("derivation_disposition", "")
        if disp not in ("ACCEPTED", "PENDING"):
            continue
        symbol = ""
        price = ""
        for e in c.get("evidence", []) or []:
            if e.startswith("symbol="):
                symbol = e.split("=", 1)[1]
            elif e.startswith("price="):
                price = e.split("=", 1)[1]
        score = c.get("score", c.get("raw_score", "?"))
        reasons = ", ".join(c.get("derivation_reasons", []) or [])
        direction = c.get("direction", "")

        entry = (symbol, price or "?", f"★{score} | {reasons}" if score != "?" else reasons)
        if direction == "LONG":
            longs.append(entry)
        elif direction == "SHORT":
            shorts.append(entry)

    has_any = False
    if longs:
        has_any = True
        lines.append("")
        lines.append("🟢 做多信号")
        for sym, px, reason in longs[:5]:
            px_str = f" ${px}" if px and px != "?" else ""
            lines.append(f"  • {sym}{px_str} {reason}")

    if shorts:
        has_any = True
        lines.append("")
        lines.append("🔴 做空信号")
        for sym, px, reason in shorts[:5]:
            px_str = f" ${px}" if px and px != "?" else ""
            lines.append(f"  • {sym}{px_str} {reason}")

    if not has_any:
        lines.append("")
        lines.append("本轮无高分信号")

    # ── Summary line ─────────────────────────────────
    total_candidates = len(candidates)
    total_filtered = sum(filtered.values())
    if total_filtered:
        lines.append(f"（{total_candidates}候选，{total_filtered}被过滤）")

    # ── Observations (squeeze watch etc) ─────────────
    if observations:
        lines.append("")
        lines.append("⏳ 观察")
        for obs in observations[:3]:
            if isinstance(obs, str):
                lines.append(f"  • {obs}")
            elif isinstance(obs, dict):
                sym = obs.get("symbol", "?")
                note = obs.get("note", obs.get("reason", ""))
                lines.append(f"  • {sym} {note}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read report JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict):
        print("ERROR: report must be a JSON object", file=sys.stderr)
        return 2

    print(render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
