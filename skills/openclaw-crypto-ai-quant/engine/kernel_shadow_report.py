"""Kernel shadow test reporting infrastructure (AQC-752).

Accumulates live-vs-kernel parity comparisons over time and provides
convergence analysis.  Used by PaperTrader's kernel delegation (AQC-742)
to replace ad-hoc log-line discrepancy warnings with structured tracking.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_SHADOW_MAX_COMPARISONS = 50000
MIN_SHADOW_MAX_COMPARISONS = 1
MAX_SHADOW_MAX_COMPARISONS = 5_000_000


def _shadow_max_comparisons() -> int:
    raw = os.getenv("AI_QUANT_SHADOW_MAX_COMPARISONS")
    if raw is None:
        return int(DEFAULT_SHADOW_MAX_COMPARISONS)
    try:
        value = int(float(str(raw).strip()))
    except Exception:
        return int(DEFAULT_SHADOW_MAX_COMPARISONS)
    return int(max(MIN_SHADOW_MAX_COMPARISONS, min(MAX_SHADOW_MAX_COMPARISONS, value)))


@dataclass
class ShadowComparison:
    """Single parity check between the Python live path and the Rust kernel."""

    timestamp: float
    metric: str  # "balance", "pnl", "margin", etc.
    old_value: float
    kernel_value: float
    delta: float
    tolerance: float
    passed: bool


@dataclass
class ShadowReport:
    """Accumulates kernel shadow comparisons and evaluates convergence."""

    comparisons: deque[ShadowComparison] = field(default_factory=lambda: deque(maxlen=_shadow_max_comparisons()))

    # ── core API ────────────────────────────────────────────────────

    def add_comparison(
        self,
        metric: str,
        old_val: float,
        kernel_val: float,
        tolerance: float = 0.01,
        *,
        timestamp: float | None = None,
    ) -> ShadowComparison:
        """Record a single parity check and return it."""
        delta = abs(old_val - kernel_val)
        passed = delta <= tolerance
        comp = ShadowComparison(
            timestamp=timestamp if timestamp is not None else time.time(),
            metric=metric,
            old_value=old_val,
            kernel_value=kernel_val,
            delta=delta,
            tolerance=tolerance,
            passed=passed,
        )
        self.comparisons.append(comp)
        if not passed:
            logger.warning(
                "[shadow] FAIL metric=%s old=%.6f kernel=%.6f delta=%.6f tol=%.6f",
                metric,
                old_val,
                kernel_val,
                delta,
                tolerance,
            )
        return comp

    def summary(self) -> dict:
        """Return aggregate statistics for all recorded comparisons."""
        total = len(self.comparisons)
        if total == 0:
            return {
                "total_checks": 0,
                "passes": 0,
                "failures": 0,
                "failure_rate": 0.0,
                "worst_delta": 0.0,
                "worst_metric": None,
            }
        passes = sum(1 for c in self.comparisons if c.passed)
        failures = total - passes
        worst = max(self.comparisons, key=lambda c: c.delta)
        return {
            "total_checks": total,
            "passes": passes,
            "failures": failures,
            "failure_rate": failures / total,
            "worst_delta": worst.delta,
            "worst_metric": worst.metric,
        }

    def is_converged(
        self,
        min_checks: int = 100,
        max_failure_rate: float = 0.01,
    ) -> bool:
        """True when enough checks have passed with an acceptable failure rate."""
        total = len(self.comparisons)
        if total < min_checks:
            return False
        failures = sum(1 for c in self.comparisons if not c.passed)
        return (failures / total) <= max_failure_rate

    # ── persistence ─────────────────────────────────────────────────

    def to_json(self, path: str) -> None:
        """Serialize the report to a JSON file."""
        data = [asdict(c) for c in self.comparisons]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("[shadow] saved %d comparisons to %s", len(data), path)

    @classmethod
    def from_json(cls, path: str) -> ShadowReport:
        """Load a report from a JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        report = cls()
        for entry in data:
            report.comparisons.append(ShadowComparison(**entry))
        logger.debug("[shadow] loaded %d comparisons from %s", len(report.comparisons), path)
        return report
