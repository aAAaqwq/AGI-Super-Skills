from __future__ import annotations

import datetime
import math
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


MIN_ORDERS_PER_MIN = 1.0
MAX_ORDERS_PER_MIN = 1000.0
MIN_SLIPPAGE_WINDOW_FILLS = 1
MAX_SLIPPAGE_WINDOW_FILLS = 1000
MIN_NOTIONAL_WINDOW_S = 10.0
DEFAULT_NOTIONAL_WINDOW_S = 60.0
MAX_NOTIONAL_WINDOW_S = 3600.0
MAX_ORDER_GAP_MS = 60000.0
SECONDS_PER_MINUTE = 60.0
MS_PER_SECOND = 1000.0
BASIS_POINTS_PER_UNIT = 10000.0


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    return default if raw is None else str(raw)


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name)
        if raw is None:
            return int(default)
        return int(float(str(raw).strip()))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        raw = os.getenv(name)
        if raw is None:
            return float(default)
        v = float(str(raw).strip())
        if not math.isfinite(v):
            return float(default)
        return v
    except Exception:
        return float(default)


class TokenBucket:
    """Simple token bucket rate limiter.

    - capacity: maximum tokens
    - refill_per_s: tokens added per second
    """

    def __init__(self, *, capacity: float, refill_per_s: float):
        self.capacity = float(max(0.0, capacity))
        self.refill_per_s = float(max(0.0, refill_per_s))
        self._tokens = float(self.capacity)
        self._last_s = time.monotonic()
        self._lock = threading.Lock()

    def _refill_unlocked(self, now: float) -> None:
        dt = max(0.0, now - self._last_s)
        self._last_s = float(now)
        if dt <= 0 or self.refill_per_s <= 0:
            return
        self._tokens = min(self.capacity, self._tokens + (dt * self.refill_per_s))

    def _refill(self) -> None:
        with self._lock:
            self._refill_unlocked(time.monotonic())

    def allow(self, *, cost: float = 1.0) -> bool:
        c = float(max(0.0, cost))
        with self._lock:
            self._refill_unlocked(time.monotonic())
            if self._tokens >= c:
                self._tokens -= c
                return True
            return False


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    kill_mode: str | None = None


class RiskManager:
    """Production guardrails: kill-switch + rate limiting + basic circuit breakers.

    Design goals:
    - Never throw in trading path.
    - Default behaviour is conservative but not annoying.
    - Kill-switch is close-only by default: it blocks OPEN/ADD but allows CLOSE/REDUCE.
    """

    def __init__(self):
        # Kill switch
        self._kill_mode: str = "off"  # off | close_only | halt_all
        self._kill_reason: str | None = None
        self._kill_since_s: float | None = None

        self._kill_file = _env_str("AI_QUANT_KILL_SWITCH_FILE", "")
        self._kill_env = _env_str("AI_QUANT_KILL_SWITCH", "").strip()
        self._kill_mode_env = _env_str("AI_QUANT_KILL_SWITCH_MODE", "close_only").strip().lower()

        # Rate limits (entry orders)
        entry_per_min = float(
            min(MAX_ORDERS_PER_MIN, max(MIN_ORDERS_PER_MIN, _env_float("AI_QUANT_RISK_MAX_ENTRY_ORDERS_PER_MIN", 30.0)))
        )
        self._entry_bucket = TokenBucket(capacity=entry_per_min, refill_per_s=entry_per_min / SECONDS_PER_MINUTE)

        entry_sym_per_min = float(
            min(
                MAX_ORDERS_PER_MIN,
                max(MIN_ORDERS_PER_MIN, _env_float("AI_QUANT_RISK_MAX_ENTRY_ORDERS_PER_MIN_PER_SYMBOL", 6.0)),
            )
        )
        self._entry_symbol_per_min = float(entry_sym_per_min)
        self._entry_symbol_events: dict[str, deque[float]] = defaultdict(deque)

        # Rate limits (exit orders)
        exit_per_min = float(
            min(MAX_ORDERS_PER_MIN, max(MIN_ORDERS_PER_MIN, _env_float("AI_QUANT_RISK_MAX_EXIT_ORDERS_PER_MIN", 120.0)))
        )
        self._exit_bucket = TokenBucket(capacity=exit_per_min, refill_per_s=exit_per_min / SECONDS_PER_MINUTE)

        # Cancels
        cancel_per_min = float(
            min(MAX_ORDERS_PER_MIN, max(MIN_ORDERS_PER_MIN, _env_float("AI_QUANT_RISK_MAX_CANCELS_PER_MIN", 120.0)))
        )
        self._cancel_bucket = TokenBucket(capacity=cancel_per_min, refill_per_s=cancel_per_min / SECONDS_PER_MINUTE)

        # Notional throttle (entry only by default)
        self._notional_window_s = float(
            max(
                MIN_NOTIONAL_WINDOW_S,
                min(MAX_NOTIONAL_WINDOW_S, _env_float("AI_QUANT_RISK_NOTIONAL_WINDOW_S", DEFAULT_NOTIONAL_WINDOW_S)),
            )
        )
        self._max_notional_per_window = float(max(0.0, _env_float("AI_QUANT_RISK_MAX_NOTIONAL_PER_WINDOW_USD", 0.0)))
        self._notional_events: deque[tuple[float, float]] = deque()  # (ts_s, notional)

        # Min spacing between orders (global)
        # Default is disabled (0) to avoid surprising behaviour changes; enable explicitly via env.
        raw_gap = os.getenv("AI_QUANT_RISK_MIN_ORDER_GAP_MS")
        if raw_gap is None:
            self._min_order_gap_ms = 0
        else:
            try:
                self._min_order_gap_ms = int(max(0.0, min(MAX_ORDER_GAP_MS, float(str(raw_gap).strip()))))
            except Exception:
                self._min_order_gap_ms = 0
        self._last_order_ts_ms: int | None = None

        # Drawdown kill-switch
        # NOTE: This value can be sourced from YAML (preferred) or env. It is refreshed periodically
        # in refresh() so operators can tune risk controls without code changes.
        self._max_drawdown_pct = float(max(0.0, min(100.0, _env_float("AI_QUANT_RISK_MAX_DRAWDOWN_PCT", 0.0))))
        # High-water mark for drawdown checks; intentionally reset on explicit resume and UTC day rollover.
        self._equity_peak: float | None = None
        self._drawdown_reduce_policy: str = "none"  # none | close_all

        # Daily realised PnL kill-switch (UTC day).
        self._max_daily_loss_usd = float(max(0.0, _env_float("AI_QUANT_RISK_MAX_DAILY_LOSS_USD", 0.0)))
        self._daily_utc_day: str | None = None
        self._daily_realised_pnl_usd: float = 0.0
        self._daily_fees_usd: float = 0.0
        self._drawdown_peak_utc_day: str | None = None

        # Slippage anomaly guard (entry fills). Uses median of recent fills vs mid/BBO.
        self._slippage_guard_enabled = _env_bool("AI_QUANT_RISK_SLIPPAGE_GUARD_ENABLED", False)
        self._slippage_guard_window_fills = int(
            max(
                MIN_SLIPPAGE_WINDOW_FILLS,
                min(MAX_SLIPPAGE_WINDOW_FILLS, _env_int("AI_QUANT_RISK_SLIPPAGE_GUARD_WINDOW_FILLS", 20)),
            )
        )
        self._slippage_guard_max_median_bps = float(
            max(0.0, _env_float("AI_QUANT_RISK_SLIPPAGE_GUARD_MAX_MEDIAN_BPS", 0.0))
        )
        self._slippage_bps: deque[float] = deque()

        # Exposure concentration limit (alts bucket).
        self._exposure_enabled = _env_bool("AI_QUANT_RISK_EXPOSURE_ENABLED", False)
        self._exposure_alts_max_longs = int(max(0, _env_int("AI_QUANT_RISK_EXPOSURE_ALTS_MAX_LONGS", 0)))
        self._exposure_alts_max_shorts = int(max(0, _env_int("AI_QUANT_RISK_EXPOSURE_ALTS_MAX_SHORTS", 0)))
        self._exposure_exclude_symbols: set[str] = {"BTC"}

        # Portfolio heat limit (risk budget).
        self._heat_enabled = _env_bool("AI_QUANT_RISK_HEAT_ENABLED", False)
        self._heat_max_pct = float(max(0.0, _env_float("AI_QUANT_RISK_HEAT_MAX_PCT", 0.0)))
        self._heat_sl_atr_mult = float(max(0.0, min(100.0, _env_float("AI_QUANT_RISK_HEAT_SL_ATR_MULT", 1.5))))
        self._heat_fallback_atr_pct = float(
            max(0.0, min(1.0, _env_float("AI_QUANT_RISK_HEAT_FALLBACK_ATR_PCT", 0.005)))
        )

        # Performance degradation soft stop (rolling PF/WR/Sharpe from realised exits).
        self._perf_stop_enabled = _env_bool("AI_QUANT_RISK_PERF_STOP_ENABLED", False)
        self._perf_stop_window_trades = int(max(0, _env_int("AI_QUANT_RISK_PERF_STOP_WINDOW_TRADES", 0)))
        self._perf_stop_window_s = float(max(0.0, _env_float("AI_QUANT_RISK_PERF_STOP_WINDOW_MINUTES", 0.0))) * 60.0
        self._perf_stop_min_trades = int(max(0, _env_int("AI_QUANT_RISK_PERF_STOP_MIN_TRADES", 0)))
        self._perf_stop_min_pf = float(max(0.0, _env_float("AI_QUANT_RISK_PERF_STOP_MIN_PF", 0.0)))
        self._perf_stop_min_wr = float(max(0.0, _env_float("AI_QUANT_RISK_PERF_STOP_MIN_WR", 0.0)))
        self._perf_stop_min_sharpe: float | None = None
        self._perf_stop_kill_mode = _env_str("AI_QUANT_RISK_PERF_STOP_KILL_MODE", "close_only").strip().lower()
        if self._perf_stop_kill_mode not in {"close_only", "halt_all"}:
            self._perf_stop_kill_mode = "close_only"
        self._perf_trades: deque[tuple[float, float]] = deque()  # (ts_s, net_pnl_usd)

        # Diagnostics
        self._blocked_counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def kill(self, *, mode: str = "close_only", reason: str = "manual") -> None:
        m = str(mode or "close_only").strip().lower()
        if m not in {"close_only", "halt_all"}:
            m = "close_only"
        r = str(reason or "manual")
        # Idempotent: avoid resetting kill_since_s on every refresh loop when the reason is stable
        # (e.g. kill file present, drawdown still breached).
        if self._kill_mode == m and self._kill_reason == r and self._kill_since_s is not None:
            return
        self._kill_mode = m
        self._kill_reason = r
        self._kill_since_s = time.time()

    def clear_kill(self, *, reason: str = "manual_clear") -> None:
        # Reset any cached state so we do not immediately re-trigger on stale peaks once the
        # operator explicitly resumes.
        self._equity_peak = None
        self._drawdown_peak_utc_day = None
        self._daily_utc_day = None
        self._daily_realised_pnl_usd = 0.0
        self._daily_fees_usd = 0.0
        self._slippage_bps.clear()
        self._perf_trades.clear()
        self._kill_mode = "off"
        self._kill_reason = str(reason or "manual_clear")
        self._kill_since_s = None

    @property
    def kill_mode(self) -> str:
        return self._kill_mode

    @property
    def kill_reason(self) -> str | None:
        return self._kill_reason

    @property
    def kill_since_s(self) -> float | None:
        return self._kill_since_s

    @property
    def drawdown_reduce_policy(self) -> str:
        return self._drawdown_reduce_policy

    def slippage_guard_stats(self) -> dict[str, Any]:
        """Best-effort slippage guard snapshot for monitoring/metrics."""
        try:
            vals = list(self._slippage_bps)
            n = int(len(vals))
            last = float(vals[-1]) if n > 0 else None
            median = None
            if n > 0:
                s = sorted(float(x) for x in vals)
                mid_i = n // 2
                if n % 2 == 1:
                    median = float(s[mid_i])
                else:
                    median = float((s[mid_i - 1] + s[mid_i]) / 2.0)
            return {
                "enabled": bool(self._slippage_guard_enabled),
                "n": int(n),
                "window_fills": int(self._slippage_guard_window_fills),
                "last_bps": last,
                "median_bps": median,
                "threshold_median_bps": float(self._slippage_guard_max_median_bps),
            }
        except Exception:
            return {
                "enabled": bool(getattr(self, "_slippage_guard_enabled", False)),
                "n": 0,
                "window_fills": int(getattr(self, "_slippage_guard_window_fills", 0) or 0),
                "last_bps": None,
                "median_bps": None,
                "threshold_median_bps": float(getattr(self, "_slippage_guard_max_median_bps", 0.0) or 0.0),
            }

    def refresh(self, *, trader: Any | None = None) -> None:
        """Call periodically (for example every 5-10s) to re-evaluate kill conditions."""
        try:
            self._refresh_risk_config()
        except Exception:
            pass

        try:
            self._refresh_manual_kill()
        except Exception:
            pass

        try:
            self._refresh_drawdown(trader)
        except Exception:
            pass

    def note_fill(
        self,
        *,
        ts_ms: int,
        symbol: str,
        action: str,
        pnl_usd: float,
        fee_usd: float,
        fill_price: float | None = None,
        side: str | None = None,
        ref_mid: float | None = None,
        ref_bid: float | None = None,
        ref_ask: float | None = None,
    ) -> None:
        """Update rolling risk state based on a newly-ingested live fill.

        This is designed to be called only for NEW fills (after DB dedupe), and must never throw.
        """
        try:
            self._refresh_daily_loss(ts_ms=ts_ms, symbol=symbol, action=action, pnl_usd=pnl_usd, fee_usd=fee_usd)
        except Exception:
            pass
        try:
            self._refresh_slippage_guard(
                ts_ms=ts_ms,
                symbol=symbol,
                action=action,
                fill_price=fill_price,
                side=side,
                ref_mid=ref_mid,
                ref_bid=ref_bid,
                ref_ask=ref_ask,
            )
        except Exception:
            pass
        try:
            self._refresh_perf_stop(ts_ms=ts_ms, symbol=symbol, action=action, pnl_usd=pnl_usd, fee_usd=fee_usd)
        except Exception:
            pass

    def allow_order(
        self,
        *,
        symbol: str,
        action: str,
        side: str,
        notional_usd: float,
        leverage: float | None,
        equity_usd: float | None = None,
        entry_price: float | None = None,
        entry_atr: float | None = None,
        sl_atr_mult: float | None = None,
        positions: dict[str, Any] | None = None,
        intent_id: str | None = None,
        reduce_risk: bool = False,
    ) -> RiskDecision:
        """Decide whether an order is allowed.

        reduce_risk=True is used for CLOSE/REDUCE. It bypasses some entry-only throttles.
        """
        sym = str(symbol or "").strip().upper()
        ac = str(action or "").strip().upper()

        # Kill switch behaviour.
        if self._kill_mode == "halt_all":
            return self._block("halt_all", sym=sym, action=ac, intent_id=intent_id)
        if self._kill_mode == "close_only" and (not reduce_risk) and ac in {"OPEN", "ADD"}:
            return self._block("close_only", sym=sym, action=ac, intent_id=intent_id)

        # Order spacing.
        if self._min_order_gap_ms > 0:
            now_ms = int(time.time() * 1000)
            last = self._last_order_ts_ms
            if last is not None and (now_ms - int(last)) < int(self._min_order_gap_ms):
                return self._block("min_order_gap", sym=sym, action=ac, intent_id=intent_id)

        # Entry throttles.
        if (not reduce_risk) and ac in {"OPEN", "ADD"}:
            # Exposure concentration: cap alt longs/shorts. Best-effort; if we cannot parse positions,
            # fail open (do not block trading).
            try:
                if self._exposure_enabled and (self._exposure_alts_max_longs > 0 or self._exposure_alts_max_shorts > 0):
                    if positions is not None:
                        sym_u = str(sym or "").strip().upper()
                        pos_map = dict(positions or {})
                        pos_syms = {str(k or "").strip().upper() for k in pos_map.keys() if str(k or "").strip()}
                        if sym_u and sym_u not in self._exposure_exclude_symbols and sym_u not in pos_syms:
                            sd = str(side or "").strip().upper()
                            want = "LONG" if sd == "BUY" else ("SHORT" if sd == "SELL" else "")

                            def _pos_dir(p: Any) -> str:
                                if not isinstance(p, dict):
                                    return ""
                                t = str(p.get("type") or p.get("pos_type") or "").strip().upper()
                                if t in {"LONG", "SHORT"}:
                                    return t
                                try:
                                    sz = float(p.get("size") or 0.0)
                                except Exception:
                                    sz = 0.0
                                if sz > 0:
                                    return "LONG"
                                if sz < 0:
                                    return "SHORT"
                                return ""

                            longs = 0
                            shorts = 0
                            for s0, p0 in pos_map.items():
                                s_u = str(s0 or "").strip().upper()
                                if not s_u or s_u in self._exposure_exclude_symbols:
                                    continue
                                d = _pos_dir(p0)
                                if d == "LONG":
                                    longs += 1
                                elif d == "SHORT":
                                    shorts += 1

                            if (
                                want == "LONG"
                                and self._exposure_alts_max_longs > 0
                                and longs >= self._exposure_alts_max_longs
                            ):
                                return self._block("exposure_alts_longs", sym=sym_u, action=ac, intent_id=intent_id)
                            if (
                                want == "SHORT"
                                and self._exposure_alts_max_shorts > 0
                                and shorts >= self._exposure_alts_max_shorts
                            ):
                                return self._block("exposure_alts_shorts", sym=sym_u, action=ac, intent_id=intent_id)
            except Exception:
                pass

            # Portfolio heat limit: cap total open risk (based on stop distance) as % of equity.
            # Best-effort; if we cannot compute a reasonable estimate, fail open (do not block trading).
            try:
                if self._heat_enabled and self._heat_max_pct > 0 and positions is not None:
                    eq = float(equity_usd or 0.0)
                    if eq > 0:
                        sl_mult = float(sl_atr_mult if sl_atr_mult is not None else self._heat_sl_atr_mult)
                        if sl_mult <= 0:
                            sl_mult = float(self._heat_sl_atr_mult or 1.5)
                        fallback_atr_pct = float(self._heat_fallback_atr_pct or 0.0)

                        heat_usd = self._portfolio_heat_usd(
                            positions=dict(positions or {}),
                            sl_atr_mult=sl_mult,
                            fallback_atr_pct=fallback_atr_pct,
                        )

                        add_usd = self._order_heat_usd_est(
                            side=str(side or ""),
                            notional_usd=float(notional_usd or 0.0),
                            entry_price=entry_price,
                            entry_atr=entry_atr,
                            sl_atr_mult=sl_mult,
                            fallback_atr_pct=fallback_atr_pct,
                        )

                        heat_pct = (float(heat_usd) / eq) * 100.0 if heat_usd > 0 else 0.0
                        add_pct = (float(add_usd) / eq) * 100.0 if add_usd > 0 else 0.0
                        total_pct = float(heat_pct + add_pct)

                        if total_pct > float(self._heat_max_pct):
                            self._audit(
                                symbol=sym or "SYSTEM",
                                event="RISK_BLOCK_HEAT",
                                level="warn",
                                data={
                                    "heat_pct": float(heat_pct),
                                    "heat_add_pct_est": float(add_pct),
                                    "heat_total_pct_est": float(total_pct),
                                    "threshold_pct": float(self._heat_max_pct),
                                    "equity_usd": float(eq),
                                },
                            )
                            return self._block("portfolio_heat", sym=sym, action=ac, intent_id=intent_id)
            except Exception:
                pass

            if not self._entry_bucket.allow(cost=1.0):
                return self._block("entry_rate", sym=sym, action=ac, intent_id=intent_id)
            if not self._allow_symbol_event(sym=sym, is_entry=True):
                return self._block("entry_rate_symbol", sym=sym, action=ac, intent_id=intent_id)
            if self._max_notional_per_window > 0:
                if not self._allow_notional(float(notional_usd or 0.0)):
                    return self._block("entry_notional_rate", sym=sym, action=ac, intent_id=intent_id)

        # Exit throttles (still limited, but higher by default).
        if reduce_risk or ac in {"CLOSE", "REDUCE"}:
            if not self._exit_bucket.allow(cost=1.0):
                return self._block("exit_rate", sym=sym, action=ac, intent_id=intent_id)

        return RiskDecision(allowed=True, reason="ok", kill_mode=self._kill_mode if self._kill_mode != "off" else None)

    def note_order_sent(
        self,
        *,
        symbol: str,
        action: str,
        notional_usd: float,
        reduce_risk: bool = False,
    ) -> None:
        """Record that we actually sent an order (call after a successful submit)."""
        try:
            self._last_order_ts_ms = int(time.time() * 1000)
        except Exception:
            self._last_order_ts_ms = None

        sym = str(symbol or "").strip().upper()
        ac = str(action or "").strip().upper()

        # Track per-symbol event counts for entry spam protection.
        if (not reduce_risk) and ac in {"OPEN", "ADD"}:
            now = time.time()
            dq = self._entry_symbol_events[sym]
            dq.append(now)
            self._prune_times(dq, window_s=60.0, now_s=now)

        # Track notional.
        if (not reduce_risk) and ac in {"OPEN", "ADD"} and self._max_notional_per_window > 0:
            now = time.time()
            self._notional_events.append((now, float(abs(notional_usd or 0.0))))
            self._prune_notional(now_s=now)

    def allow_cancel(self, *, symbol: str, exchange_order_id: str | None = None) -> RiskDecision:
        sym = str(symbol or "").strip().upper()
        if not self._cancel_bucket.allow(cost=1.0):
            return self._block("cancel_rate", sym=sym, action="CANCEL", intent_id=exchange_order_id)
        return RiskDecision(allowed=True, reason="ok", kill_mode=self._kill_mode if self._kill_mode != "off" else None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _refresh_risk_config(self) -> None:
        """Pull risk controls from YAML (preferred) with env var overrides.

        This is best-effort and must never throw.
        """
        cfg: dict[str, Any] = {}
        try:
            from .strategy_manager import StrategyManager

            cfg = StrategyManager.get().get_config("__GLOBAL__") or {}
        except Exception:
            cfg = {}

        risk_cfg = cfg.get("risk") if isinstance(cfg, dict) else None
        risk_cfg = risk_cfg if isinstance(risk_cfg, dict) else {}

        # Drawdown threshold: YAML risk.max_drawdown_pct, overridden by env when set.
        try:
            dd = risk_cfg.get("max_drawdown_pct")
            dd_pct = float(dd) if dd is not None else None
        except Exception:
            dd_pct = None
        env_dd = os.getenv("AI_QUANT_RISK_MAX_DRAWDOWN_PCT")
        if env_dd is not None and str(env_dd).strip() != "":
            try:
                dd_pct = float(str(env_dd).strip())
            except Exception:
                pass
        if dd_pct is None:
            dd_pct = float(self._max_drawdown_pct or 0.0)
        self._max_drawdown_pct = float(max(0.0, min(100.0, dd_pct)))

        # Optional: reduce-risk policy on drawdown kill.
        pol = risk_cfg.get("drawdown_reduce_policy")
        env_pol = os.getenv("AI_QUANT_RISK_DRAWDOWN_REDUCE_POLICY")
        if env_pol is not None and str(env_pol).strip() != "":
            pol = env_pol
        pol_s = str(pol or "none").strip().lower()
        if pol_s not in {"none", "close_all"}:
            pol_s = "none"
        self._drawdown_reduce_policy = pol_s

        # Daily loss threshold (USD): YAML risk.max_daily_loss_usd, overridden by env when set.
        try:
            dl = risk_cfg.get("max_daily_loss_usd")
            dl_usd = float(dl) if dl is not None else None
        except Exception:
            dl_usd = None
        env_dl = os.getenv("AI_QUANT_RISK_MAX_DAILY_LOSS_USD")
        if env_dl is not None and str(env_dl).strip() != "":
            try:
                dl_usd = float(str(env_dl).strip())
            except Exception:
                pass
        if dl_usd is None:
            dl_usd = float(self._max_daily_loss_usd or 0.0)
        self._max_daily_loss_usd = float(max(0.0, dl_usd))

        # Slippage anomaly guard.
        sg = risk_cfg.get("slippage_guard")
        sg = sg if isinstance(sg, dict) else {}

        enabled = sg.get("enabled")
        env_enabled = os.getenv("AI_QUANT_RISK_SLIPPAGE_GUARD_ENABLED")
        if env_enabled is not None and str(env_enabled).strip() != "":
            enabled = env_enabled
        try:
            self._slippage_guard_enabled = (
                bool(enabled)
                if not isinstance(enabled, str)
                else str(enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
            )
        except Exception:
            self._slippage_guard_enabled = False

        window = sg.get("window_fills")
        env_window = os.getenv("AI_QUANT_RISK_SLIPPAGE_GUARD_WINDOW_FILLS")
        if env_window is not None and str(env_window).strip() != "":
            window = env_window
        try:
            self._slippage_guard_window_fills = int(
                max(MIN_SLIPPAGE_WINDOW_FILLS, min(MAX_SLIPPAGE_WINDOW_FILLS, int(float(window or 20))))
            )
        except Exception:
            self._slippage_guard_window_fills = 20

        max_median = sg.get("max_median_bps")
        env_max_median = os.getenv("AI_QUANT_RISK_SLIPPAGE_GUARD_MAX_MEDIAN_BPS")
        if env_max_median is not None and str(env_max_median).strip() != "":
            max_median = env_max_median
        try:
            self._slippage_guard_max_median_bps = float(max(0.0, float(max_median or 0.0)))
        except Exception:
            self._slippage_guard_max_median_bps = 0.0

        # Exposure concentration limits.
        exp = risk_cfg.get("exposure")
        exp = exp if isinstance(exp, dict) else {}

        enabled = exp.get("enabled")
        env_enabled = os.getenv("AI_QUANT_RISK_EXPOSURE_ENABLED")
        if env_enabled is not None and str(env_enabled).strip() != "":
            enabled = env_enabled
        try:
            self._exposure_enabled = (
                bool(enabled)
                if not isinstance(enabled, str)
                else str(enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
            )
        except Exception:
            self._exposure_enabled = False

        max_l = exp.get("alts_max_longs")
        env_max_l = os.getenv("AI_QUANT_RISK_EXPOSURE_ALTS_MAX_LONGS")
        if env_max_l is not None and str(env_max_l).strip() != "":
            max_l = env_max_l
        try:
            self._exposure_alts_max_longs = int(max(0, int(float(max_l or 0))))
        except Exception:
            self._exposure_alts_max_longs = 0

        max_s = exp.get("alts_max_shorts")
        env_max_s = os.getenv("AI_QUANT_RISK_EXPOSURE_ALTS_MAX_SHORTS")
        if env_max_s is not None and str(env_max_s).strip() != "":
            max_s = env_max_s
        try:
            self._exposure_alts_max_shorts = int(max(0, int(float(max_s or 0))))
        except Exception:
            self._exposure_alts_max_shorts = 0

        excl = exp.get("exclude_symbols")
        env_excl = os.getenv("AI_QUANT_RISK_EXPOSURE_EXCLUDE_SYMBOLS")
        if env_excl is not None and str(env_excl).strip() != "":
            excl = env_excl
        out_excl: set[str] = {"BTC"}
        try:
            if isinstance(excl, str):
                parts = [p.strip().upper() for p in str(excl).replace("\n", ",").split(",") if p.strip()]
                out_excl.update(parts)
            elif isinstance(excl, list):
                parts = [str(p).strip().upper() for p in excl if str(p).strip()]
                out_excl.update(parts)
        except Exception:
            pass
        self._exposure_exclude_symbols = out_excl

        # Portfolio heat limit.
        heat = risk_cfg.get("heat")
        heat = heat if isinstance(heat, dict) else {}

        enabled = heat.get("enabled")
        env_enabled = os.getenv("AI_QUANT_RISK_HEAT_ENABLED")
        if env_enabled is not None and str(env_enabled).strip() != "":
            enabled = env_enabled
        try:
            self._heat_enabled = (
                bool(enabled)
                if not isinstance(enabled, str)
                else str(enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
            )
        except Exception:
            self._heat_enabled = False

        max_pct = heat.get("max_pct")
        env_max_pct = os.getenv("AI_QUANT_RISK_HEAT_MAX_PCT")
        if env_max_pct is not None and str(env_max_pct).strip() != "":
            max_pct = env_max_pct
        try:
            self._heat_max_pct = float(max(0.0, float(max_pct or 0.0)))
        except Exception:
            self._heat_max_pct = 0.0

        sl_mult = heat.get("sl_atr_mult")
        env_sl_mult = os.getenv("AI_QUANT_RISK_HEAT_SL_ATR_MULT")
        if env_sl_mult is not None and str(env_sl_mult).strip() != "":
            sl_mult = env_sl_mult
        try:
            self._heat_sl_atr_mult = float(max(0.0, min(100.0, float(sl_mult or 1.5))))
        except Exception:
            self._heat_sl_atr_mult = 1.5

        fb_atr = heat.get("fallback_atr_pct")
        env_fb_atr = os.getenv("AI_QUANT_RISK_HEAT_FALLBACK_ATR_PCT")
        if env_fb_atr is not None and str(env_fb_atr).strip() != "":
            fb_atr = env_fb_atr
        try:
            if fb_atr is None:
                fb_atr = 0.005
            self._heat_fallback_atr_pct = float(max(0.0, min(1.0, float(fb_atr))))
        except Exception:
            self._heat_fallback_atr_pct = 0.005

        # Performance degradation soft stop.
        perf = risk_cfg.get("perf_stop")
        perf = perf if isinstance(perf, dict) else {}

        enabled = perf.get("enabled")
        env_enabled = os.getenv("AI_QUANT_RISK_PERF_STOP_ENABLED")
        if env_enabled is not None and str(env_enabled).strip() != "":
            enabled = env_enabled
        try:
            self._perf_stop_enabled = (
                bool(enabled)
                if not isinstance(enabled, str)
                else str(enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
            )
        except Exception:
            self._perf_stop_enabled = False

        win_n = perf.get("window_trades")
        env_win_n = os.getenv("AI_QUANT_RISK_PERF_STOP_WINDOW_TRADES")
        if env_win_n is not None and str(env_win_n).strip() != "":
            win_n = env_win_n
        try:
            self._perf_stop_window_trades = int(max(0, int(float(win_n or 0))))
        except Exception:
            self._perf_stop_window_trades = 0

        win_m = perf.get("window_minutes")
        env_win_m = os.getenv("AI_QUANT_RISK_PERF_STOP_WINDOW_MINUTES")
        if env_win_m is not None and str(env_win_m).strip() != "":
            win_m = env_win_m
        try:
            self._perf_stop_window_s = float(max(0.0, float(win_m or 0.0))) * 60.0
        except Exception:
            self._perf_stop_window_s = 0.0

        min_n = perf.get("min_trades")
        env_min_n = os.getenv("AI_QUANT_RISK_PERF_STOP_MIN_TRADES")
        if env_min_n is not None and str(env_min_n).strip() != "":
            min_n = env_min_n
        try:
            self._perf_stop_min_trades = int(max(0, int(float(min_n or 0))))
        except Exception:
            self._perf_stop_min_trades = 0

        min_pf = perf.get("min_pf")
        env_min_pf = os.getenv("AI_QUANT_RISK_PERF_STOP_MIN_PF")
        if env_min_pf is not None and str(env_min_pf).strip() != "":
            min_pf = env_min_pf
        try:
            self._perf_stop_min_pf = float(max(0.0, float(min_pf or 0.0)))
        except Exception:
            self._perf_stop_min_pf = 0.0

        min_wr = perf.get("min_wr")
        env_min_wr = os.getenv("AI_QUANT_RISK_PERF_STOP_MIN_WR")
        if env_min_wr is not None and str(env_min_wr).strip() != "":
            min_wr = env_min_wr
        try:
            self._perf_stop_min_wr = float(max(0.0, min(1.0, float(min_wr or 0.0))))
        except Exception:
            self._perf_stop_min_wr = 0.0

        min_sh = perf.get("min_sharpe") if "min_sharpe" in perf else None
        env_min_sh = os.getenv("AI_QUANT_RISK_PERF_STOP_MIN_SHARPE")
        if env_min_sh is not None and str(env_min_sh).strip() != "":
            min_sh = env_min_sh
        try:
            self._perf_stop_min_sharpe = None if min_sh is None else float(min_sh)
        except Exception:
            self._perf_stop_min_sharpe = None

        kill_mode = perf.get("kill_mode")
        env_km = os.getenv("AI_QUANT_RISK_PERF_STOP_KILL_MODE")
        if env_km is not None and str(env_km).strip() != "":
            kill_mode = env_km
        km = str(kill_mode or "close_only").strip().lower()
        if km not in {"close_only", "halt_all"}:
            km = "close_only"
        self._perf_stop_kill_mode = km

    def _refresh_manual_kill(self) -> None:
        # Env kill
        raw = _env_str("AI_QUANT_KILL_SWITCH", "").strip()
        if raw:
            v = raw.strip().lower()
            if v in {"clear", "resume", "off", "unpause"}:
                self.clear_kill(reason="env_clear")
                return
            if v in {"1", "true", "yes", "y", "on", "close_only", "close"}:
                mode = "close_only"
                try:
                    if self._kill_mode_env in {"close_only", "halt_all"}:
                        mode = self._kill_mode_env
                except Exception:
                    mode = "close_only"
                self.kill(mode=mode, reason="env")
            elif v in {"halt", "halt_all", "2", "stop", "full"}:
                self.kill(mode="halt_all", reason="env")
        else:
            # If env cleared, do not auto-clear: only clear explicitly.
            pass

        # File kill
        kill_file = _env_str("AI_QUANT_KILL_SWITCH_FILE", "").strip() or self._kill_file
        if kill_file:
            try:
                if os.path.exists(kill_file):
                    mode = "close_only"
                    try:
                        with open(kill_file, "r", encoding="utf-8") as f:
                            txt = (f.read() or "").strip().lower()
                        if any(tok in txt for tok in ("clear", "resume", "off", "unpause")):
                            self.clear_kill(reason=f"file_clear:{kill_file}")
                            return
                        if "halt" in txt or "full" in txt:
                            mode = "halt_all"
                        elif "close" in txt:
                            mode = "close_only"
                    except Exception:
                        pass
                    self.kill(mode=mode, reason=f"file:{kill_file}")
            except Exception:
                pass

    def _current_utc_day(self) -> str:
        return datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()

    def _refresh_drawdown(self, trader: Any | None) -> None:
        # Reset drawdown high-water mark at UTC day rollover so stale historic peaks
        # do not re-trigger kills after recovery.
        try:
            utc_day = self._current_utc_day()
            if utc_day and self._drawdown_peak_utc_day != utc_day:
                self._drawdown_peak_utc_day = utc_day
                self._equity_peak = None
        except Exception:
            pass

        if self._max_drawdown_pct <= 0:
            return

        equity = None
        # Best-effort extract equity from trader.
        try:
            if trader is not None:
                fn = getattr(trader, "get_live_balance", None)
                if callable(fn):
                    equity = float(fn() or 0.0)
        except Exception:
            equity = None

        try:
            if equity is None and trader is not None:
                equity = float(getattr(trader, "_account_value_usd", 0.0) or 0.0)
        except Exception:
            equity = None

        if equity is None or equity <= 0:
            return

        if self._equity_peak is None or equity > float(self._equity_peak):
            self._equity_peak = float(equity)
            return

        peak = float(self._equity_peak or 0.0)
        if peak <= 0:
            return
        dd = max(0.0, (peak - equity) / peak) * 100.0
        if dd >= float(self._max_drawdown_pct):
            # Close-only kill.
            self.kill(mode="close_only", reason="drawdown")
            self._audit(
                symbol="SYSTEM",
                event="RISK_KILL_DRAWDOWN",
                level="warn",
                data={
                    "drawdown_pct": float(dd),
                    "threshold_pct": float(self._max_drawdown_pct),
                    "equity": float(equity),
                    "peak": float(peak),
                },
            )

    def _refresh_daily_loss(self, *, ts_ms: int, symbol: str, action: str, pnl_usd: float, fee_usd: float) -> None:
        if self._max_daily_loss_usd <= 0:
            return

        ac = str(action or "").strip().upper()
        if ac not in {"CLOSE", "REDUCE"}:
            return

        t_ms = int(ts_ms or 0)
        if t_ms <= 0:
            return

        day = datetime.datetime.fromtimestamp(t_ms / MS_PER_SECOND, tz=datetime.timezone.utc).date().isoformat()
        if not day:
            return

        if self._daily_utc_day != day:
            # Reset at UTC day boundary.
            self._daily_utc_day = day
            self._daily_realised_pnl_usd = 0.0
            self._daily_fees_usd = 0.0

        try:
            self._daily_realised_pnl_usd += float(pnl_usd or 0.0)
        except Exception:
            pass
        try:
            self._daily_fees_usd += float(fee_usd or 0.0)
        except Exception:
            pass

        net = float(self._daily_realised_pnl_usd) - float(self._daily_fees_usd)
        if net <= -float(self._max_daily_loss_usd):
            # Kill reason must be stable within the day so kill_since_s remains useful.
            self.kill(mode="close_only", reason=f"daily_loss:{day}")
            self._audit(
                symbol=str(symbol or "SYSTEM").strip().upper() or "SYSTEM",
                event="RISK_KILL_DAILY_LOSS",
                level="warn",
                data={
                    "utc_day": str(day),
                    "realised_pnl_usd": float(self._daily_realised_pnl_usd),
                    "fees_usd": float(self._daily_fees_usd),
                    "net_pnl_usd": float(net),
                    "threshold_usd": float(self._max_daily_loss_usd),
                },
            )

    def _refresh_slippage_guard(
        self,
        *,
        ts_ms: int,
        symbol: str,
        action: str,
        fill_price: float | None,
        side: str | None,
        ref_mid: float | None,
        ref_bid: float | None,
        ref_ask: float | None,
    ) -> None:
        if (not self._slippage_guard_enabled) or self._slippage_guard_max_median_bps <= 0:
            return

        ac = str(action or "").strip().upper()
        if ac not in {"OPEN", "ADD"}:
            return

        try:
            px = float(fill_price) if fill_price is not None else 0.0
        except Exception:
            px = 0.0
        if px <= 0:
            return

        sd = str(side or "").strip().upper()
        if sd not in {"BUY", "SELL"}:
            return

        ref_kind = None
        ref_px = None
        if sd == "BUY":
            if ref_ask is not None and float(ref_ask) > 0:
                ref_kind = "ask"
                ref_px = float(ref_ask)
            elif ref_mid is not None and float(ref_mid) > 0:
                ref_kind = "mid"
                ref_px = float(ref_mid)
        else:
            if ref_bid is not None and float(ref_bid) > 0:
                ref_kind = "bid"
                ref_px = float(ref_bid)
            elif ref_mid is not None and float(ref_mid) > 0:
                ref_kind = "mid"
                ref_px = float(ref_mid)

        if ref_px is None or ref_px <= 0:
            return

        if sd == "BUY":
            slip_bps = ((px - ref_px) / ref_px) * BASIS_POINTS_PER_UNIT
        else:
            slip_bps = ((ref_px - px) / ref_px) * BASIS_POINTS_PER_UNIT
        slip_bps = float(max(0.0, slip_bps))

        self._slippage_bps.append(slip_bps)
        while len(self._slippage_bps) > int(self._slippage_guard_window_fills):
            try:
                self._slippage_bps.popleft()
            except Exception:
                break

        win = int(self._slippage_guard_window_fills)
        if len(self._slippage_bps) < win:
            return

        vals = sorted(float(x) for x in self._slippage_bps)
        if not vals:
            return
        mid_i = len(vals) // 2
        if len(vals) % 2 == 1:
            median = float(vals[mid_i])
        else:
            median = float((vals[mid_i - 1] + vals[mid_i]) / 2.0)

        if median <= float(self._slippage_guard_max_median_bps):
            return

        # Avoid spamming the same kill event.
        if self._kill_mode == "close_only" and self._kill_reason == "slippage_guard" and self._kill_since_s is not None:
            return

        self.kill(mode="close_only", reason="slippage_guard")
        self._audit(
            symbol=str(symbol or "SYSTEM").strip().upper() or "SYSTEM",
            event="RISK_KILL_SLIPPAGE",
            level="warn",
            data={
                "slippage_bps_last": float(slip_bps),
                "slippage_ref_kind": str(ref_kind or ""),
                "slippage_ref_px": float(ref_px),
                "slippage_window_fills": int(win),
                "slippage_median_bps": float(median),
                "threshold_median_bps": float(self._slippage_guard_max_median_bps),
            },
        )

    def _refresh_perf_stop(self, *, ts_ms: int, symbol: str, action: str, pnl_usd: float, fee_usd: float) -> None:
        if not self._perf_stop_enabled:
            return

        ac = str(action or "").strip().upper()
        if ac not in {"CLOSE", "REDUCE"}:
            return

        t_ms = int(ts_ms or 0)
        if t_ms <= 0:
            return
        now_s = float(t_ms) / MS_PER_SECOND

        try:
            pnl = float(pnl_usd or 0.0)
        except Exception:
            pnl = 0.0
        try:
            fee = float(fee_usd or 0.0)
        except Exception:
            fee = 0.0
        net = float(pnl) - float(fee)

        self._perf_trades.append((now_s, net))

        # Bounded memory: keep more than the evaluation window so time-based windows can work
        # even with sparse trading.
        keep = max(2000, int(self._perf_stop_window_trades or 0) * 10, int(self._perf_stop_min_trades or 0) * 10)
        while len(self._perf_trades) > keep:
            self._perf_trades.popleft()

        if self._perf_stop_window_s > 0:
            cutoff_keep = now_s - (float(self._perf_stop_window_s) * 2.0)
            while self._perf_trades and float(self._perf_trades[0][0]) < cutoff_keep:
                self._perf_trades.popleft()

        # Build evaluation window.
        pairs = list(self._perf_trades)
        if self._perf_stop_window_s > 0:
            cutoff_eval = now_s - float(self._perf_stop_window_s)
            pnls = [float(p) for t, p in pairs if float(t) >= cutoff_eval]
        else:
            pnls = [float(p) for _, p in pairs]

        win_n = int(self._perf_stop_window_trades or 0)
        if win_n > 0 and len(pnls) > win_n:
            pnls = pnls[-win_n:]

        n = int(len(pnls))
        min_n = int(self._perf_stop_min_trades or 0)
        if min_n > 0 and n < min_n:
            return
        if n <= 0:
            return

        profits = 0.0
        losses = 0.0
        wins = 0
        for x in pnls:
            if x > 0:
                profits += float(x)
                wins += 1
            elif x < 0:
                losses += float(-x)

        pf = (profits / losses) if losses > 0 else (float("inf") if profits > 0 else 0.0)
        pf = min(float(pf), 9999.0)
        wr = float(wins) / float(n) if n > 0 else 0.0

        mean = sum(pnls) / float(n) if n > 0 else 0.0
        if n > 1:
            var = sum((x - mean) ** 2 for x in pnls) / float(n - 1)
        else:
            var = 0.0
        std = float(var**0.5)
        if std > 0:
            sharpe = float(mean / std)
        else:
            sharpe = float("inf") if mean > 0 else (-float("inf") if mean < 0 else 0.0)
        sharpe = max(-999.0, min(float(sharpe), 999.0))

        breaches: list[str] = []
        if self._perf_stop_min_pf > 0 and math.isfinite(pf) and float(pf) < float(self._perf_stop_min_pf):
            breaches.append("pf")
        if self._perf_stop_min_wr > 0 and math.isfinite(wr) and float(wr) < float(self._perf_stop_min_wr):
            breaches.append("wr")
        if (
            self._perf_stop_min_sharpe is not None
            and math.isfinite(sharpe)
            and float(sharpe) < float(self._perf_stop_min_sharpe)
        ):
            breaches.append("sharpe")

        if not breaches:
            return

        mode = str(self._perf_stop_kill_mode or "close_only").strip().lower()
        if mode not in {"close_only", "halt_all"}:
            mode = "close_only"

        # Avoid spamming the same kill event.
        if self._kill_mode == mode and self._kill_reason == "perf_degradation" and self._kill_since_s is not None:
            return

        def _finite(v: float) -> float | None:
            try:
                return float(v) if math.isfinite(float(v)) else None
            except Exception:
                return None

        self.kill(mode=mode, reason="perf_degradation")
        self._audit(
            symbol=str(symbol or "SYSTEM").strip().upper() or "SYSTEM",
            event="RISK_KILL_PERF_DEGRADATION",
            level="warn",
            data={
                "breaches": breaches,
                "window_trades": int(win_n),
                "window_s": float(self._perf_stop_window_s or 0.0),
                "n": int(n),
                "pf": _finite(float(pf)),
                "wr": float(wr),
                "sharpe": _finite(float(sharpe)),
                "mean_net_pnl_usd": float(mean),
                "std_net_pnl_usd": float(std),
                "min_pf": float(self._perf_stop_min_pf),
                "min_wr": float(self._perf_stop_min_wr),
                "min_sharpe": None if self._perf_stop_min_sharpe is None else float(self._perf_stop_min_sharpe),
            },
        )

    def _allow_symbol_event(self, *, sym: str, is_entry: bool) -> bool:
        if not sym:
            return True
        if not is_entry:
            return True
        now = time.time()
        dq = self._entry_symbol_events[sym]
        self._prune_times(dq, window_s=60.0, now_s=now)
        return len(dq) < int(max(1.0, float(self._entry_symbol_per_min)))

    def _allow_notional(self, add_notional: float) -> bool:
        now = time.time()
        self._prune_notional(now_s=now)
        total = 0.0
        for _, n in self._notional_events:
            total += float(n)
        if (total + float(abs(add_notional or 0.0))) > float(self._max_notional_per_window):
            return False
        return True

    def _portfolio_heat_usd(
        self,
        *,
        positions: dict[str, Any],
        sl_atr_mult: float,
        fallback_atr_pct: float,
    ) -> float:
        total = 0.0
        for _, p0 in (positions or {}).items():
            total += self._position_risk_usd(
                pos=p0,
                sl_atr_mult=sl_atr_mult,
                fallback_atr_pct=fallback_atr_pct,
            )
        return float(max(0.0, total))

    def _position_risk_usd(self, *, pos: Any, sl_atr_mult: float, fallback_atr_pct: float) -> float:
        if not isinstance(pos, dict):
            return 0.0
        t = str(pos.get("type") or pos.get("pos_type") or "").strip().upper()
        if t not in {"LONG", "SHORT"}:
            try:
                sz = float(pos.get("size") or 0.0)
            except Exception:
                sz = 0.0
            t = "LONG" if sz > 0 else ("SHORT" if sz < 0 else "")
        if t not in {"LONG", "SHORT"}:
            return 0.0

        try:
            entry = float(pos.get("entry_price") or 0.0)
        except Exception:
            entry = 0.0
        if entry <= 0:
            return 0.0

        try:
            size = float(abs(float(pos.get("size") or 0.0)))
        except Exception:
            size = 0.0
        if size <= 0:
            return 0.0

        try:
            atr = float(pos.get("entry_atr") or 0.0)
        except Exception:
            atr = 0.0
        if atr <= 0 and fallback_atr_pct > 0:
            atr = float(entry) * float(max(0.0, fallback_atr_pct))

        try:
            sl_price = float(pos.get("trailing_sl") or 0.0)
        except Exception:
            sl_price = 0.0
        if sl_price <= 0 and atr > 0 and sl_atr_mult > 0:
            if t == "LONG":
                sl_price = entry - (atr * sl_atr_mult)
            else:
                sl_price = entry + (atr * sl_atr_mult)

        dist = 0.0
        if sl_price > 0:
            if t == "LONG":
                dist = float(max(0.0, entry - sl_price))
            else:
                dist = float(max(0.0, sl_price - entry))
        return float(max(0.0, dist) * size)

    def _order_heat_usd_est(
        self,
        *,
        side: str,
        notional_usd: float,
        entry_price: float | None,
        entry_atr: float | None,
        sl_atr_mult: float,
        fallback_atr_pct: float,
    ) -> float:
        # Estimate the *incremental* heat of a new OPEN/ADD based on entry ATR and stop multiple.
        try:
            notional = float(abs(notional_usd or 0.0))
        except Exception:
            notional = 0.0
        if notional <= 0:
            return 0.0

        try:
            px = float(entry_price or 0.0)
        except Exception:
            px = 0.0
        if px <= 0:
            return 0.0

        try:
            atr = float(entry_atr or 0.0)
        except Exception:
            atr = 0.0
        if atr <= 0 and fallback_atr_pct > 0:
            atr = float(px) * float(max(0.0, fallback_atr_pct))
        if atr <= 0 or sl_atr_mult <= 0:
            return 0.0

        sd = str(side or "").strip().upper()
        if sd not in {"BUY", "SELL"}:
            return 0.0

        try:
            size = float(notional) / float(px)
        except Exception:
            size = 0.0
        if size <= 0:
            return 0.0

        risk_dist = float(max(0.0, atr * float(sl_atr_mult)))
        return float(max(0.0, risk_dist * size))

    def _prune_times(self, dq: deque[float], *, window_s: float, now_s: float) -> None:
        cutoff = float(now_s) - float(window_s)
        while dq and float(dq[0]) < cutoff:
            dq.popleft()

    def _prune_notional(self, *, now_s: float) -> None:
        cutoff = float(now_s) - float(self._notional_window_s)
        while self._notional_events and float(self._notional_events[0][0]) < cutoff:
            self._notional_events.popleft()

    def _block(self, code: str, *, sym: str, action: str, intent_id: str | None) -> RiskDecision:
        self._blocked_counts[str(code)] += 1
        reason = str(code)
        if code in {"close_only", "halt_all"}:
            # Include the root reason.
            reason = f"{code}:{self._kill_reason or 'manual'}"
        self._audit(
            symbol=sym or "SYSTEM",
            event="RISK_BLOCK",
            level="warn",
            data={
                "code": str(code),
                "action": str(action),
                "intent_id": intent_id,
                "kill_mode": self._kill_mode,
                "kill_reason": self._kill_reason,
            },
        )
        return RiskDecision(
            allowed=False, reason=reason, kill_mode=self._kill_mode if self._kill_mode != "off" else None
        )

    def _audit(self, *, symbol: str, event: str, level: str, data: dict[str, Any] | None) -> None:
        try:
            import strategy.mei_alpha_v1 as mei_alpha_v1

            mei_alpha_v1.log_audit_event(symbol=symbol, event=event, level=level, data=data)
        except Exception:
            # Never block trading on audit logging.
            return
