import os
import time
import math
import threading
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from dataclasses import dataclass

from hyperliquid.info import Info
from hyperliquid.utils import constants


@dataclass(frozen=True)
class PerpInstrument:
    name: str
    sz_decimals: int
    margin_table_id: int | None
    funding_rate: float = 0.0
    day_ntl_vlm: float = 0.0
    day_base_vlm: float = 0.0
    open_interest: float = 0.0


_CACHE_TTL_S = 60 * 5  # Reduce to 5 mins for funding rates
_cached_at_s: float | None = None
_cached_instruments: dict[str, PerpInstrument] = {}
_cached_margin_tables: dict[int, dict] = {}
_next_refresh_allowed_s: float | None = None
_CACHE_LOCK = threading.RLock()
_CACHE_REFRESH_CV = threading.Condition(_CACHE_LOCK)
_refresh_in_progress = False


def _hl_timeout_s() -> float:
    raw = os.getenv("AI_QUANT_HL_TIMEOUT_S", "10")
    try:
        v = float(raw)
    except Exception:
        v = 10.0
    return float(max(0.5, min(30.0, v)))


def _refresh_cache() -> None:
    global _cached_at_s, _cached_instruments, _cached_margin_tables, _next_refresh_allowed_s, _refresh_in_progress

    with _CACHE_REFRESH_CV:
        now_s = time.time()
        if _cached_at_s is not None and (now_s - _cached_at_s) <= _CACHE_TTL_S:
            return
        if _next_refresh_allowed_s is not None and now_s < _next_refresh_allowed_s:
            return
        while _refresh_in_progress:
            _CACHE_REFRESH_CV.wait(timeout=1.0)
            now_s = time.time()
            if _cached_at_s is not None and (now_s - _cached_at_s) <= _CACHE_TTL_S:
                return
            if _next_refresh_allowed_s is not None and now_s < _next_refresh_allowed_s:
                return
        _refresh_in_progress = True

    now_s = time.time()
    try:
        info = Info(constants.MAINNET_API_URL, skip_ws=True, timeout=_hl_timeout_s())

        # meta_and_asset_ctxs() returns [meta, asset_ctxs]
        # asset_ctxs contains real-time data including funding rates
        data = info.meta_and_asset_ctxs()
        if not data or len(data) < 2:
            return
        meta = data[0]
        asset_ctxs = data[1]

        funding_map: dict[int, float] = {}
        day_ntl_vlm_map: dict[int, float] = {}
        day_base_vlm_map: dict[int, float] = {}
        open_interest_map: dict[int, float] = {}
        for i, ctx in enumerate(asset_ctxs):
            # Index in asset_ctxs matches universe order
            try:
                funding_map[i] = float(ctx.get("funding", 0.0) or 0.0)
            except Exception:
                funding_map[i] = 0.0

            try:
                day_ntl_vlm_map[i] = float(ctx.get("dayNtlVlm", 0.0) or 0.0)
            except Exception:
                day_ntl_vlm_map[i] = 0.0

            try:
                day_base_vlm_map[i] = float(ctx.get("dayBaseVlm", 0.0) or 0.0)
            except Exception:
                day_base_vlm_map[i] = 0.0

            try:
                open_interest_map[i] = float(ctx.get("openInterest", 0.0) or 0.0)
            except Exception:
                open_interest_map[i] = 0.0

        instruments: dict[str, PerpInstrument] = {}
        for i, u in enumerate(meta.get("universe") or []):
            try:
                name = str(u["name"]).upper()
                sz_decimals = int(u["szDecimals"])
            except Exception:
                continue
            margin_table_id = u.get("marginTableId")
            try:
                margin_table_id = int(margin_table_id) if margin_table_id is not None else None
            except Exception:
                margin_table_id = None

            fr = funding_map.get(i, 0.0)
            instruments[name] = PerpInstrument(
                name=name,
                sz_decimals=sz_decimals,
                margin_table_id=margin_table_id,
                funding_rate=fr,
                day_ntl_vlm=day_ntl_vlm_map.get(i, 0.0),
                day_base_vlm=day_base_vlm_map.get(i, 0.0),
                open_interest=open_interest_map.get(i, 0.0),
            )

        margin_tables: dict[int, dict] = {}
        for entry in meta.get("marginTables") or []:
            if isinstance(entry, list) and len(entry) == 2:
                try:
                    table_id = int(entry[0])
                except Exception:
                    continue
                if isinstance(entry[1], dict):
                    margin_tables[table_id] = entry[1]

        with _CACHE_REFRESH_CV:
            _cached_instruments = instruments
            _cached_margin_tables = margin_tables
            _cached_at_s = now_s
            _next_refresh_allowed_s = None
    except Exception as e:
        # Avoid blocking/hammering in hot paths when HL is slow/unreachable.
        import logging as _logging

        _logging.getLogger(__name__).warning("metadata refresh failed: %s", e)
        try:
            cooldown_s = float(os.getenv("AI_QUANT_HL_META_FAIL_COOLDOWN_S", "60"))
        except Exception:
            cooldown_s = 60.0
        with _CACHE_REFRESH_CV:
            _next_refresh_allowed_s = now_s + max(5.0, min(600.0, cooldown_s))
    finally:
        with _CACHE_REFRESH_CV:
            _refresh_in_progress = False
            _CACHE_REFRESH_CV.notify_all()


def _ensure_cache() -> None:
    with _CACHE_LOCK:
        cached_at_s = _cached_at_s
    if cached_at_s is None or (time.time() - cached_at_s) > _CACHE_TTL_S:
        _refresh_cache()


def get_sz_decimals(symbol: str) -> int:
    _ensure_cache()
    sym = (symbol or "").upper()
    with _CACHE_LOCK:
        inst = _cached_instruments.get(sym)
    return int(inst.sz_decimals) if inst else 4


def get_funding_rate(symbol: str) -> float:
    _ensure_cache()
    sym = (symbol or "").upper()
    with _CACHE_LOCK:
        inst = _cached_instruments.get(sym)
    return float(inst.funding_rate) if inst else 0.0


def get_day_notional_volume(symbol: str) -> float:
    """Returns the 24h notional volume (USD) for the perp, if available."""
    _ensure_cache()
    sym = (symbol or "").upper()
    with _CACHE_LOCK:
        inst = _cached_instruments.get(sym)
    return float(inst.day_ntl_vlm) if inst else 0.0


def top_symbols_by_day_notional_volume(n: int, *, min_volume_usd: float = 0.0) -> list[str]:
    """
    Returns the top-N perp symbols by 24h notional volume (dayNtlVlm).
    This is useful for setting a "top 50" universe without maintaining a static list.
    """
    _ensure_cache()
    try:
        n_i = int(n)
    except Exception:
        n_i = 0
    if n_i <= 0:
        return []

    min_v = float(min_volume_usd or 0.0)
    rows: list[tuple[str, float]] = []
    with _CACHE_LOCK:
        rows_iter = list(_cached_instruments.items())

    for sym, inst in rows_iter:
        try:
            v = float(inst.day_ntl_vlm or 0.0)
        except Exception:
            v = 0.0
        if v >= min_v:
            rows.append((sym, v))
    rows.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in rows[:n_i]]


def round_size(symbol: str, size: float) -> float:
    """Rounds DOWN to the allowed size decimals."""
    try:
        size = float(size)
    except Exception:
        return 0.0
    if size <= 0:
        return 0.0
    decimals = get_sz_decimals(symbol)
    try:
        quantum = Decimal("1").scaleb(-int(max(0, decimals)))
        return float(Decimal(str(size)).quantize(quantum, rounding=ROUND_DOWN))
    except (InvalidOperation, ValueError, OverflowError):
        return 0.0


def round_size_up(symbol: str, size: float) -> float:
    """Rounds UP to the allowed size decimals (useful for minimum-notional compliance)."""
    try:
        size = float(size)
    except Exception:
        return 0.0
    if size <= 0:
        return 0.0
    decimals = get_sz_decimals(symbol)
    factor = 10**decimals
    # Protect against float representation errors.
    return math.ceil((size * factor) - 1e-12) / factor


def min_size_for_notional(symbol: str, notional_usd: float, price: float) -> float:
    """
    Returns the minimum size (rounded UP to szDecimals) such that:
      size * price >= notional_usd
    """
    try:
        ntl = float(notional_usd)
        px = float(price)
    except Exception:
        return 0.0
    if ntl <= 0 or px <= 0:
        return 0.0
    return round_size_up(symbol, ntl / px)


def max_leverage(symbol: str, notional_usd: float) -> float | None:
    """Returns the max allowed leverage for the given notional, if metadata is available."""
    _ensure_cache()
    sym = (symbol or "").upper()
    with _CACHE_LOCK:
        inst = _cached_instruments.get(sym)
        if not inst or inst.margin_table_id is None:
            return None
        table = _cached_margin_tables.get(inst.margin_table_id)
    if not table:
        return None

    tiers = table.get("marginTiers") or []
    if not isinstance(tiers, list) or not tiers:
        return None

    try:
        ntl = float(notional_usd)
    except Exception:
        return None

    best = None
    best_lb = None
    for t in tiers:
        if not isinstance(t, dict):
            continue
        try:
            lb = float(t.get("lowerBound"))
            lev = float(t.get("maxLeverage"))
        except Exception:
            continue
        if ntl >= lb and (best_lb is None or lb > best_lb):
            best_lb = lb
            best = lev
    return best
