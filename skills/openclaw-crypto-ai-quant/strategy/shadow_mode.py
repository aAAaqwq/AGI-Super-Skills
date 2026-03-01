"""AQC-821: Shadow mode — parallel Python + kernel decision tracking.

Formalises the ad-hoc shadow comparison logic that ``analyze_with_shadow()``
(AQC-812) and ``check_exit_with_shadow()`` (AQC-813) introduced into a
proper framework with:

* ``DecisionMode`` enum driven by ``KERNEL_DECISION_MODE`` env var / config
* ``ShadowDecisionTracker`` that records entry/exit comparisons, tracks
  agreement rates over a rolling window, raises alerts when agreement
  drops below a configurable threshold, and logs diffs to the
  ``decision_events`` table.
* ``ShadowDecisionReport`` data class for full statistics snapshots.

Typical usage::

    from strategy.shadow_mode import (
        DecisionMode,
        ShadowDecisionTracker,
        get_decision_mode,
        is_shadow_mode,
        should_run_kernel,
        should_run_python,
    )

    mode = get_decision_mode()
    tracker = ShadowDecisionTracker()

    if is_shadow_mode(mode):
        result = tracker.record_entry_comparison(
            symbol="ETH",
            python_signal="BUY",
            kernel_signal="BUY",
            python_confidence="high",
            kernel_confidence="high",
            timestamp_ms=1700000000000,
        )
        tracker.log_comparison_to_db(result)

    stats = tracker.get_agreement_stats()
    alert_active, msg, info = tracker.check_alert()
"""

from __future__ import annotations

import collections
import dataclasses
import enum
import json
import logging
import os
import sqlite3
import time
from typing import Any

from .event_id import generate_event_id as _generate_event_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default rolling window size for agreement rate calculation.
DEFAULT_WINDOW_SIZE = 1000

#: Default alert threshold — alert fires when agreement drops below 95 %.
DEFAULT_ALERT_THRESHOLD = 0.95

#: Maximum number of recent disagreements kept in memory for reports.
MAX_RECENT_DISAGREEMENTS = 50

# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class DecisionMode(str, enum.Enum):
    """Kernel decision routing mode.

    * ``SHADOW`` — both Python and kernel run; kernel is authoritative,
      Python result is compared and logged (default).
    * ``KERNEL`` — kernel only; full SSOT.
    * ``PYTHON`` — Python only; legacy path.
    """

    SHADOW = "shadow"
    KERNEL = "kernel"
    PYTHON = "python"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ComparisonResult:
    """Outcome of a single Python-vs-kernel comparison."""

    symbol: str
    timestamp_ms: int
    comparison_type: str  # "entry" or "exit"
    python_decision: str
    kernel_decision: str
    is_match: bool
    details: str


@dataclasses.dataclass
class ShadowDecisionReport:
    """Full statistics snapshot from a ``ShadowDecisionTracker``."""

    generated_at_ms: int
    total_comparisons: int
    entry_comparisons: int
    exit_comparisons: int
    entry_agreement_rate: float
    exit_agreement_rate: float
    overall_agreement_rate: float
    rolling_agreement_rate: float
    alert_active: bool
    alert_message: str
    recent_disagreements: list[ComparisonResult]
    by_signal_type: dict[str, float]


# ---------------------------------------------------------------------------
# ShadowDecisionTracker
# ---------------------------------------------------------------------------


class ShadowDecisionTracker:
    """Tracks agreement between Python and kernel decisions in shadow mode.

    Parameters
    ----------
    window_size : int
        Rolling window size for agreement calculation (default 1000).
    alert_threshold : float
        Alert if agreement drops below this fraction (default 0.95 = 95 %).
    config : dict, optional
        Optional config dict; may contain ``window_size`` and
        ``alert_threshold`` overrides.
    """

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        alert_threshold: float = DEFAULT_ALERT_THRESHOLD,
        config: dict[str, Any] | None = None,
    ):
        cfg = config or {}
        self._window_size: int = max(1, int(cfg.get("window_size", window_size)))
        self._alert_threshold: float = float(
            cfg.get("alert_threshold", alert_threshold)
        )
        try:
            raw_max = int(
                cfg.get("max_comparisons", max(self._window_size * 2, self._window_size))
            )
        except Exception:
            raw_max = max(self._window_size * 2, self._window_size)
        self._max_comparisons: int = int(
            max(
                1,
                self._window_size,
                raw_max,
            )
        )

        # Recent comparisons (bounded to prevent unbounded memory growth).
        self._comparisons: collections.deque[ComparisonResult] = collections.deque(
            maxlen=self._max_comparisons
        )

        # Per-signal-type agreement counters:
        #   _signal_total[signal] = number of comparisons
        #   _signal_match[signal] = number of matches
        self._signal_total: dict[str, int] = collections.defaultdict(int)
        self._signal_match: dict[str, int] = collections.defaultdict(int)

        # Entry / exit aggregate counters.
        self._entry_total: int = 0
        self._entry_match: int = 0
        self._exit_total: int = 0
        self._exit_match: int = 0

        # Recent disagreements ring-buffer.
        self._recent_disagreements: collections.deque[ComparisonResult] = (
            collections.deque(maxlen=MAX_RECENT_DISAGREEMENTS)
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_entry_comparison(
        self,
        symbol: str,
        python_signal: str,
        kernel_signal: str,
        python_confidence: str,
        kernel_confidence: str,
        timestamp_ms: int,
    ) -> ComparisonResult:
        """Record an entry signal comparison.

        Compares signal direction (BUY/SELL/NEUTRAL) and confidence level.

        Parameters
        ----------
        symbol : str
            Trading symbol (e.g. ``"ETH"``).
        python_signal : str
            Python analysis signal (``"BUY"``, ``"SELL"``, ``"NEUTRAL"``).
        kernel_signal : str
            Kernel analysis signal.
        python_confidence : str
            Python confidence level (``"low"``, ``"medium"``, ``"high"``).
        kernel_confidence : str
            Kernel confidence level.
        timestamp_ms : int
            Comparison timestamp in epoch milliseconds.

        Returns
        -------
        ComparisonResult
        """
        py_sig = str(python_signal).upper()
        k_sig = str(kernel_signal).upper()
        py_conf = str(python_confidence).lower()
        k_conf = str(kernel_confidence).lower()

        signal_match = py_sig == k_sig
        conf_match = py_conf == k_conf
        is_match = signal_match and conf_match

        details_parts: list[str] = []
        if not signal_match:
            details_parts.append(f"signal: py={py_sig} vs kernel={k_sig}")
        if not conf_match:
            details_parts.append(f"confidence: py={py_conf} vs kernel={k_conf}")
        details = "; ".join(details_parts) if details_parts else "full agreement"

        result = ComparisonResult(
            symbol=symbol,
            timestamp_ms=timestamp_ms,
            comparison_type="entry",
            python_decision=f"{py_sig}/{py_conf}",
            kernel_decision=f"{k_sig}/{k_conf}",
            is_match=is_match,
            details=details,
        )

        self._record(result, signal_type=k_sig)
        return result

    def record_exit_comparison(
        self,
        symbol: str,
        python_action: str,
        kernel_action: str,
        python_reason: str,
        kernel_reason: str,
        timestamp_ms: int,
    ) -> ComparisonResult:
        """Record an exit decision comparison.

        Compares exit action (hold/full_close/partial_close) and reason.

        Parameters
        ----------
        symbol : str
            Trading symbol.
        python_action : str
            Python exit action (``"hold"``, ``"full_close"``, ``"partial_close"``).
        kernel_action : str
            Kernel exit action.
        python_reason : str
            Python exit reason (e.g. ``"trend_breakdown"``).
        kernel_reason : str
            Kernel exit reason (e.g. ``"stop_loss"``).
        timestamp_ms : int
            Comparison timestamp in epoch milliseconds.

        Returns
        -------
        ComparisonResult
        """
        py_act = str(python_action).lower()
        k_act = str(kernel_action).lower()
        py_reason = str(python_reason).lower()
        k_reason = str(kernel_reason).lower()

        action_match = py_act == k_act
        reason_match = py_reason == k_reason
        is_match = action_match and reason_match

        details_parts: list[str] = []
        if not action_match:
            details_parts.append(f"action: py={py_act} vs kernel={k_act}")
        if not reason_match:
            details_parts.append(f"reason: py={py_reason} vs kernel={k_reason}")
        details = "; ".join(details_parts) if details_parts else "full agreement"

        result = ComparisonResult(
            symbol=symbol,
            timestamp_ms=timestamp_ms,
            comparison_type="exit",
            python_decision=f"{py_act}/{py_reason}",
            kernel_decision=f"{k_act}/{k_reason}",
            is_match=is_match,
            details=details,
        )

        self._record(result, signal_type=f"exit_{k_act}")
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_agreement_stats(self) -> dict[str, Any]:
        """Return current agreement statistics.

        Returns
        -------
        dict
            Keys:

            * ``total_comparisons`` (int)
            * ``entry_agreement_rate`` (float, 0.0--1.0)
            * ``exit_agreement_rate`` (float, 0.0--1.0)
            * ``overall_agreement_rate`` (float)
            * ``rolling_agreement_rate`` (float) — last ``window_size`` comparisons
            * ``by_signal_type`` (dict[str, float])
            * ``alert_active`` (bool)
        """
        total = self._entry_total + self._exit_total

        entry_rate = (
            self._entry_match / self._entry_total
            if self._entry_total > 0
            else 1.0
        )
        exit_rate = (
            self._exit_match / self._exit_total
            if self._exit_total > 0
            else 1.0
        )
        overall_match = self._entry_match + self._exit_match
        overall_total = self._entry_total + self._exit_total
        overall_rate = overall_match / overall_total if overall_total > 0 else 1.0

        rolling_rate = self._compute_rolling_rate()

        by_signal: dict[str, float] = {}
        for sig in self._signal_total:
            st = self._signal_total[sig]
            sm = self._signal_match[sig]
            by_signal[sig] = sm / st if st > 0 else 1.0

        alert_active = rolling_rate < self._alert_threshold if total > 0 else False

        return {
            "total_comparisons": total,
            "entry_agreement_rate": entry_rate,
            "exit_agreement_rate": exit_rate,
            "overall_agreement_rate": overall_rate,
            "rolling_agreement_rate": rolling_rate,
            "by_signal_type": by_signal,
            "alert_active": alert_active,
        }

    def get_report(self) -> ShadowDecisionReport:
        """Return a full ``ShadowDecisionReport`` snapshot.

        Returns
        -------
        ShadowDecisionReport
        """
        stats = self.get_agreement_stats()
        alert_active, alert_msg, _ = self.check_alert()

        return ShadowDecisionReport(
            generated_at_ms=int(time.time() * 1000),
            total_comparisons=stats["total_comparisons"],
            entry_comparisons=self._entry_total,
            exit_comparisons=self._exit_total,
            entry_agreement_rate=stats["entry_agreement_rate"],
            exit_agreement_rate=stats["exit_agreement_rate"],
            overall_agreement_rate=stats["overall_agreement_rate"],
            rolling_agreement_rate=stats["rolling_agreement_rate"],
            alert_active=alert_active,
            alert_message=alert_msg,
            recent_disagreements=list(self._recent_disagreements),
            by_signal_type=stats["by_signal_type"],
        )

    def check_alert(self) -> tuple[bool, str, dict[str, Any]]:
        """Check if agreement rate has dropped below the configured threshold.

        Returns
        -------
        tuple[bool, str, dict]
            ``(alert_active, message, stats_dict)``
        """
        stats = self.get_agreement_stats()
        total = stats["total_comparisons"]
        rolling = stats["rolling_agreement_rate"]

        if total == 0:
            return False, "No comparisons recorded yet", stats

        if rolling < self._alert_threshold:
            msg = (
                f"ALERT: Shadow agreement rate {rolling:.1%} is below "
                f"threshold {self._alert_threshold:.0%} "
                f"(rolling window of last {min(total, self._window_size)} comparisons)"
            )
            logger.warning("[shadow] %s", msg)
            return True, msg, stats

        msg = (
            f"OK: Shadow agreement rate {rolling:.1%} is at or above "
            f"threshold {self._alert_threshold:.0%}"
        )
        return False, msg, stats

    # ------------------------------------------------------------------
    # Database logging
    # ------------------------------------------------------------------

    def log_comparison_to_db(
        self,
        comparison: ComparisonResult,
        db_path: str | None = None,
    ) -> str | None:
        """Log a comparison to the ``decision_events`` table.

        Each comparison is stored with ``event_type='shadow_comparison'``.

        Parameters
        ----------
        comparison : ComparisonResult
            The comparison to log.
        db_path : str, optional
            Path to the SQLite database.  If ``None``, attempts to import
            ``DB_PATH`` from ``strategy.mei_alpha_v1``.

        Returns
        -------
        str or None
            The decision event ID (ULID) if logged successfully, else ``None``.
        """
        if db_path is None:
            try:
                from strategy.mei_alpha_v1 import DB_PATH
                db_path = DB_PATH
            except ImportError:
                logger.warning("[shadow] cannot import DB_PATH; skipping DB logging")
                return None

        event_id = _generate_event_id()
        context = {
            "python_decision": comparison.python_decision,
            "kernel_decision": comparison.kernel_decision,
            "is_match": comparison.is_match,
            "comparison_type": comparison.comparison_type,
            "details": comparison.details,
        }

        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            col_rows = conn.execute("PRAGMA table_info(decision_events)").fetchall()
            has_run_fingerprint = any(str(row[1]) == "run_fingerprint" for row in col_rows)
            run_fingerprint = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip() or "unknown"
            try:
                from strategy.mei_alpha_v1 import get_run_fingerprint as _get_run_fingerprint

                run_fingerprint = str(_get_run_fingerprint() or run_fingerprint)
            except Exception:
                pass
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
                        comparison.timestamp_ms,
                        comparison.symbol,
                        "shadow_comparison",
                        "match" if comparison.is_match else "mismatch",
                        "shadow_evaluation",
                        "shadow_mode",
                        comparison.comparison_type,
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
                        comparison.timestamp_ms,
                        comparison.symbol,
                        "shadow_comparison",
                        "match" if comparison.is_match else "mismatch",
                        "shadow_evaluation",
                        "shadow_mode",
                        comparison.comparison_type,
                        json.dumps(context, separators=(",", ":")),
                    ),
                )
            conn.commit()
            return event_id
        except Exception:
            logger.exception("[shadow] failed to log comparison to DB")
            return None
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all tracked comparisons and statistics."""
        self._comparisons.clear()
        self._signal_total.clear()
        self._signal_match.clear()
        self._entry_total = 0
        self._entry_match = 0
        self._exit_total = 0
        self._exit_match = 0
        self._recent_disagreements.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record(self, result: ComparisonResult, signal_type: str) -> None:
        """Record a comparison result into all tracking structures."""
        self._comparisons.append(result)

        # Per-type counters.
        self._signal_total[signal_type] += 1
        if result.is_match:
            self._signal_match[signal_type] += 1

        # Entry / exit counters.
        if result.comparison_type == "entry":
            self._entry_total += 1
            if result.is_match:
                self._entry_match += 1
        elif result.comparison_type == "exit":
            self._exit_total += 1
            if result.is_match:
                self._exit_match += 1

        # Disagreements ring-buffer.
        if not result.is_match:
            self._recent_disagreements.append(result)

        # Log to console.
        if result.is_match:
            logger.debug(
                "[shadow] %s %s agreement for %s",
                result.comparison_type,
                signal_type,
                result.symbol,
            )
        else:
            logger.warning(
                "[shadow] %s %s MISMATCH for %s: py=%s kernel=%s (%s)",
                result.comparison_type,
                signal_type,
                result.symbol,
                result.python_decision,
                result.kernel_decision,
                result.details,
            )

    def _compute_rolling_rate(self) -> float:
        """Compute agreement rate over the last ``window_size`` comparisons."""
        if not self._comparisons:
            return 1.0

        window = list(self._comparisons)[-self._window_size:]
        matches = sum(1 for c in window if c.is_match)
        return matches / len(window)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def get_decision_mode(config: dict[str, Any] | None = None) -> DecisionMode:
    """Read the current decision mode from environment or config.

    Resolution order:

    1. ``KERNEL_DECISION_MODE`` environment variable (if set and valid).
    2. ``config["decision_mode"]`` (if provided and valid).
    3. Default: ``DecisionMode.SHADOW``.

    Parameters
    ----------
    config : dict, optional
        Config dict that may contain a ``"decision_mode"`` key.

    Returns
    -------
    DecisionMode
    """
    env_val = os.environ.get("KERNEL_DECISION_MODE", "").strip().lower()
    if env_val:
        try:
            return DecisionMode(env_val)
        except ValueError:
            logger.warning(
                "[shadow] invalid KERNEL_DECISION_MODE=%r, falling back to config/default",
                env_val,
            )

    if config is not None:
        cfg_val = str(config.get("decision_mode", "")).strip().lower()
        if cfg_val:
            try:
                return DecisionMode(cfg_val)
            except ValueError:
                logger.warning(
                    "[shadow] invalid config decision_mode=%r, falling back to default",
                    cfg_val,
                )

    return DecisionMode.SHADOW


def should_run_python(mode: DecisionMode) -> bool:
    """Return ``True`` if the given mode requires running the Python path.

    True for ``SHADOW`` and ``PYTHON`` modes.
    """
    return mode in (DecisionMode.SHADOW, DecisionMode.PYTHON)


def should_run_kernel(mode: DecisionMode) -> bool:
    """Return ``True`` if the given mode requires running the kernel path.

    True for ``SHADOW`` and ``KERNEL`` modes.
    """
    return mode in (DecisionMode.SHADOW, DecisionMode.KERNEL)


def is_shadow_mode(mode: DecisionMode) -> bool:
    """Return ``True`` only for ``DecisionMode.SHADOW``."""
    return mode is DecisionMode.SHADOW
