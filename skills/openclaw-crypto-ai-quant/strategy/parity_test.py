"""AQC-822: Decision parity test -- backtest vs live kernel.

Verifies that the Rust decision kernel produces identical, deterministic
results when given the same inputs.  This is the keystone of the V8 SSOT
guarantee: if the kernel is deterministic, backtest and live must agree.

Classes
-------
DecisionParityHarness
    Record live decisions, replay them through ``bt_runtime``, compare.

Data classes
------------
ParityResult      -- outcome of replaying a single recording
ParityReport      -- aggregate of all replayed recordings
DeterminismResult -- outcome of N identical invocations

Module helpers
--------------
extract_action(result_json)
    Extract primary action (BUY/SELL/HOLD/CLOSE) from a DecisionResult.
normalize_result_for_comparison(result_json)
    Strip non-deterministic fields before deep comparison.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

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
# Non-deterministic fields stripped before comparison
# ---------------------------------------------------------------------------

#: Top-level keys in a DecisionResult that may vary across invocations
#: even when the logical decision is identical.
_NON_DETERMINISTIC_STATE_KEYS = frozenset({"timestamp_ms"})

#: Keys inside ``diagnostics`` that are informational / timing-dependent.
_NON_DETERMINISTIC_DIAG_KEYS = frozenset({"step"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ParityResult:
    """Outcome of replaying a single recorded decision."""

    recording_id: int
    is_match: bool
    diffs: list[str]
    original_action: str  # BUY / SELL / HOLD / CLOSE
    replayed_action: str


@dataclasses.dataclass
class ParityReport:
    """Aggregate result of replaying all recorded decisions."""

    total_decisions: int
    matches: int
    mismatches: int
    match_rate: float
    is_perfect_parity: bool  # True when 100 %
    mismatch_details: list[ParityResult]


@dataclasses.dataclass
class DeterminismResult:
    """Result of running the same input N times."""

    iterations: int
    is_deterministic: bool
    variations: list[str]  # empty when deterministic


# ---------------------------------------------------------------------------
# Internal recording container
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _Recording:
    """Stored inputs + expected output for a single decision."""

    recording_id: int
    state_json: str
    event_json: str
    params_json: str
    result_json: str
    exit_params_json: str | None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def extract_action(result_json: str) -> str:
    """Extract the primary action from a kernel ``DecisionResult``.

    Resolution order:

    1. If ``intents`` is non-empty, resolve from the first intent's
       ``kind`` and ``side`` fields.  The Rust kernel serializes
       ``OrderIntentKind`` as ``"open"`` / ``"add"`` / ``"close"`` /
       ``"hold"`` / ``"reverse"`` and ``PositionSide`` as ``"long"`` /
       ``"short"``.
    2. If ``fills`` is non-empty and there is a corresponding ``close``
       intent, return ``"CLOSE"``.  Otherwise map fill ``side``
       (``"long"`` -> ``"BUY"``, ``"short"`` -> ``"SELL"``).
    3. Fall back to ``"HOLD"``.

    Parameters
    ----------
    result_json : str
        JSON string of the full kernel response envelope
        ``{"ok": true, "decision": {...}}``.

    Returns
    -------
    str
        One of ``"BUY"``, ``"SELL"``, ``"HOLD"``, ``"CLOSE"``.
    """
    data = json.loads(result_json) if isinstance(result_json, str) else result_json
    decision = data.get("decision", data)

    intents = decision.get("intents", [])
    if intents:
        first = intents[0]
        kind = str(first.get("kind", "")).lower()
        side = str(first.get("side", "")).lower()

        if kind == "close":
            return "CLOSE"
        if kind in ("open", "add"):
            return "BUY" if side == "long" else "SELL"
        if kind == "hold":
            return "HOLD"
        if kind == "reverse":
            return "BUY" if side == "long" else "SELL"
        # Unknown kind — return upper-cased or HOLD
        return kind.upper() if kind else "HOLD"

    fills = decision.get("fills", [])
    if fills:
        # Check if any intent was a close (fills carry PositionSide, not
        # the intent kind, so correlate with intents if available).
        intent_kinds = {str(i.get("kind", "")).lower() for i in intents}
        if "close" in intent_kinds:
            return "CLOSE"
        # No close intent — map fill side to action
        side = str(fills[0].get("side", "")).lower()
        if side == "long":
            return "BUY"
        if side == "short":
            return "SELL"
        return "HOLD"

    return "HOLD"


def normalize_result_for_comparison(result_json: str) -> dict[str, Any]:
    """Strip non-deterministic fields from a kernel result for comparison.

    Removes timing-dependent metadata (``timestamp_ms`` from state,
    ``step`` from diagnostics) and ``intent_id`` from intents/fills,
    while preserving all decision-relevant fields (intents, fills,
    diagnostics gate/signal data, state positions, cash).

    Parameters
    ----------
    result_json : str
        JSON string of the full kernel response envelope.

    Returns
    -------
    dict
        Cleaned result dict ready for deep comparison.
    """
    data = json.loads(result_json) if isinstance(result_json, str) else result_json
    data = copy.deepcopy(data)

    decision = data.get("decision", data)

    # --- State: strip timing fields ---
    state = decision.get("state", {})
    for key in _NON_DETERMINISTIC_STATE_KEYS:
        state.pop(key, None)

    # --- Diagnostics: strip step counter ---
    diag = decision.get("diagnostics", {})
    for key in _NON_DETERMINISTIC_DIAG_KEYS:
        diag.pop(key, None)

    # --- Intents: strip intent_id (timestamp-based) ---
    for intent in decision.get("intents", []):
        intent.pop("intent_id", None)

    # --- Fills: strip intent_id ---
    for fill in decision.get("fills", []):
        fill.pop("intent_id", None)

    return data


# ---------------------------------------------------------------------------
# DecisionParityHarness
# ---------------------------------------------------------------------------


class DecisionParityHarness:
    """Replays recorded decisions through the kernel to verify determinism.

    Parameters
    ----------
    config : dict, optional
        Optional configuration.  Currently unused; reserved for future
        tolerance settings.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._recordings: list[_Recording] = []
        self._next_id: int = 0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_decision(
        self,
        state_json: str,
        event_json: str,
        params_json: str,
        result_json: str,
        exit_params_json: str | None = None,
    ) -> int:
        """Record a live decision (inputs + output) for later replay.

        Parameters
        ----------
        state_json : str
            Kernel ``StrategyState`` JSON fed to the decision.
        event_json : str
            ``MarketEvent`` JSON.
        params_json : str
            ``KernelParams`` JSON.
        result_json : str
            Actual result JSON returned by the kernel.
        exit_params_json : str, optional
            If provided, replay uses ``step_full`` instead of
            ``step_decision``.

        Returns
        -------
        int
            Unique recording ID.
        """
        rec_id = self._next_id
        self._next_id += 1
        self._recordings.append(
            _Recording(
                recording_id=rec_id,
                state_json=state_json,
                event_json=event_json,
                params_json=params_json,
                result_json=result_json,
                exit_params_json=exit_params_json,
            )
        )
        return rec_id

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay_decision(self, recording_id: int) -> ParityResult:
        """Replay a recorded decision through the kernel and compare.

        Parameters
        ----------
        recording_id : int
            ID returned by :meth:`record_decision`.

        Returns
        -------
        ParityResult

        Raises
        ------
        ValueError
            If *recording_id* is not found.
        RuntimeError
            If ``bt_runtime`` is not available.
        """
        rec = self._find_recording(recording_id)
        replayed_json = self._call_kernel(rec)
        is_match, diffs = self.compare_results(rec.result_json, replayed_json)

        original_action = extract_action(rec.result_json)
        replayed_action = extract_action(replayed_json)

        return ParityResult(
            recording_id=recording_id,
            is_match=is_match,
            diffs=diffs,
            original_action=original_action,
            replayed_action=replayed_action,
        )

    def replay_all(self) -> ParityReport:
        """Replay every recorded decision and build an aggregate report.

        Returns
        -------
        ParityReport
        """
        results: list[ParityResult] = []
        for rec in self._recordings:
            results.append(self.replay_decision(rec.recording_id))

        matches = sum(1 for r in results if r.is_match)
        mismatches = sum(1 for r in results if not r.is_match)
        total = len(results)
        rate = matches / total if total > 0 else 1.0

        return ParityReport(
            total_decisions=total,
            matches=matches,
            mismatches=mismatches,
            match_rate=rate,
            is_perfect_parity=(mismatches == 0),
            mismatch_details=[r for r in results if not r.is_match],
        )

    # ------------------------------------------------------------------
    # Determinism verification
    # ------------------------------------------------------------------

    def verify_determinism(
        self,
        state_json: str,
        event_json: str,
        params_json: str,
        exit_params_json: str | None = None,
        iterations: int = 10,
    ) -> DeterminismResult:
        """Run the same decision *iterations* times and verify identity.

        Parameters
        ----------
        state_json, event_json, params_json : str
            Kernel inputs.
        exit_params_json : str, optional
            If provided, ``step_full`` is used.
        iterations : int
            How many times to run (default 10).

        Returns
        -------
        DeterminismResult

        Raises
        ------
        RuntimeError
            If ``bt_runtime`` is not available.
        """
        if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
            raise RuntimeError("bt_runtime is not available")

        rec = _Recording(
            recording_id=-1,
            state_json=state_json,
            event_json=event_json,
            params_json=params_json,
            result_json="",  # not used for replay
            exit_params_json=exit_params_json,
        )

        baseline = self._call_kernel(rec)
        baseline_norm = normalize_result_for_comparison(baseline)
        variations: list[str] = []

        for i in range(1, iterations):
            current = self._call_kernel(rec)
            current_norm = normalize_result_for_comparison(current)
            if baseline_norm != current_norm:
                _, diffs = self.compare_results(baseline, current)
                variations.append(f"iteration {i}: {'; '.join(diffs)}")

        return DeterminismResult(
            iterations=iterations,
            is_deterministic=len(variations) == 0,
            variations=variations,
        )

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    def build_fixture(
        self,
        recordings: list[int] | None = None,
        output_path: str = "parity_fixture.json",
    ) -> str:
        """Export recordings as a JSON fixture file for CI.

        Parameters
        ----------
        recordings : list[int], optional
            Recording IDs to include.  ``None`` = all.
        output_path : str
            Destination file path.

        Returns
        -------
        str
            The *output_path* written to.
        """
        if recordings is None:
            recs = self._recordings
        else:
            recs = [self._find_recording(rid) for rid in recordings]

        items: list[dict[str, Any]] = []
        for rec in recs:
            item: dict[str, Any] = {
                "state": json.loads(rec.state_json),
                "event": json.loads(rec.event_json),
                "params": json.loads(rec.params_json),
                "expected_result": json.loads(rec.result_json),
            }
            if rec.exit_params_json is not None:
                item["exit_params"] = json.loads(rec.exit_params_json)
            items.append(item)

        with open(output_path, "w") as fh:
            json.dump(items, fh, indent=2)

        logger.info("[parity] wrote %d recordings to %s", len(items), output_path)
        return output_path

    def load_fixture(self, fixture_path: str) -> int:
        """Load a fixture file and populate recordings.

        Parameters
        ----------
        fixture_path : str
            Path to a JSON fixture produced by :meth:`build_fixture`.

        Returns
        -------
        int
            Number of recordings loaded.
        """
        with open(fixture_path) as fh:
            items = json.load(fh)

        count = 0
        for item in items:
            exit_params_json: str | None = None
            if "exit_params" in item:
                exit_params_json = json.dumps(item["exit_params"])

            self.record_decision(
                state_json=json.dumps(item["state"]),
                event_json=json.dumps(item["event"]),
                params_json=json.dumps(item["params"]),
                result_json=json.dumps(item["expected_result"]),
                exit_params_json=exit_params_json,
            )
            count += 1

        logger.info("[parity] loaded %d recordings from %s", count, fixture_path)
        return count

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare_results(
        self,
        original_json: str,
        replayed_json: str,
    ) -> tuple[bool, list[str]]:
        """Deep-compare two DecisionResult JSON strings.

        Non-deterministic fields (timestamps, IDs, step counters) are
        stripped before comparison.

        Parameters
        ----------
        original_json : str
            The expected / recorded result.
        replayed_json : str
            The replayed result from the kernel.

        Returns
        -------
        tuple[bool, list[str]]
            ``(is_match, diffs)`` where *diffs* lists human-readable
            descriptions of each difference found.
        """
        orig = normalize_result_for_comparison(original_json)
        repl = normalize_result_for_comparison(replayed_json)

        if orig == repl:
            return True, []

        diffs: list[str] = []
        orig_dec = orig.get("decision", orig)
        repl_dec = repl.get("decision", repl)

        # Compare intents
        orig_intents = orig_dec.get("intents", [])
        repl_intents = repl_dec.get("intents", [])
        if orig_intents != repl_intents:
            diffs.append(
                f"intents differ: original={json.dumps(orig_intents)} "
                f"vs replayed={json.dumps(repl_intents)}"
            )

        # Compare fills
        orig_fills = orig_dec.get("fills", [])
        repl_fills = repl_dec.get("fills", [])
        if orig_fills != repl_fills:
            diffs.append(
                f"fills differ: original={json.dumps(orig_fills)} "
                f"vs replayed={json.dumps(repl_fills)}"
            )

        # Compare state (positions, cash)
        orig_state = orig_dec.get("state", {})
        repl_state = repl_dec.get("state", {})
        if orig_state != repl_state:
            diffs.append(
                f"state differs: original={json.dumps(orig_state)} "
                f"vs replayed={json.dumps(repl_state)}"
            )

        # Compare diagnostics
        orig_diag = orig_dec.get("diagnostics", {})
        repl_diag = repl_dec.get("diagnostics", {})
        if orig_diag != repl_diag:
            diffs.append(
                f"diagnostics differ: original={json.dumps(orig_diag)} "
                f"vs replayed={json.dumps(repl_diag)}"
            )

        # If no specific diffs found but overall mismatch, report generic
        if not diffs:
            diffs.append("results differ (unspecified fields)")

        return False, diffs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_recording(self, recording_id: int) -> _Recording:
        """Look up a recording by ID.

        Raises
        ------
        ValueError
            If not found.
        """
        for rec in self._recordings:
            if rec.recording_id == recording_id:
                return rec
        raise ValueError(f"recording {recording_id} not found")

    def _call_kernel(self, rec: _Recording) -> str:
        """Invoke ``bt_runtime.step_decision`` or ``step_full``.

        Raises
        ------
        RuntimeError
            If ``bt_runtime`` is not available or the kernel returns
            an error envelope (``ok: false``).
        """
        if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
            raise RuntimeError("bt_runtime is not available")

        if rec.exit_params_json is not None:
            result = _bt_runtime.step_full(
                rec.state_json,
                rec.event_json,
                rec.params_json,
                rec.exit_params_json,
            )
        else:
            result = _bt_runtime.step_decision(
                rec.state_json,
                rec.event_json,
                rec.params_json,
            )

        # Validate the kernel response envelope
        try:
            envelope = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            raise RuntimeError(f"kernel returned invalid JSON: {result!r:.200}")

        if not envelope.get("ok", False):
            error = envelope.get("error", {})
            code = error.get("code", "UNKNOWN")
            message = error.get("message", "unknown error")
            details = error.get("details", [])
            raise RuntimeError(
                f"kernel error {code}: {message}"
                + (f" — {'; '.join(details)}" if details else "")
            )

        return result
