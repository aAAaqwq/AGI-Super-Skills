#!/usr/bin/env python3
"""Validate config parity between Python defaults, YAML, and Rust defaults.

Checks that strategy_overrides.yaml is fully explicit and that Python
_DEFAULT_STRATEGY_CONFIG matches Rust backtester defaults for all keys.
"""

import sys
import yaml
from pathlib import Path

# Add project root so we can import strategy.mei_alpha_v1
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_DIR))

from strategy.mei_alpha_v1 import _DEFAULT_STRATEGY_CONFIG  # noqa: E402

# --- Rust defaults (from bt-core/src/config.rs) ---
RUST_DEFAULTS = {
    "trade": {
        "allocation_pct": 0.03,
        "sl_atr_mult": 2.0,
        "tp_atr_mult": 4.0,
        "leverage": 3.0,
        "max_open_positions": 20,
        "max_total_margin_pct": 0.60,
        "min_notional_usd": 10.0,
        "min_atr_pct": 0.003,
        "bump_to_min_notional": False,
        "leverage_low": 1.0,
        "leverage_medium": 3.0,
        "leverage_high": 5.0,
        "use_bbo_for_fills": True,
        "slippage_bps": 10.0,
        "enable_dynamic_sizing": True,
        "confidence_mult_high": 1.0,
        "confidence_mult_medium": 0.7,
        "confidence_mult_low": 0.5,
        "adx_sizing_min_mult": 0.6,
        "adx_sizing_full_adx": 40.0,
        "vol_baseline_pct": 0.01,
        "vol_scalar_min": 0.5,
        "vol_scalar_max": 1.0,
        "enable_pyramiding": True,
        "max_adds_per_symbol": 2,
        "add_fraction_of_base_margin": 0.5,
        "add_cooldown_minutes": 60,
        "add_min_profit_atr": 0.5,
        "add_min_confidence": "medium",
        "enable_partial_tp": True,
        "tp_partial_pct": 0.5,
        "tp_partial_min_notional_usd": 10.0,
        "trailing_start_atr": 1.0,
        "trailing_distance_atr": 0.8,
        "trailing_start_atr_low_conf": 0.0,
        "trailing_distance_atr_low_conf": 0.0,
        "enable_vol_buffered_trailing": True,
        "reentry_cooldown_minutes": 60,
        "reentry_cooldown_min_mins": 45,
        "reentry_cooldown_max_mins": 180,
        "enable_reef_filter": True,
        "reef_long_rsi_block_gt": 70.0,
        "reef_short_rsi_block_lt": 30.0,
        "reef_adx_threshold": 45.0,
        "reef_long_rsi_extreme_gt": 75.0,
        "reef_short_rsi_extreme_lt": 25.0,
        "tsme_min_profit_atr": 1.0,
        "tsme_require_adx_slope_negative": True,
        "enable_ssf_filter": True,
        "enable_breakeven_stop": True,
        "breakeven_start_atr": 0.7,
        "breakeven_buffer_atr": 0.05,
        "enable_rsi_overextension_exit": True,
        "rsi_exit_profit_atr_switch": 1.5,
        "rsi_exit_ub_lo_profit": 80.0,
        "rsi_exit_ub_hi_profit": 70.0,
        "rsi_exit_lb_lo_profit": 20.0,
        "rsi_exit_lb_hi_profit": 30.0,
        "rsi_exit_ub_lo_profit_low_conf": 0.0,
        "rsi_exit_ub_hi_profit_low_conf": 0.0,
        "rsi_exit_lb_lo_profit_low_conf": 0.0,
        "rsi_exit_lb_hi_profit_low_conf": 0.0,
        "smart_exit_adx_exhaustion_lt": 18.0,
        "smart_exit_adx_exhaustion_lt_low_conf": 0.0,
        "reverse_entry_signal": False,
        "entry_min_confidence": "high",
        "block_exits_on_extreme_dev": False,
        "glitch_price_dev_pct": 0.40,
        "glitch_atr_mult": 12.0,
        "entry_cooldown_s": 20,
        "exit_cooldown_s": 15,
        "max_entry_orders_per_loop": 6,
    },
    "indicators": {
        "adx_window": 14,
        "ema_fast_window": 20,
        "ema_slow_window": 50,
        "bb_window": 20,
        "ema_macro_window": 200,
        "atr_window": 14,
        "rsi_window": 14,
        "bb_width_avg_window": 30,
        "vol_sma_window": 20,
        "vol_trend_window": 5,
        "stoch_rsi_window": 14,
        "stoch_rsi_smooth1": 3,
        "stoch_rsi_smooth2": 3,
    },
    "filters": {
        "enable_extension_filter": True,
        "enable_ranging_filter": True,
        "enable_anomaly_filter": True,
        "require_btc_alignment": True,
        "require_volume_confirmation": False,
        "require_macro_alignment": False,
        "require_adx_rising": True,
        "adx_rising_saturation": 40.0,
        "vol_confirm_include_prev": True,
        "use_stoch_rsi_filter": True,
    },
    "thresholds": {
        "entry": {
            "min_adx": 22.0,
            "max_dist_ema_fast": 0.04,
            "btc_adx_override": 40.0,
            "high_conf_volume_mult": 2.5,
            "ave_enabled": True,
            "ave_atr_ratio_gt": 1.5,
            "ave_adx_mult": 1.25,
            "ave_avg_atr_window": 50,
            "macd_hist_entry_mode": "accel",
            "enable_pullback_entries": False,
            "pullback_confidence": "low",
            "pullback_min_adx": 22.0,
            "pullback_rsi_long_min": 50.0,
            "pullback_rsi_short_max": 50.0,
            "pullback_require_macd_sign": True,
            "enable_slow_drift_entries": False,
            "slow_drift_slope_window": 20,
            "slow_drift_min_slope_pct": 0.0006,
            "slow_drift_min_adx": 10.0,
            "slow_drift_rsi_long_min": 50.0,
            "slow_drift_rsi_short_max": 50.0,
            "slow_drift_require_macd_sign": True,
        },
        "ranging": {
            "min_signals": 2,
            "adx_below": 21.0,
            "bb_width_ratio_below": 0.8,
            "rsi_low": 47.0,
            "rsi_high": 53.0,
        },
        "anomaly": {
            "price_change_pct_gt": 0.10,
            "ema_fast_dev_pct_gt": 0.50,
        },
        "tp_and_momentum": {
            "adx_strong_gt": 40.0,
            "adx_weak_lt": 30.0,
            "tp_mult_strong": 7.0,
            "tp_mult_weak": 3.0,
            "rsi_long_strong": 52.0,
            "rsi_long_weak": 56.0,
            "rsi_short_strong": 48.0,
            "rsi_short_weak": 44.0,
        },
        "stoch_rsi": {
            "block_long_if_k_gt": 0.85,
            "block_short_if_k_lt": 0.15,
        },
    },
    "market_regime": {
        "enable_regime_filter": False,
        "enable_auto_reverse": False,
        "breadth_block_short_above": 90.0,
        "breadth_block_long_below": 10.0,
        "auto_reverse_breadth_low": 10.0,
        "auto_reverse_breadth_high": 90.0,
    },
}


def flatten(d, prefix=""):
    """Flatten nested dict into dot-separated keys."""
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        else:
            items[key] = v
    return items


def load_yaml_global(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("global", {})


def main():
    yaml_path = _PROJECT_DIR / "config" / "strategy_overrides.yaml"
    yaml_global = load_yaml_global(yaml_path)

    py_flat = flatten(_DEFAULT_STRATEGY_CONFIG)
    rust_flat = flatten(RUST_DEFAULTS)
    yaml_flat = flatten(yaml_global)

    # Skip Python-only / engine-only keys
    skip_prefixes = ("watchlist_exclude", "engine.")

    all_keys = sorted(set(py_flat) | set(rust_flat) | set(yaml_flat))

    mismatches = []
    missing_yaml = []
    ok = 0

    print(f"{'Key':<50} {'Python':>12} {'Rust':>12} {'YAML':>12} {'Status':>10}")
    print("=" * 100)

    for key in all_keys:
        if any(key.startswith(p) for p in skip_prefixes):
            continue

        py_val = py_flat.get(key)
        rust_val = rust_flat.get(key)
        yaml_val = yaml_flat.get(key)

        # Normalise for comparison
        def norm(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return float(v)
            return v

        status = "OK"
        if yaml_val is None:
            status = "YAML_MISS"
            missing_yaml.append(key)
        elif py_val is not None and rust_val is not None:
            if norm(py_val) != norm(rust_val):
                status = "PY!=RUST"
                mismatches.append((key, py_val, rust_val))
        elif py_val is None and rust_val is not None:
            status = "PY_MISS"
        elif py_val is not None and rust_val is None:
            status = "RUST_MISS"

        if status == "OK":
            ok += 1

        py_str = str(py_val) if py_val is not None else "-"
        rust_str = str(rust_val) if rust_val is not None else "-"
        yaml_str = str(yaml_val) if yaml_val is not None else "-"

        if status != "OK":
            print(f"{key:<50} {py_str:>12} {rust_str:>12} {yaml_str:>12} {status:>10}")

    print("\n--- Summary ---")
    print(f"  Total keys:    {len(all_keys)}")
    print(f"  OK:            {ok}")
    print(f"  PY!=RUST:      {len(mismatches)} (defaults differ — YAML overrides both)")
    print(f"  YAML missing:  {len(missing_yaml)}")

    if mismatches:
        print("\n--- Python vs Rust default mismatches (not a problem if YAML is explicit) ---")
        for key, py_val, rust_val in mismatches:
            print(f"  {key}: Python={py_val}, Rust={rust_val}")

    if missing_yaml:
        print("\n--- Keys missing from YAML (relying on code defaults) ---")
        for key in missing_yaml:
            print(f"  {key}")

    # Exit code: 0 if no YAML missing, 1 otherwise
    return 1 if missing_yaml else 0


if __name__ == "__main__":
    sys.exit(main())
