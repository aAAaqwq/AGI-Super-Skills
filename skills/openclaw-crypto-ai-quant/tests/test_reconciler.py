"""Tests for AQC-816: Exchange-kernel position reconciliation.

Covers:
- positions_match() — size tolerance and side checks
- normalize_exchange_position() — format normalization
- calculate_severity() — severity classification from discrepancies
- PositionReconciler.reconcile() — full reconciliation detection
- PositionReconciler.classify_discrepancy() — individual discrepancy classification
- PositionReconciler.build_resolution() — resolution action generation
- PositionReconciler.apply_resolution() — state mutation via resolutions
- PositionReconciler.log_discrepancies() — DB logging of discrepancies
"""

from __future__ import annotations

import json
import sqlite3

from strategy.reconciler import (
    Discrepancy,
    PositionReconciler,
    ReconciliationReport,
    calculate_severity,
    normalize_exchange_position,
    positions_match,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1


def _make_kernel_position(
    symbol: str = "ETH",
    side: str = "long",
    quantity: float = 1.0,
    avg_entry_price: float = 3000.0,
    **kwargs,
) -> dict:
    """Build a kernel Position dict matching the Rust schema."""
    pos = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "avg_entry_price": avg_entry_price,
        "opened_at_ms": kwargs.get("opened_at_ms", 1700000000000),
        "updated_at_ms": kwargs.get("opened_at_ms", 1700000000000),
        "notional_usd": abs(quantity) * avg_entry_price,
        "margin_usd": kwargs.get("margin_usd", 0.0),
    }
    return pos


def _make_exchange_position(
    side: str = "long",
    size: float = 1.0,
    entry_price: float = 3000.0,
    leverage: float = 5.0,
    unrealized_pnl: float = 0.0,
    margin_used: float = 600.0,
) -> dict:
    """Build an exchange position dict matching the normalized schema."""
    return {
        "size": size,
        "side": side,
        "entry_price": entry_price,
        "leverage": leverage,
        "unrealized_pnl": unrealized_pnl,
        "margin_used": margin_used,
    }


def _make_exchange_position_hl(
    type_: str = "LONG",
    size: float = 1.0,
    entry_price: float = 3000.0,
    leverage: float = 5.0,
    margin_used: float = 600.0,
) -> dict:
    """Build an exchange position in HyperliquidLiveExecutor.get_positions() format."""
    return {
        "type": type_,
        "size": size,
        "entry_price": entry_price,
        "leverage": leverage,
        "margin_used": margin_used,
    }


def _make_kernel_state(
    positions: dict | None = None,
    cash_usd: float = 10000.0,
) -> str:
    """Build a minimal StrategyState JSON string."""
    state = {
        "schema_version": _SCHEMA_VERSION,
        "timestamp_ms": 1700000000000,
        "step": 0,
        "cash_usd": cash_usd,
        "positions": positions or {},
        "last_entry_ms": {},
        "last_exit_ms": {},
        "last_close_info": {},
    }
    return json.dumps(state)


def _create_decision_events_table(db_path: str) -> None:
    """Create the decision_events table for testing log_discrepancies()."""
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


# ---------------------------------------------------------------------------
# TestNormalizeExchangePosition
# ---------------------------------------------------------------------------


class TestNormalizeExchangePosition:
    """Tests for normalize_exchange_position()."""

    def test_already_normalized(self):
        raw = {"side": "long", "size": 1.5, "entry_price": 3000.0}
        result = normalize_exchange_position(raw)
        assert result["side"] == "long"
        assert result["size"] == 1.5
        assert result["entry_price"] == 3000.0

    def test_hl_type_format(self):
        """HyperliquidLiveExecutor uses 'type' = 'LONG'/'SHORT'."""
        raw = {"type": "LONG", "size": 2.0, "entry_price": 95000.0, "leverage": 10.0}
        result = normalize_exchange_position(raw)
        assert result["side"] == "long"
        assert result["size"] == 2.0

    def test_hl_short_type(self):
        raw = {"type": "SHORT", "size": 0.5, "entry_price": 95000.0}
        result = normalize_exchange_position(raw)
        assert result["side"] == "short"

    def test_defaults_for_missing_fields(self):
        raw = {"side": "long", "size": 1.0}
        result = normalize_exchange_position(raw)
        assert result["entry_price"] == 0.0
        assert result["leverage"] == 1.0
        assert result["unrealized_pnl"] == 0.0
        assert result["margin_used"] == 0.0

    def test_negative_size_becomes_absolute(self):
        raw = {"side": "short", "size": -3.0, "entry_price": 50.0}
        result = normalize_exchange_position(raw)
        assert result["size"] == 3.0


# ---------------------------------------------------------------------------
# TestPositionsMatch
# ---------------------------------------------------------------------------


class TestPositionsMatch:
    """Tests for positions_match()."""

    def test_exact_match(self):
        k = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        e = _make_exchange_position("long", 1.0, 3000.0)
        assert positions_match(k, e) is True

    def test_within_tolerance(self):
        """0.5 % diff with 1 % tolerance should match."""
        k = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        e = _make_exchange_position("long", 1.005, 3000.0)
        assert positions_match(k, e) is True

    def test_at_tolerance_boundary(self):
        """Exactly at 1 % tolerance should still match."""
        k = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        e = _make_exchange_position("long", 1.01, 3000.0)
        assert positions_match(k, e) is True

    def test_over_tolerance(self):
        """2 % diff with 1 % tolerance should NOT match."""
        k = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        e = _make_exchange_position("long", 1.03, 3000.0)
        assert positions_match(k, e) is False

    def test_different_sides_never_match(self):
        k = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        e = _make_exchange_position("short", 1.0, 3000.0)
        assert positions_match(k, e) is False

    def test_zero_size_both(self):
        k = _make_kernel_position("ETH", "long", 0.0, 3000.0)
        e = _make_exchange_position("long", 0.0, 3000.0)
        assert positions_match(k, e) is True

    def test_zero_kernel_nonzero_exchange(self):
        k = _make_kernel_position("ETH", "long", 0.0, 3000.0)
        e = _make_exchange_position("long", 1.0, 3000.0)
        assert positions_match(k, e) is False

    def test_custom_tolerance(self):
        """5 % tolerance should allow larger diffs."""
        k = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        e = _make_exchange_position("long", 1.04, 3000.0)
        assert positions_match(k, e, size_tolerance_pct=0.05) is True

    def test_kernel_uses_size_field_fallback(self):
        """If kernel has 'size' instead of 'quantity', should still work."""
        k = {"side": "long", "size": 1.0}
        e = _make_exchange_position("long", 1.0, 3000.0)
        assert positions_match(k, e) is True


# ---------------------------------------------------------------------------
# TestReconcile
# ---------------------------------------------------------------------------


class TestReconcile:
    """Tests for PositionReconciler.reconcile()."""

    def test_clean_reconciliation(self):
        """All positions match — report should be clean."""
        rec = PositionReconciler()
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("long", 1.0)}
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is True
        assert report.severity == "clean"
        assert "ETH" in report.matched
        assert len(report.discrepancies) == 0

    def test_size_mismatch_detected(self):
        """Kernel and exchange differ in size beyond tolerance."""
        rec = PositionReconciler()
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("long", 1.5)}
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert len(report.discrepancies) == 1
        disc = report.discrepancies[0]
        assert disc.type == "size_mismatch"
        assert disc.symbol == "ETH"
        assert disc.kernel_size == 1.0
        assert disc.exchange_size == 1.5

    def test_missing_in_exchange_ghost(self):
        """Position in kernel but not on exchange — ghost position."""
        rec = PositionReconciler()
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {}
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert len(report.discrepancies) == 1
        disc = report.discrepancies[0]
        assert disc.type == "missing_exchange"
        assert disc.severity == "major"
        assert disc.kernel_size == 1.0
        assert disc.exchange_size == 0.0

    def test_missing_in_kernel(self):
        """Position on exchange but not in kernel — needs kernel sync."""
        rec = PositionReconciler()
        kernel = {}
        exchange = {"ETH": _make_exchange_position("long", 2.0)}
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert len(report.discrepancies) == 1
        disc = report.discrepancies[0]
        assert disc.type == "missing_kernel"
        assert disc.severity == "major"
        assert disc.exchange_size == 2.0

    def test_side_mismatch_detected(self):
        """Kernel says long, exchange says short — critical."""
        rec = PositionReconciler()
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("short", 1.0)}
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert report.severity == "critical"
        disc = report.discrepancies[0]
        assert disc.type == "side_mismatch"
        assert disc.severity == "critical"

    def test_multiple_discrepancies(self):
        """Multiple symbols with different discrepancy types."""
        rec = PositionReconciler()
        kernel = {
            "ETH": _make_kernel_position("ETH", "long", 1.0),
            "BTC": _make_kernel_position("BTC", "short", 0.5),
            "SOL": _make_kernel_position("SOL", "long", 100.0),
        }
        exchange = {
            "ETH": _make_exchange_position("long", 1.0),  # match
            "BTC": _make_exchange_position("long", 0.5),  # side mismatch
            # SOL missing on exchange — ghost
            "DOGE": _make_exchange_position("long", 10000.0),  # missing in kernel
        }
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert "ETH" in report.matched
        assert len(report.discrepancies) == 3
        types = {d.symbol: d.type for d in report.discrepancies}
        assert types["BTC"] == "side_mismatch"
        assert types["SOL"] == "missing_exchange"
        assert types["DOGE"] == "missing_kernel"

    def test_empty_kernel_positions(self):
        """No kernel positions, some exchange positions."""
        rec = PositionReconciler()
        kernel = {}
        exchange = {
            "ETH": _make_exchange_position("long", 1.0),
            "BTC": _make_exchange_position("short", 0.1),
        }
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert len(report.discrepancies) == 2
        assert all(d.type == "missing_kernel" for d in report.discrepancies)

    def test_empty_exchange_positions(self):
        """Kernel has positions, exchange has none."""
        rec = PositionReconciler()
        kernel = {
            "ETH": _make_kernel_position("ETH", "long", 1.0),
            "BTC": _make_kernel_position("BTC", "short", 0.5),
        }
        exchange = {}
        report = rec.reconcile(kernel, exchange)

        assert report.is_clean is False
        assert len(report.discrepancies) == 2
        assert all(d.type == "missing_exchange" for d in report.discrepancies)

    def test_both_empty(self):
        """No positions on either side — clean."""
        rec = PositionReconciler()
        report = rec.reconcile({}, {})
        assert report.is_clean is True
        assert report.severity == "clean"

    def test_hl_format_accepted(self):
        """Exchange positions in HyperliquidLiveExecutor format are normalized."""
        rec = PositionReconciler()
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position_hl("LONG", 1.0)}
        report = rec.reconcile(kernel, exchange)
        assert report.is_clean is True

    def test_report_has_timestamp(self):
        """Report should have a millisecond timestamp."""
        rec = PositionReconciler()
        report = rec.reconcile({}, {})
        assert report.timestamp_ms > 0


# ---------------------------------------------------------------------------
# TestClassifyDiscrepancy
# ---------------------------------------------------------------------------


class TestClassifyDiscrepancy:
    """Tests for PositionReconciler.classify_discrepancy()."""

    def test_minor_size_mismatch(self):
        """Small size difference = minor severity."""
        rec = PositionReconciler()
        k = _make_kernel_position("ETH", "long", 1.0)
        e = normalize_exchange_position(_make_exchange_position("long", 1.05))
        disc = rec.classify_discrepancy("ETH", k, e)
        assert disc.type == "size_mismatch"
        assert disc.severity == "minor"

    def test_major_size_mismatch(self):
        """Large size difference (> 10 %) = major severity."""
        rec = PositionReconciler()
        k = _make_kernel_position("ETH", "long", 1.0)
        e = normalize_exchange_position(_make_exchange_position("long", 1.5))
        disc = rec.classify_discrepancy("ETH", k, e)
        assert disc.type == "size_mismatch"
        assert disc.severity == "major"

    def test_side_mismatch_always_critical(self):
        """Side mismatch is always critical regardless of size."""
        rec = PositionReconciler()
        k = _make_kernel_position("ETH", "long", 1.0)
        e = normalize_exchange_position(_make_exchange_position("short", 1.0))
        disc = rec.classify_discrepancy("ETH", k, e)
        assert disc.type == "side_mismatch"
        assert disc.severity == "critical"

    def test_side_mismatch_with_size_diff(self):
        """Side mismatch dominates even when sizes also differ."""
        rec = PositionReconciler()
        k = _make_kernel_position("ETH", "long", 1.0)
        e = normalize_exchange_position(_make_exchange_position("short", 2.0))
        disc = rec.classify_discrepancy("ETH", k, e)
        assert disc.type == "side_mismatch"
        assert disc.severity == "critical"

    def test_details_contain_symbol(self):
        """Discrepancy details should include the symbol name."""
        rec = PositionReconciler()
        k = _make_kernel_position("SOL", "long", 100.0)
        e = normalize_exchange_position(_make_exchange_position("long", 50.0))
        disc = rec.classify_discrepancy("SOL", k, e)
        assert "SOL" in disc.details

    def test_boundary_10_pct_is_minor(self):
        """Exactly 10 % difference should be minor (not major)."""
        rec = PositionReconciler()
        k = _make_kernel_position("ETH", "long", 1.0)
        e = normalize_exchange_position(_make_exchange_position("long", 1.10))
        disc = rec.classify_discrepancy("ETH", k, e)
        # 10 % is at boundary — (1.10 - 1.0) / 1.10 = 0.0909... <= 0.10
        assert disc.type == "size_mismatch"
        assert disc.severity == "minor"


# ---------------------------------------------------------------------------
# TestBuildResolution
# ---------------------------------------------------------------------------


class TestBuildResolution:
    """Tests for PositionReconciler.build_resolution()."""

    def test_adjust_for_size_mismatch(self):
        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, "size diff"),
            ],
            is_clean=False,
            severity="minor",
            resolutions=[],
        )
        resolutions = rec.build_resolution(report)
        assert len(resolutions) == 1
        assert resolutions[0]["action"] == "adjust"
        assert resolutions[0]["symbol"] == "ETH"
        assert resolutions[0]["details"]["exchange_size"] == 1.05

    def test_add_for_missing_kernel(self):
        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("DOGE", "missing_kernel", "major", 0.0, 10000.0, "missing", exchange_side="short"),
            ],
            is_clean=False,
            severity="major",
            resolutions=[],
        )
        resolutions = rec.build_resolution(report)
        assert len(resolutions) == 1
        assert resolutions[0]["action"] == "add"
        assert resolutions[0]["symbol"] == "DOGE"
        assert resolutions[0]["details"]["exchange_size"] == 10000.0
        assert resolutions[0]["details"]["exchange_side"] == "short"

    def test_remove_for_ghost(self):
        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("SOL", "missing_exchange", "major", 100.0, 0.0, "ghost"),
            ],
            is_clean=False,
            severity="major",
            resolutions=[],
        )
        resolutions = rec.build_resolution(report)
        assert len(resolutions) == 1
        assert resolutions[0]["action"] == "remove"
        assert resolutions[0]["symbol"] == "SOL"

    def test_alert_for_side_mismatch(self):
        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "side_mismatch", "critical", 1.0, 1.0, "side diff"),
            ],
            is_clean=False,
            severity="critical",
            resolutions=[],
        )
        resolutions = rec.build_resolution(report)
        assert len(resolutions) == 1
        assert resolutions[0]["action"] == "alert"
        assert resolutions[0]["symbol"] == "ETH"

    def test_no_resolutions_for_clean_report(self):
        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=["ETH"],
            discrepancies=[],
            is_clean=True,
            severity="clean",
            resolutions=[],
        )
        resolutions = rec.build_resolution(report)
        assert len(resolutions) == 0

    def test_multiple_resolutions(self):
        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, ""),
                Discrepancy("SOL", "missing_exchange", "major", 100.0, 0.0, ""),
                Discrepancy("BTC", "side_mismatch", "critical", 0.5, 0.5, ""),
            ],
            is_clean=False,
            severity="critical",
            resolutions=[],
        )
        resolutions = rec.build_resolution(report)
        assert len(resolutions) == 3
        actions = [r["action"] for r in resolutions]
        assert "adjust" in actions
        assert "remove" in actions
        assert "alert" in actions


# ---------------------------------------------------------------------------
# TestApplyResolution
# ---------------------------------------------------------------------------


class TestApplyResolution:
    """Tests for PositionReconciler.apply_resolution()."""

    def test_adjust_size(self):
        """Adjust kernel position size to match exchange."""
        rec = PositionReconciler()
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        state_json = _make_kernel_state(positions={"ETH": kernel_pos})

        resolution = {
            "action": "adjust",
            "symbol": "ETH",
            "details": {"kernel_size": 1.0, "exchange_size": 1.5, "delta": 0.5},
        }
        result = rec.apply_resolution(state_json, resolution)
        state = json.loads(result)
        assert state["positions"]["ETH"]["quantity"] == 1.5

    def test_add_new_position(self):
        """Add a position that exists on exchange but not in kernel."""
        rec = PositionReconciler()
        state_json = _make_kernel_state(positions={})

        resolution = {
            "action": "add",
            "symbol": "DOGE",
            "details": {"exchange_size": 10000.0, "exchange_side": "long"},
        }
        result = rec.apply_resolution(state_json, resolution)
        state = json.loads(result)
        assert "DOGE" in state["positions"]
        assert state["positions"]["DOGE"]["quantity"] == 10000.0
        assert state["positions"]["DOGE"]["side"] == "long"

    def test_add_short_position(self):
        """Add a SHORT position — side must propagate from exchange, not hardcode long."""
        rec = PositionReconciler()
        state_json = _make_kernel_state(positions={})

        resolution = {
            "action": "add",
            "symbol": "ETH",
            "details": {"exchange_size": 5.0, "exchange_side": "short"},
        }
        result = rec.apply_resolution(state_json, resolution)
        state = json.loads(result)
        assert "ETH" in state["positions"]
        assert state["positions"]["ETH"]["side"] == "short"
        assert state["positions"]["ETH"]["quantity"] == 5.0

    def test_remove_ghost_position(self):
        """Remove a kernel position that no longer exists on exchange."""
        rec = PositionReconciler()
        kernel_pos = _make_kernel_position("SOL", "long", 100.0, 150.0)
        state_json = _make_kernel_state(positions={"SOL": kernel_pos})

        resolution = {
            "action": "remove",
            "symbol": "SOL",
            "details": {"kernel_size": 100.0},
        }
        result = rec.apply_resolution(state_json, resolution)
        state = json.loads(result)
        assert "SOL" not in state["positions"]

    def test_alert_leaves_state_unchanged(self):
        """Alert resolution does not modify state."""
        rec = PositionReconciler()
        kernel_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        state_json = _make_kernel_state(positions={"ETH": kernel_pos})

        resolution = {
            "action": "alert",
            "symbol": "ETH",
            "details": {"reason": "Side mismatch requires manual intervention"},
        }
        result = rec.apply_resolution(state_json, resolution)
        # Alert should return the exact same state
        assert json.loads(result) == json.loads(state_json)

    def test_multiple_resolutions_applied(self):
        """Apply multiple resolutions sequentially."""
        rec = PositionReconciler()
        eth_pos = _make_kernel_position("ETH", "long", 1.0, 3000.0)
        sol_pos = _make_kernel_position("SOL", "long", 100.0, 150.0)
        state_json = _make_kernel_state(positions={"ETH": eth_pos, "SOL": sol_pos})

        # Adjust ETH, remove SOL, add DOGE
        resolutions = [
            {"action": "adjust", "symbol": "ETH", "details": {"exchange_size": 2.0}},
            {"action": "remove", "symbol": "SOL", "details": {"kernel_size": 100.0}},
            {"action": "add", "symbol": "DOGE", "details": {"exchange_size": 5000.0}},
        ]
        for r in resolutions:
            state_json = rec.apply_resolution(state_json, r)

        state = json.loads(state_json)
        assert state["positions"]["ETH"]["quantity"] == 2.0
        assert "SOL" not in state["positions"]
        assert "DOGE" in state["positions"]
        assert state["positions"]["DOGE"]["quantity"] == 5000.0

    def test_adjust_missing_position_logs_warning(self):
        """Adjusting a symbol not in kernel state should not crash."""
        rec = PositionReconciler()
        state_json = _make_kernel_state(positions={})
        resolution = {
            "action": "adjust",
            "symbol": "XYZ",
            "details": {"exchange_size": 1.0},
        }
        # Should not raise
        result = rec.apply_resolution(state_json, resolution)
        state = json.loads(result)
        assert "XYZ" not in state["positions"]

    def test_invalid_json_returns_original(self):
        """If state_json is invalid, return it unchanged."""
        rec = PositionReconciler()
        bad_json = "not valid json"
        resolution = {"action": "adjust", "symbol": "ETH", "details": {}}
        result = rec.apply_resolution(bad_json, resolution)
        assert result == bad_json


# ---------------------------------------------------------------------------
# TestLogDiscrepancies
# ---------------------------------------------------------------------------


class TestLogDiscrepancies:
    """Tests for PositionReconciler.log_discrepancies()."""

    def test_discrepancies_logged_to_db(self, tmp_path):
        """Discrepancies should be inserted into decision_events table."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, "size diff"),
                Discrepancy("SOL", "missing_exchange", "major", 100.0, 0.0, "ghost"),
            ],
            is_clean=False,
            severity="major",
            resolutions=[],
        )

        event_ids = rec.log_discrepancies(report, db_path=db_path)
        assert len(event_ids) == 2

        # Verify rows in DB
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM decision_events").fetchall()
        conn.close()
        assert len(rows) == 2

    def test_clean_report_logs_nothing(self, tmp_path):
        """A clean report should not create any DB entries."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=["ETH"],
            discrepancies=[],
            is_clean=True,
            severity="clean",
            resolutions=[],
        )

        event_ids = rec.log_discrepancies(report, db_path=db_path)
        assert len(event_ids) == 0

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM decision_events").fetchall()
        conn.close()
        assert len(rows) == 0

    def test_event_type_is_reconciliation(self, tmp_path):
        """Logged events should have event_type='reconciliation'."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, "diff"),
            ],
            is_clean=False,
            severity="minor",
            resolutions=[],
        )
        rec.log_discrepancies(report, db_path=db_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT event_type, triggered_by FROM decision_events").fetchone()
        conn.close()
        assert row[0] == "reconciliation"
        assert row[1] == "heartbeat"

    def test_context_json_contains_severity(self, tmp_path):
        """Context JSON should contain the discrepancy severity and type."""
        db_path = str(tmp_path / "test.db")
        _create_decision_events_table(db_path)

        rec = PositionReconciler()
        report = ReconciliationReport(
            timestamp_ms=1700000000000,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "major", 1.0, 2.0, "big diff"),
            ],
            is_clean=False,
            severity="major",
            resolutions=[],
        )
        rec.log_discrepancies(report, db_path=db_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT context_json FROM decision_events").fetchone()
        conn.close()
        ctx = json.loads(row[0])
        assert ctx["severity"] == "major"
        assert ctx["type"] == "size_mismatch"
        assert ctx["kernel_size"] == 1.0
        assert ctx["exchange_size"] == 2.0


# ---------------------------------------------------------------------------
# TestCalculateSeverity
# ---------------------------------------------------------------------------


class TestCalculateSeverity:
    """Tests for calculate_severity()."""

    def test_clean_no_discrepancies(self):
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[],
            is_clean=True,
            severity="clean",
            resolutions=[],
        )
        assert calculate_severity(report) == "clean"

    def test_minor_small_size_mismatch(self):
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, ""),
            ],
            is_clean=False,
            severity="",
            resolutions=[],
        )
        assert calculate_severity(report) == "minor"

    def test_major_large_mismatch(self):
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "major", 1.0, 2.0, ""),
            ],
            is_clean=False,
            severity="",
            resolutions=[],
        )
        assert calculate_severity(report) == "major"

    def test_major_ghost_position(self):
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "missing_exchange", "major", 1.0, 0.0, "ghost"),
            ],
            is_clean=False,
            severity="",
            resolutions=[],
        )
        assert calculate_severity(report) == "major"

    def test_critical_side_mismatch(self):
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "side_mismatch", "critical", 1.0, 1.0, ""),
            ],
            is_clean=False,
            severity="",
            resolutions=[],
        )
        assert calculate_severity(report) == "critical"

    def test_critical_dominates_mixed(self):
        """Critical severity should dominate even when minor/major also present."""
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, ""),
                Discrepancy("SOL", "missing_exchange", "major", 100.0, 0.0, ""),
                Discrepancy("BTC", "side_mismatch", "critical", 0.5, 0.5, ""),
            ],
            is_clean=False,
            severity="",
            resolutions=[],
        )
        assert calculate_severity(report) == "critical"

    def test_major_dominates_minor(self):
        """Major should dominate when mixed with minor."""
        report = ReconciliationReport(
            timestamp_ms=0,
            matched=[],
            discrepancies=[
                Discrepancy("ETH", "size_mismatch", "minor", 1.0, 1.05, ""),
                Discrepancy("SOL", "missing_exchange", "major", 100.0, 0.0, ""),
            ],
            is_clean=False,
            severity="",
            resolutions=[],
        )
        assert calculate_severity(report) == "major"


# ---------------------------------------------------------------------------
# TestKillSwitchOnCritical (H12)
# ---------------------------------------------------------------------------


class TestKillSwitchOnCritical:
    """H12: Critical reconciliation mismatch should trigger the kill-switch."""

    def test_critical_mismatch_triggers_kill_switch(self):
        """Side mismatch (critical) should call risk_manager.kill()."""

        class FakeRiskManager:
            def __init__(self):
                self.kill_calls: list[dict] = []

            def kill(self, *, mode: str, reason: str) -> None:
                self.kill_calls.append({"mode": mode, "reason": reason})

        risk = FakeRiskManager()
        rec = PositionReconciler(risk_manager=risk)
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("short", 1.0)}

        report = rec.reconcile(kernel, exchange)

        assert report.severity == "critical"
        assert len(risk.kill_calls) == 1
        assert risk.kill_calls[0]["mode"] == "close_only"
        assert "reconciliation_critical" in risk.kill_calls[0]["reason"]

    def test_non_critical_does_not_trigger_kill_switch(self):
        """Minor/major mismatches should NOT trigger the kill-switch."""

        class FakeRiskManager:
            def __init__(self):
                self.kill_calls: list[dict] = []

            def kill(self, *, mode: str, reason: str) -> None:
                self.kill_calls.append({"mode": mode, "reason": reason})

        risk = FakeRiskManager()
        rec = PositionReconciler(risk_manager=risk)
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("long", 1.5)}  # size mismatch, major

        report = rec.reconcile(kernel, exchange)

        assert report.severity in ("minor", "major")
        assert len(risk.kill_calls) == 0

    def test_no_risk_manager_still_works(self):
        """Without risk_manager, critical mismatch logs but does not crash."""
        rec = PositionReconciler()  # no risk_manager
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("short", 1.0)}

        report = rec.reconcile(kernel, exchange)

        assert report.severity == "critical"

    def test_risk_manager_exception_does_not_crash(self):
        """If risk_manager.kill() raises, reconciler should not crash."""

        class BrokenRiskManager:
            def kill(self, *, mode: str, reason: str) -> None:
                raise RuntimeError("kill failed")

        risk = BrokenRiskManager()
        rec = PositionReconciler(risk_manager=risk)
        kernel = {"ETH": _make_kernel_position("ETH", "long", 1.0)}
        exchange = {"ETH": _make_exchange_position("short", 1.0)}

        # Should not raise
        report = rec.reconcile(kernel, exchange)
        assert report.severity == "critical"
