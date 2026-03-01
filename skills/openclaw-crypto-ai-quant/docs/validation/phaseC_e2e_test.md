# Phase C — End-to-End Factory Pipeline Test (C3)

**Date:** 2026-02-14  
**File:** `tests/test_factory_e2e_pipeline.py`  
**Status:** ✅ ALL PASS (237 passed, 5 skipped in 4.76s — full suite)

## Summary

Comprehensive integration test validating the full factory pipeline's profile resolution, candidate promotion logic, edge cases, and profile aliasing — all without GPU or real candle data.

## Test Coverage

### (a) Profile Resolution — `TestProfileResolution` (6 tests)

| Test | What it validates |
|------|-------------------|
| `test_daily_profile_full_defaults` | `--profile daily` → tpe_trials=200000, shortlist_per_mode=20, shortlist_max_rank=150, num_candidates=5, plus non-profile defaults (interval, sort_by, tpe_batch, tpe_seed, promote_count, etc.) |
| `test_smoke_profile_full_defaults` | `--profile smoke` → tpe_trials=2000, shortlist_per_mode=3, shortlist_max_rank=20, num_candidates=2 |
| `test_deep_profile_full_defaults` | `--profile deep` → tpe_trials=2000000, shortlist_per_mode=30, shortlist_max_rank=400, num_candidates=10 |
| `test_weekly_profile_full_defaults` | `--profile weekly` → identical to deep |
| `test_explicit_cli_overrides_profile` | Explicit CLI flags override profile defaults |
| `test_unknown_profile_exits` | Unknown profile → SystemExit |

### (b) Promotion Integration — `TestPromotionIntegration` (5 tests)

| Test | What it validates |
|------|-------------------|
| `test_primary_has_best_balanced_score` | primary.yaml → candidate with highest `pnl × (1 - dd) × pf` |
| `test_fallback_has_lowest_dd_among_positive_pnl` | fallback.yaml → lowest max_drawdown_pct (positive PnL) |
| `test_conservative_has_absolute_lowest_dd` | conservative.yaml → absolute lowest DD |
| `test_all_three_roles_written_and_metadata_populated` | All 3 YAML files exist; metadata has config_id, promoted_path, balanced_score, etc. |
| `test_run_metadata_json_has_promotion_entries` | run_metadata.json round-trip: promotion section persists correctly |

### (c) Edge Cases — `TestPromotionEdgeCases` (7 tests)

| Test | What it validates |
|------|-------------------|
| `test_all_negative_pnl_no_promotion` | All negative PnL → skipped, no promoted_configs dir |
| `test_single_positive_pnl_gets_all_roles` | 1 positive candidate → gets primary + fallback + conservative |
| `test_promote_count_zero_skips` | promote_count=0 → skipped, no dir created |
| `test_twenty_candidates_only_top_3_promoted` | 20 candidates → exactly 3 YAML files; verifies balanced-score selection + DD selection |
| `test_zero_pnl_not_promoted` | PnL=0.0 is NOT positive → graceful skip |
| `test_empty_candidate_list` | Empty list → graceful skip |
| `test_promote_count_1_limits_output` | promote_count=1 → only primary.yaml written |

### (d) Weekly/Deep Alias — `TestWeeklyDeepAlias` (4 tests)

| Test | What it validates |
|------|-------------------|
| `test_profile_defaults_dict_identical` | `PROFILE_DEFAULTS["weekly"] == PROFILE_DEFAULTS["deep"]` |
| `test_parsed_args_identical` | Parsed args from both profiles match on all profile-controlled fields |
| `test_all_profile_keys_match_exactly` | Same key set, same values |
| `test_all_profiles_present` | All 4 profiles exist: smoke, daily, deep, weekly |

## Test Run Output

```
237 passed, 5 skipped in 4.76s
```

All 22 new tests in `test_factory_e2e_pipeline.py` pass. The 5 skips are pre-existing (jsonschema / bt_runtime not available in test env).
