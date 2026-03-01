#!/usr/bin/env python3
"""Emergency flatten helper (AQC-808).

This tool is designed for incident response. In one command it:

1) Writes a kill-switch file (default: close_only) to pause new entries.
2) Flattens positions:
   - paper: clears `position_state` and inserts SYSTEM CLOSE trades.
   - live: optional; requires explicit flags.

It intentionally defaults to paper-only to avoid accidental live actions.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PAPER_DB = PROJECT_DIR / "trading_engine.db"
DEFAULT_SECRETS_PATH = Path(
    os.getenv("AI_QUANT_SECRETS_PATH") or "~/.config/openclaw/ai-quant-secrets.json"
).expanduser()


@dataclass(frozen=True)
class FlatNowSummary:
    paused: bool
    pause_file: str | None
    pause_mode: str | None
    paper_closed: int
    live_closed: int


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_kill_switch_file(path: Path, mode: str) -> None:
    """Write the kill-switch file used by RiskManager."""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(mode or "close_only").strip() + "\n", encoding="utf-8")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(name),),
    ).fetchone()
    return row is not None


def _validate_identifier(name: str) -> None:
    """Raise ValueError if *name* is not a safe SQL identifier (alphanumeric + underscore)."""
    if not name or not all(c.isalnum() or c == "_" for c in name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    _validate_identifier(table)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return set()
    cols: set[str] = set()
    for r in rows:
        try:
            cols.add(str(r[1]))
        except Exception:
            pass
    return cols


def close_paper_positions(db_path: Path, *, reason: str) -> int:
    """Flatten paper positions by clearing `position_state` and inserting SYSTEM CLOSE trades."""
    p = Path(db_path).expanduser().resolve()
    if not p.exists():
        print(f"[flat_now] Paper DB not found: {p}", file=sys.stderr)
        return 0

    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "position_state"):
            print("[flat_now] No position_state table found; nothing to close.", file=sys.stderr)
            return 0

        rows = conn.execute("SELECT symbol FROM position_state").fetchall()
        if not rows:
            print("[flat_now] No paper positions to close.", file=sys.stderr)
            return 0

        now_iso = _utc_iso()
        symbols = [str(r["symbol"] or "").strip().upper() for r in rows if str(r["symbol"] or "").strip()]

        bal = 0.0
        if _table_exists(conn, "trades"):
            try:
                bal_row = conn.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1").fetchone()
                if bal_row is not None:
                    bal = float(bal_row["balance"] or 0.0)
            except Exception:
                bal = 0.0

        inserted = 0
        if _table_exists(conn, "trades"):
            cols = _table_columns(conn, "trades")
            base: dict[str, Any] = {
                "timestamp": now_iso,
                "symbol": None,
                "type": "SYSTEM",
                "action": "CLOSE",
                "price": 0.0,
                "size": 0.0,
                "notional": 0.0,
                "reason": str(reason or "flat_now"),
                "confidence": "N/A",
                "pnl": 0.0,
                "fee_usd": 0.0,
                "balance": float(bal),
                "entry_atr": 0.0,
                "leverage": 0.0,
                "margin_used": 0.0,
                "meta_json": '{"flat_now": true}',
            }
            # Only insert columns that exist in the local DB schema.
            # Safety: `keep_cols` originates from the hardcoded `base` dict above,
            # filtered by actual DB columns.  `_validate_identifier` rejects any
            # non-alphanumeric/underscore names as defence-in-depth.
            keep_cols = [k for k in base.keys() if k in cols]
            for c in keep_cols:
                _validate_identifier(c)
            if keep_cols:
                col_sql = ", ".join(f'"{c}"' for c in keep_cols)
                qs_sql = ", ".join(["?"] * len(keep_cols))
                for sym in symbols:
                    row_data = dict(base)
                    row_data["symbol"] = sym
                    conn.execute(
                        f"INSERT INTO trades ({col_sql}) VALUES ({qs_sql})",
                        tuple(row_data[c] for c in keep_cols),
                    )
                    inserted += 1

        conn.execute("DELETE FROM position_state")
        conn.commit()
        print(f"[flat_now] Closed {len(symbols)} paper position(s).", file=sys.stderr)
        if inserted > 0:
            print(f"[flat_now] Inserted {inserted} SYSTEM CLOSE trade row(s).", file=sys.stderr)
        return len(symbols)
    finally:
        conn.close()


def close_live_positions(
    *,
    secrets_path: Path,
    max_retries: int,
    slippage_pct: float,
    verify_sleep_s: float,
) -> int:
    """Close all live positions via Hyperliquid API. Returns the number of positions closed."""
    sys.path.insert(0, str(PROJECT_DIR))
    from exchange.executor import HyperliquidLiveExecutor, load_live_secrets  # type: ignore

    secrets = load_live_secrets(str(Path(secrets_path).expanduser().resolve()))
    executor = HyperliquidLiveExecutor(secret_key=secrets.secret_key, main_address=secrets.main_address)

    positions = executor.get_positions(force=True)
    if not positions:
        print("[flat_now] No live positions to close.", file=sys.stderr)
        return 0

    print(f"[flat_now] Closing {len(positions)} live position(s)...", file=sys.stderr)

    closed = 0
    for sym, pdata in positions.items():
        is_long = str(pdata.get("type") or "").strip().upper() == "LONG"
        size = float(pdata.get("size") or 0.0)
        if size <= 0:
            continue

        # To close: sell if long, buy if short
        is_buy = not is_long

        ok = False
        for attempt in range(1, int(max_retries) + 1):
            print(
                f"  [{sym}] Attempt {attempt}/{int(max_retries)}: closing {'LONG' if is_long else 'SHORT'} size={size:.6f}",
                file=sys.stderr,
            )
            res = executor.market_close(
                sym,
                is_buy=bool(is_buy),
                sz=float(size),
                slippage_pct=float(slippage_pct),
            )
            if res is None:
                print(f"  [{sym}] Close rejected/failed.", file=sys.stderr)
                time.sleep(1)
                continue

            time.sleep(float(max(0.0, verify_sleep_s)))
            remaining = executor.get_positions(force=True)
            if sym not in remaining:
                print(f"  [{sym}] Closed successfully.", file=sys.stderr)
                ok = True
                closed += 1
                break

            print(f"  [{sym}] Still open after close attempt.", file=sys.stderr)

        if not ok:
            raise RuntimeError(f"failed to close live position: {sym}")

    print("[flat_now] Live flatten complete.", file=sys.stderr)
    return closed


def flat_now(
    *,
    pause_file: Path | None,
    pause_mode: str,
    close_paper: bool,
    paper_db: Path,
    close_live: bool,
    secrets_path: Path,
    max_retries: int,
    slippage_pct: float,
    verify_sleep_s: float,
    reason: str,
) -> FlatNowSummary:
    paused = False
    if pause_file is not None:
        write_kill_switch_file(Path(pause_file), str(pause_mode))
        paused = True

    paper_closed = 0
    if bool(close_paper):
        paper_closed = close_paper_positions(Path(paper_db), reason=str(reason or "flat_now"))

    live_closed = 0
    if bool(close_live):
        live_closed = close_live_positions(
            secrets_path=Path(secrets_path),
            max_retries=int(max_retries),
            slippage_pct=float(slippage_pct),
            verify_sleep_s=float(verify_sleep_s),
        )

    return FlatNowSummary(
        paused=bool(paused),
        pause_file=str(pause_file) if pause_file is not None else None,
        pause_mode=str(pause_mode) if pause_file is not None else None,
        paper_closed=int(paper_closed),
        live_closed=int(live_closed),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Emergency flatten helper (AQC-808).")
    ap.add_argument(
        "--kill-file",
        default="",
        help="Kill-switch file to write (defaults to AI_QUANT_KILL_SWITCH_FILE if set).",
    )
    ap.add_argument(
        "--pause-mode",
        default="close_only",
        choices=["close_only", "halt_all"],
        help="Kill mode to write into the kill file (default: close_only).",
    )
    ap.add_argument("--reason", default="flat_now", help="Reason string recorded in paper trades (default: flat_now).")

    ap.add_argument("--paper", action="store_true", help="Flatten paper positions (default if no target is set).")
    ap.add_argument("--paper-db", default=str(DEFAULT_PAPER_DB), help="Path to paper DB (default: trading_engine.db).")

    ap.add_argument("--live", action="store_true", help="Flatten live positions (requires --yes).")
    ap.add_argument(
        "--secrets-path",
        default=str(DEFAULT_SECRETS_PATH),
        help="Path to live secrets JSON (default: AI_QUANT_SECRETS_PATH or ~/.config/openclaw/ai-quant-secrets.json).",
    )
    ap.add_argument("--max-retries", type=int, default=3, help="Max retries per symbol for live closes (default: 3).")
    ap.add_argument("--slippage-pct", type=float, default=0.02, help="Slippage bound for live closes (default: 0.02).")
    ap.add_argument(
        "--verify-sleep-s", type=float, default=5.0, help="Seconds to wait before verifying close (default: 5)."
    )

    ap.add_argument("--no-pause", action="store_true", help="Do not write a kill-switch file.")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation prompt (required for --live).")
    args = ap.parse_args(argv)

    kill_file = str(args.kill_file or "").strip()
    if not kill_file:
        kill_file = str(os.getenv("AI_QUANT_KILL_SWITCH_FILE") or "").strip()
    pause_file = None if bool(args.no_pause) else (Path(kill_file).expanduser().resolve() if kill_file else None)

    targets_specified = bool(args.paper) or bool(args.live)
    close_paper = bool(args.paper) or (not targets_specified)
    close_live = bool(args.live)

    if close_live and not bool(args.yes):
        print("[flat_now] Refusing live flatten without --yes.", file=sys.stderr)
        return 2

    if not bool(args.yes):
        if not sys.stdin.isatty():
            print("[flat_now] Non-interactive shell detected. Use --yes to skip confirmation.", file=sys.stderr)
            return 2
        print("--- flat_now plan ---", file=sys.stderr)
        if pause_file is not None:
            print(f"  pause: write {args.pause_mode} -> {pause_file}", file=sys.stderr)
        else:
            print("  pause: (skipped)", file=sys.stderr)
        print(f"  paper: {'close' if close_paper else 'skip'} (db={args.paper_db})", file=sys.stderr)
        print(f"  live:  {'close' if close_live else 'skip'}", file=sys.stderr)
        ans = input("Proceed? [y/N] ").strip().lower()
        if ans not in {"y", "yes"}:
            print("[flat_now] Aborted.", file=sys.stderr)
            return 1

    try:
        res = flat_now(
            pause_file=pause_file,
            pause_mode=str(args.pause_mode),
            close_paper=bool(close_paper),
            paper_db=Path(args.paper_db),
            close_live=bool(close_live),
            secrets_path=Path(args.secrets_path),
            max_retries=int(args.max_retries),
            slippage_pct=float(args.slippage_pct),
            verify_sleep_s=float(args.verify_sleep_s),
            reason=str(args.reason),
        )
    except Exception as e:
        print(f"[flat_now] FAILED: {e}", file=sys.stderr)
        return 1

    print(
        f"[flat_now] Done: paused={res.paused} paper_closed={res.paper_closed} live_closed={res.live_closed}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
