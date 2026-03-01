#!/usr/bin/env python3
"""Promote a paper-tested config to live with gate checks (AQC-702).

This command is designed to be automation-friendly:
- It prints a JSON result to stdout.
- It exits non-zero when any promotion gate fails.

Gate inputs are sourced from:
- Paper deployment artefact (deploy_event.json) to establish the evaluation window.
- Paper trading SQLite DB (trades + audit_events) for realised performance and kill events.

The promotion step (when --apply is set) writes the selected config YAML to the live YAML path
atomically and emits a promotion artefact under artifacts/deployments/live/.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import hashlib
import json
import os
import socket
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from tools.config_id import config_id_from_yaml_text
except ImportError:  # pragma: no cover
    from config_id import config_id_from_yaml_text  # type: ignore[no-redef]

try:
    from tools.deploy_validate import validate_yaml_text
except ImportError:  # pragma: no cover
    from deploy_validate import validate_yaml_text  # type: ignore[no-redef]

try:
    from tools.registry_index import default_registry_db_path
except ImportError:  # pragma: no cover
    from registry_index import default_registry_db_path  # type: ignore[no-redef]

try:
    from tools.replay_gate_blocker import ReplayGateViolation, assert_replay_gate_green
except ImportError:  # pragma: no cover
    from replay_gate_blocker import ReplayGateViolation, assert_replay_gate_green  # type: ignore[no-redef]


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _stderr(msg: str) -> None:
    sys.stderr.write(str(msg).rstrip("\n") + "\n")


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _atomic_write_text(path: Path, text: str) -> None:
    import uuid

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex[:12]}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def _parse_iso_to_epoch_s(ts: str) -> float | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        # Python's fromisoformat does not accept Z.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        import datetime

        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None


def _load_yaml_engine_interval(yaml_text: str) -> str:
    try:
        import yaml

        obj = yaml.safe_load(yaml_text) or {}
        if not isinstance(obj, dict):
            return ""
        glob = obj.get("global", {}) if isinstance(obj.get("global", {}), dict) else {}
        eng = glob.get("engine", {}) if isinstance(glob.get("engine", {}), dict) else {}
        iv = eng.get("interval", "")
        return str(iv or "").strip()
    except Exception:
        return ""


def _extract_trade_slippage_bps(yaml_text: str) -> float | None:
    try:
        import yaml

        obj = yaml.safe_load(yaml_text) or {}
        if not isinstance(obj, dict):
            return None
        glob = obj.get("global", {}) if isinstance(obj.get("global", {}), dict) else {}
        trade = glob.get("trade", {}) if isinstance(glob.get("trade", {}), dict) else {}
        v = trade.get("slippage_bps")
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _read_latest_paper_deploy_event(*, artifacts_dir: Path) -> dict[str, Any]:
    root = (Path(artifacts_dir) / "deployments" / "paper").expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"paper deployments dir not found: {root}")
    # Use lexicographic order since dirs are prefixed with UTC compact timestamps.
    dirs = [p for p in root.iterdir() if p.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"no paper deploy dirs under: {root}")
    dirs.sort(key=lambda p: p.name, reverse=True)
    ev_path = dirs[0] / "deploy_event.json"
    if not ev_path.exists():
        raise FileNotFoundError(f"deploy_event.json not found: {ev_path}")
    return json.loads(ev_path.read_text(encoding="utf-8"))


def _lookup_config_yaml_text(*, registry_db: Path, config_id: str) -> str:
    con = sqlite3.connect(str(registry_db), timeout=2.0)
    try:
        row = con.execute("SELECT yaml_text FROM configs WHERE config_id = ? LIMIT 1", (str(config_id),)).fetchone()
        if not row:
            raise KeyError(f"config_id not found in registry: {config_id}")
        txt = str(row[0] or "")
        if not txt.strip():
            raise ValueError(f"empty yaml_text for config_id: {config_id}")
        return txt
    finally:
        con.close()


@dataclass(frozen=True)
class GateConfig:
    min_trades: int
    min_hours: float
    min_profit_factor: float
    max_drawdown_pct: float
    max_config_slippage_bps: float | None
    max_kill_events: int


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: list[str]
    metrics: dict[str, Any]


def _compute_profit_factor(net_pnls: list[float]) -> float:
    profits = 0.0
    losses = 0.0
    for x in net_pnls:
        v = float(x or 0.0)
        if v > 0:
            profits += v
        elif v < 0:
            losses += abs(v)
    if losses <= 0:
        return float("inf") if profits > 0 else 0.0
    return float(profits / losses)


def _compute_max_drawdown_pct(equity: list[float]) -> float:
    peak = None
    max_dd = 0.0
    for x in equity:
        v = float(x or 0.0)
        if peak is None or v > peak:
            peak = v
            continue
        if peak and peak > 0:
            dd = max(0.0, (peak - v) / peak) * 100.0
            if dd > max_dd:
                max_dd = dd
    return float(max_dd)


def evaluate_paper_gates(
    *,
    paper_db: Path,
    since_epoch_s: float,
    cfg: GateConfig,
    config_yaml_text: str,
) -> GateResult:
    paper_db = Path(paper_db).expanduser().resolve()
    if not paper_db.exists():
        return GateResult(passed=False, reasons=[f"paper db not found: {paper_db}"], metrics={})

    reasons: list[str] = []

    # Collect trades since deploy.
    con = sqlite3.connect(str(paper_db), timeout=2.0)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT timestamp, action, pnl, fee_usd, balance
            FROM trades
            ORDER BY id ASC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return GateResult(passed=False, reasons=[f"failed to read trades: {e}"], metrics={})
    finally:
        try:
            con.close()
        except Exception:
            pass

    # Parse timestamps and filter.
    kept: list[dict[str, Any]] = []
    for r in rows:
        ts_s = _parse_iso_to_epoch_s(str(r.get("timestamp") or ""))
        if ts_s is None:
            continue
        if ts_s >= float(since_epoch_s):
            kept.append({**r, "_ts_s": float(ts_s)})

    now_s = time.time()
    elapsed_h = max(0.0, (now_s - float(since_epoch_s)) / 3600.0)

    # Count completed trades (CLOSE actions) as the trade-count gate.
    close_n = 0
    net_pnls: list[float] = []
    equity_curve: list[float] = []
    for r in kept:
        ac = str(r.get("action") or "").strip().upper()
        try:
            pnl = float(r.get("pnl") or 0.0)
        except Exception:
            pnl = 0.0
        try:
            fee = float(r.get("fee_usd") or 0.0)
        except Exception:
            fee = 0.0
        net = float(pnl) - float(fee)
        if ac in {"CLOSE", "REDUCE"}:
            net_pnls.append(net)
        if ac == "CLOSE":
            close_n += 1
        try:
            equity_curve.append(float(r.get("balance") or 0.0))
        except Exception:
            pass

    pf = _compute_profit_factor(net_pnls)
    dd = _compute_max_drawdown_pct(equity_curve)

    # Kill events (paper): audit_events where event starts with RISK_KILL since deploy.
    kill_events = 0
    try:
        con2 = sqlite3.connect(str(paper_db), timeout=1.0)
        con2.row_factory = sqlite3.Row
        cur2 = con2.cursor()
        cur2.execute(
            """
            SELECT timestamp, event
            FROM audit_events
            WHERE event LIKE 'RISK_KILL%'
            ORDER BY id ASC
            """
        )
        for row in cur2.fetchall():
            ts_s = _parse_iso_to_epoch_s(str(row["timestamp"] or ""))
            if ts_s is not None and ts_s >= float(since_epoch_s):
                kill_events += 1
    except Exception:
        kill_events = 0
    finally:
        try:
            con2.close()
        except Exception:
            pass

    # Config slippage (static check).
    slippage_bps = _extract_trade_slippage_bps(config_yaml_text)

    gate_min_run_ok = (close_n >= int(cfg.min_trades)) or (elapsed_h >= float(cfg.min_hours))
    if not gate_min_run_ok:
        reasons.append(f"min_run not met (close_trades={close_n} < {cfg.min_trades} AND elapsed_h={elapsed_h:.2f} < {cfg.min_hours})")

    if pf < float(cfg.min_profit_factor):
        reasons.append(f"profit_factor {pf:.3f} < {cfg.min_profit_factor}")

    if dd > float(cfg.max_drawdown_pct):
        reasons.append(f"max_drawdown_pct {dd:.3f} > {cfg.max_drawdown_pct}")

    if cfg.max_config_slippage_bps is not None and slippage_bps is not None:
        if float(slippage_bps) > float(cfg.max_config_slippage_bps):
            reasons.append(f"config slippage_bps {float(slippage_bps):.3f} > {float(cfg.max_config_slippage_bps):.3f}")

    if kill_events > int(cfg.max_kill_events):
        reasons.append(f"kill_events {kill_events} > {cfg.max_kill_events}")

    metrics = {
        "elapsed_h": float(elapsed_h),
        "close_trades": int(close_n),
        "profit_factor": float(pf),
        "max_drawdown_pct": float(dd),
        "kill_events": int(kill_events),
        "config_slippage_bps": None if slippage_bps is None else float(slippage_bps),
    }
    return GateResult(passed=not reasons, reasons=reasons, metrics=metrics)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Promote a paper-tested config to live (with gates).")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root (default: artifacts).")
    ap.add_argument("--paper-db", default="trading_engine.db", help="Paper trading SQLite DB path (default: trading_engine.db).")
    ap.add_argument("--registry-db", default="", help="Registry SQLite DB path (default: artifacts/registry/registry.sqlite).")
    ap.add_argument("--live-yaml-path", default=str(AIQ_ROOT / "config" / "strategy_overrides.yaml"), help="Target live YAML path.")
    ap.add_argument("--config-id", default="", help="Config id to promote (default: from latest paper deploy event).")

    ap.add_argument("--min-trades", type=int, default=20, help="Minimum CLOSE trades OR min-hours must be met.")
    ap.add_argument("--min-hours", type=float, default=24.0, help="Minimum run duration in hours OR min-trades must be met.")
    ap.add_argument("--min-profit-factor", type=float, default=1.2, help="Minimum profit factor (net of fees).")
    ap.add_argument("--max-drawdown-pct", type=float, default=10.0, help="Maximum allowed drawdown percentage.")
    ap.add_argument(
        "--max-config-slippage-bps",
        type=float,
        default=20.0,
        help="Fail when config trade.slippage_bps exceeds this value. Set <=0 to disable this gate.",
    )
    ap.add_argument("--max-kill-events", type=int, default=0, help="Maximum allowed RISK_KILL* audit events during paper.")

    ap.add_argument("--apply", action="store_true", help="Apply the promotion (write YAML + emit artefact).")
    ap.add_argument("--dry-run", action="store_true", help="Run all checks but do not write any files.")
    ap.add_argument(
        "--replay-gate-blocker-file",
        default="",
        help="Optional replay-gate blocker JSON path override.",
    )
    ap.add_argument(
        "--max-replay-gate-age-minutes",
        type=float,
        default=float(os.getenv("AI_QUANT_REPLAY_GATE_MAX_AGE_MINUTES", "360") or 360.0),
        help="Maximum allowed blocker age in minutes (default: 360; <=0 disables staleness check).",
    )
    ap.add_argument(
        "--ignore-replay-gate",
        action="store_true",
        help="Bypass replay-gate release-blocker checks when applying promotion (not recommended).",
    )
    args = ap.parse_args(argv)

    artifacts_dir = Path(args.artifacts_dir).expanduser().resolve()
    paper_db = Path(args.paper_db).expanduser().resolve()
    live_yaml_path = Path(args.live_yaml_path).expanduser().resolve()

    registry_db = Path(args.registry_db).expanduser().resolve() if str(args.registry_db).strip() else default_registry_db_path(artifacts_root=artifacts_dir)

    deploy_ev = _read_latest_paper_deploy_event(artifacts_dir=artifacts_dir)
    deploy_ts = str((deploy_ev.get("ts_utc") or "").strip())
    since_s = _parse_iso_to_epoch_s(deploy_ts)
    if since_s is None:
        out = {"ok": False, "error": f"invalid deploy ts_utc: {deploy_ts!r}", "deploy_event": deploy_ev}
        sys.stdout.write(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return 2

    config_id = str(args.config_id or "").strip() or str(((deploy_ev.get("what") or {}).get("config_id") or "")).strip()
    if not config_id:
        out = {"ok": False, "error": "missing config_id (provide --config-id or ensure paper deploy_event.json has what.config_id)"}
        sys.stdout.write(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return 2

    yaml_text = _lookup_config_yaml_text(registry_db=registry_db, config_id=config_id)
    computed_id = config_id_from_yaml_text(yaml_text)
    if computed_id != config_id:
        out = {"ok": False, "error": f"registry yaml_text hash mismatch: expected {config_id}, got {computed_id}"}
        sys.stdout.write(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return 2

    # YAML validation (static schema/required fields).
    errs = validate_yaml_text(yaml_text)
    if errs:
        out = {"ok": False, "error": "invalid config YAML", "errors": errs}
        sys.stdout.write(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return 2

    gate_cfg = GateConfig(
        min_trades=int(args.min_trades),
        min_hours=float(args.min_hours),
        min_profit_factor=float(args.min_profit_factor),
        max_drawdown_pct=float(args.max_drawdown_pct),
        max_config_slippage_bps=None if float(args.max_config_slippage_bps) <= 0 else float(args.max_config_slippage_bps),
        max_kill_events=int(args.max_kill_events),
    )

    gate_res = evaluate_paper_gates(paper_db=paper_db, since_epoch_s=float(since_s), cfg=gate_cfg, config_yaml_text=yaml_text)

    result: dict[str, Any] = {
        "ok": bool(gate_res.passed),
        "config_id": str(config_id),
        "deploy_ts_utc": str(deploy_ts),
        "paper_db": str(paper_db),
        "registry_db": str(registry_db),
        "gates": {
            "passed": bool(gate_res.passed),
            "reasons": list(gate_res.reasons),
            "metrics": dict(gate_res.metrics),
            "config": gate_cfg.__dict__,
        },
        "apply": bool(args.apply),
        "dry_run": bool(args.dry_run),
    }

    if not gate_res.passed:
        for r in gate_res.reasons:
            _stderr(f"⛔ Gate fail: {r}")
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 1

    if bool(args.apply) and (not bool(args.dry_run)) and (not bool(args.ignore_replay_gate)):
        blocker_override = (
            Path(str(args.replay_gate_blocker_file)).expanduser().resolve()
            if str(args.replay_gate_blocker_file or "").strip()
            else None
        )
        try:
            replay_gate_status = assert_replay_gate_green(
                blocker_path=blocker_override,
                max_age_minutes=float(args.max_replay_gate_age_minutes),
            )
            result["replay_gate"] = replay_gate_status
        except ReplayGateViolation as exc:
            result["ok"] = False
            result["error"] = f"replay gate blocked promotion: {exc}"
            result["replay_gate"] = dict(getattr(exc, "status", {}))
            sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
            return 1

    # Gate pass. Apply promotion if requested.
    if bool(args.apply) and (not bool(args.dry_run)):
        prev_text = live_yaml_path.read_text(encoding="utf-8") if live_yaml_path.exists() else ""
        prev_interval = _load_yaml_engine_interval(prev_text)
        next_interval = _load_yaml_engine_interval(yaml_text)
        restart_required = bool(prev_interval and next_interval and prev_interval != next_interval)

        ts = _utc_compact()
        short = config_id[:12]
        out_dir = (artifacts_dir / "deployments" / "live" / f"{ts}_{short}").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        event: dict[str, Any] = {
            "version": "promotion_event_v1",
            "ts_utc": _utc_now_iso(),
            "ts_compact_utc": ts,
            "who": {"user": getpass.getuser(), "hostname": socket.gethostname()},
            "what": {
                "mode": "live",
                "config_id": str(config_id),
                "registry_db": str(registry_db),
                "yaml_path": str(live_yaml_path),
                "prev_yaml_sha256": hashlib.sha256(prev_text.encode("utf-8")).hexdigest() if prev_text else "",
                "next_yaml_sha256": hashlib.sha256(yaml_text.encode("utf-8")).hexdigest(),
                "prev_engine_interval": str(prev_interval),
                "next_engine_interval": str(next_interval),
                "restart_required": bool(restart_required),
            },
            "gates": result["gates"],
        }

        (out_dir / "promoted_config.yaml").write_text(yaml_text, encoding="utf-8")
        (out_dir / "prev_config.yaml").write_text(prev_text, encoding="utf-8")
        _atomic_write_text(live_yaml_path, yaml_text)
        (out_dir / "promotion_event.json").write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        result["promotion_artifact_dir"] = str(out_dir)

    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
