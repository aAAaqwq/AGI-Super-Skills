"""Tests for AQC-821: Shadow mode — parallel Python + kernel decision tracking.

Covers:
- DecisionMode enum and mode helpers (get_decision_mode, should_run_*)
- ShadowDecisionTracker.record_entry_comparison()
- ShadowDecisionTracker.record_exit_comparison()
- ShadowDecisionTracker.get_agreement_stats()
- ShadowDecisionTracker.check_alert()
- ShadowDecisionTracker.get_report() — ShadowDecisionReport generation
- ShadowDecisionTracker.log_comparison_to_db() — DB logging
"""

from __future__ import annotations

import json
import sqlite3

from strategy.shadow_mode import (
    ComparisonResult,
    DecisionMode,
    ShadowDecisionReport,
    ShadowDecisionTracker,
    get_decision_mode,
    is_shadow_mode,
    should_run_kernel,
    should_run_python,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1700000000000


def _create_decision_events_table(db_path: str) -> None:
    """Create the decision_events table for testing log_comparison_to_db()."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_events (
            id TEXT PRIMARY KEY,
            timestamp_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            decision_phase TEXT NOT NULL,
            parent_decision_id TEXT,
            trade_id INTEGER,
            triggered_by TEXT,
            action_taken TEXT,
            rejection_reason TEXT,
            context_json TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _make_tracker(**kwargs) -> ShadowDecisionTracker:
    """Build a ShadowDecisionTracker with sensible test defaults."""
    defaults = {"window_size": 100, "alert_threshold": 0.95}
    defaults.update(kwargs)
    return ShadowDecisionTracker(**defaults)


def _record_n_entry_matches(tracker: ShadowDecisionTracker, n: int, start_ts: int = _BASE_TS) -> None:
    """Record *n* matching entry comparisons."""
    for i in range(n):
        tracker.record_entry_comparison(
            symbol="ETH",
            python_signal="BUY",
            kernel_signal="BUY",
            python_confidence="high",
            kernel_confidence="high",
            timestamp_ms=start_ts + i * 1000,
        )


def _record_n_entry_mismatches(tracker: ShadowDecisionTracker, n: int, start_ts: int = _BASE_TS) -> None:
    """Record *n* mismatching entry comparisons."""
    for i in range(n):
        tracker.record_entry_comparison(
            symbol="ETH",
            python_signal="BUY",
            kernel_signal="SELL",
            python_confidence="high",
            kernel_confidence="low",
            timestamp_ms=start_ts + i * 1000,
        )


# ===========================================================================
# TestDecisionMode
# ===========================================================================


class TestDecisionMode:
    """Tests for the DecisionMode enum and module-level helper functions."""

    def test_default_mode_is_shadow(self, monkeypatch):
        """get_decision_mode() returns SHADOW when no env var or config is set."""
        monkeypatch.delenv("KERNEL_DECISION_MODE", raising=False)
        mode = get_decision_mode()
        assert mode is DecisionMode.SHADOW

    def test_env_var_override(self, monkeypatch):
        """KERNEL_DECISION_MODE env var overrides the default."""
        monkeypatch.setenv("KERNEL_DECISION_MODE", "kernel")
        assert get_decision_mode() is DecisionMode.KERNEL

        monkeypatch.setenv("KERNEL_DECISION_MODE", "python")
        assert get_decision_mode() is DecisionMode.PYTHON

        monkeypatch.setenv("KERNEL_DECISION_MODE", "shadow")
        assert get_decision_mode() is DecisionMode.SHADOW

    def test_config_override(self, monkeypatch):
        """Config dict decision_mode is used when env var is not set."""
        monkeypatch.delenv("KERNEL_DECISION_MODE", raising=False)
        assert get_decision_mode({"decision_mode": "kernel"}) is DecisionMode.KERNEL
        assert get_decision_mode({"decision_mode": "python"}) is DecisionMode.PYTHON

    def test_env_var_takes_precedence_over_config(self, monkeypatch):
        """Env var wins when both env var and config are set."""
        monkeypatch.setenv("KERNEL_DECISION_MODE", "kernel")
        mode = get_decision_mode({"decision_mode": "python"})
        assert mode is DecisionMode.KERNEL

    def test_invalid_env_var_falls_back(self, monkeypatch):
        """Invalid env var falls back to config, then default."""
        monkeypatch.setenv("KERNEL_DECISION_MODE", "bogus")
        assert get_decision_mode() is DecisionMode.SHADOW
        assert get_decision_mode({"decision_mode": "kernel"}) is DecisionMode.KERNEL

    def test_should_run_helpers(self):
        """should_run_python/kernel return correct values for each mode."""
        # SHADOW: both run
        assert should_run_python(DecisionMode.SHADOW) is True
        assert should_run_kernel(DecisionMode.SHADOW) is True
        assert is_shadow_mode(DecisionMode.SHADOW) is True

        # KERNEL: only kernel
        assert should_run_python(DecisionMode.KERNEL) is False
        assert should_run_kernel(DecisionMode.KERNEL) is True
        assert is_shadow_mode(DecisionMode.KERNEL) is False

        # PYTHON: only python
        assert should_run_python(DecisionMode.PYTHON) is True
        assert should_run_kernel(DecisionMode.PYTHON) is False
        assert is_shadow_mode(DecisionMode.PYTHON) is False


# ===========================================================================
# TestRecordEntryComparison
# ===========================================================================


class TestRecordEntryComparison:
    """Tests for ShadowDecisionTracker.record_entry_comparison()."""

    def test_match_recorded(self):
        """Matching signals and confidence are recorded as a match."""
        tracker = _make_tracker()
        result = tracker.record_entry_comparison(
            symbol="ETH",
            python_signal="BUY",
            kernel_signal="BUY",
            python_confidence="high",
            kernel_confidence="high",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is True
        assert result.comparison_type == "entry"
        assert result.symbol == "ETH"
        assert "agreement" in result.details.lower()

    def test_signal_mismatch(self):
        """Different signals are recorded as a mismatch."""
        tracker = _make_tracker()
        result = tracker.record_entry_comparison(
            symbol="BTC",
            python_signal="BUY",
            kernel_signal="SELL",
            python_confidence="high",
            kernel_confidence="high",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is False
        assert "signal" in result.details.lower()

    def test_confidence_mismatch(self):
        """Same signal but different confidence is recorded as a mismatch."""
        tracker = _make_tracker()
        result = tracker.record_entry_comparison(
            symbol="ETH",
            python_signal="BUY",
            kernel_signal="BUY",
            python_confidence="high",
            kernel_confidence="low",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is False
        assert "confidence" in result.details.lower()

    def test_signal_types_tracked(self):
        """Per-signal-type tracking counts matches correctly."""
        tracker = _make_tracker()
        # 2 BUY matches
        for i in range(2):
            tracker.record_entry_comparison("ETH", "BUY", "BUY", "high", "high", _BASE_TS + i)
        # 1 SELL match
        tracker.record_entry_comparison("ETH", "SELL", "SELL", "high", "high", _BASE_TS + 10)
        # 1 BUY mismatch (confidence differs)
        tracker.record_entry_comparison("ETH", "BUY", "BUY", "high", "low", _BASE_TS + 20)

        stats = tracker.get_agreement_stats()
        by_sig = stats["by_signal_type"]
        # BUY: 2 match + 1 mismatch = 2/3
        assert abs(by_sig["BUY"] - 2.0 / 3.0) < 1e-9
        # SELL: 1 match / 1 total
        assert by_sig["SELL"] == 1.0

    def test_returns_comparison_result(self):
        """Return type is ComparisonResult with correct fields."""
        tracker = _make_tracker()
        result = tracker.record_entry_comparison("SOL", "NEUTRAL", "NEUTRAL", "low", "low", _BASE_TS)
        assert isinstance(result, ComparisonResult)
        assert result.python_decision == "NEUTRAL/low"
        assert result.kernel_decision == "NEUTRAL/low"
        assert result.timestamp_ms == _BASE_TS

    def test_case_normalisation(self):
        """Signals are normalised to uppercase, confidence to lowercase."""
        tracker = _make_tracker()
        result = tracker.record_entry_comparison("ETH", "buy", "Buy", "HIGH", "High", _BASE_TS)
        assert result.is_match is True
        assert result.python_decision == "BUY/high"
        assert result.kernel_decision == "BUY/high"


# ===========================================================================
# TestRecordExitComparison
# ===========================================================================


class TestRecordExitComparison:
    """Tests for ShadowDecisionTracker.record_exit_comparison()."""

    def test_hold_hold_match(self):
        """Both hold — should be a match."""
        tracker = _make_tracker()
        result = tracker.record_exit_comparison(
            symbol="ETH",
            python_action="hold",
            kernel_action="hold",
            python_reason="none",
            kernel_reason="none",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is True
        assert result.comparison_type == "exit"

    def test_close_close_match(self):
        """Both full_close with same reason — should match."""
        tracker = _make_tracker()
        result = tracker.record_exit_comparison(
            symbol="BTC",
            python_action="full_close",
            kernel_action="full_close",
            python_reason="stop_loss",
            kernel_reason="stop_loss",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is True

    def test_close_hold_mismatch(self):
        """One closes, other holds — mismatch."""
        tracker = _make_tracker()
        result = tracker.record_exit_comparison(
            symbol="ETH",
            python_action="full_close",
            kernel_action="hold",
            python_reason="trend_breakdown",
            kernel_reason="none",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is False
        assert "action" in result.details.lower()

    def test_reason_mismatch(self):
        """Same action but different reason — mismatch."""
        tracker = _make_tracker()
        result = tracker.record_exit_comparison(
            symbol="ETH",
            python_action="full_close",
            kernel_action="full_close",
            python_reason="stop_loss",
            kernel_reason="take_profit",
            timestamp_ms=_BASE_TS,
        )
        assert result.is_match is False
        assert "reason" in result.details.lower()

    def test_returns_comparison_result(self):
        """Return type is ComparisonResult with correct fields."""
        tracker = _make_tracker()
        result = tracker.record_exit_comparison("SOL", "hold", "hold", "none", "none", _BASE_TS)
        assert isinstance(result, ComparisonResult)
        assert result.python_decision == "hold/none"
        assert result.kernel_decision == "hold/none"

    def test_case_normalisation(self):
        """Actions and reasons are normalised to lowercase."""
        tracker = _make_tracker()
        result = tracker.record_exit_comparison("ETH", "Hold", "HOLD", "None", "NONE", _BASE_TS)
        assert result.is_match is True
        assert result.python_decision == "hold/none"


# ===========================================================================
# TestAgreementStats
# ===========================================================================


class TestAgreementStats:
    """Tests for ShadowDecisionTracker.get_agreement_stats()."""

    def test_100_percent_agreement(self):
        """All matches yields 1.0 agreement everywhere."""
        tracker = _make_tracker()
        _record_n_entry_matches(tracker, 10)
        stats = tracker.get_agreement_stats()

        assert stats["total_comparisons"] == 10
        assert stats["entry_agreement_rate"] == 1.0
        assert stats["overall_agreement_rate"] == 1.0
        assert stats["rolling_agreement_rate"] == 1.0
        assert stats["alert_active"] is False

    def test_mixed_agreement(self):
        """Mix of matches and mismatches yields correct rates."""
        tracker = _make_tracker()
        _record_n_entry_matches(tracker, 8)
        _record_n_entry_mismatches(tracker, 2, start_ts=_BASE_TS + 100000)

        stats = tracker.get_agreement_stats()
        assert stats["total_comparisons"] == 10
        assert abs(stats["entry_agreement_rate"] - 0.8) < 1e-9
        assert abs(stats["overall_agreement_rate"] - 0.8) < 1e-9

    def test_rolling_window_limits(self):
        """Rolling window only considers the last window_size comparisons."""
        tracker = _make_tracker(window_size=10)

        # Record 10 mismatches then 10 matches
        _record_n_entry_mismatches(tracker, 10, start_ts=_BASE_TS)
        _record_n_entry_matches(tracker, 10, start_ts=_BASE_TS + 100000)

        stats = tracker.get_agreement_stats()
        # Rolling window of last 10 should be all matches = 1.0
        assert stats["rolling_agreement_rate"] == 1.0
        # Overall should be 10/20 = 0.5
        assert abs(stats["overall_agreement_rate"] - 0.5) < 1e-9

    def test_comparison_buffer_is_bounded(self):
        tracker = _make_tracker(window_size=10)
        _record_n_entry_matches(tracker, 35)

        assert len(tracker._comparisons) == 20
        stats = tracker.get_agreement_stats()
        assert stats["total_comparisons"] == 35
        assert stats["rolling_agreement_rate"] == 1.0

    def test_max_comparisons_is_clamped_to_window_size(self):
        tracker = ShadowDecisionTracker(window_size=10, config={"max_comparisons": 1})
        assert tracker._max_comparisons == 10

        _record_n_entry_matches(tracker, 25)

        assert len(tracker._comparisons) == 10
        stats = tracker.get_agreement_stats()
        assert stats["total_comparisons"] == 25
        assert stats["rolling_agreement_rate"] == 1.0

    def test_by_signal_type_breakdown(self):
        """Per-signal type stats are computed correctly."""
        tracker = _make_tracker()
        # BUY match
        tracker.record_entry_comparison("ETH", "BUY", "BUY", "high", "high", _BASE_TS)
        # SELL mismatch
        tracker.record_entry_comparison("ETH", "BUY", "SELL", "high", "high", _BASE_TS + 1)
        # Exit hold match
        tracker.record_exit_comparison("ETH", "hold", "hold", "none", "none", _BASE_TS + 2)

        stats = tracker.get_agreement_stats()
        by_sig = stats["by_signal_type"]
        assert by_sig["BUY"] == 1.0
        assert by_sig["SELL"] == 0.0
        assert by_sig["exit_hold"] == 1.0

    def test_empty_tracker(self):
        """Empty tracker returns sane defaults."""
        tracker = _make_tracker()
        stats = tracker.get_agreement_stats()

        assert stats["total_comparisons"] == 0
        assert stats["entry_agreement_rate"] == 1.0
        assert stats["exit_agreement_rate"] == 1.0
        assert stats["overall_agreement_rate"] == 1.0
        assert stats["rolling_agreement_rate"] == 1.0
        assert stats["alert_active"] is False

    def test_entry_and_exit_separate_rates(self):
        """Entry and exit rates are tracked independently."""
        tracker = _make_tracker()
        # 2 entry matches
        _record_n_entry_matches(tracker, 2)
        # 1 exit mismatch
        tracker.record_exit_comparison("ETH", "hold", "full_close", "none", "sl", _BASE_TS + 50)

        stats = tracker.get_agreement_stats()
        assert stats["entry_agreement_rate"] == 1.0
        assert stats["exit_agreement_rate"] == 0.0
        assert abs(stats["overall_agreement_rate"] - 2.0 / 3.0) < 1e-9


# ===========================================================================
# TestCheckAlert
# ===========================================================================


class TestCheckAlert:
    """Tests for ShadowDecisionTracker.check_alert()."""

    def test_no_alert_above_threshold(self):
        """No alert when agreement is above the threshold."""
        tracker = _make_tracker(alert_threshold=0.90)
        _record_n_entry_matches(tracker, 10)

        alert_active, msg, stats = tracker.check_alert()
        assert alert_active is False
        assert "OK" in msg

    def test_alert_below_threshold(self):
        """Alert fires when agreement drops below threshold."""
        tracker = _make_tracker(alert_threshold=0.95)
        _record_n_entry_matches(tracker, 9)
        _record_n_entry_mismatches(tracker, 2, start_ts=_BASE_TS + 100000)

        # 9/11 ~ 81.8 % < 95 %
        alert_active, msg, stats = tracker.check_alert()
        assert alert_active is True
        assert "ALERT" in msg

    def test_custom_threshold(self):
        """Custom threshold is respected."""
        tracker = _make_tracker(alert_threshold=0.50)
        _record_n_entry_matches(tracker, 6)
        _record_n_entry_mismatches(tracker, 4, start_ts=_BASE_TS + 100000)

        # 6/10 = 60 % >= 50 %
        alert_active, _, _ = tracker.check_alert()
        assert alert_active is False

    def test_exactly_at_threshold(self):
        """Agreement exactly at threshold should NOT trigger alert."""
        tracker = _make_tracker(window_size=100, alert_threshold=0.80)
        _record_n_entry_matches(tracker, 80)
        _record_n_entry_mismatches(tracker, 20, start_ts=_BASE_TS + 200000)

        # 80/100 = 0.80 — not below 0.80
        alert_active, _, _ = tracker.check_alert()
        assert alert_active is False

    def test_no_comparisons_no_alert(self):
        """Empty tracker returns no alert."""
        tracker = _make_tracker()
        alert_active, msg, _ = tracker.check_alert()
        assert alert_active is False
        assert "no comparisons" in msg.lower()


# ===========================================================================
# TestShadowDecisionReport
# ===========================================================================


class TestShadowDecisionReport:
    """Tests for ShadowDecisionTracker.get_report()."""

    def test_full_report_generation(self):
        """Full report contains all expected fields with correct values."""
        tracker = _make_tracker()
        _record_n_entry_matches(tracker, 5)
        tracker.record_exit_comparison("ETH", "hold", "hold", "none", "none", _BASE_TS + 50)
        _record_n_entry_mismatches(tracker, 1, start_ts=_BASE_TS + 100000)

        report = tracker.get_report()
        assert isinstance(report, ShadowDecisionReport)
        assert report.total_comparisons == 7
        assert report.entry_comparisons == 6
        assert report.exit_comparisons == 1
        assert report.generated_at_ms > 0
        assert isinstance(report.by_signal_type, dict)
        assert 0.0 <= report.overall_agreement_rate <= 1.0

    def test_recent_disagreements_limited(self):
        """Recent disagreements are capped at MAX_RECENT_DISAGREEMENTS."""
        tracker = _make_tracker()
        # Record 60 mismatches (above the 50 cap)
        _record_n_entry_mismatches(tracker, 60)

        report = tracker.get_report()
        assert len(report.recent_disagreements) <= 50
        # Each disagreement should be a ComparisonResult
        for d in report.recent_disagreements:
            assert isinstance(d, ComparisonResult)
            assert d.is_match is False

    def test_report_with_no_data(self):
        """Report on empty tracker returns zeroed counts and no alert."""
        tracker = _make_tracker()
        report = tracker.get_report()

        assert report.total_comparisons == 0
        assert report.entry_comparisons == 0
        assert report.exit_comparisons == 0
        assert report.overall_agreement_rate == 1.0
        assert report.alert_active is False
        assert report.recent_disagreements == []


# ===========================================================================
# TestLogComparisonToDb
# ===========================================================================


class TestLogComparisonToDb:
    """Tests for ShadowDecisionTracker.log_comparison_to_db()."""

    def test_comparison_logged(self, tmp_path):
        """A comparison is inserted into decision_events."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        tracker = _make_tracker()
        result = tracker.record_entry_comparison(
            "ETH", "BUY", "BUY", "high", "high", _BASE_TS,
        )
        event_id = tracker.log_comparison_to_db(result, db_path=db_path)

        assert event_id is not None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM decision_events WHERE id = ?", (event_id,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["symbol"] == "ETH"
        assert row["timestamp_ms"] == _BASE_TS

    def test_event_type_is_shadow_comparison(self, tmp_path):
        """Event type stored is 'shadow_comparison'."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        tracker = _make_tracker()
        result = tracker.record_exit_comparison(
            "BTC", "hold", "full_close", "none", "stop_loss", _BASE_TS,
        )
        event_id = tracker.log_comparison_to_db(result, db_path=db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM decision_events WHERE id = ?", (event_id,)
        ).fetchone()
        conn.close()

        assert row["event_type"] == "shadow_comparison"
        assert row["status"] == "mismatch"

    def test_context_has_both_decisions(self, tmp_path):
        """context_json contains python_decision, kernel_decision, and is_match."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        tracker = _make_tracker()
        result = tracker.record_entry_comparison(
            "SOL", "BUY", "SELL", "high", "low", _BASE_TS,
        )
        event_id = tracker.log_comparison_to_db(result, db_path=db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM decision_events WHERE id = ?", (event_id,)
        ).fetchone()
        conn.close()

        ctx = json.loads(row["context_json"])
        assert "python_decision" in ctx
        assert "kernel_decision" in ctx
        assert "is_match" in ctx
        assert ctx["is_match"] is False
        assert ctx["python_decision"] == "BUY/high"
        assert ctx["kernel_decision"] == "SELL/low"

    def test_no_db_path_no_crash(self):
        """When DB_PATH can't be resolved, returns None without crashing."""
        tracker = _make_tracker()
        result = tracker.record_entry_comparison(
            "ETH", "BUY", "BUY", "high", "high", _BASE_TS,
        )
        # db_path=None and DB_PATH import will fail in test env — should return None
        event_id = tracker.log_comparison_to_db(result, db_path=None)
        # Either None (import failure) or a string (if DB_PATH happens to exist)
        assert event_id is None or isinstance(event_id, str)


# ===========================================================================
# TestReset
# ===========================================================================


class TestReset:
    """Tests for ShadowDecisionTracker.reset()."""

    def test_reset_clears_all(self):
        """After reset, tracker behaves as if freshly constructed."""
        tracker = _make_tracker()
        _record_n_entry_matches(tracker, 5)
        _record_n_entry_mismatches(tracker, 3, start_ts=_BASE_TS + 100000)
        tracker.record_exit_comparison("ETH", "hold", "full_close", "x", "y", _BASE_TS + 200000)

        tracker.reset()

        stats = tracker.get_agreement_stats()
        assert stats["total_comparisons"] == 0
        assert stats["entry_agreement_rate"] == 1.0
        assert stats["exit_agreement_rate"] == 1.0
        assert stats["by_signal_type"] == {}

        report = tracker.get_report()
        assert report.recent_disagreements == []
