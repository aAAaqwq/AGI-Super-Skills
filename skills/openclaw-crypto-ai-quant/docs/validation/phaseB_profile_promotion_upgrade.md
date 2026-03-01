# Phase B5 — Profile Upgrade & 20→3 Candidate Promotion

**Date:** 2026-02-14  
**Status:** ✅ Complete

## Summary

Updated factory run profiles to production-grade trial counts and added a candidate promotion step that selects the top 3 candidates for distinct deployment roles (primary, fallback, conservative).

## Changes

### Part 1: Profile Defaults (`PROFILE_DEFAULTS`)

| Profile | Key | Old | New |
|---------|-----|-----|-----|
| daily | tpe_trials | 5,000 | 200,000 |
| daily | num_candidates | 3 | 5 |
| daily | shortlist_per_mode | 10 | 20 |
| daily | shortlist_max_rank | 50 | 150 |
| deep | tpe_trials | 500,000 | 2,000,000 |
| deep | num_candidates | 5 | 10 |
| deep | shortlist_per_mode | 20 | 30 |
| deep | shortlist_max_rank | 200 | 400 |
| **weekly** (new) | — | — | Identical to `deep` |
| smoke | — | — | Unchanged |

- `weekly` is the canonical name going forward; `deep` is kept for backward compatibility.

### Part 2: Arg Parser

- `--profile` choices auto-include `weekly` via `sorted(PROFILE_DEFAULTS.keys())`.
- No manual change needed — verified it resolves to `['daily', 'deep', 'smoke', 'weekly']`.

### Part 3: Candidate Promotion (`_promote_candidates()`)

New function and CLI arguments added to `factory_run.py`:

- **CLI args:** `--promote-count` (default 3), `--promote-dir` (default `promoted_configs`)
- **Role selection logic:**
  - **PRIMARY**: highest balanced score = `PnL × (1 − max_dd) × profit_factor`
  - **FALLBACK**: lowest `max_drawdown_pct` among positive-PnL candidates (PnL tie-break)
  - **CONSERVATIVE**: absolute lowest `max_drawdown_pct` with positive PnL required
- **Output:** `promoted_configs/{primary,fallback,conservative}.yaml` copied from source configs
- **Metadata:** `meta["promotion"]` added to `run_metadata.json`
- **Skip behaviour:** `--promote-count 0` skips promotion entirely; no positive-PnL candidates also skips gracefully.

### Part 4: Tests

#### `tests/test_factory_run_profile.py` (7 tests)
- `test_profile_smoke_sets_trials_and_candidate_counts` — unchanged
- `test_profile_daily_sets_updated_values` — updated expectations
- `test_profile_deep_backward_compat` — updated expectations for new values
- `test_profile_weekly_values` — **new**
- `test_profile_weekly_matches_deep` — **new**
- `test_profile_does_not_override_explicit_values` — unchanged
- `test_all_profiles_present_in_defaults` — **new**

#### `tests/test_promote_candidates.py` (12 tests — all new)
- Role assignment: primary, fallback, conservative selection
- Negative-PnL exclusion
- YAML file output verification
- Custom promote dir
- Skip cases: promote_count=0, no positive PnL, empty candidates
- Single candidate fills all roles
- promote_count limits output count
- Metadata field verification

### Part 5: Test Results

```
19 passed in 0.05s
```

All 19 tests pass. Pre-existing failures in `test_kernel_decision_routing.py` (1 test) and `test_regime_gate_enforcement.py` (3 tests) are unrelated to this change.

## Files Modified

- `factory_run.py` — PROFILE_DEFAULTS, `_promote_candidates()`, CLI args, main pipeline integration
- `tests/test_factory_run_profile.py` — rewritten with updated expectations + new tests
- `tests/test_promote_candidates.py` — new file (12 tests)
- `docs/validation/phaseB_profile_promotion_upgrade.md` — this file
