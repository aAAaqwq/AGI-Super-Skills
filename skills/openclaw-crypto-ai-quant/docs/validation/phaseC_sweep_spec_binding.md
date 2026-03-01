# Phase C – Sweep Spec Profile Binding (C2)

**Date:** 2026-02-14
**Status:** ✅ Complete

## Problem

`factory_run.py` hard-coded `--sweep-spec` to `backtester/sweeps/smoke.yaml` as the argparse default, meaning daily/weekly/deep profiles still used the tiny 5-axis smoke spec unless operators manually passed `--sweep-spec`. This made production runs silently under-sweep.

## Changes

### `factory_run.py`

| Area | Before | After |
|---|---|---|
| `PROFILE_DEFAULTS` type | `dict[str, dict[str, int]]` | `dict[str, dict[str, int \| str]]` |
| `PROFILE_DEFAULTS["smoke"]` | no `sweep_spec` key | `"sweep_spec": "backtester/sweeps/smoke.yaml"` |
| `PROFILE_DEFAULTS["daily"]` | no `sweep_spec` key | `"sweep_spec": "backtester/sweeps/full_144v.yaml"` |
| `PROFILE_DEFAULTS["deep"]` | no `sweep_spec` key | `"sweep_spec": "backtester/sweeps/full_144v.yaml"` |
| `PROFILE_DEFAULTS["weekly"]` | no `sweep_spec` key | `"sweep_spec": "backtester/sweeps/full_144v.yaml"` |
| `--sweep-spec` argparse default | `"backtester/sweeps/smoke.yaml"` | `None` |
| `_apply_profile_defaults()` | always `int(v)` | `int(v) if isinstance(v, int) else v` — supports string defaults |

### Behaviour

- **Profile default kicks in** when `--sweep-spec` is not passed (argparse yields `None`, profile fills it).
- **Explicit `--sweep-spec`** still overrides the profile default (existing `getattr(args, k) is None` guard).
- **`weekly == deep`** invariant preserved (both map to `full_144v.yaml`).

### `tests/test_factory_run_profile.py`

Added 5 new tests:

| Test | Assertion |
|---|---|
| `test_smoke_profile_sweep_spec` | smoke → `smoke.yaml` |
| `test_daily_profile_sweep_spec` | daily → `full_144v.yaml` |
| `test_weekly_profile_sweep_spec` | weekly → `full_144v.yaml` |
| `test_deep_profile_sweep_spec` | deep → `full_144v.yaml` |
| `test_explicit_sweep_spec_overrides_profile` | explicit `--sweep-spec` wins over profile |

## Test Run

```
215 passed, 5 skipped in 4.71s
```

All existing tests continue to pass; 5 new C2-specific tests pass.
