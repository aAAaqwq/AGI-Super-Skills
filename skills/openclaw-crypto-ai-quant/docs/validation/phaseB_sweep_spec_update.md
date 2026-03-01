# Phase B3 — Sweep Spec Axis Update

**Date:** 2026-02-14  
**Task:** B3-sweep-spec-update  
**Status:** ✅ Complete

---

## Changes Made

### 1. Removed duplicate `indicators.ave_avg_atr_window`

- **File:** `backtester/sweeps/full_144v.yaml`
- **Reason:** Duplicates `thresholds.entry.ave_avg_atr_window`. The Rust config layer aliases them (writes to both), so sweeping both creates a redundant 3× multiplier in the cartesian product where the last-writer-wins and the other axis is wasted compute.
- **Confirmed by:** Workers 1 and 3 (Phase B analysis).
- **Kept:** `thresholds.entry.ave_avg_atr_window` (6 values: 30–80).

### 2. Added `trade.tp_partial_atr_mult`

- **File:** `backtester/sweeps/full_144v.yaml`
- **Values:** `[0.0, 1.0, 2.0, 3.0, 4.0]` (5 values)
- **Reason:** Fully implemented in Rust (`sweep.rs` match arm present) and Python. Materially impacts trade behavior by controlling the ATR-based trigger distance for partial take-profit. YAML default was `1.0`, Rust default `0.0` — the discrepancy alone justifies sweep coverage.
- **Confirmed by:** Worker 5 (Phase B analysis).

### 3. Header documentation for intentional exclusions

Added to `full_144v.yaml` header comment:

| Excluded Key | Reason |
|---|---|
| `trade.use_bbo_for_fills` | Engine-only — requires live orderbook (BBO data) |
| `market_regime.regime_gate_enabled` | Engine-only — requires live breadth data |
| `market_regime.regime_gate_bear_min` | Engine-only — requires live breadth data |
| `market_regime.regime_gate_bear_max` | Engine-only — requires live breadth data |
| `market_regime.regime_gate_bull_min` | Engine-only — requires live breadth data |
| `market_regime.regime_gate_bull_max` | Engine-only — requires live breadth data |
| `market_regime.regime_gate_neutral_min` | Engine-only — requires live breadth data |
| `market_regime.regime_gate_neutral_max` | Engine-only — requires live breadth data |

### 4. 17-phase manifest updated

- **Phase affected:** `p12_144v`
  - Removed `indicators.ave_avg_atr_window` (was 3-value)
  - Added `trade.tp_partial_atr_mult` (5-value)
  - Old combo: 4,374 → New combo: 7,290 (+2,916)
- **Manifest totals:** `achieved_combo` / `total_combo` updated from 100,602 → 103,518
- No other phases were affected.

---

## Net Effect

| Metric | Before | After |
|---|---|---|
| Total axes | 142 | 142 |
| Cartesian product impact | +0 axes net | −1 redundant 3× + new 5-value axis |
| 17-phase total combos | 100,602 | 103,518 |

---

## Dry Validation Results

### YAML ↔ Rust sweep.rs coverage

```
YAML axis count:         142  ✅
YAML paths missing from Rust:  0  ✅
Rust paths not in YAML:        2  (both intentionally excluded)
  - indicators.ave_avg_atr_window   → removed (alias of thresholds.entry.ave_avg_atr_window)
  - trade.use_bbo_for_fills         → excluded (engine-only)
```

### YAML ↔ 17-phase coverage

```
Total phase axes:    142  ✅
Unique phase axes:   142  ✅ (no duplicates)
YAML axes missing from phases:  0  ✅
Phase axes not in main YAML:    0  ✅
```

All 142 axes in `full_144v.yaml` are present exactly once across the 17 phase files, and every axis has a corresponding Rust `sweep.rs` match arm.

---

## Files Modified

1. `backtester/sweeps/full_144v.yaml` — header docs, −1 axis, +1 axis
2. `backtester/sweeps/full_144v_17phase/p12_144v.yaml` — swapped axes
3. `backtester/sweeps/full_144v_17phase/manifest.yaml` — updated p12 paths + combo totals
