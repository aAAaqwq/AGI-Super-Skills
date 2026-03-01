"""AQC-823: Kernel orchestrator -- Python signal generation cutover.

Replaces the Python ``analyze()`` / ``check_exit_conditions()`` signal
generation paths with a thin orchestrator that feeds data to the Rust
decision kernel and routes resulting ``OrderIntents`` to the broker
adapter.

Classes
-------
KernelOrchestrator
    Feed candles/prices to the kernel, execute intents, log decisions.

Data classes
------------
KernelDecision
    Parsed response from a single kernel step.

Enum
----
LegacyMode
    Kernel operation mode (KERNEL_ONLY, SHADOW).

Module helpers
--------------
build_evaluate_event(snap, gate_result, ema_slow_slope_pct, symbol, price)
    Construct a MarketEvent JSON for ``signal="evaluate"``.
build_price_update_event(symbol, price)
    Construct a MarketEvent JSON for ``signal="price_update"``.
get_legacy_mode(config)
    Read cutover mode from env / config.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import logging
import os
import time
from typing import Any

from .event_id import generate_event_id as _generate_event_id

logger = logging.getLogger(__name__)

__all__ = [
    "KernelCandleDecisionProvider",
    "KernelDecision",
    "KernelOrchestrator",
    "LegacyMode",
    "build_evaluate_event",
    "build_price_update_event",
    "get_legacy_mode",
]

# ---------------------------------------------------------------------------
# Lazy bt_runtime import
# ---------------------------------------------------------------------------

try:
    import bt_runtime as _bt_runtime

    _BT_RUNTIME_AVAILABLE = True
except ImportError:
    _bt_runtime = None  # type: ignore[assignment]
    _BT_RUNTIME_AVAILABLE = False

# ---------------------------------------------------------------------------
# Lazy imports from sibling strategy modules — these are kept lazy so that
# the module can be imported even when heavy dependencies (pandas, ta) are
# absent (e.g. in lightweight test environments).
# ---------------------------------------------------------------------------


def _import_mei_helpers():
    """Import indicator/gate/entry helpers from ``mei_alpha_v1``."""
    from strategy.mei_alpha_v1 import (
        build_entry_params,
        build_gate_result,
        build_indicator_snapshot,
        compute_ema_slow_slope,
    )

    return build_indicator_snapshot, build_gate_result, build_entry_params, compute_ema_slow_slope


def _import_extract_action():
    from strategy.parity_test import extract_action

    return extract_action


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Kernel schema version — must match ``KERNEL_SCHEMA_VERSION`` in Rust.
KERNEL_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# LegacyMode enum
# ---------------------------------------------------------------------------


class LegacyMode(str, enum.Enum):
    """Cutover mode for kernel operation.

    * ``KERNEL_ONLY`` -- pure kernel decisions (default).
    * ``SHADOW``      -- kernel decides but a secondary path runs in parallel for comparison.

    The former ``LEGACY`` mode (Python decides) was removed in AQC-825.
    """

    KERNEL_ONLY = "kernel_only"
    SHADOW = "shadow"


def get_legacy_mode(config: dict[str, Any] | None = None) -> LegacyMode:
    """Read the cutover mode from environment or config.

    Resolution order:

    1. ``KERNEL_LEGACY_MODE`` environment variable (if set and valid).
    2. ``config["legacy_mode"]`` (if provided and valid).
    3. Default: ``LegacyMode.KERNEL_ONLY``.

    Parameters
    ----------
    config : dict, optional
        Config dict that may contain a ``"legacy_mode"`` key.

    Returns
    -------
    LegacyMode
    """
    env_val = os.environ.get("KERNEL_LEGACY_MODE", "").strip().lower()
    if env_val:
        try:
            return LegacyMode(env_val)
        except ValueError:
            logger.warning(
                "[orchestrator] invalid KERNEL_LEGACY_MODE=%r, falling back to config/default",
                env_val,
            )

    if config is not None:
        cfg_val = str(config.get("legacy_mode", "")).strip().lower()
        if cfg_val:
            try:
                return LegacyMode(cfg_val)
            except ValueError:
                logger.warning(
                    "[orchestrator] invalid config legacy_mode=%r, falling back to default",
                    cfg_val,
                )

    return LegacyMode.KERNEL_ONLY


# ---------------------------------------------------------------------------
# KernelDecision dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class KernelDecision:
    """Parsed response from a single kernel step.

    Attributes
    ----------
    ok : bool
        ``True`` if the kernel returned a successful response.
    state_json : str
        New kernel state JSON after the step.
    intents : list[dict]
        ``OrderIntent`` dicts from the kernel decision.
    fills : list[dict]
        ``FillEvent`` dicts from the kernel decision (paper fills).
    diagnostics : dict
        Full diagnostics dict from the kernel.
    action : str
        Extracted action string (``"BUY"`` / ``"SELL"`` / ``"HOLD"`` / ``"CLOSE"``).
    raw_json : str
        Full kernel response JSON for audit trail.
    """

    ok: bool
    state_json: str
    intents: list[dict[str, Any]]
    fills: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    action: str
    raw_json: str


# ---------------------------------------------------------------------------
# MarketEvent builders
# ---------------------------------------------------------------------------


def build_evaluate_event(
    snap: dict[str, Any],
    gate_result: dict[str, Any],
    ema_slow_slope_pct: float,
    symbol: str,
    price: float | None = None,
) -> dict[str, Any]:
    """Construct a MarketEvent dict for ``signal="evaluate"``.

    Parameters
    ----------
    snap : dict
        IndicatorSnapshot dict (from ``build_indicator_snapshot``).
    gate_result : dict
        GateResult dict (from ``build_gate_result``).
    ema_slow_slope_pct : float
        EMA-slow slope as a fraction of current price.
    symbol : str
        Trading symbol (e.g. ``"ETH"``).
    price : float, optional
        Override close price.  Defaults to ``snap["close"]``.

    Returns
    -------
    dict
        MarketEvent ready for ``json.dumps()`` and kernel ingestion.
    """
    ts = int(snap.get("t", int(time.time() * 1000)))
    close_price = float(price if price is not None else snap.get("close", 0.0))

    return {
        "schema_version": KERNEL_SCHEMA_VERSION,
        "event_id": ts,
        "timestamp_ms": ts,
        "symbol": str(symbol).upper(),
        "signal": "evaluate",
        "price": close_price,
        "indicators": snap,
        "gate_result": gate_result,
        "ema_slow_slope_pct": float(ema_slow_slope_pct),
    }


def build_price_update_event(
    symbol: str,
    price: float,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    """Construct a MarketEvent dict for ``signal="price_update"``.

    Parameters
    ----------
    symbol : str
        Trading symbol (e.g. ``"ETH"``).
    price : float
        Current price.
    timestamp_ms : int, optional
        Epoch ms timestamp.  Defaults to now.

    Returns
    -------
    dict
        MarketEvent ready for ``json.dumps()`` and kernel ingestion.
    """
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)

    return {
        "schema_version": KERNEL_SCHEMA_VERSION,
        "event_id": ts,
        "timestamp_ms": ts,
        "symbol": str(symbol).upper(),
        "signal": "price_update",
        "price": float(price),
    }


# ---------------------------------------------------------------------------
# KernelOrchestrator
# ---------------------------------------------------------------------------


class KernelOrchestrator:
    """Thin orchestrator replacing Python signal generation.

    Feeds candle data (via indicator helpers) to the Rust decision kernel,
    parses the response into ``KernelDecision`` objects, and optionally
    routes ``OrderIntents`` through the broker adapter.

    Parameters
    ----------
    config : dict, optional
        Strategy / orchestrator configuration.
    broker_adapter : object, optional
        A ``BrokerAdapter`` instance for executing intents on the exchange.
    reconciler : object, optional
        A ``PositionReconciler`` instance for kernel-vs-exchange sync.
    shadow_tracker : object, optional
        A ``ShadowDecisionTracker`` for shadow-mode comparison logging.
    db_path : str, optional
        Path to the SQLite database for decision logging.  If ``None``,
        falls back to ``DB_PATH`` from ``mei_alpha_v1``.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        broker_adapter: Any | None = None,
        reconciler: Any | None = None,
        shadow_tracker: Any | None = None,
        db_path: str | None = None,
    ):
        self._config = config or {}
        self._broker_adapter = broker_adapter
        self._reconciler = reconciler
        self._shadow_tracker = shadow_tracker
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Main entry: process a candle
    # ------------------------------------------------------------------

    def process_candle(
        self,
        symbol: str,
        candle_df: Any,
        kernel_state_json: str,
        params_json: str,
        exit_params_json: str | None = None,
        btc_bullish: bool | None = None,
        cfg: dict[str, Any] | None = None,
    ) -> KernelDecision:
        """Evaluate entry signal from a candle DataFrame via the kernel.

        Steps:
            1. Build IndicatorSnapshot from ``candle_df``.
            2. Build GateResult from the snapshot.
            3. Build EntryParams from config.
            4. Compute EMA-slow slope.
            5. Construct MarketEvent with ``signal="evaluate"``.
            6. Call ``bt_runtime.step_decision()`` (or ``step_full()`` if
               *exit_params_json* provided).
            7. Parse response into ``KernelDecision``.

        Parameters
        ----------
        symbol : str
            Trading symbol.
        candle_df : pd.DataFrame
            Candle data with Open/High/Low/Close/Volume.
        kernel_state_json : str
            Current kernel ``StrategyState`` JSON.
        params_json : str
            Current ``KernelParams`` JSON.
        exit_params_json : str, optional
            If provided, ``step_full()`` is used (entry + exit in one step).
        btc_bullish : bool or None
            BTC trend direction.
        cfg : dict, optional
            Strategy config override.

        Returns
        -------
        KernelDecision
        """
        if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
            raise RuntimeError(
                "FATAL: bt_runtime extension is not available.  The Rust kernel is "
                "REQUIRED for live/paper trading (AQC-825).  Build bt_runtime or check "
                "your AI_QUANT_BT_RUNTIME_PATH configuration."
            )

        effective_cfg = cfg or self._config

        # 1-4. Build helpers
        (
            build_indicator_snapshot,
            build_gate_result,
            build_entry_params,
            compute_ema_slow_slope,
        ) = _import_mei_helpers()

        snap = build_indicator_snapshot(
            candle_df,
            symbol=symbol,
            config=effective_cfg.get("indicators"),
        )
        ema_slow_slope_pct = compute_ema_slow_slope(candle_df, effective_cfg)
        gate_result = build_gate_result(
            snap,
            symbol,
            cfg=effective_cfg,
            btc_bullish=btc_bullish,
            ema_slow_slope_pct=ema_slow_slope_pct,
        )
        entry_params = build_entry_params(effective_cfg)

        # 5. Construct MarketEvent
        event = build_evaluate_event(
            snap,
            gate_result,
            ema_slow_slope_pct,
            symbol,
        )
        event_json = json.dumps(event, default=_json_default)

        # Merge entry_params into params
        params_dict = json.loads(params_json)
        params_dict["entry_params"] = entry_params
        merged_params_json = json.dumps(params_dict)

        # 6. Call kernel
        try:
            if exit_params_json is not None:
                raw = _bt_runtime.step_full(
                    kernel_state_json,
                    event_json,
                    merged_params_json,
                    exit_params_json,
                )
            else:
                raw = _bt_runtime.step_decision(
                    kernel_state_json,
                    event_json,
                    merged_params_json,
                )
        except Exception as exc:
            logger.error("[orchestrator] kernel call failed: %s", exc)
            return KernelDecision(
                ok=False,
                state_json=kernel_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": str(exc)},
                action="HOLD",
                raw_json="{}",
            )

        return self._parse_kernel_response(raw, kernel_state_json)

    # ------------------------------------------------------------------
    # Price update (exit evaluation)
    # ------------------------------------------------------------------

    def process_price_update(
        self,
        symbol: str,
        price: float,
        kernel_state_json: str,
        params_json: str,
        exit_params_json: str,
        timestamp_ms: int | None = None,
    ) -> KernelDecision:
        """Evaluate exit conditions via a PriceUpdate through the kernel.

        Parameters
        ----------
        symbol : str
            Trading symbol.
        price : float
            Current price.
        kernel_state_json : str
            Current kernel ``StrategyState`` JSON.
        params_json : str
            Current ``KernelParams`` JSON.
        exit_params_json : str
            ``ExitParams`` JSON for the kernel.
        timestamp_ms : int, optional
            Override timestamp.

        Returns
        -------
        KernelDecision
        """
        if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
            raise RuntimeError(
                "FATAL: bt_runtime extension is not available.  The Rust kernel is "
                "REQUIRED for live/paper trading (AQC-825).  Build bt_runtime or check "
                "your AI_QUANT_BT_RUNTIME_PATH configuration."
            )

        event = build_price_update_event(symbol, price, timestamp_ms=timestamp_ms)
        event_json = json.dumps(event)

        try:
            raw = _bt_runtime.step_full(
                kernel_state_json,
                event_json,
                params_json,
                exit_params_json,
            )
        except Exception as exc:
            logger.error("[orchestrator] kernel price_update failed: %s", exc)
            return KernelDecision(
                ok=False,
                state_json=kernel_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": str(exc)},
                action="HOLD",
                raw_json="{}",
            )

        return self._parse_kernel_response(raw, kernel_state_json)

    # ------------------------------------------------------------------
    # Execute decision through broker
    # ------------------------------------------------------------------

    def execute_decision(
        self,
        decision: KernelDecision,
        dry_run: bool = False,
        symbol_info: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute intents from a ``KernelDecision`` through the broker adapter.

        Parameters
        ----------
        decision : KernelDecision
            Parsed kernel decision containing intents.
        dry_run : bool
            If ``True``, log intents but do not execute.
        symbol_info : dict, optional
            Symbol metadata for size rounding.

        Returns
        -------
        list[dict]
            ``FillEvent`` dicts from the broker adapter.  Empty list if
            ``dry_run`` is ``True``, no intents, or no broker adapter.
        """
        if not decision.intents:
            logger.debug("[orchestrator] execute_decision: no intents to execute")
            return []

        if dry_run:
            logger.info(
                "[orchestrator] DRY RUN: would execute %d intents: %s",
                len(decision.intents),
                json.dumps(decision.intents, default=str),
            )
            return []

        if self._broker_adapter is None:
            logger.warning("[orchestrator] no broker_adapter configured; cannot execute intents")
            return []

        fills = self._broker_adapter.execute_intents(
            decision.intents,
            symbol_info=symbol_info,
        )
        logger.info(
            "[orchestrator] executed %d/%d intents, got %d fills",
            len(fills),
            len(decision.intents),
            len(fills),
        )
        return fills

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile(
        self,
        kernel_state_json: str,
        exchange_positions: dict[str, dict[str, Any]],
    ) -> Any:
        """Reconcile kernel positions with exchange positions.

        Delegates to the configured ``PositionReconciler``.

        Parameters
        ----------
        kernel_state_json : str
            Current kernel ``StrategyState`` JSON (contains ``positions``).
        exchange_positions : dict
            Mapping of symbol -> exchange position dict.

        Returns
        -------
        ReconciliationReport or None
            The reconciliation report, or ``None`` if no reconciler configured.
        """
        if self._reconciler is None:
            logger.warning("[orchestrator] no reconciler configured; skipping reconciliation")
            return None

        # Extract kernel positions from state
        try:
            state = json.loads(kernel_state_json)
            kernel_positions = state.get("positions", {})
        except (json.JSONDecodeError, TypeError):
            logger.error("[orchestrator] failed to parse kernel state for reconciliation")
            return None

        return self._reconciler.reconcile(kernel_positions, exchange_positions)

    # ------------------------------------------------------------------
    # Decision logging
    # ------------------------------------------------------------------

    def log_decision(self, decision: KernelDecision, symbol: str = "") -> str | None:
        """Log a kernel decision to the ``decision_events`` SQLite table.

        Parameters
        ----------
        decision : KernelDecision
            The decision to log.
        symbol : str
            Trading symbol for the event row.

        Returns
        -------
        str or None
            The decision event ULID if logged, else ``None``.
        """
        db_path = self._db_path
        if db_path is None:
            try:
                from strategy.mei_alpha_v1 import DB_PATH

                db_path = DB_PATH
            except ImportError:
                logger.warning("[orchestrator] cannot import DB_PATH; skipping decision logging")
                return None

        import sqlite3

        event_id = _generate_event_id()
        ts = int(time.time() * 1000)

        context = {
            "ok": decision.ok,
            "action": decision.action,
            "intents_count": len(decision.intents),
            "fills_count": len(decision.fills),
            "diagnostics": decision.diagnostics,
        }
        diagnostics = decision.diagnostics if isinstance(decision.diagnostics, dict) else {}
        rejection_reason = str(
            diagnostics.get("rejection_reason")
            or diagnostics.get("reason")
            or ""
        ).strip() or None
        action_text = str(decision.action or "").strip().lower()
        intent_kinds = {
            str(intent.get("kind") or "").strip().lower()
            for intent in decision.intents
            if isinstance(intent, dict)
        }

        reason_code: str | None = None
        if action_text in {"open", "open_long", "open_short"}:
            reason_code = "entry_signal"
        elif action_text in {"buy", "sell"}:
            reason_code = "entry_pyramid" if "add" in intent_kinds else "entry_signal"
        elif action_text in {"add"}:
            reason_code = "entry_pyramid"
        elif action_text in {"close", "close_long", "close_short", "reduce"}:
            reason_lower = str(rejection_reason or "").strip().lower()
            if "stop loss" in reason_lower and "trail" not in reason_lower:
                reason_code = "exit_stop_loss"
            elif "trailing stop" in reason_lower or "trailing" in reason_lower:
                reason_code = "exit_trailing_stop"
            elif "take profit" in reason_lower or reason_lower == "tp":
                reason_code = "exit_take_profit"
            elif "signal flip" in reason_lower:
                reason_code = "exit_signal_flip"
            elif "funding" in reason_lower:
                reason_code = "exit_funding"
            else:
                reason_code = "exit_filter"
        elif action_text in {"apply_funding", "funding"}:
            reason_code = "funding_payment"
        elif action_text == "blocked":
            reason_code = "exit_filter" if rejection_reason else "hold"
        elif action_text == "hold":
            reason_code = "hold"
        if not reason_code:
            reason_code = "unknown"

        config_fingerprint: str | None = None
        run_fingerprint = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip() or "unknown"
        try:
            cfg_json = json.dumps(self._config, sort_keys=True, separators=(",", ":"), default=str)
            if cfg_json:
                config_fingerprint = hashlib.sha1(cfg_json.encode("utf-8")).hexdigest()
        except Exception:
            config_fingerprint = None
        try:
            from strategy.mei_alpha_v1 import get_run_fingerprint as _get_run_fingerprint

            run_fingerprint = str(_get_run_fingerprint() or run_fingerprint)
        except Exception:
            pass

        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            col_rows = conn.execute("PRAGMA table_info(decision_events)").fetchall()
            has_config_fingerprint = any(str(row[1]) == "config_fingerprint" for row in col_rows)
            has_run_fingerprint = any(str(row[1]) == "run_fingerprint" for row in col_rows)
            has_reason_code = any(str(row[1]) == "reason_code" for row in col_rows)
            has_rejection_reason = any(str(row[1]) == "rejection_reason" for row in col_rows)

            columns = [
                "id",
                "timestamp_ms",
                "symbol",
                "event_type",
                "status",
                "decision_phase",
                "triggered_by",
                "action_taken",
            ]
            values: list[object] = [
                event_id,
                ts,
                str(symbol).upper(),
                "kernel_decision",
                "executed" if decision.ok else "error",
                "kernel_evaluation",
                "kernel_orchestrator",
                decision.action,
            ]
            if has_rejection_reason:
                columns.append("rejection_reason")
                values.append(rejection_reason)
            if has_reason_code:
                columns.append("reason_code")
                values.append(reason_code)
            if has_config_fingerprint:
                columns.append("config_fingerprint")
                values.append(config_fingerprint)
            if has_run_fingerprint:
                columns.append("run_fingerprint")
                values.append(run_fingerprint)
            columns.append("context_json")
            values.append(json.dumps(context, separators=(",", ":")))

            sql = (
                f"INSERT INTO decision_events ({', '.join(columns)}) "
                f"VALUES ({', '.join(['?'] * len(columns))})"
            )
            conn.execute(sql, tuple(values))
            conn.commit()
            return event_id
        except Exception:
            logger.exception("[orchestrator] failed to log decision to DB")
            return None
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_kernel_response(
        self,
        raw_json: str,
        fallback_state_json: str,
    ) -> KernelDecision:
        """Parse a raw kernel JSON response into a ``KernelDecision``.

        Parameters
        ----------
        raw_json : str
            Full kernel response envelope.
        fallback_state_json : str
            State to use if parsing fails.

        Returns
        -------
        KernelDecision
        """
        try:
            envelope = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("[orchestrator] failed to parse kernel response: %s", exc)
            return KernelDecision(
                ok=False,
                state_json=fallback_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": f"JSON parse error: {exc}"},
                action="HOLD",
                raw_json=raw_json if isinstance(raw_json, str) else "{}",
            )

        if not isinstance(envelope, dict):
            msg = f"invalid kernel response envelope type: {type(envelope).__name__}"
            logger.error("[orchestrator] %s", msg)
            return KernelDecision(
                ok=False,
                state_json=fallback_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": msg},
                action="HOLD",
                raw_json=raw_json,
            )

        expected_schema_version = int(KERNEL_SCHEMA_VERSION)
        decision_obj = envelope.get("decision")
        decision = decision_obj if isinstance(decision_obj, dict) else {}
        state_obj = decision.get("state")
        state = state_obj if isinstance(state_obj, dict) else {}

        raw_schema_versions: dict[str, Any] = {}
        for source, raw_schema_version in (
            ("envelope", envelope.get("schema_version")),
            ("decision", decision.get("schema_version")),
            ("state", state.get("schema_version")),
        ):
            if raw_schema_version is not None:
                raw_schema_versions[source] = raw_schema_version

        parsed_schema_versions: dict[str, int] = {}
        for source, raw_schema_version in raw_schema_versions.items():
            try:
                parsed_schema_versions[source] = int(raw_schema_version)
            except (TypeError, ValueError, OverflowError):
                msg = f"invalid schema_version value in {source}: {raw_schema_version!r}"
                logger.error("[orchestrator] %s", msg)
                return KernelDecision(
                    ok=False,
                    state_json=fallback_state_json,
                    intents=[],
                    fills=[],
                    diagnostics={
                        "error": msg,
                        "schema_versions": raw_schema_versions,
                        "expected_schema_version": expected_schema_version,
                    },
                    action="HOLD",
                    raw_json=raw_json,
                )

        unique_schema_versions = sorted(set(parsed_schema_versions.values()))
        if len(unique_schema_versions) > 1:
            msg = (
                "conflicting schema_version fields: "
                + ", ".join(f"{src}={version}" for src, version in sorted(parsed_schema_versions.items()))
            )
            logger.error("[orchestrator] %s", msg)
            return KernelDecision(
                ok=False,
                state_json=fallback_state_json,
                intents=[],
                fills=[],
                diagnostics={
                    "error": msg,
                    "schema_versions": parsed_schema_versions,
                    "expected_schema_version": expected_schema_version,
                },
                action="HOLD",
                raw_json=raw_json,
            )

        for source, schema_version in parsed_schema_versions.items():
            if schema_version != expected_schema_version:
                msg = f"schema_version mismatch at {source}: got={schema_version} expected={expected_schema_version}"
                logger.error("[orchestrator] %s", msg)
                return KernelDecision(
                    ok=False,
                    state_json=fallback_state_json,
                    intents=[],
                    fills=[],
                    diagnostics={
                        "error": msg,
                        "schema_version": schema_version,
                        "schema_versions": parsed_schema_versions,
                        "expected_schema_version": expected_schema_version,
                    },
                    action="HOLD",
                    raw_json=raw_json,
                )

        ok = bool(envelope.get("ok", False))

        if not ok:
            error = envelope.get("error", {})
            return KernelDecision(
                ok=False,
                state_json=fallback_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": error},
                action="HOLD",
                raw_json=raw_json,
            )

        if not isinstance(decision_obj, dict):
            msg = f"invalid kernel decision payload type: {type(decision_obj).__name__}"
            logger.error("[orchestrator] %s", msg)
            return KernelDecision(
                ok=False,
                state_json=fallback_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": msg},
                action="HOLD",
                raw_json=raw_json,
            )

        intents = decision.get("intents", [])
        fills = decision.get("fills", [])
        diagnostics = decision.get("diagnostics", {})

        # Extract new state
        state = decision.get("state", {})
        if not isinstance(state, dict):
            msg = f"invalid kernel state payload type: {type(state).__name__}"
            logger.error("[orchestrator] %s", msg)
            return KernelDecision(
                ok=False,
                state_json=fallback_state_json,
                intents=[],
                fills=[],
                diagnostics={"error": msg},
                action="HOLD",
                raw_json=raw_json,
            )
        state_json = json.dumps(state, separators=(",", ":"), sort_keys=True)

        # Extract action
        extract_action = _import_extract_action()
        action = extract_action(raw_json)

        return KernelDecision(
            ok=True,
            state_json=state_json,
            intents=intents,
            fills=fills,
            diagnostics=diagnostics,
            action=action,
            raw_json=raw_json,
        )


# ---------------------------------------------------------------------------
# KernelCandleDecisionProvider
# ---------------------------------------------------------------------------


class KernelCandleDecisionProvider:
    """Decision provider that generates kernel decisions from live candle data.

    Bridges :class:`KernelOrchestrator` (which feeds candle DataFrames to the
    Rust decision kernel) with the engine's ``DecisionProvider`` protocol.

    Unlike ``KernelDecisionRustBindingProvider`` (which reads pre-built market
    events from a JSON file that may not exist), this provider computes
    indicators from *live candle data*, feeds them to the Rust kernel via
    ``process_candle()``, and returns actionable intents.

    Parameters
    ----------
    orchestrator : KernelOrchestrator, optional
        Pre-configured orchestrator.  Built from *config* if not supplied.
    config : dict, optional
        Strategy config passed to orchestrator and indicator helpers.
    state_path : str, optional
        Path to the kernel state JSON file.
        Defaults to ``~/.mei/kernel_candle_state.json``.
    decision_factory : callable, optional
        Factory ``(raw_dict) -> decision | None`` used to convert raw intent
        dicts into engine ``KernelDecision`` objects.  When wired from
        ``engine.core``, pass ``KernelDecision.from_raw``.  If ``None``, raw
        dicts are returned directly.
    """

    def __init__(
        self,
        orchestrator: KernelOrchestrator | None = None,
        config: dict[str, Any] | None = None,
        state_path: str | None = None,
        decision_factory: Any | None = None,
    ):
        if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
            raise RuntimeError(
                "bt_runtime extension is required for KernelCandleDecisionProvider. "
                "Build bt_runtime or check your AI_QUANT_BT_RUNTIME_PATH configuration."
            )

        self._config = config or {}
        self._orch = orchestrator or KernelOrchestrator(config=self._config)
        self._state_path = state_path or os.path.expanduser("~/.mei/kernel_candle_state.json")
        self._decision_factory = decision_factory

        self._state_json = self._load_or_create_state()
        self._params_json = _bt_runtime.default_kernel_params_json()

    # ---- state management ------------------------------------------------

    def _load_or_create_state(self) -> str:
        """Load kernel state from disk, or create fresh if missing/corrupt."""
        try:
            state_json = _bt_runtime.load_state(self._state_path)
            logger.info(
                "[candle-provider] kernel state loaded from %s",
                self._state_path,
            )
            return state_json
        except OSError:
            pass  # file missing — normal on first run
        except Exception:
            logger.error(
                "[candle-provider] kernel state corrupt, creating fresh: %s",
                self._state_path,
            )

        seed = float(os.getenv("AI_QUANT_PAPER_BALANCE", "10000.0"))
        fresh = _bt_runtime.default_kernel_state_json(seed, int(time.time() * 1000))
        self._persist_state(fresh)
        logger.info("[candle-provider] kernel state created fresh (seed=$%.2f)", seed)
        return fresh

    def _persist_state(self, state_json: str) -> None:
        """Save kernel state to disk.  Best-effort, never raises."""
        try:
            state_dir = os.path.dirname(self._state_path)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)
            _bt_runtime.save_state(state_json, self._state_path)
        except Exception:
            logger.warning(
                "[candle-provider] failed to persist kernel state",
                exc_info=True,
            )

    # ---- DecisionProvider protocol ---------------------------------------

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
    ) -> list[Any]:
        """Generate kernel decisions from live candle data.

        For each symbol in *symbols* (skipping *not_ready_symbols*), fetches
        candle data via ``market.get_candles_df()``, feeds it to the
        orchestrator's ``process_candle()``, extracts intents from the kernel
        response, and converts them via *decision_factory* (if provided).

        Returns
        -------
        list
            If *decision_factory* was provided at init, returns a list of
            engine ``KernelDecision`` objects.  Otherwise, returns raw intent
            dicts compatible with ``KernelDecision.from_raw()``.
        """
        ready_symbols = [s for s in symbols if s not in not_ready_symbols]
        if not ready_symbols:
            return []

        # Get strategy config for indicator computation
        effective_cfg = self._config
        if strategy is not None:
            try:
                global_cfg = strategy.get_config("__GLOBAL__")
                if global_cfg:
                    effective_cfg = global_cfg
            except Exception:
                logger.debug("failed to get strategy global config for indicator computation", exc_info=True)

        decisions: list[Any] = []

        # AQC-FIX: Reset kernel virtual cash and positions each cycle.
        #
        # The kernel state is purely virtual — actual position sizing and
        # accounting is handled by PaperTrader / LiveTrader.  Over time the
        # kernel's virtual cash can diverge (accumulated losses, positions
        # opened by kernel but rejected by engine margin caps, etc.).  Once
        # cash_usd drops below the default notional ($10 000) the kernel
        # blocks ALL entry signals, silently halting trading.
        #
        # Fix: start each decision cycle with a fresh kernel state so that
        # virtual cash never gates real trading decisions.
        seed = float(os.getenv("AI_QUANT_KERNEL_CASH_SEED", "10000000.0"))
        state_json = _bt_runtime.default_kernel_state_json(seed, now_ms)

        for sym in ready_symbols:
            try:
                df = market.get_candles_df(
                    sym,
                    interval=interval,
                    min_rows=lookback_bars,
                )
                if df is None or len(df) < 20:
                    continue

                kd = self._orch.process_candle(
                    symbol=sym,
                    candle_df=df,
                    kernel_state_json=state_json,
                    params_json=self._params_json,
                    cfg=effective_cfg,
                )

                # Update running state for next symbol (kernel state is sequential)
                if kd.ok and kd.state_json:
                    state_json = kd.state_json

                if not kd.ok or not kd.intents:
                    continue

                # Convert intents to decision dicts
                for intent in kd.intents:
                    if not isinstance(intent, dict):
                        continue

                    raw = {
                        "symbol": str(intent.get("symbol", sym)).upper(),
                        "kind": intent.get("kind"),
                        "side": intent.get("side"),
                        "action": intent.get("action", kd.action),
                        "quantity": intent.get("quantity"),
                        "price": intent.get("price"),
                        "notional_usd": intent.get("notional_usd"),
                        "notional_hint_usd": intent.get("notional_hint_usd"),
                        "intent_id": intent.get("intent_id"),
                        "signal": intent.get("signal", kd.action),
                        "confidence": intent.get("confidence", "N/A"),
                        "now_series": intent.get("now_series"),
                        "entry_key": intent.get(
                            "entry_key",
                            intent.get("candle_key"),
                        ),
                        "reason": str(intent.get("reason") or f"kernel_candle:{kd.action.lower()}").strip(),
                        "reason_code": str(intent.get("reason_code") or "").strip().lower() or None,
                    }

                    if self._decision_factory is not None:
                        dec = self._decision_factory(raw)
                        if dec is not None:
                            decisions.append(dec)
                    else:
                        decisions.append(raw)

            except Exception:
                logger.warning(
                    "[candle-provider] [%s] kernel candle decision failed",
                    sym,
                    exc_info=True,
                )

        # Persist final state
        if state_json != self._state_json:
            self._state_json = state_json
            self._persist_state(state_json)

        return decisions

    @property
    def state_json(self) -> str:
        """Current kernel state JSON (for inspection / debugging)."""
        return self._state_json


def _json_default(o: Any) -> Any:
    """JSON serializer fallback for numpy/datetime types."""
    try:
        if hasattr(o, "item"):
            return o.item()
    except Exception:
        logger.debug("_json_default: .item() failed for %s, falling back to str()", type(o).__name__)
    return str(o)
