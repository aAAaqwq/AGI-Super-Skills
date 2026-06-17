# v5.7.1 Black Swan Defense — 2026-05-28 US-Iran Airstrike Post-Mortem

## Event

2026-05-28: US airstrikes on Iran nuclear facilities → BTC dropped ~$3k in 15 minutes.
Engine was running v5.7, had no anomaly detection. Several predictions made during the crash were directionally wrong because:
1. ATR spiked to 3-5x normal but regime detection only uses vol_ratio (relative to recent average)
2. Fear & Greed Index dropped below 25 (Extreme Fear) but engine ignored it
3. Volume shrinkage after the initial drop was misread as "stabilization" rather than "panic freeze"

## Post-Mortem File

Full analysis: `review-2026-05-29.md` in skill root.

## v5.7.1 Fixes Implemented (2 of 6, compilation blocked)

### P0-1: ATR Spike Detection (COMPLETED, code patched)

New function `atr_spike_detect(candles, atr_val, lookback=5, spike_threshold=1.5, consecutive=3)`:
- Returns `(is_spike, spike_ratio, consecutive_count)`
- Detects when ATR exceeds 1.5x its recent average for 3+ consecutive candles
- Integration: `detect_regime()` forces `HIGH_VOL` when spike detected
- Integration: `direction_rule_v5()` halves confidence when ATR spike active

### P0-2: FNG Extreme Fear Filter (COMPLETED, code patched)

When `fng_value < 25` (Extreme Fear):
- `BASE_W['v_reversal']` attenuated by 50% (0.8 → 0.4) — reversal signals unreliable during panic
- `BASE_W['decel']` attenuated by 30% (0.7 → 0.49) — deceleration patterns break in black swans
- Global BASE_W save/restore pattern to prevent cross-call pollution
- Returns `fng_black_swan=True` in result dict

### P0-3: News Shock Keyword Scanning (NOT YET IMPLEMENTED)

Planned: detect keywords from `news-risk-level.json` → cap confidence at 35%.

### Remaining Fixes (NOT YET IMPLEMENTED)

- P1-1: GARCH volatility clustering model
- P1-2: Circuit breaker (consecutive losses → pause)
- P2-1: News impact retrospective database

## Key Architecture Patterns

### BASE_W Save/Restore (Pollution Prevention)

```python
# FNG black swan filter
_saved_base_for_fng = BASE_W.copy()
BASE_W['v_reversal'] = saved_w_v_rev * 0.5  # attenuate
BASE_W['decel'] = saved_w_decel * 0.7        # attenuate
raw = combine_factors(factors, regime)
if _saved_base_for_fng is not None:
    BASE_W.update(_saved_base_for_fng)        # restore
```

### Return Value Extension

`direction_rule_v5()` expanded from 6-tuple to 7-tuple:
```python
return bias, strength, score, confidence, raw, conflict, fng_black_swan
```

### FNG Fetch Timing

FNG API call moved BEFORE `direction_rule_v5()` invocation in `run()` to avoid reference-before-assignment.

## Status

- Code: All patches applied to `5minbtc-engine-v5.7.py` (~820 lines)
- Version identifier: "5.7.1" in result dict
- New output fields: `atr_spike`, `fng_black_swan`
- **BLOCKED**: Compilation fails due to Python 3.11 Unicode strictness — see SKILL.md pitfall section
- Verification: Not yet run against live data
