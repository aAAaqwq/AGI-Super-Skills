#!/usr/bin/env python3
"""Nightly strategy factory orchestrator.

This script runs the end-to-end workflow:
1) Data checks (candles + funding)
2) Sweep (GPU optional)
3) Generate a shortlist of candidate configs
4) Replay/validate candidates on CPU
5) Emit a ranked summary report and store all artifacts under a run directory

The goal is reproducibility: every run has a `run_id` and a self-contained artifact folder.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from tools.config_id import config_id_from_yaml_file
except ImportError:  # pragma: no cover
    from config_id import config_id_from_yaml_file  # type: ignore[no-redef]

try:
    from tools.registry_index import default_registry_db_path, ingest_run_dir
except ImportError:  # pragma: no cover
    from registry_index import default_registry_db_path, ingest_run_dir  # type: ignore[no-redef]


AIQ_ROOT = Path(__file__).resolve().parent
_SHUTDOWN_REQUESTED = False
_SHUTDOWN_SIGNAL: int | None = None
_ACTIVE_CHILD_PROCESS: subprocess.Popen[str] | None = None


def _reset_shutdown_state() -> None:
    global _SHUTDOWN_REQUESTED, _SHUTDOWN_SIGNAL, _ACTIVE_CHILD_PROCESS
    _SHUTDOWN_REQUESTED = False
    _SHUTDOWN_SIGNAL = None
    _ACTIVE_CHILD_PROCESS = None


def _request_shutdown(signum: int, _frame: Any) -> None:
    global _SHUTDOWN_REQUESTED, _SHUTDOWN_SIGNAL
    _SHUTDOWN_REQUESTED = True
    _SHUTDOWN_SIGNAL = int(signum)
    proc = _ACTIVE_CHILD_PROCESS
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass


def _install_shutdown_handlers() -> dict[int, Any]:
    previous = {
        signal.SIGINT: signal.getsignal(signal.SIGINT),
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
    }
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    return previous


def _restore_shutdown_handlers(previous: dict[int, Any]) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except Exception:
            pass


def _default_secrets_path() -> Path:
    return Path("~/.config/openclaw/ai-quant-secrets.json").expanduser()


def _env_float(env_name: str, *, default: float | None = None) -> float | None:
    raw = str(os.getenv(env_name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        raise SystemExit(f"{env_name} must be a float when set")


def _env_bool(env_name: str, default: bool = False) -> bool:
    raw = os.getenv(env_name, "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def _env_bool_optional(env_name: str) -> bool | None:
    if env_name not in os.environ:
        return None
    raw = str(os.getenv(env_name, "")).strip().lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise SystemExit(f"{env_name} must be a boolean when set")


def _env_int(env_name: str, *, default: int | None = None) -> int | None:
    raw = str(os.getenv(env_name, "") or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        raise SystemExit(f"{env_name} must be an integer when set")


def _env_int_optional(env_name: str) -> int | None:
    if env_name not in os.environ:
        return None
    raw = str(os.getenv(env_name, "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        raise SystemExit(f"{env_name} must be an integer when set")


def _env_float_optional(env_name: str) -> float | None:
    if env_name not in os.environ:
        return None
    raw = str(os.getenv(env_name, "")).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        raise SystemExit(f"{env_name} must be a float when set")


LIVE_BALANCE_PROFILES = {"smoke", "daily", "deep", "weekly"}


def _resolve_live_db_path_candidates() -> list[Path]:
    candidates: list[Path] = []

    env_raw = os.getenv("AI_QUANT_LIVE_DB_PATH")
    if env_raw:
        candidates.append(Path(env_raw).expanduser())

    candidates.append(AIQ_ROOT / "trading_engine_live.db")
    candidates.append(Path("/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db"))

    out: list[Path] = []
    seen: set[str] = set()
    for cand in candidates:
        try:
            rp = cand.expanduser().resolve()
        except Exception:
            continue
        rs = str(rp)
        if rs in seen:
            continue
        seen.add(rs)
        out.append(rp)

    return out


def _first_existing_live_db_path() -> Path | None:
    for cand in _resolve_live_db_path_candidates():
        if cand.exists():
            return cand
    return None


def _read_balance_from_live_db(*, db_path: Path) -> float | None:
    try:
        if not db_path.exists():
            return None
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return float(row[0])
    except Exception:
        return None


def _resolve_live_export_python() -> str:
    venv_py = AIQ_ROOT / ".venv" / "bin" / "python3"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _export_live_balance_via_cli(*, output: Path) -> tuple[float | None, dict[str, Any]]:
    output.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    secrets_raw = os.getenv("AI_QUANT_SECRETS_PATH")
    if secrets_raw:
        env["AI_QUANT_SECRETS_PATH"] = str(Path(secrets_raw).expanduser())
    else:
        default_secret_path = _default_secrets_path()
        if default_secret_path.exists():
            env["AI_QUANT_SECRETS_PATH"] = str(default_secret_path)

    cmd = [
        _resolve_live_export_python(),
        str(AIQ_ROOT / "tools" / "export_state.py"),
        "--source",
        "live",
        "--output",
        str(output),
    ]

    try:
        res = subprocess.run(
            cmd,
            cwd=str(AIQ_ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except Exception as e:
        return None, {"method": "export_state", "success": False, "error": f"{type(e).__name__}: {e}"}

    if res.returncode != 0:
        err = str(res.stderr or res.stdout or "").strip()
        if not err:
            err = f"export_state exited with code {int(res.returncode)}"
        return None, {"method": "export_state", "success": False, "error": err}

    try:
        payload = _load_json(output)
        raw_bal = payload.get("balance")
        if raw_bal is None:
            return None, {"method": "export_state", "success": False, "error": "balance missing from export payload"}
        balance = float(raw_bal)
    except Exception as e:
        return None, {
            "method": "export_state",
            "success": False,
            "error": f"failed to read export payload: {type(e).__name__}: {e}",
        }

    return balance, {
        "method": "export_state",
        "success": True,
        "path": str(output),
        "secrets_path_used": env.get("AI_QUANT_SECRETS_PATH", ""),
    }


def _write_initial_balance_state_json(*, path: Path, balance: float, metadata: dict[str, Any]) -> None:
    payload: dict[str, Any] = {
        "version": 1,
        "updated_at_ms": int(time.time() * 1000),
        "balance": round(float(balance), 4),
        "metadata": dict(metadata),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_profile_requires_live_initial_balance(*, profile: str) -> bool:
    return str(profile or "").strip().lower() in LIVE_BALANCE_PROFILES


def _resolve_factory_initial_balance(
    *, run_dir: Path, args: argparse.Namespace
) -> tuple[float | None, Path | None, dict[str, Any]]:
    if not _resolve_profile_requires_live_initial_balance(profile=str(getattr(args, "profile", "daily").strip())):
        return None, None, {"mode": "disabled", "reason": "profile_no_live_init"}

    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_json = state_dir / "live_initial_balance.json"

    if state_json.exists():
        try:
            existing = _load_json(state_json)
            if isinstance(existing, dict) and "balance" in existing:
                bal = float(existing.get("balance") or 0.0)
                return (
                    bal,
                    state_json,
                    {
                        "mode": "live",
                        "source": "cache",
                        "path": str(state_json),
                        "cached_at_ms": float(existing.get("updated_at_ms", 0.0) or 0.0),
                    },
                )
        except Exception:
            pass

    bal, meta = _export_live_balance_via_cli(output=state_json)
    if bal is not None:
        meta["mode"] = "live"
        if "path" not in meta:
            meta["path"] = str(state_json)
        _write_initial_balance_state_json(path=state_json, balance=bal, metadata=meta)
        return bal, state_json, meta

    db_path = _first_existing_live_db_path()
    if db_path is None:
        return (
            None,
            None,
            {
                "mode": "live",
                "source": "sqlite",
                "success": False,
                "reason": "missing_live_db",
                "export_error": meta.get("error"),
            },
        )

    bal_from_db = _read_balance_from_live_db(db_path=db_path)
    if bal_from_db is None:
        return (
            None,
            None,
            {
                "mode": "live",
                "source": "sqlite",
                "success": False,
                "reason": "live_db_has_no_balance_rows",
                "live_db_path": str(db_path),
                "export_error": meta.get("error"),
            },
        )

    fallback_meta = {
        "mode": "live",
        "source": "sqlite",
        "success": True,
        "live_db_path": str(db_path),
    }
    _write_initial_balance_state_json(path=state_json, balance=bal_from_db, metadata=fallback_meta)
    return bal_from_db, state_json, fallback_meta


_REPLAY_EQUIVALENCE_MODES = ("live", "paper", "backtest")


def _normalise_replay_equivalence_mode(raw: str) -> str:
    mode = str(raw or "").strip().lower()
    if not mode:
        return "backtest"
    if mode == "dry_live":
        return "live"
    if mode in _REPLAY_EQUIVALENCE_MODES:
        return mode
    return "backtest"


def _replay_equivalence_mode() -> str:
    raw_mode = os.getenv("AI_QUANT_REPLAY_EQUIVALENCE_MODE", "").strip()
    if raw_mode:
        return _normalise_replay_equivalence_mode(raw_mode)
    raw_mode = os.getenv("AI_QUANT_MODE", "").strip()
    if raw_mode:
        return _normalise_replay_equivalence_mode(raw_mode)
    return "backtest"


def _resolve_path_for_backtester(path_str: str | None) -> str | None:
    """Resolve a CLI path into an absolute path usable from the backtester cwd.

    The Rust backtester is executed with `cwd=AIQ_ROOT/backtester`, but callers frequently pass paths that are:
    - repo-root relative (e.g. `config/...`, `backtester/sweeps/...`)
    - backtester-dir relative (e.g. `sweeps/smoke.yaml`)

    Normalise these to absolute paths to avoid "file not found" issues caused by the backtester cwd.
    """

    if path_str is None:
        return None
    raw = str(path_str).strip()
    if not raw:
        return None
    if raw == "-":
        return raw

    try:
        p = Path(raw).expanduser()
        if p.is_absolute():
            return str(p.resolve())

        # Prefer repo-root relative.
        cand_root = (AIQ_ROOT / p).resolve()
        if cand_root.exists():
            return str(cand_root)

        # Common when operators run from within backtester/ or copy examples.
        cand_bt = (AIQ_ROOT / "backtester" / p).resolve()
        if cand_bt.exists():
            return str(cand_bt)

        # Best-effort: respect current working directory if the path exists there.
        cand_cwd = (Path.cwd() / p).resolve()
        if cand_cwd.exists():
            return str(cand_cwd)

        # Default to repo-root absolute even if it doesn't exist (so errors are explicit).
        return str(cand_root)
    except Exception:
        return raw


def _normalise_candles_db_arg_for_backtester(arg: str | None) -> str | None:
    """Normalise --candles-db so directory inputs do not include funding DBs.

    The backtester expands a directory into all `*.db` files, which can accidentally include `funding_rates.db` and
    cause failures ("no such table: candles"). The backtester does not support glob patterns, so when a directory is
    supplied, expand it into an explicit comma-separated list of `candles_*.db` files.
    """

    if arg is None:
        return None
    raw = str(arg).strip()
    if not raw:
        return None

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out: list[str] = []
    seen: set[str] = set()

    for part in parts:
        resolved = _resolve_path_for_backtester(part) or part
        try:
            p = Path(resolved)
            if p.is_dir():
                expanded = [
                    str(ent.resolve())
                    for ent in p.iterdir()
                    if ent.is_file() and ent.name.startswith("candles_") and ent.suffix.lower() == ".db"
                ]
                expanded.sort()
                for x in expanded:
                    if x not in seen:
                        out.append(x)
                        seen.add(x)
                if expanded:
                    continue
        except Exception:
            pass

        if resolved not in seen:
            out.append(str(resolved))
            seen.add(str(resolved))

    return ",".join(out) if out else None


def _split_csv(raw: str) -> list[str]:
    """Split a comma-separated value list into unique, deduplicated entries."""
    out: list[str] = []
    seen: set[str] = set()
    for item in str(raw or "").split(","):
        token = str(item or "").strip()
        if not token:
            continue
        if token not in seen:
            out.append(token)
            seen.add(token)
    return out


def _factory_candle_check_intervals(default: str = "1m,3m,5m,15m,30m,1h") -> list[str]:
    """Return candle intervals configured for data health checks."""
    raw = os.getenv("AI_QUANT_FACTORY_CANDLE_CHECK_INTERVALS", default)
    return _split_csv(raw)


def _iter_candle_db_paths(raw_candles_db: str) -> list[Path]:
    """Return concrete candle DB paths from a path or comma-separated list."""
    out: list[Path] = []
    seen: set[str] = set()

    for item in _split_csv(raw_candles_db):
        try:
            p = Path(item).expanduser()
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            if p.is_dir():
                for child in sorted(p.iterdir()):
                    if not child.is_file():
                        continue
                    name = child.name
                    if not (name.startswith("candles_") and name.endswith(".db")):
                        continue
                    rp = str(child.resolve())
                    if rp not in seen:
                        out.append(child.resolve())
                        seen.add(rp)
                continue

            if p.is_file():
                rp = str(p.resolve())
                if rp not in seen:
                    out.append(Path(rp))
                    seen.add(rp)
        except Exception:
            continue

    return out


def _candle_db_interval(db_path: Path) -> str:
    name = db_path.name
    if name.startswith("candles_") and name.endswith(".db"):
        return name[len("candles_") : -len(".db")]
    return ""


def _symbols_from_candle_db(db_path: Path) -> list[str]:
    try:
        con = sqlite3.connect(str(db_path))
        try:
            rows = con.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol").fetchall()
            return [str(r[0]).strip() for r in rows if str(r[0]).strip()]
        finally:
            con.close()
    except Exception:
        return []


def _run_stat_check(
    *,
    sidecar_bin: str,
    interval: str,
    db_path: Path,
    symbols: list[str],
    out_path: Path,
    err_path: Path,
) -> tuple[int, list[dict[str, Any]], str, str]:
    symbols_csv = ",".join(symbols)
    argv = [
        sidecar_bin,
        "stat",
        "--interval",
        interval,
        "--symbols",
        symbols_csv,
        "--db-dir",
        str(db_path.parent),
        "--json",
    ]
    res = _run_cmd(argv, cwd=AIQ_ROOT, stdout_path=out_path, stderr_path=err_path)
    payload = _load_json_payload(out_path)
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    bad = []
    for it in items:
        if not isinstance(it, dict):
            continue
        gap = int(it.get("gap_bars", 0) or 0)
        nulls = int(it.get("null_ohlcv", 0) or 0)
        rows = int(it.get("rows", 0) or 0)
        wanted = int(it.get("bars_wanted", rows) or 0)
        out_of_order = bool(it.get("out_of_order"))
        if gap != 0 or nulls != 0 or rows < wanted or out_of_order:
            bad.append(str(it.get("symbol") or ""))

    fail_reason = "pass" if not bad and res.exit_code == 0 else "fail"
    return res.exit_code, items, bad, fail_reason


def _resolve_nvidia_smi_bin() -> str:
    """Return the best-effort path to nvidia-smi.

    On WSL2, `nvidia-smi` is often located at `/usr/lib/wsl/lib/nvidia-smi` and may not be on `PATH` for systemd
    services.
    """

    p = shutil.which("nvidia-smi")
    if p:
        return str(p)
    wsl = Path("/usr/lib/wsl/lib/nvidia-smi")
    if wsl.exists():
        return str(wsl)
    return "nvidia-smi"


def _load_json_payload(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _funding_check_degraded_allowance(
    funding_check_json: dict[str, Any],
    *,
    max_stale_symbols: int,
) -> tuple[bool, dict[str, Any] | None]:
    if max_stale_symbols < 1:
        return False, None

    issues = funding_check_json.get("issues")
    if not isinstance(issues, list):
        return False, None

    fail_issues = [i for i in issues if str(i.get("severity") or "") == "FAIL"]
    if not fail_issues:
        return False, None

    stale_fail_issues = [i for i in fail_issues if str(i.get("type") or "") == "stale"]
    if len(stale_fail_issues) != len(fail_issues):
        return False, None

    stale_symbols = sorted(
        {str(i.get("symbol") or "").strip() for i in stale_fail_issues if str(i.get("symbol") or "").strip()}
    )
    if len(stale_symbols) == 0:
        return False, None
    if len(stale_symbols) > int(max_stale_symbols):
        return False, None

    total_fail = len(fail_issues)
    return True, {
        "symbols": stale_symbols,
        "count": len(stale_symbols),
        "fail_issues": total_fail,
        "status": str(funding_check_json.get("status") or ""),
    }


PROFILE_DEFAULTS: dict[str, dict[str, int | str]] = {
    # Very fast profile for verifying all 142 axes end-to-end (not for optimisation).
    "smoke": {
        "tpe_trials": 2000,
        "num_candidates": 2,
        "shortlist_per_mode": 3,
        "shortlist_max_rank": 20,
        "sweep_spec": "backtester/sweeps/full_144v.yaml",
    },
    # Default weekday run profile.
    # Intentionally reduced for consumer-grade GPU stability after funding-enabled parity hardening.
    # Increase via CLI/ENV overrides when running on higher-capacity hardware.
    "daily": {
        "tpe_trials": 1000000,
        "num_candidates": 5,
        "shortlist_per_mode": 10,
        "shortlist_max_rank": 1000,
        "sweep_spec": "backtester/sweeps/full_144v.yaml",
    },
    # Deep/weekly profile.
    # Intentionally reduced from earlier factory defaults to lower crash risk and keep nightly
    # completion deterministic on constrained hosts. Override in explicit deep runs as needed.
    "deep": {
        "tpe_trials": 2000000,
        "num_candidates": 10,
        "shortlist_per_mode": 10,
        "shortlist_max_rank": 1000,
        "sweep_spec": "backtester/sweeps/full_144v.yaml",
    },
    # Weekly profile — identical to deep; weekly is the canonical name going forward.
    "weekly": {
        "tpe_trials": 2000000,
        "num_candidates": 10,
        "shortlist_per_mode": 10,
        "shortlist_max_rank": 1000,
        "sweep_spec": "backtester/sweeps/full_144v.yaml",
    },
}


@dataclass(frozen=True)
class CmdResult:
    argv: list[str]
    cwd: str
    exit_code: int
    elapsed_s: float
    stdout_path: str | None
    stderr_path: str | None
    timed_out: bool = False
    interrupted: bool = False
    timeout_s: float | None = None


def _default_cmd_timeout_s() -> float | None:
    """Return default subprocess timeout for factory commands.

    Set ``AI_QUANT_FACTORY_CMD_TIMEOUT_S`` to override (seconds). Values <= 0 disable timeout.
    """
    try:
        raw = float(os.getenv("AI_QUANT_FACTORY_CMD_TIMEOUT_S", "86400"))
    except Exception:
        raw = 86400.0
    if raw <= 0.0:
        return None
    # Keep a sane upper bound (7 days) to avoid accidental runaway settings.
    return float(max(1.0, min(raw, 7 * 24 * 60 * 60.0)))


def _run_cmd(
    argv: list[str],
    *,
    cwd: Path,
    stdout_path: Path | None,
    stderr_path: Path | None,
    env: dict[str, str] | None = None,
    timeout_s: float | None = None,
) -> CmdResult:
    global _ACTIVE_CHILD_PROCESS
    t0 = time.time()
    timed_out = False
    interrupted = False
    effective_timeout_s: float | None = _default_cmd_timeout_s() if timeout_s is None else None
    if timeout_s is not None:
        try:
            parsed_timeout = float(timeout_s)
        except Exception:
            parsed_timeout = _default_cmd_timeout_s() or 0.0
        if parsed_timeout > 0:
            effective_timeout_s = parsed_timeout
        else:
            effective_timeout_s = None

    if _SHUTDOWN_REQUESTED:
        return CmdResult(
            argv=list(argv),
            cwd=str(cwd),
            exit_code=130,
            elapsed_s=float(time.time() - t0),
            stdout_path=str(stdout_path) if stdout_path is not None else None,
            stderr_path=str(stderr_path) if stderr_path is not None else None,
            timed_out=False,
            interrupted=True,
            timeout_s=effective_timeout_s,
        )

    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_f = stdout_path.open("w", encoding="utf-8")
    else:
        stdout_f = subprocess.DEVNULL  # type: ignore[assignment]

    if stderr_path is not None:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_f = stderr_path.open("w", encoding="utf-8")
    else:
        stderr_f = subprocess.DEVNULL  # type: ignore[assignment]

    proc_env = _resolve_subprocess_env(cwd=cwd, env=env)

    exit_code = -1
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdout=stdout_f,
            stderr=stderr_f,
            env=proc_env,
            text=True,
        )
        _ACTIVE_CHILD_PROCESS = proc
        deadline = None
        if effective_timeout_s is not None and effective_timeout_s > 0:
            deadline = t0 + float(effective_timeout_s)

        exit_code = 1
        while True:
            polled = proc.poll()
            if polled is not None:
                if _SHUTDOWN_REQUESTED:
                    interrupted = True
                    exit_code = 130
                    if hasattr(stderr_f, "write"):
                        try:
                            stderr_f.write(f"Command interrupted by signal {_SHUTDOWN_SIGNAL}: {list(argv)}\n")
                            stderr_f.flush()
                        except Exception:
                            pass
                else:
                    exit_code = int(polled)
                break

            if _SHUTDOWN_REQUESTED:
                interrupted = True
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=2.0)
                    except Exception:
                        pass
                exit_code = 130
                if hasattr(stderr_f, "write"):
                    try:
                        stderr_f.write(f"Command interrupted by signal {_SHUTDOWN_SIGNAL}: {list(argv)}\n")
                        stderr_f.flush()
                    except Exception:
                        pass
                break

            if deadline is not None and time.time() >= deadline:
                timed_out = True
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=2.0)
                    except Exception:
                        pass
                exit_code = 124
                if hasattr(stderr_f, "write"):
                    try:
                        stderr_f.write(
                            f"Command timed out after {float(effective_timeout_s or 0.0):.2f}s: {list(argv)}\n"
                        )
                        stderr_f.flush()
                    except Exception:
                        pass
                break

            time.sleep(0.1)

    except OSError as exc:
        exit_code = 127
        if hasattr(stderr_f, "write"):
            try:
                stderr_f.write(f"Failed to start command {list(argv)}: {type(exc).__name__}: {exc}\n")
                stderr_f.flush()
            except Exception:
                pass
    finally:
        _ACTIVE_CHILD_PROCESS = None
        if hasattr(stdout_f, "close"):
            stdout_f.close()  # type: ignore[call-arg]
        if hasattr(stderr_f, "close"):
            stderr_f.close()  # type: ignore[call-arg]

    return CmdResult(
        argv=list(argv),
        cwd=str(cwd),
        exit_code=exit_code,
        elapsed_s=float(time.time() - t0),
        stdout_path=str(stdout_path) if stdout_path is not None else None,
        stderr_path=str(stderr_path) if stderr_path is not None else None,
        timed_out=bool(timed_out),
        interrupted=bool(interrupted),
        timeout_s=effective_timeout_s,
    )


def _gpu_compute_processes(*, stdout_path: Path, stderr_path: Path) -> tuple[CmdResult, list[str]]:
    """Return a list of running CUDA compute processes (best-effort).

    Uses nvidia-smi compute-apps query; if the command fails, callers should treat the GPU as unavailable.
    """

    res = _run_cmd(
        [
            _resolve_nvidia_smi_bin(),
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ],
        cwd=AIQ_ROOT,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    if res.exit_code != 0:
        return res, []

    try:
        lines = [ln.strip() for ln in stdout_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        lines = []
    return res, lines


def _ensure_gpu_idle_or_exit(*, run_dir: Path, meta: dict[str, Any], wait_s: int, poll_s: int) -> int:
    """Gate GPU sweeps to avoid interfering with other GPU workloads.

    If `wait_s` is >0, this will poll for an idle GPU until the timeout; otherwise it exits immediately.
    """

    wait_s = int(wait_s or 0)
    poll_s = int(poll_s or 0)
    if wait_s < 0:
        wait_s = 0
    if poll_s <= 0:
        poll_s = 10

    t0 = time.time()
    deadline = t0 + float(wait_s)
    attempt = 0

    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    while True:
        attempt += 1
        out_path = run_dir / "logs" / "gpu_check.stdout.txt"
        err_path = run_dir / "logs" / "gpu_check.stderr.txt"
        res, procs = _gpu_compute_processes(stdout_path=out_path, stderr_path=err_path)
        meta["steps"].append({"name": f"gpu_check_attempt{attempt}", **res.__dict__})

        if res.exit_code != 0:
            meta["gpu_check"] = {
                "idle": False,
                "error": f"nvidia-smi failed with exit_code={res.exit_code}",
                "wait_s": wait_s,
                "poll_s": poll_s,
                "attempts": attempt,
            }
            _write_json(run_dir / "run_metadata.json", meta)
            (run_dir / "reports").mkdir(parents=True, exist_ok=True)
            (run_dir / "reports" / "report.md").write_text(
                "# Factory Run Report\n\nError: GPU requested but nvidia-smi failed.\n",
                encoding="utf-8",
            )
            return 1

        idle = not bool(procs)
        meta["gpu_check"] = {
            "idle": bool(idle),
            "processes": list(procs),
            "wait_s": wait_s,
            "poll_s": poll_s,
            "attempts": attempt,
            "waited_s": int(time.time() - t0),
        }
        _write_json(run_dir / "run_metadata.json", meta)

        if idle:
            return 0

        if time.time() >= deadline:
            (run_dir / "reports").mkdir(parents=True, exist_ok=True)
            details = "\n".join([f"- {p}" for p in procs]) if procs else "- (unknown)\n"
            (run_dir / "reports" / "report.md").write_text(
                "# Factory Run Report\n\n"
                "Error: GPU appears busy (compute processes detected). Try again later.\n\n"
                "Detected processes:\n"
                f"{details}\n",
                encoding="utf-8",
            )
            return 2

        time.sleep(float(max(1, poll_s)))


def _git_head_sha() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(AIQ_ROOT)).decode("utf-8").strip()
        return out
    except Exception:
        return ""


def _resolve_backtester_cmd() -> list[str]:
    env_bin = os.getenv("MEI_BACKTESTER_BIN", "").strip()
    if env_bin:
        return [env_bin]

    rel = AIQ_ROOT / "backtester" / "target" / "release" / "mei-backtester"
    if rel.exists():
        return [str(rel)]

    # Fallback: build+run via cargo.
    return ["cargo", "run", "-p", "bt-cli", "--bin", "mei-backtester", "--"]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_file_optional(path: Path) -> str:
    try:
        return _sha256_file(path)
    except Exception:
        return ""


def _file_fingerprint(path: Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        return {"path": str(p), "exists": False}

    out: dict[str, Any] = {"path": str(p), "exists": True, "is_file": p.is_file(), "is_dir": p.is_dir()}
    if p.is_file():
        st = p.stat()
        out.update(
            {
                "size_bytes": int(st.st_size),
                "mtime_ns": int(st.st_mtime_ns),
                "sha256": _sha256_file(p),
            }
        )
    return out


def _stat_fingerprint(path: Path) -> dict[str, Any]:
    """Lightweight fingerprint that does *not* read file contents.

    Useful for large SQLite DB inputs where sha256 over the full file is too expensive.
    """

    p = Path(path).expanduser()
    if not p.exists():
        return {"path": str(p), "exists": False}
    try:
        st = p.stat()
        return {
            "path": str(p),
            "exists": True,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "size_bytes": int(st.st_size),
            "mtime_ns": int(st.st_mtime_ns),
        }
    except Exception:
        return {"path": str(p), "exists": True}


def _split_csv_paths(arg: str | None) -> list[str]:
    if arg is None:
        return []
    raw = str(arg).strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _fingerprint_db_arg(arg: str | None) -> dict[str, Any]:
    """Fingerprint a --candles-db/--funding-db style argument.

    Accepts a single path or a comma-separated list of paths.
    Returns a stable, JSON-serialisable structure.
    """

    paths = _split_csv_paths(arg)
    fps: list[dict[str, Any]] = []
    for p in paths:
        resolved = _resolve_path_for_backtester(p)
        fps.append(_stat_fingerprint(Path(resolved) if resolved else Path(p)))
    fps.sort(key=lambda x: str(x.get("path", "")))
    raw = json.dumps(fps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "schema_version": 1,
        "count": len(fps),
        "fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "files": fps,
    }


_EFFECTIVE_RANGE_RE = re.compile(
    r"\[(?:sweep|replay)\] Effective time range: (?P<from>-?\d+) \([^)]*\)\.\.(?P<to>-?\d+) \([^)]*\)"
)


def _parse_effective_time_range_ms(log_path: Path) -> tuple[int | None, int | None, str | None]:
    """Parse the Rust backtester '[sweep] Effective time range: <ms>..<ms>' line."""

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None, None, None

    for line in text.splitlines():
        m = _EFFECTIVE_RANGE_RE.search(line)
        if not m:
            continue
        try:
            from_ms = int(m.group("from"))
            to_ms = int(m.group("to"))
            return from_ms, to_ms, line.strip()
        except Exception:
            continue
    return None, None, None


def _capture_repro_metadata(*, run_dir: Path, artifacts_root: Path, bt_cmd: list[str], meta: dict[str, Any]) -> None:
    repro_dir = run_dir / "repro"
    repro_dir.mkdir(parents=True, exist_ok=True)

    # Best-effort system/environment metadata. Failures should not block the pipeline.
    env_keys = [
        "MEI_BACKTESTER_BIN",
        "CUDA_VISIBLE_DEVICES",
        "LD_LIBRARY_PATH",
        "PYTHONHASHSEED",
    ]
    raw_sweep_spec = str(meta.get("args", {}).get("sweep_spec", "") or "").strip()
    sweep_spec_fp: dict[str, Any]
    if raw_sweep_spec:
        resolved = _resolve_path_for_backtester(raw_sweep_spec)
        sweep_spec_fp = _file_fingerprint(Path(resolved) if resolved else (AIQ_ROOT / raw_sweep_spec))
    else:
        sweep_spec_fp = {"path": "", "exists": False}

    meta["repro"] = {
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "argv0": sys.argv[0] if sys.argv else "",
        },
        "env": {k: os.getenv(k, "") for k in env_keys},
        "backtester_cmd": list(bt_cmd),
        "files": {
            "pyproject_toml": _file_fingerprint(AIQ_ROOT / "pyproject.toml"),
            "uv_lock": _file_fingerprint(AIQ_ROOT / "uv.lock"),
            "sweep_spec": sweep_spec_fp,
        },
        "cmds": [],
    }

    # Capture versions as command outputs into artifacts.
    version_cmds: list[tuple[str, list[str]]] = [
        ("uname", ["uname", "-a"]),
        ("git_status", ["git", "status", "--porcelain=v1"]),
        ("cargo_version", ["cargo", "--version"]),
        ("rustc_version", ["rustc", "--version"]),
        ("nvidia_smi", [_resolve_nvidia_smi_bin(), "-L"]),
        ("nvcc_version", ["nvcc", "--version"]),
    ]

    for name, argv in version_cmds:
        out_path = repro_dir / f"{name}.stdout.txt"
        err_path = repro_dir / f"{name}.stderr.txt"
        try:
            res = _run_cmd(argv, cwd=AIQ_ROOT, stdout_path=out_path, stderr_path=err_path)
            meta["repro"]["cmds"].append({"name": name, **res.__dict__})
        except Exception as e:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("", encoding="utf-8")
            err_path.write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
            meta["repro"]["cmds"].append(
                {
                    "name": name,
                    "argv": list(argv),
                    "cwd": str(AIQ_ROOT),
                    "exit_code": 127,
                    "elapsed_s": 0.0,
                    "stdout_path": str(out_path),
                    "stderr_path": str(err_path),
                    "exception": f"{type(e).__name__}: {e}",
                }
            )

    # Capture backtester version (stamped into the binary at build time).
    try:
        argv = list(bt_cmd) + ["--version"]
        out_path = repro_dir / "mei_backtester_version.stdout.txt"
        err_path = repro_dir / "mei_backtester_version.stderr.txt"
        res = _run_cmd(argv, cwd=AIQ_ROOT / "backtester", stdout_path=out_path, stderr_path=err_path)
        meta["repro"]["cmds"].append({"name": "mei_backtester_version", **res.__dict__})
    except Exception as e:
        out_path = repro_dir / "mei_backtester_version.stdout.txt"
        err_path = repro_dir / "mei_backtester_version.stderr.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("", encoding="utf-8")
        err_path.write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
        meta["repro"]["cmds"].append(
            {
                "name": "mei_backtester_version",
                "argv": list(bt_cmd) + ["--version"],
                "cwd": str(AIQ_ROOT / "backtester"),
                "exit_code": 127,
                "elapsed_s": 0.0,
                "stdout_path": str(out_path),
                "stderr_path": str(err_path),
                "exception": f"{type(e).__name__}: {e}",
            }
        )

    # Fingerprint the resolved backtester binary when it is a path.
    bt0 = str(bt_cmd[0]) if bt_cmd else ""
    bt_path = Path(bt0) if bt0 and ("/" in bt0 or bt0.endswith(".exe")) else None
    if bt_path and bt_path.exists():
        meta["repro"]["files"]["mei_backtester_bin"] = _file_fingerprint(bt_path)

    meta["repro"]["artifacts_root"] = str(artifacts_root)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _is_nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mark_run_interrupted(*, run_dir: Path, meta: dict[str, Any], stage: str | None = None) -> None:
    meta["status"] = "interrupted"
    meta["interrupted_at_ms"] = int(time.time() * 1000)
    if stage:
        meta["shutdown_requested_stage"] = str(stage)
    if _SHUTDOWN_SIGNAL is not None:
        meta["interrupt_signal"] = int(_SHUTDOWN_SIGNAL)
    steps = meta.get("steps")
    if isinstance(steps, list):
        steps.append(
            {
                "name": "shutdown_interrupt",
                "exit_code": 130,
                "signal": int(_SHUTDOWN_SIGNAL) if _SHUTDOWN_SIGNAL is not None else None,
            }
        )
    _write_json(run_dir / "run_metadata.json", meta)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    report_path = run_dir / "reports" / "report.md"
    if not report_path.exists():
        report_path.write_text(
            "# Factory Run Report\n\nRun interrupted by shutdown signal.\n",
            encoding="utf-8",
        )


def _mark_run_fatal_error(*, run_dir: Path, meta: dict[str, Any], stage: str, exc: Exception) -> None:
    meta["status"] = "failed"
    meta["fatal_error"] = f"{type(exc).__name__}: {exc}"
    meta["fatal_error_type"] = type(exc).__name__
    meta["fatal_error_stage"] = str(stage)
    meta["fatal_error_at_ms"] = int(time.time() * 1000)
    try:
        meta["fatal_error_traceback"] = traceback.format_exc()
    except Exception:
        pass
    _write_json(run_dir / "run_metadata.json", meta)


def _shutdown_stage_guard(*, run_dir: Path, meta: dict[str, Any], stage: str) -> bool:
    if not _SHUTDOWN_REQUESTED:
        return False
    _mark_run_interrupted(run_dir=run_dir, meta=meta, stage=stage)
    return True


def _append_reject_reason(it: dict[str, Any], reason: str) -> None:
    reason = str(reason or "").strip()
    if not reason:
        return
    if not bool(it.get("rejected")):
        it["rejected"] = True
        it["reject_reason"] = reason
        return
    prev = str(it.get("reject_reason", "") or "").strip()
    if not prev:
        it["reject_reason"] = reason
        return
    if reason in prev:
        return
    it["reject_reason"] = f"{prev}; {reason}"


def _slippage_reject_reason(*, agg: dict[str, Any], reject_bps: float, flip_sign: bool) -> str:
    if bool(agg.get("degraded", False)):
        degraded_reasons = agg.get("degraded_reasons", [])
        reasons_text = ", ".join(str(x) for x in degraded_reasons if str(x).strip())
        if reasons_text:
            return f"slippage degraded: {reasons_text}"
        return "slippage degraded run"
    if bool(flip_sign):
        return f"slippage flip at {float(reject_bps):g} bps"
    reject_reason = str(agg.get("reject_reason", "")).strip()
    if reject_reason:
        return f"slippage reject: {reject_reason}"
    return "slippage reject"


def _compute_score_v1(
    it: dict[str, Any],
    *,
    min_trades: int,
    trades_penalty_weight: float,
) -> dict[str, Any] | None:
    """Compute stability score_v1 (AQC-504).

    score_v1 = median(OOS_daily_return)
             - 2.0 * max(OOS_drawdown_pct)
             - 0.5 * slippage_fragility
             - penalty_if_trades_too_low

    Notes:
    - OOS metrics come from walk-forward validation (AQC-501).
    - slippage_fragility is a balance-normalised PnL drop from slippage stress (AQC-502).
    """

    # Require walk-forward metrics to avoid comparing incomparable candidates.
    if "wf_median_oos_daily_return" not in it or "wf_max_oos_drawdown_pct" not in it:
        return None
    # Require slippage fragility (otherwise the score is optimistic).
    if "slippage_fragility" not in it:
        return None

    try:
        oos_daily_ret = float(it.get("wf_median_oos_daily_return", 0.0))
        oos_max_dd = float(it.get("wf_max_oos_drawdown_pct", 0.0))
        slip_frag = float(it.get("slippage_fragility", 0.0))
        trades = int(it.get("total_trades", 0))
    except Exception:
        return None

    min_trades = int(min_trades)
    if min_trades < 0:
        min_trades = 0
    trades_penalty_weight = float(trades_penalty_weight)
    if trades_penalty_weight < 0:
        trades_penalty_weight = 0.0

    deficit = max(0, int(min_trades) - int(trades))
    trades_penalty = (deficit / float(max(1, min_trades))) * trades_penalty_weight if min_trades > 0 else 0.0

    dd_weight = 2.0
    slippage_weight = 0.5
    score = (
        float(oos_daily_ret)
        - dd_weight * float(oos_max_dd)
        - slippage_weight * float(slip_frag)
        - float(trades_penalty)
    )

    return {
        "version": "score_v1",
        "score": float(score),
        "components": {
            "median_oos_daily_return": float(oos_daily_ret),
            "max_oos_drawdown_pct": float(oos_max_dd),
            "slippage_fragility": float(slip_frag),
            "total_trades": int(trades),
            "min_trades": int(min_trades),
            "trades_penalty": float(trades_penalty),
            "weights": {
                "drawdown": float(dd_weight),
                "slippage": float(slippage_weight),
                "trades_penalty_weight": float(trades_penalty_weight),
            },
        },
    }


def _summarise_replay_report(path: Path) -> dict[str, Any]:
    d = _load_json(path)
    # Values may be explicitly None in the JSON, so use `or` fallback.
    return {
        "path": str(path),
        "initial_balance": float(d.get("initial_balance") or 0.0),
        "final_balance": float(d.get("final_balance") or 0.0),
        "total_pnl": float(d.get("total_pnl") or 0.0),
        "total_trades": int(d.get("total_trades") or 0),
        "win_rate": float(d.get("win_rate") or 0.0),
        "profit_factor": float(d.get("profit_factor") or 0.0),
        "max_drawdown_pct": float(d.get("max_drawdown_pct") or 0.0),
        "total_fees": float(d.get("total_fees") or 0.0),
    }


def _sweep_output_mode_from_args(args: Any) -> str:
    if bool(getattr(args, "tpe", False)) or bool(getattr(args, "gpu", False)):
        return "candidate"
    return "full"


def _infer_sweep_stage_from_args(args: Any) -> str:
    if bool(getattr(args, "tpe", False)):
        return "gpu_tpe"
    if bool(getattr(args, "gpu", False)):
        return "gpu"
    return "cpu"


def _infer_validation_gate_from_args(args: Any) -> str:
    wf = bool(getattr(args, "walk_forward", False))
    ss = bool(getattr(args, "slippage_stress", False))
    if wf and ss:
        return "score_v1+walk_forward+slippage"
    if wf:
        return "score_v1+walk_forward"
    if ss:
        return "score_v1+slippage"
    return "replay_only"


def _stage_defaults_for_candidate(*, args: Any) -> dict[str, Any]:
    return {
        "pipeline_stage": "candidate_generation",
        "sweep_stage": _infer_sweep_stage_from_args(args),
        "replay_stage": "",
        "validation_gate": _infer_validation_gate_from_args(args),
        "canonical_cpu_verified": False,
        "candidate_mode": True,
        "schema_version": 1,
    }


def _attach_replay_metadata(
    summary: dict[str, Any],
    entry: dict[str, Any] | None,
    *,
    args: Any,
    replay_stage: str = "cpu_replay",
) -> None:
    eq_status = str(summary.get("replay_equivalence_status", "")).strip().lower()
    eq_seed = bool(summary.get("replay_equivalence_seed_mode", False))
    verified = eq_status == "pass" or (eq_seed and eq_status in ("baseline_stale", "missing_baseline", "not_run"))
    candidate_mode = bool(entry.get("candidate_mode", False)) if isinstance(entry, dict) else False
    schema_version = 1
    if isinstance(entry, dict) and "schema_version" in entry:
        try:
            raw_schema_version = entry.get("schema_version")
            schema_version = int(raw_schema_version) if not isinstance(raw_schema_version, bool) else raw_schema_version
        except Exception:
            schema_version = raw_schema_version
    stage_fields = {
        "pipeline_stage": "candidate_validation",
        "sweep_stage": _infer_sweep_stage_from_args(args),
        "replay_stage": replay_stage,
        "validation_gate": _infer_validation_gate_from_args(args),
        "canonical_cpu_verified": bool(verified),
        "candidate_mode": candidate_mode,
        "schema_version": schema_version,
    }
    if entry is not None:
        for k, v in stage_fields.items():
            summary[k] = v
            entry[k] = v
        replay_report_path = str(summary.get("path", ""))
        config_path = str(summary.get("config_path", ""))
        summary["replay_report_path"] = replay_report_path
        entry["replay_report_path"] = replay_report_path
        summary["config_path"] = config_path
        entry["config_path"] = config_path
        for identity_field in ("sort_by", "rank", "overrides_key", "config_sha256"):
            if identity_field in summary and identity_field not in entry:
                entry[identity_field] = summary[identity_field]
            elif identity_field in entry and identity_field not in summary:
                summary[identity_field] = entry[identity_field]
        for proof_field in [
            "replay_equivalence_status",
            "replay_equivalence_mode",
            "replay_equivalence_strict",
            "replay_equivalence_auto_seed",
            "replay_equivalence_seed_mode",
            "replay_equivalence_seed_reason",
            "replay_equivalence_count",
            "replay_equivalence_error",
            "replay_equivalence_report_path",
            "replay_equivalence_diffs",
            "replay_equivalence_failure_code",
            "replay_equivalence_contract_fingerprint",
            "replay_equivalence_baseline_contract_fingerprint",
        ]:
            if proof_field in summary:
                entry[proof_field] = summary[proof_field]
    else:
        summary.update(stage_fields)


def _replay_equivalence_env_var(env_name: str, mode: str) -> str | None:
    mode = _normalise_replay_equivalence_mode(mode)
    raw = os.getenv(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_{env_name}", "").strip()
    if raw:
        return raw
    raw = os.getenv(f"AI_QUANT_REPLAY_EQUIVALENCE_{env_name}", "").strip()
    return raw or None


_REPLAY_EQUIVALENCE_CONTRACT_SCHEMA_VERSION = 1


def _replay_equivalence_auto_seed(*, mode: str) -> bool:
    mode = _normalise_replay_equivalence_mode(mode)
    scoped = _env_bool_optional(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_AUTO_SEED")
    if scoped is not None:
        return scoped
    return _env_bool("AI_QUANT_REPLAY_EQUIVALENCE_AUTO_SEED", True)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except Exception:
        return int(default)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return float(int(value))
        return float(value)
    except Exception:
        return float(default)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off"}:
            return False
    return bool(default)


def _normalise_shortlist_modes_list(raw: Any) -> list[str]:
    if isinstance(raw, (list, tuple)):
        parts = [str(x).strip().lower() for x in raw]
    else:
        parts = [p.strip().lower() for p in str(raw or "").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _build_replay_equivalence_contract_payload(*, args_obj: dict[str, Any], mode: str) -> dict[str, Any]:
    raw_sweep_spec = str(args_obj.get("sweep_spec", "") or "").strip()
    if raw_sweep_spec:
        resolved = _resolve_path_for_backtester(raw_sweep_spec)
        sweep_spec_fp = _file_fingerprint(Path(resolved) if resolved else (AIQ_ROOT / raw_sweep_spec))
    else:
        sweep_spec_fp = {"path": "", "exists": False}
    sweep_spec_exists = bool(sweep_spec_fp.get("exists", False))
    version_file = AIQ_ROOT / "VERSION"
    version_text = ""
    try:
        if version_file.exists():
            version_text = str(version_file.read_text(encoding="utf-8").strip() or "")
    except Exception:
        version_text = ""
    factory_fp = _file_fingerprint(AIQ_ROOT / "factory_run.py")
    bt_bin_sha256 = ""
    try:
        bt_bin_env = str(os.environ.get("MEI_BACKTESTER_BIN", "") or "").strip()
        bt_bin_candidates = [
            bt_bin_env,
            str(AIQ_ROOT / "backtester" / "dist" / "mei-backtester-gpu"),
            str(AIQ_ROOT / "backtester" / "target" / "release" / "mei-backtester"),
        ]
        for bp in bt_bin_candidates:
            if bp and Path(bp).is_file():
                bt_bin_sha256 = _sha256_file(Path(bp))
                break
    except Exception:
        pass
    return {
        "schema_version": int(_REPLAY_EQUIVALENCE_CONTRACT_SCHEMA_VERSION),
        "mode": _normalise_replay_equivalence_mode(mode),
        "profile": str(args_obj.get("profile", "") or ""),
        "interval": str(args_obj.get("interval", "") or ""),
        "sweep_spec_sha256": str(sweep_spec_fp.get("sha256", "") if sweep_spec_exists else ""),
        "sweep_spec_size_bytes": int(_coerce_int(sweep_spec_fp.get("size_bytes", 0), 0) if sweep_spec_exists else 0),
        "gpu": bool(_coerce_bool(args_obj.get("gpu", False))),
        "tpe": bool(_coerce_bool(args_obj.get("tpe", False))),
        "tpe_trials": int(_coerce_int(args_obj.get("tpe_trials", 0), 0)),
        "tpe_batch": int(_coerce_int(args_obj.get("tpe_batch", 0), 0)),
        "tpe_seed": int(_coerce_int(args_obj.get("tpe_seed", 0), 0)),
        "shortlist_modes": _normalise_shortlist_modes_list(args_obj.get("shortlist_modes", "")),
        "shortlist_per_mode": int(_coerce_int(args_obj.get("shortlist_per_mode", 0), 0)),
        "shortlist_max_rank": int(_coerce_int(args_obj.get("shortlist_max_rank", 0), 0)),
        "shortlist_top_pnl": int(_coerce_int(args_obj.get("shortlist_top_pnl", 1000), 1000)),
        "candidate_min_trades": int(_coerce_int(args_obj.get("candidate_min_trades", 0), 0)),
        "num_candidates": int(_coerce_int(args_obj.get("num_candidates", 0), 0)),
        "sort_by": str(args_obj.get("sort_by", "") or ""),
        "top_n": int(_coerce_int(args_obj.get("top_n", 0), 0)),
        "walk_forward": bool(_coerce_bool(args_obj.get("walk_forward", False))),
        "slippage_stress": bool(_coerce_bool(args_obj.get("slippage_stress", False))),
        "concentration_checks": bool(_coerce_bool(args_obj.get("concentration_checks", False))),
        "sensitivity_checks": bool(_coerce_bool(args_obj.get("sensitivity_checks", False))),
        "monte_carlo": bool(_coerce_bool(args_obj.get("monte_carlo", False))),
        "score_min_trades": int(_coerce_int(args_obj.get("score_min_trades", 0), 0)),
        "score_trades_penalty_weight": float(_coerce_float(args_obj.get("score_trades_penalty_weight", 0.0), 0.0)),
        "promote_count": int(_coerce_int(args_obj.get("promote_count", 0), 0)),
        "factory_run_sha256": str(factory_fp.get("sha256", "") if bool(factory_fp.get("exists", False)) else ""),
        "backtester_bin_sha256": bt_bin_sha256,
        "version": version_text,
    }


def _build_replay_equivalence_contract(*, args_obj: dict[str, Any], mode: str) -> dict[str, Any]:
    payload = _build_replay_equivalence_contract_payload(args_obj=args_obj, mode=mode)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return {
        "schema_version": int(_REPLAY_EQUIVALENCE_CONTRACT_SCHEMA_VERSION),
        "mode": _normalise_replay_equivalence_mode(mode),
        "fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "payload": payload,
    }


def _replay_equivalence_contract_from_meta(meta: dict[str, Any], *, mode: str) -> dict[str, Any] | None:
    existing = meta.get("replay_equivalence_contract")
    if isinstance(existing, dict) and str(existing.get("fingerprint", "")).strip():
        return existing
    args_obj = meta.get("args")
    if not isinstance(args_obj, dict):
        return None
    return _build_replay_equivalence_contract(args_obj=args_obj, mode=mode)


# ---------------------------------------------------------------------------
# Step-4 GPU↔CPU parity contract (factory_cycle step 4)
# ---------------------------------------------------------------------------

_STEP4_PARITY_CONTRACT_SCHEMA_VERSION = 1


def _build_step4_parity_contract_payload(meta: dict[str, Any]) -> dict[str, Any]:
    """Build a *comparison* contract for Step-4 GPU↔CPU parity.

    This is the non-negotiable anchor that prevents "false regressions" caused by:
    - different candle DB snapshots / updated market data
    - different effective time windows (auto-scope drift)
    - different backtester binaries / codegen outputs
    """

    args_obj = meta.get("args") if isinstance(meta.get("args"), dict) else {}
    sweep_range = (
        meta.get("sweep_effective_time_range_ms") if isinstance(meta.get("sweep_effective_time_range_ms"), dict) else {}
    )
    inputs = meta.get("input_fingerprints") if isinstance(meta.get("input_fingerprints"), dict) else {}
    repro = meta.get("repro") if isinstance(meta.get("repro"), dict) else {}
    repro_files = repro.get("files") if isinstance(repro.get("files"), dict) else {}

    bt_bin = repro_files.get("mei_backtester_bin") if isinstance(repro_files.get("mei_backtester_bin"), dict) else {}

    return {
        "schema_version": int(_STEP4_PARITY_CONTRACT_SCHEMA_VERSION),
        "run_id": str(meta.get("run_id", "") or ""),
        "git_head": str(meta.get("git_head", "") or ""),
        "profile": str(args_obj.get("profile", "") or ""),
        "interval": str(args_obj.get("interval", "") or ""),
        "start_ts_arg": str(args_obj.get("start_ts", "") or ""),
        "end_ts_arg": str(args_obj.get("end_ts", "") or ""),
        "sweep_parity_mode": str(args_obj.get("sweep_parity_mode", "") or ""),
        "gpu": bool(_coerce_bool(args_obj.get("gpu", False))),
        "tpe": bool(_coerce_bool(args_obj.get("tpe", False))),
        "effective_from_ts_ms": int(_coerce_int(sweep_range.get("from_ts_ms"), 0) or 0),
        "effective_to_ts_ms": int(_coerce_int(sweep_range.get("to_ts_ms"), 0) or 0),
        "candles_db": {
            "fingerprint": str(
                inputs.get("candles_db", {}).get("fingerprint", "")
                if isinstance(inputs.get("candles_db"), dict)
                else ""
            ),
            "count": int(
                _coerce_int(inputs.get("candles_db", {}).get("count"), 0)
                if isinstance(inputs.get("candles_db"), dict)
                else 0
            ),
        },
        "funding_db": {
            "fingerprint": str(
                inputs.get("funding_db", {}).get("fingerprint", "")
                if isinstance(inputs.get("funding_db"), dict)
                else ""
            ),
            "count": int(
                _coerce_int(inputs.get("funding_db", {}).get("count"), 0)
                if isinstance(inputs.get("funding_db"), dict)
                else 0
            ),
        },
        "balance_from": {
            "fingerprint": str(
                inputs.get("balance_from", {}).get("fingerprint", "")
                if isinstance(inputs.get("balance_from"), dict)
                else ""
            ),
        },
        "sweep_spec_sha256": str(
            repro_files.get("sweep_spec", {}).get("sha256", "")
            if isinstance(repro_files.get("sweep_spec"), dict)
            else ""
        ),
        "mei_backtester_sha256": str(bt_bin.get("sha256", "") or ""),
        "mei_backtester_version": str(meta.get("backtester_version", "") or ""),
    }


def _build_step4_parity_contract(meta: dict[str, Any]) -> dict[str, Any]:
    payload = _build_step4_parity_contract_payload(meta)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return {
        "schema_version": int(_STEP4_PARITY_CONTRACT_SCHEMA_VERSION),
        "fingerprint": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "payload": payload,
    }


def _find_run_dir(path: Path) -> Path | None:
    """Find the nearest ancestor that looks like a factory run directory."""

    start = path if path.is_dir() else path.parent
    current = start
    for _ in range(8):
        if (current / "run_metadata.json").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _coerce_replay_report_path(value: Any, *, run_dir: Path | None = None) -> Path | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        if run_dir is not None:
            p = (run_dir / p).resolve()
        else:
            p = p.expanduser().resolve()
    return p


_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _summary_config_sha256(summary: dict[str, Any]) -> str:
    cfg_sha = str(summary.get("config_sha256", "") or "").strip()
    if cfg_sha:
        return cfg_sha
    cfg_path = str(summary.get("config_path", "") or "").strip()
    if not cfg_path:
        return ""
    p = Path(cfg_path)
    if not p.exists() or not p.is_file():
        return ""
    return _sha256_file_optional(p)


def _candidate_baseline_match_score(
    *,
    row: dict[str, Any],
    summary: dict[str, Any],
    right_report: Path,
) -> int:
    score = 0

    wanted_config_id = str(summary.get("config_id", "") or "").strip()
    if wanted_config_id and str(row.get("config_id", "") or "").strip() == wanted_config_id:
        score += 100

    wanted_cfg_sha = _summary_config_sha256(summary)
    row_cfg_sha = str(row.get("config_sha256", "") or "").strip()
    if wanted_cfg_sha and row_cfg_sha and wanted_cfg_sha == row_cfg_sha:
        score += 90

    wanted_overrides = str(summary.get("overrides_key", "") or "").strip()
    row_overrides = str(row.get("overrides_key", "") or "").strip()
    if wanted_overrides and row_overrides and wanted_overrides == row_overrides:
        score += 60

    wanted_mode = str(summary.get("sort_by", "") or "").strip().lower()
    row_mode = str(row.get("sort_by", "") or "").strip().lower()
    if wanted_mode and row_mode and wanted_mode == row_mode:
        score += 20

    wanted_rank = int(_coerce_int(summary.get("rank"), 0) or 0)
    row_rank = int(_coerce_int(row.get("rank"), 0) or 0)
    if wanted_rank > 0 and row_rank > 0 and wanted_rank == row_rank:
        score += 20

    wanted_cfg_name = Path(str(summary.get("config_path", "") or "")).name
    row_cfg_path = str(row.get("path", "") or row.get("config_path", "") or "").strip()
    row_cfg_name = Path(row_cfg_path).name if row_cfg_path else ""
    if wanted_cfg_name and row_cfg_name and wanted_cfg_name == row_cfg_name:
        score += 15

    row_replay_name = Path(str(row.get("replay_report_path", "") or "")).name
    if right_report.name and row_replay_name and right_report.name == row_replay_name:
        score += 10

    return int(score)


def _resolve_candidate_replay_baseline_from_rows(
    *,
    rows: list[dict[str, Any]],
    run_dir: Path,
    summary: dict[str, Any],
    right_report: Path,
) -> Path | None:
    scored: list[tuple[int, int, Path]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        baseline_path = _coerce_replay_report_path(row.get("replay_report_path"), run_dir=run_dir)
        if baseline_path is None or not baseline_path.is_file():
            continue
        score = _candidate_baseline_match_score(row=row, summary=summary, right_report=right_report)
        scored.append((int(score), -int(idx), baseline_path))

    if scored:
        scored.sort(reverse=True)
        top_score, _neg_idx, top_path = scored[0]
        if int(top_score) > 0:
            return top_path

    # Backward-compatible final fallback by replay file name.
    return _candidate_baseline_in_directory(run_dir / "replays", right_report=right_report)


def _candidate_baseline_from_run_metadata(
    run_dir: Path,
    *,
    summary: dict[str, Any],
    right_report: Path,
) -> Path | None:
    meta = _load_json(run_dir / "run_metadata.json")
    candidates = meta.get("candidate_configs")
    if not isinstance(candidates, list):
        return None

    rows = [it for it in candidates if isinstance(it, dict)]
    return _resolve_candidate_replay_baseline_from_rows(
        rows=rows,
        run_dir=run_dir,
        summary=summary,
        right_report=right_report,
    )


def _candidate_baseline_in_directory(
    baseline_dir: Path,
    *,
    right_report: Path,
) -> Path | None:
    if not right_report.is_absolute():
        right_report = (Path.cwd() / right_report).resolve()
    candidates = [baseline_dir / right_report.name]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _candidate_baseline_from_manifest(
    manifest_path: Path,
    *,
    summary: dict[str, Any],
    right_report: Path,
) -> Path | None:
    try:
        payload = _load_json(manifest_path)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    run_dir = manifest_path.parent
    rows_raw = payload.get("candidates")
    if not isinstance(rows_raw, list):
        return None

    rows: list[dict[str, Any]] = []
    for row in rows_raw:
        if isinstance(row, dict):
            rows.append(dict(row))

    # Enrich manifest rows with run metadata identity fields when available.
    meta_path = run_dir / "run_metadata.json"
    if meta_path.exists():
        try:
            meta = _load_json(meta_path)
        except Exception:
            meta = {}
        candidates = meta.get("candidate_configs") if isinstance(meta, dict) else []
        if isinstance(candidates, list):
            by_config: dict[str, dict[str, Any]] = {}
            for it in candidates:
                if not isinstance(it, dict):
                    continue
                cfg_id = str(it.get("config_id", "") or "").strip()
                if cfg_id and cfg_id not in by_config:
                    by_config[cfg_id] = it

            for row in rows:
                cfg_id = str(row.get("config_id", "") or "").strip()
                candidate = by_config.get(cfg_id)
                if not isinstance(candidate, dict):
                    continue
                for key in ("path", "config_path", "sort_by", "rank", "overrides_key", "config_sha256"):
                    if key not in row and key in candidate:
                        row[key] = candidate.get(key)
                if not str(row.get("replay_report_path", "") or "").strip():
                    row["replay_report_path"] = candidate.get("replay_report_path")

    return _resolve_candidate_replay_baseline_from_rows(
        rows=rows,
        run_dir=run_dir,
        summary=summary,
        right_report=right_report,
    )


def _run_generated_at_ms(run_dir: Path) -> int:
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        return 0
    try:
        meta = _load_json(meta_path)
    except Exception:
        return 0
    if not isinstance(meta, dict):
        return 0
    return int(_coerce_int(meta.get("generated_at_ms"), 0) or 0)


def _artifacts_root_from_run_dir(run_dir: Path) -> Path | None:
    run_dir = run_dir.resolve()

    # Preferred source: run metadata explicitly records artifacts root.
    meta_path = run_dir / "run_metadata.json"
    if meta_path.exists():
        try:
            meta = _load_json(meta_path)
        except Exception:
            meta = {}
        repro = meta.get("repro") if isinstance(meta, dict) else {}
        raw_root = str((repro or {}).get("artifacts_root", "") or "").strip() if isinstance(repro, dict) else ""
        if raw_root:
            candidate = Path(raw_root).expanduser().resolve()
            if candidate.is_dir():
                return candidate

    # Standard layout: artifacts/YYYY-MM-DD/run_<run_id>.
    parent = run_dir.parent
    if _DATE_DIR_RE.match(parent.name):
        root = parent.parent
        if root.is_dir():
            return root

    return None


def _resolve_replay_equivalence_artifacts_root(*, right_report: Path) -> Path | None:
    run_dir = _find_run_dir(right_report)
    if run_dir is not None:
        rooted = _artifacts_root_from_run_dir(run_dir)
        if rooted is not None:
            return rooted
    fallback = (AIQ_ROOT / "artifacts").resolve()
    if fallback.is_dir():
        return fallback
    return None


def _iter_replay_equivalence_baseline_manifests(artifacts_root: Path) -> list[Path]:
    manifests: list[Path] = []
    if not artifacts_root.exists():
        return manifests

    for date_dir in sorted(
        [p for p in artifacts_root.iterdir() if p.is_dir() and _DATE_DIR_RE.match(p.name)], reverse=True
    ):
        for run_dir in sorted(
            [p for p in date_dir.iterdir() if p.is_dir() and p.name.startswith("run_")], reverse=True
        ):
            p = run_dir / "replay_equivalence_baseline_manifest.json"
            if p.is_file():
                manifests.append(p)
    return manifests


def _auto_replay_equivalence_baseline_path(
    *,
    mode: str,
    right_report: Path,
    summary: dict[str, Any],
    current_contract: dict[str, Any] | None,
) -> tuple[Path | None, dict[str, Any]]:
    info: dict[str, Any] = {
        "enabled": True,
        "selected": False,
        "selected_path": "",
        "selected_manifest": "",
        "selected_run_id": "",
        "scanned_manifests": 0,
        "matched_manifests": 0,
    }
    current_fp = str((current_contract or {}).get("fingerprint", "") or "").strip()
    if not current_fp:
        info["error"] = "missing_current_contract_fingerprint"
        return None, info

    artifacts_root = _resolve_replay_equivalence_artifacts_root(right_report=right_report)
    if artifacts_root is None:
        info["error"] = "artifacts_root_unresolved"
        return None, info
    info["artifacts_root"] = str(artifacts_root)

    manifests = _iter_replay_equivalence_baseline_manifests(artifacts_root)
    info["scanned_manifests"] = len(manifests)
    if not manifests:
        info["error"] = "no_baseline_manifests_found"
        return None, info

    mode_norm = _normalise_replay_equivalence_mode(mode)
    matches: list[tuple[int, int, Path, Path, str]] = []
    for idx, manifest_path in enumerate(manifests):
        try:
            payload = _load_json(manifest_path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        contract = payload.get("contract")
        if not isinstance(contract, dict):
            continue
        contract_fp = str(contract.get("fingerprint", "") or "").strip()
        contract_mode = _normalise_replay_equivalence_mode(str(contract.get("mode", "") or mode_norm))
        if not contract_fp or contract_fp != current_fp:
            continue
        if contract_mode != mode_norm:
            continue

        candidate_baseline = _candidate_baseline_from_manifest(
            manifest_path,
            summary=summary,
            right_report=right_report,
        )
        if candidate_baseline is None:
            continue

        run_dir = manifest_path.parent
        generated_at_ms = int(_coerce_int(payload.get("generated_at_ms"), 0) or 0)
        if generated_at_ms <= 0:
            generated_at_ms = _run_generated_at_ms(run_dir)
        run_id = str(payload.get("run_id", "") or "").strip()
        if not run_id:
            try:
                run_meta = _load_json(run_dir / "run_metadata.json")
            except Exception:
                run_meta = {}
            if isinstance(run_meta, dict):
                run_id = str(run_meta.get("run_id", "") or "").strip()

        matches.append((int(generated_at_ms), -int(idx), candidate_baseline, manifest_path, run_id))

    info["matched_manifests"] = len(matches)
    if not matches:
        info["error"] = "no_compatible_baseline_found"
        return None, info

    matches.sort(reverse=True)
    _gen_ms, _neg_idx, selected_path, selected_manifest, selected_run_id = matches[0]
    info["selected"] = True
    info["selected_path"] = str(selected_path)
    info["selected_manifest"] = str(selected_manifest)
    info["selected_run_id"] = str(selected_run_id)
    return selected_path, info


def _resolve_replay_equivalence_baseline_path(
    mode: str,
    baseline_path: Path,
    *,
    right_report: Path,
    summary: dict[str, Any],
) -> Path:
    """
    Resolve replay equivalence baseline path with stronger alignment guarantees.

    Supported inputs:
    - a direct baseline replay JSON file path,
    - a replay directory/run directory containing run_metadata.json and replay candidates.
    """

    if baseline_path.is_file():
        # 1) Use same-baseline file when the caller explicitly passes one file.
        # 2) When this file belongs to a factory run, prefer run-level match by config.
        # 3) Fall back to a sibling replay file with the same candidate name.
        run_dir = _find_run_dir(baseline_path)
        if run_dir is not None and run_dir != baseline_path:
            resolved = _candidate_baseline_from_run_metadata(
                run_dir,
                summary=summary,
                right_report=right_report,
            )
            if resolved is not None:
                return resolved

        if baseline_path.name.endswith(".replay.json") and baseline_path.name != right_report.name:
            sibling = _candidate_baseline_in_directory(baseline_path.parent, right_report=right_report)
            if sibling is not None:
                return sibling

        return baseline_path

    if not baseline_path.is_dir():
        return baseline_path

    run_dir = _find_run_dir(baseline_path) or baseline_path
    if (run_dir / "run_metadata.json").is_file():
        resolved = _candidate_baseline_from_run_metadata(run_dir, summary=summary, right_report=right_report)
        if resolved is not None:
            return resolved

    replay_dir = run_dir / "replays"
    sibling = _candidate_baseline_in_directory(replay_dir, right_report=right_report)
    if sibling is not None:
        return sibling

    return baseline_path / "__missing_replay_equivalence_baseline__.json"


def _replay_equivalence_baseline_policy(*, mode: str) -> str:
    mode = _normalise_replay_equivalence_mode(mode)
    raw = _replay_equivalence_env_var("BASELINE_POLICY", mode=mode)
    policy = str(raw or "pinned_or_auto").strip().lower()
    if policy in {"pinned", "pin", "pinned_only"}:
        return "pinned_only"
    if policy in {"auto", "auto_only"}:
        return "auto_only"
    if policy in {"hybrid", "pinned_or_auto", "pin_or_auto"}:
        return "pinned_or_auto"
    return "pinned_or_auto"


def _replay_equivalence_auto_fallback_enabled(*, mode: str) -> bool:
    mode = _normalise_replay_equivalence_mode(mode)
    scoped = _env_bool_optional(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_AUTO_FALLBACK")
    if scoped is not None:
        return scoped
    return _env_bool("AI_QUANT_REPLAY_EQUIVALENCE_AUTO_FALLBACK", True)


def _replay_equivalence_baseline_path(*, mode: str) -> Path | None:
    raw = _replay_equivalence_env_var("BASELINE", mode=mode)
    if not raw:
        return None

    resolved = _resolve_path_for_backtester(raw)
    return Path(resolved)


def _replay_equivalence_strict(*, mode: str) -> bool:
    mode = _normalise_replay_equivalence_mode(mode)
    scoped = _env_bool_optional(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_STRICT")
    if scoped is not None:
        return scoped
    return _env_bool("AI_QUANT_REPLAY_EQUIVALENCE_STRICT", False)


def _replay_equivalence_tolerance(*, mode: str) -> float:
    mode = _normalise_replay_equivalence_mode(mode)
    scoped = _env_float_optional(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_TOLERANCE")
    if scoped is not None:
        return float(scoped)
    return _env_float("AI_QUANT_REPLAY_EQUIVALENCE_TOLERANCE", default=1e-12)


def _replay_equivalence_max_diffs(*, mode: str) -> int:
    mode = _normalise_replay_equivalence_mode(mode)
    scoped = _env_int_optional(f"AI_QUANT_REPLAY_EQUIVALENCE_{mode.upper()}_MAX_DIFFS")
    if scoped is not None:
        return int(scoped or 25)
    return int(_env_int("AI_QUANT_REPLAY_EQUIVALENCE_MAX_DIFFS", default=25) or 25)


def _replay_equivalence_failure_code(status: str) -> str:
    if status == "pass":
        return ""
    if status == "fail":
        return "mismatch"
    return status


def _baseline_replay_equivalence_contract(*, baseline_path: Path, mode: str) -> dict[str, Any] | None:
    run_dir = _find_run_dir(baseline_path)
    if run_dir is None:
        return None
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        return None
    try:
        loaded = _load_json(meta_path)
    except Exception:
        return None
    if not isinstance(loaded, dict):
        return None
    return _replay_equivalence_contract_from_meta(loaded, mode=mode)


def _validate_candidate_schema_row(row: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(row, dict):
        return False, ["row is not an object"]

    candidate_mode = bool(row.get("candidate_mode", False))
    if not candidate_mode:
        errors.append("candidate_mode is not true")

    schema_version = row.get("schema_version")
    if isinstance(schema_version, bool) or schema_version is None:
        errors.append("schema_version is required and must be an integer >= 1")
    else:
        try:
            schema_version = int(schema_version)
            if schema_version != 1:
                errors.append("schema_version must be 1")
        except Exception:
            errors.append("schema_version is required and must be an integer >= 1")

    output_mode = str(row.get("output_mode", "")).strip()
    if output_mode != "candidate":
        errors.append(f"output_mode is not candidate: {output_mode!r}")

    cfg_id = row.get("config_id")
    if not isinstance(cfg_id, str) or not cfg_id.strip():
        errors.append("config_id is required and must be a non-empty string")

    overrides = row.get("overrides")
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if isinstance(value, (dict, list, tuple)):
                errors.append(f"overrides[{key!r}] has unsupported type: {type(value).__name__}")
                break
    elif isinstance(overrides, list):
        # Rust backtester emits overrides as [["key", value], ...] pairs.
        for i, pair in enumerate(overrides):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                errors.append(f"overrides[{i}] must be a [key, value] pair")
                break
            if not isinstance(pair[0], str):
                errors.append(f"overrides[{i}][0] must be a string key")
                break
    else:
        errors.append("overrides must be an object or list of [key, value] pairs")

    required_keys = [
        "total_pnl",
        "total_trades",
        "profit_factor",
        "max_drawdown_pct",
    ]
    for key in required_keys:
        if key not in row:
            errors.append(f"missing {key}")
            continue

        raw = row.get(key)
        if not isinstance(raw, (int, float)) or key == "total_trades" and raw < 0:
            errors.append(f"{key} must be numeric and non-negative when applicable")

    return (len(errors) == 0), errors


def _validate_candidate_output_schema(path: Path) -> tuple[bool, list[str]]:
    if not path.is_file():
        return False, [f"sweep output file missing: {path}"]
    if path.stat().st_size <= 0:
        return False, [f"sweep output file empty: {path}"]

    errors: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                row = json.loads(raw_line)
            except Exception as exc:
                errors.append(f"line {line_no}: invalid json: {exc}")
                continue

            ok, row_errors = _validate_candidate_schema_row(row)
            if ok:
                continue
            for err in row_errors:
                errors.append(f"line {line_no}: {err}")

    if errors:
        return False, errors
    return True, []


# ---------------------------------------------------------------------------
# Sort-key functions for _extract_top_candidates (mirrors generate_config.py)
# ---------------------------------------------------------------------------

_EXTRACT_SORT_KEYS: dict[str, Any] = {
    "pnl": lambda r: float(r.get("total_pnl", 0) or 0),
    "dd": lambda r: -float(r.get("max_drawdown_pct", 1) or 1),
    "pf": lambda r: float(r.get("profit_factor", 0) or 0),
    "wr": lambda r: float(r.get("win_rate", 0) or 0),
    "sharpe": lambda r: float(r.get("sharpe_ratio", 0) or 0),
    "trades": lambda r: float(r.get("total_trades", 0) or 0),
    # Alias: "conservative" is pure DD lane (lower DD is better).
    "conservative": lambda r: -float(r.get("max_drawdown_pct", 1) or 1),
}


def _extract_balanced_score(r: dict) -> float:
    """Composite score matching generate_config.py balanced_score()."""
    try:
        pnl = float(r.get("total_pnl", 0) or 0)
    except Exception:
        pnl = 0.0
    try:
        pf = min(float(r.get("profit_factor", 0) or 0), 10.0)
    except Exception:
        pf = 0.0
    try:
        sharpe = float(r.get("sharpe_ratio", 0) or 0)
    except Exception:
        sharpe = 0.0
    try:
        dd = float(r.get("max_drawdown_pct", 1) or 1)
    except Exception:
        dd = 1.0
    try:
        trades = int(float(r.get("total_trades", 0) or 0))
    except Exception:
        trades = 0
    trade_penalty = 0.5 if trades < 20 else 1.0
    return (pnl * 0.3 + pf * 20 + sharpe * 15 - dd * 100) * trade_penalty


def _extract_efficient_score(r: dict) -> float:
    """Efficient lane: (PnL / DD) × PF."""
    try:
        pnl = float(r.get("total_pnl", 0.0) or 0.0)
    except Exception:
        pnl = 0.0
    try:
        dd = float(r.get("max_drawdown_pct", 1.0) or 1.0)
    except Exception:
        dd = 1.0
    try:
        pf = float(r.get("profit_factor", 1.0) or 1.0)
    except Exception:
        pf = 1.0
    dd = max(dd, 0.01)
    pf = max(pf, 0.0)
    return (pnl / dd) * pf


def _extract_growth_score(r: dict) -> float:
    """Growth lane: PnL × (1 − DD) × PF (minor DD penalty)."""
    try:
        pnl = float(r.get("total_pnl", 0.0) or 0.0)
    except Exception:
        pnl = 0.0
    try:
        dd = float(r.get("max_drawdown_pct", 0.0) or 0.0)
    except Exception:
        dd = 0.0
    try:
        pf = float(r.get("profit_factor", 1.0) or 1.0)
    except Exception:
        pf = 1.0
    dd = min(max(dd, 0.0), 1.0)
    pf = max(pf, 0.0)
    return pnl * (1.0 - dd) * pf


def _extract_top_candidates(
    src: Path,
    dst: Path,
    *,
    max_rank: int,
    modes: list[str],
    min_trades: int = 0,
    validate_schema: bool = False,
    max_schema_errors: int = 100,
) -> tuple[int, list[str]]:
    """Single-pass streaming extraction of multi-criteria top-N candidates.

    Streams through *src* line-by-line (constant memory) maintaining a
    bounded min-heap per sort *mode*.  After the pass, unions all heaps,
    deduplicates by ``config_id``, and writes the compact result to *dst*.

    Returns ``(total_rows_read, schema_errors)`` where *schema_errors* is
    non-empty only when *validate_schema* is ``True`` and issues are found.

    Memory usage: O(max_rank × len(modes) × row_size) — typically < 50 MB
    even for multi-million-trial sweeps.
    """
    import heapq

    sort_fns: dict[str, Any] = {
        **_EXTRACT_SORT_KEYS,
        "balanced": _extract_balanced_score,
        "efficient": _extract_efficient_score,
        "growth": _extract_growth_score,
    }

    # One min-heap per mode, each capped at max_rank entries.
    heaps: dict[str, list[tuple[float, int, str]]] = {m: [] for m in modes if m in sort_fns}
    # Store rows by config_id so we only keep one copy of each row dict.
    row_store: dict[str, str] = {}  # config_id -> json line

    schema_errors: list[str] = []
    total_rows = 0
    counter = 0  # tie-breaker for heap ordering

    with src.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                row = json.loads(raw_line)
            except Exception as exc:
                if validate_schema:
                    schema_errors.append(f"line {line_no}: invalid json: {exc}")
                    if len(schema_errors) >= max_schema_errors:
                        break
                continue

            if validate_schema:
                ok, row_errors = _validate_candidate_schema_row(row)
                if not ok:
                    for err in row_errors:
                        schema_errors.append(f"line {line_no}: {err}")
                    if len(schema_errors) >= max_schema_errors:
                        break
                    continue

            total_rows += 1

            # Skip rows below min_trades threshold.
            try:
                trades = int(float(row.get("total_trades", 0) or 0))
            except Exception:
                trades = 0
            if min_trades > 0 and trades < min_trades:
                continue

            config_id = str(row.get("config_id", "") or "").strip()
            if not config_id:
                config_id = f"_anon_{counter}"

            counter += 1

            for mode, score_fn in sort_fns.items():
                if mode not in heaps:
                    continue
                try:
                    score = float(score_fn(row))
                except Exception:
                    continue
                entry = (score, counter, config_id)
                heap = heaps[mode]
                if len(heap) < max_rank:
                    heapq.heappush(heap, entry)
                    row_store[config_id] = raw_line
                elif score > heap[0][0]:
                    evicted = heapq.heapreplace(heap, entry)
                    row_store[config_id] = raw_line
                    # Evict row from store if no longer referenced by any heap.
                    evicted_id = evicted[2]
                    if not any(evicted_id == e[2] for h in heaps.values() for e in h):
                        row_store.pop(evicted_id, None)

    # Union all heaps, deduplicate, and write.
    seen: set[str] = set()
    output_lines: list[str] = []
    # Process heaps in deterministic order; within each heap, best-first.
    for mode in modes:
        if mode not in heaps:
            continue
        for _score, _cnt, cid in sorted(heaps[mode], reverse=True):
            if cid in seen:
                continue
            seen.add(cid)
            line = row_store.get(cid)
            if line is not None:
                output_lines.append(line)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(output_lines) + ("\n" if output_lines else ""), encoding="utf-8")

    return total_rows, schema_errors


def _run_replay_equivalence_check(
    *,
    right_report: Path,
    summary: dict[str, Any],
    current_contract: dict[str, Any] | None = None,
) -> bool:
    mode = _replay_equivalence_mode()
    summary["replay_equivalence_mode"] = mode
    strict = _replay_equivalence_strict(mode=mode)
    summary["replay_equivalence_strict"] = strict
    auto_seed = _replay_equivalence_auto_seed(mode=mode)
    summary["replay_equivalence_auto_seed"] = bool(auto_seed)
    baseline_policy = _replay_equivalence_baseline_policy(mode=mode)
    allow_auto_fallback = _replay_equivalence_auto_fallback_enabled(mode=mode)
    summary["replay_equivalence_baseline_policy"] = baseline_policy
    summary["replay_equivalence_auto_fallback"] = bool(allow_auto_fallback)
    current_fp = str((current_contract or {}).get("fingerprint", "")).strip()
    if current_fp:
        summary["replay_equivalence_contract_fingerprint"] = current_fp

    baseline: Path | None = None
    pinned_baseline: Path | None = None
    baseline_source = ""
    baseline_fallback_reason = ""

    if baseline_policy != "auto_only":
        pinned_baseline = _replay_equivalence_baseline_path(mode=mode)
        if pinned_baseline is not None:
            pinned_baseline = _resolve_replay_equivalence_baseline_path(
                mode=mode,
                baseline_path=pinned_baseline,
                right_report=right_report,
                summary=summary,
            )
            baseline = pinned_baseline
            baseline_source = "pinned"

    if baseline is None and baseline_policy == "auto_only":
        auto_baseline, auto_info = _auto_replay_equivalence_baseline_path(
            mode=mode,
            right_report=right_report,
            summary=summary,
            current_contract=current_contract,
        )
        summary["replay_equivalence_auto_baseline_lookup"] = auto_info
        if auto_baseline is not None:
            baseline = auto_baseline
            baseline_source = "auto_only"

    pinned_contract = (
        _baseline_replay_equivalence_contract(baseline_path=baseline, mode=mode) if baseline is not None else None
    )
    pinned_fp = str((pinned_contract or {}).get("fingerprint", "")).strip()

    if baseline is not None:
        if not baseline.exists():
            baseline_fallback_reason = "baseline_missing"
        elif current_fp and pinned_fp and current_fp != pinned_fp:
            baseline_fallback_reason = "baseline_stale"

    can_auto_fallback = bool(allow_auto_fallback) and baseline_policy in {"pinned_or_auto", "auto_only"}
    if baseline_fallback_reason and can_auto_fallback:
        auto_baseline, auto_info = _auto_replay_equivalence_baseline_path(
            mode=mode,
            right_report=right_report,
            summary=summary,
            current_contract=current_contract,
        )
        summary["replay_equivalence_auto_baseline_lookup"] = auto_info
        if auto_baseline is not None:
            baseline = auto_baseline
            baseline_source = "auto_fallback"
            summary["replay_equivalence_baseline_fallback_reason"] = baseline_fallback_reason
            baseline_fallback_reason = ""

    if baseline is not None:
        summary["replay_equivalence_baseline_path"] = str(baseline)
    if baseline_source:
        summary["replay_equivalence_baseline_source"] = baseline_source

    baseline_contract = (
        _baseline_replay_equivalence_contract(baseline_path=baseline, mode=mode)
        if baseline is not None and baseline.exists()
        else None
    )
    baseline_fp = str((baseline_contract or {}).get("fingerprint", "")).strip()
    if baseline_fp:
        summary["replay_equivalence_baseline_contract_fingerprint"] = baseline_fp

    if baseline is None:
        summary["replay_equivalence_status"] = "not_run"
        summary["replay_equivalence_failure_code"] = _replay_equivalence_failure_code("not_run")
        summary["replay_equivalence_error"] = "AI_QUANT_REPLAY_EQUIVALENCE_BASELINE not configured"
        summary["replay_equivalence_diffs"] = []
        summary["replay_equivalence_count"] = 0
        summary["replay_equivalence_seed_mode"] = bool(auto_seed)
        if auto_seed:
            summary["replay_equivalence_seed_reason"] = "baseline_not_configured"
            return True
        return not strict

    if not baseline.exists():
        summary["replay_equivalence_status"] = "missing_baseline"
        summary["replay_equivalence_failure_code"] = _replay_equivalence_failure_code("missing_baseline")
        summary["replay_equivalence_error"] = f"missing baseline report: {baseline}"
        summary["replay_equivalence_diffs"] = []
        summary["replay_equivalence_count"] = 0
        summary["replay_equivalence_seed_mode"] = bool(auto_seed)
        if auto_seed:
            summary["replay_equivalence_seed_reason"] = "baseline_missing"
            return True
        return not strict

    if current_fp and baseline_fp and current_fp != baseline_fp:
        summary["replay_equivalence_status"] = "baseline_stale"
        summary["replay_equivalence_failure_code"] = _replay_equivalence_failure_code("baseline_stale")
        summary["replay_equivalence_error"] = (
            f"baseline contract fingerprint mismatch: current={current_fp[:12]} baseline={baseline_fp[:12]}"
        )
        summary["replay_equivalence_diffs"] = []
        summary["replay_equivalence_count"] = 0
        summary["replay_equivalence_seed_mode"] = bool(auto_seed)
        if auto_seed:
            summary["replay_equivalence_seed_reason"] = "baseline_stale"
            return True
        return not strict

    try:
        from tools import replay_equivalence
    except Exception as exc:
        summary["replay_equivalence_status"] = "tool_unavailable"
        summary["replay_equivalence_failure_code"] = _replay_equivalence_failure_code("tool_unavailable")
        summary["replay_equivalence_error"] = f"failed to import comparator: {type(exc).__name__}: {exc}"
        summary["replay_equivalence_diffs"] = []
        summary["replay_equivalence_count"] = 0
        return not strict

    try:
        ok, diffs, rep = replay_equivalence.compare_files(
            str(baseline),
            str(right_report),
            tolerance=_replay_equivalence_tolerance(mode=mode),
            max_diffs=_replay_equivalence_max_diffs(mode=mode),
        )
    except Exception as exc:
        summary["replay_equivalence_status"] = "comparison_error"
        summary["replay_equivalence_failure_code"] = _replay_equivalence_failure_code("comparison_error")
        summary["replay_equivalence_error"] = f"{type(exc).__name__}: {exc}"
        summary["replay_equivalence_diffs"] = []
        summary["replay_equivalence_count"] = 0
        return not strict

    report_path = right_report.with_name(f"{right_report.stem}.replay_equivalence.json")
    report_payload = {
        "left_report": str(baseline or right_report),
        "right_report": str(right_report),
        "ok": ok,
        "diffs": diffs,
        "summary": rep,
        "mode": mode,
        "strict": strict,
        "baseline_policy": baseline_policy,
        "baseline_source": baseline_source,
        "baseline_path": str(baseline) if baseline is not None else "",
        "contract_fingerprint": current_fp,
        "baseline_contract_fingerprint": baseline_fp,
    }
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary["replay_equivalence_report_path"] = str(report_path)
    summary["replay_equivalence_status"] = "pass" if ok else "fail"
    summary["replay_equivalence_failure_code"] = _replay_equivalence_failure_code(summary["replay_equivalence_status"])
    summary["replay_equivalence_diffs"] = diffs
    summary["replay_equivalence_count"] = len(diffs)
    summary["replay_equivalence_seed_mode"] = False

    return ok or not strict


def _write_replay_equivalence_baseline_manifest(
    *,
    run_dir: Path,
    meta: dict[str, Any],
    replay_reports: list[dict[str, Any]],
) -> Path | None:
    contract = meta.get("replay_equivalence_contract")
    if not isinstance(contract, dict):
        return None
    contract_fp = str(contract.get("fingerprint", "")).strip()
    if not contract_fp:
        return None

    candidate_meta = meta.get("candidate_configs")
    meta_by_config_id: dict[str, dict[str, Any]] = {}
    if isinstance(candidate_meta, list):
        for row in candidate_meta:
            if not isinstance(row, dict):
                continue
            cfg_id = str(row.get("config_id", "") or "").strip()
            if cfg_id and cfg_id not in meta_by_config_id:
                meta_by_config_id[cfg_id] = row

    rows: list[dict[str, Any]] = []
    for rep in replay_reports:
        if not isinstance(rep, dict):
            continue
        cfg_id = str(rep.get("config_id", "")).strip()
        replay_path = str(rep.get("path", "") or rep.get("replay_report_path", "")).strip()
        if not cfg_id or not replay_path:
            continue
        meta_row = meta_by_config_id.get(cfg_id, {})
        config_path = str(
            rep.get("config_path", "") or meta_row.get("path", "") or meta_row.get("config_path", "")
        ).strip()
        config_sha256 = str(rep.get("config_sha256", "") or meta_row.get("config_sha256", "")).strip()
        sort_by = str(rep.get("sort_by", "") or meta_row.get("sort_by", "")).strip()
        rank = int(_coerce_int(rep.get("rank", meta_row.get("rank", 0)), 0) or 0)
        overrides_key = str(rep.get("overrides_key", "") or meta_row.get("overrides_key", "")).strip()
        rows.append(
            {
                "config_id": cfg_id,
                "replay_report_path": replay_path,
                "config_path": config_path,
                "config_sha256": config_sha256,
                "sort_by": sort_by,
                "rank": int(rank) if rank > 0 else 0,
                "overrides_key": overrides_key,
                "replay_equivalence_status": str(rep.get("replay_equivalence_status", "")).strip().lower(),
                "seed_mode": bool(rep.get("replay_equivalence_seed_mode", False)),
            }
        )

    payload = {
        "schema_version": 1,
        "generated_at_ms": int(_coerce_int(meta.get("generated_at_ms"), 0) or int(time.time() * 1000)),
        "run_id": str(meta.get("run_id", "")).strip(),
        "run_dir": str(run_dir),
        "contract": contract,
        "candidate_count": len(rows),
        "seed_mode_count": int(sum(1 for row in rows if bool(row.get("seed_mode", False)))),
        "candidates": rows,
    }
    out_path = run_dir / "replay_equivalence_baseline_manifest.json"
    _write_json(out_path, payload)
    meta["replay_equivalence_baseline_manifest"] = str(out_path)
    meta["replay_equivalence_baseline_candidate_count"] = int(payload["candidate_count"])
    meta["replay_equivalence_seed_mode_count"] = int(payload["seed_mode_count"])
    return out_path


def _render_ranked_report_md(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Factory Run Report")
    lines.append("")
    if not items:
        lines.append("No replay reports were produced.")
        lines.append("")
        return "\n".join(lines)

    kept = [it for it in items if not bool(it.get("rejected"))]
    rejected = [it for it in items if bool(it.get("rejected"))]

    if not kept:
        lines.append("No non-rejected replay reports were produced.")
        lines.append("")
    else:
        scored = [it for it in kept if isinstance(it.get("score_v1"), (int, float))]
        unscored = [it for it in kept if not isinstance(it.get("score_v1"), (int, float))]
        if scored:
            items_sorted = sorted(scored, key=lambda x: float(x.get("score_v1", float("-inf"))), reverse=True)

            lines.append("## Ranked Candidates (by score_v1, excluding rejected)")
            lines.append("")
            lines.append(
                "| Rank | score_v1 | oos_med_daily_ret | oos_max_dd_pct | slip_frag | trades_pen | trades | total_pnl | config_id | replay |"
            )
            lines.append(
                "| ---: | -------: | ---------------: | ------------: | --------: | --------: | -----: | --------: | :------ | :----- |"
            )
            for i, it in enumerate(items_sorted, start=1):
                cfg_id = str(it.get("config_id", ""))
                cfg_id_short = cfg_id[:12] if len(cfg_id) > 12 else cfg_id
                comps = it.get("score_v1_components", {})
                trades_pen = float(comps.get("trades_penalty", 0.0)) if isinstance(comps, dict) else 0.0
                lines.append(
                    "| {rank} | {score:.6f} | {oos:.6f} | {dd:.4f} | {slip:.6f} | {tpen:.6f} | {trades} | {pnl:.2f} | `{cfg_id}` | `{path}` |".format(
                        rank=i,
                        score=float(it.get("score_v1", 0.0)),
                        oos=float(it.get("wf_median_oos_daily_return", 0.0)),
                        dd=float(it.get("wf_max_oos_drawdown_pct", 0.0)),
                        slip=float(it.get("slippage_fragility", 0.0)),
                        tpen=float(trades_pen),
                        trades=int(it.get("total_trades", 0)),
                        pnl=float(it.get("total_pnl", 0.0)),
                        cfg_id=cfg_id_short,
                        path=str(it.get("path", "")),
                    )
                )
            lines.append("")
            if unscored:
                lines.append(f"Note: {len(unscored)} candidate(s) had no score_v1 (missing validation artefacts).")
                lines.append("")
        else:
            items_sorted = sorted(kept, key=lambda x: float(x.get("total_pnl", 0.0)), reverse=True)

            lines.append("## Ranked Candidates (by total_pnl, excluding rejected)")
            lines.append("")
            lines.append("| Rank | total_pnl | max_dd_pct | trades | win_rate | profit_factor | config_id | report |")
            lines.append("| ---: | --------: | ---------: | -----: | -------: | ------------: | :------ | :----- |")
            for i, it in enumerate(items_sorted, start=1):
                cfg_id = str(it.get("config_id", ""))
                cfg_id_short = cfg_id[:12] if len(cfg_id) > 12 else cfg_id
                lines.append(
                    "| {rank} | {pnl:.2f} | {dd:.4f} | {trades} | {wr:.4f} | {pf:.4f} | `{cfg_id}` | `{path}` |".format(
                        rank=i,
                        pnl=float(it.get("total_pnl", 0.0)),
                        dd=float(it.get("max_drawdown_pct", 0.0)),
                        trades=int(it.get("total_trades", 0)),
                        wr=float(it.get("win_rate", 0.0)),
                        pf=float(it.get("profit_factor", 0.0)),
                        cfg_id=cfg_id_short,
                        path=str(it.get("path", "")),
                    )
                )
            lines.append("")

    if rejected:
        lines.append("## Rejected Candidates")
        lines.append("")
        lines.append(
            "| total_pnl | config_id | reason | replay | slippage_fragility | reject_bps | pnl_drop_reject_bps | pnl_reject_bps |"
        )
        lines.append(
            "| --------: | :------ | :----- | :----- | -----------------: | ---------: | ------------------: | ------------: |"
        )
        rej_sorted = sorted(rejected, key=lambda x: float(x.get("total_pnl", 0.0)), reverse=True)
        for it in rej_sorted:
            cfg_id = str(it.get("config_id", ""))
            cfg_id_short = cfg_id[:12] if len(cfg_id) > 12 else cfg_id
            reason = str(it.get("reject_reason", "rejected"))
            lines.append(
                "| {pnl:.2f} | `{cfg}` | {reason} | `{path}` | {frag:.6f} | {rbps:.0f} | {drop:.2f} | {pnl_r:.2f} |".format(
                    pnl=float(it.get("total_pnl", 0.0)),
                    cfg=cfg_id_short,
                    reason=reason,
                    path=str(it.get("path", "")),
                    frag=float(it.get("slippage_fragility", 0.0)),
                    rbps=float(it.get("slippage_reject_bps", 0.0)),
                    drop=float(it.get("pnl_drop_at_reject_bps", 0.0)),
                    pnl_r=float(it.get("slippage_pnl_at_reject_bps", 0.0)),
                )
            )
        lines.append("")
    return "\n".join(lines)


def _render_validation_report_md(items: list[dict[str, Any]], *, score_min_trades: int) -> str:
    lines: list[str] = []
    lines.append("# Validation Report")
    lines.append("")
    lines.append("This report lists per-candidate validation signals and human-readable reasons.")
    lines.append("")
    if not items:
        lines.append("No candidates were produced.")
        lines.append("")
        return "\n".join(lines)

    def _has_num(v: Any) -> bool:
        return isinstance(v, (int, float))

    def _sort_key(it: dict[str, Any]) -> tuple[int, float]:
        if _has_num(it.get("score_v1")):
            return (2, float(it.get("score_v1", 0.0)))
        return (1, float(it.get("total_pnl", 0.0)))

    def _reasons(it: dict[str, Any]) -> list[str]:
        out: list[str] = []
        rr = str(it.get("reject_reason", "") or "").strip()
        if rr:
            out.append(rr)

        try:
            if "wf_median_oos_daily_return" in it and float(it.get("wf_median_oos_daily_return", 0.0)) < 0.0:
                out.append("OOS negative (median daily return < 0)")
        except Exception:
            pass

        try:
            if int(it.get("total_trades", 0)) < int(score_min_trades):
                out.append(f"too few trades (trades < {int(score_min_trades)})")
        except Exception:
            pass

        if not _has_num(it.get("score_v1")):
            out.append("missing score_v1 (enable --walk-forward and --slippage-stress)")

        # Deduplicate while preserving order.
        seen: set[str] = set()
        dedup: list[str] = []
        for r in out:
            if r in seen:
                continue
            seen.add(r)
            dedup.append(r)
        return dedup

    items_sorted = sorted(items, key=_sort_key, reverse=True)

    for i, it in enumerate(items_sorted, start=1):
        cfg_id = str(it.get("config_id", "")).strip()
        cfg_id_short = cfg_id[:12] if len(cfg_id) > 12 else cfg_id
        status = "REJECT" if bool(it.get("rejected")) else "ACCEPT"

        lines.append(f"## Candidate {i}: `{cfg_id_short}`")
        lines.append("")
        lines.append(f"- Status: {status}")
        if _has_num(it.get("score_v1")):
            lines.append(f"- score_v1: {float(it.get('score_v1', 0.0)):.6f}")
        else:
            lines.append("- score_v1: n/a")
        lines.append(f"- total_pnl: {float(it.get('total_pnl', 0.0)):.2f}")
        lines.append(f"- max_drawdown_pct: {float(it.get('max_drawdown_pct', 0.0)):.4f}")
        lines.append(f"- trades: {int(it.get('total_trades', 0))}")
        if _has_num(it.get("wf_median_oos_daily_return")):
            lines.append(f"- OOS median daily return: {float(it.get('wf_median_oos_daily_return', 0.0)):.6f}")
        if _has_num(it.get("wf_max_oos_drawdown_pct")):
            lines.append(f"- OOS max drawdown pct: {float(it.get('wf_max_oos_drawdown_pct', 0.0)):.4f}")
        if _has_num(it.get("slippage_fragility")):
            lines.append(f"- slippage fragility: {float(it.get('slippage_fragility', 0.0)):.6f}")
        if _has_num(it.get("sensitivity_positive_rate")):
            lines.append(f"- sensitivity positive rate: {float(it.get('sensitivity_positive_rate', 0.0)):.4f}")
        if _has_num(it.get("sensitivity_median_total_pnl")):
            lines.append(f"- sensitivity median total_pnl: {float(it.get('sensitivity_median_total_pnl', 0.0)):.2f}")
        if _has_num(it.get("sensitivity_metric_v1")):
            lines.append(f"- sensitivity metric v1: {float(it.get('sensitivity_metric_v1', 0.0)):.4f}")
        mc_ci = it.get("monte_carlo_ci")
        if isinstance(mc_ci, dict) and mc_ci:
            method = "bootstrap" if "bootstrap" in mc_ci else sorted([str(k) for k in mc_ci.keys()])[0]
            payload = mc_ci.get(method, {})
            if isinstance(payload, dict):
                r_ci = payload.get("return_pct_ci95")
                dd_ci = payload.get("max_drawdown_pct_ci95")
                if isinstance(r_ci, list) and len(r_ci) == 2:
                    lines.append(f"- MC {method} return CI95: [{float(r_ci[0]):.6f}, {float(r_ci[1]):.6f}]")
                if isinstance(dd_ci, list) and len(dd_ci) == 2:
                    lines.append(f"- MC {method} max DD pct CI95: [{float(dd_ci[0]):.6f}, {float(dd_ci[1]):.6f}]")
        cu = it.get("cross_universe")
        if isinstance(cu, dict) and cu:
            names = sorted([str(k) for k in cu.keys() if str(k).strip()])
            for name in names[:3]:
                payload = cu.get(name, {})
                if not isinstance(payload, dict):
                    continue
                lines.append(
                    "- cross-universe {name}: share_net_pnl={pnl:.4f}, share_trades={tr:.4f}, subset_net_pnl={sub:.2f}".format(
                        name=name,
                        pnl=float(payload.get("share_net_pnl_usd", 0.0) or 0.0),
                        tr=float(payload.get("share_trades", 0.0) or 0.0),
                        sub=float(payload.get("subset_net_pnl_usd", 0.0) or 0.0),
                    )
                )
        if _has_num(it.get("top1_pnl_pct")):
            lines.append(f"- top1 pnl pct: {float(it.get('top1_pnl_pct', 0.0)):.4f}")
        if _has_num(it.get("top5_pnl_pct")):
            lines.append(f"- top5 pnl pct: {float(it.get('top5_pnl_pct', 0.0)):.4f}")
        if _has_num(it.get("long_pnl_usd")) or _has_num(it.get("short_pnl_usd")):
            lines.append(
                f"- long/short pnl: {float(it.get('long_pnl_usd', 0.0)):.2f} / {float(it.get('short_pnl_usd', 0.0)):.2f}"
            )
        rs = _reasons(it)
        lines.append(f"- Reasons: {'; '.join(rs) if rs else 'none'}")
        lines.append("")

    return "\n".join(lines)


def _normalise_overrides(raw_overrides: Any) -> list[tuple[str, Any]]:
    """Accept both list-of-pairs and dict formats (matches tools/generate_config.py)."""

    if isinstance(raw_overrides, dict):
        out = list(raw_overrides.items())
    elif isinstance(raw_overrides, list):
        out = []
        for pair in raw_overrides:
            if isinstance(pair, (list, tuple)) and len(pair) == 2 and isinstance(pair[0], str):
                out.append((pair[0], pair[1]))
    else:
        out = []
    out.sort(key=lambda kv: kv[0])
    return out


def _format_overrides_key(raw_overrides: Any) -> str:
    parts: list[str] = []
    for k, v in _normalise_overrides(raw_overrides):
        if isinstance(v, float):
            parts.append(f"{k}={v:.10g}")
        else:
            parts.append(f"{k}={v}")
    return ",".join(parts)


def _write_tsv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _compute_step4_parity(
    *,
    cpu: dict[str, Any],
    gpu: dict[str, Any],
    rel_eps: float,
    abs_eps: float,
    dd_eps: float,
    pf_eps: float,
) -> dict[str, Any]:
    """Compute Step-4 CPU vs GPU deltas and pass/fail classification."""

    cpu_pnl = float(_coerce_float(cpu.get("total_pnl"), 0.0))
    gpu_pnl = float(_coerce_float(gpu.get("total_pnl"), 0.0))
    cpu_bal = float(_coerce_float(cpu.get("final_balance"), 0.0))
    gpu_bal = float(_coerce_float(gpu.get("final_balance"), 0.0))
    cpu_dd = float(_coerce_float(cpu.get("max_drawdown_pct"), 0.0))
    gpu_dd = float(_coerce_float(gpu.get("max_drawdown_pct"), 0.0))
    cpu_pf = float(_coerce_float(cpu.get("profit_factor"), 0.0))
    gpu_pf = float(_coerce_float(gpu.get("profit_factor"), 0.0))
    cpu_trades = int(_coerce_int(cpu.get("total_trades"), 0) or 0)
    gpu_trades = int(_coerce_int(gpu.get("total_trades"), 0) or 0)

    init_bal = float(_coerce_float(cpu.get("initial_balance"), 0.0))

    # Some sweep outputs omit final_balance; derive it from initial_balance + pnl.
    if ("final_balance" not in gpu or gpu.get("final_balance") in (None, "")) and init_bal:
        gpu_bal = init_bal + gpu_pnl
    if ("final_balance" not in cpu or cpu.get("final_balance") in (None, "")) and init_bal:
        cpu_bal = init_bal + cpu_pnl
    scale = max(abs(cpu_bal), abs(gpu_bal), abs(cpu_pnl), abs(gpu_pnl), abs(init_bal), 1.0)

    pnl_delta = cpu_pnl - gpu_pnl
    bal_delta = cpu_bal - gpu_bal
    dd_delta = cpu_dd - gpu_dd
    pf_delta = cpu_pf - gpu_pf
    trades_delta = cpu_trades - gpu_trades

    pnl_ok = abs(pnl_delta) <= max(abs_eps, rel_eps * scale)
    bal_ok = abs(bal_delta) <= max(abs_eps, rel_eps * scale)
    dd_ok = abs(dd_delta) <= dd_eps
    pf_ok = abs(pf_delta) <= pf_eps
    trades_ok = trades_delta == 0

    status = "pass" if (trades_ok and pnl_ok and bal_ok and dd_ok and pf_ok) else "fail"
    if status == "pass":
        cause = ""
    elif not trades_ok:
        cause = "state_machine"
    else:
        cause = "reduction_order"

    return {
        "status": status,
        "cause": cause,
        "cpu_total_pnl": cpu_pnl,
        "gpu_total_pnl": gpu_pnl,
        "pnl_delta": pnl_delta,
        "cpu_final_balance": cpu_bal,
        "gpu_final_balance": gpu_bal,
        "balance_delta": bal_delta,
        "cpu_max_drawdown_pct": cpu_dd,
        "gpu_max_drawdown_pct": gpu_dd,
        "dd_delta": dd_delta,
        "cpu_profit_factor": cpu_pf,
        "gpu_profit_factor": gpu_pf,
        "pf_delta": pf_delta,
        "cpu_total_trades": cpu_trades,
        "gpu_total_trades": gpu_trades,
        "trades_delta": trades_delta,
        "scale": scale,
        "thresholds": {
            "rel_eps": float(rel_eps),
            "abs_eps": float(abs_eps),
            "dd_eps": float(dd_eps),
            "pf_eps": float(pf_eps),
        },
    }


def _render_step4_parity_report_md(
    items: list[dict[str, Any]],
    *,
    contract_fingerprint: str,
    thresholds: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Step-4 GPU↔CPU Parity Report")
    lines.append("")
    lines.append(f"Contract fingerprint: `{contract_fingerprint}`")
    lines.append("")
    lines.append("Thresholds: " + ", ".join(f"{k}={v}" for k, v in sorted(thresholds.items())))
    lines.append("")
    if not items:
        lines.append("No parity items were generated.")
        lines.append("")
        return "\n".join(lines)

    lines.append("| status | cause | mode | rank | trades Δ | pnl Δ | dd Δ | pf Δ | config | overrides |")
    lines.append("| :----: | :---- | :--- | ---: | -------: | ----: | ---: | ---: | :----- | :------- |")
    for it in items:
        lines.append(
            "| {status} | {cause} | {mode} | {rank} | {td} | {pnl:.6f} | {dd:.6f} | {pf:.6f} | `{cfg}` | `{ov}` |".format(
                status=str(it.get("status", "")),
                cause=str(it.get("cause", "")),
                mode=str(it.get("sort_by", "")),
                rank=int(_coerce_int(it.get("rank"), 0) or 0),
                td=int(_coerce_int(it.get("trades_delta"), 0) or 0),
                pnl=float(_coerce_float(it.get("pnl_delta"), 0.0)),
                dd=float(_coerce_float(it.get("dd_delta"), 0.0)),
                pf=float(_coerce_float(it.get("pf_delta"), 0.0)),
                cfg=str(it.get("config_path", "") or ""),
                ov=str(it.get("overrides_key", "") or ""),
            )
        )

    lines.append("")
    return "\n".join(lines)


def _run_date_utc(generated_at_ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(generated_at_ms / 1000))


def resolve_run_dir(*, artifacts_root: Path, run_id: str, generated_at_ms: int) -> Path:
    """Resolve a standard run directory path under the artifacts root.

    Layout:
      artifacts_root/YYYY-MM-DD/run_<run_id>/
    """

    run_date = _run_date_utc(generated_at_ms)
    return (artifacts_root / run_date / f"run_{run_id}").resolve()


def _utc_compact(ts_ms: int) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(int(ts_ms) / 1000))


def _registry_lookup_run_dir(*, artifacts_root: Path, run_id: str) -> Path | None:
    registry_db = default_registry_db_path(artifacts_root=artifacts_root)
    if not registry_db.exists():
        return None
    uri = f"file:{registry_db}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=2.0)
    try:
        row = con.execute("SELECT run_dir FROM runs WHERE run_id = ? LIMIT 1", (str(run_id),)).fetchone()
        if not row:
            return None
        run_dir = str(row[0] or "").strip()
        return Path(run_dir).expanduser().resolve() if run_dir else None
    finally:
        con.close()


def _scan_lookup_run_dir(*, artifacts_root: Path, run_id: str) -> Path | None:
    """Fallback when registry is missing: scan artifacts for a matching run_id."""
    target = str(run_id).strip()
    if not target:
        return None
    for date_dir in sorted([p for p in artifacts_root.iterdir() if p.is_dir()]):
        for run_dir in sorted([p for p in date_dir.iterdir() if p.is_dir() and p.name.startswith("run_")]):
            meta_path = run_dir / "run_metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = _load_json(meta_path)
            except Exception:
                continue
            if str(meta.get("run_id", "")).strip() == target:
                return run_dir.resolve()
    return None


def _find_existing_run_dir(*, artifacts_root: Path, run_id: str) -> Path:
    p = _registry_lookup_run_dir(artifacts_root=artifacts_root, run_id=run_id)
    if p is None:
        p = _scan_lookup_run_dir(artifacts_root=artifacts_root, run_id=run_id)
    if p is None:
        raise FileNotFoundError(f"Could not locate run_id={run_id} under {artifacts_root}")
    return p


def _reproduce_run(*, artifacts_root: Path, source_run_id: str) -> int:
    """Re-run CPU replay/reporting for an existing run_id.

    This creates a new run directory with a derived run_id. It does not modify the original run directory.
    """
    source_run_id = str(source_run_id).strip()
    if not source_run_id:
        raise SystemExit("--reproduce cannot be empty")

    source_run_dir = _find_existing_run_dir(artifacts_root=artifacts_root, run_id=source_run_id)
    source_meta = _load_json(source_run_dir / "run_metadata.json")
    source_args = source_meta.get("args", {}) if isinstance(source_meta.get("args", {}), dict) else {}

    interval = str(source_args.get("interval", "30m"))
    candles_db = source_args.get("candles_db")
    funding_db = source_args.get("funding_db")
    candles_db_bt = _normalise_candles_db_arg_for_backtester(str(candles_db)) if candles_db else None
    funding_db_bt = _resolve_path_for_backtester(str(funding_db)) if funding_db else None
    source_gpu_requested = bool(source_args.get("gpu")) or bool(source_args.get("tpe"))
    replay_uses_funding = bool(funding_db_bt)

    generated_at_ms = int(time.time() * 1000)
    new_run_id = f"repro_{source_run_id}_{_utc_compact(generated_at_ms)}"
    run_dir = resolve_run_dir(artifacts_root=artifacts_root, run_id=new_run_id, generated_at_ms=generated_at_ms)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {
        "run_id": new_run_id,
        "generated_at_ms": generated_at_ms,
        "run_date_utc": _run_date_utc(generated_at_ms),
        "run_dir": str(run_dir),
        "git_head": _git_head_sha(),
        "args": source_args,
        "steps": [],
        "reproduce_of_run_id": source_run_id,
        "reproduce_source_run_dir": str(source_run_dir),
        "reproduce_source_git_head": str(source_meta.get("git_head", "")).strip(),
    }
    if funding_db_bt:
        meta["funding_model"] = {
            "funding_db_path": str(funding_db_bt),
            "source_gpu_path_requested": bool(source_gpu_requested),
            "applied_to_replay": bool(replay_uses_funding),
            "reason": "enabled_cpu_and_gpu_settlement_model",
        }
    replay_mode = _replay_equivalence_mode()
    replay_contract = _replay_equivalence_contract_from_meta(meta, mode=replay_mode)
    if replay_contract is not None:
        meta["replay_equivalence_contract"] = replay_contract

    bt_cmd = _resolve_backtester_cmd()
    _capture_repro_metadata(run_dir=run_dir, artifacts_root=artifacts_root, bt_cmd=bt_cmd, meta=meta)
    _write_json(run_dir / "run_metadata.json", meta)

    # ------------------------------------------------------------------
    # Copy configs from the source run
    # ------------------------------------------------------------------
    src_candidates = source_meta.get("candidate_configs", [])
    if not isinstance(src_candidates, list) or not src_candidates:
        raise FileNotFoundError(f"Missing candidate_configs in {source_run_dir / 'run_metadata.json'}")

    # Prefer reproducing only the candidates that were actually selected for replay.
    # Older runs may not have `selected`, so fall back to all entries.
    src_candidates_all = src_candidates
    src_candidates = [
        it for it in src_candidates_all if isinstance(it, dict) and ("selected" not in it or bool(it.get("selected")))
    ]
    if not src_candidates:
        src_candidates = [it for it in src_candidates_all if isinstance(it, dict)]

    configs_dir = run_dir / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    candidate_paths: list[Path] = []
    candidate_config_ids: dict[str, str] = {}
    copied_candidates: list[dict[str, Any]] = []
    entry_by_path: dict[str, dict[str, Any]] = {}

    source_args_obj = argparse.Namespace(**source_args) if isinstance(source_args, dict) else argparse.Namespace()
    source_stage_defaults = _stage_defaults_for_candidate(args=source_args_obj)
    for it in src_candidates:
        if not isinstance(it, dict):
            continue
        src_path = str(it.get("path", "")).strip()
        src_cfg_id = str(it.get("config_id", "")).strip()
        if not src_path or not src_cfg_id:
            continue

        src = Path(src_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"Missing source config file: {src}")

        dst = (configs_dir / src.name).resolve()
        shutil.copy2(src, dst)

        dst_cfg_id = config_id_from_yaml_file(dst)
        if dst_cfg_id != src_cfg_id:
            raise ValueError(f"config_id mismatch for {dst}: expected {src_cfg_id}, got {dst_cfg_id}")

        candidate_paths.append(dst)
        candidate_config_ids[str(dst)] = dst_cfg_id
        had_candidate_mode = "candidate_mode" in it
        entry = dict(source_stage_defaults)
        entry.update(
            {k: v for k, v in it.items() if isinstance(v, (str, int, float, bool, dict, list, tuple, type(None)))}
        )
        if not had_candidate_mode:
            entry["candidate_mode"] = False
        entry["path"] = str(dst)
        entry["config_id"] = dst_cfg_id
        entry["config_sha256"] = _sha256_file_optional(dst)
        entry["source_path"] = str(src)
        entry.setdefault("replay_stage", "")
        entry.setdefault("canonical_cpu_verified", False)
        copied_candidates.append(entry)
        entry_by_path[str(dst)] = entry

    if not candidate_paths:
        raise ValueError("No candidate configs found to reproduce")

    meta["candidate_configs"] = copied_candidates

    # ------------------------------------------------------------------
    # CPU replay / validation (v1: run replay once per candidate)
    # ------------------------------------------------------------------
    replays_dir = run_dir / "replays"
    replays_dir.mkdir(parents=True, exist_ok=True)

    replay_reports: list[dict[str, Any]] = []
    for cfg_path in candidate_paths:
        out_json = replays_dir / f"{cfg_path.stem}.replay.json"
        replay_argv = bt_cmd + [
            "replay",
            "--config",
            str(cfg_path),
            "--interval",
            interval,
            "--output",
            str(out_json),
        ]
        if candles_db_bt:
            replay_argv += [
                "--candles-db",
                str(candles_db_bt),
                "--exit-candles-db",
                str(candles_db_bt),
                "--entry-candles-db",
                str(candles_db_bt),
            ]
        if replay_uses_funding:
            replay_argv += ["--funding-db", str(funding_db_bt)]

        replay_res = _run_cmd(
            replay_argv,
            cwd=AIQ_ROOT / "backtester",
            stdout_path=run_dir / "replays" / f"{cfg_path.stem}.stdout.txt",
            stderr_path=run_dir / "replays" / f"{cfg_path.stem}.stderr.txt",
        )
        meta["steps"].append({"name": f"replay_{cfg_path.stem}", **replay_res.__dict__})
        if replay_res.exit_code != 0:
            _write_json(run_dir / "run_metadata.json", meta)
            return int(replay_res.exit_code)

        summary = _summarise_replay_report(out_json)
        summary["config_path"] = str(cfg_path)
        summary["config_id"] = candidate_config_ids[str(cfg_path)]
        summary["config_sha256"] = _sha256_file_optional(cfg_path)
        replay_entry = entry_by_path.get(str(cfg_path))
        if isinstance(replay_entry, dict):
            for identity_field in ("sort_by", "rank", "overrides_key", "config_sha256"):
                if identity_field in replay_entry:
                    summary[identity_field] = replay_entry[identity_field]
        if not _run_replay_equivalence_check(
            right_report=out_json,
            summary=summary,
            current_contract=meta.get("replay_equivalence_contract")
            if isinstance(meta.get("replay_equivalence_contract"), dict)
            else None,
        ):
            _write_json(run_dir / "run_metadata.json", meta)
            return 1
        _attach_replay_metadata(summary=summary, entry=replay_entry, args=source_args_obj)
        replay_reports.append(summary)
        _write_json(run_dir / "run_metadata.json", meta)

        if replay_entry is not None:
            replay_entry["replay_report_path"] = str(out_json)
            replay_entry["replay_stdout_path"] = str(replay_res.stdout_path or "")
            replay_entry["replay_stderr_path"] = str(replay_res.stderr_path or "")

    _write_replay_equivalence_baseline_manifest(
        run_dir=run_dir,
        meta=meta,
        replay_reports=replay_reports,
    )

    # ------------------------------------------------------------------
    # Reports + registry
    # ------------------------------------------------------------------
    report_md = _render_ranked_report_md(replay_reports)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports" / "report.md").write_text(report_md, encoding="utf-8")
    _write_json(run_dir / "reports" / "report.json", {"items": replay_reports})

    validation_md = _render_validation_report_md(
        replay_reports, score_min_trades=int(source_args.get("score_min_trades", 30) or 30)
    )
    (run_dir / "reports" / "validation_report.md").write_text(validation_md, encoding="utf-8")

    _write_json(run_dir / "run_metadata.json", meta)

    registry_db = default_registry_db_path(artifacts_root=artifacts_root)
    meta["registry_db"] = str(registry_db)
    try:
        res = ingest_run_dir(registry_db=registry_db, run_dir=run_dir)
        meta["registry_ingest"] = res.__dict__
    except Exception as e:
        meta["registry_error"] = str(e)
        _write_json(run_dir / "run_metadata.json", meta)
        return 1

    _write_json(run_dir / "run_metadata.json", meta)
    return 0


def _ensure_cuda_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an env dict with CUDA/WSL library paths added to LD_LIBRARY_PATH.

    The process-global ``os.environ`` is never mutated.
    """
    out = dict(os.environ if env is None else env)
    cuda_paths = [
        "/usr/lib/wsl/lib",
        "/usr/lib/x86_64-linux-gnu",
    ]
    current = str(out.get("LD_LIBRARY_PATH", "") or "")
    parts = [p for p in current.split(":") if p]
    for cp in cuda_paths:
        if Path(cp).is_dir() and cp not in parts:
            parts.append(cp)
    out["LD_LIBRARY_PATH"] = ":".join(parts)
    return out


def _resolve_subprocess_env(*, cwd: Path, env: dict[str, str] | None) -> dict[str, str] | None:
    """Resolve subprocess environment, injecting CUDA paths only for Rust backtester cwd."""
    try:
        is_backtester_cwd = cwd.resolve() == (AIQ_ROOT / "backtester").resolve()
    except Exception:
        is_backtester_cwd = False

    if is_backtester_cwd:
        return _ensure_cuda_env(env)
    if env is None:
        return None
    return dict(env)


def main(argv: list[str] | None = None) -> int:
    _reset_shutdown_state()
    prev_handlers = _install_shutdown_handlers()
    run_dir: Path | None = None
    meta: dict[str, Any] | None = None
    current_stage = "initialisation"
    try:
        args = _parse_cli_args(argv)

        artifacts_root = (AIQ_ROOT / str(args.artifacts_dir)).resolve()
        if args.reproduce and args.resume:
            raise SystemExit("--resume cannot be used with --reproduce")
        if args.reproduce:
            return _reproduce_run(artifacts_root=artifacts_root, source_run_id=str(args.reproduce))

        run_id = str(args.run_id).strip()
        if not run_id:
            raise SystemExit("--run-id cannot be empty")

        existing_run_dir: Path | None = None
        try:
            existing_run_dir = _find_existing_run_dir(artifacts_root=artifacts_root, run_id=run_id)
        except FileNotFoundError:
            existing_run_dir = None

        resuming_run = existing_run_dir is not None

        now_ms = int(time.time() * 1000)

        if existing_run_dir is not None:
            if not bool(args.resume):
                raise SystemExit(f"run_id already exists; use --resume to continue: {run_id}")
            run_dir = existing_run_dir
            (run_dir / "logs").mkdir(parents=True, exist_ok=True)
            meta_path = run_dir / "run_metadata.json"
            meta_obj = _load_json(meta_path) if meta_path.exists() else {}
            meta = meta_obj if isinstance(meta_obj, dict) else {}

            # Safety: do not allow resuming with different core parameters.
            orig_args = meta.get("args", {}) if isinstance(meta.get("args", {}), dict) else {}

            # Backward-compatible defaults for older run_metadata.json files.
            orig_args.setdefault("start_ts", "")
            orig_args.setdefault("end_ts", "")
            orig_args.setdefault("sweep_parity_mode", "production")
            guard_keys = {
                "config",
                "interval",
                "start_ts",
                "end_ts",
                "candles_db",
                "funding_db",
                "max_age_fail_hours",
                "funding_max_stale_symbols",
                "sweep_spec",
                "gpu",
                "concentration_checks",
                "conc_max_top1_pnl_pct",
                "conc_max_top5_pnl_pct",
                "conc_min_symbols_traded",
                "walk_forward",
                "walk_forward_splits_json",
                "walk_forward_min_test_days",
                "slippage_stress",
                "slippage_stress_bps",
                "slippage_stress_reject_bps",
                "sensitivity_checks",
                "sensitivity_perturb",
                "sensitivity_timeout_s",
                "monte_carlo",
                "monte_carlo_iters",
                "monte_carlo_seed",
                "monte_carlo_methods",
                "cross_universe_set",
                "score_min_trades",
                "score_trades_penalty_weight",
                "tpe",
                "tpe_trials",
                "tpe_batch",
                "tpe_seed",
                "top_n",
                "num_candidates",
                "sort_by",
                "shortlist_modes",
                "shortlist_per_mode",
                "shortlist_max_rank",
                "shortlist_top_pnl",
                "sweep_parity_mode",
            }
            mismatches: list[str] = []
            for k in sorted(guard_keys):
                if k not in orig_args:
                    continue
                if getattr(args, k, None) != orig_args.get(k):
                    mismatches.append(k)
            if mismatches:
                raise SystemExit(f"--resume args mismatch for keys: {', '.join(mismatches)}")

            # Use original args when available to keep the run reproducible.
            # Skip flags that are session-specific overrides (not part of reproducibility).
            _resume_skip_keys = {"resume", "allow_binary_drift", "allow_input_drift"}
            for k, v in orig_args.items():
                if k in _resume_skip_keys:
                    continue
                if hasattr(args, k):
                    setattr(args, k, v)

            meta.setdefault("run_id", run_id)
            meta.setdefault("run_dir", str(run_dir))
            meta.setdefault("steps", [])
            meta["resumed_at_ms"] = now_ms
            meta["resumed_git_head"] = _git_head_sha()
        else:
            generated_at_ms = now_ms
            run_dir = resolve_run_dir(artifacts_root=artifacts_root, run_id=run_id, generated_at_ms=generated_at_ms)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "logs").mkdir(parents=True, exist_ok=True)

            args_meta = dict(vars(args))
            args_meta.pop("resume", None)
            meta = {
                "run_id": run_id,
                "generated_at_ms": generated_at_ms,
                "run_date_utc": _run_date_utc(generated_at_ms),
                "run_dir": str(run_dir),
                "git_head": _git_head_sha(),
                "args": args_meta,
                "steps": [],
            }

        replay_mode = _replay_equivalence_mode()
        replay_contract = _replay_equivalence_contract_from_meta(meta, mode=replay_mode)
        if replay_contract is not None:
            meta["replay_equivalence_contract"] = replay_contract

        # Resolve backtester cmd once and persist early metadata.
        bt_cmd = _resolve_backtester_cmd()

        # Resume safety: prevent silent binary drift (a common source of "regressions").
        if resuming_run and not bool(getattr(args, "allow_binary_drift", False)):
            try:
                repro_obj = meta.get("repro") if isinstance(meta.get("repro"), dict) else {}
                orig_cmd = repro_obj.get("backtester_cmd") if isinstance(repro_obj.get("backtester_cmd"), list) else []
                if orig_cmd and list(orig_cmd) != list(bt_cmd):
                    raise SystemExit("--resume refused: backtester_cmd changed; pass --allow-binary-drift to override")
                orig_sha = (
                    repro_obj.get("files", {}).get("mei_backtester_bin", {}).get("sha256", "")
                    if isinstance(repro_obj.get("files"), dict)
                    and isinstance(repro_obj.get("files", {}).get("mei_backtester_bin"), dict)
                    else ""
                )
                bt0 = str(bt_cmd[0]) if bt_cmd else ""
                bt_path = Path(bt0) if bt0 and ("/" in bt0 or bt0.endswith(".exe")) else None
                if orig_sha and bt_path and bt_path.exists():
                    cur_sha = _sha256_file(bt_path)
                    if cur_sha and cur_sha != orig_sha:
                        raise SystemExit(
                            "--resume refused: mei-backtester binary sha256 changed; pass --allow-binary-drift to override"
                        )
            except SystemExit:
                raise
            except Exception:
                # Non-fatal: proceed if we cannot validate.
                pass
        if "repro" not in meta:
            _capture_repro_metadata(run_dir=run_dir, artifacts_root=artifacts_root, bt_cmd=bt_cmd, meta=meta)
        _write_json(run_dir / "run_metadata.json", meta)

        # Snapshot binary SHA256 at start-of-run so we can detect mid-run overwrites
        # (e.g. an unrelated `cargo build` replacing the binary between sweep and replay).
        _bt_bin_path_for_guard: Path | None = None
        _bt_bin_sha_at_start: str = ""
        try:
            _bt0 = str(bt_cmd[0]) if bt_cmd else ""
            if _bt0 and ("/" in _bt0 or _bt0.endswith(".exe")):
                _bt_bin_path_for_guard = Path(_bt0)
                if _bt_bin_path_for_guard.exists():
                    _bt_bin_sha_at_start = _sha256_file(_bt_bin_path_for_guard)
        except Exception:
            pass

        # The backtester is executed with cwd=AIQ_ROOT/backtester, so normalise common repo-relative paths.
        bt_config = _resolve_path_for_backtester(str(args.config)) or str(args.config)
        bt_sweep_spec = _resolve_path_for_backtester(str(args.sweep_spec)) or str(args.sweep_spec)
        bt_candles_db = _normalise_candles_db_arg_for_backtester(str(args.candles_db)) if args.candles_db else None
        bt_funding_db = _resolve_path_for_backtester(str(args.funding_db)) if args.funding_db else None

        # Record lightweight input fingerprints early so resume runs cannot silently
        # compare against a different data snapshot.
        current_inputs = {
            "candles_db": _fingerprint_db_arg(str(bt_candles_db) if bt_candles_db else ""),
            "funding_db": _fingerprint_db_arg(str(bt_funding_db) if bt_funding_db else ""),
        }
        orig_inputs_snapshot = (
            meta.get("input_fingerprints") if isinstance(meta.get("input_fingerprints"), dict) else {}
        )

        if resuming_run and not bool(getattr(args, "allow_input_drift", False)):
            try:
                for key in ("candles_db", "funding_db"):
                    orig_fp = orig_inputs_snapshot.get(key) if isinstance(orig_inputs_snapshot.get(key), dict) else {}
                    cur_fp = current_inputs.get(key) if isinstance(current_inputs.get(key), dict) else {}
                    if str(orig_fp.get("fingerprint", "")) and str(cur_fp.get("fingerprint", "")):
                        if str(orig_fp.get("fingerprint")) != str(cur_fp.get("fingerprint")):
                            raise SystemExit(
                                f"--resume refused: input drift detected for {key}; pass --allow-input-drift to override"
                            )
            except SystemExit:
                raise
            except Exception:
                pass

        if not isinstance(meta.get("input_fingerprints"), dict):
            meta["input_fingerprints"] = {}
        meta["input_fingerprints"].update(current_inputs)
        gpu_path_requested = bool(args.gpu) or bool(getattr(args, "tpe", False))
        funding_for_pairing = bool(bt_funding_db)
        if bt_funding_db:
            meta["funding_model"] = {
                "funding_db_path": str(bt_funding_db),
                "gpu_path_requested": bool(gpu_path_requested),
                "applied_to_sweep": bool(funding_for_pairing),
                "applied_to_cpu_replay": bool(funding_for_pairing),
                "reason": "enabled_cpu_and_gpu_settlement_model",
            }
        candles_db_for_checks = _resolve_path_for_backtester(str(args.candles_db)) if args.candles_db else None
        bt_wf_splits_json = (
            _resolve_path_for_backtester(str(getattr(args, "walk_forward_splits_json", "")))
            if getattr(args, "walk_forward_splits_json", None)
            else None
        )
        assert run_dir is not None
        assert meta is not None

        # ------------------------------------------------------------------
        # 1) Data checks
        # ------------------------------------------------------------------
        current_stage = "data_checks"
        if _shutdown_stage_guard(run_dir=run_dir, meta=meta, stage=current_stage):
            return 130
        data_checks_dir = run_dir / "data_checks"
        data_checks_dir.mkdir(parents=True, exist_ok=True)
        candle_out = data_checks_dir / "candle_dbs.json"
        candle_err = data_checks_dir / "candle_dbs.stderr.txt"
        if bool(args.resume) and _is_nonempty_file(candle_out):
            meta["steps"].append(
                {
                    "name": "check_candle_dbs_skip",
                    "argv": [],
                    "cwd": str(AIQ_ROOT),
                    "exit_code": 0,
                    "elapsed_s": 0.0,
                    "stdout_path": str(candle_out),
                    "stderr_path": str(candle_err),
                }
            )
        else:
            check_intervals = _factory_candle_check_intervals(default="1m,3m,5m,15m,30m,1h")
            sidecar_bin = shutil.which("openclaw-ai-quant-ws-sidecar") or "openclaw-ai-quant-ws-sidecar"
            check_targets: list[dict[str, Any]] = []
            check_failed = False
            check_errors: list[str] = []

            if not candles_db_for_checks:
                candles_db_for_checks = str(AIQ_ROOT / "candles_dbs")
            db_paths = _iter_candle_db_paths(str(candles_db_for_checks))
            if not db_paths:
                err_text = f"no candle DBs resolved from --candles-db={candles_db_for_checks}\n"
                check_targets.append(
                    {
                        "interval": "n/a",
                        "db_path": str(candles_db_for_checks),
                        "db_dir": str(Path(candles_db_for_checks).expanduser()),
                        "symbols": [],
                        "status": "FAIL",
                        "reason": "no_db_paths",
                    }
                )
                candle_err.write_text(err_text, encoding="utf-8")
                check_failed = True
            else:
                for db_path in db_paths:
                    interval = _candle_db_interval(db_path)
                    if not interval:
                        continue
                    if check_intervals and interval not in check_intervals:
                        continue

                    symbols = _symbols_from_candle_db(db_path)
                    out_path = data_checks_dir / f"candle_{interval}_{db_path.stem}.json"
                    err_path = data_checks_dir / f"candle_{interval}_{db_path.stem}.stderr.txt"

                    if not symbols:
                        check_targets.append(
                            {
                                "interval": interval,
                                "db_path": str(db_path),
                                "symbol_count": 0,
                                "symbols": [],
                                "status": "PASS",
                                "reason": "no_symbols",
                                "items": [],
                            }
                        )
                        continue

                    stat_exit, stat_items, bad_symbols, fail_reason = _run_stat_check(
                        sidecar_bin=sidecar_bin,
                        interval=interval,
                        db_path=db_path,
                        symbols=symbols,
                        out_path=out_path,
                        err_path=err_path,
                    )
                    fail_interval = (stat_exit != 0) or (fail_reason != "pass")
                    if fail_interval:
                        check_failed = True

                    check_targets.append(
                        {
                            "interval": interval,
                            "db_path": str(db_path),
                            "db_dir": str(db_path.parent),
                            "symbol_count": len(symbols),
                            "symbols": symbols[:500],
                            "status": "FAIL" if fail_interval else "PASS",
                            "exit_code": int(stat_exit),
                            "failed_symbols": bad_symbols,
                            "items": stat_items,
                        }
                    )
                    if err_path.is_file():
                        try:
                            err_text = err_path.read_text(encoding="utf-8")
                            if err_text.strip():
                                check_errors.append(f"[{interval}] {err_path}\n{err_text.strip()}\n")
                        except Exception:
                            pass

                    if fail_interval:
                        check_targets[-1]["status"] = "FAIL"

                    if fail_interval and bad_symbols:
                        check_targets[-1]["failed_symbols"] = bad_symbols

            if check_errors:
                check_err_text = "".join(check_errors)
                candle_err.parent.mkdir(parents=True, exist_ok=True)
                candle_err.write_text(check_err_text, encoding="utf-8")

            _write_json(
                candle_out,
                {
                    "status": "FAIL" if check_failed else "PASS",
                    "checks": check_targets,
                    "intervals": check_intervals,
                    "candle_db_root": str(candles_db_for_checks),
                },
            )
            if check_failed:
                for interval_check in check_targets:
                    interval = str(interval_check.get("interval", ""))
                    symbols_csv = ",".join(interval_check.get("symbols", []))
                    meta["steps"].append(
                        {
                            "name": f"check_candle_dbs_rust_{interval}",
                            "cwd": str(AIQ_ROOT),
                            "argv": [
                                sidecar_bin,
                                "stat",
                                "--interval",
                                interval,
                                "--symbols",
                                symbols_csv,
                                "--db-dir",
                                str(Path(interval_check.get("db_path", "")).parent)
                                if interval_check.get("db_path")
                                else str(AIQ_ROOT),
                            ],
                            "exit_code": int(1 if str(interval_check.get("status", "FAIL")) == "FAIL" else 0),
                            "elapsed_s": 0.0,
                            "stdout_path": str(candle_out),
                            "stderr_path": str(candle_err),
                            "status": str(interval_check.get("status", "PASS")),
                            "items": interval_check.get("items", []),
                            "failed_symbols": interval_check.get("failed_symbols", []),
                        }
                    )

                if not candle_err.exists():
                    # Keep metadata consistent; create empty file even when all failing intervals had no stderr details.
                    candle_err.parent.mkdir(parents=True, exist_ok=True)
                    candle_err.write_text("", encoding="utf-8")

                meta["steps"].append(
                    {
                        "name": "check_candle_dbs",
                        "argv": [],
                        "cwd": str(AIQ_ROOT),
                        "exit_code": 1,
                        "elapsed_s": 0.0,
                        "stdout_path": str(candle_out),
                        "stderr_path": str(candle_err),
                        "status": "FAIL",
                    }
                )
                _write_json(run_dir / "run_metadata.json", meta)
                return 1

            meta["steps"].append(
                {
                    "name": "check_candle_dbs",
                    "argv": [],
                    "cwd": str(AIQ_ROOT),
                    "exit_code": 0,
                    "elapsed_s": 0.0,
                    "stdout_path": str(candle_out),
                    "stderr_path": str(candle_err),
                    "status": "PASS",
                    "checks": check_targets,
                    "intervals": check_intervals,
                }
            )
        _write_json(run_dir / "run_metadata.json", meta)

        # ── Pre-sweep funding refresh ───────────────────────────────────────
        # Fetch latest funding rates before the freshness check to avoid stale-data failures.
        funding_refresh_out = run_dir / "data_checks" / "funding_refresh.stdout.txt"
        funding_refresh_err = run_dir / "data_checks" / "funding_refresh.stderr.txt"
        funding_refresh_res = _run_cmd(
            [sys.executable, "tools/fetch_funding_rates.py", "--days", "7"],
            cwd=AIQ_ROOT,
            stdout_path=funding_refresh_out,
            stderr_path=funding_refresh_err,
        )
        meta["steps"].append({"name": "refresh_funding_rates", **funding_refresh_res.__dict__})
        if funding_refresh_res.exit_code != 0:
            print(f"⚠️ Funding refresh failed (exit={funding_refresh_res.exit_code}), proceeding with existing data")
        _write_json(run_dir / "run_metadata.json", meta)

        funding_out = run_dir / "data_checks" / "funding_rates.json"
        funding_err = run_dir / "data_checks" / "funding_rates.stderr.txt"
        if bool(args.resume) and _is_nonempty_file(funding_out):
            meta["steps"].append(
                {
                    "name": "check_funding_rates_db_skip",
                    "argv": [],
                    "cwd": str(AIQ_ROOT),
                    "exit_code": 0,
                    "elapsed_s": 0.0,
                    "stdout_path": str(funding_out),
                    "stderr_path": str(funding_err),
                }
            )
        else:
            funding_argv = ["python3", "tools/check_funding_rates_db.py"]
            if bt_funding_db:
                funding_argv += ["--db", str(bt_funding_db)]
            if args.max_age_fail_hours is not None:
                funding_argv += ["--max-age-fail-hours", str(float(args.max_age_fail_hours))]
            funding_check = _run_cmd(
                funding_argv,
                cwd=AIQ_ROOT,
                stdout_path=funding_out,
                stderr_path=funding_err,
            )
            funding_check_step = {"name": "check_funding_rates_db", **funding_check.__dict__}
            if funding_check.exit_code != 0:
                if funding_check.exit_code != 2:
                    meta["steps"].append(funding_check_step)
                    _write_json(run_dir / "run_metadata.json", meta)
                    return int(funding_check.exit_code)

                funding_json = _load_json_payload(funding_out)
                allow_stale = int(args.funding_max_stale_symbols or 0)
                can_degrade, degrade_meta = _funding_check_degraded_allowance(
                    funding_json,
                    max_stale_symbols=allow_stale,
                )
                if not can_degrade:
                    meta["steps"].append(funding_check_step)
                    _write_json(run_dir / "run_metadata.json", meta)
                    return int(funding_check.exit_code)

                if isinstance(degrade_meta, dict):
                    funding_check_step["funding_check_degrade_meta"] = {
                        "warn_legacy_exit_code": funding_check.exit_code,
                        "allowed_stale_symbols": allow_stale,
                        "symbols": list(degrade_meta.get("symbols", [])),
                        "fail_issues": int(degrade_meta.get("fail_issues", 0)),
                        "status": str(degrade_meta.get("status") or ""),
                    }
                else:
                    funding_check_step["funding_check_degrade_meta"] = {
                        "warn_legacy_exit_code": funding_check.exit_code,
                        "allowed_stale_symbols": allow_stale,
                    }
                funding_check_step["funding_check_degraded"] = True
                funding_check_step["exit_code_original"] = funding_check.exit_code
                funding_check_step["exit_code"] = 0

                meta["funding_check_degraded"] = {
                    "status": "warn",
                    "symbols": funding_check_step.get("funding_check_degrade_meta", {}).get("symbols", []),
                    "allowed_symbols": allow_stale,
                }
                funding_check = CmdResult(
                    argv=funding_check_step["argv"],
                    cwd=funding_check_step["cwd"],
                    exit_code=int(funding_check_step["exit_code"]),
                    elapsed_s=float(funding_check_step["elapsed_s"]),
                    stdout_path=str(funding_check_step["stdout_path"]),
                    stderr_path=str(funding_check_step["stderr_path"]),
                )
            else:
                meta.pop("funding_check_degraded", None)

            if bool(funding_check_step.get("funding_check_degraded")):
                (run_dir / "logs" / "factory_run_warn.log").write_text(
                    "WARN: funding check passed with stale-symbol allowance\n",
                    encoding="utf-8",
                )

            meta["steps"].append(funding_check_step)

        _write_json(run_dir / "run_metadata.json", meta)

        # Resolve live-initial balance for daily/deep/weekly profiles.
        live_initial_balance, live_initial_balance_path, live_initial_balance_meta = _resolve_factory_initial_balance(
            run_dir=run_dir,
            args=args,
        )
        meta["initial_balance"] = {
            "value": live_initial_balance,
            "path": str(live_initial_balance_path) if live_initial_balance_path else "",
            "profile": str(getattr(args, "profile", "daily")).strip(),
            **live_initial_balance_meta,
        }

        # Extend input fingerprints with the resolved balance snapshot (if any).
        if isinstance(meta.get("input_fingerprints"), dict):
            if live_initial_balance_path is not None:
                bf = _file_fingerprint(Path(live_initial_balance_path))
                meta["input_fingerprints"]["balance_from"] = {
                    "schema_version": 1,
                    "fingerprint": str(bf.get("sha256", "") or ""),
                    "file": bf,
                }
            else:
                meta["input_fingerprints"].setdefault(
                    "balance_from",
                    {"schema_version": 1, "fingerprint": "", "file": {"path": "", "exists": False}},
                )

        # ------------------------------------------------------------------
        # 2) Sweep
        # ------------------------------------------------------------------
        current_stage = "sweep"
        if _shutdown_stage_guard(run_dir=run_dir, meta=meta, stage=current_stage):
            return 130
        sweep_out = run_dir / "sweeps" / "sweep_results.jsonl"
        if bool(args.resume) and _is_nonempty_file(sweep_out):
            sweep_res = CmdResult(
                argv=[],
                cwd=str(AIQ_ROOT / "backtester"),
                exit_code=0,
                elapsed_s=0.0,
                stdout_path=str(run_dir / "sweeps" / "sweep.stdout.txt"),
                stderr_path=str(run_dir / "sweeps" / "sweep.stderr.txt"),
            )
            meta["steps"].append({"name": "sweep_skip", **sweep_res.__dict__})
        else:
            if bool(args.gpu):
                rc = _ensure_gpu_idle_or_exit(
                    run_dir=run_dir,
                    meta=meta,
                    wait_s=int(getattr(args, "gpu_wait_s", 0) or 0),
                    poll_s=int(getattr(args, "gpu_poll_s", 0) or 0),
                )
                if rc != 0:
                    return int(rc)

            sweep_argv = bt_cmd + [
                "sweep",
                "--config",
                str(bt_config),
                "--sweep-spec",
                str(bt_sweep_spec),
                "--interval",
                str(args.interval),
                "--output",
                str(sweep_out),
                "--output-mode",
                _sweep_output_mode_from_args(args),
            ]

            # Lock the sweep window when provided. Even if omitted, we later parse
            # the effective window from stderr and reuse it for CPU replays.
            start_ts = str(getattr(args, "start_ts", "") or "").strip()
            end_ts = str(getattr(args, "end_ts", "") or "").strip()
            if start_ts:
                sweep_argv += ["--start-ts", start_ts]
            if end_ts:
                sweep_argv += ["--end-ts", end_ts]

            parity_mode = str(getattr(args, "sweep_parity_mode", "") or "").strip()
            if parity_mode:
                sweep_argv += ["--parity-mode", parity_mode]
            if live_initial_balance_path is not None:
                sweep_argv += ["--balance-from", str(live_initial_balance_path)]
            top_n = int(args.top_n or 0)
            if top_n <= 0:
                # Stage-1 shortlist contract:
                # 1M sweep -> top 1000 by PnL -> 3 lanes x 10 -> CPU backtest/gate -> promotion.
                _top_pnl_pool = int(getattr(args, "shortlist_top_pnl", 1000) or 1000)
                top_n = _top_pnl_pool if _top_pnl_pool > 0 else 1000
            if top_n > 0:
                sweep_argv += ["--top-n", str(top_n)]
            if bt_candles_db:
                sweep_argv += [
                    "--candles-db",
                    str(bt_candles_db),
                    "--exit-candles-db",
                    str(bt_candles_db),
                    "--entry-candles-db",
                    str(bt_candles_db),
                ]
            if funding_for_pairing:
                sweep_argv += ["--funding-db", str(bt_funding_db)]
            if bool(args.gpu):
                sweep_argv += ["--gpu"]
            allow_unsafe = bool(getattr(args, "allow_unsafe_gpu_sweep", False)) or os.getenv(
                "AI_QUANT_FACTORY_ALLOW_UNSAFE_GPU_SWEEP", ""
            ).strip().lower() in {"1", "true", "yes", "on"}
            if allow_unsafe and "--allow-unsafe-gpu-sweep" not in sweep_argv:
                sweep_argv += ["--allow-unsafe-gpu-sweep"]
            if bool(getattr(args, "tpe", False)):
                if not bool(args.gpu):
                    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
                    (run_dir / "reports" / "report.md").write_text(
                        "# Factory Run Report\n\nError: --tpe requires --gpu.\n", encoding="utf-8"
                    )
                    _write_json(run_dir / "run_metadata.json", meta)
                    return 1
                sweep_argv += [
                    "--tpe",
                    "--tpe-trials",
                    str(int(getattr(args, "tpe_trials", 5000))),
                    "--tpe-batch",
                    str(int(getattr(args, "tpe_batch", 256))),
                    "--tpe-seed",
                    str(int(getattr(args, "tpe_seed", 42))),
                ]

            sweep_output_mode = _sweep_output_mode_from_args(args)
            fallback_to_legacy_output = False
            sweep_res = _run_cmd(
                sweep_argv,
                cwd=AIQ_ROOT / "backtester",
                stdout_path=run_dir / "sweeps" / "sweep.stdout.txt",
                stderr_path=run_dir / "sweeps" / "sweep.stderr.txt",
            )
            if sweep_res.exit_code != 0:
                try:
                    sweep_stderr = (
                        Path(sweep_res.stderr_path or "").read_text(encoding="utf-8") if sweep_res.stderr_path else ""
                    )
                except Exception:
                    sweep_stderr = ""
                unsupported_output_mode = "--output-mode" in str(sweep_argv) and (
                    "unexpected argument '--output-mode'" in sweep_stderr
                    or "unexpected argument `--output-mode'" in sweep_stderr
                    or "unrecognized argument '--output-mode'" in sweep_stderr
                    or "invalid argument '--output-mode'" in sweep_stderr
                )
                if unsupported_output_mode:
                    fallback_to_legacy_output = True
                    filtered_argv = []
                    skip_next = False
                    for idx, token in enumerate(sweep_argv):
                        if skip_next:
                            skip_next = False
                            continue
                        if token == "--output-mode":
                            if idx + 1 < len(sweep_argv):
                                skip_next = True
                            continue
                        filtered_argv.append(token)

                    sweep_res = _run_cmd(
                        filtered_argv,
                        cwd=AIQ_ROOT / "backtester",
                        stdout_path=run_dir / "sweeps" / "sweep.stdout.txt",
                        stderr_path=run_dir / "sweeps" / "sweep.stderr.txt",
                    )
                    if sweep_res.exit_code == 0:
                        fallback_to_legacy_output = True

            meta["steps"].append(
                {
                    "name": "sweep",
                    "fallback_to_legacy_output_mode": fallback_to_legacy_output,
                    "sweep_output_mode_request": sweep_output_mode,
                    **sweep_res.__dict__,
                }
            )
            if sweep_res.exit_code != 0:
                _write_json(run_dir / "run_metadata.json", meta)
                return int(sweep_res.exit_code)
            if sweep_output_mode == "candidate" and not fallback_to_legacy_output:
                ok, schema_errors = _validate_candidate_output_schema(sweep_out)
                if not ok:
                    _write_json(
                        run_dir / "run_metadata.json",
                        {
                            **meta,
                            "candidate_schema_validation": {
                                "status": "fail",
                                "path": str(sweep_out),
                                "errors": schema_errors,
                            },
                        },
                    )
                    return 2
                meta["candidate_schema_validation"] = {
                    "status": "pass",
                    "path": str(sweep_out),
                    "errors": [],
                }

        # Capture effective time window used by the sweep (auto-scope output) and
        # store it as a contract anchor for Step-4 CPU replays.
        try:
            sweep_stderr_p = Path(str(sweep_res.stderr_path or ""))
            if sweep_stderr_p.is_file():
                from_ms, to_ms, line = _parse_effective_time_range_ms(sweep_stderr_p)
                if from_ms is not None and to_ms is not None:
                    meta["sweep_effective_time_range_ms"] = {
                        "from_ts_ms": int(from_ms),
                        "to_ts_ms": int(to_ms),
                        "source": "stderr_parse",
                        "stderr_path": str(sweep_stderr_p),
                        "line": str(line or ""),
                    }
        except Exception:
            pass

        # Update / (re)compute Step-4 parity contract once sweep inputs are known.
        try:
            meta["step4_parity_contract"] = _build_step4_parity_contract(meta)
        except Exception:
            pass

        _write_json(run_dir / "run_metadata.json", meta)

        # ------------------------------------------------------------------
        # 2b) Extract top candidates (single-pass streaming)
        # ------------------------------------------------------------------
        shortlist_per_mode = int(getattr(args, "shortlist_per_mode", 0) or 0)
        shortlist_max_rank = int(getattr(args, "shortlist_max_rank", 0) or 0)
        shortlist_top_pnl = int(getattr(args, "shortlist_top_pnl", 1000) or 1000)
        if shortlist_top_pnl <= 0:
            shortlist_top_pnl = 1000
        shortlist_modes_raw = str(getattr(args, "shortlist_modes", "") or "").strip()

        # Extract a deterministic stage-1 pool by PnL first.
        extract_modes = ["pnl"]

        if shortlist_max_rank <= 0:
            shortlist_max_rank = shortlist_top_pnl
        shortlist_max_rank = min(shortlist_max_rank, shortlist_top_pnl)

        candidate_min_trades = max(0, int(getattr(args, "candidate_min_trades", 1) or 0))

        sweep_candidates_out = run_dir / "sweeps" / "sweep_candidates.jsonl"
        if bool(args.resume) and _is_nonempty_file(sweep_candidates_out):
            meta["steps"].append({"name": "extract_top_candidates_skip", "path": str(sweep_candidates_out)})
        else:
            t0 = time.monotonic()
            extract_rows, extract_schema_errors = _extract_top_candidates(
                sweep_out,
                sweep_candidates_out,
                max_rank=shortlist_max_rank,
                modes=extract_modes,
                min_trades=candidate_min_trades,
            )
            elapsed = time.monotonic() - t0
            meta["steps"].append(
                {
                    "name": "extract_top_candidates",
                    "path": str(sweep_candidates_out),
                    "source_path": str(sweep_out),
                    "total_rows_scanned": extract_rows,
                    "modes": extract_modes,
                    "top_pnl_pool": shortlist_top_pnl,
                    "max_rank": shortlist_max_rank,
                    "min_trades": candidate_min_trades,
                    "elapsed_s": round(elapsed, 2),
                    "output_size_bytes": sweep_candidates_out.stat().st_size if sweep_candidates_out.exists() else 0,
                }
            )

        _write_json(run_dir / "run_metadata.json", meta)

        # All downstream generate_config calls use the compact candidates file.
        sweep_gen_source = sweep_candidates_out

        # ------------------------------------------------------------------
        # 3) Candidate config generation
        # ------------------------------------------------------------------
        current_stage = "candidate_generation"
        if _shutdown_stage_guard(run_dir=run_dir, meta=meta, stage=current_stage):
            return 130
        configs_dir = run_dir / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)

        candidate_paths: list[Path] = []
        candidate_config_ids: dict[str, str] = {}
        candidate_entries: list[dict[str, Any]] = []
        entry_by_path: dict[str, dict[str, Any]] = {}
        skip_generation = False
        default_entry_stage = _stage_defaults_for_candidate(args=args)

        if bool(args.resume):
            existing_entries = meta.get("candidate_configs", [])
            if isinstance(existing_entries, list) and existing_entries:
                candidate_entries = [it for it in existing_entries if isinstance(it, dict)]
                for it in candidate_entries:
                    defaults = dict(default_entry_stage)
                    had_candidate_mode = "candidate_mode" in it
                    for k, v in it.items():
                        if isinstance(v, (str, int, float, bool, dict, list, tuple, type(None))):
                            defaults[k] = v
                    defaults.setdefault("canonical_cpu_verified", False)
                    defaults.setdefault("pipeline_stage", "candidate_generation")
                    defaults.setdefault("sweep_stage", _infer_sweep_stage_from_args(args))
                    defaults.setdefault("replay_stage", "")
                    defaults.setdefault("validation_gate", _infer_validation_gate_from_args(args))
                    if not had_candidate_mode:
                        defaults["candidate_mode"] = False
                    it.update(defaults)
                    p = str(it.get("path", "")).strip()
                    if p:
                        entry_by_path[p] = it

                for it in candidate_entries:
                    p_raw = str(it.get("path", "")).strip()
                    if not p_raw:
                        continue
                    if "selected" in it and not bool(it.get("selected")):
                        continue
                    p = Path(p_raw).expanduser().resolve()
                    if not _is_nonempty_file(p):
                        continue
                    candidate_paths.append(p)
                    cid = str(it.get("config_id", "")).strip()
                    if not cid:
                        cid = config_id_from_yaml_file(p)
                        it["config_id"] = cid
                    if not str(it.get("config_sha256", "") or "").strip():
                        it["config_sha256"] = _sha256_file_optional(p)
                    candidate_config_ids[str(p)] = cid

                skip_generation = bool(candidate_paths)

        # Multi-mode shortlist generation (AQC-403). Deduplicate across modes by config_id.
        if not skip_generation and shortlist_per_mode > 0:
            allowed_modes = {
                "pnl",
                "dd",
                "pf",
                "wr",
                "sharpe",
                "trades",
                "balanced",
                "efficient",
                "growth",
                "conservative",
            }
            modes = [m.strip() for m in shortlist_modes_raw.split(",") if m.strip()]
            modes = [m for m in modes if m in allowed_modes]
            if not modes:
                modes = ["efficient", "growth", "conservative"]
            if shortlist_max_rank <= 0:
                shortlist_max_rank = shortlist_top_pnl
            shortlist_max_rank = min(shortlist_max_rank, shortlist_top_pnl)

            seen_ids: set[str] = set()
            for mode in modes:
                kept = 0
                for rank in range(1, shortlist_max_rank + 1):
                    out_yaml = configs_dir / f"candidate_{mode}_rank{rank}.yaml"
                    gen_argv = [
                        "python3",
                        "tools/generate_config.py",
                        "--sweep-results",
                        str(sweep_gen_source),
                        "--base-config",
                        str(args.config),
                        "--sort-by",
                        str(mode),
                        "--rank",
                        str(rank),
                        "--min-trades",
                        str(candidate_min_trades),
                        "-o",
                        str(out_yaml),
                    ]
                    gen_res = _run_cmd(
                        gen_argv,
                        cwd=AIQ_ROOT,
                        stdout_path=run_dir / "configs" / f"generate_config_{mode}_rank{rank}.stdout.txt",
                        stderr_path=run_dir / "configs" / f"generate_config_{mode}_rank{rank}.stderr.txt",
                    )
                    meta["steps"].append({"name": f"generate_config_{mode}_rank{rank}", **gen_res.__dict__})
                    if gen_res.exit_code != 0:
                        _write_json(run_dir / "run_metadata.json", meta)
                        return int(gen_res.exit_code)

                    cfg_id = config_id_from_yaml_file(out_yaml)
                    candidate_config_ids[str(out_yaml)] = cfg_id

                    is_dup = cfg_id in seen_ids
                    selected = (not is_dup) and kept < shortlist_per_mode
                    if selected:
                        seen_ids.add(cfg_id)
                        candidate_paths.append(out_yaml)
                        kept += 1

                    entry = {
                        **default_entry_stage,
                        "path": str(out_yaml),
                        "config_id": cfg_id,
                        "config_sha256": _sha256_file_optional(out_yaml),
                        "sort_by": mode,
                        "rank": int(rank),
                        "selected": bool(selected),
                        "deduped": bool(is_dup),
                        "interval": str(args.interval),
                        "base_config_path": str(args.config),
                        "sweep_spec_path": str(args.sweep_spec),
                        "sweep_results_path": str(sweep_out),
                        "sweep_stdout_path": str(sweep_res.stdout_path or ""),
                        "sweep_stderr_path": str(sweep_res.stderr_path or ""),
                        "generate_stdout_path": str(gen_res.stdout_path or ""),
                        "generate_stderr_path": str(gen_res.stderr_path or ""),
                    }
                    candidate_entries.append(entry)
                    entry_by_path[str(out_yaml)] = entry

                    if kept >= shortlist_per_mode:
                        break

        # Single-mode generation (legacy): args.num_candidates + args.sort_by.
        elif not skip_generation:
            for rank in range(1, int(args.num_candidates) + 1):
                out_yaml = configs_dir / f"candidate_{args.sort_by}_rank{rank}.yaml"
                gen_argv = [
                    "python3",
                    "tools/generate_config.py",
                    "--sweep-results",
                    str(sweep_gen_source),
                    "--base-config",
                    str(args.config),
                    "--sort-by",
                    str(args.sort_by),
                    "--rank",
                    str(rank),
                    "--min-trades",
                    str(candidate_min_trades),
                    "-o",
                    str(out_yaml),
                ]
                gen_res = _run_cmd(
                    gen_argv,
                    cwd=AIQ_ROOT,
                    stdout_path=run_dir / "configs" / f"generate_config_rank{rank}.stdout.txt",
                    stderr_path=run_dir / "configs" / f"generate_config_rank{rank}.stderr.txt",
                )
                meta["steps"].append({"name": f"generate_config_rank{rank}", **gen_res.__dict__})
                if gen_res.exit_code != 0:
                    _write_json(run_dir / "run_metadata.json", meta)
                    return int(gen_res.exit_code)
                candidate_paths.append(out_yaml)
                cfg_id = config_id_from_yaml_file(out_yaml)
                candidate_config_ids[str(out_yaml)] = cfg_id
                entry = {
                    **default_entry_stage,
                    "path": str(out_yaml),
                    "config_id": cfg_id,
                    "config_sha256": _sha256_file_optional(out_yaml),
                    "sort_by": str(args.sort_by),
                    "rank": int(rank),
                    "selected": True,
                    "deduped": False,
                    "interval": str(args.interval),
                    "base_config_path": str(args.config),
                    "sweep_spec_path": str(args.sweep_spec),
                    "sweep_results_path": str(sweep_out),
                    "sweep_stdout_path": str(sweep_res.stdout_path or ""),
                    "sweep_stderr_path": str(sweep_res.stderr_path or ""),
                    "generate_stdout_path": str(gen_res.stdout_path or ""),
                    "generate_stderr_path": str(gen_res.stderr_path or ""),
                }
                candidate_entries.append(entry)
                entry_by_path[str(out_yaml)] = entry

        meta["candidate_configs"] = candidate_entries

        # Attach the originating sweep row (metrics + overrides) to each generated
        # candidate so Step-4 can compare GPU sweep vs CPU replay deterministically.
        try:
            sweep_rows_path = Path(str(sweep_gen_source))
            if sweep_rows_path.is_file():
                sweep_rows_all = _load_jsonl_rows(sweep_rows_path)
                sweep_rows_filtered = [
                    r
                    for r in sweep_rows_all
                    if int(_coerce_int(r.get("total_trades"), 0) or 0) >= int(candidate_min_trades)
                ]

                sort_fns: dict[str, Any] = {
                    **_EXTRACT_SORT_KEYS,
                    "balanced": _extract_balanced_score,
                    "efficient": _extract_efficient_score,
                    "growth": _extract_growth_score,
                }
                sort_cache: dict[str, list[dict[str, Any]]] = {}

                for entry in candidate_entries:
                    mode_raw = str(entry.get("sort_by", "") or "").strip()
                    mode = "dd" if mode_raw == "conservative" else mode_raw
                    if mode not in sort_fns:
                        continue
                    rank = int(_coerce_int(entry.get("rank"), 0) or 0)
                    if rank <= 0:
                        continue
                    if mode not in sort_cache:
                        rows = list(sweep_rows_filtered)
                        rows.sort(key=sort_fns[mode], reverse=True)
                        sort_cache[mode] = rows
                    rows = sort_cache[mode]
                    idx = rank - 1
                    if idx < 0 or idx >= len(rows):
                        continue
                    row = rows[idx]
                    entry["sweep_candidate_row"] = {
                        "config_id": row.get("config_id"),
                        "total_pnl": row.get("total_pnl"),
                        "final_balance": row.get("final_balance"),
                        "total_trades": row.get("total_trades"),
                        "profit_factor": row.get("profit_factor"),
                        "max_drawdown_pct": row.get("max_drawdown_pct"),
                        "overrides": row.get("overrides"),
                    }
                    entry["overrides_key"] = _format_overrides_key(row.get("overrides"))
        except Exception as e:
            meta["step4_parity_attach_error"] = f"{type(e).__name__}: {e}"
        _write_json(run_dir / "run_metadata.json", meta)

        if not candidate_paths:
            (run_dir / "reports").mkdir(parents=True, exist_ok=True)
            (run_dir / "reports" / "report.md").write_text(
                "# Factory Run Report\n\nNo candidate configs were selected.\n", encoding="utf-8"
            )
            _write_json(run_dir / "run_metadata.json", meta)
            return 1

        # ------------------------------------------------------------------
        # 4) CPU replay / validation (minimal v1: run replay once per candidate)
        # ------------------------------------------------------------------

        # Guard: verify the backtester binary has not been overwritten since sweep.
        if _bt_bin_sha_at_start and _bt_bin_path_for_guard is not None:
            try:
                _bt_bin_sha_now = _sha256_file(_bt_bin_path_for_guard)
                if _bt_bin_sha_now != _bt_bin_sha_at_start:
                    msg = (
                        f"FATAL: mei-backtester binary changed mid-run! "
                        f"sweep used sha256={_bt_bin_sha_at_start[:16]}… "
                        f"but binary is now sha256={_bt_bin_sha_now[:16]}… "
                        f"({_bt_bin_path_for_guard}). "
                        f"Aborting to prevent GPU↔CPU drift."
                    )
                    print(msg, file=sys.stderr, flush=True)
                    meta["binary_drift_detected"] = {
                        "stage": "pre_cpu_replay",
                        "sweep_sha256": _bt_bin_sha_at_start,
                        "current_sha256": _bt_bin_sha_now,
                        "path": str(_bt_bin_path_for_guard),
                    }
                    _write_json(run_dir / "run_metadata.json", meta)
                    return 1
            except Exception:
                pass  # Non-fatal: proceed if we cannot read the binary.

        current_stage = "cpu_replay_validation"
        if _shutdown_stage_guard(run_dir=run_dir, meta=meta, stage=current_stage):
            return 130
        replays_dir = run_dir / "replays"
        replays_dir.mkdir(parents=True, exist_ok=True)

        replay_reports: list[dict[str, Any]] = []
        step4_parity_enabled = bool(getattr(args, "step4_parity", True))
        step4_parity_rel_eps = float(getattr(args, "step4_parity_rel_eps", 1e-6) or 1e-6)
        step4_parity_abs_eps = float(getattr(args, "step4_parity_abs_eps", 1e-3) or 1e-3)
        step4_parity_dd_eps = float(getattr(args, "step4_parity_dd_eps", 1e-6) or 1e-6)
        step4_parity_pf_eps = float(getattr(args, "step4_parity_pf_eps", 1e-4) or 1e-4)
        step4_parity_rows: list[dict[str, Any]] = []
        step4_parity_thresholds = {
            "rel_eps": step4_parity_rel_eps,
            "abs_eps": step4_parity_abs_eps,
            "dd_eps": step4_parity_dd_eps,
            "pf_eps": step4_parity_pf_eps,
        }
        for cfg_path in candidate_paths:
            out_json = replays_dir / f"{cfg_path.stem}.replay.json"

            trades_csv: Path | None = None
            if bool(getattr(args, "monte_carlo", False)):
                trades_dir = run_dir / "trades"
                trades_dir.mkdir(parents=True, exist_ok=True)
                trades_csv = trades_dir / f"{cfg_path.stem}.trades.csv"

            replay_argv = bt_cmd + [
                "replay",
                "--config",
                str(cfg_path),
                "--interval",
                str(args.interval),
                "--output",
                str(out_json),
            ]

            # Step-4 contract lock: replay MUST use the *same* effective time
            # window as the sweep. This avoids false mismatches when candle DBs
            # advance between sweep and replay.
            try:
                sweep_range = (
                    meta.get("sweep_effective_time_range_ms")
                    if isinstance(meta.get("sweep_effective_time_range_ms"), dict)
                    else {}
                )
                from_ms = _coerce_int(sweep_range.get("from_ts_ms"), 0)
                to_ms = _coerce_int(sweep_range.get("to_ts_ms"), 0)
                if from_ms and to_ms:
                    replay_argv += ["--start-ts", str(int(from_ms)), "--end-ts", str(int(to_ms))]
                else:
                    start_ts = str(getattr(args, "start_ts", "") or "").strip()
                    end_ts = str(getattr(args, "end_ts", "") or "").strip()
                    if start_ts:
                        replay_argv += ["--start-ts", start_ts]
                    if end_ts:
                        replay_argv += ["--end-ts", end_ts]
            except Exception:
                pass
            if live_initial_balance_path is not None:
                replay_argv += ["--balance-from", str(live_initial_balance_path)]
            if bt_candles_db:
                replay_argv += [
                    "--candles-db",
                    str(bt_candles_db),
                    "--exit-candles-db",
                    str(bt_candles_db),
                    "--entry-candles-db",
                    str(bt_candles_db),
                ]
            if funding_for_pairing:
                replay_argv += ["--funding-db", str(bt_funding_db)]
            if trades_csv is not None:
                replay_argv += ["--export-trades", str(trades_csv)]

            replay_stdout = run_dir / "replays" / f"{cfg_path.stem}.stdout.txt"
            replay_stderr = run_dir / "replays" / f"{cfg_path.stem}.stderr.txt"

            if (
                bool(args.resume)
                and _is_nonempty_file(out_json)
                and (trades_csv is None or _is_nonempty_file(trades_csv))
            ):
                replay_res = CmdResult(
                    argv=[],
                    cwd=str(AIQ_ROOT / "backtester"),
                    exit_code=0,
                    elapsed_s=0.0,
                    stdout_path=str(replay_stdout),
                    stderr_path=str(replay_stderr),
                )
                meta["steps"].append({"name": f"replay_{cfg_path.stem}_skip", **replay_res.__dict__})
            else:
                replay_res = _run_cmd(
                    replay_argv,
                    cwd=AIQ_ROOT / "backtester",
                    stdout_path=replay_stdout,
                    stderr_path=replay_stderr,
                )
                meta["steps"].append({"name": f"replay_{cfg_path.stem}", **replay_res.__dict__})
                if replay_res.exit_code != 0:
                    _write_json(run_dir / "run_metadata.json", meta)
                    return int(replay_res.exit_code)

            summary = _summarise_replay_report(out_json)
            summary["config_path"] = str(cfg_path)
            summary["config_id"] = candidate_config_ids[str(cfg_path)]
            summary["config_sha256"] = _sha256_file_optional(cfg_path)
            replay_entry = entry_by_path.get(str(cfg_path))
            if isinstance(replay_entry, dict):
                for identity_field in ("sort_by", "rank", "overrides_key", "config_sha256"):
                    if identity_field in replay_entry:
                        summary[identity_field] = replay_entry[identity_field]
            if not _run_replay_equivalence_check(
                right_report=out_json,
                summary=summary,
                current_contract=meta.get("replay_equivalence_contract")
                if isinstance(meta.get("replay_equivalence_contract"), dict)
                else None,
            ):
                _write_json(run_dir / "run_metadata.json", meta)
                return 1
            _attach_replay_metadata(summary=summary, entry=replay_entry, args=args)
            if replay_entry is None:
                summary["config_path"] = str(cfg_path)

            # Step-4 GPU↔CPU parity: compare CPU replay metrics to the sweep row
            # (GPU metrics) that generated this candidate config.
            if step4_parity_enabled and isinstance(replay_entry, dict):
                sweep_row = replay_entry.get("sweep_candidate_row")
                if isinstance(sweep_row, dict):
                    parity = _compute_step4_parity(
                        cpu=summary,
                        gpu=sweep_row,
                        rel_eps=step4_parity_rel_eps,
                        abs_eps=step4_parity_abs_eps,
                        dd_eps=step4_parity_dd_eps,
                        pf_eps=step4_parity_pf_eps,
                    )
                    summary["step4_parity"] = parity
                    replay_entry["step4_parity"] = parity
                    # Step4 parity (GPU==CPU) is the authoritative correctness
                    # check.  When it passes, promote canonical_cpu_verified
                    # even if replay-equivalence failed (e.g. different TPE
                    # configs across nightly runs).
                    if str(parity.get("status", "")).lower() == "pass":
                        summary["canonical_cpu_verified"] = True
                        replay_entry["canonical_cpu_verified"] = True
                    step4_parity_rows.append(
                        {
                            "status": parity.get("status", ""),
                            "cause": parity.get("cause", ""),
                            "sort_by": replay_entry.get("sort_by"),
                            "rank": replay_entry.get("rank"),
                            "config_path": str(cfg_path),
                            "overrides_key": replay_entry.get("overrides_key", ""),
                            "trades_delta": parity.get("trades_delta"),
                            "pnl_delta": parity.get("pnl_delta"),
                            "dd_delta": parity.get("dd_delta"),
                            "pf_delta": parity.get("pf_delta"),
                            "cpu_total_trades": parity.get("cpu_total_trades"),
                            "gpu_total_trades": parity.get("gpu_total_trades"),
                            "cpu_total_pnl": parity.get("cpu_total_pnl"),
                            "gpu_total_pnl": parity.get("gpu_total_pnl"),
                            "cpu_final_balance": parity.get("cpu_final_balance"),
                            "gpu_final_balance": parity.get("gpu_final_balance"),
                        }
                    )

            if bool(getattr(args, "monte_carlo", False)) and trades_csv is not None:
                mc_dir = run_dir / "monte_carlo" / str(cfg_path.stem)
                mc_dir.mkdir(parents=True, exist_ok=True)
                mc_summary_path = mc_dir / "summary.json"

                mc_stdout = mc_dir / "monte_carlo.stdout.txt"
                mc_stderr = mc_dir / "monte_carlo.stderr.txt"

                if bool(args.resume) and _is_nonempty_file(mc_summary_path):
                    mc_res = CmdResult(
                        argv=[],
                        cwd=str(AIQ_ROOT),
                        exit_code=0,
                        elapsed_s=0.0,
                        stdout_path=str(mc_stdout),
                        stderr_path=str(mc_stderr),
                    )
                    meta["steps"].append({"name": f"monte_carlo_{cfg_path.stem}_skip", **mc_res.__dict__})
                else:
                    if not _is_nonempty_file(trades_csv):
                        summary["monte_carlo_error"] = "missing trade export CSV (rerun replay without --resume)"
                    else:
                        init_bal = float(summary.get("initial_balance", 0.0) or 0.0)
                        mc_argv = [
                            "python3",
                            "tools/monte_carlo_bootstrap.py",
                            "--trades-csv",
                            str(trades_csv),
                            "--initial-balance",
                            str(init_bal),
                            "--iters",
                            str(int(getattr(args, "monte_carlo_iters", 2000) or 2000)),
                            "--seed",
                            str(int(getattr(args, "monte_carlo_seed", 42) or 42)),
                            "--methods",
                            str(getattr(args, "monte_carlo_methods", "bootstrap") or "bootstrap"),
                            "--output",
                            str(mc_summary_path),
                        ]

                        mc_res = _run_cmd(mc_argv, cwd=AIQ_ROOT, stdout_path=mc_stdout, stderr_path=mc_stderr)
                        meta["steps"].append({"name": f"monte_carlo_{cfg_path.stem}", **mc_res.__dict__})
                        if mc_res.exit_code != 0:
                            _write_json(run_dir / "run_metadata.json", meta)
                            return int(mc_res.exit_code)

                summary["monte_carlo_summary_path"] = str(mc_summary_path)
                try:
                    mc_obj = _load_json(mc_summary_path)
                    dists = mc_obj.get("distributions", {}) if isinstance(mc_obj, dict) else {}
                    mc_ci: dict[str, Any] = {}
                    if isinstance(dists, dict):
                        for method, payload in dists.items():
                            if not isinstance(payload, dict):
                                continue
                            ret = (
                                payload.get("return_pct", {}) if isinstance(payload.get("return_pct", {}), dict) else {}
                            )
                            dd = (
                                payload.get("max_drawdown_pct", {})
                                if isinstance(payload.get("max_drawdown_pct", {}), dict)
                                else {}
                            )
                            mc_ci[str(method)] = {
                                "return_pct_ci95": [float(ret.get("p02_5", 0.0)), float(ret.get("p97_5", 0.0))],
                                "max_drawdown_pct_ci95": [float(dd.get("p02_5", 0.0)), float(dd.get("p97_5", 0.0))],
                                "return_pct_median": float(ret.get("p50", 0.0)),
                                "max_drawdown_pct_median": float(dd.get("p50", 0.0)),
                            }
                    summary["monte_carlo_ci"] = mc_ci
                except Exception:
                    summary["monte_carlo_error"] = "failed to load monte_carlo summary.json"

            cu_sets = getattr(args, "cross_universe_set", None)
            if isinstance(cu_sets, list) and cu_sets:
                cu_dir = run_dir / "cross_universe" / str(cfg_path.stem)
                cu_dir.mkdir(parents=True, exist_ok=True)
                cu_summary_path = cu_dir / "summary.json"

                cu_stdout = cu_dir / "cross_universe.stdout.txt"
                cu_stderr = cu_dir / "cross_universe.stderr.txt"

                if bool(args.resume) and _is_nonempty_file(cu_summary_path):
                    cu_res = CmdResult(
                        argv=[],
                        cwd=str(AIQ_ROOT),
                        exit_code=0,
                        elapsed_s=0.0,
                        stdout_path=str(cu_stdout),
                        stderr_path=str(cu_stderr),
                    )
                    meta["steps"].append({"name": f"cross_universe_{cfg_path.stem}_skip", **cu_res.__dict__})
                else:
                    cu_argv = [
                        "python3",
                        "tools/cross_universe_validate.py",
                        "--replay-report",
                        str(out_json),
                    ]
                    for it in cu_sets:
                        if it:
                            cu_argv += ["--symbol-set", str(it)]
                    cu_argv += ["--output", str(cu_summary_path)]

                    cu_res = _run_cmd(cu_argv, cwd=AIQ_ROOT, stdout_path=cu_stdout, stderr_path=cu_stderr)
                    meta["steps"].append({"name": f"cross_universe_{cfg_path.stem}", **cu_res.__dict__})
                    if cu_res.exit_code != 0:
                        _write_json(run_dir / "run_metadata.json", meta)
                        return int(cu_res.exit_code)

                summary["cross_universe_summary_path"] = str(cu_summary_path)
                try:
                    cu_obj = _load_json(cu_summary_path)
                    sets_obj = cu_obj.get("sets", []) if isinstance(cu_obj, dict) else []
                    cu_map: dict[str, Any] = {}
                    if isinstance(sets_obj, list):
                        for s in sets_obj:
                            if not isinstance(s, dict):
                                continue
                            name = str(s.get("name", "")).strip() or "set"
                            subset = s.get("subset", {}) if isinstance(s.get("subset", {}), dict) else {}
                            shares = s.get("shares", {}) if isinstance(s.get("shares", {}), dict) else {}
                            cu_map[name] = {
                                "subset_net_pnl_usd": float(subset.get("net_pnl_usd", 0.0) or 0.0),
                                "subset_trades": float(subset.get("trades", 0.0) or 0.0),
                                "share_net_pnl_usd": float(shares.get("net_pnl_usd", 0.0) or 0.0),
                                "share_trades": float(shares.get("trades", 0.0) or 0.0),
                            }
                    summary["cross_universe"] = cu_map
                except Exception:
                    summary["cross_universe_error"] = "failed to load cross_universe summary.json"

            if bool(getattr(args, "concentration_checks", False)):
                cc_dir = run_dir / "concentration" / str(cfg_path.stem)
                cc_dir.mkdir(parents=True, exist_ok=True)
                cc_summary_path = cc_dir / "summary.json"

                cc_stdout = cc_dir / "concentration.stdout.txt"
                cc_stderr = cc_dir / "concentration.stderr.txt"

                if bool(args.resume) and _is_nonempty_file(cc_summary_path):
                    cc_res = CmdResult(
                        argv=[],
                        cwd=str(AIQ_ROOT),
                        exit_code=0,
                        elapsed_s=0.0,
                        stdout_path=str(cc_stdout),
                        stderr_path=str(cc_stderr),
                    )
                    meta["steps"].append({"name": f"concentration_{cfg_path.stem}_skip", **cc_res.__dict__})
                else:
                    cc_argv = [
                        "python3",
                        "tools/concentration_checks.py",
                        "--replay-report",
                        str(out_json),
                        "--output",
                        str(cc_summary_path),
                        "--max-top1-pnl-pct",
                        str(float(getattr(args, "conc_max_top1_pnl_pct", 0.65) or 0.65)),
                        "--max-top5-pnl-pct",
                        str(float(getattr(args, "conc_max_top5_pnl_pct", 0.90) or 0.90)),
                        "--min-symbols-traded",
                        str(int(getattr(args, "conc_min_symbols_traded", 5) or 5)),
                    ]

                    cc_res = _run_cmd(cc_argv, cwd=AIQ_ROOT, stdout_path=cc_stdout, stderr_path=cc_stderr)
                    meta["steps"].append({"name": f"concentration_{cfg_path.stem}", **cc_res.__dict__})
                    if cc_res.exit_code != 0:
                        _write_json(run_dir / "run_metadata.json", meta)
                        return int(cc_res.exit_code)

                summary["concentration_summary_path"] = str(cc_summary_path)
                try:
                    cc_obj = _load_json(cc_summary_path)
                    summary["concentration_reject"] = (
                        bool(cc_obj.get("reject", False)) if isinstance(cc_obj, dict) else False
                    )
                    metrics = cc_obj.get("metrics", {}) if isinstance(cc_obj, dict) else {}
                    if isinstance(metrics, dict):
                        summary["symbols_traded"] = int(metrics.get("symbols_traded", 0) or 0)
                        summary["top1_pnl_pct"] = float(metrics.get("top1_pnl_pct", 0.0) or 0.0)
                        summary["top5_pnl_pct"] = float(metrics.get("top5_pnl_pct", 0.0) or 0.0)
                        summary["long_pnl_usd"] = float(metrics.get("long_pnl_usd", 0.0) or 0.0)
                        summary["short_pnl_usd"] = float(metrics.get("short_pnl_usd", 0.0) or 0.0)

                    if bool(summary.get("concentration_reject")):
                        reasons = cc_obj.get("reject_reasons", []) if isinstance(cc_obj, dict) else []
                        if isinstance(reasons, list) and reasons:
                            _append_reject_reason(summary, "concentration: " + ", ".join([str(r) for r in reasons]))
                        else:
                            _append_reject_reason(summary, "concentration")
                except Exception:
                    summary["concentration_error"] = "failed to load concentration summary.json"

            if bool(getattr(args, "walk_forward", False)):
                wf_dir = run_dir / "walk_forward" / str(cfg_path.stem)
                wf_dir.mkdir(parents=True, exist_ok=True)
                wf_summary_path = wf_dir / "summary.json"

                wf_stdout = wf_dir / "walk_forward.stdout.txt"
                wf_stderr = wf_dir / "walk_forward.stderr.txt"

                if bool(args.resume) and _is_nonempty_file(wf_summary_path):
                    wf_res = CmdResult(
                        argv=[],
                        cwd=str(AIQ_ROOT),
                        exit_code=0,
                        elapsed_s=0.0,
                        stdout_path=str(wf_stdout),
                        stderr_path=str(wf_stderr),
                    )
                    meta["steps"].append({"name": f"walk_forward_{cfg_path.stem}_skip", **wf_res.__dict__})
                else:
                    wf_argv = [
                        "python3",
                        "tools/walk_forward_validate.py",
                        "--config",
                        str(cfg_path),
                        "--interval",
                        str(args.interval),
                        "--min-test-days",
                        str(int(getattr(args, "walk_forward_min_test_days", 1) or 1)),
                        "--out-dir",
                        str(wf_dir),
                        "--output",
                        str(wf_summary_path),
                    ]
                    if bt_wf_splits_json:
                        wf_argv += ["--splits-json", str(bt_wf_splits_json)]
                    if bt_candles_db:
                        wf_argv += ["--candles-db", str(bt_candles_db)]
                    if bt_funding_db:
                        wf_argv += ["--funding-db", str(bt_funding_db)]

                    wf_res = _run_cmd(wf_argv, cwd=AIQ_ROOT, stdout_path=wf_stdout, stderr_path=wf_stderr)
                    meta["steps"].append({"name": f"walk_forward_{cfg_path.stem}", **wf_res.__dict__})
                    if wf_res.exit_code != 0:
                        _write_json(run_dir / "run_metadata.json", meta)
                        return int(wf_res.exit_code)

                summary["walk_forward_summary_path"] = str(wf_summary_path)
                try:
                    wf_obj = _load_json(wf_summary_path)
                    agg = wf_obj.get("aggregate", {}) if isinstance(wf_obj, dict) else {}
                    if isinstance(agg, dict):
                        summary["wf_median_oos_daily_return"] = float(agg.get("median_oos_daily_return", 0.0))
                        summary["wf_max_oos_drawdown_pct"] = float(agg.get("max_oos_drawdown_pct", 0.0))
                        summary["wf_walk_forward_score_v1"] = float(agg.get("walk_forward_score_v1", 0.0))
                except Exception:
                    # Keep the factory pipeline resilient: store the path and continue.
                    summary["wf_error"] = "failed to load walk_forward summary.json"

            if bool(getattr(args, "slippage_stress", False)):
                ss_dir = run_dir / "slippage_stress" / str(cfg_path.stem)
                ss_dir.mkdir(parents=True, exist_ok=True)
                ss_summary_path = ss_dir / "summary.json"

                ss_stdout = ss_dir / "slippage_stress.stdout.txt"
                ss_stderr = ss_dir / "slippage_stress.stderr.txt"

                if bool(args.resume) and _is_nonempty_file(ss_summary_path):
                    ss_res = CmdResult(
                        argv=[],
                        cwd=str(AIQ_ROOT),
                        exit_code=0,
                        elapsed_s=0.0,
                        stdout_path=str(ss_stdout),
                        stderr_path=str(ss_stderr),
                    )
                    meta["steps"].append({"name": f"slippage_stress_{cfg_path.stem}_skip", **ss_res.__dict__})
                else:
                    ss_argv = [
                        "python3",
                        "tools/slippage_stress.py",
                        "--config",
                        str(cfg_path),
                        "--interval",
                        str(args.interval),
                        "--slippage-bps",
                        str(getattr(args, "slippage_stress_bps", "10,20,30") or "10,20,30"),
                        "--reject-flip-bps",
                        str(float(getattr(args, "slippage_stress_reject_bps", 20.0) or 20.0)),
                        "--out-dir",
                        str(ss_dir),
                        "--output",
                        str(ss_summary_path),
                    ]
                    if bt_candles_db:
                        ss_argv += ["--candles-db", str(bt_candles_db)]
                    if bt_funding_db:
                        ss_argv += ["--funding-db", str(bt_funding_db)]

                    ss_res = _run_cmd(ss_argv, cwd=AIQ_ROOT, stdout_path=ss_stdout, stderr_path=ss_stderr)
                    meta["steps"].append({"name": f"slippage_stress_{cfg_path.stem}", **ss_res.__dict__})
                    if ss_res.exit_code != 0:
                        _write_json(run_dir / "run_metadata.json", meta)
                        return int(ss_res.exit_code)

                summary["slippage_stress_summary_path"] = str(ss_summary_path)
                try:
                    ss_obj = _load_json(ss_summary_path)
                    agg = ss_obj.get("aggregate", {}) if isinstance(ss_obj, dict) else {}
                    if isinstance(agg, dict):
                        reject_bps = float(getattr(args, "slippage_stress_reject_bps", 20.0) or 20.0)
                        summary["slippage_fragility"] = float(agg.get("slippage_fragility", 0.0))
                        summary["slippage_flip_sign_at_reject_bps"] = bool(agg.get("flip_sign_at_reject_bps", False))
                        summary["slippage_reject"] = bool(agg.get("reject", False))
                        summary["slippage_reject_bps"] = float(reject_bps)
                        summary["pnl_drop_at_reject_bps"] = float(agg.get("pnl_drop_at_reject_bps", 0.0))
                        summary["slippage_pnl_at_reject_bps"] = float(agg.get("pnl_at_reject_bps", 0.0))

                        # Canonical key for AQC-504 scoring (when using the default 20 bps).
                        if abs(float(reject_bps) - 20.0) < 1e-9:
                            summary["pnl_drop_when_slippage_20bps"] = float(summary.get("pnl_drop_at_reject_bps", 0.0))
                        if bool(summary.get("slippage_reject")):
                            _append_reject_reason(
                                summary,
                                _slippage_reject_reason(
                                    agg=agg,
                                    reject_bps=float(reject_bps),
                                    flip_sign=bool(summary.get("slippage_flip_sign_at_reject_bps", False)),
                                ),
                            )
                except Exception:
                    summary["slippage_error"] = "failed to load slippage_stress summary.json"

            if bool(getattr(args, "sensitivity_checks", False)):
                sens_dir = run_dir / "sensitivity" / str(cfg_path.stem)
                sens_dir.mkdir(parents=True, exist_ok=True)
                sens_summary_path = sens_dir / "summary.json"

                sens_stdout = sens_dir / "sensitivity.stdout.txt"
                sens_stderr = sens_dir / "sensitivity.stderr.txt"

                if bool(args.resume) and _is_nonempty_file(sens_summary_path):
                    sens_res = CmdResult(
                        argv=[],
                        cwd=str(AIQ_ROOT),
                        exit_code=0,
                        elapsed_s=0.0,
                        stdout_path=str(sens_stdout),
                        stderr_path=str(sens_stderr),
                    )
                    meta["steps"].append({"name": f"sensitivity_{cfg_path.stem}_skip", **sens_res.__dict__})
                else:
                    sens_argv = [
                        "python3",
                        "tools/sensitivity_check.py",
                        "--config",
                        str(cfg_path),
                        "--interval",
                        str(args.interval),
                        "--baseline-replay-report",
                        str(out_json),
                        "--out-dir",
                        str(sens_dir),
                        "--output",
                        str(sens_summary_path),
                        "--timeout-s",
                        str(int(getattr(args, "sensitivity_timeout_s", 0) or 0)),
                    ]
                    if getattr(args, "sensitivity_perturb", None):
                        sens_argv += ["--perturb", str(args.sensitivity_perturb)]
                    if bt_candles_db:
                        sens_argv += ["--candles-db", str(bt_candles_db)]
                    if bt_funding_db:
                        sens_argv += ["--funding-db", str(bt_funding_db)]

                    sens_res = _run_cmd(sens_argv, cwd=AIQ_ROOT, stdout_path=sens_stdout, stderr_path=sens_stderr)
                    meta["steps"].append({"name": f"sensitivity_{cfg_path.stem}", **sens_res.__dict__})
                    if sens_res.exit_code != 0:
                        _write_json(run_dir / "run_metadata.json", meta)
                        return int(sens_res.exit_code)

                summary["sensitivity_summary_path"] = str(sens_summary_path)
                try:
                    sens_obj = _load_json(sens_summary_path)
                    agg = sens_obj.get("aggregate", {}) if isinstance(sens_obj, dict) else {}
                    if isinstance(agg, dict):
                        summary["sensitivity_positive_rate"] = float(agg.get("positive_rate", 0.0))
                        summary["sensitivity_median_total_pnl"] = float(agg.get("median_total_pnl", 0.0))
                        summary["sensitivity_median_pnl_ratio_vs_baseline_abs"] = float(
                            agg.get("median_pnl_ratio_vs_baseline_abs", 0.0)
                        )
                        summary["sensitivity_metric_v1"] = float(agg.get("sensitivity_metric_v1", 0.0))
                except Exception:
                    summary["sensitivity_error"] = "failed to load sensitivity summary.json"

            score_obj = _compute_score_v1(
                summary,
                min_trades=int(getattr(args, "score_min_trades", 30) or 30),
                trades_penalty_weight=float(getattr(args, "score_trades_penalty_weight", 0.05) or 0.05),
            )
            if score_obj is not None:
                summary["score_v1"] = float(score_obj.get("score", 0.0))
                summary["score_v1_components"] = score_obj.get("components", {})

            replay_reports.append(summary)

        _write_replay_equivalence_baseline_manifest(
            run_dir=run_dir,
            meta=meta,
            replay_reports=replay_reports,
        )

        # ------------------------------------------------------------------
        # 4b) Step-4 GPU↔CPU parity report (sweep vs replay)
        # ------------------------------------------------------------------
        if step4_parity_enabled:
            try:
                reports_dir = run_dir / "reports"
                reports_dir.mkdir(parents=True, exist_ok=True)

                contract_fp = ""
                if isinstance(meta.get("step4_parity_contract"), dict):
                    contract_fp = str(meta.get("step4_parity_contract", {}).get("fingerprint", "") or "")

                # Persist TSV / JSON / MD reports for the 30-row validation table.
                fieldnames = [
                    "status",
                    "cause",
                    "sort_by",
                    "rank",
                    "trades_delta",
                    "pnl_delta",
                    "dd_delta",
                    "pf_delta",
                    "cpu_total_trades",
                    "gpu_total_trades",
                    "cpu_total_pnl",
                    "gpu_total_pnl",
                    "cpu_final_balance",
                    "gpu_final_balance",
                    "config_path",
                    "overrides_key",
                ]
                _write_tsv(reports_dir / "step4_gpu_cpu_parity.tsv", step4_parity_rows, fieldnames=fieldnames)

                step4_md = _render_step4_parity_report_md(
                    step4_parity_rows,
                    contract_fingerprint=contract_fp,
                    thresholds=step4_parity_thresholds,
                )
                (reports_dir / "step4_gpu_cpu_parity.md").write_text(step4_md, encoding="utf-8")
                _write_json(
                    reports_dir / "step4_gpu_cpu_parity.json",
                    {
                        "contract_fingerprint": contract_fp,
                        "thresholds": step4_parity_thresholds,
                        "items": step4_parity_rows,
                    },
                )

                fails = [r for r in step4_parity_rows if str(r.get("status")) != "pass"]
                meta["step4_parity"] = {
                    "enabled": True,
                    "contract_fingerprint": contract_fp,
                    "thresholds": step4_parity_thresholds,
                    "total": len(step4_parity_rows),
                    "failures": len(fails),
                    "failures_by_cause": {
                        "state_machine": sum(1 for r in fails if str(r.get("cause")) == "state_machine"),
                        "reduction_order": sum(1 for r in fails if str(r.get("cause")) == "reduction_order"),
                    },
                    "report_paths": {
                        "tsv": str(reports_dir / "step4_gpu_cpu_parity.tsv"),
                        "md": str(reports_dir / "step4_gpu_cpu_parity.md"),
                        "json": str(reports_dir / "step4_gpu_cpu_parity.json"),
                    },
                }

                if fails and bool(getattr(args, "step4_parity_enforce", False)):
                    meta["step4_parity"]["enforced"] = True
                    _write_json(run_dir / "run_metadata.json", meta)
                    return 1
            except Exception as e:
                meta["step4_parity_error"] = f"{type(e).__name__}: {e}"

        # ------------------------------------------------------------------
        # 5) Final report
        # ------------------------------------------------------------------
        current_stage = "final_report"
        if _shutdown_stage_guard(run_dir=run_dir, meta=meta, stage=current_stage):
            return 130
        report_md = _render_ranked_report_md(replay_reports)
        (run_dir / "reports").mkdir(parents=True, exist_ok=True)
        (run_dir / "reports" / "report.md").write_text(report_md, encoding="utf-8")
        _write_json(run_dir / "reports" / "report.json", {"items": replay_reports})
        validation_md = _render_validation_report_md(
            replay_reports, score_min_trades=int(getattr(args, "score_min_trades", 30) or 30)
        )
        (run_dir / "reports" / "validation_report.md").write_text(validation_md, encoding="utf-8")

        # ------------------------------------------------------------------
        # 5b) Candidate promotion (20→3)
        # ------------------------------------------------------------------
        promote_count = int(getattr(args, "promote_count", 3) or 0)
        promote_dir = str(getattr(args, "promote_dir", "promoted_configs") or "promoted_configs")
        if promote_count > 0 and replay_reports:
            promotion_meta = _promote_candidates(
                replay_reports,
                run_dir=run_dir,
                promote_dir=promote_dir,
                promote_count=promote_count,
            )
            meta["promotion"] = promotion_meta
        else:
            meta["promotion"] = {"skipped": True, "reason": "promote_count=0 or no replay reports"}

        # Persist metadata before registry ingestion (ingest reads run_metadata.json).
        _write_json(run_dir / "run_metadata.json", meta)

        # ------------------------------------------------------------------
        # 6) Registry index
        # ------------------------------------------------------------------
        current_stage = "registry_index"
        if _shutdown_stage_guard(run_dir=run_dir, meta=meta, stage=current_stage):
            return 130
        registry_db = default_registry_db_path(artifacts_root=artifacts_root)
        meta["registry_db"] = str(registry_db)
        try:
            res = ingest_run_dir(registry_db=registry_db, run_dir=run_dir)
            meta["registry_ingest"] = res.__dict__
        except Exception as e:
            meta["registry_error"] = str(e)
            _write_json(run_dir / "run_metadata.json", meta)
            return 1

        _write_json(run_dir / "run_metadata.json", meta)
        return 0
    except Exception as exc:
        if run_dir is not None and isinstance(meta, dict):
            try:
                _mark_run_fatal_error(run_dir=run_dir, meta=meta, stage=current_stage, exc=exc)
            except Exception:
                pass
        raise
    finally:
        _restore_shutdown_handlers(prev_handlers)
        if _SHUTDOWN_REQUESTED:
            status = str(meta.get("status", "")) if isinstance(meta, dict) else ""
            if run_dir is not None and isinstance(meta, dict) and status not in {"interrupted", "failed"}:
                _mark_run_interrupted(run_dir=run_dir, meta=meta, stage=current_stage)
                return 130
            if status != "failed":
                return 130


def _apply_profile_defaults(args: argparse.Namespace) -> None:
    profile = str(getattr(args, "profile", "") or "daily").strip()
    defaults = PROFILE_DEFAULTS.get(profile)
    if defaults is None:
        raise SystemExit(f"Unknown --profile: {profile}")

    for k, v in defaults.items():
        if not hasattr(args, k):
            continue
        if getattr(args, k) is None:
            setattr(args, k, int(v) if isinstance(v, int) else v)


def _promote_candidates(
    candidates: list[dict[str, Any]],
    *,
    run_dir: Path,
    promote_dir: str = "promoted_configs",
    promote_count: int = 3,
) -> dict[str, Any]:
    """Select up to *promote_count* candidates for role channels and write promoted YAMLs.

    Channel policy:
      1) shortlist/backtest lanes: efficient, growth, conservative
      2) promotion picks rank #1 per lane after gate/evidence checks
      3) if a lane has no eligible row, fallback to role formula ranking
    """

    if promote_count <= 0:
        return {"skipped": True, "reason": "promote_count=0"}

    # Gate/evidence eligibility first, then role/channel selection.
    gated = [
        c
        for c in candidates
        if str(c.get("config_path", "") or c.get("path", "")).strip()
        and not bool(c.get("rejected", False))
        and bool(c.get("canonical_cpu_verified", True))
        and str(c.get("replay_equivalence_status", "pass")).strip().lower() == "pass"
    ]
    if not gated:
        return {"skipped": True, "reason": "no_gate_eligible_candidates"}

    # ---- Scoring helpers ------------------------------------------------
    def _risk_adjusted_score(c: dict[str, Any]) -> float:
        """Risk-adjusted: (PnL / DD) × PF.  Favours high return per unit of risk."""
        pnl = float(c.get("total_pnl", 0.0))
        dd = max(float(c.get("max_drawdown_pct", 1.0)), 0.01)  # floor to avoid div-by-zero
        pf = max(float(c.get("profit_factor", 1.0)), 0.0)
        return (pnl / dd) * pf

    def _balanced_score(c: dict[str, Any]) -> float:
        """Growth: PnL × (1 - DD) × PF.  Rewards raw PnL with mild DD penalty."""
        pnl = float(c.get("total_pnl", 0.0))
        dd = float(c.get("max_drawdown_pct", 0.0))
        pf = float(c.get("profit_factor", 1.0))
        return pnl * (1.0 - min(dd, 1.0)) * max(pf, 0.0)

    def _channel_ranked(rows: list[dict[str, Any]], channel: str) -> list[dict[str, Any]]:
        chan = str(channel).strip().lower()
        xs = [r for r in rows if str(r.get("sort_by", "")).strip().lower() == chan]
        xs.sort(
            key=lambda r: (
                int(r.get("rank", 10**9) or 10**9),
                -(float(r.get("score_v1", float("-inf")) or float("-inf"))),
                -(float(r.get("total_pnl", 0.0) or 0.0)),
            )
        )
        return xs

    # ---- Role selection -------------------------------------------------
    roles: dict[str, dict[str, Any]] = {}
    role_meta: dict[str, dict[str, Any]] = {}
    used_ids: set[str] = set()

    eff_ranked = _channel_ranked(gated, "efficient")
    gro_ranked = _channel_ranked(gated, "growth")
    con_ranked = _channel_ranked(gated, "conservative")

    # Backward-compatible aliases for older runs.
    if not gro_ranked:
        gro_ranked = _channel_ranked(gated, "balanced")
    if not con_ranked:
        con_ranked = _channel_ranked(gated, "dd")

    eff_formula = sorted(gated, key=_risk_adjusted_score, reverse=True)
    gro_formula = sorted(gated, key=_balanced_score, reverse=True)
    con_formula = sorted(
        gated,
        key=lambda c: (
            float(c.get("max_drawdown_pct", 1.0) or 1.0),
            -(float(c.get("total_pnl", 0.0) or 0.0)),
            -(float(c.get("profit_factor", 0.0) or 0.0)),
        ),
    )

    def _pick_role(
        role_name: str,
        channel_rows: list[dict[str, Any]],
        formula_rows: list[dict[str, Any]],
        channel_label: str,
    ) -> dict[str, Any] | None:
        for cand in channel_rows:
            cid = str(cand.get("config_id", "")).strip()
            if cid and cid not in used_ids:
                used_ids.add(cid)
                role_meta[role_name] = {"selection_source": "channel_rank1", "channel": channel_label}
                return cand
        for cand in formula_rows:
            cid = str(cand.get("config_id", "")).strip()
            if cid and cid not in used_ids:
                used_ids.add(cid)
                role_meta[role_name] = {"selection_source": "formula_fallback", "channel": channel_label}
                return cand
        if channel_rows:
            cand = channel_rows[0]
            cid = str(cand.get("config_id", "")).strip()
            if cid:
                used_ids.add(cid)
            role_meta[role_name] = {"selection_source": "channel_rank1_reuse", "channel": channel_label}
            return cand
        if formula_rows:
            cand = formula_rows[0]
            cid = str(cand.get("config_id", "")).strip()
            if cid:
                used_ids.add(cid)
            role_meta[role_name] = {"selection_source": "formula_fallback_reuse", "channel": channel_label}
            return cand
        return None

    primary = _pick_role("primary", eff_ranked, eff_formula, "efficient")
    fallback = _pick_role("fallback", gro_ranked, gro_formula, "growth")
    conservative = _pick_role("conservative", con_ranked, con_formula, "conservative")
    if primary is not None:
        roles["primary"] = primary
    if fallback is not None:
        roles["fallback"] = fallback
    if conservative is not None:
        roles["conservative"] = conservative
    if not roles:
        return {"skipped": True, "reason": "unable_to_select_roles_from_gated_candidates"}

    # ---- Write promoted configs -----------------------------------------
    out_dir = run_dir / promote_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    promotion_meta: dict[str, Any] = {
        "skipped": False,
        "promote_dir": str(out_dir),
        "roles": {},
    }

    written = 0
    for role_name, cand in roles.items():
        if written >= promote_count:
            break

        cfg_path_str = str(cand.get("config_path", "") or cand.get("path", "")).strip()
        if not cfg_path_str:
            continue

        src = Path(cfg_path_str)
        if not src.exists():
            promotion_meta["roles"][role_name] = {
                "config_id": str(cand.get("config_id", "")),
                "error": f"source config not found: {src}",
            }
            continue

        dst = out_dir / f"{role_name}.yaml"

        # Read source and write (preserve YAML if possible).
        try:
            content = src.read_text(encoding="utf-8")
            dst.write_text(content, encoding="utf-8")
        except Exception as exc:
            promotion_meta["roles"][role_name] = {
                "config_id": str(cand.get("config_id", "")),
                "error": f"copy failed: {type(exc).__name__}: {exc}",
            }
            continue

        promotion_meta["roles"][role_name] = {
            "config_id": str(cand.get("config_id", "")),
            "source_config": str(src),
            "promoted_path": str(dst),
            "total_pnl": float(cand.get("total_pnl", 0.0)),
            "max_drawdown_pct": float(cand.get("max_drawdown_pct", 0.0)),
            "profit_factor": float(cand.get("profit_factor", 0.0)),
            "balanced_score": _balanced_score(cand),
            "risk_adjusted_score": _risk_adjusted_score(cand),
            "selection_source": str((role_meta.get(role_name, {}) or {}).get("selection_source", "")),
            "channel": str((role_meta.get(role_name, {}) or {}).get("channel", "")),
            "rank": int(cand.get("rank", 0) or 0),
            "sort_by": str(cand.get("sort_by", "") or ""),
        }
        written += 1

    promotion_meta["promoted_count"] = written
    return promotion_meta


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Run the nightly strategy factory workflow and store artifacts.")
    mx = ap.add_mutually_exclusive_group(required=True)
    mx.add_argument("--run-id", help="Unique identifier for this run (used in artifact paths).")
    mx.add_argument("--reproduce", metavar="RUN_ID", help="Reproduce an existing run_id (CPU replay + reports only).")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root directory (default: artifacts).")
    ap.add_argument("--resume", action="store_true", help="Resume an existing run_id from artifacts.")
    ap.add_argument(
        "--allow-binary-drift",
        action="store_true",
        help="Allow --resume even if the backtester command/binary fingerprint differs from the original run.",
    )
    ap.add_argument(
        "--allow-input-drift",
        action="store_true",
        help="Allow --resume even if candles/funding inputs drift (mtime/size fingerprint mismatch).",
    )

    ap.add_argument(
        "--profile",
        default="daily",
        choices=sorted(PROFILE_DEFAULTS.keys()),
        help="Preset defaults for trials and candidate counts (default: daily).",
    )

    ap.add_argument("--config", default="config/strategy_overrides.yaml", help="Base strategy YAML config path.")
    ap.add_argument("--interval", default="30m", help="Main interval for sweep/replay (default: 30m).")
    ap.add_argument(
        "--start-ts",
        default="",
        help="Backtest window start timestamp (forwarded to mei-backtester; ms epoch recommended).",
    )
    ap.add_argument(
        "--end-ts",
        default="",
        help="Backtest window end timestamp (forwarded to mei-backtester; ms epoch recommended).",
    )
    ap.add_argument("--candles-db", default=None, help="Optional candle DB path override.")
    ap.add_argument("--funding-db", default=None, help="Optional funding DB path for replay/sweep.")
    ap.add_argument(
        "--max-age-fail-hours",
        type=float,
        default=_env_float("AI_QUANT_FUNDING_MAX_AGE_FAIL_HOURS"),
        help="Override funding check fail age (hours) for stale data. Default: checker default (typically 12h).",
    )
    ap.add_argument(
        "--funding-max-stale-symbols",
        type=int,
        default=_env_int("AI_QUANT_FUNDING_MAX_STALE_SYMBOLS", default=0),
        help="Allow this many stale symbols to pass as WARN before treating funding check as FAIL.",
    )

    ap.add_argument("--sweep-spec", default=None, help="Sweep spec YAML path.")
    ap.add_argument(
        "--sweep-parity-mode",
        default="production",
        choices=["production", "identical-symbol-universe"],
        help="Sweep parity mode (default: production).",
    )
    ap.add_argument("--gpu", action="store_true", help="Use GPU sweep (requires CUDA build/runtime).")
    ap.add_argument(
        "--allow-unsafe-gpu-sweep",
        action="store_true",
        help="Override GPU sweep guardrails for long windows.",
    )
    ap.add_argument(
        "--gpu-wait-s",
        type=int,
        default=0,
        help="Wait up to N seconds for an idle GPU before exiting (default: 0).",
    )
    ap.add_argument(
        "--gpu-poll-s",
        type=int,
        default=10,
        help="Polling interval in seconds while waiting for GPU idle (default: 10).",
    )
    ap.add_argument("--tpe", action="store_true", help="Use TPE Bayesian optimisation for GPU sweeps (requires --gpu).")
    ap.add_argument("--tpe-trials", type=int, default=None, help="Number of TPE trials (default depends on --profile).")
    ap.add_argument("--tpe-batch", type=int, default=256, help="Trials per GPU batch (default: 256).")
    ap.add_argument("--tpe-seed", type=int, default=42, help="RNG seed for TPE reproducibility (default: 42).")
    ap.add_argument("--top-n", type=int, default=0, help="Only print top N sweep results (0 = no summary).")

    ap.add_argument(
        "--num-candidates",
        type=int,
        default=None,
        help="How many candidate configs to generate when shortlist is disabled (default depends on --profile).",
    )
    ap.add_argument(
        "--sort-by",
        default="balanced",
        choices=["pnl", "dd", "pf", "wr", "sharpe", "trades", "balanced", "efficient", "growth", "conservative"],
        help="Sort metric for candidate selection when shortlist is disabled (default: balanced).",
    )
    ap.add_argument(
        "--candidate-min-trades",
        type=int,
        default=1,
        help=(
            "Minimum trade count required when selecting shortlist/candidate configurations. "
            "Set to 0 to include zero-trade candidates."
        ),
    )
    ap.add_argument(
        "--shortlist-modes",
        default="efficient,growth,conservative",
        help="Comma-separated channel modes to generate per sweep (default: efficient,growth,conservative).",
    )
    ap.add_argument(
        "--shortlist-per-mode",
        type=int,
        default=None,
        help="How many unique configs to keep per mode (default depends on --profile). Set 0 to disable shortlist.",
    )
    ap.add_argument(
        "--shortlist-max-rank",
        type=int,
        default=None,
        help="Max rank to scan per mode while deduplicating (default depends on --profile).",
    )
    ap.add_argument(
        "--shortlist-top-pnl",
        type=int,
        default=1000,
        help="Stage-1 shortlist pool size by PnL from sweep results (default: 1000).",
    )

    # Step-4 GPU↔CPU parity report / gate
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

    ap.add_argument("--walk-forward", action="store_true", help="Run walk-forward validation for each candidate.")
    ap.add_argument("--walk-forward-splits-json", default=None, help="Optional JSON file defining walk-forward splits.")
    ap.add_argument(
        "--walk-forward-min-test-days",
        type=int,
        default=1,
        help="Minimum out-of-sample test length in days for walk-forward splits (default: 1).",
    )

    ap.add_argument("--slippage-stress", action="store_true", help="Run slippage stress replays for each candidate.")
    ap.add_argument(
        "--slippage-stress-bps",
        default="10,20,30",
        help="Comma-separated slippage bps levels for stress tests (default: 10,20,30).",
    )
    ap.add_argument(
        "--slippage-stress-reject-bps",
        type=float,
        default=20.0,
        help="Reject when PnL flips sign at this slippage level (default: 20).",
    )

    ap.add_argument(
        "--concentration-checks",
        action="store_true",
        help="Run concentration/diversification checks from replay output (per-symbol breakdown).",
    )
    ap.add_argument(
        "--conc-max-top1-pnl-pct",
        type=float,
        default=0.65,
        help="Reject if top-1 symbol contributes more than this fraction of positive PnL (default: 0.65).",
    )
    ap.add_argument(
        "--conc-max-top5-pnl-pct",
        type=float,
        default=0.90,
        help="Reject if top-5 symbols contribute more than this fraction of positive PnL (default: 0.90).",
    )
    ap.add_argument(
        "--conc-min-symbols-traded",
        type=int,
        default=5,
        help="Reject if fewer than this many symbols had at least one trade (default: 5).",
    )

    ap.add_argument(
        "--sensitivity-checks",
        action="store_true",
        help="Run small parameter perturbation replays to estimate config fragility.",
    )
    ap.add_argument(
        "--sensitivity-perturb",
        default=None,
        help="Override the perturbation set (comma-separated dotpath:delta items).",
    )
    ap.add_argument(
        "--sensitivity-timeout-s",
        type=int,
        default=0,
        help="Per-variant replay timeout in seconds for sensitivity checks (default: 0).",
    )

    ap.add_argument(
        "--monte-carlo",
        action="store_true",
        help="Run Monte Carlo/bootstrap analysis on trade outcomes (confidence intervals for return and drawdown).",
    )
    ap.add_argument(
        "--monte-carlo-iters",
        type=int,
        default=2000,
        help="Number of Monte Carlo iterations per candidate (default: 2000).",
    )
    ap.add_argument(
        "--monte-carlo-seed",
        type=int,
        default=42,
        help="RNG seed for Monte Carlo reproducibility (default: 42).",
    )
    ap.add_argument(
        "--monte-carlo-methods",
        default="bootstrap",
        help="Comma-separated methods: bootstrap,shuffle (default: bootstrap).",
    )

    ap.add_argument(
        "--cross-universe-set",
        action="append",
        default=[],
        help="Cross-universe symbol set in NAME=PATH format (repeatable). Compares subset vs full using per_symbol stats.",
    )

    ap.add_argument(
        "--score-min-trades",
        type=int,
        default=30,
        help="Minimum trade count used by score_v1 trades penalty (default: 30).",
    )
    ap.add_argument(
        "--score-trades-penalty-weight",
        type=float,
        default=0.05,
        help="Maximum score_v1 trades penalty when trades=0 (default: 0.05).",
    )

    ap.add_argument(
        "--promote-count",
        type=int,
        default=3,
        help="Number of candidates to promote (0 to skip promotion entirely). Default: 3.",
    )
    ap.add_argument(
        "--promote-dir",
        default="promoted_configs",
        help="Sub-directory under the run dir for promoted config YAMLs (default: promoted_configs).",
    )

    return ap


def _parse_cli_args(argv: list[str] | None) -> argparse.Namespace:
    ap = _build_arg_parser()
    args = ap.parse_args(argv)
    _apply_profile_defaults(args)
    return args


if __name__ == "__main__":
    raise SystemExit(main())
