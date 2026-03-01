"""Unified daemon entrypoint (paper + live).

Usage:
  AI_QUANT_MODE=paper python -m engine.daemon
  AI_QUANT_MODE=dry_live python -m engine.daemon
  AI_QUANT_MODE=live python -m engine.daemon

What this replaces:
- trader_daemon.py (paper loop)
- trader_daemon_live.py (live loop)

The goal is to keep ONE orchestration loop, and let PaperTrader / LiveTrader focus on:
- strategy decision logic
- execution (paper vs real orders)

YAML config hot-reload is handled by StrategyManager, without reloading mei_alpha_v1 each loop.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import time
from collections import deque
from pathlib import Path

from .core import UnifiedEngine, _build_default_decision_provider
from .market_data import MarketDataHub
from .strategy_manager import StrategyManager
from .oms import LiveOms
from .oms_reconciler import LiveOmsReconciler
from .risk import RiskManager
from . import alerting

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _mode() -> str:
    return str(os.getenv("AI_QUANT_MODE", "paper") or "paper").strip().lower()


def _default_secrets_path() -> str:
    return str(Path("~/.config/openclaw/ai-quant-secrets.json").expanduser())


def _norm_strategy_mode(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    if s in {"mode1", "m1"}:
        return "primary"
    if s in {"mode2", "m2"}:
        return "fallback"
    if s in {"mode3", "m3", "safety", "safe"}:
        return "conservative"
    if s in {"halt", "pause", "paused"}:
        return "flat"
    return s


def _strategy_mode_file() -> Path:
    p = str(os.getenv("AI_QUANT_STRATEGY_MODE_FILE", "") or "").strip()
    if p:
        return Path(p).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    return (root / "artifacts" / "state" / "strategy_mode.txt").resolve()


def _read_code_version() -> str:
    try:
        version_path = Path(__file__).resolve().parents[1] / "VERSION"
        return str(version_path.read_text(encoding="utf-8").strip() or "unknown")
    except Exception:
        return "unknown"


def _build_run_fingerprint(
    *,
    strategy: StrategyManager,
    mode: str,
    interval: str,
    lookback_bars: int,
) -> tuple[str, dict[str, object]]:
    snap = strategy.snapshot
    try:
        watchlist = sorted({str(s).upper() for s in strategy.get_watchlist() if str(s).strip()})
    except Exception:
        watchlist = []

    payload: dict[str, object] = {
        "mode": str(mode),
        "interval": str(interval),
        "lookback_bars": int(lookback_bars),
        "code_version": _read_code_version(),
        "strategy_yaml_path": str(getattr(snap, "yaml_path", "") or ""),
        "strategy_yaml_mtime": getattr(snap, "yaml_mtime", None),
        "strategy_overrides_sha1": str(getattr(snap, "overrides_sha1", "") or ""),
        "strategy_version": str(getattr(snap, "version", "") or ""),
        "watchlist": watchlist,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return fingerprint, payload


def _ws_fills_overflow_path() -> Path:
    p = str(os.getenv("AI_QUANT_LIVE_DROPPED_FILLS_PATH", "") or "").strip()
    if p:
        return Path(p).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    return (root / "artifacts" / "state" / "ws_fills_overflow.jsonl").resolve()


def _read_strategy_mode_file(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return _norm_strategy_mode(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return ""


def _atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(str(text), encoding="utf-8")
    os.replace(str(tmp), str(path))


class StrategyModePolicy:
    """Automatic strategy-mode switching (Primary/Fallback/Conservative/Flat).

    This policy is intentionally conservative:
    - It only steps down (no automatic step-up).
    - It triggers on new kill events (kill_since_s changes).
    - It persists the selected mode to a local file so restarts can pick it up.
    """

    _ORDER = ["primary", "fallback", "conservative", "flat"]

    def __init__(self, *, risk: RiskManager | None):
        self._risk = risk
        self._enabled = _env_bool("AI_QUANT_MODE_SWITCH_ENABLE", False)
        self._exit_on_restart_required = _env_bool("AI_QUANT_MODE_SWITCH_EXIT_ON_RESTART_REQUIRED", False)
        self._mode_file = _strategy_mode_file()
        self._last_handled_kill_since_s: float | None = None
        self._last_switch_s: float = 0.0
        try:
            self._cooldown_s = float(os.getenv("AI_QUANT_MODE_SWITCH_COOLDOWN_S", "0") or 0)
        except Exception:
            self._cooldown_s = 0.0

    def _current_mode(self) -> str:
        cur = _norm_strategy_mode(str(os.getenv("AI_QUANT_STRATEGY_MODE", "") or ""))
        if cur:
            return cur
        # If env is not set, fall back to the persisted file (if present).
        return _read_strategy_mode_file(self._mode_file) or "primary"

    def _step_down(self, cur: str) -> str:
        cur = _norm_strategy_mode(cur) or "primary"
        if cur not in self._ORDER:
            cur = "primary"
        i = self._ORDER.index(cur)
        return self._ORDER[min(i + 1, len(self._ORDER) - 1)]

    def maybe_switch(self) -> None:
        if not self._enabled:
            return
        r = self._risk
        if r is None:
            return

        km = str(getattr(r, "kill_mode", "off") or "off").strip().lower()
        if km == "off":
            return
        kr = str(getattr(r, "kill_reason", "") or "").strip() or "none"
        ks = getattr(r, "kill_since_s", None)
        try:
            ks = None if ks is None else float(ks)
        except Exception:
            ks = None
        if ks is None:
            return

        if self._last_handled_kill_since_s is not None and float(ks) == float(self._last_handled_kill_since_s):
            return

        now_s = time.time()
        if self._cooldown_s > 0 and (now_s - float(self._last_switch_s or 0.0)) < float(self._cooldown_s):
            # Suppress rapid-fire switches, but mark the kill as handled to avoid log spam.
            self._last_handled_kill_since_s = float(ks)
            return

        cur = self._current_mode()
        # v1 policy: always step down on a new kill event.
        target = self._step_down(cur)
        self._last_handled_kill_since_s = float(ks)

        if target == cur:
            return

        os.environ["AI_QUANT_STRATEGY_MODE"] = str(target)
        try:
            _atomic_write_text(self._mode_file, str(target) + "\n")
        except Exception:
            pass

        self._last_switch_s = now_s

        # Log as a structured event (best-effort).
        try:
            from .event_logger import emit_event

            emit_event(
                kind="MODE_SWITCH",
                data={
                    "from": str(cur),
                    "to": str(target),
                    "trigger": "risk_kill",
                    "kill_mode": str(km),
                    "kill_reason": str(kr),
                    "kill_since_s": float(ks),
                    "restart_required": bool(cur == "primary" or target == "primary"),
                },
            )
        except Exception:
            pass

        print(f"🧭 mode switch: {cur} -> {target} (kill={km} reason={kr})")

        if bool(self._exit_on_restart_required) and bool(cur == "primary" or target == "primary"):
            raise SystemExit(f"Mode switch requires restart (interval change likely): {cur} -> {target}")


def _default_db_path() -> str:
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, "..", "trading_engine.db"))
    except (OSError, ValueError):
        return "trading_engine.db"


def _db_path() -> str:
    return str(os.getenv("AI_QUANT_DB_PATH", _default_db_path()) or _default_db_path())


def _safe_name_fragment(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "default"
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    normalised = "".join(out).strip("_.-")
    return normalised or "default"


def _resolve_kernel_decision_file_path(*, mode: str, db_path: str) -> str | None:
    raw = str(os.getenv("AI_QUANT_KERNEL_DECISION_FILE", "") or "").strip()
    if not raw:
        return None

    db_path_resolved = str(Path(str(db_path or _default_db_path())).expanduser().resolve())
    db_stem = Path(db_path_resolved).stem
    mode_part = _safe_name_fragment(mode)
    db_part = _safe_name_fragment(db_stem)
    db_hash8 = hashlib.sha1(db_path_resolved.encode("utf-8")).hexdigest()[:8]
    suffix = f"{mode_part}_{db_part}_{db_hash8}"

    rendered = (
        raw.replace("{mode}", str(mode))
        .replace("{db}", str(db_stem))
        .replace("{db_stem}", str(db_stem))
    )
    if rendered != raw:
        return str(Path(rendered).expanduser().resolve())

    path = Path(raw).expanduser()
    allow_shared = _env_bool("AI_QUANT_KERNEL_DECISION_FILE_ALLOW_SHARED", False)
    if allow_shared:
        return str(path.resolve())

    as_text = str(raw)
    if as_text.endswith("/") or as_text.endswith("\\") or (path.exists() and path.is_dir()):
        return str((path / f"kernel_events_{suffix}.json").resolve())

    ext = path.suffix if path.suffix else ".json"
    stem = path.stem if path.suffix else path.name
    namespaced = path.with_name(f"{stem}_{suffix}{ext}")
    return str(namespaced.resolve())


def _harden_db_permissions(*paths: str, project_root: Path | None = None) -> None:
    """Best-effort DB permission hardening (`0600`) for existing SQLite data + sidecar files."""
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[1]
    candidates: set[Path] = set()
    try:
        for pattern in ("*.db", "*.db-wal", "*.db-shm", "*.db-journal"):
            candidates.update(root.glob(pattern))
    except Exception:
        pass

    for raw in paths:
        try:
            p = Path(str(raw or "").strip()).expanduser()
        except Exception:
            continue
        if str(p):
            candidates.add(p)

    expanded: set[Path] = set(candidates)
    for p in list(candidates):
        p_s = str(p)
        if p_s.endswith(".db"):
            expanded.add(Path(p_s + "-wal"))
            expanded.add(Path(p_s + "-shm"))
            expanded.add(Path(p_s + "-journal"))
    candidates = expanded

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                os.chmod(str(p), 0o600)
        except OSError:
            # Best-effort hardening: never block daemon startup on chmod failure.
            pass


def _hl_timeout_s() -> float:
    # Never allow infinite REST hangs in the main loop.
    raw = os.getenv("AI_QUANT_HL_TIMEOUT_S", "10")
    try:
        v = float(raw)
    except Exception:
        v = 10.0
    return float(max(0.5, min(30.0, v)))


def acquire_lock_or_exit(lock_path: str):
    """Prevent multiple daemons from running.

    Uses fcntl when available (Linux). Falls back to a simple pid file otherwise.
    """
    lock_file = open(lock_path, "a+", encoding="utf-8")

    def _write_pid() -> None:
        try:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except Exception:
            pass

    try:
        import fcntl  # Linux/Unix
    except ImportError:
        # Best-effort pid file (no true exclusion on platforms without fcntl).
        _write_pid()
        return lock_file

    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _write_pid()
    except BlockingIOError:
        try:
            lock_file.close()
        except Exception:
            pass
        raise SystemExit(f"Another ai-quant daemon is already running (lock held): {lock_path}")
    except Exception as e:
        try:
            lock_file.close()
        except Exception:
            pass
        raise SystemExit(f"Failed to acquire lock {lock_path}: {e}")

    return lock_file


def _close_lock_file(lock_file) -> None:
    try:
        if lock_file is not None:
            lock_file.close()
    except Exception:
        # Best-effort cleanup on process exit.
        pass


def _register_lock_cleanup(lock_file, *, register_fn=atexit.register) -> None:
    """Keep lock FD for process lifetime, but close cleanly at interpreter exit."""
    try:
        register_fn(_close_lock_file, lock_file)
    except Exception:
        logger.debug("failed to register daemon lock cleanup", exc_info=True)


class PaperPlugin:
    def __init__(self, trader):
        self.trader = trader
        self._last_funding_check = 0.0
        self._funding_every_s = float(os.getenv("AI_QUANT_PAPER_FUNDING_SECS", "60"))

    def before_iteration(self) -> None:
        # Reset per-loop entry budget (mirrors LivePlugin).
        try:
            import strategy.mei_alpha_v1 as mei_alpha_v1

            cfg = mei_alpha_v1.get_strategy_config("BTC") or {}
            budget = int((cfg.get("trade") or {}).get("max_entry_orders_per_loop", 0))
            self.trader._entry_budget_remaining = budget if budget > 0 else None
        except Exception:
            pass

        # If your paper trader applies funding, do it here on a schedule.
        now = time.time()
        if (now - self._last_funding_check) >= self._funding_every_s:
            self._last_funding_check = now
            fn = getattr(self.trader, "apply_funding_payments", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass

    def after_iteration(self) -> None:
        return


class LivePlugin:
    """Hooks for live mode.

    - periodic state sync (account + open positions)
    - drain WS user events for fills/funding/orderUpdates
    - periodic REST backfill of fills as a safety net
    """

    def __init__(
        self,
        *,
        trader,
        secrets_main_address: str,
        oms: LiveOms | None = None,
        risk: RiskManager | None = None,
        reconciler: LiveOmsReconciler | None = None,
    ):
        self.trader = trader
        self.main_address = secrets_main_address
        self._oms = oms
        self._risk = risk
        self._reconciler = reconciler

        # Attach OMS onto the trader so order submission can record OrderIntents.
        if self._oms is not None:
            try:
                setattr(self.trader, "oms", self._oms)
            except Exception:
                pass

        # Attach RiskManager onto the trader so execution path can enforce guardrails.
        if self._risk is not None:
            try:
                setattr(self.trader, "risk", self._risk)
            except Exception:
                pass

        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        import exchange.ws as hyperliquid_ws
        import live.trader as live_trader

        self._ws = hyperliquid_ws.hl_ws
        self._lt = live_trader
        self._rest_info = Info(constants.MAINNET_API_URL, skip_ws=True, timeout=_hl_timeout_s())

        self._last_state_sync = 0.0
        self._state_sync_s = float(os.getenv("AI_QUANT_LIVE_STATE_SYNC_SECS", "10"))

        self._last_rest_fills_sync = 0.0
        self._rest_sync_s = float(os.getenv("AI_QUANT_LIVE_REST_FILLS_SYNC_SECS", "60"))
        self._last_rest_fills_err_s = 0.0

        # On start, backfill a small window (dedup happens in DB).
        self._last_rest_fills_ms = int(time.time() * 1000) - int(
            float(os.getenv("AI_QUANT_LIVE_BACKFILL_MS", str(2 * 60 * 60 * 1000)))
        )

        # Buffer WS fills so transient DB errors don't drop fills (WS queues are drained).
        self._pending_ws_fills: list[dict] = []
        self._err_last_s: dict[str, float] = {}
        self._err_log_every_s = float(os.getenv("AI_QUANT_LIVE_ERR_LOG_EVERY_S", "30"))
        try:
            self._max_pending_ws_fills = int(float(os.getenv("AI_QUANT_LIVE_MAX_PENDING_FILLS", "50000")))
        except Exception:
            self._max_pending_ws_fills = 50000
        self._ws_fills_overflow_path = _ws_fills_overflow_path()
        self._force_rest_fills_sync = False

        # Health guard (alerts + optional kill-switch).
        self._health_enabled = _env_bool("AI_QUANT_HEALTH_GUARD", True)
        self._health_alert_cooldown_s = float(os.getenv("AI_QUANT_HEALTH_ALERT_COOLDOWN_S", "300"))
        self._health_last_alert_s: dict[str, float] = {}
        self._health_active: dict[str, bool] = {}
        self._health_last_seen_s: dict[str, float] = {}
        try:
            self._health_resolve_after_s = float(os.getenv("AI_QUANT_HEALTH_RESOLVE_AFTER_S", "600"))
        except Exception:
            self._health_resolve_after_s = 600.0
        self._health_resolve_after_s = float(max(0.0, self._health_resolve_after_s))

        # Alert-on-change tracking (avoid spam).
        self._last_kill_mode: str | None = None
        self._last_kill_reason: str | None = None

        self._fill_ingest_fail_streak = 0
        self._fill_ingest_fail_to_kill = int(float(os.getenv("AI_QUANT_HEALTH_FILL_INGEST_FAILS_TO_KILL", "5")))
        self._fill_ingest_kill = _env_bool("AI_QUANT_HEALTH_FILL_INGEST_KILL", True)
        self._fill_ingest_kill_mode = (
            str(os.getenv("AI_QUANT_HEALTH_FILL_INGEST_KILL_MODE", "close_only") or "close_only").strip().lower()
        )

        self._unmatched_window_s = float(os.getenv("AI_QUANT_HEALTH_UNMATCHED_WINDOW_S", "900"))
        self._unmatched_alert_n = int(float(os.getenv("AI_QUANT_HEALTH_UNMATCHED_ALERT_N", "1")))
        self._unmatched_kill = _env_bool("AI_QUANT_HEALTH_UNMATCHED_KILL", False)
        self._unmatched_kill_mode = (
            str(os.getenv("AI_QUANT_HEALTH_UNMATCHED_KILL_MODE", "close_only") or "close_only").strip().lower()
        )
        self._unmatched_ts: deque[float] = deque()
        # Grace period: suppress unmatched-fill alerts during startup REST backfill.
        self._unmatched_grace_until = time.time() + float(os.getenv("AI_QUANT_HEALTH_UNMATCHED_GRACE_S", "120"))

        self._pending_fills_to_kill = int(float(os.getenv("AI_QUANT_HEALTH_PENDING_FILLS_TO_KILL", "20000")))
        self._pending_fills_kill = _env_bool("AI_QUANT_HEALTH_PENDING_FILLS_KILL", True)
        self._pending_fills_kill_mode = (
            str(os.getenv("AI_QUANT_HEALTH_PENDING_FILLS_KILL_MODE", "close_only") or "close_only").strip().lower()
        )

        # One-shot risk reduction per kill event (avoid repeated close-all loops).
        self._last_drawdown_reduce_kill_since_s: float | None = None

        # Signal backfill: repair missing `signals` rows from recent `trades` (live DB).
        # This keeps the monitor "SIGNAL" column populated even if signal logging was missed
        # (older versions, transient DB locks, REST-only ingestion).
        self._signal_backfill_enabled = _env_bool("AI_QUANT_SIGNAL_BACKFILL", True)
        try:
            self._signal_backfill_every_s = float(os.getenv("AI_QUANT_SIGNAL_BACKFILL_SECS", "300"))
        except Exception:
            self._signal_backfill_every_s = 300.0
        try:
            self._signal_backfill_lookback_h = float(os.getenv("AI_QUANT_SIGNAL_BACKFILL_LOOKBACK_H", "48"))
        except Exception:
            self._signal_backfill_lookback_h = 48.0
        try:
            self._signal_backfill_max_trades = int(float(os.getenv("AI_QUANT_SIGNAL_BACKFILL_MAX_TRADES", "2000")))
        except Exception:
            self._signal_backfill_max_trades = 2000
        try:
            self._signal_backfill_dedup_s = float(os.getenv("AI_QUANT_SIGNAL_BACKFILL_DEDUP_S", "600"))
        except Exception:
            self._signal_backfill_dedup_s = 600.0
        self._last_signal_backfill_s = 0.0

        # Per-loop entry budget (OPEN/ADD) to prevent long loops caused by burst order submissions.
        # 0 disables (unlimited).
        try:
            self._max_entry_orders_per_loop = int(float(os.getenv("AI_QUANT_LIVE_MAX_ENTRY_ORDERS_PER_LOOP", "6")))
        except Exception:
            self._max_entry_orders_per_loop = 6
        self._max_entry_orders_per_loop = max(0, int(self._max_entry_orders_per_loop))

        # Automatic strategy-mode switching (best-effort).
        self._mode_policy = StrategyModePolicy(risk=self._risk)

    def _log_exc(self, key: str, msg: str) -> None:
        now = time.time()
        last = float(self._err_last_s.get(key, 0.0) or 0.0)
        if (now - last) < float(self._err_log_every_s or 0.0):
            return
        self._err_last_s[key] = now
        try:
            import traceback

            print(f"⚠️ {msg}\n{traceback.format_exc()}")
        except Exception:
            try:
                print(f"⚠️ {msg}")
            except Exception:
                pass

    def _fill_symbol_time_sample(self, fill: dict) -> str:
        try:
            sym = str(fill.get("coin") or fill.get("symbol") or "?").strip().upper() or "?"
        except Exception:
            sym = "?"
        t_raw = fill.get("time")
        if t_raw is None:
            t_raw = fill.get("timestamp")
        try:
            t_ms = str(int(float(t_raw)))
        except Exception:
            t_ms = "?"
        return f"{sym}@{t_ms}"

    def _persist_dropped_ws_fill_keys(self, fills: list[dict]) -> None:
        if not fills:
            return
        try:
            path = Path(self._ws_fills_overflow_path).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            dropped_at_ms = int(time.time() * 1000)
            with path.open("a", encoding="utf-8") as fh:
                for fill in fills:
                    try:
                        sym = str(fill.get("coin") or fill.get("symbol") or "").strip().upper()
                    except Exception:
                        sym = ""
                    tid_raw = fill.get("tid")
                    try:
                        tid = int(tid_raw) if tid_raw is not None else None
                    except Exception:
                        tid = None
                    try:
                        fill_hash = str(fill.get("hash") or "").strip() or None
                    except Exception:
                        fill_hash = None
                    t_raw = fill.get("time")
                    if t_raw is None:
                        t_raw = fill.get("timestamp")
                    try:
                        t_ms = int(float(t_raw)) if t_raw is not None else None
                    except Exception:
                        t_ms = None
                    payload = {
                        "dropped_at_ms": dropped_at_ms,
                        "symbol": sym or None,
                        "time_ms": t_ms,
                        "tid": tid,
                        "hash": fill_hash,
                    }
                    fh.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        except Exception:
            self._log_exc("pending_fills_overflow_log", "failed to persist dropped WS fills overflow records")

    def _handle_ws_fills_overflow(self) -> None:
        if self._max_pending_ws_fills <= 0:
            return
        n_pending = len(self._pending_ws_fills)
        if n_pending <= self._max_pending_ws_fills:
            return

        drop = n_pending - self._max_pending_ws_fills
        dropped = list(self._pending_ws_fills[:drop])
        self._pending_ws_fills = self._pending_ws_fills[drop:]
        self._force_rest_fills_sync = True
        self._persist_dropped_ws_fill_keys(dropped)

        samples = ", ".join(self._fill_symbol_time_sample(fill) for fill in dropped[:5]) or "n/a"
        print(
            f"⚠️ WS fills buffer exceeded {self._max_pending_ws_fills}; "
            f"dropped {drop} oldest; samples={samples}; forcing REST backfill"
        )

    def _should_run_rest_fills_sync(self, *, now: float) -> bool:
        if self._force_rest_fills_sync:
            return True
        if self._rest_sync_s <= 0:
            return False
        return (float(now) - float(self._last_rest_fills_sync)) >= float(self._rest_sync_s)

    def _sync_rest_fills(self, *, now: float) -> None:
        if not self._should_run_rest_fills_sync(now=now):
            return

        force_sync = bool(self._force_rest_fills_sync)
        if force_sync:
            self._force_rest_fills_sync = False

        self._last_rest_fills_sync = float(now)
        now_ms = int(time.time() * 1000)
        start_ms = max(0, int(self._last_rest_fills_ms) - (5 * 60 * 1000))  # overlap
        try:
            rest_fills = (
                self._rest_info.user_fills_by_time(
                    self.main_address,
                    start_ms,
                    now_ms,
                    aggregate_by_time=False,
                )
                or []
            )
            if rest_fills:
                if self._oms is not None:
                    inserted = self._oms.process_user_fills(trader=self.trader, fills=rest_fills)
                else:
                    inserted = self._lt.process_user_fills(self.trader, rest_fills)
                if inserted:
                    try:
                        self.trader.sync_from_exchange(force=True)
                    except Exception:
                        self._log_exc("sync_after_rest_fills", "sync_from_exchange(force=True) failed after REST fills")
            # Advance the cursor only after a successful REST call.
            self._last_rest_fills_ms = now_ms
        except Exception:
            # Do not advance the cursor on failures; we'll retry on the next cycle.
            if force_sync:
                self._force_rest_fills_sync = True
            if (now - self._last_rest_fills_err_s) >= 30.0:
                self._last_rest_fills_err_s = now
                try:
                    import traceback

                    print(f"⚠️ REST fills backfill failed\n{traceback.format_exc()}")
                except Exception:
                    pass

    def _health_alert(self, key: str, message: str, *, kill: bool, kill_mode: str) -> None:
        if not self._health_enabled:
            return
        now = time.time()
        try:
            self._health_last_seen_s[str(key)] = float(now)
        except Exception:
            pass

        k = str(key)
        was_active = bool(self._health_active.get(k, False))
        self._health_active[k] = True
        if was_active:
            return

        last = float(self._health_last_alert_s.get(key, 0.0) or 0.0)
        if (now - last) < float(self._health_alert_cooldown_s or 0.0):
            return
        self._health_last_alert_s[key] = now

        msg = f"🚨 HEALTH[{key}] {message}"
        try:
            print(msg)
        except Exception:
            pass

        try:
            import strategy.mei_alpha_v1 as mei_alpha_v1

            mei_alpha_v1.log_audit_event(
                symbol="SYSTEM",
                event="HEALTH_ALERT",
                level="warn",
                data={"key": str(key), "message": str(message), "kill": bool(kill), "kill_mode": str(kill_mode)},
            )
        except Exception:
            pass

        try:
            alerting.send_alert(
                msg,
                extra={"kind": "health", "key": str(key), "kill": bool(kill), "kill_mode": str(kill_mode)},
            )
        except Exception:
            pass

        # Best-effort Discord notification (same channel as live fills).
        try:
            if hasattr(self._lt, "_live_notify_enabled") and callable(getattr(self._lt, "_live_notify_enabled")):
                if self._lt._live_notify_enabled():
                    target = self._lt._live_discord_target()
                    if target:
                        self._lt._send_discord_message(target=target, message=msg)
        except Exception:
            pass

        # Optional kill-switch.
        if kill and self._risk is not None:
            try:
                mode = str(kill_mode or "close_only").strip().lower()
                if mode not in {"close_only", "halt_all"}:
                    mode = "close_only"
                self._risk.kill(mode=mode, reason=f"health:{key}")
            except Exception:
                pass

    def _maybe_resolve_health_alerts(self, *, now_s: float) -> None:
        if not self._health_enabled:
            return
        if float(self._health_resolve_after_s or 0.0) <= 0:
            return

        for key, active in list((self._health_active or {}).items()):
            if not active:
                continue
            last_seen = float(self._health_last_seen_s.get(key, 0.0) or 0.0)
            if last_seen <= 0:
                continue
            if (float(now_s) - float(last_seen)) < float(self._health_resolve_after_s):
                continue

            self._health_active[key] = False
            msg = f"✅ HEALTH[{key}] resolved"
            try:
                print(msg)
            except Exception:
                pass

            try:
                import strategy.mei_alpha_v1 as mei_alpha_v1

                mei_alpha_v1.log_audit_event(
                    symbol="SYSTEM", event="HEALTH_RESOLVED", level="info", data={"key": str(key)}
                )
            except Exception:
                pass

            try:
                alerting.send_alert(msg, extra={"kind": "health_resolved", "key": str(key)})
            except Exception:
                pass

            # Best-effort Discord notification (same channel as live fills).
            try:
                if hasattr(self._lt, "_live_notify_enabled") and callable(getattr(self._lt, "_live_notify_enabled")):
                    if self._lt._live_notify_enabled():
                        target = self._lt._live_discord_target()
                        if target:
                            self._lt._send_discord_message(target=target, message=msg)
            except Exception:
                pass

    def _maybe_alert_kill_state_change(self) -> None:
        risk = self._risk
        if risk is None:
            return
        try:
            km = str(getattr(risk, "kill_mode", "off") or "off").strip().lower()
        except Exception:
            km = "off"
        try:
            kr = str(getattr(risk, "kill_reason", "") or "").strip() or "none"
        except Exception:
            kr = "none"

        if self._last_kill_mode is None and self._last_kill_reason is None:
            self._last_kill_mode = km
            self._last_kill_reason = kr
            if km != "off":
                try:
                    alerting.send_alert(
                        f"🛑 RISK state: kill={km} reason={kr}",
                        extra={"kind": "risk", "kill_mode": km, "kill_reason": kr},
                    )
                except Exception:
                    pass
            return

        old_km = str(self._last_kill_mode or "off")
        old_kr = str(self._last_kill_reason or "none")
        if km == old_km and kr == old_kr:
            return

        self._last_kill_mode = km
        self._last_kill_reason = kr

        msg = f"🛑 RISK state change: kill={old_km}->{km} reason={old_kr}->{kr}"
        if km == "off":
            msg = f"✅ RISK resumed: reason={old_kr}"

        try:
            alerting.send_alert(msg, extra={"kind": "risk", "kill_mode": km, "kill_reason": kr})
        except Exception:
            pass

    def before_iteration(self) -> None:
        now = time.time()

        try:
            self._maybe_resolve_health_alerts(now_s=float(now))
        except Exception:
            pass
        try:
            self._maybe_alert_kill_state_change()
        except Exception:
            pass

        # Reset per-loop entry budget on the trader (best-effort).
        try:
            if self._max_entry_orders_per_loop > 0:
                setattr(self.trader, "_entry_budget_remaining", int(self._max_entry_orders_per_loop))
            else:
                setattr(self.trader, "_entry_budget_remaining", None)
        except Exception:
            pass

        # Periodic account/position reconciliation.
        if (now - self._last_state_sync) >= self._state_sync_s:
            self._last_state_sync = now

            # Refresh risk state (kill-switch, drawdown, etc).
            try:
                if self._risk is not None:
                    self._risk.refresh(trader=self.trader)
            except Exception:
                self._log_exc("risk_refresh", "RiskManager.refresh failed")

            try:
                self.trader.sync_from_exchange(force=False)
            except Exception:
                self._log_exc("sync_from_exchange", "trader.sync_from_exchange failed")

            # Optional risk reduction action: close all positions when a drawdown kill triggers,
            # but only once per distinct kill event.
            try:
                self._maybe_reduce_risk_on_drawdown_kill()
            except Exception:
                self._log_exc("risk_reduce_drawdown", "reduce-risk on drawdown kill failed")

            # Periodic OMS maintenance (expire stale intents).
            try:
                if self._oms is not None:
                    self._oms.reconcile(trader=self.trader)
            except Exception:
                self._log_exc("oms_reconcile", "OMS reconcile() failed")

        # Mode switching policy (runs after risk.refresh so new kill events are visible).
        try:
            self._mode_policy.maybe_switch()
        except SystemExit:
            raise
        except Exception:
            pass

        # True OMS reconcile loop (open orders, stale cancels, partial-fill tidy).
        try:
            if self._reconciler is not None:
                self._reconciler.maybe_run(trader=self.trader)
        except Exception:
            self._log_exc("oms_reconciler", "OMS reconciler maybe_run() failed")

        # Drain WS user fills into a local buffer so transient DB errors don't lose fills.
        try:
            fills = self._ws.drain_user_fills(max_items=5000)
            if fills:
                self._pending_ws_fills.extend([f for f in fills if isinstance(f, dict)])
                if self._pending_fills_to_kill > 0 and len(self._pending_ws_fills) >= self._pending_fills_to_kill:
                    self._health_alert(
                        "pending_fills",
                        f"pending_ws_fills={len(self._pending_ws_fills)} exceeds {self._pending_fills_to_kill}",
                        kill=bool(self._pending_fills_kill),
                        kill_mode=str(self._pending_fills_kill_mode or "close_only"),
                    )
                self._handle_ws_fills_overflow()
        except Exception:
            self._log_exc("drain_user_fills", "WS drain_user_fills failed")

        if self._pending_ws_fills:
            try:
                pending = list(self._pending_ws_fills)
                if self._oms is not None:
                    inserted = self._oms.process_user_fills(trader=self.trader, fills=pending)
                else:
                    inserted = self._lt.process_user_fills(self.trader, pending)

                if inserted:
                    try:
                        self.trader.sync_from_exchange(force=True)
                    except Exception:
                        self._log_exc("sync_after_fills", "sync_from_exchange(force=True) failed after fills")

                # Health guard: unmatched fills and ingest failures.
                self._fill_ingest_fail_streak = 0
                if self._oms is not None:
                    try:
                        st = getattr(self._oms, "last_ingest_stats", None) or {}
                        unmatched_new = int(st.get("unmatched_new") or 0)
                        if unmatched_new > 0:
                            for _ in range(unmatched_new):
                                self._unmatched_ts.append(now)

                        cutoff = float(now) - float(self._unmatched_window_s or 0.0)
                        while self._unmatched_ts and float(self._unmatched_ts[0]) < cutoff:
                            self._unmatched_ts.popleft()

                        if self._unmatched_alert_n > 0 and len(self._unmatched_ts) >= self._unmatched_alert_n:
                            # Suppress during startup grace period (REST backfill
                            # produces unmatched fills before OMS has intents).
                            if now < self._unmatched_grace_until:
                                logger.debug(
                                    "unmatched_fills suppressed during startup grace (%.0fs remaining)",
                                    self._unmatched_grace_until - now,
                                )
                            else:
                                samples = st.get("unmatched_samples")
                                extra = ""
                                try:
                                    if isinstance(samples, list) and samples:
                                        extra = f" samples={samples[:3]}"
                                except Exception:
                                    extra = ""
                                self._health_alert(
                                    "unmatched_fills",
                                    f"unmatched_new={unmatched_new} window_s={self._unmatched_window_s} count_in_window={len(self._unmatched_ts)}{extra}",
                                    kill=bool(self._unmatched_kill),
                                    kill_mode=str(self._unmatched_kill_mode or "close_only"),
                                )
                    except Exception:
                        pass

                # Only drop buffered fills after successful processing.
                self._pending_ws_fills.clear()
            except Exception:
                self._fill_ingest_fail_streak += 1
                self._log_exc(
                    "process_user_fills",
                    f"process_user_fills failed; keeping {len(self._pending_ws_fills)} fills for retry",
                )
                if (
                    self._fill_ingest_fail_to_kill > 0
                    and self._fill_ingest_fail_streak >= self._fill_ingest_fail_to_kill
                ):
                    self._health_alert(
                        "fill_ingest_failed",
                        f"fail_streak={self._fill_ingest_fail_streak} pending_ws_fills={len(self._pending_ws_fills)}",
                        kill=bool(self._fill_ingest_kill),
                        kill_mode=str(self._fill_ingest_kill_mode or "close_only"),
                    )

        try:
            self._maybe_alert_kill_state_change()
        except Exception:
            pass

        try:
            fundings = self._ws.drain_user_fundings(max_items=2000)
            if fundings:
                self._lt.process_user_fundings(self.trader, fundings)
        except Exception:
            self._log_exc("user_fundings", "WS drain/process userFundings failed")

        try:
            ledger = self._ws.drain_user_ledger_updates(max_items=2000)
            if ledger:
                self._lt.process_ws_events("userNonFundingLedgerUpdates", ledger)
        except Exception:
            self._log_exc("user_ledger", "WS drain/process userNonFundingLedgerUpdates failed")

        try:
            order_updates = self._ws.drain_order_updates(max_items=2000)
            if order_updates:
                self._lt.process_ws_events("orderUpdates", order_updates)
        except Exception:
            self._log_exc("order_updates", "WS drain/process orderUpdates failed")

        # REST fill backfill safety. Useful if WS drops for a while.
        try:
            self._sync_rest_fills(now=now)
        except Exception:
            self._log_exc("rest_fills_backfill", "REST fills backfill failed")

        # Repair missing signals from recent trades (best-effort, throttled).
        if (
            self._signal_backfill_enabled
            and self._oms is not None
            and (self._signal_backfill_every_s > 0)
            and ((now - self._last_signal_backfill_s) >= self._signal_backfill_every_s)
        ):
            self._last_signal_backfill_s = now
            try:
                n = self._oms.backfill_signals_from_trades(
                    lookback_h=float(self._signal_backfill_lookback_h),
                    max_trades=int(self._signal_backfill_max_trades),
                    dedup_s=float(self._signal_backfill_dedup_s),
                )
                if n:
                    print(f"🧩 backfilled {int(n)} missing signals from recent trades")
            except Exception:
                self._log_exc("signal_backfill", "signal backfill failed")

    def after_iteration(self) -> None:
        return

    def _maybe_reduce_risk_on_drawdown_kill(self) -> None:
        risk = self._risk
        if risk is None:
            return
        if str(getattr(risk, "kill_mode", "off") or "off") != "close_only":
            return

        reason = str(getattr(risk, "kill_reason", "") or "")
        if not reason.startswith("drawdown"):
            return

        policy = str(getattr(risk, "drawdown_reduce_policy", "none") or "none").strip().lower()
        if policy != "close_all":
            return

        kill_since = getattr(risk, "kill_since_s", None)
        if kill_since is None:
            return
        if self._last_drawdown_reduce_kill_since_s is not None and float(kill_since) == float(
            self._last_drawdown_reduce_kill_since_s
        ):
            return
        self._last_drawdown_reduce_kill_since_s = float(kill_since)

        # Best-effort close-all using WS mids as the reference price.
        try:
            positions = dict(getattr(self.trader, "positions", None) or {})
        except Exception:
            positions = {}
        if not positions:
            return

        try:
            stale_mid_max_age_s = float(os.getenv("AI_QUANT_DRAWDOWN_CLOSE_ALL_STALE_MID_MAX_AGE_S", "60"))
        except Exception:
            stale_mid_max_age_s = 60.0
        stale_mid_max_age_s = float(max(1.0, min(stale_mid_max_age_s, 600.0)))

        for sym in sorted(positions.keys()):
            mid = None
            stale_mid_age_s = None
            ws_disconnect_age_s = None
            try:
                mid = self._ws.get_mid(sym, max_age_s=10.0)
            except Exception:
                mid = None
            if mid is None or float(mid) <= 0:
                stale_mid = None
                try:
                    stale_mid = self._ws.get_mid(sym, max_age_s=None)
                except Exception:
                    stale_mid = None

                try:
                    get_mid_age = getattr(self._ws, "get_mid_age_s", None)
                    if callable(get_mid_age):
                        stale_mid_age_s = get_mid_age(sym)
                except Exception:
                    stale_mid_age_s = None
                try:
                    get_disconnect_age = getattr(self._ws, "get_ws_disconnect_age_s", None)
                    if callable(get_disconnect_age):
                        ws_disconnect_age_s = get_disconnect_age()
                except Exception:
                    ws_disconnect_age_s = None

                stale_mid_ok = (
                    stale_mid is not None
                    and float(stale_mid) > 0.0
                    and stale_mid_age_s is not None
                    and float(stale_mid_age_s) <= stale_mid_max_age_s
                )
                if stale_mid_ok and (
                    ws_disconnect_age_s is None or float(ws_disconnect_age_s) <= stale_mid_max_age_s
                ):
                    mid = float(stale_mid)
                    logger.warning(
                        "drawdown close_all using stale WS mid for %s (mid_age=%.1fs, disconnect_age=%s)",
                        sym,
                        float(stale_mid_age_s),
                        (
                            f"{float(ws_disconnect_age_s):.1f}s"
                            if ws_disconnect_age_s is not None
                            else "n/a"
                        ),
                    )
                else:
                    logger.warning("drawdown close_all skipped %s due to missing/stale WS mid", sym)
                    continue
            try:
                self.trader.close_position(
                    sym,
                    float(mid),
                    time.time(),
                    reason="Risk: drawdown kill (close_all)",
                    meta={"risk": {"kind": "drawdown", "policy": "close_all", "kill_reason": reason}},
                )
            except Exception:
                continue


def main() -> None:
    import logging
    import sys

    mode = _mode()
    try:
        from .sqlite_logger import install_sqlite_stdio_logger

        install_sqlite_stdio_logger(db_path=_db_path(), mode=mode)
    except Exception:
        pass

    # Configure logging AFTER sqlite_stdio_logger so the handler references
    # the tee'd stdout, sending logger.info() output to both journalctl AND the DB.
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Apply promoted config from factory runs (paper daemons only).
    # Must run BEFORE StrategyManager.get() so AI_QUANT_STRATEGY_YAML is set.
    promoted_role: str | None = None
    try:
        from .promoted_config import maybe_apply_promoted_config

        promoted_role = maybe_apply_promoted_config()
    except Exception:
        import traceback

        print(f"⚠️ promoted_config: failed to apply\n{traceback.format_exc()}")

    # Sync balance from live Hyperliquid account on startup.
    # Paper mode: opt-in via AI_QUANT_PAPER_BALANCE_FROM_LIVE=1.
    # Live mode: always sync so the inherited PaperTrader kernel and
    # any code that reads PAPER_BALANCE uses the real account balance
    # instead of the $10,000 default.
    _should_sync_balance = (mode == "paper" and os.getenv("AI_QUANT_PAPER_BALANCE_FROM_LIVE", "0") == "1") or mode in {
        "live",
        "dry_live",
    }
    if _should_sync_balance:
        try:
            from exchange.executor import load_live_secrets, HyperliquidLiveExecutor

            _secrets = load_live_secrets(
                os.getenv(
                    "AI_QUANT_SECRETS_PATH",
                    _default_secrets_path(),
                )
            )
            try:
                _exec = HyperliquidLiveExecutor(
                    secret_key=_secrets.secret_key,
                    main_address=_secrets.main_address,
                    timeout_s=4,
                )
            except Exception as exc:
                logger.error("Executor init failed (%s); details redacted", exc.__class__.__name__)
                raise RuntimeError("Executor init failed — check secrets and network") from None
            _snap = _exec.account_snapshot(force=True)
            if _snap.withdrawable_usd and _snap.withdrawable_usd > 0:
                os.environ["AI_QUANT_PAPER_BALANCE"] = str(_snap.withdrawable_usd)
                print(f"balance synced from live: ${_snap.withdrawable_usd:,.2f}")
                # Seed balance into DB so the monitor shows the correct value before any trades (paper only).
                if mode == "paper":
                    try:
                        import sqlite3 as _sql

                        _con = _sql.connect(_db_path(), timeout=5)
                        _cur = _con.execute("SELECT COUNT(*) FROM trades")
                        if _cur.fetchone()[0] == 0:
                            _cols = {row[1] for row in _con.execute("PRAGMA table_info(trades)").fetchall()}
                            _seed_run_fp = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip() or "startup"
                            if "run_fingerprint" in _cols:
                                _con.execute(
                                    "INSERT INTO trades (timestamp, symbol, type, action, price, size, notional, balance, run_fingerprint)"
                                    " VALUES (datetime('now'), '__SEED__', 'SYSTEM', 'SYSTEM', 0, 0, 0, ?, ?)",
                                    (_snap.withdrawable_usd, _seed_run_fp),
                                )
                            else:
                                _con.execute(
                                    "INSERT INTO trades (timestamp, symbol, type, action, price, size, notional, balance)"
                                    " VALUES (datetime('now'), '__SEED__', 'SYSTEM', 'SYSTEM', 0, 0, 0, ?)",
                                    (_snap.withdrawable_usd,),
                                )
                            _con.commit()
                        _con.close()
                    except Exception:
                        pass
        except Exception as exc:
            print(f"balance sync failed (using default): {exc}")

    import strategy.mei_alpha_v1 as mei_alpha_v1

    default_lock_name = "ai_quant_paper.lock" if mode == "paper" else "ai_quant_live.lock"
    lock_path = os.getenv(
        "AI_QUANT_LOCK_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", default_lock_name),
    )
    # Intentionally keep the lock FD open for the daemon lifetime. Register
    # a best-effort atexit cleanup so clean interpreter shutdown releases it.
    _lock = acquire_lock_or_exit(lock_path)
    _register_lock_cleanup(_lock)

    # If a strategy mode is persisted locally, load it on startup (only when env is unset).
    try:
        if not str(os.getenv("AI_QUANT_STRATEGY_MODE", "") or "").strip():
            m = _read_strategy_mode_file(_strategy_mode_file())
            if m:
                os.environ["AI_QUANT_STRATEGY_MODE"] = str(m)
    except Exception:
        pass

    strategy = StrategyManager.get()
    market_db_path = os.getenv("AI_QUANT_MARKET_DB_PATH", mei_alpha_v1.DB_PATH)
    _harden_db_permissions(_db_path(), str(market_db_path))
    market = MarketDataHub(
        db_path=market_db_path,
        stale_mid_s=float(os.getenv("AI_QUANT_WS_STALE_MIDS_S", "60")),
        stale_bbo_s=float(os.getenv("AI_QUANT_WS_STALE_BBO_S", "120")),
        stale_candle_s=float(os.getenv("AI_QUANT_WS_STALE_CANDLES_S", str(2 * 60 * 60))),
        db_timeout_s=float(os.getenv("AI_QUANT_DB_TIMEOUT_S", "30")),
    )

    if mode == "paper":
        # PaperTrader loads its last state from the DB. To reset, delete the DB or use a fresh DB path.
        trader = mei_alpha_v1.PaperTrader()
        plugin = PaperPlugin(trader)

    elif mode in {"live", "dry_live"}:
        import live.trader as live_trader

        secrets_path = os.getenv(
            "AI_QUANT_SECRETS_PATH",
            _default_secrets_path(),
        )
        secrets = live_trader.load_live_secrets(secrets_path)

        try:
            executor = live_trader.HyperliquidLiveExecutor(
                secret_key=secrets.secret_key,
                main_address=secrets.main_address,
                timeout_s=_hl_timeout_s(),
            )
        except Exception as exc:
            logger.error("Executor init failed (%s); details redacted", exc.__class__.__name__)
            raise RuntimeError("Executor init failed — check secrets and network") from None
        trader = live_trader.LiveTrader(executor=executor)
        # Used by the engine to subscribe to WS user channels.
        trader.secrets = secrets

        try:
            live_trader._ensure_live_tables()
        except Exception:
            pass

        oms = LiveOms(db_path=mei_alpha_v1.DB_PATH)
        risk = RiskManager()
        reconciler = LiveOmsReconciler(oms=oms, executor=executor, main_address=secrets.main_address, risk=risk)

        # Dry-live should be read-only: no cancels.
        if mode == "dry_live":
            try:
                reconciler.cancel_stale = False
            except Exception:
                pass

        plugin = LivePlugin(
            trader=trader,
            secrets_main_address=secrets.main_address,
            oms=oms,
            risk=risk,
            reconciler=reconciler,
        )

    else:
        raise SystemExit(f"Unknown AI_QUANT_MODE={mode}")

    # Run a second pass after initial component bootstrap so freshly created
    # SQLite DB/sidecar files are hardened on first daemon start as well.
    _harden_db_permissions(_db_path(), str(market_db_path), str(mei_alpha_v1.DB_PATH))

    interval = str(os.getenv("AI_QUANT_INTERVAL", mei_alpha_v1.INTERVAL) or mei_alpha_v1.INTERVAL).strip()
    try:
        lookback_bars = int(os.getenv("AI_QUANT_LOOKBACK_BARS", str(mei_alpha_v1.LOOKBACK_HOURS)))
    except Exception:
        lookback_bars = int(mei_alpha_v1.LOOKBACK_HOURS)
    lookback_bars = int(max(50, min(10_000, lookback_bars)))

    try:
        preset_run_fingerprint = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip()
        if preset_run_fingerprint:
            run_fingerprint = preset_run_fingerprint
            run_fp_payload = {
                "code_version": _read_code_version(),
                "strategy_overrides_sha1": str(getattr(strategy.snapshot, "overrides_sha1", "") or ""),
                "watchlist": [],
                "source": "env",
            }
        else:
            run_fingerprint, run_fp_payload = _build_run_fingerprint(
                strategy=strategy,
                mode=mode,
                interval=interval,
                lookback_bars=lookback_bars,
            )
            os.environ["AI_QUANT_RUN_FINGERPRINT"] = str(run_fingerprint)
        try:
            mei_alpha_v1.set_run_fingerprint(str(run_fingerprint))
        except Exception:
            pass
        logger.info(
            "run_fingerprint=%s code=%s strategy_sha=%s watchlist_n=%d interval=%s lookback=%d",
            str(run_fingerprint),
            str(run_fp_payload.get("code_version", "")),
            str(run_fp_payload.get("strategy_overrides_sha1", "")),
            len(run_fp_payload.get("watchlist", []) if isinstance(run_fp_payload.get("watchlist"), list) else []),
            interval,
            lookback_bars,
        )

        # Backfill early seed rows written before fingerprint initialisation.
        try:
            import sqlite3 as _sql

            _con = _sql.connect(_db_path(), timeout=5)
            _con.execute(
                """
                UPDATE trades
                SET run_fingerprint = ?
                WHERE symbol = '__SEED__'
                  AND action = 'SYSTEM'
                  AND (run_fingerprint IS NULL OR run_fingerprint = '' OR run_fingerprint = 'startup' OR run_fingerprint = 'unknown')
                """,
                (str(run_fingerprint),),
            )
            _con.commit()
            _con.close()
        except Exception:
            pass
    except Exception:
        logger.warning("failed to build run fingerprint", exc_info=True)

    runtime_db_path = _db_path()
    kernel_decision_file_before = str(os.getenv("AI_QUANT_KERNEL_DECISION_FILE", "") or "").strip()
    resolved_kernel_decision_file = _resolve_kernel_decision_file_path(mode=mode, db_path=runtime_db_path)
    if resolved_kernel_decision_file:
        os.environ["AI_QUANT_KERNEL_DECISION_FILE"] = str(resolved_kernel_decision_file)
        if kernel_decision_file_before and kernel_decision_file_before != str(resolved_kernel_decision_file):
            logger.info(
                "kernel decision file namespaced for daemon instance: %s -> %s",
                kernel_decision_file_before,
                resolved_kernel_decision_file,
            )
    decision_provider = _build_default_decision_provider(db_path=runtime_db_path)

    # Wire kernel provider to OMS for fill reconciliation (AQC-743).
    if hasattr(plugin, "oms") and plugin.oms is not None:
        try:
            if hasattr(decision_provider, "_runtime"):
                plugin.oms.kernel_provider = decision_provider
        except Exception:
            pass

    engine = UnifiedEngine(
        trader=trader,
        strategy=strategy,
        market=market,
        interval=interval,
        lookback_bars=lookback_bars,
        mode=mode,
        mode_plugin=plugin,
        decision_provider=decision_provider,
    )
    promo_tag = f" promoted_role={promoted_role}" if promoted_role else ""
    print(f"🚀 Unified engine started. mode={mode}{promo_tag}")
    try:
        alerting.send_alert(
            f"🚀 Unified engine started. mode={mode}{promo_tag}",
            extra={"kind": "restart", "mode": str(mode), "promoted_role": str(promoted_role or "")},
        )
    except Exception:
        pass

    watchdog = None
    try:
        from .systemd_watchdog import SystemdWatchdog

        watchdog = SystemdWatchdog(service_name="ai-quant-daemon")
        watchdog.start()
    except Exception:
        watchdog = None

    try:
        engine.run_forever()
    finally:
        try:
            if watchdog is not None:
                watchdog.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
