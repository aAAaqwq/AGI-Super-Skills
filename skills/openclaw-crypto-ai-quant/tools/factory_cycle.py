#!/usr/bin/env python3
"""Run a full factory cycle and optionally auto-deploy the best config to paper.

This tool is designed for unattended runs (e.g. a systemd timer) on the `major-v8`
worktree. It orchestrates:

1) `factory_run.py` (data checks → sweep → candidate generation → CPU validation → registry)
2) Selection of the best non-rejected candidate
3) Optional paper deployment via `tools/paper_deploy.py` (atomic YAML write + optional restart)

The goal is to make the strategy factory loop runnable as a single command for a
parallel v8 instance, without touching production `master`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

AIQ_ROOT = Path(__file__).resolve().parents[1]


def _env_float(env_name: str, *, default: float | None = None) -> float | None:
    raw = str(os.getenv(env_name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        raise SystemExit(f"{env_name} must be a float when set")


def _env_bool(env_name: str, *, default: bool = False) -> bool:
    raw = os.getenv(env_name, "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def _env_int(env_name: str, *, default: int | None = None) -> int | None:
    raw = str(os.getenv(env_name, "") or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        raise SystemExit(f"{env_name} must be an integer when set")


def _nvidia_gpu_available() -> bool:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    try:
        res = subprocess.run(
            [smi, "-L"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    if int(res.returncode) != 0:
        return False
    lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
    if len(lines) == 0:
        return False

    try:
        procs = subprocess.run(
            [smi, "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        # If process-query fails, treat GPU as available to preserve existing behaviour.
        return True
    if int(procs.returncode) != 0:
        return True

    for line in (procs.stdout or "").splitlines():
        parts = [ln.strip() for ln in line.split(",")]
        if len(parts) < 1:
            continue
        pid = parts[0]
        if pid.isdigit() and pid.isascii() and os.path.exists(f"/proc/{pid}"):
            return False
    return True


# When invoked as `python3 tools/factory_cycle.py`, sys.path[0] is `tools/`.
# Ensure the repo root is importable so `import factory_run` works consistently.
if str(AIQ_ROOT) not in sys.path:
    sys.path.insert(0, str(AIQ_ROOT))

import factory_run  # noqa: E402  (needs sys.path fix above)
from engine.alerting import send_openclaw_message  # noqa: E402

try:
    from tools.paper_deploy import deploy_paper_config
    from tools.config_id import config_id_from_yaml_text
    from tools.registry_index import default_registry_db_path
    from tools.promote_to_live import GateConfig, evaluate_paper_gates
except ImportError:  # pragma: no cover
    from paper_deploy import deploy_paper_config  # type: ignore[no-redef]
    from config_id import config_id_from_yaml_text  # type: ignore[no-redef]
    from registry_index import default_registry_db_path  # type: ignore[no-redef]
    from promote_to_live import GateConfig, evaluate_paper_gates  # type: ignore[no-redef]


def _utc_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _read_yaml(path: Path) -> dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(obj, dict):
        raise ValueError(f"Expected YAML mapping at root: {path}")
    return obj


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base (mutates base)."""
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return base
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)  # type: ignore[index]
        else:
            base[k] = v
    return base


def _norm_mode_key(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    if s in {"mode1", "m1"}:
        return "primary"
    if s in {"mode2", "m2"}:
        return "fallback"
    if s in {"mode3", "m3", "safety", "safe"}:
        return "conservative"
    if s in {"halt", "pause", "paused"}:
        return "flat"
    return s


def _apply_strategy_mode_overlay(*, base: dict[str, Any], strategy_mode: str) -> dict[str, Any]:
    """Return an effective YAML dict with modes.<strategy_mode> merged into global/symbols.

    Rust backtester ignores `modes:` currently, so the overlay must be materialised into
    the effective `global:` section before sweeps/replays to keep "what you replay" in
    sync with "what you trade".
    """
    mode_key = _norm_mode_key(strategy_mode)
    if not mode_key:
        return base

    modes = base.get("modes") if isinstance(base.get("modes"), dict) else {}
    if not isinstance(modes, dict):
        return base

    mode_over = modes.get(mode_key)
    if mode_over is None:
        mode_over = modes.get(str(mode_key).upper())
    if mode_over is None:
        mode_over = modes.get(str(mode_key).lower())
    if not isinstance(mode_over, dict):
        raise KeyError(f"strategy mode not found in YAML: {mode_key}")

    out = json.loads(json.dumps(base))  # cheap deep copy for YAML primitives
    if "global" not in out or not isinstance(out.get("global"), dict):
        out["global"] = {}
    if "symbols" not in out or not isinstance(out.get("symbols"), dict):
        out["symbols"] = {}

    if "global" in mode_over or "symbols" in mode_over:
        glob = mode_over.get("global")
        sym = mode_over.get("symbols")
        if isinstance(glob, dict):
            _deep_merge(out["global"], glob)  # type: ignore[arg-type]
        if isinstance(sym, dict):
            # Merge per-symbol overlays if present.
            for k, v in sym.items():
                if not isinstance(k, str) or not isinstance(v, dict):
                    continue
                k2 = k.strip().upper()
                if not k2:
                    continue
                if k2 not in out["symbols"] or not isinstance(out["symbols"].get(k2), dict):
                    out["symbols"][k2] = {}
                _deep_merge(out["symbols"][k2], v)  # type: ignore[arg-type]
        return out

    # Shorthand: modes.<mode>: {trade: {...}, engine: {...}, ...}
    _deep_merge(out["global"], mode_over)  # type: ignore[arg-type]
    return out


def _yaml_engine_interval(yaml_obj: dict[str, Any]) -> str:
    glob = yaml_obj.get("global") if isinstance(yaml_obj.get("global"), dict) else {}
    eng = glob.get("engine") if isinstance(glob.get("engine"), dict) else {}
    v = str(eng.get("interval", "") or "").strip()
    return v


@dataclass(frozen=True)
class Candidate:
    config_id: str
    config_path: str
    score_v1: float | None
    total_pnl: float
    max_drawdown_pct: float
    total_trades: int
    profit_factor: float
    rejected: bool
    reject_reason: str
    pipeline_stage: str
    sweep_stage: str
    replay_stage: str
    validation_gate: str
    canonical_cpu_verified: bool
    candidate_mode: bool
    schema_version: int
    replay_report_path: str
    replay_equivalence_report_path: str
    replay_equivalence_status: str
    replay_equivalence_count: int
    has_stage_metadata: bool


@dataclass(frozen=True)
class DeployTarget:
    slot: int
    service: str
    yaml_path: Path


_PROMOTION_ROLE_ORDER: tuple[str, ...] = ("primary", "fallback", "conservative")
_DEFAULT_SLOT_ROLE: dict[int, str] = {1: "primary", 2: "fallback", 3: "conservative"}


def _parse_iso_to_epoch_s(ts: str) -> float | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        import datetime

        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None


def _split_csv(raw: str) -> list[str]:
    out: list[str] = []
    for part in str(raw or "").split(","):
        s = str(part or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _parse_candidate(it: dict[str, Any]) -> Candidate | None:
    try:
        config_id = str(it.get("config_id", "")).strip()
        config_path = str(it.get("config_path", "")).strip()
        if not config_id or not config_path:
            return None
        score_v1 = it.get("score_v1", None)
        score = None if score_v1 is None else float(score_v1)
        candidate_mode = bool(it.get("candidate_mode", False))
        pipeline_stage = str(it.get("pipeline_stage", "")).strip()
        sweep_stage = str(it.get("sweep_stage", "")).strip()
        replay_stage = str(it.get("replay_stage", "")).strip()
        validation_gate = str(it.get("validation_gate", "")).strip()
        replay_report_path = str(it.get("replay_report_path", "")).strip()
        replay_equivalence_report_path = str(it.get("replay_equivalence_report_path", "")).strip()
        replay_equivalence_status = str(it.get("replay_equivalence_status", "")).strip().lower()
        try:
            replay_equivalence_count = int(it.get("replay_equivalence_count", 0))
        except Exception:
            replay_equivalence_count = -1
        try:
            raw_schema_version = it.get("schema_version", None)
            if isinstance(raw_schema_version, bool):
                schema_version = 0
            else:
                schema_version = int(raw_schema_version)
        except Exception:
            schema_version = 0

        if not candidate_mode:
            pipeline_stage = pipeline_stage or "legacy"
            sweep_stage = sweep_stage or "legacy"
            if not replay_stage:
                replay_stage = ""

        return Candidate(
            config_id=config_id,
            config_path=config_path,
            score_v1=score,
            total_pnl=float(it.get("total_pnl", 0.0)),
            max_drawdown_pct=float(it.get("max_drawdown_pct", 0.0)),
            total_trades=int(it.get("total_trades", 0)),
            profit_factor=float(it.get("profit_factor", 0.0)),
            rejected=bool(it.get("rejected", False)),
            reject_reason=str(it.get("reject_reason", "") or "").strip(),
            has_stage_metadata=any(
                k in it
                for k in ("pipeline_stage", "sweep_stage", "replay_stage", "validation_gate", "canonical_cpu_verified")
            ),
            pipeline_stage=pipeline_stage,
            sweep_stage=sweep_stage,
            replay_stage=replay_stage,
            validation_gate=validation_gate or "replay_only",
            canonical_cpu_verified=bool(it.get("canonical_cpu_verified", True)),
            candidate_mode=candidate_mode,
            schema_version=schema_version,
            replay_report_path=replay_report_path,
            replay_equivalence_report_path=replay_equivalence_report_path,
            replay_equivalence_status=replay_equivalence_status,
            replay_equivalence_count=replay_equivalence_count,
        )
    except Exception:
        return None


def _candidate_stage_complete(c: Candidate) -> bool:
    if not c.candidate_mode:
        return False
    return bool(c.pipeline_stage) and bool(c.sweep_stage) and bool(c.replay_stage) and bool(c.validation_gate)


def _candidate_evidence_complete(c: Candidate) -> bool:
    if not c.candidate_mode:
        return False
    return (
        _candidate_stage_complete(c)
        and bool(c.canonical_cpu_verified)
        and c.replay_equivalence_status == "pass"
        and int(c.schema_version) == 1
        and c.replay_equivalence_count >= 0
        and bool(c.replay_report_path)
        and bool(c.replay_equivalence_report_path)
    )


def _candidate_deployable(c: Candidate, *, require_ssot_evidence: bool = True) -> bool:
    if not c.candidate_mode:
        return not require_ssot_evidence
    if not require_ssot_evidence:
        return c.canonical_cpu_verified and _candidate_stage_complete(c)
    return _candidate_evidence_complete(c)


def _candidate_sort_key(c: Candidate) -> tuple[float, float]:
    score = float(c.score_v1) if c.score_v1 is not None else float("-inf")
    return (score, float(c.total_pnl))


def _stage_rank(c: Candidate) -> int:
    if not bool(c.candidate_mode):
        return 0
    if not _candidate_stage_complete(c):
        return 0
    if c.canonical_cpu_verified and c.replay_stage:
        return 2
    if c.canonical_cpu_verified:
        return 1
    return 0


def _candidate_sort_key_with_stage(c: Candidate) -> tuple[int, float, float]:
    return (int(_stage_rank(c)), float(c.score_v1) if c.score_v1 is not None else float("-inf"), float(c.total_pnl))


def _format_float(v: Any, *, ndigits: int = 3, default: str = "n/a") -> str:
    try:
        return f"{float(v):.{ndigits}f}"
    except Exception:
        return default


def _short_id(v: str, n: int = 12) -> str:
    s = str(v or "").strip()
    return s[:n] if s else "n/a"


def _short_path(v: str, parts: int = 3) -> str:
    s = str(v or "").strip()
    if not s:
        return "n/a"
    p = Path(s)
    xs = p.parts
    if len(xs) <= int(parts):
        return s
    return str(Path(*xs[-int(parts) :]))


def _format_candidate_row(c: Candidate, *, idx: int, include_reason: bool = False) -> str:
    icon = "❌" if include_reason else "✅"
    row = (
        f"{icon} #{idx} `{_short_id(c.config_id)}` "
        f"pf={_format_float(c.profit_factor, ndigits=3)} "
        f"dd={_format_float(float(c.max_drawdown_pct) * 100.0, ndigits=2)}% "
        f"pnl={_format_float(c.total_pnl, ndigits=2)} "
        f"trades={int(c.total_trades)} "
        f"score={_format_float(c.score_v1, ndigits=4)}"
    )
    if include_reason:
        reason = str(c.reject_reason or "").strip() or "unknown"
        if len(reason) > 96:
            reason = reason[:93] + "..."
        row += f" | reason={reason}"
    return row


def _send_discord_chunks(*, target: str, lines: list[str], max_chars: int = 1800) -> None:
    tgt = str(target or "").strip()
    if not tgt:
        return
    clean = [str(x).rstrip() for x in lines if str(x).strip()]
    if not clean:
        return
    chunks: list[str] = []
    cur = ""
    for line in clean:
        if not cur:
            cur = line
            continue
        candidate = cur + "\n" + line
        if len(candidate) <= int(max_chars):
            cur = candidate
            continue
        chunks.append(cur)
        cur = line
    if cur:
        chunks.append(cur)
    for chunk in chunks:
        _send_discord(target=tgt, message=chunk)


def _write_selection_markdown(*, run_dir: Path, selection: dict[str, Any]) -> None:
    selected = selection.get("selected")
    if not isinstance(selected, dict):
        selected = {}
    selected_id = str(selected.get("config_id", "")).strip()
    selected_pf = float(selected.get("profit_factor", 0.0) or 0.0)
    selected_dd = float(selected.get("max_drawdown_pct", 0.0) or 0.0) * 100.0
    selected_pnl = float(selected.get("total_pnl", 0.0) or 0.0)
    selected_trades = int(selected.get("total_trades", 0) or 0)
    selected_score = selected.get("score_v1", "n/a")

    lines = [
        "# Factory Selection",
        "",
        f"- run_id: `{selection.get('run_id', '')}`",
        f"- selection_stage: {selection.get('selection_stage', 'selected')}",
        f"- deploy_stage: {selection.get('deploy_stage', '')}",
        f"- promotion_stage: {selection.get('promotion_stage', '')}",
        f"- selected: `{selected_id or 'none'}`",
        f"- selected_profit_factor: {selected_pf:.3f}",
        f"- selected_max_drawdown_pct: {selected_dd:.3f}",
        f"- selected_total_pnl: {selected_pnl:.3f}",
        f"- selected_total_trades: {selected_trades}",
        f"- selected_score_v1: {selected_score}",
        "",
    ]
    (run_dir / "reports" / "selection.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _nested_get(obj: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def _yaml_config_id(yaml_text: str) -> str:
    txt = str(yaml_text or "").strip()
    if not txt:
        return ""
    try:
        return str(config_id_from_yaml_text(txt))
    except Exception:
        return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def _yaml_summary(yaml_text: str) -> dict[str, str]:
    txt = str(yaml_text or "").strip()
    if not txt:
        return {}
    try:
        obj = yaml.safe_load(txt) or {}
        if not isinstance(obj, dict):
            return {}
    except Exception:
        return {}

    out: dict[str, str] = {}
    iv = str(_nested_get(obj, ("global", "engine", "interval"), "") or "").strip()
    if iv:
        out["interval"] = iv
    for k, path, nd in [
        ("allocation_pct", ("global", "trade", "allocation_pct"), 4),
        ("leverage", ("global", "trade", "leverage"), 3),
        ("sl_atr_mult", ("global", "trade", "sl_atr_mult"), 3),
        ("tp_atr_mult", ("global", "trade", "tp_atr_mult"), 3),
    ]:
        v = _nested_get(obj, path, None)
        if v is None:
            continue
        out[k] = _format_float(v, ndigits=nd, default="n/a")
    return out


def _diff_yaml_summaries(prev: dict[str, str], nxt: dict[str, str]) -> list[str]:
    keys = ["interval", "allocation_pct", "leverage", "sl_atr_mult", "tp_atr_mult"]
    lines: list[str] = []
    for k in keys:
        a = str(prev.get(k, "n/a"))
        b = str(nxt.get(k, "n/a"))
        if a == b:
            continue
        lines.append(f"- {k}: {a} -> {b}")
    return lines


def _systemctl_show_value(*, service: str, prop: str) -> str:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "show", "-p", str(prop), "--value", str(service)],
            capture_output=True,
            text=True,
            check=False,
            timeout=8.0,
        )
        if int(proc.returncode) != 0:
            return ""
        return str(proc.stdout or "").strip()
    except Exception:
        return ""


def _service_active_state(service: str) -> str:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", str(service)],
            capture_output=True,
            text=True,
            check=False,
            timeout=8.0,
        )
        return str(proc.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


_SENSITIVE_ENV_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")


def _is_sensitive_env_key(key: str) -> bool:
    key_u = str(key or "").strip().upper()
    return bool(key_u) and key_u.endswith(_SENSITIVE_ENV_SUFFIXES)


def _pid_environ(pid: int) -> dict[str, str]:
    if pid <= 0:
        return {}
    path = Path("/proc") / str(pid) / "environ"
    if not path.exists():
        return {}
    try:
        raw = path.read_bytes()
    except Exception:
        return {}
    out: dict[str, str] = {}
    for chunk in raw.split(b"\x00"):
        if b"=" not in chunk:
            continue
        k, v = chunk.split(b"=", 1)
        key = k.decode("utf-8", errors="ignore").strip()
        if not key:
            continue
        if _is_sensitive_env_key(key):
            continue
        out[key] = v.decode("utf-8", errors="ignore")
    return out


def _latest_heartbeat_fields(service: str) -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["journalctl", "--user", "-u", str(service), "-n", "120", "--no-pager"],
            capture_output=True,
            text=True,
            check=False,
            timeout=12.0,
        )
    except Exception:
        return {}
    if int(proc.returncode) != 0:
        return {}
    lines = str(proc.stdout or "").splitlines()
    hb = ""
    for line in reversed(lines):
        if "engine ok." in line:
            hb = line
            break
    if not hb:
        return {}
    out: dict[str, str] = {}
    for m in re.finditer(r"([a-zA-Z0-9_]+)=([^\s]+)", hb):
        key = str(m.group(1) or "").strip()
        val = str(m.group(2) or "").strip()
        if key:
            out[key] = val
    return out


def _health_service_list(default_service: str) -> list[str]:
    raw = str(os.getenv("AI_QUANT_FACTORY_HEALTH_SERVICES", "") or "").strip()
    if not raw:
        return [str(default_service).strip()]
    out: list[str] = []
    for part in raw.split(","):
        s = str(part or "").strip()
        if s and s not in out:
            out.append(s)
    return out or [str(default_service).strip()]


def _service_snapshot_line(service: str) -> str:
    active = _service_active_state(service)
    pid_raw = _systemctl_show_value(service=service, prop="MainPID")
    try:
        pid = int(pid_raw or "0")
    except Exception:
        pid = 0
    env = _pid_environ(pid)
    hb = _latest_heartbeat_fields(service)
    mode = str(env.get("AI_QUANT_STRATEGY_MODE", "n/a") or "n/a")
    label = str(env.get("AI_QUANT_DISCORD_LABEL", "n/a") or "n/a")
    chan = str(env.get("AI_QUANT_DISCORD_CHANNEL", "n/a") or "n/a")
    cfg = str(hb.get("config_id", "n/a") or "n/a")
    cfg_s = cfg[:12] if cfg and cfg != "n/a" else "n/a"
    wsr = str(hb.get("ws_restarts", "n/a") or "n/a")
    open_pos = str(hb.get("open_pos", "n/a") or "n/a")
    return f"• {service} | active={active} mode={mode} label={label} channel={chan} cfg={cfg_s} pos={open_pos} ws={wsr}"


def _service_runtime_env(service: str) -> dict[str, str]:
    env = _service_environment(str(service))
    pid_raw = _systemctl_show_value(service=str(service), prop="MainPID")
    try:
        pid = int(pid_raw or "0")
    except Exception:
        pid = 0
    if pid > 0:
        env_rt = _pid_environ(pid)
        if env_rt:
            env.update(env_rt)
    return env


def _service_discord_route(service: str) -> tuple[str, str]:
    env = _service_runtime_env(str(service))
    target = str(env.get("AI_QUANT_DISCORD_CHANNEL", "") or "").strip()
    label = str(env.get("AI_QUANT_DISCORD_LABEL", "") or env.get("AI_QUANT_INSTANCE_TAG", "") or "").strip()
    return (target, label)


def _format_metrics_brief(metrics: dict[str, Any]) -> str:
    m = metrics if isinstance(metrics, dict) else {}
    parts: list[str] = []
    pf = m.get("profit_factor", None)
    dd = m.get("max_drawdown_pct", None)
    pnl = m.get("total_pnl", None)
    trades = m.get("total_trades", m.get("close_trades", None))
    elapsed_h = m.get("elapsed_h", None)
    if pf is not None:
        parts.append(f"pf={_format_float(pf, ndigits=3)}")
    if dd is not None:
        parts.append(f"dd={_format_float(dd, ndigits=2)}%")
    if pnl is not None:
        parts.append(f"pnl={_format_float(pnl, ndigits=2)}")
    if trades is not None:
        try:
            parts.append(f"trades={int(trades)}")
        except Exception:
            pass
    if elapsed_h is not None:
        parts.append(f"h={_format_float(elapsed_h, ndigits=1)}")
    return " ".join(parts) if parts else "n/a"


def _user_config_change_lines(
    *,
    run_id: str,
    lane_label: str,
    lane_kind: str,
    previous_cfg: str,
    next_cfg: str,
    source_note: str,
    metrics: dict[str, Any],
    diff_lines: list[str],
) -> list[str]:
    lines = [
        "🧭 Strategy Config Updated",
        f"`lane` {lane_label or 'n/a'}  `type` {lane_kind}",
        f"`config` `{_short_id(previous_cfg)}` → `{_short_id(next_cfg)}`",
        f"`trigger` nightly factory `{run_id}` ({source_note})",
        f"`validation` {_format_metrics_brief(metrics)}",
    ]
    if diff_lines:
        lines.append("Key parameter changes:")
        lines.extend(diff_lines[:6])
    else:
        lines.append("Key parameter changes: none")
    lines.append("This update applies from the next engine cycle after service restart.")
    return lines


def _build_candidates_messages(*, run_id: str, parsed: list[Candidate]) -> list[list[str]]:
    ok = [c for c in parsed if not bool(c.rejected)]
    rej = [c for c in parsed if bool(c.rejected)]
    ok.sort(key=_candidate_sort_key, reverse=True)
    rej.sort(key=_candidate_sort_key, reverse=True)

    out: list[list[str]] = []
    head = [
        f"📊 Candidates • `{run_id}`",
        f"`deployable` {len(ok)}  `rejected` {len(rej)}  `total` {len(parsed)}",
    ]
    if ok:
        lines = (
            head
            + ["Top deployable:"]
            + [_format_candidate_row(c, idx=i + 1, include_reason=False) for i, c in enumerate(ok[:5])]
        )
        out.append(lines)
    else:
        out.append(head + ["Top deployable: none"])

    if rej:
        out.append(
            [f"🧹 Rejected • `{run_id}`", "Top rejected:"]
            + [_format_candidate_row(c, idx=i + 1, include_reason=True) for i, c in enumerate(rej[:5])]
        )
    return out


def _candidate_gate_block_reasons(c: Candidate, *, require_ssot_evidence: bool) -> list[str]:
    reasons: list[str] = []
    if bool(c.rejected):
        reasons.append("rejected")

    if not bool(c.candidate_mode):
        if bool(require_ssot_evidence):
            reasons.append("legacy_without_candidate_mode")
            return reasons
        if not bool(c.canonical_cpu_verified):
            reasons.append("canonical_cpu_unverified")
        return reasons

    if not str(c.pipeline_stage).strip():
        reasons.append("missing_pipeline_stage")
    if not str(c.sweep_stage).strip():
        reasons.append("missing_sweep_stage")
    if not str(c.replay_stage).strip():
        reasons.append("missing_replay_stage")
    if not str(c.validation_gate).strip():
        reasons.append("missing_validation_gate")
    if not bool(c.canonical_cpu_verified):
        reasons.append("canonical_cpu_unverified")

    if bool(require_ssot_evidence):
        replay_status = str(c.replay_equivalence_status or "").strip().lower()
        if replay_status != "pass":
            reasons.append(f"replay_equivalence_{replay_status or 'missing'}")
        if int(c.schema_version) != 1:
            reasons.append("schema_version_not_1")
        if int(c.replay_equivalence_count) < 0:
            reasons.append("replay_equivalence_count_invalid")
        if not str(c.replay_report_path or "").strip():
            reasons.append("missing_replay_report_path")
        if not str(c.replay_equivalence_report_path or "").strip():
            reasons.append("missing_replay_equivalence_report_path")

    return reasons


def _build_step5_gate_report(
    *,
    run_id: str,
    parsed: list[Candidate],
    require_ssot_evidence: bool,
    selection_policy: str,
    deployable_selected: list[Candidate],
    deployable_by_slot: dict[int, Candidate],
    deploy_targets: list[DeployTarget],
    selection_warnings: list[str],
    blocked_reason: str = "",
) -> dict[str, Any]:
    deployable_ids = {str(c.config_id) for c in deployable_selected}
    rows: list[dict[str, Any]] = []
    blocked_reasons_count: dict[str, int] = {}
    for c in sorted(parsed, key=_candidate_sort_key_with_stage, reverse=True):
        reasons = _candidate_gate_block_reasons(c, require_ssot_evidence=bool(require_ssot_evidence))
        deployable = str(c.config_id) in deployable_ids and not reasons
        if (
            not deployable
            and not reasons
            and _candidate_deployable(c, require_ssot_evidence=bool(require_ssot_evidence))
        ):
            deployable = True
        if not deployable:
            for reason in reasons:
                blocked_reasons_count[reason] = int(blocked_reasons_count.get(reason, 0) or 0) + 1
        rows.append(
            {
                "config_id": str(c.config_id),
                "config_path": str(c.config_path),
                "candidate_mode": bool(c.candidate_mode),
                "pipeline_stage": str(c.pipeline_stage),
                "sweep_stage": str(c.sweep_stage),
                "replay_stage": str(c.replay_stage),
                "validation_gate": str(c.validation_gate),
                "canonical_cpu_verified": bool(c.canonical_cpu_verified),
                "replay_equivalence_status": str(c.replay_equivalence_status),
                "replay_equivalence_count": int(c.replay_equivalence_count),
                "replay_report_path": str(c.replay_report_path),
                "replay_equivalence_report_path": str(c.replay_equivalence_report_path),
                "rejected": bool(c.rejected),
                "reject_reason": str(c.reject_reason),
                "score_v1": None if c.score_v1 is None else float(c.score_v1),
                "total_pnl": float(c.total_pnl),
                "max_drawdown_pct": float(c.max_drawdown_pct),
                "total_trades": int(c.total_trades),
                "profit_factor": float(c.profit_factor),
                "deployable": bool(deployable),
                "gate_block_reasons": reasons,
            }
        )

    slot_bindings: list[dict[str, Any]] = []
    for target in deploy_targets:
        cand = deployable_by_slot.get(int(target.slot))
        slot_bindings.append(
            {
                "slot": int(target.slot),
                "service": str(target.service),
                "yaml_path": str(target.yaml_path),
                "selected_config_id": None if cand is None else str(cand.config_id),
            }
        )

    return {
        "schema_version": 1,
        "run_id": str(run_id),
        "generated_at_ms": int(time.time() * 1000),
        "selection_policy": str(selection_policy),
        "require_ssot_evidence": bool(require_ssot_evidence),
        "blocked": bool(not deployable_by_slot),
        "blocked_reason": str(blocked_reason or ""),
        "selection_warnings": list(selection_warnings),
        "candidate_count": len(rows),
        "deployable_count": int(sum(1 for row in rows if bool(row.get("deployable", False)))),
        "selected_count": len(deployable_selected),
        "slot_bindings": slot_bindings,
        "blocked_reasons_count": blocked_reasons_count,
        "candidates": rows,
    }


def _render_step5_gate_report_markdown(report: dict[str, Any]) -> str:
    rows = report.get("candidates", []) if isinstance(report.get("candidates"), list) else []
    blocked_counts = (
        report.get("blocked_reasons_count", {}) if isinstance(report.get("blocked_reasons_count"), dict) else {}
    )
    lines: list[str] = [
        "# Step-5 Gate Report",
        "",
        f"- run_id: `{report.get('run_id', '')}`",
        f"- blocked: {bool(report.get('blocked', False))}",
        f"- blocked_reason: {str(report.get('blocked_reason', '') or 'n/a')}",
        f"- selection_policy: {str(report.get('selection_policy', '') or 'n/a')}",
        f"- require_ssot_evidence: {bool(report.get('require_ssot_evidence', False))}",
        f"- candidate_count: {int(report.get('candidate_count', 0) or 0)}",
        f"- deployable_count: {int(report.get('deployable_count', 0) or 0)}",
        "",
    ]

    if blocked_counts:
        lines.append("## Block Reasons")
        lines.append("")
        for key, val in sorted(blocked_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))):
            lines.append(f"- {key}: {int(val)}")
        lines.append("")

    if not rows:
        lines.append("No candidates found.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Candidates")
    lines.append("")
    lines.append("| deployable | config_id | score_v1 | pnl | dd_pct | trades | pf | replay_eq | block_reasons |")
    lines.append("| :--------- | :-------- | -------: | --: | -----: | -----: | --: | :-------- | :------------ |")
    for row in rows:
        reasons = row.get("gate_block_reasons", []) if isinstance(row.get("gate_block_reasons"), list) else []
        lines.append(
            "| {deployable} | `{config_id}` | {score} | {pnl:.4f} | {dd:.4f} | {trades} | {pf:.4f} | {replay} | {reasons} |".format(
                deployable="yes" if bool(row.get("deployable", False)) else "no",
                config_id=str(row.get("config_id", "") or "")[:12],
                score=_format_float(row.get("score_v1"), ndigits=4),
                pnl=float(row.get("total_pnl", 0.0) or 0.0),
                dd=float(row.get("max_drawdown_pct", 0.0) or 0.0) * 100.0,
                trades=int(row.get("total_trades", 0) or 0),
                pf=float(row.get("profit_factor", 0.0) or 0.0),
                replay=str(row.get("replay_equivalence_status", "") or ""),
                reasons=", ".join([str(r) for r in reasons]) if reasons else "",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _write_step5_gate_report(*, run_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "step5_gate_report.json"
    md_path = reports_dir / "step5_gate_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_step5_gate_report_markdown(report) + "\n", encoding="utf-8")
    return {"json_path": str(json_path), "md_path": str(md_path)}


def _select_best_candidate(items: list[dict[str, Any]], *, require_ssot_evidence: bool = True) -> Candidate | None:
    parsed = [c for c in (_parse_candidate(it) for it in items) if c is not None]
    parsed_ok = [c for c in parsed if not bool(c.rejected)]
    if not parsed_ok:
        return None

    # Prefer score_v1 when present. If score_v1 is missing for all candidates, fall back to total_pnl.
    any_score = any(c.score_v1 is not None for c in parsed_ok)
    filtered = [c for c in parsed_ok if _candidate_deployable(c, require_ssot_evidence=require_ssot_evidence)]
    if not filtered:
        return None
    parsed_ok = filtered
    if any_score:
        parsed_ok.sort(key=_candidate_sort_key_with_stage, reverse=True)
    else:
        parsed_ok.sort(key=lambda c: (int(_stage_rank(c)), float(c.total_pnl)), reverse=True)
    return parsed_ok[0]


def _select_deployable_candidates(
    parsed: list[Candidate], *, limit: int, require_ssot_evidence: bool = True
) -> list[Candidate]:
    if int(limit) <= 0:
        return []
    ok = [c for c in parsed if not bool(c.rejected)]
    if not ok:
        return []
    ok = [c for c in ok if _candidate_deployable(c, require_ssot_evidence=require_ssot_evidence)]
    if not ok:
        return []
    ok.sort(key=_candidate_sort_key_with_stage, reverse=True)
    return ok[: int(limit)]


def _resolve_deploy_targets(
    *,
    service: str,
    yaml_path: str,
    candidate_services: str,
    candidate_yaml_paths: str,
    candidate_count: int,
) -> list[DeployTarget]:
    services = _split_csv(candidate_services) or [str(service).strip()]
    yaml_raw = _split_csv(candidate_yaml_paths) or [str(yaml_path).strip()]
    if len(services) != len(yaml_raw):
        raise ValueError(
            f"candidate target mismatch: services={len(services)} yaml_paths={len(yaml_raw)}. "
            "Provide equal-length --candidate-services and --candidate-yaml-paths."
        )
    out: list[DeployTarget] = []
    for i, (svc, yp) in enumerate(zip(services, yaml_raw), start=1):
        out.append(
            DeployTarget(
                slot=int(i),
                service=str(svc).strip(),
                yaml_path=Path(str(yp)).expanduser().resolve(),
            )
        )
    lim = max(1, int(candidate_count))
    return out[:lim]


def _service_environment(service: str) -> dict[str, str]:
    raw = _systemctl_show_value(service=str(service), prop="Environment")
    out: dict[str, str] = {}
    for part in str(raw or "").split():
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = str(k or "").strip()
        if key and not _is_sensitive_env_key(key):
            out[key] = str(v or "")
    return out


def _normalise_promoted_role(raw: str) -> str:
    role = _norm_mode_key(raw)
    return role if role in _PROMOTION_ROLE_ORDER else ""


def _target_promoted_role(target: DeployTarget) -> str:
    env = _service_environment(str(target.service))
    for key in ("AI_QUANT_PROMOTED_ROLE", "AI_QUANT_STRATEGY_MODE"):
        role = _normalise_promoted_role(str(env.get(key, "") or ""))
        if role:
            return role
    return _DEFAULT_SLOT_ROLE.get(int(target.slot), "primary")


def _promotion_role_config_ids(run_meta: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    promotion = run_meta.get("promotion", {}) if isinstance(run_meta, dict) else {}
    roles = promotion.get("roles", {}) if isinstance(promotion, dict) else {}
    if not isinstance(roles, dict):
        return out
    for role_key, payload in roles.items():
        role = _normalise_promoted_role(str(role_key or ""))
        if not role:
            continue
        if not isinstance(payload, dict):
            continue
        cfg_id = str(payload.get("config_id", "") or "").strip()
        if cfg_id:
            out[role] = cfg_id
    return out


def _build_deploy_selection_plan(
    *,
    parsed: list[Candidate],
    run_meta: dict[str, Any],
    deploy_targets: list[DeployTarget],
    require_ssot_evidence: bool,
) -> tuple[str, list[Candidate], dict[int, Candidate], list[dict[str, Any]], list[str]]:
    ranked = _select_deployable_candidates(
        parsed,
        limit=max(1, len(parsed)),
        require_ssot_evidence=bool(require_ssot_evidence),
    )
    if not ranked:
        return ("none", [], {}, [], [])

    by_id: dict[str, Candidate] = {c.config_id: c for c in ranked}
    role_cfg_ids = _promotion_role_config_ids(run_meta)
    warnings: list[str] = []
    bindings: list[dict[str, Any]] = []
    slot_to_candidate: dict[int, Candidate] = {}
    selected: list[Candidate] = []

    if role_cfg_ids:
        for target in deploy_targets:
            role = _target_promoted_role(target)
            cfg_id = str(role_cfg_ids.get(role, "") or "").strip()
            cand = by_id.get(cfg_id) if cfg_id else None
            if cand is not None:
                slot_to_candidate[int(target.slot)] = cand
                selected.append(cand)
            else:
                if not cfg_id:
                    warnings.append(
                        f"missing promotion role mapping for slot={int(target.slot)} service={target.service} role={role}"
                    )
                else:
                    warnings.append(
                        f"promotion role config not deployable: slot={int(target.slot)} service={target.service} role={role} config={cfg_id[:12]}"
                    )
            bindings.append(
                {
                    "slot": int(target.slot),
                    "service": str(target.service),
                    "role": role,
                    "config_id": cfg_id or None,
                    "selected": bool(cand is not None),
                    "source": "promotion_roles",
                }
            )
        if slot_to_candidate:
            return ("promotion_roles_v1", selected, slot_to_candidate, bindings, warnings)

        warnings.append(
            "promotion role metadata exists but no slot resolved to deployable candidate; fallback to ranked deployables"
        )

    # Backward-compatible fallback for runs without promotion role metadata.
    for idx, target in enumerate(deploy_targets):
        if idx >= len(ranked):
            bindings.append(
                {
                    "slot": int(target.slot),
                    "service": str(target.service),
                    "role": _target_promoted_role(target),
                    "config_id": None,
                    "selected": False,
                    "source": "ranked_fallback",
                }
            )
            continue
        cand = ranked[idx]
        slot_to_candidate[int(target.slot)] = cand
        selected.append(cand)
        bindings.append(
            {
                "slot": int(target.slot),
                "service": str(target.service),
                "role": _target_promoted_role(target),
                "config_id": str(cand.config_id),
                "selected": True,
                "source": "ranked_fallback",
            }
        )
    return ("deployable_rank_v1", selected, slot_to_candidate, bindings, warnings)


def _parse_service_path_map(raw: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for part in _split_csv(raw):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = str(k or "").strip()
        val = str(v or "").strip()
        if not key or not val:
            continue
        out[key] = Path(val).expanduser().resolve()
    return out


def _paper_db_for_service(service: str, explicit: dict[str, Path]) -> Path | None:
    if service in explicit:
        return explicit[service]
    env = _service_environment(service)
    db_raw = str(env.get("AI_QUANT_DB_PATH", "") or "").strip()
    if not db_raw:
        return None
    return Path(db_raw).expanduser().resolve()


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


def _latest_paper_deploy_event_for_service(
    *,
    artifacts_dir: Path,
    service: str,
    before_epoch_s: float | None = None,
) -> dict[str, Any] | None:
    root = (Path(artifacts_dir) / "deployments" / "paper").expanduser().resolve()
    if not root.exists():
        return None
    events: list[dict[str, Any]] = []
    cutoff = float(before_epoch_s) if before_epoch_s is not None else None
    for ev_path in root.glob("**/deploy_event.json"):
        try:
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(ev, dict):
            continue
        rs = ev.get("restart", {}) if isinstance(ev.get("restart"), dict) else {}
        svc = str(rs.get("service", "") or "").strip()
        if svc != str(service).strip():
            continue
        ts = _parse_iso_to_epoch_s(str(ev.get("ts_utc", "") or ""))
        if ts is None:
            continue
        if cutoff is not None and float(ts) > cutoff:
            continue
        cfg = str(((ev.get("what") or {}).get("config_id") or "")).strip()
        events.append(
            {
                "event": ev,
                "path": str(ev_path),
                "ts_epoch_s": float(ts),
                "config_id": cfg,
            }
        )

    if not events:
        return None
    events.sort(key=lambda it: (float(it.get("ts_epoch_s", 0.0) or 0.0), str(it.get("path", ""))))
    return events[-1]


def _stable_promotion_since_s(
    *,
    artifacts_dir: Path,
    service: str,
    config_id: str,
    before_epoch_s: float | None = None,
) -> float | None:
    """Return a stable gate start for the latest contiguous deploy segment of service+config_id."""
    cfg = str(config_id or "").strip()
    if not cfg:
        return None
    root = (Path(artifacts_dir) / "deployments" / "paper").expanduser().resolve()
    if not root.exists():
        return None

    events: list[dict[str, Any]] = []
    cutoff = float(before_epoch_s) if before_epoch_s is not None else None
    for ev_path in root.glob("**/deploy_event.json"):
        try:
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(ev, dict):
            continue
        rs = ev.get("restart", {}) if isinstance(ev.get("restart"), dict) else {}
        svc = str(rs.get("service", "") or "").strip()
        if svc != str(service).strip():
            continue
        cfg_id = str(((ev.get("what") or {}).get("config_id") or "")).strip()
        ts = _parse_iso_to_epoch_s(str(ev.get("ts_utc", "") or ""))
        if ts is None:
            continue
        if cutoff is not None and float(ts) > cutoff:
            continue
        events.append(
            {
                "ts_epoch_s": float(ts),
                "config_id": str(cfg_id),
                "path": str(ev_path),
            }
        )

    if not events:
        return None

    events.sort(key=lambda it: (float(it.get("ts_epoch_s", 0.0) or 0.0), str(it.get("path", ""))))

    last_idx: int | None = None
    for i in range(len(events) - 1, -1, -1):
        if str(events[i].get("config_id", "")).strip() == cfg:
            last_idx = i
            break
    if last_idx is None:
        return None

    start_idx = int(last_idx)
    while start_idx > 0:
        prev_cfg = str(events[start_idx - 1].get("config_id", "")).strip()
        if prev_cfg != cfg:
            break
        start_idx -= 1

    try:
        return float(events[start_idx].get("ts_epoch_s", 0.0) or 0.0)
    except Exception:
        return None


def _promotion_rank_key(item: dict[str, Any]) -> tuple[float, float, float]:
    m = item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {}
    pf = float(m.get("profit_factor", 0.0) or 0.0)
    close_n = float(m.get("close_trades", 0) or 0)
    elapsed_h = float(m.get("elapsed_h", 0.0) or 0.0)
    return (pf, close_n, elapsed_h)


def _compare_candidate_vs_incumbent(
    *,
    candidate: dict[str, Any],
    incumbent: dict[str, Any],
    min_pf_delta: float,
    max_dd_regression_pct: float,
) -> tuple[bool, list[str]]:
    cand_m = candidate.get("metrics", {}) if isinstance(candidate.get("metrics"), dict) else {}
    inc_m = incumbent.get("metrics", {}) if isinstance(incumbent.get("metrics"), dict) else {}

    cand_pf = float(cand_m.get("profit_factor", 0.0) or 0.0)
    inc_pf = float(inc_m.get("profit_factor", 0.0) or 0.0)
    cand_dd = float(cand_m.get("max_drawdown_pct", 0.0) or 0.0)
    inc_dd = float(inc_m.get("max_drawdown_pct", 0.0) or 0.0)
    cand_kill = int(cand_m.get("kill_events", 0) or 0)
    inc_kill = int(inc_m.get("kill_events", 0) or 0)

    reasons: list[str] = []
    if cand_pf + 1e-9 < (inc_pf + float(min_pf_delta)):
        reasons.append(f"profit_factor regression: cand={cand_pf:.3f} < inc+delta={inc_pf + float(min_pf_delta):.3f}")
    if (cand_dd - inc_dd) > float(max_dd_regression_pct):
        reasons.append(
            f"drawdown regression: cand={cand_dd:.3f}% > inc+tol={inc_dd + float(max_dd_regression_pct):.3f}%"
        )
    if cand_kill > inc_kill:
        reasons.append(f"kill_events regression: cand={cand_kill} > inc={inc_kill}")
    return (not reasons, reasons)


def _restart_summary_from_deploy_event(deploy_event_path: Path) -> tuple[str, list[str]]:
    restart_summary = "unknown"
    restart_details: list[str] = []
    if not deploy_event_path.exists():
        return (restart_summary, restart_details)
    try:
        ev = json.loads(deploy_event_path.read_text(encoding="utf-8"))
        rs = ev.get("restart", {}) if isinstance(ev, dict) else {}
        rr = rs.get("result", {}) if isinstance(rs, dict) else {}
        results = rr.get("results", []) if isinstance(rr, dict) else []
        restart_mode = str(rs.get("mode", "unknown") or "unknown")
        restart_summary = f"mode={restart_mode}"
        if isinstance(results, list) and results:
            ok_cnt = 0
            for r in results:
                if not isinstance(r, dict):
                    continue
                svc = str(r.get("service", "unknown") or "unknown")
                ok = bool(r.get("ok", False))
                if ok:
                    ok_cnt += 1
                restart_details.append(f"- restart {svc}: {'ok' if ok else 'fail'}")
            restart_summary += f" results_ok={ok_cnt}/{len(results)}"
        else:
            restart_summary += " results=n/a"
    except Exception:
        restart_summary = "parse_failed"
    return (restart_summary, restart_details)


def _query_run_dir(*, registry_db: Path, run_id: str) -> Path:
    con = sqlite3.connect(str(registry_db), timeout=2.0)
    try:
        row = con.execute("SELECT run_dir FROM runs WHERE run_id = ? LIMIT 1", (str(run_id),)).fetchone()
        if not row:
            raise FileNotFoundError(f"run_id not found in registry: {run_id}")
        run_dir = str(row[0] or "").strip()
        if not run_dir:
            raise FileNotFoundError(f"run_dir missing in registry for run_id: {run_id}")
        return Path(run_dir).expanduser().resolve()
    finally:
        con.close()


def _mark_deployed(*, registry_db: Path, run_id: str, config_id: str) -> None:
    con = sqlite3.connect(str(registry_db), timeout=2.0)
    try:
        with con:
            con.execute(
                "UPDATE run_configs SET deployed = 1 WHERE run_id = ? AND config_id = ?",
                (str(run_id), str(config_id)),
            )
    finally:
        con.close()


def _send_discord(*, target: str, message: str) -> None:
    tgt = str(target or "").strip()
    msg = str(message or "").strip()
    if not tgt or not msg:
        return
    try:
        timeout_s = float(os.getenv("AI_QUANT_DISCORD_SEND_TIMEOUT_S", "6") or 6)
    except Exception:
        timeout_s = 6.0
    timeout_s = max(1.0, min(30.0, timeout_s))
    try:
        send_openclaw_message(channel="discord", target=tgt, message=msg, timeout_s=timeout_s)
    except Exception:
        # Notifications must never block the pipeline.
        return


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run factory_run and optionally auto-deploy the best config to paper.")
    ap.add_argument("--run-id", default="", help="Run id (default: nightly_<UTC timestamp>).")
    ap.add_argument(
        "--profile",
        default="daily",
        choices=sorted(factory_run.PROFILE_DEFAULTS.keys()),
        help="Factory profile for trials/candidates (default: daily).",
    )
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root (default: artifacts).")
    ap.add_argument("--config", default="config/strategy_overrides.yaml", help="Base strategy YAML config path.")
    ap.add_argument(
        "--strategy-mode",
        default="",
        help="Optional modes.<mode> overlay to materialise into global for this run (e.g. primary, fallback).",
    )

    ap.add_argument("--sweep-spec", default="backtester/sweeps/full_144v.yaml", help="Sweep spec YAML path.")
    ap.add_argument("--interval", default="", help="Main interval for sweep/replay (default: from effective YAML).")
    ap.add_argument(
        "--start-ts",
        default="",
        help="Backtest window start timestamp (forwarded to factory_run / mei-backtester).",
    )
    ap.add_argument(
        "--end-ts",
        default="",
        help="Backtest window end timestamp (forwarded to factory_run / mei-backtester).",
    )
    ap.add_argument("--candles-db", default="candles_dbs", help="Candle DB path (dir or glob).")
    ap.add_argument("--funding-db", default="candles_dbs/funding_rates.db", help="Funding DB path.")
    ap.add_argument(
        "--max-age-fail-hours",
        type=float,
        default=_env_float("AI_QUANT_FUNDING_MAX_AGE_FAIL_HOURS"),
        help="Override checker fail-age threshold (hours) for stale funding symbols.",
    )
    ap.add_argument(
        "--funding-max-stale-symbols",
        type=int,
        default=_env_int("AI_QUANT_FUNDING_MAX_STALE_SYMBOLS", default=0),
        help="Allow this many stale symbols to continue as WARN instead of FAIL.",
    )

    ap.add_argument("--gpu", action="store_true", help="Use GPU sweep (requires CUDA build/runtime).")
    ap.add_argument("--tpe", action="store_true", help="Use TPE Bayesian optimisation for GPU sweeps (requires --gpu).")
    ap.add_argument(
        "--sweep-parity-mode",
        default="production",
        choices=["production", "identical-symbol-universe"],
        help="Sweep parity mode passed to mei-backtester sweep (default: production).",
    )

    # Step-4 GPU↔CPU parity report / gate (forwarded to factory_run)
    ap.set_defaults(step4_parity=True)
    ap.add_argument(
        "--no-step4-parity",
        dest="step4_parity",
        action="store_false",
        help="Disable Step-4 GPU↔CPU parity report generation.",
    )
    ap.add_argument(
        "--step4-parity-enforce",
        action="store_true",
        help="Fail the run when Step-4 GPU↔CPU parity mismatches are detected.",
    )
    ap.add_argument(
        "--step4-parity-rel-eps",
        type=float,
        default=1e-6,
        help="Relative epsilon for Step-4 parity (default: 1e-6).",
    )
    ap.add_argument(
        "--step4-parity-abs-eps",
        type=float,
        default=1e-3,
        help="Absolute epsilon for Step-4 parity (default: 1e-3).",
    )
    ap.add_argument(
        "--step4-parity-dd-eps",
        type=float,
        default=1e-6,
        help="Max drawdown pct epsilon for Step-4 parity (default: 1e-6).",
    )
    ap.add_argument(
        "--step4-parity-pf-eps",
        type=float,
        default=1e-4,
        help="Profit factor epsilon for Step-4 parity (default: 1e-4).",
    )
    ap.add_argument("--tpe-batch", type=int, default=256, help="TPE batch size (trials per GPU batch, default: 256).")
    ap.add_argument("--tpe-seed", type=int, default=None, help="TPE RNG seed (default: from profile).")
    ap.add_argument(
        "--allow-unsafe-gpu-sweep",
        action="store_true",
        default=_env_bool("AI_QUANT_FACTORY_ALLOW_UNSAFE_GPU_SWEEP", default=True),
        help="Allow unsafe long-window GPU sweeps (required by daily+tpe on most environments).",
    )
    ap.add_argument(
        "--fallback-to-cpu-on-no-gpu",
        action="store_true",
        default=_env_bool("AI_QUANT_FALLBACK_TO_CPU_ON_NO_GPU", default=True),
        help="Fallback to CPU sweep if no usable GPU is detected.",
    )
    ap.add_argument("--walk-forward", action="store_true", help="Enable walk-forward validation.")
    ap.add_argument("--slippage-stress", action="store_true", help="Enable slippage stress validation.")
    ap.add_argument("--concentration-checks", action="store_true", help="Enable concentration checks.")
    ap.add_argument("--sensitivity-checks", action="store_true", help="Enable sensitivity checks.")
    ap.add_argument(
        "--resume", action="store_true", help="Resume an existing run-id from artifacts (factory_run --resume)."
    )
    ap.add_argument(
        "--allow-binary-drift",
        action="store_true",
        help="Allow resume even if backtester command/binary fingerprint differs (factory_run --allow-binary-drift).",
    )
    ap.add_argument(
        "--allow-input-drift",
        action="store_true",
        help="Allow resume even if candles/funding input fingerprints differ (factory_run --allow-input-drift).",
    )
    ap.add_argument(
        "--require-ssot-evidence",
        dest="require_ssot_evidence",
        action="store_true",
        help="Require candidate proof metadata before deployment/promotion.",
    )
    ap.add_argument(
        "--no-require-ssot-evidence",
        dest="require_ssot_evidence",
        action="store_false",
        help="Allow deployment/promotion using non-proof candidates (legacy/testing only).",
    )
    ap.set_defaults(require_ssot_evidence=_env_bool("AI_QUANT_REQUIRE_SSOT_EVIDENCE", default=True))

    ap.add_argument("--no-deploy", action="store_true", help="Run factory only; do not deploy.")
    ap.add_argument(
        "--yaml-path",
        default=str(AIQ_ROOT / "config" / "strategy_overrides.yaml"),
        help="Target strategy overrides YAML path for deployment (default: config/strategy_overrides.yaml).",
    )
    ap.add_argument(
        "--candidate-services",
        default="",
        help=("Optional CSV service list for top-N candidate deployment (e.g. svc_paper1,svc_paper2,svc_paper3)."),
    )
    ap.add_argument(
        "--candidate-yaml-paths",
        default="",
        help=(
            "Optional CSV YAML path list for top-N candidate deployment (same length/order as --candidate-services)."
        ),
    )
    ap.add_argument(
        "--candidate-count",
        type=int,
        default=1,
        help="Maximum number of deployable candidates to deploy each cycle (default: 1).",
    )
    ap.add_argument("--deploy-reason", default="", help="Reason recorded in the paper deploy artefact.")
    ap.add_argument(
        "--restart",
        default="auto",
        choices=["auto", "always", "never"],
        help="Restart policy for deployment (default: auto).",
    )
    ap.add_argument("--service", default="openclaw-ai-quant-trader", help="systemd user service name for paper trader.")
    ap.add_argument(
        "--ws-service", default="openclaw-ai-quant-ws-sidecar", help="systemd user service name for WS sidecar."
    )
    ap.add_argument("--pause-file", default="", help="Optional kill-switch file path to pause trading during restart.")
    ap.add_argument(
        "--pause-mode",
        default="close_only",
        choices=["close_only", "halt_all"],
        help="Pause mode to write into pause file (default: close_only).",
    )
    ap.add_argument(
        "--leave-paused", action="store_true", help="Do not clear the pause file after a successful restart."
    )
    ap.add_argument(
        "--verify-sleep-s", type=float, default=2.0, help="Seconds to wait before verifying service health."
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Do not modify YAML or restart services; still runs factory."
    )
    ap.add_argument(
        "--enable-livepaper-promotion",
        action="store_true",
        help="Enable gate-based promotion from paper candidate services to livepaper service.",
    )
    ap.add_argument(
        "--livepaper-service",
        default="",
        help="systemd user service name for livepaper promotion target (required when promotion is enabled).",
    )
    ap.add_argument(
        "--livepaper-yaml-path",
        default="",
        help="YAML path for livepaper promotion target (required when promotion is enabled).",
    )
    ap.add_argument(
        "--paper-db-map",
        default="",
        help="Optional CSV service=paper_db_path mapping for promotion gates.",
    )
    ap.add_argument("--promotion-min-trades", type=int, default=20, help="Gate: minimum CLOSE trades OR min-hours.")
    ap.add_argument(
        "--promotion-min-hours", type=float, default=24.0, help="Gate: minimum runtime hours OR min-trades."
    )
    ap.add_argument("--promotion-min-profit-factor", type=float, default=1.2, help="Gate: minimum paper profit factor.")
    ap.add_argument(
        "--promotion-max-drawdown-pct", type=float, default=10.0, help="Gate: maximum paper drawdown percent."
    )
    ap.add_argument(
        "--promotion-max-config-slippage-bps",
        type=float,
        default=20.0,
        help="Gate: maximum config trade.slippage_bps (<=0 disables this gate).",
    )
    ap.add_argument(
        "--promotion-max-kill-events",
        type=int,
        default=0,
        help="Gate: maximum allowed RISK_KILL* events during paper window.",
    )
    ap.add_argument(
        "--promotion-ignore-live-comparison",
        action="store_true",
        help="Disable incumbent comparison guard (default: require candidate not worse than current livepaper).",
    )
    ap.add_argument(
        "--promotion-min-pf-delta",
        type=float,
        default=0.0,
        help="Incumbent guard: candidate profit_factor must be >= incumbent + this delta.",
    )
    ap.add_argument(
        "--promotion-max-dd-regression-pct",
        type=float,
        default=0.0,
        help="Incumbent guard: candidate drawdown may exceed incumbent by at most this percentage-point tolerance.",
    )
    ap.add_argument(
        "--mirror-source",
        default="/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db",
        help="Source DB for state mirroring during promotion (default: .../trading_engine_live.db).",
    )
    ap.add_argument(
        "--skip-mirror",
        action="store_true",
        help="Force skip state mirroring when deploying a changed config.",
    )

    ap.add_argument(
        "--discord-target",
        default="",
        help="Optional Discord target to notify (uses `openclaw message send`).",
    )
    args = ap.parse_args(argv)

    run_id = str(args.run_id).strip() or f"nightly_{_utc_compact()}"
    artifacts_dir = Path(str(args.artifacts_dir)).expanduser().resolve()

    # ── Guard: skip if a successful cycle already completed for today + profile ──
    _today_utc = time.strftime("%Y-%m-%d", time.gmtime())
    _profile_tag = str(args.profile or "daily").strip()
    _done_marker = artifacts_dir / _today_utc / f".factory_done.{_profile_tag}"
    if _done_marker.is_file() and not bool(args.resume):
        _prev_run_id = _done_marker.read_text(encoding="utf-8").strip()
        print(
            f"✅ Factory cycle already completed for {_today_utc} "
            f"(profile={_profile_tag}, run={_prev_run_id}). Skipping.",
            flush=True,
        )
        return 0
    # ─────────────────────────────────────────────────────────────────────────────

    def _write_done_marker(rid: str = "") -> None:
        try:
            _done_marker.parent.mkdir(parents=True, exist_ok=True)
            _done_marker.write_text((rid or run_id) + "\n", encoding="utf-8")
        except Exception:
            pass

    base_cfg_path = Path(str(args.config)).expanduser().resolve()
    deploy_targets = _resolve_deploy_targets(
        service=str(args.service),
        yaml_path=str(args.yaml_path),
        candidate_services=str(args.candidate_services),
        candidate_yaml_paths=str(args.candidate_yaml_paths),
        candidate_count=int(args.candidate_count),
    )

    # Materialise strategy-mode overlay into an effective base YAML (required for Rust backtester parity).
    effective_cfg_path = base_cfg_path
    if str(args.strategy_mode or "").strip():
        base_obj = _read_yaml(base_cfg_path)
        eff_obj = _apply_strategy_mode_overlay(base=base_obj, strategy_mode=str(args.strategy_mode))
        out_dir = (artifacts_dir / "_effective_configs").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        effective_cfg_path = (out_dir / f"{run_id}.yaml").resolve()
        effective_cfg_path.write_text(yaml.safe_dump(eff_obj, sort_keys=False) + "\n", encoding="utf-8")

    # Default interval comes from YAML if not provided explicitly.
    interval = str(args.interval).strip()
    if not interval:
        try:
            eff_obj2 = _read_yaml(effective_cfg_path)
            interval = _yaml_engine_interval(eff_obj2) or "30m"
        except Exception:
            interval = "30m"

    run_with_gpu = bool(args.gpu)
    run_with_tpe = bool(args.tpe)
    fallback_to_cpu_on_no_gpu = bool(args.fallback_to_cpu_on_no_gpu)
    if run_with_gpu and fallback_to_cpu_on_no_gpu and not _nvidia_gpu_available():
        run_with_gpu = False
        run_with_tpe = False
        _send_discord(
            target=str(args.discord_target),
            message="⚠️ Factory WARN • GPU not usable; fallback to CPU sweep for this cycle.",
        )

    def _read_metadata(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    resume_run_args: dict[str, Any] = {}
    if bool(args.resume):
        _resume_meta_path: Path | None = None
        try:
            _registry_db = default_registry_db_path(artifacts_root=artifacts_dir)
            _run_dir = _query_run_dir(registry_db=_registry_db, run_id=run_id)
            _resume_meta_path = (_run_dir / "run_metadata.json").resolve()
        except Exception:
            _resume_meta_path = None

        # Registry may be stale/missing; fallback to deterministic artifacts lookup.
        if _resume_meta_path is None or not _resume_meta_path.is_file():
            probe_paths: list[Path] = [
                (artifacts_dir / run_id / "run_metadata.json").resolve(),
                (artifacts_dir / f"run_{run_id}" / "run_metadata.json").resolve(),
            ]
            try:
                dated_dirs = sorted(
                    [p for p in artifacts_dir.iterdir() if p.is_dir() and p.name.count("-") == 2], reverse=True
                )
            except Exception:
                dated_dirs = []
            for d in dated_dirs:
                probe_paths.append((d / run_id / "run_metadata.json").resolve())
                probe_paths.append((d / f"run_{run_id}" / "run_metadata.json").resolve())
            for candidate in probe_paths:
                if candidate.is_file():
                    _resume_meta_path = candidate
                    break

        if _resume_meta_path is not None and _resume_meta_path.is_file():
            _resume_meta = _read_metadata(_resume_meta_path)
            if isinstance(_resume_meta.get("orig_args"), dict):
                resume_run_args = dict(_resume_meta.get("orig_args") or {})
            elif isinstance(_resume_meta.get("args"), dict):
                resume_run_args = dict(_resume_meta.get("args") or {})

    factory_argv: list[str] = [
        "--run-id",
        run_id,
        "--profile",
        str(args.profile),
        "--artifacts-dir",
        str(artifacts_dir),
        "--config",
        str(effective_cfg_path),
        "--interval",
        str(interval),
        "--candles-db",
        str(args.candles_db),
        "--funding-db",
        str(args.funding_db),
    ]
    if args.max_age_fail_hours is not None:
        factory_argv += ["--max-age-fail-hours", str(float(args.max_age_fail_hours))]
    if args.funding_max_stale_symbols is not None and int(args.funding_max_stale_symbols) > 0:
        factory_argv += ["--funding-max-stale-symbols", str(int(args.funding_max_stale_symbols))]
    factory_argv += [
        "--sweep-spec",
        str(args.sweep_spec),
    ]
    if bool(args.resume):
        factory_argv.append("--resume")
        if bool(getattr(args, "allow_binary_drift", False)):
            factory_argv.append("--allow-binary-drift")
        if bool(getattr(args, "allow_input_drift", False)):
            factory_argv.append("--allow-input-drift")

        # Rehydrate shortlist knobs from the resumed run so factory_run --resume
        # guard keys remain reproducible across default changes.
        if "shortlist_modes" in resume_run_args and resume_run_args.get("shortlist_modes") is not None:
            factory_argv += ["--shortlist-modes", str(resume_run_args.get("shortlist_modes") or "")]
        if "shortlist_per_mode" in resume_run_args and resume_run_args.get("shortlist_per_mode") is not None:
            try:
                _shortlist_per_mode = int(resume_run_args.get("shortlist_per_mode"))
                factory_argv += ["--shortlist-per-mode", str(_shortlist_per_mode)]
            except Exception:
                pass
        if "shortlist_max_rank" in resume_run_args and resume_run_args.get("shortlist_max_rank") is not None:
            try:
                _shortlist_max_rank = int(resume_run_args.get("shortlist_max_rank"))
                factory_argv += ["--shortlist-max-rank", str(_shortlist_max_rank)]
            except Exception:
                pass
        if "shortlist_top_pnl" in resume_run_args and resume_run_args.get("shortlist_top_pnl") is not None:
            try:
                _shortlist_top_pnl = int(resume_run_args.get("shortlist_top_pnl"))
                factory_argv += ["--shortlist-top-pnl", str(_shortlist_top_pnl)]
            except Exception:
                pass

        # Rehydrate sweep window + parity mode (also guard-keyed in factory_run).
        _start_ts = str(resume_run_args.get("start_ts", "") or "").strip()
        _end_ts = str(resume_run_args.get("end_ts", "") or "").strip()
        _parity_mode = str(resume_run_args.get("sweep_parity_mode", "production") or "production").strip()
        if _start_ts:
            factory_argv += ["--start-ts", _start_ts]
        if _end_ts:
            factory_argv += ["--end-ts", _end_ts]
        if _parity_mode:
            factory_argv += ["--sweep-parity-mode", _parity_mode]
    else:
        _start_ts = str(getattr(args, "start_ts", "") or "").strip()
        _end_ts = str(getattr(args, "end_ts", "") or "").strip()
        _parity_mode = str(getattr(args, "sweep_parity_mode", "production") or "production").strip()
        if _start_ts:
            factory_argv += ["--start-ts", _start_ts]
        if _end_ts:
            factory_argv += ["--end-ts", _end_ts]
        if _parity_mode:
            factory_argv += ["--sweep-parity-mode", _parity_mode]

    # Forward Step-4 parity report / gate flags.
    if not bool(getattr(args, "step4_parity", True)):
        factory_argv.append("--no-step4-parity")
    if bool(getattr(args, "step4_parity_enforce", False)):
        factory_argv.append("--step4-parity-enforce")
    factory_argv += [
        "--step4-parity-rel-eps",
        str(float(getattr(args, "step4_parity_rel_eps", 1e-6) or 1e-6)),
        "--step4-parity-abs-eps",
        str(float(getattr(args, "step4_parity_abs_eps", 1e-3) or 1e-3)),
        "--step4-parity-dd-eps",
        str(float(getattr(args, "step4_parity_dd_eps", 1e-6) or 1e-6)),
        "--step4-parity-pf-eps",
        str(float(getattr(args, "step4_parity_pf_eps", 1e-4) or 1e-4)),
    ]
    if bool(run_with_gpu):
        factory_argv.append("--gpu")
    if bool(run_with_tpe):
        factory_argv.append("--tpe")
        if args.tpe_batch:
            factory_argv += ["--tpe-batch", str(int(args.tpe_batch))]
        if args.tpe_seed is not None:
            factory_argv += ["--tpe-seed", str(int(args.tpe_seed))]
    if bool(args.allow_unsafe_gpu_sweep):
        factory_argv.append("--allow-unsafe-gpu-sweep")
    if bool(args.walk_forward):
        factory_argv.append("--walk-forward")
    if bool(args.slippage_stress):
        factory_argv.append("--slippage-stress")
    if bool(args.concentration_checks):
        factory_argv.append("--concentration-checks")
    if bool(args.sensitivity_checks):
        factory_argv.append("--sensitivity-checks")

    _send_discord_chunks(
        target=str(args.discord_target),
        lines=[
            f"🧪 Factory START • `{run_id}`",
            f"`profile` {args.profile}  `mode` {str(args.strategy_mode or 'none').strip() or 'none'}  `interval` {interval}",
            f"`gpu/tpe/wf` {int(bool(run_with_gpu))}/{int(bool(run_with_tpe))}/{int(bool(args.walk_forward))}",
            (
                "`checks` stress="
                f"{int(bool(args.slippage_stress))} concentration={int(bool(args.concentration_checks))} "
                f"sensitivity={int(bool(args.sensitivity_checks))} resume={int(bool(args.resume))}"
            ),
            f"`data` candles={_short_path(str(args.candles_db), parts=4)} funding={_short_path(str(args.funding_db), parts=4)}",
            f"`funding` fail_age={_format_float(args.max_age_fail_hours, default='n/a', ndigits=1)} "
            f"stale_allow={_format_float(args.funding_max_stale_symbols, default='0', ndigits=0)}",
            f"`deploy` ws={args.ws_service} restart={args.restart}",
            f"`paper targets` {', '.join([t.service for t in deploy_targets]) or 'none'}",
            (
                f"`live promotion` enabled={int(bool(args.enable_livepaper_promotion))} "
                f"live_service={str(args.livepaper_service or '').strip() or 'n/a'} "
                f"live_yaml={_short_path(str(args.livepaper_yaml_path or ''), parts=4)}"
            ),
            (
                f"`live guard` enabled={int(not bool(args.promotion_ignore_live_comparison))} "
                f"min_pf_delta={_format_float(args.promotion_min_pf_delta, ndigits=3)} "
                f"max_dd_regress={_format_float(args.promotion_max_dd_regression_pct, ndigits=3)}%"
            ),
        ],
    )

    rc = int(factory_run.main(factory_argv))
    if rc != 0:
        _send_discord(
            target=str(args.discord_target),
            message=f"❌ Factory FAILED • `{run_id}`  exit={rc}  (check logs/artifacts)",
        )
        return rc

    registry_db = default_registry_db_path(artifacts_root=artifacts_dir)
    run_dir = _query_run_dir(registry_db=registry_db, run_id=run_id)
    run_meta = _read_metadata(run_dir / "run_metadata.json")
    funding_signal = run_meta.get("funding_check_degraded")
    if isinstance(funding_signal, dict) and str(funding_signal.get("status") or "") == "warn":
        symbols = ",".join([str(s) for s in funding_signal.get("symbols", []) if str(s).strip()])
        _send_discord(
            target=str(args.discord_target),
            message=(
                f"⚠️ Factory WARN (funding data) • `{run_id}`  "
                f"symbols={symbols or 'stale'}  allowed={funding_signal.get('allowed_symbols', 0)}"
            ),
        )
    report_path = run_dir / "reports" / "report.json"
    rep = json.loads(report_path.read_text(encoding="utf-8"))
    items = rep.get("items", []) if isinstance(rep, dict) else []
    if not isinstance(items, list):
        items = []

    parsed = [c for c in (_parse_candidate(it) for it in items) if c is not None]
    for lines in _build_candidates_messages(run_id=run_id, parsed=parsed):
        _send_discord_chunks(target=str(args.discord_target), lines=lines)

    (
        selection_policy,
        deployable_selected,
        deployable_by_slot,
        deploy_role_bindings,
        deploy_selection_warnings,
    ) = _build_deploy_selection_plan(
        parsed=parsed,
        run_meta=run_meta,
        deploy_targets=deploy_targets,
        require_ssot_evidence=bool(args.require_ssot_evidence),
    )
    for warn in deploy_selection_warnings:
        _send_discord(
            target=str(args.discord_target),
            message=f"⚠️ Selection WARN • `{run_id}` {warn}",
        )

    selected_primary: Candidate | None = None
    if deploy_targets:
        selected_primary = deployable_by_slot.get(int(deploy_targets[0].slot))
    if selected_primary is None and deployable_selected:
        selected_primary = deployable_selected[0]

    blocked_reason = ""
    if not deployable_by_slot:
        blocked_reason = "no_deployable_candidate"
    elif selected_primary is None:
        blocked_reason = "selection_primary_missing"

    step5_report = _build_step5_gate_report(
        run_id=run_id,
        parsed=parsed,
        require_ssot_evidence=bool(args.require_ssot_evidence),
        selection_policy=str(selection_policy),
        deployable_selected=deployable_selected,
        deployable_by_slot=deployable_by_slot,
        deploy_targets=deploy_targets,
        selection_warnings=deploy_selection_warnings,
        blocked_reason=blocked_reason,
    )
    step5_paths = _write_step5_gate_report(run_dir=run_dir, report=step5_report)

    selected_payload = selected_primary.__dict__ if selected_primary is not None else {}
    selection_stage = "selected" if selected_primary is not None else "blocked"
    selection = {
        "version": "factory_cycle_selection_v1",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "evidence_bundle_paths": {
            "run_dir": str(run_dir),
            "run_metadata_json": str(run_dir / "run_metadata.json"),
            "selection_json": str(run_dir / "reports" / "selection.json"),
            "report_json": str(run_dir / "reports" / "report.json"),
            "report_md": str(run_dir / "reports" / "report.md"),
            "selection_md": str(run_dir / "reports" / "selection.md"),
            "step5_gate_report_json": str(step5_paths.get("json_path", "")),
            "step5_gate_report_md": str(step5_paths.get("md_path", "")),
            "configs_dir": str(run_dir / "configs"),
            "replays_dir": str(run_dir / "replays"),
        },
        "selection_policy": str(selection_policy),
        "selection_warnings": list(deploy_selection_warnings),
        "selected": selected_payload,
        "selected_candidates": [c.__dict__ for c in deployable_selected],
        "selected_candidates_by_role": deploy_role_bindings,
        "selected_targets": [
            {"slot": t.slot, "service": t.service, "yaml_path": str(t.yaml_path)} for t in deploy_targets
        ],
        "selection_stage": selection_stage,
        "deploy_stage": "pending",
        "promotion_stage": "pending",
        "step5_gate_status": "blocked" if blocked_reason else "passed",
        "step5_gate_block_reason": blocked_reason,
        "effective_config_path": str(effective_cfg_path),
        "interval": str(interval),
        "deployed": False,
        "deployments": [],
    }
    # Keep a stable promotion reference point so promotion gates evaluate the incumbent
    # paper windows before this cycle's deploy writes new deploy_event rows.
    promotion_reference_epoch_s = float(time.time())
    selection["promotion_reference_epoch_s"] = float(promotion_reference_epoch_s)
    (run_dir / "reports" / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if blocked_reason:
        if blocked_reason == "no_deployable_candidate":
            _send_discord(
                target=str(args.discord_target),
                message=(
                    f"⚠️ Factory OK • `{run_id}` but no deployable candidates (Step-5 blocked). "
                    f"`report` {step5_paths.get('json_path', 'n/a')}"
                ),
            )
        else:
            _send_discord(
                target=str(args.discord_target),
                message=(
                    f"⚠️ Factory OK • `{run_id}` but selection produced no deployable primary candidate. "
                    f"`report` {step5_paths.get('json_path', 'n/a')}"
                ),
            )
        selection["deploy_stage"] = "blocked"
        selection["promotion_stage"] = "skipped"
        (run_dir / "reports" / "selection.json").write_text(
            json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_selection_markdown(run_dir=run_dir, selection=selection)
        _write_done_marker()
        return 0

    if bool(args.no_deploy):
        _send_discord(
            target=str(args.discord_target),
            message=(
                f"✅ Factory OK (no-deploy) • `{run_id}` "
                f"`selected` {','.join([str(c.config_id)[:12] for c in deployable_selected[: len(deploy_targets)]])}"
            ),
        )
        selection["deploy_stage"] = "no_deploy"
        selection["promotion_stage"] = "skipped"
        (run_dir / "reports" / "selection.json").write_text(
            json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_selection_markdown(run_dir=run_dir, selection=selection)
        _write_done_marker()
        return 0

    pause_file = Path(args.pause_file).expanduser().resolve() if str(args.pause_file).strip() else None
    reason_base = str(args.deploy_reason).strip() or f"auto factory_cycle run_id={run_id} profile={args.profile}"

    deployments: list[dict[str, Any]] = []
    deployed_any = False
    for i, target in enumerate(deploy_targets):
        cand = deployable_by_slot.get(int(target.slot))
        if cand is None:
            deployments.append(
                {
                    "slot": int(target.slot),
                    "service": str(target.service),
                    "yaml_path": str(target.yaml_path),
                    "status": "skipped",
                    "reason": "no_deployable_candidate",
                }
            )
            continue

        prev_yaml_text = target.yaml_path.read_text(encoding="utf-8") if target.yaml_path.exists() else ""
        prev_cfg_id = _yaml_config_id(prev_yaml_text)
        next_yaml_text = Path(cand.config_path).expanduser().resolve().read_text(encoding="utf-8")
        changed_cfg = str(prev_cfg_id) != str(cand.config_id)
        prev_summary = _yaml_summary(prev_yaml_text)
        next_summary = _yaml_summary(next_yaml_text)
        diff_lines = _diff_yaml_summaries(prev_summary, next_summary)
        selection_lines = [
            f"🎯 Selection • `{run_id}` • slot={target.slot}",
            (f"`target` {target.service}  `rank` {i + 1}/{len(deploy_targets)}"),
            (
                f"`config` `{cand.config_id[:12]}`  "
                f"`pf` {_format_float(cand.profit_factor, ndigits=3)}  "
                f"`dd` {_format_float(cand.max_drawdown_pct * 100.0, ndigits=2)}%  "
                f"`pnl` {_format_float(cand.total_pnl, ndigits=2)}  "
                f"`trades` {cand.total_trades}  "
                f"`score` {_format_float(cand.score_v1, ndigits=4)}"
            ),
            f"`previous` `{prev_cfg_id[:12] if prev_cfg_id else 'none'}`  `yaml` {_short_path(str(target.yaml_path), parts=4)}",
        ]
        if diff_lines:
            selection_lines.append("Key parameter changes:")
            selection_lines.extend(diff_lines[:8])
        else:
            selection_lines.append("Key parameter changes: none")
        _send_discord_chunks(target=str(args.discord_target), lines=selection_lines)

        out_dir = (
            artifacts_dir / "deployments" / "paper" / str(target.service) / f"{_utc_compact()}_{cand.config_id[:12]}"
        ).resolve()
        reason = f"{reason_base}; slot={target.slot}; target={target.service}; rank={i + 1}; policy={selection_policy}; config={cand.config_id[:12]}"
        try:
            deploy_dir = deploy_paper_config(
                config_id=str(cand.config_id),
                artifacts_dir=artifacts_dir,
                yaml_path=target.yaml_path,
                out_dir=out_dir,
                reason=reason,
                restart=str(args.restart),
                service=str(target.service),
                dry_run=bool(args.dry_run),
                validate=True,
                ws_service=str(args.ws_service),
                pause_file=pause_file,
                pause_mode=str(args.pause_mode),
                resume_on_success=not bool(args.leave_paused),
                verify_sleep_s=float(args.verify_sleep_s),
                mirror_source=str(args.mirror_source),
                skip_mirror=bool(args.skip_mirror),
                mirror_on_config_change=True,
            )
        except Exception as e:
            _send_discord(
                target=str(args.discord_target),
                message=(
                    f"❌ Deploy FAILED • `{run_id}` slot={target.slot} "
                    f"service={target.service} config={cand.config_id[:12]} "
                    f"error={type(e).__name__}: {e}"
                ),
            )
            raise

        if not bool(args.dry_run):
            try:
                _mark_deployed(registry_db=registry_db, run_id=run_id, config_id=str(cand.config_id))
            except Exception:
                pass
            deployed_any = True

        deploy_event_path = Path(deploy_dir) / "deploy_event.json"
        restart_summary, restart_details = _restart_summary_from_deploy_event(deploy_event_path)
        deployments.append(
            {
                "slot": int(target.slot),
                "service": str(target.service),
                "yaml_path": str(target.yaml_path),
                "status": "ok",
                "config_id": str(cand.config_id),
                "deploy_dir": str(deploy_dir),
                "restart_summary": str(restart_summary),
            }
        )
        _send_discord_chunks(
            target=str(args.discord_target),
            lines=[
                f"✅ Deployed • `{run_id}` • slot={target.slot}",
                f"`service` {target.service}  `config` `{_short_id(cand.config_id)}`",
                (
                    f"`pf` {_format_float(cand.profit_factor, ndigits=3)}  "
                    f"`dd` {_format_float(cand.max_drawdown_pct * 100.0, ndigits=2)}%  "
                    f"`pnl` {_format_float(cand.total_pnl, ndigits=2)}  "
                    f"`trades` {cand.total_trades}  "
                    f"`score` {_format_float(cand.score_v1, ndigits=4)}"
                ),
                f"`yaml` {_short_path(str(target.yaml_path), parts=4)}  `artifact` {_short_path(str(deploy_dir), parts=4)}",
                f"`restart` {restart_summary}",
                *restart_details[:8],
            ],
        )

        if changed_cfg and (not bool(args.dry_run)):
            user_target, user_label = _service_discord_route(str(target.service))
            if user_target:
                user_lines = _user_config_change_lines(
                    run_id=str(run_id),
                    lane_label=str(user_label or target.service),
                    lane_kind="paper candidate lane",
                    previous_cfg=str(prev_cfg_id),
                    next_cfg=str(cand.config_id),
                    source_note=f"candidate rank {i + 1}/{len(deploy_targets)}",
                    metrics={
                        "profit_factor": float(cand.profit_factor),
                        "max_drawdown_pct": float(cand.max_drawdown_pct) * 100.0,
                        "total_pnl": float(cand.total_pnl),
                        "total_trades": int(cand.total_trades),
                    },
                    diff_lines=list(diff_lines),
                )
                _send_discord_chunks(target=str(user_target), lines=user_lines)

    selection["deployed"] = bool(deployed_any)
    selection["deploy_stage"] = "deployed" if deployed_any else "skipped"
    selection["deployments"] = deployments
    (run_dir / "reports" / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_selection_markdown(run_dir=run_dir, selection=selection)

    if bool(args.enable_livepaper_promotion):
        promotion: dict[str, Any] = {
            "enabled": True,
            "ok": False,
            "gates": [],
            "selected": None,
            "deploy_dir": "",
            "reason": "",
        }
        live_service = str(args.livepaper_service or "").strip()
        live_yaml_raw = str(args.livepaper_yaml_path or "").strip()
        if (not live_service) or (not live_yaml_raw):
            promotion["reason"] = "missing livepaper target (--livepaper-service / --livepaper-yaml-path)"
            selection["promotion_stage"] = "skipped_missing_target"
            _send_discord(
                target=str(args.discord_target),
                message=(f"⏭️ Promotion skipped • `{run_id}`: {promotion['reason']}"),
            )
        else:
            gate_cfg = GateConfig(
                min_trades=int(args.promotion_min_trades),
                min_hours=float(args.promotion_min_hours),
                min_profit_factor=float(args.promotion_min_profit_factor),
                max_drawdown_pct=float(args.promotion_max_drawdown_pct),
                max_config_slippage_bps=(
                    None
                    if float(args.promotion_max_config_slippage_bps) <= 0
                    else float(args.promotion_max_config_slippage_bps)
                ),
                max_kill_events=int(args.promotion_max_kill_events),
            )
            explicit_db = _parse_service_path_map(str(args.paper_db_map))
            gate_rows: list[dict[str, Any]] = []
            for target in deploy_targets:
                latest = _latest_paper_deploy_event_for_service(
                    artifacts_dir=artifacts_dir,
                    service=str(target.service),
                    before_epoch_s=promotion_reference_epoch_s,
                )
                if latest is None:
                    gate_rows.append(
                        {
                            "service": str(target.service),
                            "ok": False,
                            "reasons": ["no deploy_event found for service"],
                            "metrics": {},
                        }
                    )
                    continue
                ev = latest.get("event", {}) if isinstance(latest.get("event"), dict) else {}
                config_id = str(((ev.get("what") or {}).get("config_id") or "")).strip()
                ts_utc = str(ev.get("ts_utc", "") or "").strip()
                deploy_since_s = _parse_iso_to_epoch_s(ts_utc)
                stable_since_s = _stable_promotion_since_s(
                    artifacts_dir=artifacts_dir,
                    service=str(target.service),
                    config_id=config_id,
                    before_epoch_s=promotion_reference_epoch_s,
                )
                since_s = stable_since_s if stable_since_s is not None else deploy_since_s
                paper_db = _paper_db_for_service(str(target.service), explicit_db)
                if not config_id or since_s is None or paper_db is None:
                    reasons: list[str] = []
                    if not config_id:
                        reasons.append("missing config_id in deploy_event")
                    if since_s is None:
                        reasons.append(f"invalid deploy ts_utc={ts_utc!r}")
                    if paper_db is None:
                        reasons.append("paper_db unavailable (set --paper-db-map or AI_QUANT_DB_PATH)")
                    gate_rows.append(
                        {
                            "service": str(target.service),
                            "ok": False,
                            "config_id": config_id,
                            "deploy_ts_utc": ts_utc,
                            "since_epoch_s": None,
                            "reasons": reasons,
                            "metrics": {},
                        }
                    )
                    continue
                try:
                    yaml_text = _lookup_config_yaml_text(registry_db=registry_db, config_id=config_id)
                except Exception as e:
                    gate_rows.append(
                        {
                            "service": str(target.service),
                            "ok": False,
                            "config_id": config_id,
                            "deploy_ts_utc": ts_utc,
                            "paper_db": str(paper_db),
                            "since_epoch_s": float(since_s),
                            "reasons": [f"registry lookup failed: {type(e).__name__}: {e}"],
                            "metrics": {},
                        }
                    )
                    continue
                gate = evaluate_paper_gates(
                    paper_db=paper_db,
                    since_epoch_s=float(since_s),
                    cfg=gate_cfg,
                    config_yaml_text=yaml_text,
                )
                gate_rows.append(
                    {
                        "service": str(target.service),
                        "ok": bool(gate.passed),
                        "config_id": config_id,
                        "deploy_ts_utc": ts_utc,
                        "paper_db": str(paper_db),
                        "since_epoch_s": float(since_s),
                        "reasons": list(gate.reasons),
                        "metrics": dict(gate.metrics),
                        "deploy_event_path": str(latest.get("path", "")),
                    }
                )

            promotion["gates"] = gate_rows
            gate_lines = [f"🛂 Promotion Gates • `{run_id}`"]
            for row in gate_rows:
                svc = str(row.get("service", "unknown") or "unknown")
                cid = str(row.get("config_id", "") or "")
                ok = bool(row.get("ok", False))
                mt = row.get("metrics", {}) if isinstance(row.get("metrics"), dict) else {}
                gate_lines.append(
                    (
                        f"{'✅' if ok else '❌'} {svc} "
                        f"`{cid[:12] if cid else 'n/a'}` "
                        f"pf={_format_float(mt.get('profit_factor', None), ndigits=3)} "
                        f"dd={_format_float(mt.get('max_drawdown_pct', None), ndigits=2)}% "
                        f"trades={int(mt.get('close_trades', 0) or 0)} "
                        f"h={_format_float(mt.get('elapsed_h', None), ndigits=1)} "
                        f"kill={int(mt.get('kill_events', 0) or 0)}"
                    )
                )
                if not ok:
                    reasons = row.get("reasons", [])
                    if isinstance(reasons, list):
                        for r in reasons[:2]:
                            gate_lines.append(f"↳ {str(r)}")
            _send_discord_chunks(target=str(args.discord_target), lines=gate_lines)

            live_yaml_path = Path(live_yaml_raw).expanduser().resolve()
            live_prev_text = live_yaml_path.read_text(encoding="utf-8") if live_yaml_path.exists() else ""
            live_prev_cfg = _yaml_config_id(live_prev_text)
            incumbent_row: dict[str, Any] = {
                "service": str(live_service),
                "ok": False,
                "config_id": str(live_prev_cfg),
                "deploy_ts_utc": "",
                "paper_db": "",
                "reasons": [],
                "metrics": {},
                "deploy_event_path": "",
            }
            incumbent_latest = _latest_paper_deploy_event_for_service(
                artifacts_dir=artifacts_dir,
                service=str(live_service),
                before_epoch_s=promotion_reference_epoch_s,
            )
            incumbent_since_s: float | None = None
            incumbent_cfg_id = str(live_prev_cfg or "").strip()
            incumbent_yaml_text = str(live_prev_text or "")
            if incumbent_latest is not None:
                ev_inc = incumbent_latest.get("event", {}) if isinstance(incumbent_latest.get("event"), dict) else {}
                incumbent_row["deploy_event_path"] = str(incumbent_latest.get("path", ""))
                incumbent_row["deploy_ts_utc"] = str(ev_inc.get("ts_utc", "") or "")
                incumbent_since_s = _parse_iso_to_epoch_s(str(incumbent_row["deploy_ts_utc"]))
                incumbent_cfg_evt = str(((ev_inc.get("what") or {}).get("config_id") or "")).strip()
                if incumbent_cfg_evt:
                    incumbent_cfg_id = incumbent_cfg_evt
                incumbent_stable_since_s = _stable_promotion_since_s(
                    artifacts_dir=artifacts_dir,
                    service=str(live_service),
                    config_id=str(incumbent_cfg_id),
                    before_epoch_s=promotion_reference_epoch_s,
                )
                if incumbent_stable_since_s is not None:
                    incumbent_since_s = float(incumbent_stable_since_s)
                if incumbent_cfg_id:
                    try:
                        incumbent_yaml_text = _lookup_config_yaml_text(
                            registry_db=registry_db, config_id=incumbent_cfg_id
                        )
                    except Exception:
                        # Keep live YAML text fallback when registry history is unavailable.
                        incumbent_yaml_text = str(live_prev_text or "")

            # If there is no deploy event yet, evaluate livepaper on a rolling min-hours window.
            if incumbent_since_s is None:
                incumbent_since_s = float(time.time()) - max(1.0, float(args.promotion_min_hours)) * 3600.0
                incumbent_row["reasons"] = ["incumbent deploy_event missing; used rolling window fallback"]

            incumbent_paper_db = _paper_db_for_service(str(live_service), explicit_db)
            if incumbent_paper_db is None:
                incumbent_row["reasons"] = list(incumbent_row.get("reasons", [])) + [
                    "incumbent paper_db unavailable (set --paper-db-map or AI_QUANT_DB_PATH)"
                ]
            elif not str(incumbent_yaml_text or "").strip():
                incumbent_row["reasons"] = list(incumbent_row.get("reasons", [])) + [
                    "incumbent config YAML unavailable"
                ]
            else:
                gate_inc = evaluate_paper_gates(
                    paper_db=incumbent_paper_db,
                    since_epoch_s=float(incumbent_since_s),
                    cfg=gate_cfg,
                    config_yaml_text=str(incumbent_yaml_text),
                )
                incumbent_row["ok"] = bool(gate_inc.passed)
                incumbent_row["metrics"] = dict(gate_inc.metrics)
                incumbent_row["reasons"] = list(incumbent_row.get("reasons", [])) + list(gate_inc.reasons)
                incumbent_row["paper_db"] = str(incumbent_paper_db)
                incumbent_row["config_id"] = str(incumbent_cfg_id)

            promotion["incumbent"] = incumbent_row
            inc_metrics = incumbent_row.get("metrics", {}) if isinstance(incumbent_row.get("metrics"), dict) else {}
            _send_discord_chunks(
                target=str(args.discord_target),
                lines=[
                    f"🧷 Incumbent • `{run_id}`",
                    (
                        f"{'✅' if bool(incumbent_row.get('ok', False)) else '❌'} {live_service} "
                        f"`{str(incumbent_row.get('config_id', '') or '')[:12] or 'n/a'}` "
                        f"pf={_format_float(inc_metrics.get('profit_factor', None), ndigits=3)} "
                        f"dd={_format_float(inc_metrics.get('max_drawdown_pct', None), ndigits=2)}% "
                        f"trades={int(inc_metrics.get('close_trades', 0) or 0)} "
                        f"h={_format_float(inc_metrics.get('elapsed_h', None), ndigits=1)} "
                        f"kill={int(inc_metrics.get('kill_events', 0) or 0)}"
                    ),
                    *[f"↳ {r}" for r in list(incumbent_row.get("reasons", []))[:2]],
                ],
            )

            passed_rows = [r for r in gate_rows if bool(r.get("ok", False))]
            if not passed_rows:
                promotion["reason"] = "no paper candidates passed promotion gates"
                selection["promotion_stage"] = "no_passing_candidate"
                _send_discord(
                    target=str(args.discord_target),
                    message=f"⏭️ Promotion skipped • `{run_id}`: {promotion['reason']}",
                )
            else:
                passed_rows.sort(key=_promotion_rank_key, reverse=True)
                chosen: dict[str, Any] | None = None
                if bool(args.promotion_ignore_live_comparison):
                    chosen = passed_rows[0]
                else:
                    # If incumbent itself fails base gates, allow failover to the best passing candidate.
                    if not bool(incumbent_row.get("ok", False)):
                        chosen = passed_rows[0]
                        _send_discord(
                            target=str(args.discord_target),
                            message=(
                                f"⚠️ Promotion guard bypass • `{run_id}`: "
                                "incumbent failed base gate; failover permitted."
                            ),
                        )
                    else:
                        cmp_lines = [
                            f"⚖️ Live Comparison • `{run_id}`",
                            (
                                f"rule: cand_pf >= inc_pf + {float(args.promotion_min_pf_delta):.3f}, "
                                f"cand_dd <= inc_dd + {float(args.promotion_max_dd_regression_pct):.3f}, "
                                "cand_kill <= inc_kill"
                            ),
                        ]
                        for cand in passed_rows:
                            cid = str(cand.get("config_id", "") or "").strip()
                            if cid and cid == str(live_prev_cfg):
                                chosen = cand
                                cmp_lines.append(f"✅ `{cid[:12]}` pass (already incumbent)")
                                break
                            better, reasons_cmp = _compare_candidate_vs_incumbent(
                                candidate=cand,
                                incumbent=incumbent_row,
                                min_pf_delta=float(args.promotion_min_pf_delta),
                                max_dd_regression_pct=float(args.promotion_max_dd_regression_pct),
                            )
                            if better:
                                chosen = cand
                                cmp_lines.append(f"✅ `{cid[:12] if cid else 'n/a'}` pass")
                                break
                            cmp_lines.append(
                                f"❌ `{cid[:12] if cid else 'n/a'}` fail: {'; '.join([str(x) for x in reasons_cmp[:2]])}"
                            )
                        _send_discord_chunks(target=str(args.discord_target), lines=cmp_lines)

                if chosen is None:
                    promotion["reason"] = "no passing candidate beat incumbent livepaper performance"
                    selection["promotion_stage"] = "blocked_by_comparison"
                    _send_discord(
                        target=str(args.discord_target),
                        message=f"⏭️ Promotion skipped • `{run_id}`: {promotion['reason']}",
                    )
                    selection["promotion"] = promotion
                    (run_dir / "reports" / "selection.json").write_text(
                        json.dumps(selection, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    health_services = _health_service_list(str(args.service))
                    snapshot_lines = [f"🩺 Health Snapshot • `{run_id}`"] + [
                        _service_snapshot_line(svc) for svc in health_services
                    ]
                    _send_discord_chunks(target=str(args.discord_target), lines=snapshot_lines)
                    _write_done_marker()
                    return 0

                chosen_cfg = str(chosen.get("config_id", "") or "").strip()
                if chosen_cfg and chosen_cfg == live_prev_cfg:
                    promotion["ok"] = True
                    promotion["selected"] = chosen
                    promotion["reason"] = "livepaper already running selected config"
                    selection["promotion_stage"] = "noop"
                    _send_discord(
                        target=str(args.discord_target),
                        message=(f"✅ Promotion no-op • `{run_id}` service={live_service} config={chosen_cfg[:12]}"),
                    )
                elif chosen_cfg:
                    selection["promotion_stage"] = "promoted"
                    chosen_yaml = _lookup_config_yaml_text(registry_db=registry_db, config_id=chosen_cfg)
                    live_next_summary = _yaml_summary(chosen_yaml)
                    live_prev_summary = _yaml_summary(live_prev_text)
                    live_diff = _diff_yaml_summaries(live_prev_summary, live_next_summary)
                    out_dir_live = (
                        artifacts_dir / "deployments" / "livepaper" / f"{_utc_compact()}_{chosen_cfg[:12]}"
                    ).resolve()
                    reason_live = (
                        f"auto livepaper promotion run_id={run_id}; "
                        f"source_service={chosen.get('service', 'unknown')}; config={chosen_cfg[:12]}"
                    )
                    deploy_dir_live = deploy_paper_config(
                        config_id=chosen_cfg,
                        artifacts_dir=artifacts_dir,
                        yaml_path=live_yaml_path,
                        out_dir=out_dir_live,
                        reason=reason_live,
                        restart=str(args.restart),
                        service=live_service,
                        dry_run=bool(args.dry_run),
                        validate=True,
                        ws_service=str(args.ws_service),
                        pause_file=pause_file,
                        pause_mode=str(args.pause_mode),
                        resume_on_success=not bool(args.leave_paused),
                        verify_sleep_s=float(args.verify_sleep_s),
                        mirror_source=str(args.mirror_source),
                        skip_mirror=bool(args.skip_mirror),
                    )
                    promotion["ok"] = True
                    promotion["selected"] = chosen
                    promotion["deploy_dir"] = str(deploy_dir_live)
                    promotion["reason"] = "promoted"
                    rs_live, rd_live = _restart_summary_from_deploy_event(Path(deploy_dir_live) / "deploy_event.json")
                    promo_lines = [
                        f"🚀 PROMOTED • `{run_id}`",
                        f"`to` {live_service}  `from` {chosen.get('service', 'unknown')}",
                        f"`config` `{_short_id(chosen_cfg)}`  `previous` `{_short_id(live_prev_cfg)}`",
                        f"`live_yaml` {_short_path(str(live_yaml_path), parts=4)}",
                    ]
                    if live_diff:
                        promo_lines.append("Key parameter changes:")
                        promo_lines.extend(live_diff[:8])
                    else:
                        promo_lines.append("Key parameter changes: none")
                    promo_lines.extend(
                        [
                            f"`artifact` {_short_path(str(deploy_dir_live), parts=4)}",
                            f"`restart` {rs_live}",
                            *rd_live[:8],
                        ]
                    )
                    _send_discord_chunks(target=str(args.discord_target), lines=promo_lines)

                    if not bool(args.dry_run):
                        live_target, live_label = _service_discord_route(str(live_service))
                        if live_target:
                            chosen_metrics = (
                                chosen.get("metrics", {}) if isinstance(chosen.get("metrics"), dict) else {}
                            )
                            user_lines_live = _user_config_change_lines(
                                run_id=str(run_id),
                                lane_label=str(live_label or live_service),
                                lane_kind="live proven lane",
                                previous_cfg=str(live_prev_cfg),
                                next_cfg=str(chosen_cfg),
                                source_note=f"promoted from {chosen.get('service', 'candidate')}",
                                metrics={
                                    "profit_factor": chosen_metrics.get("profit_factor", None),
                                    "max_drawdown_pct": chosen_metrics.get("max_drawdown_pct", None),
                                    "close_trades": chosen_metrics.get("close_trades", None),
                                    "elapsed_h": chosen_metrics.get("elapsed_h", None),
                                },
                                diff_lines=list(live_diff),
                            )
                            _send_discord_chunks(target=str(live_target), lines=user_lines_live)
                else:
                    promotion["reason"] = "chosen promotion row missing config_id"
                    selection["promotion_stage"] = "invalid_candidate"
                    _send_discord(
                        target=str(args.discord_target),
                        message=f"⏭️ Promotion skipped • `{run_id}`: {promotion['reason']}",
                    )
        selection["promotion"] = promotion
        (run_dir / "reports" / "selection.json").write_text(
            json.dumps(selection, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    health_services = _health_service_list(str(args.service))
    snapshot_lines = [f"🩺 Health Snapshot • `{run_id}`"] + [_service_snapshot_line(svc) for svc in health_services]
    _send_discord_chunks(target=str(args.discord_target), lines=snapshot_lines)

    _write_done_marker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
