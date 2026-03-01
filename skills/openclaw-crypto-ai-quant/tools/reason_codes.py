#!/usr/bin/env python3
"""Canonical reason-code classifier shared by replay audit tooling.

This module mirrors the canonical reason mapping used by the Rust backtester
(`bt-core/src/reason_codes.rs`) so that live/paper/backtester audit reports
use one stable, machine-readable reason vocabulary.
"""

from __future__ import annotations


def classify_reason_code(action_code: str, reason: str) -> str:
    """Classify an `(action_code, reason)` pair into a canonical reason code."""
    action = str(action_code or "").strip().upper()
    reason_text = str(reason or "")

    if action == "FUNDING":
        return "funding_payment"
    if action.startswith("OPEN_"):
        if "sub-bar" in reason_text:
            return "entry_signal_sub_bar"
        return "entry_signal"
    if action.startswith("ADD_"):
        return "entry_pyramid"
    if action.startswith("CLOSE_") or action.startswith("REDUCE_"):
        if "Stop Loss" in reason_text:
            return "exit_stop_loss"
        if "Trailing Stop" in reason_text:
            return "exit_trailing_stop"
        if "Take Profit" in reason_text:
            return "exit_take_profit"
        if "Signal Flip" in reason_text:
            return "exit_signal_flip"
        if "Funding" in reason_text:
            return "exit_funding"
        if "Force Close" in reason_text:
            return "exit_force_close"
        if "End of Backtest" in reason_text:
            return "exit_end_of_backtest"
        return "exit_filter"
    return "unknown"
