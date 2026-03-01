#!/usr/bin/env python3
"""Build a deterministic replay bundle for live-canonical replication.

The bundle contains:
- live baseline trades for a fixed window
- executable command scripts for snapshot export, paper seeding, replay, and audit
- a manifest with strict parameters and file hashes for traceability
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import sqlite3
from pathlib import Path
from typing import Any

try:
    from candles_provenance import build_candles_window_provenance
except ModuleNotFoundError:  # pragma: no cover - module execution path
    from tools.candles_provenance import build_candles_window_provenance

try:
    import yaml
except Exception:  # pragma: no cover - optional runtime dependency
    yaml = None

TRADE_ACTIONS = {"OPEN", "ADD", "REDUCE", "CLOSE", "FUNDING"}
_STRATEGY_SHA1_RE = re.compile(r"strategy_sha1=([0-9a-fA-F]{7,40})")
_STRATEGY_VERSION_RE = re.compile(r"version=([A-Za-z0-9._-]+)")


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_timestamp_ms(value: Any) -> int:
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        iv = int(value)
        if iv > 10_000_000_000:
            return iv
        return max(0, iv * 1000)

    raw = str(value).strip()
    if not raw:
        return 0

    if raw.isdigit():
        iv = int(raw)
        if iv > 10_000_000_000:
            return iv
        return iv * 1000

    try:
        ts = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(ts.timestamp() * 1000)
    except Exception:
        return 0


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _load_yaml_mapping(path: Path) -> dict[str, Any] | None:
    if yaml is None or not path.exists():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return raw if isinstance(raw, dict) else {}


_MACD_MODE_NUMERIC_MAP: dict[int, str] = {
    0: "accel",
    1: "sign",
    2: "none",
}
_MACD_MODE_ALLOWED: set[str] = {"accel", "sign", "none"}


def _normalise_macd_mode(value: Any) -> str | None:
    if isinstance(value, str):
        raw = str(value or "").strip().lower()
        if raw in _MACD_MODE_ALLOWED:
            return raw
        try:
            num_f = float(raw)
        except Exception:
            return None
    elif isinstance(value, bool):
        return None
    elif isinstance(value, (int, float)):
        num_f = float(value)
    else:
        return None

    if not math.isfinite(num_f):
        return None

    # Mirror sweep/deploy coercion semantics: truncate toward zero and clamp to u8.
    idx = int(num_f)
    if idx < 0:
        idx = 0
    elif idx > 255:
        idx = 255
    return _MACD_MODE_NUMERIC_MAP.get(idx, "none")


def _normalise_macd_modes_inplace(
    node: Any,
    *,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(node, dict):
        for key, value in list(node.items()):
            child_path = f"{path}.{key}" if path else str(key)
            if str(key) == "macd_hist_entry_mode":
                norm = _normalise_macd_mode(value)
                if norm is None:
                    errors.append(
                        f"{child_path}={value!r} (expected accel|sign|none or numeric 0/1/2)"
                    )
                else:
                    node[key] = norm
                continue
            _normalise_macd_modes_inplace(value, path=child_path, errors=errors)
        return

    if isinstance(node, list):
        for idx, item in enumerate(node):
            item_path = f"{path}[{idx}]"
            _normalise_macd_modes_inplace(item, path=item_path, errors=errors)


def _strategy_overrides_sha1(path: Path) -> str:
    """Return StrategyManager-compatible overrides hash (legacy name; SHA-256 digest)."""
    loaded = _load_yaml_mapping(path)
    if loaded is None:
        return ""
    return _hash_json_canonical(loaded)


def _strategy_overrides_sha1_legacy(path: Path) -> str:
    """Return historical StrategyManager hash used by older runtimes (SHA-1 digest)."""
    loaded = _load_yaml_mapping(path)
    if loaded is None:
        return ""
    return _hash_json_canonical_sha1(loaded)


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


def _load_config_engine_intervals(config_path: Path) -> tuple[str, str, str]:
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
    entry_iv = str(engine_cfg.get("entry_interval") or "").strip()
    exit_iv = str(engine_cfg.get("exit_interval") or "").strip()
    return interval, entry_iv, exit_iv


def _derive_interval_db(base_candles_db: Path, interval: str) -> Path | None:
    iv = str(interval or "").strip()
    if not iv:
        return None
    name = base_candles_db.name
    if not (name.startswith("candles_") and name.endswith(".db")):
        return None
    candidate = (base_candles_db.parent / f"candles_{iv}.db").resolve()
    if candidate.exists():
        return candidate
    return None


def _coerce_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _coerce_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _extract_alignment_assumptions(strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    global_cfg = strategy_cfg.get("global") if isinstance(strategy_cfg, dict) else {}
    if not isinstance(global_cfg, dict):
        global_cfg = {}
    global_trade = global_cfg.get("trade") if isinstance(global_cfg, dict) else {}
    if not isinstance(global_trade, dict):
        global_trade = {}

    use_bbo_global = _coerce_optional_bool(global_trade.get("use_bbo_for_fills"))
    slippage_bps_global = _coerce_optional_float(global_trade.get("slippage_bps"))

    symbols_cfg = strategy_cfg.get("symbols") if isinstance(strategy_cfg, dict) else {}
    if not isinstance(symbols_cfg, dict):
        symbols_cfg = {}

    use_bbo_overrides: dict[str, bool] = {}
    slippage_bps_overrides: dict[str, float] = {}
    for symbol, raw_cfg in symbols_cfg.items():
        symbol_key = str(symbol or "").strip().upper()
        if not symbol_key:
            continue
        sym_cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
        trade_cfg = sym_cfg.get("trade") if isinstance(sym_cfg, dict) else {}
        if not isinstance(trade_cfg, dict):
            continue

        if "use_bbo_for_fills" in trade_cfg:
            parsed = _coerce_optional_bool(trade_cfg.get("use_bbo_for_fills"))
            if parsed is not None:
                use_bbo_overrides[symbol_key] = bool(parsed)
        if "slippage_bps" in trade_cfg:
            parsed = _coerce_optional_float(trade_cfg.get("slippage_bps"))
            if parsed is not None:
                slippage_bps_overrides[symbol_key] = float(parsed)

    enabled_symbols = sorted([symbol for symbol, enabled in use_bbo_overrides.items() if enabled])
    disabled_symbols = sorted([symbol for symbol, enabled in use_bbo_overrides.items() if not enabled])
    bbo_enabled_any = bool(use_bbo_global) or bool(enabled_symbols)

    return {
        "bbo_fill_model": {
            "enabled_any": bool(bbo_enabled_any),
            "global_use_bbo_for_fills": use_bbo_global,
            "symbol_use_bbo_for_fills_overrides": use_bbo_overrides,
            "symbol_use_bbo_enabled": enabled_symbols,
            "symbol_use_bbo_disabled": disabled_symbols,
            "slippage_bps_global": slippage_bps_global,
            "symbol_slippage_bps_overrides": slippage_bps_overrides,
            "notes": [
                "Backtester replay currently uses candle-price execution without BBO microstructure fills.",
                "When bbo_fill_model.enabled_any=true, fill-price and realised PnL drift must be treated as a model residual unless explicitly simulated.",
            ],
        }
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a live replay bundle with deterministic artefacts.")
    parser.add_argument("--live-db", default="./trading_engine_live.db", help="Path to live SQLite DB")
    parser.add_argument("--paper-db", default="./trading_engine.db", help="Path to paper SQLite DB")
    parser.add_argument("--candles-db", required=True, help="Path to candles SQLite DB used for replay")
    parser.add_argument("--funding-db", default=None, help="Optional funding SQLite DB used for replay funding events")
    parser.add_argument("--interval", default="1h", help="Replay interval (for command template)")
    parser.add_argument(
        "--allow-interval-override",
        action="store_true",
        help=(
            "Allow replay interval override when it differs from locked strategy "
            "global.engine.interval."
        ),
    )
    parser.add_argument(
        "--strategy-config",
        help=(
            "Path to strategy YAML used for deterministic replay. "
            "Default: <live-db-dir>/config/strategy_overrides.yaml"
        ),
    )
    parser.add_argument("--from-ts", type=int, required=True, help="Replay start timestamp (ms, inclusive)")
    parser.add_argument("--to-ts", type=int, required=True, help="Replay end timestamp (ms, inclusive)")
    parser.add_argument(
        "--allow-partial-first-bar",
        action="store_true",
        help=(
            "Allow from-ts to start mid-bar for the replay interval. "
            "Default is fail-closed (requires bar-aligned from-ts for deterministic state sync)."
        ),
    )
    parser.add_argument(
        "--paper-filter-post-seed",
        action="store_true",
        help=(
            "Apply paper seed watermark lower-bound filtering in live-paper "
            "and event-order reconcile steps. Default is disabled."
        ),
    )
    parser.add_argument("--bundle-dir", required=True, help="Output bundle directory")
    parser.add_argument(
        "--snapshot-name",
        default="live_init_state_v2.json",
        help="Snapshot file name to generate inside the bundle",
    )
    return parser


def _load_live_baseline_trades(live_db: Path, *, from_ts: int, to_ts: int) -> list[dict[str, Any]]:
    conn = _connect_ro(live_db)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, symbol, action, type, price, size, pnl, balance, reason, confidence, fee_usd, leverage, margin_used, run_fingerprint "
            "FROM trades ORDER BY id ASC"
        ).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        action = str(row["action"] or "").strip().upper()
        if action not in TRADE_ACTIONS:
            continue

        ts_ms = _parse_timestamp_ms(row["timestamp"])
        if ts_ms < from_ts or ts_ms > to_ts:
            continue

        out.append(
            {
                "id": int(row["id"]),
                "timestamp": row["timestamp"],
                "timestamp_ms": ts_ms,
                "symbol": str(row["symbol"] or "").strip().upper(),
                "action": action,
                "type": str(row["type"] or "").strip().upper(),
                "price": float(row["price"] or 0.0),
                "size": float(row["size"] or 0.0),
                "pnl": float(row["pnl"] or 0.0),
                "balance": float(row["balance"] or 0.0),
                "reason": str(row["reason"] or ""),
                "confidence": str(row["confidence"] or "").strip().lower(),
                "fee_usd": float(row["fee_usd"] or 0.0),
                "leverage": float(row["leverage"] or 0.0),
                "margin_used": float(row["margin_used"] or 0.0),
                "run_fingerprint": str(row["run_fingerprint"] or "").strip(),
            }
        )

    return out


def _summarise_live_run_fingerprint_provenance(
    baseline_trades: list[dict[str, Any]],
    *,
    from_ts: int,
    to_ts: int,
) -> dict[str, Any]:
    per_fp: dict[str, dict[str, Any]] = {}
    sampled_rows = 0

    for row in baseline_trades:
        ts_ms = int(row.get("timestamp_ms") or 0)
        if ts_ms <= 0:
            continue
        sampled_rows += 1
        fp = str(row.get("run_fingerprint") or "").strip().lower() or "unknown"
        bucket = per_fp.get(fp)
        if bucket is None:
            bucket = {
                "run_fingerprint": fp,
                "sample_count": 0,
                "first_ts_ms": ts_ms,
                "last_ts_ms": ts_ms,
            }
            per_fp[fp] = bucket
        bucket["sample_count"] = int(bucket["sample_count"]) + 1
        bucket["first_ts_ms"] = min(int(bucket["first_ts_ms"]), ts_ms)
        bucket["last_ts_ms"] = max(int(bucket["last_ts_ms"]), ts_ms)

    timeline = [
        {
            "run_fingerprint": str(item["run_fingerprint"]),
            "sample_count": int(item["sample_count"]),
            "first_ts_ms": int(item["first_ts_ms"]),
            "last_ts_ms": int(item["last_ts_ms"]),
        }
        for _, item in sorted(per_fp.items(), key=lambda kv: int(kv[1]["first_ts_ms"]))
    ]
    return {
        "window_from_ts": int(from_ts),
        "window_to_ts": int(to_ts),
        "rows_sampled": int(sampled_rows),
        "run_fingerprint_distinct": len(timeline),
        "run_fingerprint_timeline": timeline,
    }


def _load_live_order_fail_events(live_db: Path, *, from_ts: int, to_ts: int) -> list[dict[str, Any]]:
    conn = _connect_ro(live_db)
    try:
        try:
            rows = conn.execute(
                "SELECT id, timestamp, symbol, event, data_json FROM audit_events ORDER BY id ASC"
            ).fetchall()
        except sqlite3.Error:
            return []
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        event = str(row["event"] or "").strip().upper()
        if not event.startswith("LIVE_ORDER_FAIL_"):
            continue

        ts_ms = _parse_timestamp_ms(row["timestamp"])
        if ts_ms < from_ts or ts_ms > to_ts:
            continue

        data_json = str(row["data_json"] or "").strip()
        data_obj: dict[str, Any] = {}
        if data_json:
            try:
                loaded = json.loads(data_json)
            except Exception:
                loaded = {}
            if isinstance(loaded, dict):
                data_obj = loaded

        out.append(
            {
                "id": int(row["id"] or 0),
                "timestamp": row["timestamp"],
                "timestamp_ms": ts_ms,
                "symbol": str(row["symbol"] or "").strip().upper(),
                "event": event,
                "data": data_obj,
            }
        )

    return out


def _load_runtime_strategy_provenance(
    live_db: Path,
    *,
    from_ts: int,
    to_ts: int,
) -> dict[str, Any]:
    conn = _connect_ro(live_db)
    try:
        rows = conn.execute(
            "SELECT ts_ms, message FROM runtime_logs WHERE ts_ms >= ? AND ts_ms <= ? ORDER BY ts_ms ASC, id ASC",
            (int(from_ts), int(to_ts)),
        ).fetchall()
    finally:
        conn.close()

    per_sha: dict[str, dict[str, Any]] = {}
    distinct_versions: set[str] = set()
    sampled_rows = 0

    for row in rows:
        ts_ms = int(row["ts_ms"] or 0)
        message = str(row["message"] or "")
        if ts_ms <= 0 or not message:
            continue

        sha_match = _STRATEGY_SHA1_RE.search(message)
        if sha_match is None:
            continue

        sha = str(sha_match.group(1) or "").strip().lower()
        if not sha:
            continue

        sampled_rows += 1

        version_match = _STRATEGY_VERSION_RE.search(message)
        version = str(version_match.group(1) or "").strip() if version_match is not None else ""

        bucket = per_sha.get(sha)
        if bucket is None:
            bucket = {
                "strategy_sha1": sha,
                "sample_count": 0,
                "first_ts_ms": ts_ms,
                "last_ts_ms": ts_ms,
                "versions": set(),
            }
            per_sha[sha] = bucket

        bucket["sample_count"] = int(bucket["sample_count"]) + 1
        bucket["first_ts_ms"] = min(int(bucket["first_ts_ms"]), ts_ms)
        bucket["last_ts_ms"] = max(int(bucket["last_ts_ms"]), ts_ms)
        if version:
            cast_versions = bucket["versions"]
            if isinstance(cast_versions, set):
                cast_versions.add(version)
            distinct_versions.add(version)

    strategy_rows: list[dict[str, Any]] = []
    for _, item in sorted(per_sha.items(), key=lambda kv: int(kv[1]["first_ts_ms"])):
        versions = item.get("versions")
        strategy_rows.append(
            {
                "strategy_sha1": str(item["strategy_sha1"]),
                "sample_count": int(item["sample_count"]),
                "first_ts_ms": int(item["first_ts_ms"]),
                "last_ts_ms": int(item["last_ts_ms"]),
                "versions": sorted(str(v) for v in versions) if isinstance(versions, set) else [],
            }
        )

    return {
        "window_from_ts": int(from_ts),
        "window_to_ts": int(to_ts),
        "runtime_rows_in_window": len(rows),
        "strategy_rows_sampled": int(sampled_rows),
        "strategy_sha1_distinct": len(strategy_rows),
        "strategy_version_distinct": len(distinct_versions),
        "strategy_sha1_timeline": strategy_rows,
    }


def _load_oms_strategy_provenance(
    live_db: Path,
    *,
    from_ts: int,
    to_ts: int,
) -> dict[str, Any]:
    conn = _connect_ro(live_db)
    try:
        rows = conn.execute(
            "SELECT COALESCE(decision_ts_ms, created_ts_ms) AS ts_ms, strategy_sha1, strategy_version "
            "FROM oms_intents "
            "WHERE COALESCE(decision_ts_ms, created_ts_ms) >= ? AND COALESCE(decision_ts_ms, created_ts_ms) <= ? "
            "ORDER BY ts_ms ASC, created_ts_ms ASC, intent_id ASC",
            (int(from_ts), int(to_ts)),
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    per_sha: dict[str, dict[str, Any]] = {}
    distinct_versions: set[str] = set()
    sampled_rows = 0
    rows_in_window = 0

    for row in rows:
        ts_ms = int(row["ts_ms"] or 0)
        sha = str(row["strategy_sha1"] or "").strip().lower()
        version = str(row["strategy_version"] or "").strip()
        if ts_ms <= 0:
            continue
        rows_in_window += 1
        if not sha:
            continue

        sampled_rows += 1
        bucket = per_sha.get(sha)
        if bucket is None:
            bucket = {
                "strategy_sha1": sha,
                "sample_count": 0,
                "first_ts_ms": ts_ms,
                "last_ts_ms": ts_ms,
                "versions": set(),
            }
            per_sha[sha] = bucket

        bucket["sample_count"] = int(bucket["sample_count"]) + 1
        bucket["first_ts_ms"] = min(int(bucket["first_ts_ms"]), ts_ms)
        bucket["last_ts_ms"] = max(int(bucket["last_ts_ms"]), ts_ms)
        if version:
            cast_versions = bucket["versions"]
            if isinstance(cast_versions, set):
                cast_versions.add(version)
            distinct_versions.add(version)

    strategy_rows: list[dict[str, Any]] = []
    for _, item in sorted(per_sha.items(), key=lambda kv: int(kv[1]["first_ts_ms"])):
        versions = item.get("versions")
        strategy_rows.append(
            {
                "strategy_sha1": str(item["strategy_sha1"]),
                "sample_count": int(item["sample_count"]),
                "first_ts_ms": int(item["first_ts_ms"]),
                "last_ts_ms": int(item["last_ts_ms"]),
                "versions": sorted(str(v) for v in versions) if isinstance(versions, set) else [],
            }
        )

    return {
        "window_from_ts": int(from_ts),
        "window_to_ts": int(to_ts),
        "oms_rows_in_window": int(rows_in_window),
        "oms_rows_sampled": int(sampled_rows),
        "strategy_sha1_distinct": len(strategy_rows),
        "strategy_version_distinct": len(distinct_versions),
        "strategy_sha1_timeline": strategy_rows,
    }


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    live_db = Path(args.live_db).expanduser().resolve()
    paper_db = Path(args.paper_db).expanduser().resolve()
    candles_db = Path(args.candles_db).expanduser().resolve()
    funding_db = Path(args.funding_db).expanduser().resolve() if args.funding_db else None
    bundle_dir = Path(args.bundle_dir).expanduser().resolve()
    snapshot_name = Path(args.snapshot_name).name

    if not live_db.exists():
        parser.error(f"live DB not found: {live_db}")
    if not paper_db.exists():
        parser.error(f"paper DB not found: {paper_db}")
    if not candles_db.exists():
        parser.error(f"candles DB not found: {candles_db}")
    if funding_db is not None and not funding_db.exists():
        parser.error(f"funding DB not found: {funding_db}")
    if args.from_ts > args.to_ts:
        parser.error("from-ts must be <= to-ts")

    strategy_config_source = (
        Path(args.strategy_config).expanduser().resolve()
        if args.strategy_config
        else (live_db.parent / "config" / "strategy_overrides.yaml").resolve()
    )
    if not strategy_config_source.exists():
        parser.error(
            f"strategy config not found: {strategy_config_source} "
            "(provide --strategy-config to pin the deterministic replay config)"
        )

    loaded_strategy_cfg = _load_yaml_mapping(strategy_config_source)
    if loaded_strategy_cfg is None:
        parser.error(
            f"strategy config YAML parse failed: {strategy_config_source}"
        )
    # Keep lock hashes from the original source object so runtime/OMS provenance
    # matching remains consistent with StrategyManager hashing semantics.
    locked_strategy_sha256 = _hash_json_canonical(loaded_strategy_cfg)
    locked_strategy_sha1_legacy = _hash_json_canonical_sha1(loaded_strategy_cfg)
    strategy_cfg_normalised: dict[str, Any] = json.loads(json.dumps(loaded_strategy_cfg))
    mode_errors: list[str] = []
    _normalise_macd_modes_inplace(
        strategy_cfg_normalised,
        path="",
        errors=mode_errors,
    )
    if mode_errors:
        parser.error(
            "invalid strategy config: macd_hist_entry_mode contains unsupported values: "
            + "; ".join(mode_errors)
        )

    bundle_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = bundle_dir / snapshot_name
    strategy_config_snapshot_path = bundle_dir / "strategy_overrides.locked.yaml"
    live_trades_path = bundle_dir / "live_baseline_trades.jsonl"
    live_order_fail_events_path = bundle_dir / "live_order_fail_events.jsonl"
    audit_report_path = bundle_dir / "state_alignment_report.json"
    replay_trades_csv = bundle_dir / "backtester_trades.csv"
    replay_report_path = bundle_dir / "backtester_replay_report.json"
    trade_reconcile_path = bundle_dir / "trade_reconcile_report.json"
    action_reconcile_path = bundle_dir / "action_reconcile_report.json"
    live_paper_action_reconcile_path = bundle_dir / "live_paper_action_reconcile_report.json"
    live_paper_decision_trace_reconcile_path = bundle_dir / "live_paper_decision_trace_reconcile_report.json"
    event_order_parity_path = bundle_dir / "event_order_parity_report.json"
    gpu_parity_report_path = bundle_dir / "gpu_smoke_parity_report.json"
    alignment_gate_path = bundle_dir / "alignment_gate_report.json"
    paper_harness_report_path = bundle_dir / "paper_deterministic_replay_run.json"
    paper_seed_watermark_path = bundle_dir / "paper_seed_watermark.json"
    paper_seed_apply_report_path = bundle_dir / "paper_seed_apply_report.json"
    manifest_path = bundle_dir / "replay_bundle_manifest.json"

    if yaml is None:
        shutil.copy2(strategy_config_source, strategy_config_snapshot_path)
    else:
        strategy_config_snapshot_path.write_text(
            yaml.safe_dump(strategy_cfg_normalised, sort_keys=False),
            encoding="utf-8",
        )
    snapshot_locked_sha256 = _strategy_overrides_sha1(strategy_config_snapshot_path)
    snapshot_locked_sha1_legacy = _strategy_overrides_sha1_legacy(strategy_config_snapshot_path)

    cfg_interval, cfg_entry_interval, cfg_exit_interval = _load_config_engine_intervals(
        strategy_config_snapshot_path
    )
    replay_entry_candles_db = _derive_interval_db(candles_db, cfg_entry_interval)
    replay_exit_candles_db = _derive_interval_db(candles_db, cfg_exit_interval)
    requested_interval = str(args.interval or "").strip()
    if (
        cfg_interval
        and requested_interval
        and cfg_interval != requested_interval
        and not bool(args.allow_interval_override)
    ):
        parser.error(
            f"replay interval '{requested_interval}' conflicts with locked strategy "
            f"engine.interval '{cfg_interval}'. "
            "Use --allow-interval-override only when this divergence is intentional."
        )
    if cfg_interval and not bool(args.allow_interval_override):
        base_interval = cfg_interval
    else:
        base_interval = requested_interval or cfg_interval or "1h"

    timestamp_bucket_ms = _interval_to_bucket_ms(base_interval)
    if timestamp_bucket_ms <= 1:
        parser.error(
            f"unsupported interval for deterministic timestamp bucketing: {base_interval!r} "
            "(expected forms like 1m, 3m, 5m, 15m, 30m, 1h)"
        )
    from_ts_aligned_to_interval = int(args.from_ts) % int(timestamp_bucket_ms) == 0
    if not from_ts_aligned_to_interval and not bool(args.allow_partial_first_bar):
        next_boundary = ((int(args.from_ts) // int(timestamp_bucket_ms)) + 1) * int(timestamp_bucket_ms)
        parser.error(
            f"from-ts {int(args.from_ts)} is not aligned to interval '{base_interval}' "
            f"(bucket_ms={int(timestamp_bucket_ms)}). "
            f"Use an aligned from-ts (for example {next_boundary}) or pass "
            "--allow-partial-first-bar if the partial first bar is intentional."
        )

    live_window_to_ts = int(args.to_ts) + int(timestamp_bucket_ms) - 1
    baseline_trades = _load_live_baseline_trades(
        live_db,
        from_ts=int(args.from_ts),
        to_ts=int(live_window_to_ts),
    )
    baseline_trade_exit_count = sum(1 for row in baseline_trades if row.get("action") in {"CLOSE", "REDUCE"})
    baseline_trade_funding_count = sum(1 for row in baseline_trades if row.get("action") == "FUNDING")
    live_run_fingerprint_provenance = _summarise_live_run_fingerprint_provenance(
        baseline_trades,
        from_ts=int(args.from_ts),
        to_ts=int(live_window_to_ts),
    )
    live_order_fail_events = _load_live_order_fail_events(
        live_db,
        from_ts=int(args.from_ts),
        to_ts=int(live_window_to_ts),
    )
    runtime_strategy_provenance = _load_runtime_strategy_provenance(
        live_db,
        from_ts=int(args.from_ts),
        to_ts=int(live_window_to_ts),
    )
    oms_strategy_provenance = _load_oms_strategy_provenance(
        live_db,
        from_ts=int(args.from_ts),
        to_ts=int(live_window_to_ts),
    )
    runtime_timeline = runtime_strategy_provenance.get("strategy_sha1_timeline")
    runtime_rows = runtime_timeline if isinstance(runtime_timeline, list) else []
    matching_runtime_prefixes = sorted(
        {
            str(row.get("strategy_sha1") or "").strip().lower()
            for row in runtime_rows
            if str(row.get("strategy_sha1") or "").strip()
            and (
                str(locked_strategy_sha256).startswith(str(row.get("strategy_sha1") or "").strip().lower())
                or str(locked_strategy_sha1_legacy).startswith(str(row.get("strategy_sha1") or "").strip().lower())
            )
        }
    )
    oms_timeline = oms_strategy_provenance.get("strategy_sha1_timeline")
    oms_rows = oms_timeline if isinstance(oms_timeline, list) else []
    matches_oms_sha1 = any(
        str(row.get("strategy_sha1") or "").strip().lower()
        in {
            str(locked_strategy_sha256).strip().lower(),
            str(locked_strategy_sha1_legacy).strip().lower(),
        }
        for row in oms_rows
    )
    alignment_assumptions = _extract_alignment_assumptions(strategy_cfg_normalised)

    with live_trades_path.open("w", encoding="utf-8") as fp:
        for row in baseline_trades:
            fp.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
    with live_order_fail_events_path.open("w", encoding="utf-8") as fp:
        for row in live_order_fail_events:
            fp.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")

    candles_provenance = build_candles_window_provenance(
        candles_db,
        interval=base_interval,
        from_ts=int(args.from_ts),
        to_ts=int(args.to_ts),
    )

    if cfg_entry_interval and cfg_entry_interval != base_interval and replay_entry_candles_db is None:
        parser.error(
            f"entry interval '{cfg_entry_interval}' requires candles DB beside {candles_db} "
            f"(expected {candles_db.parent / f'candles_{cfg_entry_interval}.db'})"
        )
    if cfg_exit_interval and cfg_exit_interval != base_interval and replay_exit_candles_db is None:
        parser.error(
            f"exit interval '{cfg_exit_interval}' requires candles DB beside {candles_db} "
            f"(expected {candles_db.parent / f'candles_{cfg_exit_interval}.db'})"
        )

    replay_sub_bar_args = ""
    if cfg_entry_interval:
        replay_sub_bar_args += f" --entry-interval {shlex.quote(cfg_entry_interval)}"
        if replay_entry_candles_db is not None:
            replay_sub_bar_args += f" --entry-candles-db {shlex.quote(str(replay_entry_candles_db))}"
    if cfg_exit_interval:
        replay_sub_bar_args += f" --exit-interval {shlex.quote(cfg_exit_interval)}"
        if replay_exit_candles_db is not None:
            replay_sub_bar_args += f" --exit-candles-db {shlex.quote(str(replay_exit_candles_db))}"

    seed_as_of_ts = max(1, int(args.from_ts) - 1)

    cmd_export_seed = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"LIVE_DB=\"${{LIVE_DB:-{shlex.quote(str(live_db))}}}\"\n"
        f"PAPER_DB=\"${{PAPER_DB:-{shlex.quote(str(paper_db))}}}\"\n"
        f"PAPER_WATERMARK_PATH=\"$BUNDLE_DIR/{paper_seed_watermark_path.name}\"\n"
        "python3 - \"$PAPER_DB\" \"$PAPER_WATERMARK_PATH\" <<'PY'\n"
        "import datetime as dt\n"
        "import json\n"
        "import sqlite3\n"
        "import sys\n"
        "\n"
        "paper_db = sys.argv[1]\n"
        "output_path = sys.argv[2]\n"
        "conn = sqlite3.connect(f\"file:{paper_db}?mode=ro\", uri=True, timeout=10)\n"
        "try:\n"
        "    row = conn.execute(\"SELECT COALESCE(MAX(id), 0) AS max_id FROM trades\").fetchone()\n"
        "finally:\n"
        "    conn.close()\n"
        "max_id = int((row[0] if row else 0) or 0)\n"
        "payload = {\n"
        "    \"schema_version\": 1,\n"
        "    \"generated_at_ms\": int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000),\n"
        "    \"paper_db\": paper_db,\n"
        "    \"pre_seed_max_trade_id\": max_id,\n"
        "}\n"
        "with open(output_path, \"w\", encoding=\"utf-8\") as fp:\n"
        "    fp.write(json.dumps(payload, indent=2, sort_keys=True))\n"
        "    fp.write(\"\\n\")\n"
        "print(output_path)\n"
        "PY\n"
        f"SNAPSHOT_PATH=\"$BUNDLE_DIR/{snapshot_name}\"\n"
        f"PAPER_SEED_APPLY_REPORT=\"$BUNDLE_DIR/{paper_seed_apply_report_path.name}\"\n"
        "STRICT_REPLACE_FLAG=\"\"\n"
        "if [ \"${AQC_SNAPSHOT_STRICT_REPLACE:-0}\" = \"1\" ]; then STRICT_REPLACE_FLAG=\"--strict-replace\"; fi\n"
        f"python3 \"$REPO_ROOT/tools/export_live_canonical_snapshot.py\" --source live --db-path \"$LIVE_DB\" --as-of-ts {seed_as_of_ts} --output \"$SNAPSHOT_PATH\"\n"
        "python3 \"$REPO_ROOT/tools/apply_canonical_snapshot_to_paper.py\" --snapshot \"$SNAPSHOT_PATH\" --target-db \"$PAPER_DB\" $STRICT_REPLACE_FLAG > \"$PAPER_SEED_APPLY_REPORT\""
    )

    if funding_db is not None:
        funding_env = f"FUNDING_DB=\"${{FUNDING_DB:-{shlex.quote(str(funding_db))}}}\"\n"
        funding_arg = " --funding-db \"$FUNDING_DB\""
    else:
        funding_env = ""
        funding_arg = ""

    cmd_replay = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"CANDLES_DB=\"${{CANDLES_DB:-{shlex.quote(str(candles_db))}}}\"\n"
        f"{funding_env}"
        f"SNAPSHOT_PATH=\"$BUNDLE_DIR/{snapshot_name}\"\n"
        "cd \"$REPO_ROOT/backtester\"\n"
        "BACKTESTER_REPLAY_BIN='./target/release/mei-backtester replay'\n"
        "BACKTESTER_REPLAY_CARGO='cargo run -q --release --package bt-cli -- replay'\n"
        "BACKTESTER_REPLAY_CMD=\"$BACKTESTER_REPLAY_CARGO\"\n"
        "EXPECTED_GIT_SHA=\"$(git rev-parse --short=7 HEAD 2>/dev/null || true)\"\n"
        "if [ \"${AQC_REPLAY_PREFER_RELEASE_BIN:-1}\" = \"1\" ] && [ -x \"./target/release/mei-backtester\" ]; then\n"
        "  BIN_GIT_SHA=\"$(./target/release/mei-backtester --version 2>/dev/null | sed -n 's/.*git:\\([0-9a-fA-F]\\{7,40\\}\\).*/\\1/p' | head -n1 | tr 'A-F' 'a-f')\"\n"
        "  EXPECTED_GIT_SHA=\"$(printf '%s' \"$EXPECTED_GIT_SHA\" | tr 'A-F' 'a-f')\"\n"
        "  if [ -n \"$EXPECTED_GIT_SHA\" ] && [ -n \"$BIN_GIT_SHA\" ] && [ \"${BIN_GIT_SHA#$EXPECTED_GIT_SHA}\" != \"$BIN_GIT_SHA\" ]; then\n"
        "    BACKTESTER_REPLAY_CMD=\"$BACKTESTER_REPLAY_BIN\"\n"
        "  else\n"
        "    echo \"[replay] release binary git sha mismatch (bin=${BIN_GIT_SHA:-unknown}, expected=${EXPECTED_GIT_SHA:-unknown}); using cargo\" >&2\n"
        "  fi\n"
        "fi\n"
        f"$BACKTESTER_REPLAY_CMD --live --config \"$BUNDLE_DIR/{strategy_config_snapshot_path.name}\" --candles-db \"$CANDLES_DB\" "
        f"--interval {shlex.quote(base_interval)} --from-ts {int(args.from_ts)} --to-ts {int(args.to_ts)} "
        f"--init-state \"$SNAPSHOT_PATH\" --export-trades \"$BUNDLE_DIR/{replay_trades_csv.name}\" "
        f"--output \"$BUNDLE_DIR/{replay_report_path.name}\" --trades{funding_arg}{replay_sub_bar_args}\n"
        f"if ! python3 - \"$BUNDLE_DIR/{replay_report_path.name}\" <<'PY'\n"
        "import json\n"
        "import sys\n"
        "\n"
        "path = sys.argv[1]\n"
        "with open(path, \"r\", encoding=\"utf-8\") as fp:\n"
        "    obj = json.load(fp)\n"
        "fingerprint = str(obj.get(\"config_fingerprint\") or \"\").strip().lower()\n"
        "ok = len(fingerprint) == 64 and all(ch in \"0123456789abcdef\" for ch in fingerprint)\n"
        "raise SystemExit(0 if ok else 1)\n"
        "PY\n"
        "then\n"
        "  if [ \"$BACKTESTER_REPLAY_CMD\" = \"$BACKTESTER_REPLAY_BIN\" ]; then\n"
        "    echo \"[replay] release binary missing config_fingerprint; retry with cargo\" >&2\n"
        f"    $BACKTESTER_REPLAY_CARGO --live --config \"$BUNDLE_DIR/{strategy_config_snapshot_path.name}\" --candles-db \"$CANDLES_DB\" "
        f"--interval {shlex.quote(base_interval)} --from-ts {int(args.from_ts)} --to-ts {int(args.to_ts)} "
        f"--init-state \"$SNAPSHOT_PATH\" --export-trades \"$BUNDLE_DIR/{replay_trades_csv.name}\" "
        f"--output \"$BUNDLE_DIR/{replay_report_path.name}\" --trades{funding_arg}{replay_sub_bar_args}\n"
        f"    python3 - \"$BUNDLE_DIR/{replay_report_path.name}\" <<'PY'\n"
        "import json\n"
        "import sys\n"
        "\n"
        "path = sys.argv[1]\n"
        "with open(path, \"r\", encoding=\"utf-8\") as fp:\n"
        "    obj = json.load(fp)\n"
        "fingerprint = str(obj.get(\"config_fingerprint\") or \"\").strip().lower()\n"
        "ok = len(fingerprint) == 64 and all(ch in \"0123456789abcdef\" for ch in fingerprint)\n"
        "raise SystemExit(0 if ok else 1)\n"
        "PY\n"
        "  else\n"
        "    echo \"[replay] missing config_fingerprint in replay report\" >&2\n"
        "    exit 1\n"
        "  fi\n"
        "fi"
    )

    cmd_audit = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"LIVE_DB=\"${{LIVE_DB:-{shlex.quote(str(live_db))}}}\"\n"
        f"PAPER_DB=\"${{PAPER_DB:-{shlex.quote(str(paper_db))}}}\"\n"
        f"SNAPSHOT_PATH=\"$BUNDLE_DIR/{snapshot_name}\"\n"
        "python3 \"$REPO_ROOT/tools/audit_state_sync_alignment.py\" --live-db \"$LIVE_DB\" "
        f"--paper-db \"$PAPER_DB\" --snapshot \"$SNAPSHOT_PATH\" --as-of-ts {seed_as_of_ts} "
        f"--output \"$BUNDLE_DIR/{audit_report_path.name}\""
    )

    cmd_trade_reconcile = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        "python3 \"$REPO_ROOT/tools/audit_live_backtester_trade_reconcile.py\" "
        f"--live-baseline \"$BUNDLE_DIR/{live_trades_path.name}\" "
        f"--backtester-trades \"$BUNDLE_DIR/{replay_trades_csv.name}\" "
        f"--bundle-manifest \"$BUNDLE_DIR/{manifest_path.name}\" "
        f"--timestamp-bucket-ms {int(timestamp_bucket_ms)} "
        "--timestamp-bucket-anchor ceil "
        f"--output \"$BUNDLE_DIR/{trade_reconcile_path.name}\""
    )

    cmd_action_reconcile = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        "python3 \"$REPO_ROOT/tools/audit_live_backtester_action_reconcile.py\" "
        f"--live-baseline \"$BUNDLE_DIR/{live_trades_path.name}\" "
        f"--backtester-replay-report \"$BUNDLE_DIR/{replay_report_path.name}\" "
        f"--live-order-fail-events \"$BUNDLE_DIR/{live_order_fail_events_path.name}\" "
        f"--timestamp-bucket-ms {int(timestamp_bucket_ms)} "
        "--timestamp-bucket-anchor floor "
        f"--output \"$BUNDLE_DIR/{action_reconcile_path.name}\""
    )

    paper_seed_filter_arg = (
        f"--paper-seed-watermark \"$BUNDLE_DIR/{paper_seed_watermark_path.name}\" "
        if args.paper_filter_post_seed
        else ""
    )

    cmd_live_paper_action_reconcile = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"LIVE_DB=\"${{LIVE_DB:-{shlex.quote(str(live_db))}}}\"\n"
        f"PAPER_DB=\"${{PAPER_DB:-{shlex.quote(str(paper_db))}}}\"\n"
        "python3 \"$REPO_ROOT/tools/audit_live_paper_action_reconcile.py\" "
        "--live-db \"$LIVE_DB\" "
        "--paper-db \"$PAPER_DB\" "
        f"{paper_seed_filter_arg}"
        f"--from-ts {int(args.from_ts)} --to-ts {int(args.to_ts)} "
        f"--timestamp-bucket-ms {int(timestamp_bucket_ms)} "
        f"--output \"$BUNDLE_DIR/{live_paper_action_reconcile_path.name}\""
    )

    cmd_live_paper_decision_trace_reconcile = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"LIVE_DB=\"${{LIVE_DB:-{shlex.quote(str(live_db))}}}\"\n"
        f"PAPER_DB=\"${{PAPER_DB:-{shlex.quote(str(paper_db))}}}\"\n"
        "python3 \"$REPO_ROOT/tools/audit_live_paper_decision_trace.py\" "
        "--live-db \"$LIVE_DB\" "
        "--paper-db \"$PAPER_DB\" "
        f"--from-ts {int(args.from_ts)} --to-ts {int(args.to_ts)} "
        f"--timestamp-bucket-ms {int(timestamp_bucket_ms)} "
        f"--output \"$BUNDLE_DIR/{live_paper_decision_trace_reconcile_path.name}\""
    )

    cmd_event_order_parity = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"PAPER_DB=\"${{PAPER_DB:-{shlex.quote(str(paper_db))}}}\"\n"
        "python3 \"$REPO_ROOT/tools/audit_live_baseline_paper_order_parity.py\" "
        f"--live-baseline \"$BUNDLE_DIR/{live_trades_path.name}\" "
        "--paper-db \"$PAPER_DB\" "
        f"{paper_seed_filter_arg}"
        f"--from-ts {int(args.from_ts)} --to-ts {int(args.to_ts)} "
        f"--timestamp-bucket-ms {int(timestamp_bucket_ms)} "
        "--fail-on-mismatch "
        f"--output \"$BUNDLE_DIR/{event_order_parity_path.name}\""
    )

    cmd_gpu_parity = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"CANDLES_DB=\"${{CANDLES_DB:-{shlex.quote(str(candles_db))}}}\"\n"
        f"export AQC_PARITY_CONFIG_PATH=\"${{AQC_PARITY_CONFIG_PATH:-$BUNDLE_DIR/{strategy_config_snapshot_path.name}}}\"\n"
        f"{funding_env}"
        "python3 \"$REPO_ROOT/tools/run_bundle_gpu_parity.py\" "
        "--bundle-dir \"$BUNDLE_DIR\" "
        "--repo-root \"$REPO_ROOT\" "
        "--candles-db \"$CANDLES_DB\" "
        f"{funding_arg} "
        f"--output \"$BUNDLE_DIR/{gpu_parity_report_path.name}\""
    )

    cmd_alignment_gate = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        f"CANDLES_DB=\"${{CANDLES_DB:-{shlex.quote(str(candles_db))}}}\"\n"
        "python3 \"$REPO_ROOT/tools/assert_replay_bundle_alignment.py\" "
        "--bundle-dir \"$BUNDLE_DIR\" "
        "--candles-db \"$CANDLES_DB\" "
        f"--live-paper-report \"$BUNDLE_DIR/{live_paper_action_reconcile_path.name}\" "
        "--require-live-paper "
        f"--live-paper-decision-trace-report \"$BUNDLE_DIR/{live_paper_decision_trace_reconcile_path.name}\" "
        "--require-live-paper-decision-trace "
        f"--event-order-report \"$BUNDLE_DIR/{event_order_parity_path.name}\" "
        "--require-event-order "
        f"--gpu-parity-report \"$BUNDLE_DIR/{gpu_parity_report_path.name}\" "
        "--require-gpu-parity "
        "--require-runtime-strategy-provenance "
        "--max-strategy-sha1-distinct 1 "
        "--require-oms-strategy-provenance "
        "--max-oms-strategy-sha1-distinct 1 "
        "--require-live-run-fingerprint-provenance "
        "--max-live-run-fingerprint-distinct 1 "
        "--require-locked-strategy-match "
        f"--output \"$BUNDLE_DIR/{alignment_gate_path.name}\""
    )

    cmd_paper_harness = (
        "set -euo pipefail\n"
        "BUNDLE_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"\n"
        "STRICT_FLAG=\"\"\n"
        "if [ \"${STRICT_NO_RESIDUALS:-0}\" = \"1\" ]; then STRICT_FLAG=\"--strict-no-residuals\"; fi\n"
        "python3 \"$REPO_ROOT/tools/run_paper_deterministic_replay.py\" "
        "--bundle-dir \"$BUNDLE_DIR\" "
        "--repo-root \"$REPO_ROOT\" "
        "$STRICT_FLAG "
        f"--output \"$BUNDLE_DIR/{paper_harness_report_path.name}\""
    )

    (bundle_dir / "run_01_export_and_seed.sh").write_text(cmd_export_seed + "\n", encoding="utf-8")
    (bundle_dir / "run_02_replay.sh").write_text(cmd_replay + "\n", encoding="utf-8")
    (bundle_dir / "run_03_audit.sh").write_text(cmd_audit + "\n", encoding="utf-8")
    (bundle_dir / "run_04_trade_reconcile.sh").write_text(cmd_trade_reconcile + "\n", encoding="utf-8")
    (bundle_dir / "run_05_action_reconcile.sh").write_text(cmd_action_reconcile + "\n", encoding="utf-8")
    (bundle_dir / "run_06_live_paper_action_reconcile.sh").write_text(cmd_live_paper_action_reconcile + "\n", encoding="utf-8")
    (bundle_dir / "run_07_live_paper_decision_trace_reconcile.sh").write_text(
        cmd_live_paper_decision_trace_reconcile + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "run_07b_event_order_parity.sh").write_text(cmd_event_order_parity + "\n", encoding="utf-8")
    (bundle_dir / "run_07c_gpu_parity.sh").write_text(cmd_gpu_parity + "\n", encoding="utf-8")
    (bundle_dir / "run_08_assert_alignment.sh").write_text(cmd_alignment_gate + "\n", encoding="utf-8")
    (bundle_dir / "run_09_paper_deterministic_replay.sh").write_text(cmd_paper_harness + "\n", encoding="utf-8")

    for script_name in (
        "run_01_export_and_seed.sh",
        "run_02_replay.sh",
        "run_03_audit.sh",
        "run_04_trade_reconcile.sh",
        "run_05_action_reconcile.sh",
        "run_06_live_paper_action_reconcile.sh",
        "run_07_live_paper_decision_trace_reconcile.sh",
        "run_07b_event_order_parity.sh",
        "run_07c_gpu_parity.sh",
        "run_08_assert_alignment.sh",
        "run_09_paper_deterministic_replay.sh",
    ):
        script_path = bundle_dir / script_name
        script_path.chmod(0o755)

    snapshot_strict_replace = str(os.getenv("AQC_SNAPSHOT_STRICT_REPLACE", "0") or "") == "1"

    manifest = {
        "schema_version": 1,
        "generated_at_ms": int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000),
        "bundle_dir": str(bundle_dir),
        "inputs": {
            "live_db": str(live_db),
            "paper_db": str(paper_db),
            "candles_db": str(candles_db),
            "funding_db": str(funding_db) if funding_db is not None else None,
            "strategy_config_source": str(strategy_config_source),
            "interval": base_interval,
            "interval_requested": requested_interval,
            "interval_from_locked_strategy": cfg_interval or None,
            "allow_interval_override": bool(args.allow_interval_override),
            "allow_partial_first_bar": bool(args.allow_partial_first_bar),
            "paper_filter_post_seed": bool(args.paper_filter_post_seed),
            "from_ts_aligned_to_interval": bool(from_ts_aligned_to_interval),
            "timestamp_bucket_ms": int(timestamp_bucket_ms),
            "entry_interval": cfg_entry_interval or None,
            "exit_interval": cfg_exit_interval or None,
            "entry_candles_db": str(replay_entry_candles_db) if replay_entry_candles_db is not None else None,
            "exit_candles_db": str(replay_exit_candles_db) if replay_exit_candles_db is not None else None,
            "from_ts": int(args.from_ts),
            "to_ts": int(args.to_ts),
            "live_window_to_ts": int(live_window_to_ts),
            "snapshot_strict_replace": bool(snapshot_strict_replace),
        },
        "input_hashes": {
            "candles_db_sha256": _hash_file(candles_db),
            "funding_db_sha256": _hash_file(funding_db) if funding_db is not None else None,
            "strategy_config_source_sha256": _hash_file(strategy_config_source),
            "strategy_config_snapshot_sha256": _hash_file(strategy_config_snapshot_path),
        },
        "candles_provenance": candles_provenance,
        "runtime_strategy_provenance": runtime_strategy_provenance,
        "oms_strategy_provenance": oms_strategy_provenance,
        "live_run_fingerprint_provenance": live_run_fingerprint_provenance,
        "locked_strategy_provenance": {
            "strategy_overrides_source_sha1": str(locked_strategy_sha256),
            "strategy_overrides_source_sha1_prefix8": str(locked_strategy_sha256)[:8],
            "strategy_overrides_source_sha1_legacy": str(locked_strategy_sha1_legacy),
            "strategy_overrides_source_sha1_legacy_prefix8": str(locked_strategy_sha1_legacy)[:8],
            "strategy_overrides_sha1": str(locked_strategy_sha256),
            "strategy_overrides_sha1_prefix8": str(locked_strategy_sha256)[:8],
            "strategy_overrides_sha1_legacy": str(locked_strategy_sha1_legacy),
            "strategy_overrides_sha1_legacy_prefix8": str(locked_strategy_sha1_legacy)[:8],
            "strategy_overrides_snapshot_sha1": str(snapshot_locked_sha256),
            "strategy_overrides_snapshot_sha1_prefix8": str(snapshot_locked_sha256)[:8],
            "strategy_overrides_snapshot_sha1_legacy": str(snapshot_locked_sha1_legacy),
            "strategy_overrides_snapshot_sha1_legacy_prefix8": str(snapshot_locked_sha1_legacy)[:8],
            "matching_runtime_sha1_prefixes": matching_runtime_prefixes,
            "matches_runtime_strategy_prefix": bool(matching_runtime_prefixes),
            "matches_oms_strategy_sha1": bool(matches_oms_sha1),
        },
        "alignment_assumptions": alignment_assumptions,
        "artefacts": {
            "snapshot_file": snapshot_path.name,
            "strategy_config_snapshot_file": strategy_config_snapshot_path.name,
            "live_baseline_trades": live_trades_path.name,
            "live_baseline_trades_sha256": _hash_file(live_trades_path),
            "live_order_fail_events": live_order_fail_events_path.name,
            "live_order_fail_events_sha256": _hash_file(live_order_fail_events_path),
            "audit_report_file": audit_report_path.name,
            "backtester_trades_csv": replay_trades_csv.name,
            "backtester_replay_report_json": replay_report_path.name,
            "trade_reconcile_report_file": trade_reconcile_path.name,
            "action_reconcile_report_file": action_reconcile_path.name,
            "live_paper_action_reconcile_report_file": live_paper_action_reconcile_path.name,
            "live_paper_decision_trace_reconcile_report_file": live_paper_decision_trace_reconcile_path.name,
            "event_order_parity_report_file": event_order_parity_path.name,
            "gpu_parity_report_file": gpu_parity_report_path.name,
            "alignment_gate_report_file": alignment_gate_path.name,
            "paper_deterministic_replay_run_report_file": paper_harness_report_path.name,
            "paper_seed_watermark_file": paper_seed_watermark_path.name,
            "paper_seed_apply_report_file": paper_seed_apply_report_path.name,
            "paper_seed_apply_report_sha256": _hash_file(paper_seed_apply_report_path)
            if paper_seed_apply_report_path.exists()
            else None,
        },
        "counts": {
            "live_baseline_trades": len(baseline_trades),
            "live_baseline_simulatable_exits": baseline_trade_exit_count,
            "live_baseline_funding_events": baseline_trade_funding_count,
            "live_order_fail_events": len(live_order_fail_events),
        },
        "commands": {
            "export_and_seed": cmd_export_seed,
            "replay": cmd_replay,
            "audit": cmd_audit,
            "trade_reconcile": cmd_trade_reconcile,
            "action_reconcile": cmd_action_reconcile,
            "live_paper_action_reconcile": cmd_live_paper_action_reconcile,
            "live_paper_decision_trace_reconcile": cmd_live_paper_decision_trace_reconcile,
            "event_order_parity": cmd_event_order_parity,
            "gpu_parity": cmd_gpu_parity,
            "alignment_gate": cmd_alignment_gate,
            "paper_deterministic_replay_harness": cmd_paper_harness,
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(manifest_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
