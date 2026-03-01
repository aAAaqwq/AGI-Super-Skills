#!/usr/bin/env python3
"""Run scheduled replay-bundle alignment checks and maintain a release blocker.

This orchestrator builds a deterministic replay bundle for a recent live window,
runs the full paper deterministic replay harness, and writes:

- a per-run report JSON
- a release-blocker JSON (blocked when the gate fails)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
from typing import Any

_STRATEGY_SHA1_RE = re.compile(r"strategy_sha1=([0-9a-fA-F]{7,40})")
_PROMOTED_ENV_PATH_RE = re.compile(r"AI_QUANT_STRATEGY_YAML\s*→\s*(\S+)")
_PROMOTED_LOADED_PATH_RE = re.compile(r"loaded role='[^']+'\s+from\s+(\S+)")

try:
    import yaml
except Exception:  # pragma: no cover - optional runtime dependency
    yaml = None


def _now_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _resolve_path(raw: str, *, base: Path) -> Path:
    p = Path(str(raw)).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (base / p).resolve()


def _cli_arg_present(flag: str) -> bool:
    needle = str(flag or "").strip()
    if not needle:
        return False
    for arg in sys.argv[1:]:
        text = str(arg or "")
        if text == needle or text.startswith(f"{needle}="):
            return True
    return False


def _read_live_baseline_count(manifest_path: Path) -> int:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return -1
    if not isinstance(payload, dict):
        return -1
    counts = payload.get("counts") or {}
    if not isinstance(counts, dict):
        return -1
    try:
        return int(counts.get("live_baseline_trades") or 0)
    except Exception:
        return -1


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_to_log(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fp:
        fp.write(f"$ {' '.join(shlex.quote(x) for x in cmd)}\n")
        fp.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=fp,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return int(proc.returncode)


def _db_has_table(db_path: Path, table_name: str) -> bool:
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (str(table_name),),
            ).fetchone()
            return bool(row is not None)
        finally:
            conn.close()
    except Exception:
        return False


def _candles_interval_coverage_ms(candles_db: Path, interval: str) -> tuple[int | None, int | None]:
    if not candles_db.exists():
        return None, None
    try:
        conn = sqlite3.connect(f"file:{candles_db}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute(
                "SELECT MIN(t), MAX(t) FROM candles WHERE interval = ?",
                (str(interval),),
            ).fetchone()
            if not row:
                return None, None
            lo_raw, hi_raw = row[0], row[1]
            if lo_raw is None or hi_raw is None:
                return None, None
            return int(lo_raw), int(hi_raw)
        finally:
            conn.close()
    except Exception:
        return None, None


def _latest_closed_bar_start_ts(candles_db: Path, *, interval: str, cutoff_ts: int) -> int | None:
    if not candles_db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{candles_db}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute(
                "SELECT MAX(t) FROM candles WHERE interval = ? AND t_close IS NOT NULL AND t_close <= ?",
                (str(interval), int(cutoff_ts)),
            ).fetchone()
            if not row or row[0] is None:
                return None
            return int(row[0])
        finally:
            conn.close()
    except Exception:
        return None


def _interval_to_bucket_ms(interval: str) -> int:
    raw = str(interval or "").strip().lower()
    if not raw:
        return 1
    m = re.fullmatch(r"(\d+)([mhd])", raw)
    if m is None:
        return 1
    qty = int(m.group(1))
    unit = m.group(2)
    unit_ms = {
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
    }[unit]
    if qty <= 0:
        return 1
    return int(qty * unit_ms)


def _runtime_strategy_window_stats(live_db: Path, *, from_ts: int, to_ts: int) -> dict[str, Any]:
    if not live_db.exists():
        return {
            "sampled_rows": 0,
            "strategy_sha1_distinct": 0,
            "last_segment_from_ts": None,
            "last_segment_to_ts": None,
            "last_segment_sha1": None,
            "timeline": [],
        }
    try:
        conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT ts_ms, message FROM runtime_logs WHERE ts_ms >= ? AND ts_ms <= ? ORDER BY ts_ms ASC, id ASC",
                (int(from_ts), int(to_ts)),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return {
            "sampled_rows": 0,
            "strategy_sha1_distinct": 0,
            "last_segment_from_ts": None,
            "last_segment_to_ts": None,
            "last_segment_sha1": None,
            "timeline": [],
        }

    timeline: list[dict[str, Any]] = []
    sampled_rows = 0
    distinct_sha: set[str] = set()

    for row in rows:
        ts_ms = int(row["ts_ms"] or 0)
        message = str(row["message"] or "")
        if ts_ms <= 0 or not message:
            continue
        m = _STRATEGY_SHA1_RE.search(message)
        if m is None:
            continue
        sha = str(m.group(1) or "").strip().lower()
        if not sha:
            continue
        sampled_rows += 1
        distinct_sha.add(sha)

        if timeline and str(timeline[-1]["strategy_sha1"]) == sha:
            timeline[-1]["last_ts_ms"] = ts_ms
            timeline[-1]["sample_count"] = int(timeline[-1]["sample_count"]) + 1
        else:
            timeline.append(
                {
                    "strategy_sha1": sha,
                    "first_ts_ms": ts_ms,
                    "last_ts_ms": ts_ms,
                    "sample_count": 1,
                }
            )

    last_segment = timeline[-1] if timeline else None
    return {
        "sampled_rows": int(sampled_rows),
        "strategy_sha1_distinct": len(distinct_sha),
        "last_segment_from_ts": int(last_segment["first_ts_ms"]) if last_segment else None,
        "last_segment_to_ts": int(last_segment["last_ts_ms"]) if last_segment else None,
        "last_segment_sha1": str(last_segment["strategy_sha1"]) if last_segment else None,
        "timeline": timeline,
    }


def _ts_ms_to_iso_utc(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=dt.timezone.utc).isoformat()


def _count_live_trades_in_window(live_db: Path, *, from_ts: int, to_ts: int) -> int:
    if not live_db.exists() or from_ts > to_ts:
        return 0
    from_iso = _ts_ms_to_iso_utc(int(from_ts))
    to_iso = _ts_ms_to_iso_utc(int(to_ts))
    try:
        conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute(
                "SELECT COUNT(1) FROM trades WHERE timestamp >= ? AND timestamp <= ?",
                (from_iso, to_iso),
            ).fetchone()
            if not row:
                return 0
            return int(row[0] or 0)
        finally:
            conn.close()
    except Exception:
        return 0


def _live_decision_trace_window_stats(live_db: Path, *, from_ts: int, to_ts: int) -> dict[str, Any]:
    out = {
        "table_present": False,
        "rows_total": 0,
        "rows_with_config_fingerprint": 0,
    }
    if not live_db.exists() or from_ts > to_ts:
        return out
    try:
        conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='decision_events' LIMIT 1"
            ).fetchone()
            if row is None:
                return out
            out["table_present"] = True

            from_i = int(from_ts)
            to_i = int(to_ts)
            total = conn.execute(
                "SELECT COUNT(1) FROM decision_events WHERE timestamp_ms >= ? AND timestamp_ms <= ?",
                (from_i, to_i),
            ).fetchone()
            out["rows_total"] = int((total[0] if total else 0) or 0)

            cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(decision_events)").fetchall()}
            if "config_fingerprint" in cols:
                cfg = conn.execute(
                    "SELECT COUNT(1) FROM decision_events "
                    "WHERE timestamp_ms >= ? AND timestamp_ms <= ? "
                    "AND COALESCE(config_fingerprint,'') <> ''",
                    (from_i, to_i),
                ).fetchone()
                out["rows_with_config_fingerprint"] = int((cfg[0] if cfg else 0) or 0)
            else:
                out["rows_with_config_fingerprint"] = 0
            return out
        finally:
            conn.close()
    except Exception:
        return out


def _oms_strategy_window_stats(live_db: Path, *, from_ts: int, to_ts: int) -> dict[str, Any]:
    out = {
        "table_present": False,
        "rows_total": 0,
        "rows_with_strategy_sha1": 0,
    }
    if not live_db.exists() or from_ts > to_ts:
        return out
    try:
        conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='oms_intents' LIMIT 1"
            ).fetchone()
            if row is None:
                return out
            out["table_present"] = True
            q = (
                "FROM oms_intents WHERE COALESCE(decision_ts_ms, created_ts_ms) >= ? "
                "AND COALESCE(decision_ts_ms, created_ts_ms) <= ?"
            )
            from_i = int(from_ts)
            to_i = int(to_ts)
            total = conn.execute(f"SELECT COUNT(1) {q}", (from_i, to_i)).fetchone()
            out["rows_total"] = int((total[0] if total else 0) or 0)
            with_sha = conn.execute(
                "SELECT COUNT(1) "
                f"{q} "
                "AND strategy_sha1 IS NOT NULL AND TRIM(strategy_sha1) <> ''",
                (from_i, to_i),
            ).fetchone()
            out["rows_with_strategy_sha1"] = int((with_sha[0] if with_sha else 0) or 0)
            return out
        finally:
            conn.close()
    except Exception:
        return out


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_strategy_engine_interval(config_path: Path) -> str:
    interval, _, _ = _load_strategy_engine_intervals(config_path)
    return interval


def _load_strategy_engine_intervals(config_path: Path) -> tuple[str, str, str]:
    if yaml is None or not config_path.exists():
        return "", "", ""
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "", "", ""
    if not isinstance(raw, dict):
        return "", "", ""
    global_cfg = raw.get("global") or {}
    if not isinstance(global_cfg, dict):
        return "", "", ""
    engine_cfg = global_cfg.get("engine") or {}
    if not isinstance(engine_cfg, dict):
        return "", "", ""
    interval = str(engine_cfg.get("interval") or "").strip()
    entry_interval = str(engine_cfg.get("entry_interval") or "").strip()
    exit_interval = str(engine_cfg.get("exit_interval") or "").strip()
    return interval, entry_interval, exit_interval


def _derive_interval_db(base_candles_db: Path, interval: str, *, repo_root: Path | None = None) -> Path | None:
    iv = str(interval or "").strip()
    if not iv:
        return None
    candidates: list[Path] = []
    base_name = str(base_candles_db.name or "")
    if base_name == f"candles_{iv}.db" and base_candles_db.exists():
        return base_candles_db.resolve()
    if base_name.startswith("candles_") and base_name.endswith(".db"):
        candidates.append((base_candles_db.parent / f"candles_{iv}.db").resolve())
    for parent in base_candles_db.parents:
        if parent.name == "candles_dbs":
            candidates.append((parent / f"candles_{iv}.db").resolve())
            break
    if repo_root is not None:
        candidates.append((repo_root / "candles_dbs" / f"candles_{iv}.db").resolve())

    seen: set[str] = set()
    for candidate in candidates:
        raw = str(candidate)
        if raw in seen:
            continue
        seen.add(raw)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _snapshot_sqlite_db(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)
    dst_conn = sqlite3.connect(str(target), timeout=30)
    try:
        src_conn.backup(dst_conn)
        dst_conn.commit()
    finally:
        dst_conn.close()
        src_conn.close()


def _freeze_market_data_dbs(
    *,
    bundle_dir: Path,
    base_candles_db: Path,
    interval: str,
    entry_interval: str,
    exit_interval: str,
    funding_db: Path | None,
    repo_root: Path,
) -> dict[str, Any]:
    snapshot_dir = (bundle_dir / "market_data_snapshot").resolve()
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    intervals: list[str] = []
    for raw in (interval, entry_interval, exit_interval):
        iv = str(raw or "").strip()
        if iv and iv not in intervals:
            intervals.append(iv)

    if not intervals:
        raise ValueError("no replay intervals available for market-data snapshot")

    src_to_dst: dict[str, Path] = {}
    interval_to_dst: dict[str, Path] = {}

    for iv in intervals:
        if iv == str(interval).strip():
            src = base_candles_db.resolve()
        else:
            resolved = _derive_interval_db(base_candles_db, iv, repo_root=repo_root)
            if resolved is None:
                raise FileNotFoundError(f"missing candles DB for interval {iv!r} beside {base_candles_db}")
            src = resolved.resolve()

        src_key = str(src)
        dst = src_to_dst.get(src_key)
        if dst is None:
            dst = (snapshot_dir / src.name).resolve()
            _snapshot_sqlite_db(src, dst)
            src_to_dst[src_key] = dst
        interval_to_dst[iv] = dst

    funding_snapshot: Path | None = None
    if funding_db is not None:
        funding_snapshot = (snapshot_dir / funding_db.name).resolve()
        _snapshot_sqlite_db(funding_db.resolve(), funding_snapshot)

    return {
        "snapshot_dir": str(snapshot_dir),
        "candles_db": str(interval_to_dst[str(interval).strip()]),
        "entry_candles_db": str(interval_to_dst.get(str(entry_interval).strip() or str(interval).strip(), interval_to_dst[str(interval).strip()])),
        "exit_candles_db": str(interval_to_dst.get(str(exit_interval).strip() or str(interval).strip(), interval_to_dst[str(interval).strip()])),
        "funding_db": str(funding_snapshot) if funding_snapshot is not None else None,
        "intervals": intervals,
    }


def _resolve_runtime_strategy_lock_file(*, bundle_root: Path, repo_root: Path, runtime_sha1: str) -> Path | None:
    sha = str(runtime_sha1 or "").strip().lower()
    if not sha:
        return None
    short = sha[:8]
    candidates = [
        (bundle_root / f"strategy_overrides_{sha}.yaml").resolve(),
        (bundle_root / f"strategy_overrides_{short}.yaml").resolve(),
        (repo_root / "config" / f"strategy_overrides_{sha}.yaml").resolve(),
        (repo_root / "config" / f"strategy_overrides_{short}.yaml").resolve(),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_yaml_mapping(path: Path) -> dict[str, Any] | None:
    if yaml is None or not path.exists():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return raw if isinstance(raw, dict) else {}


def _hash_json_canonical(obj: Any) -> str:
    try:
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = repr(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_json_canonical_sha1(obj: Any) -> str:
    try:
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception:
        payload = repr(obj).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _strategy_config_hashes(path: Path) -> tuple[str, str]:
    loaded = _load_yaml_mapping(path)
    if loaded is None:
        return "", ""
    return _hash_json_canonical(loaded), _hash_json_canonical_sha1(loaded)


def _extract_runtime_strategy_yaml_candidates(
    live_db: Path,
    *,
    from_ts: int,
    to_ts: int,
) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    if not live_db.exists() or from_ts > to_ts:
        return candidates
    try:
        conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT message FROM runtime_logs WHERE ts_ms >= ? AND ts_ms <= ? ORDER BY ts_ms DESC, id DESC",
                (int(from_ts), int(to_ts)),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return candidates

    for row in rows:
        message = str(row["message"] or "")
        if "promoted_config" not in message:
            continue
        hit = _PROMOTED_ENV_PATH_RE.search(message)
        if hit is None:
            hit = _PROMOTED_LOADED_PATH_RE.search(message)
        if hit is None:
            continue
        raw_path = str(hit.group(1) or "").strip().strip("'\"")
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        try:
            resolved = path.resolve()
        except Exception:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists() and resolved.is_file():
            candidates.append(resolved)
    return candidates


def _build_parser() -> argparse.ArgumentParser:
    repo_root = _default_repo_root()
    ap = argparse.ArgumentParser(description="Run scheduled replay alignment gate checks.")
    ap.add_argument("--repo-root", default=str(repo_root), help="Repo root path.")
    ap.add_argument(
        "--live-db",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_LIVE_DB", "./trading_engine_live.db") or "./trading_engine_live.db"),
        help="Live SQLite DB path.",
    )
    ap.add_argument(
        "--paper-db",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_PAPER_DB", "./trading_engine.db") or "./trading_engine.db"),
        help="Paper SQLite DB path.",
    )
    ap.add_argument(
        "--candles-db",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_CANDLES_DB", "") or ""),
        help="Candles SQLite DB path (required unless set via AI_QUANT_REPLAY_GATE_CANDLES_DB).",
    )
    ap.add_argument(
        "--funding-db",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_FUNDING_DB", "") or ""),
        help="Optional funding SQLite DB path.",
    )
    ap.add_argument(
        "--interval",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_INTERVAL", "1h") or "1h"),
        help="Replay interval.",
    )
    ap.add_argument(
        "--strategy-config",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_STRATEGY_CONFIG", "") or ""),
        help=(
            "Optional strategy YAML for deterministic replay. "
            "When unset, the scheduler tries runtime SHA lock files before bundle defaults."
        ),
    )
    ap.add_argument(
        "--window-minutes",
        type=int,
        default=_env_int("AI_QUANT_REPLAY_GATE_WINDOW_MINUTES", 240),
        help="Replay window size in minutes (default: 240).",
    )
    ap.add_argument(
        "--lag-minutes",
        type=int,
        default=_env_int("AI_QUANT_REPLAY_GATE_LAG_MINUTES", 2),
        help="Tail lag in minutes before now for replay end timestamp (default: 2).",
    )
    ap.add_argument(
        "--bundle-root",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_BUNDLE_ROOT", "/tmp/openclaw-ai-quant/replay_gate") or "/tmp/openclaw-ai-quant/replay_gate"),
        help="Root directory for scheduled replay bundles.",
    )
    strict_group = ap.add_mutually_exclusive_group()
    strict_group.add_argument(
        "--strict-no-residuals",
        dest="strict_no_residuals",
        action="store_true",
        help="Fail when accepted residuals are present in alignment reports.",
    )
    strict_group.add_argument(
        "--allow-residuals",
        dest="strict_no_residuals",
        action="store_false",
        help="Allow accepted residuals from alignment reports.",
    )
    ap.set_defaults(strict_no_residuals=_env_bool("AI_QUANT_REPLAY_GATE_STRICT_NO_RESIDUALS", True))
    ap.add_argument(
        "--min-live-trades",
        type=int,
        default=_env_int("AI_QUANT_REPLAY_GATE_MIN_LIVE_TRADES", 1),
        help="Minimum live baseline trade count required for a valid scheduled check (default: 1).",
    )
    ap.add_argument(
        "--release-blocker-file",
        default=str(os.getenv("AI_QUANT_REPLAY_GATE_BLOCKER_FILE", "") or ""),
        help="Optional release-blocker status path (default: <bundle-root>/release_blocker.json).",
    )
    ap.add_argument(
        "--output",
        default="",
        help="Optional run report JSON path (default: <bundle-dir>/scheduled_alignment_gate_run.json).",
    )
    auto_clamp_default = _env_bool("AI_QUANT_REPLAY_GATE_AUTO_STRATEGY_WINDOW_CLAMP", True)
    clamp_group = ap.add_mutually_exclusive_group()
    clamp_group.add_argument(
        "--auto-strategy-window-clamp",
        dest="auto_strategy_window_clamp",
        action="store_true",
        help="When strategy SHA drifts in the requested window, clamp to the latest contiguous stable SHA segment.",
    )
    clamp_group.add_argument(
        "--disable-auto-strategy-window-clamp",
        dest="auto_strategy_window_clamp",
        action="store_false",
        help="Disable auto-clamping to the latest stable strategy SHA segment.",
    )
    ap.set_defaults(auto_strategy_window_clamp=auto_clamp_default)
    strategy_lock_default = _env_bool("AI_QUANT_REPLAY_GATE_REQUIRE_RUNTIME_STRATEGY_LOCK", False)
    strategy_lock_group = ap.add_mutually_exclusive_group()
    strategy_lock_group.add_argument(
        "--require-runtime-strategy-lock",
        dest="require_runtime_strategy_lock",
        action="store_true",
        help=(
            "Fail closed when runtime strategy SHA is present but no matching "
            "strategy_overrides_<sha>.yaml lock file can be resolved."
        ),
    )
    strategy_lock_group.add_argument(
        "--allow-missing-runtime-strategy-lock",
        dest="require_runtime_strategy_lock",
        action="store_false",
        help=(
            "Allow fallback to bundle defaults when runtime strategy lock YAML "
            "cannot be resolved."
        ),
    )
    ap.set_defaults(require_runtime_strategy_lock=strategy_lock_default)
    return ap


def main() -> int:
    args = _build_parser().parse_args()

    repo_root = _resolve_path(str(args.repo_root), base=Path.cwd())
    resolve_base = repo_root if repo_root.exists() else Path.cwd()
    live_db = _resolve_path(str(args.live_db), base=resolve_base)
    paper_db = _resolve_path(str(args.paper_db), base=resolve_base)
    candles_db_raw = str(args.candles_db or "").strip()
    candles_db = _resolve_path(candles_db_raw, base=resolve_base) if candles_db_raw else Path("")
    funding_db_raw = str(args.funding_db or "").strip()
    funding_db = _resolve_path(funding_db_raw, base=resolve_base) if funding_db_raw else None

    interval = str(args.interval or "").strip()

    now_ms = _now_ms()
    lag_minutes = int(args.lag_minutes)
    window_minutes = int(args.window_minutes)
    min_live_trades = int(args.min_live_trades)
    requested_to_ts = int(now_ms - lag_minutes * 60_000)
    requested_from_ts = int(requested_to_ts - window_minutes * 60_000)
    to_ts = int(requested_to_ts)
    from_ts = int(requested_from_ts)
    coverage_from_ts: int | None = None
    coverage_to_ts: int | None = None
    strategy_window_stats: dict[str, Any] | None = None
    strategy_window_adjustment: dict[str, Any] | None = None
    strategy_config_resolution: dict[str, Any] | None = None
    live_decision_trace_stats: dict[str, Any] | None = None
    oms_strategy_stats: dict[str, Any] | None = None
    market_data_snapshot: dict[str, Any] | None = None

    bundle_root = _resolve_path(str(args.bundle_root), base=resolve_base)
    try:
        bundle_root.mkdir(parents=True, exist_ok=True)
    except Exception:
        bundle_root = Path("/tmp/openclaw-ai-quant/replay_gate").resolve()
        bundle_root.mkdir(parents=True, exist_ok=True)
    run_tag = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    interval_tag = interval if interval else "unknown_interval"
    bundle_dir = (bundle_root / f"bundle_{interval_tag}_{from_ts}_{to_ts}_{run_tag}").resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    report_path = (
        _resolve_path(str(args.output), base=resolve_base)
        if str(args.output or "").strip()
        else (bundle_dir / "scheduled_alignment_gate_run.json").resolve()
    )
    blocker_path = (
        _resolve_path(str(args.release_blocker_file), base=resolve_base)
        if str(args.release_blocker_file or "").strip()
        else (bundle_root / "release_blocker.json").resolve()
    )
    build_log = (bundle_dir / "scheduled_build_bundle.log").resolve()
    harness_log = (bundle_dir / "scheduled_harness.log").resolve()
    manifest_path = (bundle_dir / "replay_bundle_manifest.json").resolve()
    harness_report_path = (bundle_dir / "paper_deterministic_replay_run.json").resolve()
    gate_report_path = (bundle_dir / "alignment_gate_report.json").resolve()

    env = os.environ.copy()
    env["REPO_ROOT"] = str(repo_root)
    env["AQC_SNAPSHOT_STRICT_REPLACE"] = "1"
    failures: list[dict[str, Any]] = []
    strategy_config_raw = str(args.strategy_config or "").strip()
    strategy_config_cli_override = _cli_arg_present("--strategy-config")
    strategy_config_path: Path | None = (
        _resolve_path(strategy_config_raw, base=resolve_base) if strategy_config_raw else None
    )

    if not repo_root.exists():
        failures.append(
            {
                "code": "repo_root_not_found",
                "classification": "state_initialisation_gap",
                "detail": str(repo_root),
            }
        )
    if not candles_db_raw:
        failures.append(
            {
                "code": "missing_candles_db",
                "classification": "state_initialisation_gap",
                "detail": "candles DB path is required (--candles-db or AI_QUANT_REPLAY_GATE_CANDLES_DB)",
            }
        )
    if not live_db.exists():
        failures.append(
            {
                "code": "live_db_not_found",
                "classification": "state_initialisation_gap",
                "detail": str(live_db),
            }
        )
    if not paper_db.exists():
        failures.append(
            {
                "code": "paper_db_not_found",
                "classification": "state_initialisation_gap",
                "detail": str(paper_db),
            }
        )
    if candles_db_raw and not candles_db.exists():
        failures.append(
            {
                "code": "candles_db_not_found",
                "classification": "state_initialisation_gap",
                "detail": str(candles_db),
            }
        )
    if funding_db is not None and not funding_db.exists():
        failures.append(
            {
                "code": "funding_db_not_found",
                "classification": "state_initialisation_gap",
                "detail": str(funding_db),
            }
        )
    if window_minutes <= 0:
        failures.append(
            {
                "code": "invalid_window_minutes",
                "classification": "state_initialisation_gap",
                "detail": f"window_minutes={window_minutes} must be > 0",
            }
        )
    if lag_minutes < 0:
        failures.append(
            {
                "code": "invalid_lag_minutes",
                "classification": "state_initialisation_gap",
                "detail": f"lag_minutes={lag_minutes} must be >= 0",
            }
        )
    if min_live_trades < 0:
        failures.append(
            {
                "code": "invalid_min_live_trades",
                "classification": "state_initialisation_gap",
                "detail": f"min_live_trades={min_live_trades} must be >= 0",
            }
        )
    if not interval:
        failures.append(
            {
                "code": "missing_interval",
                "classification": "state_initialisation_gap",
                "detail": "interval must not be empty",
            }
        )
    if requested_from_ts > requested_to_ts:
        failures.append(
            {
                "code": "invalid_replay_window",
                "classification": "state_initialisation_gap",
                "detail": f"from_ts={requested_from_ts} > to_ts={requested_to_ts}",
            }
        )
    if strategy_config_path is not None and not strategy_config_path.exists():
        failures.append(
            {
                "code": "strategy_config_not_found",
                "classification": "state_initialisation_gap",
                "detail": str(strategy_config_path),
            }
        )
    if not failures:
        strategy_window_stats = _runtime_strategy_window_stats(
            live_db,
            from_ts=int(from_ts),
            to_ts=int(to_ts),
        )
        if bool(args.auto_strategy_window_clamp):
            distinct_sha = int(strategy_window_stats.get("strategy_sha1_distinct") or 0)
            timeline = strategy_window_stats.get("timeline")
            timeline_rows = timeline if isinstance(timeline, list) else []
            if distinct_sha > 1 and timeline_rows:
                selected_segment: dict[str, Any] | None = None
                selected_from_ts: int | None = None
                selected_to_ts: int | None = None
                selected_trade_rows = 0
                selection_mode = "latest_segment_fallback"

                for segment in reversed(timeline_rows):
                    seg_from_raw = segment.get("first_ts_ms")
                    seg_to_raw = segment.get("last_ts_ms")
                    if not isinstance(seg_from_raw, int) or not isinstance(seg_to_raw, int):
                        continue
                    seg_from_ts = max(int(from_ts), int(seg_from_raw))
                    seg_to_ts = min(int(to_ts), int(seg_to_raw))
                    if seg_from_ts >= seg_to_ts:
                        continue
                    trade_rows = _count_live_trades_in_window(
                        live_db,
                        from_ts=int(seg_from_ts),
                        to_ts=int(seg_to_ts),
                    )
                    if trade_rows >= int(min_live_trades):
                        selected_segment = segment
                        selected_from_ts = int(seg_from_ts)
                        selected_to_ts = int(seg_to_ts)
                        selected_trade_rows = int(trade_rows)
                        selection_mode = "latest_segment_with_min_live_trades"
                        break

                if selected_segment is None:
                    fallback = timeline_rows[-1]
                    seg_from_raw = fallback.get("first_ts_ms")
                    seg_to_raw = fallback.get("last_ts_ms")
                    if isinstance(seg_from_raw, int) and isinstance(seg_to_raw, int):
                        seg_from_ts = max(int(from_ts), int(seg_from_raw))
                        seg_to_ts = min(int(to_ts), int(seg_to_raw))
                        if seg_from_ts < seg_to_ts:
                            selected_segment = fallback
                            selected_from_ts = int(seg_from_ts)
                            selected_to_ts = int(seg_to_ts)
                            selected_trade_rows = _count_live_trades_in_window(
                                live_db,
                                from_ts=int(seg_from_ts),
                                to_ts=int(seg_to_ts),
                            )

                if selected_segment is not None and selected_from_ts is not None and selected_to_ts is not None:
                    if selected_from_ts >= selected_to_ts:
                        failures.append(
                            {
                                "code": "invalid_strategy_window_clamp",
                                "classification": "state_initialisation_gap",
                                "detail": (
                                    f"clamped window is empty: from_ts={selected_from_ts} >= to_ts={selected_to_ts} "
                                    f"(strategy_sha1={selected_segment.get('strategy_sha1')})"
                                ),
                            }
                        )
                    else:
                        strategy_window_adjustment = {
                            "applied": True,
                            "reason": "strategy_sha1_drift_detected",
                            "strategy_sha1_distinct": distinct_sha,
                            "selection_mode": selection_mode,
                            "selected_segment_sha1": str(selected_segment.get("strategy_sha1") or "").strip().lower(),
                            "selected_segment_first_ts_ms": int(selected_segment.get("first_ts_ms") or selected_from_ts),
                            "selected_segment_last_ts_ms": int(selected_segment.get("last_ts_ms") or selected_to_ts),
                            "selected_live_trade_rows": int(selected_trade_rows),
                            "original_from_ts": int(from_ts),
                            "original_to_ts": int(to_ts),
                            "clamped_from_ts": int(selected_from_ts),
                            "clamped_to_ts": int(selected_to_ts),
                        }
                        from_ts = int(selected_from_ts)
                        to_ts = int(selected_to_ts)

        selected_runtime_sha = ""
        if isinstance(strategy_window_adjustment, dict):
            selected_runtime_sha = str(strategy_window_adjustment.get("selected_segment_sha1") or "").strip().lower()
        if not selected_runtime_sha and isinstance(strategy_window_stats, dict):
            selected_runtime_sha = str(strategy_window_stats.get("last_segment_sha1") or "").strip().lower()
        runtime_yaml_candidates: list[Path] = []
        runtime_yaml_match: Path | None = None
        if selected_runtime_sha:
            runtime_yaml_candidates = _extract_runtime_strategy_yaml_candidates(
                live_db,
                from_ts=int(from_ts),
                to_ts=int(to_ts),
            )
            for candidate in runtime_yaml_candidates:
                cand_sha256, cand_sha1 = _strategy_config_hashes(candidate)
                if cand_sha256.startswith(selected_runtime_sha) or cand_sha1.startswith(selected_runtime_sha):
                    runtime_yaml_match = candidate
                    break

        if selected_runtime_sha:
            strategy_config_resolution = {
                "selected_runtime_sha1": selected_runtime_sha,
                "selected_runtime_sha1_prefix8": selected_runtime_sha[:8],
                "runtime_yaml_candidates": [str(p) for p in runtime_yaml_candidates],
                "runtime_yaml_match": str(runtime_yaml_match) if runtime_yaml_match is not None else None,
                "required": bool(args.require_runtime_strategy_lock),
            }

        if strategy_config_path is None and runtime_yaml_match is not None:
            strategy_config_path = runtime_yaml_match
            if strategy_config_resolution is None:
                strategy_config_resolution = {}
            strategy_config_resolution["resolved_strategy_config"] = str(strategy_config_path)
            strategy_config_resolution["resolution_mode"] = "runtime_promoted_config_match"
        elif strategy_config_path is None and selected_runtime_sha:
            resolved = _resolve_runtime_strategy_lock_file(
                bundle_root=bundle_root,
                repo_root=repo_root,
                runtime_sha1=selected_runtime_sha,
            )
            if strategy_config_resolution is None:
                strategy_config_resolution = {}
            strategy_config_resolution["resolved_strategy_config"] = str(resolved) if resolved is not None else None
            strategy_config_resolution["resolution_mode"] = "runtime_lock_file"
            if resolved is not None:
                strategy_config_path = resolved
            elif bool(args.require_runtime_strategy_lock):
                failures.append(
                    {
                        "code": "missing_runtime_strategy_lock",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            "runtime strategy lock YAML not found; expected one of "
                            f"{bundle_root / f'strategy_overrides_{selected_runtime_sha}.yaml'} or "
                            f"{bundle_root / f'strategy_overrides_{selected_runtime_sha[:8]}.yaml'}"
                        ),
                    }
                )
        elif strategy_config_path is not None and selected_runtime_sha:
            explicit_sha256, explicit_sha1 = _strategy_config_hashes(strategy_config_path)
            explicit_match = bool(
                explicit_sha256.startswith(selected_runtime_sha) or explicit_sha1.startswith(selected_runtime_sha)
            )
            if strategy_config_resolution is None:
                strategy_config_resolution = {}
            strategy_config_resolution["explicit_strategy_config"] = str(strategy_config_path)
            strategy_config_resolution["explicit_strategy_config_sha256_prefix8"] = explicit_sha256[:8]
            strategy_config_resolution["explicit_strategy_config_sha1_prefix8"] = explicit_sha1[:8]
            strategy_config_resolution["explicit_matches_runtime_sha"] = bool(explicit_match)
            strategy_config_resolution["explicit_strategy_config_cli_override"] = bool(strategy_config_cli_override)
            if (not explicit_match) and runtime_yaml_match is not None:
                if strategy_config_cli_override and (not bool(args.require_runtime_strategy_lock)):
                    strategy_config_resolution["resolution_mode"] = "keep_explicit_strategy_config"
                else:
                    strategy_config_path = runtime_yaml_match
                    strategy_config_resolution["resolved_strategy_config"] = str(strategy_config_path)
                    strategy_config_resolution["resolution_mode"] = "override_explicit_with_runtime_promoted_config"
            elif (not explicit_match) and bool(args.require_runtime_strategy_lock):
                failures.append(
                    {
                        "code": "explicit_strategy_config_runtime_sha_mismatch",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"explicit strategy-config {strategy_config_path} does not match runtime "
                            f"strategy_sha1 prefix {selected_runtime_sha[:8]}"
                        ),
                    }
                )

        if strategy_config_path is not None:
            strategy_interval = _load_strategy_engine_interval(strategy_config_path)
            if strategy_interval and strategy_interval != interval:
                derived_candles_db = _derive_interval_db(
                    candles_db,
                    strategy_interval,
                    repo_root=repo_root,
                )
                if derived_candles_db is None:
                    failures.append(
                        {
                            "code": "missing_strategy_interval_candles_db",
                            "classification": "market_data_alignment_gap",
                            "detail": (
                                f"strategy interval '{strategy_interval}' requires candles DB "
                                f"{candles_db.parent / f'candles_{strategy_interval}.db'}"
                            ),
                        }
                    )
                else:
                    interval = strategy_interval
                    candles_db = derived_candles_db
                    if strategy_config_resolution is None:
                        strategy_config_resolution = {}
                    strategy_config_resolution["interval_aligned_from"] = str(args.interval or "").strip()
                    strategy_config_resolution["interval_aligned_to"] = str(strategy_interval)
                    strategy_config_resolution["candles_db_aligned_to"] = str(candles_db)

        bucket_ms = _interval_to_bucket_ms(interval)
        if bucket_ms > 1 and (int(from_ts) % int(bucket_ms)) != 0:
            aligned_from_ts = ((int(from_ts) // int(bucket_ms)) + 1) * int(bucket_ms)
            if aligned_from_ts > int(to_ts):
                failures.append(
                    {
                        "code": "invalid_aligned_replay_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"from_ts alignment for interval={interval} produced empty window: "
                            f"aligned_from_ts={aligned_from_ts} > to_ts={int(to_ts)}"
                        ),
                    }
                )
            else:
                if strategy_config_resolution is None:
                    strategy_config_resolution = {}
                strategy_config_resolution["from_ts_aligned_from"] = int(from_ts)
                strategy_config_resolution["from_ts_aligned_to"] = int(aligned_from_ts)
                strategy_config_resolution["from_ts_alignment_bucket_ms"] = int(bucket_ms)
                from_ts = int(aligned_from_ts)

        if bucket_ms > 1:
            closed_to_ts = _latest_closed_bar_start_ts(
                candles_db,
                interval=interval,
                cutoff_ts=int(to_ts),
            )
            if closed_to_ts is None:
                failures.append(
                    {
                        "code": "missing_closed_bar_for_replay_cutoff",
                        "classification": "market_data_alignment_gap",
                        "detail": (
                            f"unable to resolve latest closed bar for interval={interval} "
                            f"and cutoff_ts={int(to_ts)} from {candles_db}"
                        ),
                    }
                )
            elif int(closed_to_ts) < int(from_ts):
                failures.append(
                    {
                        "code": "invalid_closed_bar_replay_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"closed-bar clamp produced empty window: from_ts={int(from_ts)} > "
                            f"closed_to_ts={int(closed_to_ts)} (interval={interval}, bucket_ms={int(bucket_ms)})"
                        ),
                    }
                )
            else:
                if strategy_config_resolution is None:
                    strategy_config_resolution = {}
                strategy_config_resolution["to_ts_closed_bar_aligned_from"] = int(to_ts)
                strategy_config_resolution["to_ts_closed_bar_aligned_to"] = int(closed_to_ts)
                strategy_config_resolution["to_ts_closed_bar_bucket_ms"] = int(bucket_ms)
                to_ts = int(closed_to_ts)

        coverage_from_ts, coverage_to_ts = _candles_interval_coverage_ms(candles_db, interval)
        if coverage_from_ts is None or coverage_to_ts is None:
            failures.append(
                {
                    "code": "missing_interval_coverage",
                    "classification": "market_data_alignment_gap",
                    "detail": f"no candles coverage found for interval={interval} in {candles_db}",
                }
            )
        else:
            if to_ts > coverage_to_ts:
                to_ts = int(coverage_to_ts)
                from_ts = int(to_ts - window_minutes * 60_000)
            if from_ts < coverage_from_ts:
                from_ts = int(coverage_from_ts)
            if from_ts > to_ts:
                failures.append(
                    {
                        "code": "invalid_clamped_replay_window",
                        "classification": "market_data_alignment_gap",
                        "detail": (
                            f"effective window outside coverage: from_ts={from_ts}, to_ts={to_ts}, "
                            f"coverage={coverage_from_ts}..{coverage_to_ts}"
                        ),
                    }
                )

        if not failures:
            live_decision_trace_stats = _live_decision_trace_window_stats(
                live_db,
                from_ts=int(from_ts),
                to_ts=int(to_ts),
            )
            table_present = bool((live_decision_trace_stats or {}).get("table_present"))
            rows_total = int((live_decision_trace_stats or {}).get("rows_total") or 0)
            rows_cfg = int((live_decision_trace_stats or {}).get("rows_with_config_fingerprint") or 0)
            if not table_present:
                failures.append(
                    {
                        "code": "missing_live_decision_events_table",
                        "classification": "state_initialisation_gap",
                        "detail": "live DB has no decision_events table in scheduled replay window",
                    }
                )
            elif rows_total <= 0:
                failures.append(
                    {
                        "code": "missing_live_decision_events_in_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"decision_events rows are empty in window "
                            f"from_ts={int(from_ts)} to_ts={int(to_ts)}"
                        ),
                    }
                )
            elif rows_cfg <= 0:
                failures.append(
                    {
                        "code": "missing_live_config_fingerprint_in_window",
                        "classification": "state_initialisation_gap",
                        "detail": (
                            f"decision_events has no non-empty config_fingerprint rows in window "
                            f"from_ts={int(from_ts)} to_ts={int(to_ts)}"
                        ),
                    }
                )

    if not failures:
        cfg_entry_interval = ""
        cfg_exit_interval = ""
        if strategy_config_path is not None:
            _, cfg_entry_interval, cfg_exit_interval = _load_strategy_engine_intervals(strategy_config_path)

        replay_entry_interval = str(cfg_entry_interval or interval).strip()
        replay_exit_interval = str(cfg_exit_interval or interval).strip()
        try:
            market_data_snapshot = _freeze_market_data_dbs(
                bundle_dir=bundle_dir,
                base_candles_db=candles_db,
                interval=interval,
                entry_interval=replay_entry_interval,
                exit_interval=replay_exit_interval,
                funding_db=funding_db,
                repo_root=repo_root,
            )
        except Exception as exc:
            failures.append(
                {
                    "code": "market_data_snapshot_failed",
                    "classification": "market_data_alignment_gap",
                    "detail": str(exc),
                }
            )
        else:
            candles_db = Path(str(market_data_snapshot.get("candles_db") or candles_db)).resolve()
            frozen_funding_raw = str(market_data_snapshot.get("funding_db") or "").strip()
            if funding_db is not None and frozen_funding_raw:
                funding_db = Path(frozen_funding_raw).resolve()
            if strategy_config_resolution is None:
                strategy_config_resolution = {}
            strategy_config_resolution["market_data_snapshot"] = market_data_snapshot

    build_cmd = [
        "python3",
        str((repo_root / "tools" / "build_live_replay_bundle.py").resolve()),
        "--live-db",
        str(live_db),
        "--paper-db",
        str(paper_db),
        "--candles-db",
        str(candles_db),
        "--interval",
        interval,
        "--from-ts",
        str(from_ts),
        "--to-ts",
        str(to_ts),
        "--bundle-dir",
        str(bundle_dir),
    ]
    if strategy_config_path is not None:
        build_cmd.extend(["--strategy-config", str(strategy_config_path)])
    if funding_db is not None:
        build_cmd.extend(["--funding-db", str(funding_db)])

    build_rc: int | None = None
    live_baseline_trades = -1
    if not failures:
        build_rc = _run_to_log(build_cmd, cwd=repo_root, env=env, log_path=build_log)
    if build_rc is not None and build_rc != 0:
        failures.append(
            {
                "code": "bundle_build_failed",
                "classification": "state_initialisation_gap",
                "detail": f"build_live_replay_bundle.py exited with code {build_rc}",
            }
        )
    elif build_rc is not None and not manifest_path.exists():
        failures.append(
            {
                "code": "bundle_manifest_missing",
                "classification": "state_initialisation_gap",
                "detail": str(manifest_path),
            }
        )
    elif build_rc is not None:
        live_baseline_trades = _read_live_baseline_count(manifest_path)
        if live_baseline_trades < min_live_trades:
            failures.append(
                {
                    "code": "insufficient_live_baseline_trades",
                    "classification": "state_initialisation_gap",
                    "detail": f"live_baseline_trades={live_baseline_trades} below min_live_trades={min_live_trades}",
                }
            )

    harness_rc: int | None = None
    harness_report: dict[str, Any] | None = None
    gate_report: dict[str, Any] | None = None
    require_oms_strategy_provenance = True
    market_data_provenance: dict[str, Any] = {
        "manifest_candles_provenance": None,
        "alignment_gate_market_data_provenance": None,
    }

    if not failures:
        oms_strategy_stats = _oms_strategy_window_stats(
            live_db,
            from_ts=int(from_ts),
            to_ts=int(to_ts),
        )
        require_oms_strategy_provenance = bool(
            int((oms_strategy_stats or {}).get("rows_with_strategy_sha1") or 0) > 0
        )
        env["AQC_REQUIRE_OMS_STRATEGY_PROVENANCE"] = "1" if require_oms_strategy_provenance else "0"
        if strategy_config_resolution is None:
            strategy_config_resolution = {}
        strategy_config_resolution["require_oms_strategy_provenance"] = bool(require_oms_strategy_provenance)
        strategy_config_resolution["snapshot_strict_replace"] = True
        strategy_config_resolution["oms_strategy_window_stats"] = oms_strategy_stats

        harness_cmd = [
            "python3",
            str((repo_root / "tools" / "run_paper_deterministic_replay.py").resolve()),
            "--bundle-dir",
            str(bundle_dir),
            "--repo-root",
            str(repo_root),
            "--live-db",
            str(live_db),
            "--paper-db",
            str(paper_db),
            "--candles-db",
            str(candles_db),
            "--output",
            str(harness_report_path),
        ]
        if funding_db is not None:
            harness_cmd.extend(["--funding-db", str(funding_db)])
        if bool(args.strict_no_residuals):
            harness_cmd.append("--strict-no-residuals")

        harness_rc = _run_to_log(harness_cmd, cwd=repo_root, env=env, log_path=harness_log)
        if harness_rc != 0:
            failures.append(
                {
                    "code": "deterministic_replay_harness_failed",
                    "classification": "deterministic_logic_divergence",
                    "detail": f"run_paper_deterministic_replay.py exited with code {harness_rc}",
                }
            )

        if harness_report_path.exists():
            try:
                loaded = _read_json(harness_report_path)
            except Exception as exc:
                failures.append(
                    {
                        "code": "invalid_harness_report_json",
                        "classification": "deterministic_logic_divergence",
                        "detail": str(exc),
                    }
                )
            else:
                if isinstance(loaded, dict):
                    harness_report = loaded
                    if not bool(loaded.get("ok")):
                        failures.append(
                            {
                                "code": "deterministic_replay_harness_report_failed",
                                "classification": "deterministic_logic_divergence",
                                "detail": f"failed_step={loaded.get('failed_step')}",
                            }
                        )
                else:
                    failures.append(
                        {
                            "code": "invalid_harness_report",
                            "classification": "deterministic_logic_divergence",
                            "detail": "paper_deterministic_replay_run.json is not a JSON object",
                        }
                    )
        else:
            failures.append(
                {
                    "code": "missing_harness_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": str(harness_report_path),
                }
            )

        if gate_report_path.exists():
            try:
                loaded = _read_json(gate_report_path)
            except Exception as exc:
                failures.append(
                    {
                        "code": "invalid_alignment_gate_report_json",
                        "classification": "deterministic_logic_divergence",
                        "detail": str(exc),
                    }
                )
            else:
                if isinstance(loaded, dict):
                    gate_report = loaded
                    gate_market_data_provenance = loaded.get("market_data_provenance")
                    if isinstance(gate_market_data_provenance, dict):
                        market_data_provenance["alignment_gate_market_data_provenance"] = gate_market_data_provenance
                    if not bool(loaded.get("ok")):
                        failures.append(
                            {
                                "code": "alignment_gate_failed",
                                "classification": "deterministic_logic_divergence",
                                "detail": f"failures={len(loaded.get('failures') or [])}",
                            }
                        )
                else:
                    failures.append(
                        {
                            "code": "invalid_alignment_gate_report",
                            "classification": "deterministic_logic_divergence",
                            "detail": "alignment_gate_report.json is not a JSON object",
                        }
                    )
        else:
            failures.append(
                {
                    "code": "missing_alignment_gate_report",
                    "classification": "deterministic_logic_divergence",
                    "detail": str(gate_report_path),
                }
            )

    if manifest_path.exists():
        try:
            loaded_manifest = _read_json(manifest_path)
        except Exception:
            loaded_manifest = None
        if isinstance(loaded_manifest, dict):
            manifest_candles_provenance = loaded_manifest.get("candles_provenance")
            if isinstance(manifest_candles_provenance, dict):
                market_data_provenance["manifest_candles_provenance"] = manifest_candles_provenance

    ok = len(failures) == 0
    generated_at_ms = _now_ms()

    report: dict[str, Any] = {
        "schema_version": 2,
        "generated_at_ms": generated_at_ms,
        "ok": ok,
        "repo_root": str(repo_root),
        "window": {
            "interval": interval,
            "requested_from_ts": requested_from_ts,
            "requested_to_ts": requested_to_ts,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "coverage_from_ts": coverage_from_ts,
            "coverage_to_ts": coverage_to_ts,
            "window_minutes": int(args.window_minutes),
            "lag_minutes": int(args.lag_minutes),
            "auto_strategy_window_clamp": bool(args.auto_strategy_window_clamp),
            "strategy_window_stats": strategy_window_stats,
            "strategy_window_adjustment": strategy_window_adjustment,
        },
        "paths": {
            "bundle_root": str(bundle_root),
            "bundle_dir": str(bundle_dir),
            "strategy_config": str(strategy_config_path) if strategy_config_path is not None else None,
            "live_db": str(live_db),
            "paper_db": str(paper_db),
            "candles_db": str(candles_db),
            "funding_db": str(funding_db) if funding_db is not None else None,
            "manifest": str(manifest_path),
            "harness_report": str(harness_report_path),
            "alignment_gate_report": str(gate_report_path),
            "build_log": str(build_log),
            "harness_log": str(harness_log),
            "release_blocker_file": str(blocker_path),
        },
        "min_live_trades": min_live_trades,
        "live_baseline_trades": int(live_baseline_trades),
        "strict_no_residuals": bool(args.strict_no_residuals),
        "build_exit_code": None if build_rc is None else int(build_rc),
        "harness_exit_code": None if harness_rc is None else int(harness_rc),
        "market_data_provenance": market_data_provenance,
        "strategy_config_resolution": strategy_config_resolution,
        "failures": failures,
        "db_checks": {
            "live_has_trades_table": _db_has_table(live_db, "trades"),
            "paper_has_trades_table": _db_has_table(paper_db, "trades"),
            "live_decision_trace_window_stats": live_decision_trace_stats,
            "oms_strategy_window_stats": oms_strategy_stats,
        },
    }
    try:
        _write_json(report_path, report)
    except Exception as exc:
        ok = False
        failures.append(
            {
                "code": "write_report_failed",
                "classification": "state_initialisation_gap",
                "detail": str(exc),
            }
        )
        report["ok"] = False
        report["failures"] = failures

    previous_last_passed_ms: int | None = None
    if blocker_path.exists():
        try:
            previous = _read_json(blocker_path)
            if isinstance(previous, dict):
                prev_last_pass = previous.get("last_passed_at_ms")
                if isinstance(prev_last_pass, int):
                    previous_last_passed_ms = prev_last_pass
        except Exception:
            previous_last_passed_ms = None

    blocker_payload: dict[str, Any] = {
        "schema_version": 2,
        "generated_at_ms": generated_at_ms,
        "blocked": (not ok),
        "reason_codes": [str(f.get("code") or "") for f in failures],
        "report_path": str(report_path),
        "bundle_dir": str(bundle_dir),
        "window": {
            "interval": interval,
            "requested_from_ts": requested_from_ts,
            "requested_to_ts": requested_to_ts,
            "from_ts": from_ts,
            "to_ts": to_ts,
        },
        "market_data_provenance": market_data_provenance,
    }
    if ok:
        blocker_payload["last_passed_at_ms"] = generated_at_ms
    elif previous_last_passed_ms is not None:
        blocker_payload["last_passed_at_ms"] = previous_last_passed_ms

    try:
        _write_json(blocker_path, blocker_payload)
    except Exception:
        fallback_blocker_path = Path("/tmp/openclaw-ai-quant/replay_gate/release_blocker.json").resolve()
        fallback_blocker_path.parent.mkdir(parents=True, exist_ok=True)
        blocker_payload["write_fallback_from"] = str(blocker_path)
        _write_json(fallback_blocker_path, blocker_payload)
        blocker_path = fallback_blocker_path
    print(str(report_path))
    print(str(blocker_path))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - emergency fail-closed path
        fallback_blocker_raw = str(os.getenv("AI_QUANT_REPLAY_GATE_BLOCKER_FILE", "") or "").strip()
        if not fallback_blocker_raw:
            bundle_root_raw = str(os.getenv("AI_QUANT_REPLAY_GATE_BUNDLE_ROOT", "") or "").strip()
            if bundle_root_raw:
                fallback_blocker_raw = str((Path(bundle_root_raw).expanduser() / "release_blocker.json"))
            else:
                fallback_blocker_raw = "/tmp/openclaw-ai-quant/replay_gate/release_blocker.json"

        fallback_blocker_path = Path(fallback_blocker_raw).expanduser()
        if not fallback_blocker_path.is_absolute():
            fallback_blocker_path = (Path.cwd() / fallback_blocker_path).resolve()
        fallback_payload = {
            "schema_version": 1,
            "generated_at_ms": _now_ms(),
            "blocked": True,
            "reason_codes": ["scheduler_unhandled_exception"],
            "detail": str(exc),
        }
        try:
            _write_json(fallback_blocker_path, fallback_payload)
        except Exception:
            pass
        raise
