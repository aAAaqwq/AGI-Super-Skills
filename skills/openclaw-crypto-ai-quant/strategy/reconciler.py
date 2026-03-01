"""AQC-816: Exchange-kernel position reconciliation.

Compares kernel SSOT positions (from ``get_kernel_positions()``) with live
exchange positions (from ``HyperliquidLiveExecutor.get_positions()``) and
detects discrepancies such as size mismatches, ghost positions, missing
kernel entries, and side mismatches.

The reconciler is *pure* — it takes dicts in and returns reports out.  It
does **not** execute orders; that is the broker adapter's responsibility.
The only side effect is optional logging of discrepancies to the
``decision_events`` table (AQC-801 schema).

Exchange positions are treated as the ultimate source of truth.  When a
discrepancy is found the reconciler builds resolution actions that, when
applied, bring the kernel state back in line with the exchange.

Typical usage::

    from strategy.reconciler import PositionReconciler

    rec = PositionReconciler()
    report = rec.reconcile(kernel_positions, exchange_positions)
    if not report.is_clean:
        resolutions = rec.build_resolution(report)
        for r in resolutions:
            state_json = rec.apply_resolution(state_json, r)
        rec.log_discrepancies(report)
"""

from __future__ import annotations

import dataclasses
import json
import logging
import sqlite3
import time
from typing import Any

from .event_id import generate_event_id as _generate_event_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default size tolerance — 1 % to accommodate exchange rounding.
DEFAULT_SIZE_TOLERANCE_PCT = 0.01

#: Size delta percentage thresholds for severity classification.
MAJOR_SIZE_THRESHOLD_PCT = 0.10  # >  10 % = major

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Discrepancy:
    """A single discrepancy between kernel and exchange positions."""

    symbol: str
    type: str  # size_mismatch, side_mismatch, missing_kernel, missing_exchange
    severity: str  # minor, major, critical
    kernel_size: float
    exchange_size: float
    details: str
    exchange_side: str = "long"  # "long" or "short" — from normalized exchange pos


@dataclasses.dataclass
class ReconciliationReport:
    """Full result of a reconciliation run."""

    timestamp_ms: int
    matched: list[str]
    discrepancies: list[Discrepancy]
    is_clean: bool
    severity: str  # clean, minor, major, critical
    resolutions: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def normalize_exchange_position(raw_pos: dict[str, Any]) -> dict[str, Any]:
    """Normalize an exchange position dict to the standard comparison schema.

    The standard schema uses:
        - ``size``: absolute position size (float)
        - ``side``: ``"long"`` or ``"short"`` (lowercase)
        - ``entry_price``: average entry price (float)
        - ``leverage``: leverage multiplier (float)
        - ``unrealized_pnl``: unrealized P&L in USD (float)
        - ``margin_used``: margin used in USD (float)

    Accepts both the ``HyperliquidLiveExecutor.get_positions()`` format
    (``type`` = ``"LONG"``/``"SHORT"``) and the raw exchange format
    (``side`` = ``"long"``/``"short"``).
    """
    # Determine side: accept "type" (LONG/SHORT) or "side" (long/short)
    side_raw = str(raw_pos.get("side", "") or raw_pos.get("type", "")).strip().lower()
    if side_raw in ("long",):
        side = "long"
    elif side_raw in ("short",):
        side = "short"
    else:
        if side_raw:
            logger.warning("reconciler: unknown side value %r, defaulting to 'long'", side_raw)
        side = "long"  # default

    size = abs(float(raw_pos.get("size", 0.0)))
    entry_price = float(raw_pos.get("entry_price", 0.0))
    leverage = float(raw_pos.get("leverage", 1.0))
    unrealized_pnl = float(raw_pos.get("unrealized_pnl", 0.0))
    margin_used = float(raw_pos.get("margin_used", 0.0))

    return {
        "size": size,
        "side": side,
        "entry_price": entry_price,
        "leverage": leverage,
        "unrealized_pnl": unrealized_pnl,
        "margin_used": margin_used,
    }


def positions_match(
    kernel_pos: dict[str, Any],
    exchange_pos: dict[str, Any],
    size_tolerance_pct: float = DEFAULT_SIZE_TOLERANCE_PCT,
) -> bool:
    """Check if a kernel position and exchange position are equivalent.

    Two positions match when they have the same side and their sizes agree
    within ``size_tolerance_pct`` of the larger size.

    Parameters
    ----------
    kernel_pos
        Kernel position dict (must have ``side`` and ``quantity`` or ``size``).
    exchange_pos
        Normalized exchange position dict (has ``side`` and ``size``).
    size_tolerance_pct
        Allowed fractional difference (default 1 %).

    Returns
    -------
    bool
    """
    # Extract side from kernel position
    k_side = str(kernel_pos.get("side", "")).strip().lower()
    e_side = str(exchange_pos.get("side", "")).strip().lower()

    if k_side != e_side:
        return False

    # Extract size: kernel uses "quantity", exchange uses "size"
    k_size = abs(float(kernel_pos.get("quantity", kernel_pos.get("size", 0.0))))
    e_size = abs(float(exchange_pos.get("size", 0.0)))

    # Both zero = match
    if k_size == 0.0 and e_size == 0.0:
        return True

    # One zero, other not = mismatch
    if k_size == 0.0 or e_size == 0.0:
        return False

    max_size = max(k_size, e_size)
    delta_pct = abs(k_size - e_size) / max_size

    return delta_pct <= size_tolerance_pct


def calculate_severity(report: ReconciliationReport) -> str:
    """Determine overall severity from a reconciliation report's discrepancies.

    Returns one of: ``"clean"``, ``"minor"``, ``"major"``, ``"critical"``.
    """
    if not report.discrepancies:
        return "clean"

    severities = [d.severity for d in report.discrepancies]

    if "critical" in severities:
        return "critical"
    if "major" in severities:
        return "major"
    return "minor"


# ---------------------------------------------------------------------------
# PositionReconciler
# ---------------------------------------------------------------------------


class PositionReconciler:
    """Compares kernel positions with exchange positions and detects/resolves discrepancies.

    Parameters
    ----------
    config : dict, optional
        Configuration overrides::

            {
                "size_tolerance_pct": 0.01,   # 1 % default tolerance
                "heartbeat_interval_s": 30,   # reconciliation interval
            }
    risk_manager : object, optional
        A ``RiskManager`` instance (from ``engine.risk``).  When provided and a
        critical reconciliation mismatch is detected, the reconciler activates
        the kill-switch (``close_only`` mode) to prevent further entries while
        the exchange state diverges from the kernel.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        risk_manager: Any | None = None,
    ):
        cfg = config or {}
        self._size_tolerance_pct: float = float(cfg.get("size_tolerance_pct", DEFAULT_SIZE_TOLERANCE_PCT))
        self._risk_manager = risk_manager

    # ------------------------------------------------------------------
    # Core reconciliation
    # ------------------------------------------------------------------

    def reconcile(
        self,
        kernel_positions: dict[str, dict[str, Any]],
        exchange_positions: dict[str, dict[str, Any]],
    ) -> ReconciliationReport:
        """Compare kernel positions with exchange positions.

        Parameters
        ----------
        kernel_positions
            Mapping of symbol -> kernel Position dict (from
            ``get_kernel_positions()``).  Keys like ``quantity``, ``side``,
            ``avg_entry_price``.
        exchange_positions
            Mapping of symbol -> exchange position dict.  Accepted in
            either raw Hyperliquid format (``type``/``size``) or
            normalized format (``side``/``size``).

        Returns
        -------
        ReconciliationReport
        """
        now_ms = int(time.time() * 1000)
        matched: list[str] = []
        discrepancies: list[Discrepancy] = []

        # Normalize exchange positions once
        normalized_exchange: dict[str, dict[str, Any]] = {}
        for sym, raw in exchange_positions.items():
            normalized_exchange[sym] = normalize_exchange_position(raw)

        all_symbols = set(kernel_positions.keys()) | set(normalized_exchange.keys())

        for symbol in sorted(all_symbols):
            k_pos = kernel_positions.get(symbol)
            e_pos = normalized_exchange.get(symbol)

            if k_pos is not None and e_pos is not None:
                # Both exist — check if they match
                if positions_match(k_pos, e_pos, self._size_tolerance_pct):
                    matched.append(symbol)
                else:
                    disc = self.classify_discrepancy(symbol, k_pos, e_pos)
                    discrepancies.append(disc)
            elif k_pos is not None and e_pos is None:
                # In kernel but not on exchange — ghost position
                disc = Discrepancy(
                    symbol=symbol,
                    type="missing_exchange",
                    severity="major",
                    kernel_size=abs(float(k_pos.get("quantity", k_pos.get("size", 0.0)))),
                    exchange_size=0.0,
                    details=f"{symbol}: in kernel but not on exchange (ghost position — "
                    f"possibly liquidated or manually closed)",
                )
                discrepancies.append(disc)
            elif k_pos is None and e_pos is not None:
                # On exchange but not in kernel — unknown position
                disc = Discrepancy(
                    symbol=symbol,
                    type="missing_kernel",
                    severity="major",
                    kernel_size=0.0,
                    exchange_size=float(e_pos.get("size", 0.0)),
                    details=f"{symbol}: on exchange but not in kernel (manual open or circuit breaker recovery needed)",
                    exchange_side=e_pos.get("side", "long"),
                )
                discrepancies.append(disc)

        report = ReconciliationReport(
            timestamp_ms=now_ms,
            matched=matched,
            discrepancies=discrepancies,
            is_clean=len(discrepancies) == 0,
            severity="clean",  # placeholder
            resolutions=[],
        )
        report.severity = calculate_severity(report)

        # H12: When reconciliation severity is critical, trigger kill-switch, emit alert,
        # and log at CRITICAL level.
        if report.severity == "critical":
            crit_details = "; ".join(d.details for d in discrepancies if d.severity == "critical")
            logger.critical("RECONCILIATION CRITICAL: %s", crit_details)

            # Activate kill-switch (close_only) so no new entries are placed while
            # the exchange state diverges from kernel state.
            if self._risk_manager is not None:
                try:
                    self._risk_manager.kill(
                        mode="close_only",
                        reason=f"reconciliation_critical: {crit_details}",
                    )
                    logger.critical(
                        "KILL-SWITCH ACTIVATED by reconciler due to critical mismatch: %s",
                        crit_details,
                    )
                except Exception:
                    logger.error(
                        "reconciler: failed to activate kill-switch on critical mismatch",
                        exc_info=True,
                    )

            try:
                from engine.alerting import send_alert

                send_alert(f"RECONCILIATION CRITICAL (kill-switch activated): {crit_details}")
            except Exception:
                logger.warning("failed to send critical reconciliation alert", exc_info=True)

        return report

    def classify_discrepancy(
        self,
        symbol: str,
        kernel_pos: dict[str, Any],
        exchange_pos: dict[str, Any],
    ) -> Discrepancy:
        """Classify a discrepancy between a kernel and exchange position.

        Parameters
        ----------
        symbol
            Trading symbol (e.g. ``"ETH"``).
        kernel_pos
            Kernel position dict (``side``, ``quantity``).
        exchange_pos
            Normalized exchange position dict (``side``, ``size``).

        Returns
        -------
        Discrepancy
        """
        k_side = str(kernel_pos.get("side", "")).strip().lower()
        e_side = str(exchange_pos.get("side", "")).strip().lower()

        k_size = abs(float(kernel_pos.get("quantity", kernel_pos.get("size", 0.0))))
        e_size = abs(float(exchange_pos.get("size", 0.0)))

        # Side mismatch is always critical
        if k_side != e_side:
            return Discrepancy(
                symbol=symbol,
                type="side_mismatch",
                severity="critical",
                kernel_size=k_size,
                exchange_size=e_size,
                details=f"{symbol}: kernel side={k_side} vs exchange side={e_side}",
                exchange_side=e_side,
            )

        # Size mismatch — severity based on delta percentage
        max_size = max(k_size, e_size) if max(k_size, e_size) > 0 else 1.0
        delta = abs(k_size - e_size)
        pct_diff = delta / max_size

        if pct_diff > MAJOR_SIZE_THRESHOLD_PCT:
            severity = "major"
        else:
            severity = "minor"

        return Discrepancy(
            symbol=symbol,
            type="size_mismatch",
            severity=severity,
            kernel_size=k_size,
            exchange_size=e_size,
            details=f"{symbol}: kernel_size={k_size:.8f} vs exchange_size={e_size:.8f} "
            f"(delta={delta:.8f}, {pct_diff:.2%})",
            exchange_side=e_side,
        )

    # ------------------------------------------------------------------
    # Resolution building
    # ------------------------------------------------------------------

    def build_resolution(self, report: ReconciliationReport) -> list[dict[str, Any]]:
        """Generate resolution actions for each discrepancy in a report.

        Resolution actions describe how to bring the kernel state back in
        line with the exchange.  They do **not** execute trades.

        Returns
        -------
        list[dict]
            Each dict has keys: ``action``, ``symbol``, ``details``.
            ``action`` is one of ``"adjust"``, ``"add"``, ``"remove"``,
            ``"alert"``.
        """
        resolutions: list[dict[str, Any]] = []

        for disc in report.discrepancies:
            if disc.type == "size_mismatch":
                resolutions.append(
                    {
                        "action": "adjust",
                        "symbol": disc.symbol,
                        "details": {
                            "kernel_size": disc.kernel_size,
                            "exchange_size": disc.exchange_size,
                            "delta": abs(disc.kernel_size - disc.exchange_size),
                        },
                    }
                )
            elif disc.type == "missing_kernel":
                resolutions.append(
                    {
                        "action": "add",
                        "symbol": disc.symbol,
                        "details": {
                            "exchange_size": disc.exchange_size,
                            "exchange_side": disc.exchange_side,
                        },
                    }
                )
            elif disc.type == "missing_exchange":
                resolutions.append(
                    {
                        "action": "remove",
                        "symbol": disc.symbol,
                        "details": {
                            "kernel_size": disc.kernel_size,
                        },
                    }
                )
            elif disc.type == "side_mismatch":
                resolutions.append(
                    {
                        "action": "alert",
                        "symbol": disc.symbol,
                        "details": {
                            "kernel_size": disc.kernel_size,
                            "exchange_size": disc.exchange_size,
                            "reason": "Side mismatch requires manual intervention",
                        },
                    }
                )

        return resolutions

    # ------------------------------------------------------------------
    # Resolution application
    # ------------------------------------------------------------------

    def apply_resolution(
        self,
        state_json: str,
        resolution: dict[str, Any],
    ) -> str:
        """Apply a single resolution action to kernel state JSON.

        Parameters
        ----------
        state_json
            Kernel ``StrategyState`` as a JSON string.
        resolution
            A resolution dict from ``build_resolution()``.

        Returns
        -------
        str
            Updated state JSON.  For ``"alert"`` actions the state is
            returned unchanged.
        """
        action = resolution.get("action", "")
        symbol = resolution.get("symbol", "")
        details = resolution.get("details", {})

        if action == "alert":
            logger.warning(
                "reconciler: alert for %s — %s",
                symbol,
                details.get("reason", "manual intervention required"),
            )
            return state_json

        try:
            state = json.loads(state_json)
        except (json.JSONDecodeError, TypeError):
            logger.error("reconciler: failed to parse state JSON")
            return state_json

        positions = state.get("positions")
        if positions is None:
            positions = {}
            state["positions"] = positions

        if action == "adjust":
            if symbol in positions:
                positions[symbol]["quantity"] = details.get("exchange_size", positions[symbol].get("quantity", 0.0))
                logger.info(
                    "reconciler: adjusted %s size to %.8f",
                    symbol,
                    details.get("exchange_size", 0.0),
                )
            else:
                logger.warning(
                    "reconciler: adjust requested for %s but not in kernel state",
                    symbol,
                )

        elif action == "add":
            # Add a minimal position entry for the exchange position.
            # Full position metadata should be re-synced from exchange on
            # next heartbeat.
            positions[symbol] = {
                "symbol": symbol,
                "side": details.get("exchange_side", "long"),
                "quantity": details.get("exchange_size", 0.0),
                "avg_entry_price": 0.0,
                "opened_at_ms": int(time.time() * 1000),
                "updated_at_ms": int(time.time() * 1000),
                "notional_usd": 0.0,
                "margin_usd": 0.0,
            }
            logger.info(
                "reconciler: added %s to kernel (exchange_size=%.8f)",
                symbol,
                details.get("exchange_size", 0.0),
            )

        elif action == "remove":
            removed = positions.pop(symbol, None)
            if removed is not None:
                logger.info("reconciler: removed ghost position %s from kernel", symbol)
            else:
                logger.warning(
                    "reconciler: remove requested for %s but not in kernel state",
                    symbol,
                )

        return json.dumps(state, separators=(",", ":"), sort_keys=True)

    # ------------------------------------------------------------------
    # Discrepancy logging
    # ------------------------------------------------------------------

    def log_discrepancies(
        self,
        report: ReconciliationReport,
        db_path: str | None = None,
    ) -> list[str]:
        """Log discrepancies to the ``decision_events`` table.

        Each discrepancy is stored as a decision event with
        ``event_type='reconciliation'``.

        Parameters
        ----------
        report
            A ``ReconciliationReport`` from ``reconcile()``.
        db_path
            Path to the SQLite database.  If ``None``, attempts to
            import ``DB_PATH`` from ``strategy.mei_alpha_v1``.

        Returns
        -------
        list[str]
            List of decision event IDs (ULIDs) that were created.
        """
        if report.is_clean:
            return []

        if db_path is None:
            try:
                from strategy.mei_alpha_v1 import DB_PATH

                db_path = DB_PATH
            except ImportError:
                logger.warning("reconciler: cannot import DB_PATH; skipping DB logging")
                return []

        event_ids: list[str] = []
        conn: sqlite3.Connection | None = None
        try:
            import os

            conn = sqlite3.connect(db_path, timeout=5.0)
            col_rows = conn.execute("PRAGMA table_info(decision_events)").fetchall()
            has_run_fingerprint = any(str(row[1]) == "run_fingerprint" for row in col_rows)
            run_fingerprint = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip() or "unknown"
            try:
                from strategy.mei_alpha_v1 import get_run_fingerprint as _get_run_fingerprint

                run_fingerprint = str(_get_run_fingerprint() or run_fingerprint)
            except Exception:
                pass
            for disc in report.discrepancies:
                event_id = _generate_event_id()
                context = {
                    "kernel_size": disc.kernel_size,
                    "exchange_size": disc.exchange_size,
                    "delta": abs(disc.kernel_size - disc.exchange_size),
                    "severity": disc.severity,
                    "type": disc.type,
                    "details": disc.details,
                }
                if has_run_fingerprint:
                    conn.execute(
                        """
                        INSERT INTO decision_events
                            (id, timestamp_ms, symbol, event_type, status,
                             decision_phase, triggered_by, action_taken,
                             run_fingerprint, context_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            report.timestamp_ms,
                            disc.symbol,
                            "reconciliation",
                            disc.severity,
                            "execution",
                            "heartbeat",
                            disc.type,
                            run_fingerprint,
                            json.dumps(context, separators=(",", ":")),
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO decision_events
                            (id, timestamp_ms, symbol, event_type, status,
                             decision_phase, triggered_by, action_taken,
                             context_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            report.timestamp_ms,
                            disc.symbol,
                            "reconciliation",
                            disc.severity,
                            "execution",
                            "heartbeat",
                            disc.type,
                            json.dumps(context, separators=(",", ":")),
                        ),
                    )
                event_ids.append(event_id)
            conn.commit()
        except Exception:
            logger.exception("reconciler: failed to log discrepancies to DB")
        finally:
            if conn is not None:
                conn.close()

        return event_ids
