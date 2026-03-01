# Phase C — Paper Daemon Promoted Config Integration

**Date:** 2026-02-14  
**Task:** C1-daemon-integration  
**Status:** ✅ Complete

## Summary

Integrated promoted config loading from factory runs into the paper trading daemon.
Paper daemons can now automatically pick up factory-optimised strategy parameters
by setting `AI_QUANT_PROMOTED_ROLE`.

## What Was Built

### New Module: `engine/promoted_config.py`

Core functions:

| Function | Purpose |
|----------|---------|
| `_find_latest_promoted_config(artifacts_dir, role)` | Scans `artifacts/<date>/run_*/promoted_configs/{role}.yaml` in reverse-chronological order; returns the most recent match or `None` |
| `load_promoted_config(role, ...)` | Loads base `strategy_overrides.yaml` + promoted YAML, deep-merges (promoted wins), returns merged dict |
| `maybe_apply_promoted_config()` | Entry point called at daemon startup; reads `AI_QUANT_PROMOTED_ROLE` env var, writes merged YAML, sets `AI_QUANT_STRATEGY_YAML` |

### Daemon Integration: `engine/daemon.py`

- `maybe_apply_promoted_config()` is called in `main()` **before** `StrategyManager.get()` 
- If a promoted config is found, `AI_QUANT_STRATEGY_YAML` is redirected to the merged file
- StrategyManager picks it up transparently — no changes needed to StrategyManager itself
- Startup log includes `promoted_role=` tag; alerts include the role in metadata
- Wrapped in try/except — promotion failures never block daemon startup

### Merge Semantics

```
base (strategy_overrides.yaml)  ←  promoted (factory promoted_configs/{role}.yaml)
                                     ↑ promoted takes precedence
```

- Uses existing `engine.utils.deep_merge()` (same as StrategyManager)
- Base config fills any keys the promoted config doesn't specify
- Sections like `modes:`, `symbols:` from base survive unless overridden

## Role-to-Daemon Mapping

| Paper Daemon | Env Var Value | Description |
|-------------|---------------|-------------|
| paper1 | `AI_QUANT_PROMOTED_ROLE=primary` | Best balanced score (PnL × (1-DD) × PF) |
| paper2 | `AI_QUANT_PROMOTED_ROLE=fallback` | Lowest drawdown with positive PnL |
| paper3 | `AI_QUANT_PROMOTED_ROLE=conservative` | Absolute lowest max drawdown |
| livepaper | *(not set)* | Unchanged, uses its own config |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_QUANT_PROMOTED_ROLE` | *(unset)* | `primary` \| `fallback` \| `conservative` |
| `AI_QUANT_ARTIFACTS_DIR` | `<project>/artifacts` | Root of factory artifacts tree |
| `AI_QUANT_STRATEGY_YAML` | `config/strategy_overrides.yaml` | Base config (existing) |

## Fallback Behaviour

1. `AI_QUANT_PROMOTED_ROLE` not set → no-op, daemon uses base config as before
2. Role set but no promoted config found → warning logged, base config used
3. Promoted YAML empty/invalid → warning logged, base config used
4. `promoted_config` module import fails → warning logged, daemon starts normally
5. Invalid role name → warning logged, ignored

## Tests

**New test file:** `tests/test_promoted_config_loading.py` — 21 tests

### `_find_latest_promoted_config` (9 tests)
- Finds most recent run across date directories
- Finds correct role within a run
- Returns None for missing/invalid role, empty artifacts, nonexistent dir
- Skips runs without promoted_configs/
- Handles multiple runs on same day (picks latest)
- Ignores non-date directories (`_effective_configs`, `registry`, etc.)

### `load_promoted_config` (5 tests)
- Merges promoted on top of base correctly
- Preserves base sections not in promoted (indicators, modes)
- Returns None for missing promoted / invalid role / empty YAML
- All three roles loadable independently

### `maybe_apply_promoted_config` (4 tests)
- No-op when env var not set
- Applies promoted role and sets AI_QUANT_STRATEGY_YAML
- Falls back gracefully when no promoted config exists
- Case-insensitive role handling

### Role mapping (2 tests)
- VALID_ROLES = {primary, fallback, conservative}
- Paper daemon mapping documentation

## Test Results

```
258 passed, 5 skipped in 4.40s
```

All tests pass. The 5 skips are pre-existing (optional dependencies: jsonschema, bt_runtime).

## File Changes

| File | Change |
|------|--------|
| `engine/promoted_config.py` | **New** — promoted config discovery, loading, merging |
| `engine/daemon.py` | Modified — calls `maybe_apply_promoted_config()` before StrategyManager init |
| `tests/test_promoted_config_loading.py` | **New** — 21 tests |
| `docs/validation/phaseC_daemon_integration.md` | **New** — this document |

## Usage Example

```bash
# Paper daemon 1 → primary role
AI_QUANT_MODE=paper AI_QUANT_PROMOTED_ROLE=primary python -m engine.daemon

# Paper daemon 2 → fallback role  
AI_QUANT_MODE=paper AI_QUANT_PROMOTED_ROLE=fallback python -m engine.daemon

# Paper daemon 3 → conservative role
AI_QUANT_MODE=paper AI_QUANT_PROMOTED_ROLE=conservative python -m engine.daemon

# Live paper → no promotion (unchanged)
AI_QUANT_MODE=paper python -m engine.daemon
```
