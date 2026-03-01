from __future__ import annotations

import math
import logging
import os
import json
import hashlib
import time
import traceback
import importlib
from importlib import util
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol

import pandas as pd

from .market_data import MarketDataHub
from .strategy_manager import StrategyManager
from .utils import now_ms

# AQC-801 traceability: module-level helpers from the strategy module.
# These are lazy-imported on first use to avoid circular-import issues
# (strategy imports engine in some factory paths).
_decision_event_fn = None
_link_trade_fn = None


def _get_decision_event_fn() -> Callable[..., dict[str, Any]] | None:
    global _decision_event_fn
    if _decision_event_fn is None:
        try:
            from strategy.mei_alpha_v1 import create_decision_event

            _decision_event_fn = create_decision_event
        except (ImportError, AttributeError):
            logging.getLogger(__name__).warning("mei_alpha_v1.create_decision_event import failed", exc_info=True)
            _decision_event_fn = False  # sentinel: import failed, don't retry
    return _decision_event_fn if _decision_event_fn else None


logger = logging.getLogger(__name__)

ENTRY_MAX_DELAY_MS_HARD_MAX = 2 * 60 * 60 * 1000
KERNEL_DECISION_FILE_MAX_BYTES_DEFAULT = 4 * 1024 * 1024
KERNEL_DECISION_FILE_MAX_BYTES_MIN = 1024
KERNEL_DECISION_FILE_MAX_BYTES_MAX = 128 * 1024 * 1024


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _kernel_decision_file_max_bytes() -> int:
    raw = os.getenv("AI_QUANT_KERNEL_DECISION_FILE_MAX_BYTES")
    if raw is None:
        return int(KERNEL_DECISION_FILE_MAX_BYTES_DEFAULT)
    try:
        parsed = int(raw)
    except (TypeError, ValueError, OverflowError):
        return int(KERNEL_DECISION_FILE_MAX_BYTES_DEFAULT)
    if parsed < KERNEL_DECISION_FILE_MAX_BYTES_MIN:
        return int(KERNEL_DECISION_FILE_MAX_BYTES_MIN)
    if parsed > KERNEL_DECISION_FILE_MAX_BYTES_MAX:
        return int(KERNEL_DECISION_FILE_MAX_BYTES_MAX)
    return int(parsed)


def _interval_to_ms(interval: str) -> int:
    s = str(interval or "").strip().lower()
    if not s:
        return 60 * 60 * 1000
    try:
        if s.endswith("m"):
            return int(float(s[:-1]) * 60.0 * 1000.0)
        if s.endswith("h"):
            return int(float(s[:-1]) * 60.0 * 60.0 * 1000.0)
        if s.endswith("d"):
            return int(float(s[:-1]) * 24.0 * 60.0 * 60.0 * 1000.0)
        # Fallback: assume seconds.
        return int(float(s) * 1000.0)
    except (ValueError, TypeError, OverflowError):
        return 0


def _finite_float_or_default(raw: Any, default: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    if not math.isfinite(value):
        return float(default)
    return float(value)


def _resolve_entry_max_delay_ms(*, raw_ms: str | None, raw_s: str | None) -> tuple[int, bool]:
    """Resolve entry delay env values to milliseconds.

    Returns `(value_ms, clamped)` where `clamped=True` indicates the configured
    value exceeded the hard safety maximum and was reduced.
    """

    max_delay_ms = 0
    try:
        raw_ms_f = float(raw_ms or 0.0)
        max_delay_ms = int(raw_ms_f) if math.isfinite(raw_ms_f) else 0
    except (TypeError, ValueError, OverflowError):
        max_delay_ms = 0
    if max_delay_ms <= 0:
        try:
            raw_s_f = float(raw_s or 0.0)
            max_delay_ms = int(raw_s_f * 1000.0) if math.isfinite(raw_s_f) else 0
        except (TypeError, ValueError, OverflowError):
            max_delay_ms = 0
    if max_delay_ms <= 0:
        return 0, False
    if max_delay_ms > ENTRY_MAX_DELAY_MS_HARD_MAX:
        return int(ENTRY_MAX_DELAY_MS_HARD_MAX), True
    return int(max_delay_ms), False


@dataclass
class KernelDecision:
    symbol: str
    action: str
    signal: str
    confidence: str
    score: float = 0.0
    now_series: dict[str, Any] | None = None
    target_size: float | None = None
    entry_key: int | None = None
    reason: str | None = None
    reason_code: str | None = None
    open_pos_count: int = 0

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | Any) -> "KernelDecision | None":
        if not isinstance(raw, Mapping):
            return None

        sym = str(raw.get("symbol", "")).strip().upper()
        if not sym:
            return None

        act = _normalise_kernel_action(raw.get("action"), raw_kind=raw.get("kind"))
        if act not in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
            return None

        signal = _normalise_kernel_intent_signal(
            raw.get("signal"),
            raw_action=raw.get("action"),
            raw_kind=raw.get("kind"),
            raw_side=raw.get("side"),
        )
        confidence = str(raw.get("confidence", "N/A"))
        # Kernel decisions have confidence="N/A" (Rust kernel events lack a
        # confidence field).  Normalise to "medium" — a safer default that
        # still passes the confidence gate without granting max leverage/sizing.
        if confidence.strip().upper() == "N/A":
            confidence = "medium"

        try:
            score = float(raw.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0

        now_series = raw.get("now_series")
        if not isinstance(now_series, dict):
            try:
                now_series = dict(now_series)
            except (TypeError, ValueError):
                now_series = {}

        target_size = _normalise_kernel_target_size(raw.get("quantity"), raw.get("notional_usd"), raw.get("price"))
        if target_size is None:
            target_size = _normalise_kernel_target_size(
                raw.get("target_size"),
                raw.get("notional_hint_usd"),
                raw.get("price"),
            )

        entry_key = raw.get(
            "entry_key",
            raw.get("intent_id", raw.get("entry_candle_key", raw.get("candle_key"))),
        )
        try:
            entry_key = int(entry_key) if entry_key is not None else None
        except (TypeError, ValueError):
            entry_key = None

        reason = raw.get("reason")
        if isinstance(reason, str):
            reason = reason.strip() or None
        else:
            reason = None

        reason_code = raw.get("reason_code")
        if isinstance(reason_code, str):
            reason_code = reason_code.strip().lower() or None
        else:
            reason_code = None

        try:
            open_pos_count = int(raw.get("open_pos_count", 0) or 0)
        except (TypeError, ValueError):
            open_pos_count = 0

        return cls(
            symbol=sym,
            action=act,
            signal=signal,
            confidence=confidence,
            score=score,
            now_series=now_series,
            target_size=target_size,
            entry_key=entry_key,
            reason=reason,
            reason_code=reason_code,
            open_pos_count=open_pos_count,
        )


class DecisionProvider(Protocol):
    def get_decisions(
        self,
        *,
        symbols: list[str],
        watchlist: list[str],
        open_symbols: list[str],
        market: Any,
        interval: str,
        lookback_bars: int,
        mode: str,
        not_ready_symbols: set[str],
        strategy: Any,
        now_ms: int,
    ) -> Iterable[KernelDecision]: ...


class KernelDecisionFileProvider:
    def __init__(self, path: str | None):
        self.path = str(path).strip() if path else None

    def _load_raw(self) -> list[dict[str, Any]]:
        path = self.path
        if not path:
            return []

        max_bytes = _kernel_decision_file_max_bytes()
        try:
            with open(path, "rb") as fh:
                payload = fh.read(max_bytes + 1)
        except FileNotFoundError:
            return []
        except Exception:
            logger.warning("decision file unreadable: %s", path, exc_info=True)
            return []

        if len(payload) > max_bytes:
            logger.warning(
                "decision file too large: %s (read=%dB, limit=%dB); skipping",
                path,
                int(len(payload)),
                int(max_bytes),
            )
            return []

        try:
            raw = json.loads(payload.decode("utf-8"))
        except Exception:
            logger.warning("decision file unreadable: %s", path, exc_info=True)
            return []

        if isinstance(raw, dict):
            if isinstance(raw.get("decisions"), list):
                return [item for item in raw["decisions"] if isinstance(item, Mapping)]
            if "symbol" in raw:
                return [raw]  # single-item payload
            return []

        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, Mapping)]

        return []

    def get_decisions(
        self,
        *,
        symbols: list[str],
        watchlist: list[str],
        open_symbols: list[str],
        market: Any,
        interval: str,
        lookback_bars: int,
        mode: str,
        not_ready_symbols: set[str],
        strategy: Any,
        now_ms: int,
    ) -> Iterable[KernelDecision]:
        del symbols, watchlist, open_symbols, market, interval, lookback_bars, mode, not_ready_symbols, strategy, now_ms
        for raw in self._load_raw():
            dec = KernelDecision.from_raw(raw)
            if dec is None:
                continue
            yield dec


def _load_kernel_runtime_module(module_name: str = "bt_runtime") -> object:
    """Import and return the Rust runtime binding module."""

    def _try_import() -> object:
        return importlib.import_module(module_name)

    try:
        return _try_import()
    except ModuleNotFoundError as exc:
        if exc.name not in {module_name, None}:
            raise

        candidates = [
            Path(os.getenv("AI_QUANT_BT_RUNTIME_PATH") or ""),
            Path(__file__).resolve().parents[1] / "backtester" / "target" / "release" / "deps",
            Path(__file__).resolve().parents[1] / "backtester" / "target" / "release",
            Path(__file__).resolve().parents[1] / "backtester" / "target" / "debug" / "deps",
            Path(__file__).resolve().parents[1] / "backtester" / "target" / "debug",
        ]
        for candidate in candidates:
            candidate_str = str(candidate)
            if not candidate.exists() or candidate_str in sys.path:
                continue
            sys.path.insert(0, candidate_str)

        try:
            return _try_import()
        except ModuleNotFoundError as second_exc:
            if second_exc.name not in {module_name, None}:
                raise

        for candidate_dir in candidates:
            if not candidate_dir.is_dir():
                continue
            for pattern in [
                f"lib{module_name}*.so",
                f"{module_name}*.so",
                f"{module_name}.so",
            ]:
                for candidate in candidate_dir.glob(pattern):
                    if not candidate.is_file():
                        continue
                    if not candidate.name.startswith(("lib" + module_name, module_name)):
                        continue
                    spec = util.spec_from_file_location(module_name, str(candidate))
                    if spec is None or spec.loader is None:
                        continue
                    module = util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return module

        raise


def _normalise_kernel_signal(raw_signal: Any) -> str:
    sig = str(raw_signal or "").strip().upper()
    if sig == "LONG":
        return "BUY"
    if sig == "SHORT":
        return "SELL"
    return sig


def _normalise_kernel_side(raw_side: Any) -> str:
    side = str(raw_side or "").strip().lower()
    if side == "long":
        return "BUY"
    if side == "short":
        return "SELL"
    return str(raw_side or "NEUTRAL").strip().upper()


def _normalise_kernel_intent_signal(
    raw_signal: Any,
    *,
    raw_action: Any,
    raw_kind: Any,
    raw_side: Any,
) -> str:
    has_signal = not (raw_signal is None or str(raw_signal).strip() == "")

    signal = _normalise_kernel_signal(raw_signal)
    if signal in {"BUY", "SELL", "NEUTRAL"}:
        return signal

    if raw_side is not None and str(raw_side).strip() != "":
        side = _normalise_kernel_side(raw_side)
        if side in {"BUY", "SELL", "NEUTRAL"}:
            return side

    if not has_signal:
        action = _normalise_kernel_action(raw_action, raw_kind)
        if action:
            return action

    return "NEUTRAL"


def _normalise_kernel_action(raw_action: Any, raw_kind: Any = None) -> str:
    action = str(raw_action or "").strip().upper()
    if action in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
        return action
    if action == "REVERSE":
        return "CLOSE"

    kind = str(raw_kind or "").strip().lower()
    if kind == "open":
        return "OPEN"
    if kind == "add":
        return "ADD"
    if kind == "close":
        return "CLOSE"
    if kind == "reverse":
        return "CLOSE"

    return ""


def _normalise_kernel_target_size(raw_size: Any, raw_notional: Any, raw_price: Any) -> float | None:
    try:
        notional = float(raw_notional)
        if notional > 0.0:
            price = float(raw_price)
            if price <= 0.0:
                return None
            return notional / price
    except (TypeError, ValueError):
        pass

    try:
        quantity = float(raw_size)
        if quantity > 0.0:
            return quantity
    except (TypeError, ValueError):
        pass
    return None


def _normalise_kernel_price(raw_price: Any, default: float = 0.0) -> float:
    try:
        price = float(raw_price)
        if price > 0.0:
            return price
    except (TypeError, ValueError):
        pass
    return default


def _normalise_kernel_notional(raw_notional: Any, raw_size: Any, price: float) -> float:
    try:
        raw_value = float(raw_notional)
        if raw_value > 0.0:
            return raw_value
    except (TypeError, ValueError):
        pass
    try:
        size_value = float(raw_size)
        if size_value > 0.0 and price > 0.0:
            return size_value * price
    except (TypeError, ValueError):
        pass
    return 0.0


def _normalise_kernel_event_id(raw_id: Any, fallback: int) -> int:
    try:
        parsed = int(raw_id)
        if parsed >= 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return fallback


class KernelDecisionRustBindingProvider:
    """Call the Rust decision kernel via the `bt_runtime` extension."""

    _KERNEL_STATE_PATH = str(Path("~/.mei/kernel_state.json").expanduser())
    _KERNEL_STATE_BASENAME = "kernel_state.json"

    _tunnel_table_ready: set[str] = set()

    def __init__(self, module_name: str = "bt_runtime", path: str | None = None, db_path: str | None = None) -> None:
        self._runtime = _load_kernel_runtime_module(module_name)
        self._path = str(path).strip() if path else None
        self._db_path = str(db_path).strip() if db_path else None
        self._state_path = self._resolve_state_path(self._db_path)
        self._legacy_state_path = self._KERNEL_STATE_PATH
        self._allow_legacy_state_fallback = _env_bool("AI_QUANT_KERNEL_STATE_LEGACY_FALLBACK", False)
        self._state_json = self._load_or_create_state()
        self._base_params_json = self._runtime.default_kernel_params_json()
        self._base_params_obj = self._load_json_obj(self._base_params_json)
        self._params_json = json.dumps(self._base_params_obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        self._params_cache: dict[tuple[str, str], str] = {}
        self._missing_exit_params_warned: set[tuple[str, str]] = set()
        try:
            _cache_limit_raw = int(str(os.getenv("AI_QUANT_KERNEL_PARAMS_CACHE_SIZE", "256") or "256").strip())
        except Exception:
            _cache_limit_raw = 256
        self._params_cache_limit = max(16, int(_cache_limit_raw))
        self._require_exit_params = _env_bool("AI_QUANT_KERNEL_REQUIRE_EXIT_PARAMS", False)
        self._state_json = self._bootstrap_state_from_db_if_needed(self._state_json)
        self._event_id = 1

    @staticmethod
    def _load_json_obj(raw_json: str) -> dict[str, Any]:
        try:
            loaded = json.loads(str(raw_json or "{}"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            return dict(loaded)
        return {}

    def _resolve_params_json(self, *, symbol: str, strategy: Any) -> str:
        symbol_u = str(symbol or "").strip().upper()
        if not symbol_u:
            return self._params_json

        strategy_sha = ""
        if strategy is not None:
            snap = getattr(strategy, "snapshot", None)
            strategy_sha = str(getattr(snap, "overrides_sha1", "") or "").strip().lower()
        cache_key = (strategy_sha or "no_strategy_sha", symbol_u)
        cached = self._params_cache.get(cache_key)
        if cached is not None:
            return cached

        cfg: dict[str, Any] | None = None
        if strategy is not None:
            try:
                maybe_cfg = strategy.get_config(symbol_u)
                if isinstance(maybe_cfg, dict):
                    cfg = maybe_cfg
            except Exception:
                logger.warning(
                    "Kernel params: failed to load strategy config for %s (strategy_sha1=%s)",
                    symbol_u,
                    strategy_sha[:8] or "none",
                    exc_info=True,
                )

        if cfg is None:
            try:
                maybe_global = strategy.get_config("__GLOBAL__") if strategy is not None else None
                if isinstance(maybe_global, dict):
                    cfg = maybe_global
            except Exception:
                cfg = None

        params_obj = dict(self._base_params_obj)
        params_obj.pop("entry_params", None)
        params_obj.pop("exit_params", None)
        entry_params: Mapping[str, Any] | None = None
        exit_params: Mapping[str, Any] | None = None
        try:
            from strategy.mei_alpha_v1 import build_entry_params, build_exit_params

            entry_candidate = build_entry_params(cfg if isinstance(cfg, dict) else None)
            exit_candidate = build_exit_params(cfg if isinstance(cfg, dict) else None)
            if isinstance(entry_candidate, Mapping):
                entry_params = entry_candidate
            if isinstance(exit_candidate, Mapping):
                exit_params = exit_candidate
        except Exception:
            logger.warning(
                "Kernel params merge failed for %s (strategy_sha1=%s)",
                symbol_u,
                strategy_sha[:8] or "none",
                exc_info=True,
            )

        if isinstance(entry_params, Mapping):
            params_obj["entry_params"] = dict(entry_params)
        if isinstance(exit_params, Mapping):
            params_obj["exit_params"] = dict(exit_params)
        else:
            warn_key = (strategy_sha[:8] or "none", symbol_u)
            if warn_key not in self._missing_exit_params_warned:
                logger.warning(
                    "Kernel params missing exit_params for %s (strategy_sha1=%s require_exit_params=%s)",
                    symbol_u,
                    strategy_sha[:8] or "none",
                    self._require_exit_params,
                )
                self._missing_exit_params_warned.add(warn_key)
            if self._require_exit_params:
                raise RuntimeError(f"missing exit_params for symbol={symbol_u}")

        params_json = json.dumps(params_obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if len(self._params_cache) >= self._params_cache_limit:
            self._params_cache.pop(next(iter(self._params_cache)), None)
        self._params_cache[cache_key] = params_json
        return params_json

    @staticmethod
    def _extract_exit_params_json(params_json: str) -> str | None:
        params = KernelDecisionRustBindingProvider._load_json_obj(params_json)
        exit_params = params.get("exit_params")
        if isinstance(exit_params, Mapping):
            return json.dumps(dict(exit_params), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return None

    def _probe_exit_bounds_from_evaluate(
        self,
        *,
        raw_event: Mapping[str, Any],
        state_json: str,
        params_json: str,
        exit_params_json: str,
        now_ms_value: int,
    ) -> dict[str, Any] | None:
        symbol = str(raw_event.get("symbol", "")).strip().upper()
        if not symbol:
            return None
        indicators = raw_event.get("indicators")
        if not isinstance(indicators, Mapping):
            return None
        price = _normalise_kernel_price(raw_event.get("price"), default=0.0)
        if price <= 0.0:
            return None
        timestamp_ms = raw_event.get("timestamp_ms")
        try:
            timestamp_ms = int(timestamp_ms)
            if timestamp_ms <= 0:
                timestamp_ms = int(now_ms_value or 0)
        except Exception:
            timestamp_ms = int(now_ms_value or 0)
        if int(timestamp_ms) <= 0:
            timestamp_ms = int(now_ms())

        probe_event = {
            "schema_version": 1,
            "event_id": _normalise_kernel_event_id(raw_event.get("event_id"), int(timestamp_ms)),
            "timestamp_ms": int(timestamp_ms),
            "symbol": symbol,
            "signal": "price_update",
            "price": float(price),
            "indicators": dict(indicators),
        }
        try:
            probe_resp_raw = self._runtime.step_full(
                state_json,
                json.dumps(probe_event, ensure_ascii=False),
                params_json,
                exit_params_json,
            )
            probe_env = json.loads(probe_resp_raw)
        except Exception:
            logger.debug(
                "Kernel exit-bounds probe failed for %s",
                symbol,
                exc_info=True,
            )
            return None
        if not isinstance(probe_env, dict) or not bool(probe_env.get("ok", False)):
            return None
        probe_decision = probe_env.get("decision")
        if not isinstance(probe_decision, dict):
            return None
        probe_diag = probe_decision.get("diagnostics")
        probe_eb = probe_diag.get("exit_bounds") if isinstance(probe_diag, dict) else None
        if not isinstance(probe_eb, dict):
            return None
        return dict(probe_eb)

    @classmethod
    def _resolve_state_path(cls, db_path: str | None) -> str:
        explicit = str(os.getenv("AI_QUANT_KERNEL_STATE_PATH", "") or "").strip()
        if explicit:
            return os.path.expanduser(explicit)

        base_dir = str(os.getenv("AI_QUANT_KERNEL_STATE_DIR", "~/.mei") or "~/.mei").strip() or "~/.mei"
        base_dir = os.path.expanduser(base_dir)
        if not os.path.isabs(base_dir):
            anchor_dir = os.path.dirname(str(db_path or "").strip()) if str(db_path or "").strip() else os.getcwd()
            base_dir = os.path.abspath(os.path.join(anchor_dir, base_dir))

        tag = str(os.getenv("AI_QUANT_INSTANCE_TAG", "") or "").strip()
        basename = cls._KERNEL_STATE_BASENAME
        if tag:
            stem, ext = os.path.splitext(basename)
            basename = f"{stem}_{tag}{ext}"
        elif db_path:
            db_real = str(Path(str(db_path)).expanduser().resolve())
            db_stem = Path(db_real).stem.strip()
            if db_stem:
                stem, ext = os.path.splitext(basename)
                db_hash = hashlib.sha1(db_real.encode("utf-8")).hexdigest()[:12]
                basename = f"{stem}_{db_stem}_{db_hash}{ext}"
        return str(Path(base_dir) / basename)

    def _load_latest_balance_from_db(self) -> float | None:
        db_path = str(self._db_path or "").strip()
        if not db_path:
            return None
        try:
            import sqlite3
        except Exception:
            return None
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            row = conn.execute("SELECT balance FROM trades WHERE balance IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return None
            bal = _finite_float_or_default(row[0], float("nan"))
            if not math.isfinite(bal) or bal < 0.0:
                return None
            return float(bal)
        except Exception:
            return None
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    def _load_open_positions_from_db(self) -> dict[str, dict[str, Any]]:
        db_path = str(self._db_path or "").strip()
        if not db_path:
            return {}
        try:
            import sqlite3
            import datetime as _dt
        except Exception:
            return {}

        out: dict[str, dict[str, Any]] = {}
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            require_position_state = _env_bool("AI_QUANT_KERNEL_BOOTSTRAP_REQUIRE_POSITION_STATE", True)

            has_position_state = bool(
                cur.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='position_state' LIMIT 1"
                ).fetchone()
            )
            state_cols: set[str] = set()
            if has_position_state:
                state_cols = {str(row[1]) for row in cur.execute("PRAGMA table_info(position_state)").fetchall()}
            elif require_position_state:
                logger.warning(
                    "Kernel DB bootstrap skipped: position_state table missing (db=%s)",
                    db_path,
                )
                return {}

            open_rows = cur.execute(
                """
                SELECT t.id AS open_trade_id, t.timestamp AS open_ts, t.symbol, t.type AS pos_type,
                       t.price AS open_px, t.size AS open_sz, t.confidence, t.entry_atr, t.leverage, t.margin_used
                FROM trades t
                JOIN (
                    SELECT symbol, MAX(id) AS open_id
                    FROM trades
                    WHERE action = 'OPEN'
                    GROUP BY symbol
                ) lo ON lo.symbol = t.symbol AND lo.open_id = t.id
                LEFT JOIN (
                    SELECT symbol, MAX(id) AS close_id
                    FROM trades
                    WHERE action = 'CLOSE'
                    GROUP BY symbol
                ) lc ON lc.symbol = t.symbol
                WHERE lc.close_id IS NULL OR t.id > lc.close_id
                """
            ).fetchall()

            for row in open_rows:
                symbol = str(row["symbol"] or "").strip().upper()
                if not symbol:
                    continue
                pos_type = str(row["pos_type"] or "").strip().upper()
                if pos_type not in {"LONG", "SHORT"}:
                    continue

                try:
                    avg_entry = float(row["open_px"] or 0.0)
                    net_size = float(row["open_sz"] or 0.0)
                except Exception:
                    continue
                if avg_entry <= 0.0 or net_size <= 0.0:
                    continue

                try:
                    entry_atr = float(row["entry_atr"] or 0.0)
                except Exception:
                    entry_atr = 0.0

                open_trade_id = int(row["open_trade_id"])
                add_count_hist = 0
                last_add_time_hist = 0
                fill_rows = cur.execute(
                    """
                    SELECT action, price, size, entry_atr, timestamp
                    FROM trades
                    WHERE symbol = ?
                      AND id > ?
                      AND action IN ('ADD', 'REDUCE')
                    ORDER BY id ASC
                    """,
                    (symbol, open_trade_id),
                ).fetchall()
                for fill in fill_rows:
                    try:
                        px = float(fill["price"] or 0.0)
                        sz = float(fill["size"] or 0.0)
                    except Exception:
                        continue
                    if px <= 0.0 or sz <= 0.0:
                        continue
                    action = str(fill["action"] or "").strip().upper()
                    if action == "ADD":
                        new_total = net_size + sz
                        if new_total > 0.0:
                            avg_entry = ((avg_entry * net_size) + (px * sz)) / new_total
                            fill_atr_raw = fill["entry_atr"]
                            fill_atr = None
                            if fill_atr_raw is not None:
                                try:
                                    fill_atr = float(fill_atr_raw)
                                except Exception:
                                    fill_atr = None
                            if fill_atr and fill_atr > 0:
                                if entry_atr > 0:
                                    entry_atr = ((entry_atr * net_size) + (fill_atr * sz)) / new_total
                                else:
                                    entry_atr = fill_atr
                            net_size = new_total
                        add_count_hist += 1
                        fill_ts = 0
                        try:
                            fill_ts = int(_dt.datetime.fromisoformat(str(fill["timestamp"])).timestamp() * 1000)
                        except Exception:
                            fill_ts = 0
                        if fill_ts > 0:
                            last_add_time_hist = max(last_add_time_hist, fill_ts)
                    elif action == "REDUCE":
                        net_size -= sz
                        if net_size <= 0.0:
                            net_size = 0.0
                            break

                if net_size <= 0.0:
                    continue

                try:
                    leverage = float(row["leverage"]) if row["leverage"] is not None else 1.0
                except Exception:
                    leverage = 1.0
                leverage = max(1.0, float(leverage))

                margin_used = 0.0
                try:
                    if row["margin_used"] is not None:
                        margin_used = float(row["margin_used"])
                except Exception:
                    margin_used = 0.0
                if margin_used <= 0.0 and avg_entry > 0.0:
                    margin_used = abs(net_size) * avg_entry / leverage

                trailing_sl = None
                last_funding_time = 0
                adds_count = int(add_count_hist)
                tp1_taken = 0
                last_add_time = int(last_add_time_hist)
                entry_adx_threshold = 0.0

                has_matching_state = False
                if has_position_state:
                    ps = cur.execute(
                        "SELECT * FROM position_state WHERE symbol = ? LIMIT 1",
                        (symbol,),
                    ).fetchone()
                    if ps and ("open_trade_id" not in state_cols or ps["open_trade_id"] is None or int(ps["open_trade_id"]) == open_trade_id):
                        has_matching_state = True
                        if "trailing_sl" in state_cols and ps["trailing_sl"] is not None:
                            try:
                                trailing_sl = float(ps["trailing_sl"])
                            except Exception:
                                trailing_sl = None
                        if "last_funding_time" in state_cols:
                            try:
                                last_funding_time = int(ps["last_funding_time"] or 0)
                            except Exception:
                                last_funding_time = 0
                        if "adds_count" in state_cols:
                            try:
                                adds_count = int(ps["adds_count"] or add_count_hist)
                            except Exception:
                                adds_count = int(add_count_hist)
                        if "tp1_taken" in state_cols:
                            try:
                                tp1_taken = int(ps["tp1_taken"] or 0)
                            except Exception:
                                tp1_taken = 0
                        if "last_add_time" in state_cols:
                            try:
                                ps_last_add = int(ps["last_add_time"] or 0)
                            except Exception:
                                ps_last_add = 0
                            if ps_last_add > 0:
                                last_add_time = ps_last_add
                        if "entry_adx_threshold" in state_cols:
                            try:
                                entry_adx_threshold = float(ps["entry_adx_threshold"] or 0.0)
                            except Exception:
                                entry_adx_threshold = 0.0

                if require_position_state and not has_matching_state:
                    continue

                if last_funding_time <= 0:
                    try:
                        last_funding_time = int(_dt.datetime.fromisoformat(str(row["open_ts"])).timestamp() * 1000)
                    except Exception:
                        last_funding_time = int(now_ms())

                out[symbol] = {
                    "type": pos_type,
                    "entry_price": float(avg_entry),
                    "size": float(net_size),
                    "confidence": str(row["confidence"] or "medium").strip().lower() or "medium",
                    "entry_atr": float(entry_atr),
                    "entry_adx_threshold": float(entry_adx_threshold),
                    "open_timestamp": str(row["open_ts"] or ""),
                    "trailing_sl": trailing_sl,
                    "last_funding_time": int(last_funding_time),
                    "leverage": float(leverage),
                    "margin_used": float(abs(net_size) * avg_entry / leverage if avg_entry > 0 else margin_used),
                    "adds_count": int(adds_count),
                    "tp1_taken": int(tp1_taken),
                    "last_add_time": int(last_add_time),
                }
        except Exception:
            logger.warning("Kernel DB bootstrap scan failed: %s", traceback.format_exc())
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
        return out

    def _bootstrap_state_from_db_if_needed(self, state_json: str) -> str:
        try:
            state = json.loads(state_json)
        except Exception:
            return state_json
        if not isinstance(state, dict):
            return state_json

        existing_positions = state.get("positions")
        if isinstance(existing_positions, dict) and len(existing_positions) > 0:
            return state_json

        py_positions = self._load_open_positions_from_db()
        if not py_positions:
            return state_json

        try:
            from strategy.mei_alpha_v1 import python_position_to_kernel
        except Exception:
            logger.warning("Kernel DB bootstrap skipped: failed to import python_position_to_kernel", exc_info=True)
            return state_json

        kernel_positions: dict[str, dict[str, Any]] = {}
        for symbol, py_pos in py_positions.items():
            try:
                kp = python_position_to_kernel(symbol, py_pos)
            except Exception:
                logger.debug("Kernel bootstrap conversion failed for %s", symbol, exc_info=True)
                continue
            if isinstance(kp, dict):
                clean = dict(kp)
                clean["symbol"] = str(symbol).upper()
                kernel_positions[str(symbol).upper()] = clean

        if not kernel_positions:
            return state_json

        state["positions"] = kernel_positions
        db_balance = self._load_latest_balance_from_db()
        if db_balance is not None:
            state["cash_usd"] = float(db_balance)
        state["timestamp_ms"] = int(now_ms())
        hydrated = json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        self._persist_state(hydrated)
        logger.warning(
            "Kernel state bootstrapped from DB positions: positions=%d cash=%s state_path=%s db=%s",
            len(kernel_positions),
            f"{db_balance:.2f}" if db_balance is not None else "unchanged",
            self._state_path,
            self._db_path or "",
        )
        return hydrated

    def _load_or_create_state(self) -> str:
        """Load kernel state from disk, or create fresh if missing/corrupt."""
        load_candidates_raw: list[str] = [self._state_path]
        if self._allow_legacy_state_fallback:
            load_candidates_raw.append(self._legacy_state_path)
        load_candidates: list[str] = []
        for candidate in load_candidates_raw:
            c = str(candidate or "").strip()
            if c and c not in load_candidates:
                load_candidates.append(c)
        for state_path in load_candidates:
            try:
                state_json = self._runtime.load_state(state_path)
                # Parse to extract log fields.
                try:
                    state = json.loads(state_json)
                    if not isinstance(state, dict):
                        logger.warning(
                            "Kernel state: expected dict, got %s; loaded from %s",
                            type(state).__name__,
                            state_path,
                        )
                        return state_json
                    ts_ms = int(state.get("timestamp_ms", 0))
                    positions = state.get("positions")
                    n_pos = len(positions) if isinstance(positions, dict) else 0
                    cash = float(state.get("cash_usd", 0.0))
                    age_s = max(0.0, (now_ms() - ts_ms) / 1000.0) if ts_ms > 0 else 0.0
                    logger.info(
                        "Kernel state loaded, age=%.1fs, positions=%d, cash=$%.2f",
                        age_s,
                        n_pos,
                        cash,
                    )
                    if age_s > 300.0:
                        logger.warning(
                            "Kernel state stale by %.0fs",
                            age_s,
                        )
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning("Kernel state metadata parsing failed: %s; loaded from %s", exc, state_path)
                if state_path != self._state_path:
                    self._persist_state(state_json)
                    logger.info(
                        "Kernel state migrated from %s to %s",
                        state_path,
                        self._state_path,
                    )
                return state_json
            except OSError:
                # File missing — normal on first run.
                continue
            except Exception:
                logger.error(
                    "Kernel state file corrupt, creating fresh: %s\n%s",
                    state_path,
                    traceback.format_exc(),
                )
        _seed = float(os.getenv("AI_QUANT_PAPER_BALANCE", "10000.0"))
        fresh = self._runtime.default_kernel_state_json(_seed, now_ms())
        logger.info("Kernel state created fresh")
        self._persist_state(fresh)
        return fresh

    def _persist_state(self, state_json: str) -> None:
        """Save kernel state to disk. Best-effort, never raises."""
        try:
            state_dir = Path(self._state_path).parent
            state_dir.mkdir(parents=True, exist_ok=True)
            self._runtime.save_state(state_json, self._state_path)
        except Exception:
            logger.warning(
                "Failed to persist kernel state: %s",
                traceback.format_exc(),
            )

    def _persist_exit_bounds(self, ts_ms: int, symbol: str, exit_bounds: dict, state_positions: dict) -> None:
        """Write exit tunnel row. Creates table lazily on first call. Best-effort."""
        import sqlite3

        pos = state_positions.get(symbol)
        if not isinstance(pos, dict):
            return
        entry_price = float(pos.get("avg_entry_price", 0))
        side = str(pos.get("side", ""))
        pos_type = "LONG" if side == "long" else ("SHORT" if side == "short" else "")
        if not pos_type or entry_price <= 0:
            return

        db_path = self._db_path
        if not db_path:
            return

        try:
            con = sqlite3.connect(db_path, timeout=5)
            try:
                if db_path not in KernelDecisionRustBindingProvider._tunnel_table_ready:
                    con.execute(
                        "CREATE TABLE IF NOT EXISTS exit_tunnel ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "ts_ms INTEGER NOT NULL, symbol TEXT NOT NULL,"
                        "upper_full REAL NOT NULL, upper_partial REAL,"
                        "lower_full REAL NOT NULL,"
                        "entry_price REAL NOT NULL, pos_type TEXT NOT NULL)"
                    )
                    con.execute(
                        "CREATE INDEX IF NOT EXISTS idx_exit_tunnel_sym_ts ON exit_tunnel(symbol, ts_ms)"
                    )
                    KernelDecisionRustBindingProvider._tunnel_table_ready.add(db_path)

                up = exit_bounds.get("upper_partial")
                con.execute(
                    "INSERT INTO exit_tunnel (ts_ms,symbol,upper_full,upper_partial,lower_full,entry_price,pos_type)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (
                        ts_ms,
                        symbol,
                        float(exit_bounds["upper_full"]),
                        float(up) if up is not None else None,
                        float(exit_bounds["lower_full"]),
                        entry_price,
                        pos_type,
                    ),
                )
                con.commit()
            finally:
                con.close()
        except Exception:
            logger.debug("exit_tunnel persist failed: %s", traceback.format_exc())

    def _load_raw_events(self) -> list[dict[str, Any]]:
        if not self._path:
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            return []
        except Exception:
            logger.warning("event file unreadable: %s", self._path, exc_info=True)
            return []

        if isinstance(raw, dict):
            if isinstance(raw.get("events"), list):
                return [item for item in raw["events"] if isinstance(item, Mapping)]
            if "schema_version" in raw and "symbol" in raw:
                return [raw]
            return []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, Mapping)]
        return []

    def _build_market_event(self, raw: Mapping[str, Any], *, now_ms_value: int) -> str | None:
        symbol = str(raw.get("symbol", "")).strip().upper()
        if not symbol:
            return None

        timestamp_ms = raw.get("timestamp_ms")
        try:
            timestamp_ms = int(timestamp_ms)
            if timestamp_ms <= 0:
                timestamp_ms = now_ms_value
        except (TypeError, ValueError):
            timestamp_ms = now_ms_value

        event_id = _normalise_kernel_event_id(raw.get("event_id"), self._event_id)
        self._event_id = max(self._event_id, event_id + 1)

        raw_signal = str(raw.get("signal", "")).strip().lower()
        if raw_signal in {"evaluate", "price_update", "funding", "buy", "sell", "neutral"}:
            # Pass-through for canonical MarketEvent payloads (evaluate/price_update/funding)
            # while still accepting legacy buy/sell/neutral forms.
            price = _normalise_kernel_price(raw.get("price"), default=0.0)
            if price <= 0.0:
                return None

            signal_text = raw_signal
            if signal_text in {"buy", "sell", "neutral"}:
                signal_text = signal_text

            payload: dict[str, Any] = {
                "schema_version": 1,
                "event_id": event_id,
                "timestamp_ms": timestamp_ms,
                "symbol": symbol,
                "signal": signal_text,
                "price": price,
            }

            notional_hint = _normalise_kernel_notional(
                raw.get("notional_hint_usd"),
                raw.get("target_size"),
                price,
            )
            if notional_hint > 0.0:
                payload["notional_hint_usd"] = notional_hint

            close_fraction_raw = raw.get("close_fraction")
            if close_fraction_raw is not None:
                try:
                    payload["close_fraction"] = float(close_fraction_raw)
                except (TypeError, ValueError):
                    pass

            fee_role_raw = str(raw.get("fee_role", "") or "").strip().lower()
            if fee_role_raw in {"maker", "taker"}:
                payload["fee_role"] = fee_role_raw

            if signal_text == "funding":
                funding_rate_raw = raw.get("funding_rate")
                if funding_rate_raw is not None:
                    payload["funding_rate"] = _finite_float_or_default(funding_rate_raw, 0.0)

            if signal_text == "evaluate":
                indicators = raw.get("indicators")
                gate_result = raw.get("gate_result")
                if not isinstance(indicators, Mapping) or not isinstance(gate_result, Mapping):
                    return None
                payload["indicators"] = dict(indicators)
                payload["gate_result"] = dict(gate_result)
                payload["ema_slow_slope_pct"] = _finite_float_or_default(raw.get("ema_slow_slope_pct"), 0.0)

            return json.dumps(payload, ensure_ascii=False)

        signal = _normalise_kernel_intent_signal(
            raw.get("signal"),
            raw_action=raw.get("action"),
            raw_kind=raw.get("kind"),
            raw_side=raw.get("side"),
        )
        if signal not in {"BUY", "SELL", "NEUTRAL"}:
            return None

        price = _normalise_kernel_price(
            raw.get("price"),
            default=0.0,
        )
        if price <= 0.0:
            return None

        notional_hint = _normalise_kernel_notional(
            raw.get("notional_hint_usd"),
            raw.get("target_size"),
            price,
        )

        payload = {
            "schema_version": 1,
            "event_id": event_id,
            "timestamp_ms": timestamp_ms,
            "symbol": symbol,
            "signal": signal.lower(),
            "price": price,
            "notional_hint_usd": notional_hint if notional_hint > 0.0 else None,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _intent_to_decision(
        self,
        decision: Mapping[str, Any],
        event_raw: Mapping[str, Any],
    ) -> KernelDecision | None:
        symbol = str(decision.get("symbol", "")).strip().upper()
        if not symbol:
            return None

        event_now_series = event_raw.get("now_series")
        if not isinstance(event_now_series, Mapping):
            event_now_series = event_raw.get("indicators")

        result = KernelDecision.from_raw(
            {
                "symbol": symbol,
                "action": decision.get("action"),
                "kind": decision.get("kind"),
                "side": decision.get("side"),
                "quantity": decision.get("quantity"),
                "price": decision.get("price"),
                "notional_usd": decision.get("notional_usd"),
                "notional_hint_usd": decision.get("notional_hint_usd"),
                "intent_id": decision.get("intent_id"),
                "signal": event_raw.get("signal"),
                "confidence": event_raw.get("confidence", "N/A"),
                "now_series": event_now_series,
                "entry_key": event_raw.get("entry_key", event_raw.get("event_id")),
                "reason": decision.get("reason"),
                "reason_code": decision.get("reason_code"),
            }
        )
        if result is None:
            return None

        decision_reason = str(decision.get("reason") or "").strip()
        if decision_reason:
            result.reason = decision_reason
        elif not result.reason:
            result.reason = f"kernel:{str(decision.get('kind', 'unknown')).strip().lower()}"

        decision_reason_code = str(decision.get("reason_code") or "").strip().lower()
        if decision_reason_code:
            result.reason_code = decision_reason_code
        return result

    def get_decisions(
        self,
        *,
        symbols: list[str],
        watchlist: list[str],
        open_symbols: list[str],
        market: Any,
        interval: str,
        lookback_bars: int,
        mode: str,
        not_ready_symbols: set[str],
        strategy: Any,
        now_ms: int,
    ) -> Iterable[KernelDecision]:
        del watchlist, market, interval, lookback_bars, mode

        scope_symbols = {str(sym).strip().upper() for sym in (symbols or []) if str(sym).strip()}
        open_symbol_set = {str(sym).strip().upper() for sym in (open_symbols or []) if str(sym).strip()}
        ready_block_symbols = {
            str(sym).strip().upper()
            for sym in (not_ready_symbols or set())
            if str(sym).strip() and str(sym).strip().upper() not in open_symbol_set
        }

        raw_events = self._load_raw_events()
        if not raw_events:
            return []

        decisions: list[KernelDecision] = []
        state_json = self._state_json

        for raw in raw_events:
            raw_symbol = str(raw.get("symbol", "")).strip().upper()
            if raw_symbol and scope_symbols and raw_symbol not in scope_symbols:
                continue
            if raw_symbol and raw_symbol in ready_block_symbols:
                continue

            event_json = self._build_market_event(raw, now_ms_value=int(now_ms or 0))
            if event_json is None:
                continue
            state_json_before_step = state_json
            try:
                params_json = self._resolve_params_json(symbol=raw_symbol, strategy=strategy)
            except Exception as exc:
                logger.warning(
                    "Kernel step skipped due to params resolution failure (symbol=%s): %s",
                    raw_symbol or "unknown",
                    exc,
                )
                continue
            exit_params_json = self._extract_exit_params_json(params_json)
            if exit_params_json and hasattr(self._runtime, "step_full"):
                try:
                    response = self._runtime.step_full(state_json, event_json, params_json, exit_params_json)
                except TypeError:
                    response = self._runtime.step_decision(state_json, event_json, params_json)
            else:
                response = self._runtime.step_decision(state_json, event_json, params_json)
            try:
                envelope = json.loads(response)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("kernel step response JSON parse failed: %s", exc)
                continue
            if not isinstance(envelope, dict):
                logger.warning(
                    "Kernel step response: expected dict, got %s",
                    type(envelope).__name__,
                )
                continue
            if not bool(envelope.get("ok", False)):
                continue
            decision_payload = envelope.get("decision")
            if not isinstance(decision_payload, dict):
                continue

            state_value = decision_payload.get("state")
            if not isinstance(state_value, dict):
                logger.warning(
                    "Kernel decision state: expected dict, got %s",
                    type(state_value).__name__,
                )
                continue
            state_json = json.dumps(state_value, ensure_ascii=False)
            self._state_json = state_json
            self._persist_state(state_json)

            # Persist exit tunnel bounds (diagnostic visualization data).
            diag = decision_payload.get("diagnostics")
            eb = diag.get("exit_bounds") if isinstance(diag, dict) else None
            state_positions_for_tunnel = state_value.get("positions", {})
            raw_signal = str(raw.get("signal", "")).strip().lower()
            if (
                not (isinstance(eb, dict) and eb.get("upper_full") is not None)
                and raw_signal == "evaluate"
            ):
                exit_params_json = self._extract_exit_params_json(params_json)
                if exit_params_json:
                    probe_eb = self._probe_exit_bounds_from_evaluate(
                        raw_event=raw,
                        state_json=state_json_before_step,
                        params_json=params_json,
                        exit_params_json=exit_params_json,
                        now_ms_value=int(now_ms or 0),
                    )
                    if isinstance(probe_eb, dict) and probe_eb.get("upper_full") is not None:
                        eb = probe_eb
            if isinstance(eb, dict) and eb.get("upper_full") is not None:
                self._persist_exit_bounds(
                    int(now_ms or 0), raw_symbol, eb, state_positions_for_tunnel
                )

            intents = decision_payload.get("intents", [])
            if not isinstance(intents, list):
                logger.warning(
                    "Kernel decision intents: expected list, got %s",
                    type(intents).__name__,
                )
                intents = []
            for raw_intent in intents:
                if not isinstance(raw_intent, Mapping):
                    continue
                dec = self._intent_to_decision(raw_intent, raw)
                if dec is not None:
                    decisions.append(dec)

        return decisions


class NoopDecisionProvider:
    def get_decisions(
        self,
        *,
        symbols: list[str],
        watchlist: list[str],
        open_symbols: list[str],
        market: Any,
        interval: str,
        lookback_bars: int,
        mode: str,
        not_ready_symbols: set[str],
        strategy: Any,
        now_ms: int,
    ) -> Iterable[KernelDecision]:
        del symbols, watchlist, open_symbols, market, interval, lookback_bars, mode, not_ready_symbols, strategy, now_ms
        return []


def _build_default_decision_provider(db_path: str | None = None) -> DecisionProvider:
    """Build the decision provider based on environment configuration.

    After AQC-825, the Python ``mei_alpha_v1.analyze()`` decision path has been
    removed.  The Rust kernel (``bt_runtime``) is the **only** decision source
    for live/paper/dry_live trading.  If it cannot be loaded the engine will
    fail-fast with a clear error rather than silently falling back to
    non-SSOT providers.

    Accepted values for ``AI_QUANT_KERNEL_DECISION_PROVIDER``:

    * ``rust`` / ``kernel_only`` (default) -- Rust kernel via ``bt_runtime``
      with ``AI_QUANT_KERNEL_DECISION_FILE`` as event input
    * ``none`` / ``noop`` -- no-op (explicit non-trading/testing only)

    Raises
    ------
    SystemExit
        If ``bt_runtime`` cannot be imported or provider mode is unsupported.
    RuntimeError
        If configuration is invalid.
    """
    path = os.getenv("AI_QUANT_KERNEL_DECISION_FILE")
    provider_mode = str(os.getenv("AI_QUANT_KERNEL_DECISION_PROVIDER", "") or "").strip().lower()

    if provider_mode in {"none", "noop"}:
        return NoopDecisionProvider()

    if provider_mode == "python":
        logger.fatal(
            "FATAL: AI_QUANT_KERNEL_DECISION_PROVIDER=python is no longer supported. "
            "The PythonAnalyzeDecisionProvider has been removed (AQC-825). "
            "Use 'rust', 'kernel_only', or 'none'."
        )
        raise SystemExit(1)

    if provider_mode in {"file", "candle"}:
        logger.fatal(
            "FATAL: AI_QUANT_KERNEL_DECISION_PROVIDER=%s is disabled for runtime SSOT hardening. "
            "Use 'rust'/'kernel_only' for trading modes.",
            provider_mode,
        )
        raise SystemExit(1)

    if provider_mode in {"rust", "kernel_only", ""}:
        if not path:
            logger.fatal(
                "FATAL: AI_QUANT_KERNEL_DECISION_FILE is required for Rust decision input. "
                "Runtime SSOT mode does not allow implicit/empty event sources."
            )
            raise SystemExit(1)
        try:
            return KernelDecisionRustBindingProvider(path=path, db_path=db_path)
        except Exception as exc:
            logger.fatal(
                "FATAL: bt_runtime extension unavailable — cannot initialise "
                "Rust kernel decision provider. The Rust kernel is REQUIRED "
                "for paper/live/dry_live SSOT. Error: %s",
                exc,
            )
            raise SystemExit(1) from exc

    # Unrecognised provider mode — hard error.
    logger.fatal(
        "FATAL: Unrecognised AI_QUANT_KERNEL_DECISION_PROVIDER=%r. "
        "Accepted values: rust, kernel_only, none, noop.",
        provider_mode,
    )
    raise SystemExit(1)


class ModePlugin(Protocol):
    def before_iteration(self) -> None: ...

    def after_iteration(self) -> None: ...


@dataclass
class EngineStats:
    loops: int = 0
    loop_errors: int = 0
    ws_restarts: int = 0
    last_heartbeat_s: float = 0.0
    last_ws_restart_s: float = 0.0


class UnifiedEngine:
    """One orchestration loop for both paper and live.

    v5 changes focus on scaling and stability:
    - Do not build candle DataFrames for every symbol on every loop.
      Instead poll a cheap per-symbol "candle key" (close time or open time),
      and only pull a full DF when the key changes.
    - Avoid fetching mid/funding for symbols that have nothing to do this loop.
      Exits always run for open positions. Entries only run for real entry candidates.

    The engine delegates:
    - Decision generation to the Rust kernel via DecisionProvider
    - Execution and position accounting to PaperTrader / LiveTrader
    """

    def __init__(
        self,
        *,
        trader: Any,
        strategy: StrategyManager,
        market: MarketDataHub,
        interval: str,
        lookback_bars: int,
        mode: str | None = None,
        mode_plugin: ModePlugin | None = None,
        decision_provider: DecisionProvider | None = None,
    ):
        self.trader = trader
        self.strategy = strategy
        self.market = market
        self.interval = str(interval)
        self.lookback_bars = int(lookback_bars)
        self.mode = str(mode or os.getenv("AI_QUANT_MODE", "paper") or "paper").strip().lower()
        self.mode_plugin = mode_plugin
        self.decision_provider = decision_provider or _build_default_decision_provider()
        if self.mode in {"paper", "live", "dry_live"}:
            provider_name = type(self.decision_provider).__name__
            rust_ssot_providers = {"KernelDecisionRustBindingProvider"}
            if provider_name not in rust_ssot_providers:
                logger.fatal(
                    "FATAL: mode=%s requires a Rust decision provider for SSOT. "
                    "Got provider=%s. Allowed providers=%s",
                    self.mode,
                    provider_name,
                    ",".join(sorted(rust_ssot_providers)),
                )
                raise SystemExit(1)

        self.stats = EngineStats()

        # Entry de-dup. Key is derived from the candle we are acting on.
        self._last_entry_key: dict[str, int] = {}
        self._last_entry_key_open_pos_count: dict[str, int] = {}

        # Cached strategy outputs to avoid re-running ta.*.
        # Stored per symbol:
        # - key: candle key we last analyzed (close ms if signal_on_close else open ms)
        # - sig/conf/now: outputs of the decision provider
        self._analysis_cache: dict[str, dict[str, Any]] = {}

        # BTC anchor context cache.
        self._btc_ctx: dict[str, Any] = {"key": None, "btc_bullish": None}

        # Market Breadth: % of watchlist with bullish EMA alignment (computed from cached analysis).
        self._market_breadth_pct: float | None = None

        # Global regime gate (trend vs chop). When OFF, entries are blocked (exits still run).
        self._regime_gate_on: bool = True
        self._regime_gate_reason: str = "disabled"
        self._regime_gate_last_key: int | None = None
        self._regime_gate_last_logged_on: bool | None = None

        # WS staleness control
        self._stale_strikes: int = 0
        self._ws_restart_window_started_s: float = 0.0
        self._ws_restart_count_in_window: int = 0

        # ── Config: YAML `engine:` section + env var fallback ──

        # --- Interval: YAML engine.interval → env AI_QUANT_INTERVAL → constructor arg ---
        # NOT hot-reloadable (WS subscriptions, candle readiness tied to it).
        _init_engine_cfg = (self.strategy.get_config("__GLOBAL__") or {}).get("engine") or {}
        _yaml_interval = _init_engine_cfg.get("interval")
        if _yaml_interval is not None:
            self.interval = str(_yaml_interval).strip().lower()
        # else: keep constructor value (from env var or default)

        # --- Helper: read engine config with YAML first, env fallback ---
        def _ecfg(cfg: dict) -> dict:
            """Get fresh engine: section from a config dict."""
            return cfg.get("engine") or {}

        def _cfg_float(ecfg: dict, yaml_key: str, env_key: str, default: float) -> float:
            v = ecfg.get(yaml_key)
            if v is not None:
                return _finite_float_or_default(v, default)
            e = os.getenv(f"AI_QUANT_{env_key}", "")
            return _finite_float_or_default(e, default) if e.strip() else float(default)

        def _cfg_int(ecfg: dict, yaml_key: str, env_key: str, default: int) -> int:
            return int(_cfg_float(ecfg, yaml_key, env_key, float(default)))

        def _cfg_str(ecfg: dict, yaml_key: str, env_key: str, default: str) -> str:
            v = ecfg.get(yaml_key)
            if v is not None:
                return str(v).strip().lower()
            return str(os.getenv(f"AI_QUANT_{env_key}", default) or default).strip().lower()

        def _cfg_bool(ecfg: dict, yaml_key: str, env_key: str, default: bool) -> bool:
            v = ecfg.get(yaml_key)
            if v is not None:
                return bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes")
            return _env_bool(f"AI_QUANT_{env_key}", default)

        self._cfg_float = _cfg_float
        self._cfg_int = _cfg_int
        self._cfg_str = _cfg_str
        self._cfg_bool = _cfg_bool
        self._ecfg = _ecfg

        # --- Init-time engine config (read once) ---
        self._heartbeat_every_s = _cfg_float(_init_engine_cfg, "heartbeat_every_s", "HEARTBEAT_SECS", 30.0)
        self._loop_target_s = _cfg_float(_init_engine_cfg, "loop_target_s", "LOOP_TARGET_SECS", 5.0)

        self._ws_stale_mids_s = float(os.getenv("AI_QUANT_WS_STALE_MIDS_S", "60"))
        self._ws_stale_candle_s = float(os.getenv("AI_QUANT_WS_STALE_CANDLES_S", str(2 * 60 * 60)))
        self._ws_stale_bbo_s = float(os.getenv("AI_QUANT_WS_STALE_BBO_S", "120"))

        self._ws_stale_strikes_to_restart = int(os.getenv("AI_QUANT_WS_STALE_STRIKES", "2"))
        self._ws_restart_cooldown_s = float(os.getenv("AI_QUANT_WS_RESTART_COOLDOWN_S", "60"))
        self._ws_restart_window_s = float(os.getenv("AI_QUANT_WS_RESTART_WINDOW_S", "600"))
        self._ws_restart_max_in_window = int(os.getenv("AI_QUANT_WS_RESTART_MAX_IN_WINDOW", "5"))

        # In "sidecar-only" market-data mode we must not fetch HL REST meta in the engine loop.
        self._rest_enabled = _env_bool("AI_QUANT_REST_ENABLE", True)

        # Performance and behavior knobs (init-time, not hot-reloadable)
        self._signal_on_candle_close = _cfg_bool(
            _init_engine_cfg, "signal_on_candle_close", "SIGNAL_ON_CANDLE_CLOSE", True
        )
        self._candle_close_grace_ms = _cfg_int(_init_engine_cfg, "candle_close_grace_ms", "CANDLE_CLOSE_GRACE_MS", 2000)

        # --- Hot-reloadable engine params: entry_interval, exit_interval ---
        # These are refreshed each loop via _refresh_engine_config().
        self._entry_interval: str = ""  # e.g. "3m" — determines reanalyze cadence
        self._exit_interval: str = ""  # e.g. "3m" — determines exit candle DB
        self._reanalyze_interval_s: float = 0.0
        self._last_analyze_ts: dict[str, int] = {}  # symbol → wall-clock bucket
        self._exit_reanalyze_interval_s: float = 0.0
        self._last_exit_ts: dict[str, int] = {}  # symbol → wall-clock bucket (exit)
        self._refresh_engine_config()  # populate from initial YAML

        # Optional: audit sampling for NEUTRAL signals (helps debug "why no entries" regimes).
        try:
            self._neutral_audit_sample_every_s = float(os.getenv("AI_QUANT_NEUTRAL_AUDIT_SAMPLE_EVERY_S", "0") or 0.0)
        except (TypeError, ValueError):
            self._neutral_audit_sample_every_s = 0.0
        try:
            self._neutral_audit_sample_symbols = int(os.getenv("AI_QUANT_NEUTRAL_AUDIT_SAMPLE_SYMBOLS", "5") or 5)
        except (TypeError, ValueError):
            self._neutral_audit_sample_symbols = 5
        self._neutral_audit_sample_every_s = float(max(0.0, self._neutral_audit_sample_every_s))
        self._neutral_audit_sample_symbols = int(max(0, min(250, self._neutral_audit_sample_symbols)))
        self._neutral_audit_last_s: float = 0.0
        self._neutral_audit_cursor: int = 0

        # Optional: print analyze() gates/tags periodically, even when signal is NEUTRAL.
        # Useful for "why didn't we trade this big move" debugging without writing to SQLite.
        raw_debug_syms = str(os.getenv("AI_QUANT_DEBUG_GATES_SYMBOLS", "") or "").strip()
        self._debug_gates_symbols: set[str] = set()
        if raw_debug_syms:
            self._debug_gates_symbols = {s.strip().upper() for s in raw_debug_syms.split(",") if s.strip()}
        try:
            self._debug_gates_every_s = float(os.getenv("AI_QUANT_DEBUG_GATES_EVERY_S", "0") or 0.0)
        except (TypeError, ValueError):
            self._debug_gates_every_s = 0.0
        self._debug_gates_every_s = float(max(0.0, self._debug_gates_every_s))

        # Entry timing guard (close-mode only).
        # If the engine restarts (or stalls) it may act on an older closed candle key.
        # This prevents "late" entries when the candle-close signal is too old.
        max_delay_ms, clamped = _resolve_entry_max_delay_ms(
            raw_ms=os.getenv("AI_QUANT_ENTRY_MAX_DELAY_MS"),
            raw_s=os.getenv("AI_QUANT_ENTRY_MAX_DELAY_S"),
        )
        if clamped:
            logger.warning(
                "AI_QUANT_ENTRY_MAX_DELAY exceeds hard max; clamped to %dms",
                int(ENTRY_MAX_DELAY_MS_HARD_MAX),
            )
        self._entry_max_delay_ms = int(max_delay_ms)

        # Optional: if a symbol was blocked by max_open_positions, allow re-try within the same candle
        # only when open position count decreased.
        self._entry_retry_on_capacity = _env_bool("AI_QUANT_ENTRY_RETRY_ON_CAPACITY", False)

        self._interval_ms = _interval_to_ms(self.interval)

    def _ws_is_stale(self, *, symbols: list[str]) -> tuple[bool, str]:
        h = self.market.ws_health(symbols=symbols, interval=self.interval)

        mids_age = getattr(h, "mids_age_s", None)
        candle_age = getattr(h, "candle_age_s", None)
        bbo_age = getattr(h, "bbo_age_s", None)

        if mids_age is None:
            if bool(getattr(self.market, "_sidecar_only", False)):
                logger.debug("mids_age_s is None in sidecar-only mode; skipping mids staleness check")
            else:
                return True, "mids_age_s is None"
        try:
            if mids_age is not None and float(mids_age) > self._ws_stale_mids_s:
                return True, f"mids_age_s={float(mids_age):.1f}s"
        except (TypeError, ValueError):
            return True, "mids_age_s not numeric"

        try:
            if candle_age is not None and float(candle_age) > self._ws_stale_candle_s:
                return True, f"candle_age_s={float(candle_age):.1f}s"
        except (TypeError, ValueError):
            logger.debug("candle_age not numeric, ignoring staleness check")

        # BBO can be optional. Treat it as stale only when enabled (threshold > 0) and numeric.
        try:
            if self._ws_stale_bbo_s > 0 and bbo_age is not None and float(bbo_age) > self._ws_stale_bbo_s:
                return True, f"bbo_age_s={float(bbo_age):.1f}s"
        except (TypeError, ValueError):
            logger.debug("bbo_age not numeric, ignoring staleness check")

        return False, "ok"

    def _maybe_restart_ws(self, *, active_symbols: list[str], candle_limit: int, user: str | None) -> None:
        stale, reason = self._ws_is_stale(symbols=active_symbols)
        if stale:
            self._stale_strikes += 1
        else:
            self._stale_strikes = 0

        if self._stale_strikes < self._ws_stale_strikes_to_restart:
            return

        now_s = time.time()

        if self.stats.last_ws_restart_s and (now_s - self.stats.last_ws_restart_s) < self._ws_restart_cooldown_s:
            return

        if (not self._ws_restart_window_started_s) or (
            (now_s - self._ws_restart_window_started_s) > self._ws_restart_window_s
        ):
            self._ws_restart_window_started_s = now_s
            self._ws_restart_count_in_window = 0

        self._ws_restart_count_in_window += 1
        self.stats.last_ws_restart_s = now_s

        logger.info(
            f"🔄 WS restart. stale_strikes={self._stale_strikes} reason={reason}. "
            f"restart_count_in_window={self._ws_restart_count_in_window}/{self._ws_restart_max_in_window}"
        )

        self._stale_strikes = 0
        self.stats.ws_restarts += 1

        try:
            self.market.restart_ws(
                symbols=active_symbols,
                interval=self.interval,
                candle_limit=int(candle_limit),
                user=user,
            )
        except Exception:
            logger.warning(f"⚠️ WS restart failed\n{traceback.format_exc()}")
            return

        if self._ws_restart_count_in_window >= self._ws_restart_max_in_window:
            raise SystemExit(
                f"Too many WS restarts within {self._ws_restart_window_s:.0f}s window. Exiting for supervisor restart."
            )

    def _prepare_df_for_analysis(self, df: pd.DataFrame | None) -> pd.DataFrame | None:
        """Returns the dataframe slice we want to feed into analyze().

        If AI_QUANT_SIGNAL_ON_CANDLE_CLOSE=1, we act on the most recent closed candle.
        The HL candle stream frequently updates the in-progress candle. Dropping the last row
        when it is not yet closed makes entries stable and avoids intrabar noise.
        """
        if df is None or df.empty:
            return df

        if not self._signal_on_candle_close:
            return df

        if "T" in df.columns:
            try:
                t_close = df["T"].iloc[-1]
                if pd.notna(t_close):
                    if now_ms() < (int(t_close) - int(self._candle_close_grace_ms)):
                        if len(df) >= 6:
                            return df.iloc[:-1]
            except Exception:
                logger.debug("close-mode trim failed, returning full df", exc_info=True)
                return df

        return df

    def _analysis_key(self, df: pd.DataFrame | None) -> int | None:
        if df is None or df.empty:
            return None

        if self._signal_on_candle_close and "T" in df.columns:
            try:
                t_close = df["T"].iloc[-1]
                if pd.notna(t_close):
                    return int(t_close)
            except Exception:
                logger.debug("failed to extract close-mode analysis key from T column", exc_info=True)

        try:
            return int(df["timestamp"].iloc[-1])
        except Exception:
            logger.debug("failed to extract analysis key from timestamp column", exc_info=True)
            return None

    def _entry_is_too_late(self, *, entry_key: int, now_ts_ms: int) -> bool:
        """Returns True when acting on an old candle close should be skipped."""
        if not self._signal_on_candle_close:
            return False
        max_delay = int(self._entry_max_delay_ms or 0)
        if max_delay <= 0:
            return False
        try:
            delay = int(now_ts_ms) - int(entry_key)
        except (TypeError, ValueError):
            return False
        if delay < 0:
            return False
        return delay > max_delay

    def _candle_key_hint(self, symbol: str) -> int | None:
        """Cheap per-symbol candle key used to decide whether we need to fetch a full DF.

        In close-mode, returns the close time of the last closed candle.
        In open-mode, returns the open time of the latest candle (may be in-progress).
        """
        try:
            if self._signal_on_candle_close:
                return self.market.get_last_closed_candle_key(
                    symbol,
                    interval=self.interval,
                    grace_ms=int(self._candle_close_grace_ms),
                )
            return self.market.get_latest_candle_open_key(symbol, interval=self.interval)
        except Exception:
            logger.debug("failed to get candle key for %s", symbol, exc_info=True)
            return None

    def _refresh_engine_config(self) -> None:
        """Re-read hot-reloadable engine params from YAML (entry_interval, exit_interval).

        Called at init and after every strategy.maybe_reload() in the main loop.
        """
        ecfg = self._ecfg((self.strategy.get_config("__GLOBAL__") or {}))

        # entry_interval — determines reanalyze cadence
        entry_iv = self._cfg_str(ecfg, "entry_interval", "ENTRY_INTERVAL", "")
        if not entry_iv or entry_iv == self.interval:
            # No sub-bar entry interval — reanalyze every main-interval bar
            self._entry_interval = self.interval
            self._reanalyze_interval_s = 0.0  # disabled — rely on candle-close key change
        else:
            self._entry_interval = entry_iv
            ms = _interval_to_ms(entry_iv)
            self._reanalyze_interval_s = float(ms) / 1000.0 if ms > 0 else 0.0

        # exit_interval — determines which candle DB to use for exit price
        # AND the cadence for exit checks (separate from entry reanalyze cadence).
        exit_iv = self._cfg_str(ecfg, "exit_interval", "EXIT_PRICE_SOURCE", "mid")
        # back-compat: strip "_candle" suffix (e.g. "3m_candle" → "3m")
        exit_iv = exit_iv.replace("_candle", "")
        self._exit_interval = exit_iv
        if exit_iv and exit_iv != "mid":
            exit_ms = _interval_to_ms(exit_iv)
            self._exit_reanalyze_interval_s = float(exit_ms) / 1000.0 if exit_ms > 0 else 0.0
        else:
            # No sub-bar exit interval — fall back to entry cadence
            self._exit_reanalyze_interval_s = self._reanalyze_interval_s

    def _reanalyze_due(self, symbol: str) -> bool:
        """Return True when the wall-clock interval bucket has changed for *symbol*.

        Aligned to :00 boundaries so that a 60s interval triggers at the start
        of each new minute — matching exactly when 1m candles close.
        """
        if self._reanalyze_interval_s <= 0:
            return False
        current_bucket = int(time.time()) // int(self._reanalyze_interval_s)
        last_bucket = self._last_analyze_ts.get(symbol, -1)
        return current_bucket != last_bucket

    def _mark_analyzed(self, symbol: str) -> None:
        """Record the current wall-clock bucket for *symbol*."""
        if self._reanalyze_interval_s <= 0:
            return
        self._last_analyze_ts[symbol] = int(time.time()) // int(self._reanalyze_interval_s)

    def _exit_reanalyze_due(self, symbol: str) -> bool:
        """Return True when the exit-interval wall-clock bucket has changed for *symbol*."""
        if self._exit_reanalyze_interval_s <= 0:
            return False
        current_bucket = int(time.time()) // int(self._exit_reanalyze_interval_s)
        last_bucket = self._last_exit_ts.get(symbol, -1)
        if current_bucket != last_bucket:
            self._last_exit_ts[symbol] = current_bucket
            return True
        return False

    def _attach_strategy_snapshot(self, *, symbol: str, now_series: Any) -> None:
        try:
            audit = now_series.get("audit")
        except Exception:
            audit = None

        if not isinstance(audit, dict):
            return

        snap = self.strategy.snapshot
        try:
            audit2 = dict(audit)
            audit2["strategy"] = {
                "version": str(snap.version or ""),
                "overrides_sha1": str(snap.overrides_sha1 or ""),
            }
            now_series["audit"] = audit2
        except Exception:
            logger.debug("failed to attach strategy snapshot for %s", symbol, exc_info=True)
            return

    def _build_runtime_kernel_events(
        self,
        *,
        mei_alpha_v1: Any,
        symbols: list[str],
        open_symbols: set[str],
        not_ready_symbols: set[str],
        now_ts_ms: int,
    ) -> list[dict[str, Any]]:
        """Materialise canonical Rust MarketEvent payloads for kernel-only mode.

        Events are generated from runtime candles and include full evaluate payloads
        (indicator snapshot + gate result + EMA-slow slope). For open positions where
        candles are temporarily unavailable, a price_update fallback is emitted so
        exit checks can still advance on price movement.
        """
        events: list[dict[str, Any]] = []
        btc_bullish = self._btc_ctx.get("btc_bullish")
        event_id_seed = int(max(1, int(now_ts_ms))) * 1000

        for idx, sym in enumerate(symbols):
            sym_u = str(sym or "").strip().upper()
            if not sym_u:
                continue
            if sym_u in not_ready_symbols and sym_u not in open_symbols:
                continue

            df = self.market.get_candles_df(sym_u, interval=self.interval, min_rows=self.lookback_bars)
            if df is None or df.empty or len(df) < 20:
                # Fallback path for open symbols: emit a price_update so exits can keep evaluating.
                if sym_u in open_symbols:
                    quote = self.market.get_mid_price(sym_u, max_age_s=10.0, interval=self.interval)
                    px = _finite_float_or_default(getattr(quote, "price", 0.0) if quote is not None else 0.0, 0.0)
                    if px > 0.0:
                        events.append(
                            {
                                "schema_version": 1,
                                "event_id": event_id_seed + idx + 1,
                                "timestamp_ms": int(now_ts_ms),
                                "symbol": sym_u,
                                "signal": "price_update",
                                "price": px,
                            }
                        )
                continue

            try:
                cfg = self.strategy.get_config(sym_u) or self.strategy.get_config("__GLOBAL__") or {}
            except Exception:
                cfg = {}

            snap = mei_alpha_v1.build_indicator_snapshot(df, symbol=sym_u, config=cfg)
            if not isinstance(snap, dict):
                continue

            ts_ms = int(_finite_float_or_default(snap.get("t"), float(now_ts_ms)))
            if ts_ms <= 0:
                ts_ms = int(now_ts_ms)

            close_px = _finite_float_or_default(
                snap.get("close"),
                _finite_float_or_default(df["Close"].iloc[-1], 0.0),
            )
            if close_px <= 0.0:
                continue

            ema_slow_slope_pct = _finite_float_or_default(
                mei_alpha_v1.compute_ema_slow_slope(df, cfg=cfg),
                0.0,
            )
            gate_result = mei_alpha_v1.build_gate_result(
                snap,
                sym_u,
                cfg=cfg,
                btc_bullish=btc_bullish,
                ema_slow_slope_pct=float(ema_slow_slope_pct),
            )
            if not isinstance(gate_result, dict):
                continue

            events.append(
                {
                    "schema_version": 1,
                    "event_id": event_id_seed + idx + 1,
                    "timestamp_ms": ts_ms,
                    "symbol": sym_u,
                    "signal": "evaluate",
                    "price": float(close_px),
                    "indicators": snap,
                    "gate_result": gate_result,
                    "ema_slow_slope_pct": float(ema_slow_slope_pct),
                }
            )

        return events

    def _write_runtime_kernel_events_file(self, *, path: str, events: list[dict[str, Any]]) -> None:
        """Atomically write runtime kernel events for KernelDecisionRustBindingProvider."""
        out_path = str(path or "").strip()
        if not out_path:
            return
        p = Path(out_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {"events": events}
        blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        max_bytes = _kernel_decision_file_max_bytes()
        if len(blob) > max_bytes:
            logger.warning(
                "runtime kernel events exceed max payload (%d > %d bytes); writing empty batch",
                int(len(blob)),
                int(max_bytes),
            )
            payload = {"events": []}
            blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")

        tmp = p.with_name(f".{p.name}.tmp.{os.getpid()}")
        try:
            with open(tmp, "wb") as fh:
                fh.write(blob)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, p)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def _update_regime_gate(
        self,
        *,
        mei_alpha_v1: Any,
        btc_key_hint: int | None,
        btc_df: pd.DataFrame | None,
    ) -> None:
        """Update the global regime gate state.

        The gate is designed to flip only on a schedule (typically once per main bar),
        keyed off the BTC candle key. When the gate is OFF, entries are blocked
        (exits still run).
        """
        try:
            key = int(btc_key_hint) if btc_key_hint is not None else None
        except (TypeError, ValueError):
            key = None

        # Avoid recomputing every loop; BTC key only changes once per main bar (in close-mode).
        if key is not None and self._regime_gate_last_key is not None and int(key) == int(self._regime_gate_last_key):
            return
        if key is None and self._regime_gate_last_key is None and self.stats.loops > 1:
            # No key available: keep the previous state to avoid flapping.
            return
        self._regime_gate_last_key = key

        cfg = mei_alpha_v1.get_strategy_config("BTC") or {}
        rc = cfg.get("market_regime") if isinstance(cfg, dict) else None
        rc = rc if isinstance(rc, dict) else {}

        # Sweep-compatible alias: enable_regime_filter → enable_regime_gate
        # The sweep spec (Rust side) uses enable_regime_filter; the Python engine
        # historically used enable_regime_gate. Accept both, sweep name takes precedence.
        enabled = bool(rc.get("enable_regime_filter", rc.get("enable_regime_gate", False)))
        fail_open = bool(rc.get("regime_gate_fail_open", False))

        if not enabled:
            new_on = True
            new_reason = "disabled"
        else:
            # Breadth chop zone: inside => gate OFF; outside => potential trend regime.
            # Sweep-compatible aliases: breadth_block_long_below → regime_gate_breadth_low
            #                          breadth_block_short_above → regime_gate_breadth_high
            # Sweep names take precedence when set.
            try:
                chop_lo = float(
                    rc.get(
                        "breadth_block_long_below",
                        rc.get("regime_gate_breadth_low", rc.get("auto_reverse_breadth_low", 10.0)),
                    )
                )
            except (TypeError, ValueError):
                chop_lo = 10.0
            try:
                chop_hi = float(
                    rc.get(
                        "breadth_block_short_above",
                        rc.get("regime_gate_breadth_high", rc.get("auto_reverse_breadth_high", 90.0)),
                    )
                )
            except (TypeError, ValueError):
                chop_hi = 90.0

            try:
                btc_adx_min = float(rc.get("regime_gate_btc_adx_min", 20.0))
            except (TypeError, ValueError):
                btc_adx_min = 20.0
            try:
                btc_atr_pct_min = float(rc.get("regime_gate_btc_atr_pct_min", 0.003))
            except (TypeError, ValueError):
                btc_atr_pct_min = 0.003

            breadth = self._market_breadth_pct
            try:
                b = float(breadth) if breadth is not None else None
            except (TypeError, ValueError):
                b = None

            if b is None:
                new_on = bool(fail_open)
                new_reason = "breadth_missing"
            elif chop_lo <= b <= chop_hi:
                new_on = False
                new_reason = "breadth_chop"
            else:
                # BTC metrics: prefer cached analysis output, fall back to lightweight indicator compute.
                adx: float | None = None
                atr_pct: float | None = None

                btc_now = None
                try:
                    bc = self._analysis_cache.get("BTC")
                    btc_now = bc.get("now") if isinstance(bc, dict) else None
                except Exception:
                    btc_now = None

                if isinstance(btc_now, dict):
                    try:
                        adx = float(btc_now.get("ADX") or 0.0)
                    except (TypeError, ValueError):
                        adx = None
                    try:
                        atr = float(btc_now.get("ATR") or 0.0)
                        close = float(btc_now.get("Close") or 0.0)
                        if close > 0:
                            atr_pct = atr / close
                    except (TypeError, ValueError, ZeroDivisionError):
                        atr_pct = None

                if (adx is None or atr_pct is None) and btc_df is not None and (not btc_df.empty):
                    ind = cfg.get("indicators") if isinstance(cfg, dict) else None
                    ind = ind if isinstance(ind, dict) else {}
                    try:
                        adx_w = int(ind.get("adx_window", 14))
                    except (TypeError, ValueError):
                        adx_w = 14
                    try:
                        atr_w = int(ind.get("atr_window", 14))
                    except (TypeError, ValueError):
                        atr_w = 14

                    try:
                        adx_obj = mei_alpha_v1.ta.trend.ADXIndicator(
                            btc_df["High"],
                            btc_df["Low"],
                            btc_df["Close"],
                            window=int(adx_w),
                        )
                        adx_s = adx_obj.adx()
                        if not adx_s.empty:
                            _adx_v = float(adx_s.iloc[-1])
                            if pd.notna(_adx_v):
                                adx = _adx_v
                    except Exception:
                        logger.debug("regime gate ADX indicator computation failed", exc_info=True)

                    try:
                        atr_s = mei_alpha_v1.ta.volatility.average_true_range(
                            btc_df["High"],
                            btc_df["Low"],
                            btc_df["Close"],
                            window=int(atr_w),
                        )
                        if not atr_s.empty:
                            _atr_v = float(atr_s.iloc[-1])
                            if pd.notna(_atr_v):
                                atr = _atr_v
                                close = float(btc_df["Close"].iloc[-1])
                                if close > 0:
                                    atr_pct = atr / close
                    except Exception:
                        logger.debug("regime gate ATR indicator computation failed", exc_info=True)

                if adx is None or atr_pct is None:
                    new_on = bool(fail_open)
                    new_reason = "btc_metrics_missing"
                elif float(adx) < float(btc_adx_min):
                    new_on = False
                    new_reason = "btc_adx_low"
                elif float(atr_pct) < float(btc_atr_pct_min):
                    new_on = False
                    new_reason = "btc_atr_low"
                else:
                    new_on = True
                    new_reason = "trend_ok"

        self._regime_gate_on = bool(new_on)
        self._regime_gate_reason = str(new_reason or "none").strip() or "none"

        if self._regime_gate_last_logged_on is None or bool(self._regime_gate_on) != bool(
            self._regime_gate_last_logged_on
        ):
            self._regime_gate_last_logged_on = bool(self._regime_gate_on)
            try:
                mei_alpha_v1.log_audit_event(
                    "ENGINE",
                    "REGIME_GATE_STATE",
                    data={
                        "interval": str(self.interval),
                        "gate_on": bool(self._regime_gate_on),
                        "reason": str(self._regime_gate_reason),
                        "btc_key": key,
                        "breadth_pct": self._market_breadth_pct,
                    },
                )
            except Exception:
                logger.debug("failed to log regime gate audit event", exc_info=True)
            try:
                logger.info(
                    f"🧭 regime gate {'ON' if self._regime_gate_on else 'OFF'} reason={self._regime_gate_reason}"
                )
            except Exception:
                logger.debug("failed to log regime gate state change", exc_info=True)

    def _decision_execute_trade(
        self,
        symbol: str,
        signal: str,
        price: float,
        timestamp: int,
        confidence: str,
        *,
        atr: float = 0.0,
        indicators=None,
        action: str = "",
        target_size: float | None = None,
        reason: str | None = None,
    ) -> None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return

        act = str(action or "").strip().upper()
        if act not in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
            return

        try:
            target_size_f = float(target_size) if target_size is not None else None
        except (TypeError, ValueError):
            target_size_f = None

        # Detect execute_trade capability surface (cached).
        if not hasattr(self, "_trader_accepts_action") or not hasattr(self, "_trader_accepts_mode"):
            import inspect

            try:
                _sig = inspect.signature(self.trader.execute_trade)
                self._trader_accepts_action = "action" in _sig.parameters
                self._trader_accepts_mode = "mode" in _sig.parameters
            except (ValueError, TypeError):
                self._trader_accepts_action = False
                self._trader_accepts_mode = False

        if self._trader_accepts_action:
            kwargs = {
                "atr": atr,
                "indicators": indicators,
                "action": act,
                "target_size": target_size_f,
                "reason": reason,
            }
            if self._trader_accepts_mode:
                kwargs["mode"] = self.mode
            return self.trader.execute_trade(
                symbol,
                signal,
                price,
                timestamp,
                confidence,
                **kwargs,
            )

        if act == "ADD":
            fn = getattr(self.trader, "add_to_position", None)
            if callable(fn):
                try:
                    return fn(
                        sym, price, timestamp, confidence, atr=atr, indicators=indicators, target_size=target_size_f
                    )
                except TypeError:
                    return fn(sym, price, timestamp, confidence, atr=atr, indicators=indicators)
            return

        if act in {"CLOSE", "REDUCE"}:
            if sym not in (
                (self.trader.positions or {}) if isinstance(getattr(self.trader, "positions", None), dict) else {}
            ):
                logger.debug("Skipping %s for %s: not in positions", act, sym)
                return
            pos = (self.trader.positions or {}).get(sym, {})
            try:
                pos_size = float(pos.get("size") or 0.0)
            except (TypeError, ValueError):
                pos_size = 0.0
            try:
                reduce_sz = float(target_size_f) if target_size_f is not None else pos_size
            except (TypeError, ValueError):
                reduce_sz = pos_size
            reduce_sz = float(max(0.0, min(pos_size, reduce_sz)))

            if act == "CLOSE":
                fn = getattr(self.trader, "close_position", None)
                if callable(fn):
                    try:
                        return fn(
                            sym,
                            price,
                            timestamp,
                            reason=str(reason or "Kernel CLOSE"),
                            meta={"reason": str(reason or "").strip() or None},
                        )
                    except TypeError:
                        return fn(sym, price, timestamp, str(reason or "Kernel CLOSE"))
                return
            fn = getattr(self.trader, "reduce_position", None)
            if callable(fn):
                return fn(
                    sym,
                    reduce_sz,
                    price,
                    timestamp,
                    str(reason or "Kernel REDUCE"),
                    confidence=confidence,
                    meta={"reason": str(reason or "").strip() or None},
                )
            return

        logger.warning(
            "Skipping decision for %s: trader.execute_trade does not support action-aware dispatch in SSOT mode",
            sym,
        )
        return

    def run_forever(self) -> None:
        import signal

        import strategy.mei_alpha_v1 as mei_alpha_v1

        try:
            import exchange.meta as hyperliquid_meta
        except Exception:
            logger.debug("exchange.meta import failed, hyperliquid_meta unavailable", exc_info=True)
            hyperliquid_meta = None

        _shutdown_requested = False

        def _handle_sigterm(signum, frame):
            nonlocal _shutdown_requested
            _shutdown_requested = True

        signal.signal(signal.SIGTERM, _handle_sigterm)

        while True:
            if _shutdown_requested:
                logger.info("SIGTERM received — graceful shutdown")
                break

            loop_start = time.time()
            self.stats.loops += 1

            try:
                # Hot reload YAML only.
                self.strategy.maybe_reload()
                self._refresh_engine_config()

                if self.mode_plugin is not None:
                    self.mode_plugin.before_iteration()

                watchlist = self.strategy.get_watchlist()

                # v5.076: Exclude stable/pegged assets from watchlist (hot-reloadable).
                try:
                    _global_cfg = mei_alpha_v1.get_strategy_config("__GLOBAL__") or {}
                    _wl_exclude_raw = _global_cfg.get("watchlist_exclude") or []
                    if isinstance(_wl_exclude_raw, list) and _wl_exclude_raw:
                        _wl_exclude = {str(s).upper() for s in _wl_exclude_raw if str(s).strip()}
                        if _wl_exclude:
                            watchlist = [s for s in watchlist if s.upper() not in _wl_exclude]
                except Exception:
                    logger.debug("failed to apply watchlist_exclude filter", exc_info=True)

                watch_set = {s.upper() for s in watchlist}

                neutral_sample_syms: set[str] = set()
                if self._neutral_audit_sample_every_s > 0:
                    now_s = time.time()
                    if (now_s - float(self._neutral_audit_last_s or 0.0)) >= float(self._neutral_audit_sample_every_s):
                        self._neutral_audit_last_s = now_s
                        wl = [str(s or "").upper() for s in (watchlist or []) if str(s or "").strip()]
                        if wl and self._neutral_audit_sample_symbols > 0:
                            k = max(1, min(int(self._neutral_audit_sample_symbols), len(wl)))
                            start = int(self._neutral_audit_cursor) % len(wl)
                            for i in range(k):
                                neutral_sample_syms.add(wl[(start + i) % len(wl)])
                            self._neutral_audit_cursor = (start + k) % len(wl)

                try:
                    open_syms = list((self.trader.positions or {}).keys())
                except Exception:
                    logger.debug("failed to list open position symbols", exc_info=True)
                    open_syms = []

                active_symbols = list(dict.fromkeys(["BTC"] + watchlist + open_syms))

                user = getattr(getattr(self.trader, "secrets", None), "main_address", None)
                candle_limit = self.lookback_bars + 50

                try:
                    self.market.ensure(
                        symbols=active_symbols,
                        interval=self.interval,
                        candle_limit=candle_limit,
                        user=user,
                    )
                except Exception as e:
                    logger.error("market.ensure() failed: %s", e, exc_info=True)

                try:
                    self._maybe_restart_ws(active_symbols=active_symbols, candle_limit=candle_limit, user=user)
                except SystemExit:
                    raise
                except Exception:
                    logger.warning(f"⚠️ WS health check failed\n{traceback.format_exc()}")

                # Candle readiness gate (sidecar only):
                # - Entries/adds are paused until candles are fully backfilled for the selected interval.
                # - Exit coverage remains enabled for open positions.
                not_ready_set: set[str] = set()
                try:
                    _ready, not_ready = self.market.candles_ready(symbols=active_symbols, interval=self.interval)
                    not_ready_set = {str(s).upper() for s in (not_ready or [])}
                except Exception:
                    logger.warning("candles_ready check failed, pausing entries as precaution", exc_info=True)
                    # If we cannot determine readiness, be conservative and pause entries for watchlist symbols.
                    not_ready_set = {str(s).upper() for s in watchlist}

                # If we are sampling NEUTRAL audits this loop, also persist a single candle-readiness snapshot
                # so "no trades" can be distinguished between "no signals" vs "candles not ready".
                if neutral_sample_syms and not_ready_set:
                    # Optional: include a small health sample to make the audit actionable (e.g. new listings
                    # that legitimately have fewer historical candles).
                    not_ready_health = None
                    try:
                        sample_syms = sorted(list(not_ready_set))[:10]
                        health = self.market.candles_health(symbols=sample_syms, interval=self.interval)
                        if isinstance(health, dict):
                            items = health.get("items")
                            if isinstance(items, list):
                                out = []
                                for it in items:
                                    if not isinstance(it, dict):
                                        continue
                                    out.append(
                                        {
                                            "symbol": it.get("symbol"),
                                            "ready": it.get("ready"),
                                            "have_count": it.get("have_count"),
                                            "expected_count": it.get("expected_count"),
                                            "min_t": it.get("min_t"),
                                            "max_t": it.get("max_t"),
                                            "last_ok_backfill_ms": it.get("last_ok_backfill_ms"),
                                            "last_err_backfill": it.get("last_err_backfill"),
                                        }
                                    )
                                not_ready_health = out
                    except Exception:
                        logger.debug("failed to gather candles_health sample for not-ready symbols", exc_info=True)
                        not_ready_health = None

                    try:
                        mei_alpha_v1.log_audit_event(
                            "ENGINE",
                            "CANDLES_NOT_READY_SAMPLE",
                            data={
                                "mode": str(getattr(self, "mode", os.getenv("AI_QUANT_MODE", "paper") or "paper")),
                                "interval": str(self.interval),
                                "watchlist_n": int(len(watchlist or [])),
                                "active_symbols_n": int(len(active_symbols or [])),
                                "lookback_bars": int(self.lookback_bars),
                                "candle_limit": int(candle_limit),
                                "ready_n": int(max(0, len(active_symbols or []) - len(not_ready_set))),
                                "not_ready_n": int(len(not_ready_set)),
                                "not_ready": sorted(list(not_ready_set))[:200],
                                "not_ready_health": not_ready_health,
                            },
                        )
                    except Exception:
                        logger.debug("failed to log CANDLES_NOT_READY_SAMPLE audit event", exc_info=True)

                # BTC context (anchor) only refreshes when BTC candle key changes.
                btc_key_hint = self._candle_key_hint("BTC")
                btc_df_raw: pd.DataFrame | None = None
                btc_df: pd.DataFrame | None = None
                btc_bullish = self._btc_ctx.get("btc_bullish")

                if ("BTC" not in not_ready_set) and (
                    self._reanalyze_due("BTC") or (btc_key_hint is None) or (btc_key_hint != self._btc_ctx.get("key"))
                ):
                    btc_df_raw = self.market.get_candles_df("BTC", interval=self.interval, min_rows=self.lookback_bars)
                    btc_df = self._prepare_df_for_analysis(btc_df_raw)
                    btc_bullish = None
                    if btc_df is not None and not btc_df.empty:
                        try:
                            _btc_ema_s = mei_alpha_v1.ta.trend.ema_indicator(btc_df["Close"], window=50)
                            if _btc_ema_s is not None and not _btc_ema_s.empty:
                                btc_ema_slow = _btc_ema_s.iloc[-1]
                                if mei_alpha_v1.pd.notna(btc_ema_slow):
                                    btc_bullish = btc_df["Close"].iloc[-1] > btc_ema_slow
                        except Exception:
                            logger.debug("BTC EMA bullish computation failed", exc_info=True)
                            btc_bullish = None

                    self._btc_ctx["key"] = btc_key_hint
                    self._btc_ctx["btc_bullish"] = btc_bullish
                    self._mark_analyzed("BTC")

                # Market Breadth: % of watchlist with bullish EMA alignment (Fast > Slow).
                # Primary: use cached analysis from kernel decisions.
                # Fallback: compute directly from candle DB when cache is empty
                # (avoids breadth_missing after restart while historical candles exist).
                _breadth_pos = 0
                _breadth_total = 0
                for _bsym in watch_set:
                    _bc = self._analysis_cache.get(_bsym)
                    if not isinstance(_bc, dict):
                        _bc = None
                    _bnow = _bc.get("now") if _bc else None
                    _ef: float = 0.0
                    _es: float = 0.0
                    if isinstance(_bnow, dict):
                        try:
                            _ef = float(_bnow.get("EMA_fast", 0.0) or 0.0)
                            _es = float(_bnow.get("EMA_slow", 0.0) or 0.0)
                        except (TypeError, ValueError):
                            _ef = _es = 0.0
                    # Fallback: compute EMA from candle DB when cache has no EMA.
                    if not (_ef > 0 and _es > 0):
                        try:
                            _bdf = self.market.get_candles_df(
                                _bsym, interval=self.interval, min_rows=self.lookback_bars
                            )
                            if _bdf is not None and len(_bdf) >= 20:
                                _gcfg = self.strategy.get_config("__GLOBAL__") or {}
                                _ind_cfg = _gcfg.get("indicators") or {}
                                _fw = int(_ind_cfg.get("ema_fast_window", 20))
                                _sw = int(_ind_cfg.get("ema_slow_window", 50))
                                _ema_f_s = mei_alpha_v1.ta.trend.ema_indicator(_bdf["Close"], window=_fw)
                                _ema_s_s = mei_alpha_v1.ta.trend.ema_indicator(_bdf["Close"], window=_sw)
                                if (
                                    _ema_f_s is not None
                                    and not _ema_f_s.empty
                                    and _ema_s_s is not None
                                    and not _ema_s_s.empty
                                ):
                                    _ef = float(_ema_f_s.iloc[-1])
                                    _es = float(_ema_s_s.iloc[-1])
                        except Exception:
                            logger.debug("breadth EMA fallback failed for %s", _bsym, exc_info=True)
                            _ef = _es = 0.0
                    try:
                        if _ef > 0 and _es > 0:
                            _breadth_total += 1
                            if _ef > _es:
                                _breadth_pos += 1
                    except (TypeError, ValueError):
                        continue
                self._market_breadth_pct = ((_breadth_pos / _breadth_total) * 100.0) if _breadth_total > 0 else None

                # Regime gate: a global binary switch (trend OK vs chop) that blocks entries when OFF.
                try:
                    self._update_regime_gate(mei_alpha_v1=mei_alpha_v1, btc_key_hint=btc_key_hint, btc_df=btc_df)
                except Exception:
                    logger.warning("regime gate update failed", exc_info=True)

                # Phase 1: Python exit checks removed.
                # Runtime exit decisions are Rust-kernel SSOT across paper/live/dry_live.

                # Phase 2: Execute explicit kernel decisions (OPEN/ADD/CLOSE/REDUCE) ordered by score.
                decision_exec: list[KernelDecision] = []
                try:
                    open_sym_set = {str(s).upper() for s in open_syms}
                    decision_symbols = sorted(
                        {
                            str(s).upper()
                            for s in list(watchlist) + list(open_syms)
                            if str(s).strip()
                        }
                    )
                    # Keep candle-readiness guard for entry paths, but never suppress
                    # decision coverage for already-open symbols (exit safety).
                    provider_not_ready = {str(s).upper() for s in not_ready_set if str(s).upper() not in open_sym_set}
                    decision_now_ms = now_ms()

                    # Kernel-only runtime event writer:
                    # materialise evaluate/price_update MarketEvents into the configured
                    # kernel decision file before the Rust provider reads it.
                    if type(self.decision_provider).__name__ == "KernelDecisionRustBindingProvider":
                        decision_path = str(os.getenv("AI_QUANT_KERNEL_DECISION_FILE", "") or "").strip()
                        if decision_path:
                            runtime_events = self._build_runtime_kernel_events(
                                mei_alpha_v1=mei_alpha_v1,
                                symbols=decision_symbols,
                                open_symbols=open_sym_set,
                                not_ready_symbols=provider_not_ready,
                                now_ts_ms=int(decision_now_ms),
                            )
                            self._write_runtime_kernel_events_file(path=decision_path, events=runtime_events)

                    logger.debug(f"DEBUG: calling decision_provider.get_decisions for {len(decision_symbols)} symbols")
                    for dec in self.decision_provider.get_decisions(
                        symbols=decision_symbols,
                        watchlist=watchlist,
                        open_symbols=open_syms,
                        market=self.market,
                        interval=self.interval,
                        lookback_bars=self.lookback_bars,
                        mode=self.mode,
                        not_ready_symbols=provider_not_ready,
                        strategy=self.strategy,
                        now_ms=int(decision_now_ms),
                    ):
                        if dec is None:
                            continue
                        sym_u = str(dec.symbol).upper().strip()
                        if not sym_u:
                            continue

                        act = str(dec.action or "").strip().upper()
                        if act not in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
                            continue

                        now_series = dec.now_series if isinstance(dec.now_series, dict) else {}
                        try:
                            now_series = dict(now_series)
                        except (TypeError, ValueError):
                            now_series = {}

                        if not isinstance(now_series, dict):
                            now_series = {}
                        if not now_series:
                            now_series = {"Close": None, "is_anomaly": False}

                        self._attach_strategy_snapshot(symbol=sym_u, now_series=now_series)

                        # Store the latest kernel output for reuse by downstream checks / audit.
                        self._analysis_cache[sym_u] = {
                            "key": int(dec.entry_key) if dec.entry_key is not None else None,
                            "sig": str(dec.signal),
                            "conf": str(dec.confidence),
                            "now": dict(now_series),
                            "computed_at_s": time.time(),
                            "action": act,
                        }

                        # Open-side decisions are always watchlist-controlled.
                        if act in {"OPEN", "ADD"} and sym_u not in watch_set:
                            continue

                        # Skip decision entries where candle keys are not ready.
                        if act in {"OPEN", "ADD"} and sym_u in not_ready_set:
                            logger.debug(f"🕒 skip {sym_u} {act}: candles not ready")
                            continue

                        decision_exec.append(dec)
                except Exception:
                    logger.warning(f"⚠️ Engine decision provider error: {traceback.format_exc()}")

                decision_exec.sort(
                    key=lambda item: (
                        -(item.score or 0.0),
                        str(item.symbol),
                    )
                )

                for dec in decision_exec:
                    try:
                        sym_u = str(dec.symbol).upper().strip()
                        act = str(dec.action or "").strip().upper()
                        if act not in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
                            continue

                        signal = str(dec.signal or "").upper().strip()
                        conf = str(dec.confidence or "N/A")
                        entry_key = dec.entry_key
                        open_pos_count = int(dec.open_pos_count or 0)

                        now_series = dec.now_series if isinstance(dec.now_series, dict) else {}
                        try:
                            now_series = dict(now_series)
                        except (TypeError, ValueError):
                            now_series = {}
                        if not isinstance(now_series, dict):
                            now_series = {}
                        if not now_series:
                            now_series = {"Close": None, "is_anomaly": False}
                        if dec.reason_code:
                            now_series["_kernel_reason_code"] = str(dec.reason_code).strip().lower()
                        self._attach_strategy_snapshot(symbol=sym_u, now_series=now_series)

                        if self._rest_enabled and hyperliquid_meta is not None:
                            try:
                                now_series["funding_rate"] = float(hyperliquid_meta.get_funding_rate(sym_u) or 0.0)
                            except Exception:
                                logger.debug("funding_rate fetch failed for %s (decision)", sym_u, exc_info=True)
                                now_series["funding_rate"] = 0.0
                        else:
                            now_series["funding_rate"] = 0.0

                        quote = None
                        if act in {"OPEN", "ADD"}:
                            _entry_iv = self._entry_interval
                            if _entry_iv and _entry_iv != self.interval and _entry_iv != "mid":
                                try:
                                    df_entry = self.market.get_candles_df(sym_u, interval=_entry_iv, min_rows=1)
                                    if df_entry is not None and not df_entry.empty:
                                        current_price = float(df_entry["Close"].iloc[-1])
                                    else:
                                        quote = self.market.get_mid_price(sym_u, max_age_s=10.0, interval=self.interval)
                                        current_price = (
                                            float(quote.price)
                                            if quote is not None
                                            else float(now_series.get("Close") or 0.0)
                                        )
                                except Exception:
                                    logger.debug(
                                        "entry candle price fetch failed for %s, falling back to mid",
                                        sym_u,
                                        exc_info=True,
                                    )
                                    quote = self.market.get_mid_price(sym_u, max_age_s=10.0, interval=self.interval)
                                    current_price = (
                                        float(quote.price)
                                        if quote is not None
                                        else float(now_series.get("Close") or 0.0)
                                    )
                            else:
                                quote = self.market.get_mid_price(sym_u, max_age_s=10.0, interval=self.interval)
                                current_price = (
                                    float(quote.price) if quote is not None else float(now_series.get("Close") or 0.0)
                                )
                        else:
                            quote = self.market.get_mid_price(sym_u, max_age_s=10.0, interval=self.interval)
                            current_price = (
                                float(quote.price) if quote is not None else float(now_series.get("Close") or 0.0)
                            )

                        # WARN-E3: Guard against zero price when all sources fail.
                        if current_price <= 0:
                            logger.warning(f"[{sym_u}] all price sources failed, skipping {act}")
                            _cde = _get_decision_event_fn()
                            if _cde:
                                try:
                                    _cde(
                                        sym_u,
                                        "gate_block",
                                        "blocked",
                                        "gate_evaluation",
                                        action_taken="blocked",
                                        context={"reason": "zero_price", "action": act},
                                    )
                                except Exception:
                                    logger.debug("decision event (zero_price) failed for %s", sym_u, exc_info=True)
                            continue

                        if act in {"OPEN", "ADD"}:
                            if entry_key is not None:
                                now_ts = now_ms()
                                if self._entry_is_too_late(entry_key=int(entry_key), now_ts_ms=int(now_ts)):
                                    logger.debug(
                                        f"🕒 skip {sym_u} {act}: stale candle-close signal key={int(entry_key)}"
                                    )
                                    _cde = _get_decision_event_fn()
                                    if _cde:
                                        try:
                                            _cde(
                                                sym_u,
                                                "gate_block",
                                                "blocked",
                                                "gate_evaluation",
                                                action_taken="blocked",
                                                context={"reason": "stale_candle", "entry_key": int(entry_key)},
                                            )
                                        except Exception:
                                            logger.debug(
                                                "decision event (stale_candle) failed for %s", sym_u, exc_info=True
                                            )
                                    continue

                                last_key = self._last_entry_key.get(sym_u)
                                if last_key is not None and int(last_key) == int(entry_key):
                                    if self._entry_retry_on_capacity:
                                        last_open_count = self._last_entry_key_open_pos_count.get(sym_u)
                                        if last_open_count is not None and int(len(self.trader.positions or {})) < int(
                                            last_open_count
                                        ):
                                            self._last_entry_key_open_pos_count[sym_u] = int(open_pos_count)
                                        else:
                                            _cde = _get_decision_event_fn()
                                            if _cde:
                                                try:
                                                    _cde(
                                                        sym_u,
                                                        "gate_block",
                                                        "blocked",
                                                        "gate_evaluation",
                                                        action_taken="blocked",
                                                        context={"reason": "dedup_key", "entry_key": int(entry_key)},
                                                    )
                                                except Exception:
                                                    logger.debug(
                                                        "decision event (dedup_key) failed for %s", sym_u, exc_info=True
                                                    )
                                            continue
                                    else:
                                        _cde = _get_decision_event_fn()
                                        if _cde:
                                            try:
                                                _cde(
                                                    sym_u,
                                                    "gate_block",
                                                    "blocked",
                                                    "gate_evaluation",
                                                    action_taken="blocked",
                                                    context={"reason": "dedup_key", "entry_key": int(entry_key)},
                                                )
                                            except Exception:
                                                logger.debug(
                                                    "decision event (dedup_key) failed for %s", sym_u, exc_info=True
                                                )
                                        continue

                            if self._rest_enabled and hyperliquid_meta is not None:
                                try:
                                    now_series["funding_rate"] = float(hyperliquid_meta.get_funding_rate(sym_u) or 0.0)
                                except Exception:
                                    logger.debug("funding_rate fetch failed for %s (entry exec)", sym_u, exc_info=True)
                                    now_series["funding_rate"] = 0.0
                            else:
                                now_series["funding_rate"] = 0.0

                            self._attach_strategy_snapshot(symbol=sym_u, now_series=now_series)

                            if isinstance(now_series, dict):
                                try:
                                    if quote is not None:
                                        now_series["quote"] = {
                                            "source": str(getattr(quote, "source", "")),
                                            "age_s": float(getattr(quote, "age_s", 0.0) or 0.0),
                                        }
                                except Exception:
                                    logger.debug(
                                        "failed to attach quote metadata for %s (entry exec)", sym_u, exc_info=True
                                    )

                            _did = None
                            _cde = _get_decision_event_fn()
                            if _cde:
                                try:
                                    _did = _cde(
                                        sym_u,
                                        "entry_signal",
                                        "executed",
                                        "execution",
                                        action_taken=act.lower(),
                                        context={
                                            "confidence": dec.confidence,
                                            "action": act,
                                            "source": "kernel_candle",
                                        },
                                    )
                                except Exception:
                                    logger.debug("decision event (entry_signal) failed for %s", sym_u, exc_info=True)

                            self._decision_execute_trade(
                                sym_u,
                                signal,
                                current_price,
                                int(entry_key or now_ms()),
                                conf,
                                atr=float(now_series.get("ATR") or 0.0),
                                indicators=now_series,
                                action=act,
                                target_size=dec.target_size,
                                reason=dec.reason,
                            )

                            # TODO(AQC-801): link_decision_to_trade requires trade_id
                            # from _record_trade(); needs _record_trade to return id first.

                            # BUG-E1: Set dedup key AFTER trade execution so a
                            # gate-blocked entry can retry on the next tick.
                            if entry_key is not None and sym_u in (self.trader.positions or {}):
                                self._last_entry_key[sym_u] = int(entry_key)
                                self._last_entry_key_open_pos_count[sym_u] = open_pos_count

                        elif act in {"CLOSE", "REDUCE"}:
                            _did = None
                            _cde = _get_decision_event_fn()
                            if _cde:
                                try:
                                    _did = _cde(
                                        sym_u,
                                        "exit_check",
                                        "executed",
                                        "execution",
                                        action_taken=act.lower(),
                                        context={
                                            "confidence": dec.confidence,
                                            "action": act,
                                            "source": "kernel_candle",
                                        },
                                    )
                                except Exception:
                                    logger.debug("decision event (exit_check) failed for %s", sym_u, exc_info=True)

                            self._decision_execute_trade(
                                sym_u,
                                signal,
                                current_price,
                                now_ms(),
                                conf,
                                atr=float(now_series.get("ATR") or 0.0),
                                indicators=now_series,
                                action=act,
                                target_size=dec.target_size,
                                reason=dec.reason,
                            )

                            # TODO(AQC-801): link_decision_to_trade requires trade_id
                            # from _record_trade(); needs _record_trade to return id first.
                    except SystemExit:
                        raise
                    except Exception:
                        logger.warning(f"⚠️ Engine decision execution error: {dec.symbol}\n{traceback.format_exc()}")
                        continue

                if self.mode_plugin is not None:
                    self.mode_plugin.after_iteration()

                if (time.time() - self.stats.last_heartbeat_s) >= self._heartbeat_every_s:
                    snap = self.strategy.snapshot
                    h = self.market.health(symbols=active_symbols, interval=self.interval)

                    try:
                        open_pos = len(self.trader.positions or {})
                    except Exception:
                        logger.debug("failed to count open positions for heartbeat", exc_info=True)
                        open_pos = 0

                    loop_s = time.time() - loop_start
                    _btc_cfg = mei_alpha_v1.get_strategy_config("BTC") or {}
                    _rc = (_btc_cfg.get("market_regime") or {}) if isinstance(_btc_cfg, dict) else {}
                    _tc = (_btc_cfg.get("trade") or {}) if isinstance(_btc_cfg, dict) else {}
                    try:
                        _size_mult = float(_tc.get("size_multiplier", 1.0))
                    except (TypeError, ValueError):
                        _size_mult = 1.0
                    _auto_rev_on = (
                        bool(_rc.get("enable_auto_reverse", False))
                        and self._market_breadth_pct is not None
                        and float(_rc.get("auto_reverse_breadth_low", 20.0))
                        <= self._market_breadth_pct
                        <= float(_rc.get("auto_reverse_breadth_high", 80.0))
                    )
                    cfg_id = ""
                    try:
                        from .event_logger import current_config_id

                        cfg_id = str(current_config_id() or "")
                    except Exception:
                        logger.debug("failed to get current config id for heartbeat", exc_info=True)
                        cfg_id = ""

                    risk = getattr(self.trader, "risk", None)
                    try:
                        kill_mode = str(getattr(risk, "kill_mode", "off") or "off").strip().lower()
                    except Exception:
                        logger.debug("failed to read kill_mode from risk tracker", exc_info=True)
                        kill_mode = "off"
                    try:
                        kill_reason = str(getattr(risk, "kill_reason", "") or "").strip() or "none"
                    except Exception:
                        logger.debug("failed to read kill_reason from risk tracker", exc_info=True)
                        kill_reason = "none"

                    try:
                        strategy_mode = str(os.getenv("AI_QUANT_STRATEGY_MODE", "") or "").strip().lower() or "none"
                    except Exception:
                        logger.debug("failed to read AI_QUANT_STRATEGY_MODE", exc_info=True)
                        strategy_mode = "none"

                    slip_enabled = 0
                    slip_n = 0
                    slip_win = 0
                    slip_thr_bps_s = "0"
                    slip_last_bps_s = "none"
                    slip_median_bps_s = "none"
                    try:
                        fn = getattr(risk, "slippage_guard_stats", None) if risk is not None else None
                        st = fn() if callable(fn) else {}
                        if isinstance(st, dict):
                            slip_enabled = 1 if bool(st.get("enabled")) else 0
                            slip_n = int(st.get("n") or 0)
                            slip_win = int(st.get("window_fills") or 0)
                            thr = st.get("threshold_median_bps")
                            if thr is not None:
                                slip_thr_bps_s = f"{float(thr):.3f}"
                            last = st.get("last_bps")
                            if last is not None:
                                slip_last_bps_s = f"{float(last):.3f}"
                            med = st.get("median_bps")
                            if med is not None:
                                slip_median_bps_s = f"{float(med):.3f}"
                    except Exception:
                        logger.debug("failed to gather slippage guard stats for heartbeat", exc_info=True)
                    logger.info(
                        f"🫀 engine ok. loops={self.stats.loops} errors={self.stats.loop_errors} "
                        f"symbols={len(active_symbols)} open_pos={open_pos} loop={loop_s:.2f}s "
                        f"size_mult={float(_size_mult):g} "
                        f"ws_connected={h.get('connected')} ws_thread_alive={h.get('thread_alive')} "
                        f"ws_restarts={self.stats.ws_restarts} "
                        f"kill={kill_mode} kill_reason={kill_reason} "
                        f"strategy_mode={strategy_mode} "
                        f"regime_gate={'on' if self._regime_gate_on else 'off'} regime_reason={self._regime_gate_reason} "
                        f"slip_enabled={slip_enabled} slip_n={slip_n} slip_win={slip_win} slip_thr_bps={slip_thr_bps_s} "
                        f"slip_last_bps={slip_last_bps_s} slip_median_bps={slip_median_bps_s} "
                        f"signal_on_close={int(self._signal_on_candle_close)} entry_iv={self._entry_interval} exit_iv={self._exit_interval} reanalyze_s={self._reanalyze_interval_s:.0f} exit_reanalyze_s={self._exit_reanalyze_interval_s:.0f} "
                        f"breadth={f'{self._market_breadth_pct:.1f}%' if self._market_breadth_pct is not None else 'n/a'} "
                        f"auto_rev={'ON' if _auto_rev_on else 'OFF'} "
                        f"config_id={cfg_id or 'none'} "
                        f"strategy_sha1={str(snap.overrides_sha1 or '')[:8]} version={snap.version or 'n/a'}"
                    )
                    self.stats.last_heartbeat_s = time.time()

            except SystemExit:
                raise
            except Exception:
                self.stats.loop_errors += 1
                logger.error(f"🔥 Engine loop error\n{traceback.format_exc()}")
            finally:
                if _shutdown_requested:
                    continue
                # Align sleep to wall-clock boundaries (e.g., :00 for 60s target).
                # This ensures loops fire at predictable times matching candle closes.
                now = time.time()
                interval = int(self._loop_target_s) or 1
                next_boundary = ((int(now) // interval) + 1) * interval
                sleep_s = max(0.1, next_boundary - now)
                # Sleep in short chunks so SIGTERM can stop promptly even during boundary sleep.
                deadline = now + sleep_s
                while not _shutdown_requested:
                    remain = deadline - time.time()
                    if remain <= 0:
                        break
                    time.sleep(min(0.25, remain))
