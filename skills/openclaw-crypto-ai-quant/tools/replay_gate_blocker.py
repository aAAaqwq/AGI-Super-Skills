#!/usr/bin/env python3
"""Helpers for enforcing replay alignment release-blocker status."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any


DEFAULT_BLOCKER_PATH = Path("/tmp/openclaw-ai-quant/replay_gate/release_blocker.json")
DEFAULT_MAX_AGE_MINUTES = float(os.getenv("AI_QUANT_REPLAY_GATE_MAX_AGE_MINUTES", "360") or 360.0)


class ReplayGateViolation(RuntimeError):
    """Raised when release-blocker status is red or stale."""

    def __init__(self, reasons: list[str], status: dict[str, Any]) -> None:
        self.reasons = list(reasons)
        self.status = dict(status)
        super().__init__("; ".join(self.reasons))


def _now_ms() -> int:
    return int(time.time() * 1000.0)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def default_replay_gate_blocker_path() -> Path:
    explicit = str(os.getenv("AI_QUANT_REPLAY_GATE_BLOCKER_FILE", "") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    bundle_root = str(os.getenv("AI_QUANT_REPLAY_GATE_BUNDLE_ROOT", "") or "").strip()
    if bundle_root:
        return (Path(bundle_root).expanduser() / "release_blocker.json").resolve()

    return DEFAULT_BLOCKER_PATH.resolve()


def read_replay_gate_status(
    *,
    blocker_path: Path | None = None,
    max_age_minutes: float | None = None,
) -> dict[str, Any]:
    path = Path(blocker_path).expanduser().resolve() if blocker_path is not None else default_replay_gate_blocker_path()
    ttl_minutes = float(DEFAULT_MAX_AGE_MINUTES if max_age_minutes is None else max_age_minutes)
    reasons: list[str] = []
    payload: dict[str, Any] | None = None
    generated_at_ms: int | None = None
    blocked: bool | None = None

    if not path.exists():
        reasons.append(f"release blocker file not found: {path}")
    else:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            reasons.append(f"failed to parse release blocker file: {exc}")
        else:
            if not isinstance(loaded, dict):
                reasons.append("release blocker file is not a JSON object")
            else:
                payload = loaded
                raw_blocked = loaded.get("blocked")
                if isinstance(raw_blocked, bool):
                    blocked = raw_blocked
                else:
                    reasons.append("release blocker has invalid blocked flag")

                generated_at_ms = _as_int(loaded.get("generated_at_ms"))
                if generated_at_ms is None or generated_at_ms <= 0:
                    reasons.append("release blocker has invalid generated_at_ms")

                if blocked is True:
                    reason_codes = loaded.get("reason_codes")
                    if isinstance(reason_codes, list) and reason_codes:
                        compact = [str(x or "").strip() for x in reason_codes if str(x or "").strip()]
                        if compact:
                            reasons.append(f"release blocker is active ({', '.join(compact)})")
                        else:
                            reasons.append("release blocker is active")
                    else:
                        reasons.append("release blocker is active")

    age_ms: int | None = None
    stale: bool | None = None
    if generated_at_ms is not None:
        age_ms = max(0, int(_now_ms() - generated_at_ms))
        if ttl_minutes > 0:
            stale = age_ms > int(ttl_minutes * 60_000.0)
            if stale:
                reasons.append(f"release blocker is stale (age_ms={age_ms}, max_age_minutes={ttl_minutes:g})")
        else:
            stale = False

    return {
        "ok": len(reasons) == 0,
        "blocker_path": str(path),
        "max_age_minutes": float(ttl_minutes),
        "blocked": blocked,
        "generated_at_ms": generated_at_ms,
        "age_ms": age_ms,
        "stale": stale,
        "reasons": reasons,
        "payload": payload,
    }


def assert_replay_gate_green(
    *,
    blocker_path: Path | None = None,
    max_age_minutes: float | None = None,
) -> dict[str, Any]:
    status = read_replay_gate_status(blocker_path=blocker_path, max_age_minutes=max_age_minutes)
    if not bool(status.get("ok")):
        raise ReplayGateViolation(reasons=list(status.get("reasons") or []), status=status)
    return status
