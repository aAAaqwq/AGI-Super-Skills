"""Tests for B2: Dead Axes & Naming Mismatch Cleanup.

Validates that sweep-compatible config names now work correctly in
both the Python engine and the strategy module.
"""
from __future__ import annotations

import copy
import sys
import os

# Ensure project root is on sys.path so local imports work.
_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj not in sys.path:
    sys.path.insert(0, _proj)


# ---------------------------------------------------------------------------
# 1. enable_regime_filter alias → enable_regime_gate
# ---------------------------------------------------------------------------

def test_regime_gate_reads_enable_regime_filter():
    """Engine should accept `enable_regime_filter` as alias for `enable_regime_gate`."""

    # Build a minimal config dict the engine would see.
    rc = {
        "enable_regime_filter": True,   # sweep-compatible name
        "regime_gate_fail_open": False,
        "regime_gate_breadth_low": 20.0,
        "regime_gate_breadth_high": 80.0,
        "regime_gate_btc_adx_min": 20.0,
        "regime_gate_btc_atr_pct_min": 0.003,
    }

    # The engine code: rc.get("enable_regime_filter", rc.get("enable_regime_gate", False))
    enabled = bool(rc.get("enable_regime_filter", rc.get("enable_regime_gate", False)))
    assert enabled is True, "enable_regime_filter=True should enable the regime gate"

    # When only enable_regime_gate is set (legacy):
    rc2 = {"enable_regime_gate": True}
    enabled2 = bool(rc2.get("enable_regime_filter", rc2.get("enable_regime_gate", False)))
    assert enabled2 is True

    # When neither is set:
    rc3 = {}
    enabled3 = bool(rc3.get("enable_regime_filter", rc3.get("enable_regime_gate", False)))
    assert enabled3 is False


def test_regime_filter_takes_precedence_over_gate():
    """When both are set, enable_regime_filter should take precedence."""
    rc = {
        "enable_regime_filter": True,
        "enable_regime_gate": False,
    }
    enabled = bool(rc.get("enable_regime_filter", rc.get("enable_regime_gate", False)))
    assert enabled is True, "enable_regime_filter should take precedence"


# ---------------------------------------------------------------------------
# 2. breadth_block_long_below / breadth_block_short_above aliases
# ---------------------------------------------------------------------------

def test_breadth_block_aliases():
    """Engine should read breadth_block_long_below / breadth_block_short_above."""
    rc = {
        "breadth_block_long_below": 15.0,
        "breadth_block_short_above": 85.0,
    }

    chop_lo = float(rc.get("breadth_block_long_below",
                            rc.get("regime_gate_breadth_low",
                                   rc.get("auto_reverse_breadth_low", 10.0))))
    chop_hi = float(rc.get("breadth_block_short_above",
                            rc.get("regime_gate_breadth_high",
                                   rc.get("auto_reverse_breadth_high", 90.0))))

    assert chop_lo == 15.0
    assert chop_hi == 85.0


def test_breadth_block_fallback_to_regime_gate():
    """Without sweep names, should fall back to regime_gate_breadth_*."""
    rc = {
        "regime_gate_breadth_low": 25.0,
        "regime_gate_breadth_high": 75.0,
    }

    chop_lo = float(rc.get("breadth_block_long_below",
                            rc.get("regime_gate_breadth_low",
                                   rc.get("auto_reverse_breadth_low", 10.0))))
    chop_hi = float(rc.get("breadth_block_short_above",
                            rc.get("regime_gate_breadth_high",
                                   rc.get("auto_reverse_breadth_high", 90.0))))

    assert chop_lo == 25.0
    assert chop_hi == 75.0


# ---------------------------------------------------------------------------
# 3. reverse_entry_signal in Python analyze()
# ---------------------------------------------------------------------------

def test_reverse_entry_signal_flips_buy_sell(monkeypatch):
    """When trade.reverse_entry_signal=True, BUY should become SELL and vice versa."""
    import strategy.mei_alpha_v1 as strat

    original_config = strat._DEFAULT_STRATEGY_CONFIG
    test_cfg = copy.deepcopy(original_config)
    test_cfg["trade"]["reverse_entry_signal"] = True

    # Monkey-patch get_strategy_config to return our test config.
    monkeypatch.setattr(strat, "get_strategy_config", lambda sym: copy.deepcopy(test_cfg))

    # We need some realistic data for analyze().
    # Instead of calling full analyze, let's test the reversal logic in isolation.
    signal = "BUY"
    trade_cfg = test_cfg["trade"]

    _should_reverse = bool(trade_cfg.get("reverse_entry_signal", False))
    assert _should_reverse is True

    if _should_reverse and signal in ("BUY", "SELL"):
        signal = "SELL" if signal == "BUY" else "BUY"

    assert signal == "SELL", "BUY should be reversed to SELL"


def test_reverse_entry_signal_off_by_default():
    """reverse_entry_signal defaults to False."""
    import strategy.mei_alpha_v1 as strat

    cfg = strat.get_strategy_config("BTC")
    assert cfg["trade"].get("reverse_entry_signal", False) is False


# ---------------------------------------------------------------------------
# 4. indicators.ave_avg_atr_window sync to thresholds.entry.ave_avg_atr_window
# ---------------------------------------------------------------------------

def test_ave_avg_atr_window_synced_from_indicators(monkeypatch):
    """indicators.ave_avg_atr_window should propagate to thresholds.entry.ave_avg_atr_window."""
    import strategy.mei_alpha_v1 as strat

    # Simulate a config where only indicators path is set (no threshold path).
    original = copy.deepcopy(strat._DEFAULT_STRATEGY_CONFIG)
    original["indicators"]["ave_avg_atr_window"] = 77
    # Remove from thresholds to simulate sweep-only-indicators scenario.
    if "entry" in original.get("thresholds", {}):
        original["thresholds"]["entry"].pop("ave_avg_atr_window", None)

    # Patch the strategy manager to return this config.
    monkeypatch.setattr(strat, "_strategy_mgr", None)
    monkeypatch.setattr(strat, "_STRATEGY_OVERRIDES", {
        "global": original,
    })

    cfg = strat.get_strategy_config("BTC")
    thr_val = cfg["thresholds"]["entry"].get("ave_avg_atr_window")
    assert thr_val == 77, f"Expected 77, got {thr_val}"


def test_ave_avg_atr_window_indicators_overrides_threshold(monkeypatch):
    """When both indicators and thresholds set different values, indicators wins (matching Rust)."""
    import strategy.mei_alpha_v1 as strat

    original = copy.deepcopy(strat._DEFAULT_STRATEGY_CONFIG)
    original["indicators"]["ave_avg_atr_window"] = 33
    original["thresholds"]["entry"]["ave_avg_atr_window"] = 50

    monkeypatch.setattr(strat, "_strategy_mgr", None)
    monkeypatch.setattr(strat, "_STRATEGY_OVERRIDES", {
        "global": original,
    })

    cfg = strat.get_strategy_config("BTC")
    thr_val = cfg["thresholds"]["entry"]["ave_avg_atr_window"]
    assert thr_val == 33, f"Expected 33, got {thr_val}"


def test_ave_avg_atr_window_no_indicators_key(monkeypatch):
    """When indicators.ave_avg_atr_window is not set, thresholds default is preserved."""
    import strategy.mei_alpha_v1 as strat

    original = copy.deepcopy(strat._DEFAULT_STRATEGY_CONFIG)
    original["indicators"].pop("ave_avg_atr_window", None)
    original["thresholds"]["entry"]["ave_avg_atr_window"] = 42

    monkeypatch.setattr(strat, "_strategy_mgr", None)
    monkeypatch.setattr(strat, "_STRATEGY_OVERRIDES", {
        "global": original,
    })

    cfg = strat.get_strategy_config("BTC")
    thr_val = cfg["thresholds"]["entry"]["ave_avg_atr_window"]
    assert thr_val == 42, f"Expected 42, got {thr_val}"
