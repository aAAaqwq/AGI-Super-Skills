#!/usr/bin/env python3
"""Deploy optimised sweep results to paper/live config with safety gates.

Usage:
    python deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 --dry-run
    python deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 --yaml-path ./paper.yaml --no-live --yes
    python deploy_sweep.py --sweep-results sweep_results.jsonl --rank 1 --allow-live --close-live --restart --yes
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from tools.config_id import config_id_from_yaml_text
except ImportError:  # pragma: no cover
    from config_id import config_id_from_yaml_text  # type: ignore[no-redef]

try:
    from tools.deploy_validate import validate_yaml_text
except ImportError:  # pragma: no cover
    from deploy_validate import validate_yaml_text  # type: ignore[no-redef]

try:
    from tools.replay_gate_blocker import ReplayGateViolation, assert_replay_gate_green
except ImportError:  # pragma: no cover
    from replay_gate_blocker import ReplayGateViolation, assert_replay_gate_green  # type: ignore[no-redef]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
YAML_PATH = os.path.join(PROJECT_DIR, "config", "strategy_overrides.yaml")
CHANGELOG_PATH = os.path.join(PROJECT_DIR, "strategy_changelog.json")
DEFAULT_ARTIFACTS_DIR = os.path.join(PROJECT_DIR, "artifacts")
PAPER_DB = os.path.join(PROJECT_DIR, "trading_engine.db")
LIVE_DB = os.path.join(PROJECT_DIR, "trading_engine_live.db")
DEFAULT_SECRETS_PATH = os.path.expanduser("~/.config/openclaw/ai-quant-secrets.json")
SECRETS_PATH = os.path.expanduser(
    str(os.getenv("AI_QUANT_SECRETS_PATH") or DEFAULT_SECRETS_PATH)
)

# Keep deploy-time override coercion aligned with sweep output semantics.
INT_FIELDS = {
    "max_open_positions", "max_adds_per_symbol", "add_cooldown_minutes",
    "reentry_cooldown_minutes", "reentry_cooldown_min_mins", "reentry_cooldown_max_mins",
    "max_entry_orders_per_loop", "adx_window", "ema_fast_window", "ema_slow_window",
    "bb_window", "ema_macro_window", "atr_window", "rsi_window", "bb_width_avg_window",
    "vol_sma_window", "vol_trend_window", "stoch_rsi_window", "stoch_rsi_smooth1",
    "stoch_rsi_smooth2", "slow_drift_slope_window", "min_signals",
}
BOOL_FIELDS = {
    "enable_dynamic_sizing", "enable_pyramiding",
    "enable_partial_tp", "enable_vol_buffered_trailing", "enable_reef_filter",
    "enable_ssf_filter", "enable_breakeven_stop", "enable_rsi_overextension_exit",
    "reverse_entry_signal", "block_exits_on_extreme_dev", "bump_to_min_notional",
    "use_bbo_for_fills", "tsme_require_adx_slope_negative",
    "enable_extension_filter", "enable_ranging_filter", "enable_anomaly_filter",
    "require_btc_alignment", "require_volume_confirmation", "require_macro_alignment",
    "require_adx_rising", "vol_confirm_include_prev", "use_stoch_rsi_filter",
    "enable_regime_filter", "enable_auto_reverse",
    "ave_enabled", "enable_pullback_entries", "pullback_require_macd_sign",
    "enable_slow_drift_entries", "slow_drift_require_macd_sign",
    "signal_on_candle_close",
}
CONFIDENCE_FIELDS = {
    "entry_min_confidence", "add_min_confidence", "pullback_confidence",
}
CONFIDENCE_MAP = {0: "low", 1: "medium", 2: "high"}
CATEGORICAL_FIELDS = {
    "macd_hist_entry_mode": {0: "accel", 1: "sign", 2: "none"},
}
STRING_FIELDS = {"interval", "entry_interval", "exit_interval"}


def _trunc_towards_zero(x: float) -> int:
    return int(float(x))


def _as_u8_from_float(raw_value: Any, default: int = 0) -> int:
    try:
        x = float(raw_value)
    except Exception:
        return int(default)
    if not math.isfinite(x):
        return int(default)
    i = _trunc_towards_zero(x)
    if i < 0:
        return 0
    if i > 255:
        return 255
    return i


def _coerce_override_value(param_name: str, raw_value: Any) -> Any:
    if param_name in CATEGORICAL_FIELDS:
        mapping = CATEGORICAL_FIELDS[param_name]
        if isinstance(raw_value, str):
            s = raw_value.strip().lower()
            if s in mapping.values():
                return s
        idx = _as_u8_from_float(raw_value, default=0)
        if idx in mapping:
            return mapping[idx]
        return mapping[max(mapping.keys())]

    if param_name in STRING_FIELDS:
        return str(raw_value)

    if param_name in CONFIDENCE_FIELDS:
        if isinstance(raw_value, str):
            s = str(raw_value).strip().lower()
            if s in {"low", "medium", "high"}:
                return s
        idx = _as_u8_from_float(raw_value, default=0)
        return CONFIDENCE_MAP.get(idx, "low")

    if param_name in BOOL_FIELDS:
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            s = str(raw_value).strip().lower()
            if s in {"1", "true", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "no", "n", "off"}:
                return False
        try:
            return float(raw_value) != 0.0
        except Exception:
            return bool(raw_value)

    if param_name in INT_FIELDS:
        try:
            x = float(raw_value)
            if not math.isfinite(x):
                return 0
            return max(0, _trunc_towards_zero(x))
        except Exception:
            return int(raw_value)

    try:
        return float(raw_value)
    except Exception:
        return raw_value


def _is_live_target_yaml(path: str) -> bool:
    return Path(path).expanduser().resolve() == Path(YAML_PATH).expanduser().resolve()


def _no_live_guard_error(*, no_live: bool, yaml_path: str, close_live: bool, restart: bool) -> str | None:
    if not no_live:
        return None
    if _is_live_target_yaml(yaml_path):
        return "Refusing live YAML deployment while --no-live guard is enabled."
    if close_live:
        return "Refusing --close-live while --no-live guard is enabled."
    if restart:
        return "Refusing --restart while --no-live guard is enabled (restarts live service)."
    return None


# ---------------------------------------------------------------------------
# Parse sweep results
# ---------------------------------------------------------------------------

def load_sweep_results(path: str) -> list[dict]:
    """Load JSONL sweep results, sort by total_pnl descending."""
    results = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            results.append(json.loads(line))
    results.sort(key=lambda r: r.get("total_pnl", 0), reverse=True)
    return results


# ---------------------------------------------------------------------------
# YAML operations
# ---------------------------------------------------------------------------

def _load_yaml(path: str):
    """Load YAML safely. Returns a dict."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping at root of YAML: {path}")
    return data


def _backup_yaml(path: str):
    ts = int(time.time())
    backup = f"{path}.bak.{ts}"
    import shutil
    shutil.copy2(path, backup)
    print(f"[deploy] Backed up YAML → {backup}", file=sys.stderr)
    return backup


def _atomic_write_text(path: str, text: str) -> None:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp.{int(time.time() * 1000)}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(target))
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_deploy_event(
    *,
    artifacts_dir: str,
    yaml_path: str,
    prev_text: str,
    next_text: str,
    selected: dict[str, Any],
    rank: int,
    no_live: bool,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    next_hash = _sha256_text(next_text)
    out_dir = Path(artifacts_dir).expanduser().resolve() / "deployments" / "sweep" / f"{ts}_{next_hash[:12]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "mode": "sweep_deploy",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "yaml_path": str(Path(yaml_path).expanduser().resolve()),
        "no_live_guard": bool(no_live),
        "selection": {
            "rank": int(rank),
            "config_id": config_id_from_yaml_text(next_text),
            "total_pnl": selected.get("total_pnl"),
            "total_trades": selected.get("total_trades"),
        },
        "hashes": {
            "prev_yaml_sha256": _sha256_text(prev_text) if prev_text else "",
            "next_yaml_sha256": next_hash,
        },
    }
    (out_dir / "deploy_event.json").write_text(
        json.dumps(event, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "next_config.yaml").write_text(next_text, encoding="utf-8")
    if prev_text:
        (out_dir / "prev_config.yaml").write_text(prev_text, encoding="utf-8")
    return str(out_dir)


def _set_nested(data: dict, dotpath: str, value):
    """Set a value in a nested dict using dot notation.

    e.g. 'trade.sl_atr_mult' → data['global']['trade']['sl_atr_mult']
    """
    # Prepend 'global.' if not already present (sweep overrides use short paths)
    if not dotpath.startswith("global."):
        dotpath = "global." + dotpath

    keys = dotpath.split(".")
    d = data
    for k in keys[:-1]:
        if k not in d or d[k] is None:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def _get_nested(data: dict, dotpath: str, default=None):
    """Get a value from nested dict using dot notation."""
    if not dotpath.startswith("global."):
        dotpath = "global." + dotpath
    keys = dotpath.split(".")
    d = data
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


# ---------------------------------------------------------------------------
# Show diff
# ---------------------------------------------------------------------------

def show_diff(current_yaml: dict, overrides: dict[str, Any]):
    """Display what would change."""
    print("\n--- Config Changes ---\n", file=sys.stderr)
    for path, new_val in sorted(overrides.items()):
        old_val = _get_nested(current_yaml, path, "???")
        marker = " ✓" if old_val != new_val else " (same)"
        print(f"  {path}: {old_val} → {new_val}{marker}", file=sys.stderr)
    print(file=sys.stderr)


def show_metrics(result: dict):
    """Display backtest metrics for the selected sweep result."""
    print("--- Backtest Metrics ---\n", file=sys.stderr)
    for key in ["total_pnl", "total_trades", "win_rate", "profit_factor",
                 "sharpe_ratio", "max_drawdown_pct", "final_balance"]:
        val = result.get(key, "N/A")
        if isinstance(val, float):
            if "pct" in key or "rate" in key:
                print(f"  {key}: {val*100:.1f}%", file=sys.stderr)
            else:
                print(f"  {key}: {val:.2f}", file=sys.stderr)
        else:
            print(f"  {key}: {val}", file=sys.stderr)
    print(file=sys.stderr)


# ---------------------------------------------------------------------------
# Close positions
# ---------------------------------------------------------------------------

def close_live_positions(*, max_retries: int = 3):
    """Close all live positions via Hyperliquid API."""
    sys.path.insert(0, PROJECT_DIR)
    from exchange.executor import load_live_secrets, HyperliquidLiveExecutor

    secrets = load_live_secrets(SECRETS_PATH)
    executor = HyperliquidLiveExecutor(
        secret_key=secrets.secret_key,
        main_address=secrets.main_address,
    )

    positions = executor.get_positions(force=True)
    if not positions:
        print("[deploy] No live positions to close.", file=sys.stderr)
        return True

    print(f"[deploy] Closing {len(positions)} live position(s)...", file=sys.stderr)

    for sym, pdata in positions.items():
        is_long = pdata["type"] == "LONG"
        size = pdata["size"]
        # To close: sell if long, buy if short
        is_buy = not is_long

        success = False
        for attempt in range(1, max_retries + 1):
            print(f"  [{sym}] Attempt {attempt}/{max_retries}: "
                  f"closing {pdata['type']} size={size:.6f}", file=sys.stderr)
            res = executor.market_close(
                sym,
                is_buy=is_buy,
                sz=size,
                slippage_pct=0.02,
            )
            if res is not None:
                print(f"  [{sym}] Close submitted. Waiting 5s...", file=sys.stderr)
                time.sleep(5)
                # Verify
                remaining = executor.get_positions(force=True)
                if sym not in remaining:
                    print(f"  [{sym}] Closed successfully.", file=sys.stderr)
                    success = True
                    break
                else:
                    print(f"  [{sym}] Still open after close attempt.", file=sys.stderr)
            else:
                print(f"  [{sym}] Close rejected/failed.", file=sys.stderr)
                time.sleep(2)

        if not success:
            print(f"  [{sym}] FAILED to close after {max_retries} attempts. ABORTING.", file=sys.stderr)
            return False

    print("[deploy] All live positions closed.", file=sys.stderr)
    return True


def close_paper_positions():
    """Close all paper positions by inserting CLOSE trades and clearing position_state."""
    if not os.path.exists(PAPER_DB):
        print("[deploy] Paper DB not found — nothing to close.", file=sys.stderr)
        return True

    conn = sqlite3.connect(PAPER_DB, timeout=10)
    conn.row_factory = sqlite3.Row

    # Get open positions (simplified: just read position_state)
    rows = conn.execute("SELECT symbol FROM position_state").fetchall()
    if not rows:
        print("[deploy] No paper positions to close.", file=sys.stderr)
        conn.close()
        return True

    now_iso = datetime.now(timezone.utc).isoformat()
    # Get latest balance
    bal_row = conn.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1").fetchone()
    balance = float(bal_row["balance"]) if bal_row else 0.0

    for row in rows:
        sym = row["symbol"]
        print(f"  [{sym}] Inserting CLOSE trade for paper position.", file=sys.stderr)
        conn.execute(
            "INSERT INTO trades (timestamp, symbol, type, action, price, size, notional, "
            "reason, confidence, pnl, fee_usd, balance, entry_atr, leverage, margin_used) "
            "VALUES (?, ?, 'SYSTEM', 'CLOSE', 0, 0, 0, 'deploy_sweep close', 'N/A', 0, 0, ?, 0, 0, 0)",
            (now_iso, sym, balance),
        )

    conn.execute("DELETE FROM position_state")
    conn.commit()
    conn.close()

    print(f"[deploy] Closed {len(rows)} paper position(s).", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

def update_changelog(overrides: dict[str, Any], metrics: dict, version: str):
    """Append entry to strategy_changelog.json."""
    changelog = {"current_version": version, "history": []}
    if os.path.exists(CHANGELOG_PATH):
        with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
            changelog = json.load(f)

    changes = [f"DEPLOY: Applied sweep-optimised config (rank #{metrics.get('_rank', 1)})."]
    for path, val in sorted(overrides.items()):
        changes.append(f"  {path}: → {val}")

    pnl = metrics.get("total_pnl", 0)
    trades = metrics.get("total_trades", 0)
    wr = metrics.get("win_rate", 0) * 100
    pf = metrics.get("profit_factor", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    changes.append(
        f"Backtest verification: ${pnl:.2f} PnL / {trades} trades / "
        f"{wr:.1f}% WR / PF {pf:.2f} / Sharpe {sharpe:.3f}"
    )

    entry = {
        "version": version,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "changes": changes,
    }

    changelog["current_version"] = version
    changelog["history"].insert(0, entry)

    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        json.dump(changelog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"[deploy] Changelog updated → {version}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Restart services
# ---------------------------------------------------------------------------

def restart_services():
    """Restart paper + live trading services."""
    for svc in ["openclaw-ai-quant-trader", "openclaw-ai-quant-live"]:
        print(f"[deploy] Restarting {svc}...", file=sys.stderr)
        result = subprocess.run(
            ["systemctl", "--user", "restart", svc],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"  {svc}: restarted OK", file=sys.stderr)
        else:
            print(f"  {svc}: restart FAILED — {result.stderr.strip()}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Deploy sweep-optimised config")
    parser.add_argument("--sweep-results", required=True, help="Path to sweep results JSONL file")
    parser.add_argument("--rank", type=int, default=1, help="Pick Nth best result (1 = best PnL)")
    parser.add_argument("--yaml-path", default=YAML_PATH, help="Target YAML path to update.")
    parser.add_argument("--artifacts-dir", default=DEFAULT_ARTIFACTS_DIR, help="Artifacts root for deploy events.")
    parser.add_argument("--close-live", action="store_true", help="Close all live positions before deploy")
    parser.add_argument("--close-paper", action="store_true", help="Close all paper positions before deploy")
    parser.add_argument("--restart", action="store_true", help="Restart paper + live services after deploy")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.set_defaults(no_live=True)
    parser.add_argument(
        "--no-live",
        dest="no_live",
        action="store_true",
        help="Safety guard (default): block live-target writes/close-live/restart.",
    )
    parser.add_argument(
        "--allow-live",
        dest="no_live",
        action="store_false",
        help="Disable the --no-live guard (use with care).",
    )
    parser.add_argument("--version", type=str, default=None,
                        help="Version tag for changelog (auto-incremented if omitted)")
    parser.add_argument(
        "--replay-gate-blocker-file",
        default="",
        help="Optional replay-gate blocker JSON path override.",
    )
    parser.add_argument(
        "--max-replay-gate-age-minutes",
        type=float,
        default=float(os.getenv("AI_QUANT_REPLAY_GATE_MAX_AGE_MINUTES", "360") or 360.0),
        help="Maximum allowed blocker age in minutes (default: 360; <=0 disables staleness check).",
    )
    parser.add_argument(
        "--ignore-replay-gate",
        action="store_true",
        help="Bypass replay-gate release-blocker checks (not recommended).",
    )
    args = parser.parse_args(argv)

    yaml_path = str(Path(args.yaml_path).expanduser().resolve())
    guard_err = _no_live_guard_error(
        no_live=bool(args.no_live),
        yaml_path=yaml_path,
        close_live=bool(args.close_live),
        restart=bool(args.restart),
    )
    if guard_err:
        print(f"[deploy] {guard_err} Use --allow-live to override.", file=sys.stderr)
        sys.exit(2)

    if (not bool(args.dry_run)) and (not bool(args.ignore_replay_gate)):
        blocker_override = (
            Path(str(args.replay_gate_blocker_file)).expanduser().resolve()
            if str(args.replay_gate_blocker_file or "").strip()
            else None
        )
        try:
            assert_replay_gate_green(
                blocker_path=blocker_override,
                max_age_minutes=float(args.max_replay_gate_age_minutes),
            )
        except ReplayGateViolation as exc:
            detail = "; ".join(list(getattr(exc, "reasons", []) or [])) or str(exc)
            print(f"[deploy] Replay gate blocked deployment: {detail}", file=sys.stderr)
            sys.exit(2)

    # Load sweep results
    results = load_sweep_results(args.sweep_results)
    if not results:
        print("[deploy] No results found in sweep file.", file=sys.stderr)
        sys.exit(1)

    idx = args.rank - 1
    if idx < 0 or idx >= len(results):
        print(f"[deploy] Rank {args.rank} out of range (1..{len(results)}).", file=sys.stderr)
        sys.exit(1)

    selected = results[idx]
    overrides = selected.get("overrides", {})
    if not overrides:
        print("[deploy] Selected result has no overrides.", file=sys.stderr)
        sys.exit(1)

    # Coerce override values into deploy-safe runtime types.
    coerced_overrides: dict[str, Any] = {}
    for path, raw_value in overrides.items():
        param_name = str(path).split(".")[-1]
        coerced_overrides[str(path)] = _coerce_override_value(param_name, raw_value)
    overrides = coerced_overrides

    # Load current YAML
    current_data = _load_yaml(yaml_path)

    # Show diff + metrics
    show_diff(current_data, overrides)
    show_metrics(selected)

    # Build candidate config text and run deployment-time validation before
    # any side effects (closing positions / writing files / restarting services).
    for path, value in overrides.items():
        _set_nested(current_data, path, value)

    next_yaml_text = yaml.safe_dump(current_data, sort_keys=False)
    errs = validate_yaml_text(next_yaml_text)
    if errs:
        print("[deploy] Invalid config YAML after applying sweep overrides:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("[deploy] --dry-run: no changes applied.", file=sys.stderr)
        return

    # Confirm
    if not args.yes:
        if not sys.stdin.isatty():
            print("[deploy] Non-interactive shell detected. Use --yes to skip confirmation.", file=sys.stderr)
            sys.exit(2)
        answer = input("Apply these changes? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("[deploy] Aborted.", file=sys.stderr)
            return

    # Close positions
    if args.close_live:
        if not close_live_positions():
            print("[deploy] Live close failed. Aborting deploy.", file=sys.stderr)
            sys.exit(1)

    if args.close_paper:
        if not close_paper_positions():
            print("[deploy] Paper close failed. Aborting deploy.", file=sys.stderr)
            sys.exit(1)

    prev_text = Path(yaml_path).read_text(encoding="utf-8") if Path(yaml_path).exists() else ""
    _backup_yaml(yaml_path)
    _atomic_write_text(yaml_path, next_yaml_text)

    print(f"[deploy] YAML updated atomically: {yaml_path}", file=sys.stderr)
    event_dir = _write_deploy_event(
        artifacts_dir=args.artifacts_dir,
        yaml_path=yaml_path,
        prev_text=prev_text,
        next_text=next_yaml_text,
        selected=selected,
        rank=args.rank,
        no_live=bool(args.no_live),
    )
    print(f"[deploy] Deploy artefact written: {event_dir}", file=sys.stderr)

    # Determine version
    version = args.version
    if not version:
        if os.path.exists(CHANGELOG_PATH):
            with open(CHANGELOG_PATH, "r") as f:
                cl = json.load(f)
            cur = cl.get("current_version", "v0.000")
            # Auto-increment: v6.000 → v6.001
            try:
                prefix, num = cur.rsplit(".", 1)
                version = f"{prefix}.{int(num) + 1:03d}"
            except Exception:
                version = cur + ".1"
        else:
            version = "v6.001"

    selected["_rank"] = args.rank
    update_changelog(overrides, selected, version)

    # Restart
    if args.restart:
        restart_services()

    print(f"\n[deploy] Done. Version: {version}", file=sys.stderr)


if __name__ == "__main__":
    main()
