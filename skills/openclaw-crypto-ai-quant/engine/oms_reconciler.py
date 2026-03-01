from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from .rest_client import HyperliquidRestClient
from .oms import LiveOms
from .utils import now_ms


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name)
        if raw is None:
            return int(default)
        return int(float(str(raw).strip()))
    except Exception:
        return int(default)


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    return default if raw is None else str(raw)


def _json_dumps_safe(obj: Any) -> str | None:
    try:
        return json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str)
    except Exception:
        return None


def _norm_side(side: str | None) -> str | None:
    if side is None:
        return None
    s = str(side).strip().upper()
    if s in {"B", "BUY", "LONG"}:
        return "BUY"
    if s in {"S", "SELL", "SHORT"}:
        return "SELL"
    return s or None


def _safe_float(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int | None = None) -> int | None:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _cloid_matches_prefix(cloid: str | None, prefix: str) -> bool:
    """Return True if `cloid` belongs to our bot based on a configurable prefix.

    Backwards compatibility:
    - Historically this project used human-readable `client_order_id` values like `aiq_...`.
      Hyperliquid's SDK, however, validates cloID as a 16-byte hex string with a `0x` prefix.
    - Today we encode the ASCII prefix (default: `aiq_`) into the first bytes of the cloid.

    Supported prefix formats:
    - Raw string prefix: exact `startswith()` match (e.g. `0x6169715f`)
    - ASCII prefix: decode the cloid hex to bytes and check `bytes.startswith(prefix.encode('ascii'))`
      (e.g. `aiq_`)
    """
    c = str(cloid or "").strip()
    p = str(prefix or "").strip()
    if not c or not p:
        return False

    if c.startswith(p):
        return True

    # ASCII prefix: decode cloid bytes.
    if not p.startswith("0x") and c.startswith("0x") and len(c) >= 4:
        try:
            b = bytes.fromhex(c[2:])
        except Exception:
            return False
        try:
            pb = p.encode("ascii")
        except Exception:
            pb = p.encode("ascii", errors="ignore")
        if not pb:
            return False
        return b.startswith(pb)

    return False


@dataclass(frozen=True)
class OpenOrder:
    symbol: str
    exchange_order_id: str
    client_order_id: str | None
    side: str | None
    price: float | None
    orig_size: float | None
    remaining_size: float | None
    reduce_only: bool
    ts_ms: int | None
    raw: dict[str, Any]


class LiveOmsReconciler:
    """True reconcile loop for live trading.

    What it does:
    - fetches open orders (REST fallback)
    - maps orders to OMS intents via client_order_id/exchange_order_id
    - records an upsert snapshot in oms_open_orders
    - cancels stale orders for our bot prefix
    - updates intent status to CANCELLED / PARTIAL_CANCELLED where appropriate

    This module is intentionally conservative. It does not auto-retry by default.
    """

    def __init__(
        self,
        *,
        oms: LiveOms,
        executor: Any,
        main_address: str,
        rest: HyperliquidRestClient | None = None,
        risk: Any | None = None,
    ):
        self.oms = oms
        self.store = oms.store
        self.executor = executor
        self.main_address = str(main_address or "").strip().lower()
        # REST openOrders is a best-effort safety/observability path. It must not stall the main loop.
        # Keep timeouts low by default; tune via env when needed.
        timeout_s = 3.0
        try:
            timeout_s = float(os.getenv("AI_QUANT_OMS_REST_TIMEOUT_S", "3.0") or 3.0)
        except Exception:
            timeout_s = 3.0
        timeout_s = float(max(0.5, min(30.0, timeout_s)))
        self.rest = rest or HyperliquidRestClient(timeout_s=timeout_s)
        self.risk = risk

        # Scheduling
        self.every_s = float(max(1.0, float(os.getenv("AI_QUANT_OMS_RECONCILE_SECS", "10"))))
        self._last_run_s: float = 0.0

        # Staleness
        self.order_ttl_ms = int(max(2_000, _env_int("AI_QUANT_OMS_STALE_ORDER_MS", 30_000)))
        # For orders we cannot map to an intent but have our prefix.
        self.unknown_order_ttl_ms = int(
            max(self.order_ttl_ms, _env_int("AI_QUANT_OMS_UNKNOWN_STALE_ORDER_MS", 300_000))
        )

        self.manage_prefix = _env_str("AI_QUANT_OMS_CLOID_PREFIX", "aiq_").strip() or "aiq_"
        self.cancel_stale = _env_bool("AI_QUANT_OMS_CANCEL_STALE", True)
        self.cancel_unknown_prefix = _env_bool("AI_QUANT_OMS_CANCEL_UNKNOWN_PREFIX", True)

        # Prune open-order snapshots that haven't been seen for a while.
        self.prune_after_ms = int(max(60_000, _env_int("AI_QUANT_OMS_OPEN_ORDER_PRUNE_MS", 24 * 60 * 60 * 1000)))

    def maybe_run(self, *, trader: Any | None = None) -> None:
        now = time.time()
        if self._last_run_s and (now - self._last_run_s) < self.every_s:
            return
        self._last_run_s = now
        self.run_once(trader=trader)

    def run_once(self, *, trader: Any | None = None) -> None:
        if not self.main_address:
            return

        self.store.ensure()

        now_ms_i = now_ms()

        # 1) Fetch open orders
        open_orders = self._fetch_open_orders()

        # 2) Upsert open order snapshots + cancel stale
        seen_exchange_ids: set[str] = set()
        for oo in open_orders:
            seen_exchange_ids.add(oo.exchange_order_id)
            intent_id = self._match_intent_for_order(oo)

            # Snapshot for observability
            try:
                first_seen = now_ms_i
                try:
                    # If we already have this order in the snapshot table, keep original first_seen.
                    # Best-effort: ignore errors.
                    pass
                except Exception:
                    pass
                self.store.upsert_open_order(
                    exchange_order_id=oo.exchange_order_id,
                    first_seen_ts_ms=first_seen,
                    last_seen_ts_ms=now_ms_i,
                    symbol=oo.symbol,
                    side=oo.side,
                    price=oo.price,
                    orig_size=oo.orig_size,
                    remaining_size=oo.remaining_size,
                    reduce_only=bool(oo.reduce_only),
                    client_order_id=oo.client_order_id,
                    intent_id=intent_id,
                    raw_json=_json_dumps_safe(oo.raw),
                )
            except Exception:
                pass

            # Cancel logic
            if not self.cancel_stale:
                continue

            # If kill-switch is on, cancel bot entry orders immediately.
            kill_mode = None
            try:
                kill_mode = getattr(self.risk, "kill_mode", None) if self.risk is not None else None
            except Exception:
                kill_mode = None

            if kill_mode in {"close_only", "halt_all"}:
                if self._should_cancel_under_kill_switch(
                    kill_mode=str(kill_mode),
                    intent_id=intent_id,
                    client_order_id=oo.client_order_id,
                    reduce_only=bool(oo.reduce_only),
                ):
                    self._cancel_order(
                        oo,
                        intent_id=intent_id,
                        trader=trader,
                        reason_kind="CANCEL_KILL_SWITCH",
                        audit_ok="OMS_CANCEL_KILL_SWITCH",
                        audit_fail="OMS_CANCEL_KILL_SWITCH_FAIL",
                    )
                    continue

            stale_ms = self._stale_ms_for_order(oo, intent_id=intent_id)
            if stale_ms is None:
                continue

            # Only manage our bot orders by default.
            is_ours = False
            if oo.client_order_id and _cloid_matches_prefix(str(oo.client_order_id), self.manage_prefix):
                is_ours = True
            if intent_id is not None:
                is_ours = True

            if not is_ours:
                continue

            ttl = self.order_ttl_ms if intent_id is not None else self.unknown_order_ttl_ms
            if stale_ms < int(ttl):
                continue

            # For unknown-but-ours, require explicit flag.
            if intent_id is None and (not self.cancel_unknown_prefix):
                continue

            self._cancel_order(oo, intent_id=intent_id, trader=trader)

        # 3) Prune old open-order snapshots (seen table is upsert, but we still prune long-unseen rows)
        try:
            cutoff = now_ms_i - int(self.prune_after_ms)
            self.store.prune_open_orders(older_than_ms=int(cutoff))
        except Exception:
            pass

        # 4) Intent status reconciliation (fill-based)
        try:
            self._reconcile_intent_statuses(trader=trader)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fetch open orders
    # ------------------------------------------------------------------

    def _fetch_open_orders(self) -> list[OpenOrder]:
        # Prefer executor method if present.
        raw = None
        for name in ("get_open_orders", "open_orders", "list_open_orders"):
            fn = getattr(self.executor, name, None)
            if callable(fn):
                try:
                    raw = fn()  # type: ignore[misc]
                    break
                except TypeError:
                    try:
                        raw = fn(self.main_address)  # type: ignore[misc]
                        break
                    except Exception:
                        raw = None
                except Exception:
                    raw = None

        if raw is None:
            try:
                res = self.rest.open_orders(user=self.main_address)
                raw = res.data if res.ok else None
            except Exception:
                raw = None

        return self._normalize_open_orders(raw)

    def _normalize_open_orders(self, raw: Any) -> list[OpenOrder]:
        items: list[dict[str, Any]] = []

        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, dict):
                    items.append(x)

        if isinstance(raw, dict):
            # Common shapes:
            # - {"orders": [...]} or {"openOrders": [...]}
            for k in ("orders", "openOrders", "open_orders"):
                v = raw.get(k)
                if isinstance(v, list):
                    for x in v:
                        if isinstance(x, dict):
                            items.append(x)
                    break

        out: list[OpenOrder] = []

        for o in items:
            sym = str(o.get("coin") or o.get("symbol") or "").strip().upper()
            if not sym:
                continue

            oid = o.get("oid")
            if oid is None:
                oid = o.get("orderId")
            if oid is None:
                oid = o.get("id")
            if oid is None:
                # Cannot manage without an id
                continue
            exch_id = str(oid)

            cloid = None
            for k in ("cloid", "clientOrderId", "client_order_id", "clientOid"):
                v = o.get(k)
                if isinstance(v, str) and v.strip():
                    cloid = v.strip()
                    break

            side = _norm_side(o.get("side") or o.get("dir"))

            # Some payloads include a boolean isBuy.
            if side is None:
                try:
                    if o.get("isBuy") is True:
                        side = "BUY"
                    elif o.get("isBuy") is False:
                        side = "SELL"
                except Exception:
                    pass

            price = _safe_float(o.get("limitPx") or o.get("limit_px") or o.get("price"), None)
            orig_size = _safe_float(o.get("origSz") or o.get("orig_size") or o.get("sz") or o.get("size"), None)
            rem_size = _safe_float(o.get("remainingSz") or o.get("remaining_size") or o.get("remaining"), None)
            reduce_only = bool(o.get("reduceOnly") or o.get("reduce_only") or False)

            ts_ms = None
            for k in ("timestamp", "time", "t", "ts", "createdAt", "created_at", "timestampMs"):
                v = o.get(k)
                iv = _safe_int(v, None)
                if iv is None:
                    continue
                # Heuristic: seconds vs ms
                if iv < 10_000_000_000:
                    iv = int(iv * 1000)
                ts_ms = int(iv)
                break

            out.append(
                OpenOrder(
                    symbol=sym,
                    exchange_order_id=exch_id,
                    client_order_id=cloid,
                    side=side,
                    price=price,
                    orig_size=orig_size,
                    remaining_size=rem_size,
                    reduce_only=reduce_only,
                    ts_ms=ts_ms,
                    raw=o,
                )
            )

        return out

    # ------------------------------------------------------------------
    # Matching + stale + cancel
    # ------------------------------------------------------------------

    def _match_intent_for_order(self, oo: OpenOrder) -> str | None:
        # Client order id is the best join key.
        if oo.client_order_id:
            try:
                intent = self.store.find_intent_by_client_order_id(str(oo.client_order_id))
                if intent:
                    return intent
            except Exception:
                pass

        # Exchange order id is next.
        try:
            intent = self.store.find_intent_by_exchange_order_id(str(oo.exchange_order_id))
            if intent:
                return intent
        except Exception:
            pass

        return None

    def _should_cancel_under_kill_switch(
        self,
        *,
        kill_mode: str,
        intent_id: str | None,
        client_order_id: str | None,
        reduce_only: bool,
    ) -> bool:
        """Decide whether to cancel an open order immediately when kill-switch is engaged.

        - halt_all: cancel all bot orders.
        - close_only: cancel entry orders (OPEN/ADD) and any unknown non-reduce-only bot orders.
        """

        km = str(kill_mode or "").strip().lower()
        if km not in {"close_only", "halt_all"}:
            return False

        cloid = str(client_order_id or "").strip()
        is_ours = False
        if cloid and _cloid_matches_prefix(cloid, self.manage_prefix):
            is_ours = True
        if intent_id is not None:
            is_ours = True
        if not is_ours:
            return False

        if km == "halt_all":
            return True

        # close_only
        if reduce_only:
            return False

        if intent_id is None:
            # Unknown bot order: if it's not reduce-only, cancel.
            return True

        try:
            fields = self.store.get_intent_fields(intent_id) or {}
            action = str(fields.get("action") or "").upper()
            if action in {"OPEN", "ADD"}:
                return True
            if action in {"CLOSE", "REDUCE"}:
                return False
        except Exception:
            pass

        # Default: unknown action but non-reduce-only. Cancel under close-only.
        return True

    def _stale_ms_for_order(self, oo: OpenOrder, *, intent_id: str | None) -> int | None:
        now_i = now_ms()

        if oo.ts_ms is not None and oo.ts_ms > 0:
            return int(now_i - int(oo.ts_ms))

        # Fallback to intent sent timestamp.
        if intent_id:
            try:
                fields = self.store.get_intent_fields(intent_id) or {}
                sent = _safe_int(fields.get("sent_ts_ms"), None)
                if sent is not None and sent > 0:
                    return int(now_i - int(sent))
            except Exception:
                pass

        return None

    def _cancel_order(
        self,
        oo: OpenOrder,
        *,
        intent_id: str | None,
        trader: Any | None,
        reason_kind: str = "CANCEL_STALE",
        audit_ok: str = "OMS_CANCEL_STALE_ORDER",
        audit_fail: str = "OMS_CANCEL_STALE_ORDER_FAIL",
    ) -> None:
        sym = oo.symbol
        now_i = now_ms()

        # Rate limit cancels through RiskManager if present.
        if self.risk is not None:
            try:
                dec = self.risk.allow_cancel(symbol=sym, exchange_order_id=oo.exchange_order_id)
                if not getattr(dec, "allowed", False):
                    self.store.insert_reconcile_event(
                        ts_ms=now_i,
                        kind=f"{str(reason_kind)}_BLOCKED",
                        symbol=sym,
                        intent_id=intent_id,
                        client_order_id=oo.client_order_id,
                        exchange_order_id=oo.exchange_order_id,
                        result=str(getattr(dec, "reason", "blocked")),
                        detail_json=_json_dumps_safe({"side": oo.side, "reduce_only": oo.reduce_only}),
                    )
                    return
            except Exception:
                pass

        ok, why = self._cancel_exchange_order(
            symbol=sym, exchange_order_id=oo.exchange_order_id, client_order_id=oo.client_order_id
        )

        # Audit + DB
        kind = f"{str(reason_kind)}_OK" if ok else f"{str(reason_kind)}_FAIL"
        try:
            self.store.insert_reconcile_event(
                ts_ms=now_i,
                kind=kind,
                symbol=sym,
                intent_id=intent_id,
                client_order_id=oo.client_order_id,
                exchange_order_id=oo.exchange_order_id,
                result=str(why or ("ok" if ok else "fail")),
                detail_json=_json_dumps_safe({"side": oo.side, "reduce_only": oo.reduce_only, "raw": oo.raw}),
            )
        except Exception:
            pass

        try:
            import strategy.mei_alpha_v1 as mei_alpha_v1

            mei_alpha_v1.log_audit_event(
                sym,
                str(audit_ok) if ok else str(audit_fail),
                level="warn" if not ok else "info",
                data={
                    "exchange_order_id": oo.exchange_order_id,
                    "client_order_id": oo.client_order_id,
                    "intent_id": intent_id,
                    "why": why,
                },
            )
        except Exception:
            pass

        if not ok:
            return

        # If we cancelled a known intent, update status.
        if intent_id:
            try:
                fields = self.store.get_intent_fields(intent_id) or {}
                action = str(fields.get("action") or "").upper()
                req_sz = _safe_float(fields.get("requested_size"), None)
                filled = float(self.store.sum_filled_size(intent_id) or 0.0)
                status = "CANCELLED"
                if req_sz is not None and req_sz > 0 and filled > 0:
                    status = "PARTIAL_CANCELLED" if filled < (req_sz * 0.999) else "FILLED"
                self.store.update_intent(
                    intent_id, status=status, last_error=f"{str(reason_kind).lower()}:{oo.exchange_order_id}"
                )

                # If we cancelled a full close order, clear the close-spam backoff so the strategy can reattempt.
                if trader is not None and action == "CLOSE":
                    try:
                        d = getattr(trader, "_last_full_close_sent_at_s", None)
                        if isinstance(d, dict):
                            d.pop(sym, None)
                    except Exception:
                        pass
            except Exception:
                pass

    def _cancel_exchange_order(
        self, *, symbol: str, exchange_order_id: str, client_order_id: str | None
    ) -> tuple[bool, str]:
        """Best-effort cancel using whatever executor API is available."""
        oid = str(exchange_order_id)

        # Try a variety of method names/signatures.
        candidates: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        # cancel_order
        candidates.append(("cancel_order", (oid,), {}))
        candidates.append(("cancel_order", (symbol, oid), {}))
        candidates.append(("cancel_order", (), {"symbol": symbol, "oid": oid}))
        candidates.append(("cancel_order", (), {"coin": symbol, "oid": oid}))
        candidates.append(("cancel_order", (), {"exchange_order_id": oid}))
        candidates.append(("cancel_order", (), {"order_id": oid}))
        if client_order_id:
            candidates.append(("cancel_order", (), {"cloid": client_order_id}))
            candidates.append(("cancel_order", (client_order_id,), {}))

        # cancel
        candidates.append(("cancel", (oid,), {}))
        candidates.append(("cancel", (symbol, oid), {}))
        candidates.append(("cancel", (), {"symbol": symbol, "oid": oid}))
        if client_order_id:
            candidates.append(("cancel", (), {"cloid": client_order_id}))

        # cancel_orders (batch)
        candidates.append(("cancel_orders", ([oid],), {}))
        candidates.append(("cancel_orders", ([{"coin": symbol, "oid": oid}],), {}))

        last_err = "no_method"

        for name, args, kwargs in candidates:
            fn = getattr(self.executor, name, None)
            if not callable(fn):
                continue
            try:
                res = fn(*args, **kwargs)
                if isinstance(res, dict):
                    # Common shapes: {"status": "ok"} or {"success": true}
                    if res.get("status") == "ok" or res.get("success") is True:
                        return True, "ok"
                if res is True:
                    return True, "ok"
                if res:
                    return True, "truthy"
                last_err = "falsey"
            except TypeError as e:
                last_err = f"type_error:{e}"
                continue
            except Exception as e:
                last_err = f"error:{e}"
                continue

        return False, last_err

    # ------------------------------------------------------------------
    # Intent status reconciliation
    # ------------------------------------------------------------------

    def _reconcile_intent_statuses(self, *, trader: Any | None) -> None:
        # Basic fill-based reconciliation. This keeps intent statuses tidy.
        intents = self.store.list_active_intents(statuses=("SENT", "PARTIAL"), limit=5000)
        if not intents:
            return

        for it in intents:
            try:
                intent_id = str(it.get("intent_id"))
                action = str(it.get("action") or "").upper()
                req_sz = _safe_float(it.get("requested_size"), None)
                filled = float(self.store.sum_filled_size(intent_id) or 0.0)

                if action == "CLOSE":
                    # If position no longer exists, mark filled.
                    if trader is not None:
                        try:
                            pos = (getattr(trader, "positions", {}) or {}).get(str(it.get("symbol") or "").upper())
                            if not pos:
                                self.store.update_intent(intent_id, status="FILLED")
                                continue
                        except Exception:
                            pass

                if req_sz is not None and req_sz > 0:
                    if filled >= (req_sz * 0.999):
                        self.store.update_intent(intent_id, status="FILLED")
                    elif filled > 0:
                        self.store.update_intent(intent_id, status="PARTIAL")
            except Exception:
                continue
