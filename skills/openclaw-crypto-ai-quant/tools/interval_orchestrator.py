#!/usr/bin/env python3
"""Interval change orchestration helpers (AQC-705).

Changing the main interval requires a service restart (engine.interval is not hot-reloadable).
This module provides an orchestrated restart flow that:
- (Optionally) pauses trading via a kill-switch file
- restarts WS sidecar first (to resubscribe candles) then the trader service
- verifies services are active
- only unpauses when restarts are healthy; otherwise it leaves the pause in place
"""

from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SYSTEMCTL_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class ServiceResult:
    service: str
    ok: bool
    exit_code: int
    stdout: str
    stderr: str


def _write_pause_file(path: Path, mode: str) -> None:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(mode or "close_only").strip() + "\n", encoding="utf-8")


def _clear_pause_file(path: Path) -> None:
    try:
        Path(path).expanduser().resolve().unlink(missing_ok=True)  # py312
    except TypeError:
        # Python <3.8 compatibility is not required, but keep it safe.
        p = Path(path).expanduser().resolve()
        if p.exists():
            p.unlink()


def _systemctl_restart(service: str) -> ServiceResult:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "restart", str(service)],
            capture_output=True,
            text=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        return ServiceResult(
            service=str(service),
            ok=False,
            exit_code=124,
            stdout=str(exc.stdout or ""),
            stderr=f"systemctl restart timed out after {SYSTEMCTL_TIMEOUT_S:.0f}s",
        )
    return ServiceResult(
        service=str(service),
        ok=int(proc.returncode) == 0,
        exit_code=int(proc.returncode),
        stdout=str(proc.stdout or ""),
        stderr=str(proc.stderr or ""),
    )


def _systemctl_is_active(service: str) -> bool:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", str(service)],
            capture_output=True,
            text=True,
            check=False,
            timeout=SYSTEMCTL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    return int(proc.returncode) == 0


def orchestrate_interval_restart(
    *,
    ws_service: str,
    trader_service: str,
    pause_file: Path | None,
    pause_mode: str,
    resume_on_success: bool,
    verify_sleep_s: float,
) -> list[ServiceResult]:
    """Restart WS sidecar + trader with an optional pause file.

    Returns a list of ServiceResult entries (restart attempts). If a pause_file is provided,
    it is only cleared when all restarts succeed and services are active, and resume_on_success=True.
    """
    results: list[ServiceResult] = []

    if pause_file is not None:
        _write_pause_file(Path(pause_file), str(pause_mode or "close_only"))

    # Restart order matters: bring market data back first.
    for svc in [str(ws_service), str(trader_service)]:
        res = _systemctl_restart(svc)
        results.append(res)
        if not res.ok:
            # Leave pause file in place for safety.
            return results

    time.sleep(float(max(0.0, verify_sleep_s)))
    for svc in [str(ws_service), str(trader_service)]:
        if not _systemctl_is_active(svc):
            results.append(ServiceResult(service=svc, ok=False, exit_code=1, stdout="", stderr="not active"))
            return results

    if pause_file is not None and bool(resume_on_success):
        _clear_pause_file(Path(pause_file))

    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Orchestrate restarts for an interval change (AQC-705).")
    ap.add_argument("--ws-service", default="openclaw-ai-quant-ws-sidecar", help="WS sidecar service name.")
    ap.add_argument("--trader-service", default="openclaw-ai-quant-trader", help="Trader service name.")
    ap.add_argument("--pause-file", default="", help="Optional kill-switch file path to pause trading.")
    ap.add_argument(
        "--pause-mode",
        default="close_only",
        choices=["close_only", "halt_all"],
        help="Pause mode written into the pause file (default: close_only).",
    )
    ap.add_argument(
        "--resume-on-success",
        action="store_true",
        help="Clear pause file after successful restart verification.",
    )
    ap.add_argument(
        "--verify-sleep-s",
        type=float,
        default=2.0,
        help="Seconds to wait before verifying service health (default: 2).",
    )
    args = ap.parse_args(argv)

    pause_file = Path(args.pause_file).expanduser().resolve() if str(args.pause_file).strip() else None
    results = orchestrate_interval_restart(
        ws_service=str(args.ws_service),
        trader_service=str(args.trader_service),
        pause_file=pause_file,
        pause_mode=str(args.pause_mode),
        resume_on_success=bool(args.resume_on_success),
        verify_sleep_s=float(args.verify_sleep_s),
    )

    ok = all(r.ok for r in results)
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(f"[{status}] {r.service} (exit_code={r.exit_code})")
        if (not r.ok) and r.stderr.strip():
            print(r.stderr.strip())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
