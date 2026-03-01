#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _parse_symbol_list(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in str(raw or "").replace("\n", ",").split(","):
        sym = part.strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def _iso_utc_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _sanitize_interval(interval: str) -> str:
    out = []
    for ch in str(interval or ""):
        if ("0" <= ch <= "9") or ("a" <= ch.lower() <= "z"):
            out.append(ch.lower())
        else:
            out.append("_")
    s = "".join(out).strip("_")
    return s if s else "unknown"


def _candles_db_path(interval: str) -> Path:
    raw_dir = str(os.getenv("AI_QUANT_CANDLES_DB_DIR", "") or "").strip()
    if raw_dir:
        return Path(raw_dir) / f"candles_{_sanitize_interval(interval)}.db"
    here = Path(__file__).resolve().parent
    return here.parent / "candles_dbs" / f"candles_{_sanitize_interval(interval)}.db"


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=2.0)


@dataclass(frozen=True)
class CandlePoint:
    t_close_ms: int
    close: float


def _close_at_or_before(cur: sqlite3.Cursor, *, symbol: str, interval: str, t_close_ms: int) -> CandlePoint | None:
    cur.execute(
        """
        SELECT t_close, c
        FROM candles
        WHERE symbol = ? AND interval = ? AND t_close IS NOT NULL AND t_close <= ? AND c IS NOT NULL AND c > 0
        ORDER BY t_close DESC
        LIMIT 1
        """,
        (symbol, interval, int(t_close_ms)),
    )
    row = cur.fetchone()
    if not row:
        return None
    try:
        return CandlePoint(t_close_ms=int(row[0]), close=float(row[1]))
    except Exception:
        return None


def _last_closed_t_close(cur: sqlite3.Cursor, *, symbol: str, interval: str, end_ms: int, grace_ms: int) -> int | None:
    cur.execute(
        """
        SELECT MAX(t_close)
        FROM candles
        WHERE symbol = ? AND interval = ? AND t_close IS NOT NULL AND t_close <= ?
        """,
        (symbol, interval, int(end_ms) - int(grace_ms)),
    )
    (mx,) = cur.fetchone() or (None,)
    if mx is None:
        return None
    try:
        return int(mx)
    except Exception:
        return None


def _pct_return(end: float, start: float) -> float:
    try:
        end_f = float(end)
        start_f = float(start)
    except Exception:
        return 0.0
    if (not math.isfinite(end_f)) or (not math.isfinite(start_f)) or start_f <= 0.0:
        return 0.0
    out = (end_f / start_f - 1.0) * 100.0
    return out if math.isfinite(out) else 0.0


def _stdev_1m_returns_pct(
    cur: sqlite3.Cursor, *, symbol: str, interval: str, start_ms: int, end_ms: int
) -> tuple[float | None, int]:
    cur.execute(
        """
        SELECT c
        FROM candles
        WHERE symbol = ? AND interval = ? AND t_close IS NOT NULL AND t_close >= ? AND t_close <= ? AND c IS NOT NULL AND c > 0
        ORDER BY t_close ASC
        """,
        (symbol, interval, int(start_ms), int(end_ms)),
    )
    closes = [float(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None]
    if len(closes) < 3:
        return None, 0

    rets_pct = [_pct_return(b, a) for a, b in zip(closes, closes[1:])]
    if len(rets_pct) < 2:
        return None, 0
    return float(statistics.pstdev(rets_pct)), int(len(rets_pct))


def compute_market_watch(
    *,
    db_path: Path,
    symbols: list[str],
    interval: str,
    benchmark_symbol: str,
    end_ms: int,
    grace_ms: int,
    vol_scale_sqrt_n: int,
) -> dict:
    res: dict = {
        "ok": False,
        "interval": str(interval),
        "db_path": str(db_path),
        "end_ms": int(end_ms),
        "end_utc": _iso_utc_from_ms(int(end_ms)),
        "benchmark": str(benchmark_symbol),
        "errors": [],
    }

    if not db_path.exists():
        res["errors"].append(f"candles_db_missing: {db_path}")
        return res

    symbols_u = _parse_symbol_list(",".join([str(s).strip().upper() for s in (symbols or []) if str(s).strip()]))
    if not symbols_u:
        res["errors"].append("symbols_empty")
        return res

    bench = str(benchmark_symbol or "").strip().upper() or "BTC"
    if bench not in symbols_u:
        bench = symbols_u[0]
    res["benchmark"] = bench

    con: sqlite3.Connection | None = None
    try:
        con = _connect_ro(db_path)
        cur = con.cursor()

        t_close_end = _last_closed_t_close(cur, symbol=bench, interval=interval, end_ms=end_ms, grace_ms=grace_ms)
        if t_close_end is None:
            res["errors"].append(f"no_closed_candle_for_benchmark: {bench}")
            return res

        res["end_t_close_ms"] = int(t_close_end)
        res["end_t_close_utc"] = _iso_utc_from_ms(int(t_close_end))

        end_pt = _close_at_or_before(cur, symbol=bench, interval=interval, t_close_ms=t_close_end)
        if end_pt is None:
            res["errors"].append(f"benchmark_end_close_missing: {bench}")
            return res

        def ret_for_minutes(mins: int) -> tuple[float | None, str | None, float | None]:
            start_target = int(t_close_end) - int(mins) * 60 * 1000
            start_pt = _close_at_or_before(cur, symbol=bench, interval=interval, t_close_ms=start_target)
            if start_pt is None:
                return None, None, None
            return (
                float(_pct_return(end_pt.close, start_pt.close)),
                _iso_utc_from_ms(start_pt.t_close_ms),
                float(start_pt.close),
            )

        btc_15m_ret, btc_15m_start_utc, btc_15m_start_close = ret_for_minutes(15)
        btc_60m_ret, btc_60m_start_utc, btc_60m_start_close = ret_for_minutes(60)
        res["btc"] = {
            "end_close": float(end_pt.close),
            "end_close_utc": _iso_utc_from_ms(end_pt.t_close_ms),
            "ret_15m_pct": btc_15m_ret,
            "start_15m_utc": btc_15m_start_utc,
            "start_15m_close": btc_15m_start_close,
            "ret_60m_pct": btc_60m_ret,
            "start_60m_utc": btc_60m_start_utc,
            "start_60m_close": btc_60m_start_close,
        }

        # 60m realized vol: stdev of 1m returns (%) scaled by sqrt(N) for the horizon.
        start_60m_ms = int(t_close_end) - 60 * 60 * 1000
        stdev_1m_pct, n_rets = _stdev_1m_returns_pct(
            cur, symbol=bench, interval=interval, start_ms=start_60m_ms, end_ms=t_close_end
        )
        vol_60m_pct = None
        if stdev_1m_pct is not None:
            try:
                vol_60m_pct = float(stdev_1m_pct) * math.sqrt(float(vol_scale_sqrt_n))
            except Exception:
                vol_60m_pct = None

        res["btc"]["stdev_1m_ret_pct"] = stdev_1m_pct
        res["btc"]["stdev_1m_n"] = int(n_rets)
        res["btc"]["realized_vol_60m_pct"] = vol_60m_pct
        res["btc"]["realized_vol_60m_scale_sqrt_n"] = int(vol_scale_sqrt_n)

        # Breadth + movers (60m).
        movers: list[dict] = []
        pos = neg = flat = missing = 0
        for sym in symbols_u:
            end_s = _close_at_or_before(cur, symbol=sym, interval=interval, t_close_ms=t_close_end)
            start_s = _close_at_or_before(cur, symbol=sym, interval=interval, t_close_ms=start_60m_ms)
            if end_s is None or start_s is None:
                missing += 1
                continue
            ret = float(_pct_return(end_s.close, start_s.close))
            movers.append({"symbol": sym, "ret_60m_pct": ret})
            if ret > 0:
                pos += 1
            elif ret < 0:
                neg += 1
            else:
                flat += 1

        denom = len(symbols_u) - missing
        breadth = (pos / denom * 100.0) if denom > 0 else None
        res["breadth_60m_pct"] = breadth
        res["breadth_counts"] = {"pos": pos, "neg": neg, "flat": flat, "missing": missing, "total": len(symbols_u)}

        movers_sorted = sorted(movers, key=lambda r: abs(float(r.get("ret_60m_pct") or 0.0)), reverse=True)
        res["top_movers_abs_60m"] = movers_sorted[:5]

        # Red flags (informational regime markers — signal elevated vol, not a gate).
        red_flags: list[str] = []
        try:
            if btc_15m_ret is not None and abs(float(btc_15m_ret)) >= 0.8:
                red_flags.append("btc_15m_abs_ret>=0.8%")
        except Exception:
            pass
        try:
            if vol_60m_pct is not None and float(vol_60m_pct) >= 1.2:
                red_flags.append("btc_60m_realized_vol>=1.2%")
        except Exception:
            pass
        try:
            if breadth is not None and float(breadth) <= 35.0 and vol_60m_pct is not None and float(vol_60m_pct) >= 1.2:
                red_flags.append("breadth<=35%_with_high_vol")
        except Exception:
            pass

        res["red_flags"] = red_flags

        # Simple regime label.
        regime = "CHOPPY"
        if vol_60m_pct is not None and float(vol_60m_pct) >= 1.2:
            regime = "HIGH_VOL"
        elif btc_60m_ret is not None and abs(float(btc_60m_ret)) >= 1.0:
            regime = "TRENDING"
        res["regime"] = regime

        res["ok"] = True
        return res
    except Exception as e:
        res["errors"].append(f"exception: {e}")
        return res
    finally:
        try:
            if con is not None:
                con.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="AI Quant Market Watch (local candles only)")
    ap.add_argument("--interval", default="1m")
    ap.add_argument("--db", default="")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--symbols-env", default="~/.config/openclaw/ai-quant-universe.env")
    ap.add_argument("--benchmark", default="BTC")
    ap.add_argument("--end-ms", type=int, default=0, help="Override end time (epoch ms). Default: now.")
    ap.add_argument("--grace-ms", type=int, default=2000, help="Exclude candles closed within this grace window.")
    ap.add_argument("--vol-scale-sqrt-n", type=int, default=60, help="Vol = stdev(1m returns) * sqrt(N). Default N=60.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    interval = str(args.interval or "1m").strip() or "1m"
    db_path = Path(str(args.db).strip()).expanduser() if str(args.db).strip() else _candles_db_path(interval).expanduser()

    symbols_raw = str(args.symbols or "").strip()
    if not symbols_raw:
        env_path = Path(str(args.symbols_env)).expanduser()
        env = _read_env_file(env_path)
        symbols_raw = str(env.get("AI_QUANT_SYMBOLS") or "").strip()
    if not symbols_raw:
        symbols_raw = str(os.getenv("AI_QUANT_SYMBOLS", "") or "").strip()
    symbols = _parse_symbol_list(symbols_raw)

    end_ms = int(args.end_ms) if int(args.end_ms or 0) > 0 else int(time.time() * 1000)

    res = compute_market_watch(
        db_path=db_path,
        symbols=symbols,
        interval=interval,
        benchmark_symbol=str(args.benchmark),
        end_ms=end_ms,
        grace_ms=int(args.grace_ms),
        vol_scale_sqrt_n=int(args.vol_scale_sqrt_n),
    )

    if args.json:
        print(json.dumps(res, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return 0 if res.get("ok") else 2

    if not res.get("ok"):
        print("market_watch: ERROR")
        for e in (res.get("errors") or []):
            print("-", e)
        return 2

    btc = res.get("btc") or {}

    def _fmt(val: object, fmt: str) -> str:
        try:
            return fmt.format(float(val))
        except Exception:
            return "n/a"

    print(
        " | ".join(
            [
                f"BTC 15m: {_fmt(btc.get('ret_15m_pct'), '{:+.2f}%')}",
                f"60m: {_fmt(btc.get('ret_60m_pct'), '{:+.2f}%')}",
                f"Vol(60m): {_fmt(btc.get('realized_vol_60m_pct'), '{:.2f}%')}",
                f"Breadth: {_fmt(res.get('breadth_60m_pct'), '{:.1f}%')}",
                f"Regime: {res.get('regime')}",
                f"end={res.get('end_t_close_utc')} UTC",
            ]
        )
    )

    red_flags = res.get("red_flags") or []
    if red_flags:
        print("red_flags:")
        for f in red_flags:
            print("-", f)

    movers = res.get("top_movers_abs_60m") or []
    if movers:
        print("top_movers_abs_60m:")
        for m in movers:
            sym = m.get("symbol")
            r = m.get("ret_60m_pct")
            try:
                r_s = f"{float(r):+.2f}%"
            except Exception:
                r_s = str(r)
            print(f"- {sym}: {r_s}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
