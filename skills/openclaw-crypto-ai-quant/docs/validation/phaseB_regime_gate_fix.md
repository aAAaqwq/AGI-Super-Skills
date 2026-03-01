# Phase B — Regime Gate Enforcement Fix (B1 — CRITICAL)

**Date:** 2026-02-14  
**Severity:** CRITICAL  
**Status:** ✅ FIXED & TESTED

## Bug Description

`_regime_gate_on` was computed and logged by `_update_regime_gate()` in
`engine/core.py` but **never actually enforced**. No code checked the flag
before executing OPEN or ADD orders, meaning the regime gate was purely
cosmetic — entries proceeded in chop/low-volatility regimes that the gate was
designed to block.

## Root Cause

The `_update_regime_gate()` method (lines 1201-1367) correctly computes
`_regime_gate_on` based on market breadth, BTC ADX, and BTC ATR%, and logs
state transitions. However, the Phase 2 decision execution loop in
`run_forever()` never consulted this flag before dispatching OPEN/ADD trades.

## Fix Applied

### 1. Regime gate enforcement (`engine/core.py`)

Added a gate check in the Phase 2 decision execution loop, immediately before
any OPEN/ADD-specific logic (price fetching, staleness checks, etc.):

```python
# ── Regime gate enforcement (B1 fix) ──
if act in {"OPEN", "ADD"} and not self._regime_gate_on:
    logger.info(
        f"🚫 regime gate blocked {act} for {sym_u} "
        f"reason={self._regime_gate_reason}"
    )
    continue
```

Key properties:
- **Only blocks entries** (OPEN, ADD). Exits (CLOSE, REDUCE) are unaffected.
- **Respects `enable_regime_gate` config**: when disabled, `_update_regime_gate`
  sets `_regime_gate_on = True`, so the check is a no-op.
- **Respects `regime_gate_fail_open` config**: when True and data is missing,
  `_update_regime_gate` sets `_regime_gate_on = True`, allowing entries.
- **Logs every blocked entry** with the blocking reason for audit trail.

### 2. Logger scoping fix (`engine/core.py`)

Removed a redundant local `import logging; logger = ...` inside an `except`
block in `run_forever()` that shadowed the module-level `logger`, causing
`UnboundLocalError` when subsequent code referenced `logger` outside the
except clause. This was a pre-existing bug exposed during testing.

## Tests Added

**File:** `tests/test_regime_gate_enforcement.py` (6 tests)

| Test | What it verifies |
|------|-----------------|
| `test_gate_on_entries_allowed` | OPEN executes when `_regime_gate_on = True` |
| `test_gate_off_blocks_open_and_add` | OPEN and ADD are blocked when gate is OFF |
| `test_gate_off_exits_still_work` | CLOSE and REDUCE execute even when gate is OFF |
| `test_gate_disabled_entries_allowed` | Gate disabled (`enable_regime_gate=False`) → entries allowed |
| `test_fail_open_allows_entries_when_data_missing` | `regime_gate_fail_open=True` + missing data → gate ON |
| `test_fail_open_false_blocks_entries_when_data_missing` | `fail_open=False` + missing data → gate OFF → entries blocked |

## Test Results

```
210 passed, 5 skipped in 4.19s
```

All pre-existing tests continue to pass. The 5 skips are expected (missing
optional dependencies: `jsonschema`, `bt_runtime`).

## Files Changed

| File | Change |
|------|--------|
| `engine/core.py` | +9 lines: regime gate enforcement check in Phase 2 loop |
| `engine/core.py` | −2 lines: removed redundant local logger import |
| `tests/test_regime_gate_enforcement.py` | +230 lines: new test file (6 tests) |
| `docs/validation/phaseB_regime_gate_fix.md` | This document |
