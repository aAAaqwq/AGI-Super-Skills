#!/usr/bin/env python3
"""Deploy a selected config_id to the paper trader safely (AQC-701).

This command:
1) Looks up the fully materialised YAML for a config_id from the local registry SQLite DB.
2) Writes it to the configured strategy overrides YAML path atomically (no partial writes).
3) Emits a `deploy_event.json` artefact with who/what/when/why and basic deployment metadata.
4) Optionally restarts the paper trading service when required (e.g. main interval change).

The default integration branch is `major-v8`; do not deploy to production from this repository
without explicit operator confirmation.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import sqlite3
import subprocess
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
    from tools.registry_index import default_registry_db_path
except ImportError:  # pragma: no cover
    from registry_index import default_registry_db_path  # type: ignore[no-redef]

try:
    from tools.deploy_validate import validate_yaml_text
except ImportError:  # pragma: no cover
    from deploy_validate import validate_yaml_text  # type: ignore[no-redef]

try:
    from tools.interval_orchestrator import orchestrate_interval_restart
except ImportError:  # pragma: no cover
    from interval_orchestrator import orchestrate_interval_restart  # type: ignore[no-redef]

try:
    from tools.replay_gate_blocker import ReplayGateViolation, assert_replay_gate_green
except ImportError:  # pragma: no cover
    from replay_gate_blocker import ReplayGateViolation, assert_replay_gate_green  # type: ignore[no-redef]


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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def _load_yaml_engine_interval(yaml_text: str) -> str:
    # Best-effort parse without importing project code; YAML is expected to be small.
    try:
        import yaml  # local import to keep script dependency surface minimal

        obj = yaml.safe_load(yaml_text) or {}
        if not isinstance(obj, dict):
            return ""
        glob = obj.get("global", {}) if isinstance(obj.get("global", {}), dict) else {}
        eng = glob.get("engine", {}) if isinstance(glob.get("engine", {}), dict) else {}
        iv = eng.get("interval", "")
        return str(iv or "").strip()
    except Exception:
        return ""


def _lookup_config_yaml_text(*, registry_db: Path, config_id: str) -> str:
    con = sqlite3.connect(str(registry_db), timeout=2.0)
    try:
        row = con.execute("SELECT yaml_text FROM configs WHERE config_id = ? LIMIT 1", (str(config_id),)).fetchone()
        if not row:
            raise KeyError(f"config_id not found in registry: {config_id}")
        yaml_text = str(row[0] or "")
        if not yaml_text.strip():
            raise ValueError(f"Empty yaml_text for config_id: {config_id}")
        return yaml_text
    finally:
        con.close()


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


def _service_environment(service: str) -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "show", "-p", "Environment", "--value", str(service)],
            capture_output=True,
            text=True,
            check=False,
            timeout=8.0,
        )
        if int(proc.returncode) != 0:
            return {}
        raw = str(proc.stdout or "").strip()
        out: dict[str, str] = {}
        for part in raw.split():
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            key = str(k or "").strip()
            if key:
                out[key] = str(v or "")
        return out
    except Exception:
        return {}


def _update_service_env_file(service: str, key: str, value: str) -> None:
    # Standard v8 service naming: openclaw-ai-quant-trader-v8-<name>
    name = str(service).split("-")[-1]
    env_file = Path(f"/home/fol2hk/.config/openclaw/ai-quant-trader-v8-{name}.env")
    if not env_file.exists():
        # Fallback to older naming if it exists
        alt_file = Path(f"/home/fol2hk/.config/openclaw/ai-quant-trader-{name}.env")
        if alt_file.exists():
            env_file = alt_file
    if not env_file.exists():
        return

    lines = env_file.read_text(encoding="utf-8").splitlines()
    out = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    env_file.write_text("\n".join(out) + "\n", encoding="utf-8")


def deploy_paper_config(
    *,
    config_id: str,
    artifacts_dir: Path,
    yaml_path: Path,
    out_dir: Path | None,
    reason: str,
    restart: str,
    service: str,
    dry_run: bool,
    validate: bool,
    ws_service: str = "openclaw-ai-quant-ws-sidecar",
    pause_file: Path | None = None,
    pause_mode: str = "close_only",
    resume_on_success: bool = True,
    verify_sleep_s: float = 2.0,
    mirror_source: str | None = None,
    skip_mirror: bool = False,
    mirror_on_config_change: bool = False,
) -> Path:
    """Deploy config_id to yaml_path and return the deploy directory path."""
    config_id = str(config_id).strip()
    if not config_id:
        raise ValueError("config_id cannot be empty")

    artifacts_dir = Path(artifacts_dir).expanduser().resolve()
    yaml_path = Path(yaml_path).expanduser().resolve()
    registry_db = default_registry_db_path(artifacts_root=artifacts_dir)

    yaml_text = _lookup_config_yaml_text(registry_db=registry_db, config_id=config_id)
    computed_id = config_id_from_yaml_text(yaml_text)
    if computed_id != config_id:
        raise ValueError(f"registry yaml_text hash mismatch: expected {config_id}, got {computed_id}")

    if bool(validate):
        errs = validate_yaml_text(yaml_text)
        if errs:
            msg = "Invalid config YAML (deployment validation failed):\n" + "\n".join([f"- {e}" for e in errs])
            raise ValueError(msg)

    prev_text = _read_text(yaml_path)
    prev_interval = _load_yaml_engine_interval(prev_text)
    next_interval = _load_yaml_engine_interval(yaml_text)
    restart_required = bool(prev_interval and next_interval and prev_interval != next_interval)

    ts = _utc_compact()
    short = config_id[:12]
    deploy_dir = (
        Path(out_dir).expanduser().resolve()
        if out_dir is not None
        else (artifacts_dir / "deployments" / "paper" / f"{ts}_{short}").resolve()
    )
    deploy_dir.mkdir(parents=True, exist_ok=True)

    event: dict[str, Any] = {
        "version": "deploy_event_v1",
        "ts_utc": _utc_now_iso(),
        "ts_compact_utc": ts,
        "who": {
            "user": getpass.getuser(),
            "hostname": socket.gethostname(),
        },
        "what": {
            "mode": "paper",
            "config_id": config_id,
            "registry_db": str(registry_db),
            "yaml_path": str(yaml_path),
            "prev_yaml_sha256": "",
            "next_yaml_sha256": "",
            "prev_engine_interval": prev_interval,
            "next_engine_interval": next_interval,
            "restart_required": bool(restart_required),
        },
        "why": {
            "reason": str(reason or "").strip(),
        },
        "dry_run": bool(dry_run),
        "restart": {
            "mode": str(restart),
            "service": str(service),
            "result": None,
        },
    }

    import hashlib

    event["what"]["prev_yaml_sha256"] = hashlib.sha256(prev_text.encode("utf-8")).hexdigest() if prev_text else ""
    event["what"]["next_yaml_sha256"] = hashlib.sha256(yaml_text.encode("utf-8")).hexdigest()
    config_changed = event["what"]["prev_yaml_sha256"] != event["what"]["next_yaml_sha256"]
    event["what"]["config_changed"] = bool(config_changed)

    # Always write the artefact, even in dry-run mode.
    (deploy_dir / "deployed_config.yaml").write_text(yaml_text, encoding="utf-8")
    (deploy_dir / "prev_config.yaml").write_text(prev_text, encoding="utf-8")

    if not dry_run:
        _atomic_write_text(yaml_path, yaml_text)

    restart_mode = str(restart or "auto").strip().lower()
    do_restart = (restart_mode == "always") or (restart_mode == "auto" and restart_required)
    if do_restart and not dry_run:
        results = orchestrate_interval_restart(
            ws_service=str(ws_service),
            trader_service=str(service),
            pause_file=pause_file,
            pause_mode=str(pause_mode or "close_only"),
            resume_on_success=bool(resume_on_success),
            verify_sleep_s=float(verify_sleep_s),
        )
        event["restart"]["result"] = {"results": [r.__dict__ for r in results]}
        if any(not bool(r.ok) for r in results):
            # Record the event and fail fast to avoid silent deploys without a functioning engine.
            (deploy_dir / "deploy_event.json").write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            failed = next((r for r in results if not bool(r.ok)), None)
            if failed is None:
                raise RuntimeError(f"service restart failed: {service}")
            raise RuntimeError(f"service restart failed: {failed.service} (exit_code={failed.exit_code})")

    # Mirror can be enabled either by the legacy env toggle or explicitly by
    # the caller for config-change cutovers.
    mirror_env_enabled = os.getenv("AI_QUANT_MIRROR_LIVE_ON_PROMOTE", "false").lower() in ("true", "1", "yes")
    mirror_enabled = (
        not bool(skip_mirror)
        and (
            bool(mirror_env_enabled)
            or (bool(mirror_on_config_change) and bool(config_changed))
        )
    )
    if mirror_enabled and not dry_run:
        env = _service_environment(service)
        target_db = env.get("AI_QUANT_DB_PATH")
        source_db = mirror_source or "/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db"

        if target_db and os.path.exists(source_db):
            print(f"Mirroring state from {source_db} to {target_db}...")
            mirror_script = AIQ_ROOT / "tools" / "mirror_live_state.py"
            try:
                subprocess.run(
                    [sys.executable, str(mirror_script), "--source", source_db, "--target", target_db],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                # Read balance from target DB
                con = sqlite3.connect(target_db)
                try:
                    row = con.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1").fetchone()
                    if row:
                        balance = row[0]
                        print(f"Mirrored balance: {balance}. Resetting baseline PnL.")
                        _update_service_env_file(service, "AI_QUANT_NOTIFY_BASELINE_USD", str(balance))

                        # Restart to load mirrored state and refreshed baseline.
                        print(f"Restarting {service} to load mirrored state...")
                        orchestrate_interval_restart(
                            ws_service=str(ws_service),
                            trader_service=str(service),
                            pause_file=pause_file,
                            pause_mode=str(pause_mode or "close_only"),
                            resume_on_success=bool(resume_on_success),
                            verify_sleep_s=float(verify_sleep_s),
                        )
                finally:
                    con.close()
            except Exception as e:
                print(f"Mirroring/Baseline reset failed for {service}: {e}")

    (deploy_dir / "deploy_event.json").write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return deploy_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deploy a config_id to the paper trader safely.")
    ap.add_argument("--config-id", required=True, help="config_id from the factory registry.")
    ap.add_argument("--artifacts-dir", default="artifacts", help="Artifacts root (default: artifacts).")
    ap.add_argument(
        "--yaml-path",
        default=str(AIQ_ROOT / "config" / "strategy_overrides.yaml"),
        help="Target strategy overrides YAML path (default: config/strategy_overrides.yaml).",
    )
    ap.add_argument("--out-dir", default="", help="Deploy artefact output directory (default: artifacts/deployments/paper/...).")
    ap.add_argument("--reason", default="", help="Human reason for this deployment (recorded).")
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
    ap.add_argument(
        "--ws-service",
        default="openclaw-ai-quant-ws-sidecar",
        help="systemd user service name for WS sidecar (default: openclaw-ai-quant-ws-sidecar).",
    )
    ap.add_argument(
        "--pause-file",
        default="",
        help="Optional kill-switch file path to pause trading during restart (requires AI_QUANT_KILL_SWITCH_FILE).",
    )
    ap.add_argument(
        "--pause-mode",
        default="close_only",
        choices=["close_only", "halt_all"],
        help="Pause mode to write into pause file (default: close_only).",
    )
    ap.add_argument(
        "--leave-paused",
        action="store_true",
        help="Do not clear the pause file after a successful restart.",
    )
    ap.add_argument(
        "--verify-sleep-s",
        type=float,
        default=2.0,
        help="Seconds to wait before verifying service health (default: 2).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Write artefacts but do not modify the YAML or restart.")
    ap.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip deployment-time YAML validation (not recommended).",
    )
    ap.add_argument(
        "--mirror-source",
        default="/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine_live.db",
        help="Source DB for state mirroring (default: .../trading_engine_live.db).",
    )
    ap.add_argument(
        "--skip-mirror",
        action="store_true",
        help="Force skip state mirroring.",
    )
    ap.add_argument(
        "--mirror-on-config-change",
        action="store_true",
        help="Mirror live state when the deployed config changed.",
    )
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
        help="Bypass replay-gate release-blocker checks (not recommended).",
    )
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir).expanduser().resolve() if str(args.out_dir).strip() else None
    pause_file = Path(args.pause_file).expanduser().resolve() if str(args.pause_file).strip() else None
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
            raise SystemExit(f"Replay gate blocked paper deployment: {detail}")
    try:
        deploy_paper_config(
            config_id=str(args.config_id),
            artifacts_dir=Path(args.artifacts_dir),
            yaml_path=Path(args.yaml_path),
            out_dir=out_dir,
            reason=str(args.reason),
            restart=str(args.restart),
            service=str(args.service),
            dry_run=bool(args.dry_run),
            validate=not bool(args.no_validate),
            ws_service=str(args.ws_service),
            pause_file=pause_file,
            pause_mode=str(args.pause_mode),
            resume_on_success=not bool(args.leave_paused),
            verify_sleep_s=float(args.verify_sleep_s),
            mirror_source=str(args.mirror_source),
            skip_mirror=bool(args.skip_mirror),
            mirror_on_config_change=bool(args.mirror_on_config_change),
        )
        return 0
    except KeyError as e:
        raise SystemExit(str(e))
    except Exception as e:
        raise SystemExit(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
