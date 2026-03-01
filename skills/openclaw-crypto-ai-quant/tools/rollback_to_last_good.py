#!/usr/bin/env python3
"""Rollback to last-known-good config for paper trading (AQC-704).

This command restores the previous config captured by `tools/paper_deploy.py`
and records a rollback event with a human reason.

It is intended for emergency response and should be used with care.
"""

from __future__ import annotations

import argparse
from contextlib import suppress
import getpass
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from tools.deploy_validate import validate_yaml_text
except ImportError:  # pragma: no cover
    from deploy_validate import validate_yaml_text  # type: ignore[no-redef]


AIQ_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RestartResult:
    attempted: bool
    exit_code: int
    stdout: str
    stderr: str


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_file.write(text)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_path = Path(tmp_file.name)
        os.replace(str(tmp_path), str(path))
    finally:
        if tmp_path is not None and tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


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


def _restart_systemd_user_service(service: str) -> RestartResult:
    service = str(service).strip()
    if not service:
        return RestartResult(attempted=False, exit_code=0, stdout="", stderr="service name is empty")

    proc = subprocess.run(
        ["systemctl", "--user", "restart", service],
        capture_output=True,
        text=True,
        check=False,
    )
    return RestartResult(
        attempted=True,
        exit_code=int(proc.returncode),
        stdout=str(proc.stdout or ""),
        stderr=str(proc.stderr or ""),
    )


def _list_deploy_dirs(deploy_root: Path) -> list[Path]:
    if not deploy_root.exists():
        return []
    dirs = [p for p in deploy_root.iterdir() if p.is_dir()]
    # Directories are prefixed with UTC timestamps; sort lexicographically desc.
    return sorted(dirs, key=lambda p: p.name, reverse=True)


def rollback_to_last_good(
    *,
    artifacts_dir: Path,
    yaml_path: Path,
    steps: int,
    reason: str,
    restart: str,
    service: str,
    dry_run: bool,
) -> Path:
    artifacts_dir = Path(artifacts_dir).expanduser().resolve()
    yaml_path = Path(yaml_path).expanduser().resolve()

    deploy_root = (artifacts_dir / "deployments" / "paper").resolve()
    deploy_dirs = _list_deploy_dirs(deploy_root)
    steps = int(steps)
    if steps <= 0:
        steps = 1
    if len(deploy_dirs) < steps:
        raise FileNotFoundError(f"Not enough deployments under {deploy_root} for steps={steps}")

    src_dir = deploy_dirs[steps - 1]
    prev_path = src_dir / "prev_config.yaml"
    restored_text = _read_text(prev_path).strip()
    restored_from = str(prev_path)

    # Fallback: use the deployed_config.yaml from the next older deployment.
    if not restored_text:
        if len(deploy_dirs) >= steps + 1:
            alt_dir = deploy_dirs[steps]
            alt_path = alt_dir / "deployed_config.yaml"
            restored_text = _read_text(alt_path).strip()
            restored_from = str(alt_path)
        if not restored_text:
            raise FileNotFoundError("Could not locate a rollback config (prev_config.yaml missing/empty).")

    errs = validate_yaml_text(restored_text)
    if errs:
        msg = "Rollback config failed validation:\n" + "\n".join([f"- {e}" for e in errs])
        raise ValueError(msg)

    current_text = _read_text(yaml_path)
    cur_interval = _load_yaml_engine_interval(current_text)
    next_interval = _load_yaml_engine_interval(restored_text)
    restart_required = bool(cur_interval and next_interval and cur_interval != next_interval)

    ts = _utc_compact()
    rollback_root = (artifacts_dir / "rollbacks" / "paper").resolve()
    rollback_root.mkdir(parents=True, exist_ok=True)
    rollback_dir = (rollback_root / ts).resolve()
    try:
        rollback_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        # Same-second concurrent rollbacks should not overwrite each other's artifacts.
        while True:
            suffix = f"{os.getpid()}-{threading.get_ident()}-{time.time_ns()}"
            candidate = (rollback_root / f"{ts}-{suffix}").resolve()
            try:
                candidate.mkdir(parents=False, exist_ok=False)
                rollback_dir = candidate
                break
            except FileExistsError:
                continue

    _atomic_write_text(rollback_dir / "restored_config.yaml", restored_text + "\n")

    event: dict[str, Any] = {
        "version": "rollback_event_v1",
        "ts_utc": _utc_now_iso(),
        "ts_compact_utc": ts,
        "who": {"user": getpass.getuser(), "hostname": socket.gethostname()},
        "what": {
            "mode": "paper",
            "yaml_path": str(yaml_path),
            "source_deploy_dir": str(src_dir),
            "restored_from": str(restored_from),
            "current_yaml_sha256": hashlib.sha256(current_text.encode("utf-8")).hexdigest() if current_text else "",
            "restored_yaml_sha256": hashlib.sha256(restored_text.encode("utf-8")).hexdigest(),
            "current_engine_interval": cur_interval,
            "restored_engine_interval": next_interval,
            "restart_required": bool(restart_required),
            "steps": int(steps),
        },
        "why": {"reason": str(reason or "").strip()},
        "dry_run": bool(dry_run),
        "restart": {"mode": str(restart), "service": str(service), "result": None},
    }

    if not dry_run:
        _atomic_write_text(yaml_path, restored_text + "\n")

    restart_mode = str(restart or "auto").strip().lower()
    do_restart = (restart_mode == "always") or (restart_mode == "auto" and restart_required)
    if do_restart and not dry_run:
        rr = _restart_systemd_user_service(str(service))
        event["restart"]["result"] = rr.__dict__
        if rr.attempted and rr.exit_code != 0:
            _atomic_write_text(rollback_dir / "rollback_event.json", json.dumps(event, indent=2, sort_keys=True) + "\n")
            raise RuntimeError(f"service restart failed: {service} (exit_code={rr.exit_code})")

    _atomic_write_text(rollback_dir / "rollback_event.json", json.dumps(event, indent=2, sort_keys=True) + "\n")
    return rollback_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rollback paper trading config to last-known-good.")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root (default: artifacts).")
    ap.add_argument(
        "--yaml-path",
        default=str(AIQ_ROOT / "config" / "strategy_overrides.yaml"),
        help="Target strategy overrides YAML path (default: config/strategy_overrides.yaml).",
    )
    ap.add_argument("--steps", type=int, default=1, help="How many deploy steps to roll back (default: 1).")
    ap.add_argument("--reason", default="", help="Human reason for rollback (recorded).")
    ap.add_argument(
        "--restart",
        default="auto",
        choices=["auto", "always", "never"],
        help="Restart policy (default: auto).",
    )
    ap.add_argument(
        "--service",
        default="openclaw-ai-quant-trader",
        help="systemd user service name for paper trader (default: openclaw-ai-quant-trader).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Write artefacts but do not modify YAML or restart.")
    args = ap.parse_args(argv)

    rollback_to_last_good(
        artifacts_dir=Path(args.artifacts_dir),
        yaml_path=Path(args.yaml_path),
        steps=int(args.steps),
        reason=str(args.reason),
        restart=str(args.restart),
        service=str(args.service),
        dry_run=bool(args.dry_run),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
