from __future__ import annotations

import os
import re
import sqlite3
from contextlib import suppress
from pathlib import Path
from typing import Any


def _safe_read_text_tail(path: Path, *, max_bytes: int = 256_000) -> str:
    try:
        if not path.exists():
            return ""
        size = int(path.stat().st_size)
        start = max(0, size - int(max_bytes))
        with path.open("rb") as f:
            f.seek(start, os.SEEK_SET)
            chunk = f.read()
        return bytes(chunk).decode("utf-8", errors="replace")
    except Exception:
        return ""


_HB_LOOP_RE = re.compile(r"(?:wall|loop)=([0-9.]+)s", re.IGNORECASE)
_HB_ERRORS_RE = re.compile(r"errors=([0-9]+)", re.IGNORECASE)
_HB_SYMBOLS_RE = re.compile(r"symbols=([0-9]+)", re.IGNORECASE)
_HB_OPEN_POS_RE = re.compile(r"open_pos=([0-9]+)", re.IGNORECASE)
_HB_WS_CONNECTED_RE = re.compile(r"ws_connected=(True|False)", re.IGNORECASE)
_HB_WS_THREAD_RE = re.compile(r"ws_thread_alive=(True|False)", re.IGNORECASE)
_HB_WS_RESTARTS_RE = re.compile(r"ws_restarts=([0-9]+)", re.IGNORECASE)
_HB_KILL_MODE_RE = re.compile(r"kill=(off|close_only|halt_all)", re.IGNORECASE)
_HB_KILL_REASON_RE = re.compile(r"kill_reason=([^\s]+)", re.IGNORECASE)
_HB_STRATEGY_MODE_RE = re.compile(r"strategy_mode=([^\s]+)", re.IGNORECASE)
_HB_REGIME_GATE_RE = re.compile(r"regime_gate=(on|off)", re.IGNORECASE)
_HB_REGIME_REASON_RE = re.compile(r"regime_reason=([^\s]+)", re.IGNORECASE)
_HB_CONFIG_ID_RE = re.compile(r"config_id=([0-9a-f]{8,64}|none)", re.IGNORECASE)
_HB_SLIP_ENABLED_RE = re.compile(r"slip_enabled=([01])", re.IGNORECASE)
_HB_SLIP_N_RE = re.compile(r"slip_n=([0-9]+)", re.IGNORECASE)
_HB_SLIP_WIN_RE = re.compile(r"slip_win=([0-9]+)", re.IGNORECASE)
_HB_SLIP_THR_RE = re.compile(r"slip_thr_bps=([0-9.]+)", re.IGNORECASE)
_HB_SLIP_LAST_RE = re.compile(r"slip_last_bps=([0-9.]+|none)", re.IGNORECASE)
_HB_SLIP_MED_RE = re.compile(r"slip_median_bps=([0-9.]+|none)", re.IGNORECASE)


def connect_db_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=1.0)
    con.row_factory = sqlite3.Row
    return con


def _fetchone(con: sqlite3.Connection, q: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    cur = con.cursor()
    cur.execute(q, params)
    row = cur.fetchone()
    return dict(row) if row else None


def _heartbeat_line_from_db(db_path: Path) -> tuple[int, str] | None:
    if not db_path.exists():
        return None
    try:
        con = connect_db_ro(db_path)
    except Exception:
        return None
    try:
        row = _fetchone(
            con,
            """
            SELECT ts_ms, message
            FROM runtime_logs
            WHERE message LIKE '🫀 engine ok%'
            ORDER BY ts_ms DESC
            LIMIT 1
            """,
        )
        if not row:
            return None
        try:
            ts_ms = int(row.get("ts_ms") or 0)
        except Exception:
            ts_ms = 0
        line = str(row.get("message") or "").strip()
        return ts_ms, line
    except Exception:
        return None
    finally:
        with suppress(Exception):
            con.close()


def parse_last_heartbeat(db_path: Path, log_path: Path) -> dict[str, Any]:
    """Parse the latest engine heartbeat line.

    Prefers SQLite (`runtime_logs` table) and falls back to legacy text logs.
    """
    hb = _heartbeat_line_from_db(db_path)
    if hb is not None:
        ts_ms, last_line = hb
        out: dict[str, Any] = {
            "ok": True,
            "source": "sqlite",
            "db_path": str(db_path),
            "ts_ms": ts_ms,
            "line": last_line,
        }
    else:
        text = _safe_read_text_tail(log_path, max_bytes=512_000)
        if not text:
            return {
                "ok": False,
                "error": "heartbeat_missing",
                "db_path": str(db_path),
                "log_path": str(log_path),
            }

        lines = [ln for ln in text.splitlines() if ln.strip()]
        last_line: str | None = None
        for ln in reversed(lines[-5000:]):
            if "🫀" not in ln:
                continue
            if "engine ok" in ln.lower():
                last_line = ln
                break

        if not last_line:
            return {
                "ok": False,
                "error": "heartbeat_not_found",
                "db_path": str(db_path),
                "log_path": str(log_path),
            }

        out = {
            "ok": True,
            "source": "text_log",
            "log_path": str(log_path),
            "line": last_line,
        }

    loop_m = _HB_LOOP_RE.search(last_line)
    if loop_m:
        out["loop_s"] = float(loop_m.group(1))
    err_m = _HB_ERRORS_RE.search(last_line)
    if err_m:
        out["errors"] = int(err_m.group(1))
    sym_m = _HB_SYMBOLS_RE.search(last_line)
    if sym_m:
        out["symbols"] = int(sym_m.group(1))
    op_m = _HB_OPEN_POS_RE.search(last_line)
    if op_m:
        out["open_pos"] = int(op_m.group(1))
    wsc_m = _HB_WS_CONNECTED_RE.search(last_line)
    if wsc_m:
        out["ws_connected"] = wsc_m.group(1).lower() == "true"
    wst_m = _HB_WS_THREAD_RE.search(last_line)
    if wst_m:
        out["ws_thread_alive"] = wst_m.group(1).lower() == "true"
    wsr_m = _HB_WS_RESTARTS_RE.search(last_line)
    if wsr_m:
        out["ws_restarts"] = int(wsr_m.group(1))
    km_m = _HB_KILL_MODE_RE.search(last_line)
    if km_m:
        out["kill_mode"] = km_m.group(1).lower()
    kr_m = _HB_KILL_REASON_RE.search(last_line)
    if kr_m:
        out["kill_reason"] = kr_m.group(1)
    smod_m = _HB_STRATEGY_MODE_RE.search(last_line)
    if smod_m:
        out["strategy_mode"] = smod_m.group(1).lower()
    rg_m = _HB_REGIME_GATE_RE.search(last_line)
    if rg_m:
        out["regime_gate"] = rg_m.group(1).lower() == "on"
    rr_m = _HB_REGIME_REASON_RE.search(last_line)
    if rr_m:
        out["regime_reason"] = rr_m.group(1)
    cid_m = _HB_CONFIG_ID_RE.search(last_line)
    if cid_m:
        cid = cid_m.group(1).lower()
        if cid != "none":
            out["config_id"] = cid

    se_m = _HB_SLIP_ENABLED_RE.search(last_line)
    if se_m:
        out["slip_enabled"] = se_m.group(1) == "1"
    sn_m = _HB_SLIP_N_RE.search(last_line)
    if sn_m:
        out["slip_n"] = int(sn_m.group(1))
    sw_m = _HB_SLIP_WIN_RE.search(last_line)
    if sw_m:
        out["slip_win"] = int(sw_m.group(1))
    st_m = _HB_SLIP_THR_RE.search(last_line)
    if st_m:
        out["slip_thr_bps"] = float(st_m.group(1))
    sl_m = _HB_SLIP_LAST_RE.search(last_line)
    if sl_m:
        v = sl_m.group(1).lower()
        if v != "none":
            out["slip_last_bps"] = float(v)
    sm_m = _HB_SLIP_MED_RE.search(last_line)
    if sm_m:
        v = sm_m.group(1).lower()
        if v != "none":
            out["slip_median_bps"] = float(v)
    return out
