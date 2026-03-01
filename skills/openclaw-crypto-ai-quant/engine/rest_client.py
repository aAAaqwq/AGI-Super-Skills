from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .utils import Backoff


INFO_URL = "https://api.hyperliquid.xyz/info"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(float(str(raw).strip()))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(str(raw).strip())
    except Exception:
        return float(default)


@dataclass
class RestResult:
    ok: bool
    data: Any | None
    error: str | None = None
    fetched_at_ms: int | None = None


class HyperliquidRestClient:
    """Minimal HL /info REST client used for fallback.

    This intentionally avoids introducing new dependencies.
    """

    def __init__(self, *, info_url: str = INFO_URL, timeout_s: float = 30.0):
        self._info_url = str(info_url)
        self._timeout_s = float(timeout_s)

    def _post(
        self,
        payload: dict[str, Any],
        *,
        max_retries: int = 3,
        timeout_s: float | None = None,
    ) -> RestResult:
        req = urllib.request.Request(
            self._info_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        effective_timeout = self._timeout_s if timeout_s is None else float(timeout_s)
        # Keep REST fallback responsive in the main loop.
        effective_timeout = max(0.2, min(float(effective_timeout), 30.0))

        backoff = Backoff(base_s=1.0, max_s=15.0, jitter_pct=0.25)
        last_err: str | None = None
        for attempt in range(1, max(1, int(max_retries)) + 1):
            try:
                with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                    raw_body = resp.read()
                data = json.loads(raw_body)
                return RestResult(ok=True, data=data, fetched_at_ms=int(time.time() * 1000))
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {getattr(e, 'code', '?')}: {e}"
                code = int(getattr(e, "code", 0) or 0)
                if 500 <= code < 600 and attempt < max_retries:
                    time.sleep(backoff.delay(attempt))
                    continue
                return RestResult(ok=False, data=None, error=last_err, fetched_at_ms=int(time.time() * 1000))
            except Exception as e:
                last_err = str(e)
                if attempt < max_retries:
                    time.sleep(backoff.delay(attempt))
                    continue
                return RestResult(ok=False, data=None, error=last_err, fetched_at_ms=int(time.time() * 1000))
        return RestResult(ok=False, data=None, error=last_err, fetched_at_ms=int(time.time() * 1000))

    def all_mids(self) -> RestResult:
        """Returns a dict symbol->mid."""
        # Main-loop fallback path: fail fast to avoid long stalls.
        max_retries = _env_int("AI_QUANT_REST_ALL_MIDS_RETRIES", 1)
        max_retries = max(1, min(3, int(max_retries)))
        timeout_s = _env_float("AI_QUANT_REST_ALL_MIDS_TIMEOUT_S", self._timeout_s)
        timeout_s = max(0.2, min(10.0, float(timeout_s)))
        return self._post({"type": "allMids"}, max_retries=max_retries, timeout_s=timeout_s)

    def candle_snapshot(self, *, symbol: str, interval: str, start_ms: int, end_ms: int) -> RestResult:
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": str(symbol).upper(),
                "interval": str(interval),
                "startTime": int(start_ms),
                "endTime": int(end_ms),
            },
        }
        # Candle snapshot is often called as a *fallback* path; keep retries conservative
        # to avoid stalling the main engine loop when a symbol is invalid/unavailable.
        max_retries = _env_int("AI_QUANT_REST_CANDLE_RETRIES", 2)
        max_retries = max(1, min(10, int(max_retries)))
        return self._post(payload, max_retries=max_retries)

    def open_orders(self, *, user: str) -> RestResult:
        """Best-effort fetch open orders for a user address.

        Hyperliquid /info supports multiple payload shapes over time.
        This method uses the commonly supported {type: openOrders, user: ...}.
        """
        payload = {
            "type": "openOrders",
            "user": str(user or "").strip().lower(),
        }
        # Open-order reconcile is a safety/observability path. It must not stall the main loop.
        # Keep retries conservative; tune via env if needed.
        max_retries = _env_int("AI_QUANT_REST_OPEN_ORDERS_RETRIES", 1)
        max_retries = max(1, min(10, int(max_retries)))
        return self._post(payload, max_retries=max_retries)
